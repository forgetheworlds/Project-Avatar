# Project Avatar Full SITL-To-Hardware Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Project Avatar into a locally simulated, MCP-controlled PX4/Gazebo drone system that proves the LLM-agent flight/control/vision stack before hardware purchase and keeps hardware migration to adapter/config swaps.

**Architecture:** The system is split into strict seams: MCP protocol server, shared flight runtime, MAVSDK/PX4 control adapter, offboard setpoint streamer, Guardian safety executor, telemetry cache, camera provider, detector provider, vision state, mission behaviors, and hardware profile configuration. SITL acceptance tests must use the real MCP protocol and real PX4 SITL; unit tests may use mocks only when the test name and backend metadata explicitly say mock.

**Tech Stack:** Python 3.11+, MCP Python SDK, MAVSDK-Python, PX4 SITL + Gazebo, pytest/pytest-asyncio, optional Hypothesis for property tests, Gazebo camera transport/ROS bridge adapter, optional Ultralytics YOLO, structured JSON flight logs.

---

## North Star

Before buying parts, this repo must demonstrate:

- A real MCP client can discover and call drone tools over stdio.
- PX4 SITL receives actual MAVSDK commands from those MCP calls.
- The drone can run a basic simulated mission from takeoff to landing.
- Guardian safety monitors can command RTL/Land/Hold through MAVSDK.
- Offboard velocity control has a continuous setpoint streamer with tested cleanup.
- Vision has explicit backends and can move from mock frames to Gazebo frames to hardware camera frames.
- Tracking/cinematic behaviors consume `VisionState` and telemetry through stable interfaces.
- Hardware migration is a config/profile change plus final hardware validation, not a rewrite.

## Execution Rules

- Commit after every completed task group.
- Do not mark Phase 0.5 complete unless the real MCP SITL smoke test passes.
- Do not allow docs to claim “real vision” while `mock_camera` or `mock_detector` is active.
- Do not use direct Python calls as proof of agent readiness; proof requires MCP protocol tests.
- If a test cannot run because a dependency is missing, record that dependency and add a clean skip. Do not convert dependency failure into a pass.

---

## Phase 1: Repair Runtime Baseline

### Task 1.1: Restore Importability

**Files:**
- Modify: `avatar/mcp_server/tools/tracking_tools.py:106-107`

- [x] Run:
```bash
python3 -m py_compile avatar/mcp_server/tools/tracking_tools.py
```
Expected: fail with `SyntaxError`.

- [x] Change:
```python
# Gimbal limits (degrees) - These constrain the physical movement range of the
gimbal to prevent hardware damage and maintain image stabilization.
```
To:
```python
# Gimbal limits (degrees) - These constrain the physical movement range of the
# gimbal to prevent hardware damage and maintain image stabilization.
```

- [x] Run:
```bash
python3 -m py_compile avatar/mcp_server/tools/tracking_tools.py
python3 - <<'PY'
from avatar.mcp_server.server import AvatarMCPServer
print(AvatarMCPServer.__name__)
PY
```
Expected:
```text
AvatarMCPServer
```

- [ ] Commit:
```bash
git add avatar/mcp_server/tools/tracking_tools.py
git commit -m "fix: restore importable MCP runtime"
```

### Task 1.2: Normalize Test Dependency Failures

**Files:**
- Modify: `avatar/tests/test_sitl_basic.py`
- Modify: `tests/property/conftest.py`

- [x] Add clean MAVSDK skip to the SITL-only test module:
```python
pytest.importorskip("mavsdk", reason="mavsdk is required for SITL tests")
```
Place it before `from mavsdk import System`.

- [x] Add clean Hypothesis skip to `tests/property/conftest.py`:
```python
pytest.importorskip("hypothesis", reason="hypothesis is required for property tests")
```
Place it before `from hypothesis import settings, Verbosity`.

- [x] Run:
```bash
python3 -m pytest --collect-only -q
```
Expected: collection proceeds past missing dependency errors; remaining failures must be real code errors.

- [ ] Commit:
```bash
git add avatar/tests/test_sitl_basic.py tests/property/conftest.py
git commit -m "test: skip optional dependency suites cleanly"
```

---

## Phase 2: Real MCP Protocol Foundation

### Task 2.1: Add Offline MCP Discovery Mode

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Create: `tests/mcp_server/test_server_offline_protocol.py`

- [x] Create `tests/mcp_server/test_server_offline_protocol.py`:
```python
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

    server.connection_manager.connect = fail_connect

    initialized = await server.initialize()

    assert initialized is True
    status = server.get_status()
    assert status["initialized"] is True
    assert status["connection"]["mode"] == "offline"
```

