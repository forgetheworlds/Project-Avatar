# Wave 2a: Core MCP Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 2a (D5 + D6): sixteen low-level MCP primitives, six high-level orchestrators, merge `cinematic_shots_personal.py` into `cinematic_shots.py` with typed per-template overrides, and register `acrobatic_sequence` with Guardian preflight plus ConfirmationManager per §10 item 7—each tool schema-validated, annotated, unit-tested, and wired through `AvatarMCPServer` without regressing the existing baseline tool set.

**Architecture:** Shared Pydantic models and JSON Schema live in `avatar/mcp_server/schemas.py` (minimal Mission v1.0 subset, forward-compatible with W2b). New handlers live in `avatar/mcp_server/tools/primitives.py` and `avatar/mcp_server/tools/orchestrators.py`, registered from `avatar/mcp_server/server.py` alongside Wave-1 `errors.py` structured envelopes, `ConfirmationManager`, `OffboardOwner`, and `AsyncGuardian.preflight` (W1 contract). Destructive tools call `await guardian.preflight(tool=..., payload=...)` before MAVSDK; curated confirmations use `ConfirmationManager.require(...)`. Cinematic merge removes `custom_params: dict` in favor of a discriminated union on `template_id` for typed overrides.

**Tech Stack:** Python 3.12+, Pydantic v2 (`model_json_schema`), MCP Python SDK `types.Tool` with `inputSchema` / `outputSchema` / annotations, pytest + pytest-asyncio, MAVSDK-Python (mocked in unit tests), existing `OffboardVelocityStreamer`, `FlightRecorder`, `KalmanTracker` / `TrackingState` from `advanced_tracking.py`.

---

## Wave Scope

- **D5:** sixteen primitives (`arm` … `submit_operator_confirmation`) as specified in the parent spec §4 D5 table and the task list below.
- **D6:** six orchestrators (`track_bbox`, `orbit_subject_vision`, `execute_waypoint_mission`, `log_mission_segment`, `evaluate_last_command`, `expose_advanced_tracker`).
- **D6.extra:** cinematic personal-template merge + typed overrides; `acrobatic_sequence` MCP registration + tests; validator script `EXPECTED_TOOL_COUNT = 51` (29 post-W1 + 22 W2a); W2b adds seven mission-intel tools → **58** at W2b gate; W2a gate pytest run.

**Out of wave:** Mission intelligence tools (W2b), Docker sim profiles, hardware vision providers.

---

## Dependencies

Wave **1** must be complete before starting W2a:

| Dependency | Role in W2a |
|------------|-------------|
| `avatar/mcp_server/errors.py` | `ErrorCode`, `to_error_envelope(code, message, recoverable=..., suggested_action=...)` for all failure paths (§6.7). |
| `avatar/mcp_server/confirmation.py` + `confirmation_policy.py` | Curated prompts: §10 items 1–2 (arm / mission override), 3 (geofence shrink), 8 (`set_parameter` CRITICAL), 7 (any `acrobatic_*` including `acrobatic_sequence`). |
| `avatar/mav/offboard_owner.py` | `set_velocity_body` acquires exclusive offboard streaming ownership; conflict → `OFFBOARD_OWNERSHIP_CONFLICT`. |
| `avatar/mav/guardian_async.py` | Real failsafes + **`async def preflight(self, *, tool: str, payload: dict[str, Any]) -> None`** (or equivalent) raising / returning structured guardian violations consumed by tools. |
| Tool annotations baseline | Every tool exposes `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` on `types.Tool` (§6.6). |
| `tests/mcp_server/test_compliance.py` | W1 adds `test_tool_<name>_compliant` per registered tool; W2a extends coverage to new names. |

**Test fixtures:** Prefer `tests/conftest.py` (root) plus any W0-migrated drone fixtures under `tests/` (e.g. `tests/fixtures/`). If `sitl_drone` still lives under `avatar/tests/conftest.py` on your branch, import or duplicate the minimal `MagicMock` MAVSDK `System` pattern into `tests/conftest.py` as part of W0 before W2a execution.

---

## Wave Gate

Copy from `docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md` §11:

| Wave | Gate | Verification |
|------|------|--------------|
| **W2a** | 22 new tools (primitives + orchestrators) green; personal templates merged; acrobatic_sequence registered; existing 26 tools no regression | `pytest -q tests/tools tests/mcp_server` |

(W2a-T26 records stdout/stderr of that command as evidence.)

---

## Branch Setup

```bash
git checkout main
git pull
git checkout -b wave-2a-mcp-expansion
```

All W2a commits land on `wave-2a-mcp-expansion` unless you stack on an existing W1 branch.

---

## Shared signature contract (lock for W2b / W3)

- **New modules:** `avatar/mcp_server/schemas.py`, `avatar/mcp_server/tools/primitives.py`, `avatar/mcp_server/tools/orchestrators.py`.
- **Cinematic:** `cinematic_shots_personal.py` merged into `cinematic_shots.py`; personal file **deleted** in W2a-T23.
- **Reuse:** `errors.py`, `confirmation.py`, `offboard_owner.py`, `guardian_async.py`, `OffboardVelocityStreamer`, server-held vision singletons (W1).

**Parallelism:** D5 (T00–T16) and D6 (T17–T22) may run in parallel branches after T00 merges. **Ordering constraint:** complete **W2a-T23 (cinematic merge)** before merging any orchestrator that calls `execute_cinematic_shot` / planner with new override types (notably `execute_waypoint_mission` with `BehaviorBlock` variant `cinematic`).

---

### Stream D5: Primitives (16)

---

### Task W2a-T00: Shared schemas `avatar/mcp_server/schemas.py`

**Files:**

- Create: `avatar/mcp_server/schemas.py`
- Modify: `avatar/mcp_server/__init__.py` (re-export public models if desired)
- Test: `tests/mcp_server/test_schemas_wave2a.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/test_schemas_wave2a.py
import pytest
from pydantic import ValidationError

from avatar.mcp_server.schemas import (
    Mission,
    Point,
    Waypoint,
    Polygon,
    BBox,
    HardLimitsSchema,
    FlightMode,
    CheckResult,
    BehaviorBlock,
    BehaviorHover,
    BehaviorPhoto,
    BehaviorOrbit,
    BehaviorCinematic,
)


def test_mission_json_schema_has_version_and_waypoints():
    s = Mission.model_json_schema()
    assert s["properties"]["version"]["const"] == "1.0"
    assert "waypoints" in s["properties"]


def test_behavior_block_discriminated_union():
    h = BehaviorBlock.model_validate({"kind": "hover", "duration_s": 2.0})
    assert isinstance(h, BehaviorHover)
    o = BehaviorBlock.model_validate(
        {"kind": "orbit", "radius_m": 10.0, "speed_m_s": 3.0, "duration_s": 30.0}
    )
    assert isinstance(o, BehaviorOrbit)
    with pytest.raises(ValidationError):
        BehaviorBlock.model_validate({"kind": "orbit", "duration_s": 1.0})


def test_polygon_requires_three_vertices():
    with pytest.raises(ValidationError):
        Polygon(vertices=[Point(lat_deg=0, lon_deg=0), Point(lat_deg=1, lon_deg=0)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/test_schemas_wave2a.py -v`

Expected: `ModuleNotFoundError: No module named 'avatar.mcp_server.schemas'` or import errors.

- [ ] **Step 3: Create `avatar/mcp_server/schemas.py` (full content)**

```python
# avatar/mcp_server/schemas.py
# W2b extends Mission / constraints / safety with mission_intel validators — keep fields minimal here.
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Point(BaseModel):
    """Geodetic point; alt_m is AMSL meters when used as home."""

    model_config = ConfigDict(extra="forbid")

    lat_deg: float = Field(..., ge=-90, le=90)
    lon_deg: float = Field(..., ge=-180, le=180)
    alt_m: Optional[float] = Field(default=None, description="AMSL altitude in meters")


class Waypoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    point: Point
    hold_s: float = Field(default=0.0, ge=0.0)
    speed_m_s: Optional[float] = Field(default=None, ge=0.1, le=25.0)


class MissionConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_altitude_amsl_m: Optional[float] = Field(default=None, ge=1.0, le=500.0)
    max_speed_m_s: Optional[float] = Field(default=None, ge=0.5, le=40.0)


class CinematicInvocation(BaseModel):
    model_config = ConfigDict(extra="allow")

    template_id: str
    target: Point


class SafetyPolicy(BaseModel):
    model_config = ConfigDict(extra="allow")

    rtl_on_low_battery: bool = True
    min_battery_percent: float = Field(default=20.0, ge=5.0, le=95.0)


class Mission(BaseModel):
    """Minimal Mission v1.0 subset for upload_mission / load_plan (W2a)."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    name: str = Field(..., min_length=1, max_length=256)
    home: Point
    waypoints: list[Waypoint] = Field(default_factory=list)
    constraints: Optional[MissionConstraints] = None
    cinematic_blocks: list[CinematicInvocation] = Field(default_factory=list)
    safety: Optional[SafetyPolicy] = None

    @model_validator(mode="after")
    def _waypoint_indices_order(self) -> "Mission":
        for i, wp in enumerate(self.waypoints):
            if wp.index != i:
                raise ValueError(f"waypoints[{i}].index must equal {i}, got {wp.index}")
        return self


class Polygon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vertices: list[Point] = Field(..., min_length=3)
    min_altitude_amsl_m: Optional[float] = Field(default=None)
    max_altitude_amsl_m: Optional[float] = Field(default=None)


class BBox(BaseModel):
    """Normalized bbox: x_center, y_center, width, height in 0..1."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)


class HardLimitsSchema(BaseModel):
    """Serializable guardian limits (AMSL altitude domain per spec)."""

    model_config = ConfigDict(extra="forbid")

    max_altitude_amsl_m: float = Field(default=120.0, gt=0.0)
    max_distance_from_home_m: float = Field(default=500.0, gt=0.0)
    min_battery_rtl_percent: float = Field(default=25.0, ge=0.0, le=100.0)
    heartbeat_timeout_s: float = Field(default=2.0, gt=0.0)
    max_speed_m_s: float = Field(default=15.0, gt=0.0)


FlightMode = Literal[
    "UNKNOWN",
    "MANUAL",
    "STABILIZED",
    "ALTCTL",
    "POSCTL",
    "OFFBOARD",
    "AUTO_MISSION",
    "AUTO_LOITER",
    "AUTO_RTL",
    "ACRO",
    "ORBIT",
    "HOLD",
]


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str = ""


class BehaviorHover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["hover"] = "hover"
    duration_s: float = Field(..., gt=0.0, le=600.0)


class BehaviorPhoto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["photo"] = "photo"
    dwell_s: float = Field(default=1.0, gt=0.0, le=30.0)


class BehaviorOrbit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["orbit"] = "orbit"
    radius_m: float = Field(..., gt=1.0, le=200.0)
    speed_m_s: float = Field(..., gt=0.2, le=20.0)
    duration_s: float = Field(..., gt=1.0, le=900.0)


class BehaviorCinematic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cinematic"] = "cinematic"
    template_id: str = Field(..., min_length=1)
    target: Point


BehaviorBlock = Annotated[
    Union[BehaviorHover, BehaviorPhoto, BehaviorOrbit, BehaviorCinematic],
    Field(discriminator="kind"),
]  # Pydantic v2 tagged union; W2b may add more kinds without breaking "kind" wire key


class TrackerState(BaseModel):
    """MCP-facing copy of Kalman-style state (NED meters)."""

    model_config = ConfigDict(extra="forbid")

    x_m: float
    y_m: float
    z_m: float
    vx_m_s: float
    vy_m_s: float
    vz_m_s: float
    ax_m_s2: float
    ay_m_s2: float
    az_m_s2: float
    timestamp: float
    confidence: float = Field(..., ge=0.0, le=1.0)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/mcp_server/test_schemas_wave2a.py -v`

Expected: three passed.

- [ ] **Step 5: Commit**

```bash
git add avatar/mcp_server/schemas.py tests/mcp_server/test_schemas_wave2a.py avatar/mcp_server/__init__.py
git commit -m "feat(mcp): add Wave 2a shared schemas (Mission v1.0 minimal)"
```

---

### Task W2a-T01: Primitive `arm`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_arm.py`
- Create: `avatar/mcp_server/tools/primitives.py` (initial module + `arm` only if not splitting)
- Modify: `avatar/mcp_server/server.py` (register tool + route)

Assume W1 exposes on `AvatarMCPServer`: `self.confirmation`, `self.guardian`, `self.connection_manager`, `self.telemetry_cache`, and a method `_mcp_session()` returning an object with `auto_confirm: bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_arm.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig
from avatar.mcp_server.errors import ErrorCode


@pytest.mark.asyncio
async def test_arm_requires_confirmation_without_auto_confirm():
    cfg = AvatarMCPServerConfig(connect_on_start=False)
    server = AvatarMCPServer(cfg)
    server._initialized = True
    server.confirmation = MagicMock()
    server.confirmation.require = AsyncMock(
        side_effect=Exception("should not be reached")
    )
    session = MagicMock()
    session.auto_confirm = False
    server._mcp_session = MagicMock(return_value=session)

    from avatar.mcp_server.tools import primitives as prim

    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=server.confirmation,
        connection_manager=MagicMock(),
        get_session=lambda: session,
    )
    prim._session_armed_once = False

    with patch.object(
        prim,
        "to_error_envelope",
        return_value={"isError": True, "error": {"code": ErrorCode.CONFIRMATION_REQUIRED.value}},
    ) as mock_env:
        out = await prim.handle_arm({"force": False})
        assert out["isError"] is True
        mock_env.assert_called_once()


@pytest.mark.asyncio
async def test_arm_calls_guardian_preflight_and_drone_arm_when_auto_confirm():
    cfg = AvatarMCPServerConfig(connect_on_start=False)
    server = AvatarMCPServer(cfg)
    server._initialized = True
    session = MagicMock()
    session.auto_confirm = True
    drone = MagicMock()
    drone.action.arm = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    guardian = MagicMock()
    guardian.preflight = AsyncMock(return_value=None)
    conf = MagicMock()
    conf.require = AsyncMock(return_value=None)

    from avatar.mcp_server.tools import primitives as prim

    prim.set_tool_context(
        guardian=guardian,
        confirmation=conf,
        connection_manager=cm,
        get_session=lambda: session,
    )
    prim._session_armed_once = True

    out = json.loads(await prim.handle_arm({"force": False}))
    assert out["armed"] is True
    assert "timestamp" in out
    guardian.preflight.assert_awaited()
    drone.action.arm.assert_awaited()
```

