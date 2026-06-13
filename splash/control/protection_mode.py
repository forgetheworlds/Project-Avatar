"""
protection_mode.py — Protection mode state machine for Splash water gun drone.

Protection Mode: Drone orbits a designated protected area (center_lat/lon, radius).
If ANY person enters the area, the drone:
  1. Breaks orbit and moves toward the intruder
  2. Tracks and aims the water gun
  3. Fires when within range and on-target
  4. Returns to orbit after engagement or when target leaves the area

This is NOT random spraying — targeted engagement only.
Returns to orbit after each engagement.

State Machine (sub-states of ORBITING drone state):
  IDLE → SCANNING → DETECTED → ENGAGING → RETURNING_TO_ORBIT → SCANNING

Battery-aware:
  > 30%   Full protection
  20-30%  Close-range engagement only (5m max)
  15-20%  Orbit only, no engagement
  < 15%   Return to home

Project Avatar — Splash water gun drone.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("splash.protection")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Battery thresholds (% remaining)
BATTERY_FULL = 30.0       # Full protection above 30%
BATTERY_CLOSE_RANGE = 20.0 # Close-range only at 20-30%
BATTERY_ORBIT_ONLY = 15.0  # No engagement at 15-20%
BATTERY_CRITICAL = 15.0    # RTB below 15%

# Engagement parameters
DEFAULT_ORBIT_RADIUS_M = 10.0
DEFAULT_ORBIT_ALTITUDE_M = 8.0
DEFAULT_PROTECT_RADIUS_M = 15.0   # Geofence radius (larger than orbit)
DEFAULT_ENGAGE_DISTANCE_M = 5.0   # Max distance to engage
DEFAULT_CLOSE_ENGAGE_M = 3.0      # Max distance when battery >20%
DEFAULT_BURST_MS = 500
MAX_SHOTS = 15                     # 15ml reservoir
HYSTERESIS_M = 1.0                 # ±1m hysteresis for geofence boundary

# State machine
TARGET_LOCK_FRAMES_REQUIRED = 5    # Frames before considering lock
AIM_STABLE_FRAMES_REQUIRED = 8     # Frames on-target before fire
ENGAGE_TIMEOUT_S = 15.0            # Max time per engagement
RETURN_TIMEOUT_S = 20.0            # Max time to return to orbit

# Scoring for target prioritization
SCORE_INBOUND_BONUS = 50.0
SCORE_CONFIDENCE_SCALE = 10.0
SCORE_CLOSEST_BONUS = 20.0


class ProtectionSubState(Enum):
    """Sub-states of protection mode while drone is in ORBITING state."""
    IDLE = auto()
    SCANNING = auto()
    DETECTED = auto()
    ENGAGING = auto()
    ENGAGE_WAITING = auto()    # Waiting for target to re-enter range
    RETURNING_TO_ORBIT = auto()
    ABORTED = auto()


@dataclass
class ProtectionContext:
    """Mutable context for protection mode."""
    # Protection zone
    center_lat: float = 0.0
    center_lon: float = 0.0
    protect_radius_m: float = DEFAULT_PROTECT_RADIUS_M
    orbit_radius_m: float = DEFAULT_ORBIT_RADIUS_M
    orbit_altitude_m: float = DEFAULT_ORBIT_ALTITUDE_M

    # Current engagement
    target_id: Optional[int] = None
    target_locked_frames: int = 0
    aim_stable_frames: int = 0
    engagement_start_time: float = 0.0
    return_start_time: float = 0.0
    shots_fired_this_cycle: int = 0
    total_shots_fired: int = 0

    # Last known target position
    target_lat: float = 0.0
    target_lon: float = 0.0
    target_alt: float = 0.0
    target_distance_m: float = 999.0
    target_speed_ms: float = 0.0
    target_heading_deg: float = 0.0

    # Engagement cooldown
    cooldown_until: float = 0.0
    cooldown_duration_s: float = 3.0  # 3s between bursts

    # Battery state (set externally from telemetry)
    battery_pct: float = 100.0

    def reset_engagement(self) -> None:
        """Reset engagement-specific state (keep zone config)."""
        self.target_id = None
        self.target_locked_frames = 0
        self.aim_stable_frames = 0
        self.engagement_start_time = 0.0
        self.return_start_time = 0.0
        self.shots_fired_this_cycle = 0
        self.target_lat = 0.0
        self.target_lon = 0.0
        self.target_alt = 0.0
        self.target_distance_m = 999.0
        self.target_speed_ms = 0.0
        self.target_heading_deg = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone": {
                "center": [self.center_lat, self.center_lon],
                "radius_m": self.protect_radius_m,
                "orbit_radius_m": self.orbit_radius_m,
            },
            "engagement": {
                "active": self.target_id is not None,
                "target_id": self.target_id,
                "shots_this_cycle": self.shots_fired_this_cycle,
                "total_shots": self.total_shots_fired,
                "remaining_ammo": MAX_SHOTS - self.total_shots_fired,
            },
            "battery_pct": self.battery_pct,
        }


class ProtectionMode:
    """Protection mode state machine — orchestrated by the main drone state machine.

    This runs as a sub-state machine while the drone is in ORBITING state.
    It outputs commands to: orbit, engage (aim + fire), and return to orbit.
    """

    def __init__(self) -> None:
        self.state: ProtectionSubState = ProtectionSubState.IDLE
        self.ctx = ProtectionContext()
        self._last_frame_time: float = 0.0
        self._frame_count: int = 0
        self._consecutive_detections: int = 0

        # Callbacks (set by the main state machine / MCP server)
        self.on_fire: Optional[Callable[[int], None]] = None
        self.on_aim: Optional[Callable[[float, float], None]] = None
        self.on_orbit_resume: Optional[Callable[[], None]] = None
        self.on_return_to_orbit: Optional[Callable[[], None]] = None
        self.on_abort: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, center_lat: float, center_lon: float,
              protect_radius_m: float = DEFAULT_PROTECT_RADIUS_M,
              orbit_radius_m: float = DEFAULT_ORBIT_RADIUS_M,
              orbit_altitude_m: float = DEFAULT_ORBIT_ALTITUDE_M) -> None:
        """Start protection mode with a defined zone."""
        self.state = ProtectionSubState.SCANNING
        self.ctx.center_lat = center_lat
        self.ctx.center_lon = center_lon
        self.ctx.protect_radius_m = protect_radius_m
        self.ctx.orbit_radius_m = orbit_radius_m
        self.ctx.orbit_altitude_m = orbit_altitude_m
        self.ctx.reset_engagement()
        logger.info(
            f"Protection mode START: center=({center_lat:.6f}, {center_lon:.6f}), "
            f"radius={protect_radius_m}m, orbit={orbit_radius_m}m@{orbit_altitude_m}m"
        )

    def stop(self) -> None:
        """Stop protection mode."""
        old_state = self.state
        self.state = ProtectionSubState.IDLE
        self.ctx.reset_engagement()
        logger.info(f"Protection mode STOP (was {old_state.name})")

    def update_battery(self, battery_pct: float) -> None:
        """Update battery percentage from telemetry."""
        self.ctx.battery_pct = battery_pct

    def get_effective_engage_distance(self) -> float:
        """Return max engagement distance based on battery level."""
        if self.ctx.battery_pct >= BATTERY_FULL:
            return DEFAULT_ENGAGE_DISTANCE_M
        elif self.ctx.battery_pct >= BATTERY_CLOSE_RANGE:
            return DEFAULT_CLOSE_ENGAGE_M
        else:
            return 0.0  # No engagement

    def process_detections(self, targets: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process CV pipeline detections and update state.

        Args:
            targets: List of target dicts with keys:
                id, lat, lon, alt, distance_m, speed_ms, heading_deg,
                confidence, color_label, bbox, pan_angle, tilt_angle, fire_command

        Returns:
            Action dict if a decision is needed, else None.
            Actions: {"action": "fire", "duration_ms": 500}
                     {"action": "aim", "pan": 45.0, "tilt": -10.0}
                     {"action": "orbit_resume"}
                     {"action": "rtb"}
        """
        self._frame_count += 1
        now = time.time()

        # Battery check
        if self.ctx.battery_pct < BATTERY_CRITICAL:
            logger.warning(f"Protection mode: battery critical ({self.ctx.battery_pct:.0f}%) — aborting")
            self.state = ProtectionSubState.ABORTED
            if self.on_abort:
                self.on_abort(f"Battery critical ({self.ctx.battery_pct:.0f}%)")
            return {"action": "rtb", "reason": "battery_critical"}

        if self.ctx.battery_pct < BATTERY_ORBIT_ONLY:
            if self.state in (ProtectionSubState.ENGAGING, ProtectionSubState.DETECTED):
                logger.info("Battery too low for engagement — returning to orbit")
                self.state = ProtectionSubState.RETURNING_TO_ORBIT
                self.ctx.return_start_time = now
            return {"action": "orbit_only", "reason": "battery_low"}

        # State machine
        if self.state == ProtectionSubState.SCANNING:
            return self._handle_scanning(targets, now)
        elif self.state == ProtectionSubState.DETECTED:
            return self._handle_detected(targets, now)
        elif self.state == ProtectionSubState.ENGAGING:
            return self._handle_engaging(targets, now)
        elif self.state == ProtectionSubState.ENGAGE_WAITING:
            return self._handle_engage_waiting(targets, now)
        elif self.state == ProtectionSubState.RETURNING_TO_ORBIT:
            return self._handle_returning(now)
        elif self.state == ProtectionSubState.ABORTED:
            return {"action": "rtb", "reason": "aborted"}

        return None

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_scanning(self, targets: list[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
        """SCANNING: Orbit around protected area, watch for intruders."""
        if not targets:
            self._consecutive_detections = 0
            return {"action": "continue_orbit"}

        # Filter targets inside the protection zone (with hysteresis)
        inside_zone = self._filter_inside_zone(targets)

        if not inside_zone:
            self._consecutive_detections = 0
            return {"action": "continue_orbit"}

        self._consecutive_detections += 1

        if self._consecutive_detections >= 3:  # Debounce: 3 consecutive frames
            # Prioritize targets
            target = self._prioritize_target(inside_zone)
            if target:
                logger.info(f"INTRUDER DETECTED: target #{target['id']} at {target['distance_m']:.1f}m")
                self.state = ProtectionSubState.DETECTED
                self.ctx.target_id = target["id"]
                self.ctx.engagement_start_time = now
                self.ctx.target_distance_m = target["distance_m"]
                self.ctx.target_lat = target["lat"]
                self.ctx.target_lon = target["lon"]
                self.ctx.target_speed_ms = target.get("speed_ms", 0.0)
                self.ctx.target_heading_deg = target.get("heading_deg", 0.0)
                return {"action": "break_orbit", "target": target}

        return {"action": "continue_orbit"}

    def _handle_detected(self, targets: list[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
        """DETECTED: Target identified. Move toward target, lock on."""
        # Find our target
        our_target = self._find_target_by_id(targets, self.ctx.target_id)
        if our_target is None:
            # Lost target — check if still in zone
            inside = self._filter_inside_zone(targets)
            if inside:
                # Re-target to closest
                target = self._prioritize_target(inside)
                if target:
                    self.ctx.target_id = target["id"]
                    our_target = target
                else:
                    self._consecutive_detections = 0
                    self.state = ProtectionSubState.SCANNING
                    return {"action": "return_to_orbit", "reason": "target_lost"}
            else:
                self.state = ProtectionSubState.SCANNING
                self._consecutive_detections = 0
                return {"action": "return_to_orbit", "reason": "target_left_zone"}

        # Check distance
        distance = our_target.get("distance_m", 999.0)
        effective_range = self.get_effective_engage_distance()

        if distance > (self.ctx.protect_radius_m + HYSTERESIS_M):
            # Target left the zone
            logger.info(f"Target #{our_target['id']} left protection zone")
            self.state = ProtectionSubState.RETURNING_TO_ORBIT
            self.ctx.return_start_time = now
            return {"action": "return_to_orbit", "reason": "target_left_zone"}

        if distance <= effective_range:
            # Close enough — begin engagement
            self.state = ProtectionSubState.ENGAGING
            self.ctx.aim_stable_frames = 0
            return self._handle_engaging(targets, now)

        # Still tracking, move closer
        return {"action": "approach_target", "target": our_target}

    def _handle_engaging(self, targets: list[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
        """ENGAGING: Track, aim, and fire at the target."""
        # Check timeout
        if now - self.ctx.engagement_start_time > ENGAGE_TIMEOUT_S:
            logger.info(f"Engagement timeout ({ENGAGE_TIMEOUT_S}s) — returning to orbit")
            self.state = ProtectionSubState.RETURNING_TO_ORBIT
            self.ctx.return_start_time = now
            return {"action": "return_to_orbit", "reason": "timeout"}

        # Check ammo
        max_shots = 15  # Placeholder, should come from payload
        if self.ctx.total_shots_fired >= max_shots:
            logger.warning("OUT OF AMMO — returning to orbit")
            self.state = ProtectionSubState.RETURNING_TO_ORBIT
            self.ctx.return_start_time = now
            return {"action": "return_to_orbit", "reason": "out_of_ammo"}

        # Find our target
        our_target = self._find_target_by_id(targets, self.ctx.target_id)
        if our_target is None:
            # Lost during engagement — wait briefly
            self.ctx.aim_stable_frames = 0
            if self.ctx.target_locked_frames < TARGET_LOCK_FRAMES_REQUIRED:
                self.state = ProtectionSubState.DETECTED  # Go back to detection
                return {"action": "reacquire_target"}

            self.state = ProtectionSubState.ENGAGE_WAITING
            return {"action": "wait_for_target"}

        # Check distance
        distance = our_target.get("distance_m", 999.0)
        effective_range = self.get_effective_engage_distance()

        if distance > effective_range + HYSTERESIS_M:
            # Target moved out of range — wait or follow
            if distance > self.ctx.protect_radius_m:
                self.state = ProtectionSubState.RETURNING_TO_ORBIT
                return {"action": "return_to_orbit", "reason": "target_out_of_range"}
            self.state = ProtectionSubState.DETECTED
            return {"action": "approach_target", "target": our_target}

        # Check cooldown
        if now < self.ctx.cooldown_until:
            return {"action": "track_only", "target": our_target}

        # Aim and check if stable
        pan_angle = our_target.get("pan_angle", 0.0)
        tilt_angle = our_target.get("tilt_angle", 0.0)
        fire_command = our_target.get("fire_command", False)

        if self.on_aim:
            self.on_aim(pan_angle, tilt_angle)

        if fire_command:
            self.ctx.aim_stable_frames += 1
            if self.ctx.aim_stable_frames >= AIM_STABLE_FRAMES_REQUIRED:
                # FIRE!
                self.ctx.shots_fired_this_cycle += 1
                self.ctx.total_shots_fired += 1
                self.ctx.aim_stable_frames = 0
                self.ctx.cooldown_until = now + self.ctx.cooldown_duration_s

                logger.info(
                    f"FIRE at target #{our_target['id']} — "
                    f"shot #{self.ctx.total_shots_fired}, "
                    f"{self.ctx.total_shots_fired}/{max_shots} ammo"
                )

                if self.on_fire:
                    self.on_fire(DEFAULT_BURST_MS)

                return {"action": "fire", "duration_ms": DEFAULT_BURST_MS}
        else:
            self.ctx.aim_stable_frames = max(0, self.ctx.aim_stable_frames - 1)

        return {"action": "track_and_aim", "target": our_target}

    def _handle_engage_waiting(self, targets: list[Dict[str, Any]], now: float) -> Optional[Dict[str, Any]]:
        """ENGAGE_WAITING: Brief pause waiting for target to reappear."""
        our_target = self._find_target_by_id(targets, self.ctx.target_id)
        if our_target:
            self.state = ProtectionSubState.ENGAGING
            return self._handle_engaging(targets, now)

        # Give up after short timeout
        if (now - self.ctx.engagement_start_time) > ENGAGE_TIMEOUT_S:
            self.state = ProtectionSubState.RETURNING_TO_ORBIT
            self.ctx.return_start_time = now
            return {"action": "return_to_orbit", "reason": "target_disappeared"}

        return {"action": "wait_for_target"}

    def _handle_returning(self, now: float) -> Optional[Dict[str, Any]]:
        """RETURNING_TO_ORBIT: Fly back to orbit path."""
        if self.on_return_to_orbit:
            self.on_return_to_orbit()

        # Check timeout
        if now - self.ctx.return_start_time > RETURN_TIMEOUT_S:
            self.state = ProtectionSubState.SCANNING
            self.ctx.reset_engagement()
            logger.info("Return to orbit complete — resuming scanning")
            return {"action": "orbit_resume"}

        # If we see a new intruder while returning, we can re-engage
        # (if battery allows) — handled by main state machine via process_detections
        self.state = ProtectionSubState.SCANNING
        self.ctx.reset_engagement()
        logger.info("Returned to orbit — resuming scanning")
        return {"action": "orbit_resume"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_inside_zone(self, targets: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Filter targets to those inside protection zone (with hysteresis)."""
        inside = []
        for t in targets:
            distance = t.get("distance_m", 999.0)
            # Use hysteresis: once inside, target must leave by more than HYSTERESIS_M
            effective_radius = self.ctx.protect_radius_m
            if self.ctx.target_id == t.get("id"):
                effective_radius += HYSTERESIS_M  # Don't lose target at boundary
            if distance <= effective_radius:
                inside.append(t)
        return inside

    def _prioritize_target(self, targets: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Score and select the highest-priority target.

        Scoring:
          +50 inbound (moving toward center)
          +20/confidence  (closer targets)
          +10/confidence  (YOLO confidence tiebreaker)
        """
        best_score = -1.0
        best_target = None

        for t in targets:
            score = t.get("confidence", 0.0) * SCORE_CONFIDENCE_SCALE

            # Inbound bonus
            speed = t.get("speed_ms", 0.0)
            heading = t.get("heading_deg", 0.0)
            if speed > 0.5:
                # Check if moving toward center
                tx, ty = t.get("lat", 0.0), t.get("lon", 0.0)
                cx, cy = self.ctx.center_lat, self.ctx.center_lon
                # Simple direction check: if heading roughly toward center
                # (inbound detection via bearing calculation)
                score += SCORE_INBOUND_BONUS if self._is_inbound(t) else 0.0

            # Closest bonus
            distance = t.get("distance_m", 999.0)
            if distance > 0 and distance < 20:
                score += SCORE_CLOSEST_BONUS * (1.0 - distance / 20.0)

            if score > best_score:
                best_score = score
                best_target = t

        return best_target

    def _is_inbound(self, target: Dict[str, Any]) -> bool:
        """Check if target is moving toward the protection zone center."""
        speed = target.get("speed_ms", 0.0)
        if speed < 0.5:
            return False

        # Calculate bearing from target to center
        t_lat = math.radians(target.get("lat", 0.0))
        t_lon = math.radians(target.get("lon", 0.0))
        c_lat = math.radians(self.ctx.center_lat)
        c_lon = math.radians(self.ctx.center_lon)

        d_lon = c_lon - t_lon
        bearing_to_center = math.degrees(
            math.atan2(
                math.sin(d_lon) * math.cos(c_lat),
                math.cos(t_lat) * math.sin(c_lat) -
                math.sin(t_lat) * math.cos(c_lat) * math.cos(d_lon)
            )
        )
        # Normalize
        bearing_to_center = (bearing_to_center + 360) % 360

        # If target heading within ±90° of bearing to center, it's inbound
        heading = target.get("heading_deg", 0.0)
        diff = abs(heading - bearing_to_center)
        if diff > 180:
            diff = 360 - diff
        return diff < 90.0

    def _find_target_by_id(self, targets: list[Dict[str, Any]],
                           target_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Find a target by its track ID."""
        if target_id is None:
            return None
        for t in targets:
            if t.get("id") == target_id:
                return t
        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status_dict(self) -> Dict[str, Any]:
        """Full status for telemetry."""
        state_name = self.state.name
        engage_dist = self.get_effective_engage_distance()
        remaining_shots = max(0, MAX_SHOTS - self.ctx.total_shots_fired)

        return {
            "protection_active": self.state != ProtectionSubState.IDLE,
            "sub_state": state_name,
            "zone": {
                "center": [self.ctx.center_lat, self.ctx.center_lon],
                "protect_radius_m": self.ctx.protect_radius_m,
                "orbit_radius_m": self.ctx.orbit_radius_m,
            },
            "engagement": {
                "active": self.ctx.target_id is not None,
                "target_id": self.ctx.target_id,
                "shots_this_cycle": self.ctx.shots_fired_this_cycle,
                "total_shots": self.ctx.total_shots_fired,
                "remaining_ammo": remaining_shots,
                "effective_range_m": engage_dist,
                "distance_to_target_m": round(self.ctx.target_distance_m, 1),
            },
            "battery": {
                "pct": self.ctx.battery_pct,
                "full_protection": self.ctx.battery_pct >= BATTERY_FULL,
                "close_range_only": BATTERY_CLOSE_RANGE <= self.ctx.battery_pct < BATTERY_FULL,
                "orbit_only": BATTERY_ORBIT_ONLY <= self.ctx.battery_pct < BATTERY_CLOSE_RANGE,
                "critical": self.ctx.battery_pct < BATTERY_CRITICAL,
            },
        }
