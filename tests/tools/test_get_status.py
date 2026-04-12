"""Tests for get_status MCP tool.

Verifies unified status interface aggregating telemetry, state machine,
connection manager, and guardian data.
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
    """Test that get_status returns all expected fields."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

        # Reset ConnectionManager singleton state
        cm = ConnectionManager()
        cm._state = ConnectionState.DISCONNECTED
        cm._health.is_healthy = False

        yield

        # Cleanup
        set_telemetry_cache(None)
        set_state_machine(None)
        set_guardian(None)

    @pytest.mark.asyncio
    async def test_status_structure(self):
        """Returns all expected fields in status response."""
        status = await get_status()

        # Top-level fields
        assert "timestamp" in status
        assert "success" in status
        assert status["success"] is True

        # Position section
        assert "position" in status
        pos = status["position"]
        assert "lat" in pos
        assert "lon" in pos
        assert "alt_m" in pos
        assert "rel_alt_m" in pos
        assert "heading_deg" in pos

        # Velocity section
        assert "velocity" in status
        vel = status["velocity"]
        assert "north_m_s" in vel
        assert "east_m_s" in vel
        assert "down_m_s" in vel
        assert "groundspeed_m_s" in vel

        # Attitude section
        assert "attitude" in status
        att = status["attitude"]
        assert "roll_deg" in att
        assert "pitch_deg" in att
        assert "yaw_deg" in att

        # Battery section
        assert "battery" in status
        bat = status["battery"]
        assert "percent" in bat
        assert "voltage_v" in bat
        assert "current_a" in bat

        # Flight section
        assert "flight" in status
        flt = status["flight"]
        assert "state" in flt
        assert "armed" in flt
        assert "in_air" in flt
        assert "flight_mode" in flt
        assert "valid_transitions" in flt
        assert isinstance(flt["valid_transitions"], list)

        # Connection section
        assert "connection" in status
        conn = status["connection"]
        assert "connected" in conn
        assert "state" in conn
        assert "health" in conn
        assert "gps_ok" in conn["health"]
        assert "home_ok" in conn["health"]

        # System section
        assert "system" in status
        sys = status["system"]
        assert "alerts" in sys
        assert "cache_age_ms" in sys
        assert "cache_stale" in sys


