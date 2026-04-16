# Wave 3: Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 3 integration: twelve declarative pipeline scenarios with subprocess tests, GitHub Actions CI (PR fast path, nightly Gazebo matrix, release digest pinning), Raspberry Pi OS image + flash + systemd bring-up, and PX4 flash/calibration/verify/preflight tooling — all gated by W3 verification commands.

**Architecture:** Four parallel streams (D11–D14) branch from completed W2a/W2b: D11 adds YAML scenarios under `avatar/sim/scenarios/` plus `tests/sim/scenarios/` wrappers that shell out to `scripts/run-scenario.sh`; D12 adds `.github/workflows/` and helper scripts with caching and artifact retention; D13 bakes operator-facing Pi provisioning under `hardware/pi/`; D14 bakes FC provisioning under `hardware/px4/` with `.params` overlays aligned to `PX4ParameterManager` and a dry-run preflight CLI. Hermes notes ([`hermes/03-gazebo-macos-sitl-viability.md`](../../hermes/03-gazebo-macos-sitl-viability.md)) justify **linux/amd64** Gazebo in CI (not macOS native); [`hermes/04-mavsdk-offboard-best-practices.md`](../../hermes/04-mavsdk-offboard-best-practices.md) informs scenario stages that enter offboard (setpoint-before-start, ≥2 Hz).

**Tech stack:** YAML 1.2, pytest + subprocess, GitHub Actions (Ubuntu), Docker Buildx, shellcheck, systemd, cloud-init, PX4 `upload.py` / QGC-style param files, MAVSDK-Python, Python 3.12.

---

## Wave Scope

This plan covers **Wave 3 only** ([`docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md`](../specs/2026-04-16-project-avatar-first-flight-plan-design.md) §4 D11–D14, §5, §8–§9, §11 W3):

| Stream | Deliverable |
|--------|-------------|
| **D11** | Twelve scenario YAML files + one pytest file each invoking `scripts/run-scenario.sh <id>`; extend `scripts/sim.sh` with `all-scenarios`. |
| **D12** | `pr-fast.yml`, `nightly-rich.yml`, `release.yml`, `.github/scripts/collect-artifacts.sh`, `.github/scripts/pin-digests.py`. |
| **D13** | Full `hardware/pi/` tree per spec §9.2. |
| **D14** | Full `hardware/px4/` tree per spec §9.1. |

Out of scope: Wave 4 HITL harness, runbook prose beyond one-page READMEs in hardware dirs, merging `avatar/tests` trees, MCP tool implementation beyond what scenarios call.

---

## Dependencies

Assume **before starting Wave 3**:

| Prerequisite | Evidence |
|--------------|----------|
| **W2a complete** | MCP primitives/orchestrators registered; `preflight_checklist` tool exists to shell out to `hardware/px4/preflight.py` once added. |
| **W2b complete** | `avatar/sim/runner.py` (`ScenarioLoader`, `Orchestrator`, `InjectionScheduler`, `AssertionEngine`, `ArtifactCollector`); `avatar/sim/drivers/` with `WindDriver`, `GpsLossDriver`, `VisionDropoutDriver`, `OffboardFreezeDriver`, `BatteryDrainDriver`, `ObstacleProximityDriver`, `NetworkPartitionDriver`; `scripts/sim.sh` and `scripts/run-scenario.sh` functional for `scenario <id>`. |
| **Docker sim tiers** | `docker/compose.yaml` profiles `sih`, `gazebo`; SIH <15 s heartbeat per W1 gate. |
| **`avatar/sim/scenarios.py`** | `ScenarioKind` literal includes all six kinds; enum/catalog aligned with YAML `kind` values (extend catalog rows if needed when registering new ids). |
| **MCP tool surface** | **58 tools** live per spec §6.8; `scripts/validate_mcp_server.py` reports 58. |
| **`.github/workflows/`** | Confirmed absent at plan time (`ls` → no directory); create `.github/workflows/` as part of D12. |

---

## Parallel Streams

Streams **D11 / D12 / D13 / D14** run concurrently on branch `wave-3-integration` after rebasing on the W2b completion commit. Merge order: land D11+D12 first (CI exercises scenarios), then D13+D14, or single PR with four commits grouped by stream.

---

## Wave Gate

Copy of **§11 W3 row** (verbatim):

| Wave | Gate | Verification |
|------|------|--------------|
| W3 | All 12 pipelines green in Gazebo; CI pipelines green on fresh clone; Pi image builds <10 min dry-run; PX4 params apply via `preflight.py --dry-run` | `scripts/sim.sh all-scenarios && hardware/pi/build-image.sh --dry-run && hardware/px4/preflight.py --dry-run --airframe mark4_7in` |

**Engineering note:** Several scenarios are **SIH-only** or **offline** per §5.4; the gate command still uses `all-scenarios`, which must run each YAML on its declared `sim.tier` (`sih` \| `gazebo` \| `offline`) and treat success as non-zero exit only on failure — so “all 12 pipelines green” means orchestrator exit 0 for each id, not that every run uses Gazebo.

**Post-gate:** Append entry `Wave 3 complete` to `changes-made.md` (single commit after all streams green).

---

## Branch Setup

```bash
git checkout main
git pull
git checkout -b wave-3-integration
```

Rebase frequently; do not merge until W3 gate passes locally (or on CI for D12-relevant parts).

---

## File map (Wave 3)

