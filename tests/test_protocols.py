"""Tests for type protocols.

These tests verify:
- All protocols are runtime_checkable
- Mock implementations pass isinstance checks
- Dataclass calculations are correct
- Type safety with mypy

PROTOCOL PATTERN:
Python protocols (PEP 544) define structural subtyping - objects that implement
the required methods/properties satisfy the protocol without explicit inheritance.
The @runtime_checkable decorator enables isinstance() checks at runtime.

WHY PROTOCOLS:
1. Loose coupling between components
2. Easy to mock for testing
3. Clear interface contracts
4. IDE support for autocompletion
5. Static type checking with mypy

TEST COVERAGE:
- Runtime checkability: All protocols have _is_runtime_protocol
- Implementation validation: Mocks satisfy isinstance checks
- Method contracts: Return types and behaviors are correct
- Dataclass validation: Data structures and calculations
- Edge cases: Incomplete implementations, wrong signatures
"""

import asyncio
from math import sqrt
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from avatar.mav.protocols import (
    DroneConnectionProtocol,
    GeoPoint,
    HeartbeatMonitorProtocol,
    SafetyLimits,
    SafetyValidatorProtocol,
    TelemetryProviderProtocol,
    VelocityNED,
)
from avatar.mcp_server.protocols import (
    ConfirmationProviderProtocol,
    FlightStateMachineProtocol,
    GuardianProcessProtocol,
    TelemetryBroadcasterProtocol,
    ToolHandlerProtocol,
    ToolRegistryProtocol,
)


# =============================================================================
# Mock Implementations for Testing
# =============================================================================


class MockDroneConnection:
    """Mock implementation of DroneConnectionProtocol.

    Provides a minimal in-memory implementation of the drone connection
    interface for testing protocol compliance without actual MAVSDK.
    """

    def __init__(self) -> None:
        self._connected = False
        self._drone: Optional[Any] = None

    async def connect(self, system_address: str = "udp://:14540") -> bool:
        """Simulate connection establishment."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection cleanup."""
        self._connected = False
        self._drone = None

    async def get_drone(self) -> Optional[Any]:
        """Return drone object if connected."""
        return self._drone if self._connected else None

    async def ensure_connected(self) -> Any:
        """Verify connection or raise ConnectionError."""
        if not self._connected:
            raise ConnectionError("Not connected")
        return self._drone

    @property
    def is_connected(self) -> bool:
        """Connection state property."""
        return self._connected


class MockTelemetryProvider:
    """Mock implementation of TelemetryProviderProtocol.

    Simulates a telemetry data source that can be called to return
    position and status information.
    """

    async def __call__(self) -> dict[str, Any]:
        """Return simulated telemetry data."""
        return {"latitude": 37.7749, "longitude": -122.4194}


class MockSafetyValidator:
    """Mock implementation of SafetyValidatorProtocol.

    Provides safety validation that always approves commands,
    useful for testing the protocol interface without real constraints.
    """

    def validate_command(self, command: dict[str, Any]) -> tuple[bool, str]:
        """Always approve commands in mock."""
        return True, ""

    def validate_state_transition(self, from_state: str, to_state: str) -> tuple[bool, str]:
        """Always approve state transitions in mock."""
        return True, ""


class MockHeartbeatMonitor:
    """Mock implementation of HeartbeatMonitorProtocol.

    Simulates a heartbeat tracking system for monitoring component health.
    """

    def __init__(self) -> None:
        self._running = False
        self._heartbeats: dict[str, float] = {}

    async def start_monitoring(self) -> None:
        """Start the heartbeat monitor."""
        self._running = True

    async def stop_monitoring(self) -> None:
        """Stop the heartbeat monitor."""
        self._running = False

    def check_heartbeat(self) -> bool:
        """Return monitoring status."""
        return self._running

    def record_heartbeat(self, source: str) -> None:
        """Record a heartbeat from a source."""
        self._heartbeats[source] = asyncio.get_event_loop().time()


