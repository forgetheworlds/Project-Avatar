"""Tests for validate_mcp_server.py introspected tool count functionality."""

import subprocess
import sys
from pathlib import Path

# Post–Wave-2b registered tool names (see docs/.../first-flight-plan-design.md §6.8).
# Paper rollup is 58; this repository registers one additional MCP tool name
# (granular W2a surface). Keep in sync with LISTED_TOOL_NAMES in server.py.
EXPECTED_TOOL_COUNT = 59


def test_tool_definitions_count_matches_server_source() -> None:
    """Verify avatar_mcp_tool_definitions returns the expected tool count."""
    from avatar.mcp_server.server import avatar_mcp_tool_definitions

    tools = avatar_mcp_tool_definitions()
    names = {t.name for t in tools}
    assert len(names) == len(tools), "Tool names should be unique"
    assert len(tools) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(tools)}"
    )


def test_validate_script_accepts_expected_count() -> None:
    """Verify validate_mcp_server.py accepts --expected-count argument."""
    script = Path("scripts/validate_mcp_server.py")
    proc = subprocess.run(
        [sys.executable, str(script), "--expected-count", str(EXPECTED_TOOL_COUNT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Script failed: {proc.stdout + proc.stderr}"
