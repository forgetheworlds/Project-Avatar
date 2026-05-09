"""Local telemetry dashboard server.

This module intentionally uses only the Python standard library plus optional
MAVSDK. It serves a React UI and a Server-Sent Events telemetry stream at
localhost, so the dashboard can run in dev/SITL without adding a Node toolchain.
"""

from __future__ import annotations

import argparse
import asyncio
import errno
import fcntl
import json
import math
import mimetypes
import os
import pty
import select
import shlex
import shutil
import signal
import subprocess
import struct
import threading
import time
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request


STATIC_DIR = Path(__file__).with_name("static")
PROJECT_ROOT = STATIC_DIR.parents[2]
DEMO_FRAME_SIZE = (1280, 720)
DASHBOARD_DIR = STATIC_DIR.parent
AGENT_SKILL_PATH = DASHBOARD_DIR / "agent_skills" / "avatar-drone-mcp" / "SKILL.md"
MCP_CONFIG_PATH = DASHBOARD_DIR / "claude_mcp_config.json"


AGENT_BOOT_PROMPT = "You are the Project Avatar drone MCP flight agent. Use safety gates and the Avatar MCP tools."


@dataclass(slots=True)
class DashboardSnapshot:
    """Telemetry payload consumed by the local React dashboard."""

    timestamp: float
    mode: str
    connected: bool
    source: str
    lat: float
    lon: float
    alt_m: float
    rel_alt_m: float
    heading_deg: float
    battery_pct: float | None
    groundspeed_m_s: float
    armed: bool | None
    in_air: bool | None
    safety_state: str
    note: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


class DashboardTelemetrySource:
    """Produces live MAVSDK telemetry or deterministic demo telemetry."""

    def __init__(self, *, system_address: str, demo: bool = False) -> None:
        self.system_address = system_address
        self.demo = demo
        self._started_at = time.time()
        self._latest: DashboardSnapshot | None = None
        self._latest_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self.demo or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, name="avatar-dashboard-telemetry", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def snapshot(self) -> DashboardSnapshot:
        with self._latest_lock:
            latest = self._latest
        if latest is not None and time.time() - latest.timestamp < 3.0:
            return latest
        return self._demo_snapshot(note=None if self.demo else "live telemetry unavailable; showing demo track")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._mavsdk_task())
        self._loop.run_forever()

    async def _mavsdk_task(self) -> None:
        try:
            from mavsdk import System  # type: ignore
        except Exception:
            return

        drone = System()
        try:
            await drone.connect(system_address=self.system_address)
            async for state in drone.core.connection_state():
                if state.is_connected:
                    break
                await asyncio.sleep(0.25)
        except Exception:
            return

        while not self._stop.is_set():
            snapshot = await self._read_mavsdk_snapshot(drone)
            if snapshot is not None:
                with self._latest_lock:
                    self._latest = snapshot
            await asyncio.sleep(0.5)

    async def _read_mavsdk_snapshot(self, drone: Any) -> DashboardSnapshot | None:
        try:
            position = await _first(drone.telemetry.position(), timeout_s=1.0)
            battery = await _first(drone.telemetry.battery(), timeout_s=0.5)
            attitude = await _first(drone.telemetry.attitude_euler(), timeout_s=0.5)
            velocity = await _first(drone.telemetry.velocity_ned(), timeout_s=0.5)
            armed = await _first(drone.telemetry.armed(), timeout_s=0.5)
            in_air = await _first(drone.telemetry.in_air(), timeout_s=0.5)
            flight_mode = await _first(drone.telemetry.flight_mode(), timeout_s=0.5)
        except Exception:
            return None

        if position is None:
            return None

        north = float(getattr(velocity, "north_m_s", 0.0) or 0.0)
        east = float(getattr(velocity, "east_m_s", 0.0) or 0.0)
        battery_pct = getattr(battery, "remaining_percent", None)
        if battery_pct is not None and battery_pct <= 1.0:
            battery_pct *= 100.0

        return DashboardSnapshot(
            timestamp=time.time(),
            mode=str(flight_mode or "UNKNOWN"),
            connected=True,
            source="mavsdk",
            lat=float(position.latitude_deg),
            lon=float(position.longitude_deg),
            alt_m=float(position.absolute_altitude_m),
            rel_alt_m=float(getattr(position, "relative_altitude_m", 0.0) or 0.0),
            heading_deg=float(getattr(attitude, "yaw_deg", 0.0) or 0.0),
            battery_pct=None if battery_pct is None else round(float(battery_pct), 1),
            groundspeed_m_s=round(math.hypot(north, east), 2),
            armed=bool(armed) if armed is not None else None,
            in_air=bool(in_air) if in_air is not None else None,
            safety_state="nominal",
        )

    def _demo_snapshot(self, *, note: str | None = None) -> DashboardSnapshot:
        elapsed = time.time() - self._started_at
        center_lat = 47.397742
        center_lon = 8.545594
        radius = 0.00045
        angle = elapsed / 18.0
        lat = center_lat + math.sin(angle) * radius
        lon = center_lon + math.cos(angle) * radius
        heading = (math.degrees(angle) + 90.0) % 360.0
        battery = max(15.0, 96.0 - elapsed * 0.015)

        return DashboardSnapshot(
            timestamp=time.time(),
            mode="DEMO_ORBIT",
            connected=False,
            source="demo",
            lat=lat,
            lon=lon,
            alt_m=502.0,
            rel_alt_m=22.0 + math.sin(angle * 2.0),
            heading_deg=heading,
            battery_pct=round(battery, 1),
            groundspeed_m_s=4.8,
            armed=True,
            in_air=True,
            safety_state="simulated",
            note=note,
        )