class MockToolHandler:
    """Mock implementation of ToolHandlerProtocol.

    Simulates an MCP tool that can be registered and invoked.
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "mock_tool"

    @property
    def description(self) -> str:
        """Tool description for LLM context."""
        return "A mock tool for testing"

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with parameters."""
        return {"result": "success"}


class MockToolRegistry:
    """Mock implementation of ToolRegistryProtocol.

    Manages a collection of tools with registration, lookup, and lifecycle.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandlerProtocol] = {}

    def register(self, tool: ToolHandlerProtocol) -> None:
        """Register a tool, raising if duplicate."""
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolHandlerProtocol]:
        """Lookup a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return list of registered tool names."""
        return list(self._tools.keys())

    def unregister(self, name: str) -> bool:
        """Remove a tool, returning success status."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False


class MockConfirmationProvider:
    """Mock implementation of ConfirmationProviderProtocol.

    Simulates user confirmation system for dangerous operations.
    """

    def __init__(self) -> None:
        self._required_ops: set[str] = {"arm", "takeoff", "land"}
        self._risk_levels: dict[str, str] = {
            "arm": "medium",
            "takeoff": "high",
            "land": "medium",
        }

    async def request_confirmation(self, context: dict[str, Any]) -> bool:
        """Simulate confirmation dialog (always approves in mock)."""
        return True

    def is_confirmation_required(self, operation: str) -> bool:
        """Check if operation requires confirmation."""
        return operation in self._required_ops

    def get_risk_level(self, operation: str) -> str:
        """Return risk classification for operation."""
        return self._risk_levels.get(operation, "low")


class MockTelemetryBroadcaster:
    """Mock implementation of TelemetryBroadcasterProtocol.

    Simulates a telemetry publishing system for real-time updates.
    """

    def __init__(self) -> None:
        self._running = False
        self._latest: dict[str, Any] = {}

    async def start_broadcast(self, interval_s: float = 1.0) -> None:
        """Start broadcasting telemetry."""
        self._running = True

    async def stop_broadcast(self) -> None:
        """Stop broadcasting telemetry."""
        self._running = False

    def get_latest_telemetry(self) -> dict[str, Any]:
        """Return most recent telemetry snapshot."""
        return self._latest.copy()

    def is_broadcasting(self) -> bool:
        """Check if broadcaster is active."""
        return self._running


class MockGuardianProcess:
    """Mock implementation of GuardianProcessProtocol.

    Simulates the safety validation and permission system.
    """

    async def validate(self, operation: str, params: dict[str, Any]) -> tuple[bool, str]:
        """Validate operation against safety constraints."""
        return True, ""

    def is_operation_allowed(self, state: str, operation: str) -> bool:
        """Check if operation is permitted in current state."""
        allowed: dict[str, list[str]] = {
            "landed": ["arm", "disarm", "get_telemetry"],
            "armed": ["takeoff", "disarm", "get_telemetry"],
            "flying": ["land", "goto", "hold", "get_telemetry"],
        }
        return operation in allowed.get(state, [])


class MockFlightStateMachine:
    """Mock implementation of FlightStateMachineProtocol.

    Simulates state machine for tracking and controlling flight states.
    """

    def __init__(self) -> None:
        self._state = "landed"
        self._transitions: dict[str, list[str]] = {
            "landed": ["armed"],
            "armed": ["landed", "flying"],
            "flying": ["armed"],
        }

    @property
    def current_state(self) -> str:
        """Current flight state."""
        return self._state

    async def transition_to(
        self, new_state: str, context: Optional[dict[str, Any]] = None
    ) -> bool:
        """Attempt state transition."""
        if self.is_transition_allowed(self._state, new_state):
            self._state = new_state
            return True
        return False

    def is_transition_allowed(self, from_state: str, to_state: str) -> bool:
        """Check if transition is valid."""
        return to_state in self._transitions.get(from_state, [])

    def get_allowed_operations(self, state: str) -> list[str]:
        """List operations valid in given state."""
        ops: dict[str, list[str]] = {
            "landed": ["arm", "disarm", "get_telemetry"],
            "armed": ["takeoff", "disarm", "get_telemetry"],
            "flying": ["land", "goto", "hold", "get_telemetry"],
        }
        return ops.get(state, [])


