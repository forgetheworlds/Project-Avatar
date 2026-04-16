# MCP SITL Flight Spine Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Project Avatar's real MCP server control PX4 SITL through a verified flight spine, with honest safety/offboard behavior and a vision seam ready for Gazebo/YOLO integration.

**Architecture:** The MCP server must own shared runtime components and route all flight calls through those instances. SITL acceptance tests must exercise the real MCP protocol over stdio, not direct Python helper calls, while unit tests keep mocks isolated. Safety failsafes must call MAVSDK recovery actions, and offboard control must have one explicit streaming owner instead of documentation-only heartbeat claims.

**Tech Stack:** Python 3.11+, MCP Python SDK, MAVSDK-Python, PX4 SITL + Gazebo, pytest/pytest-asyncio, stdio JSON-RPC/MCP client harness, optional Ultralytics YOLO in the follow-up vision milestone.

---

## Scope And Non-Negotiables

- This plan fixes the first critical milestone: actual MCP protocol -> server-owned flight tools -> MAVSDK/PX4 SITL.
- Mock unit tests are allowed, but they cannot be used as evidence for SITL readiness.
- The server must start in an offline discovery mode for protocol tests and in SITL-connected mode for flight tests.
- Any code path that is mock-only must be named as mock-only in code, docs, and test assertions.
- The first vision work in this plan is a seam, not full YOLO/Gazebo vision. Full Gazebo camera and detector realism should follow after the MCP flight spine passes.

## File Structure

- Modify: `avatar/mcp_server/tools/tracking_tools.py`
  - Fix the syntax error blocking MCP imports.
- Modify: `avatar/mcp_server/server.py`
  - Add environment-backed server config.
  - Add offline protocol mode.
  - Route flight tools through `self.flight_tools`.
  - Wire Guardian failsafe callbacks to MAVSDK actions.
  - Make heartbeat/offboard startup behavior explicit.
- Modify: `avatar/mcp_server/tools/flight_tools.py`
  - Add dependency injection for shared `ConnectionManager`.
  - Keep module wrappers for backward compatibility, but make server routing avoid them.
  - Prepare `set_velocity` to use the shared offboard streamer introduced below.
- Create: `avatar/mav/offboard_streamer.py`
  - Own continuous Offboard setpoint streaming for velocity commands.
- Modify: `avatar/mav/heartbeat_service.py`
  - Clarify watchdog/source-monitor role.
  - Do not imply it sends PX4 setpoints unless an explicit callback is configured.
- Modify: `avatar/mav/guardian_async.py`
  - Keep state-machine transitions, but rely on server callback for physical MAVSDK actions.
- Create: `tests/mcp_server/test_server_offline_protocol.py`
  - Test server initialization and routing without SITL.
- Create: `tests/mcp_server/test_mcp_stdio_smoke.py`
  - Launch `python3 -m avatar.mcp_server` and use the actual MCP stdio protocol for `initialize`, `tools/list`, and safe calls.
- Create: `tests/mcp_server/test_server_flight_routing.py`
  - Prove `_route_tool` uses `self.flight_tools`.
- Create: `tests/mav/test_offboard_streamer.py`
  - Prove offboard streaming sends initial setpoint, starts offboard, loops at target cadence, and stops safely.
- Create: `tests/mcp_server/test_guardian_failsafe_actions.py`
  - Prove Guardian callback calls MAVSDK RTL/Land/Hold actions.
- Create: `tests/e2e/test_mcp_sitl_smoke.py`
  - SITL-required real MCP smoke mission.
- Modify: `docs/analysis/mcp_standards_audit.md`
  - Replace “functional/SITL-ready” claims with verified status after tests pass.
- Modify: `docs/analysis/safety_architecture_gaps.md`
  - Replace “auto-triggered” claims with the actual callback-backed behavior after it exists.
- Modify: `README.md`
  - Add a truthful “Phase 0.5A status” section and exact verification commands.

---

### Task 1: Restore Importability Baseline

**Files:**
- Modify: `avatar/mcp_server/tools/tracking_tools.py:106-107`
- Test: import and compile commands

- [ ] **Step 1: Run the failing import/compile check**