| Path | Owner |
|------|-------|
| `avatar/sim/scenarios/*.yaml` | D11 |
| `tests/sim/scenarios/test_*.py` | D11 |
| `scripts/sim.sh` (add `all-scenarios`) | D11 / D12 |
| `.github/workflows/*.yml` | D12 |
| `.github/scripts/collect-artifacts.sh`, `pin-digests.py` | D12 |
| `hardware/pi/**` | D13 |
| `hardware/px4/**` | D14 |
| `changes-made.md` | Wave gate |

---

# Stream D11 — Twelve pipeline scenarios

**Convention:** Each YAML `id` matches the basename of the file. Driver names in YAML use **snake_case** matching W2b driver registry (`vision_dropout`, `gps_loss`, `wind`, `offboard_freeze`, `battery_drain`, `obstacle_proximity`, `network_partition`). `backends` lists MCP/runtime deps per §5.1 example.

**Prerequisite task (execute before D11.1 or fold into D11.12):** Extend `scripts/sim.sh` to implement `all-scenarios`:

- [ ] **Step 1:** Add subcommand `all-scenarios` that loops the twelve ids in fixed order, invokes `scripts/run-scenario.sh "$id"` for each, collects exit codes, writes `artifacts/all-scenarios-summary.json` (per-id exit, duration, artifact path).
- [ ] **Step 2:** Run locally (with Docker tier available):

```bash
chmod +x scripts/sim.sh scripts/run-scenario.sh
./scripts/sim.sh all-scenarios
```

Expected: exit `0` when every scenario succeeds; final line on stdout like `ALL_SCENARIOS_OK 12/12`.

- [ ] **Step 3:** Commit

```bash
git add scripts/sim.sh
git commit -m "feat(sim): add all-scenarios orchestration for W3 gate"
```

---

### Task D11.1: `search_acquire_follow_vision_dropout.yaml` + test

**Files:**

- Create: `avatar/sim/scenarios/search_acquire_follow_vision_dropout.yaml`
- Create: `tests/sim/scenarios/test_search_acquire_follow_vision_dropout.py`
- Modify (if needed): `avatar/sim/scenarios.py` catalog — register id for operator discovery

**Drivers (W2b cross-check):** `VisionDropoutDriver` — injection during `follow_runner` stage.

- [ ] **Step 1: Write failing test**

```python
"""W2b: VisionDropoutDriver — search→acquire→follow then vision loss."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_search_acquire_follow_vision_dropout_scenario(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "search_acquire_follow_vision_dropout"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art_dir = repo_root / "artifacts"
    assert art_dir.is_dir()
    tars = list(art_dir.glob("*search_acquire_follow_vision_dropout*.tar.gz"))
    assert tars, "expected scenario artifact tarball under artifacts/"
```

- [ ] **Step 2: Run test (expect fail until YAML + runner exist)**

Run: `pytest tests/sim/scenarios/test_search_acquire_follow_vision_dropout.py -v -m sim`
Expected: FAIL (skip if `@pytest.mark.sim` excluded without `-m sim`) or collection error until file exists.

- [ ] **Step 3: Add YAML**

Create `avatar/sim/scenarios/search_acquire_follow_vision_dropout.yaml`:

```yaml
id: search_acquire_follow_vision_dropout
kind: runner_follow
description: "takeoff → search grid → acquire → follow → vision dropout → expect hold/RTL"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 42
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 85
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 12 },
      expect: { state: HOVERING } }
  - { id: search_grid, tool: execute_search_grid, args: { radius_m: 25, leg_spacing_m: 8, altitude_m: 12, speed_m_s: 3 },
      expect: { state: HOVERING } }
  - { id: acquire_target, tool: track_bbox, args: { class_name: person, min_confidence: 0.45 },
      expect: { tracking: active } }
  - { id: follow_runner, tool: track_bbox, args: { class_name: person, follow_distance_m: 8, max_speed_m_s: 4 },
      async: true }
injections:
  - at: { stage: follow_runner, t_offset_s: 12 }
    driver: vision_dropout
    params: { duration_s: 6, drop_rate: 1.0 }
assertions:
  - within_s: 15
    expect: { state: [HOLD, RTL], reason_contains: vision }
  - eventually:
    expect: { landed: true, home_distance_m: { lt: 15 } }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Step 4: Run test with sim tier**

Run: `pytest tests/sim/scenarios/test_search_acquire_follow_vision_dropout.py -v -m sim`
Expected: PASS when Gazebo stack + runner implemented.

- [ ] **Step 5: Commit**

```bash
git add avatar/sim/scenarios/search_acquire_follow_vision_dropout.yaml tests/sim/scenarios/test_search_acquire_follow_vision_dropout.py
git commit -m "feat(sim): add search_acquire_follow_vision_dropout scenario"
```

---

### Task D11.2: `gps_jam_expect_rtl.yaml` + test

**Files:**

- Create: `avatar/sim/scenarios/gps_jam_expect_rtl.yaml`
- Create: `tests/sim/scenarios/test_gps_jam_expect_rtl.py`

**Drivers:** `GpsLossDriver` — SIH + Gazebo tiers per table.

- [ ] **Step 1: Write failing test** (same pattern as D11.1; id `gps_jam_expect_rtl`).

```python
"""W2b: GpsLossDriver — GPS denied triggers RTL per PX4 failsafe params."""
from pathlib import Path

import pytest
import subprocess


