# Project Avatar Technical Background & Implementation Guide

**Architecture Version**: 2.0 (April 2026) - Kimi K2.5 Cloud LLM with OpenCode MCP Interface

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

### 7.1 Proposed Python Package Layout

Architecture 2.0 with Kimi K2.5 cloud LLM and OpenCode MCP interface:

```text
avatar/
  # Drone Control & Safety
  mav/
    __init__.py
    connection.py        # PX4/RPi MAVLink connection
    offboard.py          # 20Hz heartbeat (runs on RPi)
    mission.py           # High-level maneuvers (goto, orbit, etc.)
    safety.py            # EKF/GPS checks, GuardianProcess validation
    guardian.py          # Hard limits enforcement (Layer 2 safety)

  # Vision Pipeline (Hybrid: YOLO local + Kimi cloud)
  vision/
    __init__.py
    video_client.py      # MJPEG/RTSP frame ingestion from RPi
    detector.py          # YOLOv8-nano (10 FPS local detection)
    tracker.py           # ByteTrack (ID persistence)
    state_string.py      # Fusion: telemetry + YOLO detections
    frame_buffer.py      # Selective frame capture for Kimi
    capture_manager.py   # Frame scheduling (every 3-5s + on-demand)

  # LLM Integration (Cloud Kimi K2.5)
  llm/
    __init__.py
    kimi_client.py       # Fireworks AI API client
    tools.py             # Tool schema definitions for Kimi
    agent.py             # Conversation loop with tool calling
    vision_adapter.py    # Frame encoding for multimodal API
    conversation.py      # Context management (128K window)

  # Agent-Agnostic MCP Server (Works with ANY MCP client)
  mcp_server/
    __init__.py
    server.py            # MCP server implementation (official SDK)
    tools/
      flight_tools.py    # Drone flight control tools
      vision_tools.py    # Frame capture and analysis
      planning_tools.py  # Mission planning tools
    handlers.py          # Tool execution handlers
    confirmation.py      # Progressive confirmation workflow
    session_manager.py   # Per-agent session state
    exception_handler.py # Mid-flight exception processing
    README.md            # Agent connection instructions

  # Maps & Planning (Pre-flight only)
  planning/
    __init__.py
    maps_mcp.py          # Google Maps MCP integration
    mission_templates.py # Orbit, search, perimeter patterns
    geofence.py          # Safety boundary calculations
    cache.py             # Offline mission context storage

  payload/
    __init__.py
    esp32_interface.py   # Serial protocol for actuators
    kinematics.py        # Physics calculations (Stage 3)

  config/
    params.yaml          # Hard limits, timeouts, thresholds
    prompts/
      system_prompt_kimi.txt       # Kimi behavior + safety rules
      mission_templates.yaml       # Predefined flight patterns
      confirmation_messages.yaml   # User interaction templates

  scripts/
    run_mcp_server.py         # Start Drone MCP server (agent-agnostic)
    test_agent_connection.py  # Test MCP connection from any agent
    test_kimi_vision.py       # Validate multimodal API
    test_confirmation.py      # Simulate confirmation workflow
    connect_claude_code.py    # Configure Claude Code MCP connection
    connect_opencode.py       # Configure OpenCode MCP skill
    connect_hermes.py         # Configure Hermes MCP connection

  # Legacy (Stage 1-2 local LLM - archived)
  _archive/
    ollama_client.py     # Local Llama 3 (superseded by Kimi)
```

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

## 8. Further Reading & Exploration

For deeper technical context and future improvements:

- **When Large Language Models Meet UAVs: How Far Are We?** – for a broad view of LLM-UAV integration patterns and open challenges.[web:56][web:215]
- **NeLV** – for a concrete five-level UAV autonomy taxonomy using LLMs.[web:22]  
- **ChatGPT for Robotics** – for design principles in tool-calling and prompt engineering.[web:29][web:216]
- **Autonomous Drone Racing: A Survey** – for insights into high-speed control, perception, and planning that may inform future upgrades.[web:210][web:217]  
- **Autonomous Drone Racing with Deep RL** – for examples of near-optimal trajectory generation and the performance ceiling of quadrotors.[web:201]
- PX4 docs on Offboard control and preflight checks – for authoritative guidance on safety and control limits.[web:45][web:184][web:190][web:130]

This document reflects **Architecture 2.0** (April 2026) with Kimi K2.5 cloud LLM and OpenCode MCP interface. Key changes from v1.0:
- Cloud LLM (200 tok/s, multimodal) replaces local 7B model (25-40 tok/s)
- OpenCode chat interface with progressive confirmation workflow
- Hybrid vision: YOLO local (10 FPS) + Kimi cloud (frames every 3-5s)
- 20Hz heartbeat moved to RPi for independence from Mac connectivity
- Google Maps integration for pre-flight mission planning

This document, combined with the PRD and roadmap, should give Claude Code enough context to: 

- Reason about the new architecture and constraints.  
- Generate concrete Python modules in the proposed structure.  
- Implement the Kimi client, MCP skill, and hybrid vision pipeline.  
- Suggest refinements based on real research instead of guesswork.

