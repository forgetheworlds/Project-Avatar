"""
jetdrive/nozzle_plate.py — fixed transom plate + stator (DESIGN.md v1).

Local frame: plate on XY (forward face at Z=0), flow along +Z (aft).

Features:
  - Plate 60 x 60 x 4 with center Ø28 bore.
  - Aft stub tube Ø28 ID / Ø32.8 OD x 14 proud (Z=4..18).
  - 4 stator vanes 2 thick x 12 long (Z=4..16) in a cross pattern inside
    the stub, joined to a Ø8 center body.
  - 4x Ø3.4 clearance holes on Ø42 PCD at 45° positions (M3x16 from
    outside through plate + transom into the pump exit-flange pilots).
  - Top + bottom pivot lugs extending 18 aft of the plate face (to Z=22)
    with coaxial Ø3.4 vertical holes at 14 aft of the plate face (Z=18).

Print: flat on plate.
"""

import math
import build123d as bd

# ── Plate ───────────────────────────────────────────────────────
PLATE_W = 60.0
PLATE_T = 4.0
BORE_R = 14.0              # Ø28

# ── Stub tube ───────────────────────────────────────────────────
WALL = 2.4
STUB_OR = BORE_R + WALL    # 16.4 -> Ø32.8 OD
STUB_L = 14.0              # proud of aft face: Z=4..18

# ── Stator ──────────────────────────────────────────────────────
VANE_T = 2.0
VANE_L = 12.0              # along Z, Z=4..16
VANE_SPAN = 31.0           # cross width; embeds 1.5 into stub wall
CENTER_BODY_R = 4.0        # Ø8

# ── Bolt pattern ────────────────────────────────────────────────
HOLE_R = 1.7               # Ø3.4
PCD_R = 21.0               # Ø42 PCD
HOLE_ANGLES = (45.0, 135.0, 225.0, 315.0)

# ── Pivot lugs ──────────────────────────────────────────────────
LUG_W = 10.0               # width along X
LUG_T = 4.0                # thickness along Y
LUG_AFT = 18.0             # extends to Z = PLATE_T + 18 = 22
LUG_HOLE_R = 1.7           # Ø3.4
LUG_HOLE_Z = PLATE_T + 14.0  # 14 aft of plate face -> Z=18


def gen_step() -> bd.Part:
    # ═══ Step 1: plate + stub ═══
    plate = bd.Box(PLATE_W, PLATE_W, PLATE_T,
                   align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    stub = bd.Cylinder(STUB_OR, STUB_L,
                       align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    stub = stub.move(bd.Location((0, 0, PLATE_T)))
    body = plate.fuse(stub)

    # ═══ Step 2: Ø28 bore through plate + stub ═══
    bore = bd.Cylinder(BORE_R, PLATE_T + STUB_L + 2.0,
                       align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    bore = bore.move(bd.Location((0, 0, -1.0)))
    body = body.cut(bore)

    # ═══ Step 3: stator — center body + 4-vane cross ═══
    center_body = bd.Cylinder(
        CENTER_BODY_R, VANE_L,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    center_body = center_body.move(bd.Location((0, 0, PLATE_T)))
    vane_x = bd.Box(VANE_SPAN, VANE_T, VANE_L,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    vane_x = vane_x.move(bd.Location((0, 0, PLATE_T)))
    vane_y = bd.Box(VANE_T, VANE_SPAN, VANE_L,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    vane_y = vane_y.move(bd.Location((0, 0, PLATE_T)))
    body = body.fuse(center_body, vane_x, vane_y)

    # ═══ Step 4: 4x Ø3.4 mounting holes on Ø42 PCD, 45° positions ═══
    for ang in HOLE_ANGLES:
        hx = PCD_R * math.cos(math.radians(ang))
        hy = PCD_R * math.sin(math.radians(ang))
        h = bd.Cylinder(HOLE_R, PLATE_T + 2.0,
                        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        body = body.cut(h.move(bd.Location((hx, hy, -1.0))))

    # ═══ Step 5: top + bottom pivot lugs with coaxial vertical holes ═══
    for s in (1.0, -1.0):
        lug = bd.Box(LUG_W, LUG_T, PLATE_T + LUG_AFT,
                     align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        lug = lug.move(
            bd.Location((0, s * (PLATE_W / 2.0 - LUG_T / 2.0), 0)))
        body = body.fuse(lug)
        hole = bd.Cylinder(LUG_HOLE_R, LUG_T + 4.0,
                           align=(bd.Align.CENTER, bd.Align.CENTER,
                                  bd.Align.CENTER))
        hole = hole.rotate(bd.Axis.X, -90)  # axis along Y (boat vertical)
        hole = hole.move(bd.Location(
            (0, s * (PLATE_W / 2.0 - LUG_T / 2.0), LUG_HOLE_Z)))
        body = body.cut(hole)

    return body


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"solids: {len(p.solids())}, volume: {p.volume / 1000.0:.2f} cm^3")