- [x] Implement `AvatarMCPServerConfig.from_env()` and `connect_on_start` in `avatar/mcp_server/server.py`:
```python
import os
import sys


@dataclass
class AvatarMCPServerConfig:
    system_address: str = "udp://:14540"
    connection_timeout_s: float = 30.0
    telemetry_refresh_ms: int = 100
    heartbeat_hz: float = 20.0
    enable_guardian: bool = True
    enable_auto_failsafe: bool = True
    max_retries: int = 3
    retry_delay_s: float = 1.0
    connect_on_start: bool = True

    @classmethod
    def from_env(cls) -> "AvatarMCPServerConfig":
        def env_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            system_address=os.getenv("AVATAR_SYSTEM_ADDRESS", cls.system_address),
            connection_timeout_s=float(os.getenv("AVATAR_CONNECTION_TIMEOUT_S", cls.connection_timeout_s)),
            telemetry_refresh_ms=int(os.getenv("AVATAR_TELEMETRY_REFRESH_MS", cls.telemetry_refresh_ms)),
            heartbeat_hz=float(os.getenv("AVATAR_HEARTBEAT_HZ", cls.heartbeat_hz)),
            enable_guardian=env_bool("AVATAR_ENABLE_GUARDIAN", cls.enable_guardian),
            enable_auto_failsafe=env_bool("AVATAR_ENABLE_AUTO_FAILSAFE", cls.enable_auto_failsafe),
            max_retries=int(os.getenv("AVATAR_MAX_RETRIES", cls.max_retries)),
            retry_delay_s=float(os.getenv("AVATAR_RETRY_DELAY_S", cls.retry_delay_s)),
            connect_on_start=env_bool("AVATAR_CONNECT_ON_START", cls.connect_on_start),
        )
```

- [x] In `initialize()`, after `logger.info("Initializing Avatar MCP Server...")`, add:
```python
if not self.config.connect_on_start:
    logger.info("Starting in offline MCP discovery mode; drone connection deferred")
    self._initialized = True
    return True
```

- [x] In `get_status()`, add:
```python
"mode": "connected" if self.config.connect_on_start else "offline",
```
inside the `connection` object.

- [x] Change `main()` to:
```python
server = AvatarMCPServer(AvatarMCPServerConfig.from_env())
```

- [x] Set logging to stderr:
```python
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
```

- [x] Run:
```bash
python3 -m pytest tests/mcp_server/test_server_offline_protocol.py -q
```
Expected: `2 passed`.

- [ ] Commit:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_server_offline_protocol.py
git commit -m "feat: support offline MCP discovery mode"
```

### Task 2.2: Add Real MCP Stdio Smoke Test

**Files:**
- Create: `tests/mcp_server/test_mcp_stdio_smoke.py`

- [x] Create `tests/mcp_server/test_mcp_stdio_smoke.py`:
```python
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
    assert "get_status" in names
    assert "arm_and_takeoff" in names
```

- [ ] Run:
```bash
python3 -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
```
Expected: pass if MCP SDK is installed; skip with a clear message if it is not installed.

- [ ] Commit:
```bash
git add tests/mcp_server/test_mcp_stdio_smoke.py
git commit -m "test: cover real MCP stdio tool discovery"
```

---

## Phase 3: Shared Flight Runtime

### Task 3.1: Route MCP Flight Calls Through Server-Owned FlightTools

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Create: `tests/mcp_server/test_server_flight_routing.py`

- [x] Create `tests/mcp_server/test_server_flight_routing.py`:
```python
import json
from unittest.mock import AsyncMock

import pytest

from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig


@pytest.mark.asyncio
async def test_route_tool_uses_server_owned_flight_tools_for_takeoff():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    server.flight_tools.arm_and_takeoff = AsyncMock(return_value={"success": True, "altitude_m": 7.0})

    raw = await server._route_tool("arm_and_takeoff", {"altitude_m": 7.0})

    assert json.loads(raw) == {"success": True, "altitude_m": 7.0}
    server.flight_tools.arm_and_takeoff.assert_awaited_once_with(7.0)


@pytest.mark.asyncio
async def test_route_tool_uses_server_owned_flight_tools_for_motion_commands():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    server.flight_tools.fly_body_offset = AsyncMock(return_value={"success": True, "command": "offset"})
    server.flight_tools.set_velocity = AsyncMock(return_value={"success": True, "command": "velocity"})
    server.flight_tools.hold = AsyncMock(return_value={"success": True, "command": "hold"})

    assert json.loads(await server._route_tool("fly_body_offset", {"forward_m": 2.0}))["command"] == "offset"
    assert json.loads(await server._route_tool("set_velocity", {"north_m_s": 1.0, "duration_s": 0.2}))["command"] == "velocity"
    assert json.loads(await server._route_tool("hold", {"duration_s": 1.0}))["command"] == "hold"
```

- [x] Replace `_route_tool()` core flight branches with `self.flight_tools` calls:
```python
if name == "arm_and_takeoff":
    return json.dumps(await self.flight_tools.arm_and_takeoff(arguments.get("altitude_m", 10.0)))
elif name == "land":
    return json.dumps(await self.flight_tools.land())
elif name == "rtl":
    return json.dumps(await self.flight_tools.rtl())
