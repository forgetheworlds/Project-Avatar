"""Tests for fly_body_offset tool.

Tests body-relative movement with coordinate transforms for forward/back/left/right movement.

WHAT THESE TESTS COVER:
- Body-to-NED coordinate transformation (core math)
- Forward/backward movement execution
- Left/right (lateral) movement execution
- Combined diagonal movement
- State machine integration (preconditions and transitions)
- Speed validation and guardian limits
- MCP tool wrapper interface

WHY THESE TESTS MATTER:
Body-relative movement is the primary navigation interface for agents.
Instead of specifying GPS coordinates, agents say "move forward 10m" or
"strafe right 5m". This requires accurate coordinate transforms that
account for the drone's current heading (yaw).

MOCK STRATEGY:
- ConnectionManager._do_connect: Mocked to return mock drone without real network
- create_mock_drone(): Factory for configured mock drone instances
- AsyncIterator: Helper for mocking MAVSDK's async telemetry streams
- FlightTools methods: Partially mocked for unit isolation
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
    """Create a properly mocked drone with async methods set up.

    WHAT THIS MOCKS:
    A complete MAVSDK System instance with telemetry and action capabilities.

    MOCK COMPONENTS:
    - telemetry.position: Async iterator returning GPS coordinates
    - telemetry.attitude_euler: Async iterator returning roll/pitch/yaw
    - action.set_maximum_speed: Async method for speed configuration
    - action.goto_location: Async method for position commands
    - core.connection_state: Async generator for connection status

    WHY THESE VALUES:
    - Position: San Francisco coordinates (37.7749, -122.4194) at 50m absolute / 10m AGL
    - Attitude: yaw=0 (facing north), roll=0, pitch=0 (level flight)
    - These provide a known baseline for transform calculations

    ASYNC MOCK PATTERN:
    MAVSDK uses async generators for telemetry (yielding continuous updates).
    The AsyncIterator helper class converts a list of values into an async
    generator that can be used with 'async for' loops.
    """
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
    # WHY: MAVSDK telemetry methods return async generators, not lists
    mock_telemetry.position = MagicMock(return_value=AsyncIterator([mock_position]))
    mock_telemetry.attitude_euler = MagicMock(return_value=AsyncIterator([mock_attitude]))
    mock_drone.telemetry = mock_telemetry

    # Mock action
    mock_action = MagicMock()
    mock_action.set_maximum_speed = AsyncMock()
    mock_action.goto_location = AsyncMock()
    mock_drone.action = mock_action

    # Mock core.connection_state for ConnectionManager
    # WHY: ConnectionManager uses this to detect connection status
    async def mock_connection_state():
        state = MagicMock()
        state.is_connected = True
        yield state

    mock_drone.core.connection_state = mock_connection_state

    return mock_drone


class TestBodyToNedTransform:
    """Tests for body-to-NED coordinate transformation.

    WHAT THIS TESTS:
    The body_to_ned() function converts "body frame" commands (forward/right)
    to "NED frame" coordinates (north/east) based on the drone's yaw heading.

    TRANSFORM MATH:
    north = forward * cos(yaw) - right * sin(yaw)
    east = forward * sin(yaw) + right * cos(yaw)

    WHY THIS MATTERS:
    This is the core math enabling intuitive agent commands. Without accurate
    transforms, "move forward" would move in the wrong direction when the
    drone is not facing north.
    """

    def test_body_to_ned_transform_north_heading(self):
        """Test transform when drone is facing north (yaw=0).

        WHAT THIS VALIDATES:
        At yaw=0, forward should map directly to north, and right should map
        directly to east (no rotation needed).

        EXPECTED OUTCOMES:
        - forward=10, right=0 → north=10, east=0 (pure north movement)
        - forward=0, right=5 → north=0, east=5 (pure east movement)

        MATH VERIFICATION:
        At yaw=0: cos(0)=1, sin(0)=0
        north = 10*1 - 0*0 = 10
        east = 10*0 + 0*1 = 0
        """
        # Facing north, move forward 10m
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 10.0
        assert pytest.approx(east, 0.01) == 0.0

        # Facing north, move right 5m (east)
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == 5.0

    def test_body_to_ned_transform_east_heading(self):
        """Test transform when drone is facing east (yaw=90).

        WHAT THIS VALIDATES:
        At yaw=90, forward should map to east movement, and right should map
        to south (negative north).

        EXPECTED OUTCOMES:
        - forward=10, right=0 → north=0, east=10 (pure east movement)
        - forward=0, right=5 → north=-5, east=0 (pure south movement)

        MATH VERIFICATION:
        At yaw=90: cos(90)=0, sin(90)=1
        forward=10: north = 10*0 - 0*1 = 0, east = 10*1 + 0*0 = 10
        right=5: north = 0*0 - 5*1 = -5, east = 0*1 + 5*0 = 0
        """
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
        """Test transform when drone is facing south (yaw=180).

        WHAT THIS VALIDATES:
        At yaw=180, forward should map to south (negative north), and right
        should map to west (negative east).

        EXPECTED OUTCOMES:
        - forward=10, right=0 → north=-10, east=0 (pure south)
        - forward=0, right=5 → north=0, east=-5 (pure west)

        MATH VERIFICATION:
        At yaw=180: cos(180)=-1, sin(180)=0
        forward=10: north = 10*(-1) - 0 = -10, east = 10*0 + 0 = 0
        right=5: north = 0 - 5*0 = 0, east = 0 + 5*(-1) = -5
        """
        # Facing south, move forward 10m (should be -north)
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=180.0)
        assert pytest.approx(north, 0.01) == -10.0
        assert pytest.approx(east, 0.01) == 0.0

        # Facing south, move right 5m (should be -east/west)
        north, east = body_to_ned(forward_m=0.0, right_m=5.0, yaw_deg=180.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == -5.0

    def test_body_to_ned_transform_west_heading(self):
        """Test transform when drone is facing west (yaw=270 or -90).

        WHAT THIS VALIDATES:
        At yaw=270, forward should map to west (negative east), and right
        should map to north.

        EXPECTED OUTCOMES:
        - forward=10, right=0 → north=0, east=-10 (pure west)
        - forward=0, right=5 → north=5, east=0 (pure north)

        MATH VERIFICATION:
        At yaw=270: cos(270)=0, sin(270)=-1
        forward=10: north = 10*0 - 0 = 0, east = 10*(-1) + 0 = -10
        right=5: north = 0 - 5*(-1) = 5, east = 0 + 5*0 = 0
        """
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
        """Test transform when drone is facing northeast (yaw=45).

        WHAT THIS VALIDATES:
        At diagonal headings, forward movement should split between north and east.

        EXPECTED OUTCOMES:
        - forward=10 at yaw=45 → north≈7.07, east≈7.07 (45-degree diagonal)

        MATH VERIFICATION:
        At yaw=45: cos(45)=sin(45)=0.707
        forward=10: north = 10*0.707 = 7.07, east = 10*0.707 = 7.07
        """
        # Facing NE (yaw=45), move forward 10m
        # north = 10*cos(45) - 0*sin(45) = 10*0.707 = 7.07
        # east = 10*sin(45) + 0*cos(45) = 10*0.707 = 7.07
        north, east = body_to_ned(forward_m=10.0, right_m=0.0, yaw_deg=45.0)
        expected = 10.0 * math.cos(math.radians(45.0))
        assert pytest.approx(north, 0.01) == expected
        assert pytest.approx(east, 0.01) == expected

    def test_body_to_ned_transform_diagonal_movement(self):
        """Test diagonal movement at various headings.

        WHAT THIS VALIDATES:
        When both forward and right are specified, the resulting movement
        is the vector sum of both components, properly rotated.

        EXPECTED OUTCOMES:
        - forward=10, right=10 at yaw=0 → north=10, east=10 (northeast in body frame)
        - At yaw=45, the result should account for both components
        """
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
        """Test with negative values (back and left movement).

        WHAT THIS VALIDATES:
        Negative values for forward and right should correctly produce
        backward and leftward movement respectively.

        EXPECTED OUTCOMES:
        - forward=-5 at yaw=0 → north=-5 (backward)
        - right=-5 at yaw=0 → east=-5 (left/west)
        """
        # Move back 5m when facing north
        north, east = body_to_ned(forward_m=-5.0, right_m=0.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == -5.0
        assert pytest.approx(east, 0.01) == 0.0

        # Move left 5m when facing north (should be -east/west)
        north, east = body_to_ned(forward_m=0.0, right_m=-5.0, yaw_deg=0.0)
        assert pytest.approx(north, 0.01) == 0.0
        assert pytest.approx(east, 0.01) == -5.0


class TestForwardMovement:
    """Tests for forward movement execution.

    WHAT THESE TESTS COVER:
    Integration tests validating that fly_body_offset() correctly:
    - Queries current position and yaw
    - Applies body-to-NED transform
    - Commands goto_location with correct target
    - Handles yaw_align parameter

    MOCK STRATEGY:
    - ConnectionManager._do_connect: Returns mock drone
    - Mock drone telemetry: Returns known position/yaw
    - Mock action.goto_location: Captures commanded target for verification
    """

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_forward_movement_executes(self, mock_do_connect):
        """Test that forward movement executes correctly.

        WHAT THIS VALIDATES:
        - FlightTools.fly_body_offset() accepts forward_m parameter
        - Gets current position from telemetry
        - Calculates correct target position (10m north at yaw=0)
        - Commands drone via goto_location()

        EXPECTED OUTCOMES:
        - success=True in result
        - offset.forward_m=10.0 in result
        - goto_location called with latitude > current (moved north)
        - goto_location called with longitude unchanged

        MOCK SETUP:
        - mock_do_connect returns create_mock_drone() (position at SF, yaw=0)
        - ConnectionManager singleton reset between tests
        - Guardian home position set for validation
        - State machine set to HOVERING
        """
        tools = FlightTools()

        # Create mock drone
        mock_drone = create_mock_drone()
        mock_do_connect.return_value = mock_drone

        # Reset ConnectionManager singleton state
        cm = ConnectionManager()
        cm._state = ConnectionManager._instance._state if hasattr(ConnectionManager._instance, '_state') else cm._state
        await cm.disconnect()

        # Set home position for guardian validation
        # WHY: Guardian validates all movements stay within geofence from home
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
        """Test forward movement with yaw alignment.

        WHAT THIS VALIDATES:
        The yaw_align=True parameter causes the drone to rotate to face the
        direction of movement (in this case, maintaining east-facing yaw).

        EXPECTED OUTCOMES:
        - success=True
        - yaw_align=True in result
        - goto_location called with yaw≈90 (matching the drone's heading)

        MOCK SETUP:
        Similar to test_forward_movement_executes but with mock_attitude.yaw_deg=90
        to test that yaw_align preserves the current heading.
        """
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
    """Tests for right/left (lateral) movement.

    WHAT THESE TESTS COVER:
    - Right movement (positive right_m) at various headings
    - Left movement (negative right_m)
    - Coordinate transform correctness for lateral offsets
    """

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_right_movement_executes(self, mock_do_connect):
        """Test that right movement executes correctly.

        WHAT THIS VALIDATES:
        Right movement (positive right_m) at yaw=0 should move the drone east
        (increasing longitude at SF coordinates).

        EXPECTED OUTCOMES:
        - success=True
        - offset.right_m=5.0 in result
        - goto_location called with longitude > current (moved east)
        - latitude unchanged

        MOCK SETUP:
        Standard mock drone at SF coordinates, yaw=0 (north).
        """
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
        """Test that left movement (negative right) executes correctly.

        WHAT THIS VALIDATES:
        Left movement (negative right_m) at yaw=0 should move the drone west
        (decreasing longitude).

        EXPECTED OUTCOMES:
        - success=True
        - offset.right_m=-5.0 in result
        - goto_location called with longitude < current (moved west)

        MOCK SETUP:
        Standard mock drone at SF coordinates, yaw=0 (north).
        """
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
    """Tests for combined/diagonal movement.

    WHAT THESE TESTS COVER:
    - Simultaneous forward, right, and up movement
    - Vector addition of body frame components
    - Altitude changes (up_m parameter)
    - Yaw alignment with combined offsets
    """

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_diagonal_forward_right(self, mock_do_connect):
        """Test diagonal forward-right movement.

        WHAT THIS VALIDATES:
        When both forward and right are specified, the drone moves diagonally.
        At yaw=0 (north), forward+right = northeast movement.

        EXPECTED OUTCOMES:
        - success=True
        - offset contains all three components (forward=10, right=10, up=5)
        - transform shows positive north_m and east_m
        - goto_location called with altitude=55 (50 + 5 up)

        MOCK SETUP:
        Standard mock drone at SF coordinates, yaw=0.
        """
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
        """Test diagonal movement with yaw alignment.

        WHAT THIS VALIDATES:
        With equal forward and right (10m each), the movement direction is
        45 degrees northeast. yaw_align=True should set target yaw to 45.

        EXPECTED OUTCOMES:
        - success=True
        - yaw_align=True in result
        - target.yaw_deg ≈ 45.0 (diagonal direction)

        MOCK SETUP:
        Standard mock drone at SF coordinates, yaw=0.
        """
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
    """Tests for position hold after reaching target.

    WHAT THESE TESTS COVER:
    - State machine transitions after movement commands
    - Entry into POSITION_CONTROL state for active waypoint following
    """

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_state_transition_to_position_control(self, mock_do_connect):
        """Test that state transitions to POSITION_CONTROL.

        WHAT THIS VALIDATES:
        After executing a body-relative movement command, the state machine
        should enter POSITION_CONTROL state to indicate active position holding.

        EXPECTED OUTCOMES:
        - Initial state: HOVERING
        - After movement: POSITION_CONTROL
        - success=True

        MOCK SETUP:
        Standard mock drone, with state machine set to HOVERING initially.
        """
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
    """Tests for state machine integration and preconditions.

    WHAT THESE TESTS COVER:
    - Movement commands require flying state (not DISARMED, etc.)
    - Appropriate error messages when preconditions fail
    - Success when in valid flying states
    """

    @pytest.mark.asyncio
    async def test_state_precondition_ground_state_fails(self):
        """Test that movement fails when in ground state.

        WHAT THIS VALIDATES:
        fly_body_offset() should reject commands when the drone is not in
        an appropriate flying state (DISARMED, LANDED, etc.).

        EXPECTED OUTCOMES:
        - isError=True (structured error envelope from Wave 1)
        - Error message mentions "Cannot move" and state name
        - Error code is PREFLIGHT_BLOCKED

        WHY THIS MATTERS:
        Prevents accidental takeoff attempts or movement commands when the
drone is not ready to fly, improving safety.
        """
        tools = FlightTools()

        # Set state machine to DISARMED (ground state)
        tools.state_machine.transition(FlightState.DISARMED, "test", "test")
        assert tools.state_machine.current_state == FlightState.DISARMED

        # Execute movement - should fail due to state precondition
        result = await tools.fly_body_offset(forward_m=10.0)

        # Check structured error envelope format (Wave 1 D2.1)
        assert result["isError"] is True
        assert result["error"]["code"] == "PREFLIGHT_BLOCKED"
        assert "Cannot move" in result["error"]["message"]
        assert "DISARMED" in result["error"]["message"]

    @pytest.mark.asyncio
    @patch.object(ConnectionManager, '_do_connect', new_callable=AsyncMock)
    async def test_state_precondition_flying_state_succeeds(self, mock_do_connect):
        """Test that movement succeeds when in flying state.

        WHAT THIS VALIDATES:
        fly_body_offset() should accept commands from any of the flying states:
        HOVERING, FLYING, POSITION_CONTROL, VELOCITY_CONTROL, MISSION_EXECUTION, HOLD

        EXPECTED OUTCOMES:
        - All flying states result in success=True
        - No errors for any valid flying state

        MOCK SETUP:
        Creates fresh FlightTools and mock drone for each state to ensure
        isolation between test iterations.
        """
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
        """Test that speed is validated against guardian limits.

        WHAT THIS VALIDATES:
        The guardian validates all movement commands against safety limits.
        If requested speed exceeds HardLimits.max_speed_m_s, the command fails.

        EXPECTED OUTCOMES:
        - isError=True when speed exceeds limit (structured error envelope)
        - Error code is GUARDIAN_VIOLATION
        - Error message indicates speed limit violation

        MOCK SETUP:
        Mock guardian with validate_command returning failure for high speed.
        """
        tools = FlightTools()

        # Set up strict limits
        hard_limits = HardLimits(max_speed_m_s=5.0)
        tools.guardian = MagicMock()
        tools.guardian.validate_command = MagicMock(return_value=(False, "Speed 10m/s exceeds max 5m/s"))

        # Set state machine to flying state
        set_state_to_flying(tools.state_machine, FlightState.HOVERING)

        # Execute movement with excessive speed
        result = await tools.fly_body_offset(forward_m=10.0, speed_m_s=10.0)

        # Check structured error envelope format (Wave 1 D2.1)
        assert result["isError"] is True
        assert result["error"]["code"] == "GUARDIAN_VIOLATION"
        assert "exceeds max" in result["error"]["message"]


class TestMcpToolWrapper:
    """Tests for the MCP tool wrapper function.

    WHAT THESE TESTS COVER:
    - The fly_body_offset MCP tool interface (JSON input/output)
    - Proper delegation to FlightTools.fly_body_offset()
    - JSON serialization of results
    """

    @pytest.mark.asyncio
    @patch("avatar.mcp_server.tools.flight_tools.FlightTools")
    async def test_fly_body_offset_wrapper(self, mock_tools_class):
        """Test the fly_body_offset MCP tool wrapper.

        WHAT THIS VALIDATES:
        The wrapper function (exposed to MCP) correctly:
        - Instantiates FlightTools
        - Calls fly_body_offset with parsed parameters
        - Returns JSON-serialized result

        EXPECTED OUTCOMES:
        - Returns valid JSON
        - JSON contains success=True
        - JSON contains offset fields matching input
        - FlightTools.fly_body_offset() called with correct arguments

        MOCK SETUP:
        Mock FlightTools class to avoid real connection attempts.
        """
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

    WHAT THIS DOES:
    State machines have strict transition rules (e.g., can't go from
    DISARMED directly to HOVERING). This helper follows the valid path:
    INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING

    WHY THIS MATTERS:
    Tests need to set up specific states, but doing so directly would
    violate state machine invariants. This helper ensures valid transitions.

    ARGUMENTS:
    - state_machine: The FlightStateMachine instance to configure
    - target_state: Desired flying state (default: HOVERING)

    TRANSITION PATH:
    1. Reset to INIT (if not already)
    2. DISARMED (initial ground state)
    3. ARMED (ready to fly)
    4. TAKING_OFF (spooling motors)
    5. HOVERING (stable flight)
    6. (Optional) target_state if different from HOVERING
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
    """Helper class to create async iterators for mocking.

    WHAT THIS DOES:
    MAVSDK telemetry methods return async generators (objects that can be
    used with 'async for'). This class wraps a list to provide that interface.

    WHY THIS MATTERS:
    Python's unittest.mock can't directly mock async generators. This helper
    allows us to simulate MAVSDK's telemetry.position() and attitude_euler()
    returning continuous streams of data.

    USAGE:
    AsyncIterator([mock_position]) creates an async iterator that yields
    mock_position once, then raises StopAsyncIteration.

    EXAMPLE:
    mock_telemetry.position = MagicMock(return_value=AsyncIterator([pos1, pos2]))
    # async for position in drone.telemetry.position():
    #     # yields pos1, then pos2
    """

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
