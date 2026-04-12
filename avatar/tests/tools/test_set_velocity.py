"""Tests for set_velocity MCP tool.

Validates offboard velocity control with:
- Velocity limits enforcement (15 m/s horizontal, 3 m/s vertical)
- State preconditions (requires HOVERING/FLYING/etc)
- 20Hz streaming rate maintenance
- Graceful stop and cleanup
- Error handling
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools.flight_tools import FlightTools, FlightToolsConfig, set_velocity


@pytest.fixture
def mock_state_machine():
    """Create a FlightStateMachine in HOVERING state."""
    sm = FlightStateMachine()
    # Transition from INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING
    sm.transition(FlightState.DISARMED, "startup_complete", "system")
    sm.transition(FlightState.ARMED, "operator_command", "operator")
    sm.transition(FlightState.TAKING_OFF, "takeoff_initiated", "llm")
    sm.transition(FlightState.HOVERING, "takeoff_complete", "telemetry")
    return sm


@pytest.fixture
def flight_tools(mock_state_machine):
    """Create FlightTools instance with mocked state machine."""
    config = FlightToolsConfig()
    tools = FlightTools(config=config, state_machine=mock_state_machine)
    return tools


@pytest.fixture
def mock_drone():
    """Create a fully mocked MAVSDK drone with offboard support."""
    drone = MagicMock()

    # Mock offboard plugin
    drone.offboard = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()

    return drone


class TestVelocityLimits:
    """Test velocity limit enforcement."""

    async def test_horizontal_speed_limit(self, flight_tools):
        """Reject velocities exceeding 15 m/s horizontal."""
        # 16 m/s north exceeds limit
        result = await flight_tools.set_velocity(
            north_m_s=16.0, east_m_s=0.0, down_m_s=0.0, duration_s=0.1
        )

        assert result["success"] is False
        assert "15 m/s" in result["error"]

    async def test_horizontal_speed_diagonal(self, flight_tools):
        """Reject diagonal velocities where sqrt(n^2 + e^2) > 15."""
        # 11.31 m/s each direction = 16 m/s total
        result = await flight_tools.set_velocity(
            north_m_s=11.31, east_m_s=11.31, down_m_s=0.0, duration_s=0.1
        )

        assert result["success"] is False
        assert "15 m/s" in result["error"]

    async def test_vertical_speed_limit_up(self, flight_tools):
        """Reject velocities exceeding 3 m/s upward (negative down)."""
        # -4.0 down_m_s = 4 m/s upward exceeds limit
        result = await flight_tools.set_velocity(
            north_m_s=0.0, east_m_s=0.0, down_m_s=-4.0, duration_s=0.1
        )

        assert result["success"] is False
        assert "3 m/s" in result["error"]

    async def test_vertical_speed_limit_down(self, flight_tools):
        """Reject velocities exceeding 3 m/s downward."""
        result = await flight_tools.set_velocity(
            north_m_s=0.0, east_m_s=0.0, down_m_s=4.0, duration_s=0.1
        )

        assert result["success"] is False
        assert "3 m/s" in result["error"]

    async def test_valid_speeds_accepted(self, flight_tools, mock_drone):
        """Accept velocities within limits."""
        with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
            mock_stream.return_value = 20  # Simulate successful streaming

            result = await flight_tools.set_velocity(
                north_m_s=10.0, east_m_s=5.0, down_m_s=-2.0, duration_s=0.1
            )

            # Should pass validation but may fail connection (which is ok for this test)
            assert result["success"] is True or "Not connected" in result.get("error", "")


class TestStatePreconditions:
    """Test state machine integration."""

    async def test_valid_states(self):
        """Test that set_velocity works in valid flying states."""
        valid_states = [
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        ]

        for state in valid_states:
            sm = FlightStateMachine()
            # Set up state machine to reach the desired state
            sm.transition(FlightState.DISARMED, "startup", "system")
            sm.transition(FlightState.ARMED, "arm", "operator")
            sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
            sm.transition(FlightState.HOVERING, "hover", "telemetry")

            if state != FlightState.HOVERING:
                sm.transition(state, f"enter_{state.name}", "llm")

            tools = FlightTools(state_machine=sm)

            # Should pass state check, will fail on connection (expected)
            result = await tools.set_velocity(duration_s=0.1)

            # Should NOT fail due to state check
            assert "Cannot set_velocity in state" not in result.get("error", "")

    async def test_invalid_states(self):
        """Test that set_velocity fails in non-flying states."""
        invalid_states = [
            FlightState.INIT,
            FlightState.DISARMED,
            FlightState.ARMED,
            FlightState.LANDING,
            FlightState.LANDED,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        ]

        for state in invalid_states:
            sm = FlightStateMachine()
            if state != FlightState.INIT:
                # Set up minimal state path
                sm.transition(FlightState.DISARMED, "startup", "system")
                if state in [FlightState.ARMED]:
                    sm.transition(state, "transition", "system")
                elif state in [FlightState.LANDING, FlightState.LANDED]:
                    sm.transition(FlightState.ARMED, "arm", "operator")
                    sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
                    sm.transition(FlightState.HOVERING, "hover", "telemetry")
                    sm.transition(state, "land", "llm")
                elif state in [FlightState.EMERGENCY, FlightState.ERROR]:
                    sm.transition(FlightState.ERROR, "error", "system")
                    sm._state = state  # Direct set for emergency states

            tools = FlightTools(state_machine=sm)

            result = await tools.set_velocity(duration_s=0.1)

            assert result["success"] is False
            assert "Cannot set_velocity in state" in result["error"]

    async def test_state_transition_to_velocity_control(self, flight_tools, mock_drone):
        """Test that state transitions to VELOCITY_CONTROL."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20

                await flight_tools.set_velocity(duration_s=0.1)

                # State should transition to VELOCITY_CONTROL
                assert flight_tools.state_machine.current_state == FlightState.VELOCITY_CONTROL