elif name == "abort_mission":
    return json.dumps(await self.flight_tools.abort_mission(arguments.get("reason", "")))
elif name == "goto_gps":
    return json.dumps(await self.flight_tools.goto_gps(
        lat=arguments.get("lat", 0.0),
        lon=arguments.get("lon", 0.0),
        alt_m=arguments.get("alt_m", 0.0) or None,
        speed_ms=arguments.get("speed_ms", 5.0),
    ))
elif name == "fly_body_offset":
    return json.dumps(await self.flight_tools.fly_body_offset(
        forward_m=arguments.get("forward_m", 0.0),
        right_m=arguments.get("right_m", 0.0),
        up_m=arguments.get("up_m", 0.0),
        yaw_align=arguments.get("yaw_align", False),
        speed_m_s=arguments.get("speed_m_s", 5.0),
    ))
elif name == "set_velocity":
    return json.dumps(await self.flight_tools.set_velocity(
        north_m_s=arguments.get("north_m_s", 0.0),
        east_m_s=arguments.get("east_m_s", 0.0),
        down_m_s=arguments.get("down_m_s", 0.0),
        yaw_deg=arguments.get("yaw_deg", 0.0),
        duration_s=arguments.get("duration_s", 1.0),
    ))
elif name == "hold":
    return json.dumps(await self.flight_tools.hold(
        duration_s=arguments.get("duration_s", 5.0),
        position_tolerance_m=arguments.get("position_tolerance_m", 1.0),
        auto_rtl_on_drift=arguments.get("auto_rtl_on_drift", False),
    ))
```

- [x] Run:
```bash
python3 -m pytest tests/mcp_server/test_server_flight_routing.py -q
```
Expected: all tests pass.

- [ ] Commit:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_server_flight_routing.py
git commit -m "fix: route MCP flight calls through shared runtime"
```

---

## Phase 4: Offboard Control And Safety Execution

### Task 4.1: Add OffboardVelocityStreamer

**Files:**
- Create: `avatar/mav/offboard_streamer.py`
- Modify: `avatar/mcp_server/tools/flight_tools.py`
- Create: `tests/mav/test_offboard_streamer.py`

- [x] Create `avatar/mav/offboard_streamer.py`:
```python
"""Offboard setpoint streaming for PX4 velocity control."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OffboardVelocityStreamer:
    """Streams MAVSDK velocity setpoints at a fixed cadence for PX4 Offboard mode."""

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        return 1.0 / self.rate_hz

    async def stream_for(self, drone: Any, velocity_setpoint: Any, duration_s: float) -> int:
        setpoint_count = 0
        started = False

        try:
            await drone.offboard.set_velocity_ned(velocity_setpoint)
            await drone.offboard.start()
            started = True

            start_time = time.monotonic()
            next_send_time = start_time

            while time.monotonic() - start_time < duration_s:
                await drone.offboard.set_velocity_ned(velocity_setpoint)
                setpoint_count += 1
                next_send_time += self.interval_s
                sleep_s = next_send_time - time.monotonic()
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            return setpoint_count

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Offboard velocity streaming failed: %s", exc)
            return setpoint_count
        finally:
            if started:
                try:
                    await drone.offboard.stop()
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)
```

- [x] Create `tests/mav/test_offboard_streamer.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.offboard_streamer import OffboardVelocityStreamer


@pytest.mark.asyncio
async def test_streamer_sends_initial_setpoint_before_starting_offboard():
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    count = await OffboardVelocityStreamer(rate_hz=20.0).stream_for(drone, setpoint, duration_s=0.12)

    assert count >= 2
    assert drone.offboard.set_velocity_ned.await_count >= 3
    drone.offboard.start.assert_awaited_once()
    drone.offboard.stop.assert_awaited_once()
```

- [x] In `avatar/mcp_server/tools/flight_tools.py`, import and initialize:
```python
from avatar.mav.offboard_streamer import OffboardVelocityStreamer
```
```python
self.offboard_streamer = OffboardVelocityStreamer(rate_hz=20.0)
```

- [x] Replace `_maintain_offboard_streaming()` with a delegation to `self.offboard_streamer.stream_for(...)` and keep the state transition back to `FLYING`.

- [x] Run:
```bash
python3 -m pytest tests/mav/test_offboard_streamer.py avatar/tests/tools/test_set_velocity.py -q
```
Expected: selected tests pass.

- [ ] Commit:
```bash
git add avatar/mav/offboard_streamer.py avatar/mcp_server/tools/flight_tools.py tests/mav/test_offboard_streamer.py
git commit -m "feat: add explicit offboard velocity streamer"
```

### Task 4.2: Wire Guardian To Physical MAVSDK Actions

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Create: `tests/mcp_server/test_guardian_failsafe_actions.py`

- [x] Create `tests/mcp_server/test_guardian_failsafe_actions.py`:
```python
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
```

- [x] In `AvatarMCPServer.__init__`, add:
```python
self.guardian.on_failsafe = self._handle_guardian_failsafe
```

