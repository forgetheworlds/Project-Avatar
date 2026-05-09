# Wave 4 — HITL Harness + Runbooks + Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Project Avatar’s **Wave 4 — Final validation**: hardware-gated HITL pytest harness under `tests/hitl/`, operator runbooks under `docs/runbooks/`, repo polish (README, CHANGELOG, plan archive index), and the §9.5 **trivial flash** reference script so first flight is a procedure, not ad-hoc debugging.

**Architecture:** Pytest owns gating (`--run-hitl`, `hitl` / `preflight` markers, deterministic skips). Two fixture modules (`fc_bench`, `pi_plus_fc`) expose MAVSDK connection strings and health checks for the two HITL topologies from spec §9.3. Scenario-style checks reuse `avatar/sim/runner.py` (W2b) for YAML-driven stages where safe; Gazebo-only injections remain skipped with explicit reasons. Runbooks mirror real CLI from `hardware/px4/preflight.py`, `hardware/px4/calibrate.py`, and MCP tools—**not** airspace/NOTAM/weather (out of scope per spec §13).

**Tech Stack:** Python 3.12+, pytest, MAVSDK-Python, optional SSH for Pi path, bash for `scripts/trivial-flash.sh`, markdown for runbooks.

---

## Wave Scope

- **In scope:** `tests/hitl/` layout and tests per shared signature contract; `docs/runbooks/*.md`; `scripts/trivial-flash.sh`; README/CHANGELOG/plan archive polish; W4 gate command from spec §11.
- **Explicitly out of scope (spec §13):** NOTAM/TFR, weather APIs, power-line DB beyond OSM tags, ROS2 migration, fixed-wing/VTOL, agent-authoring inside MCP, paid mapping tiers. Runbooks must **not** add operational steps that require those capabilities; where readers might expect them, add one line: “Out of scope; see spec §13.”

---

## Dependencies

Assume **Wave 3 complete** before starting Wave 4:

- All **12** scenario pipelines green in Gazebo tier (`scripts/sim.sh all-scenarios` or equivalent W3 orchestrator).
- CI workflows (`.github/workflows/*`) green on a fresh clone.
- `hardware/pi/build-image.sh --dry-run` succeeds.
- `hardware/px4/preflight.py --dry-run --airframe mark4_7in` succeeds and prints a structured PASS/FAIL report.
- `avatar/sim/runner.py` implements `ScenarioLoader`, `Orchestrator`, `InjectionScheduler`, and drivers including **`OffboardFreezeDriver`**, **`RcLossDriver`**, **`BatteryDrainDriver`**, **`NetworkPartitionDriver`** (HITL-compatible subset).

If any upstream path is missing at pick-up time, **stop** and complete the blocking wave task first—this plan does not re-implement W2b/W3.

---

## Wave Gate

