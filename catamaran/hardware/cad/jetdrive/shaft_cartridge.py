"""Serviceable dual-seal shaft cartridge.

Stern-local coordinates, shaft axis +Y at (X=0, Z=22).  The cartridge inserts
from the dry side of the pump bulkhead and can be removed without replacing
the pump housing.

Hardware stack, front-to-aft:
  - two 4x8x3 spring-loaded rotary seals, lips facing opposite directions;
  - 1 mm grease cavity between the seals;
  - 694-2RS (4x11x4) radial bearing;
  - 4 mm thrust washer / shaft collar reaction face.

The exact seal elastomer, bearing supplier, static O-ring and retaining method
remain sourced-hardware selections; modeled pockets are conservative nominal
envelopes, not tolerance-certified press fits.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import (
    AXIS_Z,
    CARTRIDGE_ANGLES,
    EXIT_ANGLES,
    FRONT_BEARING_OD,
    FRONT_BEARING_WIDTH,
    ROTARY_SEAL_OD,
    ROTARY_SEAL_WIDTH,
    SHAFT_CLEARANCE_DIAMETER,
    assert_single_solid,
    cyl_y,
    radial_point,
)

BODY_R = 9.0                   # Ø18 body in Ø18.3 pump seat
BODY_Y0 = 70.0
BODY_Y1 = 88.0
FLANGE_R = 15.0
FLANGE_Y0 = 67.0
FLANGE_Y1 = 70.0
MOUNT_PCD_R = 13.0
MOUNT_CLEAR_R = 1.7

SEAL_1_Y0 = 71.0
SEAL_1_Y1 = SEAL_1_Y0 + ROTARY_SEAL_WIDTH
GREASE_Y0 = SEAL_1_Y1
GREASE_Y1 = GREASE_Y0 + 1.0
SEAL_2_Y0 = GREASE_Y1
SEAL_2_Y1 = SEAL_2_Y0 + ROTARY_SEAL_WIDTH

BEARING_Y0 = 80.0
BEARING_Y1 = BEARING_Y0 + FRONT_BEARING_WIDTH
THRUST_FACE_Y = 85.0

SEAL_POCKET_R = ROTARY_SEAL_OD / 2.0 + 0.08
BEARING_POCKET_R = FRONT_BEARING_OD / 2.0 + 0.06
SHAFT_BORE_R = SHAFT_CLEARANCE_DIAMETER / 2.0
GREASE_PORT_R = 1.15
STATIC_O_RING_GROOVE_R = 0.8
STATIC_O_RING_GROOVE_CENTER_Y = 72.0


def gen_step() -> bd.Part:
    flange = cyl_y(FLANGE_R, FLANGE_Y0, FLANGE_Y1)
    flange_clip = bd.Box(
        40.0,
        FLANGE_Y1 - FLANGE_Y0 + 2.0,
        40.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(
        bd.Location(
            (0.0, (FLANGE_Y0 + FLANGE_Y1) / 2.0, 12.0)
        )
    )
    flange = flange & flange_clip
    cartridge = cyl_y(BODY_R, BODY_Y0, BODY_Y1).fuse(flange)

    cartridge = cartridge.cut(
        cyl_y(SHAFT_BORE_R, FLANGE_Y0 - 1.0, BODY_Y1 + 1.0)
    )
    cartridge = cartridge.cut(
        cyl_y(SEAL_POCKET_R, SEAL_1_Y0, SEAL_1_Y1 + 0.05)
    )
    cartridge = cartridge.cut(
        cyl_y(SEAL_POCKET_R, SEAL_2_Y0 - 0.05, SEAL_2_Y1 + 0.05)
    )
    cartridge = cartridge.cut(
        cyl_y(BEARING_POCKET_R, BEARING_Y0, BEARING_Y1 + 0.08)
    )

    # Radial grease port enters the inter-seal cavity from the top.
    grease_port = bd.Cylinder(
        GREASE_PORT_R,
        BODY_R + 2.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(
        bd.Location(
            (
                0.0,
                (GREASE_Y0 + GREASE_Y1) / 2.0,
                AXIS_Z,
            )
        )
    )
    cartridge = cartridge.cut(grease_port)

    # Static O-ring gland around the cartridge OD.  This is a revolved toroidal
    # groove and seals the cartridge-to-pump interface independently of shaft
    # rotation.
    groove = bd.Torus(
        major_radius=BODY_R - STATIC_O_RING_GROOVE_R / 2.0,
        minor_radius=STATIC_O_RING_GROOVE_R,
    )
    groove = groove.rotate(bd.Axis.X, -90.0).move(
        bd.Location((0.0, STATIC_O_RING_GROOVE_CENTER_Y, AXIS_Z))
    )
    cartridge = cartridge.cut(groove)

    for angle in CARTRIDGE_ANGLES:
        dx, dz = radial_point(MOUNT_PCD_R, angle)
        cartridge = cartridge.cut(
            cyl_y(
                MOUNT_CLEAR_R,
                FLANGE_Y0 - 1.0,
                FLANGE_Y1 + 1.0,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    cartridge.label = "shaft_seal_cartridge"
    assert_single_solid(cartridge, "shaft_seal_cartridge", min_volume=3_000.0)
    assert SEAL_1_Y1 <= GREASE_Y0 + 1e-9
    assert GREASE_Y1 <= SEAL_2_Y0 + 1e-9
    assert SEAL_2_Y1 < BEARING_Y0
    assert BEARING_Y1 < THRUST_FACE_Y
    assert math.isclose(BODY_R * 2.0, 18.0)
    return cartridge


if __name__ == "__main__":
    part = gen_step()
    bbox = part.bounding_box()
    print(
        f"cartridge bbox={bbox.size.X:.2f} x {bbox.size.Y:.2f} x "
        f"{bbox.size.Z:.2f} mm; volume={part.volume / 1000.0:.2f} cm^3"
    )
