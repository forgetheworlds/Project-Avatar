"""W2b: VisionDropoutDriver - search->acquire->follow then vision loss."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_search_acquire_follow_vision_dropout_scenario(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "search_acquire_follow_vision_dropout"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art_dir = repo_root / "artifacts"
    assert art_dir.is_dir()
    tars = list(art_dir.glob("*search_acquire_follow_vision_dropout*.tar.gz"))
    assert tars, "expected scenario artifact tarball under artifacts/"
