"""
hull_mid.py — constant-section mid hull segment (fable-cad DESIGN.md v1).

Hull frame, local Y: 0 = forward joint face, 160 = aft joint face.
X = beam (+X starboard), Z = height (keel Z=0).

Extruded deep-V outer/inner section, hollow, open deck with FLANGE_W inward
deck flange lips both sides full length. Both ends carry BULK_T bulkheads
flush with the end faces (formed by leaving the end 3 mm of the extrusion
solid).

Forward (−Y) joint face per DESIGN.md joint interface:
  - Ø3.4 x 4.5 deep pin sockets at (±30, 45)
  - Ø3.4 through clearance holes at (±38, 58), (±24, 30)
  - Ø22 wire pass hole at (0, 48)
Aft (+Y) joint face:
  - 2 alignment pins Ø3.0 x 4.0 tall at (±30, 45)
  - 4 bosses Ø8 x 8 deep with Ø2.6 pilot holes (axis Y) at (±38, 58), (±24, 30)
  - Ø22 wire pass hole at (0, 48)

Deck-lid screw bosses under the flange: Ø8 hanging 6 below the flange with
Ø2.6 vertical pilots at (±45, Y=30/80/130). Local flange pads bridge the
flange lip out to the boss position so the bosses are fully attached.

Print upright on a joint face. ~105 g.
"""

import math
import build123d as bd

# ── Global hull constants (DESIGN.md, verbatim in every hull-frame part) ──
BEAM = 120.0          # max beam at chine plane
HALF_BEAM = 60.0
DEPTH = 72.0          # keel to deck
DEADRISE_DEG = 20.0
CHINE_H = HALF_BEAM * math.tan(math.radians(DEADRISE_DEG))   # 21.84
DECK_HALF = 64.0      # topside flare: chine (60, 21.84) -> deck edge (64, 72)
WALL = 2.4
SEG_L = 160.0         # each of bow / mid / stern
BULK_T = 3.0          # joint bulkhead thickness
FLANGE_W = 8.0        # inward deck flange lip width (mid + stern)
FLANGE_T = 2.4        # deck flange thickness (Z 69.6..72)
WL = 38.0             # est. static waterline (reference only)

# Inner analytic offset profile (DESIGN.md — identical in all hull segments)
IN_KEEL_Z = WALL / math.cos(math.radians(DEADRISE_DEG))      # 2.554
IN_CHINE_X = 57.16
IN_CHINE_Z = 22.88
IN_DECK_X = 61.29

# ── Segment joint interface (DESIGN.md — identical numbers in all segments) ──
BOLT_POS = [(38.0, 58.0), (-38.0, 58.0), (24.0, 30.0), (-24.0, 30.0)]
PIN_POS = [(30.0, 45.0), (-30.0, 45.0)]
PIN_D = 3.0
PIN_L = 4.0
SOCKET_D = 3.4
SOCKET_DEPTH = 4.5
CLEAR_D = 3.4
BOSS_D = 8.0
BOSS_DEPTH = 8.0
PILOT_D = 2.6
PILOT_DEPTH = 10.0    # pilot drilled 10 deep from the joint face (M3x12)
WIRE_D = 22.0
WIRE_POS = (0.0, 48.0)

# ── Deck flange + lid bosses ──
FLANGE_IN_X = IN_DECK_X - FLANGE_W          # 53.29 flange inner edge
FLANGE_OUT_X = IN_DECK_X + 1.2              # embed lip into the side wall
LID_BOSS_X = 45.0
LID_BOSS_YS = [30.0, 80.0, 130.0]
LID_BOSS_D = 8.0
LID_BOSS_DROP = 6.0                          # boss hangs 6 below the flange
LID_PILOT_D = 2.6
LID_PAD_IN_X = LID_BOSS_X - LID_BOSS_D / 2.0 - 0.5   # 40.5
LID_PAD_LEN = 16.0                           # pad length along Y per boss


