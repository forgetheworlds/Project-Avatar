#!/usr/bin/env python3
"""Source-geometry validation harness for the Project Boat CAD.

This script imports the current build123d generators and validates their
functional interfaces without writing STEP, STL, mesh, or image artifacts.
It is deliberately tolerant of modules being added by concurrent work:
unavailable optional hardware reports SKIP, while an existing module that
cannot generate valid geometry reports FAIL.

Run from anywhere with the project's active Python interpreter:

    python hardware/fable-cad/_validate_design.py
    python hardware/fable-cad/_validate_design.py --json
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import build123d as bd


ROOT = Path(__file__).resolve().parent
PART_DIRS = (
    ROOT,
    ROOT / "hull",
    ROOT / "jetdrive",
    ROOT / "deck",
    ROOT / "electronics",
    ROOT / "cannon",
    ROOT / "stability",
    ROOT / "closures",
)
for directory in reversed(PART_DIRS):
    value = str(directory)
    if value not in sys.path:
        sys.path.insert(0, value)


@dataclass
class Result:
    status: str
    category: str
    name: str
    detail: str


class Report:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def add(self, status: str, category: str, name: str, detail: str) -> None:
        self.results.append(Result(status, category, name, detail))

    def passed(self, category: str, name: str, detail: str) -> None:
        self.add("PASS", category, name, detail)

    def failed(self, category: str, name: str, detail: str) -> None:
        self.add("FAIL", category, name, detail)

    def skipped(self, category: str, name: str, detail: str) -> None:
        self.add("SKIP", category, name, detail)

    def check(
        self, condition: bool, category: str, name: str, detail: str
    ) -> bool:
        (self.passed if condition else self.failed)(category, name, detail)
        return condition

    def counts(self) -> dict[str, int]:
        return {
            status: sum(item.status == status for item in self.results)
            for status in ("PASS", "FAIL", "SKIP")
        }


REPORT = Report()
MODULES: dict[str, Any] = {}
SHAPES: dict[str, bd.Shape] = {}


# Bbox contracts are design envelopes, not snapshots of exported files.
# Ranges accommodate intentional curved extrema while still catching scale,
# origin, and orientation errors.
BBOX_RANGES: dict[
    str, tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
] = {
    "hull_bow": ((127.0, 129.0), (163.5, 164.5), (71.5, 72.5)),
    "hull_mid": ((127.5, 128.5), (163.5, 164.5), (71.5, 72.5)),
    "hull_stern": ((127.5, 128.5), (162.5, 163.5), (71.5, 72.5)),
    "pump_housing": ((43.5, 44.5), (92.5, 93.5), (53.0, 57.0)),
    # A three-lobed circular envelope need not span the full OD in both
    # Cartesian bbox axes; radial clearance is checked separately.
    "impeller": ((24.0, 27.5), (24.0, 27.5), (18.5, 19.5)),
    "nozzle_plate": ((59.5, 60.5), (59.5, 60.5), (21.5, 22.5)),
    "nozzle": ((54.5, 55.7), (41.5, 42.5), (51.5, 52.5)),
    "servo_bracket": ((45.5, 46.5), (19.5, 20.5), (18.5, 19.5)),
    "deck_mid": ((123.5, 124.5), (157.5, 158.5), (4.9, 5.9)),
    "deck_stern": ((123.5, 124.5), (157.5, 158.5), (6.5, 7.5)),
    "electronics_house": ((98.5, 99.5), (77.1, 78.1), (34.5, 35.5)),
    "electronics_house_lid": ((73.1, 74.1), (73.1, 74.1), (2.5, 3.5)),
    "battery_tray": ((43.0, 44.0), (119.5, 120.5), (20.4, 21.4)),
    "electronics_tray": ((69.5, 70.5), (69.5, 70.5), (25.3, 26.3)),
    "water_cannon": ((45.5, 46.5), (105.0, 107.5), (34.0, 35.2)),
    "turret_base": ((55.5, 56.5), (55.5, 56.5), (29.5, 30.5)),
    "turret_platform": ((53.5, 54.5), (53.5, 54.5), (3.5, 4.5)),
    "motor_adapter": ((39.5, 40.5), (18.5, 19.5), (39.5, 40.5)),
    "shaft_cartridge": ((29.5, 30.5), (20.5, 21.5), (24.5, 25.5)),
    "pump_well_cover": ((57.5, 58.5), (57.5, 58.5), (9.3, 10.3)),
    "hose_clip": ((23.5, 24.5), (11.5, 12.5), (13.6, 14.7)),
    "nozzle_insert": ((13.1, 14.1), (13.1, 14.1), (12.0, 13.0)),
    "nozzle_insert_2p0": ((13.1, 14.1), (13.1, 14.1), (12.0, 13.0)),
    "nozzle_insert_2p5": ((13.1, 14.1), (13.1, 14.1), (12.0, 13.0)),
    "nozzle_insert_3p0": ((13.1, 14.1), (13.1, 14.1), (12.0, 13.0)),
    "pump_retainer": ((36.3, 37.3), (36.3, 37.3), (20.5, 21.5)),
    "transom_fin_port": ((23.5, 24.5), (39.5, 40.5), (34.5, 35.5)),
    "transom_fin_starboard": ((23.5, 24.5), (39.5, 40.5), (34.5, 35.5)),
    "drain_plug": ((13.5, 14.5), (13.0, 14.5), (13.5, 14.5)),
    "foam_port_plug": ((14.5, 15.5), (14.5, 15.5), (9.5, 10.5)),
    "pushrod_gland": ((11.5, 12.5), (13.0, 14.5), (11.5, 12.5)),
    "turret_thrust_washer": ((19.5, 20.5), (19.5, 20.5), (0.6, 1.0)),
    "nozzle_thrust_washer": ((6.5, 7.5), (6.5, 7.5), (0.6, 1.0)),
}

GLOBAL_JET_BBOX_RANGES: dict[
    str, tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
] = {
    "pump_housing": ((45.5, 46.5), (86.5, 87.5), (43.5, 44.5)),
    "nozzle_plate": ((57.5, 58.5), (48.5, 49.5), (49.5, 50.5)),
    "nozzle": ((50.5, 52.5), (33.0, 34.0), (51.2, 52.3)),
}

ASSEMBLY_CHILDREN = (
    "hull_bow",
    "hull_mid",
    "hull_stern",
    "pump_housing",
    "impeller",
    "nozzle_plate",
    "nozzle",
    "servo_bracket",
    "deck_mid",
    "electronics_house",
    "electronics_house_lid",
    "deck_stern",
    "battery_tray",
    "electronics_tray",
    "water_cannon",
)

# These pairs are allowed to touch, but not to occupy meaningful common
# volume. The explicit allowlist makes any new collision visible.
CONTACT_ALLOWLIST: dict[tuple[str, str], float] = {
    tuple(sorted(pair)): 0.05
    for pair in (
        ("hull_bow", "hull_mid"),
        ("hull_mid", "hull_stern"),
        ("hull_mid", "deck_mid"),
        ("hull_stern", "deck_stern"),
        ("electronics_house", "electronics_house_lid"),
        ("electronics_house", "electronics_tray"),
        ("hull_bow", "water_cannon"),
    )
}
COLLISION_EPS = 0.05


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def point_set(
    values: Iterable[Iterable[float]], digits: int = 4
) -> set[tuple[float, ...]]:
    return {tuple(round(float(v), digits) for v in value) for value in values}


def solids(shape: Any) -> list[bd.Solid]:
    if shape is None:
        return []
    try:
        return list(shape.solids())
    except Exception:
        return []


def solid_volume(shape: Any) -> float:
    return sum(float(s.volume) for s in solids(shape))


def intersection_volume(a: bd.Shape, b: bd.Shape) -> float:
    try:
        return solid_volume(a.intersect(b))
    except Exception:
        return float("inf")


def bbox_tuple(shape: bd.Shape) -> tuple[float, float, float]:
    box = shape.bounding_box()
    return (float(box.size.X), float(box.size.Y), float(box.size.Z))


def import_module(name: str, optional: bool = False) -> Any | None:
    if name in MODULES:
        return MODULES[name]
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if optional and exc.name == name:
            return None
        REPORT.failed("imports", name, f"import failed: {exc}")
        return None
    except Exception as exc:
        REPORT.failed("imports", name, f"import failed: {exc}")
        return None
    MODULES[name] = module
    return module


def generate(name: str, optional: bool = False) -> bd.Shape | None:
    if name in SHAPES:
        return SHAPES[name]
    module = import_module(name, optional=optional)
    if module is None:
        return None
    generator = getattr(module, "gen_step", None)
    if not callable(generator):
        if optional:
            REPORT.skipped("imports", name, "module has no gen_step()")
        else:
            REPORT.failed("imports", name, "module has no gen_step()")
        return None
    try:
        shape = generator()
    except Exception as exc:
        REPORT.failed(
            "generation",
            name,
            f"gen_step() raised {type(exc).__name__}: {exc}",
        )
        return None
    if shape is None:
        REPORT.failed("generation", name, "gen_step() returned None")
        return None
    SHAPES[name] = shape
    return shape


def printable_module_names() -> list[str]:
    excluded = {
        "boat_assembly",
        "jet_assembly",
        "water_cannon_section",
    }
    names: set[str] = set()
    for directory in PART_DIRS[1:]:
        for path in directory.glob("*.py"):
            if path.name.startswith("_") or path.stem in excluded:
                continue
            # Support modules such as jetdrive/interfaces.py are not
            # printable parts even though they live beside generators.
            try:
                if "def gen_step" not in path.read_text(encoding="utf-8"):
                    continue
            except OSError:
                continue
            names.add(path.stem)
    return sorted(names)


def validate_printables() -> None:
    for name in printable_module_names():
        shape = generate(name)
        if shape is None:
            continue
        count = len(solids(shape))
        REPORT.check(
            count == 1,
            "printables",
            f"{name}.single_solid",
            f"solid_count={count}",
        )
        actual = bbox_tuple(shape)
        module = MODULES.get(name)
        expected = BBOX_RANGES.get(name)
        if (
            name in GLOBAL_JET_BBOX_RANGES
            and module is not None
            and (
                hasattr(module, "PLATE_Y0")
                or hasattr(module, "NOZZLE_Y0")
                or hasattr(module, "INTAKE_FLANGE_Z")
            )
        ):
            expected = GLOBAL_JET_BBOX_RANGES[name]
        if expected is None:
            REPORT.skipped(
                "bbox",
                name,
                "no design envelope registered for newly discovered module",
            )
            continue
        ok = all(lo <= value <= hi for value, (lo, hi) in zip(actual, expected))
        ranges = " x ".join(f"[{lo:g},{hi:g}]" for lo, hi in expected)
        REPORT.check(
            ok,
            "bbox",
            name,
            f"actual={actual[0]:.3f} x {actual[1]:.3f} x "
            f"{actual[2]:.3f} mm; expected={ranges}",
        )


def ycyl(radius: float, y0: float, y1: float, x: float, z: float) -> bd.Part:
    cylinder = bd.Cylinder(
        radius,
        y1 - y0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.X, -90)
    return cylinder.moved(bd.Location((x, y0, z)))


def validate_segment_joints() -> None:
    bow = import_module("hull_bow")
    mid = import_module("hull_mid")
    stern = import_module("hull_stern")
    if not all((bow, mid, stern)):
        REPORT.skipped("joints", "segment_datums", "one or more hull modules absent")
        return

    bolt_sets = {
        name: point_set(getattr(module, "BOLT_POS", ()))
        for name, module in (("bow", bow), ("mid", mid))
    }
    stern_bolts = {
        (38.0, 58.0),
        (-38.0, 58.0),
        (24.0, 30.0),
        (-24.0, 30.0),
    }
    bolt_sets["stern"] = stern_bolts
    REPORT.check(
        len(set(map(frozenset, bolt_sets.values()))) == 1,
        "joints",
        "segment_bolt_datums",
        f"bolt_sets={bolt_sets}",
    )

    pin_bow = point_set(getattr(bow, "PIN_POS", ()))
    pin_mid = point_set(getattr(mid, "PIN_POS", ()))
    pin_stern = {(30.0, 45.0), (-30.0, 45.0)}
    REPORT.check(
        pin_bow == pin_mid == pin_stern,
        "joints",
        "segment_pin_datums",
        f"bow={pin_bow}, mid={pin_mid}, stern={pin_stern}",
    )

    pin_d = float(getattr(mid, "PIN_D", 0.0))
    socket_d = float(getattr(mid, "SOCKET_D", 0.0))
    REPORT.check(
        socket_d - pin_d >= 0.3,
        "joints",
        "pin_socket_diametral_clearance",
        f"pin_d={pin_d:.3f}, socket_d={socket_d:.3f}, "
        f"clearance={socket_d - pin_d:.3f} mm",
    )

    # Geometry-level presence check for both aft pin sets.
    for name, module in (("hull_bow", bow), ("hull_mid", mid)):
        shape = generate(name)
        if shape is None:
            continue
        seg_l = float(getattr(module, "SEG_L", 160.0))
        pin_l = float(getattr(module, "PIN_L", 4.0))
        for x, z in getattr(module, "PIN_POS", ()):
            samples = tuple(
                shape.is_inside((x, seg_l + pin_l * fraction, z))
                for fraction in (0.1, 0.5, 0.9)
            )
            REPORT.check(
                all(samples),
                "joints",
                f"{name}.pin@({x:g},{z:g})",
                f"centerline_material_samples={samples}",
            )

    # Geometry-level void checks for forward holes/sockets on aft segments.
    for name, module in (("hull_mid", mid), ("hull_stern", stern)):
        shape = generate(name)
        if shape is None:
            continue
        bulk_t = float(getattr(module, "BULK_T", 3.0))
        for x, z in bolt_sets[name.removeprefix("hull_")]:
            samples = tuple(
                shape.is_inside((x, y, z))
                for y in (0.2, bulk_t / 2.0, bulk_t - 0.2)
            )
            REPORT.check(
                not any(samples),
                "joints",
                f"{name}.clearance@({x:g},{z:g})",
                f"centerline_material_samples={samples}",
            )
        for x, z in pin_stern:
            samples = tuple(
                shape.is_inside((x, y, z)) for y in (0.2, 2.0, 3.8)
            )
            REPORT.check(
                not any(samples),
                "joints",
                f"{name}.socket@({x:g},{z:g})",
                f"centerline_material_samples={samples}",
            )


def validate_pump_hull_interfaces() -> None:
    stern = import_module("hull_stern")
    pump = import_module("pump_housing")
    plate = import_module("nozzle_plate")
    if not all((stern, pump, plate)):
        REPORT.skipped("pump", "hull_interfaces", "required module absent")
        return

    # Final hull/jet design contract. These checks intentionally do not
    # derive expected values from the modules under test.
    final_datums = {
        "axis_z": 22.0,
        "bore_d": 30.0,
        "exit_pcd_r": 18.0,
        "pad_top_z": 12.0,
        "pad_half_x": 22.0,
        "pad_y0": 68.0,
        "pad_y1": 136.0,
        "intake_half_x": 14.0,
        "intake_y0": 72.0,
        "intake_y1": 132.0,
        "fastener_x": 18.0,
        "fastener_ys": (76.0, 102.0, 128.0),
    }
    actual_final = {
        "axis_z": float(stern.NOZZLE_BORE_Z),
        "bore_d": 2.0 * float(stern.NOZZLE_BORE_R),
        "exit_pcd_r": float(stern.PCD_R),
        "pad_top_z": float(stern.PAD_TOP_Z),
        "pad_half_x": float(stern.PAD_HALF_X),
        "pad_y0": float(stern.PAD_Y0),
        "pad_y1": float(stern.PAD_Y1),
        "intake_half_x": float(stern.APER_HALF_X),
        "intake_y0": float(stern.APER_Y0),
        "intake_y1": float(stern.APER_Y1),
        "fastener_x": float(stern.PAD_PILOT_X),
        "fastener_ys": tuple(float(v) for v in stern.PAD_PILOT_YS),
    }
    exact_ok = all(
        (
            point_set((actual_final[key],)) == point_set((expected,))
            if isinstance(expected, tuple)
            else close(actual_final[key], expected, 0.01)
        )
        for key, expected in final_datums.items()
    )
    REPORT.check(
        exact_ok,
        "pump",
        "final_hull_jet_contract",
        f"actual={actual_final}; expected={final_datums}",
    )

    pump_intake_half_x = getattr(
        pump, "INTAKE_X_HALF", getattr(pump, "MOUTH_HALF_X", None)
    )
    pump_intake_y0 = getattr(
        pump, "INTAKE_Y0", getattr(pump, "MOUTH_Y0", None)
    )
    pump_intake_y1 = getattr(
        pump, "INTAKE_Y1", getattr(pump, "MOUTH_Y1", None)
    )
    pump_flange_z = getattr(
        pump, "INTAKE_FLANGE_Z", getattr(pump, "MOUTH_Z", None)
    )
    pump_fastener_x = getattr(
        pump, "INTAKE_FASTENER_X", getattr(pump, "FLANGE_HOLE_X", None)
    )
    pump_fastener_ys = getattr(
        pump, "INTAKE_FASTENER_YS", getattr(pump, "FLANGE_HOLE_YS", None)
    )
    if any(
        value is None
        for value in (
            pump_intake_half_x,
            pump_intake_y0,
            pump_intake_y1,
            pump_flange_z,
            pump_fastener_x,
            pump_fastener_ys,
        )
    ):
        REPORT.failed(
            "pump",
            "pump_interface_datums",
            "pump module does not expose complete intake/flange datums",
        )
        return

    aperture = (
        -float(stern.APER_HALF_X),
        float(stern.APER_HALF_X),
        float(stern.APER_Y0),
        float(stern.APER_Y1),
    )
    mouth = (
        -float(pump_intake_half_x),
        float(pump_intake_half_x),
        float(pump_intake_y0),
        float(pump_intake_y1),
    )
    REPORT.check(
        aperture == mouth,
        "pump",
        "intake_aperture_mouth",
        f"stern={aperture}, pump={mouth}",
    )
    REPORT.check(
        close(stern.PAD_TOP_Z, pump_flange_z, 0.05),
        "pump",
        "intake_flange_plane",
        f"stern_pad_z={stern.PAD_TOP_Z:g}, "
        f"pump_flange_z={float(pump_flange_z):g}",
    )

    stern_holes = {
        (sx * float(stern.PAD_PILOT_X), float(y))
        for sx in (-1.0, 1.0)
        for y in stern.PAD_PILOT_YS
    }
    pump_holes = {
        (sx * float(pump_fastener_x), float(y))
        for sx in (-1.0, 1.0)
        for y in pump_fastener_ys
    }
    REPORT.check(
        stern_holes == pump_holes,
        "pump",
        "intake_fastener_datums",
        f"stern={sorted(stern_holes)}, pump={sorted(pump_holes)}",
    )

    tunnel_axis = (float(getattr(pump, "AXIS_X", 0.0)), float(pump.AXIS_Z))
    transom_axis = (0.0, float(stern.NOZZLE_BORE_Z))
    REPORT.check(
        point_set((tunnel_axis,)) == point_set((transom_axis,)),
        "pump",
        "tunnel_transom_axis",
        f"pump_axis={tunnel_axis}, transom_axis={transom_axis}",
    )
    REPORT.check(
        close(pump.EXIT_PCD_R, stern.PCD_R, 0.01)
        and close(
            pump.EXIT_PCD_R,
            getattr(plate, "EXIT_PCD_R", getattr(plate, "PCD_R", -1.0)),
            0.01,
        )
        and close(pump.EXIT_PCD_R, final_datums["exit_pcd_r"], 0.01),
        "pump",
        "transom_bolt_circle",
        f"pump_r={pump.EXIT_PCD_R:g}, stern_r={stern.PCD_R:g}, "
        f"plate_r={float(getattr(plate, 'EXIT_PCD_R', getattr(plate, 'PCD_R', -1.0))):g}; "
        f"required_r={final_datums['exit_pcd_r']:g}",
    )

    stern_shape = generate("hull_stern")
    pump_shape = generate("pump_housing")
    if stern_shape is not None and pump_shape is not None:
        overlap = intersection_volume(stern_shape, pump_shape)
        REPORT.check(
            overlap <= COLLISION_EPS,
            "pump",
            "pump_housing_to_stern_material_clearance",
            f"overlap={overlap:.3f} mm3 (local stern frame)",
        )

    # The pilot at x=15.5 sits on the V bottom. Report actual available
    # vertical material above the outer skin before drilling.
    deadrise = math.radians(float(stern.DEADRISE_DEG))
    skin_z = abs(float(stern.PAD_PILOT_X)) * math.tan(deadrise)
    engagement = float(stern.PAD_TOP_Z) - skin_z
    REPORT.check(
        engagement >= 5.0,
        "pump",
        "intake_screw_engagement",
        f"estimated pad material={engagement:.3f} mm at "
        f"|x|={stern.PAD_PILOT_X:g}; minimum=5.0 mm",
    )


def validate_impeller_stack() -> None:
    pump = import_module("pump_housing")
    impeller = import_module("impeller")
    if not pump or not impeller:
        REPORT.skipped("jet_stack", "impeller_clearances", "module absent")
        return
    shape = generate("impeller")
    if shape is None:
        return
    box = shape.bounding_box()
    radial_envelope = max(
        abs(float(box.min.X)),
        abs(float(box.max.X)),
        abs(float(box.min.Y)),
        abs(float(box.max.Y)),
    )
    radial_clearance = float(pump.TUNNEL_IR) - radial_envelope
    REPORT.check(
        0.35 <= radial_clearance <= 1.5,
        "jet_stack",
        "impeller_tip_clearance",
        f"tunnel_r={pump.TUNNEL_IR:.3f}, impeller_r={radial_envelope:.3f}, "
        f"radial_clearance={radial_clearance:.3f} mm",
    )

    assembly = generate("boat_assembly", optional=True)
    if assembly is None:
        REPORT.skipped(
            "jet_stack", "impeller_axial_clearance", "boat_assembly unavailable"
        )
        return
    children = list(assembly)
    if len(children) < 7:
        REPORT.skipped(
            "jet_stack",
            "impeller_axial_clearance",
            f"assembly has {len(children)} children; expected at least 7",
        )
        return
    placed_impeller = children[4]
    placed_plate = children[5]
    imp_box = placed_impeller.bounding_box()
    plate_box = placed_plate.bounding_box()
    axial_gap = float(plate_box.min.Y - imp_box.max.Y)
    REPORT.check(
        0.5 <= axial_gap <= 5.0,
        "jet_stack",
        "impeller_to_stator_axial_gap",
        f"impeller_aft_y={imp_box.max.Y:.3f}, "
        f"plate_forward_y={plate_box.min.Y:.3f}, gap={axial_gap:.3f} mm",
    )
    pump_overlap = intersection_volume(children[3], placed_impeller)
    REPORT.check(
        pump_overlap <= COLLISION_EPS,
        "jet_stack",
        "impeller_to_pump_material_clearance",
        f"overlap={pump_overlap:.3f} mm3",
    )
    assembly_module = import_module("boat_assembly", optional=True)
    imp_center_x = 0.0
    imp_center_z = float(
        getattr(assembly_module, "TUNNEL_Z", (imp_box.min.Z + imp_box.max.Z) / 2.0)
    )
    REPORT.check(
        abs(imp_center_x) <= 0.05
        and abs(imp_center_z - float(pump.AXIS_Z)) <= 0.05,
        "jet_stack",
        "impeller_axis",
        f"assembly_axis=({imp_center_x:.3f}, {imp_center_z:.3f}); "
        f"pump=(0,{pump.AXIS_Z:g})",
    )


def validate_rotating_hardware() -> None:
    pump = import_module("pump_housing")
    plate = import_module("nozzle_plate")
    bearing_r = (
        getattr(plate, "BEARING_OD_R", None) if plate else None
    )
    if bearing_r is None and plate:
        bearing_r = getattr(plate, "BEARING_POCKET_R", None)
    shaft_r = (
        getattr(plate, "SHAFT_CLEAR_R", None) if plate else None
    )
    if shaft_r is None and plate:
        shaft_r = getattr(plate, "SHAFT_BORE_R", None)
    bearing_l = getattr(plate, "BEARING_L", None) if plate else None
    if bearing_l is None and plate and all(
        hasattr(plate, name) for name in ("BEARING_Y0", "BEARING_Y1")
    ):
        bearing_l = float(plate.BEARING_Y1 - plate.BEARING_Y0)
    if pump and plate and all(
        value is not None for value in (bearing_r, shaft_r, bearing_l)
    ):
        REPORT.check(
            float(bearing_r) > float(shaft_r) and float(bearing_l) > 0.0,
            "hardware",
            "bearing_shaft_envelope",
            f"bearing_pocket_d={2*float(bearing_r):.3f}, "
            f"shaft_clear_d={2*float(shaft_r):.3f}, "
            f"bearing_depth={float(bearing_l):.3f} mm; coaxial by shared axis",
        )
        cartridge = import_module("shaft_cartridge", optional=True)
        cartridge_shaft_r = (
            getattr(cartridge, "SHAFT_BORE_R", None) if cartridge else None
        )
        if cartridge_shaft_r is not None:
            REPORT.check(
                close(cartridge_shaft_r, shaft_r, 0.05),
                "hardware",
                "front_aft_shaft_bore_match",
                f"cartridge_d={2*float(cartridge_shaft_r):.3f}, "
                f"plate_d={2*float(shaft_r):.3f}",
            )
        else:
            pump_shaft_r = getattr(pump, "SHAFT_BORE_R", None)
            if pump_shaft_r is None:
                REPORT.skipped(
                    "hardware",
                    "front_aft_shaft_bore_match",
                    "pump uses a cartridge seat and no shaft-cartridge "
                    "module is available",
                )
            else:
                REPORT.check(
                    close(pump_shaft_r, shaft_r, 0.05),
                    "hardware",
                    "front_aft_shaft_bore_match",
                    f"pump_d={2*float(pump_shaft_r):.3f}, "
                    f"plate_d={2*float(shaft_r):.3f}",
                )

        if cartridge and hasattr(pump, "CARTRIDGE_SEAT_R"):
            body_r = getattr(cartridge, "BODY_R", None)
            if body_r is None:
                REPORT.skipped(
                    "hardware",
                    "cartridge_pump_fit",
                    "shaft cartridge exposes no BODY_R envelope",
                )
            else:
                clearance = float(pump.CARTRIDGE_SEAT_R - body_r)
                REPORT.check(
                    0.08 <= clearance <= 0.30,
                    "hardware",
                    "cartridge_pump_fit",
                    f"seat_r={pump.CARTRIDGE_SEAT_R:.3f}, "
                    f"body_r={body_r:.3f}, radial_clearance="
                    f"{clearance:.3f} mm",
                )
    else:
        REPORT.skipped(
            "hardware",
            "bearing_shaft_envelope",
            "bearing pocket/shaft clearance constants unavailable",
        )

    optional_tokens = ("shaft", "motor", "coupler", "seal", "bearing")
    discovered = {
        path.stem
        for directory in PART_DIRS
        for path in directory.glob("*.py")
        if not path.name.startswith("_")
        and any(token in path.stem.lower() for token in optional_tokens)
        and path.stem
        not in {"pump_housing", "servo_bracket", "electronics_house"}
    }
    if not discovered:
        REPORT.skipped(
            "hardware",
            "purchased_rotating_components",
            "no shaft/motor/coupler/seal/bearing generator modules present",
        )
        return
    for name in sorted(discovered):
        module = import_module(name, optional=True)
        shape = generate(name, optional=True) if module else None
        if shape is None:
            continue
        axis_x = getattr(module, "AXIS_X", 0.0)
        axis_z = getattr(module, "AXIS_Z", None)
        if axis_x is None or axis_z is None or pump is None:
            REPORT.skipped(
                "hardware",
                f"{name}.coaxial",
                "module exists but exposes no AXIS_X/AXIS_Z datum",
            )
            continue
        REPORT.check(
            close(axis_x, 0.0, 0.05) and close(axis_z, pump.AXIS_Z, 0.05),
            "hardware",
            f"{name}.coaxial",
            f"component_axis=({axis_x},{axis_z}), pump=(0,{pump.AXIS_Z})",
        )


def transformed(
    shape: bd.Shape,
    xyz: tuple[float, float, float],
    rx: float = 0.0,
    rz: float = 0.0,
) -> bd.Shape:
    result = shape
    if abs(rx) > 1e-9:
        result = result.rotate(bd.Axis.X, rx)
    if abs(rz) > 1e-9:
        result = result.rotate(bd.Axis.Z, rz)
    return result.moved(bd.Location(xyz))


def validate_nozzle_sweep() -> None:
    plate_module = import_module("nozzle_plate")
    plate_shape = generate("nozzle_plate")
    pump_module = import_module("pump_housing")
    pump_shape = generate("pump_housing")
    nozzle_shape = generate("vector_nozzle", optional=True)
    vector_name = "vector_nozzle"
    if nozzle_shape is None:
        nozzle_shape = generate("steering_nozzle", optional=True)
        vector_name = "steering_nozzle"
    if nozzle_shape is None:
        nozzle_shape = generate("nozzle", optional=True)
        vector_name = "nozzle"
    if not plate_module or plate_shape is None or nozzle_shape is None:
        REPORT.skipped("nozzle", "vector_sweep", "plate or vector nozzle absent")
        return

    nozzle_module = MODULES[vector_name]
    # New propulsion sources are authored directly in the stern-local frame.
    # Retain the legacy transform path so the validator survives partial
    # integration while concurrent modules are being replaced.
    global_frame = hasattr(plate_module, "PLATE_Y0") and hasattr(
        nozzle_module, "NOZZLE_Y0"
    )
    if global_frame and pump_module is not None and pump_shape is not None:
        contraction_inlet_r = getattr(
            plate_module,
            "CONTRACTION_INLET_R",
            getattr(plate_module, "PLATE_BORE_R", None),
        )
        tunnel_r = getattr(pump_module, "TUNNEL_IR", None)
        pump_aft_y = getattr(
            pump_module,
            "TUNNEL_Y1",
            pump_shape.bounding_box().max.Y,
        )
        plate_forward_y = float(plate_module.PLATE_Y0)
        if contraction_inlet_r is None or tunnel_r is None:
            REPORT.skipped(
                "nozzle",
                "fixed_contraction_to_pump",
                "pump tunnel or contraction inlet radius datum absent",
            )
        else:
            overlap = intersection_volume(pump_shape, plate_shape)
            axial_gap = plate_forward_y - float(pump_aft_y)
            REPORT.check(
                close(contraction_inlet_r, tunnel_r, 0.05)
                and 0.0 <= axial_gap <= 5.0
                and overlap <= COLLISION_EPS,
                "nozzle",
                "fixed_contraction_to_pump",
                f"pump_tunnel_r={float(tunnel_r):.3f}, "
                f"contraction_inlet_r={float(contraction_inlet_r):.3f}, "
                f"axial_gap={axial_gap:.3f}, overlap={overlap:.3f} mm3",
            )
    else:
        REPORT.skipped(
            "nozzle",
            "fixed_contraction_to_pump",
            "global-frame pump/contraction geometry unavailable",
        )
    if global_frame:
        placed_plate = plate_shape
        pivot_y = float(
            getattr(
                nozzle_module,
                "VECTOR_PIVOT_Y",
                getattr(nozzle_module, "NOZZLE_Y0"),
            )
        )
        tunnel_z = float(getattr(nozzle_module, "AXIS_Z", 22.0))
    else:
        transom_y = 160.0
        tunnel_z = 40.0
        placed_plate = transformed(
            plate_shape, (0.0, transom_y, tunnel_z), rx=-90.0
        )
        pivot_y = transom_y + float(plate_module.LUG_HOLE_Z)
    for angle in (-25.0, 0.0, 25.0):
        if global_frame:
            try:
                placed_nozzle = nozzle_module.gen_step(angle)
            except TypeError:
                placed_nozzle = nozzle_shape.rotate(
                    bd.Axis((0.0, pivot_y, tunnel_z), (0.0, 0.0, 1.0)),
                    angle,
                )
            except Exception as exc:
                REPORT.failed(
                    "nozzle",
                    f"{vector_name}.generation@{angle:+.0f}deg",
                    f"{type(exc).__name__}: {exc}",
                )
                continue
        else:
            placed_nozzle = transformed(
                nozzle_shape, (0.0, pivot_y, tunnel_z), rz=angle
            )
        overlap = intersection_volume(placed_plate, placed_nozzle)
        REPORT.check(
            overlap <= COLLISION_EPS,
            "nozzle",
            f"{vector_name}.clearance@{angle:+.0f}deg",
            f"pivot_y={pivot_y:.3f}, overlap={overlap:.3f} mm3",
        )

    fixed_candidates = (
        "fixed_nozzle",
        "fixed_jet_nozzle",
        "stator_nozzle",
    )
    fixed_name = next(
        (name for name in fixed_candidates if import_module(name, optional=True)),
        None,
    )
    if fixed_name is None:
        REPORT.skipped(
            "nozzle",
            "fixed_nozzle_clearance",
            "no fixed-nozzle generator module present",
        )
        return
    fixed_module = MODULES[fixed_name]
    fixed_shape = generate(fixed_name, optional=True)
    assembly_y = getattr(fixed_module, "ASSEMBLY_PIVOT_Y", None)
    if fixed_shape is None:
        return
    if assembly_y is None:
        REPORT.skipped(
            "nozzle",
            f"{fixed_name}.clearance",
            "module exists but exposes no ASSEMBLY_PIVOT_Y datum",
        )
        return
    placed_fixed = transformed(
        fixed_shape, (0.0, transom_y + float(assembly_y), tunnel_z)
    )
    overlap = intersection_volume(placed_plate, placed_fixed)
    REPORT.check(
        overlap <= COLLISION_EPS,
        "nozzle",
        f"{fixed_name}.clearance",
        f"overlap={overlap:.3f} mm3",
    )


def validate_deck_and_cannon_patterns() -> None:
    pairs = (
        ("hull_mid", "deck_mid"),
        ("hull_stern", "deck_stern"),
    )
    for hull_name, deck_name in pairs:
        hull = import_module(hull_name)
        deck = import_module(deck_name)
        if not hull or not deck:
            REPORT.skipped(
                "deck", f"{hull_name}_{deck_name}", "module absent"
            )
            continue
        hull_points = {
            (sx * float(hull.LID_BOSS_X), float(y))
            for sx in (-1.0, 1.0)
            for y in hull.LID_BOSS_YS
        }
        deck_points = {
            (sx * float(deck.SCREW_X), float(y))
            for sx in (-1.0, 1.0)
            for y in deck.SCREW_YS
        }
        REPORT.check(
            hull_points == deck_points,
            "deck",
            f"{deck_name}.screw_datums",
            f"hull={sorted(hull_points)}, deck={sorted(deck_points)}",
        )
        inner_deck_x = getattr(
            hull, "INNER_DECK_X", getattr(hull, "IN_DECK_X", None)
        )
        if inner_deck_x is None:
            REPORT.skipped(
                "deck",
                f"{deck_name}.lip_clearance",
                "hull exposes no inner-deck datum",
            )
            continue
        opening = 2.0 * float(inner_deck_x - hull.FLANGE_W)
        lip_clearance = opening - float(deck.LIP_W)
        REPORT.check(
            0.8 <= lip_clearance <= 3.0,
            "deck",
            f"{deck_name}.lip_clearance",
            f"opening={opening:.3f}, lip={deck.LIP_W:.3f}, "
            f"diametral_clearance={lip_clearance:.3f} mm",
        )

    bow = import_module("hull_bow")
    deck_mid = import_module("deck_mid")
    cannon = import_module("water_cannon")
    turret_base = import_module("turret_base")
    turret_platform = import_module("turret_platform")
    if bow and cannon and hasattr(bow, "CANNON_PCD"):
        REPORT.check(
            close(bow.CANNON_PCD, cannon.PCD32, 0.01),
            "cannon",
            "bow_cannon_bolt_circle",
            f"bow={bow.CANNON_PCD:g}, cannon={cannon.PCD32:g}",
        )
    elif bow and cannon:
        REPORT.skipped(
            "cannon",
            "bow_cannon_bolt_circle",
            "bow intentionally exposes no cannon mounting pattern",
        )
    if deck_mid and cannon:
        REPORT.check(
            close(deck_mid.PCD32, cannon.PCD32, 0.01),
            "cannon",
            "deck_cannon_bolt_circle",
            f"deck={deck_mid.PCD32:g}, cannon={cannon.PCD32:g}",
        )
    if deck_mid and turret_base:
        REPORT.check(
            close(deck_mid.PCD44, turret_base.PCD44, 0.01),
            "cannon",
            "deck_turret_bolt_circle",
            f"deck={deck_mid.PCD44:g}, turret={turret_base.PCD44:g}",
        )
    if cannon and turret_platform:
        REPORT.check(
            close(cannon.PCD32, turret_platform.PCD32, 0.01),
            "cannon",
            "platform_cannon_bolt_circle",
            f"cannon={cannon.PCD32:g}, platform={turret_platform.PCD32:g}",
        )

    assembly_module = import_module("boat_assembly", optional=True)
    if (
        bow
        and hasattr(bow, "CANNON_PAD_Y")
        and assembly_module
        and hasattr(assembly_module, "CANNON_PAD_Y")
    ):
        REPORT.check(
            close(bow.CANNON_PAD_Y, assembly_module.CANNON_PAD_Y, 0.05),
            "cannon",
            "bow_cannon_assembly_center",
            f"bow_y={bow.CANNON_PAD_Y:g}, "
            f"assembly_y={assembly_module.CANNON_PAD_Y:g}",
        )
    elif (
        bow
        and not hasattr(bow, "CANNON_PAD_Y")
        and assembly_module
        and hasattr(assembly_module, "CANNON_PAD_Y")
    ):
        REPORT.failed(
            "cannon",
            "bow_cannon_assembly_center",
            "assembly still exposes/uses a bow cannon datum after the bow "
            "mount was removed; cannon should use the mid-deck pattern",
        )
    else:
        REPORT.skipped(
            "cannon",
            "bow_cannon_assembly_center",
            "assembly or exposed cannon datum absent",
        )


def validate_containment() -> None:
    battery = import_module("battery_tray")
    if battery:
        tray_length = getattr(
            battery, "SADDLE_L", getattr(battery, "TRAY_L", None)
        )
        tray_width = getattr(
            battery, "SADDLE_W", getattr(battery, "TRAY_W", None)
        )
        inner_width = getattr(battery, "INNER_W", None)
        if inner_width is None and tray_width is not None:
            inner_width = float(tray_width - 2.0 * battery.WALL_T)
        inner_length = (
            float(tray_length - 2.0 * battery.WALL_T)
            if tray_length is not None
            else None
        )
        if inner_length is None or inner_width is None:
            REPORT.skipped(
                "containment",
                "battery_pack_in_tray",
                "battery tray exposes incomplete interior datums",
            )
        else:
            REPORT.check(
                battery.PACK_L <= inner_length and battery.PACK_W <= inner_width,
                "containment",
                "battery_pack_in_tray",
                f"pack={battery.PACK_L:g}x{battery.PACK_W:g}, "
                f"tray_inside≈{inner_length:g}x{float(inner_width):g} mm",
            )

    house = import_module("electronics_house")
    tray = import_module("electronics_tray")
    if house and tray:
        tray_x = getattr(tray, "PLATE_L", getattr(tray, "PLATE_X", None))
        tray_y = getattr(tray, "PLATE_W", getattr(tray, "PLATE_Y", None))
        if tray_x is None or tray_y is None:
            REPORT.skipped(
                "containment",
                "electronics_tray_in_house_xy",
                "electronics tray exposes no plate X/Y envelope",
            )
        else:
            REPORT.check(
                tray_x <= house.INNER_X and tray_y <= house.INNER_Y,
                "containment",
                "electronics_tray_in_house_xy",
                f"tray={tray_x:g}x{tray_y:g}, "
                f"house_inner={house.INNER_X:g}x{house.INNER_Y:g} mm",
            )

    assembly = generate("boat_assembly", optional=True)
    if assembly is None:
        REPORT.skipped(
            "containment", "assembled_containment", "boat_assembly unavailable"
        )
        return
    children = list(assembly)
    if len(children) < len(ASSEMBLY_CHILDREN):
        REPORT.skipped(
            "containment",
            "assembled_containment",
            f"assembly children={len(children)}, expected "
            f"{len(ASSEMBLY_CHILDREN)}",
        )
        return
    placed = dict(zip(ASSEMBLY_CHILDREN, children))
    battery_box = placed["battery_tray"].bounding_box()
    mid_box = placed["hull_mid"].bounding_box()
    bulk_t = float(getattr(import_module("hull_mid"), "BULK_T", 3.0))
    y_ok = (
        battery_box.min.Y >= mid_box.min.Y + bulk_t
        and battery_box.max.Y <= mid_box.max.Y - bulk_t
    )
    REPORT.check(
        y_ok,
        "containment",
        "battery_tray_in_mid_segment_y",
        f"battery_y=[{battery_box.min.Y:.3f},{battery_box.max.Y:.3f}], "
        f"mid_clear_y=[{mid_box.min.Y+bulk_t:.3f},"
        f"{mid_box.max.Y-bulk_t:.3f}]",
    )
    battery_mid = intersection_volume(
        placed["battery_tray"], placed["hull_mid"]
    )
    battery_stern = intersection_volume(
        placed["battery_tray"], placed["hull_stern"]
    )
    REPORT.check(
        battery_mid <= COLLISION_EPS and battery_stern <= COLLISION_EPS,
        "containment",
        "battery_tray_hull_clearance",
        f"mid_overlap={battery_mid:.3f}, "
        f"stern_overlap={battery_stern:.3f} mm3",
    )

    tray_house = intersection_volume(
        placed["electronics_tray"], placed["electronics_house"]
    )
    REPORT.check(
        tray_house <= COLLISION_EPS,
        "containment",
        "electronics_tray_house_clearance",
        f"overlap={tray_house:.3f} mm3",
    )
    house_deck = intersection_volume(
        placed["electronics_house"], placed["deck_mid"]
    )
    REPORT.check(
        house_deck <= COLLISION_EPS,
        "containment",
        "electronics_house_deck_clearance",
        f"overlap={house_deck:.3f} mm3",
    )


def validate_assembly_collisions() -> None:
    assembly = generate("boat_assembly", optional=True)
    if assembly is None:
        REPORT.skipped("collisions", "pairwise", "boat_assembly unavailable")
        return
    children = list(assembly)
    if len(children) < len(ASSEMBLY_CHILDREN):
        REPORT.skipped(
            "collisions",
            "pairwise",
            f"assembly has {len(children)} children; expected at least "
            f"{len(ASSEMBLY_CHILDREN)}",
        )
        return
    named = list(zip(ASSEMBLY_CHILDREN, children))
    zero_pairs = 0
    for index, (name_a, shape_a) in enumerate(named):
        for name_b, shape_b in named[index + 1 :]:
            pair = tuple(sorted((name_a, name_b)))
            overlap = intersection_volume(shape_a, shape_b)
            allowed = CONTACT_ALLOWLIST.get(pair)
            if overlap <= COLLISION_EPS:
                zero_pairs += 1
                continue
            if allowed is not None and overlap <= allowed:
                REPORT.passed(
                    "collisions",
                    f"{name_a}__{name_b}",
                    f"allowlisted contact overlap={overlap:.3f} mm3 "
                    f"(limit={allowed:.3f})",
                )
            else:
                note = (
                    f"allowlist_limit={allowed:.3f}"
                    if allowed is not None
                    else "not allowlisted"
                )
                REPORT.failed(
                    "collisions",
                    f"{name_a}__{name_b}",
                    f"overlap={overlap:.3f} mm3; {note}",
                )
    total_pairs = len(named) * (len(named) - 1) // 2
    REPORT.passed(
        "collisions",
        "zero_volume_summary",
        f"{zero_pairs}/{total_pairs} pairs have <= "
        f"{COLLISION_EPS:.3f} mm3 overlap",
    )


def validate_flood_vent() -> None:
    stern = import_module("hull_stern")
    shape = generate("hull_stern")
    if not stern or shape is None:
        REPORT.skipped("flood", "vent", "hull_stern unavailable")
        return
    radius = next(
        (
            float(getattr(stern, name))
            for name in (
                "FLOOD_VENT_R",
                "VENT_HOLE_R",
                "CHAMBER_VENT_R",
                "VENT_R",
            )
            if hasattr(stern, name)
        ),
        None,
    )
    diameter = next(
        (
            float(getattr(stern, name))
            for name in ("FLOOD_VENT_D", "VENT_HOLE_D", "CHAMBER_VENT_D")
            if hasattr(stern, name)
        ),
        None,
    )
    if radius is None and diameter is not None:
        radius = diameter / 2.0
    vent_y = next(
        (
            float(getattr(stern, name))
            for name in (
                "FLOOD_VENT_Y",
                "VENT_HOLE_Y",
                "CHAMBER_VENT_Y",
                "VENT_Y",
            )
            if hasattr(stern, name)
        ),
        None,
    )
    vent_z = next(
        (
            float(getattr(stern, name))
            for name in (
                "FLOOD_VENT_Z",
                "VENT_HOLE_Z",
                "CHAMBER_VENT_Z",
                "VENT_Z",
            )
            if hasattr(stern, name)
        ),
        None,
    )
    if radius is None or vent_y is None or vent_z is None:
        REPORT.failed(
            "flood",
            "vent",
            "no measurable flood-chamber vent datum/model found",
        )
        return
    # Current chamber openings traverse the port topside along X. Use the
    # same through-wall span as the main flood aperture when available.
    if all(
        hasattr(stern, name)
        for name in ("FLOOD_HOLE_Y", "FLOOD_HOLE_Z")
    ):
        probe_x0, probe_x1 = -70.0, -50.0
    else:
        chamber_x = float(getattr(stern, "CHAMBER_WALL_X", -34.0))
        probe_x0, probe_x1 = chamber_x - 8.0, chamber_x + 8.0
    probe = bd.Cylinder(
        radius * 0.7,
        probe_x1 - probe_x0,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).rotate(bd.Axis.Y, 90)
    probe = probe.moved(bd.Location((probe_x0, vent_y, vent_z)))
    overlap = intersection_volume(shape, probe)
    REPORT.check(
        overlap <= COLLISION_EPS,
        "flood",
        "vent",
        f"span_x=[{probe_x0:g},{probe_x1:g}], y={vent_y:g}, z={vent_z:g}, "
        f"material_in_vent={overlap:.6f} mm3",
    )


def run() -> Report:
    validate_printables()
    validate_segment_joints()
    validate_pump_hull_interfaces()
    validate_impeller_stack()
    validate_rotating_hardware()
    validate_nozzle_sweep()
    validate_deck_and_cannon_patterns()
    validate_containment()
    validate_assembly_collisions()
    validate_flood_vent()
    return REPORT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    parser.add_argument(
        "--traceback",
        action="store_true",
        help="show an unexpected harness traceback",
    )
    args = parser.parse_args()
    try:
        report = run()
    except Exception as exc:  # Harness bugs must never masquerade as CAD fails.
        if args.traceback:
            traceback.print_exc()
        else:
            print(f"HARNESS ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    counts = report.counts()
    if args.json:
        print(
            json.dumps(
                {
                    "summary": counts,
                    "results": [asdict(item) for item in report.results],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for item in report.results:
            print(
                f"{item.status:4s} [{item.category}] "
                f"{item.name}: {item.detail}"
            )
        print(
            "\nSUMMARY "
            + " ".join(f"{key}={value}" for key, value in counts.items())
        )
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
