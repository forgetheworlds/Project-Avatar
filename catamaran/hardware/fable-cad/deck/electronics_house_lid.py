"""Gasketed screw-down lid for ``electronics_house.py``."""

import build123d as bd

LID_X = 73.6
LID_Y = 73.6
LID_T = 3.0
EDGE_CHAMFER = 2.0

SCREW_D = 3.4
SCREW_X = 31.0
SCREW_Y = 31.0
HEAD_RECESS_D = 6.5
HEAD_RECESS_DEPTH = 1.2

# Closed rectangular gasket groove on the underside for 1.5–2 mm cord or
# closed-cell foam.  The groove never breaks through the top face.
GROOVE_OUTER_X = 67.0
GROOVE_OUTER_Y = 67.0
GROOVE_WIDTH = 1.8
GROOVE_DEPTH = 1.0


def _box(
    size_x: float,
    size_y: float,
    size_z: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
    z0: float = 0.0,
) -> bd.Part:
    return bd.Box(size_x, size_y, size_z).moved(
        bd.Location((center_x, center_y, z0 + size_z / 2.0))
    )


def _cyl(
    diameter: float, height: float, center_x: float, center_y: float, z0: float
) -> bd.Part:
    return bd.Cylinder(diameter / 2.0, height).moved(
        bd.Location((center_x, center_y, z0 + height / 2.0))
    )


def gen_step() -> bd.Part:
    lid = _box(LID_X, LID_Y, LID_T)

    groove_outer = _box(
        GROOVE_OUTER_X,
        GROOVE_OUTER_Y,
        GROOVE_DEPTH + 0.2,
        z0=-0.1,
    )
    groove_inner = _box(
        GROOVE_OUTER_X - 2.0 * GROOVE_WIDTH,
        GROOVE_OUTER_Y - 2.0 * GROOVE_WIDTH,
        GROOVE_DEPTH + 1.0,
        z0=-0.5,
    )
    lid = lid.cut(groove_outer.cut(groove_inner))

    for x in (-SCREW_X, SCREW_X):
        for y in (-SCREW_Y, SCREW_Y):
            lid = lid.cut(_cyl(SCREW_D, LID_T + 2.0, x, y, -1.0))
            lid = lid.cut(
                _cyl(
                    HEAD_RECESS_D,
                    HEAD_RECESS_DEPTH + 0.2,
                    x,
                    y,
                    LID_T - HEAD_RECESS_DEPTH,
                )
            )

    lid.label = "electronics_house_gasketed_lid"
    return lid


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    print(f"lid bbox: {size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm")
    assert len(result.solids()) == 1
    assert GROOVE_DEPTH < LID_T
    assert GROOVE_WIDTH >= 1.5
