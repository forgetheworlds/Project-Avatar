"""
hull_bow.py — frigate-style wave-piercing bow with pointed raked stem.

Hull frame, local Y: prow tip at Y=0 (forward-most), aft joint at Y=SEG_L.
X = beam (+starboard), Z = height (keel Z=0, deck Z=DEPTH).

Build method: loft a tapered deep-V (stable, same 5-vertex topology), then
cut the stem and deck sheer with true YZ spline edges so the side silhouette
is continuously fair and meets at a prow point — not a vertical brick face.
"""

from __future__ import annotations

import math
import build123d as bd

from hydrostatics import bow_deck_scale, bow_scale, smootherstep

# ── Global hull constants (match mid/stern) ─────────────────────
BEAM = 120.0
HALF_BEAM = 60.0
DEPTH = 72.0
DEADRISE_DEG = 20.0
CHINE_H = HALF_BEAM * math.tan(math.radians(DEADRISE_DEG))  # 21.84
DECK_HALF = 64.0
WALL = 2.4
SEG_L = 160.0
BULK_T = 3.0
FLANGE_T = 2.4

IN_KEEL_Z = WALL / math.cos(math.radians(DEADRISE_DEG))
IN_CHINE_X = 57.16
IN_CHINE_Z = 22.88
IN_DECK_X = 61.29

# Joint interface (unchanged — mates hull_mid)
BOLT_POS = [(38.0, 58.0), (-38.0, 58.0), (24.0, 30.0), (-24.0, 30.0)]
PIN_POS = [(30.0, 45.0), (-30.0, 45.0)]
PIN_D = 3.0
PIN_L = 4.0
BOSS_D = 8.0
BOSS_DEPTH = 8.0
PILOT_D = 2.6
PILOT_DEPTH = 10.0

# ── Globally fair bow / stem / sheer ─────────────────────────────
KEEL_ENTRY = 42.0
STATION_Y = [0.0, 12.0, 28.0, 48.0, 72.0, 100.0, 130.0, 160.0]
MIN_HALF_W = 1.0

SHEER_LEN = 96.0
SHEER_DROP = 8.0
TIP_Z = DEPTH - SHEER_DROP  # 64; more forward reserve/freeboard

FOAM_HOLE_D = 10.0
FOAM_HOLE_Y = 130.0


def stem_y(z: float) -> float:
    """Y of the globally fair raked stem edge."""
    if z >= TIP_Z:
        return 0.0
    return KEEL_ENTRY * (1.0 - smootherstep(z / TIP_Z))


def sheer_z(y: float) -> float:
    if y >= SHEER_LEN:
        return DEPTH
    return TIP_Z + (DEPTH - TIP_Z) * smootherstep(y / SHEER_LEN)


def _outer_pts(y: float):
    """Full-height deep-V, always 5 vertices, same winding."""
    chine_x = max(HALF_BEAM * bow_scale(y), MIN_HALF_W)
    deck_x = max(DECK_HALF * bow_deck_scale(y), MIN_HALF_W)
    return [
        (0.0, 0.0),
        (chine_x, CHINE_H),
        (deck_x, DEPTH),
        (-deck_x, DEPTH),
        (-chine_x, CHINE_H),
    ]


def _inner_pts(y: float):
    """Offset-like cavity that converges to the exact joint inner profile."""
    outer = _outer_pts(y)
    cx = max(outer[1][0] - (HALF_BEAM - IN_CHINE_X), MIN_HALF_W)
    dx = max(outer[2][0] - (DECK_HALF - IN_DECK_X), MIN_HALF_W)
    if abs(y - (SEG_L - BULK_T)) < 1e-6:
        # The cavity terminates at the forward face of the exact joint bulkhead.
        cx, dx = IN_CHINE_X, IN_DECK_X
    return [
        (0.0, IN_KEEL_Z),
        (cx, IN_CHINE_Z),
        (dx, DEPTH - 0.5),
        (-dx, DEPTH - 0.5),
        (-cx, IN_CHINE_Z),
    ]


def _close(pts):
    return list(zip(pts, pts[1:] + pts[:1]))


def _cyl_y(d: float, y0: float, y1: float, x: float, z: float) -> bd.Part:
    c = bd.Cylinder(
        d / 2.0, y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return c.rotate(bd.Axis.X, -90).moved(bd.Location((x, y0, z)))


def _extrude_yz_spline_region(
    curve_pts: list[tuple[float, float]],
    close_pts: list[tuple[float, float]],
    amount: float,
) -> bd.Part:
    """Extrude a closed YZ region whose hydrodynamic edge is a true spline."""
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.YZ):
            with bd.BuildLine():
                bd.Spline(*curve_pts)
                bd.Polyline(curve_pts[-1], *close_pts, curve_pts[0])
            bd.make_face()
        bd.extrude(amount=amount, both=True)
    return bp.part


def _stem_cutter() -> bd.Part:
    """Discard everything forward of the stem curve (Y < stem_y(Z))."""
    curve = [
        (stem_y(TIP_Z * i / 12.0) - 0.02, TIP_Z * i / 12.0)
        for i in range(13)
    ]
    close = [(-6.0, TIP_Z + 0.02), (-6.0, -4.0), (KEEL_ENTRY + 4.0, -4.0)]
    return _extrude_yz_spline_region(curve, close, DECK_HALF + 30.0)


