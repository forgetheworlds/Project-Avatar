"""hull/hull_stern.py — stern segment of the deep-V monohull (DESIGN.md v1).

Local frame: X = beam (+X starboard), Y = length (0 = forward joint face,
160 = transom aft face), Z = height (keel Z=0).

Features (per DESIGN.md "hull/hull_stern.py"):
- Forward joint bulkhead (BULK_T): Ø3.4 clearance holes at (±38,58),(±24,30);
  Ø3.4×4.5 pin sockets at (±30,45); Ø22 wire hole at (0,48).
- Transom plate Y=157..160: Ø30 jet bore at (0, Z=22); 4× Ø3.4 on Ø36 PCD
  (45° positions); pushrod/drain moved outside the jet-plate keep-out;
  2× Ø2.6 servo-bracket pilots (with Ø8 bosses) on the inner face.
- Internal intake pad (flat top Z=12) with 28×60 intake aperture and six blind
  vertical pilots with at least 5 mm screw engagement.
- Port flood chamber includes a Ø2.5 high air vent as well as the Ø15 flood hole.
- Starboard pump wet-well (ID38/wall 2.4 tube at (+32, Y=45), Ø24 shell opening).
- Motor cradle pad (flat top Z=24) with 2× Ø2.6 pilots.
- Blind hardpoints for optional removable trim tabs and a centerline turn fin.
- Deck flange lips + 6 lid bosses at (±45, Y=25/75/125) with Ø2.6 pilots.

Documented interface keep-out:
- The jet plate owns X=±30 around axis Z=22, clipped at the hull bottom, and
  Z=0..52. No drain, pushrod, servo, or trim-tab hole enters this region.
- Servo pilots remain at (+4/+32, Z=67), clear of the plate keep-out.
  Ø8×6.5 bosses added on the transom inner face so pilots get 8 mm engagement
  without breaking through the 3 mm plate.
- Lid bosses at |X|=45 get local flange widening pads (flange lip inner edge is
  |X|≈53.3, so a bare boss would float).
"""

import math

import build123d as bd

# --- Global hull constants (DESIGN.md, verbatim) ---
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
WL = 35.2             # 1.15 kg + open wet-well estimate; see hydrostatics.py

# --- Cross-section profiles (DESIGN.md analytic values) ---
INNER_APEX_Z = WALL / math.cos(math.radians(DEADRISE_DEG))   # 2.554
INNER_CHINE = (57.16, 22.88)
INNER_DECK_X = 61.29

OUTER_PTS = [
    (0.0, 0.0),
    (HALF_BEAM, CHINE_H),
    (DECK_HALF, DEPTH),
    (-DECK_HALF, DEPTH),
    (-HALF_BEAM, CHINE_H),
]
INNER_PTS = [
    (0.0, INNER_APEX_Z),
    (INNER_CHINE[0], INNER_CHINE[1]),
    (INNER_DECK_X, DEPTH),
    (-INNER_DECK_X, DEPTH),
    (-INNER_CHINE[0], INNER_CHINE[1]),
]

# --- Feature constants ---
TRANSOM_Y0 = SEG_L - BULK_T          # 157.0, forward face of transom plate
NOZZLE_BORE_R = 15.0                 # Ø30
NOZZLE_BORE_Z = 22.0
PCD_R = 18.0                         # Ø36 PCD; preserves V-bottom ligament
JET_KEEP_OUT_X = 30.0
PUMP_EXIT_POCKET_R = 22.25           # Ø44 pump flange + 0.25 radial clearance
PUMP_EXIT_POCKET_Y0 = 152.9
PUMP_EXIT_POCKET_Y1 = TRANSOM_Y0
JET_KEEP_OUT_Z0, JET_KEEP_OUT_Z1 = 0.0, 52.0
PUSHROD = (38.0, 58.0)               # Ø6, outside jet-plate keep-out
DRAIN_X, DRAIN_Z = -40.0, 48.0       # Ø8, outside jet-plate keep-out
SERVO_PILOT_XS = (4.0, 32.0)
SERVO_PILOT_Z = 58.0

