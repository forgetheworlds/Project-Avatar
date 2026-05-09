"""Tests for get_status MCP tool.

Verifies unified status interface aggregating telemetry, state machine,
connection manager, and guardian data.

The get_status tool provides a comprehensive snapshot of the drone's current
state by combining data from multiple subsystems:
- TelemetryCache: Position, velocity, attitude, battery from MAVSDK
- FlightStateMachine: Current flight state and valid transitions
- ConnectionManager: Connection health and state
- AsyncGuardian: Active safety alerts and warnings

Status Response Structure:
-------------------------
{
    "timestamp": float,          # Unix timestamp of status generation
    "success": bool,             # Always True unless internal error
    "position": {                # GPS and altitude data
        "lat": float,            # Latitude in degrees
        "lon": float,            # Longitude in degrees
        "alt_m": float,          # Absolute altitude in meters (AMSL)
        "rel_alt_m": float,      # Relative altitude in meters (above home)
        "heading_deg": float     # Heading in degrees (0-360)
    },
    "velocity": {                # Velocity components
        "north_m_s": float,    # North velocity in m/s
        "east_m_s": float,     # East velocity in m/s
        "down_m_s": float,     # Down velocity in m/s (positive = descending)
        "groundspeed_m_s": float  # Horizontal ground speed in m/s
    },
    "attitude": {              # Aircraft orientation
        "roll_deg": float,     # Roll angle in degrees
        "pitch_deg": float,    # Pitch angle in degrees
        "yaw_deg": float       # Yaw angle in degrees
    },
    "battery": {               # Battery status
        "percent": float,      # Remaining capacity percentage
        "voltage_v": float,    # Battery voltage in volts
        "current_a": float     # Current draw in amperes
    },
    "flight": {                # Flight state information
        "state": str,          # Current state (INIT, DISARMED, ARMED, etc.)
        "armed": bool,         # Whether motors are armed
        "in_air": bool,        # Whether aircraft is airborne
        "flight_mode": str,    # PX4 flight mode (MANUAL, OFFBOARD, etc.)
        "valid_transitions": []  # List of valid next states from current state
    },
    "connection": {            # Connection health
        "connected": bool,     # Whether connected to drone
        "state": str,          # Connection state string
        "health": {
            "gps_ok": bool,    # Whether GPS has good fix
            "home_ok": bool    # Whether home position is set
        }
    },
    "system": {                # System-level information
        "alerts": [],          # List of active guardian alerts
        "cache_age_ms": int,   # Age of telemetry data in milliseconds
        "cache_stale": bool    # True if telemetry data is outdated
    }
}

Mock Setup Explanation:
-----------------------
Tests use a fixture pattern with `setup_test` to isolate each test case:
1. Reset singletons (telemetry_cache, state_machine, guardian) to None
2. Reset ConnectionManager's internal state to disconnected/unhealthy
3. Yield control to the test
4. Cleanup after test completion

This ensures each test starts with a clean state and cannot be affected
by previous test runs.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from avatar.mcp_server.tools.telemetry_tools import (
    get_status,
    get_status_tool,
    set_guardian,
    set_state_machine,
    set_telemetry_cache,
)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mav.guardian_async import Alert, AsyncGuardian, GuardianConfig, GuardianStatus
from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData


class TestGetStatusStructure:
    """Test that get_status returns all expected fields.

    These tests verify the structural integrity of the status response
    without requiring actual drone connection. They ensure all required
    sections are present and have the correct types.
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test.

        This fixture runs automatically for every test in this class due to
        autouse=True. It ensures complete isolation between tests by:
        - Clearing the telemetry cache singleton
        - Clearing the state machine singleton
        - Clearing the guardian singleton
        - Resetting ConnectionManager to disconnected state
        """
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

        # Reset ConnectionManager singleton state
        cm = ConnectionManager()
        cm._state = ConnectionState.DISCONNECTED
        cm._health.is_healthy = False

        yield

        # Cleanup after test
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_status_structure(self):
        """Returns all expected fields in status response.

        Validates that the status dictionary contains all required top-level
        and nested fields. This test does not check values, only presence
        and basic type checking.

        Assertions check:
        - Top-level fields: timestamp, success
        - Position section: lat, lon, alt_m, rel_alt_m, heading_deg
        - Velocity section: north_m_s, east_m_s, down_m_s, groundspeed_m_s
        - Attitude section: roll_deg, pitch_deg, yaw_deg
        - Battery section: percent, voltage_v, current_a
        - Flight section: state, armed, in_air, flight_mode, valid_transitions
        - Connection section: connected, state, health (with gps_ok, home_ok)
        - System section: alerts, cache_age_ms, cache_stale
        """
        status = await get_status()

        # Top-level fields - timestamp is Unix epoch float, success is boolean
        assert "timestamp" in status
        assert "success" in status
        assert status["success"] is True

        # Position section - GPS coordinates and altitude data
        assert "position" in status
        pos = status["position"]
        assert "lat" in pos          # Latitude: -90 to 90 degrees
        assert "lon" in pos          # Longitude: -180 to 180 degrees
        assert "alt_m" in pos        # Absolute altitude (AMSL) in meters
        assert "rel_alt_m" in pos    # Relative altitude (above takeoff) in meters
        assert "heading_deg" in pos  # Heading in degrees, 0 = North

        # Velocity section - NED (North-East-Down) velocity components
        assert "velocity" in status
        vel = status["velocity"]
        assert "north_m_s" in vel      # North component (positive = north)
        assert "east_m_s" in vel       # East component (positive = east)
        assert "down_m_s" in vel       # Down component (positive = descending)
        assert "groundspeed_m_s" in vel  # Horizontal speed (magnitude of N/E)

        # Attitude section - Aircraft orientation in degrees
        assert "attitude" in status
        att = status["attitude"]
        assert "roll_deg" in att   # Roll: -180 to 180, positive = right bank
        assert "pitch_deg" in att  # Pitch: -90 to 90, positive = nose up
        assert "yaw_deg" in att    # Yaw: 0 to 360, 0/360 = North

        # Battery section - Power system status
        assert "battery" in status
        bat = status["battery"]
        assert "percent" in bat   # Remaining capacity 0-100%
        assert "voltage_v" in bat # Battery voltage (e.g., 16.8V for 4S)
        assert "current_a" in bat # Current draw (positive = discharging)

        # Flight section - Flight state machine information
        assert "flight" in status
        flt = status["flight"]
        assert "state" in flt              # Current state (INIT, DISARMED, etc.)
        assert "armed" in flt              # True if motors are spinning
        assert "in_air" in flt             # True if airborne
        assert "flight_mode" in flt        # PX4 mode string
        assert "valid_transitions" in flt  # List of allowed next states
        assert isinstance(flt["valid_transitions"], list)

        # Connection section - Link health monitoring
        assert "connection" in status
        conn = status["connection"]
        assert "connected" in conn  # Boolean connection status
        assert "state" in conn      # ConnectionState as string
        assert "health" in conn     # Nested health indicators
        assert "gps_ok" in conn["health"]   # True if GPS has 3D fix
        assert "home_ok" in conn["health"]  # True if home position set

        # System section - Alerts and telemetry freshness
        assert "system" in status
        sys = status["system"]
        assert "alerts" in sys        # List of active guardian alerts
        assert "cache_age_ms" in sys  # Telemetry age in milliseconds
        assert "cache_stale" in sys   # True if data is outdated (>5s old)


class TestTelemetryIntegration:
    """Test telemetry cache data integration.

    These tests verify that get_status correctly extracts and formats
