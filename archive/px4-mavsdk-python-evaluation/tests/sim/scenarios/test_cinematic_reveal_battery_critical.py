"""W2b: BatteryDrainDriver - cinematic reveal with battery critical."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_cinematic_reveal_battery_critical_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "cinematic_reveal_battery_critical"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*cinematic_reveal_battery_critical*.tar.gz"))
    assert art
