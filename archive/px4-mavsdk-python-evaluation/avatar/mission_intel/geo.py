"""Geographic primitives and utilities.

Provides Point, BBox, Polygon primitives and common geographic calculations.
All coordinates use WGS84 (EPSG:4326).

Core Functions:
    - haversine_distance: Great-circle distance between two points
    - haversine_bearing: Initial bearing from one point to another
    - destination_point: Point at given distance and bearing from origin
    - generate_circle_grid: Grid points in a circular pattern
    - generate_spiral_grid: Grid points in a spiral pattern

Usage:
    from avatar.mission_intel.geo import Point, haversine_distance

    # Distance between two points
    dist_km = haversine_distance(37.7749, -122.4194, 37.8044, -122.2712)

    # Destination from bearing
    dest = destination_point(37.7749, -122.4194, bearing_deg=45, distance_m=1000)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class Point:
    """WGS84 geographic point.

    Attributes:
        lat_deg: Latitude in degrees (-90 to 90).
        lon_deg: Longitude in degrees (-180 to 180).
        alt_m: Optional altitude in meters (AMSL or AGL depending on context).
    """

    lat_deg: float
    lon_deg: float
    alt_m: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate coordinate ranges."""
        if not -90 <= self.lat_deg <= 90:
            raise ValueError(f"Latitude must be in [-90, 90], got {self.lat_deg}")
        if not -180 <= self.lon_deg <= 180:
            raise ValueError(f"Longitude must be in [-180, 180], got {self.lon_deg}")

    def to_tuple(self) -> Tuple[float, float]:
        """Return (lat, lon) tuple."""
        return (self.lat_deg, self.lon_deg)

    def to_tuple_3d(self) -> Tuple[float, float, Optional[float]]:
        """Return (lat, lon, alt) tuple."""
        return (self.lat_deg, self.lon_deg, self.alt_m)

    @classmethod
    def from_tuple(cls, coords: Tuple[float, float], alt_m: Optional[float] = None) -> "Point":
        """Create Point from (lat, lon) tuple."""
        return cls(lat_deg=coords[0], lon_deg=coords[1], alt_m=alt_m)


@dataclass(frozen=True, slots=True)
class BBox:
    """Geographic bounding box.

    Attributes:
        south: South latitude (minimum lat).
        west: West longitude (minimum lon).
        north: North latitude (maximum lat).
        east: East longitude (maximum lon).
    """

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        """Validate bounding box."""
        if not self.south <= self.north:
            raise ValueError(f"South ({self.south}) must be <= north ({self.north})")
        if not -90 <= self.south <= 90 and not -90 <= self.north <= 90:
            raise ValueError("Latitudes must be in [-90, 90]")

    @classmethod
    def from_center_radius(
        cls, center_lat: float, center_lon: float, radius_m: float
    ) -> "BBox":
        """Create BBox from center point and radius in meters.

        Args:
            center_lat: Center latitude in degrees.
            center_lon: Center longitude in degrees.
            radius_m: Radius in meters.

        Returns:
            BBox enclosing the circle.
        """
        # Approximate degrees per meter at this latitude
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))

        lat_offset = radius_m * lat_deg_per_m
        lon_offset = radius_m * lon_deg_per_m

        return cls(
            south=center_lat - lat_offset,
            west=center_lon - lon_offset,
            north=center_lat + lat_offset,
            east=center_lon + lon_offset,
        )

    def center(self) -> Point:
        """Return the center point of the bounding box."""
        return Point(
            lat_deg=(self.south + self.north) / 2,
            lon_deg=(self.west + self.east) / 2,
        )

    def width_km(self) -> float:
        """Return the width of the bounding box in kilometers."""
        center_lat = (self.south + self.north) / 2
        return haversine_distance(
            center_lat, self.west,
            center_lat, self.east,
        )

    def height_km(self) -> float:
        """Return the height of the bounding box in kilometers."""
        center_lon = (self.west + self.east) / 2
        return haversine_distance(
            self.south, center_lon,
            self.north, center_lon,
        )


