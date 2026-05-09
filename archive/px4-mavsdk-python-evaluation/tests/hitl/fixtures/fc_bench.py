"""FC Bench fixture - SIH-on-FC (USB) topology.

This fixture provides MAVSDK connection string for Software-In-Hardware
mode on a bench Flight Controller connected via USB.

REQUIREMENTS:
- SYS_HITL=2 must be set on the Flight Controller per PX4 SIH-on-FC docs
- USB cable connecting FC to host machine
- /dev/pixhawk symlink or /dev/ttyUSB* device present
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def fc_bench_mavsdk_uri(serial_device: str, hitl_target: str) -> str:
    """Return MAVSDK URI for SIH-on-FC bench connection.

    Args:
        serial_device: Path to serial device (e.g., /dev/pixhawk)
        hitl_target: Must be 'fc_bench'

    Returns:
        MAVSDK serial:// URI string

    Skips if target is not fc_bench.
    """
    if hitl_target != "fc_bench":
        pytest.skip(f"fc_bench fixture requires AVATAR_HITL_TARGET=fc_bench, got {hitl_target!r}")

    # PX4 SIH-on-FC: SYS_HITL=2 -- MAVSDK over USB serial
    baud = int(os.environ.get("AVATAR_FC_SERIAL_BAUD", "921600"))
    return f"serial://{serial_device}:{baud}"