def _sheer_cutter() -> bd.Part:
    """Discard everything above the sheer curve."""
    curve = [
        (SHEER_LEN * i / 12.0, sheer_z(SHEER_LEN * i / 12.0) + 0.05)
        for i in range(13)
    ]
    close = [
        (SHEER_LEN + 8.0, DEPTH + 0.5),
        (SHEER_LEN + 8.0, DEPTH + SHEER_DROP + 8.0),
        (-4.0, DEPTH + SHEER_DROP + 8.0),
        (-4.0, TIP_Z),
    ]
    return _extrude_yz_spline_region(curve, close, DECK_HALF + 30.0)


def gen_step() -> bd.Part:
    # 1) Stable full-height tapered loft
    with bd.BuildPart() as outer_bp:
        for y in STATION_Y:
            pts = _outer_pts(y)
            with bd.BuildSketch(bd.Plane.XZ.offset(-y)):
                with bd.BuildLine():
                    for a, b in _close(pts):
                        bd.Line(a, b)
                bd.make_face()
        bd.loft(ruled=False)
    # OCC lofts can overshoot between sections.  The hard envelope makes
    # 128 mm an invariant rather than an assumption.
    beam_envelope = bd.Box(
        2.0 * DECK_HALF,
        SEG_L + 4.0,
        DEPTH + 8.0,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).moved(bd.Location((0.0, -2.0, -4.0)))
    clipped = outer_bp.part.intersect(beam_envelope)
    clipped_shapes = list(clipped) if isinstance(clipped, bd.ShapeList) else [clipped]
    outer = max(
        (shape for shape in clipped_shapes if shape is not None),
        key=lambda shape: shape.volume,
    )

    stem_cut = _stem_cutter()
    sheer_cut = _sheer_cutter()
    hull = outer.cut(stem_cut).cut(sheer_cut)

    # 2) Cavity — sealed tip plug forward of KEEL_ENTRY
    cavity_start = KEEL_ENTRY + 12.0
    inner_ys = [cavity_start, 72.0, 96.0, 122.0, 144.0, SEG_L - BULK_T]
    with bd.BuildPart() as inner_bp:
        for y in inner_ys:
            pts = _inner_pts(y)
            with bd.BuildSketch(bd.Plane.XZ.offset(-y)):
                with bd.BuildLine():
                    for a, b in _close(pts):
                        bd.Line(a, b)
                bd.make_face()
        bd.loft(ruled=False)
    cavity = inner_bp.part.cut(stem_cut).cut(sheer_cut)
    hull = hull.cut(cavity)

    # 3) Re-cap sealed tip (cutters can open the knife edge)
    tip_box = bd.Box(
        2.0 * DECK_HALF, KEEL_ENTRY + 8.0, DEPTH + 4.0,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).moved(bd.Location((0.0, -1.0, -1.0)))
    tip_cap = outer.intersect(tip_box)
    tip_solids = list(tip_cap) if isinstance(tip_cap, bd.ShapeList) else [tip_cap]
    for s in tip_solids:
        if s is not None and s.volume > 1e-3:
            hull = hull.fuse(s.cut(stem_cut).cut(sheer_cut))

    # 4) Deck flange along sheered top
    slab = bd.Box(
        2.0 * DECK_HALF + 4.0, SEG_L + 4.0, FLANGE_T + SHEER_DROP + 4.0,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).moved(bd.Location((0.0, -2.0, TIP_Z - FLANGE_T - 1.0)))
    deck = outer.intersect(slab)
    deck_solids = list(deck) if isinstance(deck, bd.ShapeList) else [deck]
    for s in deck_solids:
        if s is not None and s.volume > 1e-3:
            hull = hull.fuse(s.cut(stem_cut).cut(sheer_cut))

    # 5) Clean foredeck: the cannon moves to the mid deck.
    foam = bd.Cylinder(
        FOAM_HOLE_D / 2.0, FLANGE_T + SHEER_DROP + 6.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).moved(bd.Location((0.0, FOAM_HOLE_Y, DEPTH - FLANGE_T - 2.0)))
    hull = hull.cut(foam)

    for x, z in PIN_POS:
        hull = hull.fuse(_cyl_y(PIN_D, SEG_L, SEG_L + PIN_L, x, z))
    for x, z in BOLT_POS:
        hull = hull.fuse(_cyl_y(BOSS_D, SEG_L - BOSS_DEPTH, SEG_L, x, z))
        hull = hull.cut(_cyl_y(PILOT_D, SEG_L - PILOT_DEPTH, SEG_L + 1.0, x, z))

    if not isinstance(hull, bd.Part):
        hull = bd.Part(hull.wrapped)
    hull.label = "hull_bow"
    return hull


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"Size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"BBox: min({bb.min.X:.2f},{bb.min.Y:.2f},{bb.min.Z:.2f}) "
          f"max({bb.max.X:.2f},{bb.max.Y:.2f},{bb.max.Z:.2f})")
    print(f"Volume: {sum(s.volume for s in p.solids()) / 1000.0:.1f} cm^3")
    print(f"solids: {len(p.solids())}")
    print(f"Tip Z={TIP_Z}, KEEL_ENTRY={KEEL_ENTRY}, SHEER_DROP={SHEER_DROP}")
    assert len(p.solids()) == 1
    assert sz.X <= 2.0 * DECK_HALF + 0.05
    assert abs(sz.Y - (SEG_L + PIN_L)) < 0.1
    assert sz.Z <= DEPTH + 0.05
    joint_inner = _inner_pts(SEG_L - BULK_T)
    assert abs(joint_inner[1][0] - IN_CHINE_X) < 1e-9
    assert abs(joint_inner[2][0] - IN_DECK_X) < 1e-9
    print("self-check OK")