Run:
```bash
python3 -m py_compile avatar/mcp_server/tools/tracking_tools.py
```

Expected: FAIL with:
```text
SyntaxError: invalid syntax
```

- [ ] **Step 2: Fix the bare text line**

Change:
```python
# Gimbal limits (degrees) - These constrain the physical movement range of the
gimbal to prevent hardware damage and maintain image stabilization.
```

To:
```python
# Gimbal limits (degrees) - These constrain the physical movement range of the
# gimbal to prevent hardware damage and maintain image stabilization.
```

- [ ] **Step 3: Verify the direct file compile passes**

Run:
```bash
python3 -m py_compile avatar/mcp_server/tools/tracking_tools.py
```

Expected: no output and exit code 0.

- [ ] **Step 4: Verify the MCP server module imports**

Run:
```bash
python3 - <<'PY'
from avatar.mcp_server.server import AvatarMCPServer
print(AvatarMCPServer.__name__)
PY
```

Expected:
```text
AvatarMCPServer
```

- [ ] **Step 5: Commit**

Run:
```bash
git add avatar/mcp_server/tools/tracking_tools.py
git commit -m "fix: restore MCP server importability"
```

---

### Task 2: Add Offline MCP Discovery Mode

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Test: `tests/mcp_server/test_server_offline_protocol.py`

- [ ] **Step 1: Write failing tests for environment config and offline initialization**

Create `tests/mcp_server/test_server_offline_protocol.py`:
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
    assert server.get_status()["initialized"] is True
    assert server.get_status()["connection"]["mode"] == "offline"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:
```bash
python3 -m pytest tests/mcp_server/test_server_offline_protocol.py -q
```

Expected: FAIL because `AvatarMCPServerConfig.from_env` and `connect_on_start` do not exist.

- [ ] **Step 3: Add config fields and environment parsing**

In `avatar/mcp_server/server.py`, add `import os` near the imports:
```python
import os
```

Extend `AvatarMCPServerConfig`:
```python
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

- [ ] **Step 4: Make `initialize()` support offline protocol mode**

At the top of `initialize()`, after the log line:
```python
logger.info("Initializing Avatar MCP Server...")
```

add:
```python
if not self.config.connect_on_start:
    logger.info("Starting in offline MCP discovery mode; drone connection deferred")
    self._initialized = True
    return True
```

In `get_status()`, change the `connection` dict to include mode:
```python
"connection": {
    "mode": "connected" if self.config.connect_on_start else "offline",
    "state": self.connection_manager.state.name,
    "health": {
        "is_healthy": self.connection_manager.health.is_healthy,
        "gps_lock": self.connection_manager.health.gps_lock,
        "home_position_set": self.connection_manager.health.home_position_set,
        "error_count": self.connection_manager.health.error_count,
    },
},
```

- [ ] **Step 5: Use env config in module entry point**

In `main()`, change:
```python
server = AvatarMCPServer()
```

To:
```python
server = AvatarMCPServer(AvatarMCPServerConfig.from_env())
```

- [ ] **Step 6: Run the test and verify it passes**

Run:
```bash
python3 -m pytest tests/mcp_server/test_server_offline_protocol.py -q
```

Expected:
```text
2 passed
```

- [ ] **Step 7: Commit**

Run:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_server_offline_protocol.py
git commit -m "feat: add offline MCP discovery mode"
```

---

### Task 3: Route MCP Flight Tools Through The Server-Owned FlightTools

**Files:**
- Modify: `avatar/mcp_server/server.py:1369-1420`
- Test: `tests/mcp_server/test_server_flight_routing.py`

- [ ] **Step 1: Write failing routing tests**

Create `tests/mcp_server/test_server_flight_routing.py`:
```python
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
    server.flight_tools.fly_body_offset = AsyncMock(return_value={"success": True, "command": "offset"})
    server.flight_tools.set_velocity = AsyncMock(return_value={"success": True, "command": "velocity"})
    server.flight_tools.hold = AsyncMock(return_value={"success": True, "command": "hold"})

    offset_raw = await server._route_tool("fly_body_offset", {"forward_m": 2.0})
    velocity_raw = await server._route_tool("set_velocity", {"north_m_s": 1.0, "duration_s": 0.2})
    hold_raw = await server._route_tool("hold", {"duration_s": 1.0})

    assert json.loads(offset_raw)["command"] == "offset"
    assert json.loads(velocity_raw)["command"] == "velocity"
    assert json.loads(hold_raw)["command"] == "hold"
    server.flight_tools.fly_body_offset.assert_awaited_once()
    server.flight_tools.set_velocity.assert_awaited_once()
    server.flight_tools.hold.assert_awaited_once()
```

