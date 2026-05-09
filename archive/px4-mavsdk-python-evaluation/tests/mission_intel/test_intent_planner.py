"""Tests for mission_intel.intent_planner module."""

import pytest

from avatar.mission_intel.intent_planner import (
    parse_intent,
    plan_mission_from_intent,
    IntentType,
    MissionIntent,
    IntentParseResult,
)


class TestIntentParsing:
    """Tests for intent parsing - verifying 10+ core patterns."""

    def test_parse_orbit_intent(self):
        """Test parsing orbit intent."""
        intent = parse_intent("orbit the tower at 50 meters for 2 minutes")
        assert intent.intent_type == IntentType.ORBIT
        assert "tower" in intent.subject.lower()
        assert intent.altitude_m == 50.0
        assert intent.duration_s == 120.0  # 2 minutes

    def test_parse_orbit_altitude_only(self):
        """Test orbit with just altitude."""
        intent = parse_intent("orbit the building at 30m")
        assert intent.intent_type == IntentType.ORBIT
        assert intent.altitude_m == 30.0

    def test_parse_follow_intent(self):
        """Test parsing follow intent."""
        intent = parse_intent("follow the car for 5 minutes at 20 meters")
        assert intent.intent_type == IntentType.FOLLOW
        assert "car" in intent.subject.lower()
        assert intent.duration_s == 300.0  # 5 minutes
        assert intent.altitude_m == 20.0

    def test_parse_scan_intent(self):
        """Test parsing scan intent."""
        intent = parse_intent("scan the park at 50m with spiral pattern")
        assert intent.intent_type == IntentType.SCAN
        assert "park" in intent.subject.lower()
        assert intent.altitude_m == 50.0
        assert intent.pattern == "spiral"

    def test_parse_inspect_intent(self):
        """Test parsing inspect intent."""
        intent = parse_intent("inspect the bridge from 10 meters altitude 30m")
        assert intent.intent_type == IntentType.INSPECT
        assert "bridge" in intent.subject.lower()

    def test_parse_photograph_intent(self):
        """Test parsing photograph intent."""
        intent = parse_intent("photograph the monument from front angle at 40m")
        assert intent.intent_type == IntentType.PHOTOGRAPH
        assert "monument" in intent.subject.lower()
        assert intent.parameters.get("angle") == "front"

    def test_parse_fly_to_intent(self):
        """Test parsing fly-to intent."""
        intent = parse_intent("fly to the beach at 25 meters speed 10 m/s")
        assert intent.intent_type == IntentType.FLY_TO
        assert "beach" in intent.subject.lower()
        assert intent.altitude_m == 25.0
        assert intent.speed_m_s == 10.0

    def test_parse_survey_intent(self):
        """Test parsing survey intent."""
        intent = parse_intent("survey the field with grid pattern at 60m")
        assert intent.intent_type == IntentType.SURVEY
        assert "field" in intent.subject.lower()
        assert intent.pattern == "grid"
        assert intent.altitude_m == 60.0

    def test_parse_hover_intent(self):
        """Test parsing hover intent."""
        intent = parse_intent("hover at the intersection for 30 seconds at 15m")
        assert intent.intent_type == IntentType.HOVER
        assert intent.duration_s == 30.0
        assert intent.altitude_m == 15.0

    def test_parse_land_intent(self):
        """Test parsing land intent."""
        intent = parse_intent("land at the helipad")
        assert intent.intent_type == IntentType.LAND
        assert "helipad" in intent.subject.lower()

    def test_parse_rtl_intent(self):
        """Test parsing RTL intent."""
        intent = parse_intent("return to home")
        assert intent.intent_type == IntentType.RTL

    def test_parse_rtl_alternate(self):
        """Test parsing RTL intent with alternate phrasing."""
        intent = parse_intent("rtl")
        assert intent.intent_type == IntentType.RTL

    def test_parse_patrol_intent(self):
        """Test parsing patrol intent."""
        intent = parse_intent("patrol the perimeter at 40m for 10 minutes")
        assert intent.intent_type == IntentType.PATROL
        assert "perimeter" in intent.subject.lower()
        assert intent.altitude_m == 40.0
        assert intent.duration_s == 600.0  # 10 minutes

    def test_parse_search_intent(self):
        """Test parsing search intent."""
        intent = parse_intent("search for the lost hiker in the forest at 25m")
        assert intent.intent_type == IntentType.SEARCH
        assert "hiker" in intent.subject.lower()

    def test_parse_unknown_intent(self):
        """Test parsing unknown intent."""
        intent = parse_intent("do something weird with the drone")
        assert intent.intent_type == IntentType.UNKNOWN

    def test_case_insensitive(self):
        """Test that parsing is case insensitive."""
        intent = parse_intent("ORBIT THE TOWER AT 50M")
        assert intent.intent_type == IntentType.ORBIT

    def test_duration_seconds(self):
        """Test parsing duration in seconds."""
        intent = parse_intent("hover at the point for 45 sec")
        assert intent.duration_s == 45.0


