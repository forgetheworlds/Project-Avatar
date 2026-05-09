"""Tests for set_yaw MCP tool - Yaw angle (heading) control.

W2a-T13: Yaw Control Primitive Tests
=====================================

WHAT THESE TESTS VALIDATE:
    These tests verify the set_yaw() MCP tool which commands the drone
    to rotate to a specific heading (yaw angle). Key capabilities tested:
    - Input schema validation (yaw angle bounds, yaw rate limits)
    - State preconditions (requires flying state)
    - Absolute vs relative yaw modes
    - Yaw normalization to [-180, 180] range
    - Error handling for connection failures

WHY THESE TESTS MATTER:
    Yaw control is fundamental for orienting the drone in a specific direction.
    When an LLM commands "face East" or "turn 45 degrees right", the set_yaw
    tool executes that command. Without proper yaw control:
    - The drone cannot point camera at targets
    - Coordinated turns during flight would fail
    - Orbit operations would lose target lock
    - Cinematic shots would be misaligned

YAW COORDINATE FRAME (NED):
    - 0 deg = North (heading north)
    - 90 deg = East (heading east)
    - 180 deg = South (heading south)
    - -90 deg = West (heading west)

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific yaw control behaviors:
    - Input bounds: Yaw angles must be in [-180, 180] range
    - Yaw rate limits: Rate must be in (0, 90] deg/s range
    - State preconditions: Command rejected in DISARMED, LANDING, EMERGENCY states
    - Absolute mode: yaw_deg interpreted as heading relative to North
    - Relative mode: yaw_deg added to current heading
    - Normalization: Results always normalized to [-180, 180] range

Coverage:
- Input schema validation
- State preconditions
- Absolute vs relative mode
- Yaw normalization
- Error handling
"""

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools.primitives import (
    SetYawInput,
    set_yaw,
    set_state_machine,
    get_state_machine,
    _normalize_yaw,
)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_state_machine():
    """Create a FlightStateMachine in HOVERING state.

    This is the primary entry point for yaw control commands.
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
    """Create a fully mocked MAVSDK drone with telemetry support.

    Mocks telemetry and action plugins needed for yaw control.
    """
    drone = MagicMock()

    # Mock action plugin for goto_location (used for yaw)
    drone.action = MagicMock()
    drone.action.goto_location = AsyncMock()

    # Mock telemetry for position and yaw
    drone.telemetry = MagicMock()

    # Mock attitude_euler for current yaw
    # The code calls drone.telemetry.attitude_euler() which returns an async iterator
    attitude_mock = MagicMock()
    attitude_mock.yaw_deg = 0.0
    attitude_iterator = MagicMock()
    attitude_iterator.__aiter__ = lambda self: self
    attitude_iterator.__anext__ = AsyncMock(return_value=attitude_mock)
    drone.telemetry.attitude_euler.return_value = attitude_iterator

    # Mock position for current position
    # The code calls drone.telemetry.position() which returns an async iterator
    position_mock = MagicMock()
    position_mock.latitude_deg = 37.7749
    position_mock.longitude_deg = -122.4194
    position_mock.absolute_altitude_m = 50.0
    position_iterator = MagicMock()
    position_iterator.__aiter__ = lambda self: self
    position_iterator.__anext__ = AsyncMock(return_value=position_mock)
    drone.telemetry.position.return_value = position_iterator

    return drone


# =============================================================================
# TEST CLASSES - INPUT SCHEMA VALIDATION
# =============================================================================


class TestInputSchema:
    """Test SetYawInput schema validation.

    Validates that yaw angle bounds and rate limits are enforced.
    """

    def test_valid_input(self):
        """Test that valid inputs pass schema validation."""
        input_data = SetYawInput(
            yaw_deg=90.0,
            yaw_rate_deg_s=20.0,
            absolute=True
        )
        assert input_data.yaw_deg == 90.0
        assert input_data.yaw_rate_deg_s == 20.0
        assert input_data.absolute is True

    def test_valid_negative_yaw(self):
        """Test that negative yaw angles are valid."""
        input_data = SetYawInput(
            yaw_deg=-90.0,
            yaw_rate_deg_s=30.0,
            absolute=True
        )
        assert input_data.yaw_deg == -90.0

    def test_yaw_bounds_at_limits(self):
        """Test that yaw at boundary values is valid."""
        # Min boundary
        input_min = SetYawInput(yaw_deg=-180.0)
        assert input_min.yaw_deg == -180.0

        # Max boundary
        input_max = SetYawInput(yaw_deg=180.0)
        assert input_max.yaw_deg == 180.0

    def test_yaw_rate_bounds(self):
        """Test that yaw rate at boundary values is valid."""
        # Min boundary (must be > 0)
        input_min = SetYawInput(yaw_deg=0.0, yaw_rate_deg_s=0.1)
        assert input_min.yaw_rate_deg_s == 0.1

        # Max boundary
        input_max = SetYawInput(yaw_deg=0.0, yaw_rate_deg_s=90.0)
        assert input_max.yaw_rate_deg_s == 90.0

    def test_default_values(self):
        """Test that default values are applied correctly."""
        input_data = SetYawInput(yaw_deg=0.0)
        assert input_data.yaw_rate_deg_s == 20.0  # Default rate
        assert input_data.absolute is True  # Default mode

    def test_relative_mode(self):
        """Test that relative mode can be set."""
        input_data = SetYawInput(
            yaw_deg=45.0,
            absolute=False
        )
        assert input_data.absolute is False


class TestInputSchemaRejection:
    """Test that invalid inputs are rejected by schema validation."""

    def test_yaw_below_minimum(self):
        """Test that yaw below -180 is rejected."""
        with pytest.raises(Exception):
            SetYawInput(yaw_deg=-181.0)

    def test_yaw_above_maximum(self):
        """Test that yaw above 180 is rejected."""
        with pytest.raises(Exception):
            SetYawInput(yaw_deg=181.0)

    def test_yaw_rate_below_minimum(self):
        """Test that yaw rate <= 0 is rejected."""
        with pytest.raises(Exception):
            SetYawInput(yaw_deg=0.0, yaw_rate_deg_s=0.0)

    def test_yaw_rate_above_maximum(self):
        """Test that yaw rate above 90 is rejected."""
        with pytest.raises(Exception):
            SetYawInput(yaw_deg=0.0, yaw_rate_deg_s=91.0)


# =============================================================================
# TEST CLASSES - YAW NORMALIZATION
# =============================================================================


class TestYawNormalization:
    """Test yaw angle normalization to [-180, 180] range."""

    def test_already_normalized(self):
        """Test that already normalized angles are unchanged."""
        assert _normalize_yaw(0.0) == 0.0
        assert _normalize_yaw(90.0) == 90.0
        assert _normalize_yaw(-90.0) == -90.0
        assert _normalize_yaw(180.0) == 180.0
        assert _normalize_yaw(-180.0) == -180.0

    def test_positive_overflow(self):
        """Test normalization of angles > 180."""
        assert _normalize_yaw(270.0) == -90.0  # 270 -> -90
        assert _normalize_yaw(360.0) == 0.0    # 360 -> 0
        assert _normalize_yaw(450.0) == 90.0   # 450 -> 90
        assert _normalize_yaw(540.0) == 180.0  # 540 -> 180

    def test_negative_overflow(self):
        """Test normalization of angles < -180."""
        assert _normalize_yaw(-270.0) == 90.0   # -270 -> 90
        assert _normalize_yaw(-360.0) == 0.0    # -360 -> 0
        assert _normalize_yaw(-450.0) == -90.0  # -450 -> -90

    def test_large_values(self):
        """Test normalization of very large angles."""
        assert _normalize_yaw(720.0) == 0.0     # 2 full rotations
        assert _normalize_yaw(1080.0) == 0.0    # 3 full rotations
        assert _normalize_yaw(-720.0) == 0.0


# =============================================================================
# TEST CLASSES - STATE PRECONDITIONS
# =============================================================================


class TestStatePreconditions:
    """Test state machine integration for yaw control.

    WHAT THESE TESTS VALIDATE:
        - set_yaw works in valid flying states (HOVERING, FLYING, etc.)
        - set_yaw rejected in invalid states (DISARMED, LANDING, etc.)
        - Clear error messages indicate why state is invalid
    """

    @pytest.mark.asyncio
    async def test_valid_states(self):
        """Test that set_yaw works in valid flying states."""
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

            set_state_machine(sm)

            with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
                mock_drone = MagicMock()
                mock_drone.action.goto_location = AsyncMock()

                # Mock telemetry
                mock_drone.telemetry.attitude_euler = MagicMock()
                mock_drone.telemetry.attitude_euler.__aiter__ = lambda self: self
                mock_drone.telemetry.attitude_euler.return_value.__anext__ = AsyncMock(
                    return_value=MagicMock(yaw_deg=0.0)
                )
                mock_drone.telemetry.position = MagicMock()
                mock_drone.telemetry.position.__aiter__ = lambda self: self
                mock_drone.telemetry.position.__anext__ = AsyncMock(
                    return_value=MagicMock(
                        latitude_deg=37.0,
                        longitude_deg=-122.0,
                        absolute_altitude_m=50.0
                    )
                )

                mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

                result = await set_yaw(yaw_deg=90.0)
                data = json.loads(result)

                # Should NOT fail due to state check
                assert "Cannot set_yaw in state" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_invalid_states(self):
        """Test that set_yaw fails in non-flying states."""
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
                    sm.transition(FlightState.ERROR, "error", "system")
                    sm._state = state

            set_state_machine(sm)

            result = await set_yaw(yaw_deg=90.0)
            data = json.loads(result)

            # Wave 1 error envelope format
            assert data.get("isError") is True
            assert "Cannot set_yaw in state" in data.get("error", {}).get("message", "")


# =============================================================================
# TEST CLASSES - ABSOLUTE VS RELATIVE MODE
# =============================================================================


class TestYawModes:
    """Test absolute vs relative yaw modes."""

    @pytest.mark.asyncio
    async def test_absolute_mode(self, mock_state_machine, mock_drone):
        """Test that absolute mode interprets yaw as heading from North."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock current yaw as 45 degrees (NE)
            attitude_mock = MagicMock(yaw_deg=45.0)
            mock_drone.telemetry.attitude_euler.return_value.__anext__ = AsyncMock(return_value=attitude_mock)

            result = await set_yaw(yaw_deg=90.0, absolute=True)
            data = json.loads(result)

            assert data["success"] is True
            assert data["yaw_deg"] == 90.0  # Absolute heading East
            assert data["mode"] == "absolute"
            assert data["previous_yaw_deg"] == 45.0

    @pytest.mark.asyncio
    async def test_relative_mode_positive(self, mock_state_machine, mock_drone):
        """Test that relative mode adds offset to current heading."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock current yaw as 45 degrees (NE)
            attitude_mock = MagicMock(yaw_deg=45.0)
            mock_drone.telemetry.attitude_euler.return_value.__anext__ = AsyncMock(return_value=attitude_mock)

            result = await set_yaw(yaw_deg=30.0, absolute=False)
            data = json.loads(result)

            assert data["success"] is True
            assert data["yaw_deg"] == 75.0  # 45 + 30 = 75
            assert data["mode"] == "relative"

    @pytest.mark.asyncio
    async def test_relative_mode_negative(self, mock_state_machine, mock_drone):
        """Test that relative mode with negative offset subtracts from heading."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock current yaw as 45 degrees
            attitude_mock = MagicMock(yaw_deg=45.0)
            mock_drone.telemetry.attitude_euler.return_value.__anext__ = AsyncMock(return_value=attitude_mock)

            result = await set_yaw(yaw_deg=-60.0, absolute=False)
            data = json.loads(result)

            assert data["success"] is True
            assert data["yaw_deg"] == -15.0  # 45 - 60 = -15
            assert data["mode"] == "relative"

    @pytest.mark.asyncio
    async def test_relative_mode_with_normalization(self, mock_state_machine, mock_drone):
        """Test that relative mode results are normalized."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            # Mock current yaw as 150 degrees
            attitude_mock = MagicMock(yaw_deg=150.0)
            mock_drone.telemetry.attitude_euler.return_value.__anext__ = AsyncMock(return_value=attitude_mock)

            # Add 90 degrees: 150 + 90 = 240 -> should normalize to -120
            result = await set_yaw(yaw_deg=90.0, absolute=False)
            data = json.loads(result)

            assert data["success"] is True
            # 150 + 90 = 240, normalized to -120
            assert data["yaw_deg"] == -120.0


# =============================================================================
# TEST CLASSES - ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in set_yaw.

    WHAT THESE TESTS VALIDATE:
        The set_yaw tool handles error conditions gracefully:
        - Connection errors (drone not reachable)
        - Missing telemetry data
        Returns informative error messages rather than crashing.
    """

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_state_machine):
        """Test graceful handling of connection errors."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(
                side_effect=ConnectionError("Not connected")
            )

            result = await set_yaw(yaw_deg=90.0)
            data = json.loads(result)

            # Wave 1 error envelope format
            assert data.get("isError") is True
            assert "Not connected" in data.get("error", {}).get("message", "")

    @pytest.mark.asyncio
    async def test_null_drone_handling(self, mock_state_machine):
        """Test graceful handling when drone is None."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=None)

            result = await set_yaw(yaw_deg=90.0)
            data = json.loads(result)

            # Wave 1 error envelope format
            assert data.get("isError") is True
            assert "Drone not connected" in data.get("error", {}).get("message", "")


