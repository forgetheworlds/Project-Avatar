"""Tests for fly_body_offset tool.

Tests body-relative movement with coordinate transforms for forward/back/left/right movement.
"""

import json
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from avatar.mcp_server.tools.flight_tools import (
    body_to_ned,
    fly_body_offset,
    FlightTools,
    FlightToolsConfig,
)
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mav.guardian import HardLimits
from avatar.mav.connection_manager import ConnectionManager


def create_mock_drone():
    """Create a properly mocked drone with async methods set up."""
    mock_drone = MagicMock()
    mock_telemetry = MagicMock()

    # Mock position
    mock_position = MagicMock()
    mock_position.latitude_deg = 37.7749
    mock_position.longitude_deg = -122.4194
    mock_position.absolute_altitude_m = 50.0
    mock_position.relative_altitude_m = 10.0

    # Mock attitude (facing north)
    mock_attitude = MagicMock()
    mock_attitude.yaw_deg = 0.0
    mock_attitude.roll_deg = 0.0
    mock_attitude.pitch_deg = 0.0

    # Set up async iterators
    mock_telemetry.position = MagicMock(return_value=AsyncIterator([mock_position]))
    mock_telemetry.attitude_euler = MagicMock(return_value=AsyncIterator([mock_attitude]))
    mock_drone.telemetry = mock_telemetry

    # Mock action
    mock_action = MagicMock()
    mock_action.set_maximum_speed = AsyncMock()
    mock_action.goto_location = AsyncMock()
    mock_drone.action = mock_action

    # Mock core.connection_state for ConnectionManager
    async def mock_connection_state():
        state = MagicMock()
        state.is_connected = True
        yield state

    mock_drone.core.connection_state = mock_connection_state

    return mock_drone


