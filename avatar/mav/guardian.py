"""
Safety validation layer for drone operations.

Provides hard limits enforcement and heartbeat monitoring for flight safety.
"""
import logging
import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardLimits:
    """
    Immutable safety limits for drone operations.

    These are regulatory and safety-critical limits that should never be exceeded.
    Based on common drone regulations (e.g., FAA Part 107, EASA).
    """
    max_altitude_amsl_m: float = 120.0  # Max altitude above mean sea level (meters)
    max_distance_from_home_m: float = 500.0  # Max horizontal distance from home (meters)
    min_battery_rtl_percent: float = 25.0  # Min battery % before RTL trigger
    heartbeat_timeout_s: float = 2.0  # Max seconds between heartbeats
    max_speed_m_s: float = 15.0  # Max ground speed (m/s)


class GuardianProcess:
    """
    Safety validation layer that enforces hard limits on drone commands.

    Responsibilities:
    - Validate commands against safety limits (altitude, distance, speed)
    - Monitor heartbeat for connection health
    - Track home position for geofencing

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

        # Heartbeat monitoring
        guardian.update_heartbeat()
        if not guardian.check_heartbeat():
            logger.warning("Heartbeat timeout - trigger failsafe")
    """

    def __init__(self, limits: Optional[HardLimits] = None):
        """
        Initialize guardian with safety limits.

        Args:
            limits: HardLimits instance. Uses defaults if not provided.
        """
        self.limits = limits or HardLimits()
        self._home_lat: Optional[float] = None
        self._home_lon: Optional[float] = None
        self._last_heartbeat: float = time.time()

    def set_home(self, lat: float, lon: float) -> None:
        """
        Set home position for geofence calculations.

        Args:
            lat: Home latitude in degrees
            lon: Home longitude in degrees
        """
        self._home_lat = lat
        self._home_lon = lon
        logger.info(f"Home position set: ({lat}, {lon})")

    def validate_command(self, command: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a command against all safety limits.

        Args:
            command: Command dictionary with optional keys:
                - altitude_amsl_m: Target altitude above mean sea level
                - latitude: Target latitude
                - longitude: Target longitude
                - speed_m_s: Target speed
                - battery_percent: Current battery level

        Returns:
            Tuple of (is_valid: bool, reason: str)
            - (True, "OK") if command passes all checks
            - (False, "reason") if command violates a limit
        """
        # Check altitude limit
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

        # Check distance from home (geofence)
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

        # Check speed limit
        speed = command.get("speed_m_s")
        if speed is not None:
            if speed > self.limits.max_speed_m_s:
                reason = f"Speed {speed}m/s exceeds max {self.limits.max_speed_m_s}m/s"
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # Check battery level
        battery = command.get("battery_percent")
        if battery is not None:
            if battery < self.limits.min_battery_rtl_percent:
                reason = (
                    f"Battery {battery}% below minimum "
                    f"{self.limits.min_battery_rtl_percent}% - RTL required"
                )
                logger.warning(f"Command rejected: {reason}")
                return (False, reason)

        # All checks passed
        return (True, "OK")

    def check_heartbeat(self) -> bool:
        """
        Check if heartbeat is within acceptable timeout.

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
        to indicate the system is responsive.
        """
        self._last_heartbeat = time.time()
        logger.debug("Heartbeat updated")

    def get_heartbeat_age(self) -> float:
        """
        Get seconds since last heartbeat update.

        Returns:
            Time in seconds since last heartbeat.
        """
        return time.time() - self._last_heartbeat

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.

        Args:
            lat1, lon1: First coordinate (degrees)
            lat2, lon2: Second coordinate (degrees)

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

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
        """Check if home position has been set."""
        return self._home_lat is not None and self._home_lon is not None
