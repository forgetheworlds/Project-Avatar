"""W2b: WindDriver - sailboat follow with altitude floor constraint."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_sailboat_follow_altitude_floor_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "sailboat_follow_altitude_floor"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*sailboat_follow_altitude_floor*.tar.gz"))
    assert art
