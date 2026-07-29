"""
deck/deck_mid.py — mid deck lid (DESIGN.md v1).

Local frame: plate bottom on XY at Z=0 (top of hull deck flange), +Z up.
Plate uses mid-segment local Y: screw holes land at (±45, Y=30, 80, 130)
to match hull_mid deck-flange bosses; plate spans Y = 1..159 (158 long).

Features:
  - Plate 124 x 158 x 3, corners chamfered 6 (plan view).
  - Downward inner locating lip: rim outer 105 x 145, wall 3, 5 deep.
  - 6x Ø3.4 screw holes at (±45, Y=30, 80, 130).
  - Cannon/turret pad: raised Ø56 x 3 disc at (0, Y=55) with
      4x Ø2.6 pilots on Ø32 PCD at 45° positions (cannon flange), and
      4x Ø2.6 pilots on Ø44 PCD at 0/90/180/270° (turret base),
      i.e. the two patterns are offset 45° from each other.
  - Ø10 wire grommet hole at (0, Y=120).
"""

import math
import build123d as bd

# Plate
PLATE_W = 124.0            # X
PLATE_L = 158.0            # Y
PLATE_T = 3.0
CHAMFER = 6.0              # plan-view corner chamfer
Y0 = 1.0                   # plate spans Y0..Y0+PLATE_L (segment-local Y)
Y1 = Y0 + PLATE_L
YC = (Y0 + Y1) / 2.0       # 80.0

# Locating lip (downward)
LIP_W = 105.0
LIP_L = 145.0
LIP_DEPTH = 5.0
LIP_WALL = 3.0

# Screw holes (match hull_mid flange bosses)
SCREW_D = 3.4
SCREW_X = 45.0
SCREW_YS = (30.0, 80.0, 130.0)

# Cannon/turret pad
PAD_D = 56.0
PAD_T = 3.0
PAD_X = 0.0
PAD_Y = 55.0
PILOT_D = 2.6
PCD32 = 32.0               # cannon flange pattern — 45° clocking
PCD44 = 44.0               # turret base pattern — 0/90° clocking

# Wire hole
WIRE_D = 10.0
WIRE_X = 0.0
WIRE_Y = 120.0


def _cyl(d: float, h: float, x: float, y: float, z0: float) -> bd.Part:
    return bd.Cylinder(d / 2.0, h).moved(bd.Location((x, y, z0 + h / 2.0)))


def _box(lx: float, ly: float, lz: float, cx: float, cy: float,
         z0: float) -> bd.Part:
    return bd.Box(lx, ly, lz).moved(bd.Location((cx, cy, z0 + lz / 2.0)))


def _plate() -> bd.Part:
    """Chamfered-corner plate, Z = 0..PLATE_T."""
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


def _pcd_points(pcd: float, start_deg: float):
    r = pcd / 2.0
    for i in range(4):
        a = math.radians(start_deg + 90.0 * i)
        yield (r * math.cos(a), r * math.sin(a))


def gen_step() -> bd.Part:
    part = _plate()

    # Downward locating lip (perimeter rim), Z = -LIP_DEPTH..0
    lip = _box(LIP_W, LIP_L, LIP_DEPTH, 0.0, YC, -LIP_DEPTH)
    lip = lip.cut(_box(LIP_W - 2 * LIP_WALL, LIP_L - 2 * LIP_WALL,
                       LIP_DEPTH + 2.0, 0.0, YC, -LIP_DEPTH - 1.0))
    part = part.fuse(lip)

    # Raised cannon/turret pad, Z = PLATE_T..PLATE_T+PAD_T
    part = part.fuse(_cyl(PAD_D, PAD_T, PAD_X, PAD_Y, PLATE_T))

    # 6x Ø3.4 screw holes (through plate only)
    for sx in (-SCREW_X, SCREW_X):
        for sy in SCREW_YS:
            part = part.cut(_cyl(SCREW_D, PLATE_T + 2.0, sx, sy, -1.0))

    # Pad pilots: Ø32 PCD @ 45° and Ø44 PCD @ 0° (through pad + plate)
    pilot_h = PLATE_T + PAD_T + 2.0
    for dx, dy in _pcd_points(PCD32, 45.0):
        part = part.cut(_cyl(PILOT_D, pilot_h, PAD_X + dx, PAD_Y + dy, -1.0))
    for dx, dy in _pcd_points(PCD44, 0.0):
        part = part.cut(_cyl(PILOT_D, pilot_h, PAD_X + dx, PAD_Y + dy, -1.0))

    # Wire grommet hole
    part = part.cut(_cyl(WIRE_D, PLATE_T + 2.0, WIRE_X, WIRE_Y, -1.0))

    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm "
          f"(expect 124 x 158 x 11)")
    print(f"solids: {len(p.solids())} (expect 1)")
    assert abs(sz.X - PLATE_W) < 1e-6 and abs(sz.Y - PLATE_L) < 1e-6
    assert abs(sz.Z - (PLATE_T + PAD_T + LIP_DEPTH)) < 1e-6
    assert len(p.solids()) == 1
