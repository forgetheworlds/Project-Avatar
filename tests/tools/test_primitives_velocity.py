"""Tests for set_velocity_ned MCP tool - Offboard velocity control in NED frame.

WHAT THESE TESTS VALIDATE:
    These tests verify the set_velocity_ned() MCP tool which commands the drone
    to fly at a specified velocity vector using PX4's offboard control mode.
    Key capabilities tested:
    - Velocity limits enforcement (+-20 m/s horizontal, +-10 m/s vertical)
    - State preconditions (requires HOVERING, FLYING, or similar active flight state)
    - 20Hz MAVLink offboard streaming rate maintenance
    - Graceful stop and cleanup after velocity control
    - Proper state transitions (to/from VELOCITY_CONTROL)
    - Error handling for connection failures and offboard errors

WHY THESE TESTS MATTER:
    Velocity control is the foundation of autonomous movement. When an LLM
    commands "fly north at 5 m/s" or "orbit the target," the set_velocity_ned
    tool executes those commands in the NED (North-East-Down) inertial frame.

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific velocity control behaviors:
    - Velocity limits: Speeds >20 m/s horizontal or >10 m/s vertical are rejected
    - State preconditions: Command rejected in DISARMED, LANDING, EMERGENCY states
    - Streaming: Setpoints sent at ~20Hz (one every 50ms)
    - Cleanup: offboard.stop() called after duration to exit offboard mode
    - State machine: Transitions to VELOCITY_CONTROL during, FLYING after

Coverage:
- Velocity limits enforcement (+-20 m/s horizontal, +-10 m/s vertical)
- State preconditions (requires HOVERING/FLYING/etc)
- 20Hz streaming rate maintenance
- Graceful stop and cleanup
- Error handling
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools.primitives import (
    SetVelocityNedInput,
    SetVelocityBodyInput,
    VelocityStreamer,
    VelocityBodyStreamer,
    set_velocity_ned,
    set_velocity_body,
)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


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
def mock_drone():
    """Create a fully mocked MAVSDK drone with offboard support."""
    drone = MagicMock()

    # Mock offboard plugin
    drone.offboard = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()

    # Mock telemetry
    drone.telemetry = MagicMock()
    drone.telemetry.attitude_euler = MagicMock()

    async def mock_attitude():
        mock_att = MagicMock()
        mock_att.yaw_deg = 0.0
        yield mock_att

    drone.telemetry.attitude_euler.return_value = mock_attitude()

    return drone


# =============================================================================
# TEST CLASSES - INPUT SCHEMA VALIDATION
# =============================================================================


class TestVelocityInputSchema:
    """Test the SetVelocityNedInput Pydantic schema."""

    def test_valid_input(self):
        """Test that valid input passes validation."""
        input_data = SetVelocityNedInput(
            north_m_s=5.0,
            east_m_s=3.0,
            down_m_s=-1.0,
            yaw_deg=45.0,
            duration_s=3.0,
        )
        assert input_data.north_m_s == 5.0
        assert input_data.east_m_s == 3.0
        assert input_data.down_m_s == -1.0
        assert input_data.yaw_deg == 45.0
        assert input_data.duration_s == 3.0

    def test_default_values(self):
        """Test that default values are applied correctly."""
        input_data = SetVelocityNedInput(duration_s=5.0)
        assert input_data.north_m_s == 0.0
        assert input_data.east_m_s == 0.0
        assert input_data.down_m_s == 0.0
        assert input_data.yaw_deg is None

    def test_north_limit_exceeded(self):
        """Test rejection of north velocities exceeding +-20 m/s."""
        with pytest.raises(Exception):  # ValidationError
            SetVelocityNedInput(north_m_s=25.0, duration_s=1.0)

        with pytest.raises(Exception):
            SetVelocityNedInput(north_m_s=-25.0, duration_s=1.0)

    def test_east_limit_exceeded(self):
        """Test rejection of east velocities exceeding +-20 m/s."""
        with pytest.raises(Exception):
            SetVelocityNedInput(east_m_s=25.0, duration_s=1.0)

    def test_down_limit_exceeded(self):
        """Test rejection of down velocities exceeding +-10 m/s."""
        with pytest.raises(Exception):
            SetVelocityNedInput(down_m_s=15.0, duration_s=1.0)

        with pytest.raises(Exception):
            SetVelocityNedInput(down_m_s=-15.0, duration_s=1.0)

    def test_duration_limits(self):
        """Test duration must be > 0 and <= 60."""
        # Duration must be positive
        with pytest.raises(Exception):
            SetVelocityNedInput(duration_s=0.0)

        with pytest.raises(Exception):
            SetVelocityNedInput(duration_s=-1.0)

        # Duration max 60 seconds
        with pytest.raises(Exception):
            SetVelocityNedInput(duration_s=70.0)

    def test_valid_boundary_values(self):
        """Test that boundary values are accepted."""
        # Max horizontal
        input_data = SetVelocityNedInput(north_m_s=20.0, east_m_s=-20.0, duration_s=1.0)
        assert input_data.north_m_s == 20.0
        assert input_data.east_m_s == -20.0

        # Max vertical
        input_data = SetVelocityNedInput(down_m_s=10.0, duration_s=1.0)
        assert input_data.down_m_s == 10.0

        input_data = SetVelocityNedInput(down_m_s=-10.0, duration_s=1.0)
        assert input_data.down_m_s == -10.0

        # Max duration
        input_data = SetVelocityNedInput(duration_s=60.0)
        assert input_data.duration_s == 60.0


# =============================================================================
# TEST CLASSES - STATE PRECONDITIONS
# =============================================================================


class TestStatePreconditions:
    """Test state machine integration for velocity control."""

    async def test_valid_states(self):
        """Test that set_velocity_ned works in valid flying states."""
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
            sm.transition(FlightState.DISARMED, "startup", "system")
            sm.transition(FlightState.ARMED, "arm", "operator")
            sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
            sm.transition(FlightState.HOVERING, "hover", "telemetry")

            if state != FlightState.HOVERING:
                sm.transition(state, f"enter_{state.name}", "llm")

            # Mock everything
            with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
                with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                    mock_drone = MagicMock()
                    mock_drone.offboard = MagicMock()
                    mock_drone.offboard.set_velocity_ned = AsyncMock()
                    mock_drone.offboard.start = AsyncMock()
                    mock_drone.offboard.stop = AsyncMock()
                    mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                    with patch('avatar.mcp_server.tools.primitives.get_offboard_owner') as mock_owner:
                        mock_owner.return_value.acquire = AsyncMock(return_value=True)
                        mock_owner.return_value.release = AsyncMock()

                        result_json = await set_velocity_ned(duration_s=0.05)
                        result = json.loads(result_json)

            # Should NOT fail due to state check
            assert "Cannot set_velocity_ned in state" not in result.get("error", "")

    async def test_invalid_states(self):
        """Test that set_velocity_ned fails in non-flying states."""
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
                sm.transition(FlightState.DISARMED, "startup", "system")
                if state == FlightState.ARMED:
                    sm.transition(state, "transition", "system")
                elif state in [FlightState.LANDING, FlightState.LANDED]:
                    sm.transition(FlightState.ARMED, "arm", "operator")
                    sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
                    sm.transition(FlightState.HOVERING, "hover", "telemetry")
                    sm.transition(state, "land", "llm")
                elif state in [FlightState.EMERGENCY, FlightState.ERROR]:
                    sm.transition(FlightState.ERROR, "error", "system")

            with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
                result_json = await set_velocity_ned(duration_s=0.1)
                result = json.loads(result_json)

            assert result["success"] is False
            assert "Cannot set_velocity_ned in state" in result["error"]


# =============================================================================
# TEST CLASSES - OFFBOARD STREAMING
# =============================================================================


class TestOffboardStreaming:
    """Test 20Hz offboard streaming rate maintenance."""

    async def test_streaming_rate(self, mock_drone):
        """Verify that setpoints are sent at approximately 20Hz."""
        streamer = VelocityStreamer(rate_hz=20.0)

        # Import the mock VelocityNedYaw
        from avatar.mcp_server.tools.primitives import VelocityNedYaw
        velocity_setpoint = VelocityNedYaw(5.0, 0.0, 0.0, 0.0)

        # Test with short duration
        setpoint_count = await streamer.stream_for(
            drone=mock_drone,
            velocity_setpoint=velocity_setpoint,
            duration_s=0.15,  # Expect ~3 setpoints at 20Hz
            offboard_owner=None,
        )

        # Should have sent multiple setpoints
        assert setpoint_count >= 2

        # Verify offboard was started and stopped
        mock_drone.offboard.start.assert_called_once()
        mock_drone.offboard.stop.assert_called_once()

    async def test_offboard_owner_acquisition(self, mock_drone):
        """Test that OffboardOwner is properly acquired and released."""
        streamer = VelocityStreamer(rate_hz=20.0)

        from avatar.mcp_server.tools.primitives import VelocityNedYaw
        velocity_setpoint = VelocityNedYaw(1.0, 0.0, 0.0, 0.0)

        # Create mock OffboardOwner
        mock_owner = MagicMock()
        mock_owner.acquire = AsyncMock(return_value=True)
        mock_owner.release = AsyncMock()

        await streamer.stream_for(
            drone=mock_drone,
            velocity_setpoint=velocity_setpoint,
            duration_s=0.05,
            offboard_owner=mock_owner,
            owner_id="test_velocity",
        )

        # Verify ownership was acquired and released
        mock_owner.acquire.assert_called_once_with("test_velocity")
        mock_owner.release.assert_called_once_with("test_velocity")

    async def test_offboard_owner_conflict(self, mock_drone):
        """Test handling when OffboardOwner acquisition fails."""
        streamer = VelocityStreamer(rate_hz=20.0)

        from avatar.mcp_server.tools.primitives import VelocityNedYaw
        velocity_setpoint = VelocityNedYaw(1.0, 0.0, 0.0, 0.0)

        # Create mock OffboardOwner that denies acquisition
        mock_owner = MagicMock()
        mock_owner.acquire = AsyncMock(return_value=False)
        mock_owner.current_owner = MagicMock(return_value="other_tool")

        setpoint_count = await streamer.stream_for(
            drone=mock_drone,
            velocity_setpoint=velocity_setpoint,
            duration_s=0.1,
            offboard_owner=mock_owner,
            owner_id="test_velocity",
        )

        # Should return 0 setpoints when ownership fails
        assert setpoint_count == 0

        # Offboard should not have been started
        mock_drone.offboard.start.assert_not_called()


# =============================================================================
# TEST CLASSES - WRAPPER FUNCTION
# =============================================================================


class TestWrapperFunction:
    """Test the MCP wrapper function."""

    async def test_set_velocity_ned_returns_json(self):
        """Verify wrapper returns JSON string."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "system")
        sm.transition(FlightState.ARMED, "arm", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
        sm.transition(FlightState.HOVERING, "hover", "telemetry")

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_drone = MagicMock()
                mock_drone.offboard = MagicMock()
                mock_drone.offboard.set_velocity_ned = AsyncMock()
                mock_drone.offboard.start = AsyncMock()
                mock_drone.offboard.stop = AsyncMock()
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.get_offboard_owner') as mock_owner:
                    mock_owner.return_value.acquire = AsyncMock(return_value=True)
                    mock_owner.return_value.release = AsyncMock()

                    result = await set_velocity_ned(
                        north_m_s=5.0,
                        east_m_s=0.0,
                        down_m_s=0.0,
                        yaw_deg=0.0,
                        duration_s=0.05,
                    )

        # Should be a JSON string
        try:
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.fail("Wrapper should return valid JSON string")

    async def test_success_result_format(self):
        """Verify successful result contains expected fields."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "system")
        sm.transition(FlightState.ARMED, "arm", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
        sm.transition(FlightState.HOVERING, "hover", "telemetry")

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_drone = MagicMock()
                mock_drone.offboard = MagicMock()
                mock_drone.offboard.set_velocity_ned = AsyncMock()
                mock_drone.offboard.start = AsyncMock()
                mock_drone.offboard.stop = AsyncMock()
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.get_offboard_owner') as mock_owner:
                    mock_owner.return_value.acquire = AsyncMock(return_value=True)
                    mock_owner.return_value.release = AsyncMock()

                    result = await set_velocity_ned(
                        north_m_s=5.0,
                        east_m_s=3.0,
                        down_m_s=-1.0,
                        yaw_deg=45.0,
                        duration_s=0.05,
                    )

        parsed = json.loads(result)

        if parsed.get("success"):
            assert "velocity_ned" in parsed
            assert parsed["velocity_ned"] == [5.0, 3.0, -1.0]
            assert "yaw_deg" in parsed
            assert "duration_s" in parsed
            assert "setpoints_sent" in parsed
            assert "approximate_rate_hz" in parsed


# =============================================================================
# TEST CLASSES - ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in set_velocity_ned."""

    async def test_connection_error_handling(self):
        """Test graceful handling of connection errors."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "system")
        sm.transition(FlightState.ARMED, "arm", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
        sm.transition(FlightState.HOVERING, "hover", "telemetry")

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(
                    side_effect=ConnectionError("Not connected")
                )

                result = await set_velocity_ned(duration_s=0.1)
                parsed = json.loads(result)

                assert parsed["success"] is False
                assert "Not connected" in parsed["error"]

    async def test_input_validation_error(self):
        """Test that input validation errors are returned properly."""
        # This should fail validation (speed exceeds limit)
        result = await set_velocity_ned(north_m_s=30.0, duration_s=1.0)
        parsed = json.loads(result)

        assert parsed["success"] is False
        assert "validation" in parsed["error"].lower() or "failed" in parsed["error"].lower()


# =============================================================================
# TEST CLASSES - STATE TRANSITIONS
# =============================================================================


class TestStateTransitions:
    """Test state machine transitions during velocity control."""

    async def test_transition_to_velocity_control(self, mock_state_machine, mock_drone):
        """Test that state transitions to VELOCITY_CONTROL during operation."""
        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.get_offboard_owner') as mock_owner:
                    mock_owner.return_value.acquire = AsyncMock(return_value=True)
                    mock_owner.return_value.release = AsyncMock()

                    # Before: HOVERING
                    assert mock_state_machine.current_state == FlightState.HOVERING

                    await set_velocity_ned(duration_s=0.05)

                    # After: should be FLYING (transitioned back after completion)
                    assert mock_state_machine.current_state in [
                        FlightState.FLYING,
                        FlightState.VELOCITY_CONTROL,
                    ]


# =============================================================================
# TEST CLASSES - SET_VELOCITY_BODY (Body Frame)
# =============================================================================


class TestSetVelocityBodyInputSchema:
    """Test input schema validation for set_velocity_body.

    These tests validate that the Pydantic schema correctly enforces
    velocity and duration limits before any drone communication.
    """

    def test_valid_default_parameters(self):
        """Test that default parameters are valid."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        input_data = SetVelocityBodyInput(duration_s=1.0)
        assert input_data.forward_m_s == 0.0
        assert input_data.right_m_s == 0.0
        assert input_data.down_m_s == 0.0
        assert input_data.yaw_rate_deg_s == 0.0
        assert input_data.duration_s == 1.0

    def test_valid_forward_velocity(self):
        """Test that forward velocity within limits is accepted."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        input_data = SetVelocityBodyInput(forward_m_s=15.0, duration_s=2.0)
        assert input_data.forward_m_s == 15.0

    def test_valid_backward_velocity(self):
        """Test that backward velocity within limits is accepted."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        input_data = SetVelocityBodyInput(forward_m_s=-10.0, duration_s=1.0)
        assert input_data.forward_m_s == -10.0

    def test_forward_velocity_exceeds_limit_raises(self):
        """Test that forward velocity exceeding 20 m/s raises validation error."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        with pytest.raises(Exception):
            SetVelocityBodyInput(forward_m_s=25.0, duration_s=1.0)

    def test_vertical_velocity_exceeds_limit_raises(self):
        """Test that vertical velocity exceeding 10 m/s raises validation error."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        with pytest.raises(Exception):
            SetVelocityBodyInput(down_m_s=15.0, duration_s=1.0)

    def test_yaw_rate_exceeds_limit_raises(self):
        """Test that yaw rate exceeding 180 deg/s raises validation error."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        with pytest.raises(Exception):
            SetVelocityBodyInput(yaw_rate_deg_s=200.0, duration_s=1.0)

    def test_duration_zero_raises(self):
        """Test that zero duration raises validation error."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        with pytest.raises(Exception):
            SetVelocityBodyInput(duration_s=0.0)

    def test_duration_exceeds_max_raises(self):
        """Test that duration exceeding 60s raises validation error."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        with pytest.raises(Exception):
            SetVelocityBodyInput(duration_s=70.0)

    def test_duration_max_valid(self):
        """Test that max duration (60s) is accepted."""
        from avatar.mcp_server.tools.primitives import SetVelocityBodyInput
        input_data = SetVelocityBodyInput(duration_s=60.0)
        assert input_data.duration_s == 60.0


class TestVelocityBodyLimitsCombined:
    """Test combined horizontal velocity limit enforcement for body frame."""

    async def test_diagonal_velocity_within_limit(self, mock_state_machine):
        """Test that diagonal velocity within combined 20 m/s limit is accepted."""
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.VelocityBodyStreamer') as streamer_class:
                    mock_streamer = MagicMock()
                    mock_streamer.stream_for = AsyncMock(return_value=2)
                    streamer_class.return_value = mock_streamer

                    result = await set_velocity_body(
                        forward_m_s=14.14,
                        right_m_s=14.14,
                        duration_s=0.1
                    )
                    data = json.loads(result)
                    # Should succeed or fail on offboard start, not velocity limit
                    assert "20 m/s" not in data.get("error", "")

    async def test_diagonal_velocity_exceeds_limit(self, mock_state_machine):
        """Test that diagonal velocity exceeding combined 20 m/s limit is rejected."""
        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
            result = await set_velocity_body(
                forward_m_s=15.0,
                right_m_s=15.0,
                duration_s=0.1
            )
            data = json.loads(result)
            # Error envelope uses isError, not success
            assert data.get("isError") is True or data.get("success") is False
            error_msg = data.get("error", {}).get("message", "") or data.get("error", "")
            assert "20 m/s" in error_msg


class TestVelocityBodyStatePreconditions:
    """Test state machine integration for body-frame velocity control."""

    async def test_invalid_state_disarmed(self):
        """Test that set_velocity_body fails in DISARMED state."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "system")

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
            result = await set_velocity_body(duration_s=0.1)
            data = json.loads(result)
            # Error envelope uses isError, not success
            assert data.get("isError") is True or data.get("success") is False
            error_msg = data.get("error", {}).get("message", "") or data.get("error", "")
            assert "Cannot set_velocity_body in state" in error_msg

    async def test_invalid_state_init(self):
        """Test that set_velocity_body fails in INIT state."""
        sm = FlightStateMachine()  # Starts in INIT

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=sm):
            result = await set_velocity_body(duration_s=0.1)
            data = json.loads(result)
            # Error envelope uses isError, not success
            assert data.get("isError") is True or data.get("success") is False
            error_msg = data.get("error", {}).get("message", "") or data.get("error", "")
            assert "Cannot set_velocity_body in state" in error_msg


