"""
deck/deck_stern.py — stern deck lid (DESIGN.md v1).

Local frame: plate bottom on XY at Z=0 (top of hull deck flange), +Z up.
Plate uses stern-segment local Y: screw holes land at (±45, Y=25, 75, 125)
to match hull_stern deck-flange bosses; plate spans Y = 1..159 (158 long).

Same construction as deck_mid (chamfered plate + downward locating lip),
without the cannon pad. Features:
  - Plate 124 x 158 x 3, corners chamfered 6 (plan view).
  - Downward inner locating lip: rim outer 105 x 145, wall 3, 5 deep.
  - 6x Ø3.4 screw holes at (±45, Y=25, 75, 125).
  - Ø30 pump-well access hole at (+32, Y=45) (over the wet-well).
  - Ø8 wire hole at (-20, Y=100).
"""

import build123d as bd

# Plate
PLATE_W = 124.0            # X
PLATE_L = 158.0            # Y
PLATE_T = 3.0
CHAMFER = 6.0
Y0 = 1.0
Y1 = Y0 + PLATE_L
YC = (Y0 + Y1) / 2.0       # 80.0

# Locating lip (downward)
LIP_W = 105.0
LIP_L = 145.0
LIP_DEPTH = 5.0
LIP_WALL = 3.0

# Screw holes (match hull_stern flange bosses)
SCREW_D = 3.4
SCREW_X = 45.0
SCREW_YS = (25.0, 75.0, 125.0)

# Pump-well access hole
ACCESS_D = 30.0
ACCESS_X = 32.0
ACCESS_Y = 45.0

# Wire hole
WIRE_D = 8.0
WIRE_X = -20.0
WIRE_Y = 100.0


def _cyl(d: float, h: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(d / 2.0, h).moved(bd.Location((x, y, z0 + h / 2.0)))


def _box(lx: float, ly: float, lz: float, cx: float, cy: float,
         z0: float) -> bd.Part:
    return bd.Box(lx, ly, lz).moved(bd.Location((cx, cy, z0 + lz / 2.0)))


def _plate() -> bd.Part:
    hx = PLATE_W / 2.0
    c = CHAMFER
    pts = [
        (-hx + c, Y0), (hx - c, Y0), (hx, Y0 + c), (hx, Y1 - c),
        (hx - c, Y1), (-hx + c, Y1), (-hx, Y1 - c), (-hx, Y0 + c),
    ]
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XY):
            with bd.BuildLine():
                bd.Polyline(*pts, close=True)
            bd.make_face()
        bd.extrude(amount=PLATE_T, dir=(0, 0, 1))
    return bp.part


def gen_step() -> bd.Part:
    part = _plate()

    # Downward locating lip (perimeter rim), Z = -LIP_DEPTH..0
    lip = _box(LIP_W, LIP_L, LIP_DEPTH, 0.0, YC, -LIP_DEPTH)
    lip = lip.cut(_box(LIP_W - 2 * LIP_WALL, LIP_L - 2 * LIP_WALL,
                       LIP_DEPTH + 2.0, 0.0, YC, -LIP_DEPTH - 1.0))
    part = part.fuse(lip)

    # 6x Ø3.4 screw holes
    for sx in (-SCREW_X, SCREW_X):
        for sy in SCREW_YS:
            part = part.cut(_cyl(SCREW_D, PLATE_T + 2.0, sx, sy, -1.0))

    # Ø30 pump-well access hole
    part = part.cut(_cyl(ACCESS_D, PLATE_T + 2.0, ACCESS_X, ACCESS_Y, -1.0))

    # Ø8 wire hole
    part = part.cut(_cyl(WIRE_D, PLATE_T + 2.0, WIRE_X, WIRE_Y, -1.0))

    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm "
          f"(expect 124 x 158 x 8)")
    print(f"solids: {len(p.solids())} (expect 1)")
    assert abs(sz.X - PLATE_W) < 1e-6 and abs(sz.Y - PLATE_L) < 1e-6
    assert abs(sz.Z - (PLATE_T + LIP_DEPTH)) < 1e-6
    assert len(p.solids()) == 1
