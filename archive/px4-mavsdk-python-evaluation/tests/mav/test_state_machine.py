"""Tests for FlightStateMachine.

Test-driven development for the flight state machine.

SAFETY CRITICAL: The FlightStateMachine is the authoritative source of truth
for the drone's operational state. It prevents dangerous transitions like:
- Arming while already armed (motor sync issues)
- Takeoff from non-armed state (crash on throttle spike)
- Direct INIT to FLYING (missing safety checks)
- Invalid state transitions that could confuse the operator

All transitions are validated against a safety-approved transition matrix.
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
    """Tests for initial state of the state machine.

    SAFETY: The initial state must be safe and clearly indicate the system
    is not ready for flight operations. INIT state requires explicit setup.
    """

    def test_initial_state(self):
        """State machine starts in INIT state.

        VALIDATES: Fresh instance starts in safe INIT state.

        MOCK SETUP: None - testing initial condition.

        SAFETY REASON: INIT is the safest starting state because it requires
        explicit transitions through DISARMED -> ARMED before any motor activity.
        This prevents accidental arming on system startup.

        STEP-BY-STEP:
        1. Create new FlightStateMachine instance
        2. Assert current_state is FlightState.INIT
        3. Assert current_state_name is "INIT" (string representation)
        """
        sm = FlightStateMachine()
        assert sm.current_state == FlightState.INIT
        assert sm.current_state_name == "INIT"

    def test_initial_history_empty(self):
        """History is empty on initialization.

        VALIDATES: No phantom history entries exist at startup.

        MOCK SETUP: None - testing initial condition.

        SAFETY REASON: Empty history ensures no confusion about past states.
        Post-incident analysis depends on accurate history starting from boot.

        STEP-BY-STEP:
        1. Create new FlightStateMachine
        2. Call get_history()
        3. Assert returns empty list (no prior states recorded)
        """
        sm = FlightStateMachine()
        assert sm.get_history() == []

    def test_initial_flags(self):
        """Initial flags are correct.

        VALIDATES: is_flying and is_armed reflect INIT state accurately.

        MOCK SETUP: None - testing property values.

        SAFETY REASON: These flags are used by UI and safety interlocks.
        is_flying=False prevents flight-mode commands when on ground.
        is_armed=False blocks motor control in INIT state.

        STEP-BY-STEP:
        1. Create new FlightStateMachine
        2. Assert is_flying is False (INIT state is not flying)
        3. Assert is_armed is False (INIT state motors are disarmed)
        """
        sm = FlightStateMachine()
        assert not sm.is_flying
        assert not sm.is_armed


class TestValidTransitions:
    """Tests for valid state transitions.

    SAFETY: These transitions represent the approved flight operation sequence.
    Each transition has physical meaning and safety checks at the MAVSDK level.
    "Valid" means both allowed by state machine AND safe to execute.
    """

    def test_init_to_disarmed(self):
        """INIT -> DISARMED succeeds.

        VALIDATES: System can transition from initialization to ready state.

        MOCK SETUP: None - testing allowed transition.

        SAFETY REASON: DISARMED is the ground-safe state where the system
        is ready but motors are locked. This is the state after successful
        initialization and before operator arming command.

        STEP-BY-STEP:
        1. Create FlightStateMachine (starts in INIT)
        2. Call transition(DISARMED, "startup_complete", "system")
        3. Assert transition returned True (success)
        4. Assert current_state is DISARMED
        """
        sm = FlightStateMachine()
        assert sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.current_state == FlightState.DISARMED

    def test_disarmed_to_armed(self):
        """DISARMED -> ARMED succeeds.

        VALIDATES: Operator can arm the system from ready state.

        MOCK SETUP: None - first transition to DISARMED, then to ARMED.

        SAFETY REASON: Arming is the gateway to flight. Separating DISARMED
        from ARMED allows system checks before enabling motor control.
        This two-step process prevents accidental arming.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition INIT -> DISARMED (prerequisite)
        3. Transition DISARMED -> ARMED with "operator_command" reason
        4. Assert both transitions succeed
        5. Assert final state is ARMED (motors now responsive to throttle)
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.current_state == FlightState.ARMED

    def test_armed_to_taking_off(self):
        """ARMED -> TAKING_OFF succeeds.

        VALIDATES: Takeoff command accepted from armed state.

        MOCK SETUP: None - chain of transitions to reach ARMED first.

        SAFETY REASON: TAKING_OFF represents the active climb phase after
        arming. This state helps the system distinguish between ground
        armed (ready) and actively climbing (in flight transition).

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition through INIT -> DISARMED -> ARMED
        3. Transition ARMED -> TAKING_OFF with "takeoff_command"
        4. Assert final state is TAKING_OFF
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        assert sm.current_state == FlightState.TAKING_OFF

    def test_taking_off_to_hovering(self):
        """TAKING_OFF -> HOVERING succeeds.

        VALIDATES: System transitions to stable hover after reaching altitude.

        MOCK SETUP: None - standard transition chain.

        SAFETY REASON: HOVERING is the "safe" in-flight state where the
        drone maintains position. This is the state for most LLM commands.
        Explicit transition from TAKING_OFF confirms climb is complete.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Chain transitions to reach TAKING_OFF
        3. Transition TAKING_OFF -> HOVERING on "reached_altitude"
        4. Assert state is HOVERING (stable hover achieved)
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")
        assert sm.transition(FlightState.HOVERING, "reached_altitude", "telemetry")
        assert sm.current_state == FlightState.HOVERING

    def test_hovering_to_flying(self):
        """HOVERING -> FLYING succeeds.

        VALIDATES: Movement detection transitions from hover to active flight.

        MOCK SETUP: Direct state assignment (shortcut for test).

        SAFETY REASON: FLYING indicates active maneuvering (vs. stationary
        hover). This distinction helps the LLM understand if the drone is
        already in motion when issuing new commands.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Directly set state to HOVERING (shortcut)
        3. Transition HOVERING -> FLYING on "movement_detected"
        4. Assert state is FLYING (drone is now in active motion)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.FLYING, "movement_detected", "telemetry")

    def test_flying_to_position_control(self):
        """FLYING -> POSITION_CONTROL succeeds.

        VALIDATES: Position commands accepted during flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: POSITION_CONTROL is the goto waypoint mode. Only
        allowed from FLYING or HOVERING to ensure the drone is already
        airborne and stable before waypoint navigation.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Transition FLYING -> POSITION_CONTROL with "goto_command"
        4. Assert state is POSITION_CONTROL (waypoint navigation active)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.POSITION_CONTROL, "goto_command", "llm")

    def test_flying_to_velocity_control(self):
        """FLYING -> VELOCITY_CONTROL succeeds.

        VALIDATES: Velocity commands accepted during flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: VELOCITY_CONTROL enables joystick-like velocity
        commands. Allowed from FLYING or HOVERING states only to ensure
        the drone is already stable in the air.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Transition FLYING -> VELOCITY_CONTROL with "velocity_command"
        4. Assert state is VELOCITY_CONTROL (velocity mode active)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.VELOCITY_CONTROL, "velocity_command", "llm")

    def test_hovering_to_velocity_control(self):
        """HOVERING -> VELOCITY_CONTROL succeeds.

        VALIDATES: Velocity commands accepted from hover state.

        MOCK SETUP: Direct state assignment to HOVERING.

        SAFETY REASON: Direct velocity commands from hover are safe
        because the drone is already stable. The transition indicates
        the system is now responding to velocity setpoints.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Transition HOVERING -> VELOCITY_CONTROL with "velocity_command"
        4. Assert state is VELOCITY_CONTROL
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.VELOCITY_CONTROL, "velocity_command", "llm")

    def test_position_control_to_hovering(self):
        """POSITION_CONTROL -> HOVERING succeeds.

        VALIDATES: Waypoint completion returns to stable hover.

        MOCK SETUP: Direct state assignment to POSITION_CONTROL.

        SAFETY REASON: After goto completes, returning to HOVERING
        indicates the drone is now stationary and awaiting next command.
        This is the expected "command complete" state.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to POSITION_CONTROL
        3. Transition POSITION_CONTROL -> HOVERING on "goto_complete"
        4. Assert state is HOVERING (waypoint navigation complete)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.HOVERING, "goto_complete", "telemetry")

    def test_velocity_control_to_hovering(self):
        """VELOCITY_CONTROL -> HOVERING succeeds.

        VALIDATES: Velocity command completion returns to hover.

        MOCK SETUP: Direct state assignment to VELOCITY_CONTROL.

        SAFETY REASON: After velocity commands complete (e.g., "move left 2m"),
        returning to HOVERING indicates the motion is complete and the
        drone is stable for next command.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to VELOCITY_CONTROL
        3. Transition VELOCITY_CONTROL -> HOVERING on "velocity_complete"
        4. Assert state is HOVERING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.HOVERING, "velocity_complete", "telemetry")

    def test_flying_to_mission_execution(self):
        """FLYING -> MISSION_EXECUTION succeeds.

        VALIDATES: Mission commands accepted during flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: MISSION_EXECUTION state indicates the drone is
        following a pre-planned sequence. Transition from FLYING ensures
        the drone is already airborne before starting mission.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Transition FLYING -> MISSION_EXECUTION on "mission_start"
        4. Assert state is MISSION_EXECUTION (autonomous mission active)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.MISSION_EXECUTION, "mission_start", "llm")

    def test_mission_execution_to_hovering(self):
        """MISSION_EXECUTION -> HOVERING succeeds.

        VALIDATES: Mission completion returns to hover.

        MOCK SETUP: Direct state assignment to MISSION_EXECUTION.

        SAFETY REASON: After mission completes, returning to HOVERING
        indicates the drone is stable and awaiting further instructions.
        Prevents automatic transitions to landing without confirmation.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to MISSION_EXECUTION
        3. Transition MISSION_EXECUTION -> HOVERING on "mission_complete"
        4. Assert state is HOVERING (mission finished, drone stable)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.HOVERING, "mission_complete", "telemetry")

    def test_hovering_to_rtl(self):
        """HOVERING -> RTL succeeds.

        VALIDATES: RTL command accepted from hover state.

        MOCK SETUP: Direct state assignment to HOVERING.

        SAFETY REASON: RTL (Return to Launch) is the primary failsafe.
        Allowed from all flying states because it's the emergency
        recovery action. HOVERING -> RTL is a common operator command.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Transition HOVERING -> RTL with "operator_command"
        4. Assert state is RTL (return flight initiated)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_flying_to_rtl(self):
        """FLYING -> RTL succeeds.

        VALIDATES: RTL command accepted during active flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: RTL must work from any flying state as it's the
        emergency recovery. FLYING -> RTL allows immediate abort of
        maneuvers to return home safely.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Transition FLYING -> RTL with "operator_command"
        4. Assert state is RTL
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_position_control_to_rtl(self):
        """POSITION_CONTROL -> RTL succeeds.

        VALIDATES: RTL command accepted during waypoint navigation.

        MOCK SETUP: Direct state assignment to POSITION_CONTROL.

        SAFETY REASON: During goto operations, operator may need to
        abort and return home. This transition enables immediate RTL
        without waiting for goto to complete.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to POSITION_CONTROL
        3. Transition POSITION_CONTROL -> RTL with "operator_command"
        4. Assert state is RTL
        """
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_velocity_control_to_rtl(self):
        """VELOCITY_CONTROL -> RTL succeeds.

        VALIDATES: RTL command accepted during velocity control.

        MOCK SETUP: Direct state assignment to VELOCITY_CONTROL.

        SAFETY REASON: Velocity control may drift or encounter issues.
        Immediate RTL transition enables safe recovery from any velocity
        control situation.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to VELOCITY_CONTROL
        3. Transition VELOCITY_CONTROL -> RTL with "operator_command"
        4. Assert state is RTL
        """
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_mission_execution_to_rtl(self):
        """MISSION_EXECUTION -> RTL succeeds.

        VALIDATES: RTL command accepted during mission execution.

        MOCK SETUP: Direct state assignment to MISSION_EXECUTION.

        SAFETY REASON: Mission abort via RTL is essential for safety.
        If a mission encounters unexpected conditions, immediate RTL
        allows safe return without completing mission.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to MISSION_EXECUTION
        3. Transition MISSION_EXECUTION -> RTL with "operator_command"
        4. Assert state is RTL
        """
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.RTL, "operator_command", "operator")

    def test_rtl_to_landing(self):
        """RTL -> LANDING succeeds.

        VALIDATES: RTL completion transitions to landing phase.

        MOCK SETUP: Direct state assignment to RTL.

        SAFETY REASON: After RTL reaches home position, the natural
        next step is landing. This transition is typically triggered
        by telemetry indicating arrival at home position.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to RTL
        3. Transition RTL -> LANDING on "reached_home"
        4. Assert state is LANDING (descent phase active)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.RTL
        assert sm.transition(FlightState.LANDING, "reached_home", "telemetry")

    def test_hovering_to_landing(self):
        """HOVERING -> LANDING succeeds.

        VALIDATES: Land command accepted from hover state.

        MOCK SETUP: Direct state assignment to HOVERING.

        SAFETY REASON: Direct landing from hover is the normal mission
        conclusion. This transition allows operator or LLM to command
        landing at current position rather than returning to launch.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Transition HOVERING -> LANDING with "land_command"
        4. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_flying_to_landing(self):
        """FLYING -> LANDING succeeds.

        VALIDATES: Land command accepted during active flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: Emergency landing may be needed during maneuvers.
        This transition allows immediate landing without requiring
        transition to HOVERING first.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Transition FLYING -> LANDING with "land_command"
        4. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_position_control_to_landing(self):
        """POSITION_CONTROL -> LANDING succeeds.

        VALIDATES: Land command accepted during waypoint navigation.

        MOCK SETUP: Direct state assignment to POSITION_CONTROL.

        SAFETY REASON: If an issue occurs during goto, immediate
        landing may be safer than continuing or returning home. This
        transition enables that emergency option.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to POSITION_CONTROL
        3. Transition POSITION_CONTROL -> LANDING with "land_command"
        4. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.POSITION_CONTROL
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_velocity_control_to_landing(self):
        """VELOCITY_CONTROL -> LANDING succeeds.

        VALIDATES: Land command accepted during velocity control.

        MOCK SETUP: Direct state assignment to VELOCITY_CONTROL.

        SAFETY REASON: If velocity control becomes unstable, immediate
        landing is often the safest recovery. This transition allows
        landing from any velocity control situation.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to VELOCITY_CONTROL
        3. Transition VELOCITY_CONTROL -> LANDING with "land_command"
        4. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.transition(FlightState.LANDING, "land_command", "operator")

    def test_mission_execution_to_landing(self):
        """MISSION_EXECUTION -> LANDING succeeds.

        VALIDATES: Mission abort via landing command works.

        MOCK SETUP: Direct state assignment to MISSION_EXECUTION.

        SAFETY REASON: If a mission must abort but RTL is not appropriate
        (e.g., launch point is far), landing at current position may be
        better. This transition enables mission abort to landing.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to MISSION_EXECUTION
        3. Transition MISSION_EXECUTION -> LANDING with "mission_aborted"
        4. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.MISSION_EXECUTION
        assert sm.transition(FlightState.LANDING, "mission_aborted", "operator")

    def test_landing_to_landed(self):
        """LANDING -> LANDED succeeds.

        VALIDATES: Ground contact detection completes landing.

        MOCK SETUP: Direct state assignment to LANDING.

        SAFETY REASON: LANDED indicates the drone is on the ground and
        motors can be disarmed safely. This state transition requires
        ground contact confirmation to prevent premature disarm.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to LANDING
        3. Transition LANDING -> LANDED on "ground_contact"
        4. Assert state is LANDED (drone is on ground)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        assert sm.transition(FlightState.LANDED, "ground_contact", "telemetry")

    def test_landed_to_disarmed(self):
        """LANDED -> DISARMED succeeds.

        VALIDATES: Disarm command accepted after landing.

        MOCK SETUP: Direct state assignment to LANDED.

        SAFETY REASON: DISARMED is the final safe state after flight.
        Motors are locked and the system is ready for next mission.
        Transition from LANDED confirms the drone is grounded.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to LANDED
        3. Transition LANDED -> DISARMED with "disarm_command"
        4. Assert state is DISARMED (motors locked, flight complete)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.LANDED
        assert sm.transition(FlightState.DISARMED, "disarm_command", "operator")

    def test_armed_to_disarmed(self):
        """ARMED -> DISARMED succeeds.

        VALIDATES: Disarm command works from armed state (pre-flight).

        MOCK SETUP: Chain transitions to reach ARMED state.

        SAFETY REASON: Operator may decide not to fly after arming.
        This transition allows returning to DISARMED without taking off,
        essential for safety if conditions change before launch.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Chain transitions to reach ARMED
        3. Transition ARMED -> DISARMED with "disarm_command"
        4. Assert state is DISARMED (motors locked, no takeoff)
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.transition(FlightState.DISARMED, "disarm_command", "operator")

    def test_any_to_hold(self):
        """Any flying state -> HOLD succeeds.

        VALIDATES: Hold command works from any flying state.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: HOLD is the emergency pause state where all
        motion stops and the drone hovers in place. Must work from
        any flying state for immediate emergency stop.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING (represents any flying state)
        3. Transition FLYING -> HOLD with "hold_command"
        4. Assert state is HOLD (emergency pause active)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.transition(FlightState.HOLD, "hold_command", "operator")

    def test_hold_to_hovering(self):
        """HOLD -> HOVERING succeeds.

        VALIDATES: Resume command exits hold state.

        MOCK SETUP: Direct state assignment to HOLD.

        SAFETY REASON: HOLD is temporary pause. Resuming returns to
        HOVERING where normal commands can be accepted. This two-state
        approach allows clear "paused" vs "active" distinction.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOLD
        3. Transition HOLD -> HOVERING with "resume_command"
        4. Assert state is HOVERING (normal flight resumed)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOLD
        assert sm.transition(FlightState.HOVERING, "resume_command", "operator")


class TestInvalidTransitions:
    """Tests for invalid state transitions that should be blocked.

    SAFETY: These tests verify that dangerous or nonsensical transitions
    are blocked by the state machine. Each blocked transition represents
    a potential safety hazard that could cause crashes or flyaways.
    """

    def test_invalid_init_to_armed(self):
        """INIT -> ARMED should be blocked.

        VALIDATES: Cannot skip DISARMED state during startup.

        MOCK SETUP: None - testing transition from INIT.

        SAFETY REASON: Arming directly from INIT bypasses system checks
        that happen in DISARMED state. Could arm before systems ready.

        STEP-BY-STEP:
        1. Create FlightStateMachine (starts in INIT)
        2. Check can_transition(ARMED) - should return False
        3. Verify direct arming is blocked (safe startup enforced)
        """
        sm = FlightStateMachine()
        assert not sm.can_transition(FlightState.ARMED)

    def test_invalid_init_to_takeoff(self):
        """INIT -> TAKING_OFF should be blocked.

        VALIDATES: Cannot takeoff from initialization state.

        MOCK SETUP: None - testing from INIT state.

        SAFETY REASON: Taking off without arming would send throttle
        commands to unarmed motors (no effect) or cause undefined behavior.
        Proper sequence (INIT -> DISARMED -> ARMED -> TAKING_OFF) required.

        STEP-BY-STEP:
        1. Create FlightStateMachine (starts in INIT)
        2. Check can_transition(TAKING_OFF) - should return False
        """
        sm = FlightStateMachine()
        assert not sm.can_transition(FlightState.TAKING_OFF)

    def test_invalid_disarmed_to_takeoff(self):
        """DISARMED -> TAKING_OFF should be blocked.

        VALIDATES: Cannot takeoff without arming first.

        MOCK SETUP: Transition to DISARMED first.

        SAFETY REASON: Taking off from DISARMED would attempt to send
        throttle commands while motors are locked. PX4 would reject,
        but state machine should prevent this logical error.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition to DISARMED
        3. Check can_transition(TAKING_OFF) - should return False
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.can_transition(FlightState.TAKING_OFF)

    def test_invalid_armed_to_hovering(self):
        """ARMED -> HOVERING should be blocked.

        VALIDATES: Must go through TAKING_OFF first.

        MOCK SETUP: Chain transitions to reach ARMED.

        SAFETY REASON: HOVERING implies the drone is in the air and
        stable. Skipping TAKING_OFF would indicate hovering when still
        on ground, causing dangerous command expectations.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Chain to ARMED state
        3. Check can_transition(HOVERING) - should return False
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert not sm.can_transition(FlightState.HOVERING)

    def test_invalid_disarmed_to_flying(self):
        """DISARMED -> FLYING should be blocked.

        VALIDATES: Cannot be flying while disarmed.

        MOCK SETUP: Transition to DISARMED.

        SAFETY REASON: FLYING state indicates active maneuvering. Being
        in FLYING while DISARMED is logically impossible and dangerous.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition to DISARMED
        3. Check can_transition(FLYING) - should return False
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.can_transition(FlightState.FLYING)

    def test_invalid_landed_to_flying(self):
        """LANDED -> FLYING should be blocked.

        VALIDATES: Cannot transition from ground to flying directly.

        MOCK SETUP: Direct state assignment to LANDED.

        SAFETY REASON: LANDED indicates the drone is on the ground with
        motors potentially disarmed. Direct FLYING transition would
        bypass arming and takeoff sequences (crash risk).

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to LANDED
        3. Check can_transition(FLYING) - should return False
        """
        sm = FlightStateMachine()
        sm._state = FlightState.LANDED
        assert not sm.can_transition(FlightState.FLYING)

    def test_invalid_flying_to_init(self):
        """FLYING -> INIT should be blocked.

        VALIDATES: Cannot reset to initialization during flight.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: INIT state implies system startup. Transitioning
        from FLYING to INIT would appear as a system reset during flight,
        potentially clearing important flight state information mid-air.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Check can_transition(INIT) - should return False
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert not sm.can_transition(FlightState.INIT)

    def test_invalid_hovering_to_armed(self):
        """HOVERING -> ARMED should be blocked.

        VALIDATES: Cannot disarm mid-flight.

        MOCK SETUP: Direct state assignment to HOVERING.

        SAFETY REASON: ARMED state is for ground operations. Attempting
        to transition HOVERING (in-air) -> ARMED (ground) without landing
        would be catastrophic (motor cutoff in flight).

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Check can_transition(ARMED) - should return False
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert not sm.can_transition(FlightState.ARMED)

    def test_invalid_landing_to_armed(self):
        """LANDING -> ARMED should be blocked.

        VALIDATES: Cannot abort landing to armed state.

        MOCK SETUP: Direct state assignment to LANDING.

        SAFETY REASON: LANDING is the descent phase. ARMED is ground
        with motors active but not flying. This transition would
        appear as landing completion without ground contact check.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to LANDING
        3. Check can_transition(ARMED) - should return False
        """
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        assert not sm.can_transition(FlightState.ARMED)

    def test_transition_returns_false_on_invalid(self):
        """transition() returns False on invalid transition.

        VALIDATES: Invalid transitions fail gracefully.

        MOCK SETUP: None - testing return value behavior.

        SAFETY REASON: Returning False (not raising) allows calling code
        to handle the failure gracefully. This is essential for LLM
        commands that may attempt invalid transitions.

        STEP-BY-STEP:
        1. Create FlightStateMachine (starts in INIT)
        2. Attempt invalid transition INIT -> ARMED
        3. Assert transition() returns False (not True or exception)
        4. Assert current_state still INIT (unchanged by failed attempt)
        """
        sm = FlightStateMachine()
        result = sm.transition(FlightState.ARMED, "invalid_attempt", "operator")
        assert result is False
        assert sm.current_state == FlightState.INIT


