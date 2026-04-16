# Project Avatar — First-Flight-Ready Plan Design

**Spec date:** 2026-04-16
**Status:** Awaiting user review before `writing-plans`
**Scope locks confirmed in brainstorming session:** see §2

This document is the design spec that `writing-plans` will turn into a dependency-ordered implementation plan. It consolidates the output of four Composer-2 exploration subagents that read the roadmap, docs, core Python, MCP server, and simulation/test infrastructure.

---

## 1. North star

Turn Project Avatar from "verification-gated Phase 0.5A" into **first-flight-ready**: all code paths the agent depends on work end-to-end in Docker simulation, runtime profiles let us swap between SITL and hardware via configuration, the Pi and Pixhawk are provisioned by one-line scripts, an HITL harness validates the same scenarios against real hardware, and the first real outdoor flight is a runbook, not an engineering project.

The plan also lifts the MCP tool surface so the agent has both fine-grained primitives (mode, arm, body-frame velocity, mission upload, parameters, geofence) and high-level orchestrators (vision-closed-loop tracking, waypoint missions, scenic sweeps, mission-from-intent). A new mission-intelligence layer gives the agent offline-first environmental awareness (OSM + SRTM) enriched by Google Maps (Places, Static Maps, Street View, Roads, Geocoding) so it can reason about where to fly and what to shoot.

---

## 2. Scope locks (from brainstorming)

| # | Decision | Answer |
|---|---|---|
| Q1 | "Done" state | **D — First-flight-ready**: SITL-complete → flash-ready → HITL-validated → field runbook |
| Q2 | Canonical hardware | Undecided; **shopping-list stack as default** (Mark4 7″ + Pixhawk 6C Mini + Pi 4 + Pi Cam 3 Wide). Profile system must be airframe/companion-swappable without rewriting tools. |
| Q3 | Simulation strategy | **Two-tier Docker** (SIH fast + Gazebo rich) + **HITL harness** gated on hardware arrival + **first-class failure injection** |
| Q4 | MCP strategy | **Full spec + expanded surface + perception-aware mission planner** — annotations, outputSchema, structured errors, ImageContent, confirmation, new primitives, new orchestrators, mission intel |
| Q5 | Mapping layer | OSM + elevation (offline) + Google Maps enrichment (Places + Static Maps + Street View + Roads + Geocoding; key-gated with daily budget). No airspace/weather/NOTAM. |
| Q6 | Dormant code fate | **Wire everything up**: ConfirmationManager, EscalationMatrix, advanced_tracking, cinematic_shots_personal, acrobatic_sequence. Delete only legacy `DroneConnection`. |
| Q3-confirm | Confirmation policy | **Curated** short list of scary actions prompt; everything else runs silently and logs. List in §10. |
| Structural | Plan structure | **Option C — dependency-graph waves** (not waterfall, not vertical slices) |

---

## 3. Current-state baseline (from exploration)

Findings the plan must assume as starting conditions:

**Present and working:**
- ~767 pytest functions across `avatar/tests/` and `tests/`.
- 26 live MCP tools registered in `server.py`.
- Phase 0.5A spine: `ConnectionManager`, `TelemetryCache`, `HeartbeatService`, `FlightStateMachine`, `AsyncGuardian`, `PX4ParameterManager`, `OffboardVelocityStreamer`, `RuntimeProfile` scaffolding, `FlightRecorder`.
- SIH smoke and MCP stdio smoke pass per `changes-made.md`.

**Broken / disconnected wires (must be fixed by Wave 1):**
- `managed_offboard._heartbeat` only sleeps; sends no setpoints.
- `HeartbeatService._emit_loop` only invokes a callback; no MAVLink unless wired.
- `AsyncGuardian.initiate_rtl/land/hold/emergency_stop` only calls `sm.trigger_failsafe(...)` — never invokes `drone.action.*`. Python-layer failsafe does not move the aircraft.
- `EscalationMatrix` exported but zero consumers.
- Hardware vision providers `rtsp_camera` and `yolo_detector` referenced in `HARDWARE_PROFILE` have no implementation; `GazeboCameraProvider.capture_frame` raises.
- `pyproject.toml` console script `avatar = avatar.main:main` points to a file that doesn't exist.
- `.pre-commit-config.yaml` coverage hook targets `--cov=src/drone`; `.bandit.yaml` globs `./src/**` and `./drone/**`; pre-commit skips pytest/coverage on CI. None match `avatar/`.
- `orbit_target` uses async `get_drone()` without `await`.
- `scripts/validate_mcp_server.py` says 10 tools live; 26 are live.
- Tools lack `outputSchema`, annotations, `ImageContent`, structured error codes.
- `ConfirmationManager` exists but `server.py` never imports it.
- Per-call `TelemetryTools()` / `VisionTools()` instantiation on hot paths.
- `avatar/sim/scenarios.py` declares six `ScenarioKind` values, defines four; pytest gates don't assert vision/wind/depth.
- No `Dockerfile`, `docker-compose`, `.github/workflows`, `Makefile` in repo.
- Two test trees (`avatar/tests/`, `tests/`) drift from each other.
- `avatar/tests/test_sitl_basic.py` checks for `--run-sitl` in `sys.argv` (brittle).

