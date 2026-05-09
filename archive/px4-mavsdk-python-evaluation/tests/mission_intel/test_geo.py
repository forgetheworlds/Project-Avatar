"""Tests for mission_intel.geo module."""

import math
import pytest

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


class TestPoint:
    """Tests for Point class."""

    def test_create_point(self):
        """Test creating a point."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194)
        assert point.lat_deg == 37.7749
        assert point.lon_deg == -122.4194
        assert point.alt_m is None

    def test_create_point_with_altitude(self):
        """Test creating a point with altitude."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=100.0)
        assert point.alt_m == 100.0

    def test_invalid_latitude(self):
        """Test that invalid latitude raises error."""
        with pytest.raises(ValueError):
            Point(lat_deg=91.0, lon_deg=0.0)

        with pytest.raises(ValueError):
            Point(lat_deg=-91.0, lon_deg=0.0)

    def test_invalid_longitude(self):
        """Test that invalid longitude raises error."""
        with pytest.raises(ValueError):
            Point(lat_deg=0.0, lon_deg=181.0)

        with pytest.raises(ValueError):
            Point(lat_deg=0.0, lon_deg=-181.0)

    def test_to_tuple(self):
        """Test converting to tuple."""
        point = Point(lat_deg=37.7749, lon_deg=-122.4194)
        assert point.to_tuple() == (37.7749, -122.4194)

    def test_from_tuple(self):
        """Test creating from tuple."""
        point = Point.from_tuple((37.7749, -122.4194), alt_m=100.0)
        assert point.lat_deg == 37.7749
        assert point.lon_deg == -122.4194
        assert point.alt_m == 100.0


class TestBBox:
    """Tests for BBox class."""

    def test_create_bbox(self):
        """Test creating a bounding box."""
        bbox = BBox(south=37.0, west=-123.0, north=38.0, east=-122.0)
        assert bbox.south == 37.0
        assert bbox.west == -123.0
        assert bbox.north == 38.0
        assert bbox.east == -122.0

    def test_invalid_bbox(self):
        """Test that invalid bbox raises error."""
        with pytest.raises(ValueError):
            BBox(south=38.0, west=-123.0, north=37.0, east=-122.0)

    def test_from_center_radius(self):
        """Test creating bbox from center and radius."""
        bbox = BBox.from_center_radius(37.7749, -122.4194, 500)
        assert bbox.south < 37.7749
        assert bbox.north > 37.7749
        assert bbox.west < -122.4194
        assert bbox.east > -122.4194

    def test_center(self):
        """Test getting center point."""
        bbox = BBox(south=37.0, west=-123.0, north=38.0, east=-122.0)
        center = bbox.center()
        assert center.lat_deg == 37.5
        assert center.lon_deg == -122.5


class TestPolygon:
    """Tests for Polygon class."""

    def test_create_polygon(self):
        """Test creating a polygon."""
        vertices = [
            Point(lat_deg=0.0, lon_deg=0.0),
            Point(lat_deg=0.0, lon_deg=1.0),
            Point(lat_deg=1.0, lon_deg=1.0),
            Point(lat_deg=1.0, lon_deg=0.0),
        ]
        polygon = Polygon(vertices=tuple(vertices))
        assert len(polygon.vertices) == 4

    def test_polygon_needs_three_vertices(self):
        """Test that polygon needs at least 3 vertices."""
        with pytest.raises(ValueError):
            Polygon(vertices=(Point(lat_deg=0, lon_deg=0), Point(lat_deg=0, lon_deg=1)))

    def test_contains_point(self):
        """Test point-in-polygon check."""
        # Simple square polygon
        vertices = [
            Point(lat_deg=0.0, lon_deg=0.0),
            Point(lat_deg=0.0, lon_deg=2.0),
            Point(lat_deg=2.0, lon_deg=2.0),
            Point(lat_deg=2.0, lon_deg=0.0),
        ]
        polygon = Polygon(vertices=tuple(vertices))

        # Point inside
        inside_point = Point(lat_deg=1.0, lon_deg=1.0)
        assert polygon.contains(inside_point)

        # Point outside
        outside_point = Point(lat_deg=3.0, lon_deg=3.0)
        assert not polygon.contains(outside_point)


class TestHaversine:
    """Tests for haversine functions."""

    def test_haversine_distance_same_point(self):
        """Test distance between same point."""
        dist = haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert dist == pytest.approx(0.0, abs=0.001)

    def test_haversine_distance_san_francisco_to_oakland(self):
        """Test distance between San Francisco and Oakland."""
        # Distance should be approximately 13 km
        dist = haversine_distance(37.7749, -122.4194, 37.8044, -122.2712)
        assert dist == pytest.approx(13.2, abs=1.0)

    def test_haversine_bearing_north(self):
        """Test bearing to north."""
        bearing = haversine_bearing(0.0, 0.0, 1.0, 0.0)
        assert bearing == pytest.approx(0.0, abs=1.0)

    def test_haversine_bearing_east(self):
        """Test bearing to east."""
        bearing = haversine_bearing(0.0, 0.0, 0.0, 1.0)
        assert bearing == pytest.approx(90.0, abs=1.0)

    def test_destination_point_north(self):
        """Test destination point north."""
        dest = destination_point(0.0, 0.0, 0.0, 1000)  # 1km north
        assert dest.lat_deg > 0.0
        assert dest.lon_deg == pytest.approx(0.0, abs=0.001)

    def test_destination_distance_consistency(self):
        """Test that destination and distance are consistent."""
        start_lat, start_lon = 37.7749, -122.4194
        bearing = 45.0
        distance = 1000

        dest = destination_point(start_lat, start_lon, bearing, distance)
        dist = haversine_distance(start_lat, start_lon, dest.lat_deg, dest.lon_deg) * 1000

        assert dist == pytest.approx(distance, abs=10)


class TestGridGeneration:
    """Tests for grid generation functions."""

    def test_generate_circle_grid(self):
        """Test circle grid generation."""
        center = Point(lat_deg=37.7749, lon_deg=-122.4194)
        points = list(generate_circle_grid(center, radius_m=100, points_per_ring=4, num_rings=2))

        # Should have center + (2 rings * 4 points each) = 9 points
        assert len(points) == 9

        # First point should be center
        assert points[0].lat_deg == center.lat_deg
        assert points[0].lon_deg == center.lon_deg

    def test_generate_spiral_grid(self):
        """Test spiral grid generation."""
        center = Point(lat_deg=37.7749, lon_deg=-122.4194)
        points = list(generate_spiral_grid(center, max_radius_m=100, num_points=20))

        assert len(points) == 20

        # First point should be at or near center
        assert points[0].lat_deg == pytest.approx(center.lat_deg, abs=0.001)