- [ ] **Step 2: Run test and verify it fails**

Run:
```bash
python3 -m pytest tests/mcp_server/test_server_flight_routing.py -q
```

Expected: FAIL because `_route_tool()` calls module-level wrapper functions instead of `server.flight_tools`.

- [ ] **Step 3: Update `_route_tool()` flight command branches**

In `avatar/mcp_server/server.py`, replace the core flight command branch body with direct server-owned calls:
```python
if name == "arm_and_takeoff":
    result = await self.flight_tools.arm_and_takeoff(arguments.get("altitude_m", 10.0))
    return json.dumps(result)

elif name == "land":
    result = await self.flight_tools.land()
    return json.dumps(result)

elif name == "rtl":
    result = await self.flight_tools.rtl()
    return json.dumps(result)

elif name == "abort_mission":
    result = await self.flight_tools.abort_mission(arguments.get("reason", ""))
    return json.dumps(result)

elif name == "goto_gps":
    result = await self.flight_tools.goto_gps(
        lat=arguments.get("lat", 0.0),
        lon=arguments.get("lon", 0.0),
        alt_m=arguments.get("alt_m", 0.0) or None,
        speed_ms=arguments.get("speed_ms", 5.0),
    )
    return json.dumps(result)

elif name == "fly_body_offset":
    result = await self.flight_tools.fly_body_offset(
        forward_m=arguments.get("forward_m", 0.0),
        right_m=arguments.get("right_m", 0.0),
        up_m=arguments.get("up_m", 0.0),
        yaw_align=arguments.get("yaw_align", False),
        speed_m_s=arguments.get("speed_m_s", 5.0),
    )
    return json.dumps(result)

elif name == "set_velocity":
    result = await self.flight_tools.set_velocity(
        north_m_s=arguments.get("north_m_s", 0.0),
        east_m_s=arguments.get("east_m_s", 0.0),
        down_m_s=arguments.get("down_m_s", 0.0),
        yaw_deg=arguments.get("yaw_deg", 0.0),
        duration_s=arguments.get("duration_s", 1.0),
    )
    return json.dumps(result)

elif name == "hold":
    result = await self.flight_tools.hold(
        duration_s=arguments.get("duration_s", 5.0),
        position_tolerance_m=arguments.get("position_tolerance_m", 1.0),
        auto_rtl_on_drift=arguments.get("auto_rtl_on_drift", False),
    )
    return json.dumps(result)
```

- [ ] **Step 4: Run the routing tests**

Run:
```bash
python3 -m pytest tests/mcp_server/test_server_flight_routing.py -q
```

Expected:
```text
2 passed
```

- [ ] **Step 5: Run a compile/import check**

Run:
```bash
python3 -m py_compile avatar/mcp_server/server.py avatar/mcp_server/tools/flight_tools.py
```

Expected: no output and exit code 0.

- [ ] **Step 6: Commit**

Run:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_server_flight_routing.py
git commit -m "fix: route MCP flight tools through shared server state"
```

---

### Task 4: Add A Real MCP Stdio Smoke Harness

**Files:**
- Create: `tests/mcp_server/test_mcp_stdio_smoke.py`
- Modify: `pyproject.toml` only if pytest marker registration is needed

- [ ] **Step 1: Write a protocol-level smoke test**

Create `tests/mcp_server/test_mcp_stdio_smoke.py`:
```python
import os
import sys
from pathlib import Path

import pytest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover - test skip path
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

- [ ] **Step 2: Run the smoke test**

Run:
```bash
python3 -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
```

Expected before Task 2/3 is complete: fail or skip depending on MCP SDK availability.

Expected after Task 2/3 is complete and MCP SDK installed:
```text
1 passed
```

