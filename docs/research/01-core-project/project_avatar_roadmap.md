# Project Avatar Roadmap – April to September 2026

This roadmap assumes development starts immediately in April 2026 and runs through the end of September 2026.
The plan is organized into phases aligned with the PRD: **Stage 1 (Control Spine)**, **Stage 2 (Eyes)**, and early **Stage 3 (Hands, bench-only)**, with explicit milestones, deliverables, risks, and decision points.

Time references are approximate weeks; adjust calendar dates as needed.

---

## 1. Overview by Stage

- **Phase 0.5 – Virtual Drone (Pre-Hardware, 3 weeks) ✅ COMPLETE (April 12, 2026)**  
  - **Goal**: Complete software stack validation using PX4 SITL + Gazebo simulation.  
  - Build agent-agnostic MCP server with all flight tools.  
  - Integrate Kimi K2.5 for natural language mission planning.  
  - Implement progressive confirmation workflow with mock vision.  
  - Test Google Maps integration for pre-flight planning.  
  - Produce demo video with screen recording.  
  - **Completed**: Added comprehensive code comments to 87 files across the codebase for maintainability.  
  - **Completed**: Cinematic camera shots (orbit, flyby, tracking) implemented and tested in SITL.  
  - **Deliverable**: Working software system proven in simulation, ready for hardware swap.

- **Stage 0 – Preparation (Late March – Early April)**  
  - Lock architectural decisions (Kimi, MCP, hardware).  
  - Assemble development environment.  
  - Source hardware within budget (while Phase 0.5 runs in parallel).

- **Stage 1 – Control Spine (April–May)**  
  - Acquire/assemble hardware within budget.  
  - Configure PX4 on the chosen airframe.  
  - Connect validated software from Phase 0.5 to real hardware.  
  - Demonstrate safe GPS-based missions via natural language.

- **Stage 2 – Vision for Mission Logic (June–July)**  
  - Add RGB camera and video streaming.  
  - Integrate YOLOv8-nano + tracking on Mac.  
  - Implement State String pipeline and target-centric behaviors.  
  - Demonstrate real vision changing mission behavior.

- **Stage 3 (Early) – Depth & Payload Bench Work (August–September)**  
  - Acquire depth camera and ESP32 for bench experiments.  
  - Prototype depth-augmented State String and distance-aware tools.  
  - Develop payload abstraction and kinematics code on the bench.

---

## 2. Phase 0.5 – Virtual Drone ✅ COMPLETE (April 12, 2026)

**Status**: All objectives achieved. Software stack validated in PX4 SITL + Gazebo simulation. Ready for hardware swap.

**Goal**: Build and validate complete software stack using PX4 SITL + Gazebo simulation before hardware arrives. All components tested, demo video produced.

**Why Phase 0.5?**:
- Validate Kimi LLM integration without hardware risk
- Refine MCP server and agent workflows with rapid iteration
- Test confirmation workflows and safety systems
- Produce demo video proving concept before budget spent
- Software is "flight-ready" before hardware assembly

### Week -3: Foundation & Gazebo SITL

**Day 1-2**: PX4 SITL Setup
- Install PX4 Autopilot and build SITL: `make px4_sitl gz_x500`
- Verify MAVSDK connection to simulated drone
- Test basic commands: arm, takeoff, land

**Day 3-4**: Project Structure
- Create avatar repository with package structure
- Set up Python environment with dependencies
- Initialize Git repository

**Day 5**: First Simulated Flight
- End-to-end test: Python script → MAVSDK → SITL → Gazebo
- Validate basic flight commands work

**Deliverable**: SITL running locally, basic flight commands working via Python.

### Week -2: MCP Server & Kimi Integration

**Day 1-3**: Agent-Agnostic MCP Server
- Implement `mcp_server/server.py` with all flight tools
- Test with Claude Code: `arm_and_takeoff`, `goto_gps`, `land`, etc.
- Validate agent-agnostic design (works with any MCP client)

**Day 4-5**: Agent Testing
- Test MCP server with Claude Code
- Verify tool visibility and execution
- Test telemetry streaming

**Day 6-7**: Kimi K2.5 Integration
- Implement `llm/kimi_client.py` for Fireworks AI
- Multimodal support (vision + tool calling)
- Mission planning: natural language → tool calls

**Day 8-10**: End-to-End Integration
- Test: Natural language → Kimi → MCP tools → SITL
- Validate full pipeline: "Take off to 10m" executes in Gazebo
- Progressive confirmation workflow