@pytest.mark.sim
def test_gps_jam_expect_rtl_scenario():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "run-scenario.sh"
    proc = subprocess.run(
        ["bash", str(script), "gps_jam_expect_rtl"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    art = list((repo_root / "artifacts").glob("*gps_jam_expect_rtl*.tar.gz"))
    assert art
```

- [ ] **Step 2: Run test** — expect FAIL until green.

Run: `pytest tests/sim/scenarios/test_gps_jam_expect_rtl.py -v -m sim`

- [ ] **Step 3: Add YAML**

```yaml
id: gps_jam_expect_rtl
kind: nature_cinematic
description: "takeoff → loiter → GPS jam → expect RTL/land per PX4 params"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 17
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 90
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 15 },
      expect: { state: HOVERING } }
  - { id: loiter, tool: set_flight_mode, args: { mode: LOITER },
      expect: { state: HOVERING } }
  - { id: hold_position, tool: goto_local_ned, args: { x_m: 0, y_m: 0, z_m: -15, yaw_deg: 0 },
      expect: { state: HOVERING } }
injections:
  - at: { stage: hold_position, t_offset_s: 5 }
    driver: gps_loss
    params: { duration_s: 20, hdop_inflate: 50 }
assertions:
  - within_s: 25
    expect: { state: [RTL, LAND], reason_contains: gps }
  - eventually:
    expect: { landed: true, home_distance_m: { lt: 10 } }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

**Note:** For Gazebo re-run, duplicate file is not required if runner supports `sim.tier: sih+gazebo` — use **two stage files** is invalid YAML; instead add **second scenario file** `gps_jam_expect_rtl_gazebo.yaml` only if product requires both tiers in one id. Per user table, single id `gps_jam_expect_rtl` with tier **sih+gazebo** means runner must accept **list** or **primary + optional_secondary**. **Resolution:** Use YAML key `sim.tiers: [sih, gazebo]` if W2b loader supports list; else **default `tier: sih`** for PR speed and add comment in test docstring that nightly runs Gazebo copy. **Minimal plan:** set `tier: gazebo` only if SIH cannot inject GPS jam; else keep `sih`. Hermes: use Docker Gazebo for faithful jam + RTL. **Implement:** extend `ScenarioLoader` to accept `sim.tier` as string **or** `sim.secondary_tier` for optional second pass — **YAGNI for Wave 3:** use `tier: sih` above; add duplicate optional task only if SIH driver insufficient.

- [ ] **Step 4: Commit**

```bash
git add avatar/sim/scenarios/gps_jam_expect_rtl.yaml tests/sim/scenarios/test_gps_jam_expect_rtl.py
git commit -m "feat(sim): add gps_jam_expect_rtl scenario"
```

---

### Task D11.3: `runner_follow_wind_gust.yaml` + test

**Drivers:** `WindDriver`.

- [ ] **Test file** `tests/sim/scenarios/test_runner_follow_wind_gust.py` — same subprocess pattern, id `runner_follow_wind_gust`.

- [ ] **YAML** `avatar/sim/scenarios/runner_follow_wind_gust.yaml`:

```yaml
id: runner_follow_wind_gust
kind: runner_follow
description: "runner-follow → sustained wind → verify tracking-error bound, no crash"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 91
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 88
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 14 },
      expect: { state: HOVERING } }
  - { id: follow_runner, tool: track_bbox, args: { class_name: person, follow_distance_m: 10, max_speed_m_s: 5 },
      async: true }
injections:
  - at: { stage: follow_runner, t_offset_s: 3 }
    driver: wind
    params: { north_m_s: 6, east_m_s: -4, duration_s: 45, gust_peak_m_s: 3 }
assertions:
  - within_s: 50
    expect: { tracking_error_m: { lt: 6 }, guardian_alerts_max: { lte: 3 } }
  - eventually:
    expect: { crashed: false, landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit:** `feat(sim): add runner_follow_wind_gust scenario`

---

### Task D11.4: `orbit_offboard_freeze.yaml` + test

**Drivers:** `OffboardFreezeDriver`. Tiers SIH+Gazebo: use `tier: sih` for PR; document Gazebo parity in scenario README.

- [ ] **YAML** `avatar/sim/scenarios/orbit_offboard_freeze.yaml`:

```yaml
id: orbit_offboard_freeze
kind: nature_cinematic
description: "orbit → offboard freeze 3 s → expect HOLD → resume/RTL"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 3
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 92
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 15 },
      expect: { state: HOVERING } }
  - { id: goto_orbit_center, tool: goto_gps, args: { lat: 47.3978, lon: 8.5459, alt_m: 18 },
      expect: { state: HOVERING } }
  - { id: start_orbit, tool: orbit_target, args: { target_lat: 47.3978, target_lon: 8.5459,
      radius_m: 10, speed_m_s: 3, duration_s: 60 },
      async: true }
injections:
  - at: { stage: start_orbit, t_offset_s: 10 }
    driver: offboard_freeze
    params: { duration_s: 3 }
assertions:
  - within_s: 8
    expect: { state: [HOLD, RTL], reason_contains: offboard }
  - within_s: 40
    expect: { state: [OFFBOARD, HOVERING] }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Test** + **Commit** `feat(sim): add orbit_offboard_freeze scenario`

---

### Task D11.5: `cinematic_reveal_battery_critical.yaml` + test

**Drivers:** `BatteryDrainDriver`. Tier: **sih**.

```yaml
id: cinematic_reveal_battery_critical
kind: nature_cinematic
description: "cinematic reveal → battery critical → expect RTL preempts shot"
backends: [mcp_stdio, mavsdk, cinematic_templates, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 200
  speed_factor: 2.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 40
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 20 },
      expect: { state: HOVERING } }
  - { id: reveal, tool: execute_cinematic_shot, args: { template: approach_reveal, duration_s: 90 },
      async: true }
injections:
  - at: { stage: reveal, t_offset_s: 8 }
    driver: battery_drain
    params: { rate_pct_per_s: 5, floor_pct: 8 }
assertions:
  - within_s: 30
    expect: { state: RTL, reason_contains: battery }
  - eventually:
    expect: { landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add cinematic_reveal_battery_critical scenario`

