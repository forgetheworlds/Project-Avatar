"""
simscale_hull.py — sealed outer hull envelope for SimScale (hydrostatics / CFD).

Upload target: ``simscale_hull.step`` (and optional ``simscale_hull_m.step`` in metres).

What this is
------------
A single **watertight solid** of the *exterior* hull only — no cavities, jet
bore, wet-well, fasteners, or deck hardware. Matches the same beam/deadrise/
bow fairing laws as ``hydrostatics.py`` + ``hull_bow.py``.

Use this in SimScale for:
  - displacement / submerged-volume checks (CAD volume below a WL plane)
  - external-flow CFD (subtract this solid from a water-domain box)
  - free-surface / multiphase setups (hull as a wall)

Do **not** upload ``boat_assembly.step`` or the print segments — those are
full of holes and internals that break meshing.

SimScale import checklist
-------------------------
1. Upload ``simscale_hull.step`` (preferred over STL).
2. Units: geometry is **millimetres**. In SimScale CAD mode, **Scale by 0.001**
   to convert to metres (SimScale's default SI unit), **or** upload
   ``simscale_hull_m.step`` which is already in metres.
3. Confirm one solid body, watertight (no sheets).
4. Design waterline reference: Z = ``WL`` = 35.2 mm (0.0352 m) above keel —
   estimated static WL at ~1.15 kg with open wet-well correction
   (see ``hydrostatics.py``). For hydrostatics, create a cutting plane at
   that Z and keep the submerged volume.
5. For resistance CFD: create a domain box ~3–5 lengths long, ~3 beams
   wide, free surface near Z=WL; hull as no-slip wall.

Coordinate frame (same as hardware/cad hull)
-----------------------------------------
  X = beam (+starboard), Y = length (bow tip Y=0 → transom), Z = up (keel Z=0).
  Length ≈ 480 mm, beam ≈ 128 mm deck, depth 72 mm.
"""

from __future__ import annotations

import math
import build123d as bd

from hydrostatics import bow_deck_scale, bow_scale, smootherstep

# ── Match print hull globals ────────────────────────────────────
BEAM = 120.0
HALF_BEAM = 60.0
DEPTH = 72.0
DEADRISE_DEG = 20.0
CHINE_H = HALF_BEAM * math.tan(math.radians(DEADRISE_DEG))
DECK_HALF = 64.0
SEG_L = 160.0
HULL_L = 3.0 * SEG_L  # 480

KEEL_ENTRY = 42.0
SHEER_LEN = 96.0
SHEER_DROP = 8.0
TIP_Z = DEPTH - SHEER_DROP  # 64
MIN_HALF_W = 1.0

# Design WL from hydrostatics.py / hull_mid (mm above keel)
WL = 35.2

# Dense stations for a fair SimScale meshable surface
BOW_Y = [0.0, 8.0, 18.0, 30.0, 45.0, 65.0, 90.0, 120.0, 160.0]
AFT_Y = [160.0, 240.0, 320.0, 400.0, 480.0]  # mid + stern (global Y)


def stem_y(z: float) -> float:
    if z >= TIP_Z:
        return 0.0
    return KEEL_ENTRY * (1.0 - smootherstep(z / TIP_Z))


def sheer_z(y: float) -> float:
    if y >= SHEER_LEN:
        return DEPTH
    return TIP_Z + (DEPTH - TIP_Z) * smootherstep(y / SHEER_LEN)


def _outer_pts_bow(y_local: float):
    chine_x = max(HALF_BEAM * bow_scale(y_local), MIN_HALF_W)
    deck_x = max(DECK_HALF * bow_deck_scale(y_local), MIN_HALF_W)
    z_deck = sheer_z(y_local)
    return [
        (0.0, 0.0),
        (chine_x, CHINE_H),
        (deck_x, z_deck),
        (-deck_x, z_deck),
        (-chine_x, CHINE_H),
    ]


def _outer_pts_full():
    return [
        (0.0, 0.0),
        (HALF_BEAM, CHINE_H),
        (DECK_HALF, DEPTH),
        (-DECK_HALF, DEPTH),
        (-HALF_BEAM, CHINE_H),
    ]


def _close(pts):
    return list(zip(pts, pts[1:] + pts[:1]))


