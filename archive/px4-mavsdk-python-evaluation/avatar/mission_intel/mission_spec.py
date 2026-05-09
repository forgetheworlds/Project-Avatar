"""Mission specification schema for mission planning.

Extends the base schemas from avatar.mcp_server.schemas with
additional fields for mission planning and waypoint management.

Usage:
    from avatar.mission_intel.mission_spec import MissionSpec, WaypointSpec

    mission = MissionSpec(
        name="Survey Mission",
        waypoints=[
            WaypointSpec(index=0, point=Point(lat_deg=37.7749, lon_deg=-122.4194)),
        ],
    )
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

from avatar.mcp_server.schemas import Point


class WaypointSpec(BaseModel):
    """Waypoint specification for mission planning.

    Attributes:
        index: Waypoint index (0-based, sequential).
        point: Geographic coordinates with optional altitude.
        hold_s: Hold time at waypoint in seconds.
        speed_m_s: Flight speed to waypoint.
        behavior: Optional behavior at this waypoint.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    point: Point
    hold_s: float = Field(default=0.0, ge=0.0)
    speed_m_s: Optional[float] = Field(default=None, ge=0.1, le=25.0)
    behavior: Optional[str] = None


class SafetyPolicySpec(BaseModel):
    """Safety policy for mission execution.

    Attributes:
        rtl_on_low_battery: Return to launch on low battery.
        min_battery_percent: Minimum battery percentage for RTL.
        max_distance_from_home_m: Maximum distance from home.
        geofence: Optional geofence polygon.
    """

    model_config = ConfigDict(extra="allow")

    rtl_on_low_battery: bool = True
    min_battery_percent: float = Field(default=25.0, ge=5.0, le=95.0)
    max_distance_from_home_m: Optional[float] = Field(default=None, ge=100.0)
    geofence: Optional[List[Point]] = None


class BehaviorSpec(BaseModel):
    """Behavior specification for complex actions.

    Supports various behavior types via discriminated union.

    Attributes:
        kind: Behavior type (orbit, hover, scan, etc.).
        Additional fields depend on behavior kind.
    """

    model_config = ConfigDict(extra="allow")

    kind: str = Field(..., description="Behavior type")

    # Common fields
    duration_s: Optional[float] = Field(default=None, ge=1.0, le=3600.0)
    altitude_m: Optional[float] = Field(default=None, ge=1.0, le=500.0)
    speed_m_s: Optional[float] = Field(default=None, ge=0.1, le=25.0)

    # Orbit-specific
    target: Optional[Point] = None
    radius_m: Optional[float] = Field(default=None, ge=5.0, le=500.0)

    # Follow/Track-specific
    subject: Optional[str] = None
    distance_m: Optional[float] = Field(default=None, ge=1.0, le=500.0)

    # Scan/Survey-specific
    pattern: Optional[str] = None
    overlap_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Photograph-specific
    angle: Optional[str] = None

    # Land/hover-specific
    location: Optional[Union[Point, str]] = None

    # Search-specific
    area: Optional[str] = None


class MissionConstraintsSpec(BaseModel):
    """Constraints for mission execution.

    Attributes:
        max_altitude_amsl_m: Maximum altitude above sea level.
        max_speed_m_s: Maximum flight speed.
        max_duration_s: Maximum mission duration.
        min_agl_m: Minimum altitude above ground level.
    """

    model_config = ConfigDict(extra="allow")

    max_altitude_amsl_m: Optional[float] = Field(default=120.0, ge=1.0, le=500.0)
    max_speed_m_s: Optional[float] = Field(default=15.0, ge=0.5, le=40.0)
    max_duration_s: Optional[float] = Field(default=None, ge=60.0)
    min_agl_m: Optional[float] = Field(default=10.0, ge=1.0, le=50.0)


class MissionSpec(BaseModel):
    """Complete mission specification.

    Extends the base Mission schema with additional fields
    for waypoint management and behaviors.

    Attributes:
        version: Schema version.
        name: Mission name.
        home: Home position.
        waypoints: List of waypoints.
        behaviors: List of behaviors.
        constraints: Mission constraints.
        safety: Safety policy.
        metadata: Additional metadata.
    """

    model_config = ConfigDict(extra="allow")

    version: Literal["1.0"] = "1.0"
    name: str = Field(default="Unnamed Mission", min_length=1, max_length=256)
    home: Optional[Point] = None
    waypoints: List[WaypointSpec] = Field(default_factory=list)
    behaviors: List[BehaviorSpec] = Field(default_factory=list)
    constraints: Optional[MissionConstraintsSpec] = None
    safety: Optional[SafetyPolicySpec] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_waypoint_indices(self) -> "MissionSpec":
        """Validate waypoint indices are sequential."""
        for i, wp in enumerate(self.waypoints):
            if wp.index != i:
                raise ValueError(f"waypoints[{i}].index must equal {i}, got {wp.index}")
        return self

    @property
    def total_waypoints(self) -> int:
        """Total number of waypoints."""
        return len(self.waypoints)

    @property
    def total_behaviors(self) -> int:
        """Total number of behaviors."""
        return len(self.behaviors)

    def to_mission(self) -> "Mission":
        """Convert to base Mission schema for upload."""
        from avatar.mcp_server.schemas import Mission, Waypoint, MissionConstraints, SafetyPolicy

        return Mission(
            version="1.0",
            name=self.name,
            home=self.home or Point(lat_deg=0.0, lon_deg=0.0),
            waypoints=[
                Waypoint(
                    index=wp.index,
                    point=wp.point,
                    hold_s=wp.hold_s,
                    speed_m_s=wp.speed_m_s,
                )
                for wp in self.waypoints
            ],
            constraints=MissionConstraints(
                max_altitude_amsl_m=self.constraints.max_altitude_amsl_m if self.constraints else None,
                max_speed_m_s=self.constraints.max_speed_m_s if self.constraints else None,
            ) if self.constraints else None,
            safety=SafetyPolicy(
                rtl_on_low_battery=self.safety.rtl_on_low_battery if self.safety else True,
                min_battery_percent=self.safety.min_battery_percent if self.safety else 25.0,
            ) if self.safety else None,
        )


__all__ = [
    "WaypointSpec",
    "SafetyPolicySpec",
    "BehaviorSpec",
    "MissionConstraintsSpec",
    "MissionSpec",
]