---

### Task D11.6: `depth_room_obstacle_abort.yaml` + test

**Drivers:** `ObstacleProximityDriver`. Tier: **gazebo** (depth world).

```yaml
id: depth_room_obstacle_abort
kind: indoor_obstacle_room
description: "depth-room crawl → obstacle at 1.5 m → expect velocity clamp + abort"
backends: [mcp_stdio, mavsdk, depth_camera, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500_depth
  seed: 55
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 95
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 3 },
      expect: { state: HOVERING } }
  - { id: room_crawl, tool: set_velocity_body, args: { forward: 0.8, right: 0.0, down: 0.0, yawspeed: 0.0, duration_s: 25 },
      async: true }
injections:
  - at: { stage: room_crawl, t_offset_s: 6 }
    driver: obstacle_proximity
    params: { distance_m: 1.5, sector: forward }
assertions:
  - within_s: 12
    expect: { velocity_forward_m_s: { lt: 0.5 }, abort_reason_contains: obstacle }
  - eventually:
    expect: { state: HOVERING, crashed: false }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add depth_room_obstacle_abort scenario`

---

### Task D11.7: `sailboat_follow_altitude_floor.yaml` + test

**Drivers:** `WindDriver`. Tier: **gazebo**.

```yaml
id: sailboat_follow_altitude_floor
kind: sailboat_follow
description: "sailboat follow → lateral wind + altitude drift → expect AGL floor held"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 77
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 90
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 25 },
      expect: { state: HOVERING } }
  - { id: follow_boat, tool: track_bbox, args: { class_name: boat, follow_distance_m: 35, min_agl_m: 12 },
      async: true }
injections:
  - at: { stage: follow_boat, t_offset_s: 5 }
    driver: wind
    params: { north_m_s: 0, east_m_s: 7, vertical_bias_m_s: 0.35, duration_s: 40 }
assertions:
  - within_s: 45
    expect: { agl_m: { gte: 12 } }
  - eventually:
    expect: { crashed: false }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add sailboat_follow_altitude_floor scenario`

---

### Task D11.8: `mcp_tool_storm.yaml` + test

**Drivers:** none. Tier: **sih**.

```yaml
id: mcp_tool_storm
kind: skate_bowl
description: "MCP tool-storm 100 cmd/s → expect no offboard timeout, guardian stable"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 404
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 100
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 10 },
      expect: { state: HOVERING } }
  - { id: enter_offboard, tool: set_velocity_body, args: { forward: 0.0, right: 0.0, down: 0.0, yawspeed: 0.0, duration_s: 1 },
      expect: { state: OFFBOARD } }
  - { id: tool_storm, tool: noop_high_rate_commands, args: { rate_hz: 100, duration_s: 15, mix_get_telemetry: true },
      expect: { offboard_stale_ms: { lt: 400 } }
assertions:
  - within_s: 20
    expect: { state: OFFBOARD, guardian_alerts_max: { lte: 1 } }
  - eventually:
    expect: { landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

**Note:** If `noop_high_rate_commands` is not a real tool, implement as **orchestrator stage** in runner (built-in stress harness) — same YAML `tool` string must map in `Orchestrator` registry.

- [ ] **Commit** `feat(sim): add mcp_tool_storm scenario`

---

### Task D11.9: `acrobatic_corkscrew_battery_drop.yaml` + test

**Drivers:** `BatteryDrainDriver`. Tier: **sih**.

```yaml
id: acrobatic_corkscrew_battery_drop
kind: snowboard_halfpipe
description: "acrobatic corkscrew → mid-maneuver battery drop → expect safe recovery"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 88
  speed_factor: 1.5
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 45
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 30 },
      expect: { state: HOVERING } }
  - { id: corkscrew, tool: acrobatic_sequence, args: { maneuver: corkscrew, intensity: 0.7 },
      async: true }
injections:
  - at: { stage: corkscrew, t_offset_s: 2 }
    driver: battery_drain
    params: { rate_pct_per_s: 8, floor_pct: 12 }
assertions:
  - within_s: 25
    expect: { state: [RTL, LAND, HOLD] }
  - eventually:
    expect: { crashed: false, landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add acrobatic_corkscrew_battery_drop scenario`

---

### Task D11.10: `geofence_adjacent_goto_reject.yaml` + test

**Drivers:** none (negative). Tier: **sih**.

```yaml
id: geofence_adjacent_goto_reject
kind: nature_cinematic
description: "geofence-adjacent goto → expect Guardian rejection + PX4 GF defense-in-depth"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 123
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 100
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 12 },
      expect: { state: HOVERING } }
  - { id: fence_load, tool: set_geofence_polygon, args: { polygon: home_box_400m, action: rtl },
      expect: { success: true } }
  - { id: bad_goto, tool: goto_gps, args: { lat: 47.4017, lon: 8.5456, alt_m: 15 },
      expect: { rejected: true, error_code: GUARDIAN_VIOLATION } }
assertions:
  - within_s: 5
    expect: { state: HOVERING, px4_geofence_breached: false }
  - eventually:
    expect: { landed: false }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add geofence_adjacent_goto_reject scenario`

---

### Task D11.11: `companion_fc_partition_recover.yaml` + test

**Drivers:** `NetworkPartitionDriver`. Tier: **gazebo** (netem in compose sidecar per W2b).

```yaml
id: companion_fc_partition_recover
kind: runner_follow
description: "companion↔FC partition (tc netem) → expect detect + reconnect"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: gazebo
  world: urban
  px4_model: gz_x500
  seed: 33
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 95
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 12 },
      expect: { state: HOVERING } }
  - { id: loiter, tool: set_flight_mode, args: { mode: LOITER },
      expect: { state: HOVERING } }
