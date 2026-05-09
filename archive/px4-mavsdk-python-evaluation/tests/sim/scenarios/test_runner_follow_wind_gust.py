"""W2b: WindDriver - runner-follow with sustained wind gust."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_runner_follow_wind_gust_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "runner_follow_wind_gust"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*runner_follow_wind_gust*.tar.gz"))
    assert art
