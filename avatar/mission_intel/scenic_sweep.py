"""Scenic sweep mission planning.

Generates flight plans for area coverage with optimal viewpoints.
Useful for photography, inspection, and search operations.

Usage:
    from avatar.mission_intel.scenic_sweep import plan_scenic_sweep

    plan = await plan_scenic_sweep(
        center_lat=37.7749,
        center_lon=-122.4194,
        radius_m=200,
        altitude_agl_m=50,
        pattern="spiral"
    )
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from avatar.mission_intel.area_analyzer import analyze_area, AreaReport
from avatar.mission_intel.geo import (
    Point,
    destination_point,
    generate_circle_grid,
    generate_spiral_grid,
    haversine_distance,
)
from avatar.mission_intel.terrain import calculate_agl
from avatar.mission_intel.providers.elevation import ElevationProvider

logger = logging.getLogger(__name__)


class SweepPattern(str, Enum):
    """Available sweep patterns."""

    CIRCLE = "circle"
    SPIRAL = "spiral"
    GRID = "grid"
    LAWN_MOWER = "lawn_mower"


@dataclass(frozen=True, slots=True)
class SweepWaypoint:
    """A waypoint in the scenic sweep plan.

    Attributes:
        index: Waypoint index (0-based).
        location: Geographic coordinates.
        altitude_amsl_m: Altitude above mean sea level.
        altitude_agl_m: Altitude above ground level.
        speed_m_s: Recommended flight speed.
        hold_s: Hold time at waypoint.
        gimbal_pitch_deg: Gimbal pitch angle (-90 = down).
        gimbal_yaw_deg: Gimbal yaw angle (relative to heading).
        action: Action to perform at waypoint (photo, video, hover).
        note: Human-readable note about this waypoint.
    """

    index: int
    location: Point
    altitude_amsl_m: float
    altitude_agl_m: Optional[float] = None
    speed_m_s: float = 5.0
    hold_s: float = 2.0
    gimbal_pitch_deg: float = -45.0  # 45 degrees down
    gimbal_yaw_deg: float = 0.0
    action: str = "hover"
    note: str = ""


@dataclass
class ScenicSweepPlan:
    """Complete scenic sweep flight plan.

    Attributes:
        name: Plan name.
        center: Center point of sweep area.
        radius_m: Sweep radius in meters.
        pattern: Sweep pattern used.
        waypoints: Ordered list of waypoints.
        total_distance_m: Total flight distance.
        estimated_time_s: Estimated flight time.
        min_altitude_amsl_m: Minimum altitude in plan.
        max_altitude_amsl_m: Maximum altitude in plan.
        area_report: Area analysis report.
        recommended_altitude_agl_m: Recommended minimum AGL.
        safety_notes: Safety considerations.
    """

    name: str
    center: Point
    radius_m: float
    pattern: SweepPattern
    waypoints: List[SweepWaypoint] = field(default_factory=list)
    total_distance_m: float = 0.0
    estimated_time_s: float = 0.0
    min_altitude_amsl_m: float = 0.0
    max_altitude_amsl_m: float = 0.0
    area_report: Optional[AreaReport] = None
    recommended_altitude_agl_m: float = 30.0
    safety_notes: List[str] = field(default_factory=list)

    @property
    def num_waypoints(self) -> int:
        """Number of waypoints."""
        return len(self.waypoints)


async def plan_scenic_sweep(
    center_lat: float,
    center_lon: float,
    radius_m: float,
    altitude_agl_m: float = 30.0,
    pattern: str = "spiral",
    speed_m_s: float = 5.0,
    overlap_percent: float = 30.0,
    include_area_analysis: bool = True,
    elevation_provider: Optional[ElevationProvider] = None,
) -> ScenicSweepPlan:
    """Plan a scenic sweep mission.

    Generates a flight plan optimized for area coverage and photography.

    Args:
        center_lat: Center latitude in degrees.
        center_lon: Center longitude in degrees.
        radius_m: Sweep radius in meters.
        altitude_agl_m: Target altitude above ground level.
        pattern: Sweep pattern (circle, spiral, grid, lawn_mower).
        speed_m_s: Flight speed in m/s.
        overlap_percent: Overlap between passes (for grid/lawn_mower).
        include_area_analysis: Whether to include area analysis.
        elevation_provider: Elevation data provider.

    Returns:
        ScenicSweepPlan with waypoints and metadata.
    """
    center = Point(lat_deg=center_lat, lon_deg=center_lon)

    # Analyze area if requested
    area_report = None
    if include_area_analysis:
        area_report = await analyze_area(
            center_lat,
            center_lon,
            radius_m,
            elevation_provider=elevation_provider,
        )

    # Get ground elevation at center
    from avatar.mission_intel.terrain import TerrainAnalyzer
    terrain_analyzer = TerrainAnalyzer(elevation_provider)
    ground_elev = await terrain_analyzer.get_ground_elevation(center_lat, center_lon)

    # Calculate AMSL altitude
    if ground_elev is not None:
        altitude_amsl_m = ground_elev + altitude_agl_m
    else:
        # Fallback: assume sea level + altitude
        altitude_amsl_m = altitude_agl_m

    # Generate waypoints based on pattern
    sweep_pattern = SweepPattern(pattern.lower())

    if sweep_pattern == SweepPattern.CIRCLE:
        waypoints = _generate_circle_waypoints(
            center, radius_m, altitude_amsl_m, altitude_agl_m, speed_m_s
        )
    elif sweep_pattern == SweepPattern.SPIRAL:
        waypoints = _generate_spiral_waypoints(
            center, radius_m, altitude_amsl_m, altitude_agl_m, speed_m_s
        )
    elif sweep_pattern == SweepPattern.GRID:
        waypoints = _generate_grid_waypoints(
            center, radius_m, altitude_amsl_m, altitude_agl_m, speed_m_s, overlap_percent
        )
    elif sweep_pattern == SweepPattern.LAWN_MOWER:
        waypoints = _generate_lawn_mower_waypoints(
            center, radius_m, altitude_amsl_m, altitude_agl_m, speed_m_s, overlap_percent
        )
    else:
        # Default to spiral
        waypoints = _generate_spiral_waypoints(
            center, radius_m, altitude_amsl_m, altitude_agl_m, speed_m_s
        )

    # Calculate total distance and time
    total_distance = _calculate_total_distance(waypoints)
    estimated_time = _calculate_estimated_time(waypoints, speed_m_s)

    # Generate safety notes
    safety_notes = _generate_safety_notes(area_report, altitude_agl_m)

    # Determine altitude range
    altitudes = [w.altitude_amsl_m for w in waypoints]
    min_alt = min(altitudes) if altitudes else altitude_amsl_m
    max_alt = max(altitudes) if altitudes else altitude_amsl_m

    return ScenicSweepPlan(
        name=f"Scenic Sweep ({sweep_pattern.value})",
        center=center,
        radius_m=radius_m,
        pattern=sweep_pattern,
        waypoints=waypoints,
        total_distance_m=total_distance,
        estimated_time_s=estimated_time,
        min_altitude_amsl_m=min_alt,
        max_altitude_amsl_m=max_alt,
        area_report=area_report,
        recommended_altitude_agl_m=altitude_agl_m,
        safety_notes=safety_notes,
    )


def _generate_circle_waypoints(
    center: Point,
    radius_m: float,
    altitude_amsl_m: float,
    altitude_agl_m: float,
    speed_m_s: float,
    num_points: int = 12,
) -> List[SweepWaypoint]:
    """Generate waypoints in a circular pattern."""
    waypoints: List[SweepWaypoint] = []

    # Start from north, go clockwise
    for i in range(num_points):
        bearing = 360.0 * i / num_points
        point = destination_point(center.lat_deg, center.lon_deg, bearing, radius_m)

        # Camera points at center
        gimbal_pitch = -45.0

        waypoints.append(
            SweepWaypoint(
                index=i,
                location=point,
                altitude_amsl_m=altitude_amsl_m,
                altitude_agl_m=altitude_agl_m,
                speed_m_s=speed_m_s,
                hold_s=1.0,
                gimbal_pitch_deg=gimbal_pitch,
                action="photo" if i % 3 == 0 else "hover",
                note=f"Circle point {i+1}/{num_points}",
            )
        )

    return waypoints


def _generate_spiral_waypoints(
    center: Point,
    radius_m: float,
    altitude_amsl_m: float,
    altitude_agl_m: float,
    speed_m_s: float,
    num_points: int = 20,
) -> List[SweepWaypoint]:
    """Generate waypoints in an expanding spiral pattern."""
    waypoints: List[SweepWaypoint] = []

    for i, point in enumerate(
        generate_spiral_grid(center, radius_m, num_points)
    ):
        # Vary altitude slightly for better coverage
        alt_offset = (i / num_points) * 10  # Increase 10m over spiral
        current_alt_amsl = altitude_amsl_m + alt_offset

        # Camera points outward initially, then inward
        progress = i / num_points
        gimbal_pitch = -30.0 - progress * 30.0  # -30 to -60 degrees

        waypoints.append(
            SweepWaypoint(
                index=i,
                location=point,
                altitude_amsl_m=current_alt_amsl,
                altitude_agl_m=altitude_agl_m + alt_offset,
                speed_m_s=speed_m_s,
                hold_s=0.5,
                gimbal_pitch_deg=gimbal_pitch,
                action="video",
                note=f"Spiral point {i+1}/{num_points}",
            )
        )

    return waypoints


def _generate_grid_waypoints(
    center: Point,
    radius_m: float,
    altitude_amsl_m: float,
    altitude_agl_m: float,
    speed_m_s: float,
    overlap_percent: float,
) -> List[SweepWaypoint]:
    """Generate waypoints in a grid pattern."""
    waypoints: List[SweepWaypoint] = []

    # Calculate grid spacing based on overlap
    # For photography, spacing should account for camera field of view
    # Simplified: use radius/5 as spacing
    spacing_m = radius_m * 2 / 5

    # Generate grid points
    num_rows = 5
    num_cols = 5

    idx = 0
    for row in range(num_rows):
        row_waypoints: List[SweepWaypoint] = []

        for col in range(num_cols):
            # Calculate offset from center
            north_offset = (row - num_rows // 2) * spacing_m
            east_offset = (col - num_cols // 2) * spacing_m

            # Convert to lat/lon
            bearing = math.degrees(math.atan2(east_offset, north_offset))
            if bearing < 0:
                bearing += 360

            distance = math.sqrt(north_offset ** 2 + east_offset ** 2)
            point = destination_point(center.lat_deg, center.lon_deg, bearing, distance)

            row_waypoints.append(
                SweepWaypoint(
                    index=idx,
                    location=point,
                    altitude_amsl_m=altitude_amsl_m,
                    altitude_agl_m=altitude_agl_m,
                    speed_m_s=speed_m_s,
                    hold_s=1.0,
                    gimbal_pitch_deg=-90.0,  # Straight down for grid
                    action="photo",
                    note=f"Grid ({row}, {col})",
                )
            )
            idx += 1

        # Alternate direction for efficiency
        if row % 2 == 1:
            row_waypoints.reverse()

        waypoints.extend(row_waypoints)

    # Fix indices after reordering
    for i, wp in enumerate(waypoints):
        waypoints[i] = SweepWaypoint(
            index=i,
            location=wp.location,
            altitude_amsl_m=wp.altitude_amsl_m,
            altitude_agl_m=wp.altitude_agl_m,
            speed_m_s=wp.speed_m_s,
            hold_s=wp.hold_s,
            gimbal_pitch_deg=wp.gimbal_pitch_deg,
            gimbal_yaw_deg=wp.gimbal_yaw_deg,
            action=wp.action,
            note=wp.note,
        )

    return waypoints


def _generate_lawn_mower_waypoints(
    center: Point,
    radius_m: float,
    altitude_amsl_m: float,
    altitude_agl_m: float,
    speed_m_s: float,
    overlap_percent: float,
) -> List[SweepWaypoint]:
    """Generate waypoints in a lawn mower (zigzag) pattern."""
    waypoints: List[SweepWaypoint] = []

    # Calculate line spacing based on overlap
    line_spacing_m = radius_m * 2 / 5
    line_length_m = radius_m * 2

    num_lines = 5
    idx = 0

    for line in range(num_lines):
        # Start position for this line
        north_offset = (line - num_lines // 2) * line_spacing_m
        east_offset = -radius_m if line % 2 == 0 else radius_m

        bearing = math.degrees(math.atan2(east_offset, north_offset))
        if bearing < 0:
            bearing += 360
        distance = math.sqrt(north_offset ** 2 + east_offset ** 2)

        start_point = destination_point(center.lat_deg, center.lon_deg, bearing, distance)

        # Direction for this line
        direction = 90.0 if line % 2 == 0 else 270.0  # East or West

        # Points along this line
        num_points_per_line = 3
        for p in range(num_points_per_line):
            dist = line_length_m * p / (num_points_per_line - 1) - line_length_m / 2
            point = destination_point(
                start_point.lat_deg,
                start_point.lon_deg,
                direction,
                abs(dist),
            )

            waypoints.append(
                SweepWaypoint(
                    index=idx,
                    location=point,
                    altitude_amsl_m=altitude_amsl_m,
                    altitude_agl_m=altitude_agl_m,
                    speed_m_s=speed_m_s,
                    hold_s=0.0,  # No hold, continuous motion
                    gimbal_pitch_deg=-90.0,
                    action="video",
                    note=f"Lawn mower line {line+1} point {p+1}",
                )
            )
            idx += 1

    return waypoints


def _calculate_total_distance(waypoints: List[SweepWaypoint]) -> float:
    """Calculate total flight distance."""
    if len(waypoints) < 2:
        return 0.0

    total = 0.0
    for i in range(1, len(waypoints)):
        prev = waypoints[i - 1]
        curr = waypoints[i]
        dist_km = haversine_distance(
            prev.location.lat_deg,
            prev.location.lon_deg,
            curr.location.lat_deg,
            curr.location.lon_deg,
        )
        total += dist_km * 1000  # Convert to meters

    return total


def _calculate_estimated_time(waypoints: List[SweepWaypoint], speed_m_s: float) -> float:
    """Calculate estimated flight time."""
    total_distance = _calculate_total_distance(waypoints)
    travel_time = total_distance / speed_m_s if speed_m_s > 0 else 0

    hold_time = sum(wp.hold_s for wp in waypoints)

    return travel_time + hold_time


def _generate_safety_notes(
    area_report: Optional[AreaReport],
    altitude_agl_m: float,
) -> List[str]:
    """Generate safety notes for the plan."""
    notes: List[str] = []

    notes.append(f"Maintain minimum {altitude_agl_m}m AGL throughout flight")

    if area_report:
        if area_report.terrain and area_report.terrain.slope_deg > 10:
            notes.append("Uneven terrain - monitor altitude carefully")

        if area_report.obstacles:
            tall_obstacles = [o for o in area_report.obstacles if o.height_m and o.height_m > altitude_agl_m]
            if tall_obstacles:
                notes.append(f"WARNING: {len(tall_obstacles)} obstacles exceed planned altitude")

        if area_report.no_fly_zones:
            notes.append(f"Avoid no-fly zones: {', '.join(z.name for z in area_report.no_fly_zones)}")

        notes.extend(area_report.warnings)

    return notes


__all__ = [
    "plan_scenic_sweep",
    "ScenicSweepPlan",
    "SweepWaypoint",
    "SweepPattern",
]