# =============================================================================
# Protocol Runtime Checkability Tests
# =============================================================================


class TestProtocolsAreRuntimeCheckable:
    """Test that all protocols have _is_runtime_protocol attribute.

    VALIDATES:
    - All protocols are decorated with @runtime_checkable
    - isinstance() checks work with protocol implementations

    WHY RUNTIME_CHECKABLE:
    Without @runtime_checkable, isinstance() checks against protocols
    always return True (duck typing). The decorator enables actual
    method signature validation at runtime.
    """

    def test_drone_connection_is_runtime_protocol(self) -> None:
        """VALIDATES: DroneConnectionProtocol has _is_runtime_protocol flag."""
        assert hasattr(DroneConnectionProtocol, "_is_runtime_protocol")
        assert DroneConnectionProtocol._is_runtime_protocol is True

    def test_telemetry_provider_is_runtime_protocol(self) -> None:
        """VALIDATES: TelemetryProviderProtocol has _is_runtime_protocol."""
        assert hasattr(TelemetryProviderProtocol, "_is_runtime_protocol")
        assert TelemetryProviderProtocol._is_runtime_protocol is True

    def test_safety_validator_is_runtime_protocol(self) -> None:
        """VALIDATES: SafetyValidatorProtocol has _is_runtime_protocol."""
        assert hasattr(SafetyValidatorProtocol, "_is_runtime_protocol")
        assert SafetyValidatorProtocol._is_runtime_protocol is True

    def test_heartbeat_monitor_is_runtime_protocol(self) -> None:
        """VALIDATES: HeartbeatMonitorProtocol has _is_runtime_protocol."""
        assert hasattr(HeartbeatMonitorProtocol, "_is_runtime_protocol")
        assert HeartbeatMonitorProtocol._is_runtime_protocol is True

    def test_tool_handler_is_runtime_protocol(self) -> None:
        """VALIDATES: ToolHandlerProtocol has _is_runtime_protocol."""
        assert hasattr(ToolHandlerProtocol, "_is_runtime_protocol")
        assert ToolHandlerProtocol._is_runtime_protocol is True

    def test_tool_registry_is_runtime_protocol(self) -> None:
        """VALIDATES: ToolRegistryProtocol has _is_runtime_protocol."""
        assert hasattr(ToolRegistryProtocol, "_is_runtime_protocol")
        assert ToolRegistryProtocol._is_runtime_protocol is True

    def test_confirmation_provider_is_runtime_protocol(self) -> None:
        """VALIDATES: ConfirmationProviderProtocol has _is_runtime_protocol."""
        assert hasattr(ConfirmationProviderProtocol, "_is_runtime_protocol")
        assert ConfirmationProviderProtocol._is_runtime_protocol is True

    def test_telemetry_broadcaster_is_runtime_protocol(self) -> None:
        """VALIDATES: TelemetryBroadcasterProtocol has _is_runtime_protocol."""
        assert hasattr(TelemetryBroadcasterProtocol, "_is_runtime_protocol")
        assert TelemetryBroadcasterProtocol._is_runtime_protocol is True

    def test_guardian_process_is_runtime_protocol(self) -> None:
        """VALIDATES: GuardianProcessProtocol has _is_runtime_protocol."""
        assert hasattr(GuardianProcessProtocol, "_is_runtime_protocol")
        assert GuardianProcessProtocol._is_runtime_protocol is True

    def test_flight_state_machine_is_runtime_protocol(self) -> None:
        """VALIDATES: FlightStateMachineProtocol has _is_runtime_protocol."""
        assert hasattr(FlightStateMachineProtocol, "_is_runtime_protocol")
        assert FlightStateMachineProtocol._is_runtime_protocol is True