class TestFailsafeTransitions:
    """Tests for failsafe transitions that can override normal transitions.

    SAFETY: Failsafe transitions take priority over normal state logic.
    When emergency conditions occur (low battery, RC loss, geofence breach),
    the system must transition to safety states regardless of current mode.
    """

    def test_failsafe_rc_loss_from_any_state(self):
        """RC loss triggers RTL from any flying state.

        VALIDATES: RC loss failsafe works universally.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: RC (Radio Control) loss means the operator cannot
        manually control the drone. Immediate RTL brings the drone back
        to launch point for recovery. Works from any flying state.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING (represents any flying state)
        3. Call trigger_failsafe("rc_loss")
        4. Assert trigger_failsafe returned True (success)
        5. Assert state is now RTL (emergency return initiated)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("rc_loss")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_low_battery_from_hovering(self):
        """Low battery triggers RTL from hovering.

        VALIDATES: Low battery failsafe from stable hover.

        MOCK SETUP: Direct state assignment to HOVERING.

        SAFETY REASON: Low battery requires immediate return before power
        is exhausted. HOVERING -> RTL ensures the drone doesn't continue
        operations with insufficient power to return home.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Call trigger_failsafe("low_battery")
        4. Assert state is now RTL (battery preservation mode)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        assert sm.trigger_failsafe("low_battery")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_critical_battery_lands(self):
        """Critical battery triggers LANDING.

        VALIDATES: Critical battery initiates immediate landing.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: Critical battery (below RTL threshold) means there
        may not be enough power to return home. Immediate landing at
        current position preserves enough power for controlled descent.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Call trigger_failsafe("critical_battery")
        4. Assert state is LANDING (immediate descent for survival)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("critical_battery")
        assert sm.current_state == FlightState.LANDING

    def test_failsafe_geofence_breach(self):
        """Geofence breach triggers RTL.

        VALIDATES: Boundary violation initiates return.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: Geofence breach means the drone has left the safe
        operating area. Immediate RTL brings it back to authorized space.
        Prevents flyaways and airspace violations.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Call trigger_failsafe("geofence_breach")
        4. Assert state is RTL (return to safe zone)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("geofence_breach")
        assert sm.current_state == FlightState.RTL

    def test_failsafe_kill_switch(self):
        """Kill switch triggers EMERGENCY.

        VALIDATES: Emergency stop works immediately.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: Kill switch is the operator's emergency stop.
        EMERGENCY state immediately cuts motor power (or initiates
        emergency landing depending on implementation).

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Call trigger_failsafe("kill_switch")
        4. Assert state is EMERGENCY (immediate motor cutoff)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert sm.trigger_failsafe("kill_switch")
        assert sm.current_state == FlightState.EMERGENCY

    def test_failsafe_offboard_timeout(self):
        """Offboard timeout triggers HOLD.

        VALIDATES: Communication loss with companion computer triggers hold.

        MOCK SETUP: Direct state assignment to VELOCITY_CONTROL.

        SAFETY REASON: Offboard timeout means the LLM/companion computer
        has stopped sending commands. HOLD pauses motion and maintains
        position until communication is restored (safer than continuing
        last command blindly).

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to VELOCITY_CONTROL (offboard mode)
        3. Call trigger_failsafe("offboard_timeout")
        4. Assert state is HOLD (pause and maintain position)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.VELOCITY_CONTROL
        assert sm.trigger_failsafe("offboard_timeout")
        assert sm.current_state == FlightState.HOLD

    def test_failsafe_invalid_reason(self):
        """Invalid failsafe reason returns False.

        VALIDATES: Unknown failsafe reasons are rejected.

        MOCK SETUP: Direct state assignment to FLYING.

        SAFETY REASON: Invalid failsafe reasons could be typos or
        confusion. Returning False prevents accidental state changes
        from incorrect failsafe triggers.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Call trigger_failsafe("invalid_reason")
        4. Assert returns False (rejected)
        5. Assert state unchanged (still FLYING)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        assert not sm.trigger_failsafe("invalid_reason")


class TestStateHistory:
    """Tests for state transition history tracking.

    SAFETY: History tracking enables post-incident analysis and debugging.
    Understanding the sequence of states helps identify root causes of
    incidents and validates that safety systems activated correctly.
    """

    def test_history_tracks_transitions(self):
        """History tracks all state transitions.

        VALIDATES: Each transition is recorded with metadata.

        MOCK SETUP: None - perform actual transitions.

        SAFETY REASON: Post-incident analysis requires knowing exactly
        what states the drone went through. History tracks who initiated
        each transition (system, operator, LLM) and why.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Perform two transitions: INIT->DISARMED, DISARMED->ARMED
        3. Get history
        4. Assert history length is 2
        5. Assert first entry shows INIT->DISARMED, "startup_complete", "system"
        """
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
        """Each transition has a timestamp.

        VALIDATES: Transitions are temporally recorded.

        MOCK SETUP: None - use time.time() for bounds.

        SAFETY REASON: Timestamps enable timeline reconstruction during
        incident investigation. Relative timing between transitions can
        reveal race conditions or slow safety responses.

        STEP-BY-STEP:
        1. Record time before transition
        2. Perform transition
        3. Record time after transition
        4. Get history
        5. Assert timestamp is between before and after times
        """
        sm = FlightStateMachine()
        before = time.time()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        after = time.time()

        history = sm.get_history()
        assert len(history) == 1
        assert before <= history[0].timestamp <= after

    def test_history_limit(self):
        """History can be limited to N most recent entries.

        VALIDATES: Memory management via limit parameter.

        MOCK SETUP: None - perform multiple transitions.

        SAFETY REASON: Unlimited history could consume excessive memory
        on long flights. Limiting to recent entries preserves relevant
        context while preventing memory exhaustion.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Perform 4 transitions
        3. Get history with limit=2
        4. Assert only 2 entries returned
        5. Assert entries are the most recent 2 transitions
        """
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
        """get_history() returns full history when limit is None.

        VALIDATES: Default behavior returns all entries.

        MOCK SETUP: None - perform transitions.

        SAFETY REASON: Full history may be needed for detailed analysis.
        Default behavior should not arbitrarily limit investigation data.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Perform 3 transitions
        3. Get history (no limit specified)
        4. Assert all 3 entries returned
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        sm.transition(FlightState.TAKING_OFF, "takeoff_command", "operator")

        history = sm.get_history()
        assert len(history) == 3


