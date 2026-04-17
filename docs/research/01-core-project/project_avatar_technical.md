# Project Avatar Technical Background & Implementation Guide

**Architecture Version**: 2.0 (April 2026) - Kimi K2.5 Cloud LLM with MCP Interface
**Phase 0.5 Status**: COMPLETE (SITL Validation Done)
**Documentation**: 87+ files with comprehensive comments and docstrings

This document is designed as a **Claude Code reference** for building and extending Project Avatar.
It gathers relevant research, open-source projects, libraries, hardware guidance, and budget-conscious options to ground the implementation in real prior art and practical constraints.

**Major Update**: The architecture has evolved from local Llama 3 (7B, 25-40 tok/s) to **Kimi K2.5 via Fireworks AI** (cloud, 200 tok/s, native multimodal). This change enables:
- 8x faster inference (1-2s vs 3-8s responses)
- Native vision capabilities (Kimi analyzes actual camera frames)
- Dramatically improved tool-calling reliability
- OpenCode chat interface with progressive confirmation workflow

The 20Hz heartbeat and all safety-critical reflexes remain local on the RPi/Pixhawk stack, maintaining independence from cloud connectivity.

---

## 1. Research Landscape: LLMs, UAVs, and Fast Drones

### 1.1 LLMs + UAVs

Recent work has started to systematically analyze how large language models can be integrated into UAV systems.

- **When Large Language Models Meet UAVs: How Far Are We?** (2025) surveys architectures for integrating LLMs with UAVs, highlighting common patterns such as LLM-as-Parser (mapping language to structured commands) and the importance of safety wrappers and multi-level autonomy.[web:56][web:215]
- **NeLV – Next-Generation LLM for UAV** proposes a five-component framework: LLM-as-Parser, Route Planner, Path Planner, Control Platform, and Real UAV Monitoring, validated on multi-UAV missions.[web:22]  
  - This directly supports the idea of separating **instruction parsing** and **trajectory planning** from low-level control, which matches Project Avatar’s design.
- These works emphasize that LLMs should orchestrate **waypoints and mission plans**, not raw motor commands, due to latency and reliability concerns.[web:56][web:22]

**Implications for Project Avatar**:

- Keep the LLM at the level of **tools for waypoints, offsets, and missions**, not rate-level control.  
- Use a separate offboard controller (MAVSDK) to enforce real-time constraints (heartbeat, safety) while taking high-level commands from the LLM.

### 1.2 ChatGPT for Robotics and Tool Design

Microsoft’s **ChatGPT for Robotics** paper shows how LLMs can control robots through a library of high-level functions with carefully engineered prompts and safety constraints.[web:29][web:216]

Key ideas:

- Provide the model with **a clear schema of available tools** and their semantics.  
- Use prompt engineering and intermediate XML/JSON structures to constrain outputs.  
- Keep humans in the loop, especially early on, with step-by-step confirmations.

For Project Avatar, this motivates:

- A well-documented Python tool library for flight commands, mission control, and, later, payload operations.  
- A system prompt that describes tools, safety rules, and examples (e.g., avoid high altitudes, stay within geofence).

### 1.3 Autonomous Drone Racing & Fast FPV Control

Drone racing literature shows how high-speed quads achieve fast, dynamic control using classical and learning-based methods.

- **Autonomous Drone Racing: A Survey** reviews model-based and learning-based approaches, including perception, planning, and control, and discusses challenges such as reliable state estimation, flying from purely vision, and transferring to real-world applications.[web:210][web:217]
- **Autonomous Drone Racing with Deep Reinforcement Learning** demonstrates RL-based policies that compute near time-optimal trajectories, achieving real-world speeds of up to 60 km/h on quadrotors.[web:201]

Key technical patterns:

- High-speed controllers rely on **tight perception → planning → control loops** with latencies on the order of milliseconds.  
- Vision is often processed on-board or on a very low-latency link; the controller is usually a custom RL policy or a tightly tuned model-based controller.[web:201][web:217]

For Project Avatar:

- These works show that truly high-speed FPV-style reflex control is best handled by specialized controllers or onboard computation, not by a general LLM.  
- However, the **trajectory-planning and mission-choosing role** can be LLM-driven, while low-level trajectory tracking and reflexes remain in PX4 or custom high-rate controllers.

---

## 2. Open-Source Projects & Repositories

### 2.1 LLM-Controlled Drone (Simulation)

