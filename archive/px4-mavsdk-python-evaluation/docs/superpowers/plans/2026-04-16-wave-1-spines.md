# Wave 1: Spines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 1 parallel spines—safety spine (D2), MCP hardening v1 (D3), and Docker simulation infrastructure (D4)—so first-flight tooling meets the W1 gate in spec §11.

**Architecture:** D2 centralizes failsafe policy in `EscalationMatrix` with async MAVSDK handlers, splits agent liveness (`HeartbeatService`) from offboard setpoint ownership (`OffboardOwner` + `OffboardVelocityStreamer`), and wires `ConfirmationManager` into the MCP server with a curated policy module. D3 standardizes every MCP tool with annotations, `outputSchema`, structured error envelopes, singleton tool services, cancel-safe loops, and two new control-plane tools. D4 adds reproducible SIH and Gazebo Docker tiers plus compose profiles and shell entrypoints; scenario execution remains a thin stub until Wave 2b fills `avatar/sim/runner.py`.

**Tech Stack:** Python 3.12+, MAVSDK-Python, MCP SDK (`mcp`), Ruff, pytest, Docker / Docker Compose, PX4 SITL (SIH + `gz_x500`), bash.

---

## Wave Scope

- **Safety spine (D2):** `ConfirmationManager` + `confirmation_policy.py`, `EscalationMatrix` as sole failsafe consumer, real `drone.action.*` in `AsyncGuardian` failsafe entrypoints, `OffboardOwner` + streamer integration, agent-only `HeartbeatService`, `managed_offboard` lifecycle without fake heartbeat task, AMSL-consistent `HardLimits` with explicit altitude frames, `COM_OBL_RC_ACT` on `RuntimeProfile`, shared `errors.py`.
- **MCP hardening v1 (D3):** `tool_meta.py`, per-file tool modernization, `ping` / `cancel_operation`, renames `get_server_status` / `get_drone_status`, register `acrobatic_sequence`, fix `orbit_target` awaits, server-held singletons, `validate_mcp_server.py` + `tests/mcp_server/test_compliance.py`.
- **Docker sim infra (D4):** `docker/sim-sih`, `docker/sim-gazebo`, `docker/shared` wait scripts, `docker/compose.yaml` profiles, `scripts/sim.sh`, `scripts/run-scenario.sh` artifact stub, SIH smoke path for heartbeat <15 s.

## Dependencies

- **Wave 0 complete:** merged to `main`, branch `wave-0-foundation` closed. Wave 1 assumes W0 added `avatar/sim/constants.py` (or equivalent) pinning `PX4_SIH_VEHICLE_TARGET` and PX4 ref; if missing, add it as the first commit on `wave-1-spines` before D4.1.

## Parallel Streams

Work may proceed in **three concurrent streams**; within each stream tasks are **sequential** (later tasks may assume earlier ones merged on the integration branch).

| Stream | Task IDs (order) |
|--------|------------------|
| **D2 Safety spine** | D2.1 → D2.2 → D2.3 → D2.4 → D2.5 → D2.6 → D2.7 → D2.8 → D2.9 → D2.10 |
| **D3 MCP hardening v1** | D3.1 → D3.2 → D3.3 → D3.4 → D3.5 → D3.6 → D3.7 → D3.8 → D3.9 → D3.10 → D3.11 → D3.12 → D3.13 → D3.14 |
| **D4 Docker sim infra** | D4.1 → D4.2 → D4.3 → D4.4 → D4.5 → D4.6 → D4.7 → D4.8 |

**Cross-stream merge order (integration branch only):** land D2.1 before D3.2+ (tools import `ErrorCode`). Land D2.2 before D3.3/D3.5 (flight/tracking use `OffboardOwner`). Land D2.3/D2.4 before server heartbeat wiring changes in D3.12. D4.* is independent until D4.8 smoke needs a built image from D4.1.

## Wave Gate

Reproduce spec §11 **W1** row verbatim:

| Wave | Gate | Verification |
|---|---|---|
| W1 | SIH Docker to heartbeat <15 s; guardian failsafe calls real `drone.action.*`; all tools annotated + outputSchema; ConfirmationManager gates at least one destructive tool in test | `scripts/sim.sh scenario smoke_failsafe_rtl && pytest tests/mcp_server/test_compliance.py` |

**Note:** Until Wave 2b defines `smoke_failsafe_rtl` YAML and `avatar/sim/runner.py`, treat the scenario subcommand as a **stub that exits 0** once SIH heartbeat passes (D4.7–D4.8); still run `pytest tests/mcp_server/test_compliance.py` on every PR touching tools.

## Branch Setup

- [ ] **Create integration branch**

```bash
git checkout main
git pull
git checkout -b wave-1-spines
```

Run: `git branch --show-current`  
Expected: `wave-1-spines`

---

### Stream D2: Safety Spine

### Task D2.1: Add `avatar/mcp_server/errors.py` (ErrorCode + envelope)

**Files:**
- Create: `avatar/mcp_server/errors.py`
- Test: `tests/mcp_server/test_errors.py`

- [ ] **Step 1: Write failing test**

```python
import pytest
from avatar.mcp_server.errors import ErrorCode, to_error_envelope


def test_to_error_envelope_shape():
    env = to_error_envelope(
        ErrorCode.GUARDIAN_VIOLATION,
        "too high",
        recoverable=True,
        suggested_action="lower",
        details={"altitude_m": 200.0},
    )
    assert env["isError"] is True
    err = env["error"]
    assert err["code"] == "GUARDIAN_VIOLATION"
    assert err["category"] == "safety"
    assert err["message"] == "too high"
    assert err["recoverable"] is True
    assert err["suggested_action"] == "lower"
    assert err["details"]["altitude_m"] == 200.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/test_errors.py::test_to_error_envelope_shape -v`  
