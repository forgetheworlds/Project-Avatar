"""Tests for FlightStateMachine.

Test-driven development for the flight state machine.
"""

import pytest
import threading
import time
from datetime import datetime
from avatar.mav.state_machine import (
    FlightState,
    FlightStateMachine,
    StateTransition,
    StateTransitionError,
)


class TestInitialState:
    """Tests for initial state of the state machine."""

    def test_initial_state(self):
        """State machine starts in INIT state."""
        sm = FlightStateMachine()
        assert sm.current_state == FlightState.INIT
        assert sm.current_state_name == "INIT"

    def test_initial_history_empty(self):
        """History is empty on initialization."""
        sm = FlightStateMachine()
        assert sm.get_history() == []

    def test_initial_flags(self):
        """Initial flags are correct."""
        sm = FlightStateMachine()
        assert not sm.is_flying
        assert not sm.is_armed


class TestValidTransitions:
    """Tests for valid state transitions."""

    def test_init_to_disarmed(self):
        """INIT -> DISARMED succeeds."""
        sm = FlightStateMachine()
        assert sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.current_state == FlightState.DISARMED

    def test_disarmed_to_armed(self):
        """DISARMED -> ARMED succeeds."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.current_state == FlightState.ARMED

    def test_armed_to_taking_off(self):
        """ARMED -> TAKING_OFF succeeds."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        assert sm.current_state == FlightState.TAKING_OFF

    def test_taking_off_to_hovering(self):
        """TAKING_OFF -> HOVERING succeeds."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        assert sm.transition(FlightState.HOVERING, "reached_altitude", "telemetry")
        assert sm.current_state == FlightState.HOVERING

    def test_hovering_to_flying(self):
        """HOVERING -> FLYING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.FLYING, "movement_detected", "telemetry")

    def test_flying_to_position_control(self):
        """FLYING -> POSITION_CONTROL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.POSITION_CONTROL, "goto_command", "llm")

    def test_flying_to_velocity_control(self):
        """FLYING -> VELOCITY_CONTROL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.VELOCITY_CONTROL, "velocity_command", "llm")

    def test_hovering_to_velocity_control(self):
        """HOVERING -> VELOCITY_CONTROL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.VELOCITY_CONTROL, "velocity_command", "llm")

    def test_position_control_to_hovering(self):
        """POSITION_CONTROL -> HOVERING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.HOVERING, "goto_complete", "telemetry")

    def test_velocity_control_to_hovering(self):
        """VELOCITY_CONTROL -> HOVERING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.HOVERING, "velocity_complete", "telemetry")

    def test_flying_to_mission_execution(self):
        """FLYING -> MISSION_EXECUTION succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.MISSION_EXECUTION, "mission_start", "llm")

    def test_mission_execution_to_hovering(self):
        """MISSION_EXECUTION -> HOVERING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.HOVERING, "mission_complete", "telemetry")

    def test_hovering_to_rtl(self):
        """HOVERING -> RTL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_flying_to_rtl(self):
        """FLYING -> RTL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_position_control_to_rtl(self):
        """POSITION_CONTROL -> RTL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_velocity_control_to_rtl(self):
        """VELOCITY_CONTROL -> RTL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_mission_execution_to_rtl(self):
        """MISSION_EXECUTION -> RTL succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_rtl_to_landing(self):
        """RTL -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.RTL
        assert sm.transition(FlightState.LANDING, "reached_home", "telemetry")

    def test_hovering_to_landing(self):
        """HOVERING -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_flying_to_landing(self):
        """FLYING -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_position_control_to_landing(self):
        """POSITION_CONTROL -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_velocity_control_to_landing(self):
        """VELOCITY_CONTROL -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_mission_execution_to_landing(self):
        """MISSION_EXECUTION -> LANDING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.LANDING, "mission_aborted", "operator")

    def test_landing_to_landed(self):
        """LANDING -> LANDED succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        assert sm.transition(FlightState.LANDED, "ground_contact", "telemetry")

    def test_landed_to_disarmed(self):
        """LANDED -> DISARMED succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.LANDED
        assert sm.transition(FlightState.DISARMED, "disarm_command", "operator")

    def test_armed_to_disarmed(self):
        """ARMED -> DISARMED succeeds."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.transition(FlightState.DISARMED, "disarm_command", "operator")

    def test_any_to_hold(self):
        """Any flying state -> HOLD succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.HOLD, "hold_command", "operator")

    def test_hold_to_hovering(self):
        """HOLD -> HOVERING succeeds."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOLD
        assert sm.transition(FlightState.HOVERING, "resume_command", "operator")


class TestInvalidTransitions:
    """Tests for invalid state transitions that should be blocked."""

    def test_invalid_init_to_armed(self):
        """INIT -> ARMED should be blocked."""
        sm = FlightStateMachine()
        assert not sm.can_transition(FlightState.ARMED)

    def test_invalid_init_to_takeoff(self):
        """INIT -> TAKING_OFF should be blocked."""
        sm = FlightStateMachine()
        assert not sm.can_transition(FlightState.TAKING_OFF)

    def test_invalid_disarmed_to_takeoff(self):
        """DISARMED -> TAKING_OFF should be blocked."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.can_transition(FlightState.TAKING_OFF)

    def test_invalid_armed_to_hovering(self):
        """ARMED -> HOVERING should be blocked."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert not sm.can_transition(FlightState.HOVERING)

    def test_invalid_disarmed_to_flying(self):
        """DISARMED -> FLYING should be blocked."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.can_transition(FlightState.FLYING)

    def test_invalid_landed_to_flying(self):
        """LANDED -> FLYING should be blocked."""
        sm = FlightStateMachine()
        sm._state = FlightState.LANDED
        assert not sm.can_transition(FlightState.FLYING)

    def test_invalid_flying_to_init(self):
        """FLYING -> INIT should be blocked."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert not sm.can_transition(FlightState.INIT)

    def test_invalid_hovering_to_armed(self):
        """HOVERING -> ARMED should be blocked."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert not sm.can_transition(FlightState.ARMED)

    def test_invalid_landing_to_armed(self):
        """LANDING -> ARMED should be blocked."""
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        assert not sm.can_transition(FlightState.ARMED)

    def test_transition_returns_false_on_invalid(self):
        """transition() returns False on invalid transition."""
        sm = FlightStateMachine()
        result = sm.transition(FlightState.ARMED, "invalid_attempt", "operator")
        assert result is False
        assert sm.current_state == FlightState.INIT


