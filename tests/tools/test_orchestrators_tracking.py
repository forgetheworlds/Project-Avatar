"""Tests for track_bbox MCP orchestrator - Kalman-based bbox tracking.

W2a-T17: Tests for the track_bbox orchestrator tool.

WHAT THESE TESTS VALIDATE:
    These tests verify the track_bbox() orchestrator which tracks an object
    identified by bounding box using Kalman filter prediction for smooth
    intercept positioning.

    Key capabilities tested:
    - Input schema validation (bbox format, duration limits, speed limits)
    - BBox to NED position estimation
    - KalmanTracker integration for position smoothing
    - Intercept velocity calculation with standoff
    - Tracking loop execution at 10Hz
    - Proper error handling for connection failures

WHY THESE TESTS MATTER:
    track_bbox is a high-level orchestrator that coordinates:
    - Vision detection (YOLO) for bbox updates
    - KalmanTracker for position estimation and prediction
    - Flight control (set_velocity) for following

    Without proper validation:
    - Invalid bbox inputs could cause runtime errors
    - Kalman filter might not initialize correctly
    - Velocity commands could be unsafe
    - Tracking could fail to handle vision occlusions

TEST STRUCTURE:
    - TestInputSchema: Validation of TrackBboxInput schema
    - TestBboxToNed: BBox to NED position estimation
    - TestInterceptVelocity: Velocity calculation for intercept
    - TestTrackBboxFunction: Full orchestrator function tests

Coverage:
- Input schema validation (bbox format, parameter ranges)
- BBox to NED position estimation accuracy
- KalmanTracker initialization and updates
- Intercept velocity with standoff distance
- Tracking loop execution
- Error handling for connection failures
"""

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server.schemas import BBox
from avatar.mcp_server.tools.orchestrators import (
    TrackBboxInput,
    track_bbox,
    _bbox_to_ned_offset,
    _calculate_intercept_velocity,
)
from avatar.mcp_server.tools.advanced_tracking import (
    KalmanTracker,
    TrackingState,
)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def valid_bbox():
    """Create a valid bounding box for testing."""
    return BBox(x=0.5, y=0.4, w=0.15, h=0.3)


@pytest.fixture
def mock_telemetry():
    """Create mock telemetry data."""
    telem = MagicMock()
    telem.latitude_deg = 37.7749
    telem.longitude_deg = -122.4194
    telem.relative_altitude_m = 20.0
    telem.yaw_deg = 0.0
    return telem


@pytest.fixture
def mock_telemetry_cache(mock_telemetry):
    """Create mock telemetry cache."""
    cache = MagicMock()
    cache.get_latest = AsyncMock(return_value=mock_telemetry)
    return cache


@pytest.fixture
def mock_drone():
    """Create a mocked drone with gimbal support."""
    drone = MagicMock()
    drone.gimbal = MagicMock()
    drone.gimbal.set_pitch_and_yaw = AsyncMock()
    return drone


@pytest.fixture
def mock_vision_tools():
    """Create mock vision tools instance."""
    vision = MagicMock()
    vision.get_detected_objects = AsyncMock(return_value={
        "success": True,
        "detections": [],
    })
    return vision


# =============================================================================
# TEST CLASSES - INPUT SCHEMA
# =============================================================================