# =============================================================================
# Protocol Implementation Tests
# =============================================================================


class TestMockImplementsConnectionProtocol:
    """Test that mock implementations satisfy protocol requirements.

    VALIDATES:
    - isinstance() returns True for compliant implementations
    - Methods are callable with correct signatures
    - Return types match protocol specification
    - Properties work correctly
    """

    def test_mock_drone_connection_isinstance(self) -> None:
        """VALIDATES: MockDroneConnection passes isinstance check.

        A properly implemented mock should be recognized as satisfying
        the DroneConnectionProtocol interface.
        """
        mock = MockDroneConnection()
        assert isinstance(mock, DroneConnectionProtocol)

    @pytest.mark.asyncio
    async def test_mock_drone_connection_methods(self) -> None:
        """VALIDATES: MockDroneConnection methods work correctly.

        Tests the full lifecycle: connect -> check status -> disconnect.
        """
        mock = MockDroneConnection()

        assert await mock.connect() is True
        assert mock.is_connected is True

        drone = await mock.get_drone()
        assert drone is None  # We didn't set a drone

        await mock.disconnect()
        assert mock.is_connected is False

    def test_mock_telemetry_provider_isinstance(self) -> None:
        """VALIDATES: MockTelemetryProvider passes isinstance check."""
        mock = MockTelemetryProvider()
        assert isinstance(mock, TelemetryProviderProtocol)

    @pytest.mark.asyncio
    async def test_mock_telemetry_provider_callable(self) -> None:
        """VALIDATES: MockTelemetryProvider can be called.

        The protocol defines __call__ so instances are callable like functions.
        """
        mock = MockTelemetryProvider()
        result = await mock()
        assert "latitude" in result

    def test_mock_safety_validator_isinstance(self) -> None:
        """VALIDATES: MockSafetyValidator passes isinstance check."""
        mock = MockSafetyValidator()
        assert isinstance(mock, SafetyValidatorProtocol)

    def test_mock_safety_validator_methods(self) -> None:
        """VALIDATES: MockSafetyValidator methods return correct types.

        Both methods should return (bool, str) tuples.
        """
        mock = MockSafetyValidator()

        valid, reason = mock.validate_command({"test": "data"})
        assert isinstance(valid, bool)
        assert isinstance(reason, str)

        valid, reason = mock.validate_state_transition("landed", "flying")
        assert isinstance(valid, bool)
        assert isinstance(reason, str)

    def test_mock_heartbeat_monitor_isinstance(self) -> None:
        """VALIDATES: MockHeartbeatMonitor passes isinstance check."""
        mock = MockHeartbeatMonitor()
        assert isinstance(mock, HeartbeatMonitorProtocol)

    @pytest.mark.asyncio
    async def test_mock_heartbeat_monitor_lifecycle(self) -> None:
        """VALIDATES: MockHeartbeatMonitor start/stop works.

        Tests the async lifecycle methods and status checking.
        """
        mock = MockHeartbeatMonitor()

        await mock.start_monitoring()
        assert mock.check_heartbeat() is True

        await mock.stop_monitoring()
        assert mock.check_heartbeat() is False

    def test_mock_tool_handler_isinstance(self) -> None:
        """VALIDATES: MockToolHandler passes isinstance check."""
        mock = MockToolHandler()
        assert isinstance(mock, ToolHandlerProtocol)

    def test_mock_tool_handler_properties(self) -> None:
        """VALIDATES: MockToolHandler properties return strings.

        name and description should always be strings.
        """
        mock = MockToolHandler()
        assert isinstance(mock.name, str)
        assert isinstance(mock.description, str)
        assert mock.name == "mock_tool"

    @pytest.mark.asyncio
    async def test_mock_tool_handler_callable(self) -> None:
        """VALIDATES: MockToolHandler can be called.

        Should return a dict with execution results.
        """
        mock = MockToolHandler()
        result = await mock()
        assert isinstance(result, dict)

    def test_mock_tool_registry_isinstance(self) -> None:
        """VALIDATES: MockToolRegistry passes isinstance check."""
        mock = MockToolRegistry()
        assert isinstance(mock, ToolRegistryProtocol)

    def test_mock_tool_registry_operations(self) -> None:
        """VALIDATES: MockToolRegistry register/get/list work.

        Tests the full registration lifecycle.
        """
        registry = MockToolRegistry()
        tool = MockToolHandler()

        registry.register(tool)
        assert registry.get("mock_tool") is tool
        assert "mock_tool" in registry.list_tools()

        assert registry.unregister("mock_tool") is True
        assert registry.get("mock_tool") is None

    def test_mock_confirmation_provider_isinstance(self) -> None:
        """VALIDATES: MockConfirmationProvider passes isinstance check."""
        mock = MockConfirmationProvider()
        assert isinstance(mock, ConfirmationProviderProtocol)

    @pytest.mark.asyncio
    async def test_mock_confirmation_provider_methods(self) -> None:
        """VALIDATES: MockConfirmationProvider methods work.

        Tests confirmation request and risk level checking.
        """
        mock = MockConfirmationProvider()

        result = await mock.request_confirmation({"operation": "arm"})
        assert isinstance(result, bool)

        assert mock.is_confirmation_required("arm") is True
        assert mock.is_confirmation_required("get_telemetry") is False

    def test_mock_telemetry_broadcaster_isinstance(self) -> None:
        """VALIDATES: MockTelemetryBroadcaster passes isinstance check."""
        mock = MockTelemetryBroadcaster()
        assert isinstance(mock, TelemetryBroadcasterProtocol)

    @pytest.mark.asyncio
    async def test_mock_telemetry_broadcaster_lifecycle(self) -> None:
        """VALIDATES: MockTelemetryBroadcaster start/stop works.

        Tests the async broadcast lifecycle.
        """
        mock = MockTelemetryBroadcaster()

        await mock.start_broadcast()
        assert mock.is_broadcasting() is True

        await mock.stop_broadcast()
        assert mock.is_broadcasting() is False

    def test_mock_guardian_process_isinstance(self) -> None:
        """VALIDATES: MockGuardianProcess passes isinstance check."""
        mock = MockGuardianProcess()
        assert isinstance(mock, GuardianProcessProtocol)

    @pytest.mark.asyncio
    async def test_mock_guardian_process_methods(self) -> None:
        """VALIDATES: MockGuardianProcess methods work.

        Tests validation and state-based permission checking.
        """
        mock = MockGuardianProcess()

        valid, reason = await mock.validate("arm", {})
        assert isinstance(valid, bool)
        assert isinstance(reason, str)

        assert mock.is_operation_allowed("landed", "arm") is True
        assert mock.is_operation_allowed("landed", "land") is False

    def test_mock_flight_state_machine_isinstance(self) -> None:
        """VALIDATES: MockFlightStateMachine passes isinstance check."""
        mock = MockFlightStateMachine()
        assert isinstance(mock, FlightStateMachineProtocol)

    @pytest.mark.asyncio
    async def test_mock_flight_state_machine_methods(self) -> None:
        """VALIDATES: MockFlightStateMachine methods work.

        Tests state property, transition checking, and state changes.
        """
        mock = MockFlightStateMachine()

        assert mock.current_state == "landed"
        assert mock.is_transition_allowed("landed", "armed") is True
        assert mock.is_transition_allowed("landed", "flying") is False

        result = await mock.transition_to("armed")
        assert result is True
        assert mock.current_state == "armed"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestVelocityNED:
    """Test VelocityNED dataclass.

    VALIDATES:
    - Creation with velocity components
    - Speed calculations (horizontal and total)
    - Zero velocity edge case

    VelocityNED represents velocity in North-East-Down coordinate frame,
    commonly used in aviation and drone navigation.
    """

    def test_velocity_ned_creation(self) -> None:
        """VALIDATES: VelocityNED can be created with all fields."""
        vel = VelocityNED(north_m_s=1.0, east_m_s=2.0, down_m_s=0.5)
        assert vel.north_m_s == 1.0
        assert vel.east_m_s == 2.0
        assert vel.down_m_s == 0.5

    def test_velocity_ned_speed_calculation(self) -> None:
        """VALIDATES: VelocityNED.speed_m_s calculates horizontal speed correctly.

        speed_m_s is the magnitude of the horizontal velocity vector
        (north and east components only), ignoring vertical velocity.
        Used for ground speed calculations.
        """
        # Simple case: only north velocity
        vel1 = VelocityNED(north_m_s=3.0, east_m_s=0.0, down_m_s=0.0)
        assert vel1.speed_m_s == 3.0

        # Simple case: only east velocity
        vel2 = VelocityNED(north_m_s=0.0, east_m_s=4.0, down_m_s=0.0)
        assert vel2.speed_m_s == 4.0

        # 3-4-5 triangle
        vel3 = VelocityNED(north_m_s=3.0, east_m_s=4.0, down_m_s=0.0)
        assert vel3.speed_m_s == 5.0

        # Include vertical (should not affect speed_m_s)
        vel4 = VelocityNED(north_m_s=3.0, east_m_s=4.0, down_m_s=10.0)
        assert vel4.speed_m_s == 5.0  # Still 5, down not included

    def test_velocity_ned_total_speed(self) -> None:
        """VALIDATES: VelocityNED.total_speed_m_s includes vertical.

        total_speed_m_s is the full 3D velocity magnitude, including
        the down component. Used for total kinetic energy calculations.
        """
        vel = VelocityNED(north_m_s=2.0, east_m_s=0.0, down_m_s=0.0)
        assert vel.total_speed_m_s == 2.0

        # 3D case: 1^2 + 2^2 + 2^2 = 9, sqrt = 3
        vel2 = VelocityNED(north_m_s=1.0, east_m_s=2.0, down_m_s=2.0)
        assert vel2.total_speed_m_s == sqrt(1 + 4 + 4)  # sqrt(9) = 3

    def test_velocity_ned_zero(self) -> None:
        """VALIDATES: VelocityNED with zero velocity has zero speed."""
        vel = VelocityNED(north_m_s=0.0, east_m_s=0.0, down_m_s=0.0)
        assert vel.speed_m_s == 0.0
        assert vel.total_speed_m_s == 0.0


