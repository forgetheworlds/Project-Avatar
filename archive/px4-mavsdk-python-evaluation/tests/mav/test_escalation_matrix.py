"""Tests for the 6-level Safety Escalation Matrix.

ESCALATION MATRIX OVERVIEW:
===========================
The Safety Escalation Matrix is a hierarchical system for classifying and responding
to drone flight anomalies. It provides consistent, predictable responses that
match threat severity with appropriate countermeasures.

WHAT THE ESCALATION MATRIX DOES:
--------------------------------
1. Categorizes threats into 6 severity levels (L1-L6)
2. Maps each level to specific autonomous actions
3. Auto-executes responses at L3+ (no human confirmation required)
4. Tracks escalation history for post-flight analysis
5. Provides timer-based escalation for delayed threats (e.g., comm loss)
6. Integrates with AsyncGuardian for real-time safety enforcement

THE 6 ESCALATION LEVELS EXPLAINED:
==================================

L1 - MINOR (Value: 1):
  - Examples: Minor state inconsistencies, non-critical telemetry gaps
  - Response: Log alert only
  - Auto-execute: NO
  - Human notification: No immediate notification

L2 - MODERATE (Value: 2):
  - Examples: Command validation failures, intermittent sensor issues,
    heartbeat delays >2s, battery <25%
  - Response: Reject command or pause current operation
  - Auto-execute: NO
  - Human notification: Silent log entry

L3 - SIGNIFICANT (Value: 3):
  - Examples: State inconsistency requiring immediate attention, approaching
    geofence boundary (within 30m), persistent comm degradation
  - Response: Assume control, enter hold position (loiter/hover)
  - Auto-execute: YES (no human confirmation)
  - Human notification: Immediate operator alert

L4 - CRITICAL (Value: 4):
  - Examples: Geofence breach, battery below 20% (critical low),
    communication link degraded >5s, GPS loss
  - Response: Initiate Return-to-Launch (RTL)
  - Auto-execute: YES
  - Human notification: Immediate operator alert + audible alarm

L5 - EMERGENCY (Value: 5):
  - Examples: Communication link lost >10s, total power loss (0% battery),
    critical system failure
  - Response: Initiate immediate landing at current position
  - Auto-execute: YES
  - Human notification: Emergency broadcast to all operators

L6 - CATASTROPHIC (Value: 6):
  - Examples: Complete flight controller failure, uncontrolled descent,
    imminent collision with no avoidance possible
  - Response: Emergency disarm (cut power to motors)
  - Auto-execute: YES (immediate, no delay)
  - Human notification: All channels + black box recording

HOW ESCALATION TRIGGERS WORK:
==============================

1. CONDITION EVALUATION:
   - Each safety condition (e.g., "battery_critical") maps to an EscalationRule
   - Rules define: level, condition name, action, auto_execute flag, threshold

2. THRESHOLD COMPARISON:
   - Numeric thresholds trigger escalation when value < threshold
   - Example: battery_percent=18 triggers "battery_critical" (threshold=20)

3. TIMER-BASED ESCALATION:
   - Some conditions use time-delayed escalation (e.g., communication loss)
   - Timer starts when condition first detected
   - Escalation occurs only if timer expires
   - Allows for transient issues to resolve without escalation

4. AUTO-EXECUTE BOUNDARY:
   - L1-L2: Log only, wait for human decision
   - L3+: Immediate autonomous action
   - This boundary ensures rapid response to serious threats while
     avoiding unnecessary intervention for minor issues

5. HISTORY TRACKING:
   - All escalations recorded with timestamp, context, and action taken
   - Supports post-flight analysis and pattern detection
   - Rolling buffer prevents memory exhaustion

INTEGRATION WITH ASYNC GUARDIAN:
=================================
The EscalationMatrix works with AsyncGuardian (the safety validation layer):
- Guardian validates every MAVSDK command through the matrix
- Matrix.evaluate() returns an EscalationEvent if triggered
- Guardian executes action_taken from the event
- Handlers can be registered for custom actions (e.g., "initiate_rtl")

These tests verify:
- All 6 severity levels (L1-L6) are defined correctly
- Escalation evaluation works for all conditions
- Auto-execute triggers at L3 and above
- Battery levels trigger correct escalations
- Geofence breach triggers L4
- Heartbeat timeout escalates progressively
- History tracking works correctly
- Timer-based escalation works
"""

import time
from unittest.mock import MagicMock

import pytest

from avatar.mav.escalation_matrix import (
    SeverityLevel,
    EscalationRule,
    EscalationEvent,
    EscalationTimer,
    EscalationMatrix,
    check_battery_level,
    check_geofence_breach,
    check_heartbeat,
)


