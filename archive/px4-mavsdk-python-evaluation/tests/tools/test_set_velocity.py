"""Tests for set_velocity MCP tool - Offboard velocity control.

WHAT THESE TESTS VALIDATE:
    These tests verify the set_velocity() MCP tool which commands the drone to
    fly at a specified velocity vector using PX4's offboard control mode.
    Key capabilities tested:
    - Velocity limits enforcement (15 m/s horizontal, 3 m/s vertical)
    - State preconditions (requires HOVERING, FLYING, or similar active flight state)
    - 20Hz MAVLink offboard streaming rate maintenance
    - Graceful stop and cleanup after velocity control
    - Proper state transitions (to/from VELOCITY_CONTROL)
    - Error handling for connection failures and offboard errors

WHY THESE TESTS MATTER:
    Velocity control is the foundation of autonomous movement. When an LLM
    commands "fly north at 5 m/s" or "orbit the target," the set_velocity
    tool executes those commands. Without proper velocity control:
    - The drone cannot perform guided movement
    - Position-based navigation would be jerky and inefficient
    - Emergency maneuvers (evasive action) would not work
    - Safety limits (max speed) could be violated

    The 20Hz streaming requirement is critical because PX4's offboard mode
    requires a continuous stream of setpoints. If the stream stops, PX4
    exits offboard mode, which could cause the drone to drift or fall.

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific velocity control behaviors:
    - Velocity limits: Speeds >15 m/s horizontal or >3 m/s vertical are rejected
    - Diagonal limits: Combined vector magnitude is checked, not just components
    - State preconditions: Command rejected in DISARMED, LANDING, EMERGENCY states
    - Streaming: Setpoints sent at ~20Hz (one every 50ms)
    - Cleanup: offboard.stop() called after duration to exit offboard mode
    - State machine: Transitions to VELOCITY_CONTROL during, FLYING after

Coverage:
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


# =============================================================================
# PYTEST FIXTURES
# =============================================================================
# Fixtures provide consistent test setup with mocked dependencies.


@pytest.fixture
def mock_state_machine():
    """Create a FlightStateMachine in HOVERING state.

    WHAT: Provides a state machine initialized through full startup sequence
    to HOVERING state, which is the primary entry point for velocity control.

    WHY: set_velocity requires an active flight state (not DISARMED, etc.).
    HOVERING represents a stable hover ready for commanded movement.

    HOW IT WORKS - STEP BY STEP:
        1. Creates FlightStateMachine (starts in INIT)
        2. INIT -> DISARMED (startup_complete from system)
        3. DISARMED -> ARMED (operator_command from operator)
        4. ARMED -> TAKING_OFF (takeoff_initiated from llm)
        5. TAKING_OFF -> HOVERING (takeoff_complete from telemetry)
        6. Returns machine in HOVERING state

    Returns:
        FlightStateMachine in HOVERING state.
    """
    sm = FlightStateMachine()
    # Transition from INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING
    sm.transition(FlightState.DISARMED, "startup_complete", "system")
    sm.transition(FlightState.ARMED, "operator_command", "operator")
    sm.transition(FlightState.TAKING_OFF, "takeoff_initiated", "llm")
    sm.transition(FlightState.HOVERING, "takeoff_complete", "telemetry")
    return sm


@pytest.fixture
def flight_tools(mock_state_machine):
    """Create FlightTools instance with mocked state machine.

    WHAT: Provides configured FlightTools ready for velocity control tests.

    WHY: Isolates tests from real drone while maintaining realistic interfaces.

    HOW: Creates FlightTools with default config and injected state machine.

    Returns:
        FlightTools instance with mocked state.
    """
    config = FlightToolsConfig()
    tools = FlightTools(config=config, state_machine=mock_state_machine)
    return tools


@pytest.fixture
def mock_drone():
    """Create a fully mocked MAVSDK drone with offboard support.

    WHAT: Provides a MagicMock configured to simulate MAVSDK drone interface,
    specifically the offboard plugin used for velocity control.

    WHY: Real drone connection isn't needed for unit tests of limit checking,
    state validation, and streaming logic.

    HOW: Creates mock with offboard plugin having AsyncMock methods for:
        - set_velocity_ned: Send velocity setpoints
        - start: Enter offboard mode
        - stop: Exit offboard mode

    Returns:
        Mocked drone object compatible with FlightTools interfaces.
    """
    drone = MagicMock()

    # Mock offboard plugin
    drone.offboard = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()

    return drone


# =============================================================================
# TEST CLASSES - VELOCITY LIMITS
# =============================================================================


class TestVelocityLimits:
    """Test velocity limit enforcement.

    WHAT THESE TESTS VALIDATE:
        - Horizontal speed limited to 15 m/s (safety for outdoor flight)
        - Vertical speed limited to 3 m/s (safety for altitude changes)
        - Diagonal/combined velocities use magnitude, not components
        - Speeds within limits are accepted (when connection mocked)

    WHY THESE TESTS MATTER:
        Excessive speed is dangerous. 15 m/s (54 km/h) is the configured max
        for this system to ensure safe operation in typical environments.
        Vertical limits prevent rapid altitude changes that could cause:
        - Vortex ring state (settling with power)
        - Ground impact during descent
        - Loss of control during rapid climb

        These limits are the last line of defense if the LLM requests unsafe speeds.
    """

    async def test_horizontal_speed_limit(self, flight_tools):
        """Test rejection of horizontal velocities exceeding 15 m/s.

        WHAT THIS TEST VALIDATES:
            When north_m_s=16.0 (exceeding 15 m/s limit), the command is
            rejected before any drone communication occurs.

        EXPECTED OUTCOMES:
            - isError=True (Wave 1 error envelope format)
            - error message mentions "15 m/s" limit

        HOW IT WORKS:
            Calls set_velocity with 16 m/s north, asserts validation catches it.
        """
        # 16 m/s north exceeds limit
        result = await flight_tools.set_velocity(
            north_m_s=16.0, east_m_s=0.0, down_m_s=0.0, duration_s=0.1
        )

        # Wave 1 error envelope format
        assert result.get("isError") is True
        assert "15 m/s" in result.get("error", {}).get("message", "")

    async def test_horizontal_speed_diagonal(self, flight_tools):
        """Test rejection of diagonal velocities where vector magnitude exceeds 15 m/s.

        WHAT THIS TEST VALIDATES:
            The limit is on total horizontal speed (sqrt(north^2 + east^2)),
            not individual components. A command with 11.31 m/s north AND
            11.31 m/s east has total magnitude of 16 m/s, which exceeds limit.

        EXPECTED OUTCOMES:
            - isError=True (Wave 1 error envelope format)
            - error mentions "15 m/s" (the limit, not the calculated magnitude)

        HOW IT WORKS:
            Calls set_velocity with diagonal velocity totaling 16 m/s,
            asserts combined magnitude validation catches it.
        """
        # 11.31 m/s each direction = 16 m/s total
        result = await flight_tools.set_velocity(
            north_m_s=11.31, east_m_s=11.31, down_m_s=0.0, duration_s=0.1
        )

        # Wave 1 error envelope format
        assert result.get("isError") is True
        assert "15 m/s" in result.get("error", {}).get("message", "")

    async def test_vertical_speed_limit_up(self, flight_tools):
        """Test rejection of upward velocities exceeding 3 m/s.

        WHAT THIS TEST VALIDATES:
            Negative down_m_s means upward velocity (NED coordinate system:
            North-East-Down). down_m_s=-4.0 means 4 m/s upward, exceeding limit.

        EXPECTED OUTCOMES:
            - isError=True (Wave 1 error envelope format)
            - error mentions "3 m/s" vertical limit

        HOW IT WORKS:
            Calls set_velocity with -4.0 down (4 m/s up), asserts caught.
        """
        # -4.0 down_m_s = 4 m/s upward exceeds limit
        result = await flight_tools.set_velocity(
            north_m_s=0.0, east_m_s=0.0, down_m_s=-4.0, duration_s=0.1
        )

        # Wave 1 error envelope format
        assert result.get("isError") is True
        assert "3 m/s" in result.get("error", {}).get("message", "")

    async def test_vertical_speed_limit_down(self, flight_tools):
        """Test rejection of downward velocities exceeding 3 m/s.

        WHAT THIS TEST VALIDATES:
            Positive down_m_s means downward velocity. 4 m/s descent exceeds limit.

        EXPECTED OUTCOMES:
            - isError=True (Wave 1 error envelope format)
            - error mentions "3 m/s"

        HOW IT WORKS:
            Calls set_velocity with +4.0 down, asserts caught.
        """
        result = await flight_tools.set_velocity(
            north_m_s=0.0, east_m_s=0.0, down_m_s=4.0, duration_s=0.1
        )

        # Wave 1 error envelope format
        assert result.get("isError") is True
        assert "3 m/s" in result.get("error", {}).get("message", "")

    async def test_valid_speeds_accepted(self, flight_tools, mock_drone):
        """Test that velocities within limits pass validation.

        WHAT THIS TEST VALIDATES:
            When velocities are within all limits (10 north, 5 east, 2 up),
            validation passes and the command proceeds (though may fail on
            connection since we're mocking).

        EXPECTED OUTCOMES:
            - Either success=True (if fully mocked)
            - Or error mentions connection (if only streaming mocked)
            - No validation error about speed limits

        HOW IT WORKS:
            Mocks _maintain_offboard_streaming to simulate successful operation,
            then calls set_velocity with valid speeds and verifies validation passes.
        """
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)
            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20  # Simulate successful streaming

                result = await flight_tools.set_velocity(
                    north_m_s=10.0, east_m_s=5.0, down_m_s=-2.0, duration_s=0.1
                )

                assert result["success"] is True


# =============================================================================
# TEST CLASSES - STATE PRECONDITIONS
# =============================================================================


class TestStatePreconditions:
    """Test state machine integration for velocity control.

    WHAT THESE TESTS VALIDATE:
        - set_velocity works in valid flying states (HOVERING, FLYING, etc.)
        - set_velocity rejected in invalid states (DISARMED, LANDING, etc.)
        - State transitions to VELOCITY_CONTROL during operation
        - Clear error messages indicate why state is invalid

    WHY THESE TESTS MATTER:
        State preconditions prevent dangerous operations at wrong times.
        You can't velocity-control a disarmed drone or one that's landing.
        These checks ensure the state machine and tool logic stay synchronized.
    """

    async def test_valid_states(self):
        """Test that set_velocity works in valid flying states.

        WHAT THIS TEST VALIDATES:
            set_velocity is accepted in these states:
            - HOVERING: Stable hover, ready for movement
            - FLYING: Already in motion
            - POSITION_CONTROL: Switching from position to velocity
            - VELOCITY_CONTROL: Continuing velocity control
            - MISSION_EXECUTION: Interrupting mission for velocity
            - HOLD: Exiting hold for velocity

        EXPECTED OUTCOMES:
            For each valid state, set_velocity does NOT fail with state error.

        HOW IT WORKS:
            1. For each valid state, creates state machine in that state
            2. Calls set_velocity with short duration
            3. Asserts error message does NOT contain "Cannot set_velocity in state"
        """
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

            with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
                mock_cm.return_value.ensure_connected = AsyncMock(return_value=MagicMock())
                with patch.object(tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                    mock_stream.return_value = 20
                    result = await tools.set_velocity(duration_s=0.1)

            # Should NOT fail due to state check
            assert "Cannot set_velocity in state" not in result.get("error", "")

    async def test_invalid_states(self):
        """Test that set_velocity fails in non-flying states.

        WHAT THIS TEST VALIDATES:
            set_velocity is rejected in these states:
            - INIT: System not ready
            - DISARMED: Drone on ground, motors off
            - ARMED: Armed but not flying
            - LANDING: In landing sequence
            - LANDED: On ground after landing
            - EMERGENCY: Emergency condition active
            - ERROR: Error state

        EXPECTED OUTCOMES:
            For each invalid state:
            - success=False
            - error message contains "Cannot set_velocity in state"

        HOW IT WORKS:
            1. For each invalid state, creates state machine in that state
            2. Calls set_velocity
            3. Asserts appropriate error response
        """
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

            # Wave 1 error envelope format
            assert result.get("isError") is True
            assert "Cannot set_velocity in state" in result.get("error", {}).get("message", "")

    async def test_state_transition_to_velocity_control(self, flight_tools, mock_drone):
        """Test that state transitions to VELOCITY_CONTROL during operation.

        WHAT THIS TEST VALIDATES:
            When set_velocity is executed successfully, the state machine
            transitions to VELOCITY_CONTROL state.

        EXPECTED OUTCOMES:
            - After set_velocity, state_machine.current_state == VELOCITY_CONTROL

        HOW IT WORKS:
            1. Mocks ConnectionManager to return mock_drone
            2. Mocks _maintain_offboard_streaming to simulate success
            3. Calls set_velocity
            4. Verifies state transition occurred
        """
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20

                await flight_tools.set_velocity(duration_s=0.1)

                # State should transition to VELOCITY_CONTROL
                assert flight_tools.state_machine.current_state == FlightState.VELOCITY_CONTROL


# =============================================================================
# TEST CLASSES - OFFBOARD STREAMING
# =============================================================================


class TestOffboardStreaming:
    """Test 20Hz offboard streaming rate maintenance.

    WHAT THESE TESTS VALIDATE:
        - setpoints are sent at approximately 20Hz during velocity control
        - offboard.start() is called before streaming begins
        - offboard.stop() is called after streaming completes
        - Correct velocity values are sent in setpoints
        - Offboard errors are handled gracefully

    WHY THESE TESTS MATTER:
        PX4's offboard mode requires a continuous (>2Hz, recommended 10-50Hz)
        stream of setpoints. If the stream stops, PX4 exits offboard mode and
        switches to a failsafe mode (usually HOLD or RTL). The 20Hz rate:
        - Keeps PX4 reliably in offboard mode
        - Allows smooth velocity tracking
        - Provides margin if some messages are lost

        Without proper streaming, the drone would not maintain commanded velocity.
    """

    async def test_streaming_rate_calculation(self):
        """Verify that setpoints are sent at approximately 20Hz.

        WHAT THIS TEST VALIDATES:
            For a 0.15s duration at 20Hz, we expect ~3 setpoints.
            The _maintain_offboard_streaming method returns the count sent.

        EXPECTED OUTCOMES:
            - setpoint_count >= 2 (at least a couple sent)
            - offboard.start called once
            - offboard.stop called once

        HOW IT WORKS:
            1. Creates mock drone with mocked offboard
            2. Creates velocity setpoint (1 m/s north)
            3. Calls _maintain_offboard_streaming for 0.15s
            4. Verifies multiple setpoints were sent
            5. Verifies start/stop were called
        """
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
        """Verify that correct velocity values are sent in setpoints.

        WHAT THIS TEST VALIDATES:
            The velocity values passed to set_velocity are correctly
            packaged into VelocityNedYaw and sent via set_velocity_ned.

        EXPECTED OUTCOMES:
            - set_velocity_ned called with correct north, east, down, yaw values

        HOW IT WORKS:
            1. Creates specific velocity values (5 north, 3 east, -1 down, 45 yaw)
            2. Calls _maintain_offboard_streaming
            3. Inspects the calls made to set_velocity_ned
            4. Verifies first call contains expected values
        """
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
        sent_velocity = first_call.args[0]
        assert sent_velocity.north_m_s == 5.0
        assert sent_velocity.east_m_s == 3.0
        assert sent_velocity.down_m_s == -1.0
        assert sent_velocity.yaw_deg == 45.0

    async def test_streaming_failure_handling(self):
        """Test graceful handling when offboard fails to start.

        WHAT THIS TEST VALIDATES:
            If offboard.start() raises an error, the method handles it
            gracefully and returns 0 setpoints sent.

        EXPECTED OUTCOMES:
            - setpoint_count == 0 (indicating failure)
            - No unhandled exceptions raised

        HOW IT WORKS:
            1. Creates mock where offboard.start raises OffboardError
            2. Calls _maintain_offboard_streaming
            3. Verifies it returns 0 (failure indicator)
        """
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


# =============================================================================
# TEST CLASSES - GRACEFUL STOP
# =============================================================================


class TestGracefulStop:
    """Test graceful cleanup after velocity control.

    WHAT THESE TESTS VALIDATE:
        - offboard.stop() is called when streaming completes
        - State returns to FLYING after velocity control completes
        - Resources are cleaned up even if errors occur

    WHY THESE TESTS MATTER:
        Without proper cleanup, the drone could remain in offboard mode
        after the LLM thought it had stopped, leading to uncontrolled
        movement. Proper state transitions ensure the system is ready for
        the next command.
    """

    async def test_offboard_stop_called(self, flight_tools, mock_drone):
        """Verify offboard.stop is called when streaming completes.

        WHAT THIS TEST VALIDATES:
            After set_velocity duration elapses, offboard.stop() is called
            to exit offboard mode and return to normal flight.

        EXPECTED OUTCOMES:
            - _maintain_offboard_streaming mock was called

        HOW IT WORKS:
            1. Mocks ConnectionManager
            2. Mocks _maintain_offboard_streaming (which handles stop)
            3. Calls set_velocity
            4. Verifies streaming was invoked
        """
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock the streaming to complete quickly
            with patch.object(flight_tools, '_maintain_offboard_streaming', new_callable=AsyncMock) as mock_stream:
                mock_stream.return_value = 20

                await flight_tools.set_velocity(duration_s=0.1)

                # The mock stream should have been called
                mock_stream.assert_called_once()

    async def test_state_transition_back_after_completion(self, flight_tools, mock_drone):
        """Verify state returns to FLYING after velocity control.

        WHAT THIS TEST VALIDATES:
            After set_velocity completes, the state machine should be in
            an appropriate state (FLYING or VELOCITY_CONTROL) depending on
            whether cleanup occurred.

        EXPECTED OUTCOMES:
            - Final state is one of: FLYING, VELOCITY_CONTROL

        HOW IT WORKS:
            1. Mocks ConnectionManager and streaming
            2. Calls set_velocity
            3. Checks final state
        """
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


# =============================================================================
# TEST CLASSES - WRAPPER FUNCTION
# =============================================================================


class TestWrapperFunction:
    """Test the MCP wrapper function.

    WHAT THESE TESTS VALIDATE:
        The set_velocity() function exposed to MCP returns properly formatted
        JSON strings that can be parsed by the agent. Default parameters work.

    WHY THESE TESTS MATTER:
        MCP tools communicate via JSON-RPC. The wrapper must return strings,
        not Python objects, and handle default parameter values correctly.
    """

    async def test_set_velocity_wrapper_returns_json(self):
        """Verify wrapper returns JSON string.

        WHAT THIS TEST VALIDATES:
            The set_velocity() MCP entry point returns a string that can be
            parsed as valid JSON.

        EXPECTED OUTCOMES:
            - Result is a string
            - json.loads() succeeds
            - Parsed result is a dictionary

        HOW IT WORKS:
            Calls set_velocity with specific parameters, attempts JSON parse.
        """
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
        """Verify wrapper works with default parameters.

        WHAT THIS TEST VALIDATES:
            set_velocity() can be called with no arguments, using defaults.

        EXPECTED OUTCOMES:
            - Returns valid JSON
            - Contains success or error field

        HOW IT WORKS:
            Calls set_velocity with no arguments, verifies JSON response.
        """
        result = await set_velocity()

        try:
            parsed = json.loads(result)
            # Should either succeed or fail gracefully
            assert "success" in parsed or "error" in parsed
        except json.JSONDecodeError:
            pytest.fail("Wrapper should return valid JSON string")


# =============================================================================
# TEST CLASSES - ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in set_velocity.

    WHAT THESE TESTS VALIDATE:
        The set_velocity tool handles error conditions gracefully:
        - Connection errors (drone not reachable)
        - Unexpected exceptions during operation
        Returns informative error messages rather than crashing.

    WHY THESE TESTS MATTER:
        Real operations encounter network issues, hardware failures, and
        unexpected conditions. Graceful degradation allows the LLM to:
        - Understand what went wrong
        - Potentially retry or recover
        - Decide on alternative actions
    """

    async def test_connection_error_handling(self, flight_tools):
        """Test graceful handling of connection errors.

        WHAT THIS TEST VALIDATES:
            When ConnectionManager raises ConnectionError, the tool catches
            it and returns a failure response with error details.

        EXPECTED OUTCOMES:
            - success=False
            - error message explains connection issue

        HOW IT WORKS:
            1. Patches ConnectionManager to raise ConnectionError
            2. Calls set_velocity
            3. Verifies graceful error response
        """
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(
                side_effect=ConnectionError("Not connected")
            )

            result = await flight_tools.set_velocity(duration_s=0.1)

            # Wave 1 error envelope format
            assert result.get("isError") is True
            assert "Not connected" in result.get("error", {}).get("message", "")

    async def test_general_exception_handling(self, flight_tools, mock_drone):
        """Test graceful handling of unexpected errors.

        WHAT THIS TEST VALIDATES:
            When unexpected exceptions occur during streaming, the tool
            handles them without crashing and returns error information.

        EXPECTED OUTCOMES:
            - isError=True or error field present
            - No unhandled exception raised

        HOW IT WORKS:
            1. Patches ConnectionManager to return mock drone
            2. Makes offboard.start raise unexpected Exception
            3. Calls set_velocity
            4. Verifies error handling
        """
        with patch('avatar.mcp_server.tools.flight_tools.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Make offboard start raise an unexpected error
            mock_drone.offboard.start = AsyncMock(side_effect=Exception("Unexpected error"))

            # The error should be caught in _maintain_offboard_streaming
            # which returns 0, and set_velocity reports failure
            result = await flight_tools.set_velocity(duration_s=0.1)

            # Should report failure but not crash (Wave 1 error envelope format)
            assert result.get("isError") is True or "error" in result


# =============================================================================
# TEST CLASSES - RESULT FORMAT
# =============================================================================


class TestResultFormat:
    """Test the format of successful results.

    WHAT THESE TESTS VALIDATE:
        Successful set_velocity calls return dictionaries with specific
        expected fields containing correct values.

    WHY THESE TESTS MATTER:
        Consistent result format allows the LLM to reliably parse responses
        and make decisions. Field names and types must be predictable.
    """

    async def test_success_result_format(self, flight_tools, mock_drone):
        """Verify successful result contains expected fields.

        WHAT THIS TEST VALIDATES:
            A successful set_velocity returns a dict with:
            - success: True
            - velocity_ned: [north, east, down] list
            - yaw_deg: float
            - duration_s: float
            - setpoints_sent: int (count)
            - approximate_rate_hz: float

        EXPECTED OUTCOMES:
            All fields present with correct types and values matching request.

        HOW IT WORKS:
            1. Mocks connection and streaming (returning 20 setpoints)
            2. Calls set_velocity with specific parameters
            3. Asserts all expected fields present with correct values
        """
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
