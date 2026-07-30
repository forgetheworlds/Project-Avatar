"""Source-level hydrostatic checks for the Project Boat hull.

This is deliberately a light-weight geometry integrator, not a CFD or
stability program.  It mirrors the design waterlines used by hull_bow.py and
the constant mid/stern section closely enough to catch draft/displacement
mistakes before STEP generation.

The reported ``ideal`` displacement treats the hull as a closed external
envelope.  The starboard wet-well is open to the lake and is therefore
reported separately.  Intake-duct flooding is pump-geometry dependent and is
not subtracted here; the final loaded float test remains authoritative.
"""

from __future__ import annotations

import math

BEAM = 120.0
HALF_BEAM = BEAM / 2.0
DECK_HALF = 64.0
DEPTH = 72.0
DEADRISE_DEG = 20.0
CHINE_H = HALF_BEAM * math.tan(math.radians(DEADRISE_DEG))
SEG_L = 160.0
HULL_L = 3.0 * SEG_L

BOW_TIP_SCALE = 0.02
STEM_KEEL_ENTRY = 42.0
TIP_Z = 64.0

WET_WELL_X = 32.0
WET_WELL_ID_R = 19.0


def smootherstep(u: float) -> float:
    """Quintic ease with continuous first and second derivatives."""
    u = max(0.0, min(1.0, u))
    return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))


def bow_scale(y: float) -> float:
    """One globally fair monotonic beam law from tip to the exact joint."""
    return BOW_TIP_SCALE + (1.0 - BOW_TIP_SCALE) * smootherstep(y / SEG_L)


def bow_deck_scale(y: float) -> float:
    """Forward flare for reserve buoyancy, bounded to the 128 mm deck beam."""
    u = max(0.0, min(1.0, y / SEG_L))
    reserve_flare = 0.16 * 4.0 * u * (1.0 - u)
    return min(1.0, bow_scale(y) + reserve_flare)


def stem_y(z: float) -> float:
    """Fair raked stem used by the hydrostatic envelope."""
    if z >= TIP_Z:
        return 0.0
    q = max(0.0, min(1.0, z / TIP_Z))
    return STEM_KEEL_ENTRY * (1.0 - smootherstep(q))


def _half_width(z: float, chine_scale: float, deck_scale: float) -> float:
    if z <= 0.0:
        return 0.0
    if z <= CHINE_H:
        return HALF_BEAM * chine_scale * z / CHINE_H
    f = min(1.0, (z - CHINE_H) / (DEPTH - CHINE_H))
    return (
        HALF_BEAM * chine_scale
        + (DECK_HALF * deck_scale - HALF_BEAM * chine_scale) * f
    )


def _trapz(func, a: float, b: float, n: int) -> float:
    if b <= a:
        return 0.0
    h = (b - a) / n
    total = 0.5 * (func(a) + func(b))
    for i in range(1, n):
        total += func(a + i * h)
    return total * h


def bow_section_area(y: float, draft: float) -> float:
    """Submerged bow section area in mm²."""
    if draft <= 0.0:
        return 0.0
    z0 = 0.0
    if y < STEM_KEEL_ENTRY:
        # Invert the monotonic stem numerically.  This also keeps the helper
        # coupled to the exact fair stem law instead of an algebraic shortcut.
        lo, hi = 0.0, TIP_Z
        for _ in range(50):
            mid = (lo + hi) / 2.0
            if stem_y(mid) > y:
                lo = mid
            else:
                hi = mid
        z0 = (lo + hi) / 2.0
    z1 = min(draft, DEPTH)
    if z0 >= z1:
        return 0.0
    cs = bow_scale(y)
    ds = bow_deck_scale(y)
    return _trapz(lambda z: 2.0 * _half_width(z, cs, ds), z0, z1, 160)


def constant_section_area(draft: float) -> float:
    """Submerged mid/stern section area in mm²."""
    z1 = min(max(0.0, draft), DEPTH)
    return _trapz(lambda z: 2.0 * _half_width(z, 1.0, 1.0), 0.0, z1, 240)


def ideal_displacement_l(draft: float) -> float:
    """Closed-envelope displacement in litres."""
    bow_v = _trapz(lambda y: bow_section_area(y, draft), 0.0, SEG_L, 600)
    aft_v = constant_section_area(draft) * 2.0 * SEG_L
    return (bow_v + aft_v) / 1_000_000.0


def wet_well_flooded_l(draft: float) -> float:
    """Approximate lake-connected wet-well water volume below the waterline."""
    local_bottom = WET_WELL_X * math.tan(math.radians(DEADRISE_DEG))
    column = max(0.0, min(draft, DEPTH) - local_bottom)
    return math.pi * WET_WELL_ID_R**2 * column / 1_000_000.0


def draft_for_mass_kg(mass_kg: float, include_wet_well: bool = True) -> float:
    """Solve level fresh-water draft; intake flooding is intentionally omitted."""
    lo, hi = 0.0, DEPTH
    for _ in range(48):
        mid = (lo + hi) / 2.0
        supported = ideal_displacement_l(mid)
        if include_wet_well:
            supported -= wet_well_flooded_l(mid)
        if supported < mass_kg:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def hydrostatic_report(
    masses_kg: tuple[float, ...] = (1.0, 1.15, 1.2, 1.3, 1.4),
) -> list[dict[str, float]]:
    """Return source-level hydrostatic checks for design-load review."""
    rows = []
    for mass in masses_kg:
        ideal = draft_for_mass_kg(mass, include_wet_well=False)
        corrected = draft_for_mass_kg(mass, include_wet_well=True)
        rows.append(
            {
                "mass_kg": mass,
                "ideal_draft_mm": ideal,
                "wet_well_corrected_draft_mm": corrected,
                "wet_well_l": wet_well_flooded_l(corrected),
                "midship_freeboard_mm": DEPTH - corrected,
            }
        )
    return rows


def validate_hydrostatics() -> None:
    rows = hydrostatic_report()
    assert all(0.0 < row["ideal_draft_mm"] < DEPTH for row in rows)
    assert all(
        rows[i]["ideal_draft_mm"] < rows[i + 1]["ideal_draft_mm"]
        for i in range(len(rows) - 1)
    )
    assert all(
        row["wet_well_corrected_draft_mm"] > row["ideal_draft_mm"]
        for row in rows
    )


if __name__ == "__main__":
    validate_hydrostatics()
    print("mass kg | ideal draft | + open wet-well | wet-well | freeboard")
    for row in hydrostatic_report():
        print(
            f"{row['mass_kg']:7.2f} |"
            f" {row['ideal_draft_mm']:10.2f} |"
            f" {row['wet_well_corrected_draft_mm']:15.2f} |"
            f" {row['wet_well_l'] * 1000.0:7.1f} mL |"
            f" {row['midship_freeboard_mm']:8.2f} mm"
        )
    print("Caveat: intake-duct flooding and running trim require physical testing.")
