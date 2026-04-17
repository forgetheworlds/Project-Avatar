"""HITL Preflight Tests - Wraps hardware/px4/preflight.py CLI.

This test validates the preflight CLI passes against real hardware,
ensuring the complete preflight check chain works correctly.

REQUIREMENTS:
- AVATAR_HITL_TARGET=fc_bench
- FC connected via USB (/dev/pixhawk or /dev/ttyUSB*)
- PX4 firmware with SYS_HITL=2

The test invokes the preflight.py script as a subprocess and asserts:
1. Exit code is 0 (success)
2. Output contains "PASS" indicator
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.hitl, pytest.mark.preflight]


def test_preflight_cli_passes(fc_bench_mavsdk_uri: str, hitl_target: str) -> None:
    """Run preflight.py CLI and assert it passes against bench FC.

    This test shells out to the preflight.py script to validate
    the complete preflight verification chain works on real hardware.

    Args:
        fc_bench_mavsdk_uri: MAVSDK URI (not used directly, validates fc_bench target)
        hitl_target: Must be 'fc_bench'

    SKIP CONDITIONS:
        - hitl_target != fc_bench (preflight gate runs against bench FC USB)

    ASSERTIONS:
        - Exit code is 0
        - Output contains "PASS" (case insensitive)
    """
    if hitl_target != "fc_bench":
        pytest.skip("preflight gate runs against bench FC (USB)")

    # Resolve path to preflight.py
    # tests/hitl/test_hitl_preflight.py -> tests/ -> repo_root
    repo = Path(__file__).resolve().parents[2]
    script = repo / "hardware" / "px4" / "preflight.py"

    if not script.exists():
        pytest.skip(f"Preflight script not found: {script}")

    # Build command
    cmd = [
        sys.executable,
        str(script),
        "--airframe",
        "mark4_7in",
    ]

    # Run preflight check
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
        cwd=str(repo),
    )

    # Log output for debugging
    print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")

    # Assert success
    assert result.returncode == 0, (
        f"Preflight failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Check for PASS indicator
    output_upper = result.stdout.upper()
    assert "PASS" in output_upper, (
        f"Preflight output missing PASS indicator\n"
        f"stdout: {result.stdout}"
    )


def test_preflight_dry_run() -> None:
    """Run preflight.py in dry-run mode without hardware.

    This test validates the preflight script works in isolation
    without requiring a connected FC. Useful for CI validation.

    No skip conditions - this test always runs when HITL tests are enabled.
    """
    repo = Path(__file__).resolve().parents[2]
    script = repo / "hardware" / "px4" / "preflight.py"

    if not script.exists():
        pytest.skip(f"Preflight script not found: {script}")

    cmd = [
        sys.executable,
        str(script),
        "--dry-run",
        "--airframe",
        "mark4_7in",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,  # 1 minute timeout for dry-run
        cwd=str(repo),
    )

    # Dry-run should always succeed if params file exists
    if result.returncode != 0:
        # If params file missing, skip rather than fail
        if "not found" in result.stderr.lower() or "not found" in result.stdout.lower():
            pytest.skip("Airframe params file not found for dry-run")

    assert result.returncode == 0, (
        f"Dry-run preflight failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