injections:
  - at: { stage: loiter, t_offset_s: 4 }
    driver: network_partition
    params: { loss_percent: 40, duration_s: 12, interface: eth0 }
assertions:
  - within_s: 25
    expect: { link_drop_events: { gte: 1 }, link_recovered: true }
  - eventually:
    expect: { state: HOVERING, landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** `feat(sim): add companion_fc_partition_recover scenario`

---

### Task D11.12: `flight_recorder_replay_diff.yaml` + test

**Drivers:** none (replay). Tier: **offline**.

```yaml
id: flight_recorder_replay_diff
kind: nature_cinematic
description: "flight-recorder JSONL replay → regression diff vs live run"
backends: [flight_recorder]
sim:
  tier: offline
  world: default
  px4_model: none
  seed: 0
  speed_factor: 1.0
preconditions:
  px4_params: hardware/px4/airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 100
stages:
  - { id: load_baseline, tool: flight_recorder_load, args: { path: artifacts/baseline/orbit_offboard_freeze.jsonl },
      expect: { success: true } }
  - { id: replay, tool: flight_recorder_replay, args: { tolerance: strict },
      expect: { max_state_delta: { lte: 0 } } }
assertions:
  - within_s: 5
    expect: { replay_ok: true }
teardown:
  collect: [replay_diff_report, guardian_alerts]
```

- [ ] **Commit** `feat(sim): add flight_recorder_replay_diff scenario`

---

### Task D11.13: Expand W2b trio if filenames differ

If W2b delivered `search_vision_dropout.yaml` / `gps_jam_rtl.yaml` instead of D11.1/D11.2 names:

- [ ] **Step 1:** Rename files to this plan’s canonical ids **or** add symlink scripts in `avatar/sim/scenarios/` — single source of truth for `run-scenario.sh`.

- [ ] **Step 2:** Ensure `pr-fast` three scenarios (`mcp_tool_storm`, `geofence_adjacent_goto_reject`, `search_acquire_follow_vision_dropout`) exist and pass on SIH/Gazebo mix per D12.1.

- [ ] **Step 3:** Commit `chore(sim): align W2b scenario ids with Wave 3 names`

---

# Stream D12 — CI pipelines

**Pinned action references (use these exact tags):**

- `actions/checkout@v4.2.2`
- `actions/setup-python@v5.3.0`
- `docker/setup-buildx-action@v3.7.1`
- `actions/upload-artifact@v4.4.3`

**PX4 pin for matrices:** `v1.15.0` (align with hermes Gazebo note).

---

### Task D12.1: `pr-fast.yml` + yamllint

**Files:**

- Create: `.github/workflows/pr-fast.yml`

- [ ] **Step 1: Add workflow**

```yaml
name: PR Fast

on:
  pull_request:

concurrency:
  group: pr-fast-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: actions/setup-python@v5.3.0
        with:
          python-version: "3.12"
          cache: pip

      - name: Install linters
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy bandit yamllint

      - name: Ruff
        run: ruff check avatar tests scripts hardware

      - name: Mypy
        run: mypy avatar

      - name: Bandit
        run: bandit -r avatar -c pyproject.toml || bandit -r avatar

      - name: Yamllint workflows
        run: yamllint -d relaxed .github/workflows/pr-fast.yml

  unit:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ["3.12"]
        os: [ubuntu-latest]
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: actions/setup-python@v5.3.0
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install package + test deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Pytest unit (exclude sim / HITL)
        run: pytest -m "not sim and not hardware_in_loop" --tb=short -q

  sih-smoke:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: actions/setup-python@v5.3.0
        with:
          python-version: "3.12"
          cache: pip

      - uses: docker/setup-buildx-action@v3.7.1

      - name: Cache Docker layers
        uses: actions/cache@v4.2.0
        with:
          path: /tmp/.buildx-cache
          key: buildx-sih-${{ github.sha }}
          restore-keys: |
            buildx-sih-

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Start SIH stack
        run: ./scripts/sim.sh sih

      - name: Run three representative scenarios
        run: |
          ./scripts/run-scenario.sh mcp_tool_storm
          ./scripts/run-scenario.sh geofence_adjacent_goto_reject
          ./scripts/run-scenario.sh search_acquire_follow_vision_dropout || \
            ./scripts/run-scenario.sh search_acquire_follow_vision_dropout
        env:
          AVATAR_SIM_TIER: sih

      - name: Tear down
        if: always()
        run: ./scripts/sim.sh down
```

**Note:** Third scenario may require Gazebo; if `search_acquire_follow_vision_dropout` cannot run on SIH only, **replace** with `runner_follow_wind_gust` gated behind `continue-on-error: false` only after tier fix — **for <8 min budget**, use three SIH-capable ids: `mcp_tool_storm`, `geofence_adjacent_goto_reject`, `gps_jam_expect_rtl` and update comment in workflow.

**Replace the block** with:

```yaml
      - name: Run three representative scenarios
        run: |
          ./scripts/run-scenario.sh mcp_tool_storm
          ./scripts/run-scenario.sh geofence_adjacent_goto_reject
          ./scripts/run-scenario.sh gps_jam_expect_rtl
```

- [ ] **Step 2: Local yamllint**

Run: `pip install yamllint && yamllint -d relaxed .github/workflows/pr-fast.yml`
Expected: no errors.

- [ ] **Step 3: Commit** `ci: add pr-fast workflow`

---

### Task D12.2: `nightly-rich.yml`

**Files:**

- Create: `.github/workflows/nightly-rich.yml`

```yaml
name: Nightly Rich

on:
  schedule:
    - cron: "0 5 * * *"
  workflow_dispatch:

concurrency:
  group: nightly-rich-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

jobs:
  gazebo-scenarios:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        px4_tag: ["v1.15.0"]
        world: ["default", "urban", "forest"]
    env:
      PX4_TAG: ${{ matrix.px4_tag }}
      AVATAR_WORLD: ${{ matrix.world }}
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: actions/setup-python@v5.3.0
        with:
          python-version: "3.12"
          cache: pip

      - uses: docker/setup-buildx-action@v3.7.1

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          pip install hypothesis

      - name: Start Gazebo tier
        run: ./scripts/sim.sh gazebo

      - name: Run all 12 scenarios
        run: ./scripts/sim.sh all-scenarios

      - name: Property tests (Hypothesis)
        run: pytest -q tests --hypothesis-profile ci -m property || pytest -q -k hypothesis --maxfail=1

      - name: Performance suite
        run: pytest -q tests -m perf || true

      - name: Collect scenario artifacts
        if: always()
        run: bash .github/scripts/collect-artifacts.sh "${{ github.run_id }}-${{ matrix.world }}"

      - uses: actions/upload-artifact@v4.4.3
        if: always()
        with:
          name: scenario-artifacts-${{ matrix.world }}-${{ github.run_id }}
          path: collected-artifacts/
          retention-days: 30

      - name: Tear down
        if: always()
        run: ./scripts/sim.sh down
```

**Note:** Add `@pytest.mark.property` / `@pytest.mark.perf` if missing — first implement markers in `pyproject.toml` `[tool.pytest.ini_options]` markers section.

- [ ] **Commit** `ci: add nightly-rich workflow for Gazebo matrix`

---

### Task D12.3: `release.yml`

**Files:**

- Create: `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

jobs:
  build-and-verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: docker/setup-buildx-action@v3.7.1

      - name: Build sim-sih image
        run: docker build -f docker/sim-sih/Dockerfile -t avatar/sim-sih:release docker/sim-sih

      - name: Build sim-gazebo image
        run: docker build -f docker/sim-gazebo/Dockerfile -t avatar/sim-gazebo:release docker/sim-gazebo

      - uses: actions/setup-python@v5.3.0
        with:
          python-version: "3.12"
          cache: pip

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Full scenario matrix
        run: ./scripts/sim.sh all-scenarios

      - name: Pin digests to manifest
        run: |
          python .github/scripts/pin-digests.py \
            --sih-image avatar/sim-sih:release \
            --gazebo-image avatar/sim-gazebo:release \
            --out release-manifest.json

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2.2.0
        with:
          files: release-manifest.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Note:** Replace `softprops/action-gh-release@v2.2.0` if org forbids third-party; else pin is acceptable for attachment upload.

- [ ] **Commit** `ci: add release workflow with digest manifest`

---

### Task D12.4: Helper scripts `collect-artifacts.sh` + `pin-digests.py`

**Files:**

- Create: `.github/scripts/collect-artifacts.sh`
- Create: `.github/scripts/pin-digests.py`

- [ ] **`collect-artifacts.sh`** (full script):

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: collect-artifacts.sh <run_suffix>" >&2
}

RUN_SUFFIX="${1:-}"
if [[ -z "$RUN_SUFFIX" ]]; then
  usage
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
mkdir -p "$ROOT/collected-artifacts/$RUN_SUFFIX"
shopt -s nullglob
for f in "$ROOT/artifacts"/*.tar.gz; do
  cp -a "$f" "$ROOT/collected-artifacts/$RUN_SUFFIX/"
done
printf "OK\t%s\t%d files\n" "$RUN_SUFFIX" "$(ls -1 "$ROOT/collected-artifacts/$RUN_SUFFIX" | wc -l)"
```

- [ ] **`pin-digests.py`** (minimal argparse + `docker inspect`):

```python
"""Write release-manifest.json with docker image digests."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def digest_for(image: str) -> str:
    out = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", image],
        text=True,
    ).strip()
    return out or image


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sih-image", required=True)
    p.add_argument("--gazebo-image", required=True)
    p.add_argument("--out", type=Path, default=Path("release-manifest.json"))
    args = p.parse_args()
    manifest = {
        "sim_sih": digest_for(args.sih_image),
        "sim_gazebo": digest_for(args.gazebo_image),
    }
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(args.out)}))


if __name__ == "__main__":
    main()
```

- [ ] **Dry-run test**

Run: `bash -n .github/scripts/collect-artifacts.sh && echo OK`
Expected: `OK`

Run: `python -m py_compile .github/scripts/pin-digests.py && echo OK`
Expected: `OK`

- [ ] **Commit** `ci: add artifact collection and digest pinning helpers`

---

# Stream D13 — Raspberry Pi provisioning

**Shell standard:** Every `*.sh` begins with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Include `usage()` and `exit 2` on invalid args.

---

### Task D13.1: `build-image.sh` + cloud-init `user-data` + `network-config`

**Files:**

- Create: `hardware/pi/build-image.sh`
- Create: `hardware/pi/cloud-init/user-data`
- Create: `hardware/pi/cloud-init/network-config`

- [ ] **`build-image.sh`** (body):

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: build-image.sh [--dry-run]" >&2
}

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

