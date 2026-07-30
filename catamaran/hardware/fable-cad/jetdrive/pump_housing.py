"""Bolt-in Ø28 jet-pump housing with flooded intake and service interfaces.

The part is authored directly in the stern-local boat frame.  It seats on the
flat hull sealing pad at Z=12 and terminates against the transom at Y=157.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import (
    AXIS_Z,
    CARTRIDGE_ANGLES,
    EXIT_ANGLES,
    EXIT_PCD_R,
    INTAKE_FASTENER_X,
    INTAKE_FASTENER_YS,
    INTAKE_FLANGE_Z,
    INTAKE_X_HALF,
    INTAKE_Y0,
    INTAKE_Y1,
    PUMP_BULKHEAD_Y,
    TUNNEL_IR,
    TUNNEL_OR,
    WET_WALL,
    assert_single_solid,
    cyl_y,
    radial_point,
)

TUNNEL_Y0 = PUMP_BULKHEAD_Y
TUNNEL_Y1 = 157.0

FRONT_WALL_Y0 = PUMP_BULKHEAD_Y
FRONT_WALL_Y1 = 76.0
FRONT_BOSS_R = 22.0
CARTRIDGE_SEAT_R = 9.15       # Ø18.3 slip seat for service cartridge
CARTRIDGE_PCD_R = 13.0
CARTRIDGE_HOLE_R = 1.35       # M3 self-tap pilot in pump bulkhead

FLANGE_X_HALF = 23.0
FLANGE_Y0 = 70.0             # cartridge flange ends here; faces meet, not overlap
FLANGE_Y1 = 136.0
FLANGE_T = 4.0
FLANGE_HOLE_R = 1.7

MOUTH_CORNER_R = 4.0
THROAT_Y0 = 82.0
THROAT_Y1 = 128.0

GRATE_BAR_W = 2.2
GRATE_BAR_H = 3.0
GRATE_BAR_XS = (-8.0, 0.0, 8.0)

EXIT_R = 22.0
EXIT_Y0 = 153.0
EXIT_Y1 = 157.0
EXIT_PILOT_R = 1.35

COOLING_TAP_Y = 134.0
COOLING_TAP_OUTER_R = 4.5
COOLING_TAP_MID_R = 3.8
COOLING_TAP_BORE_R = 1.6
COOLING_TAP_Z0 = AXIS_Z + TUNNEL_OR - 1.0
COOLING_TAP_Z1 = COOLING_TAP_Z0 + 12.0


def _rounded_section(
    width: float,
    length: float,
    corner: float,
    y_center: float,
    z: float,
) -> bd.Face:
    section = bd.Rectangle(width - 2.0 * corner, length)
    section = section.fuse(bd.Rectangle(width, length - 2.0 * corner))
    for x in (-width / 2.0 + corner, width / 2.0 - corner):
        for y in (-length / 2.0 + corner, length / 2.0 - corner):
            section = section.fuse(
                bd.Circle(corner).move(bd.Location((x, y, 0.0)))
            )
    return section.move(bd.Location((0.0, y_center, z)))


def _intake_loft(*, inner: bool) -> bd.Part:
    """Three-section C1-like intake loft.

    The front ramp advances 10 mm over a 10 mm rise (45° nominal), while the
    aft wall advances 4 mm.  Rounded sections avoid the old square-edged,
    near-vertical inlet.
    """
    wall = 0.0 if inner else WET_WALL
    bottom_wall = 0.0  # all sub-Z12 material stays inside hull aperture
    bottom_z = INTAKE_FLANGE_Z - (0.8 if inner else 0.0)
    mid_z = 17.0
    top_z = AXIS_Z + (0.8 if inner else 0.0)

    bottom_width = 2.0 * (INTAKE_X_HALF + bottom_wall)
    bottom_length = (INTAKE_Y1 - INTAKE_Y0) + 2.0 * bottom_wall
    mid_width = 28.0 + 2.0 * wall
    mid_length = 53.0 + 2.0 * wall
    top_width = 27.0 + 2.0 * wall
    top_length = (THROAT_Y1 - THROAT_Y0) + 2.0 * wall

    sections = [
        _rounded_section(
            bottom_width,
            bottom_length,
            MOUTH_CORNER_R + wall,
            (INTAKE_Y0 + INTAKE_Y1) / 2.0,
            bottom_z,
        ),
        _rounded_section(
            mid_width,
            mid_length,
            5.0 + wall,
            104.5,
            mid_z,
        ),
        _rounded_section(
            top_width,
            top_length,
            7.0 + wall,
            (THROAT_Y0 + THROAT_Y1) / 2.0,
            top_z,
        ),
    ]
    return bd.loft(sections=sections)


def _cooling_barb() -> bd.Part:
    lower = bd.Cylinder(
        COOLING_TAP_OUTER_R,
        5.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, COOLING_TAP_Y, COOLING_TAP_Z0)))
    upper = bd.Cone(
        bottom_radius=COOLING_TAP_OUTER_R,
        top_radius=COOLING_TAP_MID_R,
        height=7.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, COOLING_TAP_Y, COOLING_TAP_Z0 + 5.0)))
    barb = lower.fuse(upper)
    bore = bd.Cylinder(
        COOLING_TAP_BORE_R,
        COOLING_TAP_Z1 - AXIS_Z + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, COOLING_TAP_Y, AXIS_Z - 1.0)))
    return barb.cut(bore)


def gen_step() -> bd.Part:
    tunnel = cyl_y(TUNNEL_OR, TUNNEL_Y0, TUNNEL_Y1)
    front_boss = cyl_y(FRONT_BOSS_R, FRONT_WALL_Y0, FRONT_WALL_Y1)
    dry_floor_clip = bd.Box(
        60.0,
        FRONT_WALL_Y1 - FRONT_WALL_Y0 + 2.0,
        60.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(
        bd.Location(
            (
                0.0,
                (FRONT_WALL_Y0 + FRONT_WALL_Y1) / 2.0,
                INTAKE_FLANGE_Z,
            )
        )
    )
    front_boss = front_boss & dry_floor_clip
    exit_flange = cyl_y(EXIT_R, EXIT_Y0, EXIT_Y1)

    flange = bd.Box(
        2.0 * FLANGE_X_HALF,
        FLANGE_Y1 - FLANGE_Y0,
        FLANGE_T,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(
        bd.Location(
            (0.0, (FLANGE_Y0 + FLANGE_Y1) / 2.0, INTAKE_FLANGE_Z)
        )
    )
    housing = tunnel.fuse(front_boss, exit_flange, flange, _intake_loft(inner=False))

    # Main flow passage and intake.
    housing = housing.cut(cyl_y(TUNNEL_IR, FRONT_WALL_Y1, EXIT_Y1 + 1.0))
    housing = housing.cut(_intake_loft(inner=True))

    mouth_cut = bd.Box(
        2.0 * INTAKE_X_HALF,
        INTAKE_Y1 - INTAKE_Y0,
        FLANGE_T + 3.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(
        bd.Location(
            (
                0.0,
                (INTAKE_Y0 + INTAKE_Y1) / 2.0,
                INTAKE_FLANGE_Z - 1.5,
            )
        )
    )
    housing = housing.cut(mouth_cut)

    # The removable pump sits on the Z=12 pad.  Outside the actual hull
    # aperture (Y=72..132), no pump material may project below that plane.
    # These D-trims prevent the circular tunnel wall from occupying the hull
    # pad immediately ahead of and behind the intake opening.
    for y0, y1 in (
        (FLANGE_Y0 - 1.0, INTAKE_Y0),
        (INTAKE_Y1, FLANGE_Y1),
    ):
        lower_trim = bd.Box(
            60.0,
            y1 - y0,
            INTAKE_FLANGE_Z + 1.0,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
        ).move(bd.Location((0.0, y0, -1.0)))
        housing = housing.cut(lower_trim)

    # Replace the old shaft hole with a service-cartridge seat and four pilots.
    # Continue the cartridge clearance through the complete cartridge body.
    # The intake loft otherwise intrudes into the lower side of the service
    # cartridge even though the cylindrical pump tunnel itself is clear.
    housing = housing.cut(
        cyl_y(CARTRIDGE_SEAT_R, FRONT_WALL_Y0 - 1.0, 89.0)
    )
    for angle in CARTRIDGE_ANGLES:
        dx, dz = radial_point(CARTRIDGE_PCD_R, angle)
        housing = housing.cut(
            cyl_y(
                CARTRIDGE_HOLE_R,
                FRONT_WALL_Y0 - 1.0,
                FRONT_WALL_Y1 + 1.0,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    # Hull-pad fasteners: 2.3 mm minimum ligament to the wet opening and
    # 3.3 mm minimum ligament to the outside flange edge.
    for x in (-INTAKE_FASTENER_X, INTAKE_FASTENER_X):
        for y in INTAKE_FASTENER_YS:
            hole = bd.Cylinder(
                FLANGE_HOLE_R,
                FLANGE_T + 2.0,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
            ).move(bd.Location((x, y, INTAKE_FLANGE_Z - 1.0)))
            housing = housing.cut(hole)

    for angle in EXIT_ANGLES:
        dx, dz = radial_point(EXIT_PCD_R, angle)
        housing = housing.cut(
            cyl_y(
                EXIT_PILOT_R,
                EXIT_Y0 - 1.0,
                EXIT_Y1 + 1.0,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    # Recessed streamwise grate, retained within the pump part but flush with
    # the sealing-pad plane rather than hidden above a hull cavity.
    for x in GRATE_BAR_XS:
        bar = bd.Box(
            GRATE_BAR_W,
            INTAKE_Y1 - INTAKE_Y0,
            GRATE_BAR_H,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
        ).move(
            bd.Location(
                (
                    x,
                    (INTAKE_Y0 + INTAKE_Y1) / 2.0,
                    INTAKE_FLANGE_Z,
                )
            )
        )
        housing = housing.fuse(bar)

    # The former Y=134 cooling tap was upstream of the impeller and could
    # ingest air. Pressurized cooling water is now taken from nozzle_plate
    # downstream of the impeller/stator instead.

    # The inner/outer loft subtraction can leave a detached crescent below
    # the intake mouth after the hull-pad D-trims.  It is not part of the
    # serviceable pump: retaining it would create a loose second print solid
    # and partially obstruct the flooded intake.  The connected flange,
    # grate, intake sidewalls and tunnel form the intended printable body.
    solids = list(housing.solids())
    if len(solids) > 1:
        largest = max(solids, key=lambda solid: solid.volume)
        housing = bd.Part() + largest
    housing.label = "pump_housing"

    assert_single_solid(housing, "pump_housing", min_volume=20_000.0)
    bbox = housing.bounding_box()
    assert bbox.min.Z >= -0.05  # Ø44 exit flange is tangent to hull baseline.
    assert math.isclose(INTAKE_FLANGE_Z, 12.0)
    assert bbox.max.Y <= EXIT_Y1 + 0.05
    assert bbox.min.X <= -FLANGE_X_HALF + 0.05
    assert bbox.max.X >= FLANGE_X_HALF - 0.05
    assert INTAKE_FASTENER_X - FLANGE_HOLE_R - INTAKE_X_HALF >= 2.0
    assert FLANGE_X_HALF - INTAKE_FASTENER_X - FLANGE_HOLE_R >= 3.0
    return housing


if __name__ == "__main__":
    part = gen_step()
    bbox = part.bounding_box()
    print(
        f"pump bbox={bbox.size.X:.2f} x {bbox.size.Y:.2f} x "
        f"{bbox.size.Z:.2f} mm; volume={part.volume / 1000.0:.1f} cm^3"
    )
