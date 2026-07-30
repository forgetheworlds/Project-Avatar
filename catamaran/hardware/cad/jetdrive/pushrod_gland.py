"""Epoxy-in pushrod guide and RC-bellows retainer for the Ø6 transom bore."""

import build123d as bd

STEM_D = 5.6
STEM_L = 7.0
FLANGE_D = 12.0
FLANGE_T = 2.0
BARB_D0 = 7.0
BARB_D1 = 8.2
BARB_L = 5.0
PUSHROD_BORE_D = 2.5


def _cyl_y(diameter, y0, y1):
    return bd.Cylinder(
        diameter / 2.0,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90.0).move(bd.Location((0.0, y0, 0.0)))


def _cone_y(d0, d1, y0, y1):
    return bd.Cone(
        d0 / 2.0,
        d1 / 2.0,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90.0).move(bd.Location((0.0, y0, 0.0)))


def gen_step():
    body = _cyl_y(STEM_D, -STEM_L, 0.0)
    body = body.fuse(_cyl_y(FLANGE_D, 0.0, FLANGE_T))
    body = body.fuse(_cone_y(BARB_D0, BARB_D1, FLANGE_T - 0.4, FLANGE_T + BARB_L))
    body = body.cut(_cyl_y(PUSHROD_BORE_D, -STEM_L - 1.0, FLANGE_T + BARB_L + 1.0))
    body.label = "pushrod_bellows_gland"
    assert len(body.solids()) == 1
    return body