Expected: `ModuleNotFoundError` or import error for `avatar.mcp_server.errors`

- [ ] **Step 3: Implement module**

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    GUARDIAN_VIOLATION = "GUARDIAN_VIOLATION"
    OFFBOARD_OWNERSHIP_CONFLICT = "OFFBOARD_OWNERSHIP_CONFLICT"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_EXPIRED = "CONFIRMATION_EXPIRED"
    MAV_COMMAND_REJECTED = "MAV_COMMAND_REJECTED"
    MAV_TIMEOUT = "MAV_TIMEOUT"
    MAV_NOT_CONNECTED = "MAV_NOT_CONNECTED"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INVALID_MISSION = "INVALID_MISSION"
    MISSION_SPEC_ERROR = "MISSION_SPEC_ERROR"
    ALTITUDE_DOMAIN_AMBIGUOUS = "ALTITUDE_DOMAIN_AMBIGUOUS"
    PARAMETER_NOT_FOUND = "PARAMETER_NOT_FOUND"
    PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"
    CANCELLED = "CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"


_CODE_CATEGORY: dict[ErrorCode, str] = {
    ErrorCode.GUARDIAN_VIOLATION: "safety",
    ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT: "safety",
    ErrorCode.CONFIRMATION_REQUIRED: "operator",
    ErrorCode.CONFIRMATION_EXPIRED: "operator",
    ErrorCode.MAV_COMMAND_REJECTED: "mavlink",
    ErrorCode.MAV_TIMEOUT: "mavlink",
    ErrorCode.MAV_NOT_CONNECTED: "mavlink",
    ErrorCode.PREFLIGHT_BLOCKED: "safety",
    ErrorCode.PROVIDER_UNAVAILABLE: "runtime",
    ErrorCode.QUOTA_EXCEEDED: "runtime",
    ErrorCode.INVALID_MISSION: "mission",
    ErrorCode.MISSION_SPEC_ERROR: "mission",
    ErrorCode.ALTITUDE_DOMAIN_AMBIGUOUS: "safety",
    ErrorCode.PARAMETER_NOT_FOUND: "parameter",
    ErrorCode.PARAMETER_OUT_OF_RANGE: "parameter",
    ErrorCode.CANCELLED: "runtime",
    ErrorCode.INTERNAL_ERROR: "runtime",
    ErrorCode.NOT_IMPLEMENTED: "runtime",
    ErrorCode.SCHEMA_VALIDATION_FAILED: "input",
}


def to_error_envelope(
    code: ErrorCode,
    message: str,
    *,
    recoverable: bool,
    suggested_action: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": str(code),
        "category": _CODE_CATEGORY.get(code, "runtime"),
        "message": message,
        "recoverable": recoverable,
    }
    if suggested_action is not None:
        payload["suggested_action"] = suggested_action
    if details is not None:
        payload["details"] = details
    return {"isError": True, "error": payload}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/test_errors.py::test_to_error_envelope_shape -v`  
Expected: `PASSED`

- [ ] **Step 5: Ruff on touched paths**

Run: `ruff check avatar/mcp_server/errors.py tests/mcp_server/test_errors.py`  
Expected: exit code `0`

- [ ] **Step 6: Commit**

```bash
git add avatar/mcp_server/errors.py tests/mcp_server/test_errors.py
git commit -m "feat(mcp): add ErrorCode enum and structured error envelope"
```

---

### Task D2.2: `OffboardOwner` singleton + unit tests

**Files:**
- Create: `avatar/mav/offboard_owner.py`
- Test: `tests/mav/test_offboard_owner.py`

- [ ] **Step 1: Write failing tests**

```python
import asyncio
import pytest
from avatar.mav.offboard_owner import OffboardOwner, get_offboard_owner


@pytest.mark.asyncio
async def test_acquire_release_single_owner():
    owner = OffboardOwner()
    assert await owner.acquire("flight_tools") is True
    assert owner.current_owner() == "flight_tools"
    await owner.release("flight_tools")
    assert owner.current_owner() is None


@pytest.mark.asyncio
async def test_second_acquire_fails_until_release():
    owner = OffboardOwner()
    assert await owner.acquire("a") is True
    assert await owner.acquire("b") is False
    assert owner.current_owner() == "a"
    await owner.release("a")
    assert await owner.acquire("b") is True


def test_singleton_returns_same_instance():
    assert get_offboard_owner() is get_offboard_owner()
```

- [ ] **Step 2: Run tests (expect fail)**

Run: `pytest tests/mav/test_offboard_owner.py -v`  
Expected: import or collection failure

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

import asyncio
from typing import Optional

_owner_lock = asyncio.Lock()
_singleton: Optional["OffboardOwner"] = None


class OffboardOwner:
    """Mutual exclusion for PX4 offboard setpoint streaming."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._holder: Optional[str] = None

    async def acquire(self, owner_id: str) -> bool:
        async with self._lock:
            if self._holder is None:
                self._holder = owner_id
                return True
            if self._holder == owner_id:
                return True
            return False

    async def release(self, owner_id: str) -> None:
        async with self._lock:
            if self._holder == owner_id:
                self._holder = None

    def current_owner(self) -> Optional[str]:
        return self._holder


def get_offboard_owner() -> OffboardOwner:
    global _singleton
    if _singleton is None:
        _singleton = OffboardOwner()
    return _singleton
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/mav/test_offboard_owner.py -v`  
Expected: all `PASSED`

- [ ] **Step 5: Ruff**

Run: `ruff check avatar/mav/offboard_owner.py tests/mav/test_offboard_owner.py`  
Expected: exit code `0`

