"""Serviceable 6 mm-flow-path water cannon body.

Local frame: flange bottom on XY at Z=0; barrel aims +Y at +10 degrees.
The monolithic printable body has a continuous Ø6 main bore and a true barb
for 6 mm-ID / roughly 8 mm-OD silicone hose.  The muzzle has a Ø10.2 cartridge
socket for separately printable 2.0, 2.5, or 3.0 mm nozzle inserts.
"""

import math

import build123d as bd

FLANGE_D = 46.0
FLANGE_T = 3.0
BOLT_D = 3.4
PCD32 = 32.0

ELEV_DEG = 10.0
PIVOT = (0.0, -9.0, 12.0)

BARREL_L = 90.0
BARREL_OD = 14.0
MAIN_BORE_D = 6.0
INSERT_SOCKET_D = 10.2
INSERT_SOCKET_DEPTH = 10.0
RETENTION_PILOT_D = 2.6
RETENTION_Z = BARREL_L - INSERT_SOCKET_DEPTH / 2.0

BARB_L = 16.0
BARB_ROOT_D = 8.0
BARB_CREST_D = 9.0
BARB_COLLAR_D = 10.0
BARB_COLLAR_L = 2.5
BARB_BORE_D = 6.0

RISER_W = 11.0
RISER_Y0 = -12.0
RISER_Y1 = 20.0
RISER_TOP = 12.0
GUSSET_T = 2.5


def _cyl(diameter: float, height: float, z0: float) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((0.0, 0.0, z0 + height / 2.0))
    )


def _cone(diameter_0: float, diameter_1: float, height: float, z0: float) -> bd.Part:
    return bd.Cone(diameter_0 / 2.0, diameter_1 / 2.0, height).moved(
        bd.Location((0.0, 0.0, z0 + height / 2.0))
    )


def _to_world(shape: bd.Part) -> bd.Part:
    return shape.rotate(bd.Axis.X, -(90.0 - ELEV_DEG)).moved(bd.Location(PIVOT))


def _gusset(x0: float) -> bd.Part:
    points = [(RISER_Y0, FLANGE_T), (16.0, FLANGE_T), (RISER_Y0, 11.0)]
    with bd.BuildPart() as build:
        with bd.BuildSketch(bd.Plane.YZ.offset(x0)):
            with bd.BuildLine():
                bd.Polyline(*points, close=True)
            bd.make_face()
        bd.extrude(amount=GUSSET_T, dir=(1, 0, 0))
    return build.part


def _barb_outer() -> bd.Part:
    """Two ramped retention crests plus a hard stop at the barrel."""
    half = (BARB_L - BARB_COLLAR_L) / 2.0
    barb = _cone(BARB_ROOT_D, BARB_CREST_D, half, -BARB_L)
    barb = barb.fuse(
        _cone(BARB_ROOT_D, BARB_CREST_D, half, -BARB_L + half)
    )
    barb = barb.fuse(_cyl(BARB_COLLAR_D, BARB_COLLAR_L, -BARB_COLLAR_L))
    return barb


def gen_step() -> bd.Part:
    part = _cyl(FLANGE_D, FLANGE_T, 0.0)

    barrel_axis_body = _cyl(BARREL_OD, BARREL_L, 0.0).fuse(_barb_outer())
    part = part.fuse(_to_world(barrel_axis_body))

    riser = bd.Box(
        RISER_W,
        RISER_Y1 - RISER_Y0,
        RISER_TOP - FLANGE_T,
    ).moved(
        bd.Location(
            (
                0.0,
                (RISER_Y0 + RISER_Y1) / 2.0,
                (FLANGE_T + RISER_TOP) / 2.0,
            )
        )
    )
    part = part.fuse(riser)
    part = part.fuse(_gusset(RISER_W / 2.0))
    part = part.fuse(_gusset(-RISER_W / 2.0 - GUSSET_T))

    radius = PCD32 / 2.0
    for index in range(4):
        angle = math.radians(45.0 + 90.0 * index)
        part = part.cut(
            bd.Cylinder(BOLT_D / 2.0, FLANGE_T + 2.0).moved(
                bd.Location(
                    (
                        radius * math.cos(angle),
                        radius * math.sin(angle),
                        FLANGE_T / 2.0,
                    )
                )
            )
        )

    # Cut one continuous, cleanable flow path.  The insert socket is a simple
    # stepped bore open at the muzzle; an M3 self-tap lands in the insert's
    # external annular groove without intersecting the water passage.
    main_bore_end = BARREL_L - INSERT_SOCKET_DEPTH
    flow_path = _cyl(
        MAIN_BORE_D,
        main_bore_end + BARB_L + 2.0,
        -BARB_L - 1.0,
    )
    flow_path = flow_path.fuse(
        _cyl(
            INSERT_SOCKET_D,
            INSERT_SOCKET_DEPTH + 2.0,
            main_bore_end,
        )
    )
    part = part.cut(_to_world(flow_path))

    radial_pilot = bd.Cylinder(
        RETENTION_PILOT_D / 2.0,
        BARREL_OD + 2.0,
    ).rotate(bd.Axis.Y, 90.0).moved(
        bd.Location((-BARREL_OD / 2.0 - 1.0, 0.0, RETENTION_Z))
    )
    part = part.cut(_to_world(radial_pilot))

    part.label = "water_cannon_serviceable_body"
    return part


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    radial_wall_at_socket = (BARREL_OD - INSERT_SOCKET_D) / 2.0
    barb_wall = (BARB_ROOT_D - BARB_BORE_D) / 2.0
    print(f"bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    print(
        f"socket radial wall={radial_wall_at_socket:.2f}; "
        f"barb-root wall={barb_wall:.2f} mm"
    )
    assert len(result.solids()) == 1
    assert radial_wall_at_socket >= 1.8
    assert BARB_BORE_D == MAIN_BORE_D == 6.0
    assert barb_wall >= 1.0
    assert BARB_CREST_D >= 8.5
