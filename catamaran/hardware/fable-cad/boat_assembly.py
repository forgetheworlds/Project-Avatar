"""
boat_assembly.py — assembled Project Boat for CAD Viewer preview.

Places every fable-cad printable in the global hull frame:
  X = beam (+starboard), Y = length (bow tip Y=0), Z = height (keel Z=0)

Segment stacking: bow [0..160], mid [160..320], stern [320..480].
Jet / cannon placements follow DESIGN.md mating datums (approximate for
purchased motor/shaft which are not modeled).

gen_step() returns a labeled AssemblyHelper compound.
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
]

import hull_bow  # noqa: E402
import hull_mid  # noqa: E402
import hull_stern  # noqa: E402
import pump_housing  # noqa: E402
import impeller  # noqa: E402
import nozzle_plate  # noqa: E402
import nozzle  # noqa: E402
import servo_bracket  # noqa: E402
import deck_mid  # noqa: E402
import deck_stern  # noqa: E402
import electronics_tray  # noqa: E402
import battery_tray  # noqa: E402
import water_cannon  # noqa: E402
import turret_base  # noqa: E402
import turret_platform  # noqa: E402

SEG_L = 160.0
MID_Y0 = SEG_L
STERN_Y0 = 2 * SEG_L
TRANSOM_Y = STERN_Y0 + SEG_L  # 480
DECK_Z = 72.0
TUNNEL_Z = 40.0


def _rx(part: bd.Part, deg: float) -> bd.Part:
    return part.rotate(bd.Axis.X, deg)


def _place(part: bd.Part, xyz, rx: float = 0.0) -> bd.Part:
    p = part
    if abs(rx) > 1e-9:
        p = _rx(p, rx)
    return p.moved(bd.Location(xyz))


def gen_step():
    asm = AssemblyHelper("project_boat")

    # ── Hull segments ───────────────────────────────────────────
    asm.add(hull_bow.gen_step(), "hull_bow")
    asm.add(_place(hull_mid.gen_step(), (0, MID_Y0, 0)), "hull_mid")
    asm.add(_place(hull_stern.gen_step(), (0, STERN_Y0, 0)), "hull_stern")

    # ── Jet drive (stern-local features already use stern Y) ────
    # Pump housing authored in stern-local frame → +STERN_Y0
    asm.add(
        _place(pump_housing.gen_step(), (0, STERN_Y0, 0)),
        "pump_housing",
    )

    # Impeller: local axis +Z → world +Y (flow aft). Sit in tunnel
    # just forward of the exit flange (~ stern-local Y=140).
    impeller_y = STERN_Y0 + 140.0
    asm.add(
        _place(impeller.gen_step(), (0, impeller_y, TUNNEL_Z), rx=-90.0),
        "impeller",
    )

    # Nozzle plate: local flow +Z → world +Y; forward face at transom.
    asm.add(
        _place(nozzle_plate.gen_step(), (0, TRANSOM_Y, TUNNEL_Z), rx=-90.0),
        "nozzle_plate",
    )

    # Nozzle: local pivot at origin, flow +Y, pivot // world Z.
    # Lug holes are 14 mm aft of plate face → pivot at Y = TRANSOM_Y + 14.
    asm.add(
        _place(nozzle.gen_step(), (0, TRANSOM_Y + 14.0, TUNNEL_Z)),
        "nozzle",
    )

    # Servo bracket on inner transom, centered on pilots X=4..32 → cx=18,
    # Z=67 (as-built). Base plate faces aft → rotate so local +Z → world -Y.
    # (Preview placement — pushrod not modeled.)
    asm.add(
        _place(
            servo_bracket.gen_step(),
            (18.0, TRANSOM_Y - 3.0, 67.0),
            rx=90.0,
        ),
        "servo_bracket",
    )

    # ── Deck lids (plate bottom on flange top Z=72) ──────────────
    asm.add(_place(deck_mid.gen_step(), (0, MID_Y0, DECK_Z)), "deck_mid")
    asm.add(_place(deck_stern.gen_step(), (0, STERN_Y0, DECK_Z)), "deck_stern")

    # ── Trays in mid bay ────────────────────────────────────────
    # Battery on keel near mid-center; electronics above it.
    asm.add(
        _place(battery_tray.gen_step(), (0, MID_Y0 + 80.0, 3.0)),
        "battery_tray",
    )
    asm.add(
        _place(electronics_tray.gen_step(), (0, MID_Y0 + 80.0, 32.0)),
        "electronics_tray",
    )

    # ── Cannon on mid-deck pad (optional turret stacked under it) ─
    # Pad center mid-local (0, 55); pad top = plate 3 + pad 3 = 6 above flange.
    pad_y = MID_Y0 + 55.0
    pad_top_z = DECK_Z + 3.0 + 3.0
    asm.add(
        _place(turret_base.gen_step(), (0, pad_y, pad_top_z)),
        "turret_base",
    )
    # Platform sits on turret body (~27 tall) — preview stack.
    asm.add(
        _place(turret_platform.gen_step(), (0, pad_y, pad_top_z + 27.0)),
        "turret_platform",
    )
    asm.add(
        _place(
            water_cannon.gen_step(),
            (0, pad_y, pad_top_z + 27.0 + 4.0),
        ),
        "water_cannon",
    )

    return asm.build()


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.1f} x {sz.Y:.1f} x {sz.Z:.1f} mm")
    print(f"solids/children: {len(list(p))}  volume: {p.volume/1000:.0f} cm^3")