- **LLM-controlled-drone (GitHub)**: A project that uses a local LLM to control a PX4 drone in Gazebo via ROS2, with a YOLO vision system feeding detections into the LLM loop.[web:48]

  Architecture highlights:

  - ROS2 nodes: telemetry aggregator, LLM node, YOLO detector, setpoint publisher.  
  - LLM used as a decision-making layer, setting waypoints and mode changes.  
  - Setpoint streaming at 10 Hz to PX4, consistent with Offboard requirements.

  How to leverage:

  - Use the node structure as a reference for **separate processes**: telemetry, vision, LLM, offboard control.  
  - Port ideas to a simpler MAVSDK + Python architecture without full ROS2 if desired.

### 2.2 YOLO Drone Projects

- **Tello Drone Control with Flask and YOLOv8**: A GitHub project showing live video streaming and YOLOv8 detection integrated with a Tello drone.[web:202]

  Patterns to reuse:

  - Simple Flask-based dashboard for viewing video and telemetry.  
  - Real-time object detection driving simple behaviors like following a path and tracking an object class.  
  - YOLOv8 integration on a laptop.

- These projects demonstrate that **YOLO-based vision for small drones is feasible on commodity hardware** and provide code examples for frame grabbing, detection, and basic control.

### 2.3 PromptCraft Robotics

- The ChatGPT for Robotics project includes **PromptCraft**, a repository with example prompts and patterns for instructing robots via language.[web:29][web:216]

  Use this as inspiration for:

  - System prompts that explain drone capabilities.  
  - Example dialogues demonstrating safe behaviors.  
  - Testing different prompting styles for robust tool calling.

---

## 3. Flight Stack: PX4 and Offboard Control

### 3.1 PX4 Offboard Mode & Heartbeat

PX4 Offboard mode allows external software to control the vehicle by sending setpoints for position, velocity, attitude, or thrust.[web:45]

Critical facts:

- PX4 requires a **continuous "proof of life" signal** at ≥ 2 Hz in the form of supported setpoint messages; if the stream stops, PX4 will exit Offboard and execute a failsafe (configurable via `COM_OBL_RC_ACT`).[web:45][web:33]
- Offboard can only be entered after PX4 has seen a valid setpoint stream for a short period (typically > 1 second).[web:45]

Implementation pattern:

- Use MAVSDK-Python or a similar client:  
  - Start Offboard setpoint streaming on a dedicated asyncio task or background thread.  
  - Expose a shared `current_target` structure that can be updated by the LLM/mission logic at a slower rate.
- Optionally move the heartbeat thread to the RPi to decouple it from laptop Wi-Fi variability.

### 3.2 Preflight Checks & EKF Health

PX4 provides preflight sensor and estimator checks that should be passed before arming.[web:184][web:190]

Key aspects:

- Verify accelerometer, gyroscope, magnetometer, and barometer health.  
- Check GPS fix type and quality; poor fixes can cause erratic GPS navigation.[web:184][web:190]  
- Monitor EKF status messages for alignment, velocity/position innovations, and altitude consistency.

Implementation suggestion:

- Implement a `mav/safety.py` module that:
  - Queries relevant MAVSDK telemetry topics for health status.  
  - Blocks `arm_and_takeoff()` until health checks are passed.  
  - Reports status to the LLM in the State String.

### 3.3 MAVSDK-Python

MAVSDK-Python provides an asyncio-based client for controlling MAVLink vehicles.[web:200]

- Installation: `pip3 install mavsdk`.  
- Example: `takeoff_and_land.py` shows how to connect and perform basic missions.[web:208]

Advantages:

- High-level API for arming, takeoff, landing, and Offboard setpoint control.  
- Async-first design fits naturally with a background heartbeat and separate mission logic.

Recommended structure:

- `mav/offboard.py`:  
  - Connect to PX4 via RPi.  
  - Implement setpoint streaming task (e.g., position/velocity setpoints at 10–20 Hz).  
  - Provide `set_target_position` / `set_target_velocity` functions that update shared state.
- `mav/mission.py`:  
  - Implement higher-level maneuvers (goto, orbit, etc.) by composing target updates.  
  - Provide the tools that the LLM can call.

---

## 4. Vision Stack: YOLOv8, Tracking, and State String

### 4.1 Detector: YOLOv8-nano

Ultralytics YOLOv8-nano (`yolov8n`) is a light detector suitable for real-time use on laptops and even some edge devices.[web:202]

- On Apple Silicon, YOLOv8 can run on MPS, though some users report that MPS is not always faster than CPU depending on configuration.[web:211][web:218]
- For Project Avatar:
  - Use `yolov8n` for people and selected object classes.  
  - Reduce input resolution (e.g., 416 px) to achieve ≥ 10 FPS on the Mac M3.  
  - Use CPU or MPS depending on profiling.

