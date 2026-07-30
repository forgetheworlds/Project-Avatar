"""One-piece snap clip for nominal 8 mm-OD (6 mm-ID) silicone hose."""

import build123d as bd

HOSE_OD = 8.0
HOSE_CLEARANCE = 0.4
CLIP_WALL = 2.0
CLIP_LENGTH = 8.0
CLIP_SLOT = 5.5

BASE_X = 24.0
BASE_Y = 12.0
BASE_T = 3.0
CLIP_X = -5.0
MOUNT_X = 7.0
MOUNT_D = 3.4


def _cyl_y(diameter: float, length: float, x: float, z: float) -> bd.Part:
    return (
        bd.Cylinder(diameter / 2.0, length)
        .rotate(bd.Axis.X, 90.0)
        .moved(bd.Location((x, 0.0, z)))
    )


def gen_step() -> bd.Part:
    base = bd.Box(BASE_X, BASE_Y, BASE_T).moved(
        bd.Location((0.0, 0.0, BASE_T / 2.0))
    )

    inner_d = HOSE_OD + 2.0 * HOSE_CLEARANCE
    outer_d = inner_d + 2.0 * CLIP_WALL
    clip_center_z = BASE_T + outer_d / 2.0 - 1.0
    clip = _cyl_y(outer_d, CLIP_LENGTH, CLIP_X, clip_center_z)
    clip = clip.cut(_cyl_y(inner_d, CLIP_LENGTH + 2.0, CLIP_X, clip_center_z))
    clip = clip.cut(
        bd.Box(CLIP_SLOT, CLIP_LENGTH + 4.0, outer_d).moved(
            bd.Location(
                (
                    CLIP_X,
                    0.0,
                    clip_center_z + outer_d / 2.0,
                )
            )
        )
    )
    part = base.fuse(clip)
    part = part.cut(
        bd.Cylinder(MOUNT_D / 2.0, BASE_T + 2.0).moved(
            bd.Location((MOUNT_X, 0.0, BASE_T / 2.0))
        )
    )
    part.label = "hose_8mm_snap_clip"
    return part


if __name__ == "__main__":
    result = gen_step()
    bbox = result.bounding_box()
    size = bbox.max - bbox.min
    print(f"bbox: {size.X:.2f} x {size.Y:.2f} x {size.Z:.2f} mm")
    assert len(result.solids()) == 1
    assert (HOSE_OD + 2.0 * HOSE_CLEARANCE) > HOSE_OD