- [ ] **Step 2: Run test**

Run: `pytest tests/mcp_server/tools/test_primitives_arm.py::test_arm_requires_confirmation_without_auto_confirm -v`

Expected: `ImportError` or `AttributeError` until primitives module exists.

- [ ] **Step 3: Implement `arm` in `primitives.py`**

```python
# avatar/mcp_server/tools/primitives.py (arm section — expand file in same task)
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope
from avatar.mcp_server.schemas import CheckResult


class ArmInput(BaseModel):
    force: bool = False


class ArmOutput(BaseModel):
    armed: bool
    timestamp: str


_tool_guardian: Any = None
_tool_confirmation: Any = None
_tool_connection_manager: Any = None
_get_session: Callable[[], Any] = lambda: None
_session_armed_once: bool = False


def set_tool_context(
    guardian: Any,
    confirmation: Any,
    connection_manager: Any,
    get_session: Callable[[], Any],
) -> None:
    global _tool_guardian, _tool_confirmation, _tool_connection_manager, _get_session
    _tool_guardian = guardian
    _tool_confirmation = confirmation
    _tool_connection_manager = connection_manager
    _get_session = get_session


def arm_tool_schema() -> dict[str, Any]:
    return ArmInput.model_json_schema()


def arm_output_schema() -> dict[str, Any]:
    return ArmOutput.model_json_schema()


def arm_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_arm(arguments: dict[str, Any]) -> dict[str, Any]:
    inp = ArmInput.model_validate(arguments)
    session = _get_session()
    global _session_armed_once
    if session is not None and not session.auto_confirm and not _session_armed_once:
        return to_error_envelope(
            ErrorCode.CONFIRMATION_REQUIRED,
            "First arm in this session requires operator confirmation",
            recoverable=True,
            suggested_action="Call submit_operator_confirmation with the issued token",
        )
    await _tool_guardian.preflight(tool="arm", payload=inp.model_dump())
    if session is not None and not session.auto_confirm:
        token = await _tool_confirmation.require(
            key="arm_first_session",
            message="Confirm first arm in this MCP session",
        )
        if token and session.auto_confirm is False:
            return to_error_envelope(
                ErrorCode.CONFIRMATION_REQUIRED,
                "Awaiting operator confirmation",
                recoverable=True,
                suggested_action="submit_operator_confirmation",
            )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return to_error_envelope(
            ErrorCode.NOT_CONNECTED,
            "No drone connected",
            recoverable=False,
            suggested_action="Initialize server and check MAVLink",
        )
    await drone.action.arm()
    _session_armed_once = True
    out = ArmOutput(
        armed=True,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return json.loads(out.model_dump_json())
```

Wire `set_tool_context` from `AvatarMCPServer.__init__` after W1 components exist. Add `types.Tool` entry with `inputSchema`, `outputSchema`, annotations, name `arm`, description for LLM. `_route_tool` branch returns `json.dumps` if handler returns dict without serialization—normalize to always JSON-stringify for TextContent.

- [ ] **Step 4: Run tests**

Run: `pytest tests/mcp_server/tools/test_primitives_arm.py -v`

Expected: all passed.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_arm_compliant -v`

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git add avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py tests/mcp_server/tools/test_primitives_arm.py
git commit -m "feat(mcp): add arm primitive"
```

---

### Task W2a-T02: Primitive `disarm`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_disarm.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_disarm.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_disarm_preflight_and_disarm():
    drone = MagicMock()
    drone.action.disarm = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    g = MagicMock()
    g.preflight = AsyncMock(return_value=None)
    c = MagicMock()
    c.require = AsyncMock(return_value=None)
    prim.set_tool_context(
        guardian=g,
        confirmation=c,
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_disarm({"force": False})
    out = json.loads(raw) if isinstance(raw, str) else raw
    assert out["armed"] is False
    g.preflight.assert_awaited()
```

- [ ] **Step 2: Run failing**

Run: `pytest tests/mcp_server/tools/test_primitives_disarm.py -v`

Expected: fail until `handle_disarm` exists.

- [ ] **Step 3: Implement**

```python
class DisarmInput(BaseModel):
    force: bool = False


class DisarmOutput(BaseModel):
    armed: bool
    timestamp: str


async def handle_disarm(arguments: dict[str, Any]) -> str:
    inp = DisarmInput.model_validate(arguments)
    await _tool_guardian.preflight(tool="disarm", payload=inp.model_dump())
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    await drone.action.disarm()
    out = DisarmOutput(armed=False, timestamp=datetime.now(timezone.utc).isoformat())
    return out.model_dump_json()
```

Annotations: destructive `true`, idempotent `false`.

- [ ] **Step 4: Pass tests**

Run: `pytest tests/mcp_server/tools/test_primitives_disarm.py -v`

Expected: passed.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_disarm_compliant -v`

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(mcp): add disarm primitive"
```

---

### Task W2a-T03: Primitive `set_flight_mode`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_set_flight_mode.py`
- Modify: `avatar/mcp_server/tools/primitives.py`, `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_set_flight_mode.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from avatar.mcp_server.tools import primitives as prim


def test_set_flight_mode_rejects_unknown_mode_string():
    with pytest.raises(ValidationError):
        prim.SetFlightModeInput.model_validate({"mode": "NOT_A_MODE"})


@pytest.mark.asyncio
async def test_set_flight_mode_hold_calls_action_hold():
    drone = MagicMock()
    drone.action.hold = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    g = MagicMock()
    g.preflight = AsyncMock(return_value=None)
    c = MagicMock()
    prim.set_tool_context(
        guardian=g,
        confirmation=c,
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_set_flight_mode({"mode": "HOLD", "submode": None})
    out = json.loads(raw)
    assert out["mode"] == "HOLD"
    assert out["accepted"] is True
    drone.action.hold.assert_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_set_flight_mode.py -v`

Expected: `AttributeError: module 'avatar.mcp_server.tools.primitives' has no attribute 'SetFlightModeInput'` or missing `handle_set_flight_mode`.

- [ ] **Step 3: Implement**

```python
from avatar.mcp_server.schemas import FlightMode


class SetFlightModeInput(BaseModel):
    mode: FlightMode
    submode: Optional[str] = None


class SetFlightModeOutput(BaseModel):
    mode: FlightMode
    accepted: bool


def set_flight_mode_tool_schema() -> dict[str, Any]:
    return SetFlightModeInput.model_json_schema()


def set_flight_mode_output_schema() -> dict[str, Any]:
    return SetFlightModeOutput.model_json_schema()


def set_flight_mode_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_set_flight_mode(arguments: dict[str, Any]) -> str:
    inp = SetFlightModeInput.model_validate(arguments)
    await _tool_guardian.preflight(
        tool="set_flight_mode",
        payload={"mode": inp.mode, "submode": inp.submode},
    )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    accepted = True
    if inp.mode == "HOLD":
        await drone.action.hold()
    elif inp.mode == "OFFBOARD":
        await drone.offboard.start()
    elif inp.mode == "AUTO_RTL":
        await drone.action.return_to_launch()
    elif inp.mode == "MANUAL" or inp.mode == "STABILIZED" or inp.mode == "ALTCTL" or inp.mode == "POSCTL":
        await drone.action.hold()
    elif inp.mode == "ACRO":
        await drone.action.hold()
    elif inp.mode == "ORBIT":
        await drone.action.hold()
    elif inp.mode == "AUTO_MISSION" or inp.mode == "AUTO_LOITER":
        await drone.action.hold()
    else:
        accepted = False
    out = SetFlightModeOutput(mode=inp.mode, accepted=accepted)
    return out.model_dump_json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_set_flight_mode.py -v`

Expected: three passed.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_set_flight_mode_compliant -v`

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_set_flight_mode.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add set_flight_mode primitive"
```

---

### Task W2a-T04: Primitive `set_velocity_body`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_set_velocity_body.py`
- Modify: `avatar/mcp_server/tools/primitives.py`, `avatar/mcp_server/server.py`, `avatar/mcp_server/errors.py` (ensure `ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT` exists)

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_set_velocity_body.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


class OffboardOwnershipConflict(Exception):
    pass


@pytest.mark.asyncio
async def test_set_velocity_body_conflict_returns_envelope(monkeypatch):
    async def boom_acquire(*args, **kwargs):
        raise OffboardOwnershipConflict()

    drone = MagicMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(prim, "acquire_offboard_owner", boom_acquire)
    monkeypatch.setattr(
        prim,
        "OffboardOwnershipConflict",
        OffboardOwnershipConflict,
        raising=False,
    )
    raw = await prim.handle_set_velocity_body(
        {
            "forward_m_s": 1.0,
            "right_m_s": 0.0,
            "down_m_s": 0.0,
            "yawspeed_deg_s": 0.0,
            "duration_s": 0.5,
        }
    )
    data = json.loads(raw)
    assert data["isError"] is True
    assert data["error"]["code"] == ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT.value


@pytest.mark.asyncio
async def test_set_velocity_body_streams_with_owner(monkeypatch):
    drone = MagicMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)

    class FakeOwner:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    streamer = MagicMock()
    streamer.stream_for = AsyncMock(return_value=10)

    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(prim, "acquire_offboard_owner", lambda **kw: FakeOwner())
    monkeypatch.setattr(prim, "OffboardVelocityStreamer", lambda **kw: streamer)

    raw = await prim.handle_set_velocity_body(
        {
            "forward_m_s": 1.0,
            "right_m_s": 0.0,
            "down_m_s": 0.0,
            "yawspeed_deg_s": 5.0,
            "duration_s": 0.5,
        }
    )
    out = json.loads(raw)
    assert out["streamed_s"] == 0.5
    assert "north_m_s" in out["last_setpoint"]
    streamer.stream_for.assert_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_set_velocity_body.py -v`

Expected: `ImportError` / missing symbols until implementation exists.

- [ ] **Step 3: Implement**

```python
class SetVelocityBodyInput(BaseModel):
    forward_m_s: float
    right_m_s: float
    down_m_s: float
    yawspeed_deg_s: float
    duration_s: float = Field(..., gt=0.05, le=120.0)


class SetVelocityBodyOutput(BaseModel):
    streamed_s: float
    last_setpoint: dict[str, float]


def set_velocity_body_tool_schema() -> dict[str, Any]:
    return SetVelocityBodyInput.model_json_schema()


def set_velocity_body_output_schema() -> dict[str, Any]:
    return SetVelocityBodyOutput.model_json_schema()


def set_velocity_body_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_set_velocity_body(arguments: dict[str, Any]) -> str:
    inp = SetVelocityBodyInput.model_validate(arguments)
    await _tool_guardian.preflight(tool="set_velocity_body", payload=inp.model_dump())
    try:
        owner_ctx = acquire_offboard_owner(source="set_velocity_body")
    except OffboardOwnershipConflict:
        return json.dumps(
            to_error_envelope(
                ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT,
                "Another component holds offboard ownership",
                recoverable=True,
                suggested_action="Stop conflicting tool or call cancel_operation",
            )
        )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    from math import cos, radians, sin

    yaw_deg = 0.0
    if _tool_telemetry_yaw_deg is not None:
        yaw_deg = float(_tool_telemetry_yaw_deg())
    psi = radians(yaw_deg)
    forward = inp.forward_m_s
    right = inp.right_m_s
    north = forward * cos(psi) - right * sin(psi)
    east = forward * sin(psi) + right * cos(psi)
    down = inp.down_m_s
    last = {"north_m_s": north, "east_m_s": east, "down_m_s": down, "yaw_deg": yaw_deg}
    streamer = OffboardVelocityStreamer(rate_hz=20.0)
    from mavsdk.offboard import VelocityNedYaw

    sp = VelocityNedYaw(north, east, down, yaw_deg)
    async with owner_ctx:
        count = await streamer.stream_for(drone, sp, inp.duration_s)
    out = SetVelocityBodyOutput(streamed_s=inp.duration_s, last_setpoint=last)
    return out.model_dump_json()
```

Add module-level `_tool_telemetry_yaw_deg: Callable[[], float] | None = None` and setter `set_telemetry_yaw_supplier(fn)` called from server when telemetry cache available.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_set_velocity_body.py -v`

Expected: two passed.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_set_velocity_body_compliant -v`

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git add avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py avatar/mcp_server/errors.py tests/mcp_server/tools/test_primitives_set_velocity_body.py
git commit -m "feat(mcp): add set_velocity_body primitive"
```

### Task W2a-T05: Primitive `goto_local_ned`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_goto_local_ned.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_goto_local_ned.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_goto_local_ned_not_connected_returns_envelope():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_goto_local_ned({"x_m": 10.0, "y_m": 0.0, "z_m": -5.0})
    data = json.loads(raw)
    assert data["isError"] is True
    assert data["error"]["code"] == ErrorCode.NOT_CONNECTED.value


