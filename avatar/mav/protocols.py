"""Type Protocols for MAV layer components.

This module defines strict Protocol classes for type checking and interface
contracts in the MAV (MAVSDK) layer. All protocols are runtime_checkable for
runtime isinstance checks.

Example:
    from avatar.mav.protocols import DroneConnectionProtocol

    class MyConnection:
        async def connect(self, system_address: str = "udp://:14540") -> bool:
            return True
        # ... implement other methods

    # Runtime check
    assert isinstance(MyConnection(), DroneConnectionProtocol)
"""

from dataclasses import dataclass
from math import sqrt
from typing import Any, Optional, Protocol, runtime_checkable


# =============================================================================
# Protocol Classes
# =============================================================================


@runtime_checkable
class DroneConnectionProtocol(Protocol):
    """Protocol for drone connection management.

    Implementations must provide async connect/disconnect methods
    and a property to check connection status.
    """

    async def connect(self, system_address: str = "udp://:14540") -> bool:
        """Connect to the drone.

        Args:
            system_address: MAVSDK system address (default: udp://:14540 for SITL)

        Returns:
            True if connection successful, False otherwise
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from the drone and cleanup resources."""
        ...

    async def get_drone(self) -> Optional[Any]:
        """Get the drone instance (fast, non-blocking).

        Returns:
            System instance if connected, None otherwise.
        """
        ...

    async def ensure_connected(self) -> Any:
        """Get drone or raise ConnectionError.

        Returns:
            System instance if connected

        Raises:
            ConnectionError: If not connected and auto-reconnect failed
        """
        ...

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to the drone."""
        ...


@runtime_checkable
class TelemetryProviderProtocol(Protocol):
    """Protocol for telemetry data providers.

    Implementations must be callable and return telemetry data.
    """

    async def __call__(self) -> Any:
        """Fetch and return telemetry data.

        Returns:
            Telemetry data object (type depends on implementation)
        """
        ...


@runtime_checkable
class SafetyValidatorProtocol(Protocol):
    """Protocol for safety validation.

    Implementations must validate commands and state transitions
    according to safety rules.
    """

    def validate_command(self, command: dict[str, Any]) -> tuple[bool, str]:
        """Validate a command before execution.

        Args:
            command: Command dictionary with operation details

        Returns:
            Tuple of (is_valid, reason) where is_valid is True if
            the command passes all safety checks, False otherwise.
            reason provides an explanation if invalid.
        """
        ...

    def validate_state_transition(self, from_state: str, to_state: str) -> tuple[bool, str]:
        """Validate a flight state transition.

        Args:
            from_state: Current flight state
            to_state: Target flight state

        Returns:
            Tuple of (is_valid, reason) where is_valid is True if
            the transition is allowed, False otherwise.
            reason provides an explanation if invalid.
        """
        ...


@runtime_checkable
class HeartbeatMonitorProtocol(Protocol):
    """Protocol for heartbeat monitoring.

    Implementations must track heartbeats from various sources
    and detect timeout conditions.
    """

    async def start_monitoring(self) -> None:
        """Start the heartbeat monitoring loop."""
        ...

    async def stop_monitoring(self) -> None:
        """Stop the heartbeat monitoring loop."""
        ...

    def check_heartbeat(self) -> bool:
        """Check if all required heartbeats are current.

        Returns:
            True if all heartbeats are within timeout thresholds,
            False if any heartbeat has expired.
        """
        ...

    def record_heartbeat(self, source: str) -> None:
        """Record a heartbeat from a source.

        Args:
            source: Identifier for the heartbeat source (e.g., "mavsdk", "mcp")
        """
        ...


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class GeoPoint:
    """Geographic point with latitude, longitude, and altitude.

    Attributes:
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)
        altitude_m: Altitude in meters above takeoff (default: 0.0)
    """

    latitude: float
    longitude: float
    altitude_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate coordinates."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(
                f"Longitude must be between -180 and 180, got {self.longitude}"
            )


@dataclass(frozen=True)
class VelocityNED:
    """Velocity in North-East-Down (NED) coordinate frame.

    Attributes:
        north_m_s: Velocity north in m/s (positive = north)
        east_m_s: Velocity east in m/s (positive = east)
        down_m_s: Velocity down in m/s (positive = down)
    """

    north_m_s: float
    east_m_s: float
    down_m_s: float

    @property
    def speed_m_s(self) -> float:
        """Calculate total horizontal speed in m/s.

        Returns:
            Speed in the horizontal plane (ignoring vertical velocity)
        """
        return sqrt(self.north_m_s**2 + self.east_m_s**2)

    @property
    def total_speed_m_s(self) -> float:
        """Calculate total 3D speed in m/s.

        Returns:
            Total speed including vertical component
        """
        return sqrt(self.north_m_s**2 + self.east_m_s**2 + self.down_m_s**2)


@dataclass(frozen=True)
class SafetyLimits:
    """Safety limits for drone operation.

    These limits define the operational envelope for safe flight.
    All values have conservative defaults appropriate for testing in SITL.

    Attributes:
        max_altitude_m: Maximum altitude in meters (default: 120.0, typical regulatory limit)
        min_altitude_m: Minimum altitude in meters (default: 5.0, safety margin above ground)
        max_distance_m: Maximum distance from home in meters (default: 500.0)
        max_speed_m_s: Maximum horizontal speed in m/s (default: 15.0, ~54 km/h)
        max_vertical_speed_m_s: Maximum vertical speed in m/s (default: 3.0)
        min_battery_percent: Minimum battery percentage (default: 25.0)
        heartbeat_timeout_s: Heartbeat timeout in seconds (default: 0.5)
    """

    max_altitude_m: float = 120.0
    min_altitude_m: float = 5.0
    max_distance_m: float = 500.0
    max_speed_m_s: float = 15.0
    max_vertical_speed_m_s: float = 3.0
    min_battery_percent: float = 25.0
    heartbeat_timeout_s: float = 0.5

    def validate_altitude(self, altitude_m: float) -> tuple[bool, str]:
        """Validate altitude against limits.

        Args:
            altitude_m: Current altitude in meters

        Returns:
            Tuple of (is_valid, reason)
        """
        if altitude_m < self.min_altitude_m:
            return False, f"Altitude {altitude_m}m below minimum {self.min_altitude_m}m"
        if altitude_m > self.max_altitude_m:
            return False, f"Altitude {altitude_m}m above maximum {self.max_altitude_m}m"
        return True, ""

    def validate_speed(self, speed_m_s: float) -> tuple[bool, str]:
        """Validate speed against limits.

        Args:
            speed_m_s: Current speed in m/s

        Returns:
            Tuple of (is_valid, reason)
        """
        if speed_m_s > self.max_speed_m_s:
            return False, f"Speed {speed_m_s}m/s above maximum {self.max_speed_m_s}m/s"
        return True, ""

    def validate_battery(self, battery_percent: float) -> tuple[bool, str]:
        """Validate battery level against limits.

        Args:
            battery_percent: Current battery percentage

        Returns:
            Tuple of (is_valid, reason)
        """
        if battery_percent < self.min_battery_percent:
            return (
                False,
                f"Battery {battery_percent}% below minimum {self.min_battery_percent}%",
            )
        return True, ""
