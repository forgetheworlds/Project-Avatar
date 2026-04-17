"""Geofence-adjacent goto - expect Guardian rejection + PX4 GF defense-in-depth."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_geofence_adjacent_goto_reject_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "geofence_adjacent_goto_reject"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*geofence_adjacent_goto_reject*.tar.gz"))
    assert art
