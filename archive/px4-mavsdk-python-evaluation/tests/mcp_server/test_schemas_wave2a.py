# tests/mcp_server/test_schemas_wave2a.py
import pytest
from pydantic import ValidationError

from avatar.mcp_server.schemas import (
    Mission,
    Point,
    Waypoint,
    Polygon,
    BBox,
    HardLimitsSchema,
    FlightMode,
    CheckResult,
    BehaviorBlock,
    BehaviorHover,
    BehaviorPhoto,
    BehaviorOrbit,
    BehaviorCinematic,
)


def test_mission_json_schema_has_version_and_waypoints():
    s = Mission.model_json_schema()
    assert s["properties"]["version"]["const"] == "1.0"
    assert "waypoints" in s["properties"]


def test_behavior_block_discriminated_union():
    h = BehaviorBlock.model_validate({"kind": "hover", "duration_s": 2.0})
    assert isinstance(h.root, BehaviorHover)
    o = BehaviorBlock.model_validate(
        {"kind": "orbit", "radius_m": 10.0, "speed_m_s": 3.0, "duration_s": 30.0}
    )
    assert isinstance(o.root, BehaviorOrbit)
    p = BehaviorBlock.model_validate({"kind": "photo", "dwell_s": 2.0})
    assert isinstance(p.root, BehaviorPhoto)
    c = BehaviorBlock.model_validate({"kind": "cinematic", "template_id": "orbit", "target": {"lat_deg": 0, "lon_deg": 0}})
    assert isinstance(c.root, BehaviorCinematic)
    with pytest.raises(ValidationError):
        BehaviorBlock.model_validate({"kind": "orbit", "duration_s": 1.0})


def test_polygon_requires_three_vertices():
    with pytest.raises(ValidationError):
        Polygon(vertices=[Point(lat_deg=0, lon_deg=0), Point(lat_deg=1, lon_deg=0)])


def test_point_validation():
    p = Point(lat_deg=45.0, lon_deg=-75.0, alt_m=100.0)
    assert p.lat_deg == 45.0
    assert p.lon_deg == -75.0
    with pytest.raises(ValidationError):
        Point(lat_deg=100.0, lon_deg=0.0)  # lat out of range


def test_bbox_validation():
    b = BBox(x=0.5, y=0.5, w=0.1, h=0.1)
    assert b.x == 0.5
    with pytest.raises(ValidationError):
        BBox(x=1.5, y=0.5, w=0.1, h=0.1)  # x out of range


def test_hard_limits_defaults():
    h = HardLimitsSchema()
    assert h.max_altitude_amsl_m == 120.0
    assert h.max_distance_from_home_m == 500.0
