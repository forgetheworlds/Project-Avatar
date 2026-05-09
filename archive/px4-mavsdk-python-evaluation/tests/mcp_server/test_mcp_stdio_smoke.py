import os
import sys
from pathlib import Path

import pytest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_mcp_stdio_lists_tools_in_offline_mode():
    if ClientSession is None:
        pytest.skip("mcp SDK is not installed")

    env = os.environ.copy()
    env["AVATAR_CONNECT_ON_START"] = "0"

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "avatar.mcp_server"],
        cwd=str(ROOT),
        env=env,
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()

    names = {tool.name for tool in tools.tools}
    # Check for key tools that should always be available
    assert "get_drone_status" in names, f"get_drone_status not found in {names}"
    assert "arm_and_takeoff" in names, f"arm_and_takeoff not found in {names}"