# =============================================================================
# TEST CLASSES - RESULT FORMAT
# =============================================================================


class TestResultFormat:
    """Test the format of successful results.

    WHAT THESE TESTS VALIDATE:
        Successful set_yaw calls return JSON strings with specific
        expected fields containing correct values.
    """

    @pytest.mark.asyncio
    async def test_success_result_format(self, mock_state_machine, mock_drone):
        """Verify successful result contains expected fields."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            result = await set_yaw(
                yaw_deg=90.0,
                yaw_rate_deg_s=30.0,
                absolute=True
            )
            data = json.loads(result)

            assert data["success"] is True
            assert "message" in data
            assert "yaw_deg" in data
            assert data["yaw_deg"] == 90.0
            assert "yaw_rate_deg_s" in data
            assert data["yaw_rate_deg_s"] == 30.0
            assert "mode" in data
            assert data["mode"] == "absolute"
            assert "previous_yaw_deg" in data

    @pytest.mark.asyncio
    async def test_json_string_output(self, mock_state_machine, mock_drone):
        """Verify that output is a valid JSON string."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            result = await set_yaw(yaw_deg=45.0)

            # Should be a string
            assert isinstance(result, str)

            # Should be valid JSON
            try:
                data = json.loads(result)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                pytest.fail("Result should be valid JSON string")


