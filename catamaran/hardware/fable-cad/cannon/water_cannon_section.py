"""Half-section of water_cannon (validation aid: shows the internal bore).

Cuts the cannon at the X=0 plane (keeps -X half) so the Ø4 barb bore,
Ø6 main bore, and Ø6->Ø2 converging nozzle are visible in snapshots.
"""

import os
import sys

import build123d as bd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import water_cannon  # noqa: E402


def gen_step() -> bd.Part:
    part = water_cannon.gen_step()
    keep_neg_x = bd.Box(200.0, 400.0, 200.0).moved(
        bd.Location((100.0, 20.0, 10.0)))
    return part.cut(keep_neg_x)


if __name__ == "__main__":
    p = gen_step()
    bb = p.bounding_box()
    sz = bb.max - bb.min
    print(f"bbox: {sz.X:.2f} x {sz.Y:.2f} x {sz.Z:.2f} mm")
