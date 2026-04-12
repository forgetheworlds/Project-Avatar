"""Tests for safety scenarios and GuardianProcess validation.

Tests geofence violations, altitude limits, battery limits, and heartbeat monitoring.
"""

import time

import pytest

from avatar.mav.guardian import GuardianProcess, HardLimits


# =============================================================================
# HARDEST LIMITS TESTS
# =============================================================================


class TestHardLimits:
    """Tests for HardLimits dataclass."""

    def test_default_limits(self):
        """Test default safety limits are regulatory compliant."""
        limits = HardLimits()

        # FAA Part 107: Max 400ft AGL (~122m)
        assert limits.max_altitude_amsl_m == 120.0

        # Reasonable geofence distance
        assert limits.max_distance_from_home_m == 500.0

        # Conservative battery RTL threshold
        assert limits.min_battery_rtl_percent == 25.0

        # Reasonable heartbeat timeout
        assert limits.heartbeat_timeout_s == 2.0

        # Reasonable speed limit
        assert limits.max_speed_m_s == 15.0

    def test_custom_limits(self):
        """Test custom safety limits."""
        limits = HardLimits(
            max_altitude_amsl_m=50.0,
            max_distance_from_home_m=100.0,
            min_battery_rtl_percent=30.0,
            heartbeat_timeout_s=1.0,
            max_speed_m_s=10.0
        )

        assert limits.max_altitude_amsl_m == 50.0
        assert limits.max_distance_from_home_m == 100.0
        assert limits.min_battery_rtl_percent == 30.0

    def test_limits_are_immutable(self):
        """Test that HardLimits is frozen (immutable)."""
        limits = HardLimits()

        with pytest.raises(AttributeError):
            limits.max_altitude_amsl_m = 200.0


# =============================================================================
# GEOFENCE VIOLATION TESTS
# =============================================================================


class TestGeofenceViolation:
    """Tests for geofence/distance violation scenarios."""

    def test_geofence_violation_basic(self, mock_guardian):
        """Test command rejected when exceeding distance from home."""
        # Home is at (37.7749, -122.4194)
        # Request position 1km away should be rejected
        is_valid, reason = mock_guardian.validate_command({
            "latitude": 37.7839,  # ~1km north
            "longitude": -122.4194,
        })

        assert is_valid is False
        assert "distance" in reason.lower()
        assert "exceeds" in reason.lower()

    def test_geofence_within_limit(self, mock_guardian):
        """Test command accepted when within geofence."""
        # Home is at (37.7749, -122.4194)
        # Request position 200m away should be accepted
        is_valid, reason = mock_guardian.validate_command({
            "latitude": 37.7767,  # ~200m north
            "longitude": -122.4194,
        })

        assert is_valid is True
        assert reason == "OK"

    def test_geofence_exact_boundary(self, mock_guardian):
        """Test command at exact geofence boundary."""
        # Default max distance is 500m
        # Position exactly 500m away
        # ~0.0045 degrees latitude = 500m
        is_valid, reason = mock_guardian.validate_command({
            "latitude": 37.7794,  # ~500m north
            "longitude": -122.4194,
        })

        # Should be accepted (at or within boundary)
        assert is_valid is True

    def test_geofence_no_home_set(self):
        """Test command rejected when home position not set."""
        guardian = GuardianProcess()
        # Don't set home position

        is_valid, reason = guardian.validate_command({
            "latitude": 37.7749,
            "longitude": -122.4194,
        })

        assert is_valid is False
        assert "home position not set" in reason.lower()

    def test_geofence_with_custom_limit(self, custom_limits):
        """Test geofence with custom distance limit."""
        custom_limits.max_distance_from_home_m = 100.0
        guardian = GuardianProcess(custom_limits)
        guardian.set_home(37.7749, -122.4194)

        # Position 200m away should be rejected with 100m limit
        is_valid, reason = guardian.validate_command({
            "latitude": 37.7767,
            "longitude": -122.4194,
        })

        assert is_valid is False
        assert "100" in reason

    def test_haversine_distance_calculation(self, mock_guardian):
        """Test Haversine distance calculation accuracy."""
        # San Francisco to Los Angeles ~559km
        distance = mock_guardian._haversine_distance(
            37.7749, -122.4194,  # San Francisco
            34.0522, -118.2437   # Los Angeles
        )

        # Should be approximately 559,000 meters (±10km)
        assert 549000 < distance < 569000