PAD_TOP_Z = 12.0
PAD_HALF_X, PAD_Y0, PAD_Y1 = 22.0, 68.0, 136.0
APER_HALF_X, APER_Y0, APER_Y1 = 14.0, 72.0, 132.0
PAD_PILOT_X, PAD_PILOT_YS = 18.0, (76.0, 102.0, 128.0)
PAD_PILOT_DEPTH = 5.0
PAD_PILOT_EDGE_LIGAMENT = PAD_HALF_X - PAD_PILOT_X - 1.3

CHAMBER_WALL_X = -34.0               # wall centerline
CHAMBER_Y0, CHAMBER_Y1 = 20.0, 120.0
CHAMBER_TOP_Z0, CHAMBER_TOP_Z1 = 61.6, 64.0
FLOOD_HOLE_R, FLOOD_HOLE_Y, FLOOD_HOLE_Z = 7.5, 70.0, 50.0
VENT_R, VENT_Y, VENT_Z = 1.25, 108.0, 59.8

WELL_X, WELL_Y = 32.0, 45.0
WELL_ID_R, WELL_WALL = 19.0, 2.4     # ID 38 / wall 2.4
WELL_TOP_Z = DEPTH - FLANGE_T        # 69.6
WELL_OPEN_R = 12.0                   # Ø24 shell opening

MOTOR_HALF_X, MOTOR_Y0, MOTOR_Y1, MOTOR_TOP_Z = 14.0, 18.0, 56.0, 24.0
MOTOR_PILOT_YS = (24.0, 50.0)

LID_BOSS_X, LID_BOSS_YS = 45.0, (25.0, 75.0, 125.0)

TRIM_TAB_XS = (-50.0, -38.0, 38.0, 50.0)
TRIM_TAB_Z = 30.0
TRIM_TAB_PILOT_DEPTH = 5.0


def _prism(points, y0, y1):
    """Extrude a closed XZ polygon along +Y from y0 to y1."""
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XZ):
            with bd.BuildLine():
                bd.Polyline(*points, close=True)
            bd.make_face()
        bd.extrude(amount=(y1 - y0), dir=(0, 1, 0))
    return bp.part.moved(bd.Location((0, y0, 0)))


def _ycyl(r, x, z, y0, y1):
    """Cylinder with axis along Y from y0 to y1 at (x, z)."""
    return bd.Pos(x, (y0 + y1) / 2, z) * bd.Rot(90, 0, 0) * bd.Cylinder(r, y1 - y0)


def _zcyl(r, x, y, z0, z1):
    """Cylinder with axis along Z from z0 to z1 at (x, y)."""
    return bd.Pos(x, y, (z0 + z1) / 2) * bd.Cylinder(r, z1 - z0)


def _xcyl(r, y, z, x0, x1):
    """Cylinder with axis along X from x0 to x1 at (y, z)."""
    return bd.Pos((x0 + x1) / 2, y, z) * bd.Rot(0, 90, 0) * bd.Cylinder(r, x1 - x0)