**Decisions already locked in docs** (DECISIONS.md): 4-layer safety, RPi holds safety cadence (DEC-003), MAVSDK-Python (DEC-004), three-stage roadmap (DEC-005), Kimi K2.5 default LLM (DEC-015), agent-agnostic MCP (DEC-016). This plan does not re-litigate any of those.

---

## 4. Architecture — domain map

Sixteen domains grouped into five dependency waves. Every domain has a clear directory target.

### Wave 0 — Foundation (sequential, blocks everything)

**D1. Dead-wood + tooling fixes**
- Fix `pyproject.toml` console script; either create `avatar/main.py` (thin entrypoint calling `avatar.mcp_server.__main__.main`) or remove the entry.
- Repair `.pre-commit-config.yaml` coverage hook, `coverage-check`, `check-import-cycles` to target `avatar/`.
- Repair `.bandit.yaml` include globs.
- Delete legacy `avatar/mav/connection.py` (`DroneConnection`) and update imports.
- Migrate `avatar/tests/` into `tests/` under the existing structure; update `pyproject.toml testpaths`.
- Replace `sys.argv`-based `--run-sitl` detection with standard pytest option in `tests/conftest.py`.
- Fix `scripts/validate_mcp_server.py` to reflect live tool count.
- Decide exact PX4 SIH target string (`sihsim_quadx` vs `sihsim_quadrotor`) via upstream probe; record in `avatar/sim/constants.py`.

### Wave 1 — Spines (parallel)

**D2. Safety spine**
- Wire `ConfirmationManager` into `AvatarMCPServer`; add session capability `auto_confirm`; list in §10 decides what prompts.
- Adopt `EscalationMatrix` as the single failsafe-policy consumer. `AsyncGuardian` publishes events to it; matrix decides action; registered handler issues MAVSDK commands.
- Make `AsyncGuardian.initiate_rtl/land/hold/emergency_stop` actually call `drone.action.return_to_launch()` / `land()` / `hold()` / emergency stop sequence. State machine update stays.
- Resolve the offboard-streaming coexistence problem: define a single "offboard owner" registry. `OffboardVelocityStreamer` becomes the only setpoint emitter. `HeartbeatService` becomes agent-liveness only (records heartbeats from named sources, raises alerts on stale; it does NOT emit MAVLink setpoints even if a callback is attached — remove that affordance). `managed_offboard` keeps its lifecycle-management role (enter/exit offboard mode with guaranteed cleanup) but its internal heartbeat task is deleted; callers that need streaming use `OffboardVelocityStreamer` explicitly. Tools that attempt to stream concurrently without ownership fail with a structured `OFFBOARD_OWNERSHIP_CONFLICT` error.
- Resolve altitude-domain confusion: `HardLimits` uses AMSL consistently; document domain on every boundary; reject ambiguous input with a structured error.
- Make `COM_OBL_RC_ACT` policy explicit and configurable via profile.

**D3. MCP hardening v1**
- Add `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` to every tool.
- Add `outputSchema` to every tool.
- Replace free-form error strings with structured envelope (`avatar/mcp_server/errors.py` enum of codes + `{code, category, message, recoverable, suggested_action}`).
- Replace JSON-as-text for vision tools with `ImageContent` MCP type.
- Add `ping` and `cancel_operation` tools.
- Kill per-call `TelemetryTools()` / `VisionTools()` — reuse server-held singletons.
- Rename: server status → `get_server_status`; drone status → `get_drone_status`.
- Register `acrobatic_sequence` (orphaned import).
- Fix `orbit_target` `get_drone()` `await` bug; add cancel-safe loops throughout.
- Update `scripts/validate_mcp_server.py`.

**D4. Docker sim infrastructure**
- `docker/sim-sih/Dockerfile` — `python:3.12-slim-bookworm`, PX4 built with `make px4_sitl_default <sih_target>`, avatar editable install, entrypoint binds `14540/udp`. Image target <700 MB.
- `docker/sim-gazebo/Dockerfile` — `ubuntu:24.04`, Gazebo Harmonic, gz-sim8, Xvfb, Mesa llvmpipe, PX4 `gz_x500`. `linux/amd64` only.
- `docker/shared/wait-for-px4.py` and `wait-for-mcp.py` health-check helpers.
- `docker/compose.yaml` with `sih`, `gazebo`, `sih-test`, `gazebo-test` profiles.
- `scripts/sim.sh` top-level CLI (`sih`, `gazebo`, `scenario <id>`, `down`, `logs`).
- `scripts/run-scenario.sh` orchestrator that spins stack, runs YAML, tars artifacts.

