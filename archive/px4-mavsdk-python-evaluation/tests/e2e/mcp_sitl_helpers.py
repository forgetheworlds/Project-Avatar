"""Helpers for MCP-over-stdio SITL scenario tests."""

from __future__ import annotations

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Any, Optional

import pytest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


ROOT = Path(__file__).resolve().parents[2]


def require_mcp_sitl(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--run-sitl"):
        pytest.skip("requires PX4 SITL running; use --run-sitl")
    if ClientSession is None:
        pytest.skip("mcp SDK is not installed")


def mcp_server_params() -> Any:
    env = os.environ.copy()
    env["AVATAR_CONNECT_ON_START"] = "1"
    env["AVATAR_SYSTEM_ADDRESS"] = os.getenv("SITL_URL", "udp://:14540")
    env.setdefault("AVATAR_ENABLE_AUTO_FAILSAFE", "0")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "avatar.mcp_server"],
        cwd=str(ROOT),
        env=env,
    )


async def call_tool_json(session: Any, name: str, args: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    result = await session.call_tool(name, args or {})
    assert result.content, f"{name} returned no content"

    text = getattr(result.content[0], "text", None)
    assert text, f"{name} returned non-text content"

    return json.loads(text)


async def run_mcp_sitl_sequence(calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    params = mcp_server_params()
    responses: list[dict[str, Any]] = []
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for name, args in calls:
                if name == "__sleep__":
                    await asyncio.sleep(float(args.get("seconds", 1.0)))
                    responses.append({"success": True, "slept_s": args.get("seconds", 1.0)})
                    continue
                responses.append(await call_tool_json(session, name, args))
    return responses
