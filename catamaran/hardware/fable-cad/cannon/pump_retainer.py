"""Drop-in guide/retainer for a common 24 x 24 x 45 mm mini pump.

The retainer fits the stern wet-well's Ø38 ID with 0.6 mm radial clearance.
Four guide tabs provide 0.5 mm clearance per pump side.  The service cover
prevents upward escape while the open ring preserves the pump intake flow.
"""

import build123d as bd

PUMP_X = 24.0
PUMP_Y = 24.0
PUMP_H = 45.0
PUMP_SIDE_CLEARANCE = 0.5
GUIDE_INNER_HALF = PUMP_X / 2.0 + PUMP_SIDE_CLEARANCE

WET_WELL_ID = 38.0
RING_OD = 36.8
RING_ID = 27.0
RING_H = 3.0
GUIDE_T = 3.0
GUIDE_W = 10.0
GUIDE_H = 18.0


def _box(
    size_x: float,
    size_y: float,
    size_z: float,
    center_x: float,
    center_y: float,
    z0: float,
) -> bd.Part:
    return bd.Box(size_x, size_y, size_z).moved(
        bd.Location((center_x, center_y, z0 + size_z / 2.0))
    )


def gen_step() -> bd.Part:
    retainer = bd.Cylinder(
        RING_OD / 2.0,
        RING_H,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    retainer = retainer.cut(
        bd.Cylinder(
            RING_ID / 2.0,
            RING_H + 2.0,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
        ).moved(bd.Location((0.0, 0.0, -1.0)))
    )

    guide_center = GUIDE_INNER_HALF + GUIDE_T / 2.0
    for x in (-guide_center, guide_center):
        retainer = retainer.fuse(
            _box(GUIDE_T, GUIDE_W, GUIDE_H + 0.5, x, 0.0, RING_H - 0.5)
        )
    for y in (-guide_center, guide_center):
        retainer = retainer.fuse(
            _box(GUIDE_W, GUIDE_T, GUIDE_H + 0.5, 0.0, y, RING_H - 0.5)
        )

    retainer.label = "mini_pump_wet_well_retainer"
    return retainer


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    radial_well_clearance = (WET_WELL_ID - RING_OD) / 2.0
    print(f"bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    print(
        f"pump side clearance={PUMP_SIDE_CLEARANCE:.2f}; "
        f"wet-well radial clearance={radial_well_clearance:.2f} mm"
    )
    assert len(result.solids()) == 1
    assert PUMP_SIDE_CLEARANCE >= 0.5
    assert radial_well_clearance >= 0.5
