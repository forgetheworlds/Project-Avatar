"""
jetdrive/servo_bracket.py — SG90 steering-servo mount.

Local frame: base plate on XY, +Z up.

Features:
  - Base 46 x 20 x 3 with two 3.4 x 6 mounting slots at X=±14.
  - SG90 pocket: 23.2 x 12.6 through-opening in a 3-wall cage 16 tall
    (two side walls + one back wall; front open for the wire exit).
  - Two Ø2.1 servo-flange pilots at X=±14 in the side-wall rims.
  - Assembly placement keeps the complete bracket below the stern deck and
    locates the servo output/linkage at the dedicated X=24, Z=38 passage.

Print: flat.
"""

import build123d as bd

from interfaces import assert_single_solid

# ── Base ────────────────────────────────────────────────────────
BASE_X = 46.0
BASE_Y = 20.0
BASE_T = 3.0

# ── Mounting slots ──────────────────────────────────────────────
SLOT_X = 14.0              # slot centers (28 mm span = stern pilots at +4/+32)
SLOT_LEN = 6.0             # overall along X
SLOT_W = 3.4

# ── SG90 pocket / cage ──────────────────────────────────────────
POCKET_X = 23.2
POCKET_Y = 12.6
CAGE_H = 16.0              # above base top: Z = 3..19
SIDE_WALL_T = 4.0          # thick enough to carry the Ø2.1 pilots at ±14
BACK_WALL_T = 2.4
PILOT_X = 14.0
PILOT_R = 1.05             # Ø2.1
PILOT_DEPTH = 8.0


def gen_step() -> bd.Part:
    # ═══ Step 1: base plate ═══
    base = bd.Box(BASE_X, BASE_Y, BASE_T,
                  align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))

    # ═══ Step 2: cage walls (2 sides + back, front open) ═══
    wall_y0 = -POCKET_Y / 2.0                      # -6.3
    wall_y1 = POCKET_Y / 2.0 + BACK_WALL_T         # 8.7
    wall_len = wall_y1 - wall_y0
    body = base
    for s in (1.0, -1.0):
        side = bd.Box(SIDE_WALL_T, wall_len, CAGE_H,
                      align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        side = side.move(bd.Location(
            (s * (POCKET_X / 2.0 + SIDE_WALL_T / 2.0),
             (wall_y0 + wall_y1) / 2.0, BASE_T)))
        body = body.fuse(side)
    back_span = POCKET_X + 2 * SIDE_WALL_T
    back = bd.Box(back_span, BACK_WALL_T, CAGE_H,
                  align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    back = back.move(bd.Location(
        (0, POCKET_Y / 2.0 + BACK_WALL_T / 2.0, BASE_T)))
    body = body.fuse(back)

    # ═══ Step 3: servo pocket through the base ═══
    pocket = bd.Box(POCKET_X, POCKET_Y, BASE_T + 2.0,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    pocket = pocket.move(bd.Location((0, 0, -1.0)))
    body = body.cut(pocket)

    # ═══ Step 4: base mounting slots (3.4 x 6 stadium) at X=±14 ═══
    for s in (1.0, -1.0):
        slot = bd.Box(SLOT_LEN - SLOT_W, SLOT_W, BASE_T + 2.0,
                      align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        for e in (1.0, -1.0):
            end = bd.Cylinder(
                SLOT_W / 2.0, BASE_T + 2.0,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
            end = end.move(bd.Location((e * (SLOT_LEN - SLOT_W) / 2.0, 0, 0)))
            slot = slot.fuse(end)
        slot = slot.move(bd.Location((s * SLOT_X, 0, -1.0)))
        body = body.cut(slot)

    # ═══ Step 5: Ø2.1 servo-flange pilots at ±14 in the wall rims ═══
    for s in (1.0, -1.0):
        pilot = bd.Cylinder(PILOT_R, PILOT_DEPTH + 1.0,
                            align=(bd.Align.CENTER, bd.Align.CENTER,
                                   bd.Align.MAX))
        pilot = pilot.move(
            bd.Location((s * PILOT_X, 0, BASE_T + CAGE_H + 1.0)))
        body = body.cut(pilot)

    body.label = "servo_bracket"
    assert_single_solid(body, "servo_bracket", min_volume=2_000.0)
    bbox = body.bounding_box()
    assert abs(bbox.size.X - BASE_X) < 0.05
    assert abs(bbox.size.Y - BASE_Y) < 0.05
    assert abs(bbox.size.Z - (BASE_T + CAGE_H)) < 0.05
    return body


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"solids: {len(p.solids())}, volume: {p.volume / 1000.0:.2f} cm^3")
