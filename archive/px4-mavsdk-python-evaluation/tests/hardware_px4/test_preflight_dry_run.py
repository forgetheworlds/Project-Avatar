"""Tests for PX4 preflight verification CLI.

This test validates:
1. preflight.py --dry-run exits with code 0 on success
2. Output contains "PASS" status
3. JSON output is valid and parseable
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PREFLIGHT_SCRIPT = PROJECT_ROOT / "hardware" / "px4" / "preflight.py"


class TestPreflightDryRun:
    """Test preflight.py --dry-run functionality."""

    def test_preflight_script_exists(self) -> None:
        """The preflight.py script must exist."""
        assert PREFLIGHT_SCRIPT.exists(), f"Script not found: {PREFLIGHT_SCRIPT}"

    def test_dry_run_mark4_exits_zero(self) -> None:
        """preflight.py --dry-run --airframe mark4_7in should exit 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "mark4_7in",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_dry_run_output_contains_pass(self) -> None:
        """preflight.py output should contain 'PASS' status."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "mark4_7in",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Output should contain PASS
        assert "PASS" in result.stdout or '"status":"PASS"' in result.stdout, (
            f"Output should contain PASS status:\n{result.stdout}"
        )

    def test_dry_run_x500_exits_zero(self) -> None:
        """preflight.py --dry-run --airframe x500_v2 should exit 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "x500_v2",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_invalid_airframe_fails(self) -> None:
        """Invalid airframe should exit non-zero."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "nonexistent_airframe",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode != 0, (
            "Should fail with nonexistent airframe"
        )


class TestPreflightJSONOutput:
    """Test --json output format."""

    def test_json_output_is_valid(self) -> None:
        """preflight.py --json should output valid JSON."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "mark4_7in",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should exit 0
        assert result.returncode == 0

        # Output should be valid JSON
        # There may be debug output, find the JSON line
        lines = result.stdout.strip().split("\n")
        json_line = None
        for line in lines:
            if line.startswith("{"):
                json_line = line
                break

        assert json_line is not None, f"No JSON found in output: {result.stdout}"

        # Parse JSON
        data = json.loads(json_line)

        # Validate required fields
        assert "status" in data
        assert "mode" in data
        assert "airframe" in data
        assert data["status"] == "PASS"
        assert data["mode"] == "dry_run"
        assert data["airframe"] == "mark4_7in"

    def test_json_contains_required_fields(self) -> None:
        """JSON output should contain all required fields."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "mark4_7in",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Find JSON line
        lines = result.stdout.strip().split("\n")
        json_line = next((l for l in lines if l.startswith("{")), None)
        assert json_line is not None

        data = json.loads(json_line)

        required_fields = [
            "status",
            "mode",
            "airframe",
            "params_file",
            "total_params",
            "valid_params",
            "invalid_params",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_json_missing_required_list(self) -> None:
        """JSON should include missing_required list."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
                "--airframe",
                "mark4_7in",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        lines = result.stdout.strip().split("\n")
        json_line = next((l for l in lines if l.startswith("{")), None)
        assert json_line is not None

        data = json.loads(json_line)

        assert "missing_required" in data
        assert isinstance(data["missing_required"], list)


class TestPreflightCLIArgs:
    """Test CLI argument handling."""

    def test_missing_airframe_exits_2(self) -> None:
        """Missing --airframe should exit with code 2."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # argparse exits with 2 for missing required args
        assert result.returncode == 2

    def test_help_exits_zero(self) -> None:
        """--help should exit 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_SCRIPT),
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "airframe" in result.stdout.lower()


class TestPreflightIntegration:
    """Integration tests for preflight verification."""

    def test_verify_dry_run_mark4(self) -> None:
        """Direct call to verify_dry_run for mark4_7in."""
        # Add project root to path
        sys.path.insert(0, str(PROJECT_ROOT))

        from hardware.px4.preflight import verify_dry_run
        from pathlib import Path

        airframes_dir = PROJECT_ROOT / "hardware" / "px4" / "airframes"

        result = verify_dry_run("mark4_7in", airframes_dir)

        assert result.status == "PASS"
        assert result.mode == "dry_run"
        assert result.airframe == "mark4_7in"
        assert result.total_params > 0

    def test_verify_dry_run_x500(self) -> None:
        """Direct call to verify_dry_run for x500_v2."""
        sys.path.insert(0, str(PROJECT_ROOT))

        from hardware.px4.preflight import verify_dry_run

        airframes_dir = PROJECT_ROOT / "hardware" / "px4" / "airframes"

        result = verify_dry_run("x500_v2", airframes_dir)

        assert result.status == "PASS"
        assert result.mode == "dry_run"
        assert result.airframe == "x500_v2"