Copy from [spec §11](file:///Users/muadhsambul/Downloads/Project-Avatar/docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md):

| Wave | Gate | Verification |
|------|------|----------------|
| **W4** | HITL green on real FC (minimum SIH-on-FC mode); first-flight runbook reviewed; CHANGELOG + archive updated | `pytest tests/hitl -m preflight --run-hitl` |

---

## Branch Setup

Create and work on branch:

```bash
git checkout -b wave-4-hitl-runbook
```

All Wave 4 commits land on this branch; merge only after W4 gate row is satisfied.

---

## File map (Wave 4 touch list)

| Path | Role |
|------|------|
| `tests/hitl/__init__.py` | Package marker |
| `tests/hitl/conftest.py` | `--run-hitl`, markers, env gate, device discovery, collection-time skips |
| `tests/hitl/fixtures/fc_bench.py` | SIH-on-FC bench (USB), `SYS_HITL=2` assumption |
| `tests/hitl/fixtures/pi_plus_fc.py` | Laptop → Pi `mavsdk_server` → FC UART |
| `tests/hitl/test_hitl_failsafes.py` | Battery / RC loss / offboard freeze |
| `tests/hitl/test_hitl_scenarios.py` | YAML subset; skips Gazebo-only |
| `tests/hitl/test_hitl_preflight.py` | Wraps `hardware/px4/preflight.py` |
| `docs/runbooks/preflight.md` | Operator preflight |
| `docs/runbooks/first-flight.md` | Tethered first flight |
| `docs/runbooks/troubleshooting.md` | ErrorCode → remediation |
| `docs/runbooks/calibration.md` | Sensor calibration cadence |
| `docs/runbooks/field-kit.md` | Packing list |
| `scripts/trivial-flash.sh` | §9.5 five-step convenience script |
| `README.md` | Status + Docker SIH + hardware + CI badges |
| `CHANGELOG.md` | `[Unreleased]` + `0.5.0` first-flight-ready rollup |
| `docs/superpowers/plans/archive/` | Archived prior-wave plans |
| `docs/superpowers/plans/README.md` | Index of active + archived plans |
| `changes-made.md` | Final stamp entry D16.10 |

---

### Stream D15: HITL Harness

**Ordering:** Complete D15.1 → D15.7 **before** any D16 work. D16 runbooks cite `pytest tests/hitl/...` commands that only exist after D15.

---

### Task D15.1: `tests/hitl` package + `conftest.py` (options, markers, skips, discovery)

**Files:**

- Create: `tests/hitl/__init__.py`
- Create: `tests/hitl/conftest.py`

- [ ] **Step 1: Create empty package**

Create `tests/hitl/__init__.py`:

```python
"""Hardware-in-the-loop tests (gated)."""
```

- [ ] **Step 2: Implement `conftest.py`**

Create `tests/hitl/conftest.py`:

```python
from __future__ import annotations

import glob
import os
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-hitl",
        action="store_true",
        default=False,
        help="Enable hardware HITL tests (requires FC and/or Pi)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "hitl: gated hardware-in-the-loop tests")
    config.addinivalue_line("markers", "preflight: HITL preflight gate subset (W4)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-hitl"):
        return
    skip_if = pytest.mark.skip(reason="HITL gate not enabled (pass --run-hitl)")
    for item in items:
        if item.get_closest_marker("hitl"):
            item.add_marker(skip_if)


def discover_serial_device() -> str | None:
    """Return first responsive serial device path, or None."""
    candidates: list[Path] = []
    pix = Path("/dev/pixhawk")
    if pix.exists():
        candidates.append(pix)
    candidates.extend(sorted(Path(p) for p in glob.glob("/dev/ttyUSB*")))
    for p in candidates:
        if p.is_char_device():
            return str(p)
    return None


@pytest.fixture(scope="session")
def hitl_target(request: pytest.FixtureRequest) -> str:
    if not request.config.getoption("--run-hitl"):
        pytest.skip("HITL gate not enabled (pass --run-hitl)")
    target = os.environ.get("AVATAR_HITL_TARGET")
    if not target:
        pytest.skip("AVATAR_HITL_TARGET unset (expected fc_bench or pi_plus_fc)")
    if target not in ("fc_bench", "pi_plus_fc"):
        pytest.skip(f"AVATAR_HITL_TARGET={target!r} invalid (expected fc_bench or pi_plus_fc)")
    return target


@pytest.fixture(scope="session")
def serial_device(hitl_target: str) -> str:
    dev = discover_serial_device()
    if hitl_target == "fc_bench" and dev is None:
        pytest.skip("HITL target fc_bench not found (/dev/pixhawk missing)")
    if dev is None:
        pytest.skip("No serial device found (/dev/pixhawk and /dev/ttyUSB* absent)")
    return dev
```

- [ ] **Step 3: Dry-run collection (no hardware)**

Run:

```bash
python3 -m pytest tests/hitl --collect-only -q
```

Expected: tests collected; each `hitl` item shows skip reason `HITL gate not enabled (pass --run-hitl)` in `-rs` output when running:

```bash
python3 -m pytest tests/hitl -rs --collect-only
```

- [ ] **Step 4: Commit**

```bash
git add tests/hitl/__init__.py tests/hitl/conftest.py
git commit -m "test(hitl): add conftest and device discovery gates"
```

---

### Task D15.2: Fixture `fc_bench` (SIH-on-FC, USB)

**Files:**

- Create: `tests/hitl/fixtures/__init__.py`
- Create: `tests/hitl/fixtures/fc_bench.py`

- [ ] **Step 1: Package init**

`tests/hitl/fixtures/__init__.py`:

```python
"""HITL session fixtures."""
```

- [ ] **Step 2: Implement bench fixture**

`tests/hitl/fixtures/fc_bench.py`:

```python
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def fc_bench_mavsdk_uri(serial_device: str, hitl_target: str) -> str:
    if hitl_target != "fc_bench":
        pytest.skip(f"fc_bench fixture requires AVATAR_HITL_TARGET=fc_bench, got {hitl_target!r}")
    # PX4 SIH-on-FC: SYS_HITL=2 — MAVSDK over USB serial
    baud = int(os.environ.get("AVATAR_FC_SERIAL_BAUD", "921600"))
    return f"serial://{serial_device}:{baud}"
```

Document in module docstring that operator must set `SYS_HITL=2` on the FC per PX4 SIH-on-FC docs before running.

- [ ] **Step 3: Commit**

```bash
git add tests/hitl/fixtures/__init__.py tests/hitl/fixtures/fc_bench.py
git commit -m "test(hitl): add fc_bench SIH-on-FC fixture"
```

---

### Task D15.3: Fixture `pi_plus_fc` (MCP laptop → Pi → FC UART)

**Files:**

- Create: `tests/hitl/fixtures/pi_plus_fc.py`

- [ ] **Step 1: Implement fixture**

`tests/hitl/fixtures/pi_plus_fc.py`:

```python
from __future__ import annotations

import os
import shutil
import subprocess

import pytest


def _pi_host() -> str:
    return os.environ.get("AVATAR_PI_HOST", "avatar.local")


@pytest.fixture(scope="session")
def pi_plus_fc_mavsdk_uri(hitl_target: str) -> str:
    if hitl_target != "pi_plus_fc":
        pytest.skip(
            f"pi_plus_fc fixture requires AVATAR_HITL_TARGET=pi_plus_fc, got {hitl_target!r}"
        )
    if shutil.which("ssh") is None:
        pytest.skip("ssh not installed; cannot verify Pi reachability")
    host = _pi_host()
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", f"pi@{host}", "true"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        pytest.skip(f"Pi not reachable via SSH pi@{host}: {r.stderr.strip() or r.stdout.strip()}")
    udp = os.environ.get("AVATAR_PI_MAVSDK_UDP", "udp://:14540")
    return udp
```

- [ ] **Step 2: Commit**

```bash
git add tests/hitl/fixtures/pi_plus_fc.py
git commit -m "test(hitl): add pi_plus_fc SSH gate fixture"
```

---

### Task D15.4: `test_hitl_failsafes.py` (battery critical, RC loss, offboard freeze)

**Files:**

- Modify: `tests/hitl/conftest.py` (add `hitl_fc_drone` fixture — same commit as test file)
- Create: `tests/hitl/test_hitl_failsafes.py`

**Prerequisite (W2b):** `avatar/sim/runner.py` exposes a frozen `DriverContext` (fields at minimum: `drone: mavsdk.System`) plus `BatteryDrainDriver`, `RcLossDriver`, `OffboardFreezeDriver` with `async def inject(self, ctx: DriverContext) -> None` and `async def release(self, ctx: DriverContext) -> None` per spec §5.3. If the W2b implementation names the type differently, adjust the import in Step 1 to the canonical export from `avatar/sim/runner.py` (single source of truth).

- [ ] **Step 1a: Extend `tests/hitl/conftest.py` with connected drone fixture**

Append after `serial_device` fixture (same patterns as `tests/e2e/conftest.py` `mavsdk_drone`). At top of `conftest.py`, add `import asyncio` and `import logging` if not already present.

```python
logger = logging.getLogger(__name__)


@pytest.fixture
async def hitl_fc_drone(fc_bench_mavsdk_uri: str, hitl_target: str):
    """Live MAVSDK `System` on bench FC (USB). Skips if MAVSDK missing or serial connect fails."""
    if hitl_target != "fc_bench":
        pytest.skip("hitl_fc_drone requires AVATAR_HITL_TARGET=fc_bench")
    try:
        from mavsdk import System
    except ImportError:
        pytest.skip("MAVSDK not installed")
    drone = System()
    await drone.connect(system_address=fc_bench_mavsdk_uri)
    connected = False
    async for state in drone.core.connection_state():
        connected = state.is_connected
        logger.info("HITL FC connection_state: connected=%s uuid=%s", state.is_connected, state.uuid)
        break
    if not connected:
        pytest.skip("Could not connect to FC over serial (check cable, SYS_HITL=2, USB permissions)")
    try:
        yield drone
    finally:
        try:
            await drone.action.disarm()
        except Exception:
            pass
```

Register asyncio mode for this package: add `pytest_plugins = ("pytest_asyncio",)` at top of `tests/hitl/conftest.py` **only if** root config already depends on `pytest-asyncio` (check `pyproject.toml`); otherwise add `asyncio_mode = auto` in `[tool.pytest.ini_options]` in `pyproject.toml` in the same commit.

- [ ] **Step 1b: Create `tests/hitl/test_hitl_failsafes.py`**

```python
from __future__ import annotations

import asyncio

import pytest

pytestmark = [pytest.mark.hitl]


async def _wait_flight_mode(drone, timeout_s: float, *acceptable) -> None:
    """Poll telemetry until one of the given mavsdk.telemetry.FlightMode values is seen."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    want = set(acceptable)
    async for mode in drone.telemetry.flight_mode():
        if mode in want:
            return
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"flight mode not in {want!r} within {timeout_s}s")


@pytest.mark.asyncio
async def test_battery_critical_rtl(hitl_fc_drone, hitl_target):
    """Battery critical → RTL (PX4 failsafe)."""
    if hitl_target != "fc_bench":
        pytest.skip("battery_critical RTL scenario requires fc_bench SIH-on-FC for injection timing")
    from avatar.sim.drivers.battery_drain import BatteryDrainDriver
    from avatar.sim.runner import DriverContext

    drone = hitl_fc_drone
    ctx = DriverContext(drone=drone)
    drv = BatteryDrainDriver()
    await drv.inject(ctx)
    from mavsdk.telemetry import FlightMode

    await _wait_flight_mode(drone, 45.0, FlightMode.RETURN_TO_LAUNCH)
    await drv.release(ctx)


@pytest.mark.asyncio
async def test_rc_loss_nav_rcl_act(hitl_fc_drone, hitl_target):
    """RC loss → behavior per NAV_RCL_ACT (HOLD / RTL / Land per params)."""
    if hitl_target != "fc_bench":
        pytest.skip("RC loss injection validated on bench FC USB")
    from avatar.sim.drivers.rc_loss import RcLossDriver
    from avatar.sim.runner import DriverContext
    from mavsdk.telemetry import FlightMode

    drone = hitl_fc_drone
    ctx = DriverContext(drone=drone)
    drv = RcLossDriver(duration_s=3.0)
    await drv.inject(ctx)
    await _wait_flight_mode(
        drone,
        30.0,
        FlightMode.HOLD,
        FlightMode.RETURN_TO_LAUNCH,
        FlightMode.LAND,
        FlightMode.AUTO,
    )
    await drv.release(ctx)


@pytest.mark.asyncio
async def test_offboard_freeze_hold(hitl_fc_drone, hitl_target):
    """Offboard freeze ~3 s → HOLD (then release)."""
    if hitl_target != "fc_bench":
        pytest.skip("offboard freeze requires direct offboard session to bench FC")
    from mavsdk.offboard import VelocityBodyYawspeed

    from avatar.sim.drivers.offboard_freeze import OffboardFreezeDriver
    from avatar.sim.runner import DriverContext
    from mavsdk.telemetry import FlightMode

    drone = hitl_fc_drone
    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
    await drone.offboard.start()
    ctx = DriverContext(drone=drone)
    drv = OffboardFreezeDriver(duration_s=3.0)
    await drv.inject(ctx)
    await _wait_flight_mode(drone, 20.0, FlightMode.HOLD)
    await drv.release(ctx)
    try:
        await drone.offboard.stop()
    except Exception:
        pass
```

**Note:** `_wait_flight_mode` uses a deadline inside the `async for` loop so it cannot spin forever if telemetry stalls.

- [ ] **Step 2: Collect-only**

```bash
AVATAR_HITL_TARGET=fc_bench python3 -m pytest tests/hitl/test_hitl_failsafes.py --run-hitl --collect-only -q
```

Expected: three tests collected.

- [ ] **Step 3: Commit**

```bash
git add tests/hitl/conftest.py tests/hitl/test_hitl_failsafes.py pyproject.toml
git commit -m "test(hitl): add failsafe HITL scenarios"
```

---

### Task D15.5: `test_hitl_scenarios.py` (YAML runner subset + explicit skips)

**Files:**

- Modify: `tests/hitl/conftest.py` (add `hitl_mavsdk_uri` — avoids instantiating both bench and Pi fixtures in one test)
- Create: `tests/hitl/test_hitl_scenarios.py`

**Prerequisite (W2b/W3):** `ScenarioLoader.load(id)` resolves `avatar/sim/scenarios/<id>.yaml` (or the W3-agreed layout). `Orchestrator` accepts `mavsdk_uri: str` and `scenario: Scenario`, and `run()` completes when assertions pass (same contract used in Docker scenario runs).

- [ ] **Step 1a: Add `hitl_mavsdk_uri` to `tests/hitl/conftest.py`**

```python
@pytest.fixture
def hitl_mavsdk_uri(request: pytest.FixtureRequest, hitl_target: str) -> str:
    if hitl_target == "fc_bench":
        return request.getfixturevalue("fc_bench_mavsdk_uri")
    return request.getfixturevalue("pi_plus_fc_mavsdk_uri")
```

- [ ] **Step 1b: Implement HITL scenario matrix + Gazebo-only skip proofs**

```python
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.hitl]

HITL_SCENARIO_IDS = ("offboard_freeze", "rc_loss", "battery_drain", "network_partition")

SKIP_GAZEBO_ONLY = {
    "gps_loss": "HITL skip: gps_loss requires Gazebo GPS jam / physics (not available on bench FC)",
    "wind": "HITL skip: wind requires Gazebo wind field",
    "obstacle_proximity": "HITL skip: obstacle_proximity requires Gazebo depth/obstacle simulation",
}


@pytest.mark.parametrize("scenario_id", HITL_SCENARIO_IDS)
@pytest.mark.asyncio
async def test_hitl_yaml_scenario(scenario_id: str, hitl_target: str, hitl_mavsdk_uri: str):
    if scenario_id == "network_partition" and hitl_target != "pi_plus_fc":
        pytest.skip(
            "HITL skip: network_partition uses tc netem on the Pi (spec §9.3); use AVATAR_HITL_TARGET=pi_plus_fc"
        )
    from avatar.sim.runner import Orchestrator, ScenarioLoader

    loader = ScenarioLoader()
    scenario = loader.load(scenario_id)
    orch = Orchestrator(mavsdk_uri=hitl_mavsdk_uri, scenario=scenario)
    await orch.run()


@pytest.mark.parametrize(
    "scenario_id,reason",
    [
        ("gps_loss", SKIP_GAZEBO_ONLY["gps_loss"]),
        ("wind", SKIP_GAZEBO_ONLY["wind"]),
        ("obstacle_proximity", SKIP_GAZEBO_ONLY["obstacle_proximity"]),
    ],
)
def test_gazebo_only_scenarios_documented_skip(scenario_id: str, reason: str) -> None:
    pytest.skip(reason)
```

- [ ] **Step 2: Commit**

```bash
git add tests/hitl/conftest.py tests/hitl/test_hitl_scenarios.py
git commit -m "test(hitl): add YAML scenario subset for HITL"
```

---

### Task D15.6: `test_hitl_preflight.py` (wraps `hardware/px4/preflight.py`)

**Files:**

- Create: `tests/hitl/test_hitl_preflight.py`

- [ ] **Step 1: Implement subprocess test**

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.hitl, pytest.mark.preflight]


