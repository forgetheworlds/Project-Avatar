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

# WHAT ARE PROTOCOL CLASSES?
# --------------------------
# Protocol classes (defined via typing.Protocol) are Python's way of doing
# "structural subtyping" - also known as "duck typing with teeth."
#
# Traditional inheritance (OOP approach):
#   class Animal: def speak(self): pass
#   class Dog(Animal): pass  # Dog IS-A Animal
#
# Protocol approach (structural typing):
#   class Speaker(Protocol): def speak(self): pass
#   class Dog: def speak(self): pass
#   # Dog satisfies Speaker WITHOUT inheriting from it!
#
# WHY USE PROTOCOLS FOR DRONE CODE?
# ---------------------------------
# 1. Loose Coupling: The MAV layer doesn't need to import concrete classes
#    from the MCP layer or vice versa. They only need to agree on the shape.
#
# 2. Testability: You can create mock implementations for testing without
#    inheriting from complex base classes.
#
# 3. Flexibility: Different implementations (real drone vs SITL vs mock) can
#    all satisfy the same protocol without being forced into an inheritance tree.
#
# 4. Type Safety: Static type checkers (mypy, pyright) verify at compile time
#    that implementations satisfy the protocol.


@runtime_checkable
class DroneConnectionProtocol(Protocol):
    """Protocol for drone connection management.

    Implementations must provide async connect/disconnect methods
    and a property to check connection status.

    TYPE SAFETY GUARANTEE:
    ----------------------
    This protocol ensures ANY implementation (real MAVSDK connection,
    mock for testing, or SITL wrapper) provides these essential methods.
    Static analysis will catch missing methods before runtime.

    USAGE EXAMPLE:
    --------------
    # In your flight controller:
    async def arm_drone(conn: DroneConnectionProtocol) -> bool:
        # Type checker knows conn has ensure_connected()
        drone = await conn.ensure_connected()
        # ... proceed with arming

    # This works with ANY object implementing the protocol:
    await arm_drone(MavsdkConnection())   # Real implementation
    await arm_drone(MockConnection())     # Test double
    await arm_drone(SitlConnection())     # SITL wrapper
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

        WHY THIS MATTERS:
        -----------------
        Provides a "fail-fast" alternative to get_drone(). Instead of
        checking for None everywhere, this either succeeds or raises
        a clear exception. Makes error handling more explicit.

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

    TYPE SAFETY GUARANTEE:
    ----------------------
    Ensures telemetry sources (MAVSDK telemetry streams, mock data
    generators, or log replay) all provide a consistent async interface.

    USAGE EXAMPLE:
    --------------
    # Multiple telemetry sources, same interface:
    sources: list[TelemetryProviderProtocol] = [
        PositionTelemetry(drone),      # Real position from MAVSDK
        BatteryTelemetry(drone),       # Real battery from MAVSDK
        MockTelemetry(simulator),      # Simulated data for testing
    ]

    # Unified collection regardless of source:
    for source in sources:
        data = await source()  # Type checker knows this is valid
        process(data)
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

    TYPE SAFETY GUARANTEE:
    ----------------------
    Safety-critical code can accept ANY validator that satisfies
    this protocol. Whether it's a simple rule-based validator or
    an AI-powered risk assessor, the interface remains consistent.

    WHY THIS PREVENTS BUGS:
    -----------------------
    The return type tuple[bool, str] forces implementers to always
    provide BOTH a pass/fail result AND an explanation. This prevents
    the common bug of silent failures where validation fails but
    no reason is given.

    USAGE EXAMPLE:
    --------------
    class SimpleValidator:
        def validate_command(self, cmd: dict) -> tuple[bool, str]:
            if cmd.get('speed', 0) > 20:
                return False, "Speed exceeds 20 m/s safety limit"
            return True, ""

        def validate_state_transition(self, from_s: str, to_s: str) -> tuple[bool, str]:
            # Prevent landing -> takeoff without disarm in between
            if from_s == "LANDING" and to_s == "TAKING_OFF":
                return False, "Must disarm after landing before takeoff"
            return True, ""

    # Usage in flight controller:
    validator: SafetyValidatorProtocol = SimpleValidator()
    ok, reason = validator.validate_command({"speed": 25})
    if not ok:
        logger.error(f"Safety check failed: {reason}")  # Always have a reason!
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

    TYPE SAFETY GUARANTEE:
    ----------------------
    Multiple monitor implementations (real-time for flight,
    relaxed for testing, strict for production) can all be used
    interchangeably in the health check system.

    USAGE EXAMPLE:
    --------------
    # Flight-critical health check:
    async def health_check(monitor: HeartbeatMonitorProtocol) -> bool:
        # Type checker ensures these methods exist
        await monitor.start_monitoring()

        while True:
            if not monitor.check_heartbeat():
                # Drone, ground station, or MCP may be down
                await emergency_land()
                return False
            await asyncio.sleep(0.5)

    # Works with:
    await health_check(StrictHeartbeatMonitor(timeout=0.5))  # Production
    await health_check(RelaxedHeartbeatMonitor(timeout=5.0))  # Testing
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

# WHY USE DATACLASSES FOR DATA?
# -----------------------------
# Dataclasses automatically generate:
# - __init__ (clean constructors)
# - __repr__ (nice debugging output)
# - __eq__ (proper equality comparison)
#
# frozen=True makes them IMMUTABLE - once created, they cannot be changed.
# This prevents the common bug where you modify a "reference" object
# thinking it's a copy.


@dataclass(frozen=True)
class GeoPoint:
    """Geographic point with latitude, longitude, and altitude.

    TYPE SAFETY GUARANTEE:
    ----------------------
    Using a dataclass instead of a raw tuple/list ensures:
    1. Named fields (no confusing point[0] vs point[1])
    2. Type checking on each field
    3. Immutability (can't accidentally corrupt a waypoint)

    WHY IMMUTABILITY MATTERS FOR DRONES:
    ------------------------------------
    Waypoints are safety-critical. If a GeoPoint could be modified
    after creation, a bug could silently corrupt your flight path.
    frozen=True means once validated, it stays valid.

    USAGE EXAMPLE:
    --------------
    # Instead of error-prone tuples:
    waypoint = (47.3977, 8.5456, 10.0)  # Which is lat? lon? alt?

    # Use explicit, validated dataclass:
    waypoint = GeoPoint(latitude=47.3977, longitude=8.5456, altitude_m=10.0)

    # Automatic validation catches errors early:
    bad_point = GeoPoint(latitude=999, longitude=8.5, altitude_m=10.0)
    # Raises ValueError: Latitude must be between -90 and 90

    Attributes:
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)
        altitude_m: Altitude in meters above takeoff (default: 0.0)
    """

    latitude: float
    longitude: float
    altitude_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate coordinates.

        WHY THIS PREVENTS BUGS:
        -----------------------
        Invalid coordinates are caught at creation time, not when
        the drone is already flying. Fail-fast principle.
        """
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(
                f"Longitude must be between -180 and 180, got {self.longitude}"
            )


