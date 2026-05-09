"""6-level safety escalation matrix for autonomous drone operations.

This module implements a hierarchical safety escalation system that determines
automated responses to safety conditions based on severity levels. It serves
as the decision-making layer for the AsyncGuardian safety system.

=============================================================================
ESCALATION LEVELS EXPLAINED
=============================================================================

Level 1 (L1 - MINOR ANOMALY):
    Purpose: Early warning system for conditions that could worsen
    Trigger Conditions:
        - Battery drops below 30% (early warning)
        - Telemetry becomes stale (>5 seconds old)
        - Minor sensor discrepancies
    Automatic Action: Log and alert operator only
    Recovery: Operator reviews and decides on action
    Drone State: Normal operation continues

Level 2 (L2 - MODERATE RISK):
    Purpose: Prevent risky LLM commands while maintaining control
    Trigger Conditions:
        - Battery drops below 25%
        - Command validation fails (unsafe LLM suggestion)
        - Heartbeat warning (>2 seconds since last heartbeat)
    Automatic Action: Reject LLM commands, alert operator
    Recovery: Operator must acknowledge and can issue safe manual commands
    Drone State: Active control maintained, but LLM suggestions blocked

Level 3 (L3 - SIGNIFICANT RISK):
    Purpose: Autonomous system assumes control to prevent unsafe situations
    Trigger Conditions:
        - State inconsistency detected (internal logic conflict)
        - Mode change fails (e.g., can't enter offboard mode)
        - Approaching geofence boundary (<50m from boundary)
    Automatic Action: System overrides to HOLD mode (position hold)
    Recovery: Operator must take manual control and resolve issue
    Drone State: Autonomous hover at current position

Level 4 (L4 - CRITICAL RISK):
    Purpose: Initiate controlled return to safety
    Trigger Conditions:
        - Battery drops below 20% (critical battery)
        - Geofence breached (exceeded max distance from home)
        - Communication link degraded (>5 seconds no contact)
        - GPS accuracy degraded (unsafe for navigation)
    Automatic Action: Initiate RTL (Return to Launch)
    Recovery: Drone autonomously returns home; operator can intervene
    Drone State: RTL mode - ascending to RTL altitude, then flying home

Level 5 (L5 - EMERGENCY):
    Purpose: Immediate landing when flight cannot continue safely
    Trigger Conditions:
        - Total power loss detected (battery at 0%)
        - Communication link lost (>10 seconds no contact)
        - Engine/motor failure detected
        - Flight stability critical (severe attitude anomalies)
    Automatic Action: Initiate immediate LAND
    Recovery: Drone lands at current position; emergency services if needed
    Drone State: Land mode - descending to ground at current location

Level 6 (L6 - CATASTROPHIC):
    Purpose: Last-resort action to minimize damage
    Trigger Conditions:
        - Total system failure (all systems unresponsive)
        - Uncontrolled descent detected
        - Unauthorized control takeover (security breach)
    Automatic Action: Emergency disarm (cut motors) - ONLY if altitude <10m
    Recovery: Emergency disarm executed; aircraft will fall
    Drone State: Motors cut - immediate descent (controlled crash if low)

=============================================================================
STATE TRANSITION DIAGRAM
=============================================================================

                         +------------------+
                         |   NORMAL FLIGHT  |
                         |   (No Escalation)|
                         +--------+---------+
                                  |
              +---------------------+---------------------+
              |                     |                     |
              v                     v                     v
    +-------------------+  +-------------------+  +-------------------+
    | L1: MINOR ANOMALY |  | L2: MODERATE RISK |  | L3: SIGNIFICANT   |
    | - Log & Alert     |  | - Reject LLM Cmds |  |     RISK          |
    | - Continue Ops    |  | - Manual Control  |  | - Hold Mode       |
    +--------+----------+  +--------+----------+  +--------+----------+
             |                      |                      |
             |  Worsens             |  Worsens             |  Worsens
             v                      v                      v
    +-------------------+  +-------------------+  +-------------------+
    | L4: CRITICAL RISK |<--|                   |<--|                   |
    | - Initiate RTL    |   |                   |   |                   |
    | - Return Home     |   |    (Can skip      |   |    levels if      |
    +--------+----------+   |    conditions     |   |    severe)        |
             |              |    worsen fast)   |   |                   |
             |  Worsens     +-------------------+   +-------------------+
             v
    +-------------------+
    | L5: EMERGENCY     |
    | - Initiate Land   |
    | - Stop Navigation |
    +--------+----------+
             |
             |  Worsens (or immediate for severe failures)
             v
    +-------------------+
    | L6: CATASTROPHIC  |
    | - Emergency Disarm| (Only if <10m altitude)
    | - Cut Motors      |
    +-------------------+

NOTE: Escalation is generally progressive, but severe conditions can jump
      multiple levels (e.g., total power loss immediately triggers L5).

=============================================================================
RECOVERY PROCEDURES BY LEVEL
=============================================================================

L1 Recovery (Minor):
    1. Operator receives alert via notification
    2. Operator reviews telemetry dashboard
    3. If condition persists, operator may choose to RTL manually
    4. Log entry created for post-flight analysis

L2 Recovery (Moderate Risk):
    1. LLM commands automatically rejected with warning
    2. Operator notified with reason for rejection
    3. Operator can:
       a) Acknowledge and continue with safe manual commands
       b) Initiate RTL to abort mission
       c) Request LLM to replan with safer parameters
    4. Once condition resolves, LLM commands re-enabled

L3 Recovery (Significant Risk):
    1. System automatically enters HOLD mode
    2. Operator immediately alerted with high-priority notification
    3. Operator must:
       a) Take manual control
       b) Diagnose the issue (check state consistency, geofence)
       c) Resolve underlying problem
    4. After resolution, operator can resume mission or RTL

L4 Recovery (Critical Risk):
    1. RTL automatically initiated
    2. Operator can monitor progress
    3. Operator may:
       a) Let RTL complete autonomously
       b) Take manual control if situation improves
       c) Upgrade to L5 (Land) if conditions worsen
    4. Upon arrival at home position, drone lands or holds

L5 Recovery (Emergency):
    1. Land mode immediately engaged
    2. Descent begins at current position
    3. Operator should:
       a) Monitor descent rate and terrain
       b) Alert ground personnel if in populated area
       c) Prepare for emergency response
    4. After touchdown, motors automatically disarm

L6 Recovery (Catastrophic):
    1. Emergency disarm executed (if altitude <10m)
    2. Motors stop immediately
    3. Aircraft will fall/crash
    4. Post-incident:
       a) Retrieve aircraft
       b) Analyze black box / logs
       c) Identify root cause
       d) Implement fixes before next flight

=============================================================================
TIMEOUT-BASED ESCALATION
=============================================================================

Some conditions use timers to escalate if they persist:

    Heartbeat Timeout:
        >2s  -> L2 (Heartbeat Warning)
        >5s  -> L4 (Comm Link Degraded)
        >10s -> L5 (Comm Link Lost)

    Geofence Approach:
        <50m from boundary -> L3 (Geofence Warning)
        Beyond boundary    -> L4 (Geofence Breach)

Timers can be cancelled if the condition resolves before timeout.

=============================================================================
USAGE EXAMPLES
=============================================================================

    # Create escalation matrix
    matrix = EscalationMatrix()

    # Evaluate a condition
    event = matrix.evaluate("low_battery", battery_percent=20)
    if event and event.level >= SeverityLevel.L4_CRITICAL:
        await guardian.initiate_rtl(event.action_taken)

    # Check battery level (convenience method)
    event = matrix.check_battery(percent=15)

    # Check geofence distance
    event = matrix.check_geofence(distance_m=550, max_m=500)

    # Check heartbeat timeout
    event = matrix.check_heartbeat_timeout(age_s=12)

    # Get escalation history for analysis
    history = matrix.get_history(limit=10)
    current_severity = matrix.get_current_severity()

=============================================================================
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Callable, Any, Awaitable, Union

logger = logging.getLogger(__name__)


# =============================================================================
# D2.7: GUARDIAN EVENT TYPES FOR FAILSAFE DISPATCH
# =============================================================================
# These types support the GuardianEvent dispatch system where AsyncGuardian
# can trigger failsafe actions through the EscalationMatrix's registered
# executor functions.


@dataclass(frozen=True)
class GuardianEvent:
    """Immutable record of a guardian-triggered safety event.

    D2.7: GuardianEvent represents a safety condition detected by AsyncGuardian
    that requires a failsafe action. The EscalationMatrix acts as the single
    consumer of these events, dispatching them to registered executors.

    Attributes:
        condition: The condition that triggered the event (e.g., "battery_critical",
            "geofence_breach", "comm_link_lost"). Maps to EscalationRule.condition.
        reason: Human-readable explanation of why this event was triggered.
        context: Additional context data (battery percentage, distance, timestamps, etc.).

    Example:
        >>> event = GuardianEvent(
        ...     condition="battery_critical",
        ...     reason="Battery at 18%, below 20% threshold",
        ...     context={"battery_percent": 18.0, "voltage": 14.2}
        ... )
    """

    condition: str
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)


class FailsafeAction(IntEnum):
    """Failsafe actions that can be triggered by guardian events.

    D2.7: These actions map to PX4 failsafe behaviors. Each action has
    an associated executor function that implements the actual MAVSDK call.

    Action Priority (highest to lowest):
        EMERGENCY_DISARM (6): Cut motors immediately - last resort
        LAND (5): Land at current position
        RTL (4): Return to launch point
        HOLD (3): Hover in place
        REJECT_COMMAND (2): Block LLM commands
        LOG_ALERT (1): Log and notify only

    Attributes:
        LOG_ALERT: Log event and notify operator (L1)
        REJECT_COMMAND: Reject LLM commands, allow manual (L2)
        HOLD: Enter hold/loiter mode (L3)
        RTL: Return to launch (L4)
        LAND: Land immediately at current position (L5)
        EMERGENCY_DISARM: Cut motors immediately (L6, only if low altitude)

    Example:
        >>> action = FailsafeAction.RTL
        >>> action.value
        4
        >>> action >= FailsafeAction.HOLD
        True
    """

    LOG_ALERT = 1
    REJECT_COMMAND = 2
    HOLD = 3
    RTL = 4
    LAND = 5
    EMERGENCY_DISARM = 6


# Type alias for executor functions
# Executor functions are async callables that perform the actual failsafe action
FailsafeExecutor = Callable[[GuardianEvent], Awaitable[None]]


class SeverityLevel(IntEnum):
    """6-level severity escalation system for autonomous drone safety.

    The severity levels form a hierarchy where higher numbers indicate
    more critical situations requiring more aggressive intervention.

    Level Progression:
        L1 -> L2 -> L3 -> L4 -> L5 -> L6
        (Minor to Catastrophic)

    Attributes:
        L1_MINOR: Minor anomaly - Log and alert operator only
        L2_MODERATE: Moderate risk - Reject LLM commands
        L3_SIGNIFICANT: Significant risk - Override to Hold mode
        L4_CRITICAL: Critical risk - Initiate RTL (Return to Launch)
        L5_EMERGENCY: Emergency - Initiate Land immediately
        L6_CATASTROPHIC: Catastrophic - Emergency disarm (if safe altitude < 10m)

    Example:
        >>> level = SeverityLevel.L4_CRITICAL
        >>> level.value
        4
        >>> level.name
        'L4_CRITICAL'
        >>> level >= SeverityLevel.L3_SIGNIFICANT
        True
    """
    L1_MINOR = 1
    L2_MODERATE = 2
    L3_SIGNIFICANT = 3
    L4_CRITICAL = 4
    L5_EMERGENCY = 5
    L6_CATASTROPHIC = 6


@dataclass(frozen=True)
class EscalationRule:
    """Defines a rule for escalating to a specific severity level.

    Each rule specifies:
    - What severity level to trigger
    - What condition triggers it (e.g., "battery_low")
    - What action to take (e.g., "initiate_rtl")
    - Whether to execute automatically
    - Whether to notify the operator
    - Optional numeric threshold

    Attributes:
        level: The severity level this rule triggers (e.g., SeverityLevel.L4_CRITICAL)
        condition: Human-readable condition identifier (e.g., "battery_low", "geofence_breach")
        action: Action to take when triggered (e.g., "initiate_rtl", "emergency_disarm")
        auto_execute: Whether to automatically execute the action without operator confirmation
        notify_operator: Whether to send notification to the operator
        threshold: Optional numeric threshold for triggering (e.g., 20.0 for battery percentage)

    Example:
        >>> rule = EscalationRule(
        ...     level=SeverityLevel.L4_CRITICAL,
        ...     condition="battery_critical",
        ...     action="initiate_rtl",
        ...     auto_execute=True,
        ...     notify_operator=True,
        ...     threshold=20.0
        ... )
    """
    level: SeverityLevel
    condition: str
    action: str
    auto_execute: bool
    notify_operator: bool
    threshold: Optional[float] = None


@dataclass(frozen=True)
class EscalationEvent:
    """Records an escalation event that has occurred.

    Immutable record of a safety escalation for logging, analysis,
    and audit trails. Created each time an escalation rule triggers.

    Attributes:
        level: The severity level of the event (SeverityLevel)
        condition: The condition that triggered the event (e.g., "battery_critical")
        timestamp: Unix timestamp when the event occurred (seconds since epoch)
        action_taken: The action that was taken or planned (e.g., "initiate_rtl")
        context: Additional context about the event (dict with relevant data)

    Example:
        >>> event = EscalationEvent(
        ...     level=SeverityLevel.L4_CRITICAL,
        ...     condition="battery_critical",
        ...     timestamp=time.time(),
        ...     action_taken="initiate_rtl",
        ...     context={"battery_percent": 18.5, "voltage": 14.2}
        ... )
    """
    level: SeverityLevel
    condition: str
    timestamp: float
    action_taken: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationTimer:
    """Tracks escalation timeouts for a condition.

    Implements time-based escalation where conditions that persist
    beyond a timeout period automatically escalate to a higher severity.
    Used primarily for heartbeat timeouts and persistent anomaly tracking.

    Attributes:
        condition: The condition being tracked (e.g., "comm_link_degraded")
        level: Severity level to escalate to if timeout expires
        timeout_s: Timeout in seconds before escalation triggers
        triggered_at: Unix timestamp when the timer was started
        is_active: Whether the timer is currently running

    Example:
        >>> timer = EscalationTimer(
        ...     condition="comm_link_lost",
        ...     level=SeverityLevel.L5_EMERGENCY,
        ...     timeout_s=10.0
        ... )
        >>> timer.is_expired()  # Check if timeout has passed
        False
        >>> timer.remaining_s()  # Get seconds remaining
        8.5
        >>> timer.cancel()  # Cancel the timer if condition resolves
    """
    condition: str
    level: SeverityLevel
    timeout_s: float
    triggered_at: float = field(default_factory=time.time)
    is_active: bool = field(default=True)

    def is_expired(self) -> bool:
        """Check if the timeout has expired.

        Returns:
            True if timer is active and timeout period has elapsed,
            False otherwise.
        """
        return self.is_active and (time.time() - self.triggered_at) >= self.timeout_s

    def remaining_s(self) -> float:
        """Get remaining seconds before timeout.

        Returns:
            Seconds remaining before expiration (0.0 if inactive or expired).
        """
        if not self.is_active:
            return 0.0
        elapsed = time.time() - self.triggered_at
        return max(0.0, self.timeout_s - elapsed)

    def cancel(self) -> None:
        """Cancel the timer.

        Marks timer as inactive. After cancellation, is_expired()
        will return False and remaining_s() will return 0.0.
        """
        self.is_active = False


class EscalationMatrix:
    """6-level safety escalation matrix for autonomous drone operations.

    The EscalationMatrix is the core decision-making component of the safety
    system. It evaluates conditions against predefined rules and triggers
    appropriate safety responses based on severity levels.

    =========================================================================
    ESCALATION LEVELS AND DEFAULT ACTIONS
    =========================================================================

    L1 (MINOR ANOMALY) -> Log and Alert:
        - Triggers on: Battery warning (30%), stale telemetry (>5s)
        - Action: Log event, notify operator
        - Auto-execute: No (informational only)
        - Recovery: Operator reviews telemetry

    L2 (MODERATE RISK) -> Reject LLM Commands:
        - Triggers on: Battery low (25%), command validation fails, heartbeat warning (>2s)
        - Action: Reject LLM suggestions, allow manual control
        - Auto-execute: Yes (command gating)
        - Recovery: Operator acknowledges, resolves condition

    L3 (SIGNIFICANT RISK) -> Assume Control (Hold Mode):
        - Triggers on: State inconsistency, mode change failure, geofence warning (<50m)
        - Action: Enter Hold mode (position hold at current location)
        - Auto-execute: Yes (autonomous takeover)
        - Recovery: Operator takes manual control

    L4 (CRITICAL RISK) -> Initiate RTL:
        - Triggers on: Battery critical (20%), geofence breach, comm degraded (>5s), GPS degraded
        - Action: Initiate Return to Launch (RTL)
        - Auto-execute: Yes (immediate RTL)
        - Recovery: Autonomous return home

    L5 (EMERGENCY) -> Initiate Land:
        - Triggers on: Total power loss, comm link lost (>10s), engine failure, stability critical
        - Action: Initiate Land (immediate descent at current position)
        - Auto-execute: Yes (emergency landing)
        - Recovery: Land and assess

    L6 (CATASTROPHIC) -> Emergency Disarm:
        - Triggers on: Total system failure, uncontrolled descent, unauthorized control
        - Action: Emergency disarm (cut motors) - ONLY if altitude <10m
        - Auto-execute: Yes (last resort)
        - Recovery: Crash/retrieve aircraft

    =========================================================================
    USAGE PATTERNS
    =========================================================================

    Basic Evaluation:
        matrix = EscalationMatrix()
        event = matrix.evaluate("low_battery", battery_percent=20)
        if event:
            print(f"Escalated to {event.level.name}: {event.action_taken}")

    Convenience Checks:
        event = matrix.check_battery(percent=15)  # Returns L4 event
        event = matrix.check_geofence(distance_m=550, max_m=500)  # Returns L4 event
        event = matrix.check_heartbeat_timeout(age_s=12)  # Returns L5 event

    Timer-Based Escalation:
        timer = matrix.start_timer("comm_link", SeverityLevel.L5_EMERGENCY, 10.0)
        # ... later in loop ...
        events = matrix.check_timers()  # Check for expired timers

    Custom Action Handlers:
        def handle_rtl(event):
            print(f"RTL triggered by {event.condition}")
        matrix.register_action_handler("initiate_rtl", handle_rtl)

    History Analysis:
        history = matrix.get_history(limit=10)
        current_severity = matrix.get_current_severity()

    =========================================================================
    DEFAULT THRESHOLDS
    =========================================================================

    Battery Levels:
        - L1 Warning: 30%
        - L2 Low: 25%
        - L4 Critical: 20%
        - L5 Emergency: 0% (total power loss)

    Geofence:
        - L3 Warning: 50 meters before boundary
        - L4 Breach: Beyond max distance

    Heartbeat/Communication:
        - L2 Warning: 2 seconds
        - L4 Degraded: 5 seconds
        - L5 Lost: 10 seconds

    =========================================================================
    THREAD SAFETY
    =========================================================================

    This class is NOT thread-safe. In multi-threaded environments, external
    synchronization is required. The AsyncGuardian provides async-safe
    wrappers around this functionality.
    """

    # =========================================================================
    # DEFAULT ESCALATION RULES
    # =========================================================================
    # These rules define the default safety policy. Each rule maps a condition
    # to a severity level, action, and notification behavior.

    DEFAULT_RULES: List[EscalationRule] = [
        # ------------------------------------------------------------------
        # L1: Minor Anomalies - Informational Only
        # Purpose: Early warning for conditions that could worsen
        # Response: Log and alert operator, no automatic action
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L1_MINOR,
            "battery_warning",      # Condition identifier
            "log_alert",            # Action to take
            False,                  # auto_execute: No - just inform
            True,                   # notify_operator: Yes
            threshold=30.0        # Trigger when battery < 30%
        ),
        EscalationRule(
            SeverityLevel.L1_MINOR,
            "telemetry_stale",      # Telemetry not updating
            "log_alert",
            False,
            True,
            threshold=5.0         # Trigger when telemetry > 5s old
        ),

        # ------------------------------------------------------------------
        # L2: Moderate Risk - Command Rejection
        # Purpose: Prevent risky LLM commands while allowing manual control
        # Response: Reject LLM commands, notify operator
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "battery_low",          # Battery getting low
            "reject_command",       # Block LLM suggestions
            True,                   # auto_execute: Yes - gate commands
            True,
            threshold=25.0        # Trigger when battery < 25%
        ),
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "command_validation_fail",  # LLM suggested unsafe command
            "reject_command",
            True,
            True
            # No threshold - triggered by validation logic
        ),
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "heartbeat_warning",    # Heartbeat getting stale
            "reject_command",
            True,
            True,
            threshold=2.0         # Trigger when heartbeat > 2s old
        ),

        # ------------------------------------------------------------------
        # L3: Significant Risk - Autonomous Hold
        # Purpose: System takes control to prevent unsafe situations
        # Response: Enter Hold mode (position hold), notify operator
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "state_inconsistency",  # Internal state conflict detected
            "assume_control_hold",  # Take control, enter Hold
            True,                   # auto_execute: Yes - autonomous
            True,
            # No threshold - triggered by state checker
        ),
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "mode_change_fail",     # Failed to enter desired mode
            "assume_control_hold",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "geofence_warning",     # Approaching geofence boundary
            "assume_control_hold",
            True,
            True,
            threshold=50.0        # Trigger when < 50m from boundary
        ),

        # ------------------------------------------------------------------
        # L4: Critical Risk - Return to Launch
        # Purpose: Controlled return to safety when flight cannot continue
        # Response: Initiate RTL (Return to Launch)
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "battery_critical",     # Battery critically low
            "initiate_rtl",         # Return to launch point
            True,                   # auto_execute: Yes - immediate RTL
            True,
            threshold=20.0        # Trigger when battery < 20%
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "geofence_breach",      # Exceeded geofence boundary
            "initiate_rtl",
            True,
            True
            # No threshold - triggered when distance > max_m
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "comm_link_degraded",   # Communication link failing
            "initiate_rtl",
            True,
            True,
            threshold=5.0         # Trigger when no comms > 5s
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "gps_degraded",         # GPS accuracy unsafe
            "initiate_rtl",
            True,
            True
        ),

        # ------------------------------------------------------------------
        # L5: Emergency - Immediate Landing
        # Purpose: Land immediately when flight is unsafe
        # Response: Initiate Land (descend at current position)
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "total_power_loss",     # Battery at 0%
            "initiate_land",        # Land immediately
            True,                   # auto_execute: Yes - emergency
            True
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "comm_link_lost",       # Communication completely lost
            "initiate_land",
            True,
            True,
            threshold=10.0        # Trigger when no comms > 10s
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "engine_failure",       # Motor/engine failure
            "initiate_land",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "flight_stability_critical",  # Severe attitude anomalies
            "initiate_land",
            True,
            True
        ),

        # ------------------------------------------------------------------
        # L6: Catastrophic - Last Resort Disarm
        # Purpose: Minimize damage when crash is inevitable
        # Response: Emergency disarm (cut motors) - ONLY if altitude <10m
        # WARNING: This will cause the aircraft to fall!
        # ------------------------------------------------------------------
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "total_system_failure",  # All systems unresponsive
            "emergency_disarm",      # Cut motors
            True,                    # auto_execute: Yes - last resort
            True
        ),
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "uncontrolled_descent",  # Falling uncontrollably
            "emergency_disarm",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "unauthorized_control_takeover",  # Security breach
            "emergency_disarm",
            True,
            True
        ),
    ]

    # =========================================================================
    # DEFAULT THRESHOLDS
    # =========================================================================
    # These values are used by convenience methods (check_battery, etc.)
    # when no custom rules are provided.

    # Battery level thresholds (percentage)
    BATTERY_MINOR_THRESHOLD = 30.0      # L1: Warning threshold
    BATTERY_LOW_THRESHOLD = 25.0        # L2: Low threshold
    BATTERY_CRITICAL_THRESHOLD = 20.0   # L4: Critical threshold

    # Geofence thresholds (meters)
    GEOFENCE_WARNING_THRESHOLD = 50.0   # L3: Warning zone (meters before boundary)

    # Heartbeat/communication thresholds (seconds)
    HEARTBEAT_WARNING_THRESHOLD = 2.0      # L2: Warning
    HEARTBEAT_CRITICAL_THRESHOLD = 5.0     # L4: Degraded
    HEARTBEAT_EMERGENCY_THRESHOLD = 10.0   # L5: Lost

    def __init__(
        self,
        rules: Optional[List[EscalationRule]] = None,
        history_size: int = 100
    ):
        """Initialize the escalation matrix.

        Creates a new escalation matrix with either custom rules or defaults.
        Sets up internal data structures for history tracking, timers, and
        action handlers.

        Args:
            rules: Custom escalation rules. If None, uses DEFAULT_RULES.
                   Custom rules allow tailoring the safety policy to specific
                   mission requirements or aircraft capabilities.
            history_size: Maximum number of events to keep in history.
                          Oldest events are automatically discarded when
                          limit is exceeded. Default is 100.

        Example:
            >>> # Default rules
            >>> matrix = EscalationMatrix()
            >>>
            >>> # Custom rules
            >>> custom_rules = [
            ...     EscalationRule(
            ...         SeverityLevel.L4_CRITICAL,
            ...         "battery_critical",
            ...         "initiate_rtl",
            ...         True, True, threshold=25.0  # More conservative
            ...     )
            ... ]
            >>> matrix = EscalationMatrix(rules=custom_rules)
        """
        # Use provided rules or copy defaults
        self.rules = rules or self.DEFAULT_RULES.copy()

        # Initialize history deque with maxlen for automatic eviction
        self._history: deque[EscalationEvent] = deque(maxlen=history_size)

        # Active timers for timeout-based escalation
        self._timers: Dict[str, EscalationTimer] = {}

        # Registered action handlers
        self._action_handlers: Dict[str, Callable[[EscalationEvent], Any]] = {}

        # Build lookup index for efficient rule retrieval by condition
        self._rules_by_condition: Dict[str, List[EscalationRule]] = {}
        for rule in self.rules:
            if rule.condition not in self._rules_by_condition:
                self._rules_by_condition[rule.condition] = []
            self._rules_by_condition[rule.condition].append(rule)

    def evaluate(
        self,
        condition: str,
        **context: Any
    ) -> Optional[EscalationEvent]:
        """Evaluate a condition and trigger escalation if needed.

        This is the core evaluation method. It looks up all rules for the
        given condition, finds the most severe applicable rule (based on
        threshold checks), and creates an EscalationEvent if triggered.

        When an escalation is triggered:
        1. Event is added to history
        2. Warning is logged with escalation details
        3. Operator is notified (if rule.notify_operator is True)
        4. Action is auto-executed (if rule.auto_execute is True)

        Args:
            condition: The condition identifier to evaluate (e.g., "battery_low")
            **context: Additional context for threshold evaluation
                      (e.g., battery_percent=22, heartbeat_age_s=3)

        Returns:
            EscalationEvent if an escalation was triggered, None otherwise.
            The event contains the severity level, action taken, and context.

        Example:
            >>> matrix = EscalationMatrix()
            >>> event = matrix.evaluate("battery_low", battery_percent=22)
            >>> if event:
            ...     print(f"Escalated to {event.level.name}")
            ...     print(f"Action: {event.action_taken}")
        """
        # Get all rules for this condition
        rules = self._rules_by_condition.get(condition, [])
        if not rules:
            logger.debug(f"No rules found for condition: {condition}")
            return None

        # Find the most severe applicable rule
        # A rule is applicable if its threshold is met by the context
        triggered_rule: Optional[EscalationRule] = None
        for rule in rules:
            if self._check_threshold(rule, context):
                # Keep the rule with highest severity (highest level value)
                if (triggered_rule is None or
                        rule.level.value > triggered_rule.level.value):
                    triggered_rule = rule

        # No applicable rule found
        if triggered_rule is None:
            return None

        # Create escalation event record
        event = EscalationEvent(
            level=triggered_rule.level,
            condition=condition,
            timestamp=time.time(),
            action_taken=triggered_rule.action,
            context=context
        )

        # Add to history for audit trail
        self._history.append(event)

        # Log the escalation
        logger.warning(
            f"Escalation triggered: {condition} -> {triggered_rule.level.name} "
            f"(action: {triggered_rule.action})"
        )

        # Notify operator if required by rule
        if triggered_rule.notify_operator:
            self._notify_operator(event)

        # Auto-execute action if enabled
        if triggered_rule.auto_execute:
            self._execute_action(event, triggered_rule.action)

        return event

    def get_level(self, condition: str) -> Optional[SeverityLevel]:
        """Get the highest severity level for a condition.

        Returns the maximum severity level among all rules for the given
        condition, regardless of whether thresholds are currently met.
        Useful for pre-flight risk assessment.

        Args:
            condition: The condition identifier (e.g., "battery_critical")

        Returns:
            Highest SeverityLevel for the condition, or None if no rules exist.

        Example:
            >>> matrix = EscalationMatrix()
            >>> level = matrix.get_level("battery_critical")
            >>> print(level)  # SeverityLevel.L4_CRITICAL
        """
        rules = self._rules_by_condition.get(condition, [])
        if not rules:
            return None

        return max(rules, key=lambda r: r.level.value).level

    def should_auto_execute(self, level: SeverityLevel) -> bool:
        """Check if a severity level should auto-execute.

        Auto-execution is enabled for L3 and above (Significant risk and higher).
        L1 and L2 require manual operator intervention or are informational.

        Args:
            level: The severity level to check

        Returns:
            True if actions at this level should auto-execute.

        Example:
            >>> matrix = EscalationMatrix()
            >>> matrix.should_auto_execute(SeverityLevel.L4_CRITICAL)
            True
            >>> matrix.should_auto_execute(SeverityLevel.L1_MINOR)
            False
        """
        return level.value >= SeverityLevel.L3_SIGNIFICANT.value

    def get_action(self, level: SeverityLevel) -> Optional[str]:
        """Get the default action for a severity level.

        Each severity level has a default action that is used when no
        specific action is defined in the triggering rule.

        Args:
            level: The severity level

        Returns:
            Default action string, or None if no default exists.

        Example:
            >>> matrix = EscalationMatrix()
            >>> matrix.get_action(SeverityLevel.L4_CRITICAL)
            'initiate_rtl'
        """
        action_map = {
            SeverityLevel.L1_MINOR: "log_alert",
            SeverityLevel.L2_MODERATE: "reject_command",
            SeverityLevel.L3_SIGNIFICANT: "assume_control_hold",
            SeverityLevel.L4_CRITICAL: "initiate_rtl",
            SeverityLevel.L5_EMERGENCY: "initiate_land",
            SeverityLevel.L6_CATASTROPHIC: "emergency_disarm",
        }
        return action_map.get(level)

    def get_history(self, limit: int = 10) -> List[EscalationEvent]:
        """Get escalation event history.

        Returns the most recent escalation events for analysis and
        audit purposes. Events are returned in chronological order
        (oldest to newest), but only the most recent 'limit' events
        are included.

        Args:
            limit: Maximum number of events to return (default 10)

        Returns:
            List of EscalationEvent, most recent events included.

        Example:
            >>> matrix = EscalationMatrix()
            >>> # ... some escalations occur ...
            >>> history = matrix.get_history(limit=5)
            >>> for event in history:
            ...     print(f"{event.condition}: {event.level.name}")
        """
        return list(self._history)[-limit:]

    def get_current_severity(self) -> SeverityLevel:
        """Get the current (highest) severity level from history.

        Returns the maximum severity level seen in the escalation history.
        Useful for determining the overall system safety state.

        Returns:
            Highest SeverityLevel seen, or L1_MINOR if no history exists.

        Example:
            >>> matrix = EscalationMatrix()
            >>> severity = matrix.get_current_severity()
            >>> if severity >= SeverityLevel.L4_CRITICAL:
            ...     print("Critical situation detected!")
        """
        if not self._history:
            return SeverityLevel.L1_MINOR
        return max((event.level for event in self._history), default=SeverityLevel.L1_MINOR)

    def check_battery(self, percent: float) -> Optional[EscalationEvent]:
        """Check battery level and escalate if needed.

        Convenience method that evaluates battery conditions against
        the default battery thresholds. Automatically triggers appropriate
        escalation level based on battery percentage.

        Battery Escalation Levels:
            - L5 (Emergency): 0% (total power loss)
            - L4 (Critical): <20% (initiate RTL)
            - L2 (Moderate): <25% (reject commands)
            - L1 (Minor): <30% (warning)

        Args:
            percent: Battery percentage remaining (0-100)

        Returns:
            EscalationEvent if escalated, None if battery level acceptable.

        Example:
            >>> matrix = EscalationMatrix()
            >>> event = matrix.check_battery(percent=18)
            >>> if event:
            ...     print(f"Battery critical! Action: {event.action_taken}")
        """
        # Total power loss - highest priority
        if percent <= 0:
            return self.evaluate("total_power_loss", battery_percent=percent)
        # Critical battery - initiate RTL
        elif percent < self.BATTERY_CRITICAL_THRESHOLD:
            return self.evaluate(
                "battery_critical",
                battery_percent=percent
            )
        # Low battery - reject LLM commands
        elif percent < self.BATTERY_LOW_THRESHOLD:
            return self.evaluate(
                "battery_low",
                battery_percent=percent
            )
        # Warning level - just log and alert
        elif percent < self.BATTERY_MINOR_THRESHOLD:
            return self.evaluate(
                "battery_warning",
                battery_percent=percent
            )
        return None

    def check_geofence(
        self,
        distance_m: float,
        max_m: float
    ) -> Optional[EscalationEvent]:
        """Check geofence distance and escalate if needed.

        Evaluates the drone's distance from home against the geofence radius.
        Triggers warning when approaching boundary and critical escalation
        when boundary is breached.

        Geofence Escalation Levels:
            - L4 (Critical): Beyond max distance (geofence breach -> RTL)
            - L3 (Significant): Within 50m of boundary (warning -> Hold)

        Args:
            distance_m: Current distance from home in meters
            max_m: Maximum allowed distance (geofence radius)

        Returns:
            EscalationEvent if escalated, None if within safe zone.

        Example:
            >>> matrix = EscalationMatrix()
            >>> event = matrix.check_geofence(distance_m=550, max_m=500)
            >>> if event:
            ...     print(f"Geofence breach! Distance: {event.context['overshoot_m']}m")
        """
        # Check if outside geofence (breach)
        if distance_m > max_m:
            return self.evaluate(
                "geofence_breach",
                distance_m=distance_m,
                max_m=max_m,
                overshoot_m=distance_m - max_m
            )

        # Check if approaching geofence (warning zone)
        warning_distance = max_m - self.GEOFENCE_WARNING_THRESHOLD
        if distance_m > warning_distance:
            return self.evaluate(
                "geofence_warning",
                distance_m=distance_m,
                max_m=max_m,
                remaining_m=max_m - distance_m
            )

        return None

    def check_heartbeat_timeout(self, age_s: float) -> Optional[EscalationEvent]:
        """Check heartbeat timeout and escalate if needed.

        Monitors the age of the last heartbeat from the drone. Escalation
        severity increases as the heartbeat age increases.

        Heartbeat Escalation Levels:
            - L5 (Emergency): >=10s (comm link lost -> Land)
            - L4 (Critical): >=5s (comm degraded -> RTL)
            - L2 (Moderate): >=2s (heartbeat warning -> Reject commands)

        Args:
            age_s: Seconds since last heartbeat was received

        Returns:
            EscalationEvent if escalated, None if heartbeat recent.

        Example:
            >>> matrix = EscalationMatrix()
            >>> event = matrix.check_heartbeat_timeout(age_s=6.5)
            >>> if event:
            ...     print(f"Comm degraded for {event.context['heartbeat_age_s']}s")
        """
        if age_s >= self.HEARTBEAT_EMERGENCY_THRESHOLD:
            return self.evaluate(
                "comm_link_lost",
                heartbeat_age_s=age_s
            )
        elif age_s >= self.HEARTBEAT_CRITICAL_THRESHOLD:
            return self.evaluate(
                "comm_link_degraded",
                heartbeat_age_s=age_s
            )
        elif age_s >= self.HEARTBEAT_WARNING_THRESHOLD:
            return self.evaluate(
                "heartbeat_warning",
                heartbeat_age_s=age_s
            )
        return None

    def start_timer(
        self,
        condition: str,
        level: SeverityLevel,
        timeout_s: float
    ) -> EscalationTimer:
        """Start an escalation timer for a condition.

        Creates a timer that will trigger escalation to the specified level
        if the timeout expires. Use this for conditions that should escalate
        if they persist beyond a time threshold.

        Common use cases:
            - Communication loss: Start timer for L5 after 10s
            - Geofence approach: Start timer if approaching for >5s
            - State inconsistency: Start timer if inconsistent for >3s

        Args:
            condition: The condition to track (e.g., "comm_link_lost")
            level: Severity level to escalate to if timeout expires
            timeout_s: Timeout in seconds

        Returns:
            The created EscalationTimer instance

        Example:
            >>> matrix = EscalationMatrix()
            >>> timer = matrix.start_timer("comm_check", SeverityLevel.L5_EMERGENCY, 10.0)
            >>> # ... later ...
            >>> if timer.is_expired():
            ...     print("Communication timeout - escalating!")
        """
        timer = EscalationTimer(
            condition=condition,
            level=level,
            timeout_s=timeout_s
        )
        self._timers[condition] = timer
        logger.debug(f"Started escalation timer for {condition}: {timeout_s}s")
        return timer

    def check_timers(self) -> List[EscalationEvent]:
        """Check all active timers for expired timeouts.

        Iterates through all active timers and triggers escalation for
        any that have expired. Expired timers are removed after triggering.

        This method should be called periodically in the main control loop
        to ensure timely escalation of time-based conditions.

        Returns:
            List of EscalationEvent for all expired timers.
            Empty list if no timers expired.

        Example:
            >>> matrix = EscalationMatrix()
            >>> # In main loop:
            >>> events = matrix.check_timers()
            >>> for event in events:
            ...     print(f"Timer expired: {event.condition}")
        """
        events = []
        expired_conditions = []

        for condition, timer in self._timers.items():
            if timer.is_expired():
                # Trigger escalation for expired timer
                event = self.evaluate(
                    condition,
                    timeout_triggered=True,
                    timeout_duration_s=timer.timeout_s
                )
                if event:
                    events.append(event)
                expired_conditions.append(condition)

        # Remove expired timers
        for condition in expired_conditions:
            del self._timers[condition]

        return events

    def cancel_timer(self, condition: str) -> bool:
        """Cancel an active escalation timer.

        Cancels the timer for the given condition, preventing the
        scheduled escalation. Use this when the condition resolves
        before the timeout expires.

        Args:
            condition: The condition timer to cancel

        Returns:
            True if timer was found and cancelled, False if no timer existed.

        Example:
            >>> matrix = EscalationMatrix()
            >>> timer = matrix.start_timer("comm_check", SeverityLevel.L5_EMERGENCY, 10.0)
            >>> # Communication restored:
            >>> cancelled = matrix.cancel_timer("comm_check")
            >>> print(f"Timer cancelled: {cancelled}")
        """
        if condition in self._timers:
            self._timers[condition].cancel()
            del self._timers[condition]
            logger.debug(f"Cancelled escalation timer for {condition}")
            return True
        return False

    def register_action_handler(
        self,
        action: str,
        handler: Callable[[EscalationEvent], Any]
    ) -> None:
        """Register a handler for an escalation action.

        Registers a callback function that will be invoked when the
        specified action is triggered by an escalation rule. The handler
        receives the EscalationEvent and can execute the actual safety
        action (e.g., call RTL, disarm, etc.).

        Common handlers to register:
            - "initiate_rtl": Trigger Return to Launch
            - "initiate_land": Trigger emergency landing
            - "emergency_disarm": Cut motors
            - "assume_control_hold": Enter Hold mode
            - "reject_command": Block LLM commands
            - "log_alert": Log and notify operator

        Args:
            action: The action identifier (e.g., "initiate_rtl")
            handler: Callable to invoke when action is triggered.
                    Receives the EscalationEvent as argument.

        Example:
            >>> matrix = EscalationMatrix()
            >>> def handle_rtl(event):
            ...     print(f"RTL triggered by {event.condition}")
            ...     # ... execute RTL via MAVSDK ...
            >>> matrix.register_action_handler("initiate_rtl", handle_rtl)
        """
        self._action_handlers[action] = handler
        logger.debug(f"Registered action handler for: {action}")

    # =========================================================================
    # D2.7: FAILSAFE EXECUTOR REGISTRATION
    # =========================================================================
    # These methods support the single-failsafe-consumer pattern where
    # AsyncGuardian dispatches events through EscalationMatrix.

    def register_failsafe_executor(
        self,
        action: FailsafeAction,
        executor: FailsafeExecutor,
    ) -> None:
        """Register an async executor for a failsafe action.

        D2.7: This is the primary registration method for failsafe executors.
        AsyncGuardian calls dispatch_guardian_event() which maps the
        escalation action to a FailsafeAction and calls the registered executor.

        Unlike register_action_handler which accepts sync callables,
        this method accepts async callables for non-blocking execution.

        Args:
            action: The FailsafeAction to register an executor for.
            executor: Async callable that performs the failsafe action.
                     Receives GuardianEvent as argument.

        Example:
            >>> matrix = EscalationMatrix()
            >>> async def handle_rtl(event: GuardianEvent) -> None:
            ...     drone = await get_drone()
            ...     await drone.action.return_to_launch()
            >>> matrix.register_failsafe_executor(FailsafeAction.RTL, handle_rtl)
        """
        # Store in _action_handlers with string key for compatibility
        # and also in a dedicated dict for type-safe access
        if not hasattr(self, '_failsafe_executors'):
            self._failsafe_executors: Dict[FailsafeAction, FailsafeExecutor] = {}

        self._failsafe_executors[action] = executor
        logger.debug(f"Registered failsafe executor for: {action.name}")

    async def dispatch_guardian_event(
        self,
        event: GuardianEvent,
    ) -> Optional[EscalationEvent]:
        """Dispatch a GuardianEvent to the appropriate failsafe executor.

        D2.7: This is the primary entry point for AsyncGuardian to trigger
        failsafe actions. It:

        1. Evaluates the event condition through the escalation matrix
        2. Maps the escalation action to a FailsafeAction
        3. Calls the registered async executor (if any)
        4. Returns the EscalationEvent for logging/history

        If no executor is registered for the action, logs a warning but
        does not raise - this allows graceful degradation.

        Args:
            event: GuardianEvent containing condition, reason, and context.

        Returns:
            EscalationEvent if escalation was triggered, None otherwise.

        Example:
            >>> matrix = EscalationMatrix()
            >>> # Register executor first
            >>> matrix.register_failsafe_executor(FailsafeAction.RTL, my_rtl_handler)
            >>> # Dispatch event
            >>> event = GuardianEvent(
            ...     condition="battery_critical",
            ...     reason="Battery at 18%",
            ...     context={"battery_percent": 18.0}
            ... )
            >>> escalation_event = await matrix.dispatch_guardian_event(event)
        """
        # Evaluate the condition through the matrix
        escalation_event = self.evaluate(
            event.condition,
            **event.context
        )

        if escalation_event is None:
            logger.debug(f"No escalation for guardian event: {event.condition}")
            return None

        # Map action string to FailsafeAction
        action_str = escalation_event.action_taken
        failsafe_action = self._map_action_to_failsafe(action_str)

        if failsafe_action is None:
            logger.warning(f"Unknown action '{action_str}' - cannot dispatch")
            return escalation_event

        # Call registered executor if available
        executors = getattr(self, '_failsafe_executors', {})
        executor = executors.get(failsafe_action)

        if executor is not None:
            try:
                logger.info(
                    f"Dispatching guardian event to executor: "
                    f"{event.condition} -> {failsafe_action.name}"
                )
                await executor(event)
            except Exception as e:
                logger.error(f"Failsafe executor failed for {failsafe_action.name}: {e}")
        else:
            logger.warning(
                f"No failsafe executor registered for {failsafe_action.name} - "
                f"action will not be executed"
            )

        return escalation_event

    def _map_action_to_failsafe(self, action: str) -> Optional[FailsafeAction]:
        """Map an action string to a FailsafeAction enum.

        This provides the mapping between escalation matrix action strings
        and the FailsafeAction enum used by the dispatch system.

        Args:
            action: Action string from EscalationRule.action.

        Returns:
            Corresponding FailsafeAction, or None if no mapping exists.
        """
        mapping = {
            "log_alert": FailsafeAction.LOG_ALERT,
            "reject_command": FailsafeAction.REJECT_COMMAND,
            "assume_control_hold": FailsafeAction.HOLD,
            "initiate_rtl": FailsafeAction.RTL,
            "initiate_land": FailsafeAction.LAND,
            "emergency_disarm": FailsafeAction.EMERGENCY_DISARM,
        }
        return mapping.get(action)

    def clear_history(self) -> None:
        """Clear the escalation history.

        Removes all events from the escalation history. Use this
        between missions or when resetting the safety system state.

        Note: This does not affect the current flight mode or any
        active timers. It only clears the audit trail.
        """
        self._history.clear()
        logger.debug("Escalation history cleared")

    def _check_threshold(self, rule: EscalationRule, context: Dict[str, Any]) -> bool:
        """Check if a rule's threshold is met based on context.

        Internal method that evaluates whether a rule's conditions are met
        based on the provided context values. Handles various threshold types
        including battery levels, heartbeat ages, and distances.

        Args:
            rule: The escalation rule to check
            context: Context dictionary with values for threshold evaluation

        Returns:
            True if threshold is met or no threshold is defined.

        Threshold Logic:
            - No threshold: Always returns True
            - timeout_triggered/force_trigger: Returns True (explicit trigger)
            - battery_percent: Returns True if < threshold
            - heartbeat_age_s: Returns True if >= threshold
            - remaining_m: Returns True if < threshold (geofence)
            - distance_m: Returns True if >= threshold
            - timeout_duration_s: Returns True if >= threshold
        """
        # No threshold defined - always applies
        if rule.threshold is None:
            return True

        # Explicit trigger flags override threshold checks
        if context.get("timeout_triggered") or context.get("force_trigger"):
            return True

        # Battery percentage - threshold is minimum acceptable value
        # Returns True when battery is BELOW the threshold (more dangerous)
        battery_percent = context.get("battery_percent")
        if battery_percent is not None and "battery" in rule.condition:
            if battery_percent < rule.threshold:
                return True

        # Heartbeat age - threshold is maximum acceptable value
        # Returns True when heartbeat is OLDER than threshold
        heartbeat_age_s = context.get("heartbeat_age_s")
        if heartbeat_age_s is not None and "heartbeat" in rule.condition:
            if heartbeat_age_s >= rule.threshold:
                return True

        # Communication link degraded - uses heartbeat_age_s
        if heartbeat_age_s is not None and rule.condition == "comm_link_degraded":
            if heartbeat_age_s >= rule.threshold:
                return True

        # Communication link lost - uses heartbeat_age_s
        if heartbeat_age_s is not None and rule.condition == "comm_link_lost":
            if heartbeat_age_s >= rule.threshold:
                return True

        # Geofence warning - uses remaining_m or distance_m
        # Returns True when remaining distance is LESS than threshold
        remaining_m = context.get("remaining_m")
        if remaining_m is not None and rule.condition == "geofence_warning":
            if remaining_m < rule.threshold:
                return True

        # Distance checks
        distance_m = context.get("distance_m")
        if distance_m is not None and "distance" in str(context.keys()):
            if distance_m >= rule.threshold:
                return True

        # Timeout duration - returns True when timeout is exceeded
        timeout_duration_s = context.get("timeout_duration_s")
        if timeout_duration_s is not None:
            if timeout_duration_s >= rule.threshold:
                return True

        return False

    def _notify_operator(self, event: EscalationEvent) -> None:
        """Notify the operator of an escalation event.

        Internal method that logs operator notifications. In a real system,
        this would also send notifications via websocket, SMS, dashboard alert,
        or other communication channels.

        Args:
            event: The escalation event to notify about
        """
        logger.warning(
            f"OPERATOR ALERT: {event.level.name} - {event.condition} "
            f"at {time.strftime('%H:%M:%S', time.localtime(event.timestamp))}"
        )

    def _execute_action(self, event: EscalationEvent, action: str) -> None:
        """Execute the action for an escalation event.

        Internal method that invokes the registered handler for the
        specified action. If no handler is registered, logs a warning.

        This is where the actual safety actions are triggered:
            - "initiate_rtl" -> calls RTL handler
            - "emergency_disarm" -> calls disarm handler
            - etc.

        Args:
            event: The escalation event
            action: The action to execute
        """
        logger.warning(f"AUTO-EXECUTING: {action} for {event.condition}")

        # Check for registered handler
        handler = self._action_handlers.get(action)
        if handler:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Action handler failed for {action}: {e}")
        else:
            logger.warning(f"No handler registered for action: {action}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================
# These functions provide a quick way to use the escalation matrix without
# creating an instance. They use default thresholds and rules.


def check_battery_level(percent: float) -> Optional[EscalationEvent]:
    """Check battery level using default matrix.

    Convenience function that creates a temporary EscalationMatrix and
    checks the battery level. Useful for quick one-off checks.

    Args:
        percent: Battery percentage remaining (0-100)

    Returns:
        EscalationEvent if escalated, None if battery level acceptable.

    Example:
        >>> event = check_battery_level(percent=18)
        >>> if event:
        ...     print(f"Battery critical: {event.level.name}")
    """
    matrix = EscalationMatrix()
    return matrix.check_battery(percent)


def check_geofence_breach(distance_m: float, max_m: float) -> Optional[EscalationEvent]:
    """Check geofence using default matrix.

    Convenience function that creates a temporary EscalationMatrix and
    checks geofence distance. Useful for quick one-off checks.

    Args:
        distance_m: Current distance from home in meters
        max_m: Maximum allowed distance (geofence radius)

    Returns:
        EscalationEvent if escalated, None if within safe zone.

    Example:
        >>> event = check_geofence_breach(distance_m=550, max_m=500)
        >>> if event:
        ...     print(f"Geofence breach: {event.context['overshoot_m']}m outside")
    """
    matrix = EscalationMatrix()
    return matrix.check_geofence(distance_m, max_m)


def check_heartbeat(age_s: float) -> Optional[EscalationEvent]:
    """Check heartbeat timeout using default matrix.

    Convenience function that creates a temporary EscalationMatrix and
    checks heartbeat age. Useful for quick one-off checks.

    Args:
        age_s: Seconds since last heartbeat was received

    Returns:
        EscalationEvent if escalated, None if heartbeat recent.

    Example:
        >>> event = check_heartbeat(age_s=6.5)
        >>> if event:
        ...     print(f"Heartbeat issue: {event.condition}")
    """
    matrix = EscalationMatrix()
    return matrix.check_heartbeat_timeout(age_s)


# =============================================================================
# D2.7: MODULE-LEVEL DISPATCH FUNCTION
# =============================================================================
# Provides a singleton pattern for guardian event dispatch without requiring
# a matrix instance. Uses a global matrix that can be configured once.

_GLOBAL_MATRIX: Optional[EscalationMatrix] = None


def get_global_matrix() -> EscalationMatrix:
    """Get or create the global escalation matrix.

    The global matrix is used by module-level dispatch functions.
    It's created lazily on first access.

    Returns:
        The global EscalationMatrix instance.

    Example:
        >>> matrix = get_global_matrix()
        >>> matrix.register_failsafe_executor(FailsafeAction.RTL, my_handler)
    """
    global _GLOBAL_MATRIX
    if _GLOBAL_MATRIX is None:
        _GLOBAL_MATRIX = EscalationMatrix()
    return _GLOBAL_MATRIX


def set_global_matrix(matrix: EscalationMatrix) -> None:
    """Set the global escalation matrix.

    Use this to configure the matrix before using module-level dispatch.
    Typically called once during system initialization.

    Args:
        matrix: The EscalationMatrix to use globally.

    Example:
        >>> matrix = EscalationMatrix()
        >>> matrix.register_failsafe_executor(FailsafeAction.RTL, handle_rtl)
        >>> set_global_matrix(matrix)
    """
    global _GLOBAL_MATRIX
    _GLOBAL_MATRIX = matrix


async def dispatch_guardian_event(
    event: GuardianEvent,
    matrix: Optional[EscalationMatrix] = None,
) -> Optional[EscalationEvent]:
    """Dispatch a GuardianEvent to the appropriate failsafe executor.

    D2.7: Module-level convenience function for dispatching guardian events.
    Uses the global matrix by default, or accepts a specific matrix instance.

    Args:
        event: GuardianEvent containing condition, reason, and context.
        matrix: Optional specific matrix to use. Uses global matrix if None.

    Returns:
        EscalationEvent if escalation was triggered, None otherwise.

    Example:
        >>> # Configure global matrix first (typically at startup)
        >>> matrix = get_global_matrix()
        >>> matrix.register_failsafe_executor(FailsafeAction.RTL, my_rtl_handler)
        >>>
        >>> # Dispatch events throughout the application
        >>> event = GuardianEvent(
        ...     condition="battery_critical",
        ...     reason="Battery at 18%",
        ...     context={"battery_percent": 18.0}
        ... )
        >>> result = await dispatch_guardian_event(event)
    """
    target_matrix = matrix or get_global_matrix()
    return await target_matrix.dispatch_guardian_event(event)
