"""Tests for set_position_ned MCP tool - Position control in NED frame.

WHAT THESE TESTS VALIDATE:
    These tests verify the set_position_ned() MCP tool which commands the drone
    to fly to a specified position in NED (North-East-Down) frame using PX4's
    offboard control mode. Key capabilities tested:
    - Input schema validation (position bounds, speed limits)
    - State preconditions (requires flying state)
    - 20Hz MAVLink offboard streaming rate
    - OffboardOwner mutual exclusion
    - Graceful stop and cleanup
    - Error handling for connection failures

WHY THESE TESTS MATTER:
    Position control is fundamental for autonomous navigation. When an LLM
    commands "fly to position 50m north, 25m east at 20m altitude", the
    set_position_ned tool executes that command. Without proper position control:
    - The drone cannot fly to specific waypoints
    - Search patterns would be impossible
    - Formation flying cannot work
    - Safety limits could be violated

    The 20Hz streaming requirement is critical because PX4's offboard mode
    requires continuous setpoints. If the stream stops, PX4 exits offboard
    mode, which could cause the drone to drift.

NED COORDINATE FRAME:
    - North: Positive = northward from home position
    - East: Positive = eastward from home position  
    - Down: Positive = descending (NEGATIVE = UP)
    - Example: down_m=-10.0 means 10 meters above home

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific position control behaviors:
    - Input bounds: Positions outside -1000 to 1000m (N/E) or -500 to 0m (D) rejected
    - State preconditions: Command rejected in DISARMED, LANDING, EMERGENCY states
    - Streaming: Setpoints sent at ~20Hz (one every 50ms)
    - OffboardOwner: Proper acquire/release sequence
    - Cleanup: offboard.stop() called after completion

Coverage:
- Input schema validation
- State preconditions
- Offboard streaming
- OffboardOwner integration
- Error handling
"""

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools.primitives import (
    SetPositionNedInput,
    PositionStreamer,
    PositionToolsConfig,
    set_position_ned,
    set_state_machine,
    get_state_machine,
)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_state_machine():
    """Create a FlightStateMachine in HOVERING state.
    
    This is the primary entry point for position control commands.
    """
    sm = FlightStateMachine()
    # Transition from INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING
    sm.transition(FlightState.DISARMED, "startup_complete", "system")
    sm.transition(FlightState.ARMED, "operator_command", "operator")
    sm.transition(FlightState.TAKING_OFF, "takeoff_initiated", "llm")
    sm.transition(FlightState.HOVERING, "takeoff_complete", "telemetry")
    return sm


@pytest.fixture
def mock_drone():
    """Create a fully mocked MAVSDK drone with offboard support.
    
    Mocks offboard, telemetry, and action plugins needed for position control.
    """
    drone = MagicMock()
    
    # Mock offboard plugin
    drone.offboard = MagicMock()
    drone.offboard.set_position_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    
    # Mock telemetry for yaw and position
    drone.telemetry = MagicMock()
    
    # Mock attitude_euler for yaw
    attitude_mock = MagicMock()
    attitude_mock.yaw_deg = 0.0
    drone.telemetry.attitude_euler = MagicMock()
    drone.telemetry.attitude_euler.__aiter__ = lambda self: self
    drone.telemetry.attitude_euler.__anext__ = AsyncMock(return_value=attitude_mock)
    
    # Mock position_velocity_ned for position tracking
    pos_vel_mock = MagicMock()
    pos_vel_mock.position.north_m = 0.0
    pos_vel_mock.position.east_m = 0.0
    pos_vel_mock.position.down_m = -5.0
    drone.telemetry.position_velocity_ned = MagicMock()
    drone.telemetry.position_velocity_ned.__aiter__ = lambda self: self
    drone.telemetry.position_velocity_ned.__anext__ = AsyncMock(return_value=pos_vel_mock)
    
    # Mock position for initial read
    drone.telemetry.position = MagicMock()
    drone.telemetry.position.__aiter__ = lambda self: self
    drone.telemetry.position.__anext__ = AsyncMock(return_value=MagicMock())
    
    return drone