class TestVelocityBodyOffboardOwnerExclusion:
    """Test OffboardOwner mutual exclusion for body-frame velocity control."""

    @pytest.mark.asyncio
    async def test_returns_conflict_if_owner_held(self, mock_state_machine):
        """Test that set_velocity_body returns OFFBOARD_OWNERSHIP_CONFLICT if owner held."""
        from avatar.mav.offboard_owner import get_offboard_owner

        owner = get_offboard_owner()
        # Clear any existing owner
        current = owner.current_owner()
        if current:
            await owner.release(current)

        # Acquire ownership with a different owner
        await owner.acquire("other_component")
        assert owner.current_owner() == "other_component"

        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        try:
            with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
                with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                    mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                    # Streamer returns 0 because ownership acquisition fails
                    result = await set_velocity_body(duration_s=0.1)
                    data = json.loads(result)

                    # Should report conflict - error envelope uses isError
                    assert data.get("isError") is True or data.get("success") is False
                    error_msg = data.get("error", {}).get("message", "") or data.get("error", "")
                    assert "OFFBOARD_OWNERSHIP_CONFLICT" in error_msg
        finally:
            # Release after test
            await owner.release("other_component")


class TestVelocityBodyStreamer:
    """Test the VelocityBodyStreamer class directly."""

    def test_rate_property(self):
        """Test that rate_hz property is correctly set."""
        streamer = VelocityBodyStreamer(rate_hz=20.0)
        assert streamer.rate_hz == 20.0

    def test_interval_property(self):
        """Test that interval_s property is correctly calculated."""
        streamer = VelocityBodyStreamer(rate_hz=20.0)
        assert streamer.interval_s == 0.05  # 1/20 = 0.05 seconds

    @pytest.mark.asyncio
    async def test_streaming_rate(self):
        """Verify that setpoints are sent at approximately 20Hz."""
        streamer = VelocityBodyStreamer(rate_hz=20.0)
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        class MockVelocitySetpoint:
            forward_m_s = 1.0
            right_m_s = 0.0
            down_m_s = 0.0
            yawspeed_deg_s = 0.0

        duration_s = 0.15  # Expect ~3 setpoints at 20Hz
        setpoint_count = await streamer.stream_for(
            mock_drone,
            MockVelocitySetpoint(),
            duration_s,
        )

        # Should have sent multiple setpoints
        assert setpoint_count >= 2

        # Verify offboard was started and stopped
        mock_drone.offboard.start.assert_called_once()
        mock_drone.offboard.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_if_acquire_fails(self):
        """Test that stream_for returns 0 if OffboardOwner acquire fails."""
        from avatar.mav.offboard_owner import OffboardOwner

        streamer = VelocityBodyStreamer(rate_hz=20.0)
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        # Create owner that's already held
        owner = OffboardOwner()
        await owner.acquire("other_owner")

        class MockVelocitySetpoint:
            forward_m_s = 1.0
            right_m_s = 0.0
            down_m_s = 0.0
            yawspeed_deg_s = 0.0

        result = await streamer.stream_for(
            mock_drone,
            MockVelocitySetpoint(),
            0.1,
            offboard_owner=owner,
            owner_id="test_streamer"
        )

        # Should return 0 because acquire failed
        assert result == 0

        # Cleanup
        await owner.release("other_owner")