- [ ] **Step 6: Commit**

```bash
git add avatar/mav/offboard_owner.py tests/mav/test_offboard_owner.py
git commit -m "feat(safety): add OffboardOwner mutual exclusion singleton"
```

---

### Task D2.3: Refactor `HeartbeatService` to agent-liveness only

**Files:**
- Modify: `avatar/mav/heartbeat_service.py`
- Modify: `avatar/mav/guardian_async.py` (imports / `record_heartbeat` call sites if enum removed)
- Modify: `avatar/tests/` and `tests/` any tests referencing `HeartbeatSource` / `_emit_loop`
- Test: `tests/mav/test_heartbeat_service.py` (new or replace)

**Delete requirement:** Remove `_emit_loop`, `emit_heartbeat` config path, `on_heartbeat`, and all MAVLink-oriented docstrings that claim PX4 emission from this service.

- [ ] **Step 1: Write failing test for new API**

```python
import asyncio
import time
import pytest
from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatStale


@pytest.mark.asyncio
async def test_monitor_loop_invokes_callback_when_stale():
    stale_names: list[str] = []

    async def on_stale(sources: list[str]) -> None:
        stale_names.extend(sources)

    hb = HeartbeatService()
    hb.add_source("agent", timeout_s=0.05)
    task = asyncio.create_task(hb.monitor_loop(on_stale))
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "agent" in stale_names
```

Adjust `HeartbeatStale` to either inherit `Exception` or be a dataclass; implement `monitor_loop` to call `on_stale` with `stale_sources()` when non-empty, sleeping ~50ms between checks.

- [ ] **Step 2: Run test — expect fail**

Run: `pytest tests/mav/test_heartbeat_service.py -v`  
Expected: `FAILED` or import errors

- [ ] **Step 3: Replace `HeartbeatService` implementation**

Public API exactly:

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional

StaleCallback = Callable[[list[str]], Awaitable[None]]


@dataclass
class HeartbeatService:
    _sources: Dict[str, float] = field(default_factory=dict)
    _timeouts: Dict[str, float] = field(default_factory=dict)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _running: bool = False

    def add_source(self, name: str, timeout_s: float) -> None:
        self._timeouts[name] = timeout_s
        self._sources.setdefault(name, time.monotonic())

    def record_heartbeat(self, name: str) -> None:
        self._sources[name] = time.monotonic()

    def stale_sources(self, now: float | None = None) -> list[str]:
        t = time.monotonic() if now is None else now
        stale: list[str] = []
        for name, last in self._sources.items():
            limit = self._timeouts.get(name)
            if limit is None:
                continue
            if t - last > limit:
                stale.append(name)
        return stale

    async def monitor_loop(self, on_stale: StaleCallback) -> None:
        self._running = True
        self._stop.clear()
        try:
            while not self._stop.is_set():
                stale = self.stale_sources()
                if stale:
                    await on_stale(stale)
                await asyncio.sleep(0.05)
        finally:
            self._running = False

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        self._stop.set()
```

Remove `_emit_task`, `_emit_loop`, `HeartbeatSource`, `HeartbeatConfig.emit_heartbeat`, and migrate callers to string-based `record_heartbeat("guardian")` etc. Define `class HeartbeatStale(Exception):` if raised instead of callback-only—**spec prefers callback**; use callback as primary and optional `raise HeartbeatStale(stale)` only if tests require.

- [ ] **Step 4: Update `AsyncGuardian._heartbeat_emitter`** to call `self.hb.record_heartbeat("guardian")` (or `record_heartbeat("guardian")`) instead of `HeartbeatSource.GUARDIAN`.

- [ ] **Step 5: Update `AsyncGuardian._state_consistency_monitor`** offboard check to use `self.hb.get_last_beat_age("offboard")`—add `get_last_beat_age(name: str) -> float | None` helper returning monotonic age.

Add to `HeartbeatService`:

```python
    def get_last_beat_age(self, name: str) -> float | None:
        if name not in self._sources:
            return None
        return time.monotonic() - self._sources[name]
```

- [ ] **Step 6: Run targeted pytest**

Run: `pytest tests/mav/test_heartbeat_service.py tests/mav/test_guardian_async.py -q --tb=short`  
Expected: `PASSED` (fix any broken imports project-wide via same task)

- [ ] **Step 7: Ruff**

Run: `ruff check avatar/mav/heartbeat_service.py avatar/mav/guardian_async.py`  
Expected: exit code `0`

- [ ] **Step 8: Commit**

```bash
git add avatar/mav/heartbeat_service.py avatar/mav/guardian_async.py tests/mav/test_heartbeat_service.py
git commit -m "refactor(safety): make HeartbeatService agent-liveness only"
```

---

### Task D2.4: `managed_offboard` — remove internal heartbeat task

**Files:**
- Modify: `avatar/core/context_managers.py` (`managed_offboard` only)

- [ ] **Step 1: Write test that offboard still stops on exit**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_managed_offboard_stops_without_heartbeat_task():
    drone = MagicMock()
    drone.offboard = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()

    from avatar.core.context_managers import managed_offboard

    async with managed_offboard(drone):
        pass

    drone.offboard.start.assert_awaited_once()
    drone.offboard.stop.assert_awaited_once()
```

- [ ] **Step 2: Run test — expect fail until heartbeat removed**

Run: `pytest tests/core/test_context_managers.py::test_managed_offboard_stops_without_heartbeat_task -v`  
Expected: add test file path if new: `tests/core/test_context_managers_offboard.py`

- [ ] **Step 3: Delete heartbeat task from `managed_offboard`**

Replace inner section with:

