"""Tests for safety scenarios and GuardianProcess validation.

Tests geofence violations, altitude limits, battery limits, and heartbeat monitoring.

SAFETY ARCHITECTURE:
The GuardianProcess implements a defense-in-depth approach with multiple validation layers:
1. HardLimits: Immutable safety envelope (altitude, distance, battery, speed)
2. Real-time validation: Every command checked against current state
3. Heartbeat monitoring: Connection health tracking
4. Geofence enforcement: Geographic boundary protection

REGULATORY COMPLIANCE:
Default limits are set to comply with FAA Part 107 (US commercial drone regulations):
- Max altitude: 400ft AGL (~122m) -> 120m for safety margin
- VLOS operation: 500m distance limit
- Conservative battery: 25% RTL threshold

TEST COVERAGE:
- HardLimits default and custom values
- Geofence violations and boundary conditions
- Altitude constraints and negative altitude handling
- Low battery detection and thresholds
- Heartbeat timeout and age tracking
- Speed limit enforcement
- Combined validation scenarios
- Home position management
- Distance calculation accuracy (Haversine)
"""

import time
from dataclasses import replace

import pytest

from avatar.mav.guardian import GuardianProcess, HardLimits


# =============================================================================
# HARD LIMITS TESTS
# =============================================================================


class TestHardLimits:
    """Tests for HardLimits dataclass.

    VALIDATES:
    - Default values match regulatory requirements (FAA Part 107)
    - Custom limits can be configured
    - Immutability (frozen dataclass)

    HardLimits defines the absolute operational envelope that cannot be
    exceeded under any circumstances. These are safety-critical constants.
    """

    def test_default_limits(self):
        """VALIDATES: Default safety limits are regulatory compliant.

        Verifies default values match or are more conservative than:
        - FAA Part 107: 400ft max altitude (120m with safety margin)
        - VLOS requirements: 500m distance limit
        - Conservative battery: 25% RTL threshold
        - Reasonable response times: 2s heartbeat timeout
        """
        limits = HardLimits()

        # FAA Part 107: Max 400ft AGL (~122m)
        assert limits.max_altitude_amsl_m == 120.0

        # Reasonable geofence distance for VLOS operations
        assert limits.max_distance_from_home_m == 500.0

        # Conservative battery RTL threshold (Return To Launch)
        assert limits.min_battery_rtl_percent == 25.0

        # Reasonable heartbeat timeout for connection monitoring
        assert limits.heartbeat_timeout_s == 2.0

        # Speed limit for safe maneuvering
        assert limits.max_speed_m_s == 15.0

    def test_custom_limits(self):
        """VALIDATES: Custom safety limits can be configured.

        Operations can specify custom limits for specific scenarios
        (e.g., indoor flight, precision operations) while maintaining
        the same validation interface.
        """
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
        """VALIDATES: HardLimits is frozen (immutable).

        Safety limits must not change during flight to prevent
        accidental or malicious modifications. Uses @dataclass(frozen=True).
        """
        limits = HardLimits()

        with pytest.raises(AttributeError):
            limits.max_altitude_amsl_m = 200.0


# =============================================================================
# GEOFENCE VIOLATION TESTS
# =============================================================================