**Deliverable**: Complete integration: User → Agent → Kimi → MCP → SITL working end-to-end.

### Week -1: Vision, Maps & Advanced Testing

**Day 1-3**: Vision Simulation
- Gazebo camera integration (simulated camera feed)
- Mock YOLO detector for Phase 0.5 testing
- Vision → exception → confirmation flow testing

**Day 4-5**: Google Maps Integration
- Pre-flight mission planning with real map data
- Area analysis, geofence suggestions
- Test with real locations (High Park, etc.)

**Day 6-7**: Safety & Exception Testing
- Test scenarios: person detected, low battery, geofence
- Exception handling and confirmation flows
- Safety system validation

**Day 8-10**: Recording & Screen Demo
- Flight recording system implementation
- Screen recording setup (Gazebo + Agent side-by-side)
- Produce demo video (4-5 minutes)

**Deliverable**: Demo video showing full workflow: natural language → Kimi planning → mission execution → exception handling → landing.

### Week 0: Transition Preparation ✅ COMPLETE

**Hardware Swap Readiness**:
- Configuration files for SITL vs hardware ✅
- Connection scripts (SITL UDP → Hardware Serial) ✅
- First hardware test procedures ✅
- Documentation updates ✅
- Comprehensive code documentation (87 files) ✅
- Cinematic camera shots (orbit, flyby, tracking) ✅

**Deliverable**: Software stack ready for hardware swap. Same code, different connection string.

---

## 2.5 Current Status & Next Priorities (April 2026)

### ✅ Phase 0.5 Achievements
- Agent-agnostic MCP server fully operational
- Kimi K2.5 integration with multimodal support complete
- Progressive confirmation workflow validated
- Mock vision pipeline tested
- Google Maps integration for pre-flight planning working
- Safety systems and exception handling validated
- **Code quality**: Comprehensive comments added to 87 files
- **Cinematic capabilities**: Orbit, flyby, and tracking camera shots implemented

### 🎯 Next Phase Priorities (Stage 1 – Control Spine)
1. **Hardware sourcing**: Acquire Holybro X500 + Pixhawk 6C within $500 budget
2. **Manual flight validation**: Achieve stable GPS Position mode hold
3. **Hardware connection**: Transition from SITL UDP to serial/USB connection
4. **First autonomous flight**: Execute natural language commanded GPS mission
5. **Safety validation**: Offboard heartbeat, geofences, kill switch configuration

---

## 3. Stage 0 – Preparation (Late March – Early April)

**Goal**: Lock key architectural decisions and assemble the minimal development environment.

**Note**: Runs in parallel with Phase 0.5. While software is being validated in simulation, source hardware from marketplace.

### 2.1 Decisions to Lock

- **Ground Station**: MacBook Pro M3 with 16 GB RAM as the primary compute for vision and orchestration.[web:212]  
- **LLM Stack**: Kimi K2.5 via Fireworks AI (cloud, 200 tok/s, native multimodal, reliable tool calling). Local inference moved to cloud to enable frontier capabilities on current hardware.[web:212]
- **Interface**: OpenCode chat with custom Drone MCP Skill for natural language control via Sisyphus orchestration.
- **Flight Stack**: PX4 on a Pixhawk-class controller (e.g., Pixhawk 6C or similar used FC) to ensure Offboard support and compatibility with MAVSDK.[web:196][web:45]
- **Programming Languages**:  
  - Python 3.10+ for MAVSDK client, vision pipeline, Kimi client, and orchestration.[web:200]  
  - C++ only within PX4/firmware and library internals.
- **Connectivity**: Phone cellular data for Kimi API; telemetry radio/WiFi for MAVLink (independent paths).
- **Budget Strategy**:  
  - Target ≤ USD 500 in new purchases for drone hardware by aggressively using second-hand markets (Facebook Marketplace, local FPV groups, etc.).[web:195][web:203][web:207]  
  - Treat MacBook, potential existing RC radio, chargers, and some batteries as sunk cost.

### 2.2 Shopping & Hardware Plan (Budget-Aware)

Approximate new prices (for reference):

- **Holybro X500 V2 ARF kit**: around USD 300–350 new (frame, motors, ESCs, PDB, props).[web:195][web:203]
- **Pixhawk 6C**: ~USD 160–180 new, often less from third-party retailers or used markets.[web:196][web:204]
- **Raspberry Pi 4 4 GB**: historical used prices around USD 40–60.[web:197]  
- **Basic RGB camera (Pi cam or USB)**: USD 20–40.  
- **RC radio + receiver**: if needed, used radios (e.g., Radiomaster-series) can be found around USD 100 depending on condition.[web:207]