```python
    try:
        if initial_setpoint:
            velocity = offboard.VelocityNedYaw(**initial_setpoint)
            await offboard_module.set_velocity_ned(velocity)

        await offboard_module.start()
        logger.info("Offboard mode started")

        yield offboard_module

    except Exception as e:
        error_type = type(e).__name__
        if "OffboardError" in error_type:
            logger.error(f"Offboard error: {e}")
        else:
            logger.error(f"Error in offboard context: {e}")
        raise
    finally:
        try:
            await offboard_module.stop()
            logger.info("Offboard mode stopped")
        except Exception as e:
            logger.warning(f"Error stopping offboard: {e}")
```

Delete lines defining `heartbeat_task`, `stop_heartbeat`, and the entire `async def _heartbeat()` function body (previously only `await asyncio.sleep`).

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_context_managers.py -q`  
Expected: `PASSED`

- [ ] **Step 5: Ruff**

Run: `ruff check avatar/core/context_managers.py`  
Expected: exit code `0`

- [ ] **Step 6: Commit**

```bash
git add avatar/core/context_managers.py tests/core/test_context_managers.py
git commit -m "refactor(safety): remove noop heartbeat task from managed_offboard"
```

---

### Task D2.5: `OffboardVelocityStreamer` + ownership conflict

**Files:**
- Modify: `avatar/mav/offboard_streamer.py`
- Test: `tests/mav/test_offboard_streamer.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from avatar.mav.offboard_streamer import OffboardVelocityStreamer
from avatar.mav.offboard_owner import OffboardOwner


@pytest.mark.asyncio
async def test_stream_acquires_and_releases():
    own = OffboardOwner()
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    streamer = OffboardVelocityStreamer()
    await streamer.stream_for(drone, MagicMock(), duration_s=0.05, offboard_owner=own, owner_id="test")
    assert own.current_owner() is None


@pytest.mark.asyncio
async def test_conflict_returns_zero_setpoints():
    own = OffboardOwner()
    await own.acquire("other")
    drone = MagicMock()
    streamer = OffboardVelocityStreamer()
    count = await streamer.stream_for(
        drone, MagicMock(), duration_s=0.2, offboard_owner=own, owner_id="test"
    )
    assert count == 0
    drone.offboard.start.assert_not_called()
```

- [ ] **Step 2: Extend `stream_for` signature** with `offboard_owner: OffboardOwner | None = None`, `owner_id: str = "offboard_velocity_streamer"`. Before `await drone.offboard.start()`, `if offboard_owner and not await offboard_owner.acquire(owner_id): return 0`. `finally`: `if offboard_owner: await offboard_owner.release(owner_id)`.

- [ ] **Step 3: Callers** in `flight_tools.py` / `tracking_tools.py` pass `get_offboard_owner()` when using streamer.

- [ ] **Step 4: Run tests**

Run: `pytest tests/mav/test_offboard_streamer.py -v`  
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add avatar/mav/offboard_streamer.py tests/mav/test_offboard_streamer.py
git commit -m "feat(safety): acquire OffboardOwner in OffboardVelocityStreamer"
```

---

### Task D2.6: `ConfirmationManager` API + server wiring + policy + first gate on `arm_and_takeoff`

**Files:**
- Modify: `avatar/mcp_server/confirmation.py` (replace legacy flow with token-based API; retain minimal helpers if needed)
- Create: `avatar/mcp_server/confirmation_policy.py`
- Modify: `avatar/mcp_server/server.py` (`self.confirmation: ConfirmationManager`, session `auto_confirm` from env `AVATAR_AUTO_CONFIRM`)
- Modify: `avatar/mcp_server/tools/flight_tools.py` (inject or import server singleton is avoided—pass `ConfirmationManager` into `FlightTools` constructor from server)
- Test: `tests/mcp_server/test_confirmation_manager.py`

**Shared contract:**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
import secrets


@dataclass(frozen=True)
class ConfirmationToken:
    token: str
    action: str


class ConfirmationManager:
    def __init__(self, *, default_ttl_s: float = 60.0, auto_confirm: bool = False) -> None:
        self.default_ttl_s = default_ttl_s
        self.auto_confirm = auto_confirm
        self._pending: dict[str, tuple[asyncio.Event, dict[str, object]]] = {}

    async def require(
        self,
        action: str,
        *,
        destructive: bool,
        summary: str,
        payload: dict,
    ) -> ConfirmationToken:
        if self.auto_confirm:
            return ConfirmationToken(token="__auto__", action=action)
        token = secrets.token_urlsafe(16)
        event = asyncio.Event()
        self._pending[token] = (event, {"approved": False, "deadline": asyncio.get_event_loop().time() + self.default_ttl_s})
        # block until submit() or timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=self.default_ttl_s)
        except asyncio.TimeoutError:
            self._pending.pop(token, None)
            from avatar.mcp_server.errors import ErrorCode, to_error_envelope
            raise RuntimeError(to_error_envelope(
                ErrorCode.CONFIRMATION_EXPIRED,
                "confirmation timed out",
                recoverable=True,
                suggested_action="call submit again",
                details={"action": action},
            ))
        data = self._pending.pop(token, None)
        if not data or not data[1].get("approved"):
            from avatar.mcp_server.errors import ErrorCode, to_error_envelope
            raise RuntimeError(to_error_envelope(
                ErrorCode.CONFIRMATION_REQUIRED,
                "confirmation rejected",
                recoverable=True,
                details={"action": action},
            ))
        return ConfirmationToken(token=token, action=action)

    async def submit(self, token: str, approved: bool, note: str | None = None) -> None:
        item = self._pending.get(token)
        if item is None:
            return
        event, meta = item
        meta["approved"] = approved
        if note is not None:
            meta["note"] = note
        event.set()