def test_preflight_cli_passes(fc_bench_mavsdk_uri, hitl_target):
    if hitl_target != "fc_bench":
        pytest.skip("preflight gate runs against bench FC (USB)")
    repo = Path(__file__).resolve().parents[2]
    script = repo / "hardware" / "px4" / "preflight.py"
    cmd = [
        sys.executable,
        str(script),
        "--airframe",
        "mark4_7in",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout.upper() or "pass" in proc.stdout.lower(), proc.stdout
```

Adjust path depth (`parents[2]`) if layout differs—must resolve to repo root containing `hardware/px4/preflight.py`.

- [ ] **Step 2: Commit**

```bash
git add tests/hitl/test_hitl_preflight.py
git commit -m "test(hitl): add preflight harness"
```

---

### Task D15.7: HITL dry-run validation matrix

**Files:**

- Modify: `tests/hitl/conftest.py` (only if markers need `preflight` registration tweak—already done in D15.1)

- [ ] **Step 1: Collect with `preflight` marker**

```bash
python3 -m pytest tests/hitl -m preflight --run-hitl --collect-only -v
```

Expected: `test_hitl_preflight.py::test_preflight_cli_passes` appears in list; fixtures resolve at collection where possible (session fixtures may defer to runtime—acceptable if runtime skip is explicit).

- [ ] **Step 2: Unset env with `--run-hitl` to confirm target skip**

```bash
unset AVATAR_HITL_TARGET
python3 -m pytest tests/hitl/test_hitl_preflight.py -m preflight --run-hitl -rs
```

Expected: skip reason `AVATAR_HITL_TARGET unset (expected fc_bench or pi_plus_fc)`.

- [ ] **Step 3: Without `--run-hitl`**

```bash
python3 -m pytest tests/hitl -m preflight -rs
```

Expected: every `hitl` test skipped with `HITL gate not enabled (pass --run-hitl)`.

- [ ] **Step 4: Commit**

If `conftest.py` needed tweaks from dry-run, include them; else empty commit is forbidden—amend prior commit or add `tests/hitl/README.md` one-paragraph operator note then commit:

```bash
git add tests/hitl/README.md  # if created
git commit -m "test(hitl): document preflight marker dry-run"
```

---

### Stream D16: Runbook + Polish + Archive

**Start only after D15.7 is green** (HITL harness merged on branch).

---

### Task D16.1: `docs/runbooks/preflight.md`

**Files:**

- Create: `docs/runbooks/preflight.md`

- [ ] **Step 1: Write file with verbatim procedure**

Create `docs/runbooks/preflight.md` with this body (adjust only if `preflight.py` CLI flags differ when the file lands):

```markdown
# Preflight checklist (bench FC)

Operator goal: confirm PX4 safety parameters, sensors, and MAVLink path before arming outdoors.

Out of scope: airspace, NOTAM, weather forecasts — see project spec §13.

## 0. Environment

```bash
cd /path/to/Project-Avatar
source .venv/bin/activate
export AVATAR_HITL_TARGET=fc_bench
```

## 1. Dry-run (no USB required)

Command:

```bash
python3 hardware/px4/preflight.py --dry-run --airframe mark4_7in
```

Expected stdout (representative):

```
dry_run: true
airframe: mark4_7in
overlay: hardware/px4/airframes/mark4_7in.params
result: PASS
notes: no serial open in dry-run mode
```

## 2. Live USB check (Pixhawk on bench)

Connect USB. Confirm symlink:

```bash
ls -l /dev/pixhawk
```

Expected:

```
lrwxrwxrwx 1 root dialout … /dev/pixhawk -> ttyACM0
```

## 3. Full preflight

Command:

```bash
python3 hardware/px4/preflight.py --airframe mark4_7in
```

Expected (representative tail):

```
serial: /dev/pixhawk @ 921600
param_verify: PASS
estimator: PASS
rc: WARN or PASS per configuration
battery: PASS (bench PSU)
overall: PASS
```

Abort if `overall: FAIL` or any `FAIL` line appears—do not arm.

## 4. MCP cross-check (optional)

```bash
python3 -m avatar.mcp_server
```

In agent session, call read-only `preflight_checklist` tool if exposed; expect JSON echoing same PASS/FAIL summary.

## 5. HITL pytest gate

```bash
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
```

Expected: `test_preflight_cli_passes` **passed** on hardware; skipped tests show explicit hardware reasons only for non-preflight markers.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/preflight.md
git commit -m "docs(runbook): add preflight.md"
```

---

### Task D16.2: `docs/runbooks/first-flight.md`

**Files:**

- Create: `docs/runbooks/first-flight.md`

- [ ] **Step 1: Write full runbook**

```markdown
# First flight (tethered → short translation)

This procedure assumes: Mark4 7″ + Pixhawk 6C Mini + Pi stack, outdoor calm wind, spotter present, RC transmitter programmed with RTL on switch. **No** NOTAM/weather automation (spec §13).

## A. Tether + ground idle

1. **Environment check:** props off for bench checks; on field, props on, tether attached to airframe frame (not ESC leads).
2. **Command:**

```bash
python3 hardware/px4/preflight.py --airframe mark4_7in
```

Expected: `overall: PASS`.

3. **MCP:** `get_drone_status` — `armed: false`, GPS `fix_type` ≥ 3, battery healthy.
4. **Abort if:** GPS no fix after 120 s, compass variance warnings, preflight FAIL, tether tangled.

## B. Hover 1 m × 10 s

1. **Environment:** clear 5 m radius, people outside cordon.
2. **MCP:** `arm` then `set_flight_mode` / `arm_and_takeoff` per tool policy — `altitude_m: 1.0`.
3. **Observe:** altitude hold within ±0.3 m; no yaw windup; tether slack not pulling craft sideways.
4. **Abort:** oscillation >±0.5 m sustained 3 s, unusual vibration, RC override invoked.

## C. Hover 3 m × 30 s

1. **MCP:** climb to `3.0` m AGL (tool-specific: `goto_local_ned` with `z_m` or `arm_and_takeoff` if still on ground—choose the primitive your W2a tools expose; document the exact JSON you used in the flight log).
2. **Observe:** stable hover, Guardian no alerts.
3. **Abort:** battery sag below configured RTL threshold unexpectedly, tether tension near structural limit.

## D. First 5 m translation

1. **MCP:** `set_velocity_body` `{forward: 0.5, right: 0, down: 0, yawspeed: 0, duration_s: 10}` then stop with zero velocity (repeat until ~5 m horizontal displacement confirmed via telemetry).
2. **Observe:** no heading drift beyond acceptable; obstacle clearance manually verified.
3. **Abort:** tether angle >45°, proximity to people, GPS dropout.

## E. RTL

1. **MCP:** `rtl()` or RC RTL switch.
2. **Observe:** climb-turn-home pattern per PX4 params; soft landing within 2 m of home.
3. **Abort:** if RTL path intersects obstacles—switch RC to manual Loiter and land visually (training mode).

Post-flight: export `flight_recorder` JSONL if enabled.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/first-flight.md
git commit -m "docs(runbook): first-flight.md"
```

---

### Task D16.3: `docs/runbooks/troubleshooting.md` (ErrorCode table)

**Files:**

- Create: `docs/runbooks/troubleshooting.md`

- [ ] **Step 1: Generate the markdown file from `ErrorCode` (deterministic, no TBD column)**

Run from repo root (requires W1 `avatar/mcp_server/errors.py` with `class ErrorCode(str, Enum)` or `Enum`):

```bash
python3 << 'PY'
from pathlib import Path

try:
    from avatar.mcp_server.errors import ERROR_METADATA, ErrorCode
except ImportError:
    from avatar.mcp_server.errors import ErrorCode

    ERROR_METADATA = {}

def _meta_for(member):
    if not ERROR_METADATA:
        return None
    return ERROR_METADATA.get(member) or ERROR_METADATA.get(member.name) or ERROR_METADATA.get(getattr(member, "value", None))

lines = [
    "# MCP troubleshooting",
    "",
    "Map structured MCP errors (`isError: true` envelope) to operator actions.",
    "",
    "| Code | Typical cause | Remediation | Escalation |",
    "|------|---------------|-------------|------------|",
]
for member in ErrorCode:
    meta = _meta_for(member)
    if not meta:
        cause = f"MCP returned `{member.name}`"
        fix = "Read `message` and `suggested_action` in the JSON error body; retry with corrected inputs."
        esc = "If repeats after parameter/mission fix: capture server log + `flight_recorder` JSONL; compare PX4 `ulog`."
    else:
        if isinstance(meta, dict):
            cause = meta.get("summary", member.name)
            fix = meta.get("suggested_action", "See MCP JSON suggested_action")
        else:
            cause = getattr(meta, "summary", member.name)
            fix = getattr(meta, "suggested_action", "See MCP JSON suggested_action")
        esc = "If repeats: maintenance log + firmware/param diff vs `hardware/px4/airframes/` overlay."
    lines.append(f"| `{member.name}` | {cause} | {fix} | {esc} |")

lines += [
    "",
    "## Notes",
    "",
    "- Agents branch on `code`, not `message`.",
    "- Escalation means: stop autonomous flight, capture logs, do not retry until root cause class is understood.",
    "- Airspace and weather tooling are out of scope (spec §13); MCP errors never imply legal clearance to fly.",
]
Path("docs/runbooks/troubleshooting.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Wrote docs/runbooks/troubleshooting.md")
PY
```

If `ERROR_METADATA` does not exist yet, replace the script body with a single loop over `ErrorCode` only and set `cause = member.name`, `fix = "Inspect MCP JSON suggested_action and guardian limits."`, `esc` as above (still one row per member, zero TBD tokens).

- [ ] **Step 2: Review + commit**

Visually verify one row per `ErrorCode` member, then:

```bash
git add docs/runbooks/troubleshooting.md
git commit -m "docs(runbook): troubleshooting ErrorCode map"
```

---

### Task D16.4: `docs/runbooks/calibration.md`

**Files:**

- Create: `docs/runbooks/calibration.md`

- [ ] **Step 1: Write body**

```markdown
# Calibration cadence

Out of scope: factory QC for new aircraft classes beyond quad — spec §13.

## When to calibrate

| Event | Sensors |
|-------|---------|
| New FC flash | Accel, gyro, mag, level |
| First hardware boot | Accel, gyro, mag, RC, motor dirs |
| After hard landing / crash inspection | Accel, mag, level |
| Monthly idle storage | Gyro quick check (optional accel level) |
| Major firmware bump | Re-run `verify.py` then full accel/mag |

## Commands (headless)

Accel + gyro + mag + level (interactive prompts suppressed if script supports `--batch`):

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors accel,gyro,mag,level
```

Expected tail:

```
calibration: accel DONE
calibration: gyro DONE
calibration: mag DONE
calibration: level DONE
result: PASS
```

RC calibration:

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors rc
```

Motor direction test (props off):

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors motor_dirs
```

## Post-calibration verify

```bash
python3 hardware/px4/verify.py --airframe mark4_7in
```

Expected: `verify: PASS`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/calibration.md
git commit -m "docs(runbook): calibration cadence"
```

---

### Task D16.5: `docs/runbooks/field-kit.md`

**Files:**

- Create: `docs/runbooks/field-kit.md`

- [ ] **Step 1: Write packing list**

```markdown
# Field kit checklist (quantities)

| Item | Qty | Notes |
|------|-----|-------|
| Laptop (MCP host) | 1 | Charged + charging brick |
| USB-C hub + PD | 1 | For FC + peripherals |
| Pixhawk 6C Mini + wiring harness | 1 | Pre-inspect solder joints |
| Raspberry Pi 4 + case + SD | 1 | Image stamped ≥ Wave 3 |
| Pi Cam 3 Wide + ribbon | 1 | Spare ribbon recommended |
| 4S / 6S LiPo (aircraft packs) | 2 | One flight + one spare, storage bag |
| XT60 smoke stopper | 1 | First energize each session |
| RC transmitter + receiver bound | 1 | RTL switch tested |
| FPV goggles | 1 | Optional first flight; spotter mandatory either way |
| Digital multimeter | 1 | Cell balance sanity |
| Prop set (CW/CCW matched) | 2 sets | Nylon standoff + torch not in kit |
| Cable kit (USB-A/C, micro, UART) | 1 roll | Label FC vs Pi cables |
| Painter’s tape + sharpie | 1 | Mark home direction |
| Fire extinguisher (LiPo rated) | 1 | Within 3 m of bench |
| Printed runbooks (`preflight`, `first-flight`) | 1 set each | Paper survives glare |

Out of scope: cellular NOTAM apps — bring your own regulatory workflow outside this repo.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/field-kit.md
git commit -m "docs(runbook): field kit list"
```

---

### Task D16.6: `README.md` rewrite (status + Docker SIH + hardware + CI badges)

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Replace top sections with concise status**

Top-of-file template after edit:

```markdown
# Project Avatar

[![PR Fast CI](https://github.com/OWNER/REPO/actions/workflows/pr-fast.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/pr-fast.yml)
[![Nightly Rich](https://github.com/OWNER/REPO/actions/workflows/nightly-rich.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/nightly-rich.yml)

**Status:** First-flight-ready when Wave 4 gate passes (`pytest tests/hitl -m preflight --run-hitl`).

## Quickstart — Docker SIH

```bash
./scripts/sim.sh sih
./scripts/sim.sh scenario smoke_failsafe_rtl
./scripts/sim.sh down
```

## Hardware bring-up

- PX4: `hardware/px4/README.md` + `./hardware/px4/flash-px4.sh --airframe mark4_7in`
- Pi: `hardware/pi/README.md` + `./hardware/pi/flash.sh`
- One-shot smoke: `./scripts/trivial-flash.sh`

## Operator docs

- `docs/runbooks/preflight.md`
- `docs/runbooks/first-flight.md`
```

Replace `OWNER/REPO` with real GitHub coordinates.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): first-flight-ready status and SIH quickstart"
```

---

### Task D16.7: `CHANGELOG.md` — `[Unreleased]` + `0.5.0` first-flight-ready rollup

**Files:**

- Modify: `CHANGELOG.md`

- [ ] **Step 1: Prepend section**

Insert below the header boilerplate:

```markdown
## [Unreleased]