Given the USD 500 ceiling, the recommended approach is:

- Prioritize **used airframe + used Pixhawk-class FC**; aim for ~50–60% of new price via local deals.  
- Consider smaller FPV frames (sub-250 g) only if they can carry a Pi and camera safely; many sub-250 frames are tight but some long-range 3–3.5 inch builds can support minimal payloads.[web:199][web:207]  
- Treat **RealSense D435i** as a Stage 3 purchase that may exceed the initial budget; used D435i units frequently sell for less than new but can still be USD 120–200.[web:198][web:206]

**Deliverable**: A simple cost spreadsheet with new and used price ranges and a concrete shopping checklist (frame, FC, Pi, camera, RC link, batteries), tuned to keep Stage 1–2 under USD 500.

---

## 3. Stage 1 – Control Spine (April–May)

**Goal**: Fly a GPS-based mission commanded via natural language, with a robust offboard heartbeat and safety wrappers.

### Week 1–2: Hardware Bring-Up & Manual Flight

- Assemble or refurbish the chosen airframe (if used, verify mechanical integrity, bearings, and wiring).  
- Install PX4 on the flight controller (via QGroundControl); perform sensor calibration (accelerometer, magnetometer, radio, ESCs).[web:184][web:190]
- Configure:
  - Flight modes, including Offboard as a mode selectable via RC or QGroundControl.[web:130]  
  - Geofences and altitude limits.  
  - RTL parameters.
- Achieve:
  - Stable manual hover.  
  - GPS Position mode hold.  
  - Clean logs for basic test flights.

**Deliverable**: Video and logs of manual GPS hold and simple flights, with notes on any vibration or tuning issues.

### Week 3: MAVLink Bridge and Telemetry

- Connect PX4 ↔ RPi via USB or UART.  
- Configure RPi to expose MAVLink over Wi-Fi UDP to the Mac (e.g., `udp://0.0.0.0:14540`).[web:200][web:130]
- On the Mac:
  - Install MAVSDK-Python and run example scripts such as `takeoff_and_land.py` to confirm remote offboard control in a safe environment (bench / no props first, then tethered or very low altitude).[web:200][web:208]

**Deliverable**: A minimal Python script that can arm, take off to a fixed altitude, hover, and land using MAVSDK, executed from the Mac via the RPi bridge.

### Week 4: Offboard Heartbeat & Tool Schema

- Implement a dedicated **offboard heartbeat thread** (either on the Mac or on the RPi) that:
  - Streams position/velocity setpoints at ≥ 2 Hz (ideally 10–20 Hz) whenever Offboard is active, per PX4 documentation.[web:45][web:33]  
  - Holds the last safe target state when high-level logic is thinking or blocked.
- Define and implement the initial JSON tool schema:
  - `arm_and_takeoff(altitude_m)`  
  - `goto_gps(lat, lon, alt_m)`  
  - `fly_body_offset(forward_m, right_m, up_m)`  
  - `hold(seconds)`  
  - `land()`  
  - `rtl()`
- Add a simple validation layer to reject out-of-bounds or insane commands (e.g., altitudes above a safe limit, coordinates far outside the test field).

**Deliverable**: A command-line tool that takes a JSON sequence of tools and executes them safely via the heartbeat.

### Week 5: LLM Integration with Kimi K2.5

- Set up Fireworks AI account and Kimi K2.5 API access.  
- Implement `kimi_client.py` wrapper for Fireworks API:
  - HTTP client with 2s timeout handling
  - Multimodal support (can send camera frames as base64)
  - Tool schema definition for flight commands
  - Conversation history management (128K context window)
- Implement OpenCode Drone MCP Skill:
  - Tool definitions: `arm_and_takeoff()`, `goto_gps()`, `land()`, `rtl()`, `capture_frame()`, etc.
  - Progressive confirmation workflow integration
  - GuardianProcess validation hooks
- Test end-to-end: OpenCode chat → Kimi → tool execution → drone response
- Early safety policy:
  - Kimi instructed to propose conservative commands (altitude caps, limited distances)
  - Sisyphus validates all parameters via GuardianProcess
  - 10-second confirmation window for all initial missions

