"""Tests for the disarm primitive tool.

W2a-T02: Disarm Primitive Tests
=================================
Tests for the disarm MCP tool that disarms the drone motors.

Test Categories:
    1. Basic disarm functionality
    2. State precondition validation
    3. Force disarm in air (requires confirmation)
    4. Guardian preflight integration
    5. Error handling
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools import primitives as prim


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_drone():
    """Create a mock drone with async action methods."""
    drone = MagicMock()
    drone.action.disarm = AsyncMock()
    drone.action.kill = AsyncMock()
    return drone


@pytest.fixture
def mock_connection_manager(mock_drone):
    """Create a mock connection manager."""
    cm = MagicMock()
    cm.ensure_connected = AsyncMock(return_value=mock_drone)
    return cm


@pytest.fixture
def mock_guardian():
    """Create a mock guardian with preflight method."""
    guardian = MagicMock()
    guardian.preflight = AsyncMock(return_value=None)  # None = allowed
    return guardian


@pytest.fixture
def mock_confirmation():
    """Create a mock confirmation manager."""
    confirmation = MagicMock()
    confirmation.require = AsyncMock(return_value=MagicMock(token="test-token"))
    confirmation.get_pending = MagicMock(return_value={"approved": True})
    confirmation.clear_pending = MagicMock()
    return confirmation


@pytest.fixture
def state_machine_armed():
    """Create a state machine in ARMED state."""
    sm = FlightStateMachine()
    sm.transition(FlightState.DISARMED, "startup", "test")
    sm.transition(FlightState.ARMED, "arm", "test")
    return sm


@pytest.fixture
def state_machine_flying():
    """Create a state machine in FLYING state (in air)."""
    sm = FlightStateMachine()
    sm.transition(FlightState.DISARMED, "startup", "test")
    sm.transition(FlightState.ARMED, "arm", "test")
    sm.transition(FlightState.TAKING_OFF, "takeoff", "test")
    sm.transition(FlightState.HOVERING, "hover", "test")
    sm.transition(FlightState.FLYING, "flying", "test")
    return sm


@pytest.fixture
def state_machine_disarmed():
    """Create a state machine in DISARMED state."""
    sm = FlightStateMachine()
    sm.transition(FlightState.DISARMED, "startup", "test")
    return sm


@pytest.fixture
def mock_session():
    """Create a mock session with auto_confirm=False."""
    return MagicMock(auto_confirm=False)


@pytest.fixture
def setup_tool_context(
    mock_connection_manager, mock_guardian, mock_confirmation, mock_session
):
    """Set up the tool context with all dependencies."""
    prim.set_connection_manager_global(mock_connection_manager)
    prim.set_guardian(mock_guardian)
    prim.set_confirmation(mock_confirmation)

    # Mock _get_session to return our mock session
    with patch.object(prim, '_get_session', return_value=mock_session):
        yield mock_connection_manager, mock_guardian, mock_confirmation, mock_session


# =============================================================================
# TEST: BASIC DISARM
# =============================================================================


class TestBasicDisarm:
    """Tests for basic disarm functionality."""

    @pytest.mark.asyncio
    async def test_disarm_from_armed_state(
        self, setup_tool_context, state_machine_armed, mock_drone
    ):
        """Test disarming from ARMED state."""
        prim.set_state_machine(state_machine_armed)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out["armed"] is False
        assert "timestamp" in out
        mock_drone.action.disarm.assert_awaited()

    @pytest.mark.asyncio
    async def test_disarm_from_landed_state(
        self, setup_tool_context, mock_drone
    ):
        """Test disarming from LANDED state."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "test")
        sm.transition(FlightState.ARMED, "arm", "test")
        sm.transition(FlightState.TAKING_OFF, "takeoff", "test")
        sm.transition(FlightState.HOVERING, "hover", "test")
        sm.transition(FlightState.LANDING, "land", "test")
        sm.transition(FlightState.LANDED, "landed", "test")
        prim.set_state_machine(sm)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out["armed"] is False
        mock_drone.action.disarm.assert_awaited()

    @pytest.mark.asyncio
    async def test_disarm_already_disarmed(
        self, setup_tool_context, state_machine_disarmed, mock_drone
    ):
        """Test that disarming when already disarmed returns success."""
        prim.set_state_machine(state_machine_disarmed)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out["armed"] is False
        # disarm should NOT be called if already disarmed
        mock_drone.action.disarm.assert_not_awaited()


# =============================================================================
# TEST: STATE PRECONDITIONS
# =============================================================================