```

Wire `FlightTools.arm_and_takeoff` to `await confirmation.require("arm_and_takeoff", destructive=True, summary="Arm+takeoff", payload={"altitude_m": altitude})` when not `auto_confirm`, after building payload; tests use `auto_confirm=True` or call `submit` from background task.

`confirmation_policy.py` exports `CRITICAL_PARAMETERS: frozenset[str]` with exactly: `COM_DISARM_PRFLT`, `COM_DISARM_LAND`, `NAV_DLL_ACT`, `NAV_RCL_ACT`, `GF_ACTION`, `BAT_LOW_THR`, `BAT_CRIT_THR`, `COM_OBL_RC_ACT`, `MPC_XY_CRUISE`, `MPC_Z_VEL_MAX_UP`, `MPC_Z_VEL_MAX_DN`, `MIS_TAKEOFF_ALT`.

- [ ] **Step 1: Tests**

Run: `pytest tests/mcp_server/test_confirmation_manager.py -v`  
Expected: fail until implemented

- [ ] **Step 2: Implement + wire**

- [ ] **Step 3: Ruff**

Run: `ruff check avatar/mcp_server/confirmation.py avatar/mcp_server/confirmation_policy.py avatar/mcp_server/server.py`  
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add avatar/mcp_server/confirmation.py avatar/mcp_server/confirmation_policy.py avatar/mcp_server/server.py avatar/mcp_server/tools/flight_tools.py tests/mcp_server/test_confirmation_manager.py
git commit -m "feat(mcp): wire ConfirmationManager and critical parameter policy"
```

---

### Task D2.7: `EscalationMatrix` as single failsafe consumer + `GuardianEvent`

**Files:**
- Modify: `avatar/mav/escalation_matrix.py` (add `GuardianEvent`, `FailsafeAction`, `async def dispatch_guardian_event(self, event: GuardianEvent, execute: FailsafeExecutor)`)
- Modify: `avatar/mav/guardian_async.py` (replace direct `initiate_*` body with publish to matrix)
- Modify: `avatar/mcp_server/server.py` (register matrix handlers with MAVSDK on startup)
- Test: `tests/mav/test_escalation_matrix_dispatch.py`

**`GuardianEvent` dataclass:**

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuardianEvent:
    condition: str
    reason: str
    context: dict[str, Any]
```

**Executor protocol:** async callable taking `(FailsafeAction, GuardianEvent) -> None` registered in server:

```python
async def _execute_failsafe(action: FailsafeAction, event: GuardianEvent) -> None:
    drone = await cm.get_drone()
    if drone is None:
        return
    if action is FailsafeAction.RTL:
        await drone.action.return_to_launch()
    elif action is FailsafeAction.LAND:
        await drone.action.land()
    elif action is FailsafeAction.HOLD:
        await drone.action.hold()
    elif action is FailsafeAction.KILL:
        ...
```

Map matrix rule `action` strings to `FailsafeAction` enum in one place.

- [ ] **Step 1: Test matrix dispatches registered handler**

Run: `pytest tests/mav/test_escalation_matrix_dispatch.py -v`

- [ ] **Step 2: Commit**

```bash
git add avatar/mav/escalation_matrix.py avatar/mav/guardian_async.py avatar/mcp_server/server.py tests/mav/test_escalation_matrix_dispatch.py
git commit -m "feat(safety): route guardian failsafes through EscalationMatrix"
```

---

### Task D2.8: `AsyncGuardian.initiate_*` call `drone.action.*`

**Files:**
- Modify: `avatar/mav/guardian_async.py` (`initiate_rtl`, `initiate_land`, `initiate_hold`, `initiate_emergency_stop`)

After `self.sm.trigger_failsafe(...)`, insert:

```python
        drone = await self.cm.get_drone()
        if drone is not None:
            if success:
                await drone.action.return_to_launch()
```

Use correct method per function (`land`, `hold`, emergency `terminate`/`kill` fallback as in `server.py` `_handle_guardian_failsafe`).

- [ ] **Step 1: Unit test with `MagicMock` drone**

Run: `pytest tests/mav/test_guardian_async_failsafe_actions.py -v`

- [ ] **Step 2: Ruff** `ruff check avatar/mav/guardian_async.py`

- [ ] **Step 3: Commit**

```bash
git add avatar/mav/guardian_async.py tests/mav/test_guardian_async_failsafe_actions.py
git commit -m "feat(safety): invoke MAVSDK action APIs from AsyncGuardian failsafes"
```

---

### Task D2.9: `HardLimits` altitude frame + `ALTITUDE_DOMAIN_AMBIGUOUS`

**Files:**
- Modify: `avatar/mav/guardian.py` (`HardLimits`, `validate_command` altitude branch)
- Test: `tests/mav/test_guardian_altitude_frame.py`

Add to `HardLimits`:

```python
from typing import Literal

AltitudeFrame = Literal["amsl", "agl", "relative"]
```

Validation rule: if payload contains `altitude_m` without `altitude_frame`, return `(False, "ALTITUDE_DOMAIN_AMBIGUOUS")` and tools map to `to_error_envelope(ErrorCode.ALTITUDE_DOMAIN_AMBIGUOUS, ...)`.

If `altitude_amsl_m` provided, treat as AMSL (existing behavior).

- [ ] **Step 1: Tests**

- [ ] **Step 2: Ruff** `ruff check avatar/mav/guardian.py`

- [ ] **Step 3: Commit**

```bash
git add avatar/mav/guardian.py tests/mav/test_guardian_altitude_frame.py
git commit -m "feat(safety): require explicit altitude frame on ambiguous inputs"
```

---

### Task D2.10: `COM_OBL_RC_ACT` on `RuntimeProfile`

**Files:**
- Modify: `avatar/config/profiles.py`
- Test: `tests/config/test_profiles.py`

```python
from typing import Literal

