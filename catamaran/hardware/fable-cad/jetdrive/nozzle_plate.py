"""Fixed transom plate, five-vane stator, bearing hub and contraction.

The printable is authored in stern-local coordinates.  Flow is +Y.  A fixed
Ø28-to-Ø20 contraction ends at Y=196; the vectoring nozzle starts downstream
with a free jet gap and never sleeves over this fixed stub.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import (
    AFT_BEARING_OD,
    AFT_BEARING_WIDTH,
    AXIS_Z,
    EXIT_ANGLES,
    EXIT_PCD_R,
    LINKAGE_X,
    LINKAGE_Z,
    SHAFT_CLEARANCE_DIAMETER,
    TRANSOM_Y,
    VECTOR_PIVOT_Y,
    WET_WALL,
    assert_single_solid,
    cone_y,
    cyl_y,
    radial_point,
)

PLATE_X = 58.0
PLATE_Z0 = 0.0
PLATE_Z1 = 50.0
PLATE_Y0 = TRANSOM_Y
PLATE_Y1 = TRANSOM_Y + 4.0
PLATE_HOLE_R = 1.7
PLATE_BORE_R = 14.0

CONTRACTION_Y0 = PLATE_Y1
CONTRACTION_Y1 = CONTRACTION_Y0 + 32.0
CONTRACTION_INLET_R = 14.0
CONTRACTION_OUTLET_R = 10.0

N_VANES = 5
VANE_Y0 = 166.5
VANE_Y1 = 181.0
VANE_ROOT_R = 4.5
VANE_TIP_R = 14.5
VANE_T = 1.35
VANE_TWIST_DEG = 11.0

HUB_R0 = 5.2
HUB_R1 = 4.5
HUB_Y0 = PLATE_Y1
HUB_Y1 = 184.0
BEARING_POCKET_R = AFT_BEARING_OD / 2.0 + 0.06
BEARING_Y0 = PLATE_Y1
BEARING_Y1 = BEARING_Y0 + AFT_BEARING_WIDTH
SHAFT_BORE_R = SHAFT_CLEARANCE_DIAMETER / 2.0

YOKE_LUG_X = 12.0
YOKE_LUG_Y0 = 195.5
YOKE_LUG_Y1 = 209.0
YOKE_LUG_T = 4.0
YOKE_OFFSET_Z = 16.5
YOKE_HOLE_R = 1.7
YOKE_WEB_Y0 = 189.0
YOKE_WEB_Y1 = 197.0

LINKAGE_PASS_R = 2.75

COOLING_TAP_X = -7.0
COOLING_TAP_Y = 184.0
COOLING_TAP_Z0 = 32.0
COOLING_TAP_Z1 = 45.0
COOLING_TAP_R0 = 4.5
COOLING_TAP_R1 = 3.8
COOLING_BORE_R = 1.6


def _plate() -> bd.Part:
    return bd.Box(
        PLATE_X,
        PLATE_Y1 - PLATE_Y0,
        PLATE_Z1 - PLATE_Z0,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).move(bd.Location((0.0, PLATE_Y0, PLATE_Z0)))


def _vane_section(y: float, angle_deg: float) -> bd.Face:
    radial_span = VANE_TIP_R - VANE_ROOT_R
    radial_center = (VANE_TIP_R + VANE_ROOT_R) / 2.0
    section = bd.Rectangle(radial_span, VANE_T)
    section = section.rotate(bd.Axis.X, 90.0)  # section plane XZ
    section = section.move(
        bd.Location((radial_center, y, AXIS_Z))
    )
    return section.rotate(
        bd.Axis((0.0, y, AXIS_Z), (0.0, 1.0, 0.0)),
        angle_deg,
    )


def _stator_vane(clock_deg: float) -> bd.Part:
    leading = _vane_section(VANE_Y0, clock_deg + VANE_TWIST_DEG)
    trailing = _vane_section(VANE_Y1, clock_deg)
    return bd.loft(sections=[leading, trailing])


def _pressure_cooling_tap() -> bd.Part:
    lower = bd.Cylinder(
        COOLING_TAP_R0,
        6.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((COOLING_TAP_X, COOLING_TAP_Y, COOLING_TAP_Z0)))
    upper = bd.Cone(
        COOLING_TAP_R0,
        COOLING_TAP_R1,
        COOLING_TAP_Z1 - COOLING_TAP_Z0 - 6.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((COOLING_TAP_X, COOLING_TAP_Y, COOLING_TAP_Z0 + 6.0)))
    tap = lower.fuse(upper)
    bore = bd.Cylinder(
        COOLING_BORE_R,
        COOLING_TAP_Z1 - 29.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((COOLING_TAP_X, COOLING_TAP_Y, 29.0)))
    return tap.cut(bore)


def gen_step() -> bd.Part:
    plate = _plate()
    outer = cone_y(
        CONTRACTION_INLET_R + WET_WALL,
        CONTRACTION_OUTLET_R + WET_WALL,
        CONTRACTION_Y0,
        CONTRACTION_Y1,
    )
    body = plate.fuse(outer)

    body = body.cut(
        cyl_y(PLATE_BORE_R, PLATE_Y0 - 1.0, PLATE_Y1 + 0.2)
    )
    body = body.cut(
        cone_y(
            CONTRACTION_INLET_R,
            CONTRACTION_OUTLET_R,
            CONTRACTION_Y0 - 0.2,
            CONTRACTION_Y1 + 0.5,
        )
    )

    hub = cone_y(HUB_R0, HUB_R1, HUB_Y0, HUB_Y1)
    hub = hub.cut(cyl_y(SHAFT_BORE_R, HUB_Y0 - 0.5, HUB_Y1 + 0.5))
    hub = hub.cut(
        cyl_y(BEARING_POCKET_R, BEARING_Y0 - 0.1, BEARING_Y1 + 0.08)
    )
    body = body.fuse(hub)

    for index in range(N_VANES):
        body = body.fuse(_stator_vane(index * 360.0 / N_VANES))

    # Pressurized pickup after the impeller/stator, on the port side away
    # from the steering horn. A cooling discharge fitting remains purchased.
    body = body.fuse(_pressure_cooling_tap())

    for angle in EXIT_ANGLES:
        dx, dz = radial_point(EXIT_PCD_R, angle)
        body = body.cut(
            cyl_y(
                PLATE_HOLE_R,
                PLATE_Y0 - 1.0,
                PLATE_Y1 + 1.0,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    # Top/bottom fixed yoke.  The vector nozzle pivots at its inlet plane,
    # downstream of the contraction with no overlapping sleeve.
    for sign in (-1.0, 1.0):
        z_center = AXIS_Z + sign * YOKE_OFFSET_Z
        lug = bd.Box(
            YOKE_LUG_X,
            YOKE_LUG_Y1 - YOKE_LUG_Y0,
            YOKE_LUG_T,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER),
        ).move(bd.Location((0.0, YOKE_LUG_Y0, z_center)))
        if sign > 0:
            web_z0 = AXIS_Z + CONTRACTION_OUTLET_R + WET_WALL - 1.0
            web_z1 = z_center + YOKE_LUG_T / 2.0
        else:
            web_z0 = z_center - YOKE_LUG_T / 2.0
            web_z1 = AXIS_Z - CONTRACTION_OUTLET_R - WET_WALL + 1.0
        web = bd.Box(
            YOKE_LUG_X,
            YOKE_WEB_Y1 - YOKE_WEB_Y0,
            web_z1 - web_z0,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
        ).move(bd.Location((0.0, YOKE_WEB_Y0, web_z0)))
        body = body.fuse(lug, web)

    pivot_hole = bd.Cylinder(
        YOKE_HOLE_R,
        2.0 * YOKE_OFFSET_Z + 2.0 * YOKE_LUG_T,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, AXIS_Z)))
    body = body.cut(pivot_hole)

    # Dedicated straight linkage tunnel through the plate, positioned above
    # and outside the contraction shell.
    body = body.cut(
        cyl_y(
            LINKAGE_PASS_R,
            PLATE_Y0 - 1.0,
            PLATE_Y1 + 1.0,
            x=LINKAGE_X,
            z=LINKAGE_Z,
        )
    )

    body.label = "stator_contraction_plate"
    assert_single_solid(body, "stator_contraction_plate", min_volume=15_000.0)
    bbox = body.bounding_box()
    assert bbox.max.Y >= YOKE_LUG_Y1 - 0.05
    assert abs(CONTRACTION_Y1 - 196.0) < 0.05
    assert N_VANES == 5
    assert math.isclose(BEARING_Y1 - BEARING_Y0, 2.5)
    return body


if __name__ == "__main__":
    part = gen_step()
    bbox = part.bounding_box()
    print(
        f"stator/contraction bbox={bbox.size.X:.2f} x {bbox.size.Y:.2f} x "
        f"{bbox.size.Z:.2f} mm; volume={part.volume / 1000.0:.2f} cm^3"
    )
