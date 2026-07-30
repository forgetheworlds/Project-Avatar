"""Low-friction prototype thrust washer providing turret running clearance."""

import build123d as bd

OD = 20.0
ID = 6.0
T = 0.8


def gen_step():
    part = bd.Cylinder(OD / 2.0, T).cut(
        bd.Cylinder(ID / 2.0, T + 2.0).move(bd.Location((0, 0, -1.0)))
    )
    part.label = "turret_thrust_washer"
    assert len(part.solids()) == 1
    return part
