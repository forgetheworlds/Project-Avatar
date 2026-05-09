import json
from unittest.mock import AsyncMock

import pytest

from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig


@pytest.mark.asyncio
async def test_route_tool_uses_server_owned_flight_tools_for_takeoff():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    server.flight_tools.arm_and_takeoff = AsyncMock(
        return_value={"success": True, "altitude_m": 7.0}
    )

    raw = await server._route_tool("arm_and_takeoff", {"altitude_m": 7.0})

    assert json.loads(raw) == {"success": True, "altitude_m": 7.0}
    server.flight_tools.arm_and_takeoff.assert_awaited_once_with(7.0)


@pytest.mark.asyncio
async def test_route_tool_uses_server_owned_flight_tools_for_motion_commands():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    server.flight_tools.fly_body_offset = AsyncMock(
        return_value={"success": True, "command": "offset"}
    )
    server.flight_tools.set_velocity = AsyncMock(
        return_value={"success": True, "command": "velocity"}
    )
    server.flight_tools.hold = AsyncMock(
        return_value={"success": True, "command": "hold"}
    )

    offset_raw = await server._route_tool("fly_body_offset", {"forward_m": 2.0})
    velocity_raw = await server._route_tool(
        "set_velocity", {"north_m_s": 1.0, "duration_s": 0.2}
    )
    hold_raw = await server._route_tool("hold", {"duration_s": 1.0})

    assert json.loads(offset_raw)["command"] == "offset"
    assert json.loads(velocity_raw)["command"] == "velocity"
    assert json.loads(hold_raw)["command"] == "hold"
    server.flight_tools.fly_body_offset.assert_awaited_once()
    server.flight_tools.set_velocity.assert_awaited_once()
    server.flight_tools.hold.assert_awaited_once()