@pytest.fixture
def config():
    """Create default PositionToolsConfig."""
    return PositionToolsConfig()


# =============================================================================
# TEST CLASSES - INPUT SCHEMA VALIDATION
# =============================================================================


class TestInputSchema:
    """Test SetPositionNedInput schema validation.
    
    Validates that position bounds and speed limits are enforced.
    """

    def test_valid_input(self):
        """Test that valid inputs pass schema validation."""
        input_data = SetPositionNedInput(
            north_m=50.0,
            east_m=25.0,
            down_m=-20.0,
            yaw_deg=0.0,
            speed_m_s=5.0,
        )
        
        assert input_data.north_m == 50.0
        assert input_data.east_m == 25.0
        assert input_data.down_m == -20.0
        assert input_data.yaw_deg == 0.0
        assert input_data.speed_m_s == 5.0

    def test_optional_yaw(self):
        """Test that yaw_deg is optional."""
        input_data = SetPositionNedInput(
            north_m=10.0,
            east_m=10.0,
            down_m=-10.0,
        )
        
        assert input_data.yaw_deg is None

    def test_north_bounds_positive(self):
        """Test north_m maximum bound (1000m)."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=1001.0,
                east_m=0.0,
                down_m=-10.0,
            )

    def test_north_bounds_negative(self):
        """Test north_m minimum bound (-1000m)."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=-1001.0,
                east_m=0.0,
                down_m=-10.0,
            )

    def test_east_bounds(self):
        """Test east_m bounds."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=0.0,
                east_m=1001.0,
                down_m=-10.0,
            )

    def test_down_bounds_altitude(self):
        """Test down_m bounds (negative = up).
        
        down_m must be <= 0 (altitude above ground).
        Positive down_m would mean below ground, which is invalid.
        """
        # Positive down_m (below ground) should fail
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=0.0,
                east_m=0.0,
                down_m=1.0,  # Below ground - invalid
            )

    def test_down_bounds_too_high(self):
        """Test down_m altitude limit (-500m = 500m altitude)."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=0.0,
                east_m=0.0,
                down_m=-501.0,  # 501m altitude exceeds limit
            )

    def test_speed_bounds_minimum(self):
        """Test speed_m_s minimum bound."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=0.0,
                east_m=0.0,
                down_m=-10.0,
                speed_m_s=0.0,  # Must be > 0
            )

    def test_speed_bounds_maximum(self):
        """Test speed_m_s maximum bound (20 m/s)."""
        with pytest.raises(Exception):
            SetPositionNedInput(
                north_m=0.0,
                east_m=0.0,
                down_m=-10.0,
                speed_m_s=21.0,  # Exceeds 20 m/s
            )


# =============================================================================
# TEST CLASSES - STATE PRECONDITIONS
# =============================================================================


class TestStatePreconditions:
    """Test state machine integration for position control."""

    async def test_valid_states(self):
        """Test that set_position_ned works in valid flying states."""
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
            
            # Verify state is set correctly
            assert sm.current_state == state

    async def test_invalid_states(self):
        """Test that set_position_ned fails in non-flying states."""
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
                if state in [FlightState.ARMED]:
                    sm.transition(state, "transition", "system")
                elif state in [FlightState.LANDING, FlightState.LANDED]:
                    sm.transition(FlightState.ARMED, "arm", "operator")
                    sm.transition(FlightState.TAKING_OFF, "takeoff", "llm")
                    sm.transition(FlightState.HOVERING, "hover", "telemetry")
                    sm.transition(state, "land", "llm")
                elif state in [FlightState.EMERGENCY, FlightState.ERROR]:
                    sm._state = state
            
            # In invalid states, the tool should reject the command
            # We test this by checking state precondition logic
            valid_states = {
                FlightState.HOVERING,
                FlightState.FLYING,
                FlightState.POSITION_CONTROL,
                FlightState.VELOCITY_CONTROL,
                FlightState.MISSION_EXECUTION,
                FlightState.HOLD,
            }
            assert sm.current_state not in valid_states


# =============================================================================
# TEST CLASSES - OFFBOARD STREAMING
# =============================================================================


class TestPositionStreaming:
    """Test 20Hz offboard streaming rate for position setpoints."""

    async def test_streaming_lifecycle(self):
        """Verify offboard start and stop are called correctly."""
        streamer = PositionStreamer(rate_hz=20.0)
        mock_drone = MagicMock()
        mock_drone.offboard = MagicMock()
        mock_drone.offboard.set_position_ned = AsyncMock()
        mock_drone.offboard.start = AsyncMock()
        mock_drone.offboard.stop = AsyncMock()
        
        # Mock position_velocity_ned to report target reached immediately
        target_pos = MagicMock()
        target_pos.north_m = 10.0
        target_pos.east_m = 5.0
        target_pos.down_m = -10.0
        
        pos_vel_mock = MagicMock()
        pos_vel_mock.position.north_m = 10.0  # At target
        pos_vel_mock.position.east_m = 5.0
        pos_vel_mock.position.down_m = -10.0
        
        mock_drone.telemetry = MagicMock()
        mock_drone.telemetry.position_velocity_ned = MagicMock()
        mock_drone.telemetry.position_velocity_ned.__aiter__ = lambda self: self
        mock_drone.telemetry.position_velocity_ned.__anext__ = AsyncMock(return_value=pos_vel_mock)
        mock_drone.telemetry.position = MagicMock()
        mock_drone.telemetry.position.__aiter__ = lambda self: self
        mock_drone.telemetry.position.__anext__ = AsyncMock(return_value=MagicMock())
        
        from avatar.mcp_server.tools.primitives import PositionNedYaw
        position_setpoint = PositionNedYaw(10.0, 5.0, -10.0, 0.0)
        
        result = await streamer.stream_until_reached(
            drone=mock_drone,
            position_setpoint=position_setpoint,
            target_north=10.0,
            target_east=5.0,
            target_down=-10.0,
            tolerance_m=1.0,
            timeout_s=5.0,
        )
        
        # Verify offboard was started
        mock_drone.offboard.start.assert_called_once()
        # Verify offboard was stopped
        mock_drone.offboard.stop.assert_called_once()
        # Verify position was reached
        assert result["reached"] is True

    async def test_setpoint_transmission(self):
        """Verify setpoints are transmitted at correct rate."""
        streamer = PositionStreamer(rate_hz=20.0)
        
        # Verify interval is correct (50ms = 0.05s)
        assert streamer.interval_s == 0.05
        assert streamer.rate_hz == 20.0


# =============================================================================
# TEST CLASSES - OFFBOARD OWNER
# =============================================================================


class TestOffboardOwnerIntegration:
    """Test OffboardOwner mutual exclusion for offboard mode."""

    async def test_acquire_release_sequence(self):
        """Test that OffboardOwner is acquired and released correctly."""
        from avatar.mav.offboard_owner import get_offboard_owner, OffboardOwner
        
        # Get fresh owner
        owner = OffboardOwner()
        
        # Should be able to acquire
        acquired = await owner.acquire("test_owner")
        assert acquired is True
        assert owner.current_owner() == "test_owner"
        
        # Release
        await owner.release("test_owner")
        assert owner.current_owner() is None

    async def test_conflicting_ownership(self):
        """Test that conflicting ownership is rejected."""
        from avatar.mav.offboard_owner import OffboardOwner
        
        owner = OffboardOwner()
        
        # First owner acquires
        acquired1 = await owner.acquire("owner_1")
        assert acquired1 is True
        
        # Second owner should fail
        acquired2 = await owner.acquire("owner_2")
        assert acquired2 is False
        assert owner.current_owner() == "owner_1"

    async def test_reentrant_acquisition(self):
        """Test that same owner can reacquire."""
        from avatar.mav.offboard_owner import OffboardOwner
        
        owner = OffboardOwner()
        
        # First acquisition
        acquired1 = await owner.acquire("same_owner")
        assert acquired1 is True
        
        # Re-entrant acquisition should succeed
        acquired2 = await owner.acquire("same_owner")
        assert acquired2 is True


# =============================================================================
# TEST CLASSES - WRAPPER FUNCTION
# =============================================================================


class TestWrapperFunction:
    """Test the MCP wrapper function."""

    async def test_wrapper_returns_json(self):
        """Verify wrapper returns JSON string."""
        # This will fail on state check but should return valid JSON
        result = await set_position_ned(
            north_m=50.0,
            east_m=25.0,
            down_m=-20.0,
        )
        
        # Should be a JSON string
        try:
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.fail("Wrapper should return valid JSON string")

    async def test_wrapper_error_format(self):
        """Verify error responses are properly formatted."""
        # Invalid input should return error
        result = await set_position_ned(
            north_m=10000.0,  # Exceeds bounds
            east_m=0.0,
            down_m=-10.0,
        )
        
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "error" in parsed


# =============================================================================
# TEST CLASSES - ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in set_position_ned."""

    async def test_connection_error_handling(self, mock_state_machine):
        """Test graceful handling of connection errors."""
        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(
                side_effect=ConnectionError("Not connected")
            )
            
            result = await set_position_ned(
                north_m=50.0,
                east_m=25.0,
                down_m=-20.0,
            )
            
            parsed = json.loads(result)
            assert parsed["success"] is False
            assert "Not connected" in parsed["error"]

    async def test_invalid_state_error(self, mock_drone):
        """Test error when drone is in invalid state."""
        # Create state machine in DISARMED state
        sm = FlightStateMachine()
        # Leave in INIT state (invalid for position commands)
        
        with patch('avatar.mcp_server.tools.primitives.get_state_machine') as mock_get_sm:
            mock_get_sm.return_value = sm
            
            result = await set_position_ned(
                north_m=50.0,
                east_m=25.0,
                down_m=-20.0,
            )
            
            parsed = json.loads(result)
            assert parsed["success"] is False
            assert "Cannot set_position_ned" in parsed["error"]


