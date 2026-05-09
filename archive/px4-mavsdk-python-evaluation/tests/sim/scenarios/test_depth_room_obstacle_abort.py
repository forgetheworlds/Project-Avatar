"""W2b: ObstacleProximityDriver - depth-room crawl with obstacle abort."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_depth_room_obstacle_abort_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "depth_room_obstacle_abort"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*depth_room_obstacle_abort*.tar.gz"))
    assert art
