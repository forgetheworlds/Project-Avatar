"""Natural language mission intent parser and planner.

Parses natural language mission descriptions into structured mission plans.
Supports 10+ core intent patterns.

Supported Intent Patterns:
1. "orbit [subject] at [altitude]m"
2. "follow [subject] for [duration]"
3. "scan [area] at [altitude]m"
4. "inspect [object] from [distance]m"
5. "photograph [subject] from [angle]"
6. "fly to [location] at [altitude]m"
7. "survey [area] with [pattern] pattern"
8. "hover at [location] for [duration]"
9. "land at [location]"
10. "return to home"
11. "patrol [path] at [altitude]m"
12. "search for [object] in [area]"

Usage:
    from avatar.mission_intel.intent_planner import plan_mission_from_intent

    result = await plan_mission_from_intent(
        "orbit the tower at 50 meters for 2 minutes"
    )
    if result.success:
        mission = result.mission
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from avatar.mission_intel.geo import Point
from avatar.mission_intel.mission_spec import (
    BehaviorSpec,
    MissionSpec,
    SafetyPolicySpec,
    WaypointSpec,
)
from avatar.mission_intel.providers.osm import OSMProvider

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Classification of mission intent types."""

    ORBIT = "orbit"
    FOLLOW = "follow"
    SCAN = "scan"
    INSPECT = "inspect"
    PHOTOGRAPH = "photograph"
    FLY_TO = "fly_to"
    SURVEY = "survey"
    HOVER = "hover"
    LAND = "land"
    RTL = "rtl"
    PATROL = "patrol"
    SEARCH = "search"
    UNKNOWN = "unknown"


@dataclass
class MissionIntent:
    """Parsed mission intent structure.

    Attributes:
        intent_type: Classified intent type.
        subject: Subject of the mission (place, object, etc.).
        location: Geographic location (if specified).
        altitude_m: Altitude in meters.
        duration_s: Duration in seconds.
        distance_m: Distance in meters.
        pattern: Flight pattern (for survey/scan).
        speed_m_s: Flight speed.
        parameters: Additional parameters extracted.
        raw_text: Original input text.
    """

    intent_type: IntentType
    subject: Optional[str] = None
    location: Optional[Point] = None
    altitude_m: Optional[float] = None
    duration_s: Optional[float] = None
    distance_m: Optional[float] = None
    pattern: Optional[str] = None
    speed_m_s: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class IntentParseResult:
    """Result of intent parsing.

    Attributes:
        success: True if parsing succeeded.
        mission: Generated mission spec if successful.
        intent: Parsed intent structure.
        errors: List of parsing errors.
        warnings: List of warnings.
        suggestions: Suggested alternatives for ambiguous inputs.
    """

    success: bool
    mission: Optional[MissionSpec] = None
    intent: Optional[MissionIntent] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# Intent patterns with regex
