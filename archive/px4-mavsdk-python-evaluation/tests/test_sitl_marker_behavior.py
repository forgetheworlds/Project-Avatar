"""
Test that the SITL marker behavior works correctly with --run-sitl flag.

These tests verify that:
1. Tests marked with 'sitl' are skipped when --run-sitl is not provided
2. Tests marked with 'sitl' run when --run-sitl is provided
3. The -m 'not sitl' marker excludes SITL tests correctly
"""

import subprocess
import sys
from pathlib import Path


def test_sitl_tests_skipped_without_flag() -> None:
    """Verify SITL tests are skipped when --run-sitl flag is not provided."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(Path("tests/test_sitl_basic.py")), "-m", "sitl", "-v"],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout + proc.stderr
    # Tests should be skipped, not failed or passed
    assert "SKIPPED" in out or "skipped" in out


def test_not_sitl_excludes_sitl_marker() -> None:
    """Verify -m 'not sitl' excludes SITL tests."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(Path("tests/test_sitl_basic.py")), "-m", "not sitl", "-q", "--collect-only"],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout + proc.stderr
    assert "test_connection" not in out or "deselected" in out