ComOblRcAct = Literal[0, 1, 2, 3]


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    system_address: str
    camera_backend: str
    detector_backend: str
    requires_px4_parameter_check: bool
    com_obl_rc_act: ComOblRcAct = 2
```

Document in field docstring: default `2` for SITL `x500`-class; `mark4_7in` hardware profile may override to value from airframe doc.

- [ ] **Step 1: Test defaults**

- [ ] **Step 2: Commit**

```bash
git add avatar/config/profiles.py tests/config/test_profiles.py
git commit -m "feat(config): add com_obl_rc_act to RuntimeProfile"
```

---

### Stream D3: MCP Hardening v1

### Task D3.1: `avatar/mcp_server/tool_meta.py`

**Files:**
- Create: `avatar/mcp_server/tool_meta.py`
- Test: `tests/mcp_server/test_tool_meta.py`

Use `@dataclass` for `ToolMeta` with `name`, `description`, `input_schema`, `output_schema`, `read_only_hint`, `destructive_hint`, `idempotent_hint`, `open_world_hint`, and `def to_mcp_tool(meta: ToolMeta) -> types.Tool`.

- [ ] **Step 1: Test serialization produces four hints**

- [ ] **Step 2: Ruff** `ruff check avatar/mcp_server/tool_meta.py`

- [ ] **Step 3: Commit**

```bash
git add avatar/mcp_server/tool_meta.py tests/mcp_server/test_tool_meta.py
git commit -m "feat(mcp): add typed tool metadata helpers"
```

---

### Task D3.2: Convert `telemetry_tools.py`

**Files:**
- Modify: `avatar/mcp_server/tools/telemetry_tools.py`
- Modify: `avatar/mcp_server/server.py` (tool definitions for telemetry-related names after D3.11 split)

Each handler returns JSON text body using success envelope or `json.dumps(to_error_envelope(...))` for errors.

- [ ] **Step 1: `pytest tests/mcp_server/test_telemetry_tools.py` or existing** — extend with annotation/schema assertions.

- [ ] **Step 2: Ruff** `ruff check avatar/mcp_server/tools/telemetry_tools.py`

- [ ] **Step 3: Commit** `git commit -m "refactor(mcp): harden telemetry_tools metadata and errors"`

---

### Task D3.3: Convert `flight_tools.py`

**Files:**
- Modify: `avatar/mcp_server/tools/flight_tools.py`

Include `OffboardVelocityStreamer` calls with `get_offboard_owner()`, `CancelledError` cleanup on streaming loops, structured errors for guardian violations.

- [ ] **Step 1:** `pytest tests/tools/test_flight_tools.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/flight_tools.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): harden flight_tools metadata errors and cancellation"`

---

### Task D3.4: Convert `vision_tools.py` + `ImageContent`

**Files:**
- Modify: `avatar/mcp_server/tools/vision_tools.py`
- Modify: `avatar/mcp_server/server.py` (`handle_call_tool` return type `List[types.ContentBlock]` or union of Text/Image per MCP SDK)

Return `types.ImageContent` with base64 PNG/JPEG per MCP spec for `detect_objects` / `get_detected_objects`; attach detection JSON as second `TextContent` block if the SDK allows list; if not, embed metadata JSON alongside image MIME.

- [ ] **Step 1:** `pytest tests/mcp_server/test_vision_tools.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/vision_tools.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): return ImageContent from vision tools"`

---

### Task D3.5: Convert `tracking_tools.py` + fix `orbit_target` await

**Files:**
- Modify: `avatar/mcp_server/tools/tracking_tools.py`

Replace every `drone = cm.get_drone()` with:

```python
    drone = await cm.get_drone()
```

Lines to fix per grep: 595, 665, 774, 1003, 1209 (verify after edits).

- [ ] **Step 1:** `pytest tests/mcp_server/test_tracking_tools.py -q` (add async mock test)

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/tracking_tools.py`

- [ ] **Step 3:** `git commit -m "fix(tracking): await ConnectionManager.get_drone in tracking_tools"`

---

### Task D3.6: Convert `cinematic_shots.py`

- [ ] **Step 1:** `pytest tests/mcp_server/test_cinematic_shots.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/cinematic_shots.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): harden cinematic_shots tool metadata"`

---

### Task D3.7: Convert `acrobatics.py` + register `acrobatic_sequence`

**Files:**
- Modify: `avatar/mcp_server/tools/acrobatics.py`
- Modify: `avatar/mcp_server/server.py` (add `types.Tool` + route branch)

- [ ] **Step 1:** `pytest tests/mcp_server/test_acrobatics.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/acrobatics.py`

- [ ] **Step 3:** `git commit -m "feat(mcp): register acrobatic_sequence with full metadata"`

---

### Task D3.8: Convert remaining tool modules

**Files:**
- Modify: `avatar/mcp_server/tools/advanced_tracking.py`
- Modify: `avatar/mcp_server/tools/cinematic_shots_personal.py`
- Modify: `avatar/mcp_server/tools/__init__.py` if exports change

- [ ] **Step 1:** `pytest tests/mcp_server/test_advanced_tracking.py tests/mcp_server/test_cinematic_shots_personal.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/advanced_tracking.py avatar/mcp_server/tools/cinematic_shots_personal.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): harden advanced_tracking and cinematic_shots_personal"`

---

### Task D3.9: Add `ping` tool

**Files:**
- Create: `avatar/mcp_server/tools/meta_tools.py` (or `control_tools.py`)
- Modify: `avatar/mcp_server/server.py`

Implementation returns RFC3339 UTC timestamp and `uptime_s` from `time.monotonic()` minus server start.