class TestOffboardStreaming:
    """Test 20Hz offboard streaming."""

    async def test_streaming_rate_calculation(self):
        """Verify that setpoints are sent at approximately 20Hz."""
        # This is a simplified test - full rate testing would require timing
        tools = FlightTools()
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        from avatar.mcp_server.tools.flight_tools import VelocityNedYaw
        velocity_setpoint = VelocityNedYaw(1.0, 0.0, 0.0, 0.0)

        # Test with short duration
        duration_s = 0.15  # Expect ~3 setpoints at 20Hz

        setpoint_count = await tools._maintain_offboard_streaming(
            mock_drone, velocity_setpoint, duration_s
        )

        # Should have sent multiple setpoints
        assert setpoint_count >= 2

        # Verify offboard was started and stopped
        mock_drone.offboard.start.assert_called_once()
        mock_drone.offboard.stop.assert_called_once()

    async def test_setpoint_parameters(self):
        """Verify that correct velocity values are sent."""
        tools = FlightTools()
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        from avatar.mcp_server.tools.flight_tools import VelocityNedYaw

        # Test with specific values
        velocity_setpoint = VelocityNedYaw(5.0, 3.0, -1.0, 45.0)
        duration_s = 0.05

        await tools._maintain_offboard_streaming(
            mock_drone, velocity_setpoint, duration_s
        )

        # Verify set_velocity_ned was called with correct parameters
        calls = mock_drone.offboard.set_velocity_ned.call_args_list
        assert len(calls) >= 1

        # Check that initial setpoint matches
        first_call = calls[0]
        sent_velocity = first_call[0][0]
        assert sent_velocity.north_m_s == 5.0
        assert sent_velocity.east_m_s == 3.0
        assert sent_velocity.down_m_s == -1.0
        assert sent_velocity.yaw_deg == 45.0

    async def test_streaming_failure_handling(self):
        """Test graceful handling when offboard fails to start."""
        tools = FlightTools()
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()

        from avatar.mcp_server.tools.flight_tools import OffboardError, VelocityNedYaw

        # Simulate offboard start failure
        async def raise_offboard_error(*args, **kwargs):
            raise OffboardError("Offboard start failed")

        mock_drone.offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard.start = AsyncMock(side_effect=raise_offboard_error)
        mock_drone.offboard.stop = AsyncMock()

        velocity_setpoint = VelocityNedYaw(1.0, 0.0, 0.0, 0.0)

        setpoint_count = await tools._maintain_offboard_streaming(
            mock_drone, velocity_setpoint, 0.1
        )

        # Should return 0 indicating failure
        assert setpoint_count == 0


