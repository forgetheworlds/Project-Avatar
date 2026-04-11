# Project Avatar Research Knowledge Base - Master Index

**Last Updated:** 2026-04-09  
**Purpose:** Central entry point for all Project Avatar research documentation  
**Status:** Living document - update as research evolves

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [Research Document Index](#research-document-index) | Complete table of all research reports |
| [Cross-Reference Matrix](#cross-reference-matrix) | Quick lookup by topic/technology |
| [Reading Order Guide](#recommended-reading-order) | Where to start, what to read next |
| [Key Takeaways Summary](#key-takeaways-summary) | Critical findings at a glance |
| [Implementation Roadmap](#implementation-roadmap) | What to build first |
| [Gaps Analysis](#gaps-analysis) | What's missing, open questions |

---

## Research Document Index

### Tier 1: Essential Core Documents (Read These First)

| # | Document | Lines | Stage | MAVSDK | Safety | Summary |
|---|----------|-------|-------|--------|--------|---------|
| 1 | [MAVSDK-Python & PX4 Deep Dive](./mavsdk_px4_deep_dive.md) | 657 | All | Core | Partial | Complete technical reference for MAVSDK-Python implementation. Covers connection management, offboard mode requirements (20Hz setpoint streaming), telemetry patterns, EKF health monitoring, and production-ready code patterns. |
| 2 | [Architecture Critique](./architecture_critique.md) | 737 | All | Yes | Core | Systems analysis identifying critical hidden assumptions, failure modes, and design gaps. Challenges Wi-Fi reliability assumptions, LLM latency, and proposes heartbeat-on-RPi architecture. **MUST READ before implementation.** |
| 3 | [RC Failsafe & Emergency Procedures](./rc_failsafe_emergency.md) | 538 | All | Yes | Core | Complete PX4 failsafe parameter reference. Documents COM_OBL_RC_ACT, battery failsafes, geofence actions, RC override procedures, kill switch implementation, and emergency hierarchy. |
| 4 | [Performance Optimization Analysis](./performance_optimization.md) | 750 | All | Yes | Partial | MacBook Pro M3 16GB performance budgets. YOLOv8-nano FPS targets, LLM quantization levels, memory allocation (16GB breakdown), latency budgets, and thermal management. |

### Tier 2: Project Foundation Documents (Located in parent directory)

| Document | Purpose | Relationship to Research |
|----------|---------|-------------------------|
| [Project PRD](../project_avatar_prd.md) | Product Requirements Document | Defines Stage 1/2/3 scope that research supports |
| [Technical Guide](../project_avatar_technical.md) | Implementation reference | References research findings for MAVSDK, YOLO, hardware |
| [Roadmap](../project_avatar_roadmap.md) | Schedule & milestones | Research informs week-by-week technical tasks |

### Tier 3: Stub/Placeholder Documents (Awaiting Content)

The following documents were created as placeholders but currently contain only minimal/error content. They represent planned research areas:

| Document | Planned Content | Priority |
|----------|-----------------|----------|
| [bec_power.md](./bec_power.md) | BEC (Battery Eliminator Circuit) power distribution for companion computers | Low |
| [cold_weather.md](./cold_weather.md) | Cold weather operation impacts on battery, GPS, IMU | Low |
| [current_sensing.md](./current_sensing.md) | Battery current monitoring for mission-time estimation | Medium |
| [drone_testing_research_raw.md](./drone_testing_research_raw.md) | Raw notes from drone testing research | Low |
| [failsafe.md](./failsafe.md) | Failsafe procedures (superseded by rc_failsafe_emergency.md) | N/A |
| [lipo_safety.md](./lipo_safety.md) | LiPo battery safety, charging, storage | Medium |
| [px4_battery_params.md](./px4_battery_params.md) | PX4 battery estimation parameters | Medium |
| [pytest_drone_patterns.md](./pytest_drone_patterns.md) | Testing patterns for drone software | Medium |

---

## Cross-Reference Matrix

### By Technology/Topic

#### MAVSDK-Python & Offboard Control
- [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Core implementation patterns
- [architecture_critique.md](./architecture_critique.md) - Network reliability challenges, heartbeat architecture
- [rc_failsafe_emergency.md](./rc_failsafe_emergency.md) - Offboard loss failsafe parameters
- [performance_optimization.md](./performance_optimization.md) - Asyncio task prioritization, latency budgets

#### Safety & Failsafes
- [rc_failsafe_emergency.md](./rc_failsafe_emergency.md) - Complete failsafe parameter reference
- [architecture_critique.md](./architecture_critique.md) - Safety monitor architecture, geofencing gaps
- [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Offboard exit detection, EKF health
- [performance_optimization.md](./performance_optimization.md) - Memory guard for safety-critical operations

#### Performance & Optimization
- [performance_optimization.md](./performance_optimization.md) - M3 16GB budgets, YOLO FPS, LLM quantization
- [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Memory-efficient telemetry patterns
- [architecture_critique.md](./architecture_critique.md) - Latency budget analysis

#### Vision Pipeline (YOLO/Tracking)
- [performance_optimization.md](./performance_optimization.md) - YOLOv8-nano configuration, MPS backend
- [architecture_critique.md](./architecture_critique.md) - Vision latency assumptions critique

#### Hardware/Power
- Placeholders: bec_power.md, lipo_safety.md, current_sensing.md, cold_weather.md

### By Project Stage

#### Stage 1 - Control Spine (No Vision)
**Priority Documents:**
1. [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Section 9: Code patterns for safe offboard
2. [rc_failsafe_emergency.md](./rc_failsafe_emergency.md) - Sections 1-2: Failsafe params, RC override
3. [architecture_critique.md](./architecture_critique.md) - Sections 1-2: Network assumptions, SPOFs
4. [performance_optimization.md](./performance_optimization.md) - Section 3.3: MAVSDK latency

**Key Implementation Tasks:**
- MAVSDK bridge (PX4 ↔ RPi ↔ Mac)
- Offboard heartbeat (20Hz setpoint streaming)
- JSON tool schema (arm_and_takeoff, goto_gps, etc.)
- EKF preflight checks
- RC override integration

#### Stage 2 - Vision for Mission Logic
**Priority Documents:**
1. [performance_optimization.md](./performance_optimization.md) - Section 3.1: YOLO optimization
2. [architecture_critique.md](./architecture_critique.md) - Section 1.3: Vision latency critique
3. [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Section 3: Telemetry for State String

**Key Implementation Tasks:**
- YOLOv8-nano + ByteTrack on M3 MPS
- State String generator (telemetry + detections)
- Vision-guided mission logic (frame-centric, NOT distance-based)
- 2D tracking for mission decisions

#### Stage 3 - Depth & Payload
**Priority Documents:**
1. [architecture_critique.md](./architecture_critique.md) - Section 3.2: Emergency tool paradigm
2. [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) - Section 6: Action & Mission APIs

**Key Implementation Tasks:**
- Intel RealSense D435i integration
- Depth-augmented State String
- Distance-aware tools (with hard reflex fallback)
- ESP32 payload control (bench-tested only)

---

## Recommended Reading Order

### For New Team Members (Start Here)

**Day 1 - Understanding the Project:**
1. Read [Project PRD](../project_avatar_prd.md) - Executive summary and Stage definitions
2. Read [Roadmap](../project_avatar_roadmap.md) - Week-by-week plan
3. Read [Technical Guide](../project_avatar_technical.md) - Stack overview

**Day 2-3 - Safety First:**
4. Read [Architecture Critique](./architecture_critique.md) - This is CRITICAL; do not fly without understanding
5. Read [RC Failsafe & Emergency Procedures](./rc_failsafe_emergency.md) - Know your emergency parameters

**Day 4-5 - Implementation Details:**
6. Read [MAVSDK-Python Deep Dive](./mavsdk_px4_deep_dive.md) - Code patterns you'll use daily
7. Read [Performance Optimization](./performance_optimization.md) - Know your hardware limits

### For Implementation Specifics

**Implementing Stage 1 (Control Spine):**
1. [mavsdk_px4_deep_dive.md](./mavsdk_px4_deep_dive.md) Sections 2, 3, 9
2. [rc_failsafe_emergency.md](./rc_failsafe_emergency.md) Sections 1, 2, 4
3. [architecture_critique.md](./architecture_critique.md) Sections 1.1, 1.4, 4.1

**Implementing Vision Pipeline:**
1. [performance_optimization.md](./performance_optimization.md) Sections 3.1, 6.1
2. [architecture_critique.md](./architecture_critique.md) Sections 1.3, 2.3

**Designing Safety Systems:**
1. [architecture_critique.md](./architecture_critique.md) Sections 3.2, 4.3, 5
2. [rc_failsafe_emergency.md](./rc_failsafe_emergency.md) Sections 3, 6

---

## Key Takeaways Summary

### Critical Safety Findings

| Finding | Source | Impact |
|---------|--------|--------|
| **Heartbeat must move to RPi** | architecture_critique.md | If Mac Wi-Fi drops, drone falls. RPi heartbeat continues. |
| **Separate Safety Monitor required** | architecture_critique.md | LLM cannot be trusted for emergency decisions. Need deterministic monitor. |
| **COM_OBL_RC_ACT = 4 (Land) recommended** | rc_failsafe_emergency.md | Default is safe; Position mode requires GPS that may be denied |
| **Geofence MUST be software-enforced** | architecture_critique.md | LLM hallucinated coordinates can fly drone to "null island" |
| **Battery model needed** | architecture_critique.md | No automatic RTL at 30% = potential crash |

### Technical Constraints

| Constraint | Value | Source |
|------------|-------|--------|
| PX4 Offboard minimum heartbeat | 2 Hz | mavsdk_px4_deep_dive.md |
| MAVSDK auto-rate | 20 Hz | mavsdk_px4_deep_dive.md |
| PX4 timeout (COM_OF_LOSS_T) | 0.5s | mavsdk_px4_deep_dive.md |
| YOLOv8-nano target FPS | 15-30 FPS @ 416x416 | performance_optimization.md |
| LLM response time | 1.5-2.5s typical | performance_optimization.md |
| End-to-end command latency | ~2s | architecture_critique.md |
| Memory budget (LLM) | 7 GB Q5_K_M | performance_optimization.md |
| M3 thermal throttle threshold | 85-95°C | performance_optimization.md |

### Hidden Failure Modes (Read architecture_critique.md Section 5)

1. **Wi-Fi Ghost** - Intermittent Wi-Fi causes phantom heartbeats; PX4 confused about mode
2. **Hallucinated Landing Pad** - LLM "sees" flat area that doesn't exist
3. **Infinite Orbit** - LLM reasoning loop drains battery
4. **Thermal Throttle Cascade** - RPi throttling → YOLO slowdown → stale vision → crash
5. **GPS-Dependent Failsafe Trap** - COM_OBL_RC_ACT=0 with GPS denied = undefined behavior

### Recommended PX4 Parameters (Quick Reference)

```bash
# From rc_failsafe_emergency.md Section 4.1
COM_OF_LOSS_T=0.5      # Offboard loss timeout
COM_OBL_RC_ACT=4       # Land on offboard loss
COM_RC_OVERRIDE=3      # Enable stick override
COM_RCL_EXCEPT=4       # Ignore RC loss in Offboard
COM_LOW_BAT_ACT=2      # Return at critical, land at emergency
GF_ACTION=3            # Return on geofence breach
```

---

## Implementation Roadmap

### Phase 0: Foundation (Pre-Flight)

**Prerequisites:**
- [ ] Read and understand Architecture Critique
- [ ] Configure PX4 failsafe parameters per rc_failsafe_emergency.md
- [ ] Implement Safety Monitor (deterministic, NOT LLM-controlled)

**Decision Gate:** Safety architecture review before any flight

### Phase 1: Control Spine (Stage 1)

**Sequence:**
1. **MAVSDK Bridge** (Week 1)
   - PX4 ↔ RPi MAVLink over USB/UART
   - RPi → Mac over Wi-Fi UDP
   - Test: Connection, basic telemetry

2. **Offboard Heartbeat on RPi** (Week 2) ⚠️ CRITICAL
   - 20Hz setpoint streaming
   - Shared target structure (Mac updates target, RPi streams)
   - Test: 10-minute continuous stream, no dropouts

3. **Tool Schema & Validation** (Week 3)
   - JSON schemas for: arm_and_takeoff, goto_gps, fly_body_offset, hold, land, rtl
   - Parameter bounds checking (geofence, altitude limits)
   - Test: Invalid commands rejected, valid commands execute

4. **LLM Integration** (Week 4)
   - Ollama + Llama 3 8B Q4_K_M
   - Tool calling with validation
   - Test: Natural language → JSON → flight

**Decision Gate:** Successful GPS mission via natural language with RC override test

### Phase 2: Vision System (Stage 2)

**Sequence:**
1. **Video Streaming** (Week 6)
   - RPi camera → MJPEG over HTTP
   - 416x416 @ 15 FPS target
   - Test: <200ms latency

2. **YOLO + Tracking** (Week 7-8)
   - YOLOv8-nano on MPS backend
   - ByteTrack for ID persistence
   - Test: 10+ FPS sustained

3. **State String Generator** (Week 9)
   - Telemetry + vision fusion every 1-2s
   - Format: detections, positions, battery, EKF status
   - Test: LLM can describe scene accurately

4. **Vision-Guided Missions** (Week 10-11)
   - GPS search patterns
   - Target lock + yaw control
   - Test: "Find person, orbit them" mission

**Decision Gate:** Closed-loop vision mission with real detections altering behavior

### Phase 3: Depth & Payload (Stage 3)

**Sequence:**
1. **Depth Hardware** (Week 12-13, BENCH ONLY)
   - Intel RealSense D435i integration
   - Depth + RGB alignment
   - Test: Distance accuracy on bench

2. **Distance-Aware Tools** (Week 14-15)
   - maintain_offset(target_id, distance_m)
   - evaluate_path_safety(distance_m)
   - Test: Bench validation only

3. **Payload Bench Work** (Week 16-17)
   - ESP32 servo control
   - Kinematics calculations
   - Test: Static payload operation

**Decision Gate:** Bench-validated depth + payload system (no flight yet)

---

## Gaps Analysis

### What Was NOT Covered

| Gap | Impact | Recommended Action |
|-----|--------|-------------------|
| **PX4 Tuning Guide** | High | Document PID tuning for specific airframe |
| **Sensor Calibration Procedures** | High | Step-by-step compass, gyro, accel calibration |
| **Vibration Analysis** | Medium | Document acceptable vibration levels, isolation |
| **GPS Quality Analysis** | Medium | HDOP, satellite count thresholds |
| **Wi-Fi Interference Patterns** | High | Characterize 2.4GHz Wi-Fi near spinning props |
| **Battery Field Testing** | Medium | Actual discharge curves for flight time estimation |
| **Legal/Regulatory Compliance** | High | FAA Part 107 (US), local regulations |
| **Weather Limits** | Medium | Wind, rain, temperature operational bounds |
| **RC Transmitter Setup** | Medium | Mode switch configuration, failsafe binding |
| **Simulation Testing (SITL)** | High | Gazebo/JMAVSim validation before flight |

### Open Questions

1. **Network Protocol:** UDP vs TCP for MAVLink commands?
   - UDP: Lower latency, no delivery guarantee
   - TCP: Reliable delivery, higher latency, head-of-line blocking
   - Recommendation: UDP for telemetry, consider TCP for critical commands

2. **LLM Quantization Trade-off:**
   - Q4_K_M (faster, lower quality) vs Q5_K_M (slower, higher quality)
   - Need empirical testing with actual drone commands

3. **Vision Pipeline Location:**
   - Current plan: YOLO on Mac
   - Alternative: YOLO on RPi with Coral TPU?
   - Trade-off: Network bandwidth vs compute distribution

4. **Safety Monitor Implementation:**
   - Should it run as separate process or thread?
   - Real-time priority requirements?
   - How to share telemetry (shared memory vs sockets)?

### Future Research Needs

| Priority | Topic | Use Case |
|----------|-------|----------|
| High | Simulation validation with SITL | Pre-flight testing without hardware risk |
| High | Wi-Fi latency characterization | Understand actual flight conditions |
| Medium | PX4 parameter tuning guide | Specific airframe optimization |
| Medium | Vibration isolation strategies | Clean IMU data for EKF |
| Low | ROS2 migration path | Future architecture evolution |
| Low | Cloud LLM fallback | Emergency or non-critical use cases |

---

## Document Maintenance

### How to Update This Index

1. Add new documents to the [Research Document Index](#research-document-index)
2. Update the [Cross-Reference Matrix](#cross-reference-matrix)
3. Add new takeaways to [Key Takeaways Summary](#key-takeaways-summary)
4. Update [Implementation Roadmap](#implementation-roadmap) as phases complete
5. Move completed gaps to resolved section in [Gaps Analysis](#gaps-analysis)

### Version History

| Date | Changes |
|------|---------|
| 2026-04-09 | Initial index creation - 4 core research documents indexed |

---

## Emergency Contacts & References

### External Documentation
- [PX4 Autopilot Docs](https://docs.px4.io/)
- [MAVSDK-Python Docs](https://github.com/mavlink/MAVSDK-Python)
- [MAVLink Message Reference](https://mavlink.io/en/messages/common.html)
- [Ultralytics YOLOv8](https://docs.ultralytics.com/)
- [Ollama LLM Platform](https://ollama.com/)

### Critical Safety Parameters (From rc_failsafe_emergency.md)
- `COM_OF_LOSS_T` - Offboard timeout (default 0.5s)
- `COM_OBL_RC_ACT` - Offboard loss action (default 4 = Land)
- `COM_RC_OVERRIDE` - Stick override enable (recommend 3)
- `NAV_DLL_ACT` - Data link loss action
- `GF_ACTION` - Geofence breach action

---

**This document is the entry point for all Project Avatar research. Start here before diving into specific documents.**