- [x] Add `_handle_guardian_failsafe()`:
```python
async def _handle_guardian_failsafe(self, action: SafetyAction, reason: str) -> None:
    drone = await self.connection_manager.get_drone()
    if drone is None:
        logger.error("Guardian requested %s but no drone is connected: %s", action.value, reason)
        return

    if action == SafetyAction.RTL:
        await drone.action.return_to_launch()
    elif action == SafetyAction.LAND:
        await drone.action.land()
    elif action == SafetyAction.HOLD:
        await drone.action.hold()
    elif action == SafetyAction.EMERGENCY_STOP:
        terminate = getattr(drone.action, "terminate", None)
        kill = getattr(drone.action, "kill", None)
        if terminate is not None:
            await terminate()
        elif kill is not None:
            await kill()
        else:
            logger.critical("No MAVSDK emergency stop action is available")
```

- [x] Run:
```bash
python3 -m pytest tests/mcp_server/test_guardian_failsafe_actions.py -q
```
Expected: tests pass.

- [ ] Commit:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_guardian_failsafe_actions.py
git commit -m "fix: execute MAVSDK guardian failsafe actions"
```

---

## Phase 5: Real MCP + PX4 SITL Smoke Mission

### Task 5.1: Add Actual MCP SITL E2E Test

**Files:**
- Create: `tests/e2e/test_mcp_sitl_smoke.py`

- [x] Create `tests/e2e/test_mcp_sitl_smoke.py`:
```python
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
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_mcp_can_run_basic_sitl_flight_smoke(request):
    if not request.config.getoption("--run-sitl"):
        pytest.skip("requires PX4 SITL running; use --run-sitl")
    if ClientSession is None:
        pytest.skip("mcp SDK is not installed")

    env = os.environ.copy()
    env["AVATAR_CONNECT_ON_START"] = "1"
    env["AVATAR_SYSTEM_ADDRESS"] = os.getenv("SITL_URL", "udp://:14540")

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "avatar.mcp_server"],
        cwd=str(ROOT),
        env=env,
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            await session.call_tool("get_status", {})
            await session.call_tool("get_telemetry", {})
            await session.call_tool("arm_and_takeoff", {"altitude_m": 5.0})
            await session.call_tool("hold", {"duration_s": 2.0})
            await session.call_tool("land", {})
```

- [x] Without SITL, run:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q
```
Expected: `1 skipped`.

- [x] With SITL running, run:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```
Expected: `1 passed`.

- [ ] Commit:
```bash
git add tests/e2e/test_mcp_sitl_smoke.py
git commit -m "test: add real MCP SITL smoke mission"
```

---

## Phase 6: Vision Seam, Then Gazebo Vision

## Simulator Backend Strategy

Use this simulator priority order:

1. **Gazebo / Gazebo Harmonic through PX4 `gz_*` targets**: primary rich-scenario simulator. Use for depth camera, obstacle worlds, cinematic/nature worlds, target following, and eventually camera-frame validation. PX4 documents `make px4_sitl gz_x500`, `gz_x500_depth`, and `gz_x500_vision`; Gazebo Harmonic has macOS install docs, but official support is best-effort on macOS, so verify locally before making it the only path.
2. **PX4 SIH (`px4_sitl_sih`)**: fallback for headless basic control, fail-safe, and MCP command tests when Gazebo is unavailable. SIH will not validate rich vision but can validate flight command logic.
3. **jMAVSim**: fallback for simple quad takeoff/fly/land/failsafe behavior if Gazebo fails on macOS. Do not use it for vision realism.
4. **Remote Linux Gazebo runner**: if local macOS Gazebo is unstable, run Gazebo/PX4 on a Linux machine or VM and connect MCP/MAVSDK over network. This should still use the same MCP tests and runtime profiles.

### Task 6.0: Add Simulator Capability Probe

**Files:**
- Create: `scripts/check_simulator_capabilities.py`
- Create: `tests/test_simulator_capability_probe.py`

- [x] Create `scripts/check_simulator_capabilities.py`:
```python
#!/usr/bin/env python3
"""Detect locally available simulator commands for Project Avatar."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def detect_capabilities(project_root: Path) -> dict[str, object]:
    px4_dir = project_root / "PX4-Autopilot"
    return {
        "px4_autopilot_dir": str(px4_dir),
        "px4_autopilot_present": px4_dir.exists(),
        "make_present": shutil.which("make") is not None,
        "gz_present": shutil.which("gz") is not None,
        "gazebo_present": shutil.which("gazebo") is not None,
        "java_present": shutil.which("java") is not None,
        "recommended_order": ["gazebo_gz_x500", "px4_sih", "jmavsim"],
        "commands": {
            "gazebo_gz_x500": "cd PX4-Autopilot && make px4_sitl gz_x500",
            "gazebo_depth": "cd PX4-Autopilot && make px4_sitl gz_x500_depth",
            "gazebo_vision": "cd PX4-Autopilot && make px4_sitl gz_x500_vision",
            "px4_sih": "cd PX4-Autopilot && make px4_sitl_sih sihsim_quadx",
            "jmavsim": "cd PX4-Autopilot && make px4_sitl jmavsim",
        },
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    print(json.dumps(detect_capabilities(project_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [x] Create `tests/test_simulator_capability_probe.py`:
```python
from pathlib import Path

from scripts.check_simulator_capabilities import detect_capabilities


def test_simulator_capability_probe_reports_expected_commands():
    capabilities = detect_capabilities(Path(__file__).resolve().parents[1])

    commands = capabilities["commands"]
    assert "gazebo_gz_x500" in commands
    assert "gazebo_depth" in commands
    assert "gazebo_vision" in commands
    assert "px4_sih" in commands
    assert "jmavsim" in commands
    assert capabilities["recommended_order"][0] == "gazebo_gz_x500"
```

- [x] Run:
```bash
python3 -m pytest tests/test_simulator_capability_probe.py -q
python3 scripts/check_simulator_capabilities.py
```

Expected: test passes and the script prints JSON with installed simulator capability booleans.

- [ ] Commit:
```bash
git add scripts/check_simulator_capabilities.py tests/test_simulator_capability_probe.py
git commit -m "feat: add simulator capability probe"
```

### Task 6.1: Add Explicit Vision Backend Interfaces

**Files:**
- Create: `avatar/vision/providers.py`
- Modify: `avatar/mcp_server/tools/vision_tools.py`
- Create: `tests/vision/test_vision_providers.py`

- [x] Create `avatar/vision/providers.py`:
```python
"""Vision provider seam for mock, Gazebo, and hardware camera backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from avatar.vision.gazebo_camera_client import GazeboCameraClient
from avatar.vision.mock_detector import Detection, MockDetector


