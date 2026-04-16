from __future__ import annotations

import importlib.metadata

import avatar.main as entry


def test_version_flag(capsys: object) -> None:
    entry.main(["--version"])
    assert capsys.readouterr().out.strip() == importlib.metadata.version("drone-control-system")


def test_main_delegates_to_server_main(monkeypatch: object) -> None:
    recorded: list[str] = []

    def fake_run(coro: object) -> None:
        recorded.append(type(coro).__name__)

    monkeypatch.setattr(entry.asyncio, "run", fake_run)
    entry.main([])
    assert recorded == ["coroutine"]
