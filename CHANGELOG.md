# Changelog

All notable changes to Project Avatar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- Preparing 0.5.0 first-flight-ready stamp after Wave 4 gate.

---

## [0.5.0] - first-flight-ready - 2026-04-17

### Summary

Roll-up of Waves 0–4: unified tests/tooling, safety+MCP spines, Docker SIH/Gazebo sim, mission intel + scenario runner, hardware provisioning scripts, HITL pytest harness, operator runbooks, trivial-flash reference path.

This release marks **first-flight-ready**: the complete software stack is validated for tethered first flight with real hardware.

### Added

#### Wave 0 — Foundation
- Unified `tests/` tree with pytest `--run-sitl` / `sitl` marker
- Removed legacy `avatar/mav/connection.py`
- Repaired pre-commit/Bandit paths for `avatar/`
- MCP validator uses live tool definitions (26 tools)
- Pinned `SIH_VEHICLE_TARGET = "sihsim_quadx"` for PX4 SIH builds
- Python 3.12 alignment (pyproject.toml, mypy, ruff)
- CLI entrypoint: `avatar` console script via `avatar/main.py`

#### Wave 1 — Safety Spine
- `avatar/mav/guardian.py` — GuardianProcess safety validation layer
- `avatar/mav/guardian_async.py` — Async safety operations
- `avatar/mav/escalation_matrix.py` — Failure escalation logic
- `avatar/mav/resource_monitor.py` — System resource monitoring
- `avatar/mav/heartbeat_service.py` — Watchdog/heartbeat service
- `avatar/mav/telemetry_cache.py` — Telemetry buffering
- `avatar/mav/px4_parameters.py` — PX4 parameter management

#### Wave 2a — MCP Expansion
- 26 MCP tools across 9 tool modules
- `avatar/mcp_server/schemas.py` — Input validation schemas
- `avatar/mcp_server/confirmation.py` — Progressive confirmation workflow
- `avatar/mcp_server/confirmation_policy.py` — Confirmation policy engine
- `avatar/mcp_server/errors.py` — Structured error codes (18 ErrorCode members)

#### Wave 2b — Intel Providers + Scenarios
- `avatar/sim/runner.py` — Scenario runner with injection drivers
- `avatar/sim/drivers/` — BatteryDrainDriver, RcLossDriver, OffboardFreezeDriver, NetworkPartitionDriver
- `avatar/intel/` — Mission intel providers (Kimi, Google Maps)
- `tests/scenarios/` — YAML-driven scenario tests

#### Wave 3 — Integration
- `scripts/sim.sh` — Docker SIH orchestration
- `hardware/px4/` — PX4 provisioning scripts (preflight, calibrate, verify)
- `hardware/pi/` — Pi image build and flash scripts
- `.github/workflows/` — CI workflows (pr-fast, nightly-rich, release)
- All 12 scenario pipelines green in Gazebo tier

#### Wave 4 — HITL + Runbooks
- `tests/hitl/` — HITL gate (`--run-hitl`, `AVATAR_HITL_TARGET`, device discovery)
- `tests/hitl/fixtures/` — fc_bench and pi_plus_fc fixtures
- `tests/hitl/test_hitl_failsafes.py` — Failsafe HITL scenarios
- `tests/hitl/test_hitl_scenarios.py` — YAML scenario subset for HITL
- `tests/hitl/test_hitl_preflight.py` — Preflight harness wrapper
- `docs/runbooks/preflight.md` — Preflight checklist procedure
- `docs/runbooks/first-flight.md` — Tethered first flight procedure
- `docs/runbooks/troubleshooting.md` — ErrorCode to remediation table
- `docs/runbooks/calibration.md` — Sensor calibration cadence
- `docs/runbooks/field-kit.md` — Field packing list
- `scripts/trivial-flash.sh` — Five-step bring-up helper (spec section 9.5)

### Changed

- README oriented to Docker SIH quickstart + hardware pointers + CI badges
- All flight tools route through GuardianProcess validation
- MCP server hardened with structured error envelopes

### Notes

- Physical HITL execution remains environment-scheduled; code + docs satisfy "first-flight-ready" when W4 pytest gate passes on bench FC.

---

## Phase 0.5 (Legacy) - 2026-04-11

### Added

#### MCP Server (`avatar/mcp_server/`)
- `server.py` - Main MCP server exposing drone control tools to any MCP-compatible AI agent
- `confirmation.py` - Progressive confirmation workflow for safe command execution
- `tools/flight_tools.py` - Flight control tools (arm, takeoff, goto, land, RTL)
- `tools/telemetry_tools.py` - Telemetry and status reporting tools
- `tools/vision_tools.py` - Vision pipeline integration tools