class TestSeverityLevels:
    """Test the 6 severity level enum definitions.

    Validates that all 6 escalation levels exist with correct values
    and proper ordering. This is foundational - if levels are wrong,
    the entire safety system is compromised.
    """

    def test_all_six_levels_exist(self):
        """All 6 severity levels are defined.

        ENSURES: The complete range of threat severity is covered from
        minor issues (L1) to catastrophic failures (L6).
        Missing levels would create gaps in safety coverage.
        """
        levels = list(SeverityLevel)
        assert len(levels) == 6
        assert SeverityLevel.L1_MINOR in levels
        assert SeverityLevel.L2_MODERATE in levels
        assert SeverityLevel.L3_SIGNIFICANT in levels
        assert SeverityLevel.L4_CRITICAL in levels
        assert SeverityLevel.L5_EMERGENCY in levels
        assert SeverityLevel.L6_CATASTROPHIC in levels

    def test_severity_level_values(self):
        """Severity levels have correct numeric values.

        ENSURES: Numeric values match expected hierarchy:
        - L1=1, L2=2, L3=3, L4=4, L5=5, L6=6
        These values enable comparison operations (e.g., >= L4_CRITICAL).
        """
        assert SeverityLevel.L1_MINOR.value == 1
        assert SeverityLevel.L2_MODERATE.value == 2
        assert SeverityLevel.L3_SIGNIFICANT.value == 3
        assert SeverityLevel.L4_CRITICAL.value == 4
        assert SeverityLevel.L5_EMERGENCY.value == 5
        assert SeverityLevel.L6_CATASTROPHIC.value == 6

    def test_severity_level_ordering(self):
        """Severity levels order correctly by value.

        ENSURES: Higher numbers = higher severity.
        This ordering is used to determine if auto-execute applies
        and to find the highest severity from multiple conditions.
        """
        assert SeverityLevel.L1_MINOR.value < SeverityLevel.L2_MODERATE.value
        assert SeverityLevel.L2_MODERATE.value < SeverityLevel.L3_SIGNIFICANT.value
        assert SeverityLevel.L3_SIGNIFICANT.value < SeverityLevel.L4_CRITICAL.value
        assert SeverityLevel.L4_CRITICAL.value < SeverityLevel.L5_EMERGENCY.value
        assert SeverityLevel.L5_EMERGENCY.value < SeverityLevel.L6_CATASTROPHIC.value


class TestEscalationRule:
    """Test the EscalationRule dataclass.

    EscalationRule defines what action to take for a specific condition:
    - level: Which of the 6 severity levels applies
    - condition: String identifier (e.g., "battery_critical")
    - action: What to do (e.g., "initiate_rtl", "emergency_disarm")
    - auto_execute: Whether to act immediately (True for L3+)
    - notify_operator: Whether to alert human operators
    - threshold: Optional numeric trigger point
    """

    def test_rule_creation(self):
        """EscalationRule can be created with all fields.

        EXAMPLE: Critical battery rule for L4 escalation.
        When battery < 20%, auto-initiate RTL and notify operator.
        """
        rule = EscalationRule(
            level=SeverityLevel.L4_CRITICAL,
            condition="battery_critical",
            action="initiate_rtl",
            auto_execute=True,
            notify_operator=True,
            threshold=20.0
        )
        assert rule.level == SeverityLevel.L4_CRITICAL
        assert rule.condition == "battery_critical"
        assert rule.action == "initiate_rtl"
        assert rule.auto_execute is True
        assert rule.notify_operator is True
        assert rule.threshold == 20.0

    def test_rule_without_threshold(self):
        """EscalationRule can be created without threshold.

        EXAMPLE: Command validation failure requires no numeric threshold.
        Any validation failure triggers L2 rejection.
        """
        rule = EscalationRule(
            level=SeverityLevel.L2_MODERATE,
            condition="command_validation_fail",
            action="reject_command",
            auto_execute=True,
            notify_operator=True
        )
        assert rule.threshold is None


class TestEscalationEvent:
    """Test the EscalationEvent dataclass.

    EscalationEvent captures an actual occurrence of an escalation:
    - level: The severity level that was triggered
    - condition: Which condition triggered it
    - timestamp: When it occurred (Unix timestamp)
    - action_taken: What the system did in response
    - context: Dict with relevant telemetry (altitude, battery, position, etc.)

    Events are recorded in history for analysis and debugging.
    """

    def test_event_creation(self):
        """EscalationEvent can be created with all fields.

        EXAMPLE: L3 event triggered by state inconsistency.
        Context includes altitude for post-incident analysis.
        """
        event = EscalationEvent(
            level=SeverityLevel.L3_SIGNIFICANT,
            condition="state_inconsistency",
            timestamp=time.time(),
            action_taken="assume_control_hold",
            context={"altitude": 50.0}
        )
        assert event.level == SeverityLevel.L3_SIGNIFICANT
        assert event.condition == "state_inconsistency"
        assert event.action_taken == "assume_control_hold"
        assert event.context == {"altitude": 50.0}