- [ ] **Step 3: If the test fails because the server logs to stdout, redirect logs to stderr**

In `avatar/mcp_server/server.py`, replace:
```python
logging.basicConfig(level=logging.INFO)
```

With:
```python
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
```

Add `import sys` to the imports if it is not present.

- [ ] **Step 4: Run the test again**

Run:
```bash
python3 -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
```

Expected:
```text
1 passed
```

- [ ] **Step 5: Commit**

Run:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_mcp_stdio_smoke.py
git commit -m "test: add real MCP stdio smoke coverage"
```

---

### Task 5: Wire Guardian Failsafes To MAVSDK Actions

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Test: `tests/mcp_server/test_guardian_failsafe_actions.py`

- [ ] **Step 1: Write failing tests for MAVSDK failsafe actions**

Create `tests/mcp_server/test_guardian_failsafe_actions.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.guardian_async import SafetyAction
from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig


@pytest.fixture
async def offline_server():
    server = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    await server.initialize()
    return server


@pytest.mark.asyncio
async def test_guardian_rtl_callback_calls_return_to_launch(offline_server):
    drone = MagicMock()
    drone.action.return_to_launch = AsyncMock()
    offline_server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await offline_server._handle_guardian_failsafe(SafetyAction.RTL, "test_rtl")

    drone.action.return_to_launch.assert_awaited_once()


@pytest.mark.asyncio
async def test_guardian_land_callback_calls_land(offline_server):
    drone = MagicMock()
    drone.action.land = AsyncMock()
    offline_server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await offline_server._handle_guardian_failsafe(SafetyAction.LAND, "test_land")

    drone.action.land.assert_awaited_once()


@pytest.mark.asyncio
async def test_guardian_hold_callback_calls_hold(offline_server):
    drone = MagicMock()
    drone.action.hold = AsyncMock()
    offline_server.connection_manager.get_drone = AsyncMock(return_value=drone)

    await offline_server._handle_guardian_failsafe(SafetyAction.HOLD, "test_hold")

    drone.action.hold.assert_awaited_once()
```

- [ ] **Step 2: Run tests and verify failure**

Run:
```bash
python3 -m pytest tests/mcp_server/test_guardian_failsafe_actions.py -q
```

Expected: FAIL because `_handle_guardian_failsafe` does not exist.

- [ ] **Step 3: Implement the server failsafe callback**

In `AvatarMCPServer.__init__`, after constructing `self.guardian`, add:
```python
self.guardian.on_failsafe = self._handle_guardian_failsafe
```

Add this method to `AvatarMCPServer`:
```python
async def _handle_guardian_failsafe(self, action: SafetyAction, reason: str) -> None:
    """Execute a physical MAVSDK recovery action requested by AsyncGuardian."""
    drone = await self.connection_manager.get_drone()
    if drone is None:
        logger.error("Guardian requested %s but drone is not connected: %s", action.value, reason)
        return

    logger.warning("Executing Guardian failsafe action %s: %s", action.value, reason)

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
            logger.critical("No MAVSDK emergency stop method available for this drone action plugin")
```

- [ ] **Step 4: Run failsafe callback tests**

Run:
```bash
python3 -m pytest tests/mcp_server/test_guardian_failsafe_actions.py -q
```

Expected:
```text
3 passed
```

- [ ] **Step 5: Commit**

Run:
```bash
git add avatar/mcp_server/server.py tests/mcp_server/test_guardian_failsafe_actions.py
git commit -m "fix: execute MAVSDK actions for guardian failsafes"
```

---

### Task 6: Introduce A Single Offboard Velocity Streamer

**Files:**
- Create: `avatar/mav/offboard_streamer.py`
- Modify: `avatar/mcp_server/tools/flight_tools.py`
- Test: `tests/mav/test_offboard_streamer.py`

- [ ] **Step 1: Write failing offboard streamer tests**

Create `tests/mav/test_offboard_streamer.py`:
```python
import asyncio
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
    streamer = OffboardVelocityStreamer(rate_hz=20.0)

    count = await streamer.stream_for(drone, setpoint, duration_s=0.12)

    assert count >= 2
    assert drone.offboard.set_velocity_ned.await_count >= 3
    assert drone.offboard.set_velocity_ned.await_args_list[0].args == (setpoint,)
    drone.offboard.start.assert_awaited_once()
    drone.offboard.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamer_stops_offboard_when_streaming_raises():
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock(side_effect=[None, RuntimeError("link lost")])
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()
    streamer = OffboardVelocityStreamer(rate_hz=20.0)

    count = await streamer.stream_for(drone, setpoint, duration_s=0.2)

    assert count == 0
    drone.offboard.stop.assert_awaited_once()
