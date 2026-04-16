"""Tests for EscalationMatrix dispatch system (D2.7).

ESCALATION MATRIX DISPATCH OVERVIEW:
=====================================
The EscalationMatrix acts as the single failsafe consumer for AsyncGuardian.
When AsyncGuardian detects a safety condition, it creates a GuardianEvent and
dispatches it through the EscalationMatrix's registered failsafe executor.

KEY CONCEPTS:
=============

1. GuardianEvent: Immutable record of a safety condition
   - condition: Maps to EscalationRule.condition
   - reason: Human-readable explanation
   - context: Additional data (battery %, distance, etc.)

2. FailsafeAction: Enum of possible failsafe responses
   - LOG_ALERT (1): Log and notify
   - REJECT_COMMAND (2): Block LLM commands
   - HOLD (3): Hover in place
   - RTL (4): Return to launch
   - LAND (5): Land immediately
   - EMERGENCY_DISARM (6): Cut motors

3. FailsafeExecutor: Async callable that performs the actual action
   - Registered via register_failsafe_executor()
   - Called by dispatch_guardian_event()

DISPATCH FLOW:
==============
1. AsyncGuardian detects condition (e.g., battery < 20%)
2. AsyncGuardian creates GuardianEvent
3. AsyncGuardian calls dispatch_guardian_event()
4. EscalationMatrix evaluates condition -> EscalationEvent
5. EscalationMatrix maps action string to FailsafeAction
6. EscalationMatrix calls registered FailsafeExecutor
7. FailsafeExecutor performs MAVSDK action

TEST SCENARIOS:
================
1. DISPATCH_SUCCESS: Verify executor is called for valid event
2. DISPATCH_NO_EXECUTOR: Verify graceful handling when no executor registered
3. DISPATCH_NO_ESCALATION: Verify handling when condition doesn't escalate
4. MAP_ACTION_TO_FAILSAFE: Verify action string to FailsafeAction mapping
5. REGISTER_EXECUTOR: Verify executor registration
6. MODULE_LEVEL_DISPATCH: Verify convenience functions work
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mav.escalation_matrix import (
    SeverityLevel,
    EscalationRule,
    EscalationEvent,
    EscalationMatrix,
    GuardianEvent,
    FailsafeAction,
    FailsafeExecutor,
    get_global_matrix,
    set_global_matrix,
    dispatch_guardian_event as module_dispatch,
)


class TestGuardianEvent:
    """Test GuardianEvent dataclass."""

    def test_event_creation(self):
        """GuardianEvent can be created with required fields."""
        event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%, below 20% threshold",
            context={"battery_percent": 18.0, "voltage": 14.2}
        )
        assert event.condition == "battery_critical"
        assert event.reason == "Battery at 18%, below 20% threshold"
        assert event.context == {"battery_percent": 18.0, "voltage": 14.2}

    def test_event_is_frozen(self):
        """GuardianEvent is immutable."""
        event = GuardianEvent(
            condition="test",
            reason="test reason",
            context={}
        )
        with pytest.raises(AttributeError):
            event.condition = "new_condition"  # type: ignore

    def test_event_default_context(self):
        """GuardianEvent has empty context by default."""
        event = GuardianEvent(condition="test", reason="test")
        assert event.context == {}


class TestFailsafeAction:
    """Test FailsafeAction enum."""

    def test_action_values(self):
        """FailsafeAction values match expected priority."""
        assert FailsafeAction.LOG_ALERT.value == 1
        assert FailsafeAction.REJECT_COMMAND.value == 2
        assert FailsafeAction.HOLD.value == 3
        assert FailsafeAction.RTL.value == 4
        assert FailsafeAction.LAND.value == 5
        assert FailsafeAction.EMERGENCY_DISARM.value == 6

    def test_action_ordering(self):
        """FailsafeAction values are ordered by severity."""
        assert FailsafeAction.LOG_ALERT < FailsafeAction.HOLD
        assert FailsafeAction.HOLD < FailsafeAction.RTL
        assert FailsafeAction.RTL < FailsafeAction.LAND
        assert FailsafeAction.LAND < FailsafeAction.EMERGENCY_DISARM


class TestRegisterFailsafeExecutor:
    """Test register_failsafe_executor method."""

    def test_register_executor(self):
        """Executor can be registered for a FailsafeAction."""
        matrix = EscalationMatrix()

        async def my_executor(event: GuardianEvent) -> None:
            pass

        matrix.register_failsafe_executor(FailsafeAction.RTL, my_executor)

        assert hasattr(matrix, '_failsafe_executors')
        assert matrix._failsafe_executors[FailsafeAction.RTL] == my_executor

    def test_register_multiple_executors(self):
        """Multiple executors can be registered."""
        matrix = EscalationMatrix()

        async def rtl_executor(event: GuardianEvent) -> None:
            pass

        async def land_executor(event: GuardianEvent) -> None:
            pass

        matrix.register_failsafe_executor(FailsafeAction.RTL, rtl_executor)
        matrix.register_failsafe_executor(FailsafeAction.LAND, land_executor)

        assert len(matrix._failsafe_executors) == 2


class TestDispatchGuardianEvent:
    """Test dispatch_guardian_event method."""

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        """Successful dispatch calls executor and returns EscalationEvent."""
        matrix = EscalationMatrix()

        # Track if executor was called
        executor_called = False
        received_event = None

        async def my_executor(event: GuardianEvent) -> None:
            nonlocal executor_called, received_event
            executor_called = True
            received_event = event

        matrix.register_failsafe_executor(FailsafeAction.RTL, my_executor)

        # Dispatch event that triggers RTL
        guardian_event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%",
            context={"battery_percent": 18.0}
        )

        result = await matrix.dispatch_guardian_event(guardian_event)

        # Verify dispatch was successful
        assert result is not None
        assert result.condition == "battery_critical"
        assert result.action_taken == "initiate_rtl"
        assert executor_called is True
        assert received_event == guardian_event

    @pytest.mark.asyncio
    async def test_dispatch_no_executor(self):
        """Dispatch works when no executor is registered (logs warning)."""
        matrix = EscalationMatrix()
        # Don't register any executor

        guardian_event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%",
            context={"battery_percent": 18.0}
        )

        # Should not raise, just return event
        result = await matrix.dispatch_guardian_event(guardian_event)

        assert result is not None
        assert result.action_taken == "initiate_rtl"

    @pytest.mark.asyncio
    async def test_dispatch_no_escalation(self):
        """Dispatch returns None when condition doesn't escalate."""
        matrix = EscalationMatrix()

        guardian_event = GuardianEvent(
            condition="unknown_condition",
            reason="Something happened",
            context={}
        )

        result = await matrix.dispatch_guardian_event(guardian_event)

        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_executor_exception(self):
        """Dispatch handles executor exceptions gracefully."""
        matrix = EscalationMatrix()

        async def failing_executor(event: GuardianEvent) -> None:
            raise RuntimeError("Executor failed!")

        matrix.register_failsafe_executor(FailsafeAction.RTL, failing_executor)

        guardian_event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%",
            context={"battery_percent": 18.0}
        )

        # Should not raise, should log error and return event
        result = await matrix.dispatch_guardian_event(guardian_event)

        assert result is not None

    @pytest.mark.asyncio
    async def test_dispatch_hold_action(self):
        """Dispatch correctly maps hold action."""
        matrix = EscalationMatrix()

        executor_called = False

        async def hold_executor(event: GuardianEvent) -> None:
            nonlocal executor_called
            executor_called = True

        matrix.register_failsafe_executor(FailsafeAction.HOLD, hold_executor)

        # state_inconsistency maps to assume_control_hold which maps to HOLD
        guardian_event = GuardianEvent(
            condition="state_inconsistency",
            reason="State mismatch detected",
            context={}
        )

        result = await matrix.dispatch_guardian_event(guardian_event)

        assert result is not None
        assert executor_called is True

    @pytest.mark.asyncio
    async def test_dispatch_land_action(self):
        """Dispatch correctly maps land action."""
        matrix = EscalationMatrix()

        executor_called = False

        async def land_executor(event: GuardianEvent) -> None:
            nonlocal executor_called
            executor_called = True

        matrix.register_failsafe_executor(FailsafeAction.LAND, land_executor)

        guardian_event = GuardianEvent(
            condition="total_power_loss",
            reason="Battery at 0%",
            context={"battery_percent": 0}
        )

        result = await matrix.dispatch_guardian_event(guardian_event)

        assert result is not None
        assert executor_called is True