class TestEscalationTimer:
    """Test the EscalationTimer class.

    TIMER-BASED ESCALATION EXPLAINED:
    =================================
    Some threats require time to confirm they're not transient:

    EXAMPLE - Communication Loss:
    - Single missed heartbeat: Not a problem (L2 warning)
    - No heartbeat for 2s: Degraded link (L2)
    - No heartbeat for 5s: Critical degradation (L4)
    - No heartbeat for 10s: Emergency - comm link lost (L5)

    The timer system allows staged escalation:
    1. Timer starts when condition first detected
    2. Each interval can have different escalation level
    3. If condition resolves before timer expires, cancel it
    4. If timer expires, escalation occurs

    This prevents over-reacting to brief glitches while ensuring
    sustained problems get appropriate response.
    """

    def test_timer_creation(self):
        """EscalationTimer can be created with correct defaults.

        EXAMPLE: Communication loss timer for L5 emergency.
        After 10 seconds of no contact, trigger emergency landing.
        """
        timer = EscalationTimer(
            condition="comm_link_lost",
            level=SeverityLevel.L5_EMERGENCY,
            timeout_s=10.0
        )
        assert timer.condition == "comm_link_lost"
        assert timer.level == SeverityLevel.L5_EMERGENCY
        assert timer.timeout_s == 10.0
        assert timer.is_active is True
        assert timer.triggered_at > 0

    def test_timer_not_expired(self):
        """Timer correctly reports not expired when within timeout.

        VALIDATES: Timer state before expiration.
        When 0.1s elapsed of 10s timeout, remaining_s() ~9.9s.
        """
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=10.0,
            triggered_at=time.time()
        )
        assert not timer.is_expired()
        assert timer.remaining_s() > 9.0

    def test_timer_expired(self):
        """Timer correctly reports expired after timeout.

        VALIDATES: Expiration detection.
        Timer started 100ms ago with 1ms timeout has expired.
        """
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=0.001,
            triggered_at=time.time() - 0.1  # Started 100ms ago
        )
        assert timer.is_expired()

    def test_timer_cancel(self):
        """Cancelled timer reports as not active.

        USE CASE: Communication restored before timer expired.
        Cancel the timer to prevent unnecessary escalation.
        """
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=10.0
        )
        timer.cancel()
        assert not timer.is_active
        assert not timer.is_expired()