```

- [ ] **Step 2: Run tests and verify failure**

Run:
```bash
python3 -m pytest tests/mav/test_offboard_streamer.py -q
```

Expected: FAIL because `avatar.mav.offboard_streamer` does not exist.

- [ ] **Step 3: Implement the offboard streamer**

Create `avatar/mav/offboard_streamer.py`:
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
        """Send velocity setpoints, start offboard mode, stream for duration, then stop."""
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

- [ ] **Step 4: Run streamer tests**

Run:
```bash
python3 -m pytest tests/mav/test_offboard_streamer.py -q
```

Expected:
```text
2 passed
```

- [ ] **Step 5: Wire FlightTools to the streamer**

In `avatar/mcp_server/tools/flight_tools.py`, add:
```python
from avatar.mav.offboard_streamer import OffboardVelocityStreamer
```

In `FlightTools.__init__`, add:
```python
self.offboard_streamer = OffboardVelocityStreamer(rate_hz=20.0)
```

Replace the body of `_maintain_offboard_streaming()` with:
```python
setpoint_count = await self.offboard_streamer.stream_for(
    drone=drone,
    velocity_setpoint=velocity_setpoint,
    duration_s=duration_s,
)

if self.state_machine.current_state == FlightState.VELOCITY_CONTROL:
    self.state_machine.transition(
        FlightState.FLYING,
        "velocity_command_completed",
        "llm",
    )

return setpoint_count
```

- [ ] **Step 6: Run velocity tests**

Run:
```bash
python3 -m pytest avatar/tests/tools/test_set_velocity.py tests/mav/test_offboard_streamer.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:
```bash
git add avatar/mav/offboard_streamer.py avatar/mcp_server/tools/flight_tools.py tests/mav/test_offboard_streamer.py
git commit -m "feat: centralize PX4 offboard velocity streaming"
```

---

### Task 7: Make HeartbeatService Documentation And Server Defaults Honest

**Files:**
- Modify: `avatar/mav/heartbeat_service.py`
- Modify: `avatar/mcp_server/server.py`
- Test: `tests/mav/test_heartbeat_service.py`

- [ ] **Step 1: Add a regression test for callback-backed emission**

Append to `tests/mav/test_heartbeat_service.py`:
```python
import asyncio

import pytest

from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig, HeartbeatSource


@pytest.mark.asyncio
async def test_heartbeat_emitter_requires_callback_for_external_side_effects():
    calls = []

    async def callback(source, timestamp):
        calls.append((source, timestamp))

    service = HeartbeatService(HeartbeatConfig(heartbeat_hz=20.0, emit_heartbeat=True))
    service.on_heartbeat = callback

    await service.start()
    await asyncio.sleep(0.12)
    await service.stop()

    assert calls
    assert {source for source, _ in calls} == {HeartbeatSource.OFFBOARD}
```

- [ ] **Step 2: Run the heartbeat tests**

Run:
```bash
python3 -m pytest tests/mav/test_heartbeat_service.py -q
```

Expected: pass. If imports duplicate existing names, merge imports instead of duplicating them.

- [ ] **Step 3: Update the HeartbeatService module docstring language**

Replace wording that says the service itself “sends OffboardControlMode messages to PX4” with:
```text
This service is a watchdog/cadence source. It only produces an external PX4 side effect when
`on_heartbeat` is configured by the caller. Velocity/position setpoint streaming is owned by
`OffboardVelocityStreamer` and flight tools.
```

- [ ] **Step 4: Make server startup not imply setpoint emission**

