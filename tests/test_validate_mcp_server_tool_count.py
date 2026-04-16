"""Tests for validate_mcp_server.py introspected tool count functionality."""

import subprocess
import sys
from pathlib import Path


def test_tool_definitions_count_matches_server_source() -> None:
    """Verify avatar_mcp_tool_definitions returns the expected tool count."""
    from avatar.mcp_server import avatar_mcp_tool_definitions
    tools = avatar_mcp_tool_definitions()
    names = {t.name for t in tools}
    assert len(names) == len(tools), "Tool names should be unique"
    assert len(tools) == 26, f"Expected 26 tools, got {len(tools)}"


def test_validate_script_accepts_expected_count() -> None:
    """Verify validate_mcp_server.py accepts --expected-count argument."""
    script = Path("scripts/validate_mcp_server.py")
    proc = subprocess.run(
        [sys.executable, str(script), "--expected-count", "26"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Script failed: {proc.stdout + proc.stderr}"