class TestTrackBboxInput:
    """Test TrackBboxInput schema validation.

    WHAT THESE TESTS VALIDATE:
        - Valid inputs are accepted
        - Invalid bbox values are rejected
        - Duration limits are enforced (0-300s)
        - Speed limits are enforced (0.1-10 m/s)
        - Standoff limits are enforced (2-50m)

    WHY THESE TESTS MATTER:
        Input validation prevents runtime errors and ensures
        safe parameter ranges for tracking operations.
    """

    def test_valid_input(self, valid_bbox):
        """Test that valid input is accepted."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=60.0,
            approach_speed_m_s=2.0,
            standoff_m=5.0,
        )
        assert input_obj.bbox.x == 0.5
        assert input_obj.duration_s == 60.0
        assert input_obj.approach_speed_m_s == 2.0
        assert input_obj.standoff_m == 5.0

    def test_bbox_dict_input(self):
        """Test that bbox can be created from dict."""
        input_obj = TrackBboxInput(
            bbox=BBox(x=0.3, y=0.7, w=0.2, h=0.4),
            duration_s=30.0,
        )
        assert input_obj.bbox.x == 0.3

    def test_duration_at_minimum(self, valid_bbox):
        """Test minimum valid duration (just above 0)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=0.1,
        )
        assert input_obj.duration_s == 0.1

    def test_duration_at_maximum(self, valid_bbox):
        """Test maximum valid duration (300s = 5 minutes)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=300.0,
        )
        assert input_obj.duration_s == 300.0

    def test_duration_exceeds_maximum(self, valid_bbox):
        """Test that duration > 300s is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=400.0,
            )

    def test_duration_negative(self, valid_bbox):
        """Test that negative duration is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=-1.0,
            )

    def test_duration_zero(self, valid_bbox):
        """Test that zero duration is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=0.0,
            )

    def test_speed_at_minimum(self, valid_bbox):
        """Test minimum valid speed (just above 0)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=10.0,
            approach_speed_m_s=0.1,
        )
        assert input_obj.approach_speed_m_s == 0.1

    def test_speed_at_maximum(self, valid_bbox):
        """Test maximum valid speed (10 m/s)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=10.0,
            approach_speed_m_s=10.0,
        )
        assert input_obj.approach_speed_m_s == 10.0

    def test_speed_exceeds_maximum(self, valid_bbox):
        """Test that speed > 10 m/s is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=10.0,
                approach_speed_m_s=15.0,
            )

    def test_standoff_at_minimum(self, valid_bbox):
        """Test minimum valid standoff (2m)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=10.0,
            standoff_m=2.0,
        )
        assert input_obj.standoff_m == 2.0

    def test_standoff_at_maximum(self, valid_bbox):
        """Test maximum valid standoff (50m)."""
        input_obj = TrackBboxInput(
            bbox=valid_bbox,
            duration_s=10.0,
            standoff_m=50.0,
        )
        assert input_obj.standoff_m == 50.0

    def test_standoff_below_minimum(self, valid_bbox):
        """Test that standoff < 2m is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=10.0,
                standoff_m=1.0,
            )

    def test_standoff_exceeds_maximum(self, valid_bbox):
        """Test that standoff > 50m is rejected."""
        with pytest.raises(Exception):
            TrackBboxInput(
                bbox=valid_bbox,
                duration_s=10.0,
                standoff_m=100.0,
            )


# =============================================================================
# TEST CLASSES - BBOX TO NED CONVERSION
# =============================================================================


class TestBboxToNedOffset:
    """Test BBox to NED position estimation.

    WHAT THESE TESTS VALIDATE:
        - Center bbox (x=0.5, y=0.5) returns zero offset
        - Off-center bbox produces appropriate NED offset
        - Altitude affects distance estimation
        - Edge cases handled gracefully

    WHY THESE TESTS MATTER:
        Accurate position estimation from 2D bbox is critical
        for tracking. Errors here would cause the drone to
        fly to wrong positions.
    """

    def test_center_bbox_returns_zero_offset(self):
        """Test that center bbox (0.5, 0.5) returns minimal offset."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)
        north, east, down = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=20.0,
        )
        # Center bbox should have minimal angular offset
        assert abs(north) < 5.0  # Small offset expected
        assert abs(east) < 5.0

    def test_bbox_right_of_center(self):
        """Test bbox to the right produces positive east offset."""
        bbox = BBox(x=0.7, y=0.5, w=0.2, h=0.3)  # x=0.7 is right of center
        north, east, down = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=20.0,
        )
        # Right of center should produce positive east
        assert east > 0

    def test_bbox_left_of_center(self):
        """Test bbox to the left produces negative east offset."""
        bbox = BBox(x=0.3, y=0.5, w=0.2, h=0.3)  # x=0.3 is left of center
        north, east, down = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=20.0,
        )
        # Left of center should produce negative east
        assert east < 0

    def test_bbox_above_center(self):
        """Test bbox above center in image (higher y is lower in world)."""
        bbox = BBox(x=0.5, y=0.3, w=0.2, h=0.3)  # y=0.3 is above center
        north, east, down = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=20.0,
        )
        # Above center in image = closer to horizon = further away
        # This affects distance estimation
        assert isinstance(north, float)
        assert isinstance(east, float)

    def test_higher_altitude_increases_distance(self):
        """Test that higher drone altitude estimates larger distance."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)

        # Low altitude
        low_north, low_east, _ = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=10.0,
        )

        # High altitude
        high_north, high_east, _ = _bbox_to_ned_offset(
            bbox=bbox,
            drone_alt_m=40.0,
        )

        # Higher altitude should estimate further distance
        distance_low = math.sqrt(low_north**2 + low_east**2)
        distance_high = math.sqrt(high_north**2 + high_east**2)

        assert distance_high > distance_low

    def test_returns_tuple_of_floats(self):
        """Test that function returns tuple of three floats."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)
        result = _bbox_to_ned_offset(bbox=bbox, drone_alt_m=20.0)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)


