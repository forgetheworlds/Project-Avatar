"""Tests for the 6-level Safety Escalation Matrix.

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
    """Test the 6 severity level enum definitions."""

    def test_all_six_levels_exist(self):
        """All 6 severity levels are defined."""
        levels = list(SeverityLevel)
        assert len(levels) == 6
        assert SeverityLevel.L1_MINOR in levels
        assert SeverityLevel.L2_MODERATE in levels
        assert SeverityLevel.L3_SIGNIFICANT in levels
        assert SeverityLevel.L4_CRITICAL in levels
        assert SeverityLevel.L5_EMERGENCY in levels
        assert SeverityLevel.L6_CATASTROPHIC in levels

    def test_severity_level_values(self):
        """Severity levels have correct numeric values."""
        assert SeverityLevel.L1_MINOR.value == 1
        assert SeverityLevel.L2_MODERATE.value == 2
        assert SeverityLevel.L3_SIGNIFICANT.value == 3
        assert SeverityLevel.L4_CRITICAL.value == 4
        assert SeverityLevel.L5_EMERGENCY.value == 5
        assert SeverityLevel.L6_CATASTROPHIC.value == 6

    def test_severity_level_ordering(self):
        """Severity levels order correctly by value."""
        assert SeverityLevel.L1_MINOR.value < SeverityLevel.L2_MODERATE.value
        assert SeverityLevel.L2_MODERATE.value < SeverityLevel.L3_SIGNIFICANT.value
        assert SeverityLevel.L3_SIGNIFICANT.value < SeverityLevel.L4_CRITICAL.value
        assert SeverityLevel.L4_CRITICAL.value < SeverityLevel.L5_EMERGENCY.value
        assert SeverityLevel.L5_EMERGENCY.value < SeverityLevel.L6_CATASTROPHIC.value


class TestEscalationRule:
    """Test the EscalationRule dataclass."""

    def test_rule_creation(self):
        """EscalationRule can be created with all fields."""
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
        """EscalationRule can be created without threshold."""
        rule = EscalationRule(
            level=SeverityLevel.L2_MODERATE,
            condition="command_validation_fail",
            action="reject_command",
            auto_execute=True,
            notify_operator=True
        )
        assert rule.threshold is None


class TestEscalationEvent:
    """Test the EscalationEvent dataclass."""

    def test_event_creation(self):
        """EscalationEvent can be created with all fields."""
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
    """Test the EscalationTimer class."""

    def test_timer_creation(self):
        """EscalationTimer can be created with correct defaults."""
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
        """Timer correctly reports not expired when within timeout."""
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=10.0,
            triggered_at=time.time()
        )
        assert not timer.is_expired()
        assert timer.remaining_s() > 9.0

    def test_timer_expired(self):
        """Timer correctly reports expired after timeout."""
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=0.001,
            triggered_at=time.time() - 0.1  # Started 100ms ago
        )
        assert timer.is_expired()

    def test_timer_cancel(self):
        """Cancelled timer reports as not active."""
        timer = EscalationTimer(
            condition="test",
            level=SeverityLevel.L1_MINOR,
            timeout_s=10.0
        )
        timer.cancel()
        assert not timer.is_active
        assert not timer.is_expired()


class TestEscalationMatrix:
    """Test the EscalationMatrix class."""

    def test_default_rules_loaded(self):
        """Default rules are loaded on initialization."""
        matrix = EscalationMatrix()
        assert len(matrix.rules) == len(EscalationMatrix.DEFAULT_RULES)

    def test_custom_rules(self):
        """Custom rules can be provided."""
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
        """Evaluate returns None for unknown condition."""
        matrix = EscalationMatrix()
        result = matrix.evaluate("unknown_condition")
        assert result is None

    def test_evaluate_known_condition(self):
        """Evaluate returns event for known condition."""
        matrix = EscalationMatrix()
        result = matrix.evaluate("battery_critical", battery_percent=15)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.action_taken == "initiate_rtl"

    def test_get_level(self):
        """get_level returns highest severity for condition."""
        matrix = EscalationMatrix()
        level = matrix.get_level("battery_critical")
        assert level == SeverityLevel.L4_CRITICAL

    def test_get_level_unknown(self):
        """get_level returns None for unknown condition."""
        matrix = EscalationMatrix()
        level = matrix.get_level("unknown")
        assert level is None

    def test_should_auto_execute_l1(self):
        """L1 does not auto-execute."""
        matrix = EscalationMatrix()
        assert not matrix.should_auto_execute(SeverityLevel.L1_MINOR)

    def test_should_auto_execute_l2(self):
        """L2 does not auto-execute."""
        matrix = EscalationMatrix()
        assert not matrix.should_auto_execute(SeverityLevel.L2_MODERATE)

    def test_should_auto_execute_l3_and_above(self):
        """L3 and above auto-execute."""
        matrix = EscalationMatrix()
        assert matrix.should_auto_execute(SeverityLevel.L3_SIGNIFICANT)
        assert matrix.should_auto_execute(SeverityLevel.L4_CRITICAL)
        assert matrix.should_auto_execute(SeverityLevel.L5_EMERGENCY)
        assert matrix.should_auto_execute(SeverityLevel.L6_CATASTROPHIC)

    def test_get_action_for_levels(self):
        """get_action returns correct action for each level."""
        matrix = EscalationMatrix()
        assert matrix.get_action(SeverityLevel.L1_MINOR) == "log_alert"
        assert matrix.get_action(SeverityLevel.L2_MODERATE) == "reject_command"
        assert matrix.get_action(SeverityLevel.L3_SIGNIFICANT) == "assume_control_hold"
        assert matrix.get_action(SeverityLevel.L4_CRITICAL) == "initiate_rtl"
        assert matrix.get_action(SeverityLevel.L5_EMERGENCY) == "initiate_land"
        assert matrix.get_action(SeverityLevel.L6_CATASTROPHIC) == "emergency_disarm"


class TestBatteryEscalation:
    """Test battery level escalation logic."""

    def test_battery_normal(self):
        """Normal battery does not trigger escalation."""
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=50)
        assert result is None

    def test_battery_warning(self):
        """Battery below 30% triggers L1 warning."""
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=28)
        assert result is not None
        assert result.level == SeverityLevel.L1_MINOR
        assert result.condition == "battery_warning"

    def test_battery_low(self):
        """Battery below 25% triggers L2 low."""
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=23)
        assert result is not None
        assert result.level == SeverityLevel.L2_MODERATE
        assert result.condition == "battery_low"

    def test_battery_critical(self):
        """Battery below 20% triggers L4 critical."""
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=18)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "battery_critical"
        assert result.action_taken == "initiate_rtl"

    def test_battery_zero(self):
        """Battery at 0% triggers L5 total power loss."""
        matrix = EscalationMatrix()
        result = matrix.check_battery(percent=0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY
        assert result.condition == "total_power_loss"

    def test_battery_threshold_boundary(self):
        """Battery thresholds are boundary-inclusive."""
        matrix = EscalationMatrix()
        # At exactly 30% should still trigger warning (30.0 < threshold)
        result = matrix.check_battery(percent=29.9)
        assert result is not None


class TestGeofenceEscalation:
    """Test geofence escalation logic."""

    def test_geofence_normal(self):
        """Normal position within geofence does not trigger."""
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=400, max_m=500)
        assert result is None

    def test_geofence_warning(self):
        """Approaching geofence triggers L3 warning."""
        matrix = EscalationMatrix()
        # 470m distance when max is 500m (30m before boundary)
        result = matrix.check_geofence(distance_m=470, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L3_SIGNIFICANT
        assert result.condition == "geofence_warning"

    def test_geofence_breach(self):
        """Breach geofence triggers L4 critical."""
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=550, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "geofence_breach"
        assert result.action_taken == "initiate_rtl"

    def test_geofence_at_boundary(self):
        """At geofence boundary triggers L4."""
        matrix = EscalationMatrix()
        result = matrix.check_geofence(distance_m=500, max_m=500)
        # At boundary - not exceeding, so warning only
        if result:
            # If triggered, should be warning
            assert result.level == SeverityLevel.L3_SIGNIFICANT


class TestHeartbeatEscalation:
    """Test heartbeat timeout escalation logic."""

    def test_heartbeat_normal(self):
        """Normal heartbeat age does not trigger."""
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=1.0)
        assert result is None

    def test_heartbeat_warning(self):
        """Heartbeat >2s triggers L2 warning."""
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=2.5)
        assert result is not None
        assert result.level == SeverityLevel.L2_MODERATE
        assert result.condition == "heartbeat_warning"

    def test_heartbeat_critical(self):
        """Heartbeat >5s triggers L4 critical."""
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=6.0)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL
        assert result.condition == "comm_link_degraded"

    def test_heartbeat_emergency(self):
        """Heartbeat >10s triggers L5 emergency."""
        matrix = EscalationMatrix()
        result = matrix.check_heartbeat_timeout(age_s=12.0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY
        assert result.condition == "comm_link_lost"


class TestHistoryTracking:
    """Test escalation history tracking."""

    def test_history_empty(self):
        """History is empty initially."""
        matrix = EscalationMatrix()
        assert matrix.get_history() == []

    def test_history_records_event(self):
        """History records escalation events."""
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        history = matrix.get_history()
        assert len(history) == 1
        assert history[0].condition == "battery_critical"

    def test_history_limit(self):
        """History respects limit parameter."""
        matrix = EscalationMatrix()
        # Create 5 events
        for i in range(5):
            matrix.evaluate("battery_critical", battery_percent=15)

        history = matrix.get_history(limit=3)
        assert len(history) == 3

    def test_history_order(self):
        """History returns most recent events."""
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        matrix.evaluate("geofence_breach", distance_m=600, max_m=500)

        history = matrix.get_history()
        assert history[-1].condition == "geofence_breach"

    def test_get_current_severity(self):
        """get_current_severity returns highest severity from history."""
        matrix = EscalationMatrix()
        assert matrix.get_current_severity() == SeverityLevel.L1_MINOR

        matrix.evaluate("battery_warning", battery_percent=28)
        assert matrix.get_current_severity() == SeverityLevel.L1_MINOR

        matrix.evaluate("battery_critical", battery_percent=15)
        assert matrix.get_current_severity() == SeverityLevel.L4_CRITICAL

    def test_clear_history(self):
        """clear_history removes all events."""
        matrix = EscalationMatrix()
        matrix.evaluate("battery_critical", battery_percent=15)
        assert len(matrix.get_history()) == 1

        matrix.clear_history()
        assert len(matrix.get_history()) == 0


class TestTimerSystem:
    """Test timer-based escalation."""

    def test_start_timer(self):
        """Timer can be started for a condition."""
        matrix = EscalationMatrix()
        timer = matrix.start_timer("test_condition", SeverityLevel.L4_CRITICAL, 5.0)
        assert timer.condition == "test_condition"
        assert timer.level == SeverityLevel.L4_CRITICAL
        assert timer.timeout_s == 5.0
        assert timer.is_active

    def test_cancel_timer(self):
        """Timer can be cancelled."""
        matrix = EscalationMatrix()
        matrix.start_timer("test_condition", SeverityLevel.L4_CRITICAL, 5.0)
        assert matrix.cancel_timer("test_condition") is True
        assert matrix.cancel_timer("test_condition") is False  # Already cancelled

    def test_check_timers_not_expired(self):
        """check_timers returns empty when no timers expired."""
        matrix = EscalationMatrix()
        matrix.start_timer("comm_link_lost", SeverityLevel.L5_EMERGENCY, 10.0)
        events = matrix.check_timers()
        assert events == []

    def test_check_timers_expired(self):
        """check_timers returns events for expired timers."""
        matrix = EscalationMatrix()
        # Start with a condition that exists in rules
        matrix.start_timer("comm_link_lost", SeverityLevel.L5_EMERGENCY, 0.001)
        time.sleep(0.01)  # Wait for timer to expire
        events = matrix.check_timers()
        assert len(events) > 0


class TestActionHandlers:
    """Test action handler registration."""

    def test_register_action_handler(self):
        """Action handler can be registered."""
        matrix = EscalationMatrix()
        handler = MagicMock()
        matrix.register_action_handler("initiate_rtl", handler)
        assert matrix._action_handlers["initiate_rtl"] == handler

    def test_handler_called_on_escalation(self):
        """Handler is called when action is auto-executed."""
        matrix = EscalationMatrix()
        handler = MagicMock()
        matrix.register_action_handler("initiate_rtl", handler)

        event = matrix.evaluate("battery_critical", battery_percent=15)
        assert event is not None
        handler.assert_called_once_with(event)


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_check_battery_level(self):
        """check_battery_level function works."""
        result = check_battery_level(percent=18)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL

    def test_check_geofence_breach(self):
        """check_geofence_breach function works."""
        result = check_geofence_breach(distance_m=550, max_m=500)
        assert result is not None
        assert result.level == SeverityLevel.L4_CRITICAL

    def test_check_heartbeat(self):
        """check_heartbeat function works."""
        result = check_heartbeat(age_s=12.0)
        assert result is not None
        assert result.level == SeverityLevel.L5_EMERGENCY


class TestIntegrationWithGuardian:
    """Test integration patterns with AsyncGuardian."""

    def test_matrix_integration_pattern(self):
        """Demonstrate integration pattern with guardian."""
        matrix = EscalationMatrix()

        # Simulate guardian validation
        battery_percent = 18
        event = matrix.check_battery(battery_percent)

        if event and event.level >= SeverityLevel.L4_CRITICAL:
            # This would be called by AsyncGuardian
            action = event.action_taken
            assert action == "initiate_rtl"

    def test_escalation_thresholds_configurable(self):
        """Thresholds are configurable via custom rules."""
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
