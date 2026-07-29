"""
jetdrive/pump_housing.py — bolt-in jet pump housing (DESIGN.md v1).

Built in the stern-local hull frame: X = beam (+X starboard), Y = length
(stern-local, 0 = forward joint face, 160 = transom aft face), Z = height
(keel Z = 0).

Features:
  - Tunnel Ø28 ID / 2.4 wall (Ø32.8 OD) on axis (X=0, Z=40), Y=64..157.
  - Front wall Y=64..68 (4 thick) on a Ø38 boss: Ø10 shaft hole, 4 radial
    motor-mount slots 3.2 wide, r=8..10, at 90° spacing.
  - Intake duct: flared cavity from the tunnel bottom (opening Y=74..122)
    down to a rectangular mouth |X|<=12, Y=70..120, underside at Z=8.
  - Perimeter intake flange 6 wide (footprint |X|<=18, Y=64..126), flat
    underside at Z=8, 6x Ø3.4 clearance holes at (±15.5, Y=76, 97, 118).
  - 3 integral longitudinal grate bars 2.5 wide x 3 deep across the mouth.
  - Exit flange Ø44 disc Y=153..157, 4x Ø2.6 pilots on Ø42 PCD at 45°
    positions; tunnel bore continues through it.

One fused solid; open flow path from intake mouth to exit flange.
Print: standing on exit flange, tunnel vertical.
"""

import math
import build123d as bd

# ── Tunnel ──────────────────────────────────────────────────────
WALL = 2.4
TUNNEL_ID = 28.0
TUNNEL_IR = TUNNEL_ID / 2.0            # 14.0
TUNNEL_OR = TUNNEL_IR + WALL           # 16.4
AXIS_Z = 40.0                          # tunnel axis height
TUNNEL_Y0 = 64.0
TUNNEL_Y1 = 157.0

# ── Front wall / motor mount ────────────────────────────────────
FRONT_Y0 = 64.0
FRONT_Y1 = 68.0                        # 4 thick
FRONT_BOSS_R = 19.0                    # Ø38 boss
SHAFT_HOLE_R = 5.0                     # Ø10
SLOT_W = 3.2                           # tangential width
SLOT_R0 = 8.0
SLOT_R1 = 10.0

# ── Intake duct / mouth ─────────────────────────────────────────
MOUTH_HALF_X = 12.0                    # |X| <= 12 -> 24 wide
MOUTH_Y0 = 70.0
MOUTH_Y1 = 120.0
TOP_OPEN_Y0 = 74.0                     # opening in tunnel bottom
TOP_OPEN_Y1 = 122.0
MOUTH_Z = 8.0                          # flat flange underside

# ── Intake flange ───────────────────────────────────────────────
FLANGE_W = 6.0                         # perimeter width around mouth
FLANGE_T = 3.0
FLANGE_HOLE_R = 1.7                    # Ø3.4
FLANGE_HOLE_X = 15.5
FLANGE_HOLE_YS = (76.0, 97.0, 118.0)

# ── Grate ───────────────────────────────────────────────────────
GRATE_BAR_W = 2.5
GRATE_BAR_D = 3.0
N_BARS = 3

# ── Exit flange ─────────────────────────────────────────────────
EXIT_R = 22.0                          # Ø44
EXIT_Y0 = 153.0
EXIT_Y1 = 157.0
EXIT_PILOT_R = 1.3                     # Ø2.6
EXIT_PCD_R = 21.0                      # Ø42 PCD
EXIT_PILOT_ANGLES = (45.0, 135.0, 225.0, 315.0)


