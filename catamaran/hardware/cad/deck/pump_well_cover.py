"""Removable splash-sealed cover for the stern pump wet-well.

The cover seats in ``deck_stern`` and carries purchased compression glands
for the 8 mm OD hose (6 mm ID) and pump cable.  The wet-well itself remains
intentionally flooded; the gasket prevents deck wash entering the dry bilge.
"""

import math

import build123d as bd

COVER_D = 41.0
COVER_T = 2.8
SEAT_CLEARANCE_D = 42.0
LOCATING_LIP_D = 34.0
LOCATING_LIP_H = 2.0

SCREW_D = 3.4
SCREW_PCD = 48.0
MOUNT_EAR_D = 10.0

GASKET_GROOVE_OD = 39.2
GASKET_GROOVE_ID = 36.2
GASKET_GROOVE_DEPTH = 0.9

HOSE_GLAND_D = 8.5
HOSE_GLAND_BOSS_D = 14.0
CABLE_GLAND_D = 5.5
CABLE_GLAND_BOSS_D = 11.0
CABLE_GLAND_X = 12.0
GLAND_BOSS_H = 5.0


def _cyl(diameter: float, height: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((x, y, z0 + height / 2.0))
    )


def gen_step() -> bd.Part:
    cover = _cyl(COVER_D, COVER_T, 0.0, 0.0, 0.0)
    cover = cover.fuse(
        _cyl(LOCATING_LIP_D, LOCATING_LIP_H, 0.0, 0.0, -LOCATING_LIP_H)
    )

    groove = _cyl(
        GASKET_GROOVE_OD,
        GASKET_GROOVE_DEPTH + 0.2,
        0.0,
        0.0,
        -0.1,
    ).cut(
        _cyl(
            GASKET_GROOVE_ID,
            GASKET_GROOVE_DEPTH + 1.0,
            0.0,
            0.0,
            -0.5,
        )
    )
    cover = cover.cut(groove)

    radius = SCREW_PCD / 2.0
    for degrees in (0.0, 90.0, 180.0, 270.0):
        angle = math.radians(degrees)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        cover = cover.fuse(_cyl(MOUNT_EAR_D, COVER_T, x, y, 0.0))
        cover = cover.cut(_cyl(SCREW_D, COVER_T + 2.0, x, y, -1.0))

    cover = cover.fuse(
        _cyl(HOSE_GLAND_BOSS_D, GLAND_BOSS_H, 0.0, 0.0, COVER_T)
    )
    cover = cover.fuse(
        _cyl(
            CABLE_GLAND_BOSS_D,
            GLAND_BOSS_H,
            CABLE_GLAND_X,
            0.0,
            COVER_T,
        )
    )
    cover = cover.cut(
        _cyl(HOSE_GLAND_D, COVER_T + GLAND_BOSS_H + 2.0, 0.0, 0.0, -1.0)
    )
    cover = cover.cut(
        _cyl(
            CABLE_GLAND_D,
            COVER_T + GLAND_BOSS_H + 2.0,
            CABLE_GLAND_X,
            0.0,
            -1.0,
        )
    )

    cover.label = "pump_well_gasketed_service_cover"
    return cover


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    print(f"cover bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    assert len(result.solids()) == 1
    assert COVER_D < SEAT_CLEARANCE_D
    assert LOCATING_LIP_D < 34.5
    assert GASKET_GROOVE_DEPTH < COVER_T