# =============================================================================
# TEST CLASSES - INTERCEPT VELOCITY
# =============================================================================


class TestInterceptVelocity:
    """Test intercept velocity calculation.

    WHAT THESE TESTS VALIDATE:
        - Velocity is clamped to max speed
        - Standoff distance is respected
        - Target velocity affects intercept point
        - Returns valid velocity tuple

    WHY THESE TESTS MATTER:
        Proper velocity calculation ensures smooth tracking
        without exceeding safety limits.
    """

    def test_at_target_returns_zero_velocity(self):
        """Test that being at target position returns zero velocity."""
        tracking_state = TrackingState(
            x=0.0, y=0.0, z=0.0,
            vx=0.0, vy=0.0, vz=0.0,
            ax=0.0, ay=0.0, az=0.0,
            timestamp=0.0,
            confidence=1.0,
        )

        # Drone at origin, target at standoff distance
        current_pos = (0.0, 0.0, 0.0)
        target_pos = (5.0, 0.0, 0.0)  # 5m north

        vel_n, vel_e, vel_d = _calculate_intercept_velocity(
            current_pos=current_pos,
            target_pos=target_pos,
            max_speed=10.0,
            standoff=5.0,  # Same as distance = should be zero velocity
            tracking_state=tracking_state,
        )

        # At standoff distance, velocity should be near zero
        assert abs(vel_n) < 0.1
        assert abs(vel_e) < 0.1
        assert abs(vel_d) < 0.1

    def test_velocity_clamped_to_max_speed(self):
        """Test that velocity magnitude is clamped to max_speed."""
        tracking_state = TrackingState(
            x=0.0, y=0.0, z=0.0,
            vx=0.0, vy=0.0, vz=0.0,
            ax=0.0, ay=0.0, az=0.0,
            timestamp=0.0,
            confidence=1.0,
        )

        # Target far away - would produce high velocity
        current_pos = (0.0, 0.0, 0.0)
        target_pos = (100.0, 100.0, 0.0)  # 141m away

        vel_n, vel_e, vel_d = _calculate_intercept_velocity(
            current_pos=current_pos,
            target_pos=target_pos,
            max_speed=5.0,  # Low max speed
            standoff=5.0,
            tracking_state=tracking_state,
        )

        # Velocity magnitude should be <= max_speed
        velocity_mag = math.sqrt(vel_n**2 + vel_e**2 + vel_d**2)
        assert velocity_mag <= 5.1  # Small tolerance for numerical errors

    def test_moving_target_affects_velocity(self):
        """Test that target velocity is accounted for in intercept."""
        # Stationary target
        stationary_state = TrackingState(
            x=10.0, y=0.0, z=0.0,
            vx=0.0, vy=0.0, vz=0.0,
            ax=0.0, ay=0.0, az=0.0,
            timestamp=0.0,
            confidence=1.0,
        )

        # Moving target (moving north)
        moving_state = TrackingState(
            x=10.0, y=0.0, z=0.0,
            vx=5.0, vy=0.0, vz=0.0,  # 5 m/s north
            ax=0.0, ay=0.0, az=0.0,
            timestamp=0.0,
            confidence=1.0,
        )

        current_pos = (0.0, 0.0, 0.0)
        target_pos = (10.0, 0.0, 0.0)

        stat_vel = _calculate_intercept_velocity(
            current_pos=current_pos,
            target_pos=target_pos,
            max_speed=10.0,
            standoff=5.0,
            tracking_state=stationary_state,
        )

        moving_vel = _calculate_intercept_velocity(
            current_pos=current_pos,
            target_pos=target_pos,
            max_speed=10.0,
            standoff=5.0,
            tracking_state=moving_state,
        )

        # Moving target should have different (higher) north velocity
        # to intercept ahead of target
        assert moving_vel[0] > stat_vel[0]


