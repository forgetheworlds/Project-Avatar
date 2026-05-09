import pytest

from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig


def test_config_from_env_disables_connect_on_start(monkeypatch):
    monkeypatch.setenv("AVATAR_CONNECT_ON_START", "0")
    monkeypatch.setenv("AVATAR_SYSTEM_ADDRESS", "udp://:14541")

    config = AvatarMCPServerConfig.from_env()

    assert config.connect_on_start is False
    assert config.system_address == "udp://:14541"


@pytest.mark.asyncio
async def test_initialize_offline_mode_does_not_connect(monkeypatch):
    monkeypatch.setenv("AVATAR_CONNECT_ON_START", "0")
    server = AvatarMCPServer(AvatarMCPServerConfig.from_env())

    async def fail_connect(*args, **kwargs):
        raise AssertionError("connect must not be called in offline mode")

    monkeypatch.setattr(server.connection_manager, "connect", fail_connect)

    initialized = await server.initialize()

    assert initialized is True
    status = server.get_status()
    assert status["initialized"] is True
    assert status["connection"]["mode"] == "offline"