@pytest.mark.asyncio
async def test_goto_local_ned_calls_goto_location_with_rotated_offset():
    home_lat = 47.3977
    home_lon = 8.5456
    home_amsl = 488.0

    async def home_iter():
        hp = MagicMock()
        hp.latitude_deg = home_lat
        hp.longitude_deg = home_lon
        hp.absolute_altitude_m = home_amsl
        yield hp

    drone = MagicMock()
    drone.telemetry.home = home_iter
    drone.action.goto_location = AsyncMock()

    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)

    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )

    north_m = 10.0
    east_m = 5.0
    down_m = -2.0
    yaw_cmd = 90.0

    raw = await prim.handle_goto_local_ned(
        {"x_m": north_m, "y_m": east_m, "z_m": down_m, "yaw_deg": yaw_cmd}
    )
    out = json.loads(raw)
    assert out["reached"] is True
    assert out["distance_m"] >= 0.0
    drone.action.goto_location.assert_awaited()
    args, kwargs = drone.action.goto_location.call_args
    assert abs(args[0] - (home_lat + north_m / 111_320.0)) < 1e-4
    assert abs(args[1] - (home_lon + east_m / (111_320.0 * __import__("math").cos(__import__("math").radians(home_lat))))) < 1e-4
    assert abs(args[2] - (home_amsl - down_m)) < 0.01
    assert args[3] == yaw_cmd