class TestStatePreconditions:
    """Tests for state precondition validation."""

    @pytest.mark.asyncio
    async def test_disarm_from_flying_state_rejected(
        self, setup_tool_context, state_machine_flying, mock_drone
    ):
        """Test that disarm from flying state is rejected without force."""
        prim.set_state_machine(state_machine_flying)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out.get("isError") is True
        assert "PREFLIGHT_BLOCKED" in out.get("error", {}).get("code", "")
        mock_drone.action.disarm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disarm_from_hovering_state_rejected(
        self, setup_tool_context, mock_drone
    ):
        """Test that disarm from hovering state is rejected without force."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "test")
        sm.transition(FlightState.ARMED, "arm", "test")
        sm.transition(FlightState.TAKING_OFF, "takeoff", "test")
        sm.transition(FlightState.HOVERING, "hover", "test")
        prim.set_state_machine(sm)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out.get("isError") is True
        assert "PREFLIGHT_BLOCKED" in out.get("error", {}).get("code", "")


# =============================================================================
# TEST: FORCE DISARM IN AIR
# =============================================================================


class TestForceDisarmInAir:
    """Tests for force disarm while in air (curated confirmation #6)."""

    @pytest.mark.asyncio
    async def test_force_disarm_in_air_requires_confirmation(
        self, setup_tool_context, state_machine_flying, mock_confirmation, mock_drone
    ):
        """Test that force disarm in air requires confirmation."""
        prim.set_state_machine(state_machine_flying)

        raw = await prim.handle_disarm({"force": True})
        out = json.loads(raw) if isinstance(raw, str) else raw

        # Confirmation should be required
        mock_confirmation.require.assert_awaited_once()
        assert mock_confirmation.require.call_args[1]["action"] == "force_disarm_in_air"
        assert mock_confirmation.require.call_args[1]["destructive"] is True

    @pytest.mark.asyncio
    async def test_force_disarm_in_air_confirmed(
        self,
        setup_tool_context,
        state_machine_flying,
        mock_confirmation,
        mock_drone,
        mock_session,
    ):
        """Test that force disarm proceeds after confirmation."""
        prim.set_state_machine(state_machine_flying)
        mock_confirmation.get_pending.return_value = {"approved": True}

        raw = await prim.handle_disarm({"force": True})
        out = json.loads(raw) if isinstance(raw, str) else raw

        # Should have called confirmation
        mock_confirmation.require.assert_awaited_once()
        # Should have called kill (force disarm)
        mock_drone.action.kill.assert_awaited()
        assert out["armed"] is False

    @pytest.mark.asyncio
    async def test_force_disarm_in_air_rejected(
        self,
        setup_tool_context,
        state_machine_flying,
        mock_confirmation,
        mock_drone,
    ):
        """Test that force disarm is rejected if confirmation denied."""
        prim.set_state_machine(state_machine_flying)
        mock_confirmation.get_pending.return_value = {"approved": False}

        raw = await prim.handle_disarm({"force": True})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out.get("isError") is True
        assert "CONFIRMATION_REQUIRED" in out.get("error", {}).get("code", "")
        mock_drone.action.kill.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_force_disarm_auto_confirm(
        self,
        mock_connection_manager,
        mock_guardian,
        mock_confirmation,
        state_machine_flying,
        mock_drone,
    ):
        """Test that auto_confirm bypasses confirmation."""
        prim.set_connection_manager_global(mock_connection_manager)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_flying)

        # Mock session with auto_confirm=True
        auto_confirm_session = MagicMock(auto_confirm=True)

        with patch.object(prim, '_get_session', return_value=auto_confirm_session):
            raw = await prim.handle_disarm({"force": True})
            out = json.loads(raw) if isinstance(raw, str) else raw

            # Should NOT have called confirmation (auto_confirm=True)
            mock_confirmation.require.assert_not_awaited()
            # Should have disarmed
            mock_drone.action.kill.assert_awaited()
            assert out["armed"] is False


# =============================================================================
# TEST: GUARDIAN INTEGRATION
# =============================================================================


class TestGuardianIntegration:
    """Tests for guardian preflight integration."""

    @pytest.mark.asyncio
    async def test_guardian_preflight_called(
        self, mock_connection_manager, mock_guardian, mock_confirmation, state_machine_armed, mock_drone
    ):
        """Test that guardian.preflight is called."""
        prim.set_connection_manager_global(mock_connection_manager)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_armed)

        with patch.object(prim, '_get_session', return_value=MagicMock(auto_confirm=False)):
            await prim.handle_disarm({"force": False})

        mock_guardian.preflight.assert_awaited_once()
        call_args = mock_guardian.preflight.call_args
        assert call_args[1]["tool"] == "disarm"
        assert "force" in call_args[1]["payload"]

    @pytest.mark.asyncio
    async def test_guardian_blocks_disarm(
        self, mock_connection_manager, mock_guardian, mock_confirmation, state_machine_armed, mock_drone
    ):
        """Test that disarm is blocked if guardian.preflight returns error."""
        mock_guardian.preflight = AsyncMock(
            return_value={"isError": True, "error": {"code": "GUARDIAN_VIOLATION"}}
        )
        prim.set_connection_manager_global(mock_connection_manager)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_armed)

        with patch.object(prim, '_get_session', return_value=MagicMock(auto_confirm=False)):
            raw = await prim.handle_disarm({"force": False})
            out = json.loads(raw) if isinstance(raw, str) else raw

            assert out.get("isError") is True
            mock_drone.action.disarm.assert_not_awaited()