# =============================================================================
# ALTITUDE LIMIT TESTS
# =============================================================================


class TestAltitudeLimit:
    """Tests for altitude limit scenarios."""

    def test_altitude_within_limit(self, mock_guardian):
        """Test command accepted when within altitude limit."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 100.0  # Below 120m limit
        })

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_exceeds_limit(self, mock_guardian):
        """Test command rejected when exceeding altitude limit."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 150.0  # Above 120m limit
        })

        assert is_valid is False
        assert "altitude" in reason.lower()
        assert "150" in reason
        assert "120" in reason

    def test_altitude_at_limit(self, mock_guardian):
        """Test command at exact altitude limit."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 120.0
        })

        assert is_valid is True

    def test_altitude_negative(self, mock_guardian):
        """Test command rejected for negative altitude."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": -10.0
        })

        assert is_valid is False
        assert "below ground" in reason.lower()

    def test_altitude_zero(self, mock_guardian):
        """Test command with zero altitude (ground level)."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 0.0
        })

        assert is_valid is True

    def test_altitude_custom_limit(self, custom_limits):
        """Test altitude with custom limit."""
        custom_limits.max_altitude_amsl_m = 50.0
        guardian = GuardianProcess(custom_limits)

        is_valid, reason = guardian.validate_command({
            "altitude_amsl_m": 75.0
        })

        assert is_valid is False
        assert "50" in reason


# =============================================================================
# LOW BATTERY TESTS
# =============================================================================


class TestLowBattery:
    """Tests for low battery scenarios."""

    def test_battery_above_threshold(self, mock_guardian):
        """Test command accepted when battery above threshold."""
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 50.0
        })

        assert is_valid is True

    def test_battery_below_threshold(self, mock_guardian):
        """Test command rejected when battery below threshold."""
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 15.0  # Below 25% threshold
        })

        assert is_valid is False
        assert "battery" in reason.lower()
        assert "rtl" in reason.lower()

    def test_battery_at_threshold(self, mock_guardian):
        """Test command at exact battery threshold."""
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 25.0
        })

        assert is_valid is True

    def test_battery_critical(self, mock_guardian):
        """Test command with critically low battery."""
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 5.0
        })

        assert is_valid is False
        assert "5" in reason

    def test_battery_custom_threshold(self, custom_limits):
        """Test battery with custom threshold."""
        custom_limits.min_battery_rtl_percent = 40.0
        guardian = GuardianProcess(custom_limits)

        is_valid, reason = guardian.validate_command({
            "battery_percent": 30.0
        })

        assert is_valid is False
        assert "40" in reason


# =============================================================================
# HEARTBEAT TIMEOUT TESTS
# =============================================================================


class TestHeartbeatTimeout:
    """Tests for heartbeat monitoring scenarios."""

    def test_heartbeat_ok_initially(self, mock_guardian):
        """Test heartbeat check passes initially."""
        is_ok = mock_guardian.check_heartbeat()

        assert is_ok is True

    def test_heartbeat_timeout(self, mock_guardian):
        """Test heartbeat fails after timeout."""
        # Simulate time passing beyond timeout
        mock_guardian._last_heartbeat = time.time() - 3.0  # 3 seconds ago

        is_ok = mock_guardian.check_heartbeat()

        assert is_ok is False

    def test_heartbeat_update(self, mock_guardian):
        """Test heartbeat update resets timeout."""
        # Simulate time passing
        mock_guardian._last_heartbeat = time.time() - 1.5

        # Update heartbeat
        mock_guardian.update_heartbeat()

        # Should now be ok
        is_ok = mock_guardian.check_heartbeat()
        assert is_ok is True

    def test_heartbeat_age(self, mock_guardian):
        """Test heartbeat age reporting."""
        mock_guardian._last_heartbeat = time.time() - 0.5

        age = mock_guardian.get_heartbeat_age()

        assert 0.4 < age < 0.6

    def test_heartbeat_custom_timeout(self, custom_limits):
        """Test heartbeat with custom timeout."""
        custom_limits.heartbeat_timeout_s = 5.0
        guardian = GuardianProcess(custom_limits)

        # 3 seconds should still be ok with 5s timeout
        guardian._last_heartbeat = time.time() - 3.0

        is_ok = guardian.check_heartbeat()
        assert is_ok is True

        # But 6 seconds should fail
        guardian._last_heartbeat = time.time() - 6.0

        is_ok = guardian.check_heartbeat()
        assert is_ok is False


# =============================================================================
# SPEED LIMIT TESTS
# =============================================================================


class TestSpeedLimit:
    """Tests for speed limit scenarios."""

    def test_speed_within_limit(self, mock_guardian):
        """Test command accepted when within speed limit."""
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 10.0
        })

        assert is_valid is True

    def test_speed_exceeds_limit(self, mock_guardian):
        """Test command rejected when exceeding speed limit."""
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 20.0  # Above 15 m/s limit
        })

        assert is_valid is False
        assert "speed" in reason.lower()

    def test_speed_at_limit(self, mock_guardian):
        """Test command at exact speed limit."""
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 15.0
        })

        assert is_valid is True

    def test_speed_custom_limit(self, custom_limits):
        """Test speed with custom limit."""
        custom_limits.max_speed_m_s = 5.0
        guardian = GuardianProcess(custom_limits)

        is_valid, reason = guardian.validate_command({
            "speed_m_s": 10.0
        })

        assert is_valid is False
        assert "5" in reason


# =============================================================================
# COMBINED VALIDATION TESTS
# =============================================================================


class TestCombinedValidation:
    """Tests for combined validation scenarios."""

    def test_all_parameters_valid(self, mock_guardian):
        """Test command with all valid parameters."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0,
            "latitude": 37.7767,  # ~200m from home
            "longitude": -122.4194,
            "speed_m_s": 5.0,
            "battery_percent": 80.0
        })

        assert is_valid is True

    def test_multiple_violations(self, mock_guardian):
        """Test command with multiple violations reports first one."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 200.0,  # Violation
            "speed_m_s": 30.0,         # Also violation
            "battery_percent": 10.0    # Also violation
        })

        assert is_valid is False
        # Should report first violation found (altitude)
        assert "altitude" in reason.lower()

    def test_one_violation_among_valid(self, mock_guardian):
        """Test command with one violation among valid parameters."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0,      # Valid
            "latitude": 37.7767,          # Valid (~200m)
            "longitude": -122.4194,
            "speed_m_s": 25.0,            # Invalid
        })

        assert is_valid is False
        assert "speed" in reason.lower()

    def test_empty_command(self, mock_guardian):
        """Test empty command is accepted (no constraints to violate)."""
        is_valid, reason = mock_guardian.validate_command({})

        assert is_valid is True

    def test_partial_command(self, mock_guardian):
        """Test command with only some parameters."""
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0
            # No lat/lon, speed, or battery specified
        })

        assert is_valid is True