### Wave 2a — Core MCP expansion (depends on W1:2, W1:3)

**D5. MCP primitives (new low-level tools)**

| Tool | Signature | Annotations |
|---|---|---|
| `arm` | `{force?: bool}` → arm only | destructive, not idempotent |
| `disarm` | `{force?: bool}` → disarm | destructive, not idempotent |
| `set_flight_mode` | `{mode: enum, submode?: string}` | destructive, idempotent |
| `set_velocity_body` | `{forward, right, down, yawspeed, duration_s}` | destructive |
| `goto_local_ned` | `{x_m, y_m, z_m, yaw_deg?}` | destructive |
| `upload_mission` | `{mission: Mission}` | destructive |
| `start_mission` | `{}` | destructive, idempotent |
| `pause_mission` | `{}` | destructive, idempotent |
| `resume_mission` | `{}` | destructive, idempotent |
| `set_geofence_polygon` | `{polygon: Polygon, action: rtl\|land\|warn}` | destructive |
| `load_plan` | `{path or contents}` → parsed Mission | readOnly |
| `get_parameter` | `{name}` | readOnly, idempotent |
| `set_parameter` | `{name, value}` | destructive |
| `preflight_checklist` | `{}` → consolidated report | readOnly |
| `get_guardian_limits` | `{}` → current HardLimits | readOnly, idempotent |
| `submit_operator_confirmation` | `{token, approved, note?}` | destructive (satisfies a queued prompt) |

**D6. MCP orchestrators (new high-level tools)**

| Tool | Purpose |
|---|---|
| `track_bbox` | Closed-loop: bbox + class → gimbal + velocity until lost or cancelled |
| `orbit_subject_vision` | Orbit center follows a tracked subject, not a GPS point |
| `execute_waypoint_mission` | Run structured waypoints with behaviors (hover, photo, orbit, cinematic); emits progress |
| `log_mission_segment` | Append named segment with summary to flight recorder |
| `evaluate_last_command` | Post-hoc: energy used, drift, success vs intent |
| `expose_advanced_tracker` | Surface the Kalman + latency-compensated tracker from `advanced_tracking.py` |

Plus: merge `cinematic_shots_personal.py` templates into `CinematicShotPlanner`. Remove the free-form `custom_params` object in `execute_cinematic_shot` in favor of typed overrides declared by each template.

**Checkpoint for W2a:** every new tool schema-validated, annotated, unit-tested, and exercised against SIH tier. No regression in existing 26 tools.

### Wave 2b — Intelligence, providers, scenarios (depends on W2a + W1:4)

**D7. Hardware vision providers**
- `avatar/vision/providers/rtsp.py` — `RtspCameraProvider` using `av` / `ffmpeg` for low-latency H.264.
- `avatar/vision/providers/yolo.py` — `YoloDetectorProvider` with backend selection (`ultralytics` on CUDA, `ncnn` on ARM64 Pi, `openvino` on x86 CPU). Lazy model load. Confidence + label filters.
- `avatar/vision/providers/realsense.py` — `RealSenseCameraProvider` stub with depth + color.
- `avatar/vision/providers/oak.py` — `OakCameraProvider` stub using `depthai` (branches DEC-005 decision to later).
- `avatar/vision/providers/gazebo.py` — replace raises-RuntimeError stub with real gz-topic subscription.
- Wire `HARDWARE_PROFILE` backend strings to concrete providers via registry.

**D8. Mission intelligence layer** — new package `avatar/mission_intel/`

Structure:
```
avatar/mission_intel/
  providers/
    base.py             # MappingProvider / ElevationProvider protocols
    osm.py              # Overpass + Nominatim; disk cache
    elevation.py        # SRTM HGT tiles + Open-Elevation fallback
    gmaps.py            # Places, Static Maps, Street View, Roads, Geocoding
    dem_cache.py        # SRTM tile store at ~/.cache/avatar/dem/
  geo.py                # Point, BBox, Polygon, haversine, grids
  terrain.py            # AGL, slope, ruggedness, line-of-sight
  area_analyzer.py      # analyze_area()
  scenic_sweep.py       # plan_scenic_sweep()
  intent_planner.py     # plan_mission_from_intent() — grammar parser, not LLM
  mission_spec.py       # pydantic Mission v1.0 + validator
  safety_checks.py      # geofence overlap, min-AGL, battery feasibility
  config.py             # API keys, cache dirs, rate limits, daily budget
```