**Cost Validation**: Confirm ~$0.10 per flight budget (~200 API calls × 500 tokens avg × $0.80/1M tokens)

**Deliverable**: Live demo via OpenCode chat:  
User: "Take off to 10 meters, fly 20 meters north, then land."  
Sisyphus: "Kimi suggests mission plan [shows preview]. Confirm?"  
User: "yes"  
→ Drone executes with telemetry streamed back to chat

---

## 4. Stage 2 – Vision for Mission Logic (June–July)

**Goal**: Real camera and YOLO detections inform mission behavior; the drone adjusts behavior based on what it sees.

### Week 6: Camera Hardware & Streaming

- Mount a Pi Camera or light USB camera on the drone with appropriate vibration isolation.  
- On the RPi, implement a lightweight streaming server:  
  - Option A: MJPEG over HTTP (good for robustness to jitter).  
  - Option B: Low-latency RTSP.  
- On the Mac, implement a `video_client.py` that pulls frames and exposes them to the vision pipeline.

**Deliverable**: Live video feed from the drone camera visible on the Mac while the drone is powered (initially static tests).

### Week 7–8: YOLOv8-nano + Tracking on Mac

- Integrate Ultralytics YOLOv8-nano for object detection on the incoming frames.[web:202][web:211]  
- Configure for MPS or CPU as appropriate to achieve ≥ 10 FPS at modest resolution, as demonstrated by community experiments on Apple silicon.[web:211][web:218]
- Integrate a tracker such as ByteTrack to maintain object IDs across frames; validate ID consistency in simple videos or live tests.[web:214]
- Expose a Python API that returns, at each frame:
  - List of detections: `(class, confidence, bbox_pixels, id)`.

**Deliverable**: Local test (without the drone flying yet) where YOLO + tracker run on sample video and produce a stable list of tracked objects.

### Week 9: State String, Hybrid Vision, and Kimi Context

- Design the **State String** format that fuses:
  - Telemetry: mode, altitude, speed, battery, GPS status.  
  - Vision: counts per class, tracked IDs, coarse positions (e.g., `ID_7 at left-middle of frame`).
- Implement hybrid vision pipeline:
  - YOLOv8-nano runs locally at 10 FPS (fast detection)
  - Selective frame capture for Kimi: every 3-5s + on-demand triggers
  - Frame buffer management (avoid memory bloat)
- Implement `capture_frame()` MCP tool for on-demand vision analysis
- Extend Kimi system prompt for multimodal vision:
  - "You receive camera frames every 3-5 seconds"
  - "Use State String for continuous context + frames for visual confirmation"
  - "Recommend mission adjustments based on what you see"
- Test Kimi vision analysis: send test frames, verify understanding

**Deliverable**: OpenCode chat interaction:
User: "What do you see?"  
Sisyphus sends frame to Kimi → Kimi: "I see 2 people near a tree on the left side of frame"  
State String: "2 persons detected (IDs: 3,7), positions: left, center"

### Week 10–11: Vision-Guided Mission Logic with Progressive Confirmation

- Implement mission templates with Kimi planning + user confirmation:
  - "Park Circuit + People Observation": GPS circuit with vision counting
  - "Moving Target Perimeter": target-centric orbit with yaw control
  - "Search and Confirm": wide search pattern → Kimi identifies target → user confirms approach
- Implement progressive confirmation workflow:
  - **Pre-flight**: Kimi generates plan → shows map preview + estimated path → user confirms
  - **Pre-arm**: Live camera view + telemetry check → "Scene looks clear. Execute?"
  - **Exception handling**: Kimi sees people → Sisyphus asks "People detected 10m away. Stop or continue?"
- Implement exception response handling:
  - User: "stop" → hold position, await further instruction
  - User: "continue" → resume with wider safety buffer
  - Timeout (10s) → default to hold position (fail-safe)
- Implement new tools:
  - `start_gps_search_pattern()` with confirmation checkpoint
  - `lock_target(id)` (logical lock, not distance-based)
  - `center_target_in_frame(id)` for yaw control
  - `abort_mission(reason)` for immediate RTL
- Ensure **Stage 2 restriction**: no distance-based stopping without depth sensors

**Deliverable**: OpenCode chat field test:
User: "Orbit this park at 20m, count people"  
Sisyphus: "Kimi suggests 35m radius orbit at 25m altitude. Preview: [map]. Confirm?"  
User: "yes"  
→ Drone executes, streams: "3 people counted at 15m, 8m, 12m distances"  
→ Kimi: "Recommend widening orbit to 40m for safety margin"  
→ Sisyphus: "Widen orbit to 40m?"  
User: "yes"