# =============================================================================
# TEST: STATE MACHINE UPDATE
# =============================================================================


class TestStateMachineUpdate:
    """Tests for state machine updates after disarm."""

    @pytest.mark.asyncio
    async def test_state_transitions_to_disarmed(
        self, setup_tool_context, state_machine_armed, mock_drone
    ):
        """Test that state machine transitions to DISARMED after disarm."""
        prim.set_state_machine(state_machine_armed)

        await prim.handle_disarm({"force": False})

        assert state_machine_armed.current_state == FlightState.DISARMED

    @pytest.mark.asyncio
    async def test_force_disarm_transitions_to_disarmed(
        self,
        mock_connection_manager,
        mock_guardian,
        mock_confirmation,
        state_machine_flying,
        mock_drone,
    ):
        """Test that state transitions to DISARMED even with force disarm."""
        prim.set_connection_manager_global(mock_connection_manager)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_flying)
        mock_confirmation.get_pending.return_value = {"approved": True}

        with patch.object(prim, '_get_session', return_value=MagicMock(auto_confirm=False)):
            await prim.handle_disarm({"force": True})

            # Force disarm in air triggers kill_switch failsafe (EMERGENCY state)
            assert state_machine_flying.current_state == FlightState.EMERGENCY


# =============================================================================
# TEST: INPUT VALIDATION
# =============================================================================


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_invalid_force_parameter(self, setup_tool_context):
        """Test that invalid force parameter returns error."""
        raw = await prim.handle_disarm({"force": "not-a-boolean"})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out.get("isError") is True
        assert "SCHEMA_VALIDATION_FAILED" in out.get("error", {}).get("code", "")

    @pytest.mark.asyncio
    async def test_missing_force_uses_default(self, setup_tool_context, state_machine_armed, mock_drone):
        """Test that missing force parameter defaults to False."""
        prim.set_state_machine(state_machine_armed)

        raw = await prim.handle_disarm({})
        out = json.loads(raw) if isinstance(raw, str) else raw

        assert out["armed"] is False
        mock_drone.action.disarm.assert_awaited()


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_disarm_not_connected(
        self, mock_guardian, mock_confirmation, state_machine_armed
    ):
        """Test that disarm fails gracefully when not connected."""
        # Create a connection manager that returns None
        cm = MagicMock()
        cm.ensure_connected = AsyncMock(return_value=None)
        prim.set_connection_manager_global(cm)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_armed)

        with patch.object(prim, '_get_session', return_value=MagicMock(auto_confirm=False)):
            raw = await prim.handle_disarm({"force": False})
            out = json.loads(raw) if isinstance(raw, str) else raw

            assert out.get("isError") is True
            assert "MAV_NOT_CONNECTED" in out.get("error", {}).get("code", "")

    @pytest.mark.asyncio
    async def test_disarm_command_rejected(
        self, mock_connection_manager, mock_guardian, mock_confirmation, state_machine_armed, mock_drone
    ):
        """Test that disarm handles MAVSDK rejection gracefully."""
        mock_drone.action.disarm = AsyncMock(side_effect=Exception("Disarm rejected"))
        prim.set_connection_manager_global(mock_connection_manager)
        prim.set_guardian(mock_guardian)
        prim.set_confirmation(mock_confirmation)
        prim.set_state_machine(state_machine_armed)

        with patch.object(prim, '_get_session', return_value=MagicMock(auto_confirm=False)):
            raw = await prim.handle_disarm({"force": False})
            out = json.loads(raw) if isinstance(raw, str) else raw

            assert out.get("isError") is True
            assert "MAV_COMMAND_REJECTED" in out.get("error", {}).get("code", "")


# =============================================================================
# TEST: OUTPUT FORMAT
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_output_is_valid_json(
        self, setup_tool_context, state_machine_armed, mock_drone
    ):
        """Test that output is valid JSON."""
        prim.set_state_machine(state_machine_armed)

        raw = await prim.handle_disarm({"force": False})

        # Should be a string
        assert isinstance(raw, str)

        # Should parse as JSON
        out = json.loads(raw)
        assert isinstance(out, dict)

    @pytest.mark.asyncio
    async def test_output_has_required_fields(
        self, setup_tool_context, state_machine_armed, mock_drone
    ):
        """Test that output has all required fields."""
        prim.set_state_machine(state_machine_armed)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw)

        assert "armed" in out
        assert "timestamp" in out
        assert isinstance(out["armed"], bool)
        assert isinstance(out["timestamp"], str)

    @pytest.mark.asyncio
    async def test_timestamp_is_iso_format(
        self, setup_tool_context, state_machine_armed, mock_drone
    ):
        """Test that timestamp is in ISO 8601 format."""
        prim.set_state_machine(state_machine_armed)

        raw = await prim.handle_disarm({"force": False})
        out = json.loads(raw)

        # Should parse as datetime
        from datetime import datetime
        dt = datetime.fromisoformat(out["timestamp"].replace("Z", "+00:00"))
        assert dt is not None