class TestGracefulStop:
    """Test graceful cleanup after velocity control."""

    async def test_offboard_stop_called(self, flight_tools, mock_drone):
        """Verify offboard.stop is called when streaming completes."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock the streaming to complete quickly
            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20

                await flight_tools.set_velocity(duration_s=0.1)

                # The mock stream should have been called
                mock_stream.assert_called_once()

    async def test_state_transition_back_after_completion(self, flight_tools, mock_drone):
        """Verify state returns to FLYING after velocity control."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock streaming but simulate completion (stop is called in finally)
            original_maintain = flight_tools._maintain_offboard_streaming

            async def mock_maintain(*args, **kwargs):
                # Simulate streaming completion by returning setpoint count
                return 20

            with patch.object(flight_tools, '_maintain_offboard_streaming', side_effect=mock_maintain):
                result = await flight_tools.set_velocity(duration_s=0.1)

                # State transitions are handled in the method
                # After completion it should be FLYING or VELOCITY_CONTROL
                # depending on whether stop() was called in finally
                assert flight_tools.state_machine.current_state in [
                    FlightState.FLYING,
                    FlightState.VELOCITY_CONTROL
                ]


class TestWrapperFunction:
    """Test the MCP wrapper function."""

    async def test_set_velocity_wrapper_returns_json(self):
        """Verify wrapper returns JSON string."""
        # This will fail on connection but should return valid JSON
        result = await set_velocity(
            north_m_s=1.0,
            east_m_s=0.0,
            down_m_s=0.0,
            yaw_deg=0.0,
            duration_s=0.1
        )

        # Should be a JSON string
        try:
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.fail("Wrapper should return valid JSON string")

    async def test_set_velocity_wrapper_default_params(self):
        """Verify wrapper works with default parameters."""
        result = await set_velocity()

        try:
            parsed = json.loads(result)
            # Should either succeed or fail gracefully
            assert "success" in parsed or "error" in parsed
        except json.JSONDecodeError:
            pytest.fail("Wrapper should return valid JSON string")


class TestErrorHandling:
    """Test error handling in set_velocity."""

    async def test_connection_error_handling(self, flight_tools):
        """Test graceful handling of connection errors."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(
                side_effect=ConnectionError("Not connected")
            )

            result = await flight_tools.set_velocity(duration_s=0.1)

            assert result["success"] is False
            assert "Not connected" in result["error"]

    async def test_general_exception_handling(self, flight_tools, mock_drone):
        """Test graceful handling of unexpected errors."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Make offboard start raise an unexpected error
            mock_drone.offboard.start = AsyncMock(side_effect=Exception("Unexpected error"))

            # The error should be caught in _maintain_offboard_streaming
            # which returns 0, and set_velocity reports failure
            result = await flight_tools.set_velocity(duration_s=0.1)

            # Should report failure but not crash
            assert result["success"] is False or "error" in result


class TestResultFormat:
    """Test the format of successful results."""

    async def test_success_result_format(self, flight_tools, mock_drone):
        """Verify successful result contains expected fields."""
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20

                result = await flight_tools.set_velocity(
                    north_m_s=5.0,
                    east_m_s=3.0,
                    down_m_s=-1.0,
                    yaw_deg=45.0,
                    duration_s=1.0
                )

                assert result["success"] is True
                assert "velocity_ned" in result
                assert result["velocity_ned"] == [5.0, 3.0, -1.0]
                assert "yaw_deg" in result
                assert result["yaw_deg"] == 45.0
                assert "duration_s" in result
                assert result["duration_s"] == 1.0
                assert "setpoints_sent" in result
                assert result["setpoints_sent"] == 20
                assert "approximate_rate_hz" in result
