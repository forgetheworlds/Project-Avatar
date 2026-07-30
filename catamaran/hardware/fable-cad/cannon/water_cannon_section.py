"""Half-section validation aid for the serviceable cannon flow path."""

import os
import sys

import build123d as bd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import water_cannon  # noqa: E402


def gen_step() -> bd.Part:
    part = water_cannon.gen_step()
    keep_positive_x = bd.Box(200.0, 400.0, 200.0).moved(
        bd.Location((-100.0, 20.0, 10.0))
    )
    section = part.cut(keep_positive_x)
    section.label = "water_cannon_flow_path_section"
    return section


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    print(f"section bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    assert len(result.solids()) >= 1
