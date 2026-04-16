"""Test suite for AsyncGuardian failsafe actions (D2.8).

Tests cover:
- initiate_rtl calls drone.action.return_to_launch()
- initiate_land calls drone.action.land()
- initiate_hold calls drone.action.hold()
- initiate_emergency_stop calls drone.action.kill() or terminate()

SAFETY CRITICAL: The failsafe actions must actually command the drone to
perform the safety maneuver. Without these calls, the state machine would
transition but the drone would not take any physical action.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.connection_manager import ConnectionHealth, ConnectionManager
from avatar.mav.guardian_async import (
    AsyncGuardian,
    GuardianConfig,
    SafetyAction,
)
from avatar.mav.heartbeat_service import HeartbeatService
from avatar.mav.state_machine import FlightState, FlightStateMachine


@pytest.fixture
def mock_drone():
    """Create a mock drone with action methods.

    MOCK SETUP:
    - MagicMock with action attribute
    - action.return_to_launch is AsyncMock
    - action.land is AsyncMock
    - action.hold is AsyncMock
    - action.kill is AsyncMock
    - action.terminate is AsyncMock

    SAFETY REASON: Mock allows verifying action calls without real drone.
    """
    drone = MagicMock()
    drone.action = MagicMock()
    drone.action.return_to_launch = AsyncMock()
    drone.action.land = AsyncMock()
    drone.action.hold = AsyncMock()
    drone.action.kill = AsyncMock()
    drone.action.terminate = AsyncMock()
    return drone


@pytest.fixture
def connection_manager(mock_drone):
    """Create a mock connection manager that returns mock drone."""
    cm = MagicMock(spec=ConnectionManager)
    cm.health = ConnectionHealth(
        is_healthy=True,
        last_heartbeat=time.time(),
        gps_lock=True,
        home_position_set=True,
    )
    cm.get_drone = AsyncMock(return_value=mock_drone)
    return cm


@pytest.fixture
def heartbeat_service():
    """Create a heartbeat service."""
    return HeartbeatService()


@pytest.fixture
def state_machine():
    """Create a state machine in POSITION_CONTROL state for failsafe tests.

    Note: offboard_timeout failsafe only applies when in POSITION_CONTROL,
    VELOCITY_CONTROL, or MISSION_EXECUTION states (offboard control modes).
    """
    sm = FlightStateMachine()
    sm.transition(FlightState.DISARMED, "startup", "test")
    sm.transition(FlightState.ARMED, "arm", "test")
    sm.transition(FlightState.TAKING_OFF, "takeoff", "test")
    sm.transition(FlightState.HOVERING, "hover", "test")
    sm.transition(FlightState.POSITION_CONTROL, "position_control", "test")
    return sm


@pytest.fixture
def guardian(connection_manager, heartbeat_service, state_machine):
    """Create an AsyncGuardian instance for testing."""
    return AsyncGuardian(
        connection_manager=connection_manager,
        heartbeat_service=heartbeat_service,
        state_machine=state_machine,
    )


class TestInitiateRtl:
    """Tests for initiate_rtl failsafe action."""

    @pytest.mark.asyncio
    async def test_initiate_rtl_calls_drone_action_return_to_launch(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_rtl must call drone.action.return_to_launch()."""
        result = await guardian.initiate_rtl("test_rtl_reason")

        assert result is True
        mock_drone.action.return_to_launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initiate_rtl_handles_drone_unavailable(
        self, guardian, connection_manager
    ):
        """D2.8: initiate_rtl should handle drone=None gracefully."""
        connection_manager.get_drone = AsyncMock(return_value=None)

        result = await guardian.initiate_rtl("test_rtl_reason")

        assert result is True  # State machine transition still succeeds

    @pytest.mark.asyncio
    async def test_initiate_rtl_handles_action_exception(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_rtl should handle action exceptions gracefully."""
        mock_drone.action.return_to_launch.side_effect = Exception("Action failed")

        result = await guardian.initiate_rtl("test_rtl_reason")

        assert result is True  # State machine transition still succeeds
        # Alert should still be recorded
        status = guardian.get_status()
        assert len(status.alerts) == 1
        assert "RTL" in status.alerts[0].message


class TestInitiateLand:
    """Tests for initiate_land failsafe action."""

    @pytest.mark.asyncio
    async def test_initiate_land_calls_drone_action_land(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_land must call drone.action.land()."""
        result = await guardian.initiate_land("test_land_reason")

        assert result is True
        mock_drone.action.land.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initiate_land_handles_drone_unavailable(
        self, guardian, connection_manager
    ):
        """D2.8: initiate_land should handle drone=None gracefully."""
        connection_manager.get_drone = AsyncMock(return_value=None)

        result = await guardian.initiate_land("test_land_reason")

        assert result is True

    @pytest.mark.asyncio
    async def test_initiate_land_handles_action_exception(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_land should handle action exceptions gracefully."""
        mock_drone.action.land.side_effect = Exception("Action failed")

        result = await guardian.initiate_land("test_land_reason")

        assert result is True
        status = guardian.get_status()
        assert len(status.alerts) == 1
        assert "Land" in status.alerts[0].message


class TestInitiateHold:
    """Tests for initiate_hold failsafe action."""

    @pytest.mark.asyncio
    async def test_initiate_hold_calls_drone_action_hold(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_hold must call drone.action.hold()."""
        result = await guardian.initiate_hold("test_hold_reason")

        assert result is True
        mock_drone.action.hold.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initiate_hold_handles_drone_unavailable(
        self, guardian, connection_manager
    ):
        """D2.8: initiate_hold should handle drone=None gracefully."""
        connection_manager.get_drone = AsyncMock(return_value=None)

        result = await guardian.initiate_hold("test_hold_reason")

        assert result is True

    @pytest.mark.asyncio
    async def test_initiate_hold_handles_action_exception(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_hold should handle action exceptions gracefully."""
        mock_drone.action.hold.side_effect = Exception("Action failed")

        result = await guardian.initiate_hold("test_hold_reason")

        assert result is True
        status = guardian.get_status()
        assert len(status.alerts) == 1
        assert "Hold" in status.alerts[0].message


class TestInitiateEmergencyStop:
    """Tests for initiate_emergency_stop failsafe action."""

    @pytest.mark.asyncio
    async def test_initiate_emergency_stop_calls_drone_action_kill(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_emergency_stop must call drone.action.kill()."""
        result = await guardian.initiate_emergency_stop("test_emergency_reason")

        assert result is True
        mock_drone.action.kill.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initiate_emergency_stop_falls_back_to_terminate(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_emergency_stop should fall back to terminate if kill fails."""
        mock_drone.action.kill.side_effect = Exception("Kill not supported")

        result = await guardian.initiate_emergency_stop("test_emergency_reason")

        assert result is True
        mock_drone.action.kill.assert_awaited_once()
        mock_drone.action.terminate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initiate_emergency_stop_handles_drone_unavailable(
        self, guardian, connection_manager
    ):
        """D2.8: initiate_emergency_stop should handle drone=None gracefully."""
        connection_manager.get_drone = AsyncMock(return_value=None)

        result = await guardian.initiate_emergency_stop("test_emergency_reason")

        assert result is True

    @pytest.mark.asyncio
    async def test_initiate_emergency_stop_handles_both_kill_and_terminate_failure(
        self, guardian, mock_drone
    ):
        """D2.8: initiate_emergency_stop should handle all action failures gracefully."""
        mock_drone.action.kill.side_effect = Exception("Kill failed")
        mock_drone.action.terminate.side_effect = Exception("Terminate failed")

        result = await guardian.initiate_emergency_stop("test_emergency_reason")

        assert result is True
        # Alert should still be recorded despite action failure
        status = guardian.get_status()
        assert len(status.alerts) == 1
        assert "EMERGENCY STOP" in status.alerts[0].message


class TestFailsafeCallback:
    """Tests for failsafe callback integration."""

    @pytest.mark.asyncio
    async def test_failsafe_callback_called_on_rtl(self, guardian, mock_drone):
        """Verify on_failsafe callback is called for RTL."""
        callback_called = []
        callback_action = []
        callback_reason = []

        async def on_failsafe(action, reason):
            callback_called.append(True)
            callback_action.append(action)
            callback_reason.append(reason)

        guardian.on_failsafe = on_failsafe

        await guardian.initiate_rtl("callback_test")

        assert len(callback_called) == 1
        assert callback_action[0] == SafetyAction.RTL
        assert callback_reason[0] == "callback_test"

    @pytest.mark.asyncio
    async def test_failsafe_callback_error_does_not_prevent_action(
        self, guardian, mock_drone
    ):
        """Verify callback errors don't prevent drone action."""
        async def failing_callback(action, reason):
            raise Exception("Callback failed")

        guardian.on_failsafe = failing_callback

        result = await guardian.initiate_hold("test")

        assert result is True
        mock_drone.action.hold.assert_awaited_once()
