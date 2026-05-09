from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.guardian_async import SafetyAction
from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig


@pytest.mark.asyncio
async def test_guardian_rtl_callback_calls_return_to_launch():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    drone = MagicMock()
    drone.action.return_to_launch = AsyncMock()
    server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await server._handle_guardian_failsafe(SafetyAction.RTL, "network_loss")

    drone.action.return_to_launch.assert_awaited_once()


@pytest.mark.asyncio
async def test_guardian_land_callback_calls_land():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    drone = MagicMock()
    drone.action.land = AsyncMock()
    server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await server._handle_guardian_failsafe(SafetyAction.LAND, "critical_battery")

    drone.action.land.assert_awaited_once()


@pytest.mark.asyncio
async def test_guardian_hold_callback_calls_hold():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    drone = MagicMock()
    drone.action.hold = AsyncMock()
    server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await server._handle_guardian_failsafe(SafetyAction.HOLD, "offboard_timeout")

    drone.action.hold.assert_awaited_once()