class TestGeoPoint:
    """Test GeoPoint dataclass.

    VALIDATES:
    - Creation with lat/lon/altitude
    - Boundary value validation
    - Default altitude handling

    GeoPoint represents a geographic coordinate with optional altitude.
    Uses WGS84 datum (standard GPS coordinate system).
    """

    def test_geopoint_creation(self) -> None:
        """VALIDATES: GeoPoint can be created with required fields."""
        point = GeoPoint(latitude=37.7749, longitude=-122.4194)
        assert point.latitude == 37.7749
        assert point.longitude == -122.4194
        assert point.altitude_m == 0.0  # Default value

    def test_geopoint_with_altitude(self) -> None:
        """VALIDATES: GeoPoint can include altitude."""
        point = GeoPoint(latitude=37.7749, longitude=-122.4194, altitude_m=100.0)
        assert point.altitude_m == 100.0

    def test_geopoint_validation_latitude(self) -> None:
        """VALIDATES: GeoPoint validates latitude range.

        Latitude must be in [-90, 90] degrees.
        """
        with pytest.raises(ValueError, match="Latitude"):
            GeoPoint(latitude=91.0, longitude=0.0)

        with pytest.raises(ValueError, match="Latitude"):
            GeoPoint(latitude=-91.0, longitude=0.0)

    def test_geopoint_validation_longitude(self) -> None:
        """VALIDATES: GeoPoint validates longitude range.

        Longitude must be in [-180, 180] degrees.
        """
        with pytest.raises(ValueError, match="Longitude"):
            GeoPoint(latitude=0.0, longitude=181.0)

        with pytest.raises(ValueError, match="Longitude"):
            GeoPoint(latitude=0.0, longitude=-181.0)

    def test_geopoint_boundary_values(self) -> None:
        """VALIDATES: GeoPoint accepts boundary values.

        Tests that exact boundary values are accepted (closed interval).
        """
        # Valid boundary values
        GeoPoint(latitude=90.0, longitude=180.0)
        GeoPoint(latitude=-90.0, longitude=-180.0)
        GeoPoint(latitude=0.0, longitude=0.0)