@dataclass(frozen=True, slots=True)
class Polygon:
    """Geographic polygon with optional altitude constraints.

    Attributes:
        vertices: List of points forming the polygon (closed or open).
        min_altitude_amsl_m: Optional minimum altitude constraint.
        max_altitude_amsl_m: Optional maximum altitude constraint.
    """

    vertices: Tuple[Point, ...]
    min_altitude_amsl_m: Optional[float] = None
    max_altitude_amsl_m: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate polygon has at least 3 vertices."""
        if len(self.vertices) < 3:
            raise ValueError(f"Polygon must have at least 3 vertices, got {len(self.vertices)}")

    @classmethod
    def from_points(cls, points: List[Point], **kwargs: float) -> "Polygon":
        """Create Polygon from list of points."""
        return cls(vertices=tuple(points), **kwargs)  # type: ignore

    def contains(self, point: Point) -> bool:
        """Check if point is inside polygon using ray casting.

        Args:
            point: Point to check.

        Returns:
            True if point is inside polygon.
        """
        x, y = point.lon_deg, point.lat_deg
        n = len(self.vertices)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = self.vertices[i].lon_deg, self.vertices[i].lat_deg
            xj, yj = self.vertices[j].lon_deg, self.vertices[j].lat_deg

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i

        return inside

    def to_bbox(self) -> BBox:
        """Return the bounding box enclosing this polygon."""
        lats = [v.lat_deg for v in self.vertices]
        lons = [v.lon_deg for v in self.vertices]
        return BBox(
            south=min(lats),
            west=min(lons),
            north=max(lats),
            east=max(lons),
        )


def haversine_distance(
    lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float
) -> float:
    """Calculate great-circle distance between two points.

    Uses the Haversine formula for spherical Earth approximation.

    Args:
        lat1_deg: Latitude of first point in degrees.
        lon1_deg: Longitude of first point in degrees.
        lat2_deg: Latitude of second point in degrees.
        lon2_deg: Longitude of second point in degrees.

    Returns:
        Distance in kilometers.

    Example:
        >>> haversine_distance(37.7749, -122.4194, 37.8044, -122.2712)
        13.2  # approximately
    """
    # Earth's radius in kilometers
    R = 6371.0

    lat1 = math.radians(lat1_deg)
    lat2 = math.radians(lat2_deg)
    lon1 = math.radians(lon1_deg)
    lon2 = math.radians(lon2_deg)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def haversine_bearing(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    """Calculate initial bearing from one point to another.

    Args:
        lat1_deg: Latitude of start point in degrees.
        lon1_deg: Longitude of start point in degrees.
        lat2_deg: Latitude of end point in degrees.
        lon2_deg: Longitude of end point in degrees.

    Returns:
        Initial bearing in degrees (0-360, 0=North, 90=East).
    """
    lat1 = math.radians(lat1_deg)
    lat2 = math.radians(lat2_deg)
    dlon = math.radians(lon2_deg - lon1_deg)

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(x, y)
    bearing_deg = math.degrees(bearing)

    # Normalize to 0-360
    return (bearing_deg + 360) % 360


def destination_point(
    lat_deg: float, lon_deg: float, bearing_deg: float, distance_m: float
) -> Point:
    """Calculate destination point from start, bearing, and distance.

    Args:
        lat_deg: Start latitude in degrees.
        lon_deg: Start longitude in degrees.
        bearing_deg: Bearing in degrees (0=North, 90=East).
        distance_m: Distance in meters.

    Returns:
        Destination Point.
    """
    # Earth's radius in meters
    R = 6371000.0

    lat1 = math.radians(lat_deg)
    lon1 = math.radians(lon_deg)
    bearing = math.radians(bearing_deg)

    d = distance_m / R

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )

    return Point(lat_deg=math.degrees(lat2), lon_deg=math.degrees(lon2))


def generate_circle_grid(
    center: Point, radius_m: float, points_per_ring: int = 8, num_rings: int = 5
) -> Iterator[Point]:
    """Generate points in concentric circles around a center point.

    Args:
        center: Center point of the grid.
        radius_m: Outer radius in meters.
        points_per_ring: Number of points per ring.
        num_rings: Number of concentric rings.

    Yields:
        Points in the grid pattern.
    """
    yield center  # Center point first

    for ring in range(1, num_rings + 1):
        ring_radius = radius_m * ring / num_rings
        for i in range(points_per_ring):
            bearing = 360.0 * i / points_per_ring
            yield destination_point(
                center.lat_deg, center.lon_deg, bearing, ring_radius
            )


def generate_spiral_grid(
    center: Point, max_radius_m: float, num_points: int = 50
) -> Iterator[Point]:
    """Generate points in an expanding spiral pattern.

    Useful for search and rescue operations.

    Args:
        center: Center point of the spiral.
        max_radius_m: Maximum radius in meters.
        num_points: Number of points in the spiral.

    Yields:
        Points in the spiral pattern.
    """
    for i in range(num_points):
        # Archimedean spiral: r = a + b * theta
        theta = i * 0.5  # Angle in radians
        r = max_radius_m * theta / (num_points * 0.5)  # Radius

        # Clamp radius
        r = min(r, max_radius_m)

        # Convert to bearing
        bearing = math.degrees(theta) % 360

        yield destination_point(center.lat_deg, center.lon_deg, bearing, r)


__all__ = [
    "Point",
    "BBox",
    "Polygon",
    "haversine_distance",
    "haversine_bearing",
    "destination_point",
    "generate_circle_grid",
    "generate_spiral_grid",
]