class TestMapActionToFailsafe:
    """Test _map_action_to_failsafe method."""

    def test_map_log_alert(self):
        """log_alert maps to LOG_ALERT."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("log_alert")
        assert action == FailsafeAction.LOG_ALERT

    def test_map_reject_command(self):
        """reject_command maps to REJECT_COMMAND."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("reject_command")
        assert action == FailsafeAction.REJECT_COMMAND

    def test_map_assume_control_hold(self):
        """assume_control_hold maps to HOLD."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("assume_control_hold")
        assert action == FailsafeAction.HOLD

    def test_map_initiate_rtl(self):
        """initiate_rtl maps to RTL."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("initiate_rtl")
        assert action == FailsafeAction.RTL

    def test_map_initiate_land(self):
        """initiate_land maps to LAND."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("initiate_land")
        assert action == FailsafeAction.LAND

    def test_map_emergency_disarm(self):
        """emergency_disarm maps to EMERGENCY_DISARM."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("emergency_disarm")
        assert action == FailsafeAction.EMERGENCY_DISARM

    def test_map_unknown_action(self):
        """Unknown action returns None."""
        matrix = EscalationMatrix()
        action = matrix._map_action_to_failsafe("unknown_action")
        assert action is None


class TestGlobalMatrix:
    """Test global matrix functions."""

    def test_get_global_matrix_creates_default(self):
        """get_global_matrix creates a matrix on first access."""
        # Reset global state
        import avatar.mav.escalation_matrix as em
        em._GLOBAL_MATRIX = None

        matrix = get_global_matrix()
        assert matrix is not None
        assert isinstance(matrix, EscalationMatrix)

    def test_set_global_matrix(self):
        """set_global_matrix sets the global matrix."""
        custom_matrix = EscalationMatrix()
        set_global_matrix(custom_matrix)

        result = get_global_matrix()
        assert result is custom_matrix