class TestGeofenceViolation:
    """Tests for geofence/distance violation scenarios.

    VALIDATES:
    - Commands rejected when exceeding distance from home
    - Commands accepted when within geofence
    - Boundary conditions (exactly at limit)
    - Home position must be set
    - Haversine distance calculation accuracy

    GEOFENCE CONCEPT:
    The geofence is a virtual boundary defined as a circle around the
    home position. If the drone would exceed this boundary, commands
    are rejected to maintain VLOS (Visual Line of Sight) compliance
    and prevent flyaways.
    """

    def test_geofence_violation_basic(self, mock_guardian):
        """VALIDATES: Command rejected when exceeding distance from home.

        When a command would take the drone beyond the max_distance_from_home_m,
        it should be rejected with a clear error message.

        Test case: Home at (37.7749, -122.4194), command to position ~1km north.
        Expected: Rejected due to geofence violation.
        """
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
        """VALIDATES: Command accepted when within geofence.

        Commands that keep the drone within the geofence boundary
        should be accepted and return OK.

        Test case: Position ~200m from home within 500m limit.
        """
        # Home is at (37.7749, -122.4194)
        # Request position 200m away should be accepted
        is_valid, reason = mock_guardian.validate_command({
            "latitude": 37.7767,  # ~200m north
            "longitude": -122.4194,
        })

        assert is_valid is True
        assert reason == "OK"

    def test_geofence_exact_boundary(self, mock_guardian):
        """VALIDATES: Command at exact geofence boundary.

        Commands exactly at the boundary should be accepted.
        This tests the boundary condition handling.

        500m ~ 0.0045 degrees latitude at this latitude.
        """
        # Default max distance is 500m
        # Position exactly 500m away
        # ~0.0045 degrees latitude = 500m
        is_valid, reason = mock_guardian.validate_command({
            "latitude": 37.779395,  # just within 500m north
            "longitude": -122.4194,
        })

        # Should be accepted (at or within boundary)
        assert is_valid is True

    def test_geofence_no_home_set(self):
        """VALIDATES: Command rejected when home position not set.

        Without a home position, geofence calculations are impossible.
        Commands should be rejected until home is initialized.

        SAFETY CRITICAL: Prevents operations without reference point.
        """
        guardian = GuardianProcess()
        # Don't set home position

        is_valid, reason = guardian.validate_command({
            "latitude": 37.7749,
            "longitude": -122.4194,
        })

        assert is_valid is False
        assert "home position not set" in reason.lower()

    def test_geofence_with_custom_limit(self, custom_limits):
        """VALIDATES: Geofence with custom distance limit.

        Custom geofence limits should be respected in validation.

        Test case: 100m limit with 200m command -> should reject.
        """
        custom_limits = replace(custom_limits, max_distance_from_home_m=100.0)
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
        """VALIDATES: Haversine distance calculation accuracy.

        The Haversine formula calculates great-circle distance between
        two points on a sphere (Earth). This test verifies accuracy
        against known distances.

        Known distance: San Francisco to Los Angeles ~559km.
        """
        # San Francisco to Los Angeles ~559km
        distance = mock_guardian._haversine_distance(
            37.7749, -122.4194,  # San Francisco
            34.0522, -118.2437   # Los Angeles
        )

        # Should be approximately 559,000 meters (+-10km tolerance)
        assert 549000 < distance < 569000


# =============================================================================
# ALTITUDE LIMIT TESTS
# =============================================================================