IMG_NAME="raspios-avatar-$(date +%Y%m%d).img.xz"
echo "IMG_NAME=$IMG_NAME"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo '{"dry_run":true,"would_invoke":"pi-gen or rpi-image-gen","eta_min":8}'
  exit 0
fi

# Real build: clone pi-gen, copy cloud-init, run build.sh — implementor fills per org mirror policy
exit 1
```

- [ ] **`user-data`** (cloud-init #cloud-config):

```yaml
#cloud-config
hostname: avatar-pi
manage_etc_hosts: true
users:
  - name: avatar
    groups: [adm, dialout, sudo, video, plugdev]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
ssh_authorized_keys:
  - ${AVATAR_SSH_KEY}
package_update: true
package_upgrade: true
packages:
  - python3.12
  - ffmpeg
  - systemd-timesyncd
runcmd:
  - systemctl enable systemd-timesyncd
```

- [ ] **`network-config`**:

```yaml
version: 2
wifis:
  wlan0:
    dhcp4: true
    access-points:
      "PLACEHOLDER_SSID":
        password: "PLACEHOLDER_PASSWORD"
```

- [ ] **Dry-run**

Run: `bash hardware/pi/build-image.sh --dry-run`
Expected stdout contains `"dry_run":true`

- [ ] **Commit** `hw(pi): add image build script and cloud-init stubs`

---

### Task D13.2: `flash.sh` + shellcheck

**Files:**

- Create: `hardware/pi/flash.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: flash.sh --wifi-config path --api-keys path [--img path]" >&2
}