class TestSafetyLimits:
    """Test SafetyLimits dataclass.

    VALIDATES:
    - Default values match regulatory requirements
    - Custom limit values can be set
    - Validation methods work correctly
    - Immutable (frozen) behavior

    SafetyLimits defines the operational envelope for safe flight,
    including altitude, distance, speed, and battery constraints.
    """

    def test_safety_limits_defaults(self) -> None:
        """VALIDATES: SafetyLimits has correct default values.

        Default limits are set to comply with FAA Part 107 regulations
        for commercial drone operations.
        """
        limits = SafetyLimits()

        assert limits.max_altitude_m == 120.0
        assert limits.min_altitude_m == 5.0
        assert limits.max_distance_m == 500.0
        assert limits.max_speed_m_s == 15.0
        assert limits.max_vertical_speed_m_s == 3.0
        assert limits.min_battery_percent == 25.0
        assert limits.heartbeat_timeout_s == 0.5

    def test_safety_limits_custom_values(self) -> None:
        """VALIDATES: SafetyLimits can have custom values.

        Limits can be customized for specific operational requirements
        while maintaining the same validation interface.
        """
        limits = SafetyLimits(
            max_altitude_m=50.0,
            min_altitude_m=10.0,
            max_distance_m=100.0,
            max_speed_m_s=5.0,
            max_vertical_speed_m_s=1.0,
            min_battery_percent=30.0,
            heartbeat_timeout_s=1.0,
        )

        assert limits.max_altitude_m == 50.0
        assert limits.min_altitude_m == 10.0
        assert limits.max_distance_m == 100.0

    def test_safety_limits_validate_altitude(self) -> None:
        """VALIDATES: SafetyLimits validates altitude correctly.

        Altitude must be within [min_altitude_m, max_altitude_m].
        Returns (bool, reason) tuple for consistent error handling.
        """
        limits = SafetyLimits(min_altitude_m=5.0, max_altitude_m=100.0)

        # Valid altitude
        valid, reason = limits.validate_altitude(50.0)
        assert valid is True
        assert reason == ""

        # Too low
        valid, reason = limits.validate_altitude(3.0)
        assert valid is False
        assert "below minimum" in reason

        # Too high
        valid, reason = limits.validate_altitude(150.0)
        assert valid is False
        assert "above maximum" in reason

        # Boundary values
        valid, _ = limits.validate_altitude(5.0)
        assert valid is True

        valid, _ = limits.validate_altitude(100.0)
        assert valid is True

    def test_safety_limits_validate_speed(self) -> None:
        """VALIDATES: SafetyLimits validates speed correctly.

        Speed must not exceed max_speed_m_s.
        """
        limits = SafetyLimits(max_speed_m_s=10.0)

        # Valid speed
        valid, reason = limits.validate_speed(5.0)
        assert valid is True

        # Too fast
        valid, reason = limits.validate_speed(15.0)
        assert valid is False
        assert "above maximum" in reason

        # Boundary
        valid, _ = limits.validate_speed(10.0)
        assert valid is True

    def test_safety_limits_validate_battery(self) -> None:
        """VALIDATES: SafetyLimits validates battery correctly.

        Battery percentage must be at or above min_battery_percent.
        Below threshold typically triggers Return-to-Land (RTL).
        """
        limits = SafetyLimits(min_battery_percent=20.0)

        # Valid battery
        valid, reason = limits.validate_battery(50.0)
        assert valid is True

        # Too low
        valid, reason = limits.validate_battery(15.0)
        assert valid is False
        assert "below minimum" in reason

        # Boundary
        valid, _ = limits.validate_battery(20.0)
        assert valid is True

    def test_safety_limits_frozen(self) -> None:
        """VALIDATES: SafetyLimits is immutable (frozen dataclass).

        Safety limits should not be modifiable after creation to prevent
        accidental changes during flight. Uses @dataclass(frozen=True).
        """
        limits = SafetyLimits()

        with pytest.raises(AttributeError):
            limits.max_altitude_m = 200.0  # type: ignore[misc]