New MCP tools exposed by `avatar/mcp_server/tools/mission_intel_tools.py`:

| Tool | Annotations |
|---|---|
| `analyze_area` | readOnly, openWorld |
| `lookup_place` | readOnly, openWorld, idempotent |
| `get_elevation` | readOnly, openWorld, idempotent |
| `get_agl` | readOnly, openWorld, idempotent |
| `plan_scenic_sweep` | readOnly, openWorld |
| `plan_mission_from_intent` | readOnly (pure calc; does not command drone) |
| `propose_orbit_for_subject` | readOnly |

Google Maps coverage (enrichment only, OSM is primary):
- **Places** — search + details.
- **Static Maps** — satellite basemap image → `AreaReport.satellite_snapshot` as `ImageContent`.
- **Street View Static** — ground-level imagery for candidate reveal anchors.
- **Roads** — nearest roads + snap, feeds obstacle awareness and approach-vector planning.
- **Geocoding** — address / place name → `Point` for intent planner.

Guardrails:
- `GOOGLE_MAPS_API_KEY` env gate; silent no-op when absent.
- `GMAPS_DAILY_BUDGET` env (default 500 req/day). Hard ceiling enforced per process.
- Every call cached by content hash under `~/.cache/avatar/gmaps/` with per-endpoint TTL.
- Every call wrapped in `asyncio.timeout(2.5)`; failures degrade gracefully to OSM.

**D9. Profile & config v2**
- Upgrade `avatar/config/profiles.py` from frozen dataclass to a real loader:
  - ENV + file + secrets, pydantic validation.
  - Airframe-aware sub-profiles: `mass_kg`, `prop_size_in`, `px4_airframe_id`, `battery_cells`, `max_thrust_n`, `param_overlay_path`.
  - Preflight gate: if `requires_px4_parameter_check`, call `PX4ParameterManager.verify_safety_parameters(airframe.param_overlay)` and block startup on mismatch.
- Templates for `mark4_7in`, `x500_v2`, `custom`.

**D10. Scenario orchestration framework**
- Declarative YAML format (see §5).
- `avatar/sim/runner.py` — `ScenarioLoader`, `Orchestrator`, `InjectionScheduler`, `AssertionEngine`, `ArtifactCollector`.
- `avatar/sim/drivers/` — `WindDriver`, `GpsLossDriver`, `VisionDropoutDriver`, `OffboardFreezeDriver`, `BatteryDrainDriver`, `RcLossDriver`, `ObstacleProximityDriver`, `TargetMotionDriver`, `NetworkPartitionDriver`.
- Define all six `ScenarioKind` (add `snowboard_halfpipe`, `skate_bowl` rows).

**Checkpoint for W2b:** `analyze_area` returns valid `AreaReport` offline; three representative pipeline scenarios run green end-to-end in Gazebo tier; hardware vision providers unit-tested on recorded frames.

### Wave 3 — Integration (parallel, depends on W2a + W2b)

**D11. Advanced multi-step scenarios** — populate all 12 pipelines from §5.

**D12. CI pipelines** — `.github/workflows/pr-fast.yml`, `nightly-rich.yml`, `release.yml`. Matrix + artifact upload.

**D13. Pi provisioning** — `hardware/pi/` with `build-image.sh`, `flash.sh`, `bring-up.sh`, systemd units (`avatar-mcp`, `avatar-heartbeat`, `mavlink-router`, `watchdog`), udev rules, cloud-init. See §8.

**D14. PX4 provisioning** — `hardware/px4/` with `flash-px4.sh`, airframe `.params` files, `calibrate.py`, `verify.py`, `preflight.py`. See §8.

### Wave 4 — Final validation (sequential)

**D15. HITL harness** — `tests/hitl/` with `--run-hitl` marker; fixtures for SIH-on-FC (laptop ↔ FC over USB) and full Pi+FC-over-UART.

**D16. Runbook + polish** — `docs/runbooks/preflight.md`, `first-flight.md`, `troubleshooting.md`, `calibration.md`, `field-kit.md`. README update, CHANGELOG, archive completed plans.

### Dependency graph (edges)

```
W0:D1 → W1:{D2, D3, D4}
W1:{D2, D3} → W2a:{D5, D6}
W1:{D2, D3, D4} + W2a:{D5, D6} → W2b:{D7, D8, D9, D10}
W2a + W2b → W3:{D11, D12, D13, D14}
W3 → W4:D15 → W4:D16
```

---

## 5. Scenario + failure-injection framework

**5.1 YAML schema** — one file per scenario under `avatar/sim/scenarios/*.yaml`