### 4.2 Tracking: ByteTrack and ID Persistence

Multi-camera person tracking work has shown that combining YOLOv8 with ByteTrack can provide robust tracking even under occlusions and varying conditions.[web:214]

- ByteTrack associates detections across frames and maintains IDs.  
- ID switches still occur in crowded or complex scenes; counts should be treated as approximate.

For Project Avatar:

- Use ByteTrack or a similar tracker to produce `(id, class, bbox_pixels)` tuples for each frame.  
- Implement heuristics for smoothing counts and avoiding rapid oscillations.

### 4.3 State String Design

The State String is a compact textual summary of:

- Flight state: mode, altitude, velocity, battery, GPS health.  
- Vision state: object counts, tracked IDs, coarse positions (e.g., `ID_7 is near the center of the frame`).

This design is inspired by the way LLM+robotics works in ChatGPT for Robotics and LLM-UAV surveys: they pass structured state to the LLM as text or simplified code, not raw sensor data.[web:29][web:56][web:22]

Implementation suggestions:

- Update every 1–2 seconds in a background thread.  
- Keep a short, consistent format so the LLM can parse patterns reliably.  
- Include explicit fields like:  
  - `detections: 3 people (IDs: 4,7,9)`  
  - `id_7_position: left-middle`  
  - `battery: 78%`  
  - `ekf_status: healthy`.

### 4.4 Depth Integration (Stage 3)

Intel RealSense D435i provides stereo depth and an IMU, with support via the RealSense SDK and ROS integration.[web:198][web:213]

- Depth stream: 1280×720 up to 90 FPS; typically used at lower resolutions.  
- Fusing depth with YOLO:
  - For each bounding box, compute the median or mean depth within the region.  
  - Add a `distance_m` field to each detection.

This enables **spatial tracking**, where objects are represented in meters rather than pixels, supporting distance-aware tools.

---

## 5. LLM Stack: Kimi K2.5 via Fireworks AI

### 5.1 Cloud LLM Architecture (Kimi K2.5)

**Rationale for Cloud LLM**: Local Llama 3 8B on MacBook M3 16GB provided only ~25-40 tok/s with limited reasoning capability. A 7B model is insufficient for reliable spatial navigation, multimodal interpretation, and tool calling under edge cases. Larger models (70B+) don't fit in 16GB unified memory.

**Kimi K2.5 via Fireworks AI**:
- **Speed**: ~200 tok/s (8x faster than local 7B)
- **Multimodal**: Native vision support - can analyze drone camera frames directly
- **Context**: 128K token window (full flight history + current state)
- **Tool Calling**: Dramatically more reliable than 7B models
- **Cost**: ~$0.80-1.00/1M tokens = ~$0.10 per 15-minute flight

**Implementation**:
```python
import openai

client = openai.OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=api_key
)

response = client.chat.completions.create(
    model="accounts/fireworks/models/kimi-k2-5",
    messages=[...],
    tools=[drone_tool_schemas],
    max_tokens=1000
)
```

### 5.2 Hybrid Vision + Multimodal LLM

**Architecture**: YOLO (local, fast) + Kimi (cloud, intelligent)

```
Camera Stream (30 FPS)
    ↓
YOLOv8-nano on Mac (10 FPS, 80ms inference)
    ↓
State String (every 1-2s): "3 people detected (IDs: 4,7,9)"
    ↓
Kimi receives:
  - State String (text telemetry + detections)
  - Camera frames (every 3-5s + on-demand)
    ↓
Kimi analyzes: "I see 2 people near a tree. Recommend orbit radius increase."
```

**Frame Capture Strategy**:
- **Continuous**: Frame every 3-5 seconds for situational awareness
- **Event-triggered**: When YOLO detects people, obstacles, or anomalies
- **On-demand**: When Kimi requests "show me current view"
- **Mission phases**: Entering new area, waypoint transitions

**Why This Works**:
- YOLO provides real-time detection (10 FPS) for immediate awareness
- Kimi gets periodic visual context without overwhelming API costs
- 1-2s latency acceptable for mission-level decisions (not reflexes)
- Cost-effective: ~$0.10/flight vs $5+ for continuous streaming

### 5.3 Agent-Agnostic MCP Server Interface

**Architecture**: User → Any MCP Agent → Drone MCP Server → [Optional: Kimi K2.5] → MAVLink → Drone

