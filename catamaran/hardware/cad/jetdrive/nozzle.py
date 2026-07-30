"""Downstream steerable vectoring nozzle.

Unlike the superseded bell sleeve, this part begins after a 7 mm free-jet gap
from the fixed contraction.  Its vertical pivot passes through the inlet-plane
center, so yaw does not demand a sliding cylindrical seal.  The 7 mm stand-off
keeps the swept inlet rim clear of the fixed Ø24.8 outlet at ±25°.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import (
    AXIS_Z,
    LINKAGE_Z,
    VECTOR_PIVOT_Y,
    VECTOR_RANGE_DEG,
    WET_WALL,
    assert_single_solid,
    cone_y,
    cyl_y,
)

INLET_ID = 22.0
OUTLET_ID = 18.0
INLET_IR = INLET_ID / 2.0
OUTLET_IR = OUTLET_ID / 2.0
INLET_OR = INLET_IR + WET_WALL
OUTLET_OR = OUTLET_IR + WET_WALL
NOZZLE_Y0 = VECTOR_PIVOT_Y
NOZZLE_Y1 = NOZZLE_Y0 + 30.0

PIVOT_BOSS_R = 3.5
LOWER_BOSS_Z0 = 7.5
LOWER_BOSS_Z1 = 10.0
UPPER_BOSS_Z0 = 34.0
UPPER_BOSS_Z1 = 36.5
PIVOT_PILOT_R = 1.3

HORN_T = 2.5
HORN_Y0 = VECTOR_PIVOT_Y + 8.0
HORN_Y1 = VECTOR_PIVOT_Y + 16.0
HORN_X0 = 3.0
HORN_X1 = 38.0
HORN_HOLE_X = 34.0
HORN_HOLE_Y = (HORN_Y0 + HORN_Y1) / 2.0
HORN_HOLE_R = 1.15
BRIDGE_Z0 = 32.5


def _unrotated() -> bd.Part:
    outer = cone_y(INLET_OR, OUTLET_OR, NOZZLE_Y0, NOZZLE_Y1)
    cavity = cone_y(
        INLET_IR,
        OUTLET_IR,
        NOZZLE_Y0 - 0.5,
        NOZZLE_Y1 + 0.5,
    )
    nozzle = outer.cut(cavity)

    lower_boss = bd.Cylinder(
        PIVOT_BOSS_R,
        LOWER_BOSS_Z1 - LOWER_BOSS_Z0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, LOWER_BOSS_Z0)))
    upper_boss = bd.Cylinder(
        PIVOT_BOSS_R,
        UPPER_BOSS_Z1 - UPPER_BOSS_Z0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, UPPER_BOSS_Z0)))
    nozzle = nozzle.fuse(lower_boss, upper_boss)

    lower_pilot = bd.Cylinder(
        PIVOT_PILOT_R,
        3.5,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, LOWER_BOSS_Z0 - 0.5)))
    upper_pilot = bd.Cylinder(
        PIVOT_PILOT_R,
        3.5,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, UPPER_BOSS_Z1 - 3.0)))
    nozzle = nozzle.cut(lower_pilot, upper_pilot)

    # Raised steering bridge and horn keep the pushrod at Z=58, above and
    # outside the fixed contraction shell.
    bridge = bd.Box(
        10.0,
        HORN_Y1 - HORN_Y0,
        LINKAGE_Z - BRIDGE_Z0 + HORN_T / 2.0,
        align=(bd.Align.MIN, bd.Align.MIN, bd.Align.MIN),
    ).move(bd.Location((HORN_X0, HORN_Y0, BRIDGE_Z0)))
    horn = bd.Box(
        HORN_X1 - HORN_X0,
        HORN_Y1 - HORN_Y0,
        HORN_T,
        align=(bd.Align.MIN, bd.Align.MIN, bd.Align.CENTER),
    ).move(bd.Location((HORN_X0, HORN_Y0, LINKAGE_Z)))
    nozzle = nozzle.fuse(bridge, horn)

    horn_hole = bd.Cylinder(
        HORN_HOLE_R,
        HORN_T + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
    ).move(bd.Location((HORN_HOLE_X, HORN_HOLE_Y, LINKAGE_Z)))
    nozzle = nozzle.cut(horn_hole)
    return nozzle


def gen_at_angle(angle_deg: float) -> bd.Part:
    assert -VECTOR_RANGE_DEG <= angle_deg <= VECTOR_RANGE_DEG
    nozzle = _unrotated()
    if abs(angle_deg) > 1e-9:
        nozzle = nozzle.rotate(
            bd.Axis((0.0, VECTOR_PIVOT_Y, AXIS_Z), (0.0, 0.0, 1.0)),
            angle_deg,
        )
    nozzle.label = "vector_nozzle"

    assert_single_solid(nozzle, "vector_nozzle", min_volume=4_000.0)
    assert math.isclose(INLET_ID, 22.0)
    assert math.isclose(OUTLET_ID, 18.0)
    assert NOZZLE_Y0 - 196.0 >= 7.0
    return nozzle


def gen_step() -> bd.Part:
    return gen_at_angle(0.0)


if __name__ == "__main__":
    for angle in (-VECTOR_RANGE_DEG, 0.0, VECTOR_RANGE_DEG):
        part = gen_at_angle(angle)
        bbox = part.bounding_box()
        print(
            f"angle={angle:+.0f} bbox={bbox.size.X:.2f} x "
            f"{bbox.size.Y:.2f} x {bbox.size.Z:.2f} mm"
        )