@dataclass(frozen=True)
class VisionBackendConfig:
    camera_backend: str = "mock_camera"
    detector_backend: str = "mock_detector"
    width: int = 640
    height: int = 480
    confidence_threshold: float = 0.5


class MockCameraProvider:
    backend_name = "mock_camera"

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.client = GazeboCameraClient(width=width, height=height)

    def capture_frame(self) -> np.ndarray:
        return self.client.capture_frame_as_numpy()


class MockDetectorProvider:
    backend_name = "mock_detector"

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.detector = MockDetector(confidence_threshold=confidence_threshold, deterministic=True)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        return self.detector.detect(frame)
```

- [x] Create `tests/vision/test_vision_providers.py`:
```python
import numpy as np

from avatar.vision.providers import MockCameraProvider, MockDetectorProvider, VisionBackendConfig


def test_mock_camera_provider_reports_backend_name():
    provider = MockCameraProvider(width=320, height=240)
    frame = provider.capture_frame()
    assert provider.backend_name == "mock_camera"
    assert frame.shape == (240, 320, 3)


def test_mock_detector_provider_reports_backend_name():
    provider = MockDetectorProvider(confidence_threshold=0.5)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = provider.detect(frame)
    assert provider.backend_name == "mock_detector"
    assert isinstance(detections, list)


def test_vision_backend_config_defaults_are_explicitly_mock():
    config = VisionBackendConfig()
    assert config.camera_backend == "mock_camera"
    assert config.detector_backend == "mock_detector"
```

- [x] Update `VisionTools` responses to include `camera_backend` and `detector_backend`.

- [x] Run:
```bash
python3 -m pytest tests/vision/test_vision_providers.py avatar/tests/test_vision_pipeline.py -q
```
Expected: selected tests pass.

- [ ] Commit:
```bash
git add avatar/vision/providers.py avatar/mcp_server/tools/vision_tools.py tests/vision/test_vision_providers.py
git commit -m "feat: make vision backends explicit"
```

### Task 6.2: Add Gazebo Camera Provider

**Files:**
- Modify: `avatar/vision/providers.py`
- Create: `tests/vision/test_gazebo_camera_provider.py`

- [x] Add a provider class that fails clearly when Gazebo/ROS transport is not configured:
```python
class GazeboCameraProvider:
    backend_name = "gazebo_camera"

    def __init__(self, topic: str = "/drone/camera/image_raw") -> None:
        self.topic = topic

    def capture_frame(self) -> np.ndarray:
        raise RuntimeError(
            "gazebo_camera backend requires a Gazebo camera transport adapter. "
            "Use mock_camera until the Gazebo bridge is configured."
        )
```

- [x] Add test:
```python
import pytest

from avatar.vision.providers import GazeboCameraProvider


def test_gazebo_camera_provider_fails_clearly_without_bridge():
    provider = GazeboCameraProvider()
    with pytest.raises(RuntimeError, match="requires a Gazebo camera transport adapter"):
        provider.capture_frame()
