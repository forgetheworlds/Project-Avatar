"""Low tapered sealed electronics house for the aft mid-deck.

Part-local origin is the center of the sealed footprint on the mounting deck.
The assembly places this origin at mid-local (X=0, Y=120).  The body is narrow
enough to leave the deck-lid screw heads at X=±45 accessible.

The purchased ESP32 and conservative ESC envelopes lie lengthwise in adjacent
lanes.  Cable bend space is primarily vertical above the devices and exits
through two compression glands in the aft floor.
"""

import build123d as bd

# Sealed body.  The 77.6 square lower footprint leaves >3 mm from a nominal
# Ø6 deck screw head centered at X=±45.
OUTER_X = 77.6
OUTER_Y = 77.6
TOP_X = 73.6
TOP_Y = 73.6
WALL = 2.4
BASE_T = 2.4
BODY_H = 35.0
INNER_X = OUTER_X - 2.0 * WALL
INNER_Y = OUTER_Y - 2.0 * WALL
INNER_H = BODY_H - BASE_T

# Lid seat and gasket interface.
RIM_H = 2.4
RIM_OPEN_X = TOP_X - 2.0 * 5.0
RIM_OPEN_Y = TOP_Y - 2.0 * 5.0

# Four captive self-tap bosses; lid uses M3 clearance holes.
LID_PILOT_D = 2.6
LID_BOSS_D = 7.5
LID_BOSS_X = 31.0
LID_BOSS_Y = 31.0

# External mounting ears.  These screws never enter the sealed cavity.
EAR_X = 44.0
EAR_YS = (-26.0, 26.0)
EAR_SIZE_X = 11.0
EAR_SIZE_Y = 12.0
EAR_T = 3.0
EAR_PILOT_D = 2.6

# Vertical cable glands align to deck_mid at global/segment-local Y=146.
GLAND_D = 10.5
GLAND_BOSS_D = 16.0
GLAND_XS = (-18.0, 18.0)
GLAND_Y = 26.0
GLAND_BOSS_H = 5.0

# The tray is retained to the sealed floor with thin 3M Dual Lock strips.
# Printed bosses formerly occupied the tray plate and defeated the claimed
# containment clearance.


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


def _cyl(
    diameter: float, height: float, center_x: float, center_y: float, z0: float
) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((center_x, center_y, z0 + height / 2.0))
    )


def _lofted_box(
    bottom_x: float,
    bottom_y: float,
    top_x: float,
    top_y: float,
    z0: float,
    z1: float,
) -> bd.Part:
    with bd.BuildPart() as build:
        with bd.BuildSketch(bd.Plane.XY.offset(z0)):
            bd.Rectangle(bottom_x, bottom_y)
        with bd.BuildSketch(bd.Plane.XY.offset(z1)):
            bd.Rectangle(top_x, top_y)
        bd.loft()
    return build.part


def gen_step() -> bd.Part:
    # Tapered outer shell and a matching overshooting interior loft.
    body = _lofted_box(OUTER_X, OUTER_Y, TOP_X, TOP_Y, 0.0, BODY_H)
    inner = _lofted_box(
        INNER_X,
        INNER_Y,
        TOP_X - 2.0 * WALL,
        TOP_Y - 2.0 * WALL,
        BASE_T,
        BODY_H + 1.0,
    )
    body = body.cut(inner)

    # Broad top rim supports a closed-cell gasket.  The groove itself is in
    # the removable lid so this house retains an uninterrupted top land.
    rim = _box(TOP_X, TOP_Y, RIM_H, 0.0, 0.0, BODY_H - RIM_H)
    rim = rim.cut(
        _box(
            RIM_OPEN_X,
            RIM_OPEN_Y,
            RIM_H + 2.0,
            0.0,
            0.0,
            BODY_H - RIM_H - 1.0,
        )
    )
    body = body.fuse(rim)

    # Lid bosses grow from the sealed floor and merge into the tapered wall.
    for x in (-LID_BOSS_X, LID_BOSS_X):
        for y in (-LID_BOSS_Y, LID_BOSS_Y):
            body = body.fuse(_cyl(LID_BOSS_D, BODY_H - BASE_T, x, y, BASE_T))
            body = body.cut(
                _cyl(
                    LID_PILOT_D,
                    BODY_H - BASE_T - 3.0,
                    x,
                    y,
                    BASE_T + 3.0,
                )
            )

    # Four dry mounting ears, clear of both the sealed volume and existing
    # deck-to-hull screws.
    for x in (-EAR_X, EAR_X):
        for y in EAR_YS:
            body = body.fuse(_box(EAR_SIZE_X, EAR_SIZE_Y, EAR_T, x, y, 0.0))
            body = body.cut(_cyl(EAR_PILOT_D, EAR_T + 1.0, x, y, -0.5))

    # Compression-gland bosses through the aft floor.  No open vent is used.
    for x in GLAND_XS:
        body = body.fuse(
            _cyl(GLAND_BOSS_D, GLAND_BOSS_H, x, GLAND_Y, 0.0)
        )
        body = body.cut(
            _cyl(GLAND_D, BASE_T + GLAND_BOSS_H + 2.0, x, GLAND_Y, -1.0)
        )

    body.label = "sealed_electronics_house"
    return body


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    nominal_screw_head_clearance = 45.0 - 3.0 - OUTER_X / 2.0
    print(f"house bbox: {size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm")
    print(f"deck screw-head side clearance: {nominal_screw_head_clearance:.2f} mm")
    assert len(result.solids()) == 1
    assert INNER_X >= 72.8 and INNER_Y >= 72.8
    assert nominal_screw_head_clearance >= 3.0
    # Floor + tray plate + 20 mm conservative ESC still leave 10.2 mm for
    # upward cable bends before the lid plane.
    assert BODY_H - (BASE_T + 2.4 + 20.0) >= 10.0