INTENT_PATTERNS: List[Tuple[IntentType, str, re.Pattern]] = [
    # Pattern: (type, description, compiled_regex)
    (
        IntentType.ORBIT,
        "orbit subject at altitude",
        re.compile(
            r"(?:orbit|circle)\s+(?:the\s+)?(.+?)\s+(?:at|from)?\s*(\d+(?:\.\d+)?)\s*"
            r"(?:m|meters?|ft|feet)?(?:\s+(?:for|duration)\s+(\d+(?:\.\d+)?)\s*"
            r"(?:s|sec|seconds?|min|minutes?)?)?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.FOLLOW,
        "follow subject for duration",
        re.compile(
            r"(?:follow|track)\s+(?:the\s+)?(.+?)(?:\s+for\s+(\d+(?:\.\d+)?)\s*"
            r"(?:s|sec|seconds?|min|minutes?))?(?:\s+at\s+(\d+(?:\.\d+)?)\s*"
            r"(?:m|meters?))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.SCAN,
        "scan area at altitude",
        re.compile(
            r"(?:scan|sweep)\s+(?:the\s+)?(.+?)(?:\s+area)?(?:\s+at\s+(\d+(?:\.\d+)?)\s*"
            r"(?:m|meters?))?(?:\s+(?:using|with)\s+(\w+)\s+pattern)?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.INSPECT,
        "inspect object from distance",
        re.compile(
            r"(?:inspect|examine|check)\s+(?:the\s+)?(.+?)(?:\s+(?:from|at)\s+"
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?)?)?(?:\s+altitude\s+(\d+(?:\.\d+)?)\s*"
            r"(?:m|meters?)?)?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.PHOTOGRAPH,
        "photograph subject from angle",
        re.compile(
            r"(?:photograph|photo|capture|shoot)\s+(?:the\s+)?(.+?)(?:\s+from\s+"
            r"(\w+)\s+angle)?(?:\s+at\s+(\d+(?:\.\d+)?)\s*(?:m|meters?))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.FLY_TO,
        "fly to location at altitude",
        re.compile(
            r"(?:fly|go|travel|navigate)\s+(?:to\s+)?(?:the\s+)?(.+?)(?:\s+at\s+"
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?))?(?:\s+(?:speed|velocity)\s+"
            r"(\d+(?:\.\d+)?)\s*(?:m/s|mps))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.SURVEY,
        "survey area with pattern",
        re.compile(
            r"(?:survey|map)\s+(?:the\s+)?(.+?)(?:\s+area)?(?:\s+(?:using|with)\s+"
            r"(\w+)\s+pattern)?(?:\s+at\s+(\d+(?:\.\d+)?)\s*(?:m|meters?))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.HOVER,
        "hover at location for duration",
        re.compile(
            r"(?:hover|hold)\s+(?:at|over|above)?\s*(?:the\s+)?(.+?)(?:\s+for\s+"
            r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?|min|minutes?))?(?:\s+at\s+"
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.LAND,
        "land at location",
        re.compile(
            r"(?:land|touchdown)\s+(?:at|on)?\s*(?:the\s+)?(.+?)",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.RTL,
        "return to home/launch",
        re.compile(
            r"(?:return\s+to\s+(?:home|launch|base)|rtl|go\s+home|come\s+back)",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.PATROL,
        "patrol path at altitude",
        re.compile(
            r"(?:patrol|guard|watch)\s+(?:the\s+)?(.+?)(?:\s+area)?(?:\s+at\s+"
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?))?(?:\s+for\s+(\d+(?:\.\d+)?)\s*"
            r"(?:min|minutes?))?",
            re.IGNORECASE,
        ),
    ),
    (
        IntentType.SEARCH,
        "search for object in area",
        re.compile(
            r"(?:search|look\s+(?:for|for\s+the))\s+(?:for\s+)?(?:the\s+)?(.+?)(?:\s+in\s+"
            r"(?:the\s+)?(.+?))?(?:\s+area)?(?:\s+at\s+(\d+(?:\.\d+)?)\s*(?:m|meters?))?",
            re.IGNORECASE,
        ),
    ),
]

# Duration multipliers
DURATION_MULTIPLIERS: Dict[str, float] = {
    "s": 1.0,
    "sec": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "min": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
}


def parse_intent(text: str) -> MissionIntent:
    """Parse natural language text into mission intent.

    Args:
        text: Natural language mission description.

    Returns:
        Parsed MissionIntent structure.
    """
    text = text.strip()

    # Try each pattern
    for intent_type, description, pattern in INTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()

            intent = MissionIntent(
                intent_type=intent_type,
                raw_text=text,
            )

            # Extract common parameters based on pattern
            if intent_type == IntentType.ORBIT:
                intent.subject = groups[0]
                if groups[1]:
                    intent.altitude_m = float(groups[1])
                if groups[2]:
                    intent.duration_s = _parse_duration(groups[2], groups[2] + "s" if groups[2] else None)

            elif intent_type == IntentType.FOLLOW:
                intent.subject = groups[0]
                if groups[1]:
                    intent.duration_s = _parse_duration(groups[1])
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            elif intent_type == IntentType.SCAN:
                intent.subject = groups[0]
                if groups[1]:
                    intent.altitude_m = float(groups[1])
                if groups[2]:
                    intent.pattern = groups[2].lower()

            elif intent_type == IntentType.INSPECT:
                intent.subject = groups[0]
                if groups[1]:
                    intent.distance_m = float(groups[1])
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            elif intent_type == IntentType.PHOTOGRAPH:
                intent.subject = groups[0]
                if groups[1]:
                    intent.parameters["angle"] = groups[1].lower()
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            elif intent_type == IntentType.FLY_TO:
                intent.subject = groups[0]
                if groups[1]:
                    intent.altitude_m = float(groups[1])
                if groups[2]:
                    intent.speed_m_s = float(groups[2])

            elif intent_type == IntentType.SURVEY:
                intent.subject = groups[0]
                if groups[1]:
                    intent.pattern = groups[1].lower()
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            elif intent_type == IntentType.HOVER:
                intent.subject = groups[0]
                if groups[1]:
                    intent.duration_s = _parse_duration(groups[1])
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            elif intent_type == IntentType.LAND:
                intent.subject = groups[0]

            elif intent_type == IntentType.RTL:
                pass  # No additional parameters

            elif intent_type == IntentType.PATROL:
                intent.subject = groups[0]
                if groups[1]:
                    intent.altitude_m = float(groups[1])
                if groups[2]:
                    intent.duration_s = float(groups[2]) * 60  # Minutes to seconds

            elif intent_type == IntentType.SEARCH:
                intent.subject = groups[0]
                if groups[1]:
                    intent.parameters["area"] = groups[1]
                if groups[2]:
                    intent.altitude_m = float(groups[2])

            return intent

    # No pattern matched
    return MissionIntent(
        intent_type=IntentType.UNKNOWN,
        raw_text=text,
    )


def _parse_duration(value: str, unit: Optional[str] = None) -> float:
    """Parse duration string to seconds.

    Args:
        value: Numeric value.
        unit: Unit string (s, min, etc.).

    Returns:
        Duration in seconds.
    """
    try:
        num = float(value)

        if unit:
            for u, mult in DURATION_MULTIPLIERS.items():
                if unit.lower().startswith(u):
                    return num * mult

        # Default to seconds if no unit
        return num
    except ValueError:
        return 0.0


async def plan_mission_from_intent(
    text: str,
    home: Optional[Point] = None,
    geocode: bool = True,
) -> IntentParseResult:
    """Plan a mission from natural language intent.

    Parses the intent and generates a complete MissionSpec.

    Args:
        text: Natural language mission description.
        home: Home position (required for RTL and relative positions).
        geocode: Whether to geocode location names.

    Returns:
        IntentParseResult with success status and generated mission.
    """
    intent = parse_intent(text)

    if intent.intent_type == IntentType.UNKNOWN:
        return IntentParseResult(
            success=False,
            intent=intent,
            errors=["Could not understand mission intent. Try phrases like: "
                    "'orbit the tower at 50m', 'fly to the park', 'scan the area'"],
        )

    # Create mission spec based on intent type
    mission = MissionSpec(
        name=f"{intent.intent_type.value.capitalize()} Mission",
        version="1.0",
    )

    if home:
        mission.home = home

    # Set default safety policy
    mission.safety = SafetyPolicySpec(
        rtl_on_low_battery=True,
        min_battery_percent=25.0,
    )

    # Generate mission based on intent
    errors: List[str] = []
    warnings: List[str] = []

    try:
        if intent.intent_type == IntentType.ORBIT:
            await _build_orbit_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.FOLLOW:
            await _build_follow_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.SCAN:
            await _build_scan_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.INSPECT:
            await _build_inspect_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.PHOTOGRAPH:
            await _build_photograph_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.FLY_TO:
            await _build_flyto_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.SURVEY:
            await _build_survey_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.HOVER:
            await _build_hover_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.LAND:
            await _build_land_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.RTL:
            _build_rtl_mission(mission, intent, warnings)

        elif intent.intent_type == IntentType.PATROL:
            await _build_patrol_mission(mission, intent, geocode, errors, warnings)

        elif intent.intent_type == IntentType.SEARCH:
            await _build_search_mission(mission, intent, geocode, errors, warnings)

    except Exception as e:
        logger.exception("Failed to build mission from intent")
        errors.append(f"Mission generation error: {str(e)}")

    if errors:
        return IntentParseResult(
            success=False,
            mission=mission,
            intent=intent,
            errors=errors,
            warnings=warnings,
        )

    return IntentParseResult(
        success=True,
        mission=mission,
        intent=intent,
        warnings=warnings,
    )


async def _geocode_subject(subject: str) -> Optional[Point]:
    """Geocode a subject/location name.

    Args:
        subject: Location name.

    Returns:
        Point if found, None otherwise.
    """
    osm = OSMProvider()
    results = await osm.search_places(subject, limit=1)
    if results:
        return results[0].location
    return None


async def _build_orbit_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build an orbit mission."""
    if not intent.subject:
        errors.append("Orbit mission requires a subject to orbit around")
        return

    # Geocode subject
    target = None
    if geocode:
        target = await _geocode_subject(intent.subject)

    if not target:
        warnings.append(f"Could not locate '{intent.subject}' - please specify coordinates")
        return

    # Set home to target area if not set
    if not mission.home:
        mission.home = Point(lat_deg=target.lat_deg, lon_deg=target.lon_deg, alt_m=0.0)

    altitude = intent.altitude_m or 30.0
    duration = intent.duration_s or 60.0

    mission.behaviors.append(
        BehaviorSpec(
            kind="orbit",
            target=target,
            radius_m=50.0,
            speed_m_s=3.0,
            duration_s=duration,
            altitude_m=altitude,
        )
    )


async def _build_follow_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a follow mission."""
    if not intent.subject:
        errors.append("Follow mission requires a subject to follow")
        return

    mission.behaviors.append(
        BehaviorSpec(
            kind="follow",
            subject=intent.subject,
            duration_s=intent.duration_s or 120.0,
            altitude_m=intent.altitude_m or 20.0,
        )
    )
    warnings.append("Follow mission requires real-time target detection")


async def _build_scan_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a scan mission."""
    altitude = intent.altitude_m or 30.0
    pattern = intent.pattern or "spiral"

    mission.behaviors.append(
        BehaviorSpec(
            kind="scan",
            pattern=pattern,
            altitude_m=altitude,
            duration_s=300.0,
        )
    )


async def _build_inspect_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build an inspect mission."""
    if not intent.subject:
        errors.append("Inspect mission requires an object to inspect")
        return

    mission.behaviors.append(
        BehaviorSpec(
            kind="inspect",
            subject=intent.subject,
            distance_m=intent.distance_m or 10.0,
            altitude_m=intent.altitude_m or 20.0,
        )
    )


async def _build_photograph_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a photograph mission."""
    if not intent.subject:
        errors.append("Photograph mission requires a subject")
        return

    angle = intent.parameters.get("angle", "front")
    altitude = intent.altitude_m or 30.0

    mission.behaviors.append(
        BehaviorSpec(
            kind="photograph",
            subject=intent.subject,
            angle=angle,
            altitude_m=altitude,
        )
    )


async def _build_flyto_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a fly-to mission."""
    if not intent.subject:
        errors.append("Fly-to mission requires a destination")
        return

    destination = None
    if geocode:
        destination = await _geocode_subject(intent.subject)

    if not destination:
        warnings.append(f"Could not locate '{intent.subject}' - please specify coordinates")
        return

    altitude = intent.altitude_m or 30.0

    mission.waypoints.append(
        WaypointSpec(
            index=0,
            point=Point(
                lat_deg=destination.lat_deg,
                lon_deg=destination.lon_deg,
                alt_m=altitude,
            ),
            speed_m_s=intent.speed_m_s or 5.0,
        )
    )


async def _build_survey_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a survey mission."""
    pattern = intent.pattern or "grid"
    altitude = intent.altitude_m or 50.0

    mission.behaviors.append(
        BehaviorSpec(
            kind="survey",
            pattern=pattern,
            altitude_m=altitude,
            overlap_percent=30.0,
        )
    )


async def _build_hover_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a hover mission."""
    location = None
    if intent.subject and geocode:
        location = await _geocode_subject(intent.subject)

    duration = intent.duration_s or 60.0
    altitude = intent.altitude_m or 30.0

    mission.behaviors.append(
        BehaviorSpec(
            kind="hover",
            duration_s=duration,
            altitude_m=altitude,
            location=location,
        )
    )


async def _build_land_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a land mission."""
    mission.behaviors.append(
        BehaviorSpec(
            kind="land",
            location=intent.subject,
        )
    )


def _build_rtl_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    warnings: List[str],
) -> None:
    """Build an RTL mission."""
    mission.behaviors.append(
        BehaviorSpec(
            kind="rtl",
        )
    )
    if not mission.home:
        warnings.append("RTL requires home position to be set")


async def _build_patrol_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a patrol mission."""
    altitude = intent.altitude_m or 40.0
    duration = intent.duration_s or 300.0

    mission.behaviors.append(
        BehaviorSpec(
            kind="patrol",
            subject=intent.subject,
            altitude_m=altitude,
            duration_s=duration,
        )
    )


async def _build_search_mission(
    mission: MissionSpec,
    intent: MissionIntent,
    geocode: bool,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Build a search mission."""
    altitude = intent.altitude_m or 30.0
    area = intent.parameters.get("area", intent.subject)

    mission.behaviors.append(
        BehaviorSpec(
            kind="search",
            subject=intent.subject,
            area=area,
            altitude_m=altitude,
            pattern="spiral",
        )
    )


__all__ = [
    "plan_mission_from_intent",
    "parse_intent",
    "IntentType",
    "MissionIntent",
    "IntentParseResult",
]
