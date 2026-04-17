"""Area analysis for drone mission planning.

Provides comprehensive analysis of an area including:
- Obstacles (buildings, towers, power lines)
- Land use (parks, residential, industrial)
- Airspace considerations
- Terrain characteristics

Works offline using OSM/SRTM data when cached.

Usage:
    from avatar.mission_intel.area_analyzer import analyze_area

    report = await analyze_area(
        center_lat=37.7749,
        center_lon=-122.4194,
        radius_m=500
    )
    print(f"Found {len(report.obstacles)} obstacles")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from avatar.mission_intel.geo import (
    BBox,
    Point,
    haversine_distance,
)
from avatar.mission_intel.providers.base import (
    LandUseResult,
    ObstacleResult,
    PlaceResult,
    PlaceType,
)
from avatar.mission_intel.providers.elevation import CompositeElevationProvider, ElevationProvider
from avatar.mission_intel.providers.osm import OSMProvider
from avatar.mission_intel.terrain import TerrainAnalyzer, TerrainResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ObstacleInfo:
    """Information about an obstacle in the area.

    Attributes:
        name: Obstacle name or description.
        obstacle_type: Type classification.
        location: Geographic location.
        height_m: Estimated height (if known).
        distance_m: Distance from center point.
        bearing_deg: Bearing from center point.
        is_no_fly: True if this is a no-fly obstacle.
    """

    name: str
    obstacle_type: str
    location: Point
    height_m: Optional[float] = None
    distance_m: float = 0.0
    bearing_deg: float = 0.0
    is_no_fly: bool = False


@dataclass(frozen=True, slots=True)
class LandUseInfo:
    """Land use information for the area.

    Attributes:
        land_use_type: Type of land use.
        coverage_percent: Percentage of area coverage.
        is_restricted: True if flight may be restricted.
    """

    land_use_type: str
    coverage_percent: float
    is_restricted: bool = False


@dataclass(frozen=True, slots=True)
class AirspaceInfo:
    """Airspace information for the area.

    Note: Full airspace analysis requires external API.
    This provides basic heuristics based on OSM data.

    Attributes:
        has_airport: True if airport within 5km.
        has_helipad: True if helipad within area.
        has_restricted_area: True if military/prison/etc in area.
        is_near_boundary: True if within 1km of restricted area.
        warning: Human-readable warning message.
    """

    has_airport: bool = False
    has_helipad: bool = False
    has_restricted_area: bool = False
    is_near_boundary: bool = False
    warning: str = ""


@dataclass
class AreaReport:
    """Comprehensive area analysis report.

    Attributes:
        center: Center point of analysis.
        radius_m: Analysis radius in meters.
        ground_elevation_m: Ground elevation at center (AMSL).
        terrain: Terrain analysis result.
        obstacles: List of obstacles in area.
        land_use: Land use classification.
        airspace: Airspace information.
        places: Points of interest.
        no_fly_zones: List of no-fly zones.
        suitability: Overall flight suitability score (0-1).
        warnings: List of warning messages.
        data_sources: Sources of data used (OSM, SRTM, etc.).
        is_offline: True if data came from cache only.
    """

    center: Point
    radius_m: float
    ground_elevation_m: Optional[float] = None
    terrain: Optional[TerrainResult] = None
    obstacles: List[ObstacleInfo] = field(default_factory=list)
    land_use: List[LandUseInfo] = field(default_factory=list)
    airspace: AirspaceInfo = field(default_factory=AirspaceInfo)
    places: List[PlaceResult] = field(default_factory=list)
    no_fly_zones: List[PlaceResult] = field(default_factory=list)
    suitability: float = 1.0
    warnings: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    is_offline: bool = False

    @property
    def is_suitable_for_flight(self) -> bool:
        """Check if area is suitable for drone flight."""
        return self.suitability > 0.5 and not self.airspace.has_restricted_area


async def analyze_area(
    center_lat: float,
    center_lon: float,
    radius_m: float = 500.0,
    elevation_provider: Optional[ElevationProvider] = None,
    include_places: bool = True,
) -> AreaReport:
    """Analyze an area for drone flight planning.

    This is the main entry point for area analysis. It gathers:
    - Terrain elevation and slope
    - Obstacles from OSM
    - Land use classification
    - Airspace considerations
    - Points of interest

    Works offline using cached OSM/SRTM data.

    Args:
        center_lat: Center latitude in degrees.
        center_lon: Center longitude in degrees.
        radius_m: Analysis radius in meters.
        elevation_provider: Elevation data provider.
        include_places: Whether to include POI search.

    Returns:
        AreaReport with comprehensive analysis.
    """
    center = Point(lat_deg=center_lat, lon_deg=center_lon)
    bbox = BBox.from_center_radius(center_lat, center_lon, radius_m)

    # Initialize providers
    osm = OSMProvider()
    terrain_analyzer = TerrainAnalyzer(elevation_provider)

    # Run analyses in parallel
    (
        ground_elev,
        terrain_result,
        obstacles,
        land_use,
        places,
    ) = await asyncio.gather(
        terrain_analyzer.get_ground_elevation(center_lat, center_lon),
        terrain_analyzer.analyze_terrain(center_lat, center_lon, radius_m / 2),
        osm.get_obstacles_in_area(bbox),
        osm.get_land_use(bbox),
        osm.search_places("", bbox=bbox, limit=20) if include_places else asyncio.sleep(0, result=[]),
    )

    # Process obstacles with distance/bearing
    obstacle_infos: List[ObstacleInfo] = []
    no_fly_zones: List[PlaceResult] = []

    for obs in obstacles:
        # Calculate distance and bearing from center
        dist_km = haversine_distance(
            center_lat, center_lon,
            obs.location.lat_deg, obs.location.lon_deg,
        )
        dist_m = dist_km * 1000

        # Calculate bearing
        lat1 = center_lat * 3.14159 / 180
        lat2 = obs.location.lat_deg * 3.14159 / 180
        dlon = (obs.location.lon_deg - center_lon) * 3.14159 / 180

        import math
        bearing = math.degrees(math.atan2(
            math.sin(dlon) * math.cos(lat2),
            math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        ))
        bearing = (bearing + 360) % 360

        obstacle_infos.append(
            ObstacleInfo(
                name=obs.name,
                obstacle_type=obs.obstacle_type.value,
                location=obs.location,
                height_m=obs.height_m,
                distance_m=dist_m,
                bearing_deg=bearing,
                is_no_fly=False,  # Obstacles aren't no-fly zones per se
            )
        )

    # Check for no-fly zones from places
    for place in places:
        if place.is_no_fly_zone:
            no_fly_zones.append(place)

    # Analyze airspace
    airspace = _analyze_airspace(places, obstacles)

    # Process land use
    land_use_infos: List[LandUseInfo] = []
    restricted_types = {"military", "prison", "airport", "industrial"}

    for lu in land_use:
        is_restricted = any(r in lu.land_use_type.lower() for r in restricted_types)
        land_use_infos.append(
            LandUseInfo(
                land_use_type=lu.land_use_type,
                coverage_percent=lu.coverage_percent,
                is_restricted=is_restricted,
            )
        )

    # Calculate suitability score
    suitability = _calculate_suitability(
        terrain_result,
        obstacle_infos,
        land_use_infos,
        airspace,
        no_fly_zones,
    )

    # Generate warnings
    warnings = _generate_warnings(
        terrain_result,
        obstacle_infos,
        land_use_infos,
        airspace,
        no_fly_zones,
    )

    # Determine data sources
    data_sources = ["OSM"]
    if ground_elev is not None:
        data_sources.append("SRTM")

    return AreaReport(
        center=center,
        radius_m=radius_m,
        ground_elevation_m=ground_elev,
        terrain=terrain_result,
        obstacles=obstacle_infos,
        land_use=land_use_infos,
        airspace=airspace,
        places=places,
        no_fly_zones=no_fly_zones,
        suitability=suitability,
        warnings=warnings,
        data_sources=data_sources,
        is_offline=True,  # Using OSM/SRTM which can work offline
    )


def _analyze_airspace(
    places: List[PlaceResult],
    obstacles: List[ObstacleResult],
) -> AirspaceInfo:
    """Analyze airspace from places and obstacles.

    Args:
        places: List of places in area.
        obstacles: List of obstacles in area.

    Returns:
        AirspaceInfo with airspace analysis.
    """
    has_airport = any(p.place_type == PlaceType.AIRPORT for p in places)
    has_helipad = any(p.place_type == PlaceType.HELIPAD for p in places)

    restricted_types = {PlaceType.PRISON, PlaceType.MILITARY}
    has_restricted = any(p.place_type in restricted_types for p in places)

    warning = ""
    if has_airport:
        warning = "Airport in area - check NOTAMs and airspace restrictions"
    elif has_helipad:
        warning = "Helipad in area - watch for helicopter traffic"
    elif has_restricted:
        warning = "Restricted area in vicinity - verify flight authorization"

    return AirspaceInfo(
        has_airport=has_airport,
        has_helipad=has_helipad,
        has_restricted_area=has_restricted,
        warning=warning,
    )


def _calculate_suitability(
    terrain: Optional[TerrainResult],
    obstacles: List[ObstacleInfo],
    land_use: List[LandUseInfo],
    airspace: AirspaceInfo,
    no_fly_zones: List[PlaceResult],
) -> float:
    """Calculate overall flight suitability score.

    Args:
        terrain: Terrain analysis result.
        obstacles: List of obstacles.
        land_use: Land use classification.
        airspace: Airspace info.
        no_fly_zones: No-fly zones.

    Returns:
        Suitability score from 0 to 1.
    """
    score = 1.0

    # Terrain penalty
    if terrain:
        if terrain.slope_deg > 10:
            score -= 0.1
        if terrain.ruggedness > 0.5:
            score -= 0.1

    # Obstacle density penalty
    high_obstacles = [o for o in obstacles if o.height_m and o.height_m > 30]
    score -= len(high_obstacles) * 0.05

    # Restricted land use penalty
    for lu in land_use:
        if lu.is_restricted:
            score -= 0.2 * (lu.coverage_percent / 100)

    # Airspace penalty
    if airspace.has_airport:
        score -= 0.5
    if airspace.has_restricted_area:
        score -= 0.8
    if airspace.has_helipad:
        score -= 0.1

    # No-fly zone penalty
    score -= len(no_fly_zones) * 0.3

    return max(0.0, min(1.0, score))


def _generate_warnings(
    terrain: Optional[TerrainResult],
    obstacles: List[ObstacleInfo],
    land_use: List[LandUseInfo],
    airspace: AirspaceInfo,
    no_fly_zones: List[PlaceResult],
) -> List[str]:
    """Generate warning messages.

    Args:
        terrain: Terrain analysis.
        obstacles: Obstacles.
        land_use: Land use.
        airspace: Airspace info.
        no_fly_zones: No-fly zones.

    Returns:
        List of warning messages.
    """
    warnings: List[str] = []

    if terrain:
        if terrain.slope_deg > 15:
            warnings.append(f"Steep terrain ({terrain.slope_deg:.1f}deg slope) - use caution for landing")
        if terrain.ruggedness > 0.6:
            warnings.append("Rugged terrain - maintain higher altitude for safety")

    tall_obstacles = [o for o in obstacles if o.height_m and o.height_m > 50]
    if tall_obstacles:
        warnings.append(f"{len(tall_obstacles)} tall obstacles (>50m) in area")

    if airspace.warning:
        warnings.append(airspace.warning)

    if no_fly_zones:
        zone_names = [z.name for z in no_fly_zones[:3]]
        warnings.append(f"No-fly zones: {', '.join(zone_names)}")

    return warnings


__all__ = [
    "analyze_area",
    "AreaReport",
    "ObstacleInfo",
    "LandUseInfo",
    "AirspaceInfo",
]
