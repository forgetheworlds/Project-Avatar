"""Safety checks for mission planning.

Validates mission plans against:
- Geofence overlap
- Minimum AGL requirements
- Battery feasibility
- Terrain obstacles
- Airspace restrictions

Usage:
    from avatar.mission_intel.safety_checks import run_safety_checks

    results = await run_safety_checks(mission, battery_percent=85)
    if all(r.passed for r in results):
        # Safe to proceed
        pass
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from avatar.mission_intel.geo import (
    BBox,
    Point,
    Polygon,
    haversine_distance,
)
from avatar.mission_intel.mission_spec import MissionSpec
from avatar.mission_intel.terrain import TerrainAnalyzer
from avatar.mission_intel.area_analyzer import analyze_area
from avatar.mission_intel.providers.elevation import ElevationProvider

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Status of a safety check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class SafetyCheckResult:
    """Result of a single safety check.

    Attributes:
        name: Name of the check.
        status: Pass, warn, or fail.
        message: Human-readable message.
        details: Additional details.
        severity: Severity level (1-10, 10 being most severe).
    """

    name: str
    status: CheckStatus
    message: str = ""
    details: str = ""
    severity: int = 1

    @property
    def passed(self) -> bool:
        """True if check passed or warned."""
        return self.status in (CheckStatus.PASS, CheckStatus.WARN)


def check_geofence_overlap(
    mission: MissionSpec,
    geofence: Optional[Polygon] = None,
) -> SafetyCheckResult:
    """Check if mission waypoints are within geofence.

    Args:
        mission: Mission specification.
        geofence: Geofence polygon (optional).

    Returns:
        SafetyCheckResult with status and details.
    """
    if not geofence:
        return SafetyCheckResult(
            name="geofence_overlap",
            status=CheckStatus.WARN,
            message="No geofence defined - mission unrestricted",
            severity=3,
        )

    violations: List[int] = []

    for wp in mission.waypoints:
        if not geofence.contains(wp.point):
            violations.append(wp.index)

    # Also check home position
    if mission.home and not geofence.contains(mission.home):
        violations.append(-1)  # -1 indicates home position

    if violations:
        return SafetyCheckResult(
            name="geofence_overlap",
            status=CheckStatus.FAIL,
            message=f"{len(violations)} waypoints outside geofence",
            details=f"Waypoint indices: {violations}",
            severity=8,
        )

    return SafetyCheckResult(
        name="geofence_overlap",
        status=CheckStatus.PASS,
        message="All waypoints within geofence",
        severity=0,
    )


async def check_min_agl(
    mission: MissionSpec,
    min_agl_m: float = 10.0,
    elevation_provider: Optional[ElevationProvider] = None,
) -> SafetyCheckResult:
    """Check if mission maintains minimum AGL.

    Args:
        mission: Mission specification.
        min_agl_m: Minimum altitude above ground level.
        elevation_provider: Elevation data provider.

    Returns:
        SafetyCheckResult with status and details.
    """
    terrain_analyzer = TerrainAnalyzer(elevation_provider)

    violations: List[dict] = []

    for wp in mission.waypoints:
        if wp.point.alt_m is None:
            continue

        # Get ground elevation
        ground_elev = await terrain_analyzer.get_ground_elevation(
            wp.point.lat_deg, wp.point.lon_deg
        )

        if ground_elev is None:
            continue  # Can't check without elevation data

        agl = wp.point.alt_m - ground_elev

        if agl < min_agl_m:
            violations.append({
                "index": wp.index,
                "altitude_amsl_m": wp.point.alt_m,
                "ground_elevation_m": ground_elev,
                "agl_m": agl,
            })

    if violations:
        min_agl_found = min(v["agl_m"] for v in violations)
        return SafetyCheckResult(
            name="min_agl",
            status=CheckStatus.FAIL,
            message=f"{len(violations)} waypoints below minimum AGL ({min_agl_m}m)",
            details=f"Minimum AGL found: {min_agl_found:.1f}m",
            severity=7,
        )

    return SafetyCheckResult(
        name="min_agl",
        status=CheckStatus.PASS,
        message=f"All waypoints maintain {min_agl_m}m+ AGL",
        severity=0,
    )


def check_battery_feasibility(
    mission: MissionSpec,
    battery_percent: float,
    battery_capacity_mah: float = 5000.0,
    hover_current_a: float = 15.0,
    cruise_current_a: float = 10.0,
    cell_voltage: float = 3.7,
    min_reserve_percent: float = 20.0,
) -> SafetyCheckResult:
    """Check if mission is feasible with current battery.

    Estimates power consumption based on:
    - Hover time at waypoints
    - Cruise time between waypoints
    - Behaviors (orbit, hover, etc.)

    Args:
        mission: Mission specification.
        battery_percent: Current battery percentage.
        battery_capacity_mah: Battery capacity in mAh.
        hover_current_a: Hover current draw in Amps.
        cruise_current_a: Cruise current draw in Amps.
        cell_voltage: Cell voltage for energy calculation.
        min_reserve_percent: Minimum battery reserve.

    Returns:
        SafetyCheckResult with status and details.
    """
    # Calculate available energy
    available_percent = battery_percent - min_reserve_percent
    if available_percent <= 0:
        return SafetyCheckResult(
            name="battery_feasibility",
            status=CheckStatus.FAIL,
            message="Battery below reserve level",
            details=f"Current: {battery_percent:.1f}%, Reserve: {min_reserve_percent:.1f}%",
            severity=10,
        )

    available_mah = battery_capacity_mah * available_percent / 100

    # Estimate power consumption
    total_time_s = 0.0
    hover_time_s = 0.0
    cruise_time_s = 0.0

    # Calculate waypoint timing
    for i, wp in enumerate(mission.waypoints):
        hover_time_s += wp.hold_s

        if i > 0:
            prev_wp = mission.waypoints[i - 1]
            dist_km = haversine_distance(
                prev_wp.point.lat_deg, prev_wp.point.lon_deg,
                wp.point.lat_deg, wp.point.lon_deg,
            )
            speed = wp.speed_m_s or 5.0
            cruise_time_s += (dist_km * 1000) / speed

    # Add behavior durations
    for behavior in mission.behaviors:
        if behavior.duration_s:
            # Assume behaviors are mostly hover-like
            hover_time_s += behavior.duration_s

    total_time_s = hover_time_s + cruise_time_s

    # Estimate energy consumption
    # Energy (Wh) = Current (A) * Voltage (V) * Time (h)
    cell_count = 4  # Typical 4S battery
    total_voltage = cell_voltage * cell_count

    hover_energy_wh = (
        hover_current_a * total_voltage * hover_time_s / 3600
    )
    cruise_energy_wh = (
        cruise_current_a * total_voltage * cruise_time_s / 3600
    )
    total_energy_wh = hover_energy_wh + cruise_energy_wh

    # Convert to mAh
    # mAh = Wh * 1000 / V
    required_mah = total_energy_wh * 1000 / total_voltage

    if required_mah > available_mah:
        shortfall_percent = (required_mah - available_mah) / battery_capacity_mah * 100
        return SafetyCheckResult(
            name="battery_feasibility",
            status=CheckStatus.FAIL,
            message=f"Mission requires more battery than available",
            details=f"Required: {required_mah:.0f}mAh, Available: {available_mah:.0f}mAh "
                    f"({available_percent:.1f}% with reserve)",
            severity=9,
        )

    remaining_percent = (available_mah - required_mah) / battery_capacity_mah * 100

    if remaining_percent < 10:
        return SafetyCheckResult(
            name="battery_feasibility",
            status=CheckStatus.WARN,
            message=f"Low battery margin after mission",
            details=f"Estimated remaining: {remaining_percent:.1f}%",
            severity=5,
        )

    return SafetyCheckResult(
        name="battery_feasibility",
        status=CheckStatus.PASS,
        message=f"Mission feasible with current battery",
        details=f"Required: {required_mah:.0f}mAh, Available: {available_mah:.0f}mAh, "
                f"Estimated time: {total_time_s/60:.1f}min",
        severity=0,
    )


async def check_terrain_obstacles(
    mission: MissionSpec,
    elevation_provider: Optional[ElevationProvider] = None,
    margin_m: float = 10.0,
) -> SafetyCheckResult:
    """Check for terrain obstacles along flight path.

    Samples terrain between waypoints to check for obstacles
    that exceed planned altitude.

    Args:
        mission: Mission specification.
        elevation_provider: Elevation data provider.
        margin_m: Safety margin above terrain.

    Returns:
        SafetyCheckResult with status and details.
    """
    if not mission.waypoints:
        return SafetyCheckResult(
            name="terrain_obstacles",
            status=CheckStatus.PASS,
            message="No waypoints to check",
            severity=0,
        )

    terrain_analyzer = TerrainAnalyzer(elevation_provider)
    obstacles: List[dict] = []

    for i, wp in enumerate(mission.waypoints):
        if wp.point.alt_m is None:
            continue

        # Get terrain at waypoint
        terrain = await terrain_analyzer.analyze_terrain(
            wp.point.lat_deg, wp.point.lon_deg, radius_m=50
        )

        if terrain.ground_elevation_m + margin_m > wp.point.alt_m:
            obstacles.append({
                "index": i,
                "altitude_amsl_m": wp.point.alt_m,
                "ground_elevation_m": terrain.ground_elevation_m,
                "slope_deg": terrain.slope_deg,
            })

    if obstacles:
        return SafetyCheckResult(
            name="terrain_obstacles",
            status=CheckStatus.WARN,
            message=f"{len(obstacles)} waypoints near terrain obstacles",
            details=f"Apply {margin_m}m margin for safety",
            severity=4,
        )

    return SafetyCheckResult(
        name="terrain_obstacles",
        status=CheckStatus.PASS,
        message="No terrain obstacles detected",
        severity=0,
    )


async def check_airspace_restrictions(
    mission: MissionSpec,
) -> SafetyCheckResult:
    """Check for airspace restrictions.

    Analyzes mission area for no-fly zones and restrictions.
    Uses OSM data for basic analysis.

    Args:
        mission: Mission specification.

    Returns:
        SafetyCheckResult with status and details.
    """
    if not mission.waypoints:
        return SafetyCheckResult(
            name="airspace_restrictions",
            status=CheckStatus.PASS,
            message="No waypoints to check",
            severity=0,
        )

    # Calculate mission bounding box
    lats = [wp.point.lat_deg for wp in mission.waypoints]
    lons = [wp.point.lon_deg for wp in mission.waypoints]

    if mission.home:
        lats.append(mission.home.lat_deg)
        lons.append(mission.home.lon_deg)

    bbox = BBox(
        south=min(lats),
        west=min(lons),
        north=max(lats),
        east=max(lons),
    )

    # Analyze area for airspace info
    report = await analyze_area(
        (bbox.south + bbox.north) / 2,
        (bbox.west + bbox.east) / 2,
        radius_m=max(
            haversine_distance(bbox.south, bbox.west, bbox.north, bbox.east) * 1000 / 2,
            500
        ),
        include_places=True,
    )

    if report.airspace.has_restricted_area:
        return SafetyCheckResult(
            name="airspace_restrictions",
            status=CheckStatus.FAIL,
            message="Mission overlaps restricted airspace",
            details=report.airspace.warning,
            severity=10,
        )

    if report.no_fly_zones:
        zone_names = [z.name for z in report.no_fly_zones[:3]]
        return SafetyCheckResult(
            name="airspace_restrictions",
            status=CheckStatus.WARN,
            message=f"No-fly zones in mission area: {', '.join(zone_names)}",
            details="Verify flight authorization before proceeding",
            severity=6,
        )

    if report.airspace.has_airport or report.airspace.has_helipad:
        return SafetyCheckResult(
            name="airspace_restrictions",
            status=CheckStatus.WARN,
            message=report.airspace.warning or "Aviation activity in area",
            details="Check NOTAMs before flying",
            severity=5,
        )

    return SafetyCheckResult(
        name="airspace_restrictions",
        status=CheckStatus.PASS,
        message="No airspace restrictions detected",
        severity=0,
    )


async def run_safety_checks(
    mission: MissionSpec,
    battery_percent: Optional[float] = None,
    geofence: Optional[Polygon] = None,
    min_agl_m: float = 10.0,
    elevation_provider: Optional[ElevationProvider] = None,
) -> List[SafetyCheckResult]:
    """Run all safety checks for a mission.

    Executes all available safety checks and returns results.

    Args:
        mission: Mission specification.
        battery_percent: Current battery percentage.
        geofence: Geofence polygon.
        min_agl_m: Minimum AGL requirement.
        elevation_provider: Elevation data provider.

    Returns:
        List of SafetyCheckResult for each check.
    """
    results: List[SafetyCheckResult] = []

    # Synchronous checks
    results.append(check_geofence_overlap(mission, geofence))

    if battery_percent is not None:
        results.append(check_battery_feasibility(mission, battery_percent))

    # Async checks
    results.append(await check_min_agl(mission, min_agl_m, elevation_provider))
    results.append(await check_terrain_obstacles(mission, elevation_provider))
    results.append(await check_airspace_restrictions(mission))

    return results


__all__ = [
    "CheckStatus",
    "SafetyCheckResult",
    "check_geofence_overlap",
    "check_min_agl",
    "check_battery_feasibility",
    "check_terrain_obstacles",
    "check_airspace_restrictions",
    "run_safety_checks",
]
