"""Mission Intelligence MCP Tools.

Exposes mission planning and analysis capabilities through MCP tools.
All tools are read-only and work offline when data is cached.

Available Tools:
- analyze_area: Comprehensive area analysis
- lookup_place: Look up a place by name or ID
- get_elevation: Get elevation for coordinates
- get_agl: Calculate Above Ground Level altitude
- plan_scenic_sweep: Generate scenic sweep flight plan
- plan_mission_from_intent: Plan mission from natural language
- propose_orbit_for_subject: Generate orbit plan for a subject

Usage:
    from avatar.mcp_server.tools.mission_intel_tools import (
        analyze_area_tool,
        get_elevation_tool,
        plan_mission_from_intent_tool,
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from avatar.mission_intel import (
    analyze_area as _analyze_area,
    plan_scenic_sweep as _plan_scenic_sweep,
    plan_mission_from_intent as _plan_mission_from_intent,
)
from avatar.mission_intel.geo import Point
from avatar.mission_intel.terrain import calculate_agl, TerrainAnalyzer
from avatar.mission_intel.providers.elevation import CompositeElevationProvider
from avatar.mission_intel.providers.osm import OSMProvider
from avatar.mission_intel.providers.gmaps import GoogleMapsProvider
from avatar.mission_intel.config import get_config
from avatar.mcp_server.tool_meta import ToolMeta

logger = logging.getLogger(__name__)


# ==============================================================================
# Tool: analyze_area
# ==============================================================================

ANALYZE_AREA_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,  # Accesses external APIs (OSM)
}


def analyze_area_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for analyze_area tool."""
    return {
        "type": "object",
        "properties": {
            "center_lat": {
                "type": "number",
                "description": "Center latitude in degrees (-90 to 90)",
            },
            "center_lon": {
                "type": "number",
                "description": "Center longitude in degrees (-180 to 180)",
            },
            "radius_m": {
                "type": "number",
                "description": "Analysis radius in meters",
                "default": 500,
                "minimum": 50,
                "maximum": 5000,
            },
            "include_places": {
                "type": "boolean",
                "description": "Include points of interest in analysis",
                "default": True,
            },
        },
        "required": ["center_lat", "center_lon"],
    }


def analyze_area_output_schema() -> Dict[str, Any]:
    """Return output schema for analyze_area tool."""
    return {
        "type": "object",
        "properties": {
            "isError": {"type": "boolean"},
            "error": {"type": "object"},
            "center": {"type": "object"},
            "radius_m": {"type": "number"},
            "ground_elevation_m": {"type": "number"},
            "terrain": {"type": "object"},
            "obstacles": {"type": "array"},
            "land_use": {"type": "array"},
            "airspace": {"type": "object"},
            "suitability": {"type": "number"},
            "warnings": {"type": "array"},
        },
    }


ANALYZE_AREA_TOOL = ToolMeta(
    name="analyze_area",
    description=(
        "Analyze an area for drone flight planning. "
        "Returns terrain, obstacles, land use, and airspace information. "
        "Works offline when OSM/SRTM data is cached. "
        "Use to assess flight suitability before mission planning."
    ),
    input_schema=analyze_area_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    open_world_hint=True,
)