class DashboardCameraSource:
    """Provides either a proxied camera frame or a generated demo frame."""

    def __init__(self, *, camera_url: str | None = None, timeout_s: float = 0.35) -> None:
        self.camera_url = camera_url
        self.timeout_s = timeout_s
        self._started_at = time.time()

    @property
    def source_name(self) -> str:
        if not self.camera_url:
            return "demo"
        if os.getenv("AVATAR_SIM_CAMERA_URL") and self.camera_url == os.getenv("AVATAR_SIM_CAMERA_URL"):
            return "simulation"
        return "camera"

    def frame(self) -> tuple[bytes, str]:
        if self.camera_url:
            try:
                req = url_request.Request(self.camera_url, headers={"User-Agent": "ProjectAvatarDashboard/1.0"})
                with url_request.urlopen(req, timeout=self.timeout_s) as response:
                    content_type = response.headers.get_content_type() or "image/jpeg"
                    return response.read(), content_type
            except (OSError, url_error.URLError, TimeoutError):
                pass
        return self._demo_frame(), "image/svg+xml"

    def _demo_frame(self) -> bytes:
        elapsed = time.time() - self._started_at
        horizon = 42 + math.sin(elapsed / 3.0) * 5
        target_x = 50 + math.cos(elapsed / 4.0) * 22
        target_y = 54 + math.sin(elapsed / 5.0) * 12
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#6f8fa4"/>
      <stop offset="1" stop-color="#d2c1a3"/>
    </linearGradient>
    <linearGradient id="ground" x1="0" x2="1">
      <stop offset="0" stop-color="#394235"/>
      <stop offset="1" stop-color="#73745d"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="{horizon * 7.2:.0f}" fill="url(#sky)"/>
  <path d="M0 {horizon * 7.2:.0f} C260 {horizon * 6.4:.0f} 510 {horizon * 8.2:.0f} 780 {horizon * 7.1:.0f} C980 {horizon * 6.2:.0f} 1120 {horizon * 6.8:.0f} 1280 {horizon * 6.4:.0f} L1280 720 L0 720 Z" fill="url(#ground)"/>
  <path d="M0 585 C250 520 510 612 780 542 C1010 486 1160 515 1280 472" fill="none" stroke="#1d2a21" stroke-width="24" opacity="0.58"/>
  <circle cx="{target_x * 12.8:.0f}" cy="{target_y * 7.2:.0f}" r="34" fill="none" stroke="#f1b84b" stroke-width="6"/>
  <text x="52" y="74" fill="#f4efe2" font-family="monospace" font-size="26">CAMERA DEMO FEED - set AVATAR_CAMERA_URL for live video</text>
  <path d="M620 360 h40 M640 340 v40" stroke="#f4efe2" stroke-width="4" opacity="0.72"/>