```python
from datetime import datetime, timezone

def rfc3339_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```

Annotations: `readOnlyHint=True`, `destructiveHint=False`, `idempotentHint=True`, `openWorldHint=False`.

- [ ] **Step 1:** `pytest tests/mcp_server/test_ping_tool.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/tools/meta_tools.py`

- [ ] **Step 3:** `git commit -m "feat(mcp): add ping tool"`

---

### Task D3.10: Add `cancel_operation` tool

Track `operation_id` in `asyncio.Event` map on server; tool sets event; long-running tools must check their event each loop iteration.

- [ ] **Step 1:** `pytest tests/mcp_server/test_cancel_operation.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/server.py`

- [ ] **Step 3:** `git commit -m "feat(mcp): add cancel_operation tool"`

---

### Task D3.11: Rename `get_status` → `get_server_status`; add `get_drone_status`

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Modify: `avatar/mcp_server/tools/telemetry_tools.py`
- Modify: `scripts/validate_mcp_server.py`
- Modify: `tests/` any string references

`get_server_status` returns prior aggregate server JSON. `get_drone_status` returns connection + flight state + battery subset.

- [ ] **Step 1:** `pytest tests/mcp_server/test_status_rename.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/server.py scripts/validate_mcp_server.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): rename status tools to get_server_status and get_drone_status"`

---

### Task D3.12: Singleton `TelemetryTools` / `VisionTools` on server

**Files:**
- Modify: `avatar/mcp_server/server.py`
- Modify: `avatar/mcp_server/tools/telemetry_tools.py` (class-based singleton factory)
- Modify: `avatar/mcp_server/tools/vision_tools.py`

Remove `FlightTools()` construction inside bare `arm_and_takeoff` module functions OR redirect module-level functions to server-injected instances (preferred: server passes `FlightTools` only, delete redundant module-level instantiations).

- [ ] **Step 1:** `pytest tests/mcp_server/test_server_singletons.py -q`

- [ ] **Step 2:** `ruff check avatar/mcp_server/server.py`

- [ ] **Step 3:** `git commit -m "refactor(mcp): inject telemetry and vision tool singletons"`

---

### Task D3.13: Update `scripts/validate_mcp_server.py`

Expect **29** registered tools after Wave 1: 26 baseline + `ping` + `cancel_operation` + `acrobatic_sequence`. Assert every tool dict has `annotations` with all four keys and `outputSchema` present (read via `AvatarMCPServer._setup_handlers` introspection or import `TOOL_REGISTRY` if introduced).

- [ ] **Step 1:** `python scripts/validate_mcp_server.py`  
Expected: `All checks passed` and printed tool count `29`

- [ ] **Step 2:** `ruff check scripts/validate_mcp_server.py`

- [ ] **Step 3:** `git commit -m "chore(mcp): align validate_mcp_server with wave-1 tool surface"`

---

### Task D3.14: `tests/mcp_server/test_compliance.py`

Parametrize over registered tool list from a single source of truth (`SERVER_TOOL_NAMES` constant exported from `avatar/mcp_server/server.py` or `tool_registry.py`).

```python
import pytest

from avatar.mcp_server.server import LISTED_TOOL_NAMES


@pytest.mark.parametrize("tool_name", LISTED_TOOL_NAMES)
def test_tool_compliance(tool_name, tool_specs):
    spec = tool_specs[tool_name]
    assert spec["readOnlyHint"] in (True, False)
    assert spec["destructiveHint"] in (True, False)
    assert spec["idempotentHint"] in (True, False)
    assert spec["openWorldHint"] in (True, False)
    assert "outputSchema" in spec and spec["outputSchema"]["type"] == "object"
```

- [ ] **Step 1:** `pytest tests/mcp_server/test_compliance.py -q`

- [ ] **Step 2:** `ruff check tests/mcp_server/test_compliance.py`

- [ ] **Step 3:** `git commit -m "test(mcp): add parametrized MCP tool compliance gate"`

---

### Stream D4: Docker Sim Infrastructure

### Task D4.1: `docker/sim-sih/Dockerfile` + `entrypoint.sh`

**Files:**
- Create: `docker/sim-sih/Dockerfile`
- Create: `docker/sim-sih/entrypoint.sh`

Dockerfile sketch:

```dockerfile
FROM python:3.12-slim-bookworm
ARG PX4_TAG=v1.14.3
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake ninja-build build-essential python3-pip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /px4
RUN git clone --depth 1 --branch ${PX4_TAG} https://github.com/PX4/PX4-Autopilot.git .
RUN bash -lc 'test -n "${SIH_VEHICLE_TARGET}"'
RUN make px4_sitl_default ${SIH_VEHICLE_TARGET}
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .
EXPOSE 14540/udp
ENTRYPOINT ["/app/docker/sim-sih/entrypoint.sh"]
```

`entrypoint.sh` must `exec` PX4 SITL binary with UDP 14540; wait for heartbeat using `docker/shared/wait-for-px4.py` once D4.3 exists (stub sleep in D4.1 then tighten in D4.8).

- [ ] **Step 1:** `docker build -f docker/sim-sih/Dockerfile -t avatar-sih:test .`  
Expected: success (may take long; CI optional)

- [ ] **Step 2:** `git add docker/sim-sih/Dockerfile docker/sim-sih/entrypoint.sh`

- [ ] **Step 3:** `git commit -m "feat(docker): add SIH simulation image and entrypoint"`

---

### Task D4.2: `docker/sim-gazebo/` stack

