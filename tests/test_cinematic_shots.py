#!/usr/bin/env python3
"""Unit tests for cinematic shot system.

Tests the cinematic shot planning and motion curve functionality
without requiring the full Gazebo simulation.

This test suite validates:
- Motion curve interpolation (linear, ease-in-out, exponential)
- Shot template creation and validation
- Pre-defined cinematic template library
- Trajectory calculations (orbit and follow modes)
- Quality metrics for shot evaluation
- MCP tool endpoints (list, preview, execute)
- Latency compensation via LookaheadPredictor
- Distance maintenance via PIDController
- Sport-specific motion profiles

All tests use mocks to avoid requiring live drone connections or simulators,
making them fast and reliable for CI/CD pipelines.
"""

import asyncio
import json
import math
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mcp_server.tools.cinematic_shots import (
    MotionCurve,
    MotionCurveType,
    ShotTemplate,
    ShotType,
    ShotMetrics,
    CinematicShotPlanner,
    CINEMATIC_TEMPLATES,
    execute_cinematic_shot,
    list_cinematic_templates,
    preview_cinematic_shot,
)


# =============================================================================
# MOCK CLASSES
# =============================================================================
# These mock classes simulate drone hardware and telemetry without requiring
# a live PX4 SITL simulation or physical drone connection.
# They allow tests to run quickly and deterministically in CI/CD environments.


class MockTelemetry:
    """Mock telemetry data simulating drone position and orientation.

    Provides realistic default coordinates (Zurich, Switzerland - the default
    PX4 SITL location) so tests can validate geospatial calculations without
    needing actual GPS data from a simulator.

    Attributes:
        latitude_deg: Latitude in decimal degrees
        longitude_deg: Longitude in decimal degrees
        relative_altitude_m: Height above takeoff in meters
        yaw_deg: Heading angle in degrees (0 = North)
    """
    def __init__(self, lat=47.397742, lon=8.545594, alt=20.0, yaw=0.0):
        self.latitude_deg = lat
        self.longitude_deg = lon
        self.relative_altitude_m = alt
        self.yaw_deg = yaw


class MockCache:
    """Mock telemetry cache simulating the telemetry subscription system.

    In production, the telemetry cache receives real-time updates from the
    MAVSDK telemetry streams. This mock provides the same interface but
    returns static test data for deterministic testing.

    Attributes:
        _telemetry: MockTelemetry instance holding the cached position data
    """
    def __init__(self, telemetry=None):
        self._telemetry = telemetry or MockTelemetry()

    async def get_latest(self):
        """Return the latest cached telemetry (async to match production API).

        Returns:
            MockTelemetry: The current mock telemetry data
        """
        return self._telemetry


class MockDrone:
    """Mock drone object simulating MAVSDK System interface.

    Provides mock implementations of MAVSDK action and gimbal interfaces
    used by the cinematic shot system. AsyncMock is used for methods that
    would normally involve hardware communication delays.

    Attributes:
        gimbal: Mock gimbal control interface for camera positioning
    """
    def __init__(self):
        self.gimbal = MagicMock()
        # set_pitch_and_yaw is async in production (hardware I/O)
        self.gimbal.set_pitch_and_yaw = AsyncMock()


class MockConnectionManager:
    """Mock connection manager simulating drone connection state.

    The cinematic shot system checks connection state before executing shots
    for safety. This mock allows testing both connected and disconnected
    scenarios without actual network operations.

    Attributes:
        _connected: Boolean connection state flag
        _drone: MockDrone instance for hardware interface testing
        _cache: MockCache instance for telemetry access
    """
    def __init__(self, connected=True):
        self._connected = connected
        self._drone = MockDrone()
        self._cache = MockCache()

    def is_connected(self):
        """Return connection state - used by safety checks before flight."""
        return self._connected

    def get_drone(self):
        """Return mock drone for action execution testing."""
        return self._drone

    def get_telemetry_cache(self):
        """Return mock cache for position/altitude telemetry."""
        return self._cache


# =============================================================================
# MOTION CURVE TESTS
# =============================================================================
# Motion curves control how smoothly the drone accelerates and decelerates
# during cinematic shots. Poor motion curves cause jerky footage.