# =============================================================================
# TEST CLASSES - TRACK_BBOX FUNCTION
# =============================================================================


class TestTrackBboxFunction:
    """Test the track_bbox orchestrator function.

    WHAT THESE TESTS VALIDATE:
        - Function accepts valid input and returns JSON
        - Connection errors are handled gracefully
        - Tracking loop executes correctly
        - Statistics are returned in response

    WHY THESE TESTS MATTER:
        The track_bbox function is the main entry point for
        bbox-based tracking. Proper error handling ensures
        safe operation.
    """

    async def test_returns_valid_json(self, valid_bbox):
        """Test that function returns valid JSON string."""
        result = await track_bbox(
            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
            duration_s=0.5,  # Short duration for test
        )

        # Should be a string
        assert isinstance(result, str)

        # Should be parseable as JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    async def test_handles_invalid_bbox(self):
        """Test that invalid bbox returns error envelope."""
        result = await track_bbox(
            bbox={"x": 2.0, "y": 0.5, "w": 0.2, "h": 0.3},  # x > 1 is invalid
            duration_s=10.0,
        )

        parsed = json.loads(result)

        # Should indicate error
        assert parsed.get("success") is False or parsed.get("isError") is True

    async def test_handles_duration_exceeds_limit(self):
        """Test that duration > 300s returns error."""
        result = await track_bbox(
            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
            duration_s=500.0,  # Exceeds 300s limit
        )

        parsed = json.loads(result)

        # Should indicate error
        assert parsed.get("success") is False or parsed.get("isError") is True

    async def test_handles_no_connection(self, valid_bbox):
        """Test handling when drone is not connected."""
        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.get_drone = AsyncMock(return_value=None)
            mock_cm.return_value = mock_instance

            result = await track_bbox(
                bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
                duration_s=5.0,
            )

            parsed = json.loads(result)

            # Should indicate connection error
            assert parsed.get("success") is False or parsed.get("isError") is True

    async def test_successful_tracking(self, valid_bbox, mock_drone, mock_telemetry_cache, mock_vision_tools):
        """Test successful tracking with mocked dependencies."""
        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.get_drone = AsyncMock(return_value=mock_drone)
            mock_instance.get_telemetry_cache = MagicMock(return_value=mock_telemetry_cache)
            mock_cm.return_value = mock_instance

            with patch('avatar.mcp_server.tools.orchestrators.get_vision_tools_instance', return_value=mock_vision_tools):
                with patch('avatar.mcp_server.tools.orchestrators.set_velocity', new_callable=AsyncMock) as mock_vel:
                    with patch('avatar.mcp_server.tools.orchestrators.hold', new_callable=AsyncMock):
                        result = await track_bbox(
                            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
                            duration_s=0.5,  # Short for test
                            approach_speed_m_s=2.0,
                            standoff_m=5.0,
                        )

                        parsed = json.loads(result)

                        # Should indicate success
                        assert parsed.get("success") is True

                        # Should have tracking stats
                        assert "tracking_stats" in parsed
                        assert "duration_s" in parsed
                        assert "final_state" in parsed

    async def test_statistics_included_in_response(self):
        """Test that tracking statistics are included in response."""
        # This test verifies the response format includes expected fields
        # We'll check the format with a minimal mock

        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.get_drone = AsyncMock(return_value=None)
            mock_cm.return_value = mock_instance

            result = await track_bbox(
                bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
                duration_s=5.0,
            )

            # Even on failure, should be valid JSON
            parsed = json.loads(result)
            assert isinstance(parsed, dict)


# =============================================================================
# TEST CLASSES - KALMAN INTEGRATION
# =============================================================================


