"""Flight State Machine for Avatar Drone MCP Server.

Provides thread-safe flight state management with validated transitions,
failsafe handling, and telemetry synchronization.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class FlightState(Enum):
    """Flight state enumeration representing all possible drone states.

    State Diagram:
        INIT -> DISARMED -> ARMED -> TAKING_OFF -> HOVERING
                                                  |
        +---> POSITION_CONTROL <-> VELOCITY_CONTROL
        |         |        |            |
        |         v        v            v
        +-----> HOLD <- RTL <- MISSION_EXECUTION
                      |
                      v
                   LANDING -> LANDED -> DISARMED

    Special states:
        - EMERGENCY: Kill switch triggered
        - ERROR: System error state
    """

    INIT = auto()
    DISARMED = auto()
    ARMED = auto()
    TAKING_OFF = auto()
    HOVERING = auto()
    FLYING = auto()
    POSITION_CONTROL = auto()
    VELOCITY_CONTROL = auto()
    MISSION_EXECUTION = auto()
    HOLD = auto()
    RTL = auto()
    LANDING = auto()
    LANDED = auto()
    EMERGENCY = auto()
    ERROR = auto()


@dataclass
class StateTransition:
    """Record of a state transition.

    Attributes:
        from_state: Previous flight state
        to_state: New flight state
        timestamp: Unix timestamp of transition
        reason: Human-readable reason for transition
        source: Source of transition command ("llm", "operator", "guardian",
            "telemetry", "failsafe")
    """

    from_state: FlightState
    to_state: FlightState
    timestamp: float
    reason: str
    source: str


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted.

    Attributes:
        from_state: The current state
        to_state: The requested state
    """

    def __init__(
        self,
        from_state: FlightState,
        to_state: FlightState,
        message: Optional[str] = None,
    ):
        self.from_state = from_state
        self.to_state = to_state
        default_message = (
            f"Invalid state transition from {from_state.name} to {to_state.name}"
        )
        super().__init__(message or default_message)