def _box(x0, x1, y0, y1, z0, z1):
    return bd.Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * bd.Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def gen_step() -> bd.Part:
    # Trimming envelope: outer profile extruded past both ends, used to clip
    # internal features (pads, chamber walls, well tube) to the hull surface.
    env = _prism(OUTER_PTS, -5.0, 170.0)

    # -- Base shell: outer prism minus inner cavity (leaves fwd bulkhead
    #    Y=0..3 and solid transom Y=157..160).
    outer = _prism(OUTER_PTS, 0.0, SEG_L)
    cavity = _prism(INNER_PTS, BULK_T, TRANSOM_Y0)
    part = outer - cavity

    # -- Forward joint bulkhead (−Y face of aft segment, DESIGN joint spec).
    for sx in (1.0, -1.0):
        part -= _ycyl(1.7, sx * 38.0, 58.0, -2.0, 5.0)   # Ø3.4 clearance
        part -= _ycyl(1.7, sx * 24.0, 30.0, -2.0, 5.0)   # Ø3.4 clearance
        part -= _ycyl(1.7, sx * 30.0, 45.0, -2.0, 4.5)   # Ø3.4×4.5 pin socket
    part -= _ycyl(11.0, 0.0, 48.0, -2.0, 5.0)            # Ø22 wire hole

    # -- Deck flange lips (both sides, full length, Z 69.6..72).
    for sx in (1.0, -1.0):
        x_in = INNER_DECK_X - FLANGE_W                    # 53.29
        x_out = INNER_DECK_X + 0.4                        # bite into side wall
        part += _box(min(sx * x_in, sx * x_out), max(sx * x_in, sx * x_out),
                     0.0, SEG_L, DEPTH - FLANGE_T, DEPTH)

    # -- Lid bosses: local flange widening pad + Ø8 boss hanging 6 below
    #    flange + Ø2.6 vertical pilot (stops above flood-chamber top plate).
    for sx in (1.0, -1.0):
        for yy in LID_BOSS_YS:
            x_a, x_b = sx * 40.0, sx * (INNER_DECK_X + 0.4)
            part += _box(min(x_a, x_b), max(x_a, x_b), yy - 6.0, yy + 6.0,
                         DEPTH - FLANGE_T, DEPTH)
            part += _zcyl(4.0, sx * LID_BOSS_X, yy, DEPTH - FLANGE_T - 6.0, DEPTH)
            part -= _zcyl(1.3, sx * LID_BOSS_X, yy, 64.6, DEPTH + 1.0)

    # -- Intake pad: internal raised floor, planar top Z=12, clipped to the
    #    hull envelope.  The ±22 width gives every Ø2.6 pilot 2.7 mm edge
    #    ligament; blind 5 mm pilots retain the external skin.
    part += (_box(-PAD_HALF_X, PAD_HALF_X, PAD_Y0, PAD_Y1, -1.0, PAD_TOP_Z) & env)
    # Intake aperture through pad + shell bottom.
    part -= _box(-APER_HALF_X, APER_HALF_X, APER_Y0, APER_Y1, -5.0, PAD_TOP_Z + 1.0)
    # Six blind Ø2.6 vertical pilots, drilled down from the pad top.
    for sx in (1.0, -1.0):
        for yy in PAD_PILOT_YS:
            part -= _zcyl(
                1.3,
                sx * PAD_PILOT_X,
                yy,
                PAD_TOP_Z - PAD_PILOT_DEPTH,
                PAD_TOP_Z + 1.0,
            )

    # -- Motor cradle pad: flat top Z=24, clipped to hull bottom.
    part += (_box(-MOTOR_HALF_X, MOTOR_HALF_X, MOTOR_Y0, MOTOR_Y1, -1.0,
                  MOTOR_TOP_Z) & env)
    for yy in MOTOR_PILOT_YS:
        part -= _zcyl(1.3, 0.0, yy, MOTOR_TOP_Z - 8.0, MOTOR_TOP_Z + 1.5)

    # -- Port flood chamber: main wall, end walls, sealed top plate.
    part += (_box(CHAMBER_WALL_X - WALL / 2, CHAMBER_WALL_X + WALL / 2,
                  CHAMBER_Y0, CHAMBER_Y1, 2.0, CHAMBER_TOP_Z1) & env)
    for y_a in (CHAMBER_Y0, CHAMBER_Y1 - WALL):
        part += (_box(-64.5, CHAMBER_WALL_X + WALL / 2, y_a, y_a + WALL,
                      2.0, CHAMBER_TOP_Z1) & env)
    part += (_box(-64.5, CHAMBER_WALL_X + WALL / 2, CHAMBER_Y0, CHAMBER_Y1,
                  CHAMBER_TOP_Z0, CHAMBER_TOP_Z1) & env)
    # Ø15 flood hole through the port hull side.
    part -= _xcyl(FLOOD_HOLE_R, FLOOD_HOLE_Y, FLOOD_HOLE_Z, -70.0, -50.0)
    # High vent prevents the single-hole chamber from air-locking during a
    # capsize.  Its crown remains below the Z=61.6 chamber top plate.
    part -= _xcyl(VENT_R, VENT_Y, VENT_Z, -70.0, -50.0)

    # -- Starboard pump wet-well: ID38 / wall 2.4 tube from Z=69.6 down to the
    #    hull bottom (annulus clipped to hull), Ø24 opening through the shell.
    tube = bd.Pos(WELL_X, WELL_Y, (WELL_TOP_Z - 2.0) / 2) * (
        bd.Cylinder(WELL_ID_R + WELL_WALL, WELL_TOP_Z + 2.0)
        - bd.Cylinder(WELL_ID_R, WELL_TOP_Z + 20.0)
    )
    part += (tube & env)
    part -= _zcyl(WELL_OPEN_R, WELL_X, WELL_Y, -5.0, 30.0)

    # -- Transom features.
    # Drain boss Ø14×3 proud on aft face (clipped to hull silhouette).
    part += (_ycyl(7.0, DRAIN_X, DRAIN_Z, SEG_L - 1.0, SEG_L + 3.0) & env)
    part -= _ycyl(4.0, DRAIN_X, DRAIN_Z, SEG_L - 6.0, SEG_L + 5.0)   # Ø8 drain
    # Service pocket for the pump's Ø44 internal exit flange.  The removable
    # pump replaces this short patch of hull material and seals against the
    # untouched forward face of the transom at Y=157.
    part -= _ycyl(
        PUMP_EXIT_POCKET_R,
        0.0,
        NOZZLE_BORE_Z,
        PUMP_EXIT_POCKET_Y0,
        PUMP_EXIT_POCKET_Y1,
    )
    part -= _ycyl(NOZZLE_BORE_R, 0.0, NOZZLE_BORE_Z, TRANSOM_Y0 - 2.0,
                  SEG_L + 2.0)                                       # Ø30 bore
    for ang in (45.0, 135.0, 225.0, 315.0):                          # Ø36 PCD
        part -= _ycyl(1.7,
                      PCD_R * math.cos(math.radians(ang)),
                      NOZZLE_BORE_Z + PCD_R * math.sin(math.radians(ang)),
                      TRANSOM_Y0 - 2.0, SEG_L + 2.0)
    part -= _ycyl(3.0, PUSHROD[0], PUSHROD[1], TRANSOM_Y0 - 2.0, SEG_L + 2.0)
    # Servo-bracket bosses + blind Ø2.6 pilots on the transom inner face.
    for x in SERVO_PILOT_XS:
        part += _ycyl(4.0, x, SERVO_PILOT_Z, TRANSOM_Y0 - 6.5, TRANSOM_Y0 + 0.5)
        part -= _ycyl(1.3, x, SERVO_PILOT_Z, TRANSOM_Y0 - 7.5, SEG_L - 1.0)

    # -- Optional removable trim-tab hardpoints.  These are blind from the
    #    transom exterior; no tab geometry is installed in the base hull.
    for x in TRIM_TAB_XS:
        part += _ycyl(4.0, x, TRIM_TAB_Z, TRANSOM_Y0 - 6.5, TRANSOM_Y0 + 0.5)
        part -= _ycyl(
            1.3,
            x,
            TRIM_TAB_Z,
            SEG_L - TRIM_TAB_PILOT_DEPTH,
            SEG_L + 1.0,
        )

    if not isinstance(part, bd.Part):
        part = bd.Part(part.wrapped)
    part.label = "hull_stern"
    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    n_solids = len(p.solids())
    print(f"solids: {n_solids}")
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"bbox size: ({bb.size.X:.2f}, {bb.size.Y:.2f}, {bb.size.Z:.2f})")
    print(f"volume: {p.volume / 1000.0:.1f} cm^3")
    assert n_solids == 1, f"expected single solid, got {n_solids}"
    assert abs(bb.size.X - 128.0) < 0.5, "beam bbox mismatch"
    assert abs(bb.size.Y - 163.0) < 0.5, "length bbox mismatch (160 + 3 drain boss)"
    assert abs(bb.size.Z - 72.0) < 0.5, "depth bbox mismatch"
    assert PAD_PILOT_EDGE_LIGAMENT >= 2.5
    assert PAD_PILOT_DEPTH >= 5.0
    assert not (-JET_KEEP_OUT_X <= DRAIN_X <= JET_KEEP_OUT_X
                and JET_KEEP_OUT_Z0 <= DRAIN_Z <= JET_KEEP_OUT_Z1)
    assert not (-JET_KEEP_OUT_X <= PUSHROD[0] <= JET_KEEP_OUT_X
                and JET_KEEP_OUT_Z0 <= PUSHROD[1] <= JET_KEEP_OUT_Z1)
    print("self-check OK")