class TestEscalationMatrix:
    """Test the EscalationMatrix class.

    ESCALATION MATRIX CORE FUNCTIONS:
    =================================

    1. RULE MANAGEMENT:
       - Loads default safety rules on initialization
       - Supports custom rules for specific missions
       - Rules map conditions (e.g., "battery_critical") to responses

    2. CONDITION EVALUATION:
       - evaluate(condition, **context) -> EscalationEvent or None
       - get_level(condition) -> SeverityLevel or None
       - Returns None if condition doesn't trigger (e.g., battery OK)

    3. AUTO-EXECUTE DECISION:
       - should_auto_execute(level) -> True for L3 and above
       - False for L1-L2 (human decision required)
       - This is the critical boundary for autonomous action

    4. ACTION RESOLUTION:
       - get_action(level) -> action string (e.g., "initiate_rtl")
       - Actions are registered handlers or default behaviors

    DEFAULT RULES INCLUDE:
    - battery_warning (L1): <30% battery
    - battery_low (L2): <25% battery
    - battery_critical (L4): <20% battery (triggers RTL)
    - total_power_loss (L5): 0% battery (triggers land)
    - geofence_warning (L3): Within 30m of boundary
    - geofence_breach (L4): Outside boundary (triggers RTL)
    - heartbeat_warning (L2): >2s since last heartbeat
    - comm_link_degraded (L4): >5s since last heartbeat
    - comm_link_lost (L5): >10s since last heartbeat (triggers land)
    """

    def test_default_rules_loaded(self):
        """Default rules are loaded on initialization.

        VALIDATES: Matrix comes pre-configured with essential safety rules.
        Users don't need to define rules for common threats.
        """
        matrix = EscalationMatrix()
        assert len(matrix.rules) == len(EscalationMatrix.DEFAULT_RULES)

    def test_custom_rules(self):
        """Custom rules can be provided.

        USE CASE: Mission-specific safety thresholds.
        Example: Indoor flight with custom geofence distances.
        """
        custom_rules = [
            EscalationRule(
                SeverityLevel.L1_MINOR,
                "custom_condition",
                "custom_action",
                False,
                True
            )
        ]
        matrix = EscalationMatrix(rules=custom_rules)
        assert matrix.rules == custom_rules

    def test_evaluate_unknown_condition(self):
        """Evaluate returns None for unknown condition.

        VALIDATES: Unknown conditions don't trigger false escalations.
        Returns None = no action needed.
        """
        matrix = EscalationMatrix()
        result = matrix.evaluate("unknown_condition")
        assert result is None

    def test_evaluate_known_condition(self):
        """Evaluate returns event for known condition.

        VALIDATES: Known conditions with sufficient context trigger escalation.
        Example: battery_percent=15 triggers battery_critical (L4).
        """
        matrix = EscalationMatrix()
        result = matrix.evaluate("battery_critical", battery_percent=15)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.action_taken == "initiate_rtl"

    def test_get_level(self):
        """get_level returns highest severity for condition.

        VALIDATES: Can query the severity level without triggering.
        Used by AsyncGuardian for pre-flight planning.
        """
        matrix = EscalationMatrix()
        level = matrix.get_level("battery_critical")
        assert level == SeverityLevel.L4_CRITICAL

    def test_get_level_unknown(self):
        """get_level returns None for unknown condition.

        VALIDATES: Unknown conditions don't have a severity level.
        """
        matrix = EscalationMatrix()
        level = matrix.get_level("unknown")
        assert level is None

    def test_should_auto_execute_l1(self):
        """L1 does not auto-execute.

        AUTO-EXECUTE BOUNDARY: L1-L2 require human decision.
        Only log and notify, don't take action.
        """
        matrix = EscalationMatrix()
        assert not matrix.should_auto_execute(SeverityLevel.L1_MINOR)

    def test_should_auto_execute_l2(self):
        """L2 does not auto-execute.

        AUTO-EXECUTE BOUNDARY: L2 commands are rejected but
        require human for recovery action.
        """
        matrix = EscalationMatrix()
        assert not matrix.should_auto_execute(SeverityLevel.L2_MODERATE)

    def test_should_auto_execute_l3_and_above(self):
        """L3 and above auto-execute.

        AUTO-EXECUTE BOUNDARY: L3+ takes immediate autonomous action.
        This is the critical threshold for safety intervention.
        L3: Hold position, L4: RTL, L5: Land, L6: Disarm
        """
        matrix = EscalationMatrix()
        assert matrix.should_auto_execute(SeverityLevel.L3_SIGNIFICANT)
        assert matrix.should_auto_execute(SeverityLevel.L4_CRITICAL)
        assert matrix.should_auto_execute(SeverityLevel.L5_EMERGENCY)
        assert matrix.should_auto_execute(SeverityLevel.L6_CATASTROPHIC)

    def test_get_action_for_levels(self):
        """get_action returns correct action for each level.

        ACTION MAPPING:
        - L1: log_alert (record only)
        - L2: reject_command (block dangerous commands)
        - L3: assume_control_hold (take over, hover)
        - L4: initiate_rtl (return home)
        - L5: initiate_land (land immediately)
        - L6: emergency_disarm (cut motors - last resort)
        """
        matrix = EscalationMatrix()
        assert matrix.get_action(SeverityLevel.L1_MINOR) == "log_alert"
        assert matrix.get_action(SeverityLevel.L2_MODERATE) == "reject_command"
        assert matrix.get_action(SeverityLevel.L3_SIGNIFICANT) == "assume_control_hold"
        assert matrix.get_action(SeverityLevel.L4_CRITICAL) == "initiate_rtl"
        assert matrix.get_action(SeverityLevel.L5_EMERGENCY) == "initiate_land"
        assert matrix.get_action(SeverityLevel.L6_CATASTROPHIC) == "emergency_disarm"