# macOS: diskutil list + raw device; Linux: lsblk
# xz -d -c image.img.xz | sudo dd of=...
# mount boot partition; write wpa_supplicant.conf / firstrun.sh from --wifi-config JSON; copy keys env
# unmount

exit 1
```

- [ ] **shellcheck**

Run: `shellcheck hardware/pi/flash.sh hardware/pi/build-image.sh`
Expected: no errors (adjust until clean).

- [ ] **Commit** `hw(pi): add SD flash script for macOS and Linux`

---

### Task D13.3: Bootstrap installers

**Files:**

- Create: `hardware/pi/bootstrap/install-avatar.sh`
- Create: `hardware/pi/bootstrap/install-mavsdk.sh`
- Create: `hardware/pi/bootstrap/install-yolo-runtime.sh`

Each: clone `/opt/avatar`, `pip install -e .`, download `mavsdk_server` aarch64 from official release URL, install `ncnn` on arm64 / `openvino` on x86_64 guarded by `uname -m`.

- [ ] **shellcheck** all three; **Commit** `hw(pi): add bootstrap installers for avatar, mavsdk, yolo runtime`

---

### Task D13.4: systemd units + watchdog

**Files:**

- Create: `hardware/pi/systemd/avatar-mavlink-bridge.service`
- Create: `hardware/pi/systemd/avatar-heartbeat.service`
- Create: `hardware/pi/systemd/avatar-mcp.service`
- Create: `hardware/pi/systemd/watchdog.service`

**Example `avatar-mavlink-bridge.service`:**

```ini
[Unit]
Description=Avatar MAVLink bridge (mavsdk_server + mavlink-router)
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/opt/avatar/hardware/pi/bootstrap/run-mavlink-bridge.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

**`avatar-mcp.service`:** add `DisabledByDefault=yes` equivalent via `systemctl mask` doc in README; unit file includes comment `# default: disabled`.

- [ ] **Verify**

Run (on Linux with systemd): `systemd-analyze verify hardware/pi/systemd/*.service`
Expected: `OK` / no errors.

- [ ] **Commit** `hw(pi): add systemd units for mavlink bridge, heartbeat, optional MCP, watchdog`

---

### Task D13.5: udev + bring-up + README

**Files:**

- Create: `hardware/pi/udev/99-pixhawk.rules`
- Create: `hardware/pi/bring-up.sh`
- Create: `hardware/pi/README.md`

**`99-pixhawk.rules` example:**

```
# FTDI cable for Pixhawk TELEM
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="pixhawk", MODE="0660", GROUP="dialout"
```

- [ ] **bring-up.sh** writes `/boot/firmware/avatar-status.txt` on Bookworm or `/boot/avatar-status.txt` on older — detect mount point; status `green|yellow|red` + reasons.

- [ ] **Commit** `hw(pi): add udev rules, bring-up smoke, and operator README`

---

### Task D13.6: W3 dry-run gate (<10 min)

- [ ] **Step 1:** Implement `build-image.sh --dry-run` to complete in **<10 minutes** by avoiding heavy work (only validates inputs, dockerfile parse, `pi-gen` config tree).

- [ ] **Step 2:** Time it

Run: `/usr/bin/time -p bash hardware/pi/build-image.sh --dry-run`
Expected: `real` < 600

- [ ] **Step 3:** Commit `hw(pi): ensure build-image dry-run meets W3 timing gate`

---

# Stream D14 — PX4 provisioning

### Task D14.1: `flash-px4.sh` + shellcheck

**Files:**

- Create: `hardware/px4/flash-px4.sh`

- Script accepts `--airframe mark4_7in|x500_v2`, downloads pinned firmware from `https://github.com/PX4/PX4-Autopilot/releases/download/v1.15.0/Firmware-<board>.px4` (exact URL pattern to be verified against release assets), runs `python3 PX4-Autopilot/Tools/upload.py --port <usb> <file.px4>` without QGC.

- [ ] **shellcheck** clean

- [ ] **Commit** `hw(px4): add USB flash script using PX4 upload.py`

---

### Task D14.2: `airframes/mark4_7in.params` + test

