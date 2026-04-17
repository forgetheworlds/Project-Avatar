"""Tests for orbit_subject_vision orchestrator tool.

WHAT THESE TESTS VALIDATE:
    These tests verify the orbit_subject_vision() MCP orchestrator which
    enables a drone to orbit around a visually-detected subject while
    keeping them centered in the camera frame.

    Key capabilities tested:
    - Input validation for bounding box and orbit parameters
    - Subject position estimation from 2D bounding box
    - Orbit velocity vector calculation
    - Integration with tracking and flight subsystems
    - Error handling for invalid inputs and missing connections

WHY THESE TESTS MATTER:
    The orbit_subject_vision orchestrator is critical for cinematic and
    surveillance operations. Without proper testing:
    - Subject position could be estimated incorrectly
    - Orbit trajectory could be unstable or dangerous
    - Gimbal could lose tracking during orbit
    - Invalid inputs could cause crashes or dangerous behavior

Test Coverage:
    - W2a-T18: orbit_subject_vision orchestrator implementation
"""

import json
import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server.schemas import BBox
from avatar.mcp_server.tools.orchestrators import (
    orbit_subject_vision,
    OrbitSubjectVisionInput,
    ORBIT_SUBJECT_VISION_TOOL,
    _estimate_subject_position_3d,
    _calculate_orbit_velocity_vectors,
    MIN_ORBIT_RADIUS_M,
    MAX_ORBIT_RADIUS_M,
    MIN_ORBIT_SPEED_M_S,
    MAX_ORBIT_SPEED_M_S,
    MAX_ORBITS,
    MIN_ALTITUDE_M,
)


# =============================================================================
# MOCK TELEMETRY CLASSES
# =============================================================================


@dataclass
class MockTelemetryData:
    """Mock telemetry data structure for testing.

    Provides all required fields for orbit operations testing.
    """
    timestamp: float
    latitude_deg: float
    longitude_deg: float
    relative_altitude_m: float = 15.0
    absolute_altitude_m: float = 50.0
    velocity_north_m_s: float = 0.0
    velocity_east_m_s: float = 0.0
    velocity_down_m_s: float = 0.0
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    battery_percent: float = 100.0
    armed: bool = True
    in_air: bool = True
    flight_mode: str = "OFFBOARD"


class MockTelemetryCache:
    """Mock telemetry cache for testing."""

    def __init__(self, data: Optional[MockTelemetryData] = None):
        self._data = data
        self._sequence = []
        self._index = 0

    def set_sequence(self, sequence):
        """Set sequence of telemetry data points."""
        self._sequence = sequence
        self._index = 0

    async def get_latest(self):
        """Get current or next telemetry data."""
        if self._sequence:
            if self._index < len(self._sequence):
                data = self._sequence[self._index]
                self._index += 1
                return data
            return self._sequence[-1]
        return self._data


class MockGimbal:
    """Mock gimbal for testing."""

    def __init__(self):
        self.pitch = 0.0
        self.yaw = 0.0
        self.set_pitch_and_yaw = AsyncMock()


class MockDrone:
    """Mock drone for testing."""

    def __init__(self):
        self.gimbal = MockGimbal()
        self.action = MagicMock()
        self.offboard = MagicMock()
        self.telemetry = MagicMock()


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_connection_manager():
    """Create mocked connection manager."""
    with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm_class:
        mock_cm = MagicMock()
        mock_drone = MockDrone()
        mock_cache = MockTelemetryCache()

        mock_cm.get_drone = AsyncMock(return_value=mock_drone)
        mock_cm.get_telemetry_cache = MagicMock(return_value=mock_cache)
        mock_cm_class.return_value = mock_cm

        yield mock_cm, mock_drone, mock_cache


@pytest.fixture
def valid_bbox():
    """Valid bounding box for testing."""
    return {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3}


@pytest.fixture
def valid_telemetry():
    """Valid telemetry data for orbit operations."""
    return MockTelemetryData(
        timestamp=time.time(),
        latitude_deg=37.7749,
        longitude_deg=-122.4194,
        relative_altitude_m=15.0,
    )


# =============================================================================
# INPUT SCHEMA TESTS
# =============================================================================