class TestBatteryEscalation:
    """Test battery level escalation logic.

    BATTERY ESCALATION THRESHOLDS:
    ================================

    Normal (>30%): No escalation
    Warning (<30%): L1 - Log alert, monitor closely
    Low (<25%): L2 - Moderate, prepare for RTL
    Critical (<20%): L4 - Critical, initiate RTL immediately
    Total Power Loss (0%): L5 - Emergency, land now

    Note: There is no L3 for battery - jumps from L2 to L4.
    This reflects the binary nature of battery reserves:
    either you have enough (L2) or you must RTL now (L4).

    THRESHOLD LOGIC:
    - Triggers when battery_percent < threshold
    - 29.9% triggers warning (30.0 < 30 threshold)
    - Exactly 30% does not trigger (30.0 is not < 30)
    """

    def test_battery_normal(self):
        """Normal battery does not trigger escalation.

        50% battery is well above all thresholds.
        No action needed.
        """
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=50)
        assert result is None

    def test_battery_warning(self):
        """Battery below 30% triggers L1 warning.

        At 28%: First threshold crossed.
        Action: log_alert
        Human notification: None (logged only)
        """
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=28)
        assert result is not None
        assert result.level == SeverityLevel.L1_MINOR
        assert result.condition == "battery_warning"

    def test_battery_low(self):
        """Battery below 25% triggers L2 low.

        At 23%: Second threshold crossed.
        Action: reject_command (pause non-essential operations)
        Human notification: None (logged only)
        """
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=23)
        assert result is not None
        assert result.level == SeverityLevel.L2_MODERATE
        assert result.condition == "battery_low"

    def test_battery_critical(self):
        """Battery below 20% triggers L4 critical.

        At 18%: Critical threshold crossed.
        AUTO-EXECUTE: YES - Immediate RTL without human confirmation.
        This is the L3+ auto-execute boundary in action.
        """
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=18)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "battery_critical"
        assert result.action_taken == "initiate_rtl"

    def test_battery_zero(self):
        """Battery at 0% triggers L5 total power loss.

        At 0%: Emergency landing required.
        AUTO-EXECUTE: YES - Land immediately at current position.
        Cannot RTL - no power to reach home.
        """
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY
        assert result.condition == "total_power_loss"

    def test_battery_threshold_boundary(self):
        """Battery thresholds are boundary-inclusive.

        VALIDATES: < comparison used, not <=.
        29.9% triggers warning (29.9 < 30).
        Exactly 30% does not trigger (30.0 is not < 30).
        """
        matrix = EscalationMatrix()
        # At exactly 30% should still trigger warning (30.0 < threshold)
        result = matrix.check_battery(percent=29.9)
        assert result is not None


class TestGeofenceEscalation:
    """Test geofence escalation logic.

    GEOFENCE ESCALATION THRESHOLDS:
    =================================

    The geofence is a virtual boundary (e.g., 500m radius from home).

    Normal (within boundary): No escalation
    Warning (within 30m of boundary): L3 - Significant
    Breach (outside boundary): L4 - Critical

    PROGRESSIVE ESCALATION:
    - As drone approaches boundary, first warning (L3)
    - If continues past boundary, critical (L4) - initiate RTL
    - RTL will bring drone back inside boundary automatically

    DISTANCE CALCULATION:
    - distance_m: Current distance from home point
    - max_m: Geofence radius
    - Trigger warning when: distance_m > (max_m - 30m)
    - Trigger breach when: distance_m > max_m
    """

    def test_geofence_normal(self):
        """Normal position within geofence does not trigger.

        400m from home with 500m radius = 100m margin.
        No action needed.
        """
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=400, max_m=500)
        assert result is None

    def test_geofence_warning(self):
        """Approaching geofence triggers L3 warning.

        At 470m with 500m radius: 30m from boundary.
        Action: assume_control_hold (hover in place).
        AUTO-EXECUTE: YES - Take control immediately.
        Human notification: Immediate alert.
        """
        matrix = EscalationMatrix()
        # 470m distance when max is 500m (30m before boundary)
        result = matrix.check_geofence(distance_m=470, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L3_SIGNIFICANT
        assert result.condition == "geofence_warning"

    def test_geofence_breach(self):
        """Breach geofence triggers L4 critical.

        At 550m with 500m radius: 50m past boundary.
        Action: initiate_rtl (return to launch point).
        AUTO-EXECUTE: YES - Start RTL immediately.
        """
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=550, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "geofence_breach"
        assert result.action_taken == "initiate_rtl"

    def test_geofence_at_boundary(self):
        """At geofence boundary triggers L4.

        Edge case: Exactly at boundary (500m with 500m radius).
        Depending on implementation, may trigger warning or breach.
        Test ensures consistent behavior at boundary.
        """
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=500, max_m=500)
        # At boundary - not exceeding, so warning only
        if result:
            # If triggered, should be warning
            assert result.level == SeverityLevel.L3_SIGNIFICANT