data from the TelemetryCache singleton. The TelemetryCache receives
MAVSDK telemetry messages and stores the latest values.
"""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test.

        Ensures each telemetry test starts with clean state to prevent
        cross-test contamination from singleton state.
        """
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.fixture
    def sample_telemetry_data(self):
        """Create sample telemetry data.

        Returns a TelemetryData dataclass instance with realistic values
        for testing. This fixture provides consistent test data that
        matches what MAVSDK would send from a flying drone.

        Values represent:
        - Position: San Francisco coordinates, 10m altitude
        - Velocity: 2.5 m/s ground speed, slight climb
        - Attitude: Near level flight, NE heading (0.785 rad = 45 deg)
        - Battery: 85% charge, 16.8V (4S LiPo), 5.2A draw
        - State: Armed, in air, OFFBOARD mode
        """
        return TelemetryData(
            timestamp=time.time(),
            latitude=37.7749,       # San Francisco latitude
            longitude=-122.4194,    # San Francisco longitude
            altitude=10.0,          # 10 meters AMSL
            velocity_north=1.5,     # Moving north at 1.5 m/s
            velocity_east=2.0,      # Moving east at 2.0 m/s
            velocity_down=-0.5,     # Climbing at 0.5 m/s (negative = up)
            groundspeed=2.5,        # Total horizontal speed
            roll=0.1,               # Slight right bank (0.1 rad = ~6 deg)
            pitch=0.05,             # Slight nose up (0.05 rad = ~3 deg)
            yaw=0.785,              # Northeast heading (45 degrees)
            battery_percent=85.0,   # 85% remaining
            battery_voltage=16.8,   # 4S LiPo nominal voltage
            battery_current=5.2,    # 5.2A discharge current
            armed=True,             # Motors armed
            in_air=True,            # Airborne
            flight_mode="OFFBOARD", # Autonomous control mode
            gps_fix=3,              # 3D GPS fix
            is_gps_ok=True,         # GPS healthy
            is_home_position_ok=True,  # Home position set
        )

    @pytest.mark.asyncio
    async def test_telemetry_integration(self):
        """Includes telemetry data in status response.

        Validates that get_status correctly extracts data from TelemetryCache
        and formats it into the status dictionary. Uses direct cache._data
        assignment to inject test telemetry without requiring MAVSDK connection.

        Test steps:
        1. Create TelemetryCache instance
        2. Inject test telemetry via cache._data (mock approach)
        3. Register cache with set_telemetry_cache()
        4. Create FlightStateMachine (required dependency)
        5. Call get_status() and verify all telemetry fields

        Verifies:
        - Position data matches injected values (lat, lon, alt, heading)
        - Velocity data matches (NED components + groundspeed)
        - Attitude data matches (roll, pitch, yaw in degrees)
        - Battery data matches (percent, voltage, current)
        - Flight state flags match (armed, in_air, flight_mode)
        - Connection health flags match (gps_ok, home_ok)
        - Cache status is fresh (cache_stale=False, age >= 0)
        """
        # Create and populate telemetry cache
        cache = TelemetryCache()

        telemetry = TelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
            altitude=10.0,
            velocity_north=1.5,
            velocity_east=2.0,
            velocity_down=-0.5,
            groundspeed=2.5,
            roll=0.1,
            pitch=0.05,
            yaw=0.785,
            battery_percent=85.0,
            battery_voltage=16.8,
            battery_current=5.2,
            armed=True,
            in_air=True,
            flight_mode="OFFBOARD",
            gps_fix=3,
            is_gps_ok=True,
            is_home_position_ok=True,
        )

        # Mock the cache data directly by setting internal _data attribute
        # This bypasses the normal MAVSDK subscription flow for unit testing
        cache._data = telemetry

        # Register singletons with get_status tool
        set_telemetry_cache(cache)
        set_state_machine(FlightStateMachine())

        status = await get_status()

        # Verify position data from telemetry
        assert status["position"]["lat"] == pytest.approx(37.7749, abs=0.0001)
        assert status["position"]["lon"] == pytest.approx(-122.4194, abs=0.0001)
        assert status["position"]["alt_m"] == pytest.approx(10.0, abs=0.1)
        assert status["position"]["heading_deg"] == pytest.approx(0.785, abs=0.001)

        # Verify velocity data
        assert status["velocity"]["north_m_s"] == pytest.approx(1.5, abs=0.01)
        assert status["velocity"]["east_m_s"] == pytest.approx(2.0, abs=0.01)
        assert status["velocity"]["down_m_s"] == pytest.approx(-0.5, abs=0.01)
        assert status["velocity"]["groundspeed_m_s"] == pytest.approx(2.5, abs=0.01)

        # Verify attitude data
        assert status["attitude"]["roll_deg"] == pytest.approx(0.1, abs=0.001)
        assert status["attitude"]["pitch_deg"] == pytest.approx(0.05, abs=0.001)
        assert status["attitude"]["yaw_deg"] == pytest.approx(0.785, abs=0.001)

        # Verify battery data
        assert status["battery"]["percent"] == pytest.approx(85.0, abs=0.1)
        assert status["battery"]["voltage_v"] == pytest.approx(16.8, abs=0.1)
        assert status["battery"]["current_a"] == pytest.approx(5.2, abs=0.1)

        # Verify flight state from telemetry
        assert status["flight"]["armed"] is True
        assert status["flight"]["in_air"] is True
        assert status["flight"]["flight_mode"] == "OFFBOARD"

        # Verify connection health from telemetry
        assert status["connection"]["health"]["gps_ok"] is True
        assert status["connection"]["health"]["home_ok"] is True

        # Verify cache status - should be fresh since we just created it
        assert status["system"]["cache_age_ms"] >= 0
        assert status["system"]["cache_stale"] is False


