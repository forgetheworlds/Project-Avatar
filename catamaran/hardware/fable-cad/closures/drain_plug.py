"""Serviceable transom drain plug for the hull's 8 mm drain bore.

Local origin is the transom exterior plane; stem points into -Y and the
external flange points aft. Use silicone grease or removable marine sealant.
"""

import build123d as bd

STEM_D0 = 7.4
STEM_D1 = 7.8
STEM_L = 6.0
FLANGE_D = 14.0
FLANGE_T = 2.5
GRIP_D = 8.0
GRIP_L = 5.0


def _cone_y(d0, d1, y0, y1):
    if abs(d0 - d1) < 1e-9:
        return bd.Cylinder(
            d0 / 2.0,
            y1 - y0,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
        ).rotate(bd.Axis.X, -90.0).move(bd.Location((0.0, y0, 0.0)))
    return bd.Cone(
        d0 / 2.0,
        d1 / 2.0,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90.0).move(bd.Location((0.0, y0, 0.0)))


def gen_step():
    stem = _cone_y(STEM_D0, STEM_D1, -STEM_L, 0.0)
    flange = _cone_y(FLANGE_D, FLANGE_D, 0.0, FLANGE_T)
    grip = _cone_y(GRIP_D, GRIP_D, FLANGE_T - 0.5, FLANGE_T + GRIP_L)
    part = stem.fuse(flange, grip)
    part.label = "transom_drain_plug"
    assert len(part.solids()) == 1
    return part