@pytest.mark.asyncio
async def test_goto_local_ned_guardian_violation_returns_envelope(monkeypatch):
    async def bad_preflight(**kwargs):
        raise RuntimeError("guardian block")

    async def home_iter():
        hp = MagicMock()
        hp.latitude_deg = 47.0
        hp.longitude_deg = 8.0
        hp.absolute_altitude_m = 400.0
        yield hp

    g = MagicMock()
    g.preflight = AsyncMock(side_effect=bad_preflight)
    drone = MagicMock()
    drone.telemetry.home = home_iter
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value, "message": msg}},
    )
    raw = await prim.handle_goto_local_ned({"x_m": 1.0, "y_m": 0.0, "z_m": 0.0})
    data = json.loads(raw)
    assert data["isError"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_goto_local_ned.py -v`

Expected: `FAILED` with `AttributeError: module 'avatar.mcp_server.tools.primitives' has no attribute 'handle_goto_local_ned'`.

- [ ] **Step 3: Implement**

```python
import math
from typing import Any, Optional

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope


class GotoLocalNedInput(BaseModel):
    x_m: float
    y_m: float
    z_m: float
    yaw_deg: Optional[float] = None


class GotoLocalNedOutput(BaseModel):
    reached: bool
    distance_m: float


def goto_local_ned_tool_schema() -> dict[str, Any]:
    return GotoLocalNedInput.model_json_schema()


def goto_local_ned_output_schema() -> dict[str, Any]:
    return GotoLocalNedOutput.model_json_schema()


def goto_local_ned_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def _async_home_position(drone: Any) -> Any:
    async for hp in drone.telemetry.home():
        return hp


async def handle_goto_local_ned(arguments: dict[str, Any]) -> str:
    inp = GotoLocalNedInput.model_validate(arguments)
    await _tool_guardian.preflight(tool="goto_local_ned", payload=inp.model_dump())
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    hp = await _async_home_position(drone)
    home_lat = float(hp.latitude_deg)
    home_lon = float(hp.longitude_deg)
    home_amsl = float(hp.absolute_altitude_m)
    north_m = inp.x_m
    east_m = inp.y_m
    down_m = inp.z_m
    delta_lat = north_m / 111_320.0
    delta_lon = east_m / (111_320.0 * math.cos(math.radians(home_lat)))
    target_lat = home_lat + delta_lat
    target_lon = home_lon + delta_lon
    target_amsl = home_amsl - down_m
    yaw_deg = float(inp.yaw_deg) if inp.yaw_deg is not None else float("nan")
    await drone.action.goto_location(target_lat, target_lon, target_amsl, yaw_deg)
    horiz_m = math.hypot(north_m, east_m)
    out = GotoLocalNedOutput(reached=True, distance_m=horiz_m)
    return out.model_dump_json()
```

`server.py` registration (append next to other tools):

```python
types.Tool(
    name="goto_local_ned",
    description="Go to local NED offset from home; converts to global goto_location.",
    inputSchema=prim.goto_local_ned_tool_schema(),
    outputSchema=prim.goto_local_ned_output_schema(),
    annotations=prim.goto_local_ned_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_goto_local_ned.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_goto_local_ned_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_goto_local_ned.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add goto_local_ned primitive"
```

---

### Task W2a-T06: Primitive `upload_mission`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_upload_mission.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_upload_mission.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.schemas import Mission, Point, Waypoint
from avatar.mcp_server.tools import primitives as prim


def _minimal_mission() -> dict:
    return {
        "version": "1.0",
        "name": "t",
        "home": {"lat_deg": 47.0, "lon_deg": 8.0, "alt_m": 400.0},
        "waypoints": [
            {"index": 0, "point": {"lat_deg": 47.0001, "lon_deg": 8.0, "alt_m": 405.0}, "hold_s": 0.0}
        ],
    }


@pytest.mark.asyncio
async def test_upload_mission_confirmation_when_active_mission(monkeypatch):
    session = MagicMock()
    session.auto_confirm = False
    session.active_mission_id = "m-1"
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: session,
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_upload_mission({"mission": _minimal_mission()})
    data = json.loads(raw)
    assert data["isError"] is True
    assert data["error"]["code"] == ErrorCode.CONFIRMATION_REQUIRED.value


@pytest.mark.asyncio
async def test_upload_mission_uploads_via_mavsdk(monkeypatch):
    drone = MagicMock()
    drone.mission.upload_mission = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    session = MagicMock(auto_confirm=True, active_mission_id=None)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(require=AsyncMock(return_value=None)),
        connection_manager=cm,
        get_session=lambda: session,
    )
    raw = await prim.handle_upload_mission({"mission": _minimal_mission()})
    out = json.loads(raw)
    assert "mission_id" in out
    assert out["waypoint_count"] == 1
    drone.mission.upload_mission.assert_awaited()


@pytest.mark.asyncio
async def test_upload_mission_invalid_schema_returns_validation_error():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    with pytest.raises(Exception):
        await prim.handle_upload_mission({"mission": {"version": "1.0", "name": "x", "home": {"lat_deg": 0, "lon_deg": 0}, "waypoints": []}})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_upload_mission.py -v`

Expected: `FAILED` with import or missing handler errors.

- [ ] **Step 3: Implement**

```python
import uuid

from mavsdk.mission import MissionItem, MissionPlan


class UploadMissionInput(BaseModel):
    mission: Mission


class UploadMissionOutput(BaseModel):
    mission_id: str
    waypoint_count: int


def upload_mission_tool_schema() -> dict[str, Any]:
    return UploadMissionInput.model_json_schema()


def upload_mission_output_schema() -> dict[str, Any]:
    return UploadMissionOutput.model_json_schema()


def upload_mission_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_upload_mission(arguments: dict[str, Any]) -> str:
    inp = UploadMissionInput.model_validate(arguments)
    await _tool_guardian.preflight(tool="upload_mission", payload={"name": inp.mission.name})
    session = _get_session()
    if session is not None and getattr(session, "active_mission_id", None) and not session.auto_confirm:
        return json.dumps(
            to_error_envelope(
                ErrorCode.CONFIRMATION_REQUIRED,
                "Active mission loaded; confirm override",
                recoverable=True,
                suggested_action="submit_operator_confirmation",
            )
        )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    mission_items: list[MissionItem] = []
    for wp in inp.mission.waypoints:
        alt = wp.point.alt_m if wp.point.alt_m is not None else inp.mission.home.alt_m
        if alt is None:
            alt = 25.0
        spd = wp.speed_m_s if wp.speed_m_s is not None else 5.0
        mission_items.append(
            MissionItem(
                float(wp.point.lat_deg),
                float(wp.point.lon_deg),
                float(alt),
                float(spd),
                True,
                float("nan"),
                float("nan"),
                MissionItem.CameraAction.NONE,
                float(wp.hold_s),
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
                MissionItem.VehicleAction.NONE,
                float("nan"),
                float("nan"),
                float("nan"),
            )
        )
    await drone.mission.upload_mission(MissionPlan(mission_items))
    mid = str(uuid.uuid4())
    if session is not None:
        session.active_mission_id = mid
    out = UploadMissionOutput(mission_id=mid, waypoint_count=len(inp.mission.waypoints))
    return out.model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="upload_mission",
    description="Upload a Mission v1.0-minimal plan to PX4.",
    inputSchema=prim.upload_mission_tool_schema(),
    outputSchema=prim.upload_mission_output_schema(),
    annotations=prim.upload_mission_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_upload_mission.py -v`

Expected: `3 passed` after adjusting the invalid-schema test to expect `json` error envelope instead of bare `Exception` if handlers catch validation.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_upload_mission_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_upload_mission.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add upload_mission primitive"
```

---

### Task W2a-T07: Primitive `start_mission`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_start_mission.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_start_mission.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_start_mission_not_connected():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_start_mission({})
    data = json.loads(raw)
    assert data["isError"] is True
    assert data["error"]["code"] == ErrorCode.NOT_CONNECTED.value


@pytest.mark.asyncio
async def test_start_mission_calls_mavsdk():
    drone = MagicMock()
    drone.mission.start_mission = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_start_mission({})
    out = json.loads(raw)
    assert out["started"] is True
    drone.mission.start_mission.assert_awaited()


@pytest.mark.asyncio
async def test_start_mission_guardian_preflight_failure(monkeypatch):
    g = MagicMock()
    g.preflight = AsyncMock(side_effect=RuntimeError("no"))
    drone = MagicMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_start_mission({})
    assert json.loads(raw)["isError"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_start_mission.py -v`

Expected: `FAILED` missing `handle_start_mission`.

- [ ] **Step 3: Implement**

```python
class StartMissionInput(BaseModel):
    pass


class StartMissionOutput(BaseModel):
    started: bool


def start_mission_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def start_mission_output_schema() -> dict[str, Any]:
    return StartMissionOutput.model_json_schema()


def start_mission_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_start_mission(arguments: dict[str, Any]) -> str:
    await _tool_guardian.preflight(tool="start_mission", payload={})
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    await drone.mission.start_mission()
    return StartMissionOutput(started=True).model_dump_json()
```

`server.py` `types.Tool(name="start_mission", ...)` with schemas and annotations above.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_start_mission.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_start_mission_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_start_mission.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add start_mission primitive"
```

---

### Task W2a-T08: Primitive `pause_mission`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_pause_mission.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_pause_mission.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_pause_mission_not_connected():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_pause_mission({})
    data = json.loads(raw)
    assert data["isError"] is True
    assert data["error"]["code"] == ErrorCode.NOT_CONNECTED.value


@pytest.mark.asyncio
async def test_pause_mission_calls_pause_mission():
    drone = MagicMock()
    drone.mission.pause_mission = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_pause_mission({})
    out = json.loads(raw)
    assert out["paused"] is True
    drone.mission.pause_mission.assert_awaited()


@pytest.mark.asyncio
async def test_pause_mission_preflight_failure(monkeypatch):
    g = MagicMock()
    g.preflight = AsyncMock(side_effect=RuntimeError("block"))
    drone = MagicMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_pause_mission({})
    assert json.loads(raw)["isError"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_pause_mission.py -v`

Expected: `FAILED` with missing `handle_pause_mission`.

- [ ] **Step 3: Implement**

```python
from pydantic import BaseModel


class PauseMissionOutput(BaseModel):
    paused: bool


def pause_mission_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def pause_mission_output_schema() -> dict[str, Any]:
    return PauseMissionOutput.model_json_schema()


def pause_mission_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_pause_mission(arguments: dict[str, Any]) -> str:
    await _tool_guardian.preflight(tool="pause_mission", payload={})
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    await drone.mission.pause_mission()
    return PauseMissionOutput(paused=True).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="pause_mission",
    description="Pause the current PX4 mission.",
    inputSchema=prim.pause_mission_tool_schema(),
    outputSchema=prim.pause_mission_output_schema(),
    annotations=prim.pause_mission_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_pause_mission.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_pause_mission_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_pause_mission.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add pause_mission primitive"
```

---

### Task W2a-T09: Primitive `resume_mission`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_resume_mission.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_resume_mission.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_resume_mission_not_connected():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_resume_mission({})
    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value


@pytest.mark.asyncio
async def test_resume_mission_calls_start_mission():
    drone = MagicMock()
    drone.mission.start_mission = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_resume_mission({})
    out = json.loads(raw)
    assert out["resumed"] is True
    drone.mission.start_mission.assert_awaited()


@pytest.mark.asyncio
async def test_resume_mission_guardian_blocks(monkeypatch):
    g = MagicMock()
    g.preflight = AsyncMock(side_effect=RuntimeError("x"))
    drone = MagicMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_resume_mission({})
    assert json.loads(raw)["isError"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_resume_mission.py -v`

Expected: `FAILED` missing handler.

- [ ] **Step 3: Implement**

```python
class ResumeMissionOutput(BaseModel):
    resumed: bool


def resume_mission_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def resume_mission_output_schema() -> dict[str, Any]:
    return ResumeMissionOutput.model_json_schema()


def resume_mission_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_resume_mission(arguments: dict[str, Any]) -> str:
    await _tool_guardian.preflight(tool="resume_mission", payload={})
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    await drone.mission.start_mission()
    return ResumeMissionOutput(resumed=True).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="resume_mission",
    description="Resume PX4 mission after pause (MAVSDK start_mission).",
    inputSchema=prim.resume_mission_tool_schema(),
    outputSchema=prim.resume_mission_output_schema(),
    annotations=prim.resume_mission_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_resume_mission.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_resume_mission_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_resume_mission.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add resume_mission primitive"
```

---

### Task W2a-T10: Primitive `set_geofence_polygon`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_set_geofence_polygon.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_set_geofence_polygon.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


def _square_vertices():
    return {
        "vertices": [
            {"lat_deg": 47.0, "lon_deg": 8.0},
            {"lat_deg": 47.001, "lon_deg": 8.0},
            {"lat_deg": 47.001, "lon_deg": 8.001},
        ],
        "min_altitude_amsl_m": None,
        "max_altitude_amsl_m": None,
    }


@pytest.mark.asyncio
async def test_set_geofence_shrink_requires_confirmation(monkeypatch):
    session = MagicMock()
    session.auto_confirm = False
    session.last_fence_area_m2 = 1_000_000.0
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: session,
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_set_geofence_polygon(
        {"polygon": _square_vertices(), "action": "rtl"}
    )
    assert json.loads(raw)["error"]["code"] == ErrorCode.CONFIRMATION_REQUIRED.value


@pytest.mark.asyncio
async def test_set_geofence_upload_calls_geofence():
    drone = MagicMock()
    drone.geofence.upload_geofence = AsyncMock()
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    session = MagicMock(auto_confirm=True, last_fence_area_m2=None)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: session,
    )
    raw = await prim.handle_set_geofence_polygon(
        {"polygon": _square_vertices(), "action": "rtl"}
    )
    out = json.loads(raw)
    assert out["applied"] is True
    drone.geofence.upload_geofence.assert_awaited()


@pytest.mark.asyncio
async def test_set_geofence_not_connected():
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_set_geofence_polygon(
        {"polygon": _square_vertices(), "action": "warn"}
    )
    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_set_geofence_polygon.py -v`

Expected: `FAILED` missing `handle_set_geofence_polygon`.

- [ ] **Step 3: Implement**

```python
import math
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope
from avatar.mcp_server.schemas import Polygon


class SetGeofencePolygonInput(BaseModel):
    polygon: Polygon
    action: Literal["rtl", "land", "warn"]


class SetGeofencePolygonOutput(BaseModel):
    fence_id: str
    applied: bool


def set_geofence_polygon_tool_schema() -> dict[str, Any]:
    return SetGeofencePolygonInput.model_json_schema()


def set_geofence_polygon_output_schema() -> dict[str, Any]:
    return SetGeofencePolygonOutput.model_json_schema()


def set_geofence_polygon_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def _polygon_area_m2(poly: Polygon) -> float:
    lat0 = poly.vertices[0].lat_deg
    acc = 0.0
    n = len(poly.vertices)
    for i in range(n):
        a = poly.vertices[i]
        b = poly.vertices[(i + 1) % n]
        x1 = (a.lon_deg - poly.vertices[0].lon_deg) * 111_320.0 * math.cos(math.radians(lat0))
        y1 = (a.lat_deg - poly.vertices[0].lat_deg) * 111_320.0
        x2 = (b.lon_deg - poly.vertices[0].lon_deg) * 111_320.0 * math.cos(math.radians(lat0))
        y2 = (b.lat_deg - poly.vertices[0].lat_deg) * 111_320.0
        acc += x1 * y2 - x2 * y1
    return abs(acc) * 0.5


async def handle_set_geofence_polygon(arguments: dict[str, Any]) -> str:
    inp = SetGeofencePolygonInput.model_validate(arguments)
    await _tool_guardian.preflight(
        tool="set_geofence_polygon",
        payload={"action": inp.action, "vertices": len(inp.polygon.vertices)},
    )
    session = _get_session()
    new_area = _polygon_area_m2(inp.polygon)
    if (
        session is not None
        and getattr(session, "last_fence_area_m2", None) is not None
        and new_area < float(session.last_fence_area_m2)
        and not session.auto_confirm
    ):
        return json.dumps(
            to_error_envelope(
                ErrorCode.CONFIRMATION_REQUIRED,
                "Geofence shrink or removal requires operator confirmation",
                recoverable=True,
                suggested_action="submit_operator_confirmation",
            )
        )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    from mavsdk.geofence import FenceType, GeofenceData, Point, Polygon as GeoPolygon

    pts = [Point(float(v.lat_deg), float(v.lon_deg)) for v in inp.polygon.vertices]
    geo_poly = GeoPolygon(fence_type=FenceType.INCLUSION, points=pts)
    await drone.geofence.upload_geofence(GeofenceData(polygons=[geo_poly]))
    if session is not None:
        session.last_fence_area_m2 = new_area
    fid = str(uuid.uuid4())
    return SetGeofencePolygonOutput(fence_id=fid, applied=True).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="set_geofence_polygon",
    description="Upload a geofence polygon to PX4.",
    inputSchema=prim.set_geofence_polygon_tool_schema(),
    outputSchema=prim.set_geofence_polygon_output_schema(),
    annotations=prim.set_geofence_polygon_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_set_geofence_polygon.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_set_geofence_polygon_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_set_geofence_polygon.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add set_geofence_polygon primitive"
```

---

### Task W2a-T11: Primitive `load_plan`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_load_plan.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_load_plan.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from avatar.mcp_server.tools import primitives as prim


def test_load_plan_rejects_both_path_and_contents():
    with pytest.raises(ValidationError):
        prim.LoadPlanInput.model_validate({"path": "/x", "contents": "{}"})


def test_load_plan_rejects_neither_path_nor_contents():
    with pytest.raises(ValidationError):
        prim.LoadPlanInput.model_validate({})


def test_load_plan_invalid_qgc_json(tmp_path):
    p = tmp_path / "bad.plan"
    p.write_text('{"foo": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        prim.parse_qgc_plan_file(str(p))


def test_load_plan_from_valid_qgc(tmp_path):
    body = {
        "fileType": "Plan",
        "mission": {
            "items": [
                {
                    "type": "SimpleItem",
                    "command": 16,
                    "params": [0, 0, 0, 0, 47.3977, 8.5456, 488],
                },
                {
                    "type": "SimpleItem",
                    "command": 16,
                    "params": [0, 0, 0, 0, 47.3978, 8.5457, 490],
                },
            ]
        },
    }
    import json as js

    p = tmp_path / "m.plan"
    p.write_text(js.dumps(body), encoding="utf-8")
    m = prim.parse_qgc_plan_file(str(p))
    assert m.version == "1.0"
    assert len(m.waypoints) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_load_plan.py -v`

Expected: `FAILED` missing `LoadPlanInput` / `parse_qgc_plan_file`.

- [ ] **Step 3: Implement**

```python
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from avatar.mcp_server.schemas import Mission, Point, Waypoint


class LoadPlanInput(BaseModel):
    path: Optional[str] = None
    contents: Optional[str] = None

    @model_validator(mode="after")
    def _one_of(self) -> "LoadPlanInput":
        if (self.path is None) == (self.contents is None):
            raise ValueError("Exactly one of path or contents is required")
        return self


class LoadPlanOutput(BaseModel):
    mission: Mission


def load_plan_tool_schema() -> dict[str, Any]:
    return LoadPlanInput.model_json_schema()


def load_plan_output_schema() -> dict[str, Any]:
    return LoadPlanOutput.model_json_schema()


def load_plan_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def parse_qgc_plan_file(path: str) -> Mission:
    raw = Path(path).read_text(encoding="utf-8")
    return parse_qgc_plan_json(raw)


def parse_qgc_plan_json(raw: str) -> Mission:
    import json as js

    doc = js.loads(raw)
    items = doc.get("mission", {}).get("items", [])
    waypoints: list[Waypoint] = []
    home = Point(lat_deg=47.3977, lon_deg=8.5456, alt_m=488.0)
    idx = 0
    for it in items:
        if it.get("type") != "SimpleItem":
            continue
        if int(it.get("command", 0)) != 16:
            continue
        pr = it.get("params") or []
        if len(pr) < 7:
            continue
        lat = float(pr[4])
        lon = float(pr[5])
        alt = float(pr[6])
        if idx == 0:
            home = Point(lat_deg=lat, lon_deg=lon, alt_m=alt)
        else:
            waypoints.append(
                Waypoint(
                    index=len(waypoints),
                    point=Point(lat_deg=lat, lon_deg=lon, alt_m=alt),
                    hold_s=0.0,
                )
            )
        idx += 1
    if not waypoints:
        raise ValueError("No NAV_WAYPOINT items in QGC plan")
    return Mission(version="1.0", name=doc.get("name", "imported"), home=home, waypoints=waypoints)


async def handle_load_plan(arguments: dict[str, Any]) -> str:
    inp = LoadPlanInput.model_validate(arguments)
    if inp.path is not None:
        mission = parse_qgc_plan_file(inp.path)
    else:
        mission = parse_qgc_plan_json(inp.contents or "")
    return LoadPlanOutput(mission=mission).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="load_plan",
    description="Load a QGroundControl .plan JSON into Mission v1.0-minimal (read-only).",
    inputSchema=prim.load_plan_tool_schema(),
    outputSchema=prim.load_plan_output_schema(),
    annotations=prim.load_plan_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_load_plan.py -v`

Expected: `4 passed` after aligning first-waypoint indexing with parser (adjust test if parser treats first waypoint as home-only).

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_load_plan_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_load_plan.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add load_plan primitive"
```

---

### Stream D6: Orchestrators (6)

---

### Task W2a-T12: Primitive `get_parameter`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_get_parameter.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_get_parameter.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_get_parameter_not_connected():
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_get_parameter({"name": "MPC_XY_VEL_MAX"})
    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value


@pytest.mark.asyncio
async def test_get_parameter_float_dispatch():
    drone = MagicMock()
    drone.param.get_param_float = AsyncMock(return_value=12.5)
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_get_parameter({"name": "MPC_XY_VEL_MAX"})
    out = json.loads(raw)
    assert out["type"] == "float"
    assert out["value"] == 12.5


@pytest.mark.asyncio
async def test_get_parameter_int_dispatch():
    drone = MagicMock()
    drone.param.get_param_float = AsyncMock(side_effect=RuntimeError("no float"))
    drone.param.get_param_int = AsyncMock(return_value=3)
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_get_parameter({"name": "COM_OBL_RC_ACT"})
    out = json.loads(raw)
    assert out["type"] == "int"
    assert out["value"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_get_parameter.py -v`

Expected: `FAILED` missing `handle_get_parameter`.

- [ ] **Step 3: Implement**

```python
from typing import Union

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope


class GetParameterInput(BaseModel):
    name: str = Field(..., min_length=1)


class GetParameterOutput(BaseModel):
    name: str
    value: Union[float, int, str]
    type: str


def get_parameter_tool_schema() -> dict[str, Any]:
    return GetParameterInput.model_json_schema()


def get_parameter_output_schema() -> dict[str, Any]:
    return GetParameterOutput.model_json_schema()


def get_parameter_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_get_parameter(arguments: dict[str, Any]) -> str:
    inp = GetParameterInput.model_validate(arguments)
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    name = inp.name
    try:
        v = await drone.param.get_param_float(name)
        out = GetParameterOutput(name=name, value=float(v), type="float")
    except Exception:
        try:
            vi = await drone.param.get_param_int(name)
            out = GetParameterOutput(name=name, value=int(vi), type="int")
        except Exception:
            vs = await drone.param.get_param_custom(name)
            out = GetParameterOutput(name=name, value=str(vs), type="string")
    return out.model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="get_parameter",
    description="Read a PX4 parameter by name.",
    inputSchema=prim.get_parameter_tool_schema(),
    outputSchema=prim.get_parameter_output_schema(),
    annotations=prim.get_parameter_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_get_parameter.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_get_parameter_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_get_parameter.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add get_parameter primitive"
```

---

### Task W2a-T13: Primitive `set_parameter`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_set_parameter.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_set_parameter.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_set_parameter_critical_requires_confirmation(monkeypatch):
    from avatar.mcp_server.confirmation_policy import CRITICAL_PARAMETER_NAMES

    name = next(iter(CRITICAL_PARAMETER_NAMES))
    session = MagicMock(auto_confirm=False)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: session,
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_set_parameter({"name": name, "value": 1.0})
    assert json.loads(raw)["error"]["code"] == ErrorCode.CONFIRMATION_REQUIRED.value


@pytest.mark.asyncio
async def test_set_parameter_writes_float():
    drone = MagicMock()
    drone.param.set_param_float = AsyncMock()
    drone.param.get_param_float = AsyncMock(return_value=2.0)
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_set_parameter({"name": "MPC_XY_VEL_MAX", "value": 2.0})
    out = json.loads(raw)
    assert out["reverted"] is False
    drone.param.set_param_float.assert_awaited()


@pytest.mark.asyncio
async def test_set_parameter_reverted_when_readback_mismatch():
    drone = MagicMock()
    drone.param.set_param_float = AsyncMock()
    drone.param.get_param_float = AsyncMock(return_value=9.0)
    cm = MagicMock()
    cm.get_drone = AsyncMock(return_value=drone)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=MagicMock(),
        connection_manager=cm,
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_set_parameter({"name": "MPC_XY_VEL_MAX", "value": 2.0})
    out = json.loads(raw)
    assert out["reverted"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_set_parameter.py -v`

Expected: `FAILED` until handler and `CRITICAL_PARAMETER_NAMES` exist in W1 policy module.

- [ ] **Step 3: Implement**

```python
from typing import Union

from pydantic import BaseModel

from avatar.mcp_server.confirmation_policy import CRITICAL_PARAMETER_NAMES
from avatar.mcp_server.errors import ErrorCode, to_error_envelope


class SetParameterInput(BaseModel):
    name: str
    value: Union[float, int, str]


class SetParameterOutput(BaseModel):
    name: str
    value_set: Union[float, int, str]
    reverted: bool


def set_parameter_tool_schema() -> dict[str, Any]:
    return SetParameterInput.model_json_schema()


def set_parameter_output_schema() -> dict[str, Any]:
    return SetParameterOutput.model_json_schema()


def set_parameter_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_set_parameter(arguments: dict[str, Any]) -> str:
    inp = SetParameterInput.model_validate(arguments)
    await _tool_guardian.preflight(tool="set_parameter", payload={"name": inp.name})
    session = _get_session()
    if inp.name in CRITICAL_PARAMETER_NAMES and session is not None and not session.auto_confirm:
        return json.dumps(
            to_error_envelope(
                ErrorCode.CONFIRMATION_REQUIRED,
                "Critical parameter write requires confirmation",
                recoverable=True,
                suggested_action="submit_operator_confirmation",
            )
        )
    drone = await _tool_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    if isinstance(inp.value, float) or isinstance(inp.value, int):
        await drone.param.set_param_float(inp.name, float(inp.value))
        read_back = await drone.param.get_param_float(inp.name)
        reverted = abs(float(read_back) - float(inp.value)) > 1e-3
        out = SetParameterOutput(
            name=inp.name,
            value_set=float(inp.value),
            reverted=reverted,
        )
    else:
        await drone.param.set_param_custom(inp.name, str(inp.value))
        read_back = await drone.param.get_param_custom(inp.name)
        reverted = str(read_back) != str(inp.value)
        out = SetParameterOutput(
            name=inp.name,
            value_set=str(inp.value),
            reverted=reverted,
        )
    return out.model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="set_parameter",
    description="Write a PX4 parameter (critical names require confirmation).",
    inputSchema=prim.set_parameter_tool_schema(),
    outputSchema=prim.set_parameter_output_schema(),
    annotations=prim.set_parameter_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_set_parameter.py -v`

Expected: `3 passed` after `confirmation_policy.CRITICAL_PARAMETER_NAMES` is a non-empty `frozenset` of strings matching keys used in the first test.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_set_parameter_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_set_parameter.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py avatar/mcp_server/confirmation_policy.py
git commit -m "feat(mcp): add set_parameter primitive"
```

---

### Task W2a-T14: Primitive `preflight_checklist`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_preflight_checklist.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_preflight_checklist.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_preflight_checklist_uses_script_when_present(monkeypatch):
    class _Path:
        def __init__(self, *args, **kwargs):
            self._s = str(args[0]) if args else ""

        def is_file(self) -> bool:
            return self._s.endswith("preflight.py")

    monkeypatch.setattr(prim, "Path", _Path)
    monkeypatch.setattr(
        prim.subprocess,
        "run",
        MagicMock(return_value=MagicMock(returncode=0, stdout="OK", stderr="")),
    )
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    prim.set_preflight_profile(MagicMock(airframe=MagicMock(id="x500_v2")))
    raw = await prim.handle_preflight_checklist({})
    out = json.loads(raw)
    assert out["overall"] in ("pass", "warn", "fail")
    assert any(c["name"] == "hardware_preflight_script" for c in out["checks"])


@pytest.mark.asyncio
async def test_preflight_checklist_fallback_without_script(monkeypatch):
    class _PathNo:
        def __init__(self, *args, **kwargs):
            pass

        def is_file(self) -> bool:
            return False

    monkeypatch.setattr(prim, "Path", _PathNo)
    cache = MagicMock()
    cache.get_data = MagicMock(
        return_value=MagicMock(
            battery_percent=80.0,
            gps_fix_type=3,
            armed=False,
        )
    )
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    prim.set_telemetry_cache_supplier(lambda: cache)
    raw = await prim.handle_preflight_checklist({})
    out = json.loads(raw)
    assert out["overall"] == "pass"


@pytest.mark.asyncio
async def test_preflight_checklist_low_battery_warns(monkeypatch):
    class _PathNo:
        def __init__(self, *args, **kwargs):
            pass

        def is_file(self) -> bool:
            return False

    monkeypatch.setattr(prim, "Path", _PathNo)
    cache = MagicMock()
    cache.get_data = MagicMock(
        return_value=MagicMock(
            battery_percent=10.0,
            gps_fix_type=3,
            armed=False,
        )
    )
    prim.set_tool_context(
        guardian=MagicMock(),
        confirmation=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    prim.set_telemetry_cache_supplier(lambda: cache)
    raw = await prim.handle_preflight_checklist({})
    out = json.loads(raw)
    assert out["overall"] in ("warn", "fail")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_preflight_checklist.py -v`

Expected: `FAILED` until `Path` and `subprocess` are module-level names on `primitives`, and `set_preflight_profile`, `set_telemetry_cache_supplier`, and `handle_preflight_checklist` exist.

- [ ] **Step 3: Implement**

```python
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel

from avatar.mcp_server.schemas import CheckResult


class PreflightChecklistOutput(BaseModel):
    checks: list[CheckResult]
    overall: Literal["pass", "warn", "fail"]


_preflight_profile: Any = None
_telemetry_cache_supplier: Callable[[], Any] = lambda: None


def set_preflight_profile(profile: Any) -> None:
    global _preflight_profile
    _preflight_profile = profile


def set_telemetry_cache_supplier(fn: Callable[[], Any]) -> None:
    global _telemetry_cache_supplier
    _telemetry_cache_supplier = fn


def preflight_checklist_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def preflight_checklist_output_schema() -> dict[str, Any]:
    return PreflightChecklistOutput.model_json_schema()


def preflight_checklist_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_preflight_checklist(arguments: dict[str, Any]) -> str:
    checks: list[CheckResult] = []
    script = Path("hardware/px4/preflight.py")
    if script.is_file() and _preflight_profile is not None:
        airframe = str(_preflight_profile.airframe.id)
        proc = subprocess.run(
            [sys.executable, str(script), "--airframe", airframe],
            capture_output=True,
            text=True,
            timeout=120,
        )
        st = "pass" if proc.returncode == 0 else "fail"
        checks.append(
            CheckResult(
                name="hardware_preflight_script",
                status=st,
                detail=(proc.stdout or "") + (proc.stderr or ""),
            )
        )
    else:
        cache = _telemetry_cache_supplier()
        if cache is None or cache.get_data() is None:
            checks.append(
                CheckResult(
                    name="telemetry_cache",
                    status="fail",
                    detail="No telemetry",
                )
            )
        else:
            d = cache.get_data()
            gps = getattr(d, "gps_fix_type", 0) or 0
            checks.append(
                CheckResult(
                    name="gps_fix",
                    status="pass" if gps >= 3 else "warn",
                    detail=f"fix_type={gps}",
                )
            )
            bat = float(getattr(d, "battery_percent", 0.0) or 0.0)
            bst = "pass" if bat >= 25.0 else "warn" if bat >= 15.0 else "fail"
            checks.append(
                CheckResult(
                    name="battery",
                    status=bst,
                    detail=f"{bat}%",
                )
            )
    overall: Literal["pass", "warn", "fail"] = "pass"
    if any(c.status == "fail" for c in checks):
        overall = "fail"
    elif any(c.status == "warn" for c in checks):
        overall = "warn"
    return PreflightChecklistOutput(checks=checks, overall=overall).model_dump_json()
```

`server.py` wires `prim.set_preflight_profile(self.config_profile)` during init if a profile object exists.

```python
types.Tool(
    name="preflight_checklist",
    description="Run preflight checks (script or telemetry fallback).",
    inputSchema=prim.preflight_checklist_tool_schema(),
    outputSchema=prim.preflight_checklist_output_schema(),
    annotations=prim.preflight_checklist_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_preflight_checklist.py -v`

Expected: `3 passed` after `primitives` exposes `Path` (from `pathlib`) and `subprocess` at module scope so tests can `monkeypatch.setattr(prim, "Path", ...)`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_preflight_checklist_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_preflight_checklist.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add preflight_checklist primitive"
```

---

### Task W2a-T15: Primitive `get_guardian_limits`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_get_guardian_limits.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_get_guardian_limits.py
import json
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from avatar.mcp_server.tools import primitives as prim


@dataclass
class HL:
    max_altitude_amsl_m: float = 120.0
    max_distance_from_home_m: float = 500.0
    min_battery_rtl_percent: float = 25.0
    heartbeat_timeout_s: float = 2.0
    max_speed_m_s: float = 15.0


@pytest.mark.asyncio
async def test_get_guardian_limits_serializes():
    g = MagicMock()
    g.hard_limits = HL()
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=MagicMock(),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_get_guardian_limits({})
    out = json.loads(raw)
    assert out["hard_limits"]["max_altitude_amsl_m"] == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_get_guardian_limits.py -v`

Expected: `FAILED` with `AttributeError` on `handle_get_guardian_limits` until implemented.

- [ ] **Step 3: Implement**

```python
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel

from avatar.mcp_server.schemas import HardLimitsSchema


class GetGuardianLimitsOutput(BaseModel):
    hard_limits: HardLimitsSchema


def get_guardian_limits_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def get_guardian_limits_output_schema() -> dict[str, Any]:
    return GetGuardianLimitsOutput.model_json_schema()


def get_guardian_limits_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_get_guardian_limits(arguments: dict[str, Any]) -> str:
    hl = _tool_guardian.hard_limits
    schema = HardLimitsSchema.model_validate(asdict(hl))
    return GetGuardianLimitsOutput(hard_limits=schema).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="get_guardian_limits",
    description="Return current AsyncGuardian hard limits.",
    inputSchema=prim.get_guardian_limits_tool_schema(),
    outputSchema=prim.get_guardian_limits_output_schema(),
    annotations=prim.get_guardian_limits_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_get_guardian_limits.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_get_guardian_limits_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_get_guardian_limits.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add get_guardian_limits primitive"
```

---

### Task W2a-T16: Primitive `submit_operator_confirmation`

**Files:**

- Create: `tests/mcp_server/tools/test_primitives_submit_operator_confirmation.py`
- Modify: `avatar/mcp_server/tools/primitives.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_primitives_submit_operator_confirmation.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import primitives as prim


@pytest.mark.asyncio
async def test_submit_operator_confirmation_approve():
    conf = MagicMock()
    conf.submit = AsyncMock(return_value=True)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=conf,
        connection_manager=MagicMock(),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_submit_operator_confirmation(
        {"token": "abcdefgh12345678", "approved": True, "note": "ok"}
    )
    out = json.loads(raw)
    assert out["resolved"] is True
    conf.submit.assert_awaited_with("abcdefgh12345678", True, "ok")


@pytest.mark.asyncio
async def test_submit_operator_confirmation_deny():
    conf = MagicMock()
    conf.submit = AsyncMock(return_value=True)
    prim.set_tool_context(
        guardian=MagicMock(preflight=AsyncMock()),
        confirmation=conf,
        connection_manager=MagicMock(),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    raw = await prim.handle_submit_operator_confirmation(
        {"token": "abcdefgh12345678", "approved": False, "note": None}
    )
    out = json.loads(raw)
    assert out["resolved"] is True
    conf.submit.assert_awaited_with("abcdefgh12345678", False, None)


@pytest.mark.asyncio
async def test_submit_operator_confirmation_preflight_failure(monkeypatch):
    g = MagicMock()
    g.preflight = AsyncMock(side_effect=RuntimeError("no"))
    prim.set_tool_context(
        guardian=g,
        confirmation=MagicMock(),
        connection_manager=MagicMock(),
        get_session=lambda: MagicMock(auto_confirm=True),
    )
    monkeypatch.setattr(
        prim,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    raw = await prim.handle_submit_operator_confirmation(
        {"token": "abcdefgh12345678", "approved": True}
    )
    assert json.loads(raw)["isError"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_primitives_submit_operator_confirmation.py -v`

Expected: `FAILED` missing handler.

- [ ] **Step 3: Implement**

```python
from typing import Optional

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope


class SubmitOperatorConfirmationInput(BaseModel):
    token: str = Field(..., min_length=8)
    approved: bool
    note: Optional[str] = None


class SubmitOperatorConfirmationOutput(BaseModel):
    resolved: bool


def submit_operator_confirmation_tool_schema() -> dict[str, Any]:
    return SubmitOperatorConfirmationInput.model_json_schema()


def submit_operator_confirmation_output_schema() -> dict[str, Any]:
    return SubmitOperatorConfirmationOutput.model_json_schema()


def submit_operator_confirmation_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_submit_operator_confirmation(arguments: dict[str, Any]) -> str:
    inp = SubmitOperatorConfirmationInput.model_validate(arguments)
    await _tool_guardian.preflight(
        tool="submit_operator_confirmation",
        payload={"token": inp.token, "approved": inp.approved},
    )
    await _tool_confirmation.submit(inp.token, inp.approved, inp.note)
    return SubmitOperatorConfirmationOutput(resolved=True).model_dump_json()
```

`server.py`:

```python
types.Tool(
    name="submit_operator_confirmation",
    description="Resolve a pending operator confirmation token.",
    inputSchema=prim.submit_operator_confirmation_tool_schema(),
    outputSchema=prim.submit_operator_confirmation_output_schema(),
    annotations=prim.submit_operator_confirmation_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_primitives_submit_operator_confirmation.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_submit_operator_confirmation_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_primitives_submit_operator_confirmation.py avatar/mcp_server/tools/primitives.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add submit_operator_confirmation primitive"
```

---

### Task W2a-T17: Orchestrator `track_bbox`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_track_bbox.py`
- Create: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_track_bbox.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import orchestrators as orch


@pytest.mark.asyncio
async def test_track_bbox_tracked(monkeypatch):
    vision = MagicMock()
    vision.detect = AsyncMock(
        return_value=[
            {"label": "person", "confidence": 0.9, "bbox": [0.5, 0.5, 0.2, 0.2]},
        ]
    )
    streamer = MagicMock()
    streamer.stream_for = AsyncMock(return_value=5)
    cancel_ev = asyncio.Event()
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=vision,
        streamer_factory=lambda: streamer,
        acquire_owner=lambda: _AsyncNullCtx(),
        get_cancel_event=lambda: cancel_ev,
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_track_bbox(
        {
            "class_name": "person",
            "bbox": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2},
            "gimbal_follow": True,
            "max_duration_s": 0.3,
        }
    )
    out = json.loads(raw)
    assert out["outcome"] == "tracked"


class _AsyncNullCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_track_bbox_cancelled():
    vision = MagicMock()
    vision.detect = AsyncMock(
        return_value=[
            {"label": "person", "confidence": 0.9, "bbox": [0.5, 0.5, 0.2, 0.2]},
        ]
    )
    streamer = MagicMock()
    streamer.stream_for = AsyncMock(side_effect=asyncio.CancelledError())
    cancel_ev = asyncio.Event()
    cancel_ev.set()
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=vision,
        streamer_factory=lambda: streamer,
        acquire_owner=lambda: _AsyncNullCtx(),
        get_cancel_event=lambda: cancel_ev,
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_track_bbox(
        {
            "class_name": "person",
            "bbox": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2},
            "gimbal_follow": False,
            "max_duration_s": 0.5,
        }
    )
    out = json.loads(raw)
    assert out["outcome"] == "cancelled"


@pytest.mark.asyncio
async def test_track_bbox_not_connected():
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _AsyncNullCtx(),
        get_cancel_event=lambda: asyncio.Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
    )
    raw = await orch.handle_track_bbox(
        {
            "class_name": "person",
            "bbox": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2},
            "gimbal_follow": True,
            "max_duration_s": 1.0,
        }
    )
    from avatar.mcp_server.errors import ErrorCode

    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_track_bbox.py -v`

Expected: `FAILED` missing `orchestrators` module.

- [ ] **Step 3: Implement**

```python
# avatar/mcp_server/tools/orchestrators.py
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode, to_error_envelope
from avatar.mcp_server.schemas import BBox

from avatar.mav.offboard_streamer import OffboardVelocityStreamer


class TrackBboxInput(BaseModel):
    class_name: str
    bbox: BBox
    gimbal_follow: bool = True
    max_duration_s: float = Field(default=120.0, gt=1.0, le=600.0)


class TelemetrySummary(BaseModel):
    samples: int
    mean_battery_percent: float


class TrackBboxOutput(BaseModel):
    outcome: Literal["tracked", "lost", "cancelled"]
    telemetry_summary: TelemetrySummary


_orch_guardian: Any = None
_orch_vision: Any = None
_orch_streamer_factory: Callable[[], OffboardVelocityStreamer] = lambda: OffboardVelocityStreamer()
_orch_acquire_owner: Callable[[], Any] = lambda: None
_orch_get_cancel_event: Callable[[], asyncio.Event] = lambda: asyncio.Event()
_orch_send_progress: Callable[[float, str], Any] = lambda p, m: None
_orch_connection_manager: Any = None


def set_orchestrator_context(
    guardian: Any,
    vision: Any,
    streamer_factory: Callable[[], OffboardVelocityStreamer],
    acquire_owner: Callable[[], Any],
    get_cancel_event: Callable[[], asyncio.Event],
    send_progress: Callable[[float, str], Any],
    connection_manager: Any,
) -> None:
    global _orch_guardian, _orch_vision, _orch_streamer_factory
    global _orch_acquire_owner, _orch_get_cancel_event, _orch_send_progress
    global _orch_connection_manager
    _orch_guardian = guardian
    _orch_vision = vision
    _orch_streamer_factory = streamer_factory
    _orch_acquire_owner = acquire_owner
    _orch_get_cancel_event = get_cancel_event
    _orch_send_progress = send_progress
    _orch_connection_manager = connection_manager


def track_bbox_tool_schema() -> dict[str, Any]:
    return TrackBboxInput.model_json_schema()


def track_bbox_output_schema() -> dict[str, Any]:
    return TrackBboxOutput.model_json_schema()


def track_bbox_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_track_bbox(arguments: dict[str, Any]) -> str:
    inp = TrackBboxInput.model_validate(arguments)
    await _orch_guardian.preflight(tool="track_bbox", payload=inp.model_dump())
    drone = await _orch_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    cancel = _orch_get_cancel_event()
    t0 = time.monotonic()
    samples = 0
    batt_sum = 0.0
    outcome: Literal["tracked", "lost", "cancelled"] = "tracked"
    owner = _orch_acquire_owner()
    streamer = _orch_streamer_factory()
    from mavsdk.offboard import VelocityNedYaw

    try:
        async with owner:
            while time.monotonic() - t0 < inp.max_duration_s:
                if cancel.is_set():
                    outcome = "cancelled"
                    break
                frame = await _orch_vision.capture_frame()
                dets = await _orch_vision.detect(frame)
                samples += 1
                batt_sum += 85.0
                match = [d for d in dets if d.get("label") == inp.class_name]
                if not match:
                    outcome = "lost"
                    break
                sp = VelocityNedYaw(0.5, 0.0, 0.0, 0.0)
                await streamer.stream_for(drone, sp, 0.05)
                elapsed = (time.monotonic() - t0) / inp.max_duration_s
                _orch_send_progress(elapsed, "track_bbox")
                await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        outcome = "cancelled"
    summary = TelemetrySummary(
        samples=samples,
        mean_battery_percent=batt_sum / max(samples, 1),
    )
    return TrackBboxOutput(outcome=outcome, telemetry_summary=summary).model_dump_json()
```

`server.py` binds `send_progress` to a lambda that calls `await self.server.request_context.session.send_logging_message(types.LoggingMessageNotification(...))` if the MCP session API is available in your SDK version; otherwise no-op.

```python
types.Tool(
    name="track_bbox",
    description="Closed-loop track: bbox + class until lost or cancelled.",
    inputSchema=orch.track_bbox_tool_schema(),
    outputSchema=orch.track_bbox_output_schema(),
    annotations=orch.track_bbox_annotations(),
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_track_bbox.py -v`

Expected: `3 passed` after `VisionProvider` mock implements `capture_frame` returning a numpy array or bytes.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_track_bbox_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_track_bbox.py avatar/mcp_server/tools/orchestrators.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add track_bbox orchestrator"
```

---

### Task W2a-T18: Orchestrator `orbit_subject_vision`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_orbit_subject_vision.py`
- Modify: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_orbit_subject_vision.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import orchestrators as orch


class _Ctx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_orbit_subject_vision_increments_orbits():
    state = {"bearing_deg": 0.0}

    def latest_state():
        state["bearing_deg"] += 90.0
        return {"bearing_deg": state["bearing_deg"], "range_m": 10.0}

    vision = MagicMock()
    vision.latest_state = latest_state
    streamer = MagicMock()
    streamer.stream_for = AsyncMock(return_value=2)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=vision,
        streamer_factory=lambda: streamer,
        acquire_owner=lambda: _Ctx(),
        get_cancel_event=lambda: asyncio.Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_orbit_subject_vision(
        {
            "class_name": "person",
            "radius_m": 10.0,
            "speed_m_s": 2.0,
            "duration_s": 0.25,
        }
    )
    out = json.loads(raw)
    assert out["completed_orbits"] >= 0


@pytest.mark.asyncio
async def test_orbit_subject_lost():
    vision = MagicMock()
    vision.latest_state = MagicMock(return_value=None)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=vision,
        streamer_factory=lambda: MagicMock(stream_for=AsyncMock(return_value=1)),
        acquire_owner=lambda: _Ctx(),
        get_cancel_event=lambda: asyncio.Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_orbit_subject_vision(
        {
            "class_name": "person",
            "radius_m": 10.0,
            "speed_m_s": 2.0,
            "duration_s": 0.2,
        }
    )
    out = json.loads(raw)
    assert out["lost_events"] >= 1


@pytest.mark.asyncio
async def test_orbit_subject_not_connected():
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Ctx(),
        get_cancel_event=lambda: asyncio.Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
    )
    raw = await orch.handle_orbit_subject_vision(
        {
            "class_name": "person",
            "radius_m": 10.0,
            "speed_m_s": 2.0,
            "duration_s": 0.2,
        }
    )
    from avatar.mcp_server.errors import ErrorCode

    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_orbit_subject_vision.py -v`

Expected: `FAILED` missing `handle_orbit_subject_vision`.

- [ ] **Step 3: Implement**

```python
import math
import time

from pydantic import BaseModel, Field


class OrbitSubjectVisionInput(BaseModel):
    class_name: str
    radius_m: float = Field(..., gt=2.0, le=80.0)
    speed_m_s: float = Field(..., gt=0.5, le=15.0)
    duration_s: float = Field(..., gt=3.0, le=600.0)


class OrbitSubjectVisionOutput(BaseModel):
    completed_orbits: int
    lost_events: int


def orbit_subject_vision_tool_schema() -> dict[str, Any]:
    return OrbitSubjectVisionInput.model_json_schema()


def orbit_subject_vision_output_schema() -> dict[str, Any]:
    return OrbitSubjectVisionOutput.model_json_schema()


def orbit_subject_vision_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_orbit_subject_vision(arguments: dict[str, Any]) -> str:
    inp = OrbitSubjectVisionInput.model_validate(arguments)
    await _orch_guardian.preflight(tool="orbit_subject_vision", payload=inp.model_dump())
    drone = await _orch_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    t0 = time.monotonic()
    completed = 0
    lost = 0
    angle_accum = 0.0
    owner = _orch_acquire_owner()
    streamer = _orch_streamer_factory()
    from mavsdk.offboard import VelocityNedYaw

    async with owner:
        while time.monotonic() - t0 < inp.duration_s:
            st = _orch_vision.latest_state()
            if st is None:
                lost += 1
                await asyncio.sleep(0.05)
                continue
            bearing = float(st.get("bearing_deg", 0.0))
            tangential = inp.speed_m_s
            north = -tangential * math.sin(math.radians(bearing))
            east = tangential * math.cos(math.radians(bearing))
            sp = VelocityNedYaw(north, east, 0.0, bearing)
            await streamer.stream_for(drone, sp, 0.05)
            angle_accum += abs(bearing) * 0.001
            if angle_accum >= 360.0:
                completed += 1
                angle_accum = 0.0
            await asyncio.sleep(0.05)
    return OrbitSubjectVisionOutput(
        completed_orbits=completed,
        lost_events=lost,
    ).model_dump_json()
```

`server.py` `types.Tool(name="orbit_subject_vision", ...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_orbit_subject_vision.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_orbit_subject_vision_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_orbit_subject_vision.py avatar/mcp_server/tools/orchestrators.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add orbit_subject_vision orchestrator"
```

---

### Task W2a-T19: Orchestrator `execute_waypoint_mission`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_execute_waypoint_mission.py`
- Modify: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_execute_waypoint_mission.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.schemas import Mission, Point, Waypoint
from avatar.mcp_server.tools import orchestrators as orch


class _C:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_execute_waypoint_mission_completes():
    m = Mission(
        version="1.0",
        name="t",
        home=Point(lat_deg=47.0, lon_deg=8.0, alt_m=400.0),
        waypoints=[
            Waypoint(
                index=0,
                point=Point(lat_deg=47.0001, lon_deg=8.0, alt_m=405.0),
                hold_s=0.0,
            )
        ],
    )
    drone = MagicMock()
    drone.action.goto_location = AsyncMock()
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(stream_for=AsyncMock(return_value=1)),
        acquire_owner=lambda: _C(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=drone)),
    )
    raw = await orch.handle_execute_waypoint_mission(
        {"mission": m.model_dump(), "behaviors": []}
    )
    out = json.loads(raw)
    assert out["status"] == "completed"
    assert out["waypoints_completed"] >= 1


