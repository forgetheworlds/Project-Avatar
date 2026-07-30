"""Shared propulsion datums and small geometry helpers.

All assembly-level coordinates are in the stern-local boat frame:
X = beam/starboard, Y = aft, Z = up.  The pump/shaft axis is parallel to +Y.
"""

from __future__ import annotations

import math

import build123d as bd

# Primary hull / propulsion interface datums.
AXIS_X = 0.0
AXIS_Z = 22.0
TRANSOM_Y = 160.0
PUMP_BULKHEAD_Y = 70.0

TUNNEL_ID = 28.0
TUNNEL_IR = TUNNEL_ID / 2.0
WET_WALL = 2.4
TUNNEL_OR = TUNNEL_IR + WET_WALL

INTAKE_X_HALF = 14.0
INTAKE_Y0 = 72.0
INTAKE_Y1 = 132.0
INTAKE_FLANGE_Z = 12.0
INTAKE_FASTENER_X = 18.0
INTAKE_FASTENER_YS = (76.0, 102.0, 128.0)

IMPELLER_Y0 = 137.0
IMPELLER_Y1 = 156.0

# Transom stack: Ø36 PCD, selected by the hull team to preserve the lower
# fastener ligament at the new Z=22 axis.
EXIT_PCD_R = 18.0
EXIT_ANGLES = (45.0, 135.0, 225.0, 315.0)
CARTRIDGE_ANGLES = (0.0, 90.0, 180.0)

# Dry-side drivetrain.
MOTOR_FACE_Y = 48.0
MOTOR_DIAMETER = 28.0
MOTOR_LENGTH = 40.0
MOTOR_SHAFT_DIAMETER = 3.175
MOTOR_SHAFT_LENGTH = 15.0
MOTOR_PCD_RANGE = (16.0, 19.0)

SHAFT_DIAMETER = 4.0
SHAFT_CLEARANCE_DIAMETER = 4.25
SHAFT_NOMINAL_LENGTH = 120.0

COUPLER_OD = 12.0
COUPLER_MAX_LENGTH = 19.0

# Service cartridge hardware envelopes. Exact suppliers remain to be selected.
ROTARY_SEAL_ID = 4.0
ROTARY_SEAL_OD = 8.0
ROTARY_SEAL_WIDTH = 3.0
FRONT_BEARING_ID = 4.0
FRONT_BEARING_OD = 11.0  # 694-2RS envelope
FRONT_BEARING_WIDTH = 4.0
AFT_BEARING_ID = 4.0
AFT_BEARING_OD = 7.0     # MR74-2RS
AFT_BEARING_WIDTH = 2.5

# Steering interface.
VECTOR_PIVOT_Y = 203.0
VECTOR_PIVOT_Z = AXIS_Z
VECTOR_RANGE_DEG = 25.0
# Final hull transom pushrod bore, deliberately outside the jet-plate keepout.
LINKAGE_X = 38.0
LINKAGE_Z = 58.0


def cyl_y(
    radius: float,
    y0: float,
    y1: float,
    *,
    x: float = AXIS_X,
    z: float = AXIS_Z,
) -> bd.Part:
    """Closed cylinder with its axis along +Y."""
    part = bd.Cylinder(
        radius,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part = part.rotate(bd.Axis.X, -90.0)
    return part.move(bd.Location((x, y0, z)))


def cone_y(
    r0: float,
    r1: float,
    y0: float,
    y1: float,
    *,
    x: float = AXIS_X,
    z: float = AXIS_Z,
) -> bd.Part:
    """Closed cone/frustum with its axis along +Y."""
    part = bd.Cone(
        bottom_radius=r0,
        top_radius=r1,
        height=y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part = part.rotate(bd.Axis.X, -90.0)
    return part.move(bd.Location((x, y0, z)))


def radial_point(radius: float, angle_deg: float) -> tuple[float, float]:
    """Return an X/Z offset around the pump axis."""
    angle = math.radians(angle_deg)
    return radius * math.cos(angle), radius * math.sin(angle)


def annulus_y(
    outer_radius: float,
    inner_radius: float,
    y0: float,
    y1: float,
    *,
    x: float = AXIS_X,
    z: float = AXIS_Z,
) -> bd.Part:
    return cyl_y(outer_radius, y0, y1, x=x, z=z).cut(
        cyl_y(inner_radius, y0 - 0.2, y1 + 0.2, x=x, z=z)
    )


def assert_single_solid(
    part: bd.Part,
    label: str,
    *,
    min_volume: float = 1.0,
) -> None:
    solids = part.solids()
    assert len(solids) == 1, f"{label}: expected one solid, got {len(solids)}"
    assert part.volume > min_volume, f"{label}: non-positive/implausible volume"
    assert part.is_valid, f"{label}: invalid BREP"