def _cyl_y(radius: float, y0: float, y1: float, x: float = 0.0,
           z: float = AXIS_Z) -> bd.Part:
    """Cylinder with axis along Y spanning y0..y1 at (x, z)."""
    c = bd.Cylinder(radius, y1 - y0,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    c = c.rotate(bd.Axis.X, -90)  # Z -> Y
    return c.move(bd.Location((x, (y0 + y1) / 2.0, z)))


def _duct_loft(inner: bool) -> bd.Part:
    """Loft between the mouth rectangle (Z=8) and the tunnel-bottom
    opening rectangle (extended up to the tunnel axis Z=40 so the cavity
    always merges with the bore and the outer wall fuses with the tunnel).
    """
    off = 0.0 if inner else WALL
    bottom = bd.Rectangle(2 * (MOUTH_HALF_X + off),
                          (MOUTH_Y1 - MOUTH_Y0) + 2 * off)
    bottom = bottom.move(
        bd.Location((0, (MOUTH_Y0 + MOUTH_Y1) / 2.0, MOUTH_Z)))
    top = bd.Rectangle(2 * (MOUTH_HALF_X + off),
                       (TOP_OPEN_Y1 - TOP_OPEN_Y0) + 2 * off)
    top = top.move(
        bd.Location((0, (TOP_OPEN_Y0 + TOP_OPEN_Y1) / 2.0, AXIS_Z)))
    return bd.loft(sections=[bottom, top])


def gen_step() -> bd.Part:
    # ═══ Step 1: outer solids ═══
    tunnel_outer = _cyl_y(TUNNEL_OR, TUNNEL_Y0, TUNNEL_Y1)
    front_boss = _cyl_y(FRONT_BOSS_R, FRONT_Y0, FRONT_Y1)
    exit_flange = _cyl_y(EXIT_R, EXIT_Y0, EXIT_Y1)
    duct_outer = _duct_loft(inner=False)

    flange_len = (MOUTH_Y1 - MOUTH_Y0) + 2 * FLANGE_W       # 62
    flange_wid = 2 * (MOUTH_HALF_X + FLANGE_W)              # 36
    intake_flange = bd.Box(
        flange_wid, flange_len, FLANGE_T,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    intake_flange = intake_flange.move(
        bd.Location((0, (MOUTH_Y0 + MOUTH_Y1) / 2.0, MOUTH_Z)))

    housing = tunnel_outer.fuse(front_boss, exit_flange, duct_outer,
                                intake_flange)

    # ═══ Step 2: tunnel bore (aft of front wall, through exit flange) ═══
    bore = _cyl_y(TUNNEL_IR, FRONT_Y1, EXIT_Y1 + 1.0)
    housing = housing.cut(bore)

    # ═══ Step 3: intake duct cavity + mouth through-cut ═══
    cavity = _duct_loft(inner=True)
    mouth_cut = bd.Box(
        2 * MOUTH_HALF_X, MOUTH_Y1 - MOUTH_Y0, FLANGE_T + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    mouth_cut = mouth_cut.move(
        bd.Location((0, (MOUTH_Y0 + MOUTH_Y1) / 2.0, MOUTH_Z - 1.0)))
    housing = housing.cut(cavity, mouth_cut)

    # ═══ Step 4: shaft hole + motor-mount slots in front wall ═══
    shaft_hole = _cyl_y(SHAFT_HOLE_R, FRONT_Y0 - 1.0, FRONT_Y1 + 1.0)
    housing = housing.cut(shaft_hole)

    slot_proto = bd.Box(
        SLOT_R1 - SLOT_R0,                      # radial (X)
        (FRONT_Y1 - FRONT_Y0) + 2.0,            # through wall (Y)
        SLOT_W,                                 # tangential (Z)
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    slot_proto = slot_proto.move(bd.Location(
        ((SLOT_R0 + SLOT_R1) / 2.0, (FRONT_Y0 + FRONT_Y1) / 2.0, AXIS_Z)))
    tunnel_axis = bd.Axis((0, (FRONT_Y0 + FRONT_Y1) / 2.0, AXIS_Z), (0, 1, 0))
    for k in range(4):
        housing = housing.cut(slot_proto.rotate(tunnel_axis, 90.0 * k))

    # ═══ Step 5: intake flange clearance holes ═══
    for xs in (FLANGE_HOLE_X, -FLANGE_HOLE_X):
        for yh in FLANGE_HOLE_YS:
            h = bd.Cylinder(
                FLANGE_HOLE_R, FLANGE_T + 4.0,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
            housing = housing.cut(
                h.move(bd.Location((xs, yh, MOUTH_Z + FLANGE_T / 2.0))))

    # ═══ Step 6: exit-flange pilot holes (Ø42 PCD, 45° positions) ═══
    for ang in EXIT_PILOT_ANGLES:
        px = EXIT_PCD_R * math.cos(math.radians(ang))
        pz = AXIS_Z + EXIT_PCD_R * math.sin(math.radians(ang))
        housing = housing.cut(
            _cyl_y(EXIT_PILOT_R, EXIT_Y0 - 1.0, EXIT_Y1 + 1.0, x=px, z=pz))

    # ═══ Step 7: integral grate bars across the mouth ═══
    gap = (2 * MOUTH_HALF_X - N_BARS * GRATE_BAR_W) / (N_BARS + 1)  # 4.125
    bar_len = (MOUTH_Y1 - MOUTH_Y0) + 4.0   # overlap 2 into each end wall
    for i in range(N_BARS):
        xc = -MOUTH_HALF_X + gap * (i + 1) + GRATE_BAR_W * (i + 0.5)
        bar = bd.Box(GRATE_BAR_W, bar_len, GRATE_BAR_D,
                     align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        bar = bar.move(
            bd.Location((xc, (MOUTH_Y0 + MOUTH_Y1) / 2.0, MOUTH_Z)))
        housing = housing.fuse(bar)

    return housing


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
    print(f"solids: {len(p.solids())}, volume: {p.volume / 1000.0:.1f} cm^3")