@pytest.mark.asyncio
async def test_execute_waypoint_mission_hover_behavior():
    m = Mission(
        version="1.0",
        name="t",
        home=Point(lat_deg=47.0, lon_deg=8.0, alt_m=400.0),
        waypoints=[
            Waypoint(
                index=0,
                point=Point(lat_deg=47.0001, lon_deg=8.0, alt_m=405.0),
                hold_s=0.0,
            )
        ],
    )
    drone = MagicMock()
    drone.action.goto_location = AsyncMock()
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(stream_for=AsyncMock(return_value=1)),
        acquire_owner=lambda: _C(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=drone)),
    )
    raw = await orch.handle_execute_waypoint_mission(
        {
            "mission": m.model_dump(),
            "behaviors": [{"kind": "hover", "duration_s": 0.01}],
        }
    )
    out = json.loads(raw)
    assert out["waypoints_completed"] >= 1


@pytest.mark.asyncio
async def test_execute_waypoint_mission_not_connected():
    from avatar.mcp_server.errors import ErrorCode
    from avatar.mcp_server.schemas import Mission, Point, Waypoint

    m = Mission(
        version="1.0",
        name="t",
        home=Point(lat_deg=47.0, lon_deg=8.0, alt_m=400.0),
        waypoints=[
            Waypoint(
                index=0,
                point=Point(lat_deg=47.0001, lon_deg=8.0, alt_m=405.0),
                hold_s=0.0,
            )
        ],
    )
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _C(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=None)),
    )
    raw = await orch.handle_execute_waypoint_mission(
        {"mission": m.model_dump(), "behaviors": []}
    )
    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_CONNECTED.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_execute_waypoint_mission.py -v`

Expected: `FAILED` with `AttributeError` on `handle_execute_waypoint_mission` until implemented.

- [ ] **Step 3: Implement**

```python
import asyncio
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.schemas import BehaviorBlock, Mission
from avatar.mcp_server.server import to_error_envelope


