"""
jetdrive/impeller.py — 3-blade jet-drive impeller (DESIGN.md v1).

Local frame: rotation axis = Z, origin at hub base.

Features:
  - Hub Ø10 x 18 tall; bore Ø4.05 through (4mm shaft slip fit).
  - Radial Ø2.6 set-screw pilot at mid-hub height (between blades).
  - 3 blades at 120°: radial span r=5 -> 13.5 (OD 27 = 0.5 tip clearance
    in the Ø28 tunnel), thickness 1.8, chord ~12 root -> ~9 tip, pitched:
    chord angle 35° from the rotation plane at root -> 22° at tip,
    ~15° backward (scimitar) sweep.
  - Blade built as a loft between rotated rectangular sections stacked
    along the radius, then trimmed to OD 27 with a cylinder intersection.

Print: hub down, supports allowed. Consumable — print 2.
"""

import math
import build123d as bd

# ── Hub ─────────────────────────────────────────────────────────
HUB_R = 5.0                # Ø10
HUB_H = 18.0
BORE_R = 4.05 / 2.0        # Ø4.05 slip fit
SET_SCREW_R = 1.3          # Ø2.6 pilot
SET_SCREW_AZIMUTH = 60.0   # between blades (blade 1 at 0°)

# ── Blades ──────────────────────────────────────────────────────
N_BLADES = 3
ROOT_R = 5.0
TIP_R = 13.5               # OD 27
LOFT_R0 = 4.5              # start inside hub for solid fusion
LOFT_R1 = 14.5             # overshoot; trimmed back to TIP_R
BLADE_T = 1.8
CHORD_ROOT = 12.0
CHORD_TIP = 9.0
ANGLE_ROOT = 35.0          # chord angle from rotation plane at root
ANGLE_TIP = 22.0           # at tip
SWEEP_DEG = 15.0           # backward sweep
BLADE_MID_Z = HUB_H / 2.0  # blade centered on hub


def _blade() -> bd.Part:
    """Twisted blade: loft rectangular sections stacked along local Z,
    each rotated for pitch and offset tangentially for sweep, then rotate
    the loft so the stack axis becomes radial (+X)."""
    radii = (4.5, 7.0, 9.5, 12.0, 14.5)
    sections = []
    for r in radii:
        f = (r - ROOT_R) / (TIP_R - ROOT_R)
        chord = CHORD_ROOT + f * (CHORD_TIP - CHORD_ROOT)
        pitch_from_plane = ANGLE_ROOT + f * (ANGLE_TIP - ANGLE_ROOT)
        # Pre-rotation the chord lies along X (which maps to the axial
        # direction after the 90° Y rotation); rotating the section by
        # (90 - pitch) about the stack axis leaves the chord at
        # `pitch_from_plane` degrees from the rotation plane.
        twist = 90.0 - pitch_from_plane
        sweep = (r - ROOT_R) * math.tan(math.radians(SWEEP_DEG))
        rect = bd.Rectangle(chord, BLADE_T)
        rect = rect.rotate(bd.Axis.Z, twist)
        rect = rect.move(bd.Location((0, sweep, r - LOFT_R0)))
        sections.append(rect)
    blade = bd.loft(sections=sections)
    blade = blade.rotate(bd.Axis.Y, 90)          # stack Z -> radial X
    blade = blade.move(bd.Location((LOFT_R0, 0, BLADE_MID_Z)))
    return blade


def gen_step() -> bd.Part:
    # ═══ Step 1: hub ═══
    hub = bd.Cylinder(HUB_R, HUB_H,
                      align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))

    # ═══ Step 2: blades, circular pattern x3 ═══
    blade = _blade()
    imp = hub
    for i in range(N_BLADES):
        imp = imp.fuse(blade.rotate(bd.Axis.Z, i * 360.0 / N_BLADES))

    # ═══ Step 3: trim blade tips to OD 27 ═══
    trim = bd.Cylinder(TIP_R, HUB_H + 10.0,
                       align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    trim = trim.move(bd.Location((0, 0, HUB_H / 2.0)))
    imp = imp & trim

    # ═══ Step 4: shaft bore Ø4.05 through ═══
    bore = bd.Cylinder(BORE_R, HUB_H + 4.0,
                       align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    bore = bore.move(bd.Location((0, 0, HUB_H / 2.0)))
    imp = imp.cut(bore)

    # ═══ Step 5: radial set-screw pilot at mid-hub, between blades ═══
    pilot = bd.Cylinder(SET_SCREW_R, HUB_R + 3.0,
                        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    pilot = pilot.rotate(bd.Axis.Y, 90)          # along +X, from axis out
    pilot = pilot.move(bd.Location((0, 0, HUB_H / 2.0)))
    pilot = pilot.rotate(bd.Axis((0, 0, HUB_H / 2.0), (0, 0, 1)),
                         SET_SCREW_AZIMUTH)
    imp = imp.cut(pilot)

    return imp


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox min: ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})")
    print(f"bbox max: ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    print(f"size: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm (OD target 27)")
    print(f"solids: {len(p.solids())}, volume: {p.volume / 1000.0:.2f} cm^3")