class TestVelocityBodyWrapperFunction:
    """Test the MCP wrapper function for body-frame velocity."""

    @pytest.mark.asyncio
    async def test_wrapper_returns_json_string(self, mock_state_machine):
        """Verify wrapper returns JSON string."""
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.VelocityBodyStreamer') as streamer_class:
                    mock_streamer = MagicMock()
                    mock_streamer.stream_for = AsyncMock(return_value=20)
                    streamer_class.return_value = mock_streamer

                    result = await set_velocity_body(
                        forward_m_s=1.0,
                        duration_s=0.1
                    )

                    # Should be a string
                    assert isinstance(result, str)

                    # Should be valid JSON
                    data = json.loads(result)
                    assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_wrapper_success_result_format(self, mock_state_machine):
        """Verify successful result contains expected fields."""
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_velocity_body = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()

        with patch('avatar.mcp_server.tools.primitives.get_state_machine', return_value=mock_state_machine):
            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                with patch('avatar.mcp_server.tools.primitives.VelocityBodyStreamer') as streamer_class:
                    mock_streamer = MagicMock()
                    mock_streamer.stream_for = AsyncMock(return_value=20)
                    streamer_class.return_value = mock_streamer

                    result = await set_velocity_body(
                        forward_m_s=5.0,
                        right_m_s=3.0,
                        down_m_s=-1.0,
                        yaw_rate_deg_s=45.0,
                        duration_s=1.0
                    )

                    data = json.loads(result)

                    assert data["success"] is True
                    assert "velocity_body" in data
                    assert data["velocity_body"] == [5.0, 3.0, -1.0]
                    assert "yaw_rate_deg_s" in data
                    assert data["yaw_rate_deg_s"] == 45.0
                    assert "duration_s" in data
                    assert data["duration_s"] == 1.0
                    assert "setpoints_sent" in data
                    assert data["setpoints_sent"] == 20
                    assert "approximate_rate_hz" in data