class TestBodyToNedTransform:
    """Tests for body-to-NED coordinate transformation."""

    def test_body_to_ned_transform_north_heading(self):
        """Test transform when drone is facing north (yaw=0)."""
        # Facing north, move forward 10m
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 10.0
        assert pytest.approx(east, 0.01) == 0.0

        # Facing north, move right 5m (east)
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == 5.0

    def test_body_to_ned_transform_east_heading(self):
        """Test transform when drone is facing east (yaw=90)."""
        # Facing east, move forward 10m (should be +east)
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=90.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == 10.0

        # Facing east, move right 5m (should be +north)
        # When facing east, right is pointing south, but wait...
        # Let me verify: at yaw=90 (facing east), right is toward south
        # So right_m=5 should give negative north (south)
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=90.0)
        # right_m=5 at yaw=90: north = 0*cos(90) - 5*sin(90) = -5
        assert pytest.approx(north, 0.01) == -5.0
        assert pytest.approx(east, 0.01) == 0.0

    def test_body_to_ned_transform_south_heading(self):
        """Test transform when drone is facing south (yaw=180)."""
        # Facing south, move forward 10m (should be -north)
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=180.0)
        assert pytest.approx(north, 0.01) == -10.0
        assert pytest.approx(east, 0.01) == 0.0

        # Facing south, move right 5m (should be -east/west)
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=180.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == -5.0

    def test_body_to_ned_transform_west_heading(self):
        """Test transform when drone is facing west (yaw=270 or -90)."""
        # Facing west (yaw=270), move forward 10m
        # north = 10*cos(270) - 0*sin(270) = 0
        # east = 10*sin(270) + 0*cos(270) = -10
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=270.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == -10.0

        # Facing west (yaw=270), move right 5m
        # right when facing west is toward north
        # north = 0*cos(270) - 5*sin(270) = -5*(-1) = 5
        # east = 0*sin(270) + 5*cos(270) = 0
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=270.0)
        assert pytest.approx(north, 0.01) == 5.0
        assert pytest.approx(east, 0.01) == 0.0

    def test_body_to_ned_transform_northeast_heading(self):
        """Test transform when drone is facing northeast (yaw=45)."""
        # Facing NE (yaw=45), move forward 10m
        # north = 10*cos(45) - 0*sin(45) = 10*0.707 = 7.07
        # east = 10*sin(45) + 0*cos(45) = 10*0.707 = 7.07
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=45.0)
        expected = 10.0 * math.cos(math.radians(45.0))
        assert pytest.approx(north, 0.01) == expected
        assert pytest.approx(east, 0.01) == expected

    def test_body_to_ned_transform_diagonal_movement(self):
        """Test diagonal movement at various headings."""
        # Move forward and right equally at 0 yaw
        north, east = body_to_ned(forward_m=10.0, right_m=10.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 10.0
        assert pytest.approx(east, 0.01) == 10.0

        # Move forward and right at 45 yaw
        north, east = body_to_ned(forward_m=10.0, right_m=10.0, yaw_deg=45.0)
        # At 45 degrees, forward is split between north and east
        # right is also split but with signs adjusted
        assert north > 0
        assert east > 0

    def test_body_to_ned_transform_negative_values(self):
        """Test with negative values (back and left movement)."""
        # Move back 5m when facing north
        north, east = body_to_ned(forward_m=-5.0, right_m=0.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == -5.0
        assert pytest.approx(east, 0.01) == 0.0

        # Move left 5m when facing north (should be -east/west)
        north, east = body_to_ned(forward_m=0.0, right_m=-5.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == -5.0


class TestForwardMovement:
    """Tests for forward movement."""

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_forward_movement_executes(self, mock_do_connect):
        """Test that forward movement executes correctly."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton state
        cm = ConnectionManager()
        cm._state = ConnectionManager._instance._state if hasattr(ConnectionManager._instance, '_state') else cm._state
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute forward movement
        result = await tools.fly_body_offset(forward_m=10.0, right_m=0.0, up_m=0.0)

        assert result["success"] is True
        assert result["offset"]["forward_m"] == 10.0
        assert result["offset"]["right_m"] == 0.0

        # Verify goto_location was called
        mock_drone.action.goto_location.assert_called_once()
        call_args = mock_drone.action.goto_location.call_args[0]

        # Target should be north of current position (yaw=0, forward=10m)
        assert call_args[0] > 37.7749  # latitude increased (north)
        assert pytest.approx(call_args[1], 0.0001) == -122.4194  # longitude unchanged
        assert call_args[2] == 50.0  # altitude unchanged

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_forward_movement_with_yaw_align(self, mock_do_connect):
        """Test forward movement with yaw alignment."""
        tools = FlightTools()

        # Create mock drone with east-facing attitude
        mock_drone = MagicMock()
        mock_telemetry = MagicMock()

        # Mock position
        mock_position = MagicMock()
        mock_position.latitude_deg = 37.7749
        mock_position.longitude_deg = -122.4194
        mock_position.absolute_altitude_m = 50.0
        mock_position.relative_altitude_m = 10.0

        # Mock attitude (facing east)
        mock_attitude = MagicMock()
        mock_attitude.yaw_deg = 90.0
        mock_attitude.roll_deg = 0.0
        mock_attitude.pitch_deg = 0.0

        # Set up async iterators
        mock_telemetry.position = MagicMock(return_value=AsyncIterator([mock_position]))
        mock_telemetry.attitude_euler = MagicMock(return_value=AsyncIterator([mock_attitude]))
        mock_drone.telemetry = mock_telemetry

        # Mock action
        mock_action = MagicMock()
        mock_action.set_maximum_speed = AsyncMock()
        mock_action.goto_location = AsyncMock()
        mock_drone.action = mock_action

        # Mock core.connection_state for ConnectionManager
        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute forward movement with yaw alignment
        result = await tools.fly_body_offset(forward_m=10.0, right_m=0.0, up_m=0.0, yaw_align=True)

        assert result["success"] is True
        assert result["yaw_align"] is True

        # Verify goto_location was called with yaw aligned to movement (90 degrees)
        call_args = mock_action.goto_location.call_args[0]
        assert pytest.approx(call_args[3], 0.1) == 90.0  # yaw should remain 90 (forward)


class TestRightMovement:
    """Tests for right/left movement."""

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_right_movement_executes(self, mock_do_connect):
        """Test that right movement executes correctly."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute right movement
        result = await tools.fly_body_offset(forward_m=0.0, right_m=5.0, up_m=0.0)

        assert result["success"] is True
        assert result["offset"]["forward_m"] == 0.0
        assert result["offset"]["right_m"] == 5.0

        # Verify goto_location was called
        call_args = mock_drone.action.goto_location.call_args[0]

        # Target should be east of current position (yaw=0, right=5m)
        assert pytest.approx(call_args[0], 0.0001) == 37.7749  # latitude unchanged
        assert call_args[1] > -122.4194  # longitude increased (east)

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_left_movement_executes(self, mock_do_connect):
        """Test that left movement (negative right) executes correctly."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute left movement (negative right)
        result = await tools.fly_body_offset(forward_m=0.0, right_m=-5.0, up_m=0.0)

        assert result["success"] is True
        assert result["offset"]["right_m"] == -5.0

        # Verify goto_location was called
        call_args = mock_drone.action.goto_location.call_args[0]

        # Target should be west of current position (yaw=0, right=-5m)
        assert call_args[1] < -122.4194  # longitude decreased (west)


class TestCombinedOffset:
    """Tests for combined/diagonal movement."""

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_diagonal_forward_right(self, mock_do_connect):
        """Test diagonal forward-right movement."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute diagonal movement
        result = await tools.fly_body_offset(forward_m=10.0, right_m=10.0, up_m=5.0)

        assert result["success"] is True
        assert result["offset"]["forward_m"] == 10.0
        assert result["offset"]["right_m"] == 10.0
        assert result["offset"]["up_m"] == 5.0

        # Verify transform
        assert result["transform"]["north_m"] > 0
        assert result["transform"]["east_m"] > 0

        # Verify altitude increased
        call_args = mock_drone.action.goto_location.call_args[0]
        assert call_args[2] == 55.0  # 50 + 5 up

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_diagonal_with_yaw_align(self, mock_do_connect):
        """Test diagonal movement with yaw alignment."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute diagonal movement with yaw align
        result = await tools.fly_body_offset(
            forward_m=10.0, right_m=10.0, up_m=0.0, yaw_align=True
        )

        assert result["success"] is True
        assert result["yaw_align"] is True

        # Yaw should be aligned to diagonal (45 degrees for equal forward/right)
        assert pytest.approx(result["target"]["yaw_deg"], 0.1) == 45.0


class TestPositionHoldAfter:
    """Tests for position hold after reaching target."""

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_state_transition_to_position_control(self, mock_do_connect):
        """Test that state transitions to POSITION_CONTROL."""
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton
        cm = ConnectionManager()
        await cm.disconnect()

        # Set home position for guardian validation
        tools.guardian.set_home(37.7749, -122.4194)

        # Start from HOVERING state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)
        assert tools.state_machine.current_state == FlightState.HOVERING

        # Execute movement
        result = await tools.fly_body_offset(forward_m=10.0)

        assert result["success"] is True
        # State should transition to POSITION_CONTROL
        assert tools.state_machine.current_state == FlightState.POSITION_CONTROL


class TestStatePrecondition:
    """Tests for state machine integration and preconditions."""

    @pytest.mark.asyncio
    async def test_state_precondition_ground_state_fails(self):
        """Test that movement fails when in ground state."""
        tools = FlightTools()

        # Set state machine to DISARMED (ground state)
        tools.state_machine.transition(FlightState.DISARMED, "test", "test")
        assert tools.state_machine.current_state == FlightState.DISARMED

        # Execute movement - should fail due to state precondition
        result = await tools.fly_body_offset(forward_m=10.0)

        assert result["success"] is False
        assert "State precondition failed" in result["error"]
        assert "DISARMED" in result["error"]

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_state_precondition_flying_state_succeeds(self, mock_do_connect):
        """Test that movement succeeds when in flying state."""

        # Test from various flying states
        flying_states = [
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        ]

        # Reset ConnectionManager singleton at start
        cm = ConnectionManager()
        await cm.disconnect()

        for state in flying_states:
            # Create new tools instance for each state (fresh mocks)
            tools = FlightTools()

            # Create mock drone using helper
            mock_drone = create_mock_drone()
            mock_do_connect.return_value = mock_drone

            # Reset ConnectionManager between iterations to force reconnect
            await cm.disconnect()

            # Set home position for guardian validation
            tools.guardian.set_home(37.7749, -122.4194)

            # Set state machine to flying state
            set_state_to_flying(tools.state_machine, FlightState.HOVERING)
            if state != FlightState.HOVERING:
                tools.state_machine.transition(state, "test", "test")

            # Execute movement
            result = await tools.fly_body_offset(forward_m=10.0)

            assert result["success"] is True, f"Failed for state {state.name}"

    @pytest.mark.asyncio
    async def test_speed_validation_against_limits(self):
        """Test that speed is validated against guardian limits."""
        tools = FlightTools()

        # Set up strict limits
        hard_limits = HardLimits(max_speed_m_s=5.0)
        tools.guardian = MagicMock()
        tools.guardian.validate_command = MagicMock(return_value=(False, "Speed 10m/s exceeds max 5m/s"))

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute movement with excessive speed
        result = await tools.fly_body_offset(forward_m=10.0, speed_m_s=10.0)

        assert result["success"] is False
        assert "exceeds max" in result["error"]


class TestMcpToolWrapper:
    """Tests for the MCP tool wrapper function."""

    @pytest.mark.asyncio
    @patch("avatar.mcp_server.tools.flight_tools.FlightTools")
    async def test_fly_body_offset_wrapper(self, mock_tools_class):
        """Test the fly_body_offset MCP tool wrapper."""
        # Set up mock
        mock_tools = MagicMock()
        mock_tools.fly_body_offset = AsyncMock(return_value={
            "success": True,
            "offset": {"forward_m": 10.0, "right_m": 5.0, "up_m": 2.0},
        })
        mock_tools_class.return_value = mock_tools

        # Call wrapper
        result_json = await fly_body_offset(forward_m=10.0, right_m=5.0, up_m=2.0)

        # Parse result
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["offset"]["forward_m"] == 10.0
        assert result["offset"]["right_m"] == 5.0
        assert result["offset"]["up_m"] == 2.0

        # Verify the method was called
        mock_tools.fly_body_offset.assert_called_once_with(10.0, 5.0, 2.0, False, 5.0)


# Helper function to set state machine to flying state for tests
def set_state_to_flying(state_machine: FlightStateMachine, target_state: FlightState = FlightState.HOVERING) -> None:
    """Set state machine to a flying state following valid transitions.

    Valid path: INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING
    From HOVERING, can transition to other flying states.
    """
    # Reset to INIT first
    if state_machine.current_state != FlightState.INIT:
        state_machine.reset(force=True)

    # Follow valid transition path
    state_machine.transition(FlightState.DISARMED, "test_init", "test")
    state_machine.transition(FlightState.ARMED, "test_arm", "test")
    state_machine.transition(FlightState.TAKING_OFF, "test_takeoff", "test")
    state_machine.transition(FlightState.HOVERING, "test_hover", "test")

    # If target is different from HOVERING, transition there
    if target_state != FlightState.HOVERING and target_state in state_machine.get_valid_transitions():
        state_machine.transition(target_state, f"test_to_{target_state.name}", "test")


# Helper class for mocking async iterators
class AsyncIterator:
    """Helper class to create async iterators for mocking."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