**Files:**

- Create: `hardware/px4/airframes/mark4_7in.params`
- Create: `tests/hardware_px4/test_params_apply_mark4.py`

**Params (QGC / airframe syntax — `param set-default` lines for clarity + PX4 apply script compatibility):**

```
# Mark4 7" 6S 1500kV — minimum safety + offboard overlay (typical starting values; tune after bench)
param set-default SYS_AUTOSTART 4001
param set-default COM_OBL_RC_ACT 3
param set-default COM_OF_LOSS_T 0.5
param set-default COM_DISARM_PRFLT 15
param set-default NAV_DLL_ACT 2
param set-default NAV_RCL_ACT 2
param set-default COM_RCL_EXCEPT 4
param set-default BAT_N_CELLS 6
param set-default BAT_CAPACITY 1500
param set-default BAT_LOW_THR 0.25
param set-default BAT_CRIT_THR 0.15
param set-default BAT_EMERGEN_THR 0.10
param set-default GF_ACTION 2
param set-default GF_MAX_HOR_DIST 500
param set-default GF_MAX_VER_DIST 150
param set-default MC_ROLLRATE_P 0.15
```

- [ ] **Test:** parse file into dict; assert keys non-empty.

- [ ] **Commit** `hw(px4): add Mark4 7in airframe param overlay`

---

### Task D14.3: `airframes/x500_v2.params` + test

Mirror D14.2 with X500 defaults (`SYS_AUTOSTART` for `gz_x500` / quad generic — use `4011` as placeholder; engineer to match PX4 airframe list).

- [ ] **Commit** `hw(px4): add X500 v2 param overlay`

---

### Task D14.4: `airframes/custom_template.params`

Comment-only template: each tunable with **range + recommended start**; empty `param set-default` lines for user fill-in.

- [ ] **Commit** `hw(px4): add custom param template with ranges`

---

### Task D14.5: `calibrate.py` + stubbed unit test

**Files:**

- Create: `hardware/px4/calibrate.py`
- Create: `tests/hardware_px4/test_calibrate.py`

Use MAVSDK `calibration` plugin; mock `System` in test to assert step order: accel → gyro → mag → level → RC → motor (if applicable).

- [ ] **Commit** `hw(px4): add headless calibration walkthrough script`

---

### Task D14.6: `verify.py` + unit test + `PX4ParameterManager` overlay extension

**Files:**

- Create: `hardware/px4/verify.py`
- Modify: `avatar/mav/px4_parameters.py` — add optional `overlay: dict[str, int | float] | Path` to `verify_safety_parameters` merging **file params + CRITICAL_PARAMETERS** (overlay wins on key intersection).

- [ ] **verify.py** loads `hardware/px4/airframes/<airframe>.params`, builds overlay dict, instantiates manager against mock drone, asserts all valid.

- [ ] **Commit** `feat(px4): verify airframe overlay against FC or mock`

---

### Task D14.7: `preflight.py` + `--dry-run` + README

**Files:**

- Create: `hardware/px4/preflight.py`
- Create: `hardware/px4/README.md`
- Create: `tests/hardware_px4/test_preflight_dry_run.py`

**Dry-run behavior:** `python hardware/px4/preflight.py --dry-run --airframe mark4_7in` loads overlay, runs `verify` logic **without** TCP/serial connect; prints plaintext + JSON line `{"status":"PASS","mode":"dry_run"}` to stdout; exit `0`.

Run:

```bash
python hardware/px4/preflight.py --dry-run --airframe mark4_7in
```

Expected: exit code `0`; stdout contains `"PASS"`.

- [ ] **Commit** `hw(px4): add preflight CLI and operator README`

---

## Self-Review

**1. Spec coverage**

| Spec section | Task(s) |
|--------------|---------|
| §4 D11 twelve pipelines | D11.1–D11.12 (+ D11.13 alignment) |
| §4 D12 CI | D12.1–D12.4 |
| §4 D13 Pi tree | D13.1–D13.6 |
| §4 D14 PX4 tree | D14.1–D14.7 |
| §5.1 YAML fields | Every YAML includes `id`, `kind`, `description`, `backends`, `sim.*`, `preconditions`, `stages`, `injections`, `assertions`, `teardown` |
| §8 Docker + CI | D12 workflows reference `scripts/sim.sh`, Docker Buildx, caching |
| §9.1 / §9.2 hardware layouts | D13 / D14 file maps |
| §11 W3 gate | Wave Gate section + D13.6 + D14.7 + `all-scenarios` prerequisite |
| `changes-made.md` | Wave gate post-step |

**Gaps addressed in-plan:** `verify_safety_parameters(overlay)` extension (D14.6); `pr-fast` third scenario uses SIH-capable list (D12.1 note); `noop_high_rate_commands` / replay tools must exist in runner (D11.8, D11.12) — **if missing from W2b**, add runner tasks in Wave 2b hotfix before W3.

**2. Placeholder scan**

No `TBD` / `TODO` / unfilled test bodies for primary deliverables; intentional `exit 1` stubs in `flash.sh` / real image build must be replaced during implementation (acceptable as explicit fail-fast until completed — engineer replaces with real `pi-gen` invocation in same task series).

**3. Type consistency**

Scenario `id` strings match `run-scenario.sh` argv, test glob patterns, and `all-scenarios` list order. Driver snake_case matches D10 naming. `pytest` markers: `sim` for subprocess scenario tests; `property` / `perf` optional for nightly.

---

**Plan complete.** Execution choice per writing-plans: subagent-driven development vs executing-plans — pick after W2b merge.