In `avatar/mcp_server/server.py`, update the comment above heartbeat startup to:
```python
# Start heartbeat watchdog/source monitor.
# Actual PX4 offboard velocity setpoint streaming is owned by OffboardVelocityStreamer.
```

- [ ] **Step 5: Run focused tests**

Run:
```bash
python3 -m pytest tests/mav/test_heartbeat_service.py tests/mav/test_guardian_async.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add avatar/mav/heartbeat_service.py avatar/mcp_server/server.py tests/mav/test_heartbeat_service.py
git commit -m "docs: make heartbeat watchdog behavior explicit"
```

---

### Task 8: Add Explicit Vision Seam Without Solving Full Gazebo Vision

**Files:**
- Create: `avatar/vision/providers.py`
- Modify: `avatar/mcp_server/tools/vision_tools.py`
- Test: `tests/vision/test_vision_providers.py`

- [ ] **Step 1: Write failing tests for camera/detector backend naming**

Create directory and file `tests/vision/test_vision_providers.py`:
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

- [ ] **Step 2: Run tests and verify failure**

Run:
```bash
python3 -m pytest tests/vision/test_vision_providers.py -q
```

Expected: FAIL because `avatar.vision.providers` does not exist.

- [ ] **Step 3: Implement provider seam**

Create `avatar/vision/providers.py`:
```python
"""Vision provider seam for mock, Gazebo, and future hardware camera backends."""

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

- [ ] **Step 4: Wire `VisionTools` to the seam**

In `avatar/mcp_server/tools/vision_tools.py`, import:
```python
from avatar.vision.providers import MockCameraProvider, MockDetectorProvider, VisionBackendConfig
```

Change `VisionTools.__init__` to store:
```python
self.backend_config = VisionBackendConfig(
    camera_backend="mock_camera",
    detector_backend="mock_detector",
    width=self.config.camera_width,
    height=self.config.camera_height,
    confidence_threshold=self.config.confidence_threshold,
)
self._camera_provider: Optional[MockCameraProvider] = None
self._detector_provider: Optional[MockDetectorProvider] = None
```

Add to `capture_frame()` success response:
```python
"camera_backend": self.backend_config.camera_backend,
```

Add to `get_detected_objects()` success response:
```python
"detector_backend": self.backend_config.detector_backend,
```

- [ ] **Step 5: Run provider and existing vision tests**

Run:
```bash
python3 -m pytest tests/vision/test_vision_providers.py avatar/tests/test_vision_pipeline.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add avatar/vision/providers.py avatar/mcp_server/tools/vision_tools.py tests/vision/test_vision_providers.py
git commit -m "feat: add explicit vision backend seam"
```

---

### Task 9: Add Real MCP SITL Smoke Test

**Files:**
- Create: `tests/e2e/test_mcp_sitl_smoke.py`
- Modify: `tests/e2e/conftest.py` only if marker behavior needs reuse

- [ ] **Step 1: Write the SITL-required smoke test**

Create `tests/e2e/test_mcp_sitl_smoke.py`:
```python
import os
import sys
from pathlib import Path

import pytest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover
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
            status = await session.call_tool("get_status", {})
            assert status.content

            telemetry = await session.call_tool("get_telemetry", {})
            assert telemetry.content

            takeoff = await session.call_tool("arm_and_takeoff", {"altitude_m": 5.0})
            assert takeoff.content

            hold = await session.call_tool("hold", {"duration_s": 2.0})
            assert hold.content

            land = await session.call_tool("land", {})
            assert land.content
```

- [ ] **Step 2: Run without SITL and verify it skips**

Run:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q
```

Expected:
```text
1 skipped
```

- [ ] **Step 3: Run with SITL after starting PX4**

In terminal 1:
```bash
cd PX4-Autopilot
make px4_sitl gz_x500
```

In terminal 2:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```

Expected after Tasks 1-7 are complete and PX4 SITL is healthy:
```text
1 passed
```

- [ ] **Step 4: If the test fails because PX4 has no GPS/home yet, keep the failure and capture logs**

Run:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl -vv
```

Expected: either PASS or a concrete failure message from MAVSDK/PX4 health checks. Do not mark SITL ready until this passes.

- [ ] **Step 5: Commit**

