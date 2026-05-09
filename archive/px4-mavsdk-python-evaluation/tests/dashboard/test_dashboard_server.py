"""Tests for the local React telemetry dashboard server."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from pathlib import Path

from avatar.dashboard.server import (
    DashboardAgentBridge,
    DashboardCameraSource,
    DashboardTelemetrySource,
    DashboardTerminalSession,
    MCP_CONFIG_PATH,
    AGENT_SKILL_PATH,
    _default_terminal_command,
    _load_agent_skill_prompt,
    make_handler,
)


def _test_terminal() -> DashboardTerminalSession:
    return DashboardTerminalSession(
        cwd=Path.cwd(),
        command=["/bin/sh"],
        auto_prompt=False,
    )


def test_demo_snapshot_has_required_map_fields() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)

    snapshot = json.loads(source.snapshot().to_json())

    assert snapshot["source"] == "demo"
    assert isinstance(snapshot["lat"], float)
    assert isinstance(snapshot["lon"], float)
    assert "battery_pct" in snapshot
    assert "safety_state" in snapshot


def test_dashboard_serves_index_and_telemetry_json() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/")
        response = conn.getresponse()
        html = response.read().decode("utf-8")
        assert response.status == 200
        assert "Project Avatar Flight Console" in html

        conn.request("GET", "/api/telemetry")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["source"] == "demo"
        assert payload["mode"] == "DEMO_ORBIT"
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_demo_camera_frame_is_served() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    camera = DashboardCameraSource()
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, camera, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/camera.jpg")
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        assert response.status == 200
        assert response.getheader("Content-Type") == "image/svg+xml"
        assert "CAMERA DEMO FEED" in body
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_demo_camera_stream_starts_multipart_response() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    camera = DashboardCameraSource()
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, camera, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/camera/stream")
        response = conn.getresponse()
        chunk = response.read(160)
        assert response.status == 200
        assert response.getheader("Content-Type").startswith("multipart/x-mixed-replace")
        assert b"avatar-camera-frame" in chunk
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_camera_status_reports_configured_simulation_source(monkeypatch) -> None:
    monkeypatch.setenv("AVATAR_SIM_CAMERA_URL", "http://127.0.0.1:9999/frame.jpg")
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    camera = DashboardCameraSource(camera_url="http://127.0.0.1:9999/frame.jpg")
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, camera, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/api/camera/status")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["source"] == "simulation"
        assert payload["url_configured"] is True
        assert payload["stream_path"] == "/camera/stream"
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_agent_message_endpoint_queues_messages() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    terminal = _test_terminal()
    agent = DashboardAgentBridge(terminal=terminal)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, agent=agent, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        body = json.dumps({
            "text": "circle this target and keep tracking it",
            "annotation": {"x": 42, "y": 51, "r": 12},
        })
        conn.request("POST", "/api/agent/message", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["accepted"] is True
        assert payload["forwarded"] is True
        assert payload["message"]["annotation"]["x"] == 42
        assert payload["terminal"]["status"] == "sent_to_terminal"

        conn.request("GET", "/api/agent/messages")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert len(payload["messages"]) == 1
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_terminal_input_endpoint_writes_to_pty() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        body = json.dumps({"data": "printf DASHBOARD_PTY_OK\\n\n"})
        conn.request("POST", "/api/terminal/input", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["accepted"] is True

        output = ""
        deadline_chunks = 0
        while "DASHBOARD_PTY_OK" not in output and deadline_chunks < 10:
            chunks = terminal.wait_for_chunks(0, timeout_s=0.5)
            output = "".join(chunk for _, chunk in chunks)
            deadline_chunks += 1
        assert "DASHBOARD_PTY_OK" in output
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_terminal_control_endpoints_resize_stop_and_restart() -> None:
    source = DashboardTelemetrySource(system_address="udp://:14540", demo=True)
    terminal = _test_terminal()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(source, terminal=terminal))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        conn = HTTPConnection(host, port, timeout=2)
        conn.request(
            "POST",
            "/api/terminal/resize",
            body=json.dumps({"rows": 18, "cols": 72}),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"]["rows"] == 18
        assert payload["status"]["cols"] == 72

        conn.close()
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("POST", "/api/terminal/stop", body="{}", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["accepted"] is True

        conn.close()
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("POST", "/api/terminal/restart", body="{}", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"]["running"] is True
    finally:
        server.shutdown()
        server.server_close()
        terminal.stop()
        thread.join(timeout=2)


def test_avatar_agent_skill_and_mcp_config_are_deployable() -> None:
    skill = AGENT_SKILL_PATH.read_text(encoding="utf-8")
    config = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    prompt = _load_agent_skill_prompt()

    assert "name: avatar-drone-mcp" in skill
    assert "Safety first" in skill
    assert "Camera Annotations" in skill
    assert "avatar-flight-operations" in prompt
    assert "avatar-vision-targeting" in prompt
    assert "avatar-sitl-scenarios" in prompt
    assert "google-ai-mode-skill" in prompt
    assert "Never bypass Guardian" in prompt
    assert "Target Lock Flow" in prompt
    assert "avatar/dashboard/claude_mcp_config.json" in prompt
    assert ".venv/bin/python -m avatar.mcp_server" in prompt
    assert "/Users/muadhsambul/.agents/skills/google-ai-mode" in prompt
    assert "avatar-drone" in config["mcpServers"]
    assert config["mcpServers"]["avatar-drone"]["args"] == ["-m", "avatar.mcp_server"]


def test_default_claude_command_is_isolated_and_bypasses_permissions() -> None:
    command = _default_terminal_command()
    if "claude" not in Path(command[0]).name:
        return

    assert "--bare" in command
    assert "--disable-slash-commands" in command
    assert "--strict-mcp-config" in command
    assert "--dangerously-skip-permissions" in command
    assert str(MCP_CONFIG_PATH) in command
