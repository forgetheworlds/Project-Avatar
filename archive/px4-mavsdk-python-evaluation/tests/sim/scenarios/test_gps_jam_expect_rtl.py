"""W2b: GpsLossDriver - GPS denied triggers RTL per PX4 failsafe params."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_gps_jam_expect_rtl_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "gps_jam_expect_rtl"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*gps_jam_expect_rtl*.tar.gz"))
    assert art