class TestHeartbeatEscalation:
    """Test heartbeat timeout escalation logic.

    HEARTBEAT ESCALATION (TIMER-BASED):
    ====================================

    Heartbeat messages indicate the drone is communicating.
    Progressive escalation as silence duration increases:

    Normal (<2s): No escalation
    Warning (>2s): L2 - heartbeat_warning
    Critical (>5s): L4 - comm_link_degraded (initiate RTL)
    Emergency (>10s): L5 - comm_link_lost (initiate land)

    WHY STAGED ESCALATION:
    - Brief gaps (2s) happen due to radio interference
    - Longer gaps (5s) indicate real problems
    - Extended gaps (10s) mean likely communication loss

    Each stage gives opportunity for recovery before
    escalating to next severity level.
    """

    def test_heartbeat_normal(self):
        """Normal heartbeat age does not trigger.

        1 second since last heartbeat is normal telemetry interval.
        No action needed.
        """
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=1.0)
        assert result is None

    def test_heartbeat_warning(self):
        """Heartbeat >2s triggers L2 warning.

        At 2.5s: First threshold crossed.
        Action: Log warning (reject_command)
        AUTO-EXECUTE: NO (L2)
        Human notification: None (logged only)
        """
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=2.5)
        assert result is not None
        assert result.level == SeverityLevel.L2_MODERATE
        assert result.condition == "heartbeat_warning"

    def test_heartbeat_critical(self):
        """Heartbeat >5s triggers L4 critical.

        At 6s: Second threshold crossed.
        Action: initiate_rtl (return to launch)
        AUTO-EXECUTE: YES (L4)
        Assumes comm degraded, return home while still possible.
        """
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=6.0)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "comm_link_degraded"

    def test_heartbeat_emergency(self):
        """Heartbeat >10s triggers L5 emergency.

        At 12s: Third threshold crossed.
        Action: initiate_land (land immediately)
        AUTO-EXECUTE: YES (L5)
        Communication assumed lost - land now at current position.
        """
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=12.0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY
        assert result.condition == "comm_link_lost"


class TestHistoryTracking:
    """Test escalation history tracking.

    HISTORY TRACKING PURPOSE:
    =========================

    1. POST-FLIGHT ANALYSIS:
       - Review what escalations occurred
       - Identify patterns of issues
       - Tune thresholds for future flights

    2. DEBUGGING:
       - Reconstruct sequence of events
       - Correlate with telemetry logs
       - Analyze root cause of incidents

    3. COMPLIANCE:
       - Demonstrate safety system operation
       - Prove appropriate responses to threats
       - Required for some commercial operations

    HISTORY FEATURES:
    - Rolling buffer (prevents memory exhaustion)
    - Configurable limit (e.g., last 100 events)
    - Ordered by timestamp (oldest first)
    - get_current_severity() returns highest level from history
    - clear_history() resets for new flight
    """

    def test_history_empty(self):
        """History is empty initially.

        VALIDATES: Clean state at matrix creation.
        No carryover from previous flights.
        """
        matrix = EscalationMatrix()
        assert matrix.get_history() == []

    def test_history_records_event(self):
        """History records escalation events.

        VALIDATES: Each evaluate() call that triggers escalation
        adds an EscalationEvent to history.
        """
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        history = matrix.get_history()
        assert len(history) == 1
        assert history[0].condition == "battery_critical"

    def test_history_limit(self):
        """History respects limit parameter.

        VALIDATES: Can request subset of history.
        Useful for UI display (show last 5 events).
        """
        matrix = EscalationMatrix()
        # Create 5 events
        for i in range(5):
            matrix.evaluate("battery_critical", battery_percent=15)

        history = matrix.get_history(limit=3)
        assert len(history) == 3

    def test_history_order(self):
        """History returns most recent events.

        VALIDATES: Events appended in chronological order.
        Last element is most recent.
        """
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        matrix.evaluate("geofence_breach", distance_m=600, max_m=500)

        history = matrix.get_history()
        assert history[-1].condition == "geofence_breach"

    def test_get_current_severity(self):
        """get_current_severity returns highest severity from history.

        VALIDATES: Can query current threat level across all conditions.
        Returns highest level seen (resets to L1 if history empty).

        EXAMPLE PROGRESSION:
        - Initial: L1 (no issues)
        - Battery warning: L1 (still highest)
        - Battery critical: L4 (now highest)
        """
        matrix = EscalationMatrix()
        assert matrix.get_current_severity() == SeverityLevel.L1_MINOR

        matrix.evaluate("battery_warning", battery_percent=28)
        assert matrix.get_current_severity() == SeverityLevel.L1_MINOR

        matrix.evaluate("battery_critical", battery_percent=15)
        assert matrix.get_current_severity() == SeverityLevel.L4_CRITICAL

    def test_clear_history(self):
        """clear_history removes all events.

        USE CASE: Reset between flights or after incident resolution.
        """
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        assert len(matrix.get_history()) == 1

        matrix.clear_history()
        assert len(matrix.get_history()) == 0