class FlightStateMachine:
    """Thread-safe flight state machine with validated transitions.

    This class manages the complete flight state lifecycle with:
    - Validated state transitions
    - Failsafe handling
    - Command preconditions
    - State history tracking
    - Telemetry synchronization

    Thread Safety:
        All public methods are thread-safe using internal locking.

    Example:
        >>> sm = FlightStateMachine()
        >>> sm.transition(FlightState.DISARMED, "startup_complete", "system")
        True
        >>> sm.transition(FlightState.ARMED, "operator_command", "operator")
        True
        >>> sm.current_state
        <FlightState.ARMED: 3>
    """

    # Valid state transitions map
    TRANSITIONS: Dict[FlightState, Set[FlightState]] = {
        # Initial state
        FlightState.INIT: {FlightState.DISARMED, FlightState.ERROR},
        # Ground states
        FlightState.DISARMED: {FlightState.ARMED, FlightState.ERROR},
        FlightState.ARMED: {FlightState.TAKING_OFF, FlightState.DISARMED, FlightState.ERROR},
        FlightState.LANDED: {FlightState.DISARMED, FlightState.ERROR},
        # Takeoff sequence
        FlightState.TAKING_OFF: {FlightState.HOVERING, FlightState.LANDING, FlightState.ERROR},
        # Flying states
        FlightState.HOVERING: {
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.LANDED,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        FlightState.FLYING: {
            FlightState.HOVERING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.LANDED,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Control modes
        FlightState.POSITION_CONTROL: {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        FlightState.VELOCITY_CONTROL: {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Mission execution
        FlightState.MISSION_EXECUTION: {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.HOLD,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Hold state
        FlightState.HOLD: {
            FlightState.HOVERING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.RTL,
            FlightState.LANDING,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Return to launch
        FlightState.RTL: {
            FlightState.LANDING,
            FlightState.HOVERING,
            FlightState.HOLD,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Landing sequence
        FlightState.LANDING: {
            FlightState.LANDED,
            FlightState.HOVERING,
            FlightState.HOLD,
            FlightState.EMERGENCY,
            FlightState.ERROR,
        },
        # Emergency states - require explicit recovery
        FlightState.EMERGENCY: {FlightState.INIT, FlightState.ERROR},
        FlightState.ERROR: {FlightState.INIT, FlightState.DISARMED, FlightState.ERROR},
    }

    # Failsafe triggers -> target state mapping
    FAILSAFE_TRANSITIONS: Dict[str, FlightState] = {
        "rc_loss": FlightState.RTL,
        "low_battery": FlightState.RTL,
        "critical_battery": FlightState.LANDING,
        "geofence_breach": FlightState.RTL,
        "kill_switch": FlightState.EMERGENCY,
        "offboard_timeout": FlightState.HOLD,
    }

    # Command preconditions -> required states
    COMMAND_PRECONDITIONS: Dict[str, Set[FlightState]] = {
        "arm": {FlightState.INIT, FlightState.DISARMED},
        "disarm": {FlightState.ARMED, FlightState.LANDED, FlightState.DISARMED},
        "takeoff": {FlightState.ARMED},
        "land": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
            FlightState.RTL,
        },
        "set_velocity": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },
        "set_position": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },
        "set_attitude": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },
        "return_to_launch": {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        },
        "hold": {
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
        },
        "start_mission": {
            FlightState.HOVERING,
            FlightState.FLYING,
        },
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
        "kill": {FlightState.ARMED, FlightState.TAKING_OFF, FlightState.HOVERING, FlightState.FLYING,
                 FlightState.POSITION_CONTROL, FlightState.VELOCITY_CONTROL,
                 FlightState.MISSION_EXECUTION, FlightState.HOLD, FlightState.RTL, FlightState.LANDING},
    }

    # States considered "flying"
    FLYING_STATES: Set[FlightState] = {
        FlightState.TAKING_OFF,
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
        FlightState.RTL,
        FlightState.LANDING,
    }

    # States considered "armed"
    ARMED_STATES: Set[FlightState] = {
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
    }

    def __init__(self) -> None:
        """Initialize the flight state machine in INIT state."""
        self._state = FlightState.INIT
        self._history: List[StateTransition] = []
        self._lock = threading.RLock()

    @property
    def current_state(self) -> FlightState:
        """Get the current flight state."""
        with self._lock:
            return self._state

    @property
    def current_state_name(self) -> str:
        """Get the string name of the current flight state."""
        with self._lock:
            return self._state.name

    @property
    def is_flying(self) -> bool:
        """Check if the drone is currently flying (in the air).

        Returns:
            True if the drone is in a flying state (HOVERING, FLYING,
            POSITION_CONTROL, etc.), False otherwise.
        """
        with self._lock:
            return self._state in self.FLYING_STATES

    @property
    def is_armed(self) -> bool:
        """Check if the drone is currently armed.

        Returns:
            True if the drone is in an armed state, False otherwise.
        """
        with self._lock:
            return self._state in self.ARMED_STATES

    def can_transition(self, to_state: FlightState) -> bool:
        """Check if a transition to the given state is valid.

        Args:
            to_state: The target state to transition to.

        Returns:
            True if the transition is valid from the current state.
        """
        with self._lock:
            valid_targets = self.TRANSITIONS.get(self._state, set())
            return to_state in valid_targets

    def transition(
        self,
        to_state: FlightState,
        reason: str,
        source: str,
        raise_on_error: bool = False,
    ) -> bool:
        """Attempt to transition to a new state.

        Args:
            to_state: The target state to transition to.
            reason: Human-readable reason for the transition.
            source: Source of the transition ("llm", "operator", "guardian",
                "telemetry", "failsafe").
            raise_on_error: If True, raise StateTransitionError on invalid
                transition instead of returning False.

        Returns:
            True if the transition was successful, False otherwise.

        Raises:
            StateTransitionError: If raise_on_error is True and the
                transition is invalid.
        """
        with self._lock:
            if not self.can_transition(to_state):
                if raise_on_error:
                    raise StateTransitionError(self._state, to_state)
                return False

            # Record transition
            transition_record = StateTransition(
                from_state=self._state,
                to_state=to_state,
                timestamp=time.time(),
                reason=reason,
                source=source,
            )
            self._history.append(transition_record)

            # Perform transition
            self._state = to_state
            return True

    def trigger_failsafe(self, reason: str) -> bool:
        """Trigger a failsafe transition.

        Failsafe transitions can override normal state transition rules
        in certain cases (e.g., low battery always triggers RTL regardless
        of current state in most cases).

        Args:
            reason: The failsafe reason. Must be a key in
                FAILSAFE_TRANSITIONS (e.g., "rc_loss", "low_battery",
                "kill_switch").

        Returns:
            True if the failsafe was triggered successfully, False if
            the failsafe reason is unknown or transition is not possible.
        """
        with self._lock:
            if reason not in self.FAILSAFE_TRANSITIONS:
                return False

            target_state = self.FAILSAFE_TRANSITIONS[reason]

            # Special handling for kill switch - can trigger from most armed states
            if reason == "kill_switch":
                if self._state in self.ARMED_STATES or self._state in self.FLYING_STATES:
                    return self.transition(target_state, reason, "failsafe")
                return False

            # For offboard timeout, only trigger if currently in an offboard mode
            if reason == "offboard_timeout":
                offboard_states = {
                    FlightState.POSITION_CONTROL,
                    FlightState.VELOCITY_CONTROL,
                    FlightState.MISSION_EXECUTION,
                }
                if self._state not in offboard_states:
                    return False
                return self.transition(target_state, reason, "failsafe")

            # Standard failsafes - trigger if in a flying state
            if self._state in self.FLYING_STATES:
                return self.transition(target_state, reason, "failsafe")

            # Some failsafes can also trigger from armed ground states
            if self._state in {FlightState.ARMED, FlightState.TAKING_OFF}:
                if reason in {"rc_loss", "geofence_breach", "critical_battery"}:
                    return self.transition(target_state, reason, "failsafe")

            return False

    def check_command_precondition(self, command: str) -> bool:
        """Check if a command can be executed in the current state.

        Args:
            command: The command name to check.

        Returns:
            True if the command can be executed in the current state.
        """
        with self._lock:
            if command not in self.COMMAND_PRECONDITIONS:
                return False

            required_states = self.COMMAND_PRECONDITIONS[command]
            return self._state in required_states

    def get_history(self, limit: Optional[int] = None) -> List[StateTransition]:
        """Get the state transition history.

        Args:
            limit: Maximum number of transitions to return. If None,
                returns the complete history. If positive, returns the
                most recent N transitions.

        Returns:
            List of StateTransition records in chronological order.
        """
        with self._lock:
            if limit is None:
                return self._history.copy()
            return self._history[-limit:]

    def sync_from_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Synchronize state from telemetry data.

        This method updates the internal state based on actual telemetry
        from the drone. It does NOT override EMERGENCY or ERROR states
        without explicit user action.

        Args:
            telemetry: Dictionary containing telemetry data. Expected keys:
                - armed: bool - Whether the drone is armed
                - in_air: bool - Whether the drone is in the air
                - landed: bool - Whether the drone has landed
                - velocity: List[float] - Velocity vector [vx, vy, vz] (optional)
                - landing: bool - Whether currently landing (optional)
                - ground_contact: bool - Whether on ground (optional)

        Note:
            This method only makes valid state transitions. If the telemetry
            suggests an invalid state transition, it will be ignored.
            From INIT state, telemetry sync can directly set any state (boot-time recovery).
        """
        with self._lock:
            # Never override emergency or error states without explicit action
            if self._state in {FlightState.EMERGENCY, FlightState.ERROR}:
                return

            armed = telemetry.get("armed", False)
            in_air = telemetry.get("in_air", False)
            landed = telemetry.get("landed", True)
            velocity = telemetry.get("velocity", [0.0, 0.0, 0.0])
            is_landing = telemetry.get("landing", False)
            ground_contact = telemetry.get("ground_contact", False)

            # Determine target state based on telemetry
            target_state: Optional[FlightState] = None

            if not armed:
                target_state = FlightState.DISARMED
            elif armed and not in_air and (landed or ground_contact):
                # Armed but on ground - could be ARMED or LANDED
                if self._state == FlightState.LANDING:
                    # Just finished landing
                    target_state = FlightState.LANDED
                elif self._state == FlightState.LANDED:
                    target_state = FlightState.LANDED
                elif self._state == FlightState.ARMED:
                    target_state = FlightState.ARMED
                elif self._state == FlightState.INIT:
                    # From INIT, armed on ground means ARMED (ready for takeoff)
                    target_state = FlightState.ARMED
                else:
                    # Transition to LANDED if we were in a flying state
                    target_state = FlightState.LANDED
            elif is_landing:
                target_state = FlightState.LANDING
            elif ground_contact and not in_air:
                target_state = FlightState.LANDED
            elif in_air and not landed:
                # Determine flying state based on velocity
                velocity_magnitude = sum(v ** 2 for v in velocity) ** 0.5
                if velocity_magnitude < 0.5:  # Threshold for "hovering"
                    target_state = FlightState.HOVERING
                else:
                    target_state = FlightState.FLYING

            # Attempt transition if valid
            if target_state is not None and target_state != self._state:
                # Special case: from INIT, telemetry can set any state (boot-time sync)
                if self._state == FlightState.INIT:
                    # Record transition directly without going through normal flow
                    transition_record = StateTransition(
                        from_state=self._state,
                        to_state=target_state,
                        timestamp=time.time(),
                        reason="telemetry_sync",
                        source="telemetry",
                    )
                    self._history.append(transition_record)
                    self._state = target_state
                elif self.can_transition(target_state):
                    self.transition(
                        target_state,
                        f"telemetry_sync",
                        "telemetry",
                    )

    def get_valid_transitions(self) -> Set[FlightState]:
        """Get the set of valid transitions from the current state.

        Returns:
            Set of FlightState values that are valid from the current state.
        """
        with self._lock:
            return self.TRANSITIONS.get(self._state, set()).copy()

    def reset(self, force: bool = False) -> bool:
        """Reset the state machine to INIT state.

        This is a special operation that can only be performed from
        ground states unless force=True.

        Args:
            force: If True, reset regardless of current state. DANGEROUS!

        Returns:
            True if reset was successful.
        """
        with self._lock:
            if not force and self._state in self.FLYING_STATES:
                return False

            self._state = FlightState.INIT
            self._history.clear()
            return True

    def __repr__(self) -> str:
        """String representation of the state machine."""
        return f"FlightStateMachine(state={self.current_state_name})"