class TestTelemetryIntegration:
    """Test telemetry cache data integration."""

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

    @pytest.fixture
    def sample_telemetry_data(self):
        """Create sample telemetry data."""
        return TelemetryData(
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

    @pytest.mark.asyncio
    async def test_telemetry_integration(self):
        """Includes telemetry data in status response."""
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

        # Mock the cache data directly
        cache._data = telemetry

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

        # Verify cache status
        assert status["system"]["cache_age_ms"] >= 0
        assert status["system"]["cache_stale"] is False


class TestStateMachineIntegration:
    """Test state machine integration."""

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
        """Includes state machine info in status response."""
        sm = FlightStateMachine()
        set_state_machine(sm)

        status = await get_status()

        # Verify state info
        assert "flight" in status
        assert status["flight"]["state"] == "INIT"
        assert isinstance(status["flight"]["valid_transitions"], list)

        # Should have valid transitions from INIT
        assert len(status["flight"]["valid_transitions"]) > 0
        assert "DISARMED" in status["flight"]["valid_transitions"]

    @pytest.mark.asyncio
    async def test_state_transitions_update(self):
        """Valid transitions update after state change."""
        sm = FlightStateMachine()
        set_state_machine(sm)

        # Start at INIT
        status = await get_status()
        init_transitions = status["flight"]["valid_transitions"]
        assert "DISARMED" in init_transitions

        # Transition to DISARMED
        sm.transition(FlightState.DISARMED, "test", "test")

        status = await get_status()
        disarmed_transitions = status["flight"]["valid_transitions"]
        assert "ARMED" in disarmed_transitions


class TestConnectionIntegration:
    """Test connection manager integration."""

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
        """Includes connection health in status response."""
        set_state_machine(FlightStateMachine())

        status = await get_status()

        # Verify connection section
        assert "connection" in status
        conn = status["connection"]

        # Should have connection state info
        assert "connected" in conn
        assert isinstance(conn["connected"], bool)
        assert "state" in conn
        assert isinstance(conn["state"], str)
        assert "health" in conn

    @pytest.mark.asyncio
    async def test_connection_connected_state(self):
        """Reports connected=True when connection manager is connected."""
        set_state_machine(FlightStateMachine())

        # Mock connection manager to be connected
        cm = ConnectionManager()
        cm._state = ConnectionState.CONNECTED
        cm._health.is_healthy = True

        status = await get_status()

        assert status["connection"]["connected"] is True
        assert status["connection"]["state"] == "CONNECTED"


class TestGuardianIntegration:
    """Test guardian integration."""

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
        """Includes guardian alerts in status response."""
        set_state_machine(FlightStateMachine())

        # Create mock guardian with alerts
        mock_cm = MagicMock()
        mock_hb = MagicMock()
        mock_sm = FlightStateMachine()

        guardian = AsyncGuardian(
            connection_manager=mock_cm,
            heartbeat_service=mock_hb,
            state_machine=mock_sm,
            config=GuardianConfig(),
        )

        # Add a test alert
        test_alert = Alert(
            level="warning",
            source="test",
            message="Test alert message",
            timestamp=time.time(),
        )
        guardian._alerts = [test_alert]

        set_guardian(guardian)

        status = await get_status()

        # Verify alerts section
        assert "system" in status
        assert "alerts" in status["system"]
        assert isinstance(status["system"]["alerts"], list)

        # Should have our test alert
        assert len(status["system"]["alerts"]) == 1
        alert = status["system"]["alerts"][0]
        assert alert["level"] == "warning"
        assert alert["source"] == "test"
        assert alert["message"] == "Test alert message"
        assert "timestamp" in alert

    @pytest.mark.asyncio
    async def test_no_guardian_no_alerts(self):
        """Returns empty alerts when no guardian configured."""
        set_state_machine(FlightStateMachine())
        set_guardian(None)

        status = await get_status()

        assert status["system"]["alerts"] == []


class TestJSONSerialization:
    """Test JSON serialization."""

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
        """Status can be serialized to JSON."""
        set_state_machine(FlightStateMachine())

        status = await get_status()

        # Should serialize without errors
        json_str = json.dumps(status, indent=2)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

        # Should be deserializable
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "timestamp" in parsed

    @pytest.mark.asyncio
    async def test_get_status_tool_returns_json(self):
        """get_status_tool returns JSON string."""
        set_state_machine(FlightStateMachine())

        json_str = await get_status_tool()

        assert isinstance(json_str, str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["success"] is True


class TestEdgeCases:
    """Test edge cases and error handling."""

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
        """Handles missing telemetry cache gracefully."""
        set_state_machine(FlightStateMachine())
        set_telemetry_cache(None)

        status = await get_status()

        # Should still return status with defaults
        assert status["success"] is True
        assert status["system"]["cache_stale"] is True
        assert status["position"]["lat"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_telemetry_cache(self):
        """Handles empty telemetry cache gracefully."""
        set_state_machine(FlightStateMachine())

        cache = TelemetryCache()
        # Don't populate data
        set_telemetry_cache(cache)

        status = await get_status()

        # Should return defaults
        assert status["success"] is True
        assert status["system"]["cache_stale"] is True

    @pytest.mark.asyncio
    async def test_guardian_error_handling(self):
        """Handles guardian errors gracefully."""
        set_state_machine(FlightStateMachine())

        # Create a mock guardian that raises on get_status
        mock_guardian = MagicMock()
        mock_guardian.get_status.side_effect = Exception("Guardian error")

        set_guardian(mock_guardian)

        status = await get_status()

        # Should still succeed with empty alerts
        assert status["success"] is True
        assert status["system"]["alerts"] == []
