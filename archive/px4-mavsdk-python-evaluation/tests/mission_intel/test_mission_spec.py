"""Tests for mission_intel.mission_spec module."""

import pytest
from pydantic import ValidationError

from avatar.mission_intel.mission_spec import (
    WaypointSpec,
    SafetyPolicySpec,
    BehaviorSpec,
    MissionConstraintsSpec,
    MissionSpec,
)
from avatar.mcp_server.schemas import Point


class TestWaypointSpec:
    """Tests for WaypointSpec."""

    def test_create_waypoint(self):
        """Test creating a waypoint."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=100.0)
        wp = WaypointSpec(index=0, point=point)
        assert wp.index == 0
        assert wp.point.lat_deg == 37.7749
        assert wp.hold_s == 0.0

    def test_waypoint_with_speed(self):
        """Test waypoint with speed."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=100.0)
        wp = WaypointSpec(index=0, point=point, speed_m_s=10.0)
        assert wp.speed_m_s == 10.0

    def test_invalid_hold_time(self):
        """Test that negative hold time is invalid."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=100.0)
        with pytest.raises(ValidationError):
            WaypointSpec(index=0, point=point, hold_s=-1.0)


class TestSafetyPolicySpec:
    """Tests for SafetyPolicySpec."""

    def test_default_safety_policy(self):
        """Test default safety policy."""
        policy = SafetyPolicySpec()
        assert policy.rtl_on_low_battery is True
        assert policy.min_battery_percent == 25.0

    def test_custom_safety_policy(self):
        """Test custom safety policy."""
        policy = SafetyPolicySpec(
            rtl_on_low_battery=False,
            min_battery_percent=30.0,
        )
        assert policy.rtl_on_low_battery is False
        assert policy.min_battery_percent == 30.0


class TestBehaviorSpec:
    """Tests for BehaviorSpec."""

    def test_hover_behavior(self):
        """Test hover behavior."""
        behavior = BehaviorSpec(kind="hover", duration_s=60.0)
        assert behavior.kind == "hover"
        assert behavior.duration_s == 60.0

    def test_orbit_behavior(self):
        """Test orbit behavior."""
        target = Point(lat_deg=37.7749, lon_deg=-122.4194)
        behavior = BehaviorSpec(
            kind="orbit",
            target=target,
            radius_m=50.0,
            duration_s=120.0,
        )
        assert behavior.kind == "orbit"
        assert behavior.radius_m == 50.0

    def test_follow_behavior(self):
        """Test follow behavior."""
        behavior = BehaviorSpec(
            kind="follow",
            subject="car",
            duration_s=300.0,
        )
        assert behavior.subject == "car"


class TestMissionConstraintsSpec:
    """Tests for MissionConstraintsSpec."""

    def test_default_constraints(self):
        """Test default constraints."""
        constraints = MissionConstraintsSpec()
        assert constraints.max_altitude_amsl_m == 120.0
        assert constraints.max_speed_m_s == 15.0


class TestMissionSpec:
    """Tests for MissionSpec."""

    def test_create_mission(self):
        """Test creating a mission."""
        mission = MissionSpec(name="Test Mission")
        assert mission.name == "Test Mission"
        assert mission.version == "1.0"
        assert len(mission.waypoints) == 0

    def test_mission_with_home(self):
        """Test mission with home position."""
        home = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=0.0)
        mission = MissionSpec(name="Test Mission", home=home)
        assert mission.home.lat_deg == 37.7749

    def test_mission_with_waypoints(self):
        """Test mission with waypoints."""
        home = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=0.0)
        wp1 = WaypointSpec(
            index=0,
            point=Point(lat_deg=37.7759, lon_deg=-122.4184, alt_m=50.0),
        )
        wp2 = WaypointSpec(
            index=1,
            point=Point(lat_deg=37.7769, lon_deg=-122.4174, alt_m=50.0),
        )

        mission = MissionSpec(
            name="Test Mission",
            home=home,
            waypoints=[wp1, wp2],
        )
        assert len(mission.waypoints) == 2
        assert mission.total_waypoints == 2

    def test_waypoint_indices_must_be_sequential(self):
        """Test that waypoint indices must be sequential."""
        home = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=0.0)
        wp1 = WaypointSpec(
            index=0,
            point=Point(lat_deg=37.7759, lon_deg=-122.4184, alt_m=50.0),
        )
        wp2 = WaypointSpec(
            index=2,  # Wrong index!
            point=Point(lat_deg=37.7769, lon_deg=-122.4174, alt_m=50.0),
        )

        with pytest.raises(ValidationError):
            MissionSpec(name="Test Mission", home=home, waypoints=[wp1, wp2])

    def test_mission_with_behaviors(self):
        """Test mission with behaviors."""
        behavior = BehaviorSpec(kind="hover", duration_s=60.0)
        mission = MissionSpec(
            name="Test Mission",
            behaviors=[behavior],
        )
        assert len(mission.behaviors) == 1
        assert mission.total_behaviors == 1

    def test_mission_to_mission_conversion(self):
        """Test converting MissionSpec to base Mission."""
        home = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=0.0)
        wp1 = WaypointSpec(
            index=0,
            point=Point(lat_deg=37.7759, lon_deg=-122.4184, alt_m=50.0),
        )

        mission = MissionSpec(
            name="Test Mission",
            home=home,
            waypoints=[wp1],
        )

        # Convert to base Mission
        base_mission = mission.to_mission()
        assert base_mission.name == "Test Mission"
        assert len(base_mission.waypoints) == 1