class TestStateMachineIntegration:
    """Test state machine integration.

    Verifies that get_status correctly reports the current flight state
    from the FlightStateMachine and lists valid state transitions.

    The FlightStateMachine enforces safe state transitions for drone
    operations (e.g., can only arm from DISARMED state).
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_state_machine_integration(self):
        """Includes state machine info in status response.

        Validates that get_status reports:
        - Current flight state (starts in INIT after creation)
        - List of valid transitions from current state

        FlightStateMachine states: INIT → DISARMED → ARMED → FLYING → LANDING
        Each state has specific allowed next states for safety.
        """
        sm = FlightStateMachine()
        set_state_machine(sm)

        status = await get_status()

        # Verify state info section exists
        assert "flight" in status
        assert status["flight"]["state"] == "INIT"  # Default initial state
        assert isinstance(status["flight"]["valid_transitions"], list)

        # Should have valid transitions from INIT (at minimum can go to DISARMED)
        assert len(status["flight"]["valid_transitions"]) > 0
        assert "DISARMED" in status["flight"]["valid_transitions"]

    @pytest.mark.asyncio
    async def test_state_transitions_update(self):
        """Valid transitions update after state change.

        Tests that get_status reflects state changes and updates the
        valid_transitions list accordingly.

        State flow tested: INIT → DISARMED → ARMED
        """
        sm = FlightStateMachine()
        set_state_machine(sm)

        # Start at INIT state
        status = await get_status()
        init_transitions = status["flight"]["valid_transitions"]
        assert "DISARMED" in init_transitions

        # Transition to DISARMED state
        sm.transition(FlightState.DISARMED, "test", "test")

        status = await get_status()
        disarmed_transitions = status["flight"]["valid_transitions"]
        # From DISARMED, should be able to arm
        assert "ARMED" in disarmed_transitions


class TestConnectionIntegration:
    """Test connection manager integration.

    Verifies that get_status reports connection state and health
    from the ConnectionManager singleton.

    ConnectionManager handles MAVSDK connection lifecycle and tracks:
    - Connection state: DISCONNECTED → CONNECTING → CONNECTED
    - Health indicators: GPS fix quality, home position status
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_connection_integration(self):
        """Includes connection health in status response.

        Validates connection section structure with default (disconnected) state.
        """
        set_state_machine(FlightStateMachine())

        status = await get_status()

        # Verify connection section exists with expected fields
        assert "connection" in status
        conn = status["connection"]

        # Should have connection state info even when disconnected
        assert "connected" in conn
        assert isinstance(conn["connected"], bool)
        assert "state" in conn
        assert isinstance(conn["state"], str)
        assert "health" in conn

    @pytest.mark.asyncio
    async def test_connection_connected_state(self):
        """Reports connected=True when connection manager is connected.

        Uses direct state manipulation of ConnectionManager singleton to
        simulate a connected state without requiring actual drone connection.
        """
        set_state_machine(FlightStateMachine())

        # Mock connection manager to be connected by setting internal state
        cm = ConnectionManager()
        cm._state = ConnectionState.CONNECTED
        cm._health.is_healthy = True

        status = await get_status()

        assert status["connection"]["connected"] is True
        assert status["connection"]["state"] == "CONNECTED"