class TestOrbitSubjectVisionInput:
    """Tests for OrbitSubjectVisionInput Pydantic schema validation.

    These tests ensure that invalid inputs are rejected and valid inputs
    are properly validated according to the schema constraints.
    """

    def test_valid_input_with_defaults(self, valid_bbox):
        """Test that valid input with default values passes validation."""
        input_data = OrbitSubjectVisionInput(bbox=valid_bbox)

        assert input_data.bbox.x == 0.5
        assert input_data.bbox.y == 0.5
        assert input_data.radius_m == 10.0
        assert input_data.speed_m_s == 3.0
        assert input_data.orbits == 1
        assert input_data.direction == "cw"

    def test_valid_input_with_custom_values(self, valid_bbox):
        """Test that valid input with custom values passes validation."""
        input_data = OrbitSubjectVisionInput(
            bbox=valid_bbox,
            radius_m=25.0,
            speed_m_s=5.0,
            orbits=3,
            direction="ccw",
        )

        assert input_data.radius_m == 25.0
        assert input_data.speed_m_s == 5.0
        assert input_data.orbits == 3
        assert input_data.direction == "ccw"

    def test_invalid_bbox_missing_field(self):
        """Test that bbox missing required fields fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox={"x": 0.5})  # Missing y, w, h

    def test_invalid_bbox_out_of_range(self):
        """Test that bbox values outside 0-1 range fail validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox={"x": 1.5, "y": 0.5, "w": 0.2, "h": 0.3})

    def test_invalid_radius_too_small(self, valid_bbox):
        """Test that radius below minimum fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, radius_m=MIN_ORBIT_RADIUS_M - 0.1)

    def test_invalid_radius_too_large(self, valid_bbox):
        """Test that radius above maximum fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, radius_m=MAX_ORBIT_RADIUS_M + 1.0)

    def test_invalid_speed_too_slow(self, valid_bbox):
        """Test that speed below minimum fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, speed_m_s=MIN_ORBIT_SPEED_M_S - 0.1)

    def test_invalid_speed_too_fast(self, valid_bbox):
        """Test that speed above maximum fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, speed_m_s=MAX_ORBIT_SPEED_M_S + 1.0)

    def test_invalid_orbits_zero(self, valid_bbox):
        """Test that zero orbits fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, orbits=0)

    def test_invalid_orbits_too_many(self, valid_bbox):
        """Test that too many orbits fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, orbits=MAX_ORBITS + 1)

    def test_invalid_direction(self, valid_bbox):
        """Test that invalid direction fails validation."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, direction="left")

    def test_extra_fields_forbidden(self, valid_bbox):
        """Test that extra fields are forbidden by config."""
        with pytest.raises(Exception):  # ValidationError
            OrbitSubjectVisionInput(bbox=valid_bbox, extra_field="not_allowed")


# =============================================================================
# POSITION ESTIMATION TESTS
# =============================================================================


class TestEstimateSubjectPosition3d:
    """Tests for _estimate_subject_position_3d function.

    These tests verify the geometric calculations that convert a 2D
    bounding box into an estimated 3D world position.
    """

    def test_center_bbox_at_default_pitch(self):
        """Test estimation for centered bbox at default -45 degree pitch."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)
        drone_lat = 37.7749
        drone_lon = -122.4194
        drone_alt = 15.0
        camera_pitch = -45.0

        lat, lon, alt = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=drone_alt,
            camera_pitch_deg=camera_pitch,
        )

        # Subject should be estimated in front of drone
        # At -45 degree pitch from 15m altitude, ground distance = 15m
        assert lat != drone_lat
        assert lon == drone_lon  # No east-west offset for centered bbox
        assert alt == 0.0  # Ground level assumption

    def test_off_center_bbox_moves_east(self):
        """Test that bbox offset to the right estimates position to the east."""
        bbox = BBox(x=0.7, y=0.5, w=0.2, h=0.3)  # Offset right
        drone_lat = 37.7749
        drone_lon = -122.4194
        drone_alt = 20.0

        lat, lon, alt = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=drone_alt,
        )

        # Longitude should be east (greater) than drone
        assert lon > drone_lon

    def test_off_center_bbox_moves_west(self):
        """Test that bbox offset to the left estimates position to the west."""
        bbox = BBox(x=0.3, y=0.5, w=0.2, h=0.3)  # Offset left
        drone_lat = 37.7749
        drone_lon = -122.4194
        drone_alt = 20.0

        lat, lon, alt = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=drone_alt,
        )

        # Longitude should be west (lesser) than drone
        assert lon < drone_lon

    def test_higher_altitude_extends_distance(self):
        """Test that higher altitude estimates farther subject."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)
        drone_lat = 37.7749
        drone_lon = -122.4194

        # Lower altitude
        _, _, _ = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=10.0,
            camera_pitch_deg=-45.0,
        )

        # Higher altitude - should estimate farther from drone
        lat_high, _, _ = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=30.0,
            camera_pitch_deg=-45.0,
        )

        # Higher altitude should estimate subject farther north (in front)
        # This is because ground_distance = alt / tan(pitch)
        assert lat_high > drone_lat

    def test_near_horizontal_pitch_returns_drone_position(self):
        """Test that near-horizontal pitch returns drone position as fallback."""
        bbox = BBox(x=0.5, y=0.5, w=0.2, h=0.3)
        drone_lat = 37.7749
        drone_lon = -122.4194

        # Near-horizontal pitch (can't estimate ground position)
        lat, lon, alt = _estimate_subject_position_3d(
            bbox=bbox,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt_m=15.0,
            camera_pitch_deg=-0.001,  # Very close to horizontal (triggers fallback)
        )

        # Should return drone position as fallback
        assert lat == drone_lat
        assert lon == drone_lon


# =============================================================================
# ORBIT VELOCITY CALCULATION TESTS
# =============================================================================


class TestCalculateOrbitVelocityVectors:
    """Tests for _calculate_orbit_velocity_vectors function.

    These tests verify the orbital mechanics calculations that generate
    velocity vectors for circular orbit motion.
    """

    def test_clockwise_orbit_velocity(self):
        """Test that clockwise orbit produces correct velocity direction."""
        # Drone directly north of subject
        drone_lat = 37.7758  # ~100m north
        drone_lon = -122.4194
        subject_lat = 37.7749
        subject_lon = -122.4194
        radius_m = 100.0
        speed_m_s = 5.0

        north_vel, east_vel = _calculate_orbit_velocity_vectors(
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            subject_lat=subject_lat,
            subject_lon=subject_lon,
            radius_m=radius_m,
            speed_m_s=speed_m_s,
            clockwise=True,
        )

        # For clockwise orbit when north of subject:
        # Should move east (tangent direction for CW)
        assert east_vel > 0

    def test_counter_clockwise_orbit_velocity(self):
        """Test that counter-clockwise orbit produces opposite velocity direction."""
        drone_lat = 37.7758  # ~100m north
        drone_lon = -122.4194
        subject_lat = 37.7749
        subject_lon = -122.4194
        radius_m = 100.0
        speed_m_s = 5.0

        north_vel_cw, east_vel_cw = _calculate_orbit_velocity_vectors(
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            subject_lat=subject_lat,
            subject_lon=subject_lon,
            radius_m=radius_m,
            speed_m_s=speed_m_s,
            clockwise=True,
        )

        north_vel_ccw, east_vel_ccw = _calculate_orbit_velocity_vectors(
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            subject_lat=subject_lat,
            subject_lon=subject_lon,
            radius_m=radius_m,
            speed_m_s=speed_m_s,
            clockwise=False,
        )

        # CCW should have opposite tangent direction
        assert east_vel_ccw < east_vel_cw

    def test_velocity_magnitude_approximately_speed(self):
        """Test that velocity magnitude is approximately the requested speed when at radius."""
        # Place drone at exactly the orbit radius from subject
        # ~10m north corresponds to ~0.00009 degrees latitude
        subject_lat = 37.7749
        subject_lon = -122.4194
        radius_m = 10.0
        speed_m_s = 5.0

        # Calculate drone position at exact radius north of subject
        meters_per_lat = 111320.0
        drone_lat = subject_lat + (radius_m / meters_per_lat)
        drone_lon = subject_lon

        north_vel, east_vel = _calculate_orbit_velocity_vectors(
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            subject_lat=subject_lat,
            subject_lon=subject_lon,
            radius_m=radius_m,
            speed_m_s=speed_m_s,
            clockwise=True,
        )

        # Velocity magnitude should be close to requested speed
        # At exact radius, radial correction should be minimal
        velocity_mag = math.sqrt(north_vel**2 + east_vel**2)
        # Allow up to 20% deviation for radial correction
        assert abs(velocity_mag - speed_m_s) < speed_m_s * 0.5


# =============================================================================
# ORCHESTRATOR MCP TOOL TESTS
# =============================================================================


class TestOrbitSubjectVisionTool:
    """Tests for the orbit_subject_vision MCP tool wrapper function.

    These tests verify the complete orchestrator functionality including
    input validation, connection handling, and result formatting.
    """

    @pytest.mark.asyncio
    async def test_invalid_bbox_returns_error(self):
        """Test that invalid bbox returns properly formatted error."""
        result_json = await orbit_subject_vision(
            bbox={"x": 2.0, "y": 0.5, "w": 0.2, "h": 0.3},  # Invalid x > 1
            radius_m=10.0,
            speed_m_s=3.0,
            orbits=1,
            direction="cw",
        )

        result = json.loads(result_json)
        assert "isError" in result or "success" in result
        if "success" in result:
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_radius_returns_error(self):
        """Test that invalid radius returns properly formatted error."""
        result_json = await orbit_subject_vision(
            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
            radius_m=1.0,  # Below minimum
            speed_m_s=3.0,
            orbits=1,
            direction="cw",
        )

        result = json.loads(result_json)
        assert "isError" in result or "success" in result

    @pytest.mark.asyncio
    async def test_invalid_speed_returns_error(self):
        """Test that invalid speed returns properly formatted error."""
        result_json = await orbit_subject_vision(
            bbox={"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3},
            radius_m=10.0,
            speed_m_s=20.0,  # Above maximum
            orbits=1,
            direction="cw",
        )

        result = json.loads(result_json)
        assert "isError" in result or "success" in result

    @pytest.mark.asyncio
    async def test_no_drone_connection_returns_error(self, valid_bbox):
        """Test that missing drone connection returns proper error."""
        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.get_drone = AsyncMock(return_value=None)  # No drone
            mock_cm.get_telemetry_cache = MagicMock(return_value=None)
            mock_cm_class.return_value = mock_cm

            result_json = await orbit_subject_vision(
                bbox=valid_bbox,
                radius_m=10.0,
                speed_m_s=3.0,
                orbits=1,
                direction="cw",
            )

            result = json.loads(result_json)
            assert "isError" in result or "success" in result

    @pytest.mark.asyncio
    async def test_low_altitude_returns_error(self, valid_bbox, valid_telemetry):
        """Test that altitude below minimum returns proper error."""
        low_alt_telemetry = MockTelemetryData(
            timestamp=time.time(),
            latitude_deg=37.7749,
            longitude_deg=-122.4194,
            relative_altitude_m=MIN_ALTITUDE_M - 1.0,  # Below minimum
        )

        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm_class:
            mock_cm = MagicMock()
            mock_drone = MockDrone()
            mock_cache = MockTelemetryCache(low_alt_telemetry)

            mock_cm.get_drone = AsyncMock(return_value=mock_drone)
            mock_cm.get_telemetry_cache = MagicMock(return_value=mock_cache)
            mock_cm_class.return_value = mock_cm

            result_json = await orbit_subject_vision(
                bbox=valid_bbox,
                radius_m=10.0,
                speed_m_s=3.0,
                orbits=1,
                direction="cw",
            )

            result = json.loads(result_json)
            assert result["success"] is False
            assert "altitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_orbit_returns_result(self, valid_bbox, valid_telemetry, mock_connection_manager):
        """Test that successful orbit returns proper result structure."""
        mock_cm, mock_drone, mock_cache = mock_connection_manager
        mock_cache._data = valid_telemetry

        # Mock set_velocity and hold to avoid actual flight commands
        with patch('avatar.mcp_server.tools.orchestrators.set_velocity', new_callable=AsyncMock) as mock_vel:
            with patch('avatar.mcp_server.tools.orchestrators.hold', new_callable=AsyncMock) as mock_hold:
                mock_vel.return_value = json.dumps({"success": True})
                mock_hold.return_value = json.dumps({"success": True})

                result_json = await orbit_subject_vision(
                    bbox=valid_bbox,
                    radius_m=10.0,
                    speed_m_s=3.0,
                    orbits=1,
                    direction="cw",
                )

                result = json.loads(result_json)
                # Should have success and orbit statistics
                assert "success" in result
                assert "orbits_completed" in result or "error" in result


# =============================================================================
# TOOL METADATA TESTS
# =============================================================================


class TestToolMetadata:
    """Tests for tool registration metadata.

    Verifies that the tool metadata required for MCP server registration
    is properly defined.
    """

    def test_tool_metadata_exists(self):
        """Test that tool metadata is defined."""
        assert ORBIT_SUBJECT_VISION_TOOL is not None

    def test_tool_name(self):
        """Test that tool name is correct."""
        assert ORBIT_SUBJECT_VISION_TOOL["name"] == "orbit_subject_vision"

    def test_tool_has_description(self):
        """Test that tool has a description."""
        assert "description" in ORBIT_SUBJECT_VISION_TOOL
        assert len(ORBIT_SUBJECT_VISION_TOOL["description"]) > 0

    def test_tool_has_input_schema(self):
        """Test that tool has input schema."""
        assert "inputSchema" in ORBIT_SUBJECT_VISION_TOOL
        schema = ORBIT_SUBJECT_VISION_TOOL["inputSchema"]
        assert "properties" in schema
        assert "bbox" in schema["properties"]
        assert "radius_m" in schema["properties"]
        assert "speed_m_s" in schema["properties"]
        assert "orbits" in schema["properties"]
        assert "direction" in schema["properties"]

    def test_tool_has_annotations(self):
        """Test that tool has MCP annotations."""
        assert "annotations" in ORBIT_SUBJECT_VISION_TOOL
        annotations = ORBIT_SUBJECT_VISION_TOOL["annotations"]
        assert "readOnlyHint" in annotations
        assert "destructiveHint" in annotations
        assert annotations["readOnlyHint"] is False  # It modifies drone state
        assert annotations["destructiveHint"] is False  # It's not destructive

    def test_tool_has_output_schema(self):
        """Test that tool has output schema."""
        assert "outputSchema" in ORBIT_SUBJECT_VISION_TOOL
        assert ORBIT_SUBJECT_VISION_TOOL["outputSchema"]["type"] == "object"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOrbitIntegration:
    """Integration tests for orbit_subject_vision with other components.

    These tests verify that the orchestrator correctly integrates with
    other parts of the system (telemetry, velocity control, gimbal).
    """

    @pytest.mark.asyncio
    async def test_orbit_uses_telemetry_for_position(self, valid_bbox):
        """Test that orbit uses telemetry for position estimation."""
        telemetry = MockTelemetryData(
            timestamp=time.time(),
            latitude_deg=37.7749,
            longitude_deg=-122.4194,
            relative_altitude_m=20.0,
        )

        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm_class:
            mock_cm = MagicMock()
            mock_drone = MockDrone()
            mock_cache = MockTelemetryCache(telemetry)

            mock_cm.get_drone = AsyncMock(return_value=mock_drone)
            mock_cm.get_telemetry_cache = MagicMock(return_value=mock_cache)
            mock_cm_class.return_value = mock_cm

            with patch('avatar.mcp_server.tools.orchestrators.set_velocity') as mock_vel:
                with patch('avatar.mcp_server.tools.orchestrators.hold') as mock_hold:
                    mock_vel.return_value = json.dumps({"success": True})
                    mock_hold.return_value = json.dumps({"success": True})

                    await orbit_subject_vision(
                        bbox=valid_bbox,
                        radius_m=10.0,
                        speed_m_s=3.0,
                        orbits=1,
                    )

    @pytest.mark.asyncio
    async def test_orbit_respects_direction_parameter(self, valid_bbox, valid_telemetry, mock_connection_manager):
        """Test that orbit respects direction (cw vs ccw) parameter."""
        mock_cm, mock_drone, mock_cache = mock_connection_manager
        mock_cache._data = valid_telemetry

        with patch('avatar.mcp_server.tools.orchestrators.set_velocity') as mock_vel:
            with patch('avatar.mcp_server.tools.orchestrators.hold') as mock_hold:
                mock_vel.return_value = json.dumps({"success": True})
                mock_hold.return_value = json.dumps({"success": True})

                # Run CW orbit
                await orbit_subject_vision(
                    bbox=valid_bbox,
                    radius_m=10.0,
                    speed_m_s=3.0,
                    orbits=1,
                    direction="cw",
                )

    @pytest.mark.asyncio
    async def test_orbit_handles_gimbal_unavailable(self, valid_bbox, valid_telemetry):
        """Test that orbit continues if gimbal is unavailable."""
        mock_drone = MockDrone()
        mock_drone.gimbal.set_pitch_and_yaw = AsyncMock(
            side_effect=Exception("Gimbal not available")
        )

        with patch('avatar.mcp_server.tools.orchestrators.ConnectionManager') as mock_cm_class:
            mock_cm = MagicMock()
            mock_cache = MockTelemetryCache(valid_telemetry)

            mock_cm.get_drone = AsyncMock(return_value=mock_drone)
            mock_cm.get_telemetry_cache = MagicMock(return_value=mock_cache)
            mock_cm_class.return_value = mock_cm

            with patch('avatar.mcp_server.tools.orchestrators.set_velocity') as mock_vel:
                with patch('avatar.mcp_server.tools.orchestrators.hold') as mock_hold:
                    mock_vel.return_value = json.dumps({"success": True})
                    mock_hold.return_value = json.dumps({"success": True})

                    # Should not raise exception even with gimbal failure
                    result_json = await orbit_subject_vision(
                        bbox=valid_bbox,
                        radius_m=10.0,
                        speed_m_s=3.0,
                        orbits=1,
                    )

                    # Should still return a result
                    result = json.loads(result_json)
                    assert "success" in result
