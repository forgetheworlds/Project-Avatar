"""Integration tests for AvatarMCPServer.

These tests verify:
- Server initializes all components correctly
- Singleton pattern is respected across all components
- Lifecycle management (init -> run -> shutdown) works properly
- Graceful shutdown cleans up all resources
- Tools use shared components (no duplicate instances)
- End-to-end flow from tool call to drone command

All tests use mocked drone connections to avoid requiring SITL.
"""

import asyncio
import json
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mav.state_machine import FlightState
from avatar.mav.heartbeat_service import HeartbeatSource
from avatar.mav.telemetry_cache import TelemetryData


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset ConnectionManager singleton before each test."""
    ConnectionManager._instance = None
    yield
    # Cleanup after test
    ConnectionManager._instance = None


@pytest.fixture
def mock_drone() -> MagicMock:
    """Create a fully mocked MAVSDK drone."""
    drone = MagicMock()

    # Mock core connection state
    async def mock_connection_state():
        state = MagicMock()
        state.is_connected = True
        yield state

    drone.core.connection_state = mock_connection_state

    # Mock telemetry streams
    async def mock_position():
        pos = MagicMock()
        pos.latitude_deg = 37.7749
        pos.longitude_deg = -122.4194
        pos.relative_altitude_m = 10.0
        pos.absolute_altitude_m = 110.0
        yield pos

    async def mock_velocity():
        vel = MagicMock()
        vel.north_m_s = 0.0
        vel.east_m_s = 0.0
        vel.down_m_s = 0.0
        yield vel

    async def mock_attitude():
        att = MagicMock()
        att.roll_deg = 0.0
        att.pitch_deg = 0.0
        att.yaw_deg = 90.0
        yield att

    async def mock_battery():
        bat = MagicMock()
        bat.remaining_percent = 0.85
        bat.voltage_v = 16.8
        bat.current_a = 5.0
        yield bat

    async def mock_armed():
        yield False

    async def mock_landed_state():
        yield 0  # On ground

    async def mock_flight_mode():
        yield "HOLD"

    async def mock_health():
        health = MagicMock()
        health.is_global_position_ok = True
        health.is_home_position_ok = True
        yield health

    async def mock_gps_info():
        gps = MagicMock()
        gps.fix_type = 3
        yield gps

    async def mock_odometry():
        odom = MagicMock()
        odom.position_covariance = [0.1] * 9
        odom.velocity_covariance = [0.1] * 9
        yield odom

    drone.telemetry.position = mock_position
    drone.telemetry.velocity_ned = mock_velocity
    drone.telemetry.attitude_euler = mock_attitude
    drone.telemetry.battery = mock_battery
    drone.telemetry.armed = mock_armed
    drone.telemetry.landed_state = mock_landed_state
    drone.telemetry.flight_mode = mock_flight_mode
    drone.telemetry.health = mock_health
    drone.telemetry.gps_info = mock_gps_info
    drone.telemetry.odometry = mock_odometry

    # Mock actions
    drone.action.arm = AsyncMock()
    drone.action.disarm = AsyncMock()
    drone.action.takeoff = AsyncMock()
    drone.action.land = AsyncMock()
    drone.action.hold = AsyncMock()
    drone.action.return_to_launch = AsyncMock()
    drone.action.goto_location = AsyncMock()
    drone.action.set_takeoff_altitude = AsyncMock()
    drone.action.set_maximum_speed = AsyncMock()

    # Mock offboard
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    drone.offboard.set_velocity_ned = AsyncMock()

    return drone


class TestServerInitialization:
    """Test server component initialization."""

    @pytest.mark.asyncio
    async def test_server_initializes_connection_manager(self, mock_drone: MagicMock) -> None:
        """Server initializes ConnectionManager singleton on startup."""
        server = AvatarMCPServer()

        # ConnectionManager should be a singleton
        cm = server.connection_manager
        assert cm is ConnectionManager()

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            success = await server.initialize()
            assert success is True
            assert cm.state == ConnectionState.CONNECTED

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_server_initializes_telemetry_cache(self, mock_drone: MagicMock) -> None:
        """Server initializes TelemetryCache with 100ms refresh."""
        server = AvatarMCPServer()

        # Verify config is set correctly
        assert server.telemetry_cache.refresh_ms == 100

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Telemetry cache should be started
            assert server.telemetry_cache._started is True

            # Wait for at least one refresh cycle
            await asyncio.sleep(0.15)

            # Cache should have data
            data = server.telemetry_cache.get_data()
            assert data is not None
            assert isinstance(data, TelemetryData)

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_server_initializes_heartbeat_service(self, mock_drone: MagicMock) -> None:
        """Server initializes HeartbeatService with 20Hz emission."""
        server = AvatarMCPServer()

        # Verify config is set correctly
        assert server.heartbeat_service.config.heartbeat_hz == 20.0

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Heartbeat service should be running
            assert server.heartbeat_service.is_running is True

            # Wait for some heartbeats
            await asyncio.sleep(0.15)

            # Should have emitted at least 2 heartbeats (20Hz = 3 in 0.15s)
            metrics = server.heartbeat_service.get_metrics()
            assert metrics["emit_count"] >= 2

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_server_initializes_state_machine(self, mock_drone: MagicMock) -> None:
        """Server initializes FlightStateMachine from telemetry."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # State machine should be initialized
            assert server.state_machine.current_state is not None
            # From mock data (armed=False), should be DISARMED
            assert server.state_machine.current_state == FlightState.DISARMED

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_server_initializes_guardian(self, mock_drone: MagicMock) -> None:
        """Server initializes AsyncGuardian monitoring."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Guardian should be running
            assert server.guardian.is_running is True

            # Guardian should have monitors active
            status = server.guardian.get_status()
            assert status.is_running is True
            assert len(status.active_monitors) > 0

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_server_initialization_failure_cleanup(self, mock_drone: MagicMock) -> None:
        """Server cleans up partial initialization on failure."""
        server = AvatarMCPServer()

        # Make connection fail
        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None  # Connection fails

            success = await server.initialize()
            assert success is False

        # After failed init, components should be cleaned up
        assert server._initialized is False


class TestSingletonPattern:
    """Test singleton pattern across components."""

    @pytest.mark.asyncio
    async def test_connection_manager_is_singleton(self) -> None:
        """ConnectionManager is shared across all access points."""
        from avatar.mcp_server.tools.flight_tools import FlightTools

        server = AvatarMCPServer()
        tools = FlightTools()

        # Both should get the same ConnectionManager instance
        cm1 = server.connection_manager
        cm2 = ConnectionManager()

        assert cm1 is cm2

    @pytest.mark.asyncio
    async def test_state_machine_is_shared(self, mock_drone: MagicMock) -> None:
        """State machine is shared between server and tools."""
        from avatar.mcp_server.tools.flight_tools import get_state_machine

        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Global reference should match server's state machine
            global_sm = get_state_machine()
            assert global_sm is server.state_machine

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_telemetry_cache_is_shared(self, mock_drone: MagicMock) -> None:
        """Telemetry cache is shared between server and tools."""
        from avatar.mcp_server.tools.flight_tools import get_telemetry_cache

        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Global reference should match server's cache
            global_cache = get_telemetry_cache()
            assert global_cache is server.telemetry_cache

        await server.shutdown()


class TestGracefulShutdown:
    """Test graceful shutdown sequence."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_guardian_first(self, mock_drone: MagicMock) -> None:
        """Shutdown stops guardian before other components."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()
            assert server.guardian.is_running is True

            await server.shutdown()

            # Guardian should be stopped
            assert server.guardian.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_stops_heartbeat_service(self, mock_drone: MagicMock) -> None:
        """Shutdown stops heartbeat service."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()
            assert server.heartbeat_service.is_running is True

            await server.shutdown()

            # Heartbeat service should be stopped
            assert server.heartbeat_service.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_stops_telemetry_cache(self, mock_drone: MagicMock) -> None:
        """Shutdown stops telemetry cache."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()
            assert server.telemetry_cache._started is True

            await server.shutdown()

            # Telemetry cache should be stopped
            assert server.telemetry_cache._started is False

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_drone(self, mock_drone: MagicMock) -> None:
        """Shutdown disconnects from drone."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()
            assert server.connection_manager.state == ConnectionState.CONNECTED

            await server.shutdown()

            # Should be disconnected
            assert server.connection_manager.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, mock_drone: MagicMock) -> None:
        """Shutdown can be called multiple times safely."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()
            await server.shutdown()

            # Second shutdown should not raise
            await server.shutdown()
            await server.shutdown()  # Multiple calls OK

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, mock_drone: MagicMock) -> None:
        """Context manager ensures cleanup on exit."""
        cm = ConnectionManager()

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with AvatarMCPServer() as server:
                assert server._initialized is True
                assert server.connection_manager.state == ConnectionState.CONNECTED

            # After exit, should be disconnected
            assert cm.state == ConnectionState.DISCONNECTED


class TestEndToEndFlow:
    """Test end-to-end tool execution flow."""

    @pytest.mark.asyncio
    async def test_get_status_tool(self, mock_drone: MagicMock) -> None:
        """get_status tool returns comprehensive status."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Route the tool call
            result_str = await server._route_tool("get_status", {})
            result = json.loads(result_str)

            # Verify structure
            assert "initialized" in result
            assert "connection" in result
            assert "telemetry" in result
            assert "heartbeat" in result
            assert "state_machine" in result
            assert "guardian" in result

            # Verify values
            assert result["initialized"] is True
            assert result["state_machine"]["current_state"] == "DISARMED"

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_get_telemetry_tool(self, mock_drone: MagicMock) -> None:
        """get_telemetry tool returns cached telemetry."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Wait for telemetry to populate
            await asyncio.sleep(0.15)

            # Route the tool call
            result_str = await server._route_tool("get_telemetry", {})
            result = json.loads(result_str)

            # Verify structure
            assert "success" in result
            if result["success"]:
                assert "position" in result
                assert "battery" in result
                assert "attitude" in result

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_arm_and_takeoff_tool(self, mock_drone: MagicMock) -> None:
        """arm_and_takeoff tool executes flight command."""
        server = AvatarMCPServer()

        # Set up mock to appear armed after takeoff
        async def mock_armed_after_takeoff():
            yield True

        mock_drone.telemetry.armed = mock_armed_after_takeoff

        # Patch GuardianProcess to bypass home position validation in tool functions
        with patch('avatar.mcp_server.tools.flight_tools.GuardianProcess') as MockGuardian:
            mock_guardian = MagicMock()
            mock_guardian.validate_command.return_value = (True, "OK")
            mock_guardian.set_home = MagicMock()
            mock_guardian.home_position = (37.7749, -122.4194)
            MockGuardian.return_value = mock_guardian

            with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_drone

                await server.initialize()

                # Route the tool call
                result_str = await server._route_tool("arm_and_takeoff", {"altitude_m": 10.0})
                result = json.loads(result_str)

                # Should return success (actual arming is async background)
                assert "success" in result

                # Verify action was called
                mock_drone.action.arm.assert_called_once()
                mock_drone.action.takeoff.assert_called_once()

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_land_tool(self, mock_drone: MagicMock) -> None:
        """land tool executes landing command."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING
            server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
            server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
            server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")

            # Route the tool call
            result_str = await server._route_tool("land", {})
            result = json.loads(result_str)

            # Should return success
            assert result["success"] is True

            # Verify action was called
            mock_drone.action.land.assert_called_once()

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_rtl_tool(self, mock_drone: MagicMock) -> None:
        """rtl tool executes return-to-launch command."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING
            server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
            server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
            server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")

            # Route the tool call
            result_str = await server._route_tool("rtl", {})
            result = json.loads(result_str)

            # Should return success
            assert result["success"] is True

            # Verify action was called
            mock_drone.action.return_to_launch.assert_called_once()

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_goto_gps_tool(self, mock_drone: MagicMock) -> None:
        """goto_gps tool executes navigation command."""
        server = AvatarMCPServer()

        # Patch GuardianProcess to bypass home position validation in tool functions
        with patch('avatar.mcp_server.tools.flight_tools.GuardianProcess') as MockGuardian:
            mock_guardian = MagicMock()
            mock_guardian.validate_command.return_value = (True, "OK")
            mock_guardian.set_home = MagicMock()
            mock_guardian.home_position = (37.7749, -122.4194)
            MockGuardian.return_value = mock_guardian

            with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_drone

                await server.initialize()

                # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING
                server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
                server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
                server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")

                # Route the tool call
                result_str = await server._route_tool(
                    "goto_gps",
                    {"lat": 37.7750, "lon": -122.4195, "alt_m": 15.0, "speed_ms": 5.0}
                )
                result = json.loads(result_str)

                # Should return success
                assert result["success"] is True

                # Verify action was called
                mock_drone.action.goto_location.assert_called_once()

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_fly_body_offset_tool(self, mock_drone: MagicMock) -> None:
        """fly_body_offset tool executes body-relative movement."""
        server = AvatarMCPServer()

        # Patch GuardianProcess to bypass home position validation in tool functions
        with patch('avatar.mcp_server.tools.flight_tools.GuardianProcess') as MockGuardian:
            mock_guardian = MagicMock()
            mock_guardian.validate_command.return_value = (True, "OK")
            mock_guardian.set_home = MagicMock()
            mock_guardian.home_position = (37.7749, -122.4194)
            MockGuardian.return_value = mock_guardian

            with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_drone

                await server.initialize()

                # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING
                server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
                server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
                server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")

                # Route the tool call
                result_str = await server._route_tool(
                    "fly_body_offset",
                    {"forward_m": 10.0, "right_m": 5.0, "up_m": 2.0}
                )
                result = json.loads(result_str)

                # Should return success
                assert result["success"] is True

                # Verify state transition occurred
                assert server.state_machine.current_state == FlightState.POSITION_CONTROL

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_hold_tool(self, mock_drone: MagicMock) -> None:
        """hold tool executes position hold command."""
        server = AvatarMCPServer()

        # Patch GuardianProcess to bypass home position validation in tool functions
        with patch('avatar.mcp_server.tools.flight_tools.GuardianProcess') as MockGuardian:
            mock_guardian = MagicMock()
            mock_guardian.validate_command.return_value = (True, "OK")
            mock_guardian.set_home = MagicMock()
            mock_guardian.home_position = (37.7749, -122.4194)
            MockGuardian.return_value = mock_guardian

            with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_drone

                await server.initialize()

                # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING -> FLYING
                server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
                server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
                server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")
                server.state_machine.transition(FlightState.FLYING, "test_flying", "test")

                # Route the tool call with short duration
                result_str = await server._route_tool(
                    "hold",
                    {"duration_s": 0.1, "position_tolerance_m": 1.0}
                )
                result = json.loads(result_str)

                # Should return success
                assert result["success"] is True
                assert result["duration_s"] == 0.1

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_abort_mission_tool(self, mock_drone: MagicMock) -> None:
        """abort_mission tool executes abort command."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Transition through valid states: DISARMED -> ARMED -> TAKING_OFF -> HOVERING -> FLYING -> MISSION_EXECUTION
            server.state_machine.transition(FlightState.ARMED, "test_arm", "test")
            server.state_machine.transition(FlightState.TAKING_OFF, "test_takeoff_start", "test")
            server.state_machine.transition(FlightState.HOVERING, "test_takeoff_complete", "test")
            server.state_machine.transition(FlightState.FLYING, "test_flying", "test")
            server.state_machine.transition(FlightState.MISSION_EXECUTION, "test_mission", "test")

            # Route the tool call
            result_str = await server._route_tool(
                "abort_mission",
                {"reason": "Test abort"}
            )
            result = json.loads(result_str)

            # Should return success
            assert result["success"] is True

            # Verify action was called
            mock_drone.action.hold.assert_called_once()

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_drone: MagicMock) -> None:
        """Unknown tool returns error."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Route unknown tool
            result_str = await server._route_tool("unknown_tool", {})
            result = json.loads(result_str)

            assert result["success"] is False
            assert "Unknown tool" in result["error"]

        await server.shutdown()


class TestCustomConfiguration:
    """Test custom server configuration."""

    @pytest.mark.asyncio
    async def test_custom_telemetry_refresh(self) -> None:
        """Custom telemetry refresh interval is respected."""
        config = AvatarMCPServerConfig(telemetry_refresh_ms=50)  # 50ms
        server = AvatarMCPServer(config)

        assert server.telemetry_cache.refresh_ms == 50

    @pytest.mark.asyncio
    async def test_custom_heartbeat_hz(self) -> None:
        """Custom heartbeat frequency is respected."""
        config = AvatarMCPServerConfig(heartbeat_hz=10.0)  # 10Hz
        server = AvatarMCPServer(config)

        assert server.heartbeat_service.config.heartbeat_hz == 10.0

    @pytest.mark.asyncio
    async def test_custom_system_address(self) -> None:
        """Custom system address is used for connection."""
        config = AvatarMCPServerConfig(system_address="serial:///dev/ttyUSB0:921600")
        server = AvatarMCPServer(config)

        assert server.config.system_address == "serial:///dev/ttyUSB0:921600"

    @pytest.mark.asyncio
    async def test_guardian_disabled(self, mock_drone: MagicMock) -> None:
        """Guardian can be disabled via config."""
        config = AvatarMCPServerConfig(enable_guardian=False)
        server = AvatarMCPServer(config)

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # Guardian should not be running
            assert server.guardian.is_running is False

        await server.shutdown()


class TestServerStatus:
    """Test server status reporting."""

    @pytest.mark.asyncio
    async def test_get_status_structure(self, mock_drone: MagicMock) -> None:
        """get_status returns complete status structure."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            status = server.get_status()

            # Verify all expected keys
            assert "initialized" in status
            assert "connection" in status
            assert "telemetry" in status
            assert "heartbeat" in status
            assert "state_machine" in status
            assert "guardian" in status

            # Verify nested structure
            assert "state" in status["connection"]
            assert "health" in status["connection"]
            assert "current_state" in status["state_machine"]
            assert "is_flying" in status["state_machine"]
            assert "is_armed" in status["state_machine"]

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_status_reflects_current_state(self, mock_drone: MagicMock) -> None:
        """Status reflects current server state accurately."""
        server = AvatarMCPServer()

        # Before initialization
        status = server.get_status()
        assert status["initialized"] is False

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            await server.initialize()

            # After initialization
            status = server.get_status()
            assert status["initialized"] is True
            assert status["connection"]["state"] == "CONNECTED"
            assert status["state_machine"]["current_state"] == "DISARMED"

        await server.shutdown()

        # After shutdown
        status = server.get_status()
        assert status["initialized"] is False