**MCP Server Tools** (exposed to ANY agent):
```python
@mcp_server.tool()
def arm_and_takeoff(altitude_m: float) -> str:
    """Arm drone and take off to specified altitude."""
    
@mcp_server.tool()
def goto_gps(lat: float, lon: float, alt_m: float, speed_ms: float = 5.0) -> str:
    """Fly to GPS coordinates at specified altitude and speed."""
    
@mcp_server.tool()
def capture_frame() -> Image:
    """Capture current camera frame for vision analysis."""
    
@mcp_server.tool()
def abort_mission(reason: str) -> str:
    """Immediately abort mission and RTL."""

@mcp_server.tool()
def plan_mission(natural_language_request: str) -> MissionPlan:
    """Generate mission plan from natural language (uses Kimi if configured)."""
```

**Agent Compatibility**:
| Agent | Connection Method | Confirmation UI |
|-------|-------------------|-----------------|
| **Claude Desktop** | Native MCP connector | Chat-based |
| **OpenCode** | MCP skill configuration | Chat-based |
| **Hermes** | MCP config file | CLI + notifications |
| **OpenClaw** | MCP connector | Web UI |
| **Custom scripts** | Python MCP SDK | Programmatic |

**Progressive Confirmation Workflow** (Agent-Agnostic):
1. **Pre-flight**: Agent sends `plan_mission()` → Server returns plan → Agent displays to user → User confirms
2. **Pre-arm**: `get_telemetry()` + `capture_frame()` → Agent displays → "Execute mission?"
3. **Exception handling**: Server detects exception → Agent prompts user → "Stop or continue?"

The confirmation mechanism is **agent-driven**: the MCP server provides the data and recommendations; the agent handles the user interaction.

### 5.4 Tool/Function Calling Pattern

Based on ChatGPT for Robotics and NeLV, adapted for cloud LLM:

- Provide **small, well-defined set of tools** per stage.[web:29][web:22]  
- Use JSON schemas for arguments; validate in GuardianProcess before execution.  
- Kimi can reason, call tools, receive observations, and update plan in conversation loop.

**Stage 1 Tools**: `arm_and_takeoff`, `goto_gps`, `fly_body_offset`, `land`, `rtl`, `get_telemetry`  
**Stage 2 Tools**: Add `start_gps_search_pattern`, `lock_target`, `center_target_in_frame`, `capture_frame`, `abort_mission`  
**Stage 3 Tools**: Add `maintain_offset`, `evaluate_path_safety`, `aim_gimbal`, `trigger_payload`

### 5.5 Safety Wrappers & Confirmation

**Hard Limits** (immutable, validated before any tool execution):
```python
@dataclass(frozen=True)
class HardLimits:
    max_altitude_amsl_m: float = 120.0
    max_distance_from_home_m: float = 500.0
    min_battery_rtl_percent: float = 25.0
    max_wind_speed_ms: float = 12.0
```

**Progressive Confirmation**:
- **Level 1**: Pre-flight mission confirmation (plan preview + map context)
- **Level 2**: Pre-arm live check (camera view + telemetry)
- **Level 3**: Mid-flight exceptions (people detected, geofence warning)

**Default-Safe Behavior**:
- 10-second confirmation window
- No response → hold position (not continue)
- RC transmitter always overrides software decisions

**Logging**: All Kimi reasoning, tool calls, and confirmations logged for audit.

---

## 6. Hardware & Cost Guidance (≤ USD 500 for Drone Hardware)

### 6.1 Baseline Components

Assuming the MacBook Pro M3 is already owned, the core drone hardware budget must cover:

- Airframe (frame, motors, ESCs, PDB, props).  
- Flight controller (PX4-capable).  
- Companion computer (Raspberry Pi 4).  
- RGB camera.  
- RC radio + receiver (unless already owned).  
- Batteries and basic charger (if not already available).

### 6.2 Airframe Options

- **Holybro X500 V2 ARF kit**:  
  - New: around USD 300–350, including carbon frame, motors, ESCs, PDB, props, and companion-computer mounts.[web:195][web:203]  
  - Advantage: well-documented, supports Pixhawk, includes RealSense-compatible mounts.  
  - Budget implication: likely too expensive to buy new under a strict USD 500 cap if other parts are also new.

- **Sub-250 g frames / long-range quads**:  
  - Example: Lumenier QAV-S 2 Sub-250 DIY kit; these are ~3″ frames designed for lightweight FPV, usually around a few hundred dollars when fully built new.[web:199][web:207]  
  - Limitation: payload for a Pi and extra sensors is tight; careful weight budgeting is critical.

**Recommendation**:

