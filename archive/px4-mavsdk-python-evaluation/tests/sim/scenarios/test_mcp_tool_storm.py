"""MCP tool-storm 100 cmd/s - verify no offboard timeout, guardian stable."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_mcp_tool_storm_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "mcp_tool_storm"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*mcp_tool_storm*.tar.gz"))
    assert art