class TestMissionPlanning:
    """Tests for mission planning from intent."""

    @pytest.mark.asyncio
    async def test_plan_rtl_mission(self):
        """Test planning RTL mission."""
        result = await plan_mission_from_intent(
            "return to home",
            geocode=False,
        )
        assert result.success
        assert result.intent.intent_type == IntentType.RTL

    @pytest.mark.asyncio
    async def test_plan_hover_mission(self):
        """Test planning hover mission."""
        result = await plan_mission_from_intent(
            "hover for 60 seconds at 30m",
            geocode=False,
        )
        assert result.success
        assert any(b.kind == "hover" for b in result.mission.behaviors)

    @pytest.mark.asyncio
    async def test_plan_orbit_mission_no_geocode(self):
        """Test planning orbit mission without geocoding."""
        result = await plan_mission_from_intent(
            "orbit the tower at 50m for 2 minutes",
            geocode=False,
        )
        # Without geocoding, we can't find the tower, so it should warn
        assert len(result.warnings) > 0 or not result.success

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_error(self):
        """Test that unknown intent returns error."""
        result = await plan_mission_from_intent(
            "do something impossible",
            geocode=False,
        )
        assert not result.success
        assert len(result.errors) > 0


class TestIntentTypes:
    """Tests for IntentType enum."""

    def test_all_intent_types_exist(self):
        """Test that all expected intent types exist."""
        expected = [
            IntentType.ORBIT,
            IntentType.FOLLOW,
            IntentType.SCAN,
            IntentType.INSPECT,
            IntentType.PHOTOGRAPH,
            IntentType.FLY_TO,
            IntentType.SURVEY,
            IntentType.HOVER,
            IntentType.LAND,
            IntentType.RTL,
            IntentType.PATROL,
            IntentType.SEARCH,
            IntentType.UNKNOWN,
        ]
        for it in expected:
            assert isinstance(it.value, str)


class TestMissionIntent:
    """Tests for MissionIntent dataclass."""

    def test_default_values(self):
        """Test default values."""
        intent = MissionIntent(intent_type=IntentType.HOVER)
        assert intent.subject is None
        assert intent.altitude_m is None
        assert intent.duration_s is None

    def test_with_all_values(self):
        """Test with all values set."""
        intent = MissionIntent(
            intent_type=IntentType.ORBIT,
            subject="tower",
            altitude_m=50.0,
            duration_s=120.0,
            distance_m=100.0,
            pattern="circle",
            speed_m_s=5.0,
            parameters={"custom": "value"},
            raw_text="orbit the tower at 50m",
        )
        assert intent.subject == "tower"
        assert intent.altitude_m == 50.0
        assert intent.duration_s == 120.0


class TestIntentParseResult:
    """Tests for IntentParseResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = IntentParseResult(
            success=True,
            intent=MissionIntent(intent_type=IntentType.RTL),
        )
        assert result.success
        assert result.errors == []

    def test_failure_result(self):
        """Test failure result."""
        result = IntentParseResult(
            success=False,
            errors=["Could not understand intent"],
        )
        assert not result.success
        assert len(result.errors) == 1