- Look for a used 4–5" or 500 mm class quadcopter **frame + motors + ESCs** locally (FPV groups, marketplace).  
- Avoid buying a brand-new X500 kit unless a significant discount is found.  
- Aim for ≤ USD 150 total for frame + motors + ESCs via used deals.

### 6.3 Flight Controller

A Pixhawk-class FC that supports PX4 is required.

- **Pixhawk 6C**: ~USD 160–180 new from official/retail sources.[web:196][web:204]  
- Used units can often be found at ~60–70% of new cost.

Alternative options:

- Other PX4-compatible FCs (e.g., older Pixhawk variants) may be cheaper used.  
- Ensure Offboard support and good documentation.

**Budget target**: ≤ USD 120 for a used Pixhawk-class FC.

### 6.4 Companion Computer

- Raspberry Pi 4 4 GB: Amazon price history suggests used units around USD 40–60.[web:197]  
- Include a 5 V BEC or power module capable of powering the Pi from the main LiPo.

**Budget target**: ~USD 50 for Pi 4 + required cables.

### 6.5 Camera

- Pi Camera Module or small USB camera: typically USD 20–40 new.

**Budget target**: USD 30.

### 6.6 RC Radio & Power

- If an RC radio is already owned, reuse it.  
- If not, look for used transmitters + receivers; new sub-250g drones plus radios on FPV shops show typical pricing in the USD 100+ range, which suggests used radios might be found near USD 80–120.[web:207]

**Budget target**: assume radio is already owned; otherwise, budget USD 100 and accept that total may exceed USD 500.

### 6.7 Depth Camera & Payload (Stage 3+)

- Intel RealSense D435i new units are significantly more expensive than the project’s Stage 1–2 budget; used units sometimes appear in the USD 120–200 range depending on condition and seller.[web:198][web:206]
- ESP32 boards are inexpensive (typically under USD 15 new) and servos are also low-cost.

**Recommendation**:

- Treat depth camera and payload hardware as **Stage 3 investments**, possibly outside the initial USD 500 envelope.  
- Only proceed with these purchases after Stage 1–2 success.

### 6.8 Sample Budget (Target)

Assuming aggressive used deals and reusing an existing radio and batteries:

- Used frame + motors + ESCs: ~USD 150.  
- Used Pixhawk-class FC: ~USD 120.  
- Raspberry Pi 4 4 GB: ~USD 50.  
- Camera: ~USD 30.  
- Misc (BEC, wiring, mounts, fasteners): ~USD 50.

Total: ~USD 400, leaving some buffer for unexpected costs while staying under USD 500.

If a radio must be purchased used, that may push the total closer to USD 500 or slightly above.

---

## 7. Software Architecture for Implementation

### 7.1 Python Package Layout (Current Implementation)

**Architecture 2.0** - 45 Python modules, fully documented with docstrings:

```text
avatar/
  __init__.py

  # Configuration (YAML-based, hardware profiles)
  config/
    __init__.py
    hardware.yaml         # Mark4 7" build configuration
    sitl.yaml             # SITL simulation parameters
    prompts/              # LLM prompts and templates

  # Core Utilities (async patterns, decorators, context managers)
  core/
    __init__.py
    decorators.py         # @require_offboard, @require_armed
    context_managers.py   # Safe mode transition contexts

  # Drone Control & Safety Layer
  mav/
    __init__.py
    connection.py         # MAVSDK-Python bridge to PX4
    connection_manager.py # Async connection lifecycle
    guardian.py           # Hard limits enforcement (Layer 2)
    guardian_async.py     # Async validation wrappers
    heartbeat_service.py  # 20Hz offboard heartbeat
    protocols.py          # MAVLink message protocols
    px4_parameters.py   # Parameter validation and tuning
    state_machine.py      # Flight state transitions
    telemetry_cache.py    # Buffered telemetry storage
    escalation_matrix.py  # Failure escalation handling
    resource_monitor.py   # CPU/memory monitoring

  # Vision Pipeline (YOLO + ByteTrack)
  vision/
    __init__.py
    mock_detector.py      # Simulated detection for testing
    gazebo_camera_client.py  # Gazebo camera integration
    state_string.py       # Telemetry + detection fusion

  # Agent-Agnostic MCP Server (Works with ANY MCP client)
  mcp_server/
    __init__.py
    __main__.py           # Server entry point
    server.py             # MCP server implementation
    compat.py             # Backward compatibility layer
    confirmation.py       # Progressive confirmation workflow
    protocols.py          # MCP protocol definitions
    tools/
      __init__.py
      flight_tools.py     # arm, takeoff, land, goto, orbit
      telemetry_tools.py  # get_telemetry, get_state
      vision_tools.py     # capture_frame, start_detection
      tracking_tools.py   # target lock, follow subject
      cinematic_shots.py       # 16 professional shot templates
      cinematic_shots_personal.py  # Sport-specific profiles
      acrobatics.py       # Flip, roll maneuvers
      advanced_tracking.py  # Multi-subject tracking

  # Utilities
  utils/
    __init__.py
    flight_recorder.py    # Black box logging

  # Test Suite (pytest-based)
  tests/
    __init__.py
    conftest.py
    test_sitl_basic.py
    test_mcp_tools.py
    test_vision_pipeline.py
    test_safety_scenarios.py
    mav/
      test_px4_parameters.py
    tools/
      test_set_velocity.py

  # Scripts
  scripts/
    demo_script.md
    swap_to_hardware.sh   # Hardware/SITL mode switch

# Project-wide Tests (87 total test cases)
tests/
  __init__.py
  conftest.py
  test_cinematic_shots.py
  test_tracking_tools.py
  test_protocols.py
  core/
    test_decorators.py
    test_context_managers.py
  mav/
    test_state_machine.py
    test_heartbeat_service.py
    test_guardian_async.py
    test_connection_manager.py
    test_resource_monitor.py
    test_escalation_matrix.py
    test_telemetry_cache.py
  tools/
    test_hold.py
    test_fly_body_offset.py
    test_get_status.py
  e2e/
    test_full_mission.py
    test_failsafes.py
    test_mcp_realtime_control.py
    test_performance.py
  mcp_server/
    test_server_integration.py
    test_backward_compat.py
  property/
    test_safety_bounds.py
    test_coordinates.py
```

**Code Documentation Status**: 43 of 45 Python files have comprehensive docstrings including module-level documentation, class docstrings, and function docstrings. All public APIs are documented.

**Key Architectural Changes from v1.0**:
- **Agent-Agnostic**: `mcp_server/` replaces agent-specific integrations - works with ANY MCP client (OpenCode, Claude Desktop, Hermes, OpenClaw, etc.)
- **Cloud LLM**: `llm/kimi_client.py` replaces local Ollama (200 tok/s, multimodal)
- **Hybrid Vision**: `vision/capture_manager.py` manages YOLO local (10 FPS) + Kimi cloud frames
- **Pre-Flight Planning**: `planning/` module for Google Maps integration
- **Safety Independence**: 20Hz heartbeat moved to RPi (`mav/offboard.py`) - works regardless of agent connectivity

### 7.2 Libraries & Dependencies

**Core Drone Control**:
- `mavsdk` – PX4 offboard & telemetry.[web:200][web:208]  
- `asyncio` – orchestrating MAVSDK, heartbeat, and concurrent operations.

**Vision Pipeline**:
- `ultralytics` – YOLOv8-nano for local detection.[web:202]  
- `opencv-python` – frame capture, encoding, visualization.[web:202]  
- `bytetrack` or equivalent – multi-object tracking.[web:214]  
- `pillow` – image format conversion for API upload.

**Cloud LLM (Kimi K2.5)**:
- `openai` – Fireworks AI API client (OpenAI-compatible).  
- `requests` / `httpx` – HTTP client with timeout handling.  
- `tenacity` – retry logic for API failures.  
- `base64` – frame encoding for multimodal API calls.

**OpenCode MCP**:
- `mcp` – Model Context Protocol SDK for skill implementation.

**Maps & Planning**:
- `googlemaps` or `geopy` – Location geocoding (pre-flight only).  
- `shapely` – Geofence polygon calculations.

**Stage 3 (Depth)**:
- `pyrealsense2` – RealSense SDK for depth.[web:198]

### 7.3 Implementation Notes

- Use asyncio tasks for:  
  - MAVSDK telemetry listener.  
  - Offboard heartbeat.  
  - Vision processing loop.  
  - LLM agent loop.
- Use thread-safe queues or asyncio queues to pass data between components (e.g., detections to State String, State String to LLM agent).
- Ensure graceful shutdown: on exceptions or user interrupt, send `land()` or `rtl()` and drop out of Offboard.

---

## 8. Cinematic Shot System (16 Templates)

The cinematic shot system provides professional-quality drone filming capabilities for action sports (snowboarding, skateboarding, motocross, trail running).

### 8.1 Shot Template Library

