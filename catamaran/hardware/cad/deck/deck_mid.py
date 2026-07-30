"""Mid deck lid with separated cannon and electronics-house interfaces.

Local frame:
    X = beam, Y = mid-segment local 0..160, plate bottom Z=0, +Z up.

The cannon interface is recessed/flush at Y=55 and reinforced below the
plate.  The electronics house is centered at Y=120.  Its four mounting holes
are outside the sealed wall footprint but clear of the hull lid fasteners.
"""

import math

import build123d as bd

# Deck plate and hull interface.
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
SCREW_YS = (30.0, 80.0, 130.0)

# Flush cannon/turret interface.  The Ø46 cannon flange locates in the shallow
# recess.  The optional Ø56 turret base seats on the surrounding flat deck.
CANNON_X = 0.0
CANNON_Y = 55.0
CANNON_RECESS_D = 46.4
CANNON_RECESS_DEPTH = 0.6
CANNON_REINFORCE_D = 60.0
CANNON_REINFORCE_T = 2.4
PILOT_D = 2.6
PCD32 = 32.0
PCD44 = 44.0

# Electronics-house body is nominally 77.6 x 77.6 and centered at Y=120.
# Mounting ears sit outside the sealed wall; screws enter the house-ear pilots
# from below through these clearance holes.
HOUSE_CENTER_Y = 120.0
HOUSE_MOUNT_D = 3.4
HOUSE_MOUNT_X = 44.0
HOUSE_MOUNT_YS = (94.0, 146.0)

# Two sealed vertical cable glands in the electronics-house floor.
HOUSE_GLAND_D = 10.5
HOUSE_GLAND_XS = (-18.0, 18.0)
HOUSE_GLAND_Y = 146.0


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


def _pcd_points(pcd: float, start_degrees: float):
    radius = pcd / 2.0
    for index in range(4):
        angle = math.radians(start_degrees + 90.0 * index)
        yield radius * math.cos(angle), radius * math.sin(angle)


def gen_step() -> bd.Part:
    part = _plate()

    # Six indexed screws locate the lid.  A former continuous underside lip
    # occupied every hull lid-boss pad; it was redundant and unassemblable.

    # Reinforcement stays below the deck so neither cannon option creates a
    # raised snag or overlaps the aft electronics house.
    part = part.fuse(
        _cyl(
            CANNON_REINFORCE_D,
            CANNON_REINFORCE_T,
            CANNON_X,
            CANNON_Y,
            -CANNON_REINFORCE_T,
        )
    )
    part = part.cut(
        _cyl(
            CANNON_RECESS_D,
            CANNON_RECESS_DEPTH + 0.2,
            CANNON_X,
            CANNON_Y,
            PLATE_T - CANNON_RECESS_DEPTH,
        )
    )

    # Existing deck-to-hull fasteners.
    for x in (-SCREW_X, SCREW_X):
        for y in SCREW_YS:
            part = part.cut(_cyl(SCREW_D, PLATE_T + 2.0, x, y, -1.0))

    # Cannon direct pattern and optional turret pattern.
    interface_height = PLATE_T + CANNON_REINFORCE_T + 2.0
    for dx, dy in _pcd_points(PCD32, 45.0):
        part = part.cut(
            _cyl(
                PILOT_D,
                interface_height,
                CANNON_X + dx,
                CANNON_Y + dy,
                -CANNON_REINFORCE_T - 1.0,
            )
        )
    for dx, dy in _pcd_points(PCD44, 0.0):
        part = part.cut(
            _cyl(
                PILOT_D,
                interface_height,
                CANNON_X + dx,
                CANNON_Y + dy,
                -CANNON_REINFORCE_T - 1.0,
            )
        )

    # Explicit electronics-house mounting and sealed cable-pass pattern.
    for x in (-HOUSE_MOUNT_X, HOUSE_MOUNT_X):
        for y in HOUSE_MOUNT_YS:
            part = part.cut(_cyl(HOUSE_MOUNT_D, PLATE_T + 2.0, x, y, -1.0))
    for x in HOUSE_GLAND_XS:
        part = part.cut(
            _cyl(HOUSE_GLAND_D, PLATE_T + 2.0, x, HOUSE_GLAND_Y, -1.0)
        )

    part.label = "deck_mid_payload_layout"
    return part


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    cannon_aft = CANNON_Y + CANNON_RECESS_D / 2.0
    house_forward = HOUSE_CENTER_Y - 77.6 / 2.0
    nearest_lid_fastener_clearance = (
        HOUSE_CENTER_Y - 77.6 / 2.0
    )  # retained for readable checks below
    print(f"bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    print(f"cannon-to-house nominal gap: {house_forward - cannon_aft:.2f} mm")
    assert abs(size.X - PLATE_W) < 1e-6
    assert abs(size.Y - PLATE_L) < 1e-6
    assert len(result.solids()) == 1
    assert house_forward - cannon_aft >= 3.0
    assert min(abs(HOUSE_MOUNT_X - SCREW_X), 999.0) == 1.0
    assert min(abs(y - sy) for y in HOUSE_MOUNT_YS for sy in SCREW_YS) >= 14.0