```

- [x] Run:
```bash
python3 -m pytest tests/vision/test_gazebo_camera_provider.py -q
```
Expected: pass.

- [ ] Commit:
```bash
git add avatar/vision/providers.py tests/vision/test_gazebo_camera_provider.py
git commit -m "feat: add explicit Gazebo camera provider boundary"
```

### Task 6.3: Add Scenario Catalog For Realistic Drone Use Cases

**Files:**
- Create: `avatar/sim/scenarios.py`
- Create: `tests/sim/test_scenarios.py`

- [x] Create `avatar/sim/scenarios.py`:
```python
"""Simulation scenarios that represent real Project Avatar use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ScenarioKind = Literal[
    "runner_follow",
    "sailboat_follow",
    "nature_cinematic",
    "indoor_obstacle_room",
    "snowboard_halfpipe",
    "skate_bowl",
]


@dataclass(frozen=True)
class SimulationScenario:
    name: str
    kind: ScenarioKind
    simulator: str
    px4_command: str
    required_backends: tuple[str, ...]
    acceptance_test: str
    description: str


SCENARIOS: dict[str, SimulationScenario] = {
    "runner_follow_basic": SimulationScenario(
        name="runner_follow_basic",
        kind="runner_follow",
        simulator="gazebo_or_mock_target",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "vision_state"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_runner_follow.py -q --run-sitl",
        description="Drone takes off, tracks a moving runner target state, keeps safe follow distance, then lands.",
    ),
    "sailboat_follow_wide": SimulationScenario(
        name="sailboat_follow_wide",
        kind="sailboat_follow",
        simulator="gazebo_marine_world_or_mock_target",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "vision_state", "wind_safe_offsets"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_sailboat_follow.py -q --run-sitl",
        description="Drone follows a slow moving boat from a wide lateral offset without descending below safe altitude.",
    ),
    "nature_orbit_reveal": SimulationScenario(
        name="nature_orbit_reveal",
        kind="nature_cinematic",
        simulator="gazebo_gz_x500",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "cinematic_templates"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_nature_cinematic.py -q --run-sitl",
        description="Drone runs a slow reveal and orbit shot around a static landmark target.",
    ),
    "indoor_obstacle_room_depth": SimulationScenario(
        name="indoor_obstacle_room_depth",
        kind="indoor_obstacle_room",
        simulator="gazebo_depth",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500_depth",
        required_backends=("mcp_stdio", "mavsdk", "depth_camera", "guardian_geofence"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_indoor_obstacles.py -q --run-sitl",
        description="Drone navigates a room-like obstacle layout using conservative speed and aborts on obstacle/vision loss.",
    ),
}


def get_scenario(name: str) -> SimulationScenario:
    return SCENARIOS[name]


def list_scenarios() -> list[SimulationScenario]:
    return list(SCENARIOS.values())
```

- [x] Create `tests/sim/test_scenarios.py`:
```python
from avatar.sim.scenarios import SCENARIOS, get_scenario, list_scenarios


def test_scenario_catalog_contains_real_use_cases():
    assert "runner_follow_basic" in SCENARIOS
    assert "sailboat_follow_wide" in SCENARIOS
    assert "nature_orbit_reveal" in SCENARIOS
    assert "indoor_obstacle_room_depth" in SCENARIOS


def test_each_scenario_has_acceptance_command():
    for scenario in list_scenarios():
        assert scenario.acceptance_test.startswith("python3 -m pytest ")
        assert scenario.px4_command.startswith("cd PX4-Autopilot && make ")
        assert "mcp_stdio" in scenario.required_backends


def test_get_scenario_returns_named_scenario():
    scenario = get_scenario("sailboat_follow_wide")

    assert scenario.kind == "sailboat_follow"
    assert "boat" in scenario.description.lower()
```

- [x] Run:
```bash
python3 -m pytest tests/sim/test_scenarios.py -q
```

Expected: all scenario catalog tests pass.

- [ ] Commit:
```bash
git add avatar/sim/scenarios.py tests/sim/test_scenarios.py
git commit -m "feat: add realistic simulation scenario catalog"
```

### Task 6.4: Add Scenario Acceptance Test Skeletons With Real Gates

**Files:**
- Create: `tests/e2e/test_scenario_runner_follow.py`
- Create: `tests/e2e/test_scenario_sailboat_follow.py`
- Create: `tests/e2e/test_scenario_nature_cinematic.py`
- Create: `tests/e2e/test_scenario_indoor_obstacles.py`

- [x] Create `tests/e2e/test_scenario_runner_follow.py`:
```python
import pytest

from avatar.sim.scenarios import get_scenario


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_runner_follow_scenario_gate(request):
    if not request.config.getoption("--run-sitl"):
        pytest.skip("runner follow requires PX4 SITL and scenario target driver")

    scenario = get_scenario("runner_follow_basic")
    assert scenario.kind == "runner_follow"
    pytest.fail("Implement after MCP SITL smoke and VisionState target driver pass")
```

- [x] Create `tests/e2e/test_scenario_sailboat_follow.py`:
```python
import pytest

from avatar.sim.scenarios import get_scenario


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_sailboat_follow_scenario_gate(request):
    if not request.config.getoption("--run-sitl"):
        pytest.skip("sailboat follow requires PX4 SITL and marine target driver")

    scenario = get_scenario("sailboat_follow_wide")
    assert scenario.kind == "sailboat_follow"
    pytest.fail("Implement after wide-offset target tracking controller exists")
```

- [x] Create `tests/e2e/test_scenario_nature_cinematic.py`:
```python
import pytest

from avatar.sim.scenarios import get_scenario


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_nature_cinematic_scenario_gate(request):
    if not request.config.getoption("--run-sitl"):
        pytest.skip("nature cinematic scenario requires PX4 SITL")

    scenario = get_scenario("nature_orbit_reveal")
    assert scenario.kind == "nature_cinematic"
    pytest.fail("Implement after cinematic shot execution passes MCP SITL smoke")
```

- [x] Create `tests/e2e/test_scenario_indoor_obstacles.py`:
```python
import pytest

from avatar.sim.scenarios import get_scenario


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_indoor_obstacle_room_scenario_gate(request):
    if not request.config.getoption("--run-sitl"):
        pytest.skip("indoor obstacle scenario requires Gazebo depth-camera SITL")

    scenario = get_scenario("indoor_obstacle_room_depth")
    assert scenario.kind == "indoor_obstacle_room"
    pytest.fail("Implement after depth-camera Gazebo backend and obstacle abort policy exist")
```

- [x] Run without SITL:
```bash
python3 -m pytest \
  tests/e2e/test_scenario_runner_follow.py \
  tests/e2e/test_scenario_sailboat_follow.py \
  tests/e2e/test_scenario_nature_cinematic.py \
  tests/e2e/test_scenario_indoor_obstacles.py \
  -q
```

Expected: all scenario tests skip without `--run-sitl`.

- [ ] Run with SITL only when the corresponding driver exists:
```bash
python3 -m pytest tests/e2e/test_scenario_runner_follow.py -q --run-sitl
```

Expected before the target driver exists: fail with the explicit message in `pytest.fail`. This is intentional so scenario readiness cannot be claimed prematurely.

- [ ] Commit:
```bash
git add tests/e2e/test_scenario_runner_follow.py tests/e2e/test_scenario_sailboat_follow.py tests/e2e/test_scenario_nature_cinematic.py tests/e2e/test_scenario_indoor_obstacles.py
git commit -m "test: add gated real-world scenario acceptance tests"
```

---

## Phase 7: Tracking And Cinematic Behaviors On Stable Interfaces

### Task 7.1: Fix Cinematic Shot Connection API

**Files:**
- Modify: `avatar/mcp_server/tools/cinematic_shots.py`
- Modify: `tests/test_cinematic_shots.py`

- [x] Add focused test:
```python
import json
from unittest.mock import AsyncMock, patch

import pytest

from avatar.mcp_server.tools.cinematic_shots import execute_cinematic_shot


@pytest.mark.asyncio
async def test_execute_cinematic_shot_handles_missing_drone_without_unawaited_coroutine():
    with patch("avatar.mcp_server.tools.cinematic_shots.ConnectionManager") as manager_cls:
        manager = manager_cls.return_value
        manager.get_drone = AsyncMock(return_value=None)
        raw = await execute_cinematic_shot("orbit_close", 37.0, -122.0)

    data = json.loads(raw)
    assert data["success"] is False
    assert data["error"] == "Drone not connected"
```

- [x] Replace invalid calls:
```python
drone = cm.get_drone()
cache = cm.get_telemetry_cache()
```
With:
```python
drone = await cm.get_drone()
cache = get_telemetry_cache()
```

- [x] Import:
```python
from avatar.mcp_server.tools.flight_tools import set_velocity, get_telemetry_cache
```

- [x] Run:
```bash
python3 -m pytest tests/test_cinematic_shots.py -q
```
Expected: selected suite passes.

- [ ] Commit:
```bash
git add avatar/mcp_server/tools/cinematic_shots.py tests/test_cinematic_shots.py
git commit -m "fix: use valid connection APIs in cinematic shots"
```

---

## Phase 8: Hardware Profile Preparation

### Task 8.1: Add Flight Profile Configuration

**Files:**
- Create: `avatar/config/profiles.py`
- Create: `tests/config/test_profiles.py`

- [x] Create `avatar/config/profiles.py`:
```python
"""Runtime profiles for SITL and hardware connection boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    system_address: str
    camera_backend: str
    detector_backend: str
    requires_px4_parameter_check: bool