```yaml
id: orbit_with_offboard_freeze
kind: nature_cinematic
description: "Orbit a landmark, simulate MCP offboard link freeze mid-orbit, verify RTL"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo              # sih | gazebo
  world: default
  px4_model: gz_x500
  seed: 42
  speed_factor: 1.0
preconditions:
  px4_params: airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 85
stages:
  - { id: takeoff,     tool: arm_and_takeoff, args: { altitude_m: 15 },
      expect: { state: HOVERING } }
  - { id: goto_target, tool: goto_gps,        args: { lat: 47.3978, lon: 8.5460, alt_m: 25 } }
  - { id: start_orbit, tool: orbit_target,    args: { target_lat: 47.3978, target_lon: 8.5460,
                                                      radius_m: 10, speed_m_s: 3, duration_s: 60 },
      async: true }
injections:
  - at: { stage: start_orbit, t_offset_s: 15 }
    driver: offboard_freeze
    params: { duration_s: 3 }
assertions:
  - within_s: 8
    expect: { state: [HOLD, RTL], reason_contains: offboard }
  - eventually:
    expect: { landed: true, home_distance_m: { lt: 5 } }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

**5.2 Runner** — `avatar/sim/runner.py`

- `ScenarioLoader` — YAML → pydantic `Scenario`.
- `Orchestrator` — runs stages sequentially (or `async: true` in parallel) against a live MCP stdio session.
- `InjectionScheduler` — subscribes to stage start/progress events, fires drivers at `t_offset_s`.
- `AssertionEngine` — matches `within_s` (time-bounded) and `eventually` (end-of-run).
- `ArtifactCollector` — tars PX4 log, flight recorder JSONL, guardian alerts, state-machine transitions, sim topics into `artifacts/<run_id>/`.

**5.3 Driver interface**

```python
class Driver(Protocol):
    name: str
    supported_tiers: set[SimTier]

    async def inject(self, ctx: DriverContext) -> None: ...
    async def release(self, ctx: DriverContext) -> None: ...