### Changed

- Preparing 0.5.0 first-flight-ready stamp after Wave 4 gate.

## [0.5.0] - first-flight-ready - 2026-04-16

### Summary

Roll-up of Waves 0–4: unified tests/tooling, safety+MCP spines, Docker SIH/Gazebo sim, mission intel + scenario runner, hardware provisioning scripts, HITL pytest harness, operator runbooks, trivial-flash reference path.

### Added

- `tests/hitl/` HITL gate (`--run-hitl`, `AVATAR_HITL_TARGET`, device discovery).
- `docs/runbooks/` preflight, first flight, troubleshooting, calibration, field kit.
- `scripts/trivial-flash.sh` five-step bring-up helper.

### Changed

- README oriented to Docker SIH quickstart + hardware pointers + CI badges.

### Notes

- Physical HITL execution remains environment-scheduled; code + docs satisfy “first-flight-ready” when W4 pytest gate passes on bench FC.
```

Merge with any existing `[0.5.0] - 2026-04-11` section: produce **one** canonical `## [0.5.0]` heading (Keep a Changelog style — no leading `v`) whose body combines prior Phase 0.5 notes with the Wave 0–4 rollup bullets above; delete duplicate `0.5.0` headers so the file has a single release block for that version. Retain older versions (e.g. pre-0.5) below unchanged.

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): 0.5.0 first-flight-ready rollup"
```

---

### Task D16.8: `scripts/trivial-flash.sh` (§9.5)

**Files:**

- Create: `scripts/trivial-flash.sh`

- [ ] **Step 1: Add executable script**

```bash
cat > scripts/trivial-flash.sh << 'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/5] Flash PX4 (mark4_7in)"
./hardware/px4/flash-px4.sh --airframe mark4_7in

