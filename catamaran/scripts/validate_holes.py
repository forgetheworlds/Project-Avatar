"""Validation helper: report cylindrical-face axes per STEP (dev tool).

For each STEP, groups cylindrical faces by diameter and prints unique
axis locations (x, y at z=0 of the axis line, plus axis direction), so
PCDs and hole positions can be checked numerically against DESIGN.md.
"""

import math
import sys

import build123d as bd
from build123d import GeomType


def axis_key(face):
    """Return (diameter, point-on-axis, direction) for a cylindrical face."""
    g = face.geom_adaptor()
    cyl = g.Cylinder()
    ax = cyl.Axis()
    loc = ax.Location()
    d = ax.Direction()
    return (2.0 * cyl.Radius(),
            (loc.X(), loc.Y(), loc.Z()),
            (d.X(), d.Y(), d.Z()))


def report(path):
    part = bd.import_step(path)
    print(f"\n===== {path} =====")
    groups = {}
    for f in part.faces().filter_by(GeomType.CYLINDER):
        dia, p, d = axis_key(f)
        dia = round(dia, 3)
        # project axis point to z=0 for vertical axes for readability
        if abs(abs(d[2]) - 1.0) < 1e-6:
            p = (round(p[0], 3), round(p[1], 3), 0.0)
            d = (0.0, 0.0, 1.0)
        else:
            p = tuple(round(v, 3) for v in p)
            d = tuple(round(v, 4) for v in d)
        groups.setdefault(dia, set()).add((p, d))
    for dia in sorted(groups):
        pts = sorted(groups[dia])
        print(f"  D{dia}: {len(pts)} axis/axes")
        for p, d in pts:
            print(f"    at {p} dir {d}")
        # pairwise spacings for 4-hole vertical patterns
        vert = [p for p, d in pts if d == (0.0, 0.0, 1.0)]
        if len(vert) == 4:
            cx = sum(p[0] for p in vert) / 4.0
            cy = sum(p[1] for p in vert) / 4.0
            radii = [math.hypot(p[0] - cx, p[1] - cy) for p in vert]
            print(f"    pattern center ({cx:.3f}, {cy:.3f}) "
                  f"PCD {2 * sum(radii) / 4:.3f}")
            ds = sorted(
                math.hypot(a[0] - b[0], a[1] - b[1])
                for i, a in enumerate(vert) for b in vert[i + 1:])
            print(f"    spacings: {[round(v, 3) for v in ds]}")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        report(path)