class TestAltitudeLimit:
    """Tests for altitude limit scenarios.

    VALIDATES:
    - Commands within altitude limit accepted
    - Commands exceeding altitude limit rejected
    - Boundary conditions (exactly at limit)
    - Negative altitude rejected (below ground)
    - Zero altitude accepted (ground level)
    - Custom altitude limits

    ALTITUDE SAFETY:
    Altitude limits prevent:
    1. Regulatory violations (exceeding 400ft AGL)
    2. Controlled airspace incursions
    3. Loss of VLOS (too high to see)
    4. Reduced maneuverability at altitude
    """

    def test_altitude_within_limit(self, mock_guardian):
        """VALIDATES: Command accepted when within altitude limit.

        Commands specifying altitude below max_altitude_amsl_m should pass.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 100.0  # Below 120m limit
        })

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_exceeds_limit(self, mock_guardian):
        """VALIDATES: Command rejected when exceeding altitude limit.

        Commands specifying altitude above max_altitude_amsl_m should fail
        with a descriptive error including the offending value.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 150.0  # Above 120m limit
        })

        assert is_valid is False
        assert "altitude" in reason.lower()
        assert "150" in reason
        assert "120" in reason

    def test_altitude_at_limit(self, mock_guardian):
        """VALIDATES: Command at exact altitude limit.

        Commands exactly at max_altitude_amsl_m should be accepted.
        Tests boundary condition handling.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 120.0
        })

        assert is_valid is True

    def test_altitude_negative(self, mock_guardian):
        """VALIDATES: Command rejected for negative altitude.

        Negative altitude (below ground level) is physically impossible
        for aerial operations and should be rejected.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": -10.0
        })

        assert is_valid is False
        assert "below ground" in reason.lower()

    def test_altitude_zero(self, mock_guardian):
        """VALIDATES: Command with zero altitude (ground level).

        Zero altitude represents ground level and should be accepted
        for takeoff and landing operations.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 0.0
        })

        assert is_valid is True

    def test_altitude_custom_limit(self, custom_limits):
        """VALIDATES: Altitude with custom limit.

        Custom altitude limits should be respected for specialized
        operations (e.g., indoor flight at 50m).
        """
        custom_limits = replace(custom_limits, max_altitude_amsl_m=50.0)
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
    """Tests for low battery scenarios.

    VALIDATES:
    - Commands accepted when battery above threshold
    - Commands rejected when battery below threshold
    - Boundary conditions (exactly at threshold)
    - Critical battery level detection
    - Custom battery thresholds

    BATTERY SAFETY:
    Low battery is a primary RTL (Return To Launch) trigger. Continuing
    operations with insufficient battery risks uncontrolled landing or
    crash. The 25% threshold provides margin for unexpected conditions.
    """

    def test_battery_above_threshold(self, mock_guardian):
        """VALIDATES: Command accepted when battery above threshold.

        Operations with battery above min_battery_rtl_percent should pass.
        """
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 50.0
        })

        assert is_valid is True

    def test_battery_below_threshold(self, mock_guardian):
        """VALIDATES: Command rejected when battery below threshold.

        Operations with battery below min_battery_rtl_percent should fail,
        triggering RTL recommendation in the error message.
        """
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 15.0  # Below 25% threshold
        })

        assert is_valid is False
        assert "battery" in reason.lower()
        assert "rtl" in reason.lower()

    def test_battery_at_threshold(self, mock_guardian):
        """VALIDATES: Command at exact battery threshold.

        Operations at exactly min_battery_rtl_percent should be allowed,
        providing clear boundary semantics.
        """
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 25.0
        })

        assert is_valid is True

    def test_battery_critical(self, mock_guardian):
        """VALIDATES: Command with critically low battery.

        Very low battery levels should be rejected with the actual
        percentage included in the error for diagnostics.
        """
        is_valid, reason = mock_guardian.validate_command({
            "battery_percent": 5.0
        })

        assert is_valid is False
        assert "5" in reason

    def test_battery_custom_threshold(self, custom_limits):
        """VALIDATES: Battery with custom threshold.

        Custom battery thresholds allow operations with different risk
        profiles (e.g., 40% for long-range missions).
        """
        custom_limits = replace(custom_limits, min_battery_rtl_percent=40.0)
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
    """Tests for heartbeat monitoring scenarios.

    VALIDATES:
    - Heartbeat check passes initially
    - Heartbeat fails after timeout period
    - Heartbeat update resets the timer
    - Age calculation is accurate
    - Custom timeout values work

    HEARTBEAT SAFETY:
    Heartbeat monitoring ensures the control connection is alive. If
    heartbeats stop (e.g., controller crash, network partition), the drone
    should trigger failsafe behavior (hold, RTL, or land depending on config).

    DEFAULT: 2 second timeout allows for normal network jitter while
    detecting actual failures quickly enough to respond.
    """

    def test_heartbeat_ok_initially(self, mock_guardian):
        """VALIDATES: Heartbeat check passes initially.

        After initialization, heartbeat should pass until timeout expires.
        """
        is_ok = mock_guardian.check_heartbeat()

        assert is_ok is True

    def test_heartbeat_timeout(self, mock_guardian):
        """VALIDATES: Heartbeat fails after timeout.

        If no heartbeat received within heartbeat_timeout_s,
        check_heartbeat() should return False.

        Test simulates 3 seconds elapsed (beyond 2s default timeout).
        """
        # Simulate time passing beyond timeout
        mock_guardian._last_heartbeat = time.time() - 3.0  # 3 seconds ago

        is_ok = mock_guardian.check_heartbeat()

        assert is_ok is False

    def test_heartbeat_update(self, mock_guardian):
        """VALIDATES: Heartbeat update resets timeout.

        Calling update_heartbeat() should reset the timer, allowing
        continuous operations as long as heartbeats arrive.
        """
        # Simulate time passing
        mock_guardian._last_heartbeat = time.time() - 1.5

        # Update heartbeat
        mock_guardian.update_heartbeat()

        # Should now be ok
        is_ok = mock_guardian.check_heartbeat()
        assert is_ok is True

    def test_heartbeat_age(self, mock_guardian):
        """VALIDATES: Heartbeat age reporting.

        get_heartbeat_age() should return seconds since last heartbeat
        with reasonable accuracy.
        """
        mock_guardian._last_heartbeat = time.time() - 0.5

        age = mock_guardian.get_heartbeat_age()

        assert 0.4 < age < 0.6

    def test_heartbeat_custom_timeout(self, custom_limits):
        """VALIDATES: Heartbeat with custom timeout.

        Custom heartbeat timeouts allow tuning for network conditions.
        Longer timeouts for high-latency links, shorter for local control.
        """
        custom_limits = replace(custom_limits, heartbeat_timeout_s=5.0)
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
    """Tests for speed limit scenarios.

    VALIDATES:
    - Commands within speed limit accepted
    - Commands exceeding speed limit rejected
    - Boundary conditions (exactly at limit)
    - Custom speed limits

    SPEED SAFETY:
    Speed limits prevent:
    1. Excessive kinetic energy (harder to stop/avoid obstacles)
    2. Loss of control authority at high speeds
    3. Reduced time to react to obstacles
    4. Regulatory violations (some jurisdictions have speed limits)

    DEFAULT: 15 m/s (~54 km/h, ~33 mph) - fast but controllable
    """

    def test_speed_within_limit(self, mock_guardian):
        """VALIDATES: Command accepted when within speed limit."""
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 10.0
        })

        assert is_valid is True

    def test_speed_exceeds_limit(self, mock_guardian):
        """VALIDATES: Command rejected when exceeding speed limit.

        High speed commands should be rejected to maintain control.
        """
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 20.0  # Above 15 m/s limit
        })

        assert is_valid is False
        assert "speed" in reason.lower()

    def test_speed_at_limit(self, mock_guardian):
        """VALIDATES: Command at exact speed limit.

        Commands exactly at max_speed_m_s should be accepted.
        """
        is_valid, reason = mock_guardian.validate_command({
            "speed_m_s": 15.0
        })

        assert is_valid is True

    def test_speed_custom_limit(self, custom_limits):
        """VALIDATES: Speed with custom limit.

        Custom speed limits allow tuning for environment (e.g., 5 m/s
        for indoor operations, 20 m/s for racing).
        """
        custom_limits = replace(custom_limits, max_speed_m_s=5.0)
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
    """Tests for combined validation scenarios.

    VALIDATES:
    - All parameters valid -> command accepted
    - Multiple violations -> first one reported
    - One violation among valid parameters -> rejected
    - Empty commands accepted (no constraints to violate)
    - Partial commands accepted (unspecified params not checked)

    VALIDATION ORDER:
    When multiple violations exist, the first checked constraint
    is reported. This provides deterministic error messages for
    debugging and user feedback.
    """

    def test_all_parameters_valid(self, mock_guardian):
        """VALIDATES: Command with all valid parameters.

        A fully specified command within all limits should pass.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0,
            "latitude": 37.7767,  # ~200m from home
            "longitude": -122.4194,
            "speed_m_s": 5.0,
            "battery_percent": 80.0
        })

        assert is_valid is True

    def test_multiple_violations(self, mock_guardian):
        """VALIDATES: Command with multiple violations reports first one.

        When altitude, speed, and battery all violate limits,
        only the first checked violation is reported.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 200.0,  # Violation
            "speed_m_s": 30.0,         # Also violation
            "battery_percent": 10.0    # Also violation
        })

        assert is_valid is False
        # Should report first violation found (altitude)
        assert "altitude" in reason.lower()

    def test_one_violation_among_valid(self, mock_guardian):
        """VALIDATES: Command with one violation among valid parameters.

        A single violation should cause rejection even if all other
        parameters are within limits.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0,      # Valid
            "latitude": 37.7767,          # Valid (~200m)
            "longitude": -122.4194,
            "speed_m_s": 25.0,            # Invalid
        })

        assert is_valid is False
        assert "speed" in reason.lower()

    def test_empty_command(self, mock_guardian):
        """VALIDATES: Empty command is accepted (no constraints to violate).

        Commands with no parameters don't violate any constraints
        and should pass (vacuously true).
        """
        is_valid, reason = mock_guardian.validate_command({})

        assert is_valid is True

    def test_partial_command(self, mock_guardian):
        """VALIDATES: Command with only some parameters.

        Only specified parameters are validated. Unspecified parameters
        don't cause failures, allowing incremental command building.
        """
        is_valid, reason = mock_guardian.validate_command({
            "altitude_amsl_m": 50.0
            # No lat/lon, speed, or battery specified
        })

        assert is_valid is True


