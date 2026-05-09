"""Mission Intelligence Layer for Project Avatar.

This package provides offline-first mapping, elevation, and mission planning
capabilities for autonomous drone operations.

Architecture:
    - providers/: External data providers (OSM, SRTM, Google Maps)
    - geo.py: Geographic primitives and utilities
    - terrain.py: Terrain analysis (AGL, slope, line-of-sight)
    - area_analyzer.py: Area analysis and reporting
    - scenic_sweep.py: Scenic sweep mission planning
    - intent_planner.py: Natural language mission planning
    - mission_spec.py: Mission specification schema
    - safety_checks.py: Pre-flight safety validation
    - config.py: Configuration and API key management

Offline-First Design:
    - OSM/SRTM data cached locally, works without internet
    - Google Maps optional, gracefully degrades when unavailable
    - DEM tiles stored at ~/.cache/avatar/dem/
    - GMaps cache at ~/.cache/avatar/gmaps/

Usage:
    from avatar.mission_intel import analyze_area, get_elevation
    from avatar.mission_intel.providers import OSMProvider, SRTMProvider

    # Analyze an area (offline-capable)
    report = await analyze_area(center_lat=37.7749, center_lon=-122.4194, radius_m=500)

    # Get elevation for a point (SRTM offline)
    elevation = await get_elevation(lat=37.7749, lon=-122.4194)
"""

from avatar.mission_intel.geo import (
    Point,
    BBox,
    Polygon,
    haversine_distance,
    haversine_bearing,
    destination_point,
    generate_circle_grid,
    generate_spiral_grid,
)
from avatar.mission_intel.terrain import (
    TerrainAnalyzer,
    TerrainResult,
    calculate_agl,
    calculate_slope,
    calculate_line_of_sight,
)
from avatar.mission_intel.area_analyzer import (
    analyze_area,
    AreaReport,
    ObstacleInfo,
    LandUseInfo,
    AirspaceInfo,
)
from avatar.mission_intel.scenic_sweep import (
    plan_scenic_sweep,
    ScenicSweepPlan,
    SweepWaypoint,
)
from avatar.mission_intel.intent_planner import (
    plan_mission_from_intent,
    IntentParseResult,
    MissionIntent,
)
from avatar.mission_intel.mission_spec import (
    MissionSpec,
    WaypointSpec,
    BehaviorSpec,
    SafetyPolicySpec,
)
from avatar.mission_intel.safety_checks import (
    SafetyCheckResult,
    check_geofence_overlap,
    check_min_agl,
    check_battery_feasibility,
    run_safety_checks,
)
from avatar.mission_intel.config import MissionIntelConfig, get_config

__all__ = [
    # Geo primitives
    "Point",
    "BBox",
    "Polygon",
    "haversine_distance",
    "haversine_bearing",
    "destination_point",
    "generate_circle_grid",
    "generate_spiral_grid",
    # Terrain analysis
    "TerrainAnalyzer",
    "TerrainResult",
    "calculate_agl",
    "calculate_slope",
    "calculate_line_of_sight",
    # Area analysis
    "analyze_area",
    "AreaReport",
    "ObstacleInfo",
    "LandUseInfo",
    "AirspaceInfo",
    # Scenic sweep planning
    "plan_scenic_sweep",
    "ScenicSweepPlan",
    "SweepWaypoint",
    # Intent planning
    "plan_mission_from_intent",
    "IntentParseResult",
    "MissionIntent",
    # Mission specification
    "MissionSpec",
    "WaypointSpec",
    "BehaviorSpec",
    "SafetyPolicySpec",
    # Safety checks
    "SafetyCheckResult",
    "check_geofence_overlap",
    "check_min_agl",
    "check_battery_feasibility",
    "run_safety_checks",
    # Configuration
    "MissionIntelConfig",
    "get_config",
]