Run:
```bash
git add tests/e2e/test_mcp_sitl_smoke.py
git commit -m "test: add MCP-driven SITL smoke mission"
```

---

### Task 10: Fix Cinematic Shot Connection API Before Re-Enabling Claims

**Files:**
- Modify: `avatar/mcp_server/tools/cinematic_shots.py`
- Test: `tests/test_cinematic_shots.py`

- [ ] **Step 1: Write a focused regression test for disconnected cinematic execution**

Append to `tests/test_cinematic_shots.py`:
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

        raw = await execute_cinematic_shot(
            template_name="orbit_close",
            target_lat=37.0,
            target_lon=-122.0,
        )

    data = json.loads(raw)
    assert data["success"] is False
    assert data["error"] == "Drone not connected"
```

- [ ] **Step 2: Run test and verify failure**

Run:
```bash
python3 -m pytest tests/test_cinematic_shots.py::test_execute_cinematic_shot_handles_missing_drone_without_unawaited_coroutine -q
```

Expected: FAIL because `get_drone()` is not awaited and `get_telemetry_cache()` does not exist.

- [ ] **Step 3: Fix async call and telemetry cache lookup**

In `avatar/mcp_server/tools/cinematic_shots.py`, replace:
```python
cm = ConnectionManager()
drone = cm.get_drone()
cache = cm.get_telemetry_cache()

if not drone or not cache:
    return json.dumps({
        "success": False,
        "error": "Drone not connected"
    })
```

With:
```python
cm = ConnectionManager()
drone = await cm.get_drone()
cache = get_telemetry_cache()

if not drone:
    return json.dumps({
        "success": False,
        "error": "Drone not connected"
    })

if not cache:
    return json.dumps({
        "success": False,
        "error": "Telemetry cache not available"
    })
```

Import `get_telemetry_cache` from flight tools:
```python
from avatar.mcp_server.tools.flight_tools import set_velocity, get_telemetry_cache
```

- [ ] **Step 4: Run cinematic focused tests**

Run:
```bash
python3 -m pytest tests/test_cinematic_shots.py::test_execute_cinematic_shot_handles_missing_drone_without_unawaited_coroutine -q
```

Expected:
```text
1 passed
```

- [ ] **Step 5: Commit**

Run:
```bash
git add avatar/mcp_server/tools/cinematic_shots.py tests/test_cinematic_shots.py
git commit -m "fix: use valid async connection APIs in cinematic shots"
```

---

### Task 11: Truthful Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/analysis/mcp_standards_audit.md`
- Modify: `docs/analysis/safety_architecture_gaps.md`

- [ ] **Step 1: Update README Phase 0.5 language**

Replace any “Phase 0.5 complete / all software validated” wording with:
```markdown
### Phase 0.5A: MCP-Controlled SITL Flight Spine

Current verification target:
- MCP server starts through the real stdio protocol.
- Tools can be discovered through MCP.
- Core flight tools route through shared server-owned state.
- PX4 SITL smoke mission passes with `tests/e2e/test_mcp_sitl_smoke.py --run-sitl`.

Mock-only components:
- Vision currently defaults to `mock_camera` and `mock_detector`.
- Gazebo camera frame ingestion and YOLO detector backends are planned after the MCP flight spine passes.

Run:
```bash
python3 -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```
```

- [ ] **Step 2: Update MCP audit status**

In `docs/analysis/mcp_standards_audit.md`, add at top:
```markdown
> 2026-04-13 update: Prior “Phase 0.5 complete” claims were not valid while MCP imports and routing were broken. Current readiness is gated by `tests/mcp_server/test_mcp_stdio_smoke.py` and `tests/e2e/test_mcp_sitl_smoke.py`.
```

- [ ] **Step 3: Update safety architecture status**

In `docs/analysis/safety_architecture_gaps.md`, add at top:
```markdown
> 2026-04-13 update: Guardian failsafes are considered implemented only when `AvatarMCPServer._handle_guardian_failsafe()` is wired and tested to call MAVSDK recovery actions. State-machine-only transitions do not count as physical failsafe execution.
```

- [ ] **Step 4: Run doc grep sanity check**

