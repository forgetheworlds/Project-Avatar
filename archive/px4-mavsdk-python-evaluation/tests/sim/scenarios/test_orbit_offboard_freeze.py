"""W2b: OffboardFreezeDriver - orbit with offboard command freeze."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_orbit_offboard_freeze_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "orbit_offboard_freeze"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*orbit_offboard_freeze*.tar.gz"))
    assert art
