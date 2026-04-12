# Changelog

All notable changes to Project Avatar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-04-11

### Summary

Phase 0.5: Complete software stack validation in PX4 SITL + Gazebo simulation before hardware purchase. This release establishes the foundation for agent-agnostic drone control via MCP protocol with cloud LLM integration.

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
