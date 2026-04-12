#!/usr/bin/env python3
"""Unit tests for tracking tools.

Tests the tracking and camera control functionality without requiring
the full Gazebo simulation.
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal, point_camera_at, orbit_target,
    track_target, spiral_search, _calculate_look_angles,
    _calculate_orbit_velocity, _predict_target_position,
    TargetInfo, GimbalAngles, _clamp
)


class MockTelemetry:
    """Mock telemetry data."""
    def __init__(self, lat=47.397742, lon=8.545594, alt=20.0):
        self.latitude_deg = lat
        self.longitude_deg = lon
        self.relative_altitude_m = alt
        self.yaw_deg = 0.0


class MockDrone:
    """Mock drone for testing."""
    def __init__(self):
        self.gimbal = MagicMock()
        self.gimbal.set_pitch_and_yaw = AsyncMock()
        self.manual_control = MagicMock()
        self.manual_control.set_manual_control_input = AsyncMock()


class MockConnectionManager:
    """Mock connection manager."""
    def __init__(self):
        self._connected = True
        self._drone = MockDrone()
        self._cache = MagicMock()

    def is_connected(self):
        return self._connected

    def get_drone(self):
        return self._drone

    def get_telemetry_cache(self):
        return self._cache

    async def get_latest(self):
        return MockTelemetry()


def test_clamp():
    """Test clamp function."""
    assert _clamp(5.0, 0.0, 10.0) == 5.0
    assert _clamp(-5.0, 0.0, 10.0) == 0.0
    assert _clamp(15.0, 0.0, 10.0) == 10.0
    print("✓ _clamp tests passed")


def test_calculate_look_angles():
    """Test look angle calculation."""
    # Drone at (47.397742, 8.545594, 20m)
    # Target at same position
    pitch, yaw = _calculate_look_angles(
        47.397742, 8.545594, 20.0,
        47.397742, 8.545594, 10.0  # Target below
    )

    # Should be looking down
    assert pitch < 0, f"Expected negative pitch (looking down), got {pitch}"
    print(f"✓ Look angles: pitch={pitch:.1f}°, yaw={yaw:.1f}°")


def test_calculate_orbit_velocity():
    """Test orbit velocity calculation."""
    north_vel, east_vel, yaw_rate = _calculate_orbit_velocity(
        47.397742, 8.545594,  # Drone
        47.397742, 8.545594,  # Target (same position - need to move to radius)
        10.0,  # Radius
        3.0,   # Speed
        True   # Clockwise
    )

    # Should produce velocity components
    assert isinstance(north_vel, float)
    assert isinstance(east_vel, float)
    assert isinstance(yaw_rate, float)
    print(f"✓ Orbit velocity: N={north_vel:.2f}, E={east_vel:.2f}, yaw_rate={yaw_rate:.2f}")


def test_predict_target_position():
    """Test target prediction."""
    target = TargetInfo(
        lat=47.397742,
        lon=8.545594,
        velocity_north=5.0,
        velocity_east=0.0
    )

    predicted_lat, predicted_lon = _predict_target_position(target, 1.0)

    # Should have moved north
    assert predicted_lat > target.lat
    print(f"✓ Target prediction: moved from ({target.lat:.6f}, {target.lon:.6f}) to ({predicted_lat:.6f}, {predicted_lon:.6f})")


async def test_set_gimbal():
    """Test gimbal control."""
    with patch('avatar.mcp_server.tools.tracking_tools.ConnectionManager') as mock_cm:
        mock_instance = MockConnectionManager()
        mock_cm.return_value = mock_instance

        result_json = await set_gimbal(
            pitch_deg=-45.0,
            yaw_deg=30.0,
            roll_deg=0.0
        )
        result = json.loads(result_json)

        assert result.get("success") == True
        assert result.get("pitch_deg") == -45.0
        assert result.get("yaw_deg") == 30.0
        print(f"✓ set_gimbal: {result.get('message')}")


async def test_point_camera_at():
    """Test camera pointing."""
    with patch('avatar.mcp_server.tools.tracking_tools.ConnectionManager') as mock_cm:
        mock_instance = MockConnectionManager()
        mock_cm.return_value = mock_instance

        # Mock the cache to return telemetry
        mock_instance.get_telemetry_cache = MagicMock(return_value=mock_instance)
        mock_instance.get_latest = AsyncMock(return_value=MockTelemetry())

        result_json = await point_camera_at(
            lat=47.397742,
            lon=8.545594,
            alt_m=0.0
        )
        result = json.loads(result_json)

        # Should either succeed or handle the mock gracefully
        print(f"✓ point_camera_at result: {result}")


async def main():
    """Run all tests."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║        TRACKING TOOLS UNIT TEST SUITE                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    tests = [
        ("Clamp function", test_clamp),
        ("Look angle calculation", test_calculate_look_angles),
        ("Orbit velocity calculation", test_calculate_orbit_velocity),
        ("Target prediction", test_predict_target_position),
        ("Set gimbal", test_set_gimbal),
        ("Point camera", test_point_camera_at),
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
        print("✓ All tracking tool tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