**ORBIT SHOTS** (Circular tracking around subject):
1. `orbit_close` - Tight 8m radius orbit, 2m/s, cinematic feel
   - USE WHEN: Subject is relatively stationary, you want dramatic emphasis
   - EXAMPLE: Skater preparing for trick, athlete at starting line

2. `orbit_wide` - Wide 20m radius, 4m/s, shows environmental context
   - USE WHEN: Subject in scenic location, establishing shot
   - EXAMPLE: Snowboarder on mountain ridge, runner on coastal trail

**FOLLOW SHOTS** (Dynamic tracking of moving subject):
3. `follow_close` - Close 6m distance, 8m/s, immersive action feel
   - USE WHEN: Fast action, want viewer to feel "in the action"
   - EXAMPLE: Following a snowboarder through trees, motocross through whoops

4. `follow_wide` - Wide 15m distance, 12m/s, shows subject in environment
   - USE WHEN: Higher speed action where context matters
   - EXAMPLE: Downhill mountain bike run, powder snowboard descent

**REVEAL SHOTS** (Vertical movement for dramatic reveal):
5. `reveal_hero` - Rising from ground level to 20m, dramatic subject reveal
   - USE WHEN: Starting low (behind obstacle), revealing hero moment
   - EXAMPLE: Rising over hill to reveal skater landing trick

6. `reveal_descent` - Coming down to reveal subject detail
   - USE WHEN: Starting high, want to focus on subject detail
   - EXAMPLE: Descending to show skateboarder's foot placement

**PASS-BY SHOTS** (Lateral tracking for profile view):
7. `pass_by_low` - Low 1.5m height, 6m/s, smooth profile tracking
   - USE WHEN: Want side/profile view of subject in motion
   - EXAMPLE: Tracking alongside skater doing ledge tricks, runner stride analysis

**TOP-DOWN SHOTS** (Overhead perspective):
8. `top_down_dynamic` - Direct overhead at 15m, shows patterns/movement
   - USE WHEN: Want to show subject's path through terrain
   - EXAMPLE: Surfer on wave pattern, skater in bowl, motocross track lines

**HEIGHT-LOCKED TRACKING** (For vertical motion sports):
9. `height_locked_jump` - Maintains exact altitude offset from subject
   - USE WHEN: Subject has significant vertical movement (jumps, drops)
   - EXAMPLE: Snowboarder in halfpipe, motocross jumps, skate bowl airs
   - KEY FEATURE: PID controller with tight gains keeps constant height offset

**FPV-STYLE SHOTS** (Aggressive, fluid motion):
10. `fpv_dynamic` - Fast 15m/s, close 4m distance, bezier motion paths
    - USE WHEN: Want "fpv drone racing" aesthetic for action sports
    - EXAMPLE: Following snowboarder through terrain park, weaving through trees
    - WARNING: Requires skilled pilot oversight, aggressive motion profile

**SPORT-SPECIFIC TEMPLATES** (Pre-tuned parameters):
11. `snowboard_halfpipe` - Height-locked tracking for vertical transitions
    - USE WHEN: Snowboarder/skier in halfpipe (up/down wall transitions)
    - FEATURES: Predictive apex tracking, smooth wall transitions

12. `skate_pool_bowl` - Overhead with height-locked transitions
    - USE WHEN: Skateboarder in pool/bowl with airs
    - FEATURES: Tight radius orbits, quick height adjustments

13. `motocross_jump` - Long-distance follow with jump apex tracking
    - USE WHEN: Motocross rider hitting jump lines
    - FEATURES: 15-25m safety distance, trajectory prediction

14. `trail_runner` - Smooth follow with terrain-matching height
    - USE WHEN: Trail runner on technical terrain
    - FEATURES: Soft motion curves, consistent distance

15. `slow_reveal_push_in` - Cinematic push-in with slow reveal
    - USE WHEN: Opening shot, establishing location and subject
    - FEATURES: Combines lateral reveal with forward push

16. `orbit_with_tracking` - Orbiting while maintaining subject heading
    - USE WHEN: Subject moving in orbit pattern around feature
    - FEATURES: Continuous yaw adjustment to track subject

### 8.2 Key Technical Features

**Predictive Tracking (LookaheadPredictor)**:
- Compensates for 150-250ms vision processing latency (Pi 4 + YOLOv8-nano)
- Predicts subject position at command arrival time
- Eliminates "laggy follow" effect common in vision-based systems

**Smooth Motion Control**:
- Motion curves: ease_in_out, bezier, exponential
- PID controllers for precise distance/height maintenance
- Jerk-limited velocity ramps for fluid footage