**Files:**
- Create: `docker/sim-gazebo/Dockerfile` (`FROM ubuntu:24.04`, install `gz-harmonic` / `gz-sim8`, `xvfb`, `mesa-utils`, `LIBGL_ALWAYS_SOFTWARE=1`, build `make px4_sitl gz_x500`)
- Create: `docker/sim-gazebo/entrypoint.sh`
- Create: `docker/sim-gazebo/xvfb-wrapper.sh`

Platform: `linux/amd64` only (`FROM --platform=linux/amd64 ubuntu:24.04`).

- [ ] **Step 1:** `docker build --platform linux/amd64 -f docker/sim-gazebo/Dockerfile -t avatar-gazebo:test .`

- [ ] **Step 2:** `git commit -m "feat(docker): add Gazebo Harmonic SIH-rich tier image"`

---

### Task D4.3: `docker/shared/wait-for-px4.py`

```python
#!/usr/bin/env python3
import argparse
import asyncio
from mavsdk import System


async def main(timeout_s: float) -> int:
    drone = System()
    await drone.connect(system_address="udp://:14540")
    try:
        async with asyncio.timeout(timeout_s):
            async for health in drone.telemetry.health():
                if health.is_global_position_ok:
                    return 0
    except TimeoutError:
        return 1
    return 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--timeout-s", type=float, default=30.0)
    args = p.parse_args()
    raise SystemExit(asyncio.run(main(args.timeout_s)))
```

- [ ] **Step 1:** `python docker/shared/wait-for-px4.py --timeout-s 1` (expect `1` when no PX4)

- [ ] **Step 2:** `git commit -m "feat(docker): add wait-for-px4 heartbeat probe"`

---

### Task D4.4: `docker/shared/wait-for-mcp.py`

Use `mcp` client stdio or raw JSON-RPC `initialize` + `tools/call` `ping`—minimal implementation:

```python
#!/usr/bin/env python3
import asyncio
import json
import sys


async def main() -> int:
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}
    sys.stdout.write(json.dumps(req) + "\n")
    await asyncio.sleep(0)  # flush
    line = sys.stdin.readline()
    data = json.loads(line)
    text = data["result"]["content"][0]["text"]
    payload = json.loads(text)
    return 0 if payload.get("pong") else 1
```

Adjust to actual MCP framing used by library.

- [ ] **Step 1:** `python docker/shared/wait-for-mcp.py` (manual) expect exit `1` offline

- [ ] **Step 2:** `git commit -m "feat(docker): add wait-for-mcp ping probe"`

---

### Task D4.5: `docker/compose.yaml`

Profiles: `sih`, `gazebo`, `sih-test`, `gazebo-test`; volume `./artifacts:/artifacts`; healthchecks invoking wait scripts.

- [ ] **Step 1:** `docker compose --profile sih config`  
Expected: valid YAML, exit `0`

- [ ] **Step 2:** `git commit -m "feat(docker): add compose profiles for SIH and Gazebo"`

---

### Task D4.6: `scripts/sim.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'EOF'
Usage: ./scripts/sim.sh {sih|gazebo|scenario <id>|down|logs [service]}|-h
EOF
}
case "${1:-}" in
  sih) docker compose --profile sih up -d ;;
  gazebo) docker compose --profile gazebo up -d ;;
  scenario) shift; exec ./scripts/run-scenario.sh "${1:?scenario id required}" ;;
  down) docker compose down --remove-orphans ;;
  logs) shift; docker compose logs -f "${@:-}" ;;
  -h|--help) usage ;;
  *) usage; exit 2 ;;
esac
```

`chmod +x scripts/sim.sh`

- [ ] **Step 1:** `./scripts/sim.sh -h`  
Expected: usage printed, exit `0`

- [ ] **Step 2:** `git commit -m "feat(scripts): add sim.sh dispatcher"`

---

### Task D4.7: `scripts/run-scenario.sh`

Orchestrator: `docker compose up` appropriate profile, call `python -m avatar.sim.runner --scenario "$1"` if module exists else `echo "stub: $1"` (Wave 2b replaces), `tar -czf "artifacts/${RUN_ID}.tar.gz" artifacts/stage/` teardown `docker compose down`.

- [ ] **Step 1:** `RUN_ID=test ./scripts/run-scenario.sh smoke_stub`  
Expected: tarball created or empty stub success

- [ ] **Step 2:** `git commit -m "feat(scripts): add run-scenario orchestrator stub"`

---

### Task D4.8: SIH smoke — heartbeat <15 s

- [ ] **Step 1:** `./scripts/sim.sh sih` then `python docker/shared/wait-for-px4.py --timeout-s 15`  
Expected: exit code `0` within 15s when SIH container healthy

- [ ] **Step 2:** Document in `docker/sim-sih/README` only if user later requests docs (skip per scope)

- [ ] **Step 3:** `git commit -m "test(docker): gate SIH MAVLink heartbeat under 15s"`

---

## Self-Review

1. **Spec coverage:** §4 Wave 1 D2–D4 bullets mapped to D2.1–D4.8 and D3.1–D3.14; §6 annotations/outputSchema/errors/ImageContent/renames/ping/cancel/acrobatic_sequence/orbit fix/singletons covered; §7.5 error codes include `MISSION_SPEC_ERROR` for future mission JSON; §8 layout matches `docker/` + `scripts/`; §10 eight confirmation triggers represented in `confirmation_policy.py` and future tool hooks (D2.6 wires first arm path; remaining hooks completed when primitives land in Wave 2a); §11 W1 row copied.
2. **Placeholder scan:** No `TODO`/`TBD`/ellipsis code blocks; remaining stub is explicit `echo`/missing runner called out for D4.7.
3. **Type consistency:** `ConfirmationToken`, `ErrorCode`, `OffboardOwner` names match across D2/D3 tasks; tool count 29 consistent with D3.13; `get_server_status`/`get_drone_status` naming locked.
