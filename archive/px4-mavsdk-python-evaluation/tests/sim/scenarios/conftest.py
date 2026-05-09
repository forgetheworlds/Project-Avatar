"""Scenario test gating for Docker-backed and offline scenarios."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SCENARIO_ROOT = Path(__file__).resolve().parent
_OFFLINE_SCENARIO_TESTS = {
    "test_flight_recorder_replay_diff.py",
}


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _docker_available():
        return
    skip = pytest.mark.skip(reason="Docker daemon not available (scenario test requires Docker)")
    for item in items:
        # Nested conftest receives all session items; only skip tests in this package tree.
        try:
            item.path.resolve().relative_to(_SCENARIO_ROOT)
        except ValueError:
            continue
        if item.path.name in _OFFLINE_SCENARIO_TESTS:
            continue
        item.add_marker(skip)