class TestFailsafeTransitions:
    """Tests for failsafe transitions that can override normal transitions."""

    def test_failsafe_rc_loss_from_any_state(self):
        """RC loss triggers RTL from any flying state."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("rc_loss")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_low_battery_from_hovering(self):
        """Low battery triggers RTL from hovering."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.trigger_failsafe("low_battery")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_critical_battery_lands(self):
        """Critical battery triggers LANDING."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("critical_battery")
        assert sm.current_state == FlightState.LANDING

    def test_failsafe_geofence_breach(self):
        """Geofence breach triggers RTL."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("geofence_breach")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_kill_switch(self):
        """Kill switch triggers EMERGENCY."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("kill_switch")
        assert sm.current_state == FlightState.EMERGENCY

    def test_failsafe_offboard_timeout(self):
        """Offboard timeout triggers HOLD."""
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.trigger_failsafe("offboard_timeout")
        assert sm.current_state == FlightState.HOLD

    def test_failsafe_invalid_reason(self):
        """Invalid failsafe reason returns False."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert not sm.trigger_failsafe("invalid_reason")


class TestStateHistory:
    """Tests for state transition history tracking."""

    def test_history_tracks_transitions(self):
        """History tracks all state transitions."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")

        history = sm.get_history()
        assert len(history) == 2
        assert history[0].from_state == FlightState.INIT
        assert history[0].to_state == FlightState.DISARMED
        assert history[0].reason == "startup_complete"
        assert history[0].source == "system"

    def test_history_has_timestamp(self):
        """Each transition has a timestamp."""
        sm = FlightStateMachine()
        before = time.time()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        after = time.time()

        history = sm.get_history()
        assert len(history) == 1
        assert before <= history[0].timestamp <= after

    def test_history_limit(self):
        """History can be limited to N most recent entries."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        sm.transition(FlightState.HOVERING, "reached_altitude", "telemetry")

        history = sm.get_history(limit=2)
        assert len(history) == 2
        assert history[0].to_state == FlightState.TAKING_OFF
        assert history[1].to_state == FlightState.HOVERING

    def test_history_returns_full_if_limit_none(self):
        """get_history() returns full history when limit is None."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")

        history = sm.get_history()
        assert len(history) == 3


class TestCommandPreconditions:
    """Tests for command preconditions based on state."""

    def test_arm_precondition(self):
        """Arm command requires DISARMED state."""
        sm = FlightStateMachine()
        assert sm.check_command_precondition("arm")  # INIT allows arm -> DISARMED first
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.check_command_precondition("arm")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert not sm.check_command_precondition("arm")

    def test_disarm_precondition(self):
        """Disarm command requires ARMED or LANDED state."""
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("disarm")

        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.check_command_precondition("disarm")

    def test_takeoff_precondition(self):
        """Takeoff command requires ARMED state."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.check_command_precondition("takeoff")

        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.check_command_precondition("takeoff")

    def test_land_precondition(self):
        """Land command requires flying states."""
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("land")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("land")

        sm._state = FlightState.FLYING
        assert sm.check_command_precondition("land")

        sm._state = FlightState.LANDING
        assert not sm.check_command_precondition("land")

    def test_set_velocity_precondition(self):
        """Set velocity command requires HOVERING or FLYING states."""
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("set_velocity")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("set_velocity")

        sm._state = FlightState.FLYING
        assert sm.check_command_precondition("set_velocity")

    def test_set_position_precondition(self):
        """Set position command requires HOVERING or FLYING states."""
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("set_position")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("set_position")

    def test_invalid_command(self):
        """Invalid command returns False."""
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("invalid_command")