class TestGuardianIntegration:
    """Test guardian integration.

    Verifies that get_status includes active alerts from the AsyncGuardian
    safety monitoring system.

    AsyncGuardian continuously monitors:
    - Telemetry health (stale data detection)
    - Battery levels (low battery warnings)
    - Geofence violations
    - State machine consistency

    Alerts have levels: info, warning, critical
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_guardian_integration(self):
        """Includes guardian alerts in status response.

        Creates a mock guardian with a test alert and verifies it appears
        in the status response's system.alerts array.

        Alert structure:
        - level: "info" | "warning" | "critical"
        - source: Component that generated the alert
        - message: Human-readable description
        - timestamp: Unix epoch when alert was created
        """
        set_state_machine(FlightStateMachine())

        # Create mock guardian with alerts
        mock_cm = MagicMock()  # Mock ConnectionManager
        mock_hb = MagicMock()  # Mock HeartbeatService
        mock_sm = FlightStateMachine()

        guardian = AsyncGuardian(
            connection_manager=mock_cm,
            heartbeat_service=mock_hb,
            state_machine=mock_sm,
            config=GuardianConfig(),
        )

        # Add a test alert directly to guardian's internal alert list
        test_alert = Alert(
            level="warning",
            source="test",
            message="Test alert message",
            timestamp=time.time(),
        )
        guardian._alerts = [test_alert]

        set_guardian(guardian)

        status = await get_status()

        # Verify alerts section structure
        assert "system" in status
        assert "alerts" in status["system"]
        assert isinstance(status["system"]["alerts"], list)

        # Should contain our injected test alert
        assert len(status["system"]["alerts"]) == 1
        alert = status["system"]["alerts"][0]
        assert alert["level"] == "warning"
        assert alert["source"] == "test"
        assert alert["message"] == "Test alert message"
        assert "timestamp" in alert

    @pytest.mark.asyncio
    async def test_no_guardian_no_alerts(self):
        """Returns empty alerts when no guardian configured.

        When guardian singleton is None, get_status should gracefully
        handle the missing dependency and return an empty alerts list.
        """
        set_state_machine(FlightStateMachine())
        set_guardian(None)  # Explicitly ensure no guardian

        status = await get_status()

        assert status["system"]["alerts"] == []


class TestJSONSerialization:
    """Test JSON serialization.

    Verifies that status responses can be serialized to JSON for
    transmission over the MCP protocol.

    MCP tools communicate via JSON-RPC, so all responses must be
    JSON-serializable.
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_json_serializable(self):
        """Status can be serialized to JSON.

        Validates that the status dictionary returned by get_status()
        can be converted to a JSON string and parsed back without
        data loss.
        """
        set_state_machine(FlightStateMachine())

        status = await get_status()

        # Serialize to JSON string (indent=2 for readability in logs)
        json_str = json.dumps(status, indent=2)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

        # Deserialize and verify structure intact
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "timestamp" in parsed

    @pytest.mark.asyncio
    async def test_get_status_tool_returns_json(self):
        """get_status_tool returns JSON string.

        The MCP tool wrapper get_status_tool() should return a JSON
        string directly (not a Python dict), as required by the
        MCP protocol for tool responses.
        """
        set_state_machine(FlightStateMachine())

        json_str = await get_status_tool()

        assert isinstance(json_str, str)

        # Should be valid JSON that parses to a dict with success=True
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["success"] is True