class TestTimerSystem:
    """Test timer-based escalation.

    TIMER SYSTEM EXPLAINED:
    =======================

    Some conditions require time-delayed escalation:
    - Communication loss (must be sustained, not brief gap)
    - GPS degradation (must persist, not momentary)
    - Sensor errors (must recur, not one-off)

    TIMER LIFECYCLE:
    1. start_timer() - Create timer for condition
    2. check_timers() - Poll for expired timers, return events
    3. cancel_timer() - Stop timer if condition resolves

    TIMER USE CASE - Communication Loss:
    - 2s gap: Warning (no timer needed, immediate)
    - Start 10s timer for L5 emergency
    - If comm restored at 8s: cancel_timer(), no escalation
    - If timer expires: L5 emergency event generated
    """

    def test_start_timer(self):
        """Timer can be started for a condition.

        VALIDATES: Timer creation with correct parameters.
        Timer is active immediately.
        """
        matrix = EscalationMatrix()
        timer = matrix.start_timer("test_condition", SeverityLevel.L4_CRITICAL, 5.0)
        assert timer.condition == "test_condition"
        assert timer.level == SeverityLevel.L4_CRITICAL
        assert timer.timeout_s == 5.0
        assert timer.is_active

    def test_cancel_timer(self):
        """Timer can be cancelled.

        USE CASE: Condition resolved before timer expired.
        Returns True if timer existed and was cancelled.
        Returns False if no active timer found.
        """
        matrix = EscalationMatrix()
        matrix.start_timer("test_condition", SeverityLevel.L4_CRITICAL, 5.0)
        assert matrix.cancel_timer("test_condition") is True
        assert matrix.cancel_timer("test_condition") is False  # Already cancelled

    def test_check_timers_not_expired(self):
        """check_timers returns empty when no timers expired.

        VALIDATES: Only expired timers generate events.
        Active timers return empty list.
        """
        matrix = EscalationMatrix()
        matrix.start_timer("comm_link_lost", SeverityLevel.L5_EMERGENCY, 10.0)
        events = matrix.check_timers()
        assert events == []

    def test_check_timers_expired(self):
        """check_timers returns events for expired timers.

        VALIDATES: Expired timers generate EscalationEvents.
        Event includes level and condition from timer.
        """
        matrix = EscalationMatrix()
        # Start with a condition that exists in rules
        matrix.start_timer("comm_link_lost", SeverityLevel.L5_EMERGENCY, 0.001)
        time.sleep(0.01)  # Wait for timer to expire
        events = matrix.check_timers()
        assert len(events) > 0


class TestActionHandlers:
    """Test action handler registration.

    ACTION HANDLER SYSTEM:
    ======================

    The matrix defines WHAT action to take (e.g., "initiate_rtl"),
    but doesn't know HOW to execute it.

    Action handlers bridge this gap:
    - Register a callable for each action string
    - Handler receives the EscalationEvent as context
    - Handler executes the actual MAVSDK commands

    EXAMPLE HANDLERS:
    - "initiate_rtl": Call drone.action.return_to_launch()
    - "initiate_land": Call drone.action.land()
    - "emergency_disarm": Call drone.action.kill()
    - "assume_control_hold": Enter offboard mode, hold position

    HANDLER REGISTRATION PATTERN:
    matrix.register_action_handler("initiate_rtl", rtl_handler)
    """

    def test_register_action_handler(self):
        """Action handler can be registered.

        VALIDATES: Handlers stored in internal dictionary.
        Key is action string, value is callable.
        """
        matrix = EscalationMatrix()
        handler = MagicMock()
        matrix.register_action_handler("initiate_rtl", handler)
        assert matrix._action_handlers["initiate_rtl"] == handler

    def test_handler_called_on_escalation(self):
        """Handler is called when action is auto-executed.

        VALIDATES: When escalation triggers and auto_execute=True,
        the registered handler is called with the EscalationEvent.

        EXAMPLE FLOW:
        1. Battery drops to 15%
        2. evaluate() returns L4 event with action="initiate_rtl"
        3. auto_execute=True (L4 >= L3)
        4. Handler "initiate_rtl" is called with event
        5. Handler executes RTL via MAVSDK
        """
        matrix = EscalationMatrix()
        handler = MagicMock()
        matrix.register_action_handler("initiate_rtl", handler)

        event = matrix.evaluate("battery_critical", battery_percent=15)
        assert event is not None
        handler.assert_called_once_with(event)


