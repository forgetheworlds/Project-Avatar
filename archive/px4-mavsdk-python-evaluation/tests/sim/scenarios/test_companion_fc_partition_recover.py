"""W2b: NetworkPartitionDriver - companion<->FC partition with reconnect."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_companion_fc_partition_recover_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "companion_fc_partition_recover"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*companion_fc_partition_recover*.tar.gz"))
    assert art
