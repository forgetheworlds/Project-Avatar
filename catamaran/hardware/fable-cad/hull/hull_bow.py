"""
hull_bow.py — wave-piercing bow segment (fable-cad DESIGN.md v1).

Hull frame, local Y: 0 = stem tip, 160 = aft joint face.
X = beam (+X starboard), Z = height (keel Z=0).

Lofted deep-V outer shell through XZ stations at Y = 0/40/80/120/160 with
beam scale factors 0.05/0.35/0.65/0.88/1.00 (X scaled only; keel stays Z=0,
deck stays Z=72). Matching inner loft (Y=WALL..157) subtracted for the
cavity, leaving a solid aft bulkhead (sealed foam-filled buoyancy chamber).
Integral full deck plate Z 69.6..72 with a Ø10 foam-fill hole at (0, 140).

Aft (+Y) joint face per DESIGN.md joint interface:
  - 2 alignment pins Ø3.0 x 4.0 tall at (±30, 45)
  - 4 bosses Ø8 x 8 deep with Ø2.6 pilot holes (axis Y) at (±38, 58), (±24, 30)
  - bulkhead otherwise solid (no wire hole, no clearance holes)

Print upright on the joint face. ~110 g.
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
BOSS_D = 8.0
BOSS_DEPTH = 8.0
PILOT_D = 2.6
PILOT_DEPTH = 10.0    # pilot drilled 10 deep from the joint face (M3x12)

# ── Bow loft schedule ──
STATION_Y = [0.0, 40.0, 80.0, 120.0, 160.0]
STATION_S = [0.05, 0.35, 0.65, 0.88, 1.00]
MIN_HALF_W = 1.2      # clamp for inner sections near the stem

FOAM_HOLE_D = 10.0
FOAM_HOLE_Y = 140.0


def _scale_at(y: float) -> float:
    """Linear interpolation of the beam scale schedule."""
    for i in range(len(STATION_Y) - 1):
        y0, y1 = STATION_Y[i], STATION_Y[i + 1]
        if y0 <= y <= y1:
            f = (y - y0) / (y1 - y0)
            return STATION_S[i] + f * (STATION_S[i + 1] - STATION_S[i])
    return STATION_S[-1]


def _outer_pts(s: float):
    return [
        (0.0, 0.0),
        (HALF_BEAM * s, CHINE_H),
        (DECK_HALF * s, DEPTH),
        (-DECK_HALF * s, DEPTH),
        (-HALF_BEAM * s, CHINE_H),
    ]


def _inner_pts(s: float):
    cx = max(IN_CHINE_X * s, MIN_HALF_W)
    dx = max(IN_DECK_X * s, MIN_HALF_W)
    return [
        (0.0, IN_KEEL_Z),
        (cx, IN_CHINE_Z),
        (dx, DEPTH),
        (-dx, DEPTH),
        (-cx, IN_CHINE_Z),
    ]


def _cyl_y(d: float, y0: float, y1: float, x: float, z: float) -> bd.Part:
    """Cylinder of diameter d along +Y from y0 to y1, axis at (x, z)."""
    c = bd.Cylinder(
        d / 2.0, y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return c.rotate(bd.Axis.X, -90).moved(bd.Location((x, y0, z)))


def gen_step() -> bd.Part:
    # Outer lofted shell (Plane.XZ normal is -Y, so offset(-y) -> station at +y)
    # NOTE: BuildLine/make_face must stay inline in this frame — build123d
    # scopes builder auto-registration to the frame that created the builder.
    with bd.BuildPart() as outer_bp:
        for y in STATION_Y:
            pts = _outer_pts(_scale_at(y))
            with bd.BuildSketch(bd.Plane.XZ.offset(-y)):
                with bd.BuildLine():
                    for a, b in zip(pts, pts[1:] + pts[:1]):
                        bd.Line(a, b)
                bd.make_face()
        bd.loft(ruled=True)
    outer = outer_bp.part

    # Inner loft, Y = WALL .. SEG_L - BULK_T (aft bulkhead stays solid)
    inner_ys = [WALL, 40.0, 80.0, 120.0, SEG_L - BULK_T]
    with bd.BuildPart() as inner_bp:
        for y in inner_ys:
            pts = _inner_pts(_scale_at(y))
            with bd.BuildSketch(bd.Plane.XZ.offset(-y)):
                with bd.BuildLine():
                    for a, b in zip(pts, pts[1:] + pts[:1]):
                        bd.Line(a, b)
                bd.make_face()
        bd.loft(ruled=True)
    cavity = inner_bp.part

    hull = outer.cut(cavity)

    # Integral deck plate Z 69.6..72: slab intersected with the outer envelope
    slab = bd.Box(
        2.0 * DECK_HALF + 2.0, SEG_L, FLANGE_T,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).moved(bd.Location((0.0, 0.0, DEPTH - FLANGE_T)))
    deck = outer.intersect(slab)
    deck_solids = list(deck) if isinstance(deck, bd.ShapeList) else [deck]
    hull = hull.fuse(*deck_solids)

    # Foam-fill hole Ø10 through the deck at (0, 140)
    foam = bd.Cylinder(
        FOAM_HOLE_D / 2.0, FLANGE_T + 4.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).moved(bd.Location((0.0, FOAM_HOLE_Y, DEPTH - FLANGE_T - 2.0)))
    hull = hull.cut(foam)

    # Aft joint face (+Y): alignment pins
    for x, z in PIN_POS:
        hull = hull.fuse(_cyl_y(PIN_D, SEG_L, SEG_L + PIN_L, x, z))

    # Aft joint face: Ø8 bosses 8 deep behind the bulkhead
    for x, z in BOLT_POS:
        hull = hull.fuse(_cyl_y(BOSS_D, SEG_L - BOSS_DEPTH, SEG_L, x, z))

    # Ø2.6 pilot holes, axis Y, drilled from the joint face into the bosses
    for x, z in BOLT_POS:
        hull = hull.cut(_cyl_y(PILOT_D, SEG_L - PILOT_DEPTH, SEG_L + 1.0, x, z))

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