Run:
```bash
rg -n "Phase 0.5.*COMPLETE|SITL-Ready|all software validated|fully functional" README.md docs/analysis research/01-core-project
```

Expected: every remaining match is either historical context or explicitly qualified by current verification status.

- [ ] **Step 5: Commit**

Run:
```bash
git add README.md docs/analysis/mcp_standards_audit.md docs/analysis/safety_architecture_gaps.md
git commit -m "docs: align SITL readiness claims with verification"
```

---

### Task 12: Final Verification Matrix

**Files:**
- No code changes unless verification exposes a concrete bug.

- [ ] **Step 1: Compile critical modules**

Run:
```bash
python3 -m py_compile \
  avatar/mcp_server/server.py \
  avatar/mcp_server/tools/flight_tools.py \
  avatar/mcp_server/tools/tracking_tools.py \
  avatar/mcp_server/tools/cinematic_shots.py \
  avatar/mav/heartbeat_service.py \
  avatar/mav/guardian_async.py \
  avatar/mav/offboard_streamer.py \
  avatar/vision/providers.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run focused unit/integration tests**

Run:
```bash
python3 -m pytest \
  tests/mcp_server/test_server_offline_protocol.py \
  tests/mcp_server/test_server_flight_routing.py \
  tests/mcp_server/test_guardian_failsafe_actions.py \
  tests/mcp_server/test_mcp_stdio_smoke.py \
  tests/mav/test_offboard_streamer.py \
  tests/mav/test_heartbeat_service.py \
  tests/mav/test_guardian_async.py \
  avatar/tests/mav/test_px4_parameters.py \
  tests/vision/test_vision_providers.py \
  avatar/tests/test_vision_pipeline.py \
  -q
```

Expected: all selected tests pass or MCP SDK-dependent tests skip with a clear missing dependency reason.

- [ ] **Step 3: Run full collection**

Run:
```bash
python3 -m pytest --collect-only -q
```

Expected: collection succeeds. If it fails because `mavsdk` or `hypothesis` is missing, install project dev dependencies in the active environment or mark SITL/property tests to skip cleanly when dependencies are unavailable.

- [ ] **Step 4: Run full test suite where dependencies are installed**

Run:
```bash
python3 -m pytest -q
```

Expected: tests pass or SITL-required tests skip unless `--run-sitl` is supplied.

- [ ] **Step 5: Run SITL smoke test**

In terminal 1:
```bash
cd PX4-Autopilot
make px4_sitl gz_x500
```

In terminal 2:
```bash
python3 -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```

Expected:
```text
1 passed
```

- [ ] **Step 6: Commit final verification-only doc if needed**

If verification results require a status note, update `changes-made.md` with:
```markdown
## 2026-04-13 MCP SITL Flight Spine Verification

- MCP stdio smoke: PASS
- Focused unit/integration tests: PASS
- Full collection: PASS
- SITL MCP smoke mission: PASS
- Remaining mock-only subsystem: vision defaults to `mock_camera` and `mock_detector`
```

Then run:
```bash
git add changes-made.md
git commit -m "docs: record MCP SITL spine verification"
```

---

## Self-Review

**Spec coverage:**
- MCP import/startup blocker: Task 1.
- Server-owned FlightTools routing: Task 3.
- Actual MCP protocol, not internal shortcuts: Task 4 and Task 9.
- Guardian failsafes execute MAVSDK actions: Task 5.
- Heartbeat/offboard honesty: Task 6 and Task 7.
- Vision is important but not allowed to remain invisible mock plumbing: Task 8.
- Cinematic execution runtime API mismatch: Task 10.
- Documentation truthfulness: Task 11.
- Full verification matrix: Task 12.

**Placeholder scan:** The plan contains no `TBD`, no unspecified “add tests”, and no vague “handle edge cases” steps. Each implementation task includes concrete file paths, code snippets, commands, and expected results.

**Type consistency:** `AvatarMCPServerConfig.connect_on_start`, `AvatarMCPServerConfig.from_env()`, `AvatarMCPServer._handle_guardian_failsafe()`, `OffboardVelocityStreamer.stream_for()`, `VisionBackendConfig`, `MockCameraProvider`, and `MockDetectorProvider` are introduced before later tasks reference them.

