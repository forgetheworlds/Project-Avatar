"""HITL pytest configuration - options, markers, skips, and device discovery.

This conftest implements the HITL test harness gates per Wave 4 spec:
- --run-hitl flag to enable HITL tests
- hitl and preflight markers for categorization
- Device discovery for /dev/pixhawk or /dev/ttyUSB*
- Session fixtures for fc_bench and pi_plus_fc topologies
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
from pathlib import Path
from typing import Any

import pytest

# Import fixtures from subdirectory to make them available to all HITL tests
# These fixtures are used by tests via request.getfixturevalue() or direct injection
# Using relative imports to work with pytest's path resolution
from tests.hitl.fixtures import fc_bench, pi_plus_fc

# Re-export fixtures for pytest discovery
fc_bench_mavsdk_uri = fc_bench.fc_bench_mavsdk_uri
pi_plus_fc_mavsdk_uri = pi_plus_fc.pi_plus_fc_mavsdk_uri

logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-hitl command line option."""
    parser.addoption(
        "--run-hitl",
        action="store_true",
        default=False,
        help="Enable hardware HITL tests (requires FC and/or Pi)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure hitl and preflight markers."""
    config.addinivalue_line("markers", "hitl: gated hardware-in-the-loop tests")
    config.addinivalue_line("markers", "preflight: HITL preflight gate subset (W4)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip hitl tests unless --run-hitl flag is provided."""
    if config.getoption("--run-hitl"):
        return
    skip_if = pytest.mark.skip(reason="HITL gate not enabled (pass --run-hitl)")
    for item in items:
        if item.get_closest_marker("hitl"):
            item.add_marker(skip_if)


def discover_serial_device() -> str | None:
    """Return first responsive serial device path, or None."""
    candidates: list[Path] = []
    pix = Path("/dev/pixhawk")
    if pix.exists():
        candidates.append(pix)
    candidates.extend(sorted(Path(p) for p in glob.glob("/dev/ttyUSB*")))
    for p in candidates:
        if p.is_char_device():
            return str(p)
    return None


@pytest.fixture(scope="session")
def hitl_target(request: pytest.FixtureRequest) -> str:
    """Return the HITL target topology from environment.

    Expects AVATAR_HITL_TARGET to be set to 'fc_bench' or 'pi_plus_fc'.

    Skips if not set or invalid.
    """
    if not request.config.getoption("--run-hitl"):
        pytest.skip("HITL gate not enabled (pass --run-hitl)")
    target = os.environ.get("AVATAR_HITL_TARGET")
    if not target:
        pytest.skip("AVATAR_HITL_TARGET unset (expected fc_bench or pi_plus_fc)")
    if target not in ("fc_bench", "pi_plus_fc"):
        pytest.skip(f"AVATAR_HITL_TARGET={target!r} invalid (expected fc_bench or pi_plus_fc)")
    return target


@pytest.fixture(scope="session")
def serial_device(hitl_target: str) -> str:
    """Return serial device path for bench FC connection.

    Skips if no device found and target is fc_bench.
    """
    dev = discover_serial_device()
    if hitl_target == "fc_bench" and dev is None:
        pytest.skip("HITL target fc_bench not found (/dev/pixhawk missing)")
    if dev is None:
        pytest.skip("No serial device found (/dev/pixhawk and /dev/ttyUSB* absent)")
    return dev


@pytest.fixture
def hitl_mavsdk_uri(request: pytest.FixtureRequest, hitl_target: str) -> str:
    """Return MAVSDK URI appropriate for the HITL target.

    Dispatches to fc_bench_mavsdk_uri or pi_plus_fc_mavsdk_uri based on target.
    """
    if hitl_target == "fc_bench":
        return request.getfixturevalue("fc_bench_mavsdk_uri")
    return request.getfixturevalue("pi_plus_fc_mavsdk_uri")


@pytest.fixture
async def hitl_fc_drone(fc_bench_mavsdk_uri: str, hitl_target: str):
    """Live MAVSDK System on bench FC (USB).

    Requires AVATAR_HITL_TARGET=fc_bench and SYS_HITL=2 on FC.

    Yields connected drone, ensures disarm on cleanup.
    """
    if hitl_target != "fc_bench":
        pytest.skip("hitl_fc_drone requires AVATAR_HITL_TARGET=fc_bench")
    try:
        from mavsdk import System
    except ImportError:
        pytest.skip("MAVSDK not installed")

    drone = System()
    logger.info(f"Connecting to HITL FC at {fc_bench_mavsdk_uri}")
    await drone.connect(system_address=fc_bench_mavsdk_uri)

    connected = False
    async for state in drone.core.connection_state():
        connected = state.is_connected
        logger.info("HITL FC connection_state: connected=%s uuid=%s", state.is_connected, state.uuid)
        break

    if not connected:
        pytest.skip("Could not connect to FC over serial (check cable, SYS_HITL=2, USB permissions)")

    try:
        yield drone
    finally:
        try:
            await drone.action.disarm()
        except Exception:
            pass
