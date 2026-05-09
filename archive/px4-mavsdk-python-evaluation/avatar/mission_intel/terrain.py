"""Terrain analysis for drone flight planning.

Provides:
- AGL (Above Ground Level) calculation
- Slope analysis for landing zones
- Terrain ruggedness assessment
- Line-of-sight calculations

Usage:
    from avatar.mission_intel.terrain import calculate_agl, calculate_slope

    # Get AGL for a flight altitude
    agl = await calculate_agl(lat=37.7749, lon=-122.4194, altitude_amsl_m=100)

    # Check slope for landing
    slope = await calculate_slope(center_lat=37.7749, center_lon=-122.4194, radius_m=50)
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from avatar.mission_intel.geo import (
    BBox,
    Point,
    destination_point,
    haversine_distance,
)
from avatar.mission_intel.providers.elevation import (
    CompositeElevationProvider,
    ElevationProvider,
    SRTMProvider,
)
from avatar.mission_intel.providers.base import ElevationResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TerrainResult:
    """Result of terrain analysis.

    Attributes:
        ground_elevation_m: Ground elevation at point (AMSL).
        slope_deg: Terrain slope in degrees (0-90).
        ruggedness: Terrain ruggedness index (0-1, higher = more rugged).
        aspect_deg: Slope aspect/direction (0-360, 0=North).
        is_flat: True if slope < 5 degrees (suitable for landing).
    """

    ground_elevation_m: float
    slope_deg: float = 0.0
    ruggedness: float = 0.0
    aspect_deg: float = 0.0

    @property
    def is_flat(self) -> bool:
        """Check if terrain is flat enough for landing."""
        return self.slope_deg < 5.0


class TerrainAnalyzer:
    """Analyze terrain for drone flight planning.

    Uses elevation data to compute:
    - Ground elevation at points
    - Slope for landing zone assessment
    - Terrain ruggedness for navigation planning
    - Line-of-sight for communication range
    """

    def __init__(self, elevation_provider: Optional[ElevationProvider] = None):
        """Initialize terrain analyzer.

        Args:
            elevation_provider: Elevation data provider. Defaults to SRTM.
        """
        self._elevation = elevation_provider or CompositeElevationProvider()

    async def get_ground_elevation(
        self,
        lat_deg: float,
        lon_deg: float,
    ) -> Optional[float]:
        """Get ground elevation at a point.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Ground elevation in meters (AMSL) or None.
        """
        result = await self._elevation.get_elevation(lat_deg, lon_deg)
        if result:
            return result.elevation_m
        return None

    async def analyze_terrain(
        self,
        lat_deg: float,
        lon_deg: float,
        radius_m: float = 50.0,
    ) -> TerrainResult:
        """Analyze terrain around a point.

        Samples elevation in a grid pattern around the center point
        to compute slope and ruggedness.

        Args:
            lat_deg: Center latitude.
            lon_deg: Center longitude.
            radius_m: Analysis radius in meters.

        Returns:
            TerrainResult with elevation, slope, and ruggedness.
        """
        # Get center elevation
        center_elev = await self.get_ground_elevation(lat_deg, lon_deg)
        if center_elev is None:
            return TerrainResult(ground_elevation_m=0.0)

        # Sample points in a 3x3 grid
        points: List[Tuple[Point, float]] = []
        for dlat in [-1, 0, 1]:
            for dlon in [-1, 0, 1]:
                offset_m = radius_m / 3
                bearing = 0.0
                if dlat != 0 or dlon != 0:
                    bearing = math.degrees(math.atan2(dlon, dlat))
                    if bearing < 0:
                        bearing += 360
                    distance = math.sqrt(dlat ** 2 + dlon ** 2) * offset_m
                else:
                    distance = 0.0

                if distance > 0:
                    point = destination_point(lat_deg, lon_deg, bearing, distance)
                else:
                    point = Point(lat_deg=lat_deg, lon_deg=lon_deg)

                elev = await self.get_ground_elevation(point.lat_deg, point.lon_deg)
                if elev is not None:
                    points.append((point, elev))

        if len(points) < 4:
            return TerrainResult(ground_elevation_m=center_elev)

        # Calculate slope using elevation differences
        max_slope = 0.0
        aspect = 0.0

        for point, elev in points[1:]:  # Skip center
            # Distance from center
            dist = haversine_distance(
                lat_deg, lon_deg,
                point.lat_deg, point.lon_deg,
            ) * 1000  # Convert to meters

            if dist > 0:
                slope = math.degrees(math.atan2(abs(elev - center_elev), dist))
                if slope > max_slope:
                    max_slope = slope
                    # Aspect is direction of steepest descent
                    bearing = math.degrees(
                        math.atan2(
                            lon_deg - point.lon_deg,
                            lat_deg - point.lat_deg,
                        )
                    )
                    aspect = (bearing + 360) % 360

        # Calculate ruggedness as standard deviation of elevations
        elevations = [e for _, e in points]
        mean_elev = sum(elevations) / len(elevations)
        variance = sum((e - mean_elev) ** 2 for e in elevations) / len(elevations)
        ruggedness = min(1.0, math.sqrt(variance) / 50.0)  # Normalize to 0-1

        return TerrainResult(
            ground_elevation_m=center_elev,
            slope_deg=max_slope,
            ruggedness=ruggedness,
            aspect_deg=aspect,
        )

    async def check_line_of_sight(
        self,
        point1: Point,
        point2: Point,
        sample_interval_m: float = 100.0,
    ) -> bool:
        """Check if there's line-of-sight between two points.

        Samples terrain along the path to check for obstructions.

        Args:
            point1: First point (with altitude).
            point2: Second point (with altitude).
            sample_interval_m: Distance between sample points.

        Returns:
            True if line-of-sight exists.
        """
        if point1.alt_m is None or point2.alt_m is None:
            return True  # Can't check without altitudes

        # Calculate bearing and distance
        lat1 = math.radians(point1.lat_deg)
        lon1 = math.radians(point1.lon_deg)
        lat2 = math.radians(point2.lat_deg)
        lon2 = math.radians(point2.lon_deg)

        dlon = lon2 - lon1

        bearing = math.atan2(
            math.sin(dlon) * math.cos(lat2),
            math.cos(lat1) * math.sin(lat2)
            - math.sin(lat1) * math.cos(lat2) * math.cos(dlon),
        )
        bearing_deg = math.degrees(bearing)

        dist_km = haversine_distance(
            point1.lat_deg, point1.lon_deg,
            point2.lat_deg, point2.lon_deg,
        )
        dist_m = dist_km * 1000

        # Sample along the path
        num_samples = max(2, int(dist_m / sample_interval_m))

        for i in range(1, num_samples):
            frac = i / num_samples
            sample_dist = dist_m * frac

            # Interpolate altitude
            interp_alt = point1.alt_m + frac * (point2.alt_m - point1.alt_m)

            # Get terrain elevation at sample point
            sample_point = destination_point(
                point1.lat_deg, point1.lon_deg,
                bearing_deg, sample_dist,
            )

            terrain_elev = await self.get_ground_elevation(
                sample_point.lat_deg, sample_point.lon_deg,
            )

            if terrain_elev is not None and terrain_elev >= interp_alt:
                return False  # Obstructed

        return True


async def calculate_agl(
    lat_deg: float,
    lon_deg: float,
    altitude_amsl_m: float,
    elevation_provider: Optional[ElevationProvider] = None,
) -> Optional[float]:
    """Calculate Above Ground Level altitude.

    Args:
        lat_deg: Latitude in degrees.
        lon_deg: Longitude in degrees.
        altitude_amsl_m: Altitude above mean sea level in meters.
        elevation_provider: Elevation data provider.

    Returns:
        AGL in meters or None if ground elevation unavailable.
    """
    analyzer = TerrainAnalyzer(elevation_provider)
    ground_elev = await analyzer.get_ground_elevation(lat_deg, lon_deg)

    if ground_elev is None:
        return None

    return altitude_amsl_m - ground_elev


async def calculate_slope(
    lat_deg: float,
    lon_deg: float,
    radius_m: float = 50.0,
    elevation_provider: Optional[ElevationProvider] = None,
) -> Optional[float]:
    """Calculate terrain slope around a point.

    Args:
        lat_deg: Latitude in degrees.
        lon_deg: Longitude in degrees.
        radius_m: Analysis radius in meters.
        elevation_provider: Elevation data provider.

    Returns:
        Slope in degrees or None if elevation unavailable.
    """
    analyzer = TerrainAnalyzer(elevation_provider)
    result = await analyzer.analyze_terrain(lat_deg, lon_deg, radius_m)
    return result.slope_deg


async def calculate_line_of_sight(
    point1: Point,
    point2: Point,
    elevation_provider: Optional[ElevationProvider] = None,
) -> Optional[bool]:
    """Check line-of-sight between two points.

    Args:
        point1: First point (with altitude).
        point2: Second point (with altitude).
        elevation_provider: Elevation data provider.

    Returns:
        True if line-of-sight, False if obstructed, None if can't check.
    """
    if point1.alt_m is None or point2.alt_m is None:
        return None

    analyzer = TerrainAnalyzer(elevation_provider)
    return await analyzer.check_line_of_sight(point1, point2)


__all__ = [
    "TerrainResult",
    "TerrainAnalyzer",
    "calculate_agl",
    "calculate_slope",
    "calculate_line_of_sight",
]