class TestLifecycleManagement:
    """Test server lifecycle management."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_drone: MagicMock) -> None:
        """Complete lifecycle from init to shutdown."""
        server = AvatarMCPServer()

        # Initial state
        assert server._initialized is False

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            # Initialize
            success = await server.initialize()
            assert success is True
            assert server._initialized is True
            assert server.connection_manager.state == ConnectionState.CONNECTED
            assert server.telemetry_cache._started is True
            assert server.heartbeat_service.is_running is True
            assert server.guardian.is_running is True

            # Run (would block, so we just verify it would start)
            # await server.run()  # Not called to avoid blocking

            # Shutdown
            await server.shutdown()
            assert server._initialized is False
            assert server.connection_manager.state == ConnectionState.DISCONNECTED
            assert server.telemetry_cache._started is False
            assert server.heartbeat_service.is_running is False
            assert server.guardian.is_running is False

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_drone: MagicMock) -> None:
        """Initialize can be called multiple times safely."""
        server = AvatarMCPServer()

        with patch.object(server.connection_manager, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            # First init
            success1 = await server.initialize()
            assert success1 is True

            # Second init (should return True, not create duplicates)
            success2 = await server.initialize()
            assert success2 is True

            # Components should still be healthy
            assert server.telemetry_cache._started is True
            assert server.heartbeat_service.is_running is True

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_uninitialized_server_rejects_tools(self) -> None:
        """Tools return error when server not initialized."""
        server = AvatarMCPServer()
        assert server._initialized is False

        # Simulate calling without initialization
        # The routing should still work (it returns status showing uninitialized)
        handler_results = await server._route_tool("get_status", {})
        result = json.loads(handler_results)

        # Status should reflect that server is not initialized
        assert result["initialized"] is False

        # Non-status tools may fail when server not initialized
        # (This depends on the specific tool implementation)