```

**5.4 The 12 pipelines** (Wave 3 deliverable)

| # | Pipeline | Injection | Tier |
|---|---|---|---|
| 1 | takeoff → search grid → acquire → follow → vision dropout → expect hold/RTL | VisionDropout | GZ |
| 2 | takeoff → loiter → GPS jam → expect RTL/land per PX4 params | GpsLoss | SIH+GZ |
| 3 | runner-follow → sustained wind → verify tracking error bound and no crash | Wind | GZ |
| 4 | orbit → offboard freeze 3 s → expect HOLD → resume or RTL | OffboardFreeze | SIH+GZ |
| 5 | cinematic reveal → battery critical → expect RTL preempts shot | BatteryDrain | SIH |
| 6 | depth-room crawl → obstacle at 1.5 m → expect velocity clamp + abort | ObstacleProximity | GZ |
| 7 | sailboat follow → lateral wind + altitude drift → expect AGL floor held | Wind | GZ |
| 8 | MCP tool-storm (100 cmd/s) → expect no offboard timeout, guardian stable | none | SIH |
| 9 | acrobatic corkscrew → mid-maneuver battery drop → expect safe recovery | BatteryDrain | SIH |
| 10 | geofence-adjacent goto → expect guardian rejection + PX4 GF defense-in-depth | none (negative) | SIH |
| 11 | companion↔FC partition (tc netem) → expect detect + reconnect | NetworkPartition | GZ |
| 12 | flight-recorder JSONL replay → regression diff vs live run | none (replay) | offline |

**5.5 Determinism contract**

Every scenario pins `seed`, `speed_factor`, PX4 commit hash, Gazebo world hash, container digest. Hypothesis property tests use `derandomize=true` in CI. Artifacts are diffable run-to-run.

---

## 6. MCP tool surface — before / after

**6.1 Existing 26 tools — fixed in Wave 1 (D3)**

- All get annotations + outputSchema + structured errors.
- `get_telemetry` uses singleton cache (kills per-call instantiation).
- `land` / `rtl` / `abort_mission` gain Guardian validation.
- `set_velocity` schema tightened; splits from `set_velocity_body` in Wave 2a.
- `detect_objects` / `get_detected_objects` expose `target_labels` + `min_confidence`; return `ImageContent`.
- `get_status` renamed `get_server_status`; drone status → `get_drone_status`.
- Acrobatic tools gain `destructiveHint` + Guardian preflight + `HardLimits` min-altitude.
- `orbit_target` fixed (`await cm.get_drone()`), cancel-safe.
- `execute_cinematic_shot` replaces free-form `custom_params` with typed overrides; merges personal templates.
- Register orphan `acrobatic_sequence`.
- Add top-level `ping` and `cancel_operation`.

**6.2 New primitives — Wave 2a (D5)**

See D5 table above (16 tools).

**6.3 New orchestrators — Wave 2a (D6)**

See D6 table above (6 tools).

**6.4 New mission-intel tools — Wave 2b (D8)**

See D8 table above (7 tools).

**6.5 Removed**

- `avatar/mav/connection.py` (`DroneConnection`) — deleted as clear legacy.

**6.6 Annotation policy**

Every tool declares all four of `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`. Default `openWorldHint: false` except mission-intel tools hitting external APIs (set `true`).

**6.7 Structured error envelope**

```json
{
  "isError": true,
  "error": {
    "code": "GUARDIAN_VIOLATION",
    "category": "safety",
    "message": "altitude_m=150 exceeds HardLimits.max_altitude_m=120",
    "recoverable": true,
    "suggested_action": "Retry with altitude_m <= 120 or call set_guardian_limits"
  }
}
```

Codes enumerated in `avatar/mcp_server/errors.py`. Agents branch on `code`, not prose.

**6.8 Total tool count after Wave 2b**

- Existing 26 (all modernized in Wave 1)
- + 3 Wave 1 additions: `ping`, `cancel_operation`, `acrobatic_sequence` (orphan → registered)
- + 16 primitives (D5)
- + 6 orchestrators (D6)
- + 7 mission-intel (D8)
- **= 58 tools**

---

## 7. Mission intelligence layer

**7.1 Providers**

All behind `MappingProvider` / `ElevationProvider` protocols.

- **OSM (primary)** — Overpass for structured queries (buildings, POIs, power lines, ways), Nominatim for reverse geocoding fallback. Disk cache at `~/.cache/avatar/osm/<sha1>.json` with per-query-kind TTL (buildings 30 d, places 7 d, ways 30 d).
- **SRTM/Open-Elevation** — SRTM3 HGT tiles at `~/.cache/avatar/dem/`; persistent, never expire; downloaded lazily. Fallback to Open-Elevation HTTP when a tile is missing and network is available.
- **Google Maps (enrichment, keyed)** — Places, Static Maps, Street View Static, Roads, Geocoding. Cache at `~/.cache/avatar/gmaps/` with per-endpoint TTL. Daily budget guard (default 500 requests/day). Completely optional — if `GOOGLE_MAPS_API_KEY` absent, provider registers as unavailable and planners degrade gracefully.

**7.2 Area analysis**

`analyze_area(bbox, intent) → AreaReport`:
- Terrain: mean/median elevation, slope distribution, max-min AGL, ruggedness index.
- Built environment: building density, tallest structure height (OSM `building:height`), road/trail summary.
- POIs: ranked by intent (cinematic → viewpoints, water, prominent landmarks; survey → boundaries + access).
- Satellite snapshot: `ImageContent` if GMaps key; else None.
- Hazards: power-line ways, dense built-up polygons, water crossings.
- Recommended altitude band (AGL) given ruggedness + hazards.

**7.3 Scenic sweep planner**

`plan_scenic_sweep(bbox, style, duration_budget_s) → SweepPlan`:

1. `analyze_area` for POIs + terrain.
2. Rank candidate reveal anchors by visual prominence (isolation + elevation delta + POI density).
3. For each anchor, propose approach vector maximizing sun-back-lighting if `sun_time` provided.
4. Chain 3–6 anchors respecting duration budget + battery model.
5. Insert 2–3 cinematic primitives per anchor (`approach_reveal`, `orbit`, `pullback`, `crane_up`).
6. Validate clearances via `safety_checks` (min AGL, no-fly overlap, max distance from home, battery feasibility).
7. Return ordered `Mission` + per-leg cinematic template invocations.

**7.4 Intent planner**

`plan_mission_from_intent(intent, bbox, constraints) → Mission`:

Deterministic grammar-guided extractor (`intent.Parser`), not an LLM call. At least ten core patterns are required for W2b acceptance: `perimeter`, `orbit`, `lawnmower`, `reveal`, `establish`, `follow`, `inspect`, `transect`, `photo_grid`, `hover_at`. Each pattern is an enumerated class in `intent_planner.py` with its own parser + `Mission` emitter + unit tests. Out-of-grammar input returns `MissionSpecError` with suggested rephrasings. Additional patterns can be added later without changing the `Mission` schema.

**7.5 Mission spec**

```python
class Mission(BaseModel):
    version: Literal["1.0"]
    name: str
    home: Point
    constraints: MissionConstraints
    waypoints: list[Waypoint]
    cinematic_blocks: list[CinematicInvocation]
    safety: SafetyPolicy
```

Serializable to PX4 `.plan` format for `upload_mission`; renderable to human-readable summary for `preview_mission`.

---

## 8. Docker simulation platform

**8.1 Layout**

```
docker/
  sim-sih/
    Dockerfile
    entrypoint.sh
  sim-gazebo/
    Dockerfile
    entrypoint.sh
    xvfb-wrapper.sh
  shared/
    wait-for-px4.py
    wait-for-mcp.py
  compose.yaml
