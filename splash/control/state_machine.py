"""
state_machine.py — Drone state management for Splash MCP server.

States: IDLE → ARMED → FLYING → (ORBITING | ENGAGING) → RETURNING → IDLE
Emergency: any state → DISARMED

Battery-aware operation:
  > 30%   Full operations
  20-30%  Close-range engagement only
  15-20%  Orbit-only, no engagement
  < 15%   Force RETURN, prevent re-engagement

Ammo tracking: 15 shots per 15ml reservoir

Project Avatar — Splash water gun drone MCP tool server.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, Any

logger = logging.getLogger("splash.state")


# ---------------------------------------------------------------------------
# Battery thresholds
# ---------------------------------------------------------------------------

BATTERY_FULL = 30.0         # %
BATTERY_CLOSE_RANGE = 20.0
BATTERY_ORBIT_ONLY = 15.0
BATTERY_CRITICAL = 15.0
MAX_AMMO = 15                # 15ml reservoir = ~15 shots


class DroneState(Enum):
    """Valid drone operational states."""
    IDLE      = auto()   # Not armed, on ground
    ARMED     = auto()   # Armed, on ground, ready for takeoff
    FLYING    = auto()   # In flight (GUIDED mode)
    TAKING_OFF = auto()  # Transitioning: armed → flying
    ORBITING  = auto()   # In CIRCLE mode orbiting a point
    ENGAGING  = auto()   # Track+aim+fire active
    LANDING   = auto()   # Transitioning: flying → landed
    RETURNING = auto()   # RTL active, returning to home
    DISARMED  = auto()   # Emergency disarm (failsafe)
    ERROR     = auto()   # Faulted / lost connection


# Valid state transitions
VALID_TRANSITIONS: Dict[DroneState, set[DroneState]] = {
    DroneState.IDLE:      {DroneState.ARMED, DroneState.ERROR},
    DroneState.ARMED:     {DroneState.TAKING_OFF, DroneState.DISARMED,
                           DroneState.IDLE, DroneState.ERROR},
    DroneState.TAKING_OFF:{DroneState.FLYING, DroneState.LANDING,
                           DroneState.ERROR},
    DroneState.FLYING:    {DroneState.ORBITING, DroneState.ENGAGING,
                           DroneState.LANDING, DroneState.RETURNING,
                           DroneState.ERROR, DroneState.DISARMED},
    DroneState.ORBITING:  {DroneState.FLYING, DroneState.ENGAGING,
                           DroneState.LANDING, DroneState.RETURNING,
                           DroneState.ERROR, DroneState.DISARMED},
    DroneState.ENGAGING:  {DroneState.FLYING, DroneState.ORBITING,
                           DroneState.LANDING, DroneState.RETURNING,
                           DroneState.ERROR, DroneState.DISARMED},
    DroneState.LANDING:   {DroneState.IDLE, DroneState.ERROR},
    DroneState.RETURNING: {DroneState.IDLE, DroneState.LANDING,
                           DroneState.ERROR},
    DroneState.DISARMED:  {DroneState.IDLE, DroneState.ERROR},
    DroneState.ERROR:     set(),  # Manual reset only
}

# States that allow flight commands
FLYING_STATES = {
    DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING,
    DroneState.TAKING_OFF, DroneState.RETURNING, DroneState.LANDING,
}

# States considered "in air"
AIRBORNE_STATES = {
    DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING,
    DroneState.TAKING_OFF, DroneState.RETURNING, DroneState.LANDING,
}


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class StateGuardError(Exception):
    """Raised when a command is issued from an invalid state."""
    pass


class BatteryGuardError(Exception):
    """Raised when battery level prevents a command."""
    pass


class AmmoGuardError(Exception):
    """Raised when ammo is depleted."""
    pass


@dataclass
class DroneContext:
    """Mutable context carried with the drone state machine.

    Stores mission parameters, active targets, protection zone info,
    battery state, and ammo tracking.
    """
    # Current mission parameters
    home_lat: float = 0.0
    home_lon: float = 0.0
    takeoff_alt: float = 2.5
    target_lat: float = 0.0
    target_lon: float = 0.0
    target_alt: float = 0.0

    # Orbit parameters
    orbit_center_lat: float = 0.0
    orbit_center_lon: float = 0.0
    orbit_radius_m: float = 10.0
    orbit_altitude_m: float = 10.0

    # Protection zone
    protect_center_lat: float = 0.0
    protect_center_lon: float = 0.0
    protect_radius_m: float = 20.0

    # Target info
    target_description: Optional[str] = None
    target_acquired: bool = False

    # Ammo tracking
    ammo_remaining: int = MAX_AMMO
    shots_fired: int = 0

    # Battery
    battery_pct: float = 100.0

    # Connection health
    last_heartbeat: float = field(default_factory=time.time)
    telemetry_age_s: float = 999.0

    # Protection mode sub-state machine reference (optional)
    protection_mode: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "home_lat": self.home_lat,
            "home_lon": self.home_lon,
            "takeoff_alt": self.takeoff_alt,
            "target_description": self.target_description,
            "target_acquired": self.target_acquired,
            "shots_fired": self.shots_fired,
            "ammo_remaining": self.ammo_remaining,
            "battery_pct": self.battery_pct,
            "battery_level": self.battery_level_str(),
            "protect_zone": {
                "center": [self.protect_center_lat, self.protect_center_lon],
                "radius_m": self.protect_radius_m,
            } if self.protect_center_lat != 0 else None,
        }

    def battery_level_str(self) -> str:
        """Human-readable battery level description."""
        if self.battery_pct >= BATTERY_FULL:
            return "full"
        elif self.battery_pct >= BATTERY_CLOSE_RANGE:
            return "close_range_only"
        elif self.battery_pct >= BATTERY_ORBIT_ONLY:
            return "orbit_only"
        else:
            return "critical"

    def can_engage(self) -> bool:
        """Check if battery and ammo allow engagement."""
        if self.battery_pct < BATTERY_CLOSE_RANGE:
            return False
        if self.ammo_remaining <= 0:
            return False
        return True

    def use_ammo(self, count: int = 1) -> None:
        """Consume ammo. Tracks shots_fired and ammo_remaining."""
        used = min(count, self.ammo_remaining)
        self.ammo_remaining -= used
        self.shots_fired += used

    def update_battery(self, pct: float) -> None:
        """Update battery percentage and auto-return if critical."""
        self.battery_pct = pct


class StateMachine:
    """Thread-safe drone state machine with transition guards and battery awareness."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: DroneState = DroneState.IDLE
        self.context = DroneContext()
        self._transition_history: list[tuple[DroneState, DroneState, float]] = []

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def state(self) -> DroneState:
        """Current state (thread-safe read)."""
        with self._lock:
            return self._state

    @property
    def state_name(self) -> str:
        """Human-readable state name."""
        return self.state.name

    # ------------------------------------------------------------------
    # Transition
    # ------------------------------------------------------------------

    def transition(self, to_state: DroneState) -> None:
        """Attempt to transition to a new state.

        Raises StateTransitionError if the transition is not allowed.
        """
        with self._lock:
            from_state = self._state
            allowed = VALID_TRANSITIONS.get(from_state, set())

            if to_state not in allowed:
                raise StateTransitionError(
                    f"Cannot transition from {from_state.name} → {to_state.name}. "
                    f"Allowed: {[s.name for s in allowed]}"
                )

            self._state = to_state
            self._transition_history.append((from_state, to_state, time.time()))
            logger.info(f"State: {from_state.name} → {to_state.name}")

    def force_state(self, new_state: DroneState) -> None:
        """Override state without transition validation (emergency use)."""
        with self._lock:
            old = self._state
            self._state = new_state
            self._transition_history.append((old, new_state, time.time()))
            logger.warning(f"State FORCED: {old.name} → {new_state.name}")

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def require_state(self, *allowed: DroneState) -> None:
        """Raise StateGuardError if current state not in allowed set."""
        if self.state not in allowed:
            raise StateGuardError(
                f"Command requires state in {[s.name for s in allowed]}, "
                f"currently {self.state.name}"
            )

    def guard_battery(self, require_engage: bool = False) -> None:
        """Battery-aware guard. Raises BatteryGuardError if battery too low.

        Args:
            require_engage: If True, requires battery >= CLOSE_RANGE for engagement.
                            If False, checks only CRITICAL threshold.
        """
        if require_engage and not self.context.can_engage():
            raise BatteryGuardError(
                f"Cannot engage: battery={self.context.battery_pct:.0f}%, "
                f"ammo={self.context.ammo_remaining}. "
                f"Need battery >= {BATTERY_CLOSE_RANGE:.0f}% and ammo > 0."
            )
        if self.context.battery_pct < BATTERY_CRITICAL:
            raise BatteryGuardError(
                f"Battery critical ({self.context.battery_pct:.0f}% < "
                f"{BATTERY_CRITICAL:.0f}%) — RTB required."
            )

    def guard_ammo(self, require: int = 1) -> None:
        """Raise AmmoGuardError if insufficient ammo."""
        if self.context.ammo_remaining < require:
            raise AmmoGuardError(
                f"Insufficient ammo: {self.context.ammo_remaining} remaining, "
                f"{require} required."
            )

    def is_airborne(self) -> bool:
        return self.state in AIRBORNE_STATES

    def is_flying(self) -> bool:
        return self.state in FLYING_STATES

    def can_arm(self) -> bool:
        return self.state in {DroneState.IDLE, DroneState.DISARMED}

    # ------------------------------------------------------------------
    # Convenience transitions
    # ------------------------------------------------------------------

    def set_arming(self) -> None:
        self.transition(DroneState.ARMED)

    def set_taking_off(self) -> None:
        self.transition(DroneState.TAKING_OFF)

    def set_flying(self) -> None:
        # Can come from TAKING_OFF or other in-air states
        if self.state != DroneState.FLYING:
            if self.state == DroneState.TAKING_OFF:
                self.transition(DroneState.FLYING)
            else:
                # Force for recovery from ORBITING/ENGAGING without landing
                self.force_state(DroneState.FLYING)

    def set_orbiting(self) -> None:
        if self.state != DroneState.ORBITING:
            self.transition(DroneState.ORBITING)

    def set_engaging(self) -> None:
        # Battery + ammo guard
        self.guard_battery(require_engage=True)
        self.guard_ammo()
        if self.state != DroneState.ENGAGING:
            self.transition(DroneState.ENGAGING)

    def set_landing(self) -> None:
        if self.state != DroneState.LANDING:
            if DroneState.LANDING in VALID_TRANSITIONS.get(self.state, set()):
                self.transition(DroneState.LANDING)
            else:
                self.force_state(DroneState.LANDING)

    def set_returning(self) -> None:
        if self.state != DroneState.RETURNING:
            if DroneState.RETURNING in VALID_TRANSITIONS.get(self.state, set()):
                self.transition(DroneState.RETURNING)
            else:
                self.force_state(DroneState.RETURNING)

    def set_idle(self) -> None:
        if self.state != DroneState.IDLE:
            if DroneState.IDLE in VALID_TRANSITIONS.get(self.state, set()):
                self.transition(DroneState.IDLE)
            else:
                self.force_state(DroneState.IDLE)

    def set_disarmed(self) -> None:
        if self.state != DroneState.DISARMED:
            if DroneState.DISARMED in VALID_TRANSITIONS.get(self.state, set()):
                self.transition(DroneState.DISARMED)
            else:
                self.force_state(DroneState.DISARMED)

    def set_error(self, reason: str = "") -> None:
        logger.error(f"Drone ERROR: {reason}")
        if self.state != DroneState.ERROR:
            self.force_state(DroneState.ERROR)

    # ------------------------------------------------------------------
    # Battery monitoring helper
    # ------------------------------------------------------------------

    def check_battery_for_state(self) -> Optional[DroneState]:
        """Check battery and suggest forced state transition.

        Returns:
            DroneState.RETURNING if battery critical and airborne,
            DroneState.LANDING if battery critical and near ground,
            None if battery OK.
        """
        if self.context.battery_pct < BATTERY_CRITICAL and self.is_airborne():
            logger.warning(
                f"Battery CRITICAL ({self.context.battery_pct:.0f}%) — "
                f"forcing auto-RTB"
            )
            if self.state in (DroneState.FLYING, DroneState.ORBITING,
                              DroneState.ENGAGING):
                return DroneState.RETURNING
        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status_dict(self) -> Dict[str, Any]:
        """Full status report for MCP responses."""
        with self._lock:
            return {
                "state": self._state.name,
                "is_airborne": self._state in AIRBORNE_STATES,
                "context": self.context.to_dict(),
                "transitions": len(self._transition_history),
            }

    def recent_transitions(self, n: int = 10) -> list[str]:
        """Last N transitions as human-readable strings."""
        with self._lock:
            recent = self._transition_history[-n:]
        return [
            f"{f.name} → {t.name} ({ts:.0f}s ago)"
            for f, t, ts in recent
        ]