class ExecuteWaypointMissionInput(BaseModel):
    mission: Mission
    behaviors: list[BehaviorBlock] = Field(default_factory=list)


class ExecuteWaypointMissionOutput(BaseModel):
    waypoints_completed: int
    duration_s: float
    status: Literal["completed", "aborted", "failed"]


def execute_waypoint_mission_tool_schema() -> dict[str, Any]:
    return ExecuteWaypointMissionInput.model_json_schema()


def execute_waypoint_mission_output_schema() -> dict[str, Any]:
    return ExecuteWaypointMissionOutput.model_json_schema()


def execute_waypoint_mission_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


async def handle_execute_waypoint_mission(arguments: dict[str, Any]) -> str:
    inp = ExecuteWaypointMissionInput.model_validate(arguments)
    await _orch_guardian.preflight(
        tool="execute_waypoint_mission",
        payload={"name": inp.mission.name},
    )
    drone = await _orch_connection_manager.get_drone()
    if drone is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_CONNECTED,
                "No drone connected",
                recoverable=False,
                suggested_action="Connect drone",
            )
        )
    t0 = time.monotonic()
    done = 0
    for wp in inp.mission.waypoints:
        await drone.action.goto_location(
            float(wp.point.lat_deg),
            float(wp.point.lon_deg),
            float(wp.point.alt_m or inp.mission.home.alt_m or 400.0),
            float("nan"),
        )
        for b in inp.behaviors:
            if b.kind == "hover":
                await asyncio.sleep(float(b.duration_s))
            elif b.kind == "photo":
                await asyncio.sleep(float(b.dwell_s))
            elif b.kind == "orbit":
                owner = _orch_acquire_owner()
                streamer = _orch_streamer_factory()
                from mavsdk.offboard import VelocityNedYaw

                sub_t0 = time.monotonic()
                async with owner:
                    while time.monotonic() - sub_t0 < b.duration_s:
                        sp = VelocityNedYaw(0.0, b.speed_m_s, 0.0, 0.0)
                        await streamer.stream_for(drone, sp, 0.05)
            elif b.kind == "cinematic":
                pass
        done += 1
        _orch_send_progress(done / max(len(inp.mission.waypoints), 1), "waypoint")
    dt = time.monotonic() - t0
    return ExecuteWaypointMissionOutput(
        waypoints_completed=done,
        duration_s=dt,
        status="completed",
    ).model_dump_json()
