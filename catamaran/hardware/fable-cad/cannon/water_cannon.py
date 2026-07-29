"""
cannon/water_cannon.py — water cannon (DESIGN.md v1).

Local frame: flange bottom on XY at Z=0, +Z up; barrel points +Y,
elevated +10°.

Features:
  - Flange Ø46 x 3 with 4x Ø3.4 on Ø32 PCD at 45° positions
    (identical clocking to deck_mid pad Ø32 pilots / turret_platform).
  - Riser pedestal + 2 gussets (2.5 thick) support the barrel, which is
    built on its own axis and rotated to +10° elevation (the riser/gusset
    stack forms the wedge).
  - Barrel 90 long, Ø12 OD; SUBTRACTIVE bore: Ø6 ID converging to Ø2
    outlet over the last 15 (open through-path).
  - Rear hose barb 14 long with Ø7.5/Ø6.0 barbed steps and Ø4 bore
    joining the main bore (6mm ID silicone tube).

Barrel axis frame: built along +Z (rear face at z'=0, muzzle z'=90,
barb z'=-14..0), then rotated about X by -80° (so +Z -> +10° elevated +Y)
and moved to the pivot point (0, -14, 11).
"""

import math
import build123d as bd

# Flange
FLANGE_D = 46.0
FLANGE_T = 3.0
BOLT_D = 3.4
PCD32 = 32.0               # 45° clocking — matches deck pad / platform

# Elevation and barrel placement
ELEV_DEG = 10.0
PIVOT = (0.0, -14.0, 11.0)  # world position of barrel rear-face center

# Barrel
BARREL_L = 90.0
BARREL_OD = 12.0
BORE_D = 6.0
OUTLET_D = 2.0
NOZZLE_L = 15.0            # converging length at muzzle
REAR_PLUG_T = 3.0          # solid wall between barb bore and main bore

# Hose barb (behind barrel rear face, along -axis)
BARB_L = 14.0
BARB_MAJOR_D = 7.5
BARB_MINOR_D = 6.0
BARB_BORE_D = 4.0

# Riser + gussets
RISER_W = 10.0             # X
RISER_Y0, RISER_Y1 = -12.0, 20.0
RISER_TOP = 11.0           # embeds into barrel underside
GUSSET_T = 2.5


def _cyl(d: float, h: float, z0: float) -> bd.Part:
    """Cylinder on the Z axis from z0 to z0+h."""
    return bd.Cylinder(d / 2.0, h).moved(bd.Location((0, 0, z0 + h / 2.0)))


def _cone(d0: float, d1: float, h: float, z0: float) -> bd.Part:
    """Cone on the Z axis, diameter d0 at z0 -> d1 at z0+h."""
    return bd.Cone(d0 / 2.0, d1 / 2.0, h).moved(
        bd.Location((0, 0, z0 + h / 2.0)))


def _to_world(shape: bd.Part) -> bd.Part:
    """Barrel-axis frame -> world: +Z becomes +Y elevated by ELEV_DEG."""
    return shape.rotate(bd.Axis.X, -(90.0 - ELEV_DEG)).moved(
        bd.Location(PIVOT))


def _gusset(x0: float) -> bd.Part:
    """Triangular rib in YZ, thickness GUSSET_T extruded in +X from x0."""
    pts = [(RISER_Y0, FLANGE_T), (16.0, FLANGE_T), (RISER_Y0, 10.0)]
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.YZ.offset(x0)):
            with bd.BuildLine():
                bd.Polyline(*pts, close=True)
            bd.make_face()
        bd.extrude(amount=GUSSET_T, dir=(1, 0, 0))
    return bp.part


def gen_step() -> bd.Part:
    # Flange
    part = bd.Cylinder(FLANGE_D / 2.0, FLANGE_T).moved(
        bd.Location((0, 0, FLANGE_T / 2.0)))

    # Barrel + hose barb (built on Z axis, moved to elevated pose)
    barrel = _cyl(BARREL_OD, BARREL_L, 0.0)
    seg = BARB_L / 2.0 - 1.5                    # 5.5 per barb cone
    barb = _cone(BARB_MINOR_D, BARB_MAJOR_D, seg, -BARB_L)
    barb = barb.fuse(_cone(BARB_MINOR_D, BARB_MAJOR_D, seg, -BARB_L + seg))
    barb = barb.fuse(_cyl(BARB_MAJOR_D, 3.0, -3.0))   # collar at rear face
    part = part.fuse(_to_world(barrel.fuse(barb)))

    # Riser pedestal (fuses into the tilted barrel underside)
    riser = bd.Box(RISER_W, RISER_Y1 - RISER_Y0, RISER_TOP - FLANGE_T).moved(
        bd.Location((0, (RISER_Y0 + RISER_Y1) / 2.0,
                     (FLANGE_T + RISER_TOP) / 2.0)))
    part = part.fuse(riser)

    # 2 gussets flanking the riser
    part = part.fuse(_gusset(RISER_W / 2.0))
    part = part.fuse(_gusset(-RISER_W / 2.0 - GUSSET_T))

    # Flange bolt holes: Ø3.4 on Ø32 PCD, 45° positions
    r = PCD32 / 2.0
    for i in range(4):
        a = math.radians(45.0 + 90.0 * i)
        hole = bd.Cylinder(BOLT_D / 2.0, FLANGE_T + 2.0).moved(
            bd.Location((r * math.cos(a), r * math.sin(a),
                         FLANGE_T / 2.0)))
        part = part.cut(hole)

    # SUBTRACTIVE bore (cut last so riser/gussets can't plug it):
    #   barb Ø4 -> main Ø6 -> converging cone -> Ø2 outlet (open both ends)
    cone_z0 = BARREL_L - NOZZLE_L
    bore = _cyl(BORE_D, cone_z0 - REAR_PLUG_T, REAR_PLUG_T)
    bore = bore.fuse(_cone(BORE_D, OUTLET_D, NOZZLE_L, cone_z0))
    bore = bore.fuse(_cyl(OUTLET_D, 4.0, BARREL_L - 2.0))     # muzzle overshoot
    bore = bore.fuse(_cyl(BARB_BORE_D, REAR_PLUG_T + 3.0 + BARB_L + 2.0,
                          -BARB_L - 2.0))                     # rear overshoot
    part = part.cut(_to_world(bore))

    return part


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm "
          f"(expect ~46 x ~102 x ~33)")
    print(f"solids: {len(p.solids())} (expect 1)")
    assert len(p.solids()) == 1
    assert abs(sz.X - FLANGE_D) < 1e-6          # flange is widest feature
    assert sz.Y > 95.0 and sz.Z > 25.0