class TestTelemetrySync:
    """Tests for telemetry-based state synchronization."""

    def test_sync_from_telemetry_disarmed(self):
        """Sync to DISARMED when not armed."""
        sm = FlightStateMachine()
        telemetry = {"armed": False, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.DISARMED

    def test_sync_from_telemetry_armed(self):
        """Sync to ARMED when armed but not flying."""
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.ARMED

    def test_sync_from_telemetry_hovering(self):
        """Sync to HOVERING when in air and stable."""
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": True, "landed": False, "velocity": [0.0, 0.0, 0.0]}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.HOVERING

    def test_sync_from_telemetry_flying(self):
        """Sync to FLYING when in air and moving."""
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": True, "landed": False, "velocity": [1.0, 0.0, 0.0]}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.FLYING

    def test_sync_from_telemetry_landing(self):
        """Sync to LANDING when landing detected."""
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        telemetry = {"armed": True, "in_air": True, "landed": False, "landing": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.LANDING

    def test_sync_from_telemetry_landed(self):
        """Sync to LANDED when grounded."""
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        telemetry = {"armed": True, "in_air": False, "landed": True, "ground_contact": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.LANDED

    def test_sync_does_not_override_emergency(self):
        """Emergency state is not overridden by telemetry sync."""
        sm = FlightStateMachine()
        sm._state = FlightState.EMERGENCY
        telemetry = {"armed": True, "in_air": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.EMERGENCY

    def test_sync_does_not_override_error(self):
        """Error state is not overridden by telemetry sync."""
        sm = FlightStateMachine()
        sm._state = FlightState.ERROR
        telemetry = {"armed": False, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.ERROR


class TestThreadSafety:
    """Tests for thread-safe state transitions."""

    def test_concurrent_transitions(self):
        """Concurrent transitions are thread-safe."""
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        sm.transition(FlightState.HOVERING, "reached_altitude", "telemetry")

        errors = []
        results = []

        def attempt_transition():
            try:
                result = sm.transition(FlightState.RTL, "concurrent_test", "test")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=attempt_transition) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Only one transition should succeed, rest should return False
        assert sum(results) == 1
        assert sm.current_state == FlightState.RTL

    def test_concurrent_failsafe(self):
        """Failsafe triggers are thread-safe."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING

        errors = []
        results = []

        def trigger_failsafe():
            try:
                result = sm.trigger_failsafe("low_battery")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=trigger_failsafe) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Only one failsafe should succeed
        assert sum(results) == 1
        assert sm.current_state == FlightState.RTL


class TestStateProperties:
    """Tests for state properties and helper methods."""

    def test_is_flying_property(self):
        """is_flying property is correct for each state."""
        flying_states = [
            FlightState.TAKING_OFF,
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
        ]

        non_flying_states = [
            FlightState.INIT,
            FlightState.DISARMED,
            FlightState.ARMED,
            FlightState.LANDED,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        ]

        sm = FlightStateMachine()

        for state in flying_states:
            sm._state = state
            assert sm.is_flying, f"State {state.name} should be flying"

        for state in non_flying_states:
            sm._state = state
            assert not sm.is_flying, f"State {state.name} should not be flying"

    def test_is_armed_property(self):
        """is_armed property is correct for each state."""
        armed_states = [
            FlightState.ARMED,
            FlightState.TAKING_OFF,
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.LANDED,
            FlightState.EMERGENCY,
        ]

        disarmed_states = [
            FlightState.INIT,
            FlightState.DISARMED,
            FlightState.ERROR,
        ]

        sm = FlightStateMachine()

        for state in armed_states:
            sm._state = state
            assert sm.is_armed, f"State {state.name} should be armed"

        for state in disarmed_states:
            sm._state = state
            assert not sm.is_armed, f"State {state.name} should not be armed"

    def test_all_states_have_names(self):
        """All FlightState enum values have proper string names."""
        for state in FlightState:
            sm = FlightStateMachine()
            sm._state = state
            assert sm.current_state_name == state.name


class TestErrorHandling:
    """Tests for error state handling."""

    def test_error_transition(self):
        """Can transition to ERROR state."""
        sm = FlightStateMachine()
        assert sm.transition(FlightState.ERROR, "system_failure", "guardian")
        assert sm.current_state == FlightState.ERROR

    def test_from_error_to_disarmed(self):
        """Can recover from ERROR to DISARMED."""
        sm = FlightStateMachine()
        sm.transition(FlightState.ERROR, "system_failure", "guardian")
        assert sm.transition(FlightState.DISARMED, "error_cleared", "operator")

    def test_emergency_requires_manual_reset(self):
        """EMERGENCY state requires explicit handling."""
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        sm.trigger_failsafe("kill_switch")
        assert sm.current_state == FlightState.EMERGENCY

        # Regular transitions blocked
        assert not sm.can_transition(FlightState.DISARMED)


class TestStateTransitionException:
    """Tests for StateTransitionError exception."""

    def test_exception_raised_when_requested(self):
        """Can raise exception instead of returning False."""
        sm = FlightStateMachine()
        with pytest.raises(StateTransitionError):
            sm.transition(FlightState.ARMED, "invalid", "operator", raise_on_error=True)

    def test_exception_message(self):
        """Exception includes helpful message."""
        sm = FlightStateMachine()
        with pytest.raises(StateTransitionError) as exc_info:
            sm.transition(FlightState.ARMED, "invalid", "operator", raise_on_error=True)
        assert "INIT" in str(exc_info.value)
        assert "ARMED" in str(exc_info.value)

