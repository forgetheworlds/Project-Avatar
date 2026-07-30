"""Balanced three-blade impeller for the Ø28 pump tunnel.

Part-local frame: rotation axis +Z, hub base Z=0.  The assembly rotates the
part onto +Y and places it at Y=140..159 in the stern-local frame.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import assert_single_solid

HUB_R = 5.0
AXIAL_LENGTH = 19.0
BORE_R = 2.05
SET_SCREW_R = 1.3
SET_SCREW_AZIMUTH = 60.0

N_BLADES = 3
ROOT_R = 4.6                 # embeds 0.4 mm inside the hub
TIP_R = 13.5                 # Ø27, 0.5 mm radial tunnel clearance
BLADE_T = 1.6
CHORD_ROOT = 11.5
CHORD_TIP = 8.5
ANGLE_ROOT = 36.0
ANGLE_TIP = 23.0
SWEEP_DEG = 12.0

# Dynamic-balance datum: shaft axis + either hub end plane.  The set-screw
# azimuth is an assembly clocking datum, not the balance reference.
BALANCE_AXIS = bd.Axis.Z
BALANCE_PLANE_Z = 0.0


def _blade() -> bd.Part:
    radii = (ROOT_R, 6.8, 9.0, 11.3, TIP_R + 0.7)
    sections = []
    for radius in radii:
        fraction = (radius - ROOT_R) / (TIP_R - ROOT_R)
        chord = CHORD_ROOT + fraction * (CHORD_TIP - CHORD_ROOT)
        pitch = ANGLE_ROOT + fraction * (ANGLE_TIP - ANGLE_ROOT)
        sweep = (radius - ROOT_R) * math.tan(math.radians(SWEEP_DEG))
        section = bd.Rectangle(chord, BLADE_T)
        section = section.rotate(bd.Axis.Z, 90.0 - pitch)
        section = section.move(bd.Location((0.0, sweep, radius - ROOT_R)))
        sections.append(section)

    blade = bd.loft(sections=sections)
    blade = blade.rotate(bd.Axis.Y, 90.0)
    blade = blade.move(bd.Location((ROOT_R, 0.0, AXIAL_LENGTH / 2.0)))
    return blade


def gen_step() -> bd.Part:
    impeller = bd.Cylinder(
        HUB_R,
        AXIAL_LENGTH,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )

    blade = _blade()
    for index in range(N_BLADES):
        impeller = impeller.fuse(
            blade.rotate(bd.Axis.Z, index * 360.0 / N_BLADES)
        )

    # Enforce the exact OD and axial service envelope.
    trim = bd.Cylinder(
        TIP_R,
        AXIAL_LENGTH,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    impeller = impeller & trim

    bore = bd.Cylinder(
        BORE_R,
        AXIAL_LENGTH + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, 0.0, -1.0)))
    impeller = impeller.cut(bore)

    set_screw = bd.Cylinder(
        SET_SCREW_R,
        HUB_R + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    set_screw = set_screw.rotate(bd.Axis.Y, 90.0)
    set_screw = set_screw.move(bd.Location((0.0, 0.0, AXIAL_LENGTH / 2.0)))
    set_screw = set_screw.rotate(
        bd.Axis((0.0, 0.0, AXIAL_LENGTH / 2.0), (0.0, 0.0, 1.0)),
        SET_SCREW_AZIMUTH,
    )
    impeller = impeller.cut(set_screw)
    impeller.label = "impeller"

    assert_single_solid(impeller, "impeller", min_volume=900.0)
    bbox = impeller.bounding_box()
    assert abs(bbox.size.Z - AXIAL_LENGTH) < 0.05
    max_radius = max(
        math.hypot(vertex.X, vertex.Y) for vertex in impeller.vertices()
    )
    assert TIP_R - 0.05 <= max_radius <= TIP_R + 0.02
    center_mass = impeller.center(bd.CenterOf.MASS)
    assert math.hypot(center_mass.X, center_mass.Y) < 0.25, (
        "impeller radial COM exceeds printable balance allowance"
    )
    return impeller


if __name__ == "__main__":
    part = gen_step()
    bbox = part.bounding_box()
    print(
        f"impeller bbox={bbox.size.X:.2f} x {bbox.size.Y:.2f} x "
        f"{bbox.size.Z:.2f} mm; volume={part.volume / 1000.0:.2f} cm^3"
    )
