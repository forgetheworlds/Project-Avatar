#!/usr/bin/env python3
"""Unit tests for cinematic shot system.

Tests the cinematic shot planning and motion curve functionality
without requiring the full Gazebo simulation.
"""

import asyncio
import json
import math
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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


class MockTelemetry:
    """Mock telemetry data."""
    def __init__(self, lat=47.397742, lon=8.545594, alt=20.0, yaw=0.0):
        self.latitude_deg = lat
        self.longitude_deg = lon
        self.relative_altitude_m = alt
        self.yaw_deg = yaw


class MockCache:
    """Mock telemetry cache."""
    def __init__(self, telemetry=None):
        self._telemetry = telemetry or MockTelemetry()

    async def get_latest(self):
        return self._telemetry


class MockDrone:
    """Mock drone for testing."""
    def __init__(self):
        self.gimbal = MagicMock()
        self.gimbal.set_pitch_and_yaw = AsyncMock()


class MockConnectionManager:
    """Mock connection manager."""
    def __init__(self, connected=True):
        self._connected = connected
        self._drone = MockDrone()
        self._cache = MockCache()

    def is_connected(self):
        return self._connected

    def get_drone(self):
        return self._drone

    def get_telemetry_cache(self):
        return self._cache


def test_motion_curve_linear():
    """Test linear motion curve."""
    curve = MotionCurve(
        curve_type=MotionCurveType.LINEAR,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Start value
    assert curve.evaluate(0.0) == 0.0

    # Mid value
    assert curve.evaluate(5.0) == 50.0

    # End value
    assert curve.evaluate(10.0) == 100.0

    # After end
    assert curve.evaluate(15.0) == 100.0

    print("✓ Motion curve linear interpolation tests passed")


def test_motion_curve_ease_in_out():
    """Test ease-in-out motion curve."""
    curve = MotionCurve(
        curve_type=MotionCurveType.EASE_IN_OUT,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Start and end
    assert curve.evaluate(0.0) == 0.0
    assert curve.evaluate(10.0) == 100.0

    # Middle should be near 50 but curved (ease-in-out is smoother)
    mid_value = curve.evaluate(5.0)
    assert 40 < mid_value < 60, f"Expected mid value near 50, got {mid_value}"

    # Should accelerate at start, decelerate at end
    # So at 25% time, should be less than 25% of value
    quarter_value = curve.evaluate(2.5)
    assert quarter_value < 25.0, f"Ease-in: expected <25 at 25% time, got {quarter_value}"

    print("✓ Motion curve ease-in-out tests passed")


def test_motion_curve_exponential():
    """Test exponential motion curve."""
    curve = MotionCurve(
        curve_type=MotionCurveType.EXPONENTIAL,
        start_time=0.0,
        duration=10.0,
        start_value=0.0,
        end_value=100.0
    )

    # Start and end
    assert curve.evaluate(0.0) == 0.0
    # Exponential curve asymptotically approaches end value
    end_value = curve.evaluate(10.0)
    assert end_value > 99.0, f"Exponential: expected close to 100 at end, got {end_value}"

    # Exponential: quick start, slow settle
    # At 50% time, should be significantly more than 50%
    half_value = curve.evaluate(5.0)
    assert half_value > 60, f"Exponential: expected >60 at 50% time, got {half_value}"

    print("✓ Motion curve exponential tests passed")


def test_shot_template_creation():
    """Test shot template dataclass."""
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

    assert template.name == "Test Shot"
    assert template.shot_type == ShotType.ORBIT
    assert template.distance_m == 15.0
    assert template.height_lock == True
    assert "max_position_error_m" in template.quality_thresholds

    print("✓ Shot template creation tests passed")


def test_cinematic_templates_library():
    """Test pre-defined cinematic templates."""
    planner = CinematicShotPlanner()

    # Check all expected templates exist
    expected_templates = [
        "orbit_close", "orbit_wide",
        "follow_close", "follow_wide",
        "reveal_hero", "pass_by_low",
        "top_down_dynamic", "height_locked_jump",
        "fpv_dynamic", "snowboard_halfpipe",
        "skate_ledge_gap"
    ]

    for name in expected_templates:
        template = planner.get_template(name)
        assert template is not None, f"Template {name} not found"
        assert template.name != ""
        assert template.shot_type is not None

    # Check snowboard_halfpipe has height lock
    snowboard = planner.get_template("snowboard_halfpipe")
    assert snowboard.height_lock == True
    assert snowboard.height_offset_m == 5.0

    # Check skate_ledge_gap parameters
    skate = planner.get_template("skate_ledge_gap")
    assert skate.shot_type == ShotType.FOLLOW_DYNAMIC
    assert skate.height_offset_m == 2.0  # Close for skate filming

    print(f"✓ Cinematic templates library tests passed ({len(expected_templates)} templates)")


def test_shot_metrics():
    """Test shot quality metrics."""
    metrics = ShotMetrics(
        position_error_m=0.5,
        height_error_m=0.3,
        framing_score=0.85,
        smoothness_score=0.9,
        velocity_m_s=8.0,
        distance_to_subject_m=10.0
    )

    # Should pass with default thresholds
    assert metrics.is_quality_acceptable({}) == True

    # Should fail with strict thresholds
    strict_thresholds = {
        "max_position_error_m": 0.3,
        "max_height_error_m": 0.2,
        "min_framing_score": 0.9
    }
    assert metrics.is_quality_acceptable(strict_thresholds) == False

    print("✓ Shot metrics quality check tests passed")


def test_orbit_trajectory_calculation():
    """Test orbit trajectory calculation."""
    planner = CinematicShotPlanner()

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

    assert len(trajectory) == 36

    # Check all points are at same altitude
    for lat, lon, alt in trajectory:
        assert alt == height_m
        # Check points form a circle around center
        # (approximate check using haversine-like distance)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

        dx = (lat - center_lat) * meters_per_lat
        dy = (lon - center_lon) * meters_per_lon
        dist = math.sqrt(dx**2 + dy**2)

        assert abs(dist - radius_m) < 0.5, f"Orbit radius mismatch: {dist} vs {radius_m}"

    # First and last points should be very close (closed circle with discrete sampling)
    # Due to discrete sampling, they won't be exactly equal
    lat_diff = abs(trajectory[0][0] - trajectory[-1][0])
    lon_diff = abs(trajectory[0][1] - trajectory[-1][1])
    assert lat_diff < 0.0001, f"First and last lat should be close: {lat_diff}"
    assert lon_diff < 0.0001, f"First and last lon should be close: {lon_diff}"

    print("✓ Orbit trajectory calculation tests passed")


def test_follow_trajectory_calculation():
    """Test follow trajectory calculation."""
    planner = CinematicShotPlanner()

    # Create a simple subject path (moving north)
    subject_path = []
    meters_per_lat = 111320.0
    center_lat = 47.397742

    for i in range(10):
        lat = center_lat + (i * 5) / meters_per_lat  # 5m north each point
        lon = 8.545594
        alt = 10.0 + i  # Climbing
        subject_path.append((lat, lon, alt))

    # Calculate drone trajectory (5m behind and 3m above)
    trajectory = planner.calculate_follow_trajectory(
        subject_path,
        offset_north=-5.0,  # Behind
        offset_east=0.0,
        offset_up=3.0  # Above
    )

    assert len(trajectory) == len(subject_path)

    # Check each drone position maintains offset
    for i, ((subj_lat, subj_lon, subj_alt), (drone_lat, drone_lon, drone_alt)) in enumerate(
        zip(subject_path, trajectory)
    ):
        assert drone_alt == subj_alt + 3.0

        # Check horizontal offset
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(subj_lat))

        dx = (drone_lat - subj_lat) * meters_per_lat
        dy = (drone_lon - subj_lon) * meters_per_lon
        dist = math.sqrt(dx**2 + dy**2)

        assert abs(dist - 5.0) < 0.5, f"Follow offset mismatch: {dist} vs 5.0"

    print("✓ Follow trajectory calculation tests passed")


async def test_list_cinematic_templates():
    """Test list_cinematic_templates tool."""
    result_json = await list_cinematic_templates()
    result = json.loads(result_json)

    assert result.get("success") == True
    assert "templates" in result
    assert result.get("count") > 0

    # Check template structure
    templates = result["templates"]
    for template in templates:
        assert "name" in template
        assert "display_name" in template
        assert "shot_type" in template
        assert "height_lock" in template

    print(f"✓ list_cinematic_templates: {result['count']} templates listed")


async def test_preview_cinematic_shot():
    """Test preview_cinematic_shot tool."""
    result_json = await preview_cinematic_shot(
        template_name="orbit_close",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    assert result.get("success") == True
    assert result.get("template") == "orbit_close"
    assert "sample_trajectory" in result
    assert "total_waypoints" in result
    assert "estimated_duration_s" in result
    assert "motion_curve" in result

    print(f"✓ preview_cinematic_shot: {result['total_waypoints']} waypoints")


async def test_preview_unknown_template():
    """Test preview with unknown template."""
    result_json = await preview_cinematic_shot(
        template_name="nonexistent_template",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    assert result.get("success") == False
    assert "error" in result

    print("✓ preview_cinematic_shot error handling passed")


async def test_execute_cinematic_shot_unknown_template():
    """Test execute with unknown template."""
    result_json = await execute_cinematic_shot(
        template_name="nonexistent",
        target_lat=47.397742,
        target_lon=8.545594
    )
    result = json.loads(result_json)

    assert result.get("success") == False
    assert "error" in result
    assert "Available" in result.get("error", "")

    print("✓ execute_cinematic_shot unknown template handling passed")


def test_lookahead_predictor():
    """Test LookaheadPredictor for latency compensation."""
    from avatar.mcp_server.tools.cinematic_shots import LookaheadPredictor, PREDICTION_HORIZON_S

    predictor = LookaheadPredictor(horizon_s=0.2)

    # Initial update at origin
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
    """Test PIDController for distance maintenance."""
    from avatar.mcp_server.tools.cinematic_shots import PIDController

    pid = PIDController(kp=0.8, ki=0.1, kd=0.2, output_limit=5.0)

    # Test error response
    output1 = pid.update(error=2.0)
    assert output1 > 0, "PID should output positive for positive error"
    assert output1 <= 5.0, "PID output should respect limit"

    # Test response to smaller error (proportional term should be smaller)
    # Reset to avoid integral windup affecting test
    pid.reset()
    output2_small = pid.update(error=1.0)
    # For P-only (kp=0.8): 0.8*2.0=1.6 vs 0.8*1.0=0.8, so smaller error -> smaller output
    assert output2_small < output1, "Smaller error should produce smaller correction"

    # Test negative error (overshoot correction)
    pid.reset()
    output_neg = pid.update(error=-2.0)
    assert output_neg < 0, "Negative error should produce negative output"
    assert abs(output_neg) == output1, "Same magnitude error should produce same magnitude output"

    # Test reset clears state
    pid.reset()
    output_after_reset = pid.update(error=2.0)
    assert abs(output_after_reset - output1) < 0.01, "After reset, same error should give same output"

    print(f"✓ PIDController: kp=0.8, ki=0.1, kd=0.2, responds to error correctly")


def test_sport_profiles():
    """Test sport-specific motion profiles."""
    from avatar.mcp_server.tools.cinematic_shots import SPORT_PROFILES, CINEMATIC_TEMPLATES, HARDWARE_MAX_SPEED_M_S

    # Verify all sport profiles exist
    expected_profiles = [
        "snowboard_halfpipe", "snowboard_powder",
        "skate_ledge", "skate_bowl",
        "motocross_jump", "trail_running"
    ]

    for profile_name in expected_profiles:
        assert profile_name in SPORT_PROFILES, f"Missing sport profile: {profile_name}"
        profile = SPORT_PROFILES[profile_name]
        assert profile.max_speed_m_s <= HARDWARE_MAX_SPEED_M_S, f"{profile_name} speed exceeds hardware limit"

    # Verify templates use sport profiles
    assert "snowboard_halfpipe" in CINEMATIC_TEMPLATES, "Missing snowboard_halfpipe template"
    assert "skate_ledge_gap" in CINEMATIC_TEMPLATES, "Missing skate_ledge_gap template"
    assert "skate_bowl" in CINEMATIC_TEMPLATES, "Missing skate_bowl template"
    assert "motocross_jump" in CINEMATIC_TEMPLATES, "Missing motocross_jump template"
    assert "trail_running" in CINEMATIC_TEMPLATES, "Missing trail_running template"

    # Check hardware-aware speeds
    snowboard_template = CINEMATIC_TEMPLATES["snowboard_halfpipe"]
    assert snowboard_template.speed_m_s <= 8.0, "Snowboard speed should be conservative"

    moto_template = CINEMATIC_TEMPLATES["motocross_jump"]
    assert moto_template.speed_m_s <= 12.0, "Motocross speed should be within hardware limit"

    print(f"✓ Sport profiles: {len(SPORT_PROFILES)} profiles, hardware-aware limits verified")


async def main():
    """Run all cinematic shot tests."""
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
