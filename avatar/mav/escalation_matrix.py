"""6-level safety escalation matrix for autonomous drone operations.

Determines automated responses to safety conditions based on severity levels.
Integrates with AsyncGuardian to execute safety-critical actions.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


class SeverityLevel(IntEnum):
    """6-level severity escalation system.

    L1: Minor anomaly - Log and alert operator
    L2: Moderate risk - Reject LLM commands
    L3: Significant risk - Override to Hold mode
    L4: Critical risk - Initiate RTL (Return to Launch)
    L5: Emergency - Initiate Land
    L6: Catastrophic - Emergency disarm (if safe altitude < 10m)
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

    Attributes:
        level: The severity level this rule triggers
        condition: Human-readable condition identifier (e.g., "battery_low")
        action: Action to take (e.g., "initiate_rtl", "emergency_disarm")
        auto_execute: Whether to automatically execute the action
        notify_operator: Whether to notify the operator
        threshold: Optional numeric threshold for triggering this rule
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

    Attributes:
        level: The severity level of the event
        condition: The condition that triggered the event
        timestamp: Unix timestamp when the event occurred
        action_taken: The action that was taken (or planned)
        context: Additional context about the event
    """
    level: SeverityLevel
    condition: str
    timestamp: float
    action_taken: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationTimer:
    """Tracks escalation timeouts for a condition.

    Attributes:
        condition: The condition being tracked
        level: Severity level for timeout
        timeout_s: Timeout in seconds before escalation
        triggered_at: When the timer was started
        is_active: Whether the timer is currently running
    """
    condition: str
    level: SeverityLevel
    timeout_s: float
    triggered_at: float = field(default_factory=time.time)
    is_active: bool = field(default=True)

    def is_expired(self) -> bool:
        """Check if the timeout has expired."""
        return self.is_active and (time.time() - self.triggered_at) >= self.timeout_s

    def remaining_s(self) -> float:
        """Get remaining seconds before timeout."""
        if not self.is_active:
            return 0.0
        elapsed = time.time() - self.triggered_at
        return max(0.0, self.timeout_s - elapsed)

    def cancel(self) -> None:
        """Cancel the timer."""
        self.is_active = False


class EscalationMatrix:
    """6-level safety escalation matrix.

    Levels:
    L1: Minor anomaly -> Log, alert operator
    L2: Moderate risk -> Reject LLM commands
    L3: Significant risk -> Override to Hold mode
    L4: Critical risk -> Initiate RTL
    L5: Emergency -> Initiate Land
    L6: Catastrophic -> Emergency disarm (if safe altitude < 10m)

    Usage:
        matrix = EscalationMatrix()

        # Evaluate condition
        event = matrix.evaluate("low_battery", battery_percent=20)
        if event and event.level >= SeverityLevel.L4_CRITICAL:
            await guardian.initiate_rtl(event.action_taken)

        # Check battery level
        event = matrix.check_battery(percent=15)

        # Check geofence
        event = matrix.check_geofence(distance_m=550, max_m=500)

        # Get escalation history
        history = matrix.get_history(limit=10)
    """

    DEFAULT_RULES: List[EscalationRule] = [
        # L1: Minor anomalies - just log and alert
        EscalationRule(
            SeverityLevel.L1_MINOR,
            "battery_warning",
            "log_alert",
            False,
            True,
            threshold=30.0
        ),
        EscalationRule(
            SeverityLevel.L1_MINOR,
            "telemetry_stale",
            "log_alert",
            False,
            True,
            threshold=5.0
        ),

        # L2: Moderate risk - reject commands
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "battery_low",
            "reject_command",
            True,
            True,
            threshold=25.0
        ),
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "command_validation_fail",
            "reject_command",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L2_MODERATE,
            "heartbeat_warning",
            "reject_command",
            True,
            True,
            threshold=2.0
        ),

        # L3: Significant risk - assume control to Hold
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "state_inconsistency",
            "assume_control_hold",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "mode_change_fail",
            "assume_control_hold",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L3_SIGNIFICANT,
            "geofence_warning",
            "assume_control_hold",
            True,
            True,
            threshold=50.0  # meters before geofence
        ),

        # L4: Critical risk - RTL
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "battery_critical",
            "initiate_rtl",
            True,
            True,
            threshold=20.0
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "geofence_breach",
            "initiate_rtl",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "comm_link_degraded",
            "initiate_rtl",
            True,
            True,
            threshold=5.0  # seconds
        ),
        EscalationRule(
            SeverityLevel.L4_CRITICAL,
            "gps_degraded",
            "initiate_rtl",
            True,
            True
        ),

        # L5: Emergency - Land
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "total_power_loss",
            "initiate_land",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "comm_link_lost",
            "initiate_land",
            True,
            True,
            threshold=10.0  # seconds
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "engine_failure",
            "initiate_land",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L5_EMERGENCY,
            "flight_stability_critical",
            "initiate_land",
            True,
            True
        ),

        # L6: Catastrophic - Emergency disarm
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "total_system_failure",
            "emergency_disarm",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "uncontrolled_descent",
            "emergency_disarm",
            True,
            True
        ),
        EscalationRule(
            SeverityLevel.L6_CATASTROPHIC,
            "unauthorized_control_takeover",
            "emergency_disarm",
            True,
            True
        ),
    ]

    # Default thresholds for battery levels
    BATTERY_MINOR_THRESHOLD = 30.0
    BATTERY_LOW_THRESHOLD = 25.0
    BATTERY_CRITICAL_THRESHOLD = 20.0

    # Default thresholds for geofence
    GEOFENCE_WARNING_THRESHOLD = 50.0  # meters before boundary

    # Default thresholds for heartbeat
    HEARTBEAT_WARNING_THRESHOLD = 2.0
    HEARTBEAT_CRITICAL_THRESHOLD = 5.0
    HEARTBEAT_EMERGENCY_THRESHOLD = 10.0

    def __init__(
        self,
        rules: Optional[List[EscalationRule]] = None,
        history_size: int = 100
    ):
        """Initialize the escalation matrix.

        Args:
            rules: Custom escalation rules. Uses DEFAULT_RULES if not provided.
            history_size: Maximum number of events to keep in history.
        """
        self.rules = rules or self.DEFAULT_RULES.copy()
        self._history: deque[EscalationEvent] = deque(maxlen=history_size)
        self._timers: Dict[str, EscalationTimer] = {}
        self._action_handlers: Dict[str, Callable[[EscalationEvent], Any]] = {}

        # Build lookup for rules by condition
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

        Args:
            condition: The condition identifier to evaluate
            **context: Additional context for evaluation

        Returns:
            EscalationEvent if an escalation was triggered, None otherwise
        """
        rules = self._rules_by_condition.get(condition, [])
        if not rules:
            logger.debug(f"No rules found for condition: {condition}")
            return None

        # Find the most severe applicable rule
        triggered_rule: Optional[EscalationRule] = None
        for rule in rules:
            if self._check_threshold(rule, context):
                if (triggered_rule is None or
                        rule.level.value > triggered_rule.level.value):
                    triggered_rule = rule

        if triggered_rule is None:
            return None

        # Create escalation event
        event = EscalationEvent(
            level=triggered_rule.level,
            condition=condition,
            timestamp=time.time(),
            action_taken=triggered_rule.action,
            context=context
        )

        # Add to history
        self._history.append(event)

        # Log the escalation
        logger.warning(
            f"Escalation triggered: {condition} -> {triggered_rule.level.name} "
            f"(action: {triggered_rule.action})"
        )

        # Notify operator if required
        if triggered_rule.notify_operator:
            self._notify_operator(event)

        # Auto-execute if enabled
        if triggered_rule.auto_execute:
            self._execute_action(event, triggered_rule.action)

        return event

    def get_level(self, condition: str) -> Optional[SeverityLevel]:
        """Get the highest severity level for a condition.

        Args:
            condition: The condition identifier

        Returns:
            Highest SeverityLevel for the condition, or None if no rules
        """
        rules = self._rules_by_condition.get(condition, [])
        if not rules:
            return None

        return max(rules, key=lambda r: r.level.value).level

    def should_auto_execute(self, level: SeverityLevel) -> bool:
        """Check if a severity level should auto-execute.

        Args:
            level: The severity level to check

        Returns:
            True if actions at this level should auto-execute
        """
        return level.value >= SeverityLevel.L3_SIGNIFICANT.value

    def get_action(self, level: SeverityLevel) -> Optional[str]:
        """Get the default action for a severity level.

        Args:
            level: The severity level

        Returns:
            Default action string, or None if no default
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

        Args:
            limit: Maximum number of events to return

        Returns:
            List of EscalationEvent, most recent first
        """
        return list(self._history)[-limit:]

    def get_current_severity(self) -> SeverityLevel:
        """Get the current (highest) severity level from history.

        Returns:
            Highest SeverityLevel seen, or L1_MINOR if no history
        """
        if not self._history:
            return SeverityLevel.L1_MINOR
        return max((event.level for event in self._history), default=SeverityLevel.L1_MINOR)

    def check_battery(self, percent: float) -> Optional[EscalationEvent]:
        """Check battery level and escalate if needed.

        Args:
            percent: Battery percentage remaining

        Returns:
            EscalationEvent if escalated, None otherwise
        """
        if percent <= 0:
            return self.evaluate("total_power_loss", battery_percent=percent)
        elif percent < self.BATTERY_CRITICAL_THRESHOLD:
            return self.evaluate(
                "battery_critical",
                battery_percent=percent
            )
        elif percent < self.BATTERY_LOW_THRESHOLD:
            return self.evaluate(
                "battery_low",
                battery_percent=percent
            )
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

        Args:
            distance_m: Current distance from home in meters
            max_m: Maximum allowed distance (geofence radius)

        Returns:
            EscalationEvent if escalated, None otherwise
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

        Args:
            age_s: Seconds since last heartbeat

        Returns:
            EscalationEvent if escalated, None otherwise
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

        Args:
            condition: The condition to track
            level: Severity level if timeout expires
            timeout_s: Timeout in seconds

        Returns:
            The created EscalationTimer
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

        Returns:
            List of EscalationEvent for expired timers
        """
        events = []
        expired_conditions = []

        for condition, timer in self._timers.items():
            if timer.is_expired():
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

        Args:
            condition: The condition timer to cancel

        Returns:
            True if timer was found and cancelled, False otherwise
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

        Args:
            action: The action identifier
            handler: Callable to invoke when action is triggered
        """
        self._action_handlers[action] = handler
        logger.debug(f"Registered action handler for: {action}")

    def clear_history(self) -> None:
        """Clear the escalation history."""
        self._history.clear()
        logger.debug("Escalation history cleared")

    def _check_threshold(self, rule: EscalationRule, context: Dict[str, Any]) -> bool:
        """Check if a rule's threshold is met based on context.

        Args:
            rule: The escalation rule to check
            context: Context dictionary with values

        Returns:
            True if threshold is met or no threshold defined
        """
        if rule.threshold is None:
            return True

        # If explicitly triggered
        if context.get("timeout_triggered") or context.get("force_trigger"):
            return True

        # Check for specific known value keys
        # Battery percentage - threshold is minimum acceptable value
        battery_percent = context.get("battery_percent")
        if battery_percent is not None and "battery" in rule.condition:
            if battery_percent < rule.threshold:
                return True

        # Heartbeat age - threshold is maximum acceptable value
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
        remaining_m = context.get("remaining_m")
        if remaining_m is not None and rule.condition == "geofence_warning":
            if remaining_m < rule.threshold:
                return True

        # Distance checks
        distance_m = context.get("distance_m")
        if distance_m is not None and "distance" in str(context.keys()):
            if distance_m >= rule.threshold:
                return True

        # Timeout duration
        timeout_duration_s = context.get("timeout_duration_s")
        if timeout_duration_s is not None:
            if timeout_duration_s >= rule.threshold:
                return True

        return False

    def _notify_operator(self, event: EscalationEvent) -> None:
        """Notify the operator of an escalation event.

        Args:
            event: The escalation event to notify about
        """
        logger.warning(
            f"OPERATOR ALERT: {event.level.name} - {event.condition} "
            f"at {time.strftime('%H:%M:%S', time.localtime(event.timestamp))}"
        )

    def _execute_action(self, event: EscalationEvent, action: str) -> None:
        """Execute the action for an escalation event.

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


# Convenience functions for common checks
def check_battery_level(percent: float) -> Optional[EscalationEvent]:
    """Check battery level using default matrix.

    Args:
        percent: Battery percentage remaining

    Returns:
        EscalationEvent if escalated, None otherwise
    """
    matrix = EscalationMatrix()
    return matrix.check_battery(percent)


def check_geofence_breach(distance_m: float, max_m: float) -> Optional[EscalationEvent]:
    """Check geofence using default matrix.

    Args:
        distance_m: Current distance from home in meters
        max_m: Maximum allowed distance

    Returns:
        EscalationEvent if escalated, None otherwise
    """
    matrix = EscalationMatrix()
    return matrix.check_geofence(distance_m, max_m)


def check_heartbeat(age_s: float) -> Optional[EscalationEvent]:
    """Check heartbeat timeout using default matrix.

    Args:
        age_s: Seconds since last heartbeat

    Returns:
        EscalationEvent if escalated, None otherwise
    """
    matrix = EscalationMatrix()
    return matrix.check_heartbeat_timeout(age_s)