# =============================================================================
# TEST CLASSES - WRAPPER FUNCTION
# =============================================================================


class TestWrapperFunction:
    """Test the MCP wrapper function.

    WHAT THESE TESTS VALIDATE:
        The set_yaw() function exposed to MCP returns properly formatted
        JSON strings that can be parsed by the agent. Default parameters work.
    """

    @pytest.mark.asyncio
    async def test_set_yaw_wrapper_returns_json(self, mock_state_machine, mock_drone):
        """Verify wrapper returns JSON string."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            result = await set_yaw(yaw_deg=90.0)

            # Should be a string
            try:
                parsed = json.loads(result)
                assert isinstance(parsed, dict)
            except json.JSONDecodeError:
                pytest.fail("Wrapper should return valid JSON string")

    @pytest.mark.asyncio
    async def test_set_yaw_wrapper_default_params(self, mock_state_machine, mock_drone):
        """Verify wrapper works with default parameters."""
        set_state_machine(mock_state_machine)

        with patch('avatar.mcp_server.tools.primitives.ConnectionManager') as mock_cm:
            mock_cm.return_value.ensure_connected = AsyncMock(return_value=mock_drone)

            result = await set_yaw(yaw_deg=0.0)

            try:
                parsed = json.loads(result)
                # Should either succeed or fail gracefully
                assert "success" in parsed or "isError" in parsed
            except json.JSONDecodeError:
                pytest.fail("Wrapper should return valid JSON string")
