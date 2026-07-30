"""Printable 2.5 mm water-cannon nozzle insert."""

from nozzle_insert import gen_insert


def gen_step():
    return gen_insert(2.5)


if __name__ == "__main__":
    assert len(gen_step().solids()) == 1
