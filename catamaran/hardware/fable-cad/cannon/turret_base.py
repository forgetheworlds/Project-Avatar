"""
cannon/turret_base.py — pan turret base (DESIGN.md v1).

Local frame: base bottom on XY at Z=0, +Z up, part axis = Z.

Features:
  - Ø56 x 3 base plate with 4x Ø3.4 on Ø44 PCD at 0/90/180/270°
    (identical clocking to deck_mid pad Ø44 pilots).
  - Cylindrical body Ø50 OD / wall 2.4, 27 tall (Z=3..30), closed by an
    integral 2.4-thick top plate.
  - SG90 pocket 23.2 x 12.6 cut through the top face, centered on the
    part axis, long axis X (servo drops in from top, output spline up).
  - 2x Ø2.1 servo-flange pilots at (±14, 0), reinforced by Ø6 bosses
    hanging under the top plate.
  - Side wire slot 8 wide through the wall at azimuth 45°, open to the
    top edge (Z=12..top).
  - Ø7 access reliefs (Z=3..12) at each base hole: the Ø44 PCD lands
    under the Ø50 shell, so the wall bottom is locally notched for the
    screw head / driver.
"""

import math
import build123d as bd

BASE_D = 56.0
BASE_T = 3.0
BOLT_D = 3.4
PCD44 = 44.0               # 0/90° clocking — matches deck pad Ø44 pilots

BODY_OD = 50.0
BODY_WALL = 2.4
BODY_H = 27.0              # Z = BASE_T .. BASE_T + BODY_H
TOP_T = 2.4                # integral top plate thickness

POCKET_L = 23.2            # X (servo long axis)
POCKET_W = 12.6            # Y
SERVO_PILOT_D = 2.1
SERVO_PILOT_X = 14.0
SERVO_BOSS_D = 6.0
SERVO_BOSS_H = 5.0

WIRE_SLOT_W = 8.0
WIRE_SLOT_AZ_DEG = 45.0
WIRE_SLOT_Z0 = 12.0

RELIEF_D = 7.0
RELIEF_TOP = 12.0

TOP_Z = BASE_T + BODY_H    # 30.0


def _cyl(d: float, h: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(d / 2.0, h).moved(bd.Location((x, y, z0 + h / 2.0)))


def gen_step() -> bd.Part:
    # Base plate
    part = _cyl(BASE_D, BASE_T, 0.0, 0.0, 0.0)

    # Body shell + integral top plate
    body = _cyl(BODY_OD, BODY_H, 0.0, 0.0, BASE_T)
    body = body.cut(_cyl(BODY_OD - 2 * BODY_WALL, BODY_H - TOP_T,
                         0.0, 0.0, BASE_T))
    part = part.fuse(body)

    # Servo pilot bosses under the top plate
    for sx in (-SERVO_PILOT_X, SERVO_PILOT_X):
        part = part.fuse(_cyl(SERVO_BOSS_D, SERVO_BOSS_H, sx, 0.0,
                              TOP_Z - TOP_T - SERVO_BOSS_H))

    # SG90 pocket through the top face
    pocket = bd.Box(POCKET_L, POCKET_W, TOP_T + 2.0).moved(
        bd.Location((0.0, 0.0, TOP_Z - TOP_T / 2.0)))
    part = part.cut(pocket)

    # Servo-flange pilots through top plate + bosses
    for sx in (-SERVO_PILOT_X, SERVO_PILOT_X):
        part = part.cut(_cyl(SERVO_PILOT_D, TOP_T + SERVO_BOSS_H + 2.0,
                             sx, 0.0, TOP_Z - TOP_T - SERVO_BOSS_H - 1.0))

    # Side wire slot (8 wide, open to top edge, azimuth 45°)
    r_mid = (BODY_OD / 2.0 + BODY_OD / 2.0 - BODY_WALL) / 2.0  # wall mid ~23.8
    a = math.radians(WIRE_SLOT_AZ_DEG)
    slot = bd.Box(14.0, WIRE_SLOT_W, TOP_Z - WIRE_SLOT_Z0 + 2.0)
    slot = slot.rotate(bd.Axis.Z, WIRE_SLOT_AZ_DEG).moved(
        bd.Location((r_mid * math.cos(a), r_mid * math.sin(a),
                     (WIRE_SLOT_Z0 + TOP_Z + 2.0) / 2.0)))
    part = part.cut(slot)

    # Base bolt holes + access reliefs (Ø44 PCD, cardinal positions)
    r = PCD44 / 2.0
    for i in range(4):
        b = math.radians(90.0 * i)
        hx, hy = r * math.cos(b), r * math.sin(b)
        part = part.cut(_cyl(BOLT_D, BASE_T + 2.0, hx, hy, -1.0))
        part = part.cut(_cyl(RELIEF_D, RELIEF_TOP - BASE_T, hx, hy, BASE_T))

    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm "
          f"(expect 56 x 56 x 30)")
    print(f"solids: {len(p.solids())} (expect 1)")
    assert abs(sz.X - BASE_D) < 1e-6 and abs(sz.Y - BASE_D) < 1e-6
    assert abs(sz.Z - TOP_Z) < 1e-6
    assert len(p.solids()) == 1
