"""
jetdrive/nozzle.py — steerable jet nozzle (DESIGN.md v1).

Local frame: pivot axis = Z through the origin; flow along +Y.
The bell face (inlet mouth) sits at Y=-14, so the vertical pivot axis is
14 from the bell face — matching the nozzle_plate lug holes at 14 aft of
the plate face (bell mouth registers at the plate face; the Ø34 ID bell
rides over the plate's Ø32.8 OD stub with ~0.6 diametral clearance).

Features:
  - Inlet bell Ø34 ID x 8 long, wall 2.4 (Ø38.8 OD), Y=-14..-6.
  - Converging cone Ø34 ID -> Ø15 ID outlet over 34 (Y=-6..28), wall 2.4.
  - All bores SUBTRACTIVE: outer solid built first, flow cavity cut out.
  - Top + bottom Ø7 pivot bosses on the Z axis with Ø2.6 pilots drilled
    8 deep from each boss end face (M3 self-tap pivot pins).
  - Starboard (+X) steering horn: 2.5 thick arm reaching 18 out from the
    body wall, Ø2.1 pushrod hole at the tip.

Print: outlet up.
"""

import build123d as bd

# ── Flow path ───────────────────────────────────────────────────
WALL = 2.4
BELL_IR = 17.0             # Ø34 ID
BELL_OR = BELL_IR + WALL   # 19.4
BELL_L = 8.0
BELL_Y0 = -14.0            # bell face (inlet mouth); pivot axis at Y=0
BELL_Y1 = BELL_Y0 + BELL_L                 # -6
OUT_IR = 7.5               # Ø15 outlet
OUT_OR = OUT_IR + WALL     # 9.9
CONE_L = 34.0
CONE_Y1 = BELL_Y1 + CONE_L                 # 28

# ── Pivot bosses ────────────────────────────────────────────────
BOSS_R = 3.5               # Ø7
BOSS_TOP = 26.0            # boss end face height above axis
BOSS_ROOT = 10.0           # embedded start (inside flow, trimmed by cavity)
PILOT_R = 1.3              # Ø2.6
PILOT_DEPTH = 8.0

# ── Steering horn ───────────────────────────────────────────────
HORN_T = 2.5               # thickness (Z)
HORN_W = 10.0              # width (Y)
HORN_REACH = 18.0          # beyond the body wall at Y=0 (outer r ~17.7)
HORN_ROOT_X = 10.0         # embedded start (trimmed by cavity)
HORN_TIP_X = 17.7 + HORN_REACH             # ~35.7
HORN_HOLE_R = 1.05         # Ø2.1
HORN_HOLE_X = HORN_TIP_X - 3.0


def _cyl_y(radius: float, y0: float, y1: float, x: float = 0.0,
           z: float = 0.0) -> bd.Part:
    c = bd.Cylinder(radius, y1 - y0,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    c = c.rotate(bd.Axis.X, -90)  # Z -> Y
    return c.move(bd.Location((x, (y0 + y1) / 2.0, z)))


def _cone_y(r_start: float, r_end: float, y0: float, y1: float) -> bd.Part:
    c = bd.Cone(bottom_radius=r_start, top_radius=r_end, height=y1 - y0,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    c = c.rotate(bd.Axis.X, -90)  # +Z -> +Y
    return c.move(bd.Location((0, y0, 0)))


def gen_step() -> bd.Part:
    # ═══ Step 1: outer solid (bell + cone) ═══
    outer_bell = _cyl_y(BELL_OR, BELL_Y0, BELL_Y1)
    outer_cone = _cone_y(BELL_OR, OUT_OR, BELL_Y1, CONE_Y1)
    body = outer_bell.fuse(outer_cone)

    # ═══ Step 2: pivot bosses + steering horn (fused before the cavity
    # cut so their inner ends are trimmed flush with the flow path) ═══
    for s in (1.0, -1.0):
        boss = bd.Cylinder(BOSS_R, BOSS_TOP - BOSS_ROOT,
                           align=(bd.Align.CENTER, bd.Align.CENTER,
                                  bd.Align.MIN))
        boss = boss.move(bd.Location((0, 0, BOSS_ROOT)))
        if s < 0:
            boss = boss.rotate(bd.Axis.Y, 180)
        body = body.fuse(boss)

    horn = bd.Box(HORN_TIP_X - HORN_ROOT_X, HORN_W, HORN_T,
                  align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.CENTER))
    horn = horn.move(bd.Location((HORN_ROOT_X, 0, 0)))
    body = body.fuse(horn)

    # ═══ Step 3: SUBTRACTIVE flow cavity (bell + cone + outlet overshoot) ═══
    cavity = _cyl_y(BELL_IR, BELL_Y0 - 1.5, BELL_Y1)
    cavity = cavity.fuse(_cone_y(BELL_IR, OUT_IR, BELL_Y1, CONE_Y1))
    cavity = cavity.fuse(_cyl_y(OUT_IR, CONE_Y1 - 2.0, CONE_Y1 + 2.0))
    body = body.cut(cavity)

    # ═══ Step 4: pivot pilots, 8 deep from each boss end face ═══
    for s in (1.0, -1.0):
        pilot = bd.Cylinder(PILOT_R, PILOT_DEPTH + 1.0,
                            align=(bd.Align.CENTER, bd.Align.CENTER,
                                   bd.Align.MAX))
        pilot = pilot.move(bd.Location((0, 0, BOSS_TOP + 1.0)))
        if s < 0:
            pilot = pilot.rotate(bd.Axis.Y, 180)
        body = body.cut(pilot)

    # ═══ Step 5: pushrod hole at horn tip ═══
    hole = bd.Cylinder(HORN_HOLE_R, HORN_T + 4.0,
                       align=(bd.Align.CENTER, bd.Align.CENTER,
                              bd.Align.CENTER))
    body = body.cut(hole.move(bd.Location((HORN_HOLE_X, 0, 0))))

    return body


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"solids: {len(p.solids())}, volume: {p.volume / 1000.0:.2f} cm^3")