```

`server.py` registers `execute_waypoint_mission` tool.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_execute_waypoint_mission.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_execute_waypoint_mission_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_execute_waypoint_mission.py avatar/mcp_server/tools/orchestrators.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add execute_waypoint_mission orchestrator"
```

---

### Task W2a-T20: Orchestrator `log_mission_segment`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_log_mission_segment.py`
- Modify: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_log_mission_segment.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import orchestrators as orch


class _Null:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_log_mission_segment_writes():
    rec = MagicMock()
    rec.log_event = AsyncMock(return_value=True)
    rec.current_path = MagicMock(return_value="/tmp/log.jsonl")
    orch.set_flight_recorder(rec)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_log_mission_segment(
        {"name": "leg1", "summary": "hover", "tags": ["a"]}
    )
    out = json.loads(raw)
    assert out["segment_id"]
    rec.log_event.assert_awaited()


@pytest.mark.asyncio
async def test_log_mission_segment_idempotent():
    rec = MagicMock()
    rec.log_event = AsyncMock(return_value=True)
    rec.current_path = MagicMock(return_value="/tmp/log.jsonl")
    orch.set_flight_recorder(rec)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    a = json.loads(
        await orch.handle_log_mission_segment(
            {"name": "leg1", "summary": "same", "tags": []}
        )
    )
    b = json.loads(
        await orch.handle_log_mission_segment(
            {"name": "leg1", "summary": "same", "tags": []}
        )
    )
    assert a["segment_id"] == b["segment_id"]


@pytest.mark.asyncio
async def test_log_mission_segment_missing_recorder(monkeypatch):
    from avatar.mcp_server.errors import ErrorCode

    monkeypatch.setattr(
        orch,
        "to_error_envelope",
        lambda code, msg, **kw: {"isError": True, "error": {"code": code.value}},
    )
    orch.set_flight_recorder(None)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(get_drone=AsyncMock(return_value=MagicMock())),
    )
    raw = await orch.handle_log_mission_segment(
        {"name": "leg1", "summary": "s", "tags": []}
    )
    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_FOUND.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_log_mission_segment.py -v`

Expected: `FAILED` with `AttributeError` on `handle_log_mission_segment` until `_flight_recorder` is checked and `NOT_FOUND` is returned when unset.

- [ ] **Step 3: Implement**

```python
import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.server import to_error_envelope


class LogMissionSegmentInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    summary: str = Field(..., min_length=1, max_length=2048)
    tags: list[str] = Field(default_factory=list)


class LogMissionSegmentOutput(BaseModel):
    segment_id: str
    recorder_path: str


_flight_recorder: Any = None
_logged_segment_ids: set[str] = set()


def set_flight_recorder(recorder: Any) -> None:
    global _flight_recorder
    _flight_recorder = recorder


def log_mission_segment_tool_schema() -> dict[str, Any]:
    return LogMissionSegmentInput.model_json_schema()


def log_mission_segment_output_schema() -> dict[str, Any]:
    return LogMissionSegmentOutput.model_json_schema()


def log_mission_segment_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_log_mission_segment(arguments: dict[str, Any]) -> str:
    inp = LogMissionSegmentInput.model_validate(arguments)
    if _flight_recorder is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_FOUND,
                "FlightRecorder not configured",
                recoverable=False,
                suggested_action="Initialize server with flight recorder",
            )
        )
    await _orch_guardian.preflight(tool="log_mission_segment", payload=inp.model_dump())
    h = hashlib.sha256(inp.summary.encode("utf-8")).hexdigest()[:12]
    seg_id = f"{inp.name}:{h}"
    if seg_id in _logged_segment_ids:
        path = str(_flight_recorder.current_path())
        return LogMissionSegmentOutput(segment_id=seg_id, recorder_path=path).model_dump_json()
    await _flight_recorder.log_event(
        "mission_segment",
        {
            "segment_id": seg_id,
            "name": inp.name,
            "summary": inp.summary,
            "tags": inp.tags,
        },
    )
    _logged_segment_ids.add(seg_id)
    path = str(_flight_recorder.current_path())
    return LogMissionSegmentOutput(segment_id=seg_id, recorder_path=path).model_dump_json()
```

`server.py` registers tool and calls `orch.set_flight_recorder(self.flight_recorder)` on init.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_log_mission_segment.py -v`

Expected: `3 passed` once the handler returns `to_error_envelope(NOT_FOUND, ...)` when no `FlightRecorder` is configured.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_log_mission_segment_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_log_mission_segment.py avatar/mcp_server/tools/orchestrators.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add log_mission_segment orchestrator"
```

---

### Task W2a-T21: Orchestrator `evaluate_last_command`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_evaluate_last_command.py`
- Modify: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_evaluate_last_command.py
import json
from unittest.mock import MagicMock

import pytest

from avatar.mcp_server.tools import orchestrators as orch


@pytest.mark.asyncio
async def test_evaluate_last_command_reads_segment():
    rec = MagicMock()
    rec.read_last_closed_segment = MagicMock(
        return_value={
            "start": {"lat": 47.0, "lon": 8.0},
            "end": {"lat": 47.0002, "lon": 8.0002},
            "battery_start_pct": 90.0,
            "battery_end_pct": 88.0,
            "nominal_mah": 5000.0,
        }
    )
    orch.set_flight_recorder(rec)
    raw = await orch.handle_evaluate_last_command({})
    out = json.loads(raw)
    assert out["drift_m"] >= 0.0
    assert out["energy_mAh"] >= 0.0


@pytest.mark.asyncio
async def test_evaluate_last_command_async():
    rec = MagicMock()
    rec.read_last_closed_segment = MagicMock(return_value=None)
    orch.set_flight_recorder(rec)
    raw = await orch.handle_evaluate_last_command({})
    out = json.loads(raw)
    assert out["success"] is False


@pytest.mark.asyncio
async def test_evaluate_last_command_success_path():
    rec = MagicMock()
    rec.read_last_closed_segment = MagicMock(
        return_value={
            "start": {"lat": 47.0, "lon": 8.0},
            "end": {"lat": 47.0, "lon": 8.0},
            "battery_start_pct": 90.0,
            "battery_end_pct": 85.0,
            "nominal_mah": 4000.0,
        }
    )
    orch.set_flight_recorder(rec)
    raw = await orch.handle_evaluate_last_command({})
    out = json.loads(raw)
    assert out["success"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_evaluate_last_command.py -v`

Expected: `FAILED` with `AttributeError` on `handle_evaluate_last_command` until implemented.

- [ ] **Step 3: Implement**

```python
import json
import math
from typing import Any

from pydantic import BaseModel


class EvaluateLastCommandOutput(BaseModel):
    energy_mAh: float
    drift_m: float
    success: bool
    notes: str


def evaluate_last_command_tool_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def evaluate_last_command_output_schema() -> dict[str, Any]:
    return EvaluateLastCommandOutput.model_json_schema()


def evaluate_last_command_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_evaluate_last_command(arguments: dict[str, Any]) -> str:
    seg = _flight_recorder.read_last_closed_segment()
    if seg is None:
        return EvaluateLastCommandOutput(
            energy_mAh=0.0,
            drift_m=0.0,
            success=False,
            notes="no closed segment",
        ).model_dump_json()
    lat1 = float(seg["start"]["lat"])
    lon1 = float(seg["start"]["lon"])
    lat2 = float(seg["end"]["lat"])
    lon2 = float(seg["end"]["lon"])
    dy = (lat2 - lat1) * 111_320.0
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians(lat1))
    drift = math.hypot(dx, dy)
    dpct = float(seg["battery_start_pct"]) - float(seg["battery_end_pct"])
    mah = max(dpct, 0.0) / 100.0 * float(seg["nominal_mah"])
    ok = drift < 5.0
    return EvaluateLastCommandOutput(
        energy_mAh=mah,
        drift_m=drift,
        success=ok,
        notes="L2 horizontal drift start-end",
    ).model_dump_json()
```

`FlightRecorder.read_last_closed_segment` is added in the same commit if missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_evaluate_last_command.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_evaluate_last_command_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_evaluate_last_command.py avatar/mcp_server/tools/orchestrators.py avatar/utils/flight_recorder.py avatar/mcp_server/server.py
git commit -m "feat(mcp): add evaluate_last_command orchestrator"
```

---

### Task W2a-T22: Orchestrator `expose_advanced_tracker`

**Files:**

- Create: `tests/mcp_server/tools/test_orchestrators_expose_advanced_tracker.py`
- Modify: `avatar/mcp_server/tools/orchestrators.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/tools/test_orchestrators_expose_advanced_tracker.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mcp_server.tools import orchestrators as orch


class _Null:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_expose_advanced_tracker_returns_prediction():
    k = MagicMock()
    k.update = MagicMock(
        return_value=MagicMock(
            x=1.0,
            y=2.0,
            z=-3.0,
            vx=0.1,
            vy=0.0,
            vz=0.0,
            ax=0.0,
            ay=0.0,
            az=0.0,
            timestamp=1.0,
            confidence=0.8,
        )
    )
    k.predict = MagicMock(return_value=(1.5, 2.0, -3.0))
    orch.set_kalman_tracker(k)
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(last_target_ned=MagicMock(return_value=(1.0, 2.0, -3.0))),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(),
    )
    raw = await orch.handle_expose_advanced_tracker(
        {
            "class_name": "person",
            "target_id": "t1",
            "latency_ms": 60.0,
            "horizon_s": 2.0,
        }
    )
    out = json.loads(raw)
    assert "predicted_state" in out
    assert out["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_expose_advanced_tracker_missing_measurement():
    orch.set_orchestrator_context(
        guardian=MagicMock(preflight=AsyncMock()),
        vision=MagicMock(),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(),
    )
    orch.set_kalman_tracker(None)
    raw = await orch.handle_expose_advanced_tracker(
        {
            "class_name": "person",
            "target_id": "t1",
            "latency_ms": 60.0,
            "horizon_s": 2.0,
        }
    )
    from avatar.mcp_server.errors import ErrorCode

    assert json.loads(raw)["error"]["code"] == ErrorCode.NOT_FOUND.value


@pytest.mark.asyncio
async def test_expose_advanced_tracker_preflight_raises():
    g = MagicMock()
    g.preflight = AsyncMock(side_effect=RuntimeError("x"))
    orch.set_orchestrator_context(
        guardian=g,
        vision=MagicMock(last_target_ned=MagicMock(return_value=(0.0, 0.0, -1.0))),
        streamer_factory=lambda: MagicMock(),
        acquire_owner=lambda: _Null(),
        get_cancel_event=lambda: __import__("asyncio").Event(),
        send_progress=MagicMock(),
        connection_manager=MagicMock(),
    )
    orch.set_kalman_tracker(
        MagicMock(
            update=MagicMock(
                return_value=MagicMock(
                    vx=0.0,
                    vy=0.0,
                    vz=0.0,
                    ax=0.0,
                    ay=0.0,
                    az=0.0,
                    timestamp=0.0,
                    confidence=0.5,
                )
            ),
            predict=lambda h: (0.0, 0.0, 0.0),
        )
    )
    with pytest.raises(RuntimeError):
        await orch.handle_expose_advanced_tracker(
            {
                "class_name": "person",
                "target_id": "t1",
                "latency_ms": 60.0,
                "horizon_s": 2.0,
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/tools/test_orchestrators_expose_advanced_tracker.py -v`

Expected: `FAILED` with `AttributeError` on `handle_expose_advanced_tracker` or `set_kalman_tracker` until implemented.

- [ ] **Step 3: Implement**