scripts/
  sim.sh
  run-scenario.sh
```

**8.2 `sim-sih` (fast tier)**

- Base `python:3.12-slim-bookworm`.
- PX4 pinned tag, built `make px4_sitl_default <sih_target>`.
- Avatar editable install.
- Target <700 MB, heartbeat <15 s.
- Every-PR CI.

**8.3 `sim-gazebo` (rich tier)**

- Base `ubuntu:24.04`.
- Gazebo Harmonic + gz-sim8.
- Xvfb + Mesa llvmpipe (`LIBGL_ALWAYS_SOFTWARE=1`).
- PX4 built `gz_x500`.
- Target 4–5 GB, first camera frame <45 s.
- `linux/amd64` only; Apple Silicon runs via Rosetta.
- Nightly CI.

**8.4 Compose profiles**

`sih`, `gazebo`, `sih-test`, `gazebo-test`. Healthchecks wired via `wait-for-*.py`.

**8.5 `scripts/sim.sh` interface**

```
sim.sh sih                             # spin up SIH tier
sim.sh gazebo                          # spin up Gazebo tier
sim.sh scenario <id>                   # run one YAML scenario with artifact collection
sim.sh down                            # tear everything down
sim.sh logs [service]
```

**8.6 CI matrix**

- `pr-fast.yml`: lint + mypy + bandit + unit + SIH smoke (three scenarios). Target <8 min.
- `nightly-rich.yml`: Gazebo + all 12 pipelines + e2e + property + performance. Artifacts uploaded.
- `release.yml`: matrix over {px4 tag × world} + container digest pin.

---

## 9. Hardware bring-up + HITL

**9.1 PX4 provisioning — `hardware/px4/`**

```
flash-px4.sh                # CLI flash via PX4 upload.py; no QGC required
airframes/
  mark4_7in.params
  x500_v2.params
  custom_template.params
calibrate.py                # headless walk: accel, gyro, mag, level, RC, motor dirs
verify.py                   # wraps PX4ParameterManager.verify_safety_parameters
preflight.py                # connect → verify → sanity → report; used by preflight_checklist tool
README.md
```

`.params` files are diffs over PX4 defaults, minimum set for offboard, failsafe, geofence, battery. `preflight.py` is what the `preflight_checklist` MCP tool shells out to.

**9.2 Pi provisioning — `hardware/pi/`**

```
build-image.sh              # bake Raspberry Pi OS Lite 64-bit + cloud-init
cloud-init/
  user-data
  network-config
flash.sh                    # one-liner: select SD, write, post-config
bootstrap/
  install-avatar.sh
  install-mavsdk.sh
  install-yolo-runtime.sh   # NCNN on Pi 4; OpenVINO on x86
systemd/
  avatar-mavlink-bridge.service   # mavsdk_server + mavlink-router; always enabled
  avatar-heartbeat.service        # DEC-003: safety cadence lives on Pi, always enabled
  avatar-mcp.service              # optional: runs MCP server on the Pi for autonomous field ops; disabled by default, Mac is canonical MCP host during first-flight era
  watchdog.service                # systemd-notify watchdog across all above
udev/99-pixhawk.rules       # stable /dev/pixhawk symlink
bring-up.sh                 # first-boot: test, connect to FC, verify, write /boot/avatar-status.txt
README.md
```

**9.3 HITL harness — `tests/hitl/`**

```
conftest.py                 # --run-hitl, device discovery, skip gates
fixtures/
  fc_bench.py               # SIH-on-FC (SYS_HITL=2), laptop↔FC over USB
  pi_plus_fc.py             # full stack: laptop MCP → Pi mavsdk_server → FC over UART