SITL_PROFILE = RuntimeProfile(
    name="sitl",
    system_address="udp://:14540",
    camera_backend="mock_camera",
    detector_backend="mock_detector",
    requires_px4_parameter_check=False,
)

HARDWARE_PROFILE = RuntimeProfile(
    name="hardware",
    system_address="serial:///dev/ttyACM0:921600",
    camera_backend="rtsp_camera",
    detector_backend="yolo_detector",
    requires_px4_parameter_check=True,
)
```

- [x] Create `tests/config/test_profiles.py`:
```python
from avatar.config.profiles import HARDWARE_PROFILE, SITL_PROFILE


def test_sitl_profile_uses_sitl_udp_connection():
    assert SITL_PROFILE.name == "sitl"
    assert SITL_PROFILE.system_address == "udp://:14540"
    assert SITL_PROFILE.requires_px4_parameter_check is False


def test_hardware_profile_requires_parameter_check():
    assert HARDWARE_PROFILE.name == "hardware"
    assert HARDWARE_PROFILE.requires_px4_parameter_check is True
    assert HARDWARE_PROFILE.system_address.startswith("serial://")
```

- [x] Run:
```bash
python3 -m pytest tests/config/test_profiles.py -q
```
Expected: pass.

- [ ] Commit:
```bash
git add avatar/config/profiles.py tests/config/test_profiles.py
git commit -m "feat: define SITL and hardware runtime profiles"
```

---

## Phase 9: Documentation Truth Gate

### Task 9.1: Replace Completion Claims With Verification Gates

**Files:**
- Modify: `README.md`
- Modify: `docs/analysis/mcp_standards_audit.md`
- Modify: `docs/analysis/safety_architecture_gaps.md`

- [x] Add this README status section:
```markdown
## Phase 0.5 Verification Status

