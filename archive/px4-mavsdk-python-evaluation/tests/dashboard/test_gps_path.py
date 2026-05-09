"""Tests for dashboard GPS path scaffolding."""

from avatar.dashboard.gps_path import GpsPoint, bearing_deg, haversine_m, summarize_path, to_local_m


def test_haversine_and_bearing_for_small_north_move() -> None:
    origin = GpsPoint(lat_deg=47.397742, lon_deg=8.545594, alt_m=500.0)
    north = GpsPoint(lat_deg=47.398642, lon_deg=8.545594, alt_m=510.0)

    assert 99.0 < haversine_m(origin, north) < 101.0
    assert bearing_deg(origin, north) < 1.0 or bearing_deg(origin, north) > 359.0


def test_local_projection_tracks_north_east_up() -> None:
    origin = GpsPoint(lat_deg=47.397742, lon_deg=8.545594, alt_m=500.0)
    point = GpsPoint(lat_deg=47.398642, lon_deg=8.546920, alt_m=512.0)

    local = to_local_m(point, origin)

    assert 99.0 < local.north_m < 101.0
    assert 99.0 < local.east_m < 101.0
    assert local.up_m == 12.0


def test_summarize_path_returns_metrics_and_local_points() -> None:
    points = [
        GpsPoint(47.397742, 8.545594, 500.0),
        GpsPoint(47.398192, 8.545594, 505.0),
        GpsPoint(47.398192, 8.546257, 508.0),
    ]

    summary = summarize_path(points)

    assert summary.point_count == 3
    assert 99.0 < summary.total_distance_m < 101.0
    assert summary.displacement_m > 70.0
    assert summary.bearing_deg is not None
    assert summary.min_alt_m == 500.0
    assert summary.max_alt_m == 508.0
    assert len(summary.local_points) == 3