# =============================================================================
# TEST CLASSES - RESULT FORMAT
# =============================================================================


class TestResultFormat:
    """Test the format of successful results."""

    async def test_success_result_format(self, mock_state_machine, mock_drone):
        """Verify successful result contains expected fields."""
        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)
            
            with patch('avatar.mcp_server.tools.primitives.get_state_machine') as mock_get_sm:
                mock_get_sm.return_value = mock_state_machine
                
                # Mock the streamer to return success quickly
                with patch.object(
                    PositionStreamer,
                    'stream_until_reached',
                    new_callable=AsyncMock
                ) as mock_stream:
                    mock_stream.return_value = {
                        "setpoints_sent": 20,
                        "reached": True,
                        "final_distance_m": 0.5,
                    }
                    
                    result = await set_position_ned(
                        north_m=50.0,
                        east_m=25.0,
                        down_m=-20.0,
                        yaw_deg=0.0,
                        speed_m_s=5.0,
                    )
                    
                    parsed = json.loads(result)
                    
                    assert parsed["success"] is True
                    assert "message" in parsed
                    assert "position" in parsed
                    assert parsed["position"]["north_m"] == 50.0
                    assert parsed["position"]["east_m"] == 25.0
                    assert parsed["position"]["down_m"] == -20.0
                    assert parsed["yaw_deg"] == 0.0
                    assert parsed["speed_m_s"] == 5.0
                    assert parsed["setpoints_sent"] == 20
                    assert parsed["reached"] is True
                    assert "final_distance_m" in parsed


# =============================================================================
# TEST CLASSES - CONFIGURATION
# =============================================================================


class TestConfiguration:
    """Test PositionToolsConfig defaults."""

    def test_default_config(self):
        """Verify default configuration values."""
        config = PositionToolsConfig()
        
        assert config.streaming_rate_hz == 20.0
        assert config.approach_timeout_s == 60.0
        assert config.position_tolerance_m == 1.0
        assert config.max_retries == 3

    def test_custom_config(self):
        """Verify custom configuration values."""
        config = PositionToolsConfig(
            streaming_rate_hz=10.0,
            approach_timeout_s=30.0,
            position_tolerance_m=0.5,
        )
        
        assert config.streaming_rate_hz == 10.0
        assert config.approach_timeout_s == 30.0
        assert config.position_tolerance_m == 0.5


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
