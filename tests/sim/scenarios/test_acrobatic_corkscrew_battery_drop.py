"""W2b: BatteryDrainDriver - acrobatic corkscrew with mid-maneuver battery drop."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_acrobatic_corkscrew_battery_drop_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "acrobatic_corkscrew_battery_drop"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*acrobatic_corkscrew_battery_drop*.tar.gz"))
    assert art
