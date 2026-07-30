"""Flush cap for the bow's 10 mm foam-fill/service opening."""

import build123d as bd

STEM_D = 9.6
STEM_L = 8.0
FLANGE_D = 15.0
FLANGE_T = 2.2


def gen_step():
    stem = bd.Cylinder(
        STEM_D / 2.0,
        STEM_L,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX),
    )
    flange = bd.Cylinder(
        FLANGE_D / 2.0,
        FLANGE_T,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    part = stem.fuse(flange)
    part.label = "bow_foam_port_plug"
    assert len(part.solids()) == 1
    return part