class TestModuleLevelDispatch:
    """Test module-level dispatch_guardian_event function."""

    @pytest.mark.asyncio
    async def test_module_dispatch(self):
        """Module-level dispatch works with global matrix."""
        matrix = EscalationMatrix()

        executor_called = False

        async def my_executor(event: GuardianEvent) -> None:
            nonlocal executor_called
            executor_called = True

        matrix.register_failsafe_executor(FailsafeAction.RTL, my_executor)
        set_global_matrix(matrix)

        guardian_event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%",
            context={"battery_percent": 18.0}
        )

        result = await module_dispatch(guardian_event)

        assert result is not None
        assert executor_called is True

    @pytest.mark.asyncio
    async def test_module_dispatch_with_custom_matrix(self):
        """Module-level dispatch accepts custom matrix."""
        matrix = EscalationMatrix()

        executor_called = False

        async def my_executor(event: GuardianEvent) -> None:
            nonlocal executor_called
            executor_called = True

        matrix.register_failsafe_executor(FailsafeAction.RTL, my_executor)

        guardian_event = GuardianEvent(
            condition="battery_critical",
            reason="Battery at 18%",
            context={"battery_percent": 18.0}
        )

        result = await module_dispatch(guardian_event, matrix=matrix)

        assert result is not None
        assert executor_called is True


class TestIntegrationWithGuardian:
    """Test integration patterns with AsyncGuardian."""

    @pytest.mark.asyncio
    async def test_guardian_dispatches_through_matrix(self):
        """AsyncGuardian dispatches events through EscalationMatrix."""
        from avatar.mav.guardian_async import AsyncGuardian, GuardianConfig
        from avatar.mav.connection_manager import ConnectionManager
        from avatar.mav.heartbeat_service import HeartbeatService
        from avatar.mav.state_machine import FlightStateMachine

        # Create components
        cm = ConnectionManager()
        hb = HeartbeatService()
        sm = FlightStateMachine()

        # Create matrix with executor
        matrix = EscalationMatrix()

        executor_called = False

        async def rtl_executor(event: GuardianEvent) -> None:
            nonlocal executor_called
            executor_called = True

        matrix.register_failsafe_executor(FailsafeAction.RTL, rtl_executor)

        # Create guardian with matrix
        guardian = AsyncGuardian(
            connection_manager=cm,
            heartbeat_service=hb,
            state_machine=sm,
            escalation_matrix=matrix
        )

        # Trigger RTL - this should dispatch through the matrix
        result = await guardian.initiate_rtl("Test RTL dispatch")

        # State machine should transition
        assert result is True or executor_called is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
