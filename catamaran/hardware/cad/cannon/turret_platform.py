"""
cannon/turret_platform.py — rotating turret platform (DESIGN.md v1).

Local frame: disc bottom on XY at Z=0, +Z up, part axis = Z.
Underside faces the SG90 round horn inside the turret base.

Features:
  - Disc Ø54 x 4.
  - Underside: round-horn pocket Ø21.5 x 2 deep, Ø5.5 spline recess
    (3 deep from the bottom face), Ø2.6 center screw hole through.
  - Top: 4x Ø2.6 pilots on Ø32 PCD at 45° positions, through
    (identical clocking to the cannon flange Ø32 bolt holes).
"""

import math
import build123d as bd

DISC_D = 54.0
DISC_T = 4.0

HORN_POCKET_D = 21.5
HORN_POCKET_DEPTH = 2.0
SPLINE_D = 5.5
SPLINE_DEPTH = 3.0
CENTER_HOLE_D = 2.6

PILOT_D = 2.6
PCD32 = 32.0               # 45° clocking — matches cannon flange


def _cyl(d: float, h: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(d / 2.0, h).moved(bd.Location((x, y, z0 + h / 2.0)))


def gen_step() -> bd.Part:
    part = _cyl(DISC_D, DISC_T, 0.0, 0.0, 0.0)

    # Underside horn pocket + spline recess (cut up from the bottom face)
    part = part.cut(_cyl(HORN_POCKET_D, HORN_POCKET_DEPTH + 1.0,
                         0.0, 0.0, -1.0))
    part = part.cut(_cyl(SPLINE_D, SPLINE_DEPTH + 1.0, 0.0, 0.0, -1.0))

    # Center horn screw hole (through)
    part = part.cut(_cyl(CENTER_HOLE_D, DISC_T + 2.0, 0.0, 0.0, -1.0))

    # Top pilots: Ø2.6 on Ø32 PCD, 45° positions (through)
    r = PCD32 / 2.0
    for i in range(4):
        a = math.radians(45.0 + 90.0 * i)
        part = part.cut(_cyl(PILOT_D, DISC_T + 2.0,
                             r * math.cos(a), r * math.sin(a), -1.0))

    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm "
          f"(expect 54 x 54 x 4)")
    print(f"solids: {len(p.solids())} (expect 1)")
    assert abs(sz.X - DISC_D) < 1e-6 and abs(sz.Y - DISC_D) < 1e-6
    assert abs(sz.Z - DISC_T) < 1e-6
    assert len(p.solids()) == 1
