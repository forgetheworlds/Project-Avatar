"""Mirrored removable stern tracking fins using existing trim-tab hardpoints.

Local origin is the center of each two-hole transom pattern. +Y points aft,
+Z up, and the mounting plate sits on Y=0. The blade remains outboard of the
full steering-nozzle envelope and downstream of the intake, so it cannot
disturb pump inflow.
"""

from __future__ import annotations

import build123d as bd

PLATE_X = 24.0
PLATE_T = 3.0
PLATE_Z = 26.0
HOLE_X = 6.0
HOLE_D = 3.4

BLADE_OFFSET_X = 9.0
BLADE_T = 3.2
BLADE_Y0 = 2.5
BLADE_Y1 = 40.0
BLADE_TOP_Z = -8.0
BLADE_BOTTOM_Z = -22.0


def _cyl_y(diameter: float, y0: float, y1: float, x: float, z: float) -> bd.Part:
    return bd.Cylinder(
        diameter / 2.0,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90.0).move(bd.Location((x, y0, z)))


def gen_fin(side: int = 1) -> bd.Part:
    """side=+1 starboard, side=-1 port."""
    assert side in (-1, 1)
    plate = bd.Box(
        PLATE_X,
        PLATE_T,
        PLATE_Z,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER),
    )

    # Raked lower edge sheds weeds and reduces grounding shock.
    points = [
        (BLADE_Y0, BLADE_TOP_Z),
        (BLADE_Y1, BLADE_TOP_Z),
        (BLADE_Y1, BLADE_BOTTOM_Z + 3.0),
        (12.0, BLADE_BOTTOM_Z),
        (BLADE_Y0, BLADE_BOTTOM_Z + 6.0),
    ]
    x0 = side * BLADE_OFFSET_X - BLADE_T / 2.0
    with bd.BuildPart() as build:
        with bd.BuildSketch(bd.Plane.YZ.offset(x0)):
            with bd.BuildLine():
                bd.Polyline(*points, close=True)
            bd.make_face()
        bd.extrude(amount=BLADE_T, dir=(1, 0, 0))
    fin = plate.fuse(build.part)

    for x in (-HOLE_X, HOLE_X):
        fin = fin.cut(_cyl_y(HOLE_D, -1.0, PLATE_T + 1.0, x, 0.0))

    fin.label = "tracking_fin_starboard" if side > 0 else "tracking_fin_port"
    assert len(fin.solids()) == 1
    return fin


def gen_step() -> bd.Part:
    return gen_fin(1)
