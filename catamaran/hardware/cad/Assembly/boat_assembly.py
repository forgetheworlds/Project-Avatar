"""Project Catamaran release assembly.

Global frame: X beam/starboard, Y bow-to-stern, Z up.  The first fifteen
children intentionally preserve the validation-harness order; later children
are service parts and purchased-component envelopes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import build123d as bd
from cadpy.assembly import AssemblyHelper

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [
    str(ROOT / "hull"),
    str(ROOT / "jetdrive"),
    str(ROOT / "deck"),
    str(ROOT / "electronics"),
    str(ROOT / "cannon"),
    str(ROOT / "components"),
    str(ROOT / "stability"),
    str(ROOT / "closures"),
]

import battery_tray  # noqa: E402
import deck_mid  # noqa: E402
import deck_stern  # noqa: E402
import electronics_house  # noqa: E402
import electronics_house_lid  # noqa: E402
import electronics_tray  # noqa: E402
import envelopes  # noqa: E402
import drain_plug  # noqa: E402
import foam_port_plug  # noqa: E402
import hose_clip  # noqa: E402
import hull_bow  # noqa: E402
import hull_mid  # noqa: E402
import hull_stern  # noqa: E402
import impeller  # noqa: E402
import motor_adapter  # noqa: E402
import nozzle  # noqa: E402
import nozzle_insert_2p5  # noqa: E402
import nozzle_plate  # noqa: E402
import nozzle_thrust_washer  # noqa: E402
import pump_housing  # noqa: E402
import pump_retainer  # noqa: E402
import pump_well_cover  # noqa: E402
import pushrod_gland  # noqa: E402
import servo_bracket  # noqa: E402
import shaft_cartridge  # noqa: E402
import transom_fin_port  # noqa: E402
import transom_fin_starboard  # noqa: E402
import turret_base  # noqa: E402
import turret_platform  # noqa: E402
import turret_thrust_washer  # noqa: E402
import water_cannon  # noqa: E402
import jet_assembly  # noqa: E402
from interfaces import AXIS_Z, IMPELLER_Y0, LINKAGE_X, LINKAGE_Z, MOTOR_FACE_Y, SHAFT_NOMINAL_LENGTH  # noqa: E402

SEG_L = 160.0
MID_Y0 = 160.0
STERN_Y0 = 320.0
DECK_Z = 72.0
TUNNEL_Z = AXIS_Z

CANNON_GLOBAL_Y = MID_Y0 + deck_mid.CANNON_Y
HOUSE_Y = MID_Y0 + deck_mid.HOUSE_CENTER_Y
HOUSE_Z = DECK_Z + deck_mid.PLATE_T
BATTERY_Y = 180.0
BATTERY_Z = hull_mid.IN_KEEL_Z + 0.05


def _move(shape: bd.Shape, xyz: tuple[float, float, float]) -> bd.Shape:
    return shape.moved(bd.Location(xyz))


def _place_impeller() -> bd.Part:
    return _move(
        impeller.gen_step().rotate(bd.Axis.X, -90.0),
        (0.0, STERN_Y0 + IMPELLER_Y0, AXIS_Z),
    )


def _place_servo_bracket() -> bd.Part:
    return _move(
        servo_bracket.gen_step().rotate(bd.Axis.X, 180.0),
        (24.0, STERN_Y0 + 140.0, LINKAGE_Z),
    )


def _place_cannon_on_turret() -> bd.Part:
    # Source barrel is +Y; rotate to fire forward (-Y). The cannon flange
    # mounts to the rotating platform rather than the former direct recess.
    return _move(
        water_cannon.gen_step().rotate(bd.Axis.Z, 180.0),
        (
            0.0,
            CANNON_GLOBAL_Y,
            DECK_Z
            + deck_mid.PLATE_T
            + turret_base.TOP_Z
            + turret_thrust_washer.T
            + turret_platform.DISC_T,
        ),
    )


def gen_step():
    asm = AssemblyHelper("project_catamaran_release")

    # Validation-critical printable assembly, fixed order.
    asm.add(hull_bow.gen_step(), "hull_bow")
    asm.add(_move(hull_mid.gen_step(), (0.0, MID_Y0, 0.0)), "hull_mid")
    asm.add(_move(hull_stern.gen_step(), (0.0, STERN_Y0, 0.0)), "hull_stern")
    asm.add(_move(pump_housing.gen_step(), (0.0, STERN_Y0, 0.0)), "pump_housing")
    asm.add(_place_impeller(), "impeller")
    asm.add(_move(nozzle_plate.gen_step(), (0.0, STERN_Y0, 0.0)), "nozzle_plate")
    asm.add(_move(nozzle.gen_step(), (0.0, STERN_Y0, 0.0)), "nozzle")
    asm.add(_place_servo_bracket(), "servo_bracket")
    asm.add(_move(deck_mid.gen_step(), (0.0, MID_Y0, DECK_Z)), "deck_mid")
    asm.add(_move(electronics_house.gen_step(), (0.0, HOUSE_Y, HOUSE_Z)), "electronics_house")
    asm.add(
        _move(
            electronics_house_lid.gen_step(),
            (0.0, HOUSE_Y, HOUSE_Z + electronics_house.BODY_H),
        ),
        "electronics_house_lid",
    )
    asm.add(_move(deck_stern.gen_step(), (0.0, STERN_Y0, DECK_Z)), "deck_stern")
    asm.add(_move(battery_tray.gen_step(), (0.0, BATTERY_Y, BATTERY_Z)), "battery_tray")
    asm.add(
        _move(
            electronics_tray.gen_step(),
            (0.0, HOUSE_Y, HOUSE_Z + electronics_house.BASE_T),
        ),
        "electronics_tray",
    )
    asm.add(_place_cannon_on_turret(), "water_cannon")

    # Service parts and hardware envelopes.
    asm.add(
        _move(
            pump_well_cover.gen_step(),
            (hull_stern.WELL_X, STERN_Y0 + hull_stern.WELL_Y, DECK_Z + deck_stern.PLATE_T),
        ),
        "pump_well_cover",
    )
    asm.add(
        _move(
            pump_retainer.gen_step(),
            (hull_stern.WELL_X, STERN_Y0 + hull_stern.WELL_Y, 15.0),
        ),
        "cannon_pump_retainer",
    )
    asm.add(
        _move(
            envelopes.mini_submersible_pump_envelope(),
            (hull_stern.WELL_X, STERN_Y0 + hull_stern.WELL_Y, 18.0),
        ),
        "mini_pump_envelope",
    )
    asm.add(
        # Reuse the starboard forward stern-lid screw: the clip's mounting
        # hole is local X=+7, so origin X=38 aligns it to the X=45 boss.
        _move(hose_clip.gen_step(), (38.0, STERN_Y0 + 25.0, DECK_Z + deck_stern.PLATE_T)),
        "cannon_hose_clip",
    )

    # 2.5 mm cannon insert shown exploded 18 mm ahead of the muzzle; all three
    # printable insert sizes are exported separately.
    insert = nozzle_insert_2p5.gen_step().rotate(bd.Axis.X, 100.0)
    asm.add(_move(insert, (0.0, MID_Y0 + 118.0, 99.0)), "cannon_insert_2p5_exploded")
    asm.add(
        _move(
            turret_base.gen_step(),
            (0.0, CANNON_GLOBAL_Y, DECK_Z + deck_mid.PLATE_T),
        ),
        "cannon_turret_base",
    )
    asm.add(
        _move(
            turret_platform.gen_step(),
            (
                0.0,
                CANNON_GLOBAL_Y,
                DECK_Z
                + deck_mid.PLATE_T
                + turret_base.TOP_Z
                + turret_thrust_washer.T,
            ),
        ),
        "cannon_turret_platform",
    )
    asm.add(
        _move(
            turret_thrust_washer.gen_step(),
            (
                0.0,
                CANNON_GLOBAL_Y,
                DECK_Z + deck_mid.PLATE_T + turret_base.TOP_Z,
            ),
        ),
        "cannon_turret_thrust_washer",
    )
    asm.add(_move(transom_fin_port.gen_step(), (-44.0, 480.0, 30.0)), "tracking_fin_port")
    asm.add(_move(transom_fin_starboard.gen_step(), (44.0, 480.0, 30.0)), "tracking_fin_starboard")
    asm.add(
        _move(drain_plug.gen_step(), (hull_stern.DRAIN_X, 480.0, hull_stern.DRAIN_Z)),
        "transom_drain_plug",
    )
    asm.add(
        _move(foam_port_plug.gen_step(), (0.0, hull_bow.FOAM_HOLE_Y, hull_bow.DEPTH)),
        "bow_foam_port_plug",
    )
    asm.add(
        _move(
            pushrod_gland.gen_step(),
            (LINKAGE_X, STERN_Y0 + hull_stern.SEG_L, LINKAGE_Z),
        ),
        "pushrod_bellows_gland",
    )

    # Complete propulsion stack and steering hardware envelopes.
    asm.add(_move(shaft_cartridge.gen_step(), (0.0, STERN_Y0, 0.0)), "shaft_seal_cartridge")
    asm.add(_move(motor_adapter.gen_step(), (0.0, STERN_Y0, 0.0)), "motor_adapter")
    asm.add(
        _move(envelopes.motor_2838_envelope(), (0.0, STERN_Y0 + MOTOR_FACE_Y, AXIS_Z)),
        "motor_2838_envelope",
    )
    asm.add(
        _move(envelopes.rigid_coupler_envelope(), (0.0, STERN_Y0 + MOTOR_FACE_Y, AXIS_Z)),
        "motor_coupler_envelope",
    )
    asm.add(
        _move(
            envelopes.shaft_4mm_envelope(SHAFT_NOMINAL_LENGTH),
            (0.0, STERN_Y0 + MOTOR_FACE_Y, AXIS_Z),
        ),
        "shaft_4mm_envelope",
    )
    asm.add(_move(jet_assembly._place_sg90(), (0.0, STERN_Y0, 0.0)), "steering_sg90")

    servo_horn = bd.Box(
        LINKAGE_X - 24.0,
        4.0,
        2.5,
        align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.CENTER),
    ).move(bd.Location((24.0, STERN_Y0 + 140.0, LINKAGE_Z)))
    asm.add(servo_horn, "steering_servo_horn")
    asm.add(
        _move(
            jet_assembly._cylinder_between(
                (LINKAGE_X, 140.0, LINKAGE_Z),
                jet_assembly._horn_point(0.0),
                1.0,
            ),
            (0.0, STERN_Y0, 0.0),
        ),
        "steering_pushrod_center",
    )
    asm.add(
        _move(nozzle_thrust_washer.gen_step(), (0.0, STERN_Y0 + 203.0, 10.0)),
        "nozzle_thrust_washer_lower",
    )
    asm.add(
        _move(nozzle_thrust_washer.gen_step(), (0.0, STERN_Y0 + 203.0, 33.2)),
        "nozzle_thrust_washer_upper",
    )

    return asm.build()


if __name__ == "__main__":
    result = gen_step()
    box = result.bounding_box()
    print(
        f"bbox={box.size.X:.1f} x {box.size.Y:.1f} x {box.size.Z:.1f} mm; "
        f"children={len(list(result))}"
    )