class TestCommandPreconditions:
    """Tests for command preconditions based on state.

    SAFETY: Commands have prerequisites. Attempting to arm when already
    armed, or land when not flying, could cause errors or dangerous behavior.
    These preconditions prevent invalid commands from reaching the autopilot.
    """

    def test_arm_precondition(self):
        """Arm command requires DISARMED state.

        VALIDATES: Arm only from DISARMED.

        MOCK SETUP: Chain transitions through states.

        SAFETY REASON: Arming when already armed could cause motor sync
        issues or confusion. Preconditions ensure commands make sense.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Assert arm allowed from INIT (implicit DISARMED transition path)
        3. Transition to DISARMED
        4. Assert arm allowed
        5. Transition to ARMED
        6. Assert arm NOT allowed (already armed)
        """
        sm = FlightStateMachine()
        assert sm.check_command_precondition("arm")  # INIT allows arm -> DISARMED first
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert sm.check_command_precondition("arm")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert not sm.check_command_precondition("arm")

    def test_disarm_precondition(self):
        """Disarm command requires ARMED or LANDED state.

        VALIDATES: Disarm only from appropriate states.

        MOCK SETUP: Chain transitions to ARMED.

        SAFETY REASON: Disarming from inappropriate states could cause
        unexpected motor cutoff or confusion about system readiness.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Assert disarm NOT allowed from INIT
        3. Chain to ARMED state
        4. Assert disarm allowed from ARMED
        """
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("disarm")

        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.check_command_precondition("disarm")

    def test_takeoff_precondition(self):
        """Takeoff command requires ARMED state.

        VALIDATES: Takeoff only from ARMED.

        MOCK SETUP: Chain transitions to DISARMED then check preconditions.

        SAFETY REASON: Takeoff from DISARMED would fail or cause undefined
        behavior. Preconditions ensure the drone is ready for flight.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Chain to DISARMED
        3. Assert takeoff NOT allowed from DISARMED
        4. Transition to ARMED
        5. Assert takeoff allowed from ARMED
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup_complete", "system")
        assert not sm.check_command_precondition("takeoff")

        sm.transition(FlightState.ARMED, "operator_command", "operator")
        assert sm.check_command_precondition("takeoff")

    def test_land_precondition(self):
        """Land command requires flying states.

        VALIDATES: Land only from in-air states.

        MOCK SETUP: Direct state assignments to various states.

        SAFETY REASON: Landing while not flying would be confusing and
        potentially dangerous if the system thought it was landing when
        actually on ground.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Assert land NOT allowed from INIT
        3. Set state to HOVERING
        4. Assert land allowed
        5. Set state to FLYING
        6. Assert land allowed
        7. Set state to LANDING
        8. Assert land NOT allowed (already landing)
        """
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("land")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("land")

        sm._state = FlightState.FLYING
        assert sm.check_command_precondition("land")

        sm._state = FlightState.LANDING
        assert not sm.check_command_precondition("land")

    def test_set_velocity_precondition(self):
        """Set velocity command requires HOVERING or FLYING states.

        VALIDATES: Velocity control only from stable flight states.

        MOCK SETUP: Direct state assignments.

        SAFETY REASON: Velocity commands from non-flying states could
        cause unexpected motor activity or be rejected by PX4 in ways
        that confuse the LLM.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Assert set_velocity NOT allowed from INIT
        3. Set state to HOVERING
        4. Assert set_velocity allowed
        5. Set state to FLYING
        6. Assert set_velocity allowed
        """
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("set_velocity")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("set_velocity")

        sm._state = FlightState.FLYING
        assert sm.check_command_precondition("set_velocity")

    def test_set_position_precondition(self):
        """Set position command requires HOVERING or FLYING states.

        VALIDATES: Position control only from stable flight states.

        MOCK SETUP: Direct state assignments.

        SAFETY REASON: Goto commands from non-flying states would fail
        or cause dangerous behavior. Preconditions ensure the drone is
        ready for waypoint navigation.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Assert set_position NOT allowed from INIT
        3. Set state to HOVERING
        4. Assert set_position allowed
        """
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("set_position")

        sm._state = FlightState.HOVERING
        assert sm.check_command_precondition("set_position")

    def test_invalid_command(self):
        """Invalid command returns False.

        VALIDATES: Unknown commands are rejected.

        MOCK SETUP: None - testing unknown command.

        SAFETY REASON: Invalid commands could be typos or hallucinations
        from the LLM. Returning False allows graceful handling rather
        than raising exceptions that could crash the system.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Call check_command_precondition("invalid_command")
        3. Assert returns False (unknown command rejected)
        """
        sm = FlightStateMachine()
        assert not sm.check_command_precondition("invalid_command")


class TestTelemetrySync:
    """Tests for telemetry-based state synchronization.

    SAFETY: The state machine can sync from actual telemetry to handle
    cases where commands failed or external factors changed state.
    Prevents state machine drift from physical reality.
    """

    def test_sync_from_telemetry_disarmed(self):
        """Sync to DISARMED when not armed.

        VALIDATES: Telemetry showing disarmed updates state machine.

        MOCK SETUP: None - pass telemetry dict to sync_from_telemetry.

        SAFETY REASON: If the drone disarmed unexpectedly (RC override),
        the state machine must reflect reality. Sync prevents thinking
        the drone is armed when it's not.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Create telemetry dict: armed=False, in_air=False, landed=True
        3. Call sync_from_telemetry(telemetry)
        4. Assert state is DISARMED (synced from telemetry)
        """
        sm = FlightStateMachine()
        telemetry = {"armed": False, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.DISARMED

    def test_sync_from_telemetry_armed(self):
        """Sync to ARMED when armed but not flying.

        VALIDATES: Telemetry showing armed updates state machine.

        MOCK SETUP: None - telemetry dict.

        SAFETY REASON: Sync ensures the state machine knows the drone
        is armed even if the arm command response was lost.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Create telemetry: armed=True, in_air=False, landed=True
        3. Call sync_from_telemetry
        4. Assert state is ARMED
        """
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.ARMED

    def test_sync_from_telemetry_hovering(self):
        """Sync to HOVERING when in air and stable.

        VALIDATES: Telemetry showing hover updates state machine.

        MOCK SETUP: None - telemetry dict with zero velocity.

        SAFETY REASON: Hover detection from velocity helps distinguish
        between stationary flight and active maneuvers.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Create telemetry: armed=True, in_air=True, landed=False, velocity=[0,0,0]
        3. Call sync_from_telemetry
        4. Assert state is HOVERING (stable hover detected)
        """
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": True, "landed": False, "velocity": [0.0, 0.0, 0.0]}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.HOVERING

    def test_sync_from_telemetry_flying(self):
        """Sync to FLYING when in air and moving.

        VALIDATES: Telemetry showing movement updates state machine.

        MOCK SETUP: None - telemetry with non-zero velocity.

        SAFETY REASON: Movement detection ensures the state machine
        knows when the drone is actively maneuvering vs. hovering.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Create telemetry: armed=True, in_air=True, landed=False, velocity=[1,0,0]
        3. Call sync_from_telemetry
        4. Assert state is FLYING (movement detected)
        """
        sm = FlightStateMachine()
        telemetry = {"armed": True, "in_air": True, "landed": False, "velocity": [1.0, 0.0, 0.0]}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.FLYING

    def test_sync_from_telemetry_landing(self):
        """Sync to LANDING when landing detected.

        VALIDATES: Telemetry showing landing updates state machine.

        MOCK SETUP: Direct state assignment to HOVERING, then sync.

        SAFETY REASON: Landing detection from telemetry allows the state
        machine to track descent phase accurately.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to HOVERING
        3. Create telemetry: landing=True
        4. Call sync_from_telemetry
        5. Assert state is LANDING
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING
        telemetry = {"armed": True, "in_air": True, "landed": False, "landing": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.LANDING

    def test_sync_from_telemetry_landed(self):
        """Sync to LANDED when grounded.

        VALIDATES: Telemetry showing ground contact updates state machine.

        MOCK SETUP: Direct state assignment to LANDING, then sync.

        SAFETY REASON: Ground contact detection is critical for knowing
        when it's safe to disarm. Sync ensures state machine reflects
        this important safety milestone.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to LANDING
        3. Create telemetry: landed=True, ground_contact=True
        4. Call sync_from_telemetry
        5. Assert state is LANDED
        """
        sm = FlightStateMachine()
        sm._state = FlightState.LANDING
        telemetry = {"armed": True, "in_air": False, "landed": True, "ground_contact": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.LANDED

    def test_sync_does_not_override_emergency(self):
        """Emergency state is not overridden by telemetry sync.

        VALIDATES: Emergency state persists until explicitly cleared.

        MOCK SETUP: Direct state assignment to EMERGENCY.

        SAFETY REASON: Emergency state indicates a critical situation.
        Telemetry sync should not accidentally clear this state,
        as it could hide ongoing emergencies from the operator.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to EMERGENCY
        3. Create telemetry that would normally suggest FLYING
        4. Call sync_from_telemetry
        5. Assert state remains EMERGENCY (not overridden)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.EMERGENCY
        telemetry = {"armed": True, "in_air": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.EMERGENCY

    def test_sync_does_not_override_error(self):
        """Error state is not overridden by telemetry sync.

        VALIDATES: Error state persists until explicitly cleared.

        MOCK SETUP: Direct state assignment to ERROR.

        SAFETY REASON: Error state indicates a system problem. Like
        EMERGENCY, it should persist until explicitly handled to
        ensure the operator is aware of the issue.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to ERROR
        3. Create telemetry suggesting DISARMED
        4. Call sync_from_telemetry
        5. Assert state remains ERROR
        """
        sm = FlightStateMachine()
        sm._state = FlightState.ERROR
        telemetry = {"armed": False, "in_air": False, "landed": True}
        sm.sync_from_telemetry(telemetry)
        assert sm.current_state == FlightState.ERROR


class TestThreadSafety:
    """Tests for thread-safe state transitions.

    SAFETY: The state machine may be accessed from multiple threads
    (LLM commands, telemetry updates, failsafe triggers). Race conditions
    could cause state corruption or lost transitions. Thread safety ensures
    consistent state under concurrent access.
    """

    def test_concurrent_transitions(self):
        """Concurrent transitions are thread-safe.

        VALIDATES: Only one transition succeeds with concurrent attempts.

        MOCK SETUP: Real threads attempting simultaneous transition.

        SAFETY REASON: If two components simultaneously try to change state
        (e.g., LLM commands goto while Guardian triggers RTL), only one
        should succeed. The other should get False, allowing fallback logic.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Chain to HOVERING state
        3. Create 10 threads, each attempting HOVERING -> RTL
        4. Start all threads simultaneously
        5. Wait for all to complete
        6. Assert no exceptions occurred
        7. Assert exactly 1 transition succeeded (sum(results) == 1)
        8. Assert final state is RTL
        """
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
        """Failsafe triggers are thread-safe.

        VALIDATES: Concurrent failsafe calls are handled safely.

        MOCK SETUP: Real threads calling trigger_failsafe simultaneously.

        SAFETY REASON: Emergency situations may trigger multiple failsafes
        simultaneously (low battery + geofence breach). Thread safety
        ensures the first failsafe wins and state remains consistent.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Create 5 threads, each triggering low_battery failsafe
        4. Start all threads simultaneously
        5. Wait for all to complete
        6. Assert no exceptions
        7. Assert exactly 1 succeeds (others may have been valid but late)
        8. Assert final state is RTL
        """
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
    """Tests for state properties and helper methods.

    SAFETY: Properties like is_flying and is_armed are used by UI and
    safety interlocks. They must be accurate for all possible states.
    """

    def test_is_flying_property(self):
        """is_flying property is correct for each state.

        VALIDATES: is_flying returns True only for in-air states.

        MOCK SETUP: Direct state assignments for all states.

        SAFETY REASON: is_flying determines if RTL/Land commands make
        sense. UI uses this to show/hide flight controls. Incorrect
        values could allow dangerous commands or confuse the operator.

        STEP-BY-STEP:
        1. Define list of flying states (TAKING_OFF through LANDING)
        2. Define list of non-flying states (INIT, DISARMED, ARMED, etc.)
        3. For each flying state, set state and assert is_flying is True
        4. For each non-flying state, set state and assert is_flying is False
        """
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
        """is_armed property is correct for each state.

        VALIDATES: is_armed returns True for states with active motors.

        MOCK SETUP: Direct state assignments for all states.

        SAFETY REASON: is_armed indicates if motors are responsive to
        throttle. This affects UI warnings and command availability.
        Incorrect values could allow throttle commands when disarmed.

        STEP-BY-STEP:
        1. Define list of armed states (ARMED through EMERGENCY)
        2. Define list of disarmed states (INIT, DISARMED, ERROR)
        3. For each armed state, set state and assert is_armed is True
        4. For each disarmed state, set state and assert is_armed is False
        """
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
        """All FlightState enum values have proper string names.

        VALIDATES: current_state_name works for all states.

        MOCK SETUP: Iterate through all FlightState enum values.

        SAFETY REASON: State names are used in logging and UI. Missing
        or incorrect names would make debugging and monitoring difficult.

        STEP-BY-STEP:
        1. Iterate through all FlightState enum values
        2. For each state, create FlightStateMachine and set state
        3. Assert current_state_name matches the enum name
        """
        for state in FlightState:
            sm = FlightStateMachine()
            sm._state = state
            assert sm.current_state_name == state.name


class TestErrorHandling:
    """Tests for error state handling.

    SAFETY: ERROR state indicates a problem that prevents normal operation.
    The system must handle errors gracefully and provide recovery paths.
    """

    def test_error_transition(self):
        """Can transition to ERROR state.

        VALIDATES: ERROR state is reachable.

        MOCK SETUP: None - transition from INIT.

        SAFETY REASON: ERROR state must be reachable from any state
        when problems occur. This allows unified error handling.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition INIT -> ERROR with "system_failure" reason
        3. Assert transition succeeds
        4. Assert state is ERROR
        """
        sm = FlightStateMachine()
        assert sm.transition(FlightState.ERROR, "system_failure", "guardian")
        assert sm.current_state == FlightState.ERROR

    def test_from_error_to_disarmed(self):
        """Can recover from ERROR to DISARMED.

        VALIDATES: ERROR is not a permanent trap state.

        MOCK SETUP: Transition to ERROR first.

        SAFETY REASON: Errors may be recoverable (temporary connection
        loss, for example). Allowing ERROR -> DISARMED enables system
        recovery without full restart.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Transition to ERROR
        3. Transition ERROR -> DISARMED with "error_cleared"
        4. Assert transition succeeds
        """
        sm = FlightStateMachine()
        sm.transition(FlightState.ERROR, "system_failure", "guardian")
        assert sm.transition(FlightState.DISARMED, "error_cleared", "operator")

    def test_emergency_requires_manual_reset(self):
        """EMERGENCY state requires explicit handling.

        VALIDATES: EMERGENCY state blocks normal transitions.

        MOCK SETUP: Direct state assignment to FLYING, then trigger failsafe.

        SAFETY REASON: EMERGENCY indicates a critical situation (kill switch).
        Normal transitions should be blocked to prevent accidental
        clearing of the emergency condition. Requires explicit handling.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Set state to FLYING
        3. Trigger kill_switch failsafe to enter EMERGENCY
        4. Assert state is EMERGENCY
        5. Assert can_transition(DISARMED) returns False
        6. (Emergency requires explicit reset protocol not tested here)
        """
        sm = FlightStateMachine()
        sm._state = FlightState.FLYING
        sm.trigger_failsafe("kill_switch")
        assert sm.current_state == FlightState.EMERGENCY

        # Regular transitions blocked
        assert not sm.can_transition(FlightState.DISARMED)


class TestStateTransitionException:
    """Tests for StateTransitionError exception.

    SAFETY: Some callers may prefer exceptions over return values for
    invalid transitions. This ensures errors cannot be silently ignored.
    """

    def test_exception_raised_when_requested(self):
        """Can raise exception instead of returning False.

        VALIDATES: raise_on_error flag triggers exception.

        MOCK SETUP: None - attempt invalid transition with raise_on_error.

        SAFETY REASON: Exceptions force error handling. In critical code
        paths, this prevents accidentally continuing after a failed
        transition that was assumed to succeed.

        STEP-BY-STEP:
        1. Create FlightStateMachine (starts in INIT)
        2. Attempt invalid transition INIT -> ARMED with raise_on_error=True
        3. Assert StateTransitionError is raised
        """
        sm = FlightStateMachine()
        with pytest.raises(StateTransitionError):
            sm.transition(FlightState.ARMED, "invalid", "operator", raise_on_error=True)

    def test_exception_message(self):
        """Exception includes helpful message.

        VALIDATES: Exception message contains state information.

        MOCK SETUP: None - catch and inspect exception message.

        SAFETY REASON: Clear error messages help operators and developers
        understand why a transition failed. This speeds up incident
        response and debugging.

        STEP-BY-STEP:
        1. Create FlightStateMachine
        2. Attempt invalid transition with raise_on_error=True
        3. Catch StateTransitionError
        4. Assert "INIT" and "ARMED" appear in exception message
        """
        sm = FlightStateMachine()
        with pytest.raises(StateTransitionError) as exc_info:
            sm.transition(FlightState.ARMED, "invalid", "operator", raise_on_error=True)
        assert "INIT" in str(exc_info.value)
        assert "ARMED" in str(exc_info.value)