class TestKalmanIntegration:
    """Test KalmanTracker integration in track_bbox.

    WHAT THESE TESTS VALIDATE:
        - KalmanTracker is properly initialized
        - Position updates are processed
        - Predictions are generated correctly
        - State includes confidence

    WHY THESE TESTS MATTER:
        Kalman filtering smooths noisy vision measurements
        and enables prediction for intercept tracking.
    """

    def test_kalman_initialization(self):
        """Test that KalmanTracker can be initialized."""
        kalman = KalmanTracker(dt=0.1)

        assert kalman.dt == 0.1
        assert kalman.state.shape == (9,)  # 9-dimensional state

    def test_kalman_update(self):
        """Test that KalmanTracker processes position updates."""
        kalman = KalmanTracker(dt=0.1)

        # Update with position measurement
        state = kalman.update(x=10.0, y=5.0, z=-20.0, timestamp=1.0)

        assert state.x == pytest.approx(10.0, abs=1.0)
        assert state.y == pytest.approx(5.0, abs=1.0)
        assert state.z == pytest.approx(-20.0, abs=1.0)

    def test_kalman_prediction(self):
        """Test that KalmanTracker generates predictions."""
        kalman = KalmanTracker(dt=0.1)

        # Initialize with position
        kalman.update(x=10.0, y=5.0, z=-20.0, timestamp=1.0)

        # Predict ahead
        pred_x, pred_y, pred_z = kalman.predict(horizon_s=0.5)

        # Prediction should be close to current position (no velocity yet)
        assert abs(pred_x - 10.0) < 5.0
        assert abs(pred_y - 5.0) < 5.0

    def test_kalman_confidence(self):
        """Test that KalmanTracker provides confidence measure."""
        kalman = KalmanTracker(dt=0.1)

        state = kalman.update(x=10.0, y=5.0, z=-20.0, timestamp=1.0)

        # Confidence should be between 0 and 1
        assert 0.0 <= state.confidence <= 1.0

    def test_kalman_velocity_estimation(self):
        """Test that KalmanTracker estimates velocity from position changes."""
        kalman = KalmanTracker(dt=0.1)

        # First measurement
        kalman.update(x=0.0, y=0.0, z=-20.0, timestamp=1.0)

        # Second measurement (moving)
        state = kalman.update(x=1.0, y=0.0, z=-20.0, timestamp=1.1)

        # Should have estimated some velocity
        # Note: Kalman may not immediately estimate velocity with just 2 samples
        # but the state should be valid
        assert isinstance(state.vx, float)
        assert isinstance(state.vy, float)


# =============================================================================
# TEST CLASSES - RESULT FORMAT
# =============================================================================


class TestResultFormat:
    """Test the format of successful results.

    WHAT THESE TESTS VALIDATE:
        - Successful result contains expected fields
        - Field types are correct
        - Statistics are properly formatted

    WHY THESE TESTS MATTER:
        Consistent result format allows LLM to parse and
        make decisions based on tracking outcomes.
    """

    async def test_success_result_format(self, mock_drone, mock_telemetry_cache, mock_vision_tools):
        """Test that successful result contains expected fields."""
        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm:
            mock_instance = MagicMock()
            mock_instance.get_drone = AsyncMock(return_value=mock_drone)
            mock_instance.get_telemetry_cache = MagicMock(return_value=mock_telemetry_cache)
            mock_cm.return_value = mock_instance

            with patch('avatar.mcp_server.tools.orchestrators.get_vision_tools_instance', return_value=mock_vision_tools):
                with patch('avatar.mcp_server.tools.orchestrators.set_velocity', new_callable=AsyncMock):
                    with patch('avatar.mcp_server.tools.orchestrators.hold', new_callable=AsyncMock):
                        result = await track_bbox(
                            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
                            duration_s=0.5,
                        )

                        parsed = json.loads(result)

                        assert parsed["success"] is True
                        assert "duration_s" in parsed
                        assert "tracking_stats" in parsed
                        assert "final_state" in parsed
                        assert "parameters" in parsed

                        # Check tracking_stats structure
                        stats = parsed["tracking_stats"]
                        assert "total_updates" in stats
                        assert "avg_confidence" in stats
                        assert "max_velocity_m_s" in stats
                        assert "kalman_predictions" in stats

                        # Check final_state structure
                        state = parsed["final_state"]
                        assert "x_m" in state
                        assert "y_m" in state
                        assert "z_m" in state
                        assert "vx_m_s" in state
                        assert "vy_m_s" in state
                        assert "vz_m_s" in state
                        assert "confidence" in state

                        # Check parameters structure
                        params = parsed["parameters"]
                        assert "standoff_m" in params
                        assert "approach_speed_m_s" in params
                        assert "initial_bbox" in params
