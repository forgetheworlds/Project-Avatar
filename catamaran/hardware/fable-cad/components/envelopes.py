"""Conservative purchased-component envelopes for assembly validation.

These are not printable substitutes and are not vendor-certified drawings.
The SG90 assembly should import the exact step.parts model where practical;
the remaining envelopes document the frozen prototype assumptions from
ENGINEERING_BRIEF.md until exact vendor STEP files are selected.

Hull frame convention used by the assembly:
X = beam, Y = bow-to-stern / shaft axis, Z = up.
"""

from __future__ import annotations

import build123d as bd


def _cyl_y(radius: float, length: float, y0: float = 0.0) -> bd.Part:
    part = bd.Cylinder(
        radius,
        length,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return part.rotate(bd.Axis.X, -90).moved(bd.Location((0, y0, 0)))


def motor_2838_envelope() -> bd.Part:
    """Surpass KK 2838: mounting face at Y=0, body forward (-Y)."""
    body = _cyl_y(14.0, 40.0, -40.0)
    shaft = _cyl_y(3.175 / 2.0, 15.0, 0.0)
    part = body.fuse(shaft)
    part.label = "motor_2838_envelope"
    return part


def rigid_coupler_envelope() -> bd.Part:
    """Conservative 3.175-to-4 mm rigid coupler, axis +Y."""
    part = _cyl_y(6.0, 20.0, 0.0)
    part.label = "coupler_3p175_to_4_envelope"
    return part


def shaft_4mm_envelope(length: float = 120.0) -> bd.Part:
    part = _cyl_y(2.0, length, 0.0)
    part.label = "shaft_4mm_envelope"
    return part


def bearing_envelope(
    outer_diameter: float,
    width: float,
    label: str,
) -> bd.Part:
    part = _cyl_y(outer_diameter / 2.0, width, 0.0)
    part.label = label
    return part


def seal_4x8x3_envelope() -> bd.Part:
    outer = _cyl_y(4.0, 3.0, 0.0)
    bore = _cyl_y(2.0, 5.0, -1.0)
    part = outer.cut(bore)
    part.label = "rotary_seal_4x8x3_envelope"
    return part


def shaft_collar_4mm_envelope() -> bd.Part:
    outer = _cyl_y(4.0, 5.0, 0.0)
    bore = _cyl_y(2.05, 7.0, -1.0)
    part = outer.cut(bore)
    part.label = "shaft_collar_4mm_envelope"
    return part


def battery_3s_2200_envelope() -> bd.Part:
    """Battery centered in X/Y, base at Z=0; includes small wire allowance."""
    pack = bd.Box(
        35.0,
        106.0,
        26.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    lead = bd.Cylinder(
        3.0,
        20.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90).moved(bd.Location((0, 53.0, 18.0)))
    part = pack.fuse(lead)
    part.label = "battery_3s_2200_envelope"
    return part


def mini_submersible_pump_envelope() -> bd.Part:
    """Common 5 V mini pump: 24 x 24 x 45 body plus 7 mm outlet."""
    body = bd.Box(
        24.0,
        24.0,
        45.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    outlet = bd.Cylinder(
        3.5,
        12.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).moved(bd.Location((0, 0, 45.0)))
    part = body.fuse(outlet)
    part.label = "mini_submersible_pump_envelope"
    return part


def esp32_s3_devkit_envelope() -> bd.Part:
    part = bd.Box(
        65.0,
        30.0,
        14.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part.label = "esp32_s3_devkit_envelope"
    return part


def esc_60a_marine_envelope() -> bd.Part:
    """Conservative envelope pending final marine ESC SKU."""
    part = bd.Box(
        65.0,
        35.0,
        20.0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part.label = "esc_60a_marine_envelope"
    return part


def small_sensor_envelope(label: str, x: float, y: float, z: float) -> bd.Part:
    part = bd.Box(
        x,
        y,
        z,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part.label = label
    return part

