"""Flight-recorder JSONL replay - regression diff vs live run."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_flight_recorder_replay_diff_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "flight_recorder_replay_diff"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*flight_recorder_replay_diff*.tar.gz"))
    assert art