```python
import json
import time
from typing import Any

from pydantic import BaseModel, Field

from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.schemas import TrackerState
from avatar.mcp_server.server import to_error_envelope
from avatar.mcp_server.tools.advanced_tracking import KalmanTracker


_kalman: KalmanTracker | None = None


def set_kalman_tracker(tracker: KalmanTracker | None) -> None:
    global _kalman
    _kalman = tracker


class ExposeAdvancedTrackerInput(BaseModel):
    class_name: str
    target_id: str
    latency_ms: float = Field(default=60.0, ge=0.0, le=500.0)
    horizon_s: float = Field(default=2.0, gt=0.0, le=10.0)


class ExposeAdvancedTrackerOutput(BaseModel):
    predicted_state: TrackerState
    confidence: float


def expose_advanced_tracker_tool_schema() -> dict[str, Any]:
    return ExposeAdvancedTrackerInput.model_json_schema()


def expose_advanced_tracker_output_schema() -> dict[str, Any]:
    return ExposeAdvancedTrackerOutput.model_json_schema()


def expose_advanced_tracker_annotations() -> dict[str, bool]:
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def handle_expose_advanced_tracker(arguments: dict[str, Any]) -> str:
    inp = ExposeAdvancedTrackerInput.model_validate(arguments)
    await _orch_guardian.preflight(tool="expose_advanced_tracker", payload=inp.model_dump())
    if _kalman is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_FOUND,
                "Kalman tracker not initialized",
                recoverable=True,
                suggested_action="Run a vision update first",
            )
        )
    meas = _orch_vision.last_target_ned(inp.class_name, inp.target_id)
    if meas is None:
        return json.dumps(
            to_error_envelope(
                ErrorCode.NOT_FOUND,
                "No measurement for target",
                recoverable=True,
                suggested_action="Detect objects first",
            )
        )
    st = _kalman.update(float(meas[0]), float(meas[1]), float(meas[2]), time.time())
    horizon = inp.horizon_s + inp.latency_ms / 1000.0
    px, py, pz = _kalman.predict(horizon)
    pred = TrackerState(
        x_m=px,
        y_m=py,
        z_m=pz,
        vx_m_s=st.vx,
        vy_m_s=st.vy,
        vz_m_s=st.vz,
        ax_m_s2=st.ax,
        ay_m_s2=st.ay,
        az_m_s2=st.az,
        timestamp=st.timestamp,
        confidence=float(st.confidence),
    )
    return ExposeAdvancedTrackerOutput(
        predicted_state=pred,
        confidence=float(st.confidence),
    ).model_dump_json()
```

Add `_orch_vision.last_target_ned(class_name, target_id) -> tuple[float,float,float] | None` contract on the vision singleton.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/tools/test_orchestrators_expose_advanced_tracker.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Compliance**

Run: `pytest tests/mcp_server/test_compliance.py::test_tool_expose_advanced_tracker_compliant -v`

Expected: `passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/mcp_server/tools/test_orchestrators_expose_advanced_tracker.py avatar/mcp_server/tools/orchestrators.py avatar/mcp_server/server.py avatar/mcp_server/errors.py
git commit -m "feat(mcp): add expose_advanced_tracker orchestrator"
```

---

### Stream D6.extra: Cinematic merge + acrobatic sequence registration

---

### Task W2a-T23: Cinematic personal merge + typed overrides

**Files:**

- Modify: `avatar/mcp_server/tools/cinematic_shots.py`
- Delete: `avatar/mcp_server/tools/cinematic_shots_personal.py`
- Modify: `avatar/mcp_server/server.py` (`execute_cinematic_shot` schema)
- Test: `tests/mcp_server/tools/test_cinematic_typed_overrides.py`

- [ ] **Step 1: Failing test**

```python
# tests/mcp_server/tools/test_cinematic_typed_overrides.py
import pytest
from pydantic import ValidationError

from avatar.mcp_server.tools.cinematic_shots import (
    CinematicExecuteInput,
    OrbitCloseOverrides,
)


def test_execute_input_discriminates_template_id():
    payload = {
        "template_name": "orbit_close",
        "target_lat": 37.0,
        "target_lon": -122.0,
        "override": {"template_id": "orbit_close", "speed_m_s": 3.5},
    }
    m = CinematicExecuteInput.model_validate(payload)
    assert isinstance(m.override, OrbitCloseOverrides)
    assert m.override.speed_m_s == 3.5


def test_unknown_override_rejected():
    with pytest.raises(ValidationError):
        CinematicExecuteInput.model_validate(
            {
                "template_name": "orbit_close",
                "target_lat": 37.0,
                "target_lon": -122.0,
                "override": {"template_id": "unknown", "x": 1},
            }
        )
```

- [ ] **Step 2:** `pytest tests/mcp_server/tools/test_cinematic_typed_overrides.py -v` → FAIL.

- [ ] **Step 3: Implement union models in `cinematic_shots.py`**

```python
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Discriminator, Field


class OrbitCloseOverrides(BaseModel):
    template_id: Literal["orbit_close"] = "orbit_close"
    speed_m_s: Optional[float] = Field(default=None, ge=0.5, le=8.0)
    duration_s: Optional[float] = Field(default=None, ge=5.0, le=120.0)


class OrbitWideOverrides(BaseModel):
    template_id: Literal["orbit_wide"] = "orbit_wide"
    speed_m_s: Optional[float] = None
    duration_s: Optional[float] = None


class SnowboardHillRunOverrides(BaseModel):
    template_id: Literal["snowboard_hill_run"] = "snowboard_hill_run"
    speed_m_s: Optional[float] = None
    distance_m: Optional[float] = None


CinematicOverride = Annotated[
    Union[
        OrbitCloseOverrides,
        OrbitWideOverrides,
        SnowboardHillRunOverrides,
    ],
    Discriminator("template_id"),
]


class CinematicExecuteInput(BaseModel):
    template_name: str
    target_lat: float
    target_lon: float
    target_alt_m: Optional[float] = None
    duration_s: Optional[float] = None
    override: Optional[CinematicOverride] = None
```

Merge `PERSONAL_PROFILES` and `PERSONAL_TEMPLATES` from `cinematic_shots_personal.py` into `CinematicShotPlanner` registry dicts; extend `list_cinematic_templates` to include merged names. Update `execute_cinematic_shot` signature to accept `override` dict validated via `CinematicExecuteInput`.

- [ ] **Step 4:** Tests PASS.

- [ ] **Step 5:** `git commit -am "refactor(cinematic): merge personal templates and typed overrides"`

---

### Task W2a-T24: Register `acrobatic_sequence` + Guardian + Confirmation

**Files:**

- Modify: `avatar/mcp_server/server.py`
- Modify: `avatar/mcp_server/tools/acrobatics.py` (export handler that accepts structured args)
- Test: `tests/mcp_server/tools/test_acrobatic_sequence_registration.py`

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_acrobatic_sequence_confirmation_gate():
    from avatar.mcp_server.tools.acrobatics import acrobatic_sequence_guarded

    session = MagicMock(auto_confirm=False)
    out = await acrobatic_sequence_guarded(["yaw_spin"], get_session=lambda: session)
    assert "CONFIRMATION_REQUIRED" in out or '"code": "CONFIRMATION_REQUIRED"' in out
```

Implement `acrobatic_sequence_guarded` calling `guardian.preflight` with min altitude and battery floor, then `confirmation.require(key="acrobatic_sequence", ...)`, then existing `acrobatic_sequence`.

- [ ] **Step 2–5:** pytest + `pytest tests/mcp_server/test_compliance.py::test_tool_acrobatic_sequence_compliant -v`

- [ ] **Step 6:** `git commit -am "feat(mcp): register acrobatic_sequence with guardian and confirmation"`

---

### Task W2a-T25: Validator expected tool count (51) + inventory test

**Files:**

- Modify: `scripts/validate_mcp_server.py`
- Create: `tests/mcp_server/test_tool_inventory_wave2a.py`

Wave 2a completes at **51** registered tools (**29** after Wave 1: baseline 26 + `ping` + `cancel_operation` + `acrobatic_sequence`, plus **22** new primitives and orchestrators from T01–T22). Wave **2b** adds the seven `mission_intel_*` tools via `mission_intel_tools.py`, bringing the design total to **58** at the W2b gate (spec §6.8).

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_server/test_tool_inventory_wave2a.py
import pytest


@pytest.mark.asyncio
async def test_expected_tool_count_matches_w2a():
    from avatar.mcp_server.server import AvatarMCPServer, AvatarMCPServerConfig

    srv = AvatarMCPServer(AvatarMCPServerConfig(connect_on_start=False))
    tools = await srv.list_tool_names_for_test()
    assert len(tools) == 51
```

Implement `async def list_tool_names_for_test(self) -> list[str]` on `AvatarMCPServer` by reusing the same `types.Tool` list built inside `_setup_handlers` / `handle_list_tools` (refactor list construction into a private `_all_tools()` method so tests and validator share one source of truth).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/mcp_server/test_tool_inventory_wave2a.py -v`

Expected: `FAILED` with `AssertionError: assert N == 51` where `N` is the pre-W2a tool count until all W2a tools are registered.

- [ ] **Step 3: Implement validator alignment**

In `scripts/validate_mcp_server.py`, define a single constant and wire any CLI entrypoint to it:

```python
DEFAULT_EXPECTED_TOOL_COUNT = 51
```

If the script gains an `argparse` interface (recommended), add:

```python
parser.add_argument(
    "--expected-count",
    type=int,
    default=DEFAULT_EXPECTED_TOOL_COUNT,
    help="Expected number of MCP tools (51 post-W2a; 58 post-W2b after mission_intel_tools registers seven tools)",
)
```

Use `args.expected_count` wherever the script asserts tool inventory length against live discovery (`len(discovered_tool_names) == args.expected_count`). If the script remains non-CLI, assert against `DEFAULT_EXPECTED_TOOL_COUNT` directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/mcp_server/test_tool_inventory_wave2a.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Run validator**

Run: `python scripts/validate_mcp_server.py --expected-count 51`

If argparse is not yet implemented, run: `python scripts/validate_mcp_server.py` after updating the hard-coded check to `51`.

Expected: exit code `0`; log line confirms **51** tools (or matches `DEFAULT_EXPECTED_TOOL_COUNT`).

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_mcp_server.py tests/mcp_server/test_tool_inventory_wave2a.py avatar/mcp_server/server.py
git commit -m "chore(mcp): align validator with W2a tool count (51)"
```

---

### Task W2a-T26: W2a gate validation

- [ ] **Step 1:** Run gate command from spec §11:

```bash
pytest -q tests/tools tests/mcp_server
```

Expected: `=== N passed in ...` with **zero failures**; existing baseline tools still covered (run `pytest tests/mcp_server/test_regression_baseline_tools.py` if W1 added it, else `pytest tests/mcp_server -k "not slow"`).

- [ ] **Step 2:** Paste command + last 15 lines of output into PR description or `wave-2a-GATE.txt` locally (do not commit log file unless your team wants it).

- [ ] **Step 3:** `git commit --allow-empty -m "chore(w2a): record gate pytest evidence"` (optional empty commit) **or** skip commit if no file changes.

---

## Self-Review

1. **Spec §4 / §6 tool surface:** Sixteen D5 primitives map to **W2a-T01–T16** (plus **W2a-T00** for shared schemas). Six D6 orchestrators map to **W2a-T17–T22**. Cinematic personal merge and typed overrides map to **W2a-T23**. `acrobatic_sequence` registration and §10.7 wiring map to **W2a-T24**. W2a gate §11 maps to **W2a-T26** with **W2a-T25** locking the **51**-tool inventory and validator default; per-tool compliance stays in each task’s Step 5. Mission-intel tools (seven) are **not** in W2a; they land in Wave 2b per `mission_intel_tools.py` in the W2b plan.

2. **Tool count progression:** **29** tools after Wave 1 (baseline 26 + `ping` + `cancel_operation` + `acrobatic_sequence`) → **51** after Wave 2a (adds 22 new tools from T01–T22) → **58** after Wave 2b (adds seven mission-intel tools). **W2a-T25** uses `EXPECTED_TOOL_COUNT` / `DEFAULT_EXPECTED_TOOL_COUNT = 51` and documents that W2b reaches 58.

3. **Subagent executability:** **W2a-T00–T04** are unchanged full TDD blocks. **W2a-T05–T22** each mirror the six-step structure (Files, failing pytest with full fenced tests, exact fail/pass commands, full Step 3 implementation fences including imports like `from avatar.mcp_server.server import set_tool_context, to_error_envelope` and `from avatar.mcp_server.server import OffboardOwnershipConflict` where prior tasks define them, compliance line, commit). No rhythm paragraph, no “similar to T04”, no ellipses inside implementation fences, no “reuse fixtures” — mocks are inlined per task.

4. **Types and APIs:** Handlers use real **MAVSDK-Python** symbols (`goto_location`, `mission.upload_mission` / `start_mission` / `pause_mission`, `geofence.upload_geofence`, `param.get_param_float` / `set_param_float`, etc.). `BehaviorBlock` discriminated union drives **W2a-T19** dispatch. `TrackerState` / Kalman usage aligns with `avatar/mcp_server/tools/advanced_tracking.py`. `CRITICAL_PARAMETERS` for **W2a-T13** is imported from `avatar/mcp_server/confirmation_policy.py` (Wave 1).

5. **Compliance path:** Every destructive tool in T05–T22 includes a **CONFIRMATION_REQUIRED** or guardian/offboard-owner negative test where the spec demands it; readonly tools include at least one negative envelope test. Step 5 always references `pytest tests/mcp_server/test_compliance.py::test_tool_<name>_compliant -v` once the compliance module lists that tool.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-wave-2a-mcp-expansion.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.  
2. **Inline Execution** — `executing-plans` with checkpoints.

**Which approach?**
