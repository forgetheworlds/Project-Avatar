"""Surpass 2838 motor adapter and dry coupler standoff cage.

Stern-local coordinates.  The motor mounting face is Y=48.  Four connected
standoffs terminate at Y=67 against the shaft-cartridge flange, leaving a
19 mm-long, Ø16 unobstructed coupler service envelope.
"""

from __future__ import annotations

import math

import build123d as bd

from interfaces import (
    AXIS_Z,
    CARTRIDGE_ANGLES,
    EXIT_ANGLES,
    MOTOR_FACE_Y,
    MOTOR_PCD_RANGE,
    assert_single_solid,
    cyl_y,
    radial_point,
)

FRONT_PLATE_Y0 = MOTOR_FACE_Y
FRONT_PLATE_Y1 = 52.0
FRONT_PLATE_R = 20.0
CENTER_CLEAR_R = 8.0

STANDOFF_Y0 = FRONT_PLATE_Y1
STANDOFF_Y1 = 63.0
STANDOFF_PCD_R = 13.0
STANDOFF_R = 3.8
STANDOFF_BORE_R = 1.7

REAR_RING_Y0 = STANDOFF_Y1
REAR_RING_Y1 = 67.0
REAR_RING_OR = 17.0
REAR_RING_IR = CENTER_CLEAR_R

MOTOR_SLOT_W = 3.4
MOTOR_SLOT_R0 = MOTOR_PCD_RANGE[0] / 2.0
MOTOR_SLOT_R1 = MOTOR_PCD_RANGE[1] / 2.0


def _motor_slot() -> bd.Part:
    """Tangential M3 slot covering both Ø16 and Ø19 motor PCDs."""
    radial_length = MOTOR_SLOT_R1 - MOTOR_SLOT_R0
    slot = bd.Box(
        radial_length,
        FRONT_PLATE_Y1 - FRONT_PLATE_Y0 + 2.0,
        MOTOR_SLOT_W,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
    ).move(
        bd.Location(
            (
                (MOTOR_SLOT_R0 + MOTOR_SLOT_R1) / 2.0,
                (FRONT_PLATE_Y0 + FRONT_PLATE_Y1) / 2.0,
                AXIS_Z,
            )
        )
    )
    return slot


def gen_step() -> bd.Part:
    adapter = cyl_y(FRONT_PLATE_R, FRONT_PLATE_Y0, FRONT_PLATE_Y1)
    adapter = adapter.fuse(
        cyl_y(REAR_RING_OR, REAR_RING_Y0, REAR_RING_Y1).cut(
            cyl_y(REAR_RING_IR, REAR_RING_Y0 - 0.5, REAR_RING_Y1 + 0.5)
        )
    )

    for angle in CARTRIDGE_ANGLES:
        dx, dz = radial_point(STANDOFF_PCD_R, angle)
        adapter = adapter.fuse(
            cyl_y(
                STANDOFF_R,
                STANDOFF_Y0,
                STANDOFF_Y1,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    adapter = adapter.cut(
        cyl_y(CENTER_CLEAR_R, FRONT_PLATE_Y0 - 1.0, FRONT_PLATE_Y1 + 1.0)
    )

    motor_slot = _motor_slot()
    pump_axis = bd.Axis((0.0, (FRONT_PLATE_Y0 + FRONT_PLATE_Y1) / 2.0, AXIS_Z), (0, 1, 0))
    for index in range(4):
        adapter = adapter.cut(motor_slot.rotate(pump_axis, 90.0 * index))

    for angle in CARTRIDGE_ANGLES:
        dx, dz = radial_point(STANDOFF_PCD_R, angle)
        adapter = adapter.cut(
            cyl_y(
                STANDOFF_BORE_R,
                STANDOFF_Y0 - 1.0,
                REAR_RING_Y1 + 1.0,
                x=dx,
                z=AXIS_Z + dz,
            )
        )

    adapter.label = "motor_adapter"
    assert_single_solid(adapter, "motor_adapter", min_volume=4_000.0)
    assert math.isclose(REAR_RING_Y1 - MOTOR_FACE_Y, 19.0)
    assert CENTER_CLEAR_R * 2.0 >= 16.0
    assert MOTOR_SLOT_R0 <= 8.0 and MOTOR_SLOT_R1 >= 9.5
    return adapter


if __name__ == "__main__":
    part = gen_step()
    bbox = part.bounding_box()
    print(
        f"adapter bbox={bbox.size.X:.2f} x {bbox.size.Y:.2f} x "
        f"{bbox.size.Z:.2f} mm; volume={part.volume / 1000.0:.2f} cm^3"
    )