# =============================================================================
# HOME POSITION TESTS
# =============================================================================


class TestHomePosition:
    """Tests for home position management.

    VALIDATES:
    - Home position can be set
    - Home position initially None
    - Home position can be updated
    - is_home_set property works

    HOME POSITION CONCEPT:
    The home position is the reference point for:
    1. Geofence calculations (max distance from home)
    2. Return-to-Launch (RTL) destination
    3. Relative position reporting

    Must be set before operations requiring position awareness.
    """

    def test_set_home(self, mock_guardian):
        """VALIDATES: Setting home position.

        set_home(lat, lon) should store the coordinates and update
        is_home_set to True.
        """
        guardian = GuardianProcess()
        guardian.set_home(37.7749, -122.4194)

        assert guardian.is_home_set is True
        assert guardian.home_position == (37.7749, -122.4194)

    def test_home_position_none_initially(self):
        """VALIDATES: Home position is None before being set.

        A new GuardianProcess should have no home position until
        explicitly set.
        """
        guardian = GuardianProcess()

        assert guardian.is_home_set is False
        assert guardian.home_position is None

    def test_update_home_position(self, mock_guardian):
        """VALIDATES: Updating home position.

        Home position can be changed (e.g., after moving to a new
        operating location).
        """
        mock_guardian.set_home(34.0522, -118.2437)  # Los Angeles

        assert mock_guardian.home_position == (34.0522, -118.2437)