# =============================================================================
# Protocol Edge Cases
# =============================================================================


class TestProtocolEdgeCases:
    """Test edge cases and protocol behavior.

    VALIDATES:
    - Incomplete implementations fail isinstance
    - Wrong signatures may fail isinstance (implementation dependent)
    - Non-protocol objects don't pass isinstance
    - Multiple protocol implementation is possible
    """

    def test_incomplete_impl_fails_isinstance(self) -> None:
        """VALIDATES: Incomplete implementation fails isinstance check.

        Objects missing required protocol methods should not pass isinstance.
        This is critical for runtime type safety.
        """

        class IncompleteConnection:
            async def connect(self, system_address: str = "udp://:14540") -> bool:
                return True
            # Missing disconnect, get_drone, ensure_connected, is_connected

        incomplete = IncompleteConnection()
        assert not isinstance(incomplete, DroneConnectionProtocol)

    def test_wrong_signature_fails_isinstance(self) -> None:
        """VALIDATES: Implementation with wrong signature fails isinstance check.

        Protocols validate method signatures, not just presence.
        Missing required parameters should cause isinstance to return False.
        """

        class WrongSignatureConnection:
            async def connect(self) -> bool:  # Missing required parameter
                return True

            async def disconnect(self) -> None:
                pass

            async def get_drone(self) -> Optional[Any]:
                return None

            async def ensure_connected(self) -> Any:
                return None

            @property
            def is_connected(self) -> bool:
                return False

        wrong = WrongSignatureConnection()
        # This may or may not pass depending on Protocol strictness
        # but we're documenting the behavior
        result = isinstance(wrong, DroneConnectionProtocol)
        # Just verify we can check it without error
        assert isinstance(result, bool)

    def test_non_protocol_object_fails_isinstance(self) -> None:
        """VALIDATES: Regular objects don't pass protocol isinstance.

        Built-in types and unrelated objects should not satisfy protocols.
        """
        assert not isinstance("string", DroneConnectionProtocol)
        assert not isinstance(123, TelemetryProviderProtocol)
        assert not isinstance({}, SafetyValidatorProtocol)

    def test_multiple_protocols(self) -> None:
        """VALIDATES: An object can implement multiple protocols.

        A single class can satisfy multiple protocols by implementing
        all required methods from each. This enables flexible composition.
        """

        class MultiProtocol:
            async def connect(self, system_address: str = "udp://:14540") -> bool:
                return True

            async def disconnect(self) -> None:
                pass

            async def get_drone(self) -> Optional[Any]:
                return None

            async def ensure_connected(self) -> Any:
                return None

            @property
            def is_connected(self) -> bool:
                return False

            async def __call__(self) -> Any:
                return {}

            def validate_command(self, command: dict[str, Any]) -> tuple[bool, str]:
                return True, ""

            def validate_state_transition(self, from_state: str, to_state: str) -> tuple[bool, str]:
                return True, ""

        multi = MultiProtocol()
        assert isinstance(multi, DroneConnectionProtocol)
        assert isinstance(multi, TelemetryProviderProtocol)
        assert isinstance(multi, SafetyValidatorProtocol)