async def analyze_area(
    center_lat: float,
    center_lon: float,
    radius_m: float = 500.0,
    include_places: bool = True,
) -> str:
    """Analyze an area for drone flight planning.

    Args:
        center_lat: Center latitude in degrees.
        center_lon: Center longitude in degrees.
        radius_m: Analysis radius in meters.
        include_places: Include points of interest.

    Returns:
        JSON string with analysis results.
    """
    try:
        report = await _analyze_area(
            center_lat=center_lat,
            center_lon=center_lon,
            radius_m=radius_m,
            include_places=include_places,
        )

        result = {
            "success": True,
            "center": {
                "lat_deg": report.center.lat_deg,
                "lon_deg": report.center.lon_deg,
            },
            "radius_m": report.radius_m,
            "ground_elevation_m": report.ground_elevation_m,
            "terrain": {
                "slope_deg": report.terrain.slope_deg if report.terrain else None,
                "ruggedness": report.terrain.ruggedness if report.terrain else None,
                "is_flat": report.terrain.is_flat if report.terrain else None,
            } if report.terrain else None,
            "obstacles": [
                {
                    "name": o.name,
                    "type": o.obstacle_type,
                    "location": {
                        "lat_deg": o.location.lat_deg,
                        "lon_deg": o.location.lon_deg,
                    },
                    "height_m": o.height_m,
                    "distance_m": o.distance_m,
                }
                for o in report.obstacles
            ],
            "land_use": [
                {
                    "type": lu.land_use_type,
                    "coverage_percent": lu.coverage_percent,
                    "is_restricted": lu.is_restricted,
                }
                for lu in report.land_use
            ],
            "airspace": {
                "has_airport": report.airspace.has_airport,
                "has_helipad": report.airspace.has_helipad,
                "has_restricted_area": report.airspace.has_restricted_area,
                "warning": report.airspace.warning,
            },
            "no_fly_zones": [
                {
                    "name": z.name,
                    "type": z.place_type.value,
                    "location": {
                        "lat_deg": z.location.lat_deg,
                        "lon_deg": z.location.lon_deg,
                    },
                }
                for z in report.no_fly_zones
            ],
            "suitability": report.suitability,
            "is_suitable_for_flight": report.is_suitable_for_flight,
            "warnings": report.warnings,
            "data_sources": report.data_sources,
        }

        return json.dumps(result)

    except Exception as e:
        logger.exception("analyze_area failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: lookup_place
# ==============================================================================

LOOKUP_PLACE_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def lookup_place_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for lookup_place tool."""
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Place name or address to look up",
            },
            "lat": {
                "type": "number",
                "description": "Optional latitude to bias search",
            },
            "lon": {
                "type": "number",
                "description": "Optional longitude to bias search",
            },
            "radius_m": {
                "type": "number",
                "description": "Search radius when lat/lon provided",
                "default": 1000,
            },
        },
        "required": ["query"],
    }


LOOKUP_PLACE_TOOL = ToolMeta(
    name="lookup_place",
    description=(
        "Look up a place by name or address. "
        "Returns location and metadata. "
        "Uses OSM Nominatim (and Google Maps if API key set). "
        "Results are cached for offline use."
    ),
    input_schema=lookup_place_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


async def lookup_place(
    query: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_m: float = 1000.0,
) -> str:
    """Look up a place by name or address.

    Args:
        query: Place name or address.
        lat: Optional latitude to bias search.
        lon: Optional longitude to bias search.
        radius_m: Search radius when lat/lon provided.

    Returns:
        JSON string with place information.
    """
    try:
        osm = OSMProvider()
        config = get_config()

        bbox = None
        if lat is not None and lon is not None:
            from avatar.mission_intel.geo import BBox
            bbox = BBox.from_center_radius(lat, lon, radius_m)

        # Try OSM first
        places = await osm.search_places(query, bbox=bbox, limit=5)

        # Optionally try Google Maps
        if not places and config.gmaps_enabled:
            gmaps = GoogleMapsProvider()
            if gmaps.is_available():
                places = await gmaps.search_places(query, bbox=bbox, limit=5)

        if not places:
            return json.dumps({
                "success": False,
                "error": f"Place not found: {query}",
                "isError": True,
            })

        result = {
            "success": True,
            "places": [
                {
                    "name": p.name,
                    "type": p.place_type.value,
                    "location": {
                        "lat_deg": p.location.lat_deg,
                        "lon_deg": p.location.lon_deg,
                    },
                    "address": p.address,
                    "is_no_fly_zone": p.is_no_fly_zone,
                    "osm_id": p.osm_id,
                }
                for p in places
            ],
            "source": "OSM" if not config.gmaps_enabled else "OSM/Google",
        }

        return json.dumps(result)

    except Exception as e:
        logger.exception("lookup_place failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: get_elevation
# ==============================================================================

GET_ELEVATION_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def get_elevation_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for get_elevation tool."""
    return {
        "type": "object",
        "properties": {
            "lat": {
                "type": "number",
                "description": "Latitude in degrees",
            },
            "lon": {
                "type": "number",
                "description": "Longitude in degrees",
            },
        },
        "required": ["lat", "lon"],
    }


GET_ELEVATION_TOOL = ToolMeta(
    name="get_elevation",
    description=(
        "Get ground elevation for coordinates. "
        "Uses SRTM tiles (offline when cached) or Open-Elevation API. "
        "Returns elevation in meters above sea level."
    ),
    input_schema=get_elevation_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


async def get_elevation(lat: float, lon: float) -> str:
    """Get ground elevation for coordinates.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        JSON string with elevation data.
    """
    try:
        provider = CompositeElevationProvider()
        result = await provider.get_elevation(lat, lon)

        if result is None:
            return json.dumps({
                "success": False,
                "error": "Elevation data not available for these coordinates",
                "isError": True,
            })

        return json.dumps({
            "success": True,
            "elevation_m": result.elevation_m,
            "source": result.source,
            "resolution_m": result.resolution_m,
            "is_interpolated": result.is_interpolated,
            "location": {
                "lat_deg": lat,
                "lon_deg": lon,
            },
        })

    except Exception as e:
        logger.exception("get_elevation failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: get_agl
# ==============================================================================

GET_AGL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def get_agl_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for get_agl tool."""
    return {
        "type": "object",
        "properties": {
            "lat": {
                "type": "number",
                "description": "Latitude in degrees",
            },
            "lon": {
                "type": "number",
                "description": "Longitude in degrees",
            },
            "altitude_amsl_m": {
                "type": "number",
                "description": "Altitude above mean sea level in meters",
            },
        },
        "required": ["lat", "lon", "altitude_amsl_m"],
    }


GET_AGL_TOOL = ToolMeta(
    name="get_agl",
    description=(
        "Calculate Above Ground Level (AGL) altitude. "
        "Given a planned altitude (AMSL) and coordinates, "
        "returns the height above the ground."
    ),
    input_schema=get_agl_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


async def get_agl(lat: float, lon: float, altitude_amsl_m: float) -> str:
    """Calculate Above Ground Level altitude.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.
        altitude_amsl_m: Altitude above mean sea level in meters.

    Returns:
        JSON string with AGL calculation.
    """
    try:
        agl = await calculate_agl(lat, lon, altitude_amsl_m)

        if agl is None:
            return json.dumps({
                "success": False,
                "error": "Could not determine ground elevation",
                "isError": True,
            })

        return json.dumps({
            "success": True,
            "agl_m": agl,
            "altitude_amsl_m": altitude_amsl_m,
            "location": {
                "lat_deg": lat,
                "lon_deg": lon,
            },
        })

    except Exception as e:
        logger.exception("get_agl failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: plan_scenic_sweep
# ==============================================================================

PLAN_SCENIC_SWEEP_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}


def plan_scenic_sweep_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for plan_scenic_sweep tool."""
    return {
        "type": "object",
        "properties": {
            "center_lat": {
                "type": "number",
                "description": "Center latitude in degrees",
            },
            "center_lon": {
                "type": "number",
                "description": "Center longitude in degrees",
            },
            "radius_m": {
                "type": "number",
                "description": "Sweep radius in meters",
                "default": 200,
                "minimum": 50,
                "maximum": 1000,
            },
            "altitude_agl_m": {
                "type": "number",
                "description": "Target altitude above ground level in meters",
                "default": 30,
                "minimum": 5,
                "maximum": 120,
            },
            "pattern": {
                "type": "string",
                "description": "Sweep pattern",
                "enum": ["circle", "spiral", "grid", "lawn_mower"],
                "default": "spiral",
            },
            "speed_m_s": {
                "type": "number",
                "description": "Flight speed in m/s",
                "default": 5,
                "minimum": 1,
                "maximum": 15,
            },
        },
        "required": ["center_lat", "center_lon", "radius_m"],
    }


PLAN_SCENIC_SWEEP_TOOL = ToolMeta(
    name="plan_scenic_sweep",
    description=(
        "Plan a scenic sweep mission for area coverage. "
        "Generates optimized flight path for photography or inspection. "
        "Includes terrain analysis and safety notes."
    ),
    input_schema=plan_scenic_sweep_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    open_world_hint=True,
)


async def plan_scenic_sweep(
    center_lat: float,
    center_lon: float,
    radius_m: float,
    altitude_agl_m: float = 30.0,
    pattern: str = "spiral",
    speed_m_s: float = 5.0,
) -> str:
    """Plan a scenic sweep mission.

    Args:
        center_lat: Center latitude in degrees.
        center_lon: Center longitude in degrees.
        radius_m: Sweep radius in meters.
        altitude_agl_m: Target altitude AGL in meters.
        pattern: Sweep pattern (circle, spiral, grid, lawn_mower).
        speed_m_s: Flight speed in m/s.

    Returns:
        JSON string with flight plan.
    """
    try:
        plan = await _plan_scenic_sweep(
            center_lat=center_lat,
            center_lon=center_lon,
            radius_m=radius_m,
            altitude_agl_m=altitude_agl_m,
            pattern=pattern,
            speed_m_s=speed_m_s,
            include_area_analysis=True,
        )

        result = {
            "success": True,
            "name": plan.name,
            "pattern": plan.pattern.value,
            "center": {
                "lat_deg": plan.center.lat_deg,
                "lon_deg": plan.center.lon_deg,
            },
            "radius_m": plan.radius_m,
            "num_waypoints": plan.num_waypoints,
            "total_distance_m": plan.total_distance_m,
            "estimated_time_s": plan.estimated_time_s,
            "estimated_time_min": plan.estimated_time_s / 60,
            "altitudes": {
                "min_amsl_m": plan.min_altitude_amsl_m,
                "max_amsl_m": plan.max_altitude_amsl_m,
                "recommended_agl_m": plan.recommended_altitude_agl_m,
            },
            "waypoints": [
                {
                    "index": wp.index,
                    "location": {
                        "lat_deg": wp.location.lat_deg,
                        "lon_deg": wp.location.lon_deg,
                    },
                    "altitude_amsl_m": wp.altitude_amsl_m,
                    "speed_m_s": wp.speed_m_s,
                    "hold_s": wp.hold_s,
                    "gimbal_pitch_deg": wp.gimbal_pitch_deg,
                    "action": wp.action,
                    "note": wp.note,
                }
                for wp in plan.waypoints
            ],
            "safety_notes": plan.safety_notes,
            "area_suitability": plan.area_report.suitability if plan.area_report else None,
            "area_warnings": plan.area_report.warnings if plan.area_report else [],
        }

        return json.dumps(result)

    except Exception as e:
        logger.exception("plan_scenic_sweep failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: plan_mission_from_intent
# ==============================================================================

PLAN_MISSION_FROM_INTENT_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


def plan_mission_from_intent_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for plan_mission_from_intent tool."""
    return {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": (
                    "Natural language mission description. "
                    "Examples: 'orbit the tower at 50m', "
                    "'fly to the park at 30m', "
                    "'scan the area with spiral pattern'"
                ),
            },
            "home_lat": {
                "type": "number",
                "description": "Home position latitude (for RTL missions)",
            },
            "home_lon": {
                "type": "number",
                "description": "Home position longitude (for RTL missions)",
            },
            "geocode": {
                "type": "boolean",
                "description": "Whether to geocode location names",
                "default": True,
            },
        },
        "required": ["intent"],
    }


PLAN_MISSION_FROM_INTENT_TOOL = ToolMeta(
    name="plan_mission_from_intent",
    description=(
        "Plan a mission from natural language intent. "
        "Supports 10+ intent patterns: orbit, follow, scan, inspect, "
        "photograph, fly-to, survey, hover, land, RTL, patrol, search. "
        "Example: 'orbit the tower at 50m for 2 minutes'"
    ),
    input_schema=plan_mission_from_intent_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
)


async def plan_mission_from_intent(
    intent: str,
    home_lat: Optional[float] = None,
    home_lon: Optional[float] = None,
    geocode: bool = True,
) -> str:
    """Plan a mission from natural language intent.

    Args:
        intent: Natural language mission description.
        home_lat: Home position latitude.
        home_lon: Home position longitude.
        geocode: Whether to geocode location names.

    Returns:
        JSON string with mission plan.
    """
    try:
        home = None
        if home_lat is not None and home_lon is not None:
            home = Point(lat_deg=home_lat, lon_deg=home_lon)

        result = await _plan_mission_from_intent(
            text=intent,
            home=home,
            geocode=geocode,
        )

        response = {
            "success": result.success,
            "intent": {
                "type": result.intent.intent_type.value if result.intent else None,
                "subject": result.intent.subject if result.intent else None,
                "altitude_m": result.intent.altitude_m if result.intent else None,
                "raw_text": result.intent.raw_text if result.intent else None,
            },
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
        }

        if result.mission:
            response["mission"] = {
                "name": result.mission.name,
                "version": result.mission.version,
                "home": {
                    "lat_deg": result.mission.home.lat_deg,
                    "lon_deg": result.mission.home.lon_deg,
                } if result.mission.home else None,
                "waypoints": [
                    {
                        "index": wp.index,
                        "location": {
                            "lat_deg": wp.point.lat_deg,
                            "lon_deg": wp.point.lon_deg,
                            "alt_m": wp.point.alt_m,
                        },
                        "hold_s": wp.hold_s,
                        "speed_m_s": wp.speed_m_s,
                    }
                    for wp in result.mission.waypoints
                ],
                "behaviors": [
                    {
                        "kind": b.kind,
                        "duration_s": b.duration_s,
                        "altitude_m": b.altitude_m,
                        "subject": b.subject,
                        "pattern": b.pattern,
                    }
                    for b in result.mission.behaviors
                ],
            }

        return json.dumps(response)

    except Exception as e:
        logger.exception("plan_mission_from_intent failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


# ==============================================================================
# Tool: propose_orbit_for_subject
# ==============================================================================

PROPOSE_ORBIT_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}


def propose_orbit_for_subject_tool_schema() -> Dict[str, Any]:
    """Return JSON schema for propose_orbit_for_subject tool."""
    return {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Subject to orbit (place name or description)",
            },
            "radius_m": {
                "type": "number",
                "description": "Orbit radius in meters",
                "default": 50,
                "minimum": 10,
                "maximum": 200,
            },
            "altitude_m": {
                "type": "number",
                "description": "Orbit altitude in meters (AGL)",
                "default": 30,
                "minimum": 5,
                "maximum": 120,
            },
            "duration_s": {
                "type": "number",
                "description": "Orbit duration in seconds",
                "default": 60,
                "minimum": 10,
                "maximum": 600,
            },
            "speed_m_s": {
                "type": "number",
                "description": "Flight speed in m/s",
                "default": 3,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["subject"],
    }


PROPOSE_ORBIT_FOR_SUBJECT_TOOL = ToolMeta(
    name="propose_orbit_for_subject",
    description=(
        "Propose an orbit plan for a subject. "
        "Looks up the subject location and generates orbit waypoints. "
        "Returns altitude, waypoints, and safety considerations."
    ),
    input_schema=propose_orbit_for_subject_tool_schema(),
    output_schema=analyze_area_output_schema(),
    read_only_hint=True,
    open_world_hint=True,
)


async def propose_orbit_for_subject(
    subject: str,
    radius_m: float = 50.0,
    altitude_m: float = 30.0,
    duration_s: float = 60.0,
    speed_m_s: float = 3.0,
) -> str:
    """Propose an orbit plan for a subject.

    Args:
        subject: Subject to orbit.
        radius_m: Orbit radius in meters.
        altitude_m: Orbit altitude AGL in meters.
        duration_s: Orbit duration in seconds.
        speed_m_s: Flight speed in m/s.

    Returns:
        JSON string with orbit plan.
    """
    try:
        # Look up subject location
        osm = OSMProvider()
        places = await osm.search_places(subject, limit=1)

        if not places:
            return json.dumps({
                "success": False,
                "error": f"Could not locate subject: {subject}",
                "isError": True,
            })

        target = places[0]

        # Generate orbit waypoints
        from avatar.mission_intel.geo import destination_point, generate_circle_grid

        center = target.location

        # Calculate number of points based on duration and speed
        circumference = 2 * 3.14159 * radius_m
        orbit_time_at_speed = circumference / speed_m_s
        num_points = max(8, int(duration_s / (orbit_time_at_speed / 8)))

        waypoints = []
        for i in range(num_points):
            bearing = 360.0 * i / num_points
            point = destination_point(center.lat_deg, center.lon_deg, bearing, radius_m)

            waypoints.append({
                "index": i,
                "location": {
                    "lat_deg": point.lat_deg,
                    "lon_deg": point.lon_deg,
                },
                "altitude_agl_m": altitude_m,
                "gimbal_pitch_deg": -45.0,
                "action": "photo" if i % 4 == 0 else "video",
            })

        # Analyze the area
        area_report = await _analyze_area(
            center_lat=center.lat_deg,
            center_lon=center.lon_deg,
            radius_m=radius_m + 50,
            include_places=False,
        )

        result = {
            "success": True,
            "subject": {
                "name": target.name,
                "type": target.place_type.value,
                "location": {
                    "lat_deg": center.lat_deg,
                    "lon_deg": center.lon_deg,
                },
                "is_no_fly_zone": target.is_no_fly_zone,
            },
            "orbit": {
                "radius_m": radius_m,
                "altitude_agl_m": altitude_m,
                "duration_s": duration_s,
                "speed_m_s": speed_m_s,
                "num_waypoints": num_points,
            },
            "waypoints": waypoints,
            "area_analysis": {
                "ground_elevation_m": area_report.ground_elevation_m,
                "terrain_slope_deg": area_report.terrain.slope_deg if area_report.terrain else None,
                "obstacle_count": len(area_report.obstacles),
                "suitability": area_report.suitability,
            },
            "safety_notes": area_report.warnings,
        }

        if target.is_no_fly_zone:
            result["warnings"] = [f"WARNING: {target.name} may be a restricted area"]

        return json.dumps(result)

    except Exception as e:
        logger.exception("propose_orbit_for_subject failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "isError": True,
        })


__all__ = [
    # Tool definitions
    "ANALYZE_AREA_TOOL",
    "LOOKUP_PLACE_TOOL",
    "GET_ELEVATION_TOOL",
    "GET_AGL_TOOL",
    "PLAN_SCENIC_SWEEP_TOOL",
    "PLAN_MISSION_FROM_INTENT_TOOL",
    "PROPOSE_ORBIT_FOR_SUBJECT_TOOL",
    # Tool implementations
    "analyze_area",
    "lookup_place",
    "get_elevation",
    "get_agl",
    "plan_scenic_sweep",
    "plan_mission_from_intent",
    "propose_orbit_for_subject",
    # Schema functions
    "analyze_area_tool_schema",
    "lookup_place_tool_schema",
    "get_elevation_tool_schema",
    "get_agl_tool_schema",
    "plan_scenic_sweep_tool_schema",
    "plan_mission_from_intent_tool_schema",
    "propose_orbit_for_subject_tool_schema",
    # Annotations
    "ANALYZE_AREA_ANNOTATIONS",
    "LOOKUP_PLACE_ANNOTATIONS",
    "GET_ELEVATION_ANNOTATIONS",
    "GET_AGL_ANNOTATIONS",
    "PLAN_SCENIC_SWEEP_ANNOTATIONS",
    "PLAN_MISSION_FROM_INTENT_ANNOTATIONS",
    "PROPOSE_ORBIT_ANNOTATIONS",
]