class TestEdgeCases:
    """Test edge cases and error handling.

    Validates graceful handling of missing or incomplete dependencies.
    The get_status tool should never raise exceptions - it should
    return partial data with appropriate defaults when components
    are unavailable.
    """

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)
        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_no_telemetry_cache(self):
        """Handles missing telemetry cache gracefully.

        When telemetry_cache singleton is None, get_status should:
        - Still return success=True
        - Mark cache as stale (cache_stale=True)
        - Return default values (0.0) for position

        This allows status to work before telemetry is initialized.
        """
        set_state_machine(FlightStateMachine())
        set_telemetry_cache(None)

        status = await get_status()

        # Should return status with defaults rather than raising
        assert status["success"] is True
        assert status["system"]["cache_stale"] is True  # No cache = stale
        assert status["position"]["lat"] == 0.0  # Default position

    @pytest.mark.asyncio
    async def test_empty_telemetry_cache(self):
        """Handles empty telemetry cache gracefully.

        When telemetry cache exists but has no data (never received
        MAVSDK messages), get_status should:
        - Still return success=True
        - Mark cache as stale
        - Return default/zero values
        """
        set_state_machine(FlightStateMachine())

        cache = TelemetryCache()
        # Don't populate data - leave cache empty
        set_telemetry_cache(cache)

        status = await get_status()

        # Should return defaults rather than failing
        assert status["success"] is True
        assert status["system"]["cache_stale"] is True

    @pytest.mark.asyncio
    async def test_guardian_error_handling(self):
        """Handles guardian errors gracefully.

        When guardian.get_status() raises an exception, get_status
        should catch the error and return empty alerts rather than
        propagating the exception.

        This tests the error handling wrapper around guardian integration.
        """
        set_state_machine(FlightStateMachine())

        # Create a mock guardian that raises Exception on get_status()
        mock_guardian = MagicMock()
        mock_guardian.get_status.side_effect = Exception("Guardian error")

        set_guardian(mock_guardian)

        status = await get_status()

        # Should still succeed with empty alerts instead of raising
        assert status["success"] is True
        assert status["system"]["alerts"] == []