def _cyl_y(d: float, y0: float, y1: float, x: float, z: float) -> bd.Part:
    """Cylinder of diameter d along +Y from y0 to y1, axis at (x, z)."""
    c = bd.Cylinder(
        d / 2.0, y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return c.rotate(bd.Axis.X, -90).moved(bd.Location((x, y0, z)))


def _cyl_z(d: float, z0: float, z1: float, x: float, y: float) -> bd.Part:
    """Vertical cylinder of diameter d from z0 to z1, axis at (x, y)."""
    c = bd.Cylinder(
        d / 2.0, z1 - z0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return c.moved(bd.Location((x, y, z0)))


def gen_step() -> bd.Part:
    # Outer prismatic shell, Y 0..160
    outer_pts = [
        (0.0, 0.0),
        (HALF_BEAM, CHINE_H),
        (DECK_HALF, DEPTH),
        (-DECK_HALF, DEPTH),
        (-HALF_BEAM, CHINE_H),
    ]
    # NOTE: BuildLine/make_face must stay inline in this frame — build123d
    # scopes builder auto-registration to the frame that created the builder.
    with bd.BuildPart() as shell_bp:
        with bd.BuildSketch(bd.Plane.XZ):
            with bd.BuildLine():
                for a, b in zip(outer_pts, outer_pts[1:] + outer_pts[:1]):
                    bd.Line(a, b)
            bd.make_face()
        bd.extrude(amount=SEG_L, dir=(0, 1, 0))
    hull = shell_bp.part

    # Interior cavity, Y BULK_T..SEG_L-BULK_T (both bulkheads stay solid).
    # Cut loop overshoots 1 above the deck (side planes extended) to fully
    # open the top.
    side_slope = (IN_DECK_X - IN_CHINE_X) / (DEPTH - IN_CHINE_Z)
    top_x = IN_DECK_X + side_slope * 1.0
    cav_pts = [
        (0.0, IN_KEEL_Z),
        (IN_CHINE_X, IN_CHINE_Z),
        (top_x, DEPTH + 1.0),
        (-top_x, DEPTH + 1.0),
        (-IN_CHINE_X, IN_CHINE_Z),
    ]
    with bd.BuildPart() as cav_bp:
        with bd.BuildSketch(bd.Plane.XZ):
            with bd.BuildLine():
                for a, b in zip(cav_pts, cav_pts[1:] + cav_pts[:1]):
                    bd.Line(a, b)
            bd.make_face()
        bd.extrude(amount=SEG_L - 2.0 * BULK_T, dir=(0, 1, 0))
    hull = hull.cut(cav_bp.part.moved(bd.Location((0.0, BULK_T, 0.0))))

    # Deck flange lips, both sides, full length (Z 69.6..72)
    flange_w = FLANGE_OUT_X - FLANGE_IN_X
    flange_cx = (FLANGE_OUT_X + FLANGE_IN_X) / 2.0
    for sx in (1.0, -1.0):
        lip = bd.Box(
            flange_w, SEG_L, FLANGE_T,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
        ).moved(bd.Location((sx * flange_cx, 0.0, DEPTH - FLANGE_T)))
        hull = hull.fuse(lip)

    # Lid-boss flange pads (bridge the lip inward to X=±45) + bosses + pilots
    pad_w = FLANGE_OUT_X - LID_PAD_IN_X
    pad_cx = (FLANGE_OUT_X + LID_PAD_IN_X) / 2.0
    for sx in (1.0, -1.0):
        for ly in LID_BOSS_YS:
            pad = bd.Box(
                pad_w, LID_PAD_LEN, FLANGE_T,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
            ).moved(bd.Location((sx * pad_cx, ly, DEPTH - FLANGE_T)))
            hull = hull.fuse(pad)
            boss = _cyl_z(
                LID_BOSS_D,
                DEPTH - FLANGE_T - LID_BOSS_DROP,   # 63.6
                DEPTH - 1.0,                        # embed into flange
                sx * LID_BOSS_X, ly,
            )
            hull = hull.fuse(boss)
    for sx in (1.0, -1.0):
        for ly in LID_BOSS_YS:
            pilot = _cyl_z(
                LID_PILOT_D,
                DEPTH - FLANGE_T - LID_BOSS_DROP - 1.0,
                DEPTH + 1.0,
                sx * LID_BOSS_X, ly,
            )
            hull = hull.cut(pilot)

    # Aft (+Y) joint face: pins + pilot bosses
    for x, z in PIN_POS:
        hull = hull.fuse(_cyl_y(PIN_D, SEG_L, SEG_L + PIN_L, x, z))
    for x, z in BOLT_POS:
        hull = hull.fuse(_cyl_y(BOSS_D, SEG_L - BOSS_DEPTH, SEG_L, x, z))
    for x, z in BOLT_POS:
        hull = hull.cut(_cyl_y(PILOT_D, SEG_L - PILOT_DEPTH, SEG_L + 1.0, x, z))

    # Forward (−Y) joint face: clearance holes + pin sockets
    for x, z in BOLT_POS:
        hull = hull.cut(_cyl_y(CLEAR_D, -1.0, BULK_T + 1.0, x, z))
    for x, z in PIN_POS:
        hull = hull.cut(_cyl_y(SOCKET_D, -1.0, SOCKET_DEPTH, x, z))

    # Ø22 wire pass holes through both bulkheads at (0, 48)
    wx, wz = WIRE_POS
    hull = hull.cut(_cyl_y(WIRE_D, -1.0, BULK_T + 1.0, wx, wz))
    hull = hull.cut(_cyl_y(WIRE_D, SEG_L - BULK_T - 1.0, SEG_L + 1.0, wx, wz))

    return hull


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"Size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"BBox: min({bb.min.X:.2f},{bb.min.Y:.2f},{bb.min.Z:.2f}) "
          f"max({bb.max.X:.2f},{bb.max.Y:.2f},{bb.max.Z:.2f})")
    ok = (abs(sz.X - 2 * DECK_HALF) < 0.5
          and abs(sz.Y - (SEG_L + PIN_L)) < 0.5
          and abs(sz.Z - DEPTH) < 0.5)
    print(f"Expected ~128 x 164 x 72: {'OK' if ok else 'MISMATCH'}")
    print(f"Volume: {p.volume / 1000.0:.1f} cm^3")