echo "[2/5] Flash Pi image (pass-through args to flash.sh)"
./hardware/pi/flash.sh "$@"

echo "[3/5] Poll Pi status file (/boot/avatar-status.txt)"
HOST="${AVATAR_PI_HOST:-avatar.local}"
ok=0
for i in $(seq 1 60); do
  state="$(ssh -o ConnectTimeout=5 "pi@${HOST}" 'cat /boot/avatar-status.txt 2>/dev/null || echo missing')" || true
  echo "  try ${i}: ${state}"
  case "$state" in
    *green*) ok=1; echo "STATUS: GREEN"; break ;;
    *red*) echo "STATUS: RED — abort"; exit 2 ;;
  esac
  sleep 5
done
if [[ "$ok" -ne 1 ]]; then
  echo "TIMEOUT: never saw green in /boot/avatar-status.txt"
  exit 1
fi

echo "[4/5] HITL preflight pytest"
export AVATAR_HITL_TARGET="${AVATAR_HITL_TARGET:-fc_bench}"
python3 -m pytest tests/hitl -m preflight --run-hitl -rs

echo "[5/5] Tethered flight (manual — see docs/runbooks/first-flight.md)"
echo "ALL STEPS COMPLETE"
SH
chmod +x scripts/trivial-flash.sh
```

Pass-through: all CLI args after script name go to `./hardware/pi/flash.sh` (`"$@"`). `AVATAR_HITL_TARGET` defaults to `fc_bench` for step 4 if unset.

- [ ] **Step 2: Commit**

```bash
git add scripts/trivial-flash.sh
git commit -m "chore(scripts): add trivial-flash bring-up helper"
```

---

### Task D16.9: Archive Wave 0–3 plans + plans README index

**Files:**

- Create: `docs/superpowers/plans/archive/` (if absent)
- Move: matching `2026-04-16-wave-0*.md` … `wave-3*.md` when those files exist on disk
- Create/modify: `docs/superpowers/plans/README.md`

- [ ] **Step 1: Move archives**

```bash
mkdir -p docs/superpowers/plans/archive
shopt -s nullglob
for f in docs/superpowers/plans/2026-04-16-wave-{0,1,2a,2b,3}-*.md; do
  git mv "$f" docs/superpowers/plans/archive/