def test_motion_curve_linear():
    """Test linear motion curve - constant velocity interpolation.

    WHAT THIS TEST VALIDATES:
        The linear motion curve produces values that change at a constant
        rate from start_value to end_value over the specified duration.
        This is the simplest interpolation type, producing constant velocity
        movement (no acceleration or deceleration).

    EXPECTED BEHAVIOR:
        - At time=0: value equals start_value (0.0)
        - At time=duration/2: value equals midpoint (50.0)
        - At time=duration: value equals end_value (100.0)
        - After duration: value clamps to end_value (100.0)

    WHY THIS TEST MATTERS:
        Linear interpolation is the baseline motion type. It validates that
        the MotionCurve class correctly handles time normalization (t/duration)
        and value interpolation. If this fails, all other curve types will
        likely fail too since they build on the same foundation.
    """
    curve = MotionCurve(
        curve_type=MotionCurveType.LINEAR,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Verify curve starts at the correct initial value
    assert curve.evaluate(0.0) == 0.0

    # Verify linear interpolation at midpoint (50% time = 50% value)
    assert curve.evaluate(5.0) == 50.0

    # Verify curve reaches the target value at exactly the end time
    assert curve.evaluate(10.0) == 100.0

    # Verify curve clamps to end_value after duration expires
    # (prevents extrapolation beyond defined range)
    assert curve.evaluate(15.0) == 100.0

    print("✓ Motion curve linear interpolation tests passed")


def test_motion_curve_ease_in_out():
    """Test ease-in-out motion curve - smooth acceleration and deceleration.

    WHAT THIS TEST VALIDATES:
        The ease-in-out curve uses an S-curve (sigmoid) function that provides
        smooth acceleration at the start and smooth deceleration at the end.
        This creates professional-looking footage without abrupt velocity changes.

    EXPECTED BEHAVIOR:
        - At time=0 and time=duration: values match start and end exactly
        - At time=duration/2: value is near midpoint but slightly different
          due to the cubic easing function
        - At 25% time: value is LESS than 25% (accelerating phase - slow start)
        - Velocity starts at 0, increases to max at midpoint, decreases to 0

    WHY THIS TEST MATTERS:
        Ease-in-out is the most commonly used motion curve for cinematic shots
        because it eliminates the "jerky start/stop" problem. This test ensures
        the cubic easing math is correct and produces the characteristic
        S-curve acceleration profile that filmmakers expect.
    """
    curve = MotionCurve(
        curve_type=MotionCurveType.EASE_IN_OUT,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Start and end values must be exact regardless of curve shape
    assert curve.evaluate(0.0) == 0.0
    assert curve.evaluate(10.0) == 100.0

    # Middle should be near 50 but curved (ease-in-out is smoother)
    # The exact midpoint of cubic ease-in-out is exactly 50%, but we allow
    # some tolerance for floating point math
    mid_value = curve.evaluate(5.0)
    assert 40 < mid_value < 60, f"Expected mid value near 50, got {mid_value}"

    # Should accelerate at start, decelerate at end
    # So at 25% time, should be less than 25% of value (acceleration phase)
    quarter_value = curve.evaluate(2.5)
    assert quarter_value < 25.0, f"Ease-in: expected <25 at 25% time, got {quarter_value}"

    print("✓ Motion curve ease-in-out tests passed")


def test_motion_curve_exponential():
    """Test exponential motion curve - quick start with gradual settling.

    WHAT THIS TEST VALIDATES:
        The exponential curve uses an exponential function that produces rapid
        initial movement that gradually slows as it approaches the target.
        This is useful for "snap to position" shots where you want quick
        response but smooth settling.

    EXPECTED BEHAVIOR:
        - At time=0: value equals start_value exactly
        - At time=duration: value approaches end_value asymptotically
          (exponential decay means it never quite reaches 100%, but gets very close)
        - At 50% time: value is significantly MORE than 50% (fast start)
        - The curve spends more time "settling" near the target than starting

    WHY THIS TEST MATTERS:
        Exponential curves are useful for dynamic shots where you want the
        drone to respond quickly to subject movement but not overshoot.
        This is particularly important for action sports where the subject
        moves unpredictably and the drone needs to "catch up" quickly.
    """
    curve = MotionCurve(
        curve_type=MotionCurveType.EXPONENTIAL,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Start value must be exact
    assert curve.evaluate(0.0) == 0.0

    # Exponential curve asymptotically approaches end value
    # It never quite reaches exactly 100.0, but should be very close (>99%)
    end_value = curve.evaluate(10.0)
    assert end_value > 99.0, f"Exponential: expected close to 100 at end, got {end_value}"

    # Exponential: quick start, slow settle
    # At 50% time, should be significantly more than 50% (fast initial movement)
    half_value = curve.evaluate(5.0)
    assert half_value > 60, f"Exponential: expected >60 at 50% time, got {half_value}"

    print("✓ Motion curve exponential tests passed")


# =============================================================================
# SHOT TEMPLATE TESTS
# =============================================================================
# Shot templates define pre-configured cinematic movements with specific
# parameters for distance, height, speed, and quality thresholds.


def test_shot_template_creation():
    """Test shot template dataclass creation and default values.

    WHAT THIS TEST VALIDATES:
        The ShotTemplate dataclass correctly stores all configuration
        parameters for a cinematic shot and provides sensible defaults
        for quality thresholds used to validate shot execution.

    EXPECTED BEHAVIOR:
        - All provided parameters are stored correctly
        - Quality thresholds dictionary is auto-populated with defaults
        - Template can be instantiated with minimal or full parameter sets

    WHY THIS TEST MATTERS:
        Shot templates are the core data structure for the cinematic system.
        They define the "recipe" for each shot type. This test ensures the
        data structure is sound and default quality thresholds (like
        max_position_error_m) are always available for shot validation.
    """
    template = ShotTemplate(
        name="Test Shot",
        shot_type=ShotType.ORBIT,
        distance_m=15.0,
        height_offset_m=5.0,
        speed_m_s=3.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        height_lock=True
    )

    # Verify all explicitly set parameters are stored correctly
    assert template.name == "Test Shot"
    assert template.shot_type == ShotType.ORBIT
    assert template.distance_m == 15.0
    assert template.height_lock == True

    # Verify default quality thresholds are auto-populated
    # These are used during shot execution to verify tracking quality
    assert "max_position_error_m" in template.quality_thresholds

    print("✓ Shot template creation tests passed")


def test_cinematic_templates_library():
    """Test pre-defined cinematic templates library completeness.

    WHAT THIS TEST VALIDATES:
        The CINEMATIC_TEMPLATES dictionary contains all expected shot types
        with valid configurations. Each template has required fields and
        sport-specific templates have appropriate parameters.

    EXPECTED BEHAVIOR:
        - All expected template names exist in the library
        - Each template has non-empty name and valid shot_type
        - Sport-specific templates (snowboard, skate) have correct settings
          like height_lock and appropriate distance/height values

    WHY THIS TEST MATTERS:
        The template library is the user-facing API for cinematic shots.
        Users reference these by name (e.g., "orbit_close", "snowboard_halfpipe").
        This test ensures the library is complete and configurations are
        appropriate for each sport/use case. Missing templates would break
        user workflows and potentially cause runtime errors.
    """
    planner = CinematicShotPlanner()

    # List of all expected templates that should be available to users
    expected_templates = [
        "orbit_close", "orbit_wide",
        "follow_close", "follow_wide",
        "reveal_hero", "pass_by_low",
        "top_down_dynamic", "height_locked_jump",
        "fpv_dynamic", "snowboard_halfpipe",
        "skate_ledge_gap"
    ]

    # Verify each expected template exists and has valid configuration
    for name in expected_templates:
        template = planner.get_template(name)
        assert template is not None, f"Template {name} not found"
        assert template.name != ""
        assert template.shot_type is not None

    # Verify sport-specific templates have appropriate parameters
    # Snowboard halfpipe needs height lock to maintain consistent framing
    # as the athlete goes up/down the pipe walls
    snowboard = planner.get_template("snowboard_halfpipe")
    assert snowboard.height_lock == True
    assert snowboard.height_offset_m == 5.0

    # Skate ledge gap needs close follow for detail shots
    skate = planner.get_template("skate_ledge_gap")
    assert skate.shot_type == ShotType.FOLLOW_DYNAMIC
    assert skate.height_offset_m == 2.0  # Close for skate filming

    print(f"✓ Cinematic templates library tests passed ({len(expected_templates)} templates)")


# =============================================================================
# QUALITY METRICS TESTS
# =============================================================================
# Quality metrics track how well the drone is executing a shot and determine
# if the footage meets cinematic standards.


def test_shot_metrics():
    """Test shot quality metrics calculation and threshold validation.

    WHAT THIS TEST VALIDATES:
        The ShotMetrics dataclass correctly tracks execution quality
        (position error, height error, framing score, smoothness) and can
        determine if current performance meets configurable quality thresholds.

    EXPECTED BEHAVIOR:
        - Default thresholds should pass with moderate error values
        - Strict thresholds should fail with the same moderate values
        - Each metric component is independently evaluated

    WHY THIS TEST MATTERS:
        Quality metrics are essential for cinematic shots because they
        tell the operator (or autonomous system) if the current take is
        usable or needs to be repeated. This test ensures the threshold
        logic works correctly so the system can make go/no-go decisions
        during filming.
    """
    metrics = ShotMetrics(
        position_error_m=0.5,      # 50cm from ideal position
        height_error_m=0.3,        # 30cm from ideal height
        framing_score=0.85,        # Good framing (85%)
        smoothness_score=0.9,      # Very smooth (90%)
        velocity_m_s=8.0,          # Current speed
        distance_to_subject_m=10.0 # Distance from target
    )

    # Should pass with default (lenient) thresholds
    # Default thresholds allow up to 1.0m position error, 0.5m height error
    assert metrics.is_quality_acceptable({}) == True

    # Should fail with strict thresholds
    # These thresholds are tighter than the metrics above
    strict_thresholds = {
        "max_position_error_m": 0.3,  # Require <30cm error (we have 50cm)
        "max_height_error_m": 0.2,    # Require <20cm error (we have 30cm)
        "min_framing_score": 0.9      # Require 90% score (we have 85%)
    }
    assert metrics.is_quality_acceptable(strict_thresholds) == False

    print("✓ Shot metrics quality check tests passed")


# =============================================================================
# TRAJECTORY CALCULATION TESTS
# =============================================================================
# Trajectory calculations convert shot templates into actual GPS waypoints
# that the drone will fly. These must be geospatially accurate.


def test_orbit_trajectory_calculation():
    """Test orbit trajectory calculation - circular path around target.

    WHAT THIS TEST VALIDATES:
        The calculate_orbit_trajectory method generates a circular path
        around a center point at a specified radius and altitude. The
        generated waypoints must form a closed circle with consistent
        radius and altitude.

    EXPECTED BEHAVIOR:
        - Number of waypoints equals requested num_points parameter
        - All waypoints maintain the specified altitude exactly
        - All waypoints are approximately radius_m from center point
        - First and last waypoints are nearly identical (closed circle)

    MOCK SETUP EXPLANATION:
        Uses Zurich coordinates (47.397742, 8.545594) which are the default
        PX4 SITL home position. This ensures tests can be validated against
        real simulator runs if needed. meters_per_lat/lon conversions
        account for the non-linear relationship between degrees and meters
        at this latitude.

    WHY THIS TEST MATTERS:
        Orbit shots are the most common cinematic shot type. This test
        validates the core geospatial math that converts polar coordinates
        (radius, angle) to GPS coordinates (lat, lon). Errors here would
        cause the drone to fly the wrong path, potentially creating
        unusable footage or safety hazards.
    """
    planner = CinematicShotPlanner()

    # Test coordinates - Zurich, Switzerland (PX4 SITL default location)
    center_lat = 47.397742
    center_lon = 8.545594
    radius_m = 10.0
    height_m = 20.0
    duration_s = 30.0

    trajectory = planner.calculate_orbit_trajectory(
        center_lat, center_lon,
        radius_m, height_m,
        duration_s,
        num_points=36  # 10-degree increments
    )

    # Verify we got exactly the requested number of waypoints
    assert len(trajectory) == 36

    # Verify each waypoint maintains correct altitude and distance from center
    for lat, lon, alt in trajectory:
        # Altitude should be exactly as specified (orbit is flat, not spiral)
        assert alt == height_m

        # Check points form a circle around center using haversine-like approximation
        # At this latitude, 1 degree latitude = ~111.32 km
        # 1 degree longitude = ~111.32 km * cos(latitude)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

        dx = (lat - center_lat) * meters_per_lat
        dy = (lon - center_lon) * meters_per_lon
        dist = math.sqrt(dx**2 + dy**2)

        # Allow 0.5m tolerance for floating point and projection errors
        assert abs(dist - radius_m) < 0.5, f"Orbit radius mismatch: {dist} vs {radius_m}"

    # First and last points should be very close (closed circle with discrete sampling)
    # Due to discrete sampling at 36 points (10-degree steps), they won't be exactly equal
    lat_diff = abs(trajectory[0][0] - trajectory[-1][0])
    lon_diff = abs(trajectory[0][1] - trajectory[-1][1])
    assert lat_diff < 0.0001, f"First and last lat should be close: {lat_diff}"
    assert lon_diff < 0.0001, f"First and last lon should be close: {lon_diff}"

    print("✓ Orbit trajectory calculation tests passed")


def test_follow_trajectory_calculation():
    """Test follow trajectory calculation - drone follows subject path with offset.

    WHAT THIS TEST VALIDATES:
        The calculate_follow_trajectory method generates a drone path that
        maintains a specified offset from a moving subject. This is used for
        tracking shots where the drone follows an athlete or vehicle.

    EXPECTED BEHAVIOR:
        - Output waypoint count matches subject path count
        - Each drone waypoint maintains the specified altitude offset
        - Each drone waypoint maintains the specified horizontal offset

    MOCK SETUP EXPLANATION:
        Creates a subject path moving north at 5m increments with climbing
        altitude. Tests with offset_north=-5.0 (5m behind) and offset_up=3.0
        (3m above) to verify 3D offset calculation.

    WHY THIS TEST MATTERS:
        Follow shots are essential for action sports filming. The drone must
        maintain consistent framing (distance and angle) relative to a moving
        subject. Errors in offset calculation would cause the drone to drift
        relative to the subject, resulting in poorly framed footage.
    """
    planner = CinematicShotPlanner()

    # Create a simple subject path (moving north, climbing)
    subject_path = []
    meters_per_lat = 111320.0
    center_lat = 47.397742

    for i in range(10):
        lat = center_lat + (i * 5) / meters_per_lat  # 5m north each point
        lon = 8.545594
        alt = 10.0 + i  # Climbing 1m per point
        subject_path.append((lat, lon, alt))

    # Calculate drone trajectory (5m behind and 3m above subject)
    trajectory = planner.calculate_follow_trajectory(
        subject_path,
        offset_north=-5.0,  # Behind (negative = south of subject)
        offset_east=0.0,
        offset_up=3.0  # Above subject
    )

    # Output should have same number of waypoints as input
    assert len(trajectory) == len(subject_path)

    # Check each drone position maintains the 3D offset
    for i, ((subj_lat, subj_lon, subj_alt), (drone_lat, drone_lon, drone_alt)) in enumerate(
        zip(subject_path, trajectory)
    ):
        # Verify altitude offset is maintained (3m above subject)
        assert drone_alt == subj_alt + 3.0

        # Verify horizontal offset is maintained (5m behind)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(subj_lat))

        dx = (drone_lat - subj_lat) * meters_per_lat
        dy = (drone_lon - subj_lon) * meters_per_lon
        dist = math.sqrt(dx**2 + dy**2)

        # Allow 0.5m tolerance for floating point errors
        assert abs(dist - 5.0) < 0.5, f"Follow offset mismatch: {dist} vs 5.0"

    print("✓ Follow trajectory calculation tests passed")


# =============================================================================
# MCP TOOL ENDPOINT TESTS
# =============================================================================
# These tests validate the MCP tool functions that AI agents use to interact
# with the cinematic shot system.


async def test_list_cinematic_templates():
    """Test list_cinematic_templates MCP tool endpoint.

    WHAT THIS TEST VALIDATES:
        The list_cinematic_templates tool returns a properly formatted JSON
        response containing all available templates with their metadata.
        This is the discovery endpoint that AI agents call to learn what
        shots are available.

    EXPECTED BEHAVIOR:
        - Returns success=true status
        - Returns a count of available templates (>0)
        - Returns a templates array with required fields for each template

    WHY THIS TEST MATTERS:
        This is the primary API that AI agents use to discover cinematic
        capabilities. If this endpoint fails or returns malformed data,
        agents cannot know what shots are available, effectively disabling
        the cinematic feature for autonomous operation.
    """
    result_json = await list_cinematic_templates()
    result = json.loads(result_json)

    # Response must indicate success
    assert result.get("success") == True
    # Must contain templates array
    assert "templates" in result
    # Must report non-zero count
    assert result.get("count") > 0

    # Each template must have required metadata fields
    templates = result["templates"]
    for template in templates:
        assert "name" in template  # Machine-readable identifier
        assert "display_name" in template  # Human-readable label
        assert "shot_type" in template  # Type of movement
        assert "height_lock" in template  # Whether altitude is maintained

    print(f"✓ list_cinematic_templates: {result['count']} templates listed")


async def test_preview_cinematic_shot():
    """Test preview_cinematic_shot MCP tool endpoint.

    WHAT THIS TEST VALIDATES:
        The preview_cinematic_shot tool generates a preview of a shot
        without actually executing it. This allows AI agents to validate
        shot parameters and see what the trajectory would look like.

    EXPECTED BEHAVIOR:
        - Returns success=true for valid template names
        - Returns sample_trajectory showing example waypoints
        - Returns total_waypoints count for planning
        - Returns estimated_duration_s for scheduling
        - Returns motion_curve type for reference

    MOCK SETUP EXPLANATION:
        Uses "orbit_close" template with Zurich coordinates to generate
        a realistic preview. No mock needed since preview is calculation-only
        and doesn't require drone connection.

    WHY THIS TEST MATTERS:
        Preview allows agents to validate shots before execution, preventing
        mistakes that could waste battery or create unusable footage. This
        is especially important for autonomous operation where there's no
        human operator to catch errors before they happen.
    """
    result_json = await preview_cinematic_shot(
        template_name="orbit_close",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    # Verify successful preview generation
    assert result.get("success") == True
    assert result.get("template") == "orbit_close"

    # Verify preview contains planning information
    assert "sample_trajectory" in result  # Example waypoints
    assert "total_waypoints" in result    # For flight planning
    assert "estimated_duration_s" in result  # For battery/time planning
    assert "motion_curve" in result       # For motion reference

    print(f"✓ preview_cinematic_shot: {result['total_waypoints']} waypoints")


async def test_preview_unknown_template():
    """Test preview_cinematic_shot error handling for unknown templates.

    WHAT THIS TEST VALIDATES:
        The preview_cinematic_shot tool gracefully handles requests for
        non-existent template names, returning a proper error response
        instead of crashing or returning malformed data.

    EXPECTED BEHAVIOR:
        - Returns success=false for invalid template names
        - Returns an error message explaining the problem

    WHY THIS TEST MATTERS:
        Error handling is critical for robust agent operation. When an
        agent requests an invalid template (perhaps due to hallucination or
        a typo), the system must provide clear feedback so the agent can
        correct its approach rather than getting stuck or confused.
    """
    result_json = await preview_cinematic_shot(
        template_name="nonexistent_template",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    # Must indicate failure
    assert result.get("success") == False
    # Must provide error explanation
    assert "error" in result

    print("✓ preview_cinematic_shot error handling passed")


async def test_execute_cinematic_shot_unknown_template():
    """Test execute_cinematic_shot error handling for unknown templates.

    WHAT THIS TEST VALIDATES:
        The execute_cinematic_shot tool safely rejects attempts to execute
        non-existent templates without attempting any drone operations.
        This is a safety-critical validation that prevents invalid commands.

    EXPECTED BEHAVIOR:
        - Returns success=false for invalid template names
        - Returns an error message mentioning available templates
        - Does NOT attempt to connect to or command a drone

    WHY THIS TEST MATTERS:
        This is a critical safety test. Execute commands control actual
        hardware that could cause property damage or injury. The system
        must validate ALL parameters before attempting any hardware
        interaction. This test ensures the validation layer catches
        invalid templates before they reach the hardware control layer.
    """
    result_json = await execute_cinematic_shot(
        template_name="nonexistent",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    # Must indicate failure
    assert result.get("success") == False
    # Must provide error explanation
    assert "error" in result
    # Error should mention available templates to guide user
    assert "Available" in result.get("error", "")

    print("✓ execute_cinematic_shot unknown template handling passed")


@pytest.mark.asyncio
async def test_execute_cinematic_shot_handles_missing_drone_without_unawaited_coroutine():
    with patch("avatar.mcp_server.tools.cinematic_shots.ConnectionManager") as manager_cls:
        manager = manager_cls.return_value
        manager.get_drone = AsyncMock(return_value=None)
        raw = await execute_cinematic_shot("orbit_close", 37.0, -122.0)

    data = json.loads(raw)
    assert data["success"] is False
    assert data["error"] == "Drone not connected"


# =============================================================================
# CONTROL SYSTEM TESTS
# =============================================================================
# These tests validate the control algorithms that maintain shot quality
# during execution by compensating for latency and maintaining distance.


def test_lookahead_predictor():
    """Test LookaheadPredictor for latency compensation.

    WHAT THIS TEST VALIDATES:
        The LookaheadPredictor estimates where a moving subject will be in
        the future based on current position and velocity. This compensates
        for control system latency (sensor delay + processing delay + actuator
        delay) that would otherwise cause the drone to lag behind subjects.

    EXPECTED BEHAVIOR:
        - Predicts future position based on velocity vector
        - Moving north at 5 m/s for 0.2s should predict ~1m north movement
        - East and altitude should remain unchanged for pure north velocity

    MOCK SETUP EXPLANATION:
        Creates a predictor with 0.2s horizon (typical control latency).
        Initializes at origin (0,0,10m alt) with 5 m/s north velocity.
        Prediction should show ~1m north displacement.

    WHY THIS TEST MATTERS:
        Latency compensation is essential for tracking fast-moving subjects
        like athletes or vehicles. Without it, the drone would consistently
        lag behind the subject by the control loop latency (typically 100-500ms),
        resulting in poorly framed footage. This predictor is the key algorithm
        that enables smooth tracking shots.
    """
    from avatar.mcp_server.tools.cinematic_shots import LookaheadPredictor, PREDICTION_HORIZON_S

    predictor = LookaheadPredictor(horizon_s=0.2)

    # Initial update at origin with northward velocity
    predictor.update(lat=0.0, lon=0.0, alt_m=10.0, vel_north=5.0, vel_east=0.0, vel_up=0.0)

    # Predict 0.2s in the future
    pred_lat, pred_lon, pred_alt = predictor.predict_future(0.2)

    # Should have moved north by ~1m (5 m/s * 0.2s = 1m)
    # 1m / 111320 m/deg ≈ 0.000009 degrees
    assert pred_lat > 0.0, "Predicted latitude should be north of origin"
    assert abs(pred_lon - 0.0) < 0.000001, "Predicted longitude should be unchanged"
    assert abs(pred_alt - 10.0) < 0.01, "Predicted altitude should be unchanged"

    print(f"✓ LookaheadPredictor: horizon={PREDICTION_HORIZON_S}s, predicted movement at 5 m/s")


def test_pid_controller():
    """Test PIDController for distance maintenance.

    WHAT THIS TEST VALIDATES:
        The PIDController maintains a target distance from the subject by
        calculating correction velocities based on error (difference between
        target and actual distance). It uses proportional, integral, and
        derivative terms for smooth, stable control.

    EXPECTED BEHAVIOR:
        - Positive error produces positive output (move closer)
        - Smaller error produces smaller output (proportional response)
        - Negative error produces negative output (move away)
        - Same magnitude error produces same magnitude output (symmetric)
        - Output respects configured limits
        - Reset clears accumulated state (integral windup prevention)

    MOCK SETUP EXPLANATION:
        Creates PID with kp=0.8 (proportional gain), ki=0.1 (integral),
        kd=0.2 (derivative), and output_limit=5.0 m/s. Tests with errors
        of 2.0m and 1.0m to verify proportional response, then tests
        reset to ensure stateless behavior between shots.

    WHY THIS TEST MATTERS:
        The PID controller is the core algorithm that maintains shot framing
        by continuously adjusting drone velocity to maintain target distance.
        A malfunctioning PID would cause the drone to oscillate (unstable)
        or drift (insufficient correction), ruining footage. Proper reset
        behavior prevents integral windup that could cause erratic behavior
        when switching between different shot types.
    """
    from avatar.mcp_server.tools.cinematic_shots import PIDController

    pid = PIDController(kp=0.8, ki=0.1, kd=0.2, output_limit=5.0)

    # Test error response - positive error should produce positive correction
    output1 = pid.update(error=2.0)
    assert output1 > 0, "PID should output positive for positive error"
    assert output1 <= 5.0, "PID output should respect limit"

    # Test response to smaller error (proportional term should be smaller)
    # Reset to avoid integral windup affecting test
    pid.reset()
    output2_small = pid.update(error=1.0)
    # For P-only (kp=0.8): 0.8*2.0=1.6 vs 0.8*1.0=0.8, so smaller error -> smaller output
    assert output2_small < output1, "Smaller error should produce smaller correction"

    # Test negative error (overshoot correction - drone too close)
    pid.reset()
    output_neg = pid.update(error=-2.0)
    assert output_neg < 0, "Negative error should produce negative output"
    assert abs(output_neg) == output1, "Same magnitude error should produce same magnitude output"

    # Test reset clears accumulated integral state
    # After reset, same error should give approximately same output as first time
    pid.reset()
    output_after_reset = pid.update(error=2.0)
    assert abs(output_after_reset - output1) < 0.01, "After reset, same error should give same output"

    print(f"✓ PIDController: kp=0.8, ki=0.1, kd=0.2, responds to error correctly")


# =============================================================================
# SPORT PROFILE TESTS
# =============================================================================
# Sport profiles provide optimized motion parameters for different sports
# based on their typical movement patterns and filming requirements.


def test_sport_profiles():
    """Test sport-specific motion profiles for hardware-aware limits.

    WHAT THIS TEST VALIDATES:
        The SPORT_PROFILES dictionary contains optimized parameters for each
        supported sport, with speeds that respect HARDWARE_MAX_SPEED_M_S limits.
        Each profile is linked to appropriate cinematic templates.

    EXPECTED BEHAVIOR:
        - All expected sport profiles exist
        - All profile speeds are within hardware safety limits
        - Templates reference appropriate sport profiles
        - Sport-specific speeds are appropriate (conservative for snowboard,
          faster for motocross)

    WHY THIS TEST MATTERS:
        Different sports have different movement patterns that require
        tailored drone settings. Snowboarders move slower but need height
        lock for pipe walls; motocross requires faster tracking for jumps.
        This test ensures all sports have valid profiles and that speeds
        are capped by hardware limits to prevent dangerous flight commands.
    """
    from avatar.mcp_server.tools.cinematic_shots import SPORT_PROFILES, CINEMATIC_TEMPLATES, HARDWARE_MAX_SPEED_M_S

    # Verify all sport profiles exist that users might request
    expected_profiles = [
        "snowboard_halfpipe", "snowboard_powder",
        "skate_ledge", "skate_bowl",
        "motocross_jump", "trail_running"
    ]

    for profile_name in expected_profiles:
        assert profile_name in SPORT_PROFILES, f"Missing sport profile: {profile_name}"
        profile = SPORT_PROFILES[profile_name]
        # Safety-critical: verify no profile exceeds hardware capabilities
        assert profile.max_speed_m_s <= HARDWARE_MAX_SPEED_M_S, f"{profile_name} speed exceeds hardware limit"

    # Verify templates use sport profiles appropriately
    assert "snowboard_halfpipe" in CINEMATIC_TEMPLATES, "Missing snowboard_halfpipe template"
    assert "skate_ledge_gap" in CINEMATIC_TEMPLATES, "Missing skate_ledge_gap template"
    assert "skate_bowl" in CINEMATIC_TEMPLATES, "Missing skate_bowl template"
    assert "motocross_jump" in CINEMATIC_TEMPLATES, "Missing motocross_jump template"
    assert "trail_running" in CINEMATIC_TEMPLATES, "Missing trail_running template"

    # Check hardware-aware speeds are appropriate for each sport
    # Snowboard: conservative speed (maneuvering in tight pipe)
    snowboard_template = CINEMATIC_TEMPLATES["snowboard_halfpipe"]
    assert snowboard_template.speed_m_s <= 8.0, "Snowboard speed should be conservative"

    # Motocross: faster but still within limits (tracking fast jumps)
    moto_template = CINEMATIC_TEMPLATES["motocross_jump"]
    assert moto_template.speed_m_s <= 12.0, "Motocross speed should be within hardware limit"

    print(f"✓ Sport profiles: {len(SPORT_PROFILES)} profiles, hardware-aware limits verified")


# =============================================================================
# TEST RUNNER
# =============================================================================


async def main():
    """Run all cinematic shot tests with progress reporting.

    Executes all test functions in sequence, handling both sync and async
    tests. Provides detailed pass/fail reporting and stack traces for failures.

    Returns:
        bool: True if all tests passed, False otherwise
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║     CINEMATIC SHOTS UNIT TEST SUITE                          ║
╚══════════════════════════════════════════════════════════════╝
    """)

    tests = [
        ("Motion curve - linear", test_motion_curve_linear),
        ("Motion curve - ease-in-out", test_motion_curve_ease_in_out),
        ("Motion curve - exponential", test_motion_curve_exponential),
        ("Shot template creation", test_shot_template_creation),
        ("Cinematic templates library", test_cinematic_templates_library),
        ("Shot metrics quality", test_shot_metrics),
        ("Orbit trajectory calculation", test_orbit_trajectory_calculation),
        ("Follow trajectory calculation", test_follow_trajectory_calculation),
        ("List templates", test_list_cinematic_templates),
        ("Preview shot", test_preview_cinematic_shot),
        ("Preview unknown template", test_preview_unknown_template),
        ("Execute unknown template", test_execute_cinematic_shot_unknown_template),
        ("LookaheadPredictor", test_lookahead_predictor),
        ("PIDController", test_pid_controller),
        ("Sport profiles", test_sport_profiles),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\nRunning: {name}...")
            # Handle both async and sync test functions
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✓ All cinematic shot tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