Phase 0.5 is considered complete only when:

```bash
python3 -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```

both pass.

Current mock-only boundaries:
- `mock_camera`
- `mock_detector`

Current real boundaries:
- MCP stdio protocol
- MAVSDK connection to PX4 SITL when `AVATAR_CONNECT_ON_START=1`
- Guardian failsafe callback to MAVSDK actions after the safety callback tests pass
```

- [x] Run:
```bash
rg -n "Phase 0.5.*COMPLETE|SITL-Ready|all software validated|fully functional" README.md docs/analysis research/01-core-project
```
Expected: every remaining match is historical or explicitly qualified by verification gates.

- [ ] Commit:
```bash
git add README.md docs/analysis/mcp_standards_audit.md docs/analysis/safety_architecture_gaps.md
git commit -m "docs: replace completion claims with verification gates"
```

---

## Phase 10: Final Pre-Purchase Readiness Gate

### Current Verification Notes

- `.venv/bin/python -m pytest -q` passes in the dependency-complete environment.
- `.venv/bin/python -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl --timeout=120` passed once against PX4/Gazebo `gz_x500`.
- Gazebo launch is currently flaky across repeated start/stop cycles: later scenario runs failed before tests because `gz_bridge` timed out spawning `x500_0`. Clean up stale `gz sim` processes before retrying scenario tests.
- Scenario tests now execute real MCP sequences when `--run-sitl` is supplied, but their SITL checkbox remains unchecked until the Gazebo lifecycle is stable enough for the full scenario set to pass.

### Task 10.1: Run Full Verification Matrix

**Files:**
- Modify: `changes-made.md` only if recording final verification status.

- [x] Compile:
```bash
python3 -m py_compile \
  avatar/mcp_server/server.py \
  avatar/mcp_server/tools/flight_tools.py \
  avatar/mcp_server/tools/tracking_tools.py \
  avatar/mcp_server/tools/cinematic_shots.py \
  avatar/mav/offboard_streamer.py \
  avatar/mav/heartbeat_service.py \
  avatar/mav/guardian_async.py \
  avatar/vision/providers.py
```

- [x] Run focused non-SITL tests:
```bash
python3 -m pytest \
  tests/mcp_server/test_server_offline_protocol.py \
  tests/mcp_server/test_mcp_stdio_smoke.py \
  tests/mcp_server/test_server_flight_routing.py \
  tests/mcp_server/test_guardian_failsafe_actions.py \
  tests/mav/test_offboard_streamer.py \
  tests/vision/test_vision_providers.py \
  avatar/tests/test_vision_pipeline.py \
  -q
```

- [x] Run full collection:
```bash
python3 -m pytest --collect-only -q
```

- [x] Run full suite:
```bash
python3 -m pytest -q
```

- [x] Run SITL MCP smoke:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```

- [ ] Record final status in `changes-made.md`:
```markdown
## 2026-04-13 Project Avatar SITL-To-Hardware Build Status

- MCP stdio discovery: PASS
- Shared MCP flight routing: PASS
- Guardian MAVSDK failsafe callbacks: PASS
- Offboard velocity streamer: PASS
- Vision backend seam: PASS
- Full collection: PASS
- Full test suite: PASS
- MCP SITL smoke mission: PASS
- Remaining hardware-only items: physical serial link, real camera transport, real YOLO backend, PX4 parameter verification on hardware
```

- [ ] Commit:
```bash
git add changes-made.md
git commit -m "docs: record pre-purchase readiness verification"
```