@dataclass(frozen=True)
class VelocityNED:
    """Velocity in North-East-Down (NED) coordinate frame.

    TYPE SAFETY GUARANTEE:
    ----------------------
    NED is the standard aerospace coordinate frame:
    - North: Positive X (forward)
    - East: Positive Y (right)
    - Down: Positive Z (toward earth)

    Using a dedicated type instead of a tuple prevents confusion
    with ENU (East-North-Up) or other coordinate systems.

    WHY NED MATTERS:
    ----------------
    Different aerospace systems use different frames:
    - PX4/MAVSDK: Uses NED
    - Some ROS packages: Use ENU
    - GPS: Uses ECEF or local tangent plane

    Explicit typing prevents mixing coordinate systems.

    USAGE EXAMPLE:
    --------------
    velocity = VelocityNED(north_m_s=5.0, east_m_s=0.0, down_m_s=-1.0)
    # down_m_s=-1.0 means CLIMBING (negative down = up)

    # Helper properties for common calculations:
    horizontal_speed = velocity.speed_m_s  # Ground speed
    total_speed = velocity.total_speed_m_s  # 3D airspeed estimate

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

        WHY THIS MATTERS:
        -----------------
        Ground speed is critical for:
        - Battery consumption estimates
        - Reachability calculations
        - Regulatory compliance (some areas have speed limits)

        Returns:
            Speed in the horizontal plane (ignoring vertical velocity)
        """
        return sqrt(self.north_m_s**2 + self.east_m_s**2)

    @property
    def total_speed_m_s(self) -> float:
        """Calculate total 3D speed in m/s.

        WHY THIS MATTERS:
        -----------------
        Total airspeed affects aerodynamics and is important
        for stall prevention and efficiency calculations.

        Returns:
            Total speed including vertical component
        """
        return sqrt(self.north_m_s**2 + self.east_m_s**2 + self.down_m_s**2)


@dataclass(frozen=True)
class SafetyLimits:
    """Safety limits for drone operation.

    These limits define the operational envelope for safe flight.
    All values have conservative defaults appropriate for testing in SITL.

    TYPE SAFETY GUARANTEE:
    ----------------------
    Encapsulating all limits in one immutable object ensures:
    1. No magic numbers scattered through the code
    2. Limits are validated together as a set
    3. Cannot be accidentally modified during flight

    WHY DEFAULTS ARE CONSERVATIVE:
    ------------------------------
    - max_altitude_m=120: Most countries limit drones to 120m/400ft
    - min_altitude_m=5: Safety margin for takeoff/landing errors
    - max_distance_m=500: Keep VLOS (Visual Line of Sight) for safety
    - max_speed_m_s=15: ~54 km/h, manageable for emergency stops

    USAGE EXAMPLE:
    --------------
    # Create with defaults (safe for SITL):
    limits = SafetyLimits()

    # Override specific limits:
    limits = SafetyLimits(max_altitude_m=50, max_distance_m=100)

    # Validation methods return (ok, reason) tuples:
    ok, reason = limits.validate_altitude(150)
    if not ok:
        logger.warning(f"Altitude limit exceeded: {reason}")
        # Returns: "Altitude 150m above maximum 50m"

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

        WHY THIS PATTERN:
        -----------------
        Returning (bool, str) instead of raising exceptions or returning
        just bool ensures the caller ALWAYS has context for failures.
        No silent failures, no unexplained rejections.

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
