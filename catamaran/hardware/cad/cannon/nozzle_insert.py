"""Interchangeable water-cannon nozzle cartridge.

The 9.6 mm spigot slips into the cannon's 10.2 mm socket (0.3 mm radial FDM
clearance).  A shallow external groove accepts the cannon-body M3 retainer.
Use ``gen_insert(outlet_d)`` for 2.0, 2.5, or 3.0 mm outlets.
"""

import build123d as bd

INLET_D = 6.0
SPIGOT_D = 9.6
SPIGOT_L = 10.0
GROOVE_D = 8.8
GROOVE_Z0 = 3.4
GROOVE_L = 2.2
SHOULDER_D = 13.6
SHOULDER_L = 2.5
SOCKET_D = 10.2
VALID_OUTLETS = (2.0, 2.5, 3.0)


def _cyl(diameter: float, height: float, z0: float) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((0.0, 0.0, z0 + height / 2.0))
    )


def gen_insert(outlet_diameter: float = 2.5) -> bd.Part:
    if outlet_diameter not in VALID_OUTLETS:
        raise ValueError(f"outlet must be one of {VALID_OUTLETS}")

    insert = _cyl(SPIGOT_D, GROOVE_Z0, 0.0)
    insert = insert.fuse(_cyl(GROOVE_D, GROOVE_L, GROOVE_Z0))
    insert = insert.fuse(
        _cyl(
            SPIGOT_D,
            SPIGOT_L - GROOVE_Z0 - GROOVE_L,
            GROOVE_Z0 + GROOVE_L,
        )
    )
    insert = insert.fuse(_cyl(SHOULDER_D, SHOULDER_L, SPIGOT_L))

    inlet_length = 2.0
    inlet = _cyl(INLET_D, inlet_length + 1.0, -1.0)
    converging = bd.Cone(
        INLET_D / 2.0,
        outlet_diameter / 2.0,
        SPIGOT_L + SHOULDER_L - inlet_length + 1.0,
    ).moved(
        bd.Location(
            (
                0.0,
                0.0,
                inlet_length
                + (SPIGOT_L + SHOULDER_L - inlet_length + 1.0) / 2.0,
            )
        )
    )
    insert = insert.cut(inlet.fuse(converging))
    insert.label = f"water_cannon_nozzle_{outlet_diameter:.1f}mm"
    return insert


def gen_step() -> bd.Part:
    return gen_insert(2.5)


if __name__ == "__main__":
    for outlet in VALID_OUTLETS:
        result = gen_insert(outlet)
        clearance = (SOCKET_D - SPIGOT_D) / 2.0
        print(
            f"{outlet:.1f} mm insert: solids={len(result.solids())}, "
            f"radial clearance={clearance:.2f} mm"
        )
        assert len(result.solids()) == 1
        assert clearance >= 0.3 - 1e-9
        assert outlet < INLET_D