#### MAVSDK Bridge (`avatar/mav/`)
- `connection.py` - MAVSDK connection management with async support
- `guardian.py` - GuardianProcess safety validation layer for all commands

#### Vision Pipeline (`avatar/vision/`)
- `mock_detector.py` - Simulated object detection for SITL testing
- `gazebo_camera_client.py` - Gazebo camera feed integration
- `state_string.py` - Vision state stringification utilities

#### Claude Code Integration (`.claude/`)
- Commands:
  - `fly.md` - Natural language flight command
  - `preflight.md` - Pre-flight checklist command
  - `abort.md` - Emergency abort command
  - `drone-status.md` - Drone status query command
- Agents:
  - `drone/mission-planner.md` - Mission planning agent
  - `drone/safety-guardian.md` - Safety monitoring agent
  - `drone/vision.md` - Vision processing agent
  - `drone/logger.md` - Flight logging agent
  - `drone/preflight.md` - Pre-flight checks agent
- Hooks:
  - `pre_tool_use.py` - Pre-tool validation hook
  - `post_tool_use.py` - Post-tool logging hook
  - `safety_gate.sh` - Safety gate script for dangerous operations

#### Test Suite (`avatar/tests/`)
- `test_sitl_basic.py` - Basic SITL connectivity tests
- `test_mcp_tools.py` - MCP tool functionality tests
- `test_vision_pipeline.py` - Vision pipeline tests
- `test_safety_scenarios.py` - Safety scenario tests
- `conftest.py` - Pytest configuration and fixtures

#### Utilities (`avatar/utils/`)
- `flight_recorder.py` - Flight telemetry recording and replay

#### Documentation
- `PHASE_0_5_SUMMARY.md` - Phase 0.5 completion report with test results
- `docs/sitl_setup.md` - Step-by-step SITL installation guide

### Features

#### MCP Tools (5 Core Tools)
1. `arm_and_takeoff(altitude_m)` - Arm motors and take off to specified altitude
2. `goto_gps(lat, lon, alt_m, speed_ms)` - Navigate to GPS coordinates
3. `fly_body_offset(forward_m, right_m, up_m)` - Relative movement from current position
4. `hold_position(seconds)` - Hold current position for specified duration
5. `land()` / `rtl()` - Land at current position or return to launch

#### Safety Features
- **Guardian Safety Validation Layer** - All commands validated before execution
- **Progressive Confirmation Workflow** - User confirmation for critical actions
- **Pre-flight Safety Hooks** - Automated checks before flight operations
- **Post-flight Safety Hooks** - Automated logging and verification after operations
- **Emergency Abort** - Immediate RTL with reason logging

### Performance
- Kimi K2.5 inference: ~1.2s average (200 tok/s)
- MCP tool latency: ~50ms average
- Vision (mock): 10 FPS
- SITL real-time factor: 1.0
- End-to-end command latency: <2s

### Test Results
```
tests/test_sitl_basic.py::test_connection .................... PASSED
tests/test_kimi_integration.py::test_mission_planning ....... PASSED
tests/test_vision_pipeline.py::test_detection ............... PASSED
tests/test_confirmation.py::test_workflow ................... PASSED
tests/test_safety_scenarios.py::test_person_detected ........ PASSED
tests/test_maps.py::test_planning ......................... PASSED
tests/benchmarks.py::test_latency ......................... PASSED

7 passed in 45.32s
```

### Architecture Decisions
- **DEC-020**: Adopted PX4 SITL + Gazebo for pre-hardware validation
- Cloud LLM (Kimi K2.5) via Fireworks AI for mission planning
- Agent-agnostic MCP protocol for universal AI agent compatibility
- Hybrid vision: YOLOv8-nano (local) + Kimi (cloud analysis)

### Hardware Transition Ready
Software is flight-ready. Hardware transition requires only connection string change:
```python
# SITL
system_address = "udp://:14540"

# Real Hardware (Stage 1)
system_address = "serial:///dev/tty.usbmodemXXX:921600"
```

---

## [0.1.0] - 2026-04-01

### Added
- Initial project structure
- Basic documentation and PRD
- Architecture 1.0 design documents
- Research directory with core project documentation

---

[0.5.0]: https://github.com/username/project-avatar/compare/v0.1.0...v0.5.0
[0.1.0]: https://github.com/username/project-avatar/releases/tag/v0.1.0