</svg>"""
        return svg.encode("utf-8")


class DashboardTerminalSession:
    """Runs a real local PTY and exposes it to the browser dashboard."""

    def __init__(
        self,
        *,
        cwd: Path,
        command: list[str] | None = None,
        boot_prompt: str = AGENT_BOOT_PROMPT,
        auto_prompt: bool = True,
    ) -> None:
        self.cwd = cwd
        self.command = command or _default_terminal_command()
        self.boot_prompt = boot_prompt
        self.auto_prompt = auto_prompt
        self._master_fd: int | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._chunks: list[tuple[int, str]] = []
        self._seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._started = False
        self._stopped = threading.Event()
        self._rows = 30
        self._cols = 100

    @property
    def command_label(self) -> str:
        redacted: list[str] = []
        skip_next = False
        for part in self.command:
            if skip_next:
                redacted.append("<avatar-skill-pack>")
                skip_next = False
                continue
            redacted.append(part)
            if part in {"--append-system-prompt", "--system-prompt"}:
                skip_next = True
        return " ".join(shlex.quote(part) for part in redacted)

    def start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        self._stopped.clear()
        self._started = True
        master_fd, slave_fd = pty.openpty()
        _set_pty_size(slave_fd, rows=self._rows, cols=self._cols)
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError:
            fallback = [os.environ.get("SHELL", "/bin/zsh"), "-l"]
            self._process = subprocess.Popen(
                fallback,
                cwd=self.cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                start_new_session=True,
            )
            self.command = fallback
        finally:
            os.close(slave_fd)

        self._master_fd = master_fd
        self._reader = threading.Thread(target=self._read_loop, name="avatar-dashboard-terminal", daemon=True)
        self._reader.start()
        self._append_output(
            f"\r\n[dashboard] PTY started: {self.command_label}\r\n"
            f"[dashboard] cwd: {self.cwd}\r\n"
        )
        if self.auto_prompt:
            threading.Thread(target=self._send_boot_prompt, daemon=True).start()

    def stop(self) -> None:
        self._stopped.set()
        process = self._process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        self._process = None

    def restart(self) -> None:
        self.stop()
        self._append_output("\r\n[dashboard] restarting terminal session\r\n")
        self.start()

    def resize(self, *, rows: int, cols: int) -> None:
        self._rows = max(8, min(int(rows), 80))
        self._cols = max(20, min(int(cols), 240))
        if self._master_fd is not None:
            _set_pty_size(self._master_fd, rows=self._rows, cols=self._cols)

    def write(self, data: str) -> bool:
        self.start()
        if self._master_fd is None:
            return False
        try:
            os.write(self._master_fd, data.encode("utf-8", errors="replace"))
            return True
        except OSError as exc:
            self._append_output(f"\r\n[dashboard] terminal input failed: {exc}. Use Restart to launch a new session.\r\n")
            return False

    def send_message(self, text: str, *, annotation: dict[str, Any] | None, telemetry: dict[str, Any] | None) -> dict[str, Any]:
        prompt = self._format_operator_message(text, annotation=annotation, telemetry=telemetry)
        sent = self.write(prompt + "\n")
        return {"accepted": sent, "forwarded": sent, "status": "sent_to_terminal" if sent else "terminal_unavailable", "terminal": self.command_label}

    def chunks_since(self, seq: int) -> list[tuple[int, str]]:
        with self._lock:
            return [(idx, chunk) for idx, chunk in self._chunks if idx > seq]

    def wait_for_chunks(self, seq: int, *, timeout_s: float = 15.0) -> list[tuple[int, str]]:
        deadline = time.time() + timeout_s
        with self._condition:
            while not self._stopped.is_set():
                chunks = [(idx, chunk) for idx, chunk in self._chunks if idx > seq]
                if chunks:
                    return chunks
                remaining = deadline - time.time()
                if remaining <= 0:
                    return []
                self._condition.wait(timeout=min(remaining, 1.0))
            return []

    def status(self) -> dict[str, Any]:
        process = self._process
        return {
            "started": self._started,
            "running": bool(process and process.poll() is None),
            "pid": process.pid if process else None,
            "command": self.command,
            "command_label": self.command_label,
            "cwd": str(self.cwd),
            "rows": self._rows,
            "cols": self._cols,
        }

    def _send_boot_prompt(self) -> None:
        time.sleep(1.2)
        if _looks_like_agent_command(self.command):
            self.write(self.boot_prompt.strip() + "\n")

    def _read_loop(self) -> None:
        assert self._master_fd is not None
        while not self._stopped.is_set():
            try:
                readable, _, _ = select.select([self._master_fd], [], [], 0.25)
                if not readable:
                    process = self._process
                    if process and process.poll() is not None:
                        self._append_output(f"\r\n[dashboard] terminal exited with code {process.returncode}\r\n")
                        return
                    continue
                data = os.read(self._master_fd, 8192)
                if not data:
                    return
                self._append_output(data.decode("utf-8", errors="replace"))
            except OSError as exc:
                if exc.errno in {errno.EIO, errno.EBADF}:
                    return
                self._append_output(f"\r\n[dashboard] terminal read error: {exc}\r\n")
                return

    def _append_output(self, chunk: str) -> None:
        with self._condition:
            self._seq += 1
            self._chunks.append((self._seq, chunk))
            self._chunks = self._chunks[-2000:]
            self._condition.notify_all()

    def _format_operator_message(
        self,
        text: str,
        *,
        annotation: dict[str, Any] | None,
        telemetry: dict[str, Any] | None,
    ) -> str:
        telemetry = telemetry or {}
        lines = [
            "",
            "[DASHBOARD_OPERATOR_MESSAGE]",
            f"text: {text.strip()}",
            "context:",
            f"- drone_lat_lon: {telemetry.get('lat')}, {telemetry.get('lon')}",
            f"- rel_alt_m: {telemetry.get('rel_alt_m')}",
            f"- heading_deg: {telemetry.get('heading_deg')}",
            f"- mode: {telemetry.get('mode')}",
            f"- telemetry_source: {telemetry.get('source')}",
        ]
        if annotation:
            pixel = _annotation_to_pixels(annotation)
            lines.extend([
                "camera_annotation:",
                f"- normalized_center_pct: x={annotation.get('x')}, y={annotation.get('y')}",
                f"- normalized_radius_pct: {annotation.get('r')}",
                f"- frame_pixels: {DEMO_FRAME_SIZE[0]}x{DEMO_FRAME_SIZE[1]}",
                f"- pixel_center: x={pixel['cx']}, y={pixel['cy']}",
                f"- pixel_radius: {pixel['radius']}",
                f"- bbox_pixels: left={pixel['left']}, top={pixel['top']}, right={pixel['right']}, bottom={pixel['bottom']}",
                "- operator_intent: selected visual target/region of interest in current camera frame",
            ])
        lines.extend([
            "instruction:",
            "- Treat this as operator intent. If flight movement is requested, inspect status/preflight first and use MCP tools with safety gates.",
            "[/DASHBOARD_OPERATOR_MESSAGE]",
        ])
        return "\n".join(lines)


class DashboardAgentBridge:
    """Accepts dashboard messages and optionally forwards them to an agent webhook."""

    def __init__(self, *, webhook_url: str | None = None, terminal: DashboardTerminalSession | None = None) -> None:
        self.webhook_url = webhook_url
        self.terminal = terminal
        self._messages: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = {
            "id": len(self._messages) + 1,
            "timestamp": time.time(),
            "text": str(payload.get("text", "")).strip(),
            "annotation": payload.get("annotation"),
            "telemetry": payload.get("telemetry"),
            "source": "dashboard",
        }
        with self._lock:
            self._messages.append(message)
            self._messages = self._messages[-100:]

        forwarded = False
        terminal_result: dict[str, Any] | None = None
        error: str | None = None
        if self.terminal:
            terminal_result = self.terminal.send_message(
                message["text"],
                annotation=message["annotation"],
                telemetry=message["telemetry"],
            )
            forwarded = True
        if self.webhook_url:
            try:
                body = json.dumps(message).encode("utf-8")
                req = url_request.Request(
                    self.webhook_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with url_request.urlopen(req, timeout=3.0):
                    forwarded = True
            except (OSError, url_error.URLError, TimeoutError) as exc:
                error = str(exc)

        return {
            "accepted": True,
            "forwarded": forwarded,
            "message": message,
            "status": "sent_to_terminal" if terminal_result else ("forwarded" if forwarded else "queued"),
            "terminal": terminal_result,
            "note": None if forwarded else "No terminal or AVATAR_AGENT_WEBHOOK_URL configured; message queued locally.",
            "error": error,
        }

    def recent(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._messages)


async def _first(stream: Any, *, timeout_s: float) -> Any:
    async def read_one() -> Any:
        async for item in stream:
            return item
        return None

    return await asyncio.wait_for(read_one(), timeout=timeout_s)


def _default_terminal_command() -> list[str]:
    claude = shutil.which("claude")
    if claude:
        return [
            claude,
            "--bare",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--dangerously-skip-permissions",
            "--mcp-config",
            str(MCP_CONFIG_PATH),
            "--append-system-prompt",
            _load_agent_skill_prompt(),
            "--name",
            "Project Avatar Flight Deck",
        ]
    shell = os.environ.get("SHELL", "/bin/zsh")
    return [shell, "-l"]


def _looks_like_agent_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    return executable in {"codex"}


def _load_agent_skill_prompt() -> str:
    skill_root = AGENT_SKILL_PATH.parents[1]
    skill_files = sorted(skill_root.glob("*/SKILL.md"))
    if not skill_files:
        return AGENT_BOOT_PROMPT
    parts = [
        "Project Avatar dashboard agent skill pack. Follow these instructions as session-level operating guidance."
    ]
    for path in skill_files:
        parts.append(f"\n--- BEGIN {path.parent.name} ---\n{path.read_text(encoding='utf-8').strip()}\n--- END {path.parent.name} ---")
    return "\n".join(parts)


def _set_pty_size(fd: int, *, rows: int, cols: int) -> None:
    try:
        fcntl.ioctl(fd, termios_tiocswinsz(), struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def termios_tiocswinsz() -> int:
    import termios

    return termios.TIOCSWINSZ


def _annotation_to_pixels(annotation: dict[str, Any]) -> dict[str, int]:
    width, height = DEMO_FRAME_SIZE
    x_pct = float(annotation.get("x", 0.0))
    y_pct = float(annotation.get("y", 0.0))
    radius_pct = float(annotation.get("r", 0.0))
    cx = round(width * x_pct / 100.0)
    cy = round(height * y_pct / 100.0)
    radius = round(min(width, height) * radius_pct / 100.0)
    return {
        "cx": cx,
        "cy": cy,
        "radius": radius,
        "left": max(0, cx - radius),
        "top": max(0, cy - radius),
        "right": min(width, cx + radius),
        "bottom": min(height, cy + radius),
    }


def make_handler(
    source: DashboardTelemetrySource,
    camera: DashboardCameraSource | None = None,
    agent: DashboardAgentBridge | None = None,
    terminal: DashboardTerminalSession | None = None,
) -> type[BaseHTTPRequestHandler]:
    camera = camera or DashboardCameraSource()
    terminal = terminal or DashboardTerminalSession(cwd=PROJECT_ROOT)
    agent = agent or DashboardAgentBridge(terminal=terminal)
    terminal.start()

    class DashboardHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except ConnectionResetError:
                return

        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
                return
            if self.path == "/app.jsx":
                self._send_file(STATIC_DIR / "app.jsx", "text/javascript; charset=utf-8")
                return
            if self.path == "/styles.css":
                self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
                return
            if self.path == "/api/telemetry":
                self._send_json(source.snapshot().to_json())
                return
            if self.path == "/api/agent/messages":
                self._send_json(json.dumps({"messages": agent.recent()}))
                return
            if self.path == "/api/terminal/status":
                self._send_json(json.dumps(terminal.status()))
                return
            if self.path == "/api/camera/status":
                self._send_json(json.dumps({
                    "source": camera.source_name,
                    "url_configured": bool(camera.camera_url),
                    "stream_path": "/camera/stream",
                    "frame_path": "/camera.jpg",
                }))
                return
            if self.path.startswith("/terminal/events"):
                self._send_terminal_events()
                return
            if self.path.startswith("/camera.jpg"):
                self._send_camera_frame()
                return
            if self.path.startswith("/camera/stream"):
                self._send_camera_stream()
                return
            if self.path == "/events":
                self._send_events()
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path == "/api/agent/message":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                except (ValueError, json.JSONDecodeError):
                    self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
                    return
                self._send_json(json.dumps(agent.submit(payload)))
                return
            if self.path == "/api/terminal/input":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    sent = terminal.write(str(payload.get("data", "")))
                except (ValueError, json.JSONDecodeError):
                    self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
                    return
                self._send_json(json.dumps({"accepted": sent}))
                return
            if self.path == "/api/terminal/restart":
                terminal.restart()
                self._send_json(json.dumps({"accepted": True, "status": terminal.status()}))
                return
            if self.path == "/api/terminal/stop":
                terminal.stop()
                self._send_json(json.dumps({"accepted": True, "status": terminal.status()}))
                return
            if self.path == "/api/terminal/resize":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    terminal.resize(rows=int(payload.get("rows", 30)), cols=int(payload.get("cols", 100)))
                except (ValueError, json.JSONDecodeError):
                    self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
                    return
                self._send_json(json.dumps({"accepted": True, "status": terminal.status()}))
                return
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

        def _send_file(self, path: Path, content_type: str | None = None) -> None:
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _send_json(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _send_camera_frame(self) -> None:
            body, content_type = camera.frame()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _send_camera_stream(self) -> None:
            boundary = "avatar-camera-frame"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                try:
                    body, content_type = camera.frame()
                    header = (
                        f"--{boundary}\r\n"
                        f"Content-Type: {content_type}\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n"
                    ).encode("utf-8")
                    self.wfile.write(header)
                    self.wfile.write(body)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                    time.sleep(max(0.0, float(os.getenv("AVATAR_CAMERA_STREAM_INTERVAL_MS", "66")) / 1000.0))
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break

        def _send_events(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            while True:
                try:
                    payload = f"data: {source.snapshot().to_json()}\n\n".encode("utf-8")
                    self.wfile.write(payload)
                    self.wfile.flush()
                    time.sleep(0.5)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break

        def _send_terminal_events(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            seq = 0
            while True:
                try:
                    chunks = terminal.wait_for_chunks(seq, timeout_s=15.0)
                    if not chunks:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    for seq, chunk in chunks:
                        payload = json.dumps({"seq": seq, "data": chunk})
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break

    return DashboardHandler


def run_server(
    *,
    host: str,
    port: int,
    system_address: str,
    demo: bool,
    camera_url: str | None = None,
    agent_webhook_url: str | None = None,
    terminal_command: list[str] | None = None,
    terminal_auto_prompt: bool = True,
) -> None:
    source = DashboardTelemetrySource(system_address=system_address, demo=demo)
    camera = DashboardCameraSource(camera_url=camera_url)
    terminal = DashboardTerminalSession(
        cwd=PROJECT_ROOT,
        command=terminal_command,
        auto_prompt=terminal_auto_prompt,
    )
    agent = DashboardAgentBridge(webhook_url=agent_webhook_url, terminal=terminal)
    source.start()
    server = ThreadingHTTPServer((host, port), make_handler(source, camera, agent, terminal))
    print(f"Avatar dashboard: http://{host}:{port}")
    print(f"Telemetry source: {'demo' if demo else system_address}")
    print(f"Camera source: {camera_url or 'demo generated frame'}")
    print(f"Agent bridge: browser terminal ({terminal.command_label})")
    if agent_webhook_url:
        print(f"Agent webhook mirror: {agent_webhook_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        terminal.stop()
        source.stop()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Project Avatar local telemetry dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--system-address", default="udp://:14540")
    parser.add_argument("--camera-url", default=os.getenv("AVATAR_CAMERA_URL"))
    parser.add_argument("--agent-webhook-url", default=os.getenv("AVATAR_AGENT_WEBHOOK_URL"))
    parser.add_argument("--terminal-command", default=os.getenv("AVATAR_TERMINAL_CMD"))
    parser.add_argument("--no-terminal-auto-prompt", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Force deterministic demo telemetry")
    args = parser.parse_args()
    terminal_command = shlex.split(args.terminal_command) if args.terminal_command else None
    run_server(
        host=args.host,
        port=args.port,
        system_address=args.system_address,
        demo=args.demo,
        camera_url=args.camera_url,
        agent_webhook_url=args.agent_webhook_url,
        terminal_command=terminal_command,
        terminal_auto_prompt=not args.no_terminal_auto_prompt,
    )


if __name__ == "__main__":
    main()