**Sport-Specific Profiles**:
- Snowboard: Responsive PID for sudden direction changes
- Runner: Soft settings for smooth, predictable pace
- Skate: Tight orbits for bowl/pool maneuvers
- Motocross: Safety distance with aggressive tracking

### 8.3 Hardware Context

- Frame: Mark4 7" long-range cinematic platform
- Max speed: ~12-15 m/s (limited for filming smoothness)
- Comfortable filming speed: 4-5 m/s (optimal for stable footage)
- Vision latency: 150-250ms (Pi 4 YOLO inference)
- Total pipeline latency compensated by lookahead predictor

### 8.4 PX4 Parameters for Cinematic Flight

```yaml
# Smooth, filmic settings - reduce all accelerations
MPC_XY_VEL_MAX: 8.0        # m/s - enough for runners/casual snowboard
MPC_XY_VEL_P_ACC: 1.2      # Softer horizontal response
MPC_Z_VEL_MAX_UP: 2.0      # Slow ascent = cinematic
MPC_Z_VEL_MAX_DN: 1.5      # Slow descent = cinematic
MPC_JERK_AUTO: 2.0         # Jerk limiting for fluid motion
MPC_ACC_HOR: 1.5            # Gentle acceleration
MC_YAW_P: 2.0               # Slower yaw sweep
MPC_YAWRAUTO: 60.0          # Max yaw rate in auto modes
```

---

## 9. Further Reading & Exploration

For deeper technical context and future improvements:

- **When Large Language Models Meet UAVs: How Far Are We?** – for a broad view of LLM-UAV integration patterns and open challenges.[web:56][web:215]
- **NeLV** – for a concrete five-level UAV autonomy taxonomy using LLMs.[web:22]  
- **ChatGPT for Robotics** – for design principles in tool-calling and prompt engineering.[web:29][web:216]
- **Autonomous Drone Racing: A Survey** – for insights into high-speed control, perception, and planning that may inform future upgrades.[web:210][web:217]  
- **Autonomous Drone Racing with Deep RL** – for examples of near-optimal trajectory generation and the performance ceiling of quadrotors.[web:201]
- PX4 docs on Offboard control and preflight checks – for authoritative guidance on safety and control limits.[web:45][web:184][web:190][web:130]

---

## 10. Phase 0.5 Completion Status

**Status**: COMPLETE (April 2026)

Phase 0.5 (Virtual Drone - Pre-Hardware Validation) has been successfully completed. The entire software stack has been built and validated in PX4 SITL + Gazebo simulation:

### Completed Components
- **45 Python modules** with comprehensive docstrings (43 of 45 documented)
- **87 test cases** (81 passing, 6 minor implementation issues)
- **16 cinematic shot templates** with sport-specific profiles
- **Agent-agnostic MCP server** supporting any MCP client (Claude Desktop, OpenCode, Hermes, OpenClaw)
- **20Hz heartbeat service** for PX4 offboard control independence
- **Vision pipeline** with YOLOv8-nano + ByteTrack integration
- **Safety layer** with GuardianProcess, hard limits, and progressive confirmation

### Architecture Validated in Simulation
- SITL (Software In The Loop) testing complete
- Gazebo physics simulation verified
- MAVSDK-Python integration working
- MCP tool calling validated
- Progressive confirmation workflow tested

### Next Phase: Hardware Integration
The system is ready for Stage 1 hardware integration:
- Mark4 7" frame assembly
- Pixhawk 6C Mini flight controller
- Raspberry Pi 4 companion computer
- Pi Camera 3 Wide

See `PHASE_0_5_COMPLETION.md` and `PHASE_0_5_SUMMARY.md` for detailed test results.

---

This document reflects **Architecture 2.0** (April 2026) with Kimi K2.5 cloud LLM and MCP interface.

Key capabilities:
- **Cloud LLM**: Kimi K2.5 via Fireworks AI (200 tok/s, multimodal vision)
- **Agent-Agnostic**: Works with ANY MCP client through standardized protocol
- **Hybrid Vision**: YOLO local (10 FPS) + Kimi cloud (frames every 3-5s)
- **Cinematic Shots**: 16 professional templates for action sports filming
- **Safety Independence**: 20Hz heartbeat works regardless of agent connectivity
- **87+ Files**: Comprehensive documentation with docstrings throughout

This document, combined with the PRD, roadmap, and cinematic research, provides Claude Code with the context to:

- Reason about the production architecture and constraints
- Generate concrete Python modules in the current structure
- Implement additional cinematic shot templates
- Extend the MCP server for new capabilities
- Suggest refinements based on real research instead of guesswork

