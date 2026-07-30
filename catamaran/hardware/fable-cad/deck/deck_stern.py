"""Stern deck lid with gasketed pump-well service-cover interface.

Local frame is stern-segment X/Y with plate bottom at Z=0.  Removing the
whole lid exposes the propulsion servo and motor.  A smaller recessed cover
at the starboard wet-well allows pump service without disturbing that seal.
"""

import math

import build123d as bd

PLATE_W = 124.0
PLATE_L = 158.0
PLATE_T = 3.0
CHAMFER = 6.0
Y0 = 1.0
Y1 = Y0 + PLATE_L
YC = (Y0 + Y1) / 2.0

LIP_W = 105.0
LIP_L = 145.0
LIP_DEPTH = 5.0
LIP_WALL = 3.0

SCREW_D = 3.4
SCREW_X = 45.0
SCREW_YS = (25.0, 75.0, 125.0)

# Hull wet-well is fixed at (+32, 45), ID 38.  A Ø34.5 opening passes the
# diagonal of a nominal 24 x 24 pump body with a small handling allowance.
WELL_X = 32.0
WELL_Y = 45.0
ACCESS_D = 34.5
SEAT_D = 42.0
SEAT_DEPTH = 0.6
REINFORCE_D = 47.0
REINFORCE_T = 2.4
COVER_PCD = 48.0
COVER_PILOT_D = 2.6

# Sealed cable gland for propulsion servo/motor wiring.  This replaces the
# old unsealed Ø8 wire hole.
PROP_GLAND_X = -20.0
PROP_GLAND_Y = 108.0
PROP_GLAND_D = 10.5
PROP_GLAND_BOSS_D = 16.0
PROP_GLAND_BOSS_H = 4.0


def _cyl(diameter: float, height: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((x, y, z0 + height / 2.0))
    )


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


def _plate() -> bd.Part:
    half_x = PLATE_W / 2.0
    points = [
        (-half_x + CHAMFER, Y0),
        (half_x - CHAMFER, Y0),
        (half_x, Y0 + CHAMFER),
        (half_x, Y1 - CHAMFER),
        (half_x - CHAMFER, Y1),
        (-half_x + CHAMFER, Y1),
        (-half_x, Y1 - CHAMFER),
        (-half_x, Y0 + CHAMFER),
    ]
    with bd.BuildPart() as build:
        with bd.BuildSketch(bd.Plane.XY):
            with bd.BuildLine():
                bd.Polyline(*points, close=True)
            bd.make_face()
        bd.extrude(amount=PLATE_T)
    return build.part


def _pcd_points(pcd: float):
    radius = pcd / 2.0
    for degrees in (0.0, 90.0, 180.0, 270.0):
        angle = math.radians(degrees)
        yield WELL_X + radius * math.cos(angle), WELL_Y + radius * math.sin(angle)


def gen_step() -> bd.Part:
    part = _plate()

    # The earlier continuous locating lip occupied the hull's six lid-boss
    # pads, the wet-well wall and the steering-servo hardpoints.  Six indexed
    # screws already locate this lid; removing the redundant lip gives those
    # service features real clearance while the flange gasket controls seal.

    for x in (-SCREW_X, SCREW_X):
        for y in SCREW_YS:
            part = part.cut(_cyl(SCREW_D, PLATE_T + 2.0, x, y, -1.0))

    # The hull's wet-well wall already backs this land.  A former underside
    # reinforcement ring occupied that wall and made assembly impossible;
    # the 3 mm lid plus the service cover now clamp directly across the wall.
    part = part.cut(_cyl(ACCESS_D, PLATE_T + 2.0, WELL_X, WELL_Y, -1.0))
    part = part.cut(
        _cyl(SEAT_D, SEAT_DEPTH + 0.2, WELL_X, WELL_Y, PLATE_T - SEAT_DEPTH)
    )
    for x, y in _pcd_points(COVER_PCD):
        part = part.cut(
            _cyl(
                COVER_PILOT_D,
                PLATE_T + 2.0,
                x,
                y,
                -1.0,
            )
        )

    # Purchased compression gland, not an open wire vent.
    part = part.fuse(
        _cyl(
            PROP_GLAND_BOSS_D,
            PROP_GLAND_BOSS_H,
            PROP_GLAND_X,
            PROP_GLAND_Y,
            PLATE_T,
        )
    )
    part = part.cut(
        _cyl(
            PROP_GLAND_D,
            PLATE_T + PROP_GLAND_BOSS_H + 2.0,
            PROP_GLAND_X,
            PROP_GLAND_Y,
            -1.0,
        )
    )

    part.label = "deck_stern_service_layout"
    return part


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    nearest_lid_screw = min(
        math.hypot(WELL_X - x, WELL_Y - y)
        for x in (-SCREW_X, SCREW_X)
        for y in SCREW_YS
    )
    print(f"bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    print(f"well-center to nearest deck screw: {nearest_lid_screw:.2f} mm")
    assert abs(size.X - PLATE_W) < 1e-6
    assert abs(size.Y - PLATE_L) < 1e-6
    assert len(result.solids()) == 1
    assert ACCESS_D >= math.hypot(24.0, 24.0)
    assert nearest_lid_screw > SEAT_D / 2.0 + SCREW_D / 2.0