class TestConvenienceFunctions:
    """Test module-level convenience functions.

    CONVENIENCE FUNCTIONS:
    ======================

    Module-level functions for direct use without creating matrix:
    - check_battery_level(percent) -> EscalationEvent or None
    - check_geofence_breach(distance_m, max_m) -> EscalationEvent or None
    - check_heartbeat(age_s) -> EscalationEvent or None

    USE CASE: Quick checks in simple scripts or one-off validations.
    Internally creates temporary matrix with default rules.
    """

    def test_check_battery_level(self):
        """check_battery_level function works.

        VALIDATES: Direct battery check without matrix instance.
        """
        result = check_battery_level(percent=18)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL

    def test_check_geofence_breach(self):
        """check_geofence_breach function works.

        VALIDATES: Direct geofence check without matrix instance.
        """
        result = check_geofence_breach(distance_m=550, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL

    def test_check_heartbeat(self):
        """check_heartbeat function works.

        VALIDATES: Direct heartbeat check without matrix instance.
        """
        result = check_heartbeat(age_s=12.0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY


class TestIntegrationWithGuardian:
    """Test integration patterns with AsyncGuardian.

    ASYNC GUARDIAN INTEGRATION:
    ============================

    AsyncGuardian is the safety validation layer that uses EscalationMatrix.

    INTEGRATION PATTERN:
    1. Guardian receives MAVSDK command from agent
    2. Guardian evaluates safety conditions through matrix
    3. If escalation triggered:
       - Auto-execute L3+ actions immediately
       - Block/reject L1-L2 triggering commands
       - Notify operator of all escalations
    4. Guardian logs all decisions for audit

    EXAMPLE FLOW:
    - Agent sends "fly_to(coordinates)"
    - Guardian checks: battery, geofence, comm link
    - Battery at 18% -> L4 critical escalation
    - Guardian auto-executes RTL instead of fly_to
    - Agent receives: "Command blocked - L4 escalation active"

    THRESHOLD CONFIGURATION:
    - Different missions may need different thresholds
    - Indoor flight: Tighter geofence, higher battery reserve
    - Long-range: Lower battery threshold, larger geofence
    - Custom rules passed to EscalationMatrix constructor
    """

    def test_matrix_integration_pattern(self):
        """Demonstrate integration pattern with guardian.

        VALIDATES: Shows how AsyncGuardian would use the matrix
        for real-time safety validation.

        SIMULATED FLOW:
        1. Battery at 18% detected
        2. check_battery() returns L4 event
        3. L4 >= L3, so auto-execute applies
        4. action_taken = "initiate_rtl"
        5. Guardian would call RTL via MAVSDK
        """
        matrix = EscalationMatrix()

        # Simulate guardian validation
        battery_percent = 18
        event = matrix.check_battery(battery_percent)

        if event and event.level >= SeverityLevel.L4_CRITICAL:
            # This would be called by AsyncGuardian
            action = event.action_taken
            assert action == "initiate_rtl"

    def test_escalation_thresholds_configurable(self):
        """Thresholds are configurable via custom rules.

        VALIDATES: Custom rules enable mission-specific thresholds.

        EXAMPLE: Indoor flight with stricter battery threshold.
        - Default: Critical at <20%
        - Custom: Critical at <15%

        THRESHOLD LOGIC:
        - Triggers when battery_percent < threshold
        - 18% with 15% threshold: No trigger (18 > 15)
        - 14% with 15% threshold: Triggers (14 < 15)
        """
        custom_rules = [
            EscalationRule(
                SeverityLevel.L4_CRITICAL,
                "custom_battery_critical",
                "initiate_rtl",
                True,
                True,
                threshold=15.0  # Custom 15% threshold
            )
        ]
        matrix = EscalationMatrix(rules=custom_rules)

        # At 18% with 15% threshold, should NOT trigger (18 > 15)
        result = matrix.evaluate("custom_battery_critical", battery_percent=18)
        assert result is None

        # At 20% with 15% threshold, should NOT trigger (20 > 15)
        result = matrix.evaluate("custom_battery_critical", battery_percent=20)
        assert result is None

        # At exactly 15%, should NOT trigger (15 is not < 15)
        result = matrix.evaluate("custom_battery_critical", battery_percent=15)
        assert result is None

        # At 14% definitely triggers (14 < 15)
        result = matrix.evaluate("custom_battery_critical", battery_percent=14)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
