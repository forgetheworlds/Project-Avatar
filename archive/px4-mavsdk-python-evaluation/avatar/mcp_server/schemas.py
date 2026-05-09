# avatar/mcp_server/schemas.py
# W2b extends Mission / constraints / safety with mission_intel validators — keep fields minimal here.
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class Point(BaseModel):
    """Geodetic point; alt_m is AMSL meters when used as home."""

    model_config = ConfigDict(extra="forbid")

    lat_deg: float = Field(..., ge=-90, le=90)
    lon_deg: float = Field(..., ge=-180, le=180)
    alt_m: Optional[float] = Field(default=None, description="AMSL altitude in meters")


class Waypoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    point: Point
    hold_s: float = Field(default=0.0, ge=0.0)
    speed_m_s: Optional[float] = Field(default=None, ge=0.1, le=25.0)


class MissionConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_altitude_amsl_m: Optional[float] = Field(default=None, ge=1.0, le=500.0)
    max_speed_m_s: Optional[float] = Field(default=None, ge=0.5, le=40.0)


class CinematicInvocation(BaseModel):
    model_config = ConfigDict(extra="allow")

    template_id: str
    target: Point


class SafetyPolicy(BaseModel):
    model_config = ConfigDict(extra="allow")

    rtl_on_low_battery: bool = True
    min_battery_percent: float = Field(default=20.0, ge=5.0, le=95.0)


class Mission(BaseModel):
    """Minimal Mission v1.0 subset for upload_mission / load_plan (W2a)."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    name: str = Field(..., min_length=1, max_length=256)
    home: Point
    waypoints: list[Waypoint] = Field(default_factory=list)
    constraints: Optional[MissionConstraints] = None
    cinematic_blocks: list[CinematicInvocation] = Field(default_factory=list)
    safety: Optional[SafetyPolicy] = None

    @model_validator(mode="after")
    def _waypoint_indices_order(self) -> "Mission":
        for i, wp in enumerate(self.waypoints):
            if wp.index != i:
                raise ValueError(f"waypoints[{i}].index must equal {i}, got {wp.index}")
        return self


class Polygon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vertices: list[Point] = Field(..., min_length=3)
    min_altitude_amsl_m: Optional[float] = Field(default=None)
    max_altitude_amsl_m: Optional[float] = Field(default=None)


class BBox(BaseModel):
    """Normalized bbox: x_center, y_center, width, height in 0..1."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)


class HardLimitsSchema(BaseModel):
    """Serializable guardian limits (AMSL altitude domain per spec)."""

    model_config = ConfigDict(extra="forbid")

    max_altitude_amsl_m: float = Field(default=120.0, gt=0.0)
    max_distance_from_home_m: float = Field(default=500.0, gt=0.0)
    min_battery_rtl_percent: float = Field(default=25.0, ge=0.0, le=100.0)
    heartbeat_timeout_s: float = Field(default=2.0, gt=0.0)
    max_speed_m_s: float = Field(default=15.0, gt=0.0)


FlightMode = Literal[
    "UNKNOWN",
    "MANUAL",
    "STABILIZED",
    "ALTCTL",
    "POSCTL",
    "OFFBOARD",
    "AUTO_MISSION",
    "AUTO_LOITER",
    "AUTO_RTL",
    "ACRO",
    "ORBIT",
    "HOLD",
]


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str = ""


class BehaviorHover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["hover"] = "hover"
    duration_s: float = Field(..., gt=0.0, le=600.0)


class BehaviorPhoto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["photo"] = "photo"
    dwell_s: float = Field(default=1.0, gt=0.0, le=30.0)


class BehaviorOrbit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["orbit"] = "orbit"
    radius_m: float = Field(..., gt=1.0, le=200.0)
    speed_m_s: float = Field(..., gt=0.2, le=20.0)
    duration_s: float = Field(..., gt=1.0, le=900.0)


class BehaviorCinematic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cinematic"] = "cinematic"
    template_id: str = Field(..., min_length=1)
    target: Point


_BehaviorBlockUnion = Annotated[
    Union[BehaviorHover, BehaviorPhoto, BehaviorOrbit, BehaviorCinematic],
    Field(discriminator="kind"),
]


class BehaviorBlock(RootModel[_BehaviorBlockUnion]):
    """Pydantic v2 discriminated union wrapper; validates via 'kind' field."""

    pass  # RootModel provides model_validate via root field


class TrackerState(BaseModel):
    """MCP-facing copy of Kalman-style state (NED meters)."""

    model_config = ConfigDict(extra="forbid")

    x_m: float
    y_m: float
    z_m: float
    vx_m_s: float
    vy_m_s: float
    vz_m_s: float
    ax_m_s2: float
    ay_m_s2: float
    az_m_s2: float
    timestamp: float
    confidence: float = Field(..., ge=0.0, le=1.0)
