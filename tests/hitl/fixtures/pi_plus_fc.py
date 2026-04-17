"""Pi + FC fixture - Laptop to Pi to FC UART topology.

This fixture provides MAVSDK connection string for the Pi + FC topology
where the MCP host (laptop) connects via UDP to a Raspberry Pi running
mavsdk_server, which in turn connects to the FC via UART.

REQUIREMENTS:
- Raspberry Pi on same network, reachable via SSH
- mavsdk_server running on Pi, bridging to FC UART
- AVATAR_PI_HOST environment variable set (defaults to avatar.local)
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest


def _pi_host() -> str:
    """Return Pi hostname from environment."""
    return os.environ.get("AVATAR_PI_HOST", "avatar.local")


@pytest.fixture(scope="session")
def pi_plus_fc_mavsdk_uri(hitl_target: str) -> str:
    """Return MAVSDK URI for Pi + FC topology.

    Verifies Pi reachability via SSH before returning the UDP URI.

    Args:
        hitl_target: Must be 'pi_plus_fc'

    Returns:
        MAVSDK UDP URI string (e.g., udp://:14540)

    Skips if:
        - target is not pi_plus_fc
        - ssh not installed
        - Pi not reachable via SSH
    """
    if hitl_target != "pi_plus_fc":
        pytest.skip(
            f"pi_plus_fc fixture requires AVATAR_HITL_TARGET=pi_plus_fc, got {hitl_target!r}"
        )

    if shutil.which("ssh") is None:
        pytest.skip("ssh not installed; cannot verify Pi reachability")

    host = _pi_host()
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", f"pi@{host}", "true"],
        capture_output=True,
        text=True,
    )

    if r.returncode != 0:
        pytest.skip(f"Pi not reachable via SSH pi@{host}: {r.stderr.strip() or r.stdout.strip()}")

    udp = os.environ.get("AVATAR_PI_MAVSDK_UDP", "udp://:14540")
    return udp