# =============================================================================
# HOME POSITION TESTS
# =============================================================================


class TestHomePosition:
    """Tests for home position management."""

    def test_set_home(self, mock_guardian):
        """Test setting home position."""
        guardian = GuardianProcess()
        guardian.set_home(37.7749, -122.4194)

        assert guardian.is_home_set is True
        assert guardian.home_position == (37.7749, -122.4194)

    def test_home_position_none_initially(self):
        """Test home position is None before being set."""
        guardian = GuardianProcess()

        assert guardian.is_home_set is False
        assert guardian.home_position is None

    def test_update_home_position(self, mock_guardian):
        """Test updating home position."""
        mock_guardian.set_home(34.0522, -118.2437)  # Los Angeles

        assert mock_guardian.home_position == (34.0522, -118.2437)


# =============================================================================
# GUARDIAN PROCESS TESTS
# =============================================================================


class TestGuardianProcess:
    """Tests for GuardianProcess class."""

    def test_initialization_default_limits(self):
        """Test GuardianProcess initializes with default limits."""
        guardian = GuardianProcess()

        assert guardian.limits is not None
        assert isinstance(guardian.limits, HardLimits)

    def test_initialization_custom_limits(self, custom_limits):
        """Test GuardianProcess with custom limits."""
        guardian = GuardianProcess(custom_limits)

        assert guardian.limits == custom_limits

    def test_repr_methods(self, mock_guardian):
        """Test string representation methods."""
        assert mock_guardian.home_position is not None
        assert isinstance(mock_guardian.is_home_set, bool)
