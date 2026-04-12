# Phase 0.5 SITL Implementation - Task Index

**Generated**: 2026-04-11
**Total Tasks**: 47
**Waves**: 6

## Task Status Legend
- [ ] Not Started
- [~] In Progress
- [X] Completed
- [!] Blocked

---

## Wave 1: Foundation (12 tasks)

### Track A: Environment Setup
- [X] A-001: Clone PX4-Autopilot repository
- [X] A-002: Checkout PX4 v1.15.0 stable release
- [X] A-003: Run macOS setup script
- [X] A-004: Build PX4 SITL with Gazebo (gz_x500)

### Track B: Project Structure
- [X] B-001: Create avatar/ directory structure
- [X] B-002: Initialize Python virtual environment
- [X] B-003: Install core dependencies (mavsdk, opencv, etc.)
- [X] B-004: Initialize Git repository

### Track P: Claude Code Configuration
- [X] P-001: Create .claude/ directory structure
- [X] P-002: Create project CLAUDE.md with drone-specific instructions
- [X] P-003: Create settings.json with drone permissions
- [ ] P-004: Create .mcp.json for drone MCP server registration

---

## Wave 2: Basic Validation (12 tasks)

### Track A: Environment (continued)
- [X] A-005: Start SITL and verify Gazebo visualization
- [X] A-006: Test MAVSDK connection to SITL (udp://:14540)

### Track C: Flight Testing
- [ ] C-001: Create tests/test_sitl_basic.py
- [ ] C-002: Run basic arm/takeoff/land test in SITL

### Track D: MCP Server
- [X] D-001: Create mcp_server/ directory and files
- [X] D-002: Implement DroneMCPServer class skeleton (T18 - Server Wiring)

### Track S: Drone Subagents
- [ ] S-001: Create subagents/ directory structure
- [ ] S-002: Create Mission Planner subagent config
- [ ] S-003: Create Safety Guardian subagent config
- [ ] S-004: Create Vision subagent config
- [ ] S-005: Create Logger subagent config
- [ ] S-006: Create Preflight subagent config

---

## Wave 3: Integration (17 tasks)

### Track D: MCP Server (continued)
- [ ] D-003: Implement arm_and_takeoff tool
- [ ] D-004: Implement goto_gps tool
- [ ] D-005: Implement get_telemetry tool
- [ ] D-006: Implement land tool
- [ ] D-007: Implement abort_mission/RTL tool

### Track E: Agent Testing
- [ ] E-001: Test MCP server with Claude Code connection
- [ ] E-002: Verify all tools appear in Claude Code

### Track G: Vision Pipeline
- [X] G-001: Create vision/ directory structure
- [ ] G-002: Create gazebo_camera_client.py
- [ ] G-003: Create mock_detector.py for synthetic detections
- [ ] G-004: Test vision pipeline with mock data

### Track Q: Claude Code Skills
- [ ] Q-001: Create /fly skill definition
- [ ] Q-002: Create /preflight skill definition
- [ ] Q-003: Create /mission skill definition
- [ ] Q-004: Create /abort skill definition
- [ ] Q-005: Create /drone-status skill definition

---

## Wave 4: Advanced Features (18 tasks)

### Track H: Google Maps Integration
- [ ] H-001: Create planning/ directory structure
- [ ] H-002: Create maps_integration.py with Google Maps API
- [ ] H-003: Test maps planning with real location queries

### Track I: Safety & Confirmation
- [ ] I-001: Create mcp_server/confirmation.py
- [ ] I-002: Implement progressive confirmation workflow
- [ ] I-003: Create tests/test_safety_scenarios.py
- [ ] I-004: Test person detection -> confirmation flow
- [ ] I-005: Test low battery -> RTL flow

### Track R: Claude Code Safety Hooks
- [ ] R-001: Create PreToolUse hook for dangerous commands
- [ ] R-002: Create PostToolUse hook for telemetry validation
- [ ] R-003: Create PreCompact hook for mission state preservation
- [ ] R-004: Create Notification hook for mission events
- [ ] R-005: Create Safety Gate hook (geofence, altitude, battery)
- [ ] R-006: Create Confirmation Timeout hook
- [ ] R-007: Create Vision Exception hook
- [ ] R-008: Create Abort Cascade hook

---

## Wave 5: Recording & Testing (14 tasks)

### Track J: Recording & Logging
- [ ] J-001: Create utils/ directory structure
- [ ] J-002: Create flight_recorder.py
- [ ] J-003: Create scripts/start_demo_recording.sh
- [ ] J-004: Test mission logging and replay

### Track L: Testing & Benchmarks
- [ ] L-001: Create tests/test_kimi_integration.py
- [ ] L-002: Create tests/test_vision_pipeline.py
- [ ] L-003: Create tests/test_confirmation.py
- [ ] L-004: Create tests/benchmarks.py for latency validation
- [ ] L-005: Run full test suite (pytest)
- [ ] L-006: Verify end-to-end latency < 2 seconds

### Track K: Demo Production
- [ ] K-001: Write demo scenario script
- [ ] K-002: Create screen recording setup
- [ ] K-003: Record demo video (4-5 minutes)
- [ ] K-004: Export and upload demo to video platform

---

## Wave 6: Documentation & Transition (10 tasks)

### Track M: Documentation
- [ ] M-001: Update README.md with Phase 0.5 section
- [ ] M-002: Create PHASE_0_5_SUMMARY.md
- [ ] M-003: Add DEC-020 to DECISIONS.md
- [ ] M-004: Create SITL setup guide in docs/
- [ ] M-005: Update architecture diagram

### Track N: Hardware Transition
- [ ] N-001: Create config/sitl.yaml
- [ ] N-002: Create config/hardware.yaml
- [ ] N-003: Create scripts/swap_to_hardware.sh
- [ ] N-004: Create hardware transition checklist
- [ ] N-005: Verify all checklist items complete

---

## Progress Summary

| Wave | Total | Completed | In Progress | Blocked | Not Started |
|------|-------|-----------|-------------|---------|-------------|
| 1 | 12 | 11 | 0 | 0 | 1 |
| 2 | 12 | 4 | 0 | 0 | 8 |
| 3 | 17 | 1 | 0 | 0 | 16 |
| 4 | 18 | 0 | 0 | 0 | 18 |
| 5 | 14 | 0 | 0 | 0 | 14 |
| 6 | 10 | 0 | 0 | 0 | 10 |
| **Total** | **47** | **17** | **0** | **0** | **30** |

---

## Corrections Applied

### Removed
- **Track F (Kimi Client)**: Claude Code already uses Kimi K2.5 as its backend. No separate Kimi client needed.

### Added
- **Track P**: Claude Code Configuration
- **Track Q**: Claude Code Skills
- **Track R**: Claude Code Safety Hooks
- **Track S**: Drone Subagents

---

*Task tracking initialized by Wave Coordinator Agent*

---

## Task Files

- **Wave Schedule**: `/tmp/wave-schedule-1775938851.md`
- **Wave 1 Tasks**: `wave-1-tasks.md`
- **Wave 2 Tasks**: `wave-2-tasks.md`
- **Wave 3 Tasks**: `wave-3-tasks.md`
- **Wave 4 Tasks**: `wave-4-tasks.md`
- **Wave 5 Tasks**: `wave-5-tasks.md`
- **Wave 6 Tasks**: `wave-6-tasks.md`

---

## Quick Start

To begin Wave 1 execution, dispatch parallel subagents for:
- A-001 (PX4 clone)
- B-001 (Avatar directory structure)
- P-001 (Claude config directory)

These three tasks have NO dependencies and can start immediately.