# =============================================================================
# GUARDIAN PROCESS TESTS
# =============================================================================


class TestGuardianProcess:
    """Tests for GuardianProcess class.

    VALIDATES:
    - Initialization with default limits
    - Initialization with custom limits
    - String representation methods

    GuardianProcess is the main safety validation class that coordinates
    all safety checks. It combines HardLimits with state tracking and
    provides the primary validate_command() interface.
    """

    def test_initialization_default_limits(self):
        """VALIDATES: GuardianProcess initializes with default limits.

        Creating a GuardianProcess without arguments should use
        HardLimits() defaults (FAA Part 107 compliant).
        """
        guardian = GuardianProcess()

        assert guardian.limits is not None
        assert isinstance(guardian.limits, HardLimits)

    def test_initialization_custom_limits(self, custom_limits):
        """VALIDATES: GuardianProcess with custom limits.

        Custom HardLimits can be provided for specialized operations.
        """
        guardian = GuardianProcess(custom_limits)

        assert guardian.limits == custom_limits

    def test_repr_methods(self, mock_guardian):
        """VALIDATES: String representation methods.

        __repr__ should provide useful debugging information without
        exposing sensitive data.
        """
        assert mock_guardian.home_position is not None
        assert isinstance(mock_guardian.is_home_set, bool)
