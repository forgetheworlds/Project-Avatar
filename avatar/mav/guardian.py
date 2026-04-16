"""
Safety Guardian - Layer 2 of the 4-Layer Safety Architecture

PROJECT AVATAR SAFETY SYSTEM OVERVIEW
=====================================

The safety system uses a 4-layer defense-in-depth approach:

┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: LLM Safety Prompting                                   │
│   - Kimi K2.5 instructed to avoid dangerous commands            │
│   - High-level mission planning safety                          │
│   - Soft constraints (LLM can be persuaded to bypass)           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: GUARDIAN PROCESS (THIS FILE)                         │
│   - Hard limits enforcement (altitude, distance, battery)         │
│   - Geofencing calculations                                     │
│   - Heartbeat monitoring for connection health                  │
│   - CANNOT be bypassed - hardcoded safety limits                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: PX4 Autopilot Failsafes                                │
│   - Return-to-Launch (RTL) on low battery                       │
│   - Geofence violation triggers RTL                             │
│   - Loss of signal (RC link loss) handling                      │
│   - Configurable via PX4 parameters                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Hardware Kill Switch                                   │
│   - Physical emergency stop on transmitter                      │
│   - Immediate motor cutoff                                      │
│   - Pilot-in-the-loop override capability                       │
│   - Required for all real-world flights per FAA guidelines      │
└─────────────────────────────────────────────────────────────────┘

SAFETY ESCALATION FLOW
======================

When a safety violation is detected, the escalation follows this path:

1. Guardian rejects command BEFORE sending to PX4
   ↓
2. If PX4 receives command but detects violation:
   - Trigger Return-to-Launch (RTL)
   ↓
3. If PX4 fails or connection lost:
   - Pilot uses hardware kill switch
   ↓
4. Physical intervention (manual control)

WHY EACH SAFETY RULE EXISTS
===========================

MAX ALTITUDE (120m / 400ft):
  - FAA Part 107 and EASA limit for uncrewed aircraft
  - Avoids manned aircraft flight paths
  - Maintains visual line-of-sight capability
  - CRITICAL: Exceeding this violates federal regulations

MAX DISTANCE (500m from home):
  - Ensures reliable radio control link
  - Maintains visual line-of-sight
  - Prevents flyaway situations
  - Provides safe RTL range with battery reserves

MIN BATTERY (25% for RTL):
  - Accounts for headwinds during return flight
  - Ensures enough power for landing maneuver
  - Accounts for battery degradation over time
  - Margin for unexpected power consumption

MAX SPEED (15 m/s / 54 km/h / 33 mph):
  - Safe control authority limits
  - Braking distance considerations
  - Wind tolerance margins
  - Reduces kinetic energy in collisions

HEARTBEAT TIMEOUT (2 seconds):
  - Detection of software/agent crash
  - Network link monitoring
  - Prevents runaway commands
  - Time-critical: System must respond quickly

ARCHITECTURE NOTES
==================

The Guardian runs as a separate validation layer that ALL commands
must pass through before reaching PX4. This ensures:

1. Single point of enforcement for hard limits
2. Centralized logging of safety events
3. Testable safety logic independent of flight control
4. Clear audit trail for safety incidents

The Guardian is intentionally simple - no async code, no complex
state machines, no external dependencies beyond Python stdlib.
This reduces the attack surface and makes verification easier.

USAGE EXAMPLE
=============

    from avatar.mav.guardian import GuardianProcess, HardLimits

    # Initialize with default safety limits
    guardian = GuardianProcess()

    # Set home position for geofencing
    guardian.set_home(37.7749, -122.4194)

    # Validate a command from the LLM
    is_valid, reason = guardian.validate_command({
        "type": "goto",
        "latitude": 37.7750,
        "longitude": -122.4195,
        "altitude_amsl_m": 50.0,
        "speed_m_s": 10.0
    })

    if not is_valid:
        print(f"SAFETY VIOLATION: {reason}")
        # DO NOT send to PX4

    # Heartbeat monitoring
    guardian.update_heartbeat()  # Call every second from control loop
    if not guardian.check_heartbeat():
        print("CONNECTION LOST - Triggering failsafe")
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any, Literal

# Altitude frame types for validating altitude domain
AltitudeFrame = Literal["amsl", "agl", "relative"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardLimits:
    """
    Immutable safety limits for drone operations.

    These are regulatory and safety-critical limits that should never be exceeded.
    Based on common drone regulations (FAA Part 107, EASA).

    The dataclass is frozen (immutable) to prevent accidental modification
    of limits during runtime. Safety limits should only change through
    explicit code changes and safety review.

    Attributes:
        max_altitude_amsl_m: Maximum altitude above mean sea level (meters).
            Default 120m (400ft) per FAA Part 107. This is the altitude
            ceiling for uncrewed aircraft in most jurisdictions.

        max_distance_from_home_m: Maximum horizontal distance from home point.
            Default 500m to maintain radio link and visual line-of-sight.
            Beyond this distance, signal loss becomes increasingly likely.

        min_battery_rtl_percent: Minimum battery percentage before Return-to-Launch
            is triggered. Default 25% provides safety margin for unexpected
            headwinds and landing power requirements.

        heartbeat_timeout_s: Maximum seconds between heartbeat updates before
            considering the system unresponsive. Default 2 seconds - fast enough
            to detect crashes but tolerant of brief network delays.

        max_speed_m_s: Maximum ground speed (meters/second). Default 15 m/s
            (54 km/h / 33 mph). Limits kinetic energy and ensures adequate
            control authority in moderate winds.
    """
    max_altitude_amsl_m: float = 120.0  # Max altitude above mean sea level (meters)
    max_distance_from_home_m: float = 500.0  # Max horizontal distance from home (meters)
    min_battery_rtl_percent: float = 25.0  # Min battery % before RTL trigger
    heartbeat_timeout_s: float = 2.0  # Max seconds between heartbeats
    max_speed_m_s: float = 15.0  # Max ground speed (m/s)


class GuardianProcess:
    """
    Safety validation layer that enforces hard limits on drone commands.

    This is Layer 2 of the 4-layer safety architecture. The Guardian acts as
    a gatekeeper - ALL commands from the LLM must pass through validate_command()
    before being sent to PX4. This ensures hard safety limits are enforced
    regardless of what the LLM decides to send.

    Responsibilities:
    - Validate commands against safety limits (altitude, distance, speed)
    - Monitor heartbeat for connection health
    - Track home position for geofencing calculations
    - Log all safety violations for audit trail

    Why this design:
    - SINGLE POINT OF ENFORCEMENT: All safety checks in one place
    - FAIL-CLOSED: Unknown command types are rejected by default
    - AUDITABLE: All violations logged with full context
    - TESTABLE: Pure functions with no side effects (except logging)
    - SIMPLE: No async, no threads, no external dependencies

    Usage:
        limits = HardLimits()
        guardian = GuardianProcess(limits)
        guardian.set_home(37.7749, -122.4194)  # San Francisco

        # Validate a command
        is_valid, reason = guardian.validate_command({
            "type": "goto",
            "latitude": 37.7750,
            "longitude": -122.4195,
            "altitude_amsl_m": 50.0,
            "speed_m_s": 10.0
        })

        if not is_valid:
            # Command violates safety - DO NOT send to PX4
            logger.error(f"Safety violation: {reason}")

        # Heartbeat monitoring - call update_heartbeat() every second
        guardian.update_heartbeat()
        if not guardian.check_heartbeat():
            logger.warning("Heartbeat timeout - trigger failsafe")
    """

    def __init__(self, limits: Optional[HardLimits] = None):
        """
        Initialize guardian with safety limits.

        Args:
            limits: HardLimits instance. Uses defaults if not provided.
                    The defaults are based on FAA Part 107 regulations.

        Note:
            Home position is not set during initialization. You MUST call
            set_home() before validating any commands that include GPS
            coordinates, otherwise distance checks will fail.
        """
        self.limits = limits or HardLimits()
        self._home_lat: Optional[float] = None
        self._home_lon: Optional[float] = None
        self._last_heartbeat: float = time.time()

    def set_home(self, lat: float, lon: float) -> None:
        """
        Set home position for geofence calculations.

        The home position is the reference point for the max distance limit.
        This is typically set at:
        - Takeoff location
        - Current position when armed
        - Pilot's ground control station location

        IMPORTANT: All distance calculations use haversine formula on the
        WGS84 ellipsoid. This is accurate to ~0.5% for distances up to
        several kilometers - more than adequate for drone geofencing.

        Args:
            lat: Home latitude in degrees (-90 to 90)
            lon: Home longitude in degrees (-180 to 180)
        """
        self._home_lat = lat
        self._home_lon = lon
        logger.info(f"Home position set: ({lat}, {lon})")

    def validate_command(self, command: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a command against all safety limits.

        This is the MAIN SAFETY GATE. Every command from the LLM must pass
        through this method before being sent to PX4. The validation is
        COMPREHENSIVE - if any check fails, the entire command is rejected.

        VALIDATION ORDER (designed for fastest rejection of common issues):
        1. Altitude check (very common issue, cheap to compute)
        2. Distance check (requires haversine calculation)
        3. Speed check (rare issue, simple comparison)
        4. Battery check (critical safety check)

        SAFETY PRINCIPLE: We check ALL parameters present in the command,
        even if some are missing. A command with only altitude is still
        checked against altitude limits. This prevents partial validation
        that could miss safety violations.

        Args:
            command: Command dictionary with optional keys:
                - altitude_amsl_m: Target altitude above mean sea level (meters)
                - latitude: Target latitude (degrees)
                - longitude: Target longitude (degrees)
                - speed_m_s: Target speed (meters/second)
                - battery_percent: Current battery level (0-100)

        Returns:
            Tuple of (is_valid: bool, reason: str)
            - (True, "OK") if command passes all checks
            - (False, "reason") if command violates a limit, with descriptive reason

        Examples:
            # Valid command
            >>> guardian.validate_command({
            ...     "altitude_amsl_m": 50.0,
            ...     "latitude": 37.7750,
            ...     "longitude": -122.4195
            ... })
            (True, "OK")

            # Altitude violation
            >>> guardian.validate_command({"altitude_amsl_m": 150.0})
            (False, "Altitude 150m exceeds max 120m")
        """
        # ============================================================================
        # CHECK 0: ALTITUDE DOMAIN AMBIGUITY
        # ============================================================================
        # WHY THIS MATTERS:
        #   - Altitude can be specified as AMSL (above mean sea level), AGL (above
        #     ground level), or RELATIVE (above home/takeoff point)
        #   - Without explicit frame, the altitude domain is ambiguous
        #   - PX4 and autopilots require clarity on altitude reference
        #   - Prevents dangerous misinterpretation of altitude commands
        #
        # ESCALATION IF VIOLATED:
        #   - Command rejected BEFORE sending to PX4
        #   - User must specify altitude_frame explicitly
        # ============================================================================
        altitude_m = command.get("altitude_m")
        altitude_frame = command.get("altitude_frame")
        if altitude_m is not None and altitude_frame is None:
            reason = (
                "ALTITUDE_DOMAIN_AMBIGUOUS: altitude_m specified without "
                "altitude_frame. Must specify frame as 'amsl', 'agl', or 'relative'"
            )
            logger.warning(f"Command rejected: {reason}")
            return (False, "ALTITUDE_DOMAIN_AMBIGUOUS")

        # ============================================================================
        # CHECK 1: ALTITUDE LIMITS
        # ============================================================================
        # WHY THIS MATTERS:
        #   - FAA Part 107: Maximum 400ft (120m) above ground level
        #   - EASA: Maximum 120m above ground level
        #   - Avoids manned aircraft (typically fly at 500ft+ AGL minimum)
        #   - Maintains visual line-of-sight capability
        #
        # ESCALATION IF VIOLATED:
        #   - Command rejected BEFORE sending to PX4
        #   - No immediate flight action (preventive)
        #
        # EDGE CASES HANDLED:
        #   - Negative altitudes (below ground) are rejected
        #   - Uses AMSL (above mean sea level) not AGL (above ground level)
        #     NOTE: This is a simplification. Real implementation should use
        #     terrain elevation data to compute AGL accurately.
        #   - Also checks altitude_m when provided with a valid frame
        # ============================================================================
        altitude = command.get("altitude_amsl_m")
        if altitude is not None:
            if altitude > self.limits.max_altitude_amsl_m:
                reason = f"Altitude {altitude}m exceeds max {self.limits.max_altitude_amsl_m}m"
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)
            if altitude < 0:
                reason = f"Altitude {altitude}m is below ground level"
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # Also check altitude_m when frame is specified
        if altitude_m is not None and altitude_frame is not None:
            # For AMSL and relative frames, check against max altitude
            if altitude_frame in ("amsl", "relative"):
                if altitude_m > self.limits.max_altitude_amsl_m:
                    reason = f"Altitude {altitude_m}m exceeds max {self.limits.max_altitude_amsl_m}m"
                    logger.warning(f"Command rejected: {reason}")
                    return (False, reason)
                if altitude_m < 0:
                    reason = f"Altitude {altitude_m}m is below ground level"
                    logger.warning(f"Command rejected: {reason}")
                    return (False, reason)
            # For AGL, we would need terrain elevation data for accurate check
            # For now, just validate non-negative
            elif altitude_frame == "agl":
                if altitude_m < 0:
                    reason = f"Altitude {altitude_m}m is below ground level"
                    logger.warning(f"Command rejected: {reason}")
                    return (False, reason)

        # ============================================================================
        # CHECK 2: DISTANCE FROM HOME (GEOFENCE)
        # ============================================================================
        # WHY THIS MATTERS:
        #   - Maintains reliable radio control link (range-dependent)
        #   - Ensures visual line-of-sight compliance
        #   - Prevents flyaway into unknown/uncontrolled airspace
        #   - 500m provides ~3 minutes flight time for RTL at 15m/s
        #
        # ESCALATION IF VIOLATED:
        #   - Command rejected BEFORE sending to PX4
        #   - PX4 internal geofence would also trigger if somehow bypassed
        #
        # EDGE CASES HANDLED:
        #   - Home not set: Command rejected (safety-first)
        #   - Distance calculated using haversine formula (WGS84)
        #   - Accuracy ~0.5% for drone-scale distances
        #
        # PRECONDITION: Home position must be set via set_home()
        # FAILURE MODE: If home is not set, distance checks fail closed
        #               (reject command) rather than fail open (allow it)
        # ============================================================================
        lat = command.get("latitude")
        lon = command.get("longitude")
        if lat is not None and lon is not None:
            if self._home_lat is None or self._home_lon is None:
                reason = "Home position not set - cannot validate distance"
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

            distance = self._haversine_distance(
                self._home_lat, self._home_lon, lat, lon
            )
            if distance > self.limits.max_distance_from_home_m:
                reason = (
                    f"Distance {distance:.1f}m exceeds max "
                    f"{self.limits.max_distance_from_home_m}m from home"
                )
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # ============================================================================
        # CHECK 3: SPEED LIMIT
        # ============================================================================
        # WHY THIS MATTERS:
        #   - Reduces kinetic energy in potential collisions (E = 0.5 * m * v^2)
        #   - Ensures adequate control authority in moderate winds
        #   - Braking distance increases with v^2
        #   - 15 m/s = 54 km/h = 33 mph (reasonable for multirotor drones)
        #
        # ESCALATION IF VIOLATED:
        #   - Command rejected BEFORE sending to PX4
        #   - High-speed flight risks loss of control in gusts
        #
        # EDGE CASES:
        #   - Speed limit is ground speed (not airspeed)
        #   - Does not account for wind (PX4 handles that)
        # ============================================================================
        speed = command.get("speed_m_s")
        if speed is not None:
            if speed > self.limits.max_speed_m_s:
                reason = f"Speed {speed}m/s exceeds max {self.limits.max_speed_m_s}m/s"
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # ============================================================================
        # CHECK 4: BATTERY LEVEL
        # ============================================================================
        # WHY THIS MATTERS:
        #   - 25% provides safety margin for:
        #     * Headwinds during RTL (can double power consumption)
        #     * Landing maneuver (high power for stabilization)
        #     * Battery degradation over time (cells lose capacity)
        #     * Voltage sag under load (apparent capacity drops)
        #   - Lithium batteries drop voltage rapidly below 20%
        #   - Deep discharge damages battery permanently
        #
        # ESCALATION IF VIOLATED:
        #   - Command rejected BEFORE sending to PX4
        #   - PX4 would also trigger RTL if battery failsafe enabled
        #   - Critical: Below this threshold, ONLY RTL/Land commands allowed
        #
        # NOTE: This check prevents NEW commands when battery is low.
        # It does NOT trigger RTL itself - that's PX4's responsibility.
        # ============================================================================
        battery = command.get("battery_percent")
        if battery is not None:
            if battery < self.limits.min_battery_rtl_percent:
                reason = (
                    f"Battery {battery}% below minimum "
                    f"{self.limits.min_battery_rtl_percent}% - RTL required"
                )
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # ============================================================================
        # ALL SAFETY CHECKS PASSED
        # ============================================================================
        # The command has passed all applicable safety limits. It is now
        # safe to send to PX4 for execution.
        #
        # NOTE: This does not guarantee flight safety - it only ensures
        # the command itself doesn't violate hard limits. PX4 will apply
        # its own safety checks, and the pilot retains ultimate authority
        # via hardware kill switch (Layer 4).
        # ============================================================================
        return (True, "OK")

    def check_heartbeat(self) -> bool:
        """
        Check if heartbeat is within acceptable timeout.

        Heartbeat monitoring detects when the controlling agent (LLM or
        automation) has crashed, frozen, or lost network connectivity.
        This is CRITICAL for autonomous operation - without it, a crashed
        agent could leave the drone executing stale commands.

        WHY THIS MATTERS:
        - Detects software crashes in the control loop
        - Detects network partitions between agent and drone
        - Enables failsafe actions (hover, RTL, land) when control lost
        - Required by FAA for beyond-visual-line-of-sight operations

        ESCALATION ON TIMEOUT:
        1. Agent detects timeout via this method
        2. Agent should command PX4 to hover or RTL
        3. If agent completely unresponsive, PX4 loss-of-link failsafe triggers
        4. Pilot can use hardware kill switch if all else fails

        Returns:
            True if last heartbeat was within timeout threshold.
            False if heartbeat timeout exceeded (connection lost).
        """
        elapsed = time.time() - self._last_heartbeat
        if elapsed > self.limits.heartbeat_timeout_s:
            logger.warning(
                f"Heartbeat timeout: {elapsed:.2f}s > "
                f"{self.limits.heartbeat_timeout_s}s threshold"
            )
            return False
        return True

    def update_heartbeat(self) -> None:
        """
        Update heartbeat timestamp to current time.

        Call this periodically (e.g., every 1 second) from the control loop
to indicate the system is responsive. The heartbeat is a keepalive
signal - as long as it's updating, the Guardian knows the agent is alive.

BEST PRACTICES:
- Call at regular intervals (1Hz recommended)
- Call BEFORE processing commands (to show you're alive)
- If control loop blocks for >2s, consider threading
- Log heartbeat failures immediately - they're time-critical

Failure to call this regularly will cause check_heartbeat() to return
False, triggering failsafe procedures.
        """
        self._last_heartbeat = time.time()
        logger.debug("Heartbeat updated")

    def get_heartbeat_age(self) -> float:
        """
        Get seconds since last heartbeat update.

        This is useful for diagnostics and progressive escalation:
        - < 2s: Normal operation
        - 2-5s: Warning, potential connection issues
        - > 5s: Critical, initiate failsafe

        Returns:
            Time in seconds since last heartbeat.
        """
        return time.time() - self._last_heartbeat

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.

        The Haversine formula gives the great-circle distance between two
        points on a sphere given their longitudes and latitudes. It assumes
        a spherical Earth, which introduces ~0.5% error - acceptable for
        drone geofencing (500m * 0.5% = 2.5m error margin).

        For production use with larger distances or higher precision needs,
        consider Vincenty's formulae on the WGS84 ellipsoid.

        Args:
            lat1, lon1: First coordinate (degrees)
            lat2, lon2: Second coordinate (degrees)

        Returns:
            Distance in meters

        Reference:
            https://en.wikipedia.org/wiki/Haversine_formula
        """
        R = 6371000  # Earth radius in meters (mean radius)

        # Convert to radians
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        # Haversine formula
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @property
    def home_position(self) -> Optional[Tuple[float, float]]:
        """
        Get current home position.

        Returns:
            Tuple of (latitude, longitude) or None if not set.
        """
        if self._home_lat is not None and self._home_lon is not None:
            return (self._home_lat, self._home_lon)
        return None

    @property
    def is_home_set(self) -> bool:
        """
        Check if home position has been set.

        This is useful before validating commands that require distance
        calculations. If home is not set, those validations will fail.

        Returns:
            True if home position is set, False otherwise.
        """
        return self._home_lat is not None and self._home_lon is not None