test_hitl_failsafes.py
test_hitl_scenarios.py      # runs the same YAML framework through HITL
test_hitl_preflight.py
```

`NetworkPartitionDriver` uses `tc netem` on the Pi. `OffboardFreezeDriver` and `RcLossDriver` work in HITL; `GpsLoss`, `Wind`, `ObstacleProximity` skip with clear reason.

**9.4 Runbook — `docs/runbooks/`**

- `preflight.md` — copy/paste from `preflight.py` output.
- `first-flight.md` — tethered hover → low altitude → first translation → RTL.
- `troubleshooting.md` — failure modes mapped to MCP error codes.
- `calibration.md` — when + how often.
- `field-kit.md` — what to pack.

**9.5 The "trivial flash" sequence (end state after Wave 4)**

1. `./hardware/px4/flash-px4.sh --airframe mark4_7in` — FC ready.
2. `./hardware/pi/flash.sh --wifi-config wifi.json --api-keys keys.env` — Pi ready.
3. Boot Pi → auto bring-up → `/boot/avatar-status.txt` = green.
4. `pytest tests/hitl -k preflight --run-hitl` on laptop — validates FC+Pi.
5. Tethered flight per `first-flight.md`.

---

## 10. Confirmation policy

`ConfirmationManager` prompts on this curated list only:

1. First `arm` or `arm_and_takeoff` in a new MCP session (one-time per session).
2. `upload_mission` when an active mission is already loaded (override).
3. `set_geofence_polygon` when it would remove or shrink an existing fence.
4. `disable_geofence` / equivalent param writes.
5. `abort_mission` when in autonomous mission execution (not when idle).
6. `force_disarm` while in-air.
7. Any `acrobatic_*` tool (flips, rolls, loops, corkscrew).
8. `set_parameter` for any param in `CRITICAL_PARAMETERS`.

Config lives in `avatar/mcp_server/confirmation_policy.py`, editable per deployment. Session capability `auto_confirm` disables even the curated list (used in Docker/CI).

---

## 11. Success gates per wave

| Wave | Gate | Verification |
|---|---|---|
| W0 | Lint/mypy/bandit clean; console script runs; unified test suite passes; validator script matches live tool count | `pytest -q -m "not slow and not hardware_in_loop" && avatar --version && python scripts/validate_mcp_server.py` |
| W1 | SIH Docker to heartbeat <15 s; guardian failsafe calls real `drone.action.*`; all tools annotated + outputSchema; ConfirmationManager gates at least one destructive tool in test | `scripts/sim.sh scenario smoke_failsafe_rtl && pytest tests/mcp_server/test_compliance.py` |
| W2a | 22 new tools (primitives + orchestrators) green; personal templates merged; acrobatic_sequence registered; existing 26 tools no regression | `pytest -q tests/tools tests/mcp_server` |
| W2b | `analyze_area` returns valid report offline; 3 representative scenarios green in Gazebo; hardware vision providers unit-tested on recorded frames | `scripts/sim.sh scenario analyze_area_offline && pytest tests/vision tests/mission_intel` |
| W3 | All 12 pipelines green in Gazebo; CI pipelines green on fresh clone; Pi image builds <10 min dry-run; PX4 params apply via `preflight.py --dry-run` | `scripts/sim.sh all-scenarios && hardware/pi/build-image.sh --dry-run && hardware/px4/preflight.py --dry-run --airframe mark4_7in` |
| W4 | HITL green on real FC (minimum SIH-on-FC mode); first-flight runbook reviewed; CHANGELOG + archive updated | `pytest tests/hitl -m preflight --run-hitl` |

---

## 12. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Gazebo perf in Docker on Apple Silicon slow; CI wall-clock bloat | SIH as PR gate; Gazebo nightly only |
| R2 | PX4 `sihsim_*` target name mismatch | W0 probes upstream and pins target in `avatar/sim/constants.py` |
| R3 | Google Maps quota surprise | Hard daily ceiling; provider absent without key; OSM path always works |
| R4 | YOLO on Pi 4 misses 10 FPS | NCNN int8 backend; fallback to laptop-side detection over RTSP; Pi 5+Hailo documented as upgrade |
| R5 | Offboard-streaming coexistence conflicts | Single "offboard owner" registry in W1; explicit error on conflict |
| R6 | Confirmation interrupts agent flow | Curated short-list policy; `auto_confirm` session capability for CI |
| R7 | Two test trees drift | W0 one-shot migration commit |
| R8 | Hardware doesn't arrive in time | W4 lands as code + docs; physical validation is a separate calendar event |
| R9 | Cinematic template scope creep | Bounded to existing 16 templates; no new authoring in this plan |
| R10 | Agent hallucinates outside intent grammar | Strict grammar + structured errors with rephrasing suggestions; never proxy free text to PX4 |

---

## 13. Out of scope (hard limits)

- No airspace / NOTAM / TFR integration.
- No weather forecast integration.
- No obstacle / powerline database beyond OSM tags.
- No ROS2 migration (DEC-004).
- No new aircraft class (fixed-wing, VTOL).
- No agent-authoring tooling inside the MCP server.
- No paid mapping tier beyond GMaps free-adjacent quota.

---

## 14. What `writing-plans` will generate from this spec

A dependency-ordered implementation plan with:
- One task per domain (D1–D16) and one sub-task per bullet within a domain.
- Explicit edges encoding §4's dependency graph so subagents can execute waves in parallel.
- Test criteria per task mapped to the verification commands in §11.
- Branch structure per domain so review happens at the checkpoint between waves.

The plan file lands at `docs/superpowers/plans/2026-04-16-project-avatar-first-flight-build.md`.