done
```

If globs match nothing, **do not error**—note in README under Archive: “Wave 0–3 plan files not present at archive time (glob had no matches).”

**Do not** move or rename `2026-04-16-wave-4-hitl-runbook.md` until the W4 gate passes; it stays in `docs/superpowers/plans/` as the active plan.

- [ ] **Step 2: Write `docs/superpowers/plans/README.md`**

```markdown
# Superpowers implementation plans

## Active

- `2026-04-16-wave-4-hitl-runbook.md` — Wave 4 HITL + runbooks (in progress until W4 gate)

## Archive

See `archive/` for completed wave plans.

## Spec

- `docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md`
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/README.md docs/superpowers/plans/archive
git commit -m "chore(plans): archive wave-0..3 and add plans index"
```

---

### Task D16.10: W4 gate validation + `changes-made.md` stamp

**Files:**

- Modify: `changes-made.md`

- [ ] **Step 1: Run gate on hardware**

```bash
export AVATAR_HITL_TARGET=fc_bench
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
```

Expected: **PASS** (no fails); skips only for non-selected tests outside `-m preflight`.

- [ ] **Step 2: Human review**

Spot-check `docs/runbooks/*.md` links and command literals against repo scripts.

- [ ] **Step 3: Append to `changes-made.md`**

```markdown
## 2026-04-16 — Wave 4 complete — first-flight-ready

- HITL preflight pytest gate: PASS on bench FC (SIH-on-FC).
- Runbooks reviewed (preflight, first-flight, troubleshooting, calibration, field-kit).
- CHANGELOG 0.5.0 first-flight-ready entry added; plans index updated; waves 0–3 archived.

Verification:

```bash
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
./scripts/trivial-flash.sh --help 2>/dev/null || true
```
```

- [ ] **Step 4: Commit**

```bash
git add changes-made.md
git commit -m "chore: wave 4 complete first-flight-ready stamp"
```

---

## Self-Review

**1. Spec coverage**

| Spec slice | Task |
|------------|------|
| §4 Wave 4 sequential D15→D16 | Stream order + branch note |
| §9.3 HITL layout | D15.1–D15.6 files |
| §9.4 runbooks | D16.1–D16.5 |
| §9.5 trivial flash | D16.8 |
| §11 W4 gate | Wave Gate table + D16.10 |
| §13 out-of-scope | Wave Scope + runbook footers |

**2. Placeholder scan**

- D15.4/D15.5 contain **complete** intended test bodies (no `NotImplementedError`, no “fill later” test steps). Troubleshooting table is generated from `ErrorCode` (+ optional `ERROR_METADATA`) without a `TBD` column.
- D16.8 uses distinct step labels `[1/5]`…`[5/5]`, `"$@"` passthrough, timeout if Pi never goes green, and sets `AVATAR_HITL_TARGET` before pytest.

**3. Type consistency**

- `hitl_target` strings restricted to `fc_bench` / `pi_plus_fc` across conftest and tests.
- `pytest` marker names `hitl` and `preflight` aligned with gate command `-m preflight`.

**Gap addressed:** `preflight.py` / `runner.py` / `hardware/` not present in workspace snapshot—plan states W3/W2b dependencies explicitly so implementer does not invent paths.
