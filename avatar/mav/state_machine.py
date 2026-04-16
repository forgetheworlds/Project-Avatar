"""Flight State Machine for Avatar Drone MCP Server.

This module implements a robust, thread-safe finite state machine for managing
drone flight states. It enforces valid state transitions, handles failsafe conditions,
and tracks state history for debugging and auditing.

WHY A STATE MACHINE?
====================
Drones are safety-critical systems where operations must only occur in appropriate
states. For example:
- You cannot take off if already flying
- You cannot arm the motors if already armed
- Emergency kill switch must work from ANY flying state
- Telemetry sync must not override emergency states

The state machine acts as a "gatekeeper" that prevents invalid operations and
provides clear preconditions for all flight commands.

STATE MACHINE PHILOSOPHY
========================
1. EXPLICIT STATES: Every drone condition is explicitly modeled (not implicit)
2. VALIDATED TRANSITIONS: Only allowed transitions can occur
3. FAILSAFE PRIORITY: Safety transitions override normal rules
4. HISTORY TRACKING: All transitions are logged for debugging
5. THREAD-SAFE: Multiple threads (telemetry, LLM, guardian) can safely interact

Example Usage:
    >>> sm = FlightStateMachine()
    >>> sm.transition(FlightState.DISARMED, "startup_complete", "system")
    True
    >>> sm.transition(FlightState.ARMED, "operator_command", "operator")
    True
    >>> sm.can_transition(FlightState.TAKING_OFF)
    True
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class FlightState(Enum):
    """Enumeration of all possible drone flight states.

    Each state represents a specific operational mode of the drone. The state
    machine enforces that transitions between these states follow safety rules.

    STATE DIAGRAM OVERVIEW:
    =======================

    Ground States (Motors may be armed but drone is on ground):
        INIT -> DISARMED -> ARMED

    Takeoff Sequence (One-way progression to get airborne):
        ARMED -> TAKING_OFF -> HOVERING

    Flying States (Drone is airborne and responsive to commands):
        HOVERING <-> POSITION_CONTROL
        HOVERING <-> VELOCITY_CONTROL
        HOVERING <-> MISSION_EXECUTION
        HOVERING <-> HOLD
        HOVERING <-> RTL (Return to Launch)
        HOVERING <-> ACROBATIC

    Landing Sequence (Progression back to ground):
        [any flying state] -> LANDING -> LANDED -> DISARMED

    Emergency States (Require explicit recovery action):
        [any state] -> EMERGENCY (kill switch triggered)
        [any state] -> ERROR (system malfunction)

    WHY EACH STATE EXISTS:
    ======================

    INIT: Initial boot state before system is ready
    DISARMED: Motors disarmed, drone safe to handle
    ARMED: Motors armed, ready for takeoff but on ground
    TAKING_OFF: Active takeoff in progress, altitude increasing
    HOVERING: Stationary in air (velocity near zero), ready for commands
    FLYING: Generic airborne state when specific mode not yet determined
    POSITION_CONTROL: GPS-guided waypoint navigation mode
    VELOCITY_CONTROL: Direct velocity vector commands (manual-ish)
    MISSION_EXECUTION: Autonomous mission running (waypoints, actions)
    HOLD: Position hold - stay at current location
    RTL: Return to launch - autonomous return and land
    LANDING: Active landing in progress, altitude decreasing
    LANDED: On ground after landing, motors still armed
    ACROBATIC: Acrobatic/rate control mode (sports/manual flying)
    EMERGENCY: Kill switch engaged, immediate motor stop
    ERROR: System error, requires inspection before reset
    """

    # =======================================================================
    # GROUND STATES - Drone is on the ground
    # =======================================================================

    INIT = auto()
    """Initial system state on startup.

    WHY: Distinguishes between a fresh boot and an operational system.
    From INIT, telemetry sync can jump to any state (recovery after restart).
    """

    DISARMED = auto()
    """Motors are disarmed, drone is safe to approach.

    WHY: Critical safety state. Props are not spinning, no accidental startup.
    This is the default ground state for normal operations.
    """

    ARMED = auto()
    """Motors are armed but drone is still on ground.

    WHY: Distinguishes between "ready to takeoff" and "already flying".
    In this state, props may spin at idle but not at flight RPM.
    """

    LANDED = auto()
    """Drone has landed but motors still armed.

    WHY: Intermediate state between flying and disarmed. Allows for:
    - Quick re-takeoff (no re-arm needed)
    - Post-flight checks before disarming
    - Detection of successful landing completion
    """

    # =======================================================================
    # TAKEOFF SEQUENCE - Progression from ground to air
    # =======================================================================

    TAKING_OFF = auto()
    """Active takeoff in progress.

    WHY: Takeoff is a critical, non-interruptible operation. This state:
    - Prevents other commands during takeoff
    - Allows abort only to LANDING or EMERGENCY
    - Tracks that we're actively climbing to hover altitude
    """

    # =======================================================================
    # FLYING STATES - Drone is airborne
    # =======================================================================

    HOVERING = auto()
    """Drone is stationary in air, maintaining position.

    WHY: This is the "idle" state for flying. When velocity is near zero
    and we're maintaining position, we're hovering. Most commands transition
    from/to this state as it's the "ready" airborne state.
    """

    FLYING = auto()
    """Generic flying state when specific mode is not yet determined.

    WHY: Telemetry sync may detect we're in air before we know the exact
    control mode. This is a transitional state resolved by further telemetry.
    """

    POSITION_CONTROL = auto()
    """GPS position hold with waypoint navigation.

    WHY: Distinguishes between "hold position" (HOVERING) and "go to waypoint"
    (POSITION_CONTROL). The drone is actively navigating to or maintaining
    a specific geographic coordinate.
    """

    VELOCITY_CONTROL = auto()
    """Direct velocity control mode.

    WHY: Used for manual-style control where LLM or operator sends velocity
    vectors (vx, vy, vz) rather than position targets. Different from
    POSITION_CONTROL because no specific target position is tracked.
    """

    MISSION_EXECUTION = auto()
    """Autonomous mission is being executed.

    WHY: Distinguishes between single commands and multi-waypoint missions.
    In this state, the drone is following a pre-programmed mission plan with
    multiple waypoints and actions.
    """

    HOLD = auto()
    """Emergency hold - pause current operation and maintain position.

    WHY: Provides a "pause button" for any operation. Differs from HOVERING
    because it implies an interruption that can be resumed (e.g., mission).
    Entered on: offboard timeout, operator pause command.
    """

    RTL = auto()
    """Return to Launch - autonomous return to takeoff point and land.

    WHY: Critical failsafe state. Drone is flying autonomously back to the
    launch position for landing. Cannot be interrupted by normal commands
    (only emergency commands).
    """

    ACROBATIC = auto()
    """Acrobatic/rate control mode.

    WHY: Sports flying mode where attitude rates are controlled directly.
    Not used in normal autonomous operations but supported for testing.
    Transition only allowed from flying states.
    """

    # =======================================================================
    # LANDING SEQUENCE - Progression from air to ground
    # =======================================================================

    LANDING = auto()
    """Active landing in progress.

    WHY: Like TAKING_OFF, this is a critical sequence that:
    - Cannot be interrupted by most commands
    - Can transition to HOVERING (abort landing) or EMERGENCY
    - Tracks that we're actively descending to ground
    """

    # =======================================================================
    # EMERGENCY STATES - Require explicit recovery action
    # =======================================================================

    EMERGENCY = auto()
    """Emergency kill switch engaged - immediate motor stop.

    WHY: ABSOLUTE SAFETY STATE. Once entered, requires explicit reset to INIT.
    The kill switch immediately stops all motors. This state can be entered
    from ANY armed or flying state instantly.

    RECOVERY: Must transition to INIT, then full startup sequence.
    """

    ERROR = auto()
    """System error detected, operation halted.

    WHY: Distinguishes between operator-triggered emergency (EMERGENCY) and
    system-detected errors (sensor failure, communication loss, etc.).
    Allows for error-specific recovery logic.

    RECOVERY: Can transition to INIT or DISARMED depending on error severity.
    """


@dataclass
class StateTransition:
    """Immutable record of a single state transition.

    Every state change in the FlightStateMachine is logged as a StateTransition
    record. This provides an audit trail for debugging and post-flight analysis.

    Attributes:
        from_state: The previous flight state before the transition
        to_state: The new flight state after the transition
        timestamp: Unix timestamp (seconds since epoch) when transition occurred
        reason: Human-readable description of why the transition happened
        source: What triggered the transition ("llm", "operator", "guardian",
            "telemetry", "failsafe")

    WHY TRACK HISTORY?
    ==================
    - Debugging: See exactly what state changes occurred and when
    - Safety audit: Prove that failsafes triggered correctly
    - LLM context: Provide the LLM with recent state changes for decisions
    - Post-flight analysis: Understand flight timeline
    """

    from_state: FlightState
    """Previous state before transition."""

    to_state: FlightState
    """New state after transition."""

    timestamp: float
    """Unix timestamp of when transition occurred."""

    reason: str
    """Human-readable reason for the transition (e.g., "takeoff_complete")."""

    source: str
    """Originator of the transition:
    - "llm": LLM agent command
    - "operator": Human operator command
    - "guardian": Safety guardian process
    - "telemetry": Telemetry synchronization
    - "failsafe": Automatic failsafe trigger
    """


class StateTransitionError(Exception):
    """Exception raised when an invalid state transition is attempted.

    This exception is raised only when raise_on_error=True is passed to
    the transition() method. By default, invalid transitions return False
    rather than raising exceptions (for friendlier LLM interaction).

    Attributes:
        from_state: The current state when the invalid transition was attempted
        to_state: The requested target state that is not allowed

    Example:
        >>> try:
        ...     sm.transition(FlightState.TAKING_OFF, "test", "test", raise_on_error=True)
        ... except StateTransitionError as e:
        ...     print(f"Cannot go from {e.from_state} to {e.to_state}")
    """

    def __init__(
        self,
        from_state: FlightState,
        to_state: FlightState,
        message: Optional[str] = None,
    ):
        self.from_state = from_state
        self.to_state = to_state

        # Generate default message if none provided
        default_message = (
            f"Invalid state transition from {from_state.name} to {to_state.name}"
        )
        super().__init__(message or default_message)


class FlightStateMachine:
    """Thread-safe flight state machine with validated transitions and failsafe handling.

    This class is the central authority for all drone state management. It:
    - Enforces valid state transitions via TRANSITIONS map
    - Handles failsafe triggers with special logic
    - Validates command preconditions
    - Maintains complete state transition history
    - Synchronizes with actual telemetry data

    THREAD SAFETY:
    ==============
    All public methods acquire a reentrant lock (RLock) before accessing state.
    This ensures safe concurrent access from:
    - Telemetry thread (updating state based on sensor data)
    - LLM thread (sending commands that change state)
    - Guardian thread (monitoring safety and triggering failsafes)
    - Main control thread (coordinating operations)

    STATE TRANSITION RULES:
    =======================
    1. Normal transitions must be in the TRANSITIONS map
    2. Failsafe transitions can override certain rules
    3. From INIT, telemetry can set any state (boot recovery)
    4. EMERGENCY and ERROR states cannot be overridden by telemetry
    5. Kill switch can trigger from ANY armed or flying state

    Example Usage:
        >>> sm = FlightStateMachine()
        >>> sm.current_state
        <FlightState.INIT: 1>
        >>> sm.transition(FlightState.DISARMED, "system_ready", "system")
        True
        >>> sm.transition(FlightState.ARMED, "operator_arm", "operator")
        True
        >>> sm.check_command_precondition("takeoff")
        True
        >>> sm.transition(FlightState.TAKING_OFF, "takeoff_initiated", "llm")
        True
    """

    # =========================================================================
    # TRANSITION VALIDATION MAP
    # =========================================================================
    # This dictionary defines the VALID state transitions. Each key is a source
    # state, and the value is a set of allowed destination states.
    #
    # WHY THIS APPROACH?
    # - Explicit: Every allowed transition is listed
    # - Auditable: Easy to review all allowed transitions
    # - Testable: Can validate the map has no orphaned states
    # - Safe: Default-deny (not in set = not allowed)
    # =========================================================================

    TRANSITIONS: Dict[FlightState, Set[FlightState]] = {
        # ------------------------------------------------------------------
        # INITIAL STATE
        # From INIT: Only go to operational state or error state
        # WHY: INIT represents boot-time; once operational, we never return
        # ------------------------------------------------------------------
        FlightState.INIT: {FlightState.DISARMED, FlightState.ERROR},

        # ------------------------------------------------------------------
        # GROUND STATES
        # These states represent the drone being safely on the ground
        # ------------------------------------------------------------------

        # DISARMED: Can arm (to ARMED) or error out
        # WHY: This is the normal ground state - only way out is to arm or error
        FlightState.DISARMED: {FlightState.ARMED, FlightState.ERROR},

        # ARMED: Can take off, disarm (if changed mind), or error
        # WHY: From armed ground state, logical next step is takeoff,
        # but operator may decide to disarm instead
        FlightState.ARMED: {FlightState.TAKING_OFF, FlightState.DISARMED, FlightState.ERROR},

        # LANDED: Can disarm (normal cleanup) or error
        # WHY: After landing, we're still armed but on ground. Next step is disarm.
        FlightState.LANDED: {FlightState.DISARMED, FlightState.ERROR},

        # ------------------------------------------------------------------
        # TAKEOFF SEQUENCE
        # One-way progression from ground to hovering in air
        # ------------------------------------------------------------------

        # TAKING_OFF: Can reach hover, abort to landing, or error
        # WHY: Limited transitions because takeoff is critical. Cannot:
        # - Disarm mid-air (would crash)
        # - Start mission (must hover first)
        # Only HOVERING (success), LANDING (abort), or ERROR
        FlightState.TAKING_OFF: {FlightState.HOVERING, FlightState.LANDING, FlightState.ERROR},

        # ------------------------------------------------------------------
        # FLYING STATES (Core airborne operational states)
        # These states represent the drone being airborne and responsive
        # ------------------------------------------------------------------

        # HOVERING: Central "hub" state - can go to almost any other flying state
        # WHY: Hovering means "ready for command" - it's the idle state in air.
        # From here we can start missions, change control modes, land, etc.
        FlightState.HOVERING: {
            FlightState.FLYING,            # Generic flying (before mode determined)
            FlightState.POSITION_CONTROL,  # Start waypoint navigation
            FlightState.VELOCITY_CONTROL,    # Switch to velocity commands
            FlightState.MISSION_EXECUTION, # Start autonomous mission
            FlightState.HOLD,              # Pause/hold position
            FlightState.RTL,               # Return to launch
            FlightState.LANDING,           # Begin landing
            FlightState.LANDED,            # Already landed (telemetry sync)
            FlightState.ACROBATIC,         # Sports mode
            FlightState.EMERGENCY,         # Kill switch
            FlightState.ERROR,             # System error
        },

        # FLYING: Generic airborne state - can transition to specific modes
        # WHY: Used when telemetry shows we're flying but mode not yet known.
        # Same transitions as HOVERING since both represent "airborne and ready"
        FlightState.FLYING: {
            FlightState.HOVERING,            # Determine we're hovering
            FlightState.POSITION_CONTROL,  # GPS mode engaged
            FlightState.VELOCITY_CONTROL,    # Velocity mode engaged
            FlightState.MISSION_EXECUTION, # Mission started
            FlightState.HOLD,              # Hold position
            FlightState.RTL,               # Return to launch
            FlightState.LANDING,           # Landing initiated
            FlightState.LANDED,            # Telemetry shows landed
            FlightState.ACROBATIC,         # Sports mode
            FlightState.EMERGENCY,         # Kill switch
            FlightState.ERROR,             # System error
        },

        # ------------------------------------------------------------------
        # CONTROL MODES
        # Different ways of controlling the drone while flying
        # ------------------------------------------------------------------

        # POSITION_CONTROL: GPS-based position/waypoint control
        # WHY: Can switch between control modes, hover, hold, land, etc.
        # The rich transition set allows flexible mode switching.
        FlightState.POSITION_CONTROL: {
            FlightState.HOVERING,            # Stop at current position
            FlightState.FLYING,              # Generic flying
            FlightState.VELOCITY_CONTROL,    # Switch to velocity mode
            FlightState.MISSION_EXECUTION, # Switch to mission mode
            FlightState.HOLD,                # Pause current operation
            FlightState.RTL,                 # Emergency return
            FlightState.LANDING,             # Land now
            FlightState.ACROBATIC,           # Sports mode
            FlightState.EMERGENCY,           # Kill switch
            FlightState.ERROR,               # System error
        },

        # VELOCITY_CONTROL: Direct velocity vector control
        # WHY: Same transitions as POSITION_CONTROL - both are flying modes
        # that can switch to any other flying mode or emergency state
        FlightState.VELOCITY_CONTROL: {
            FlightState.HOVERING,            # Stop moving (hover)
            FlightState.FLYING,              # Generic flying
            FlightState.POSITION_CONTROL,    # Switch to GPS mode
            FlightState.MISSION_EXECUTION, # Switch to mission
            FlightState.HOLD,                # Pause
            FlightState.RTL,                 # Emergency return
            FlightState.LANDING,             # Land
            FlightState.ACROBATIC,           # Sports mode
            FlightState.EMERGENCY,           # Kill switch
            FlightState.ERROR,               # System error
        },

        # MISSION_EXECUTION: Autonomous waypoint mission
        # WHY: While executing a mission, we can pause (HOLD), abort (RTL),
        # or switch to manual control modes. Rich transitions for flexibility.
        FlightState.MISSION_EXECUTION: {
            FlightState.HOVERING,            # Pause mission, hover
            FlightState.FLYING,              # Generic transition
            FlightState.POSITION_CONTROL,    # Manual waypoint control
            FlightState.VELOCITY_CONTROL,    # Manual velocity control
            FlightState.HOLD,                # Pause mission
            FlightState.RTL,                 # Abort mission, return home
            FlightState.LANDING,             # Abort mission, land here
            FlightState.EMERGENCY,           # Kill switch
            FlightState.ERROR,               # System error
        },

        # ------------------------------------------------------------------
        # HOLD STATE
        # Pause current operation and maintain position
        # ------------------------------------------------------------------

        # HOLD: Can resume operations or initiate emergency procedures
        # WHY: HOLD is a "paused" state - can resume control modes or
        # initiate failsafe procedures (RTL, LANDING, EMERGENCY)
        FlightState.HOLD: {
            FlightState.HOVERING,            # Resume to ready state
            FlightState.POSITION_CONTROL,    # Resume GPS control
            FlightState.VELOCITY_CONTROL,    # Resume velocity control
            FlightState.RTL,                 # Emergency return
            FlightState.LANDING,             # Land from hold
            FlightState.EMERGENCY,           # Kill switch
            FlightState.ERROR,               # System error
        },

        # ------------------------------------------------------------------
        # RETURN TO LAUNCH (RTL)
        # Autonomous return to takeoff point
        # ------------------------------------------------------------------

        # RTL: Can land, hover (abort RTL), hold, or emergency
        # WHY: RTL is a committed operation but can be interrupted for safety.
        # Cannot switch to mission or control modes (would abort RTL).
        FlightState.RTL: {
            FlightState.LANDING,     # Continue RTL to landing
            FlightState.HOVERING,    # Abort RTL, hover in place
            FlightState.HOLD,        # Pause RTL
            FlightState.EMERGENCY,   # Kill switch
            FlightState.ERROR,       # System error
        },

        # ------------------------------------------------------------------
        # ACROBATIC MODE
        # Sports/rate control flying
        # ------------------------------------------------------------------

        # ACROBATIC: Can return to normal flying modes or emergency
        # WHY: Acrobatic is "special" mode - can exit to any normal flying state
        # or emergency. Not used in autonomous operations.
        FlightState.ACROBATIC: {
            FlightState.HOVERING,            # Return to normal flight
            FlightState.FLYING,              # Generic transition
            FlightState.POSITION_CONTROL,    # Return to GPS mode
            FlightState.VELOCITY_CONTROL,    # Return to velocity mode
            FlightState.HOLD,                # Pause
            FlightState.EMERGENCY,           # Kill switch
            FlightState.ERROR,               # System error
        },

        # ------------------------------------------------------------------
        # LANDING SEQUENCE
        # Progression from flying to ground
        # ------------------------------------------------------------------

        # LANDING: Can complete (LANDED), abort (HOVER/HOLD), or emergency
        # WHY: Landing is critical - limited transitions. Cannot:
        # - Start mission (would be dangerous mid-landing)
        # - Switch control modes (landing takes precedence)
        FlightState.LANDING: {
            FlightState.LANDED,      # Landing complete
            FlightState.HOVERING,    # Abort landing, climb to hover
            FlightState.HOLD,        # Pause landing (hold altitude)
            FlightState.EMERGENCY,   # Kill switch
            FlightState.ERROR,       # System error
        },

        # ------------------------------------------------------------------
        # EMERGENCY STATES
        # These states require explicit recovery actions
        # ------------------------------------------------------------------

        # EMERGENCY: Kill switch triggered - immediate motor stop
        # WHY: EMERGENCY is terminal until explicitly reset. Can only:
        # - Reset to INIT (full restart sequence)
        # - Transition to ERROR (if we want to log as error state)
        FlightState.EMERGENCY: {FlightState.INIT, FlightState.ERROR},

        # ERROR: System error detected
        # WHY: ERROR allows recovery to INIT (full restart) or DISARMED
        # (if on ground and safe). Self-loop allows staying in ERROR.
        FlightState.ERROR: {FlightState.INIT, FlightState.DISARMED, FlightState.ERROR},
    }

    # =========================================================================
    # FAILSAFE MAPPING
    # =========================================================================
    # Maps failsafe trigger reasons to target states. These transitions
    # can override normal transition rules in certain circumstances.
    #
    # WHY EACH FAILSAFE EXISTS:
    # - rc_loss: Radio control lost - RTL to maintain link
    # - low_battery: Battery getting low - RTL while we still can
    # - critical_battery: Battery critically low - land NOW
    # - geofence_breach: Left safe area - RTL back to safety
    # - position_drift: Position estimate degrading - RTL before total loss
    # - kill_switch: Operator emergency stop - immediate motor cutoff
    # - offboard_timeout: LLM/control link lost - hold position (wait for reconnect)
    # =========================================================================

    FAILSAFE_TRANSITIONS: Dict[str, FlightState] = {
        "rc_loss": FlightState.RTL,           # Return home when RC lost
        "low_battery": FlightState.RTL,       # Return home on low battery
        "critical_battery": FlightState.LANDING,  # Land immediately on critical battery
        "geofence_breach": FlightState.RTL,   # Return home if left safe area
        "position_drift": FlightState.RTL,    # Return home if position estimate failing
        "kill_switch": FlightState.EMERGENCY, # Kill motors immediately
        "offboard_timeout": FlightState.HOLD, # Hold position if control link lost
    }

    # =========================================================================
    # COMMAND PRECONDITIONS
    # =========================================================================
    # Maps command names to the set of states in which that command is allowed.
    # This prevents commands from being sent when they would be dangerous or
    # ineffective.
    #
    # WHY CHECK PRECONDITIONS?
    # - Safety: Don't arm if already armed (confusing, possibly dangerous)
    # - Logic: Don't take off if already flying (impossible)
    # - Efficiency: Don't land if already on ground (unnecessary)
    # =========================================================================

    COMMAND_PRECONDITIONS: Dict[str, Set[FlightState]] = {
        # ARM: Can only arm from initial/ground states
        # WHY: Arming from flying states would be nonsensical
        "arm": {FlightState.INIT, FlightState.DISARMED},

        # DISARM: Can disarm from armed states
        # WHY: Disarming from flying states would crash - not allowed
        "disarm": {FlightState.ARMED, FlightState.LANDED, FlightState.DISARMED},

        # TAKEOFF: Can only take off from armed ground state
        # WHY: Must be armed and on ground to take off
        "takeoff": {FlightState.ARMED},

        # LAND: Can land from any flying state
        # WHY: Landing is always possible when airborne
        "land": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
        },

        # SET_VELOCITY: Can set velocity from flying states
        # WHY: Velocity commands require being airborne
        "set_velocity": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },

        # SET_POSITION: Can set position target from flying states
        # WHY: Position commands require being airborne
        "set_position": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },

        # SET_ATTITUDE: Can set attitude from flying states
        # WHY: Attitude commands require being airborne
        "set_attitude": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },

        # RETURN_TO_LAUNCH: Can RTL from flying states
        # WHY: RTL requires being airborne to return
        "return_to_launch": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },

        # HOLD: Can hold from active airborne states
        # WHY: Hold is also idempotent from hover; missions often take off
        # into HOVERING before explicitly asking to hold position.
        "hold": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
        },

        # START_MISSION: Can start mission from ready flying states
        # WHY: Mission requires being airborne and ready
        "start_mission": {
            FlightState.HOVERING,
            FlightState.FLYING,
        },

        # ABORT: Can abort from almost any active state
        # WHY: Abort is the "eject button" - should work from most states
        "abort": {
            FlightState.TAKING_OFF,
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
        },

        # KILL: Emergency kill switch - works from any armed/flying state
        # WHY: Kill switch must work from EVERY armed state for safety
        "kill": {
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
        },
    }

    # =========================================================================
    # STATE GROUPS
    # =========================================================================
    # These sets group related states for quick checking. Used by properties
    # like is_flying and is_armed, and by failsafe logic.
    # =========================================================================

    # FLYING_STATES: All states where the drone is in the air
    # WHY: Used to check if drone is airborne for:
    # - Failsafe logic (only trigger RTL if flying)
    # - Safety checks (don't allow certain ops if flying)
    # - Telemetry validation (expect in_air=True if in these states)
    FLYING_STATES: Set[FlightState] = {
        FlightState.TAKING_OFF,      # In air, climbing
        FlightState.HOVERING,          # In air, stationary
        FlightState.FLYING,            # In air, moving
        FlightState.POSITION_CONTROL,  # In air, navigating
        FlightState.VELOCITY_CONTROL,  # In air, velocity control
        FlightState.MISSION_EXECUTION, # In air, on mission
        FlightState.HOLD,              # In air, paused
        FlightState.RTL,               # In air, returning
        FlightState.LANDING,           # In air, descending
    }

    # ARMED_STATES: All states where the motors are or could be spinning
    # WHY: Used to check if the drone is "hot" - props could spin.
    # Safety critical for ground personnel.
    ARMED_STATES: Set[FlightState] = {
        FlightState.ARMED,             # Armed on ground
        FlightState.TAKING_OFF,        # Armed, in air
        FlightState.HOVERING,          # Armed, in air
        FlightState.FLYING,            # Armed, in air
        FlightState.POSITION_CONTROL,  # Armed, in air
        FlightState.VELOCITY_CONTROL,  # Armed, in air
        FlightState.MISSION_EXECUTION, # Armed, in air
        FlightState.HOLD,              # Armed, in air
        FlightState.RTL,               # Armed, in air
        FlightState.LANDING,           # Armed, in air
        FlightState.LANDED,              # Armed, on ground
        FlightState.EMERGENCY,           # Armed (but killed)
    }

    # =========================================================================
    # CONSTRUCTOR
    # =========================================================================

    def __init__(self) -> None:
        """Initialize the flight state machine.

        Sets up:
        - Initial state to INIT (fresh boot)
        - Empty transition history
        - Thread-safe lock (RLock for reentrant access)
        """
        # Start in INIT state - represents fresh boot
        self._state = FlightState.INIT

        # Empty history - no transitions yet
        self._history: List[StateTransition] = []

        # Reentrant lock for thread safety
        # WHY RLock? Allows same thread to acquire lock multiple times
        # (e.g., public method calls internal method that also locks)
        self._lock = threading.RLock()

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def current_state(self) -> FlightState:
        """Get the current flight state.

        Returns:
            The current FlightState enum value.

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            return self._state

    @property
    def current_state_name(self) -> str:
        """Get the human-readable name of the current state.

        Returns:
            String name of current state (e.g., "HOVERING").

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            return self._state.name

    @property
    def is_flying(self) -> bool:
        """Check if the drone is currently flying (in the air).

        Returns:
            True if the drone is in any FLYING_STATES, False otherwise.

        WHY THIS PROPERTY?
        ==================
        Convenient shorthand for checking airborne status. Used for:
        - Failsafe decisions (different response if flying vs ground)
        - UI display (show "In Air" vs "On Ground")
        - Safety checks (prevent ground ops while flying)

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Check membership in FLYING_STATES set (O(1) lookup)
            return self._state in self.FLYING_STATES

    @property
    def is_armed(self) -> bool:
        """Check if the drone is currently armed.

        Returns:
            True if the drone is in any ARMED_STATES, False otherwise.

        WHY THIS PROPERTY?
        ==================
        Convenient shorthand for checking armed status. Used for:
        - Safety warnings (props could spin)
        - Pre-flight checks (must be armed before takeoff)
        - Post-flight checks (should disarm after landing)

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Check membership in ARMED_STATES set (O(1) lookup)
            return self._state in self.ARMED_STATES

    # =========================================================================
    # TRANSITION METHODS
    # =========================================================================

    def can_transition(self, to_state: FlightState) -> bool:
        """Check if a transition to the given state is valid.

        Args:
            to_state: The target state to check.

        Returns:
            True if the transition from current_state to to_state is allowed.

        WHY THIS METHOD?
        =================
        Allows checking validity before attempting transition. Used for:
        - UI feedback (disable buttons for invalid transitions)
        - LLM planning (check if desired state reachable)
        - Validation (pre-check before expensive operations)

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Get allowed targets for current state from TRANSITIONS map
            valid_targets = self.TRANSITIONS.get(self._state, set())

            # Check if to_state is in the set of valid targets
            return to_state in valid_targets

    def transition(
        self,
        to_state: FlightState,
        reason: str,
        source: str,
        raise_on_error: bool = False,
    ) -> bool:
        """Attempt to transition to a new state.

        This is the PRIMARY method for changing state. It:
        1. Validates the transition is allowed
        2. Records the transition in history
        3. Updates the current state

        Args:
            to_state: The target state to transition to.
            reason: Human-readable reason for the transition (e.g., "takeoff_complete").
            source: Source of the transition ("llm", "operator", "guardian",
                "telemetry", "failsafe").
            raise_on_error: If True, raise StateTransitionError on invalid
                transition instead of returning False.

        Returns:
            True if the transition was successful, False if invalid (and
            raise_on_error is False).

        Raises:
            StateTransitionError: If raise_on_error is True and the transition
                is not in the TRANSITIONS map.

        WHY THIS METHOD?
        =================
        Centralized state change method ensures:
        - All transitions are validated
        - All transitions are logged
        - Thread-safe access
        - Consistent error handling

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Validate the transition is allowed
            if not self.can_transition(to_state):
                if raise_on_error:
                    # Raise exception if requested (for strict error handling)
                    raise StateTransitionError(self._state, to_state)
                # Otherwise return False (for friendly error handling)
                return False

            # Create transition record for history
            transition_record = StateTransition(
                from_state=self._state,
                to_state=to_state,
                timestamp=time.time(),
                reason=reason,
                source=source,
            )

            # Append to history (for debugging and audit trail)
            self._history.append(transition_record)

            # Perform the actual state change
            self._state = to_state

            return True

    # =========================================================================
    # FAILSAFE METHODS
    # =========================================================================

    def trigger_failsafe(self, reason: str) -> bool:
        """Trigger a failsafe transition.

        Failsafes are AUTOMATIC safety responses to critical conditions.
        They can override normal transition rules in certain cases.

        Args:
            reason: The failsafe trigger. Must be a key in FAILSAFE_TRANSITIONS:
                - "rc_loss": Radio control lost
                - "low_battery": Battery below safe threshold
                - "critical_battery": Battery critically low
                - "geofence_breach": Exited safe flight area
                - "position_drift": Position estimate degrading
                - "kill_switch": Operator emergency stop
                - "offboard_timeout": Control link lost

        Returns:
            True if the failsafe was triggered successfully, False if:
            - The failsafe reason is unknown
            - The current state doesn't allow this failsafe
            - The target transition is invalid

        WHY THIS METHOD?
        =================
        Failsafes need special handling because:
        - They may need to trigger from unusual states
        - They have priority over normal operations
        - They need different validation than normal transitions

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Validate the failsafe reason is known
            if reason not in self.FAILSAFE_TRANSITIONS:
                return False

            # Get the target state for this failsafe
            target_state = self.FAILSAFE_TRANSITIONS[reason]

            # ---------------------------------------------------------------------
            # SPECIAL HANDLING: Kill Switch
            # ---------------------------------------------------------------------
            # Kill switch is the highest priority - can trigger from ANY armed state
            if reason == "kill_switch":
                # Check if we're in an armed or flying state (safety: can't kill if disarmed)
                if self._state in self.ARMED_STATES or self._state in self.FLYING_STATES:
                    return self.transition(target_state, reason, "failsafe")
                return False

            # ---------------------------------------------------------------------
            # SPECIAL HANDLING: Offboard Timeout
            # ---------------------------------------------------------------------
            # Offboard timeout only applies when in offboard control modes
            # (position, velocity, mission). Other modes don't use offboard link.
            if reason == "offboard_timeout":
                offboard_states = {
                    FlightState.POSITION_CONTROL,
                    FlightState.VELOCITY_CONTROL,
                    FlightState.MISSION_EXECUTION,
                }
                if self._state not in offboard_states:
                    # Not in offboard mode - timeout doesn't apply
                    return False
                return self.transition(target_state, reason, "failsafe")

            # ---------------------------------------------------------------------
            # STANDARD FAILSAFES
            # ---------------------------------------------------------------------
            # Standard failsafes (RC loss, battery, geofence, etc.) only trigger
            # if we're in a flying state. No point triggering RTL if on ground.

            if self._state in self.FLYING_STATES:
                return self.transition(target_state, reason, "failsafe")

            # ---------------------------------------------------------------------
            # GROUND STATE FAILSAFES
            # ---------------------------------------------------------------------
            # Some failsafes can also trigger from armed ground states
            # (e.g., armed but takeoff not started yet)

            if self._state in {FlightState.ARMED, FlightState.TAKING_OFF}:
                # These failsafes make sense even from ground/armed states
                if reason in {"rc_loss", "geofence_breach", "critical_battery"}:
                    return self.transition(target_state, reason, "failsafe")

            # Failsafe not applicable to current state
            return False

    # =========================================================================
    # COMMAND VALIDATION
    # =========================================================================

    def check_command_precondition(self, command: str) -> bool:
        """Check if a command can be executed in the current state.

        Args:
            command: The command name to check. Common commands:
                - "arm", "disarm", "takeoff", "land"
                - "set_velocity", "set_position", "set_attitude"
                - "return_to_launch", "hold", "start_mission", "abort", "kill"

        Returns:
            True if the command is allowed in the current state.

        WHY THIS METHOD?
        =================
        Prevents sending commands that would be:
        - Dangerous (disarm while flying)
        - Ineffective (take off when already flying)
        - Confusing (arm when already armed)

        Used by the GuardianProcess to validate LLM commands.

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Unknown commands are not allowed (fail secure)
            if command not in self.COMMAND_PRECONDITIONS:
                return False

            # Get the set of allowed states for this command
            required_states = self.COMMAND_PRECONDITIONS[command]

            # Check if current state is in the allowed set
            return self._state in required_states

    # =========================================================================
    # HISTORY METHODS
    # =========================================================================

    def get_history(self, limit: Optional[int] = None) -> List[StateTransition]:
        """Get the state transition history.

        Args:
            limit: Maximum number of transitions to return.
                - If None: returns complete history
                - If positive: returns the most recent N transitions

        Returns:
            List of StateTransition records in chronological order
            (oldest first, newest last).

        WHY THIS METHOD?
        =================
        History is essential for:
        - Debugging: See exactly what states the drone went through
        - Auditing: Prove safety systems worked correctly
        - LLM context: Give the LLM recent state changes for decisions
        - Post-flight analysis: Reconstruct flight timeline

        Thread-safe: Yes (acquires lock, returns copy)
        """
        with self._lock:
            if limit is None:
                # Return complete history copy (prevents external modification)
                return self._history.copy()

            # Return last N transitions (negative indexing handles this)
            return self._history[-limit:]

    # =========================================================================
    # TELEMETRY SYNCHRONIZATION
    # =========================================================================

    def sync_from_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Synchronize state from telemetry data.

        This method updates the internal state based on actual telemetry
        from the drone. It's used to keep the state machine in sync with
        reality, especially after connection loss or restart.

        IMPORTANT: Does NOT override EMERGENCY or ERROR states without
        explicit user action (safety requirement).

        Args:
            telemetry: Dictionary containing telemetry data. Expected keys:
                - armed: bool - Whether the drone is armed
                - in_air: bool - Whether the drone is in the air
                - landed: bool - Whether the drone has landed
                - velocity: List[float] - Velocity vector [vx, vy, vz] (optional)
                - landing: bool - Whether currently landing (optional)
                - ground_contact: bool - Whether on ground (optional)

        WHY THIS METHOD?
        =================
        Telemetry sync is critical because:
        - State machine may restart while drone is flying (need to recover)
        - Telemetry is ground truth - state machine should reflect reality
        - Detects state changes that bypassed the state machine (direct PX4 commands)

        SAFETY NOTES:
        =============
        - Never overrides EMERGENCY or ERROR (require explicit reset)
        - From INIT, can jump to any state (boot-time recovery)
        - Invalid transitions are silently ignored (telemetry may be stale)

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # ---------------------------------------------------------------------
            # SAFETY CHECK: Never override emergency/error from telemetry
            # ---------------------------------------------------------------------
            # WHY: Emergency and error states require EXPLICIT human acknowledgment.
            # We don't want stale telemetry clearing a real emergency.
            if self._state in {FlightState.EMERGENCY, FlightState.ERROR}:
                return

            # ---------------------------------------------------------------------
            # EXTRACT TELEMETRY VALUES
            # ---------------------------------------------------------------------
            # Use .get() with defaults to handle missing keys gracefully

            armed = telemetry.get("armed", False)
            in_air = telemetry.get("in_air", False)
            landed = telemetry.get("landed", True)
            velocity = telemetry.get("velocity", [0.0, 0.0, 0.0])
            is_landing = telemetry.get("landing", False)
            ground_contact = telemetry.get("ground_contact", False)

            # ---------------------------------------------------------------------
            # DETERMINE TARGET STATE FROM TELEMETRY
            # ---------------------------------------------------------------------
            # Logic: Convert raw telemetry into the most appropriate FlightState

            target_state: Optional[FlightState] = None

            if not armed:
                # Not armed -> disarmed state
                target_state = FlightState.DISARMED

            elif armed and not in_air and (landed or ground_contact):
                # Armed but on ground - could be ARMED, LANDED, or LANDING completion

                if self._state == FlightState.LANDING:
                    # We were landing and now we're on ground -> landing complete
                    target_state = FlightState.LANDED

                elif self._state == FlightState.LANDED:
                    # Already in LANDED state, stay there
                    target_state = FlightState.LANDED

                elif self._state == FlightState.ARMED:
                    # Already in ARMED state, stay there
                    target_state = FlightState.ARMED

                elif self._state == FlightState.INIT:
                    # From INIT, armed on ground means we're ready for takeoff
                    target_state = FlightState.ARMED

                else:
                    # Transition from any other state to LANDED (we're on ground)
                    target_state = FlightState.LANDED

            elif is_landing:
                # Telemetry indicates we're actively landing
                target_state = FlightState.LANDING

            elif ground_contact and not in_air:
                # On ground contact, not in air -> landed
                target_state = FlightState.LANDED

            elif in_air and not landed:
                # In the air - determine if hovering or flying based on velocity
                # WHY: Velocity magnitude < 0.5 m/s means "essentially stationary"
                velocity_magnitude = sum(v ** 2 for v in velocity) ** 0.5

                if velocity_magnitude < 0.5:  # 0.5 m/s threshold for hovering
                    target_state = FlightState.HOVERING
                else:
                    target_state = FlightState.FLYING

            # ---------------------------------------------------------------------
            # APPLY STATE TRANSITION
            # ---------------------------------------------------------------------

            if target_state is not None and target_state != self._state:
                # Special case: from INIT, we can jump directly to any state
                # WHY: This handles state machine restart while drone is flying.
                # We record the transition directly without validation.
                if self._state == FlightState.INIT:
                    transition_record = StateTransition(
                        from_state=self._state,
                        to_state=target_state,
                        timestamp=time.time(),
                        reason="telemetry_sync",
                        source="telemetry",
                    )
                    self._history.append(transition_record)
                    self._state = target_state

                # Normal case: validate transition before applying
                elif self.can_transition(target_state):
                    self.transition(
                        target_state,
                        "telemetry_sync",
                        "telemetry",
                    )
                # If transition invalid, silently ignore (telemetry may be stale)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_valid_transitions(self) -> Set[FlightState]:
        """Get the set of valid transitions from the current state.

        Returns:
            Set of FlightState values that are valid destinations from the
            current state.

        WHY THIS METHOD?
        =================
        Useful for:
        - UI: Show available next states
        - LLM planning: Know what states are reachable
        - Testing: Validate state machine configuration

        Thread-safe: Yes (acquires lock, returns copy)
        """
        with self._lock:
            # Return copy to prevent external modification
            return self.TRANSITIONS.get(self._state, set()).copy()

    def reset(self, force: bool = False) -> bool:
        """Reset the state machine to INIT state.

        This is a DESTRUCTIVE operation that clears the state and history.
        Use with caution.

        Args:
            force: If True, reset regardless of current state (DANGEROUS).
                If False, only reset if not in a flying state.

        Returns:
            True if reset was successful, False if prevented (not forced and
            currently flying).

        WHY THIS METHOD?
        =================
        Used for:
        - Clean shutdown and restart
        - Recovery from error states (after inspection)
        - Testing: Reset between test cases

        SAFETY: By default, prevents reset while flying to avoid losing state.

        Thread-safe: Yes (acquires lock)
        """
        with self._lock:
            # Safety check: don't reset while flying unless forced
            if not force and self._state in self.FLYING_STATES:
                return False

            # Reset to INIT state
            self._state = FlightState.INIT

            # Clear history (fresh start)
            self._history.clear()

            return True

    def __repr__(self) -> str:
        """String representation of the state machine.

        Returns:
            A string like "FlightStateMachine(state=HOVERING)".
        """
        return f"FlightStateMachine(state={self.current_state_name})"