def _extrude_yz_polygon(yz_pts, amount: float) -> bd.Part:
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.YZ):
            bd.Polygon(*yz_pts)
        bd.extrude(amount=amount, both=True)
    return bp.part


def _stem_cutter() -> bd.Part:
    n = 24
    pts = [(-6.0, DEPTH + 6.0), (-6.0, -4.0), (KEEL_ENTRY + 4.0, -4.0)]
    for i in range(n + 1):
        z = TIP_Z * i / n
        pts.append((stem_y(z) - 0.02, z))
    pts.append((-6.0, TIP_Z + 0.02))
    return _extrude_yz_polygon(pts, DECK_HALF + 40.0)


def _sheer_cutter() -> bd.Part:
    n = 20
    pts = [(-4.0, DEPTH + SHEER_DROP + 8.0), (SHEER_LEN + 8.0, DEPTH + SHEER_DROP + 8.0)]
    pts.append((SHEER_LEN + 8.0, DEPTH + 0.5))
    for i in range(n, -1, -1):
        y = SHEER_LEN * i / n
        pts.append((y, sheer_z(y) + 0.05))
    return _extrude_yz_polygon(pts, DECK_HALF + 40.0)


def gen_step() -> bd.Part:
    """Watertight outer envelope in millimetres (hardware/cad frame)."""
    # 1) Bow loft (local Y = global Y)
    with bd.BuildPart() as bow_bp:
        for y in BOW_Y:
            pts = _outer_pts_bow(y)
            with bd.BuildSketch(bd.Plane.XZ.offset(-y)):
                with bd.BuildLine():
                    for a, b in _close(pts):
                        bd.Line(a, b)
                bd.make_face()
        bd.loft(ruled=False)
    bow = bow_bp.part.cut(_stem_cutter()).cut(_sheer_cutter())

    # 2) Mid + stern constant section (global Y = SEG_L .. HULL_L)
    full = _outer_pts_full()
    with bd.BuildPart() as aft_bp:
        with bd.BuildSketch(bd.Plane.XZ.offset(-SEG_L)):
            with bd.BuildLine():
                for a, b in _close(full):
                    bd.Line(a, b)
            bd.make_face()
        bd.extrude(amount=HULL_L - SEG_L, dir=(0, 1, 0))
    aft = aft_bp.part

    hull = bow.fuse(aft)

    # 3) Seal the open deck with a flush top plate (SimScale needs a closed solid)
    #    Clip to outer envelope so sheer/tip stay fair.
    deck_box = bd.Box(
        2.0 * DECK_HALF + 8.0,
        HULL_L + 4.0,
        3.0,
        align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
    ).moved(bd.Location((0.0, -2.0, TIP_Z - 0.5)))
    sealed = hull.intersect(
        bd.Box(
            2.0 * DECK_HALF + 20.0,
            HULL_L + 20.0,
            DEPTH + 20.0,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN),
        ).moved(bd.Location((0.0, -10.0, -5.0)))
    )
    # Prefer hull itself if already closed enough; fuse a thin deck slab clipped
    deck_cap = hull.intersect(deck_box)
    if isinstance(deck_cap, bd.ShapeList):
        for s in deck_cap:
            if s is not None and getattr(s, "volume", 0) > 1e-3:
                hull = hull.fuse(s)
    elif deck_cap is not None and deck_cap.volume > 1e-3:
        hull = hull.fuse(deck_cap)

    # Ensure single solid
    sols = list(hull.solids())
    if len(sols) > 1:
        hull = sols[0].fuse(*sols[1:])
    return hull


def gen_step_metres() -> bd.Part:
    """Same envelope scaled to metres for direct SimScale SI import."""
    return gen_step().scale(0.001)


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    vol_l = p.volume / 1_000_000.0
    print(f"simscale_hull (mm): {sz.X:.1f} x {sz.Y:.1f} x {sz.Z:.1f} mm")
    print(f"BBox min ({bb.min.X:.2f},{bb.min.Y:.2f},{bb.min.Z:.2f}) "
          f"max ({bb.max.X:.2f},{bb.max.Y:.2f},{bb.max.Z:.2f})")
    print(f"Volume: {vol_l:.3f} L  solids: {len(p.solids())}")
    print(f"Design WL Z={WL} mm  (scale ×0.001 → {WL/1000:.4f} m)")
    print("Upload simscale_hull.step to SimScale; scale 0.001 if units=m.")
