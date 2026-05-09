"""GPS path helpers for the dashboard.

These helpers intentionally do not depend on a map renderer. They turn MAVSDK
GPS telemetry into path metrics and local meter coordinates that can feed a
future map, minimap, mission preview, or flight-path planner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True, slots=True)
class GpsPoint:
    """A geodetic point from drone telemetry."""

    lat_deg: float
    lon_deg: float
    alt_m: float | None = None
    timestamp: float | None = None


@dataclass(frozen=True, slots=True)
class LocalPoint:
    """Local tangent-plane point in meters relative to a reference GPS point."""

    north_m: float
    east_m: float
    up_m: float | None = None


@dataclass(frozen=True, slots=True)
class PathSummary:
    """Dashboard-friendly GPS path metrics."""

    point_count: int
    total_distance_m: float
    displacement_m: float
    bearing_deg: float | None
    min_alt_m: float | None
    max_alt_m: float | None
    local_points: list[LocalPoint]


def haversine_m(a: GpsPoint, b: GpsPoint) -> float:
    """Great-circle distance between two GPS points in meters."""

    lat1 = math.radians(a.lat_deg)
    lat2 = math.radians(b.lat_deg)
    d_lat = lat2 - lat1
    d_lon = math.radians(b.lon_deg - a.lon_deg)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a: GpsPoint, b: GpsPoint) -> float:
    """Initial bearing from point a to b in degrees clockwise from north."""

    lat1 = math.radians(a.lat_deg)
    lat2 = math.radians(b.lat_deg)
    d_lon = math.radians(b.lon_deg - a.lon_deg)
    y = math.sin(d_lon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def to_local_m(point: GpsPoint, origin: GpsPoint) -> LocalPoint:
    """Project GPS to a local north/east/up approximation around origin."""

    d_lat = math.radians(point.lat_deg - origin.lat_deg)
    d_lon = math.radians(point.lon_deg - origin.lon_deg)
    mean_lat = math.radians((point.lat_deg + origin.lat_deg) / 2)
    north_m = d_lat * EARTH_RADIUS_M
    east_m = d_lon * EARTH_RADIUS_M * math.cos(mean_lat)
    up_m = None
    if point.alt_m is not None and origin.alt_m is not None:
        up_m = point.alt_m - origin.alt_m
    return LocalPoint(north_m=north_m, east_m=east_m, up_m=up_m)


def summarize_path(points: list[GpsPoint]) -> PathSummary:
    """Summarize a GPS path without requiring a map provider."""

    if not points:
        return PathSummary(0, 0.0, 0.0, None, None, None, [])

    total = sum(haversine_m(a, b) for a, b in zip(points, points[1:]))
    displacement = haversine_m(points[0], points[-1]) if len(points) > 1 else 0.0
    bearing = bearing_deg(points[0], points[-1]) if len(points) > 1 else None
    altitudes = [p.alt_m for p in points if p.alt_m is not None]

    return PathSummary(
        point_count=len(points),
        total_distance_m=total,
        displacement_m=displacement,
        bearing_deg=bearing,
        min_alt_m=min(altitudes) if altitudes else None,
        max_alt_m=max(altitudes) if altitudes else None,
        local_points=[to_local_m(point, points[0]) for point in points],
    )

