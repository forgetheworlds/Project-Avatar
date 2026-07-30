"""Labeled propulsion assembly with printable parts and hardware envelopes.

All resolved placements are in the stern-local boat frame.  The assembly is
static at the requested vector-nozzle angle; source datums below document the
functional interfaces used for placement and later STEP validation.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import build123d as bd
from cadpy.assembly import AssemblyHelper

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "components"
sys.path.insert(0, str(COMPONENTS))

import envelopes  # noqa: E402
import impeller  # noqa: E402
import motor_adapter  # noqa: E402
import nozzle  # noqa: E402
import nozzle_plate  # noqa: E402
import pump_housing  # noqa: E402
import pushrod_gland  # noqa: E402
import servo_bracket  # noqa: E402
import shaft_cartridge  # noqa: E402
from interfaces import (  # noqa: E402
    AFT_BEARING_OD,
    AFT_BEARING_WIDTH,
    AXIS_Z,
    FRONT_BEARING_OD,
    FRONT_BEARING_WIDTH,
    IMPELLER_Y0,
    LINKAGE_X,
    LINKAGE_Z,
    MOTOR_FACE_Y,
    ROTARY_SEAL_WIDTH,
    SHAFT_NOMINAL_LENGTH,
    VECTOR_PIVOT_Y,
    VECTOR_RANGE_DEG,
    cyl_y,
)

SG90_STEP = COMPONENTS / "sg90_micro_servo.step"

DATUMS = {
    "shaft_axis": bd.Axis((0.0, MOTOR_FACE_Y, AXIS_Z), (0.0, 1.0, 0.0)),
    "motor_face": bd.Location((0.0, MOTOR_FACE_Y, AXIS_Z)),
    "pump_bulkhead": bd.Location((0.0, 70.0, AXIS_Z)),
    "impeller_front": bd.Location((0.0, IMPELLER_Y0, AXIS_Z)),
    "transom_face": bd.Location((0.0, 160.0, AXIS_Z)),
    "vector_pivot": bd.Location((0.0, VECTOR_PIVOT_Y, AXIS_Z)),
    "linkage_pass": bd.Location((LINKAGE_X, 160.0, LINKAGE_Z)),
}


def _place_impeller() -> bd.Part:
    return impeller.gen_step().rotate(bd.Axis.X, -90.0).moved(
        bd.Location((0.0, IMPELLER_Y0, AXIS_Z))
    )


def _place_servo_bracket() -> bd.Part:
    # Hang the bracket under a horizontal plane so the spline is vertical.
    return servo_bracket.gen_step().rotate(bd.Axis.X, 180.0).moved(
        bd.Location((24.0, 140.0, LINKAGE_Z))
    )


def _place_sg90() -> bd.Shape:
    # The step.parts servo has spline axis +Z and origin on the spline axis.
    # Invert it so the body hangs inside while the spline remains vertical.
    servo = bd.import_step(str(SG90_STEP))
    servo = servo.rotate(bd.Axis.X, 180.0)
    servo = servo.moved(bd.Location((24.0, 140.0, LINKAGE_Z)))
    servo.label = "sg90_servo"
    return servo


def _move_hardware(part: bd.Shape, y: float) -> bd.Shape:
    return part.moved(bd.Location((0.0, y, AXIS_Z)))


def _cylinder_between(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
) -> bd.Part:
    p0 = bd.Vector(*start)
    p1 = bd.Vector(*end)
    vector = p1 - p0
    length = vector.length
    plane = bd.Plane(origin=p0, z_dir=vector)
    rod = bd.Cylinder(
        radius,
        length,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return rod.moved(plane.location)


def _horn_point(angle_deg: float) -> tuple[float, float, float]:
    x0 = nozzle.HORN_HOLE_X
    dy = nozzle.HORN_HOLE_Y - VECTOR_PIVOT_Y
    angle = math.radians(angle_deg)
    return (
        x0 * math.cos(angle) - dy * math.sin(angle),
        VECTOR_PIVOT_Y + x0 * math.sin(angle) + dy * math.cos(angle),
        LINKAGE_Z,
    )


def gen_steered(nozzle_angle_deg: float):
    assert -VECTOR_RANGE_DEG <= nozzle_angle_deg <= VECTOR_RANGE_DEG
    assembly = AssemblyHelper("jet_drive")

    # Printable service parts.
    assembly.add(pump_housing.gen_step(), "pump_housing")
    assembly.add(shaft_cartridge.gen_step(), "shaft_seal_cartridge")
    assembly.add(motor_adapter.gen_step(), "motor_adapter")
    assembly.add(_place_impeller(), "impeller")
    assembly.add(nozzle_plate.gen_step(), "stator_contraction_plate")
    assembly.add(nozzle.gen_at_angle(nozzle_angle_deg), "vector_nozzle")
    assembly.add(_place_servo_bracket(), "servo_bracket")

    # Purchased / cut-to-fit hardware envelopes.
    motor = envelopes.motor_2838_envelope().moved(
        bd.Location((0.0, MOTOR_FACE_Y, AXIS_Z))
    )
    assembly.add(motor, "motor_2838_envelope")

    coupler = envelopes.rigid_coupler_envelope().moved(
        bd.Location((0.0, MOTOR_FACE_Y, AXIS_Z))
    )
    assembly.add(coupler, "coupler_3p175_to_4_envelope")

    shaft = envelopes.shaft_4mm_envelope(SHAFT_NOMINAL_LENGTH).moved(
        bd.Location((0.0, MOTOR_FACE_Y, AXIS_Z))
    )
    assembly.add(shaft, "shaft_4mm_cut_to_fit")

    seal_1 = _move_hardware(envelopes.seal_4x8x3_envelope(), 71.0)
    seal_2 = _move_hardware(envelopes.seal_4x8x3_envelope(), 75.0)
    assembly.add(seal_1, "rotary_seal:dry_side")
    assembly.add(seal_2, "rotary_seal:wet_side")

    front_bearing = _move_hardware(
        envelopes.bearing_envelope(
            FRONT_BEARING_OD,
            FRONT_BEARING_WIDTH,
            "694_2rs_envelope",
        ),
        80.0,
    )
    aft_bearing = _move_hardware(
        envelopes.bearing_envelope(
            AFT_BEARING_OD,
            AFT_BEARING_WIDTH,
            "mr74_2rs_envelope",
        ),
        164.0,
    )
    assembly.add(front_bearing, "bearing:front_694_2rs")
    assembly.add(aft_bearing, "bearing:aft_mr74_2rs")

    collar = _move_hardware(envelopes.shaft_collar_4mm_envelope(), 84.5)
    assembly.add(collar, "shaft_collar:thrust_reaction")
    assembly.add(_place_sg90(), "sg90_servo")

    # A 14 mm horn brings the vertical-spline output to the sealed X=38
    # pushrod passage, providing a real fore-aft stroke.
    servo_horn = bd.Box(
        LINKAGE_X - 24.0,
        4.0,
        2.5,
        align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.CENTER),
    ).move(bd.Location((24.0, 140.0, LINKAGE_Z)))
    assembly.add(servo_horn, "sg90_14mm_horn_envelope")
    inner_link = _cylinder_between(
        (LINKAGE_X, 140.0, LINKAGE_Z),
        (LINKAGE_X, 164.0, LINKAGE_Z),
        1.0,
    )
    outer_link = _cylinder_between(
        (LINKAGE_X, 164.0, LINKAGE_Z),
        _horn_point(nozzle_angle_deg),
        1.0,
    )
    assembly.add(inner_link, "pushrod:inner")
    assembly.add(outer_link, "pushrod:outer_ball_link")
    assembly.add(
        pushrod_gland.gen_step().moved(
            bd.Location((LINKAGE_X, 160.0, LINKAGE_Z))
        ),
        "pushrod_bellows_gland",
    )

    lower_pin = bd.Cylinder(
        1.5,
        6.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, 5.0)))
    upper_pin = bd.Cylinder(
        1.5,
        6.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).move(bd.Location((0.0, VECTOR_PIVOT_Y, 33.5)))
    assembly.add(lower_pin, "m3_pivot_screw:lower")
    assembly.add(upper_pin, "m3_pivot_screw:upper")
    return assembly.build()


def gen_step():
    return gen_steered(0.0)


if __name__ == "__main__":
    for angle in (-VECTOR_RANGE_DEG, 0.0, VECTOR_RANGE_DEG):
        result = gen_steered(angle)
        bbox = result.bounding_box()
        print(
            f"jet angle={angle:+.0f}: bbox={bbox.size.X:.1f} x "
            f"{bbox.size.Y:.1f} x {bbox.size.Z:.1f} mm"
        )