---

## 5. Stage 3 (Early) – Depth & Payload Bench Work (August–September)

**Goal**: Stand up the depth and payload subsystems on the bench, integrate distance-aware logic into the State String, and prototype kinematics and payload tools.

### Week 12–13: Depth Hardware Acquisition & Bench Bring-Up

- Hunt for a used Intel RealSense D435i within budget; new units cost more, but used or refurbished units sometimes appear at lower prices.[web:198][web:206]  
- On the bench (no drone), integrate the D435i with either the Mac or the RPi using the RealSense SDK and confirm:  
  - Depth stream at usable frame rates.  
  - Alignment of depth and RGB frames.  
- Implement minimal depth processing: for a chosen bounding box, estimate mean depth in meters.

**Deliverable**: Bench demo where an object placed at various distances yields a consistent `distance_m` in logs.

### Week 14–15: Depth-Augmented State String & Distance Tools

- Extend the State String to include, for each tracked object where depth is valid:  
  - `distance_m`.  
  - Simple relative bearing (ahead, left, right, above, below) computed from camera geometry.[web:198][web:213]
- Define new tools that require distance and remain disabled unless depth is active:  
  - `evaluate_path_safety(distance_m)` (can trigger high-level `stop_movement()`).  
  - `maintain_offset(target_id, distance_m)` for tracking at a safe separation (initially only in simulation or bench logic).

**Deliverable**: Simulated or bench-only tests where the LLM receives depth-enhanced State Strings and decides, for example, to "stop" when an object is closer than a threshold.

### Week 16–17: Payload Abstraction & Kinematics (Bench Only)

- Acquire an ESP32 and simple actuators (e.g., servos) for a bench payload rail.  
- Implement `esp32_interface.py` to expose safe abstracted commands: `set_servo_angle(channel, angle_deg)`, `trigger_payload(duration_ms)`.  
- Implement `kinematics.py` with helper functions for simple ballistic or pointing calculations (for non-human, inanimate targets).  
- Integrate with the LLM as tools, enforcing constraints (angle limits, rate limits) in the Python layer rather than in the LLM.

**Deliverable**: Bench test where the LLM, given a target distance and simple scenario, calls kinematic tools and actuates a servo to a computed angle.

---

## 6. Risk Register & Mitigations

### 6.1 Budget Risk

- **Risk**: Holybro X500 + Pixhawk + Pi + camera + RC + batteries may exceed USD 500 if purchased new.  
- **Mitigation**:  
  - Aggressively pursue used deals for frame and FC.  
  - Reuse any existing RC radio and batteries.  
  - Defer RealSense and payload to Stage 3, potentially beyond the initial budget window.

### 6.2 Compute & Performance Risk

- **Risk**: YOLOv8 on M3 with MPS may not hit desired FPS at high resolutions.[web:211][web:218]  
- **Mitigation**:  
  - Use YOLOv8-nano and reduced input size (e.g., 416 px).  
  - Limit detection classes.  
  - Use CPU or mixed CPU/MPS if MPS is suboptimal.

### 6.3 Offboard Stability Risk

- **Risk**: Offboard control is sensitive to heartbeat dropouts and network jitter.[web:45][web:33]  
- **Mitigation**:  
  - Prefer locating heartbeat thread on the RPi directly attached to PX4.  
  - Use robust Wi-Fi configuration and avoid saturating links with video.

### 6.4 Vision Reliability Risk

- **Risk**: Person detection and tracking in real parks can be noisy (occlusions, lighting).  
- **Mitigation**:  
  - Treat counts as approximate.  
  - Use simple heuristics and thresholds for mission decisions.  
  - Log all detections for offline analysis.

---

## 7. End-of-September Target State

By the end of September 2026, the target is to have:

- A **fully functional Stage 1 & 2** system:  
  - Natural-language-driven GPS missions with robust offboard control.  
  - Real vision influencing mission decisions and target-centric orientation.  
- A **bench-tested Stage 3** subsystem:  
  - Depth camera integrated and providing distance metrics.  
  - Distance-aware tools defined and tested in non-flight contexts.  
  - Payload and kinematics modules working reliably on the bench.

This represents a realistic, safety-aware, and budget-constrained path from an LLM-driven control spine to a genuinely embodied, vision-guided drone avatar.

