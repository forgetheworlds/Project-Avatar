# Project Avatar PRD – LLM-Driven Drone Avatar

## 1. Executive Summary

Project Avatar aims to build a real, flyable drone system where a user can speak in natural language via OpenCode chat and a cloud LLM (Kimi K2.5 via Fireworks AI) autonomously plans and executes missions, using real camera data to drive real flight behavior and, later, payload actions.
The core constraint is that **nothing is mocked**: sensor data are real, the LLM sees real camera frames, and the vehicle flies real missions, but the system architecture strictly respects physics and latency boundaries so that safety-critical reflexes never depend on the LLM.

This PRD formalizes a three-stage development path:

- **Stage 1 – Control Spine (No Vision)**: Prove end-to-end OpenCode chat → Kimi LLM → JSON tools → MAVSDK → PX4 Offboard control with a robust heartbeat, EKF/GPS health gating, RC override, and structured logging.
- **Stage 2 – Real Vision for Mission Logic ("Eyes")**: Add RGB camera, YOLOv8-nano and tracking on the Mac; implement hybrid vision where YOLO provides real-time detection and Kimi receives periodic camera frames for mission-level decisions and target-centered behaviors, but not for distance-based collision reflexes.
- **Stage 3 – Depth, Spatial Reasoning, and Payload ("Hands")**: Introduce depth sensing (Intel RealSense D435i), spatial grounding (distance in meters, basic 3D reasoning), and bench-tested payload control via ESP32, enabling depth-gated LLM reactions and kinematic calculations while PX4 and low-level processes still own hard reflexes.

The target ground station is a **local MacBook Pro M3** running YOLOv8 on MPS and interfacing with **Kimi K2.5 via Fireworks AI** (cloud LLM with 200 tok/s, native multimodal vision, and reliable tool calling); the drone uses a PX4-capable flight controller and a Raspberry Pi 4 companion computer as the bridge.[web:196][web:197][web:212] 

**Architecture Update (April 2026)**: Cloud LLM (Kimi K2.5) is now the primary inference engine, accessed via phone cellular data. This provides 8x faster inference (200 tok/s vs 25-40 tok/s local), native multimodal vision capabilities, and dramatically improved tool-calling reliability compared to local 7B models. The 20Hz heartbeat and safety-critical reflexes remain local on the RPi/Pixhawk, maintaining independence from cloud connectivity.

---

## 2. System Philosophy

### 2.1 Layered Autonomy and Latency Bands

The system follows a **hierarchical, latency-bounded architecture**:

- **Hard Reflex Layer (< 100 ms)**  
  - Implemented in PX4 and, later, in simple companion-computer guard processes.  
  - Examples: geofencing, failsafe on Offboard heartbeat loss, altitude limits, collision prevention using depth or range sensors.  
  - This layer must always be safe without the LLM.[web:45][web:130]

- **LLM Reaction Layer (~1–3 s)**  
  - LLM reads text state (telemetry + detections) and decides to reroute, loiter, or change mission phase.  
  - Examples: "I see a person in my path, I will change the orbit radius," "I have observed 5–7 people, mission complete, return."  
  - This layer never relies on millisecond timing for collision prevention; it shapes trajectories and goals.

- **Mission & Operator Layer (seconds–minutes)**  
  - Human specifies high-level natural language goals.  
  - Mission templates (e.g., park circuit, perimeter scan, moving-target tracking) provide structure and guardrails.

### 2.2 Reaction vs Reflex

The architecture **codifies** the distinction between:

- **Hard Reflex**: Response that must occur within tens of milliseconds to avoid collision (e.g., stopping a 5 kg drone moving at 5 m/s before hitting a tree). This can only be implemented in PX4 (failsafes, obstacle avoidance), or in simple low-level processes triggered by depth/range data, not by the LLM.[web:45][web:213]
- **LLM Reaction**: Semantic and spatial decisions that can tolerate 1–3 seconds of latency (e.g., aborting a mission after observing people, choosing a different approach vector, adjusting offset distance once depth is available).

Stage definitions and tool APIs must respect this boundary. The LLM controls **where to go and what to do**, but does not own the millisecond reflex loop.

---

## 3. High-Level Architecture

### 3.1 Components

- **User Interface (Any MCP-Compatible Agent)**  
  - Natural language commands via chat interface.  
  - Examples: OpenCode, Claude Desktop, Hermes, OpenClaw, or custom scripts.  
  - **Agent-agnostic**: Any MCP client can connect to Drone MCP Server.  
  - Progressive confirmation workflow with mission preview and exception handling.

- **Ground Station (MacBook Pro M3)**  
  - **LLM Client**: Kimi K2.5 via Fireworks AI API (cloud, 200 tok/s, native multimodal).  
  - YOLOv8-nano object detector and ByteTrack tracker on live camera stream (local, 10-15 FPS).[web:202][web:214]  
  - **Hybrid Vision**: YOLO for real-time detection + selective frame capture for Kimi analysis.  
  - **Drone MCP Server**: Agent-agnostic Model Context Protocol server exposing flight tools.  
  - Video recording and telemetry logging to local storage.

- **Companion Computer (Raspberry Pi 4)**  
  - Bridges MAVLink between PX4 and the Mac over Wi-Fi/telemetry radio (UDP).  
  - **Hosts the offboard heartbeat thread** (20Hz, independent of Mac connectivity).[web:200][web:130]  
  - Provides video encoding/streaming (MJPEG/RTSP) to the Mac.  
  - GuardianProcess validation (Layer 2 safety).

- **Flight Controller (PX4-capable, e.g., Pixhawk 6C)**  
  - Runs PX4 firmware with GPS-based navigation and offboard support.[web:196][web:45]  
  - Enforces geofencing, failsafes, and sensor preflight checks.[web:184][web:190]  
  - Hard reflexes (<100ms) completely independent of LLM.

- **Sensors**  
  - Stage 1: GPS, IMU, barometer only.  
  - Stage 2: Add RGB camera (Pi Cam or USB camera), Google Maps MCP for pre-flight planning.  
  - Stage 3: Add Intel RealSense D435i for depth, fused with RGB detections.[web:198][web:213]

- **Connectivity**  
  - Phone cellular data → MacBook (for Kimi API access).  
  - Telemetry radio or WiFi → RPi (MAVLink, independent of cellular).

- **Payload & Actuators (Stage 3)**  
  - ESP32 microcontroller managing servos, pumps, or other actuators, abstracted as high-level tools (e.g., `aim_gimbal`, `trigger_payload`).

### 3.2 Software Stack

- **PX4 Autopilot** for low-level control & failsafes.[web:45][web:130]
- **MAVSDK-Python** for offboard control, telemetry, and mission commands.[web:200][web:208]
- **Drone MCP Server** (Agent-Agnostic Model Context Protocol):
  - Exposes drone control tools to LLM agent.  
  - Validates all tool calls via GuardianProcess.  
  - Manages confirmation workflow and exception handling.
- **Kimi K2.5 Client** (Fireworks AI):
  - Cloud LLM inference with 128K context.  
  - Native multimodal vision (analyzes drone camera frames).  
  - Reliable tool calling for flight commands.
- **Python Orchestrator** managing:
  - User intent parsing and mission planning.  
  - Google Maps MCP integration (pre-flight only).  
  - LLM conversation flow with Kimi.  
  - Hybrid vision coordination (YOLO + selective frame capture).  
  - Progressive confirmation workflow.
- **YOLOv8 + ByteTrack** for real-time detection and ID persistence (local, 10-15 FPS).[web:202][web:214]
- **Vision Pipeline**:
  - Frame capture and YOLO inference on Mac.  
  - State String generation (telemetry + detections).  
  - Selective frame capture for Kimi analysis (every 3-5s + on-demand).
- **RealSense SDK** in Stage 3 for depth + IMU fusion.[web:198]

---

## 4. Staged Functional Requirements

### 4.1 Stage 1 – Control Spine (No Vision)

**Goal**: Prove the LLM → JSON tools → MAVSDK → PX4 Offboard chain with a robust heartbeat and safety.

#### 4.1.1 In-Scope

- Bi-directional MAVLink/Offboard pipeline: PX4 ↔ RPi ↔ Mac.  
- Offboard heartbeat subsystem (continuous setpoint streaming, independent of LLM latency).[web:45][web:33]
- Strict JSON tool schema for flight commands (takeoff, land, goto, hold, rtl).  
- LLM integration via local Llama 3 (Ollama), using function/tool-calling to emit valid JSON.  
- EKF/GPS pre-arm gating and health checks before arming.[web:184][web:190]
- RC transmitter override & kill switch with absolute priority.[web:130]
- Structured logging of all commands, telemetry summaries, and LLM decisions.

#### 4.1.2 Out-of-Scope

- Any camera, YOLO, VLM, or visual logic.  
- Any distance-based collision avoidance beyond PX4’s built-in failsafes and geofences.  
- Any payload hardware.

#### 4.1.3 Functional Requirements

- **FR 1.1 – MAVLink Bridge**  
  The system shall establish a bi-directional MAVLink connection between PX4 and the Mac, routed via the RPi over Wi-Fi (UDP, e.g., `udp://:14540`).[web:200][web:130]

- **FR 1.2 – Offboard Heartbeat Manager**  
  The system shall include an offboard heartbeat manager that streams valid setpoints to PX4 at ≥ 2 Hz whenever offboard mode is engaged, and continues streaming even if the LLM is blocked or slow.[web:45][web:33]

- **FR 1.3 – JSON Tool Schema (Control)**  
  The LLM shall only issue flight commands via a predefined JSON schema, including (minimum):  
  - `arm_and_takeoff(altitude_m)`  
  - `goto_gps(lat, lon, alt_m)`  
  - `fly_body_offset(forward_m, right_m, up_m)`  
  - `hold(seconds)`  
  - `land()`  
  - `rtl()`

- **FR 1.4 – Blocking Execution with Heartbeat Hold**  
  The orchestrator shall ensure that only one high-level command is active at a time, and shall keep the last valid setpoint streaming until a new tool completes or is cancelled.

- **FR 1.5 – EKF/GPS Pre-Arm Gating**  
  Before arming, the system shall check PX4’s preflight and estimator status (EKF flags, GPS fix type/quality) and refuse to arm if any required checks fail.[web:184][web:190]

- **FR 1.6 – RC Override Priority**  
  RC input shall always be able to override offboard control and initiate a manual or RTL mode as configured in PX4 (`COM_OBL_RC_ACT` and related parameters).[web:45][web:130]

- **FR 1.7 – Logging & Telemetry Summary**  
  All commands, tool calls, mode changes, and summarized telemetry shall be logged with timestamps for later analysis.

#### 4.1.4 Stage 1 Definition of Done

- Typing:  
  `"Take off to 10 meters, fly east 20 meters, and land."`  
  leads to LLM-emitted JSON tools.  
- The orchestrator validates tools, runs pre-arm checks, arms, executes the mission using PX4 Offboard with a continuous heartbeat, and lands.  
- RC kill switch can interrupt at any time.  
- Log shows a clear sequence of decisions and telemetry snapshots.

---

### 4.2 Stage 2 – Real Vision for Mission Logic ("Eyes")

**Goal**: Integrate a real camera and YOLO pipeline so the LLM can use **real visual detections** to drive mission-level decisions and target-centered orientation, without attempting 2D-only distance-based reflexes.

#### 4.2.1 In-Scope

- RGB camera (Pi Camera module or USB webcam) mounted on the drone.[web:195]  
- Video streaming from RPi to Mac (e.g., MJPEG over HTTP or low-latency RTSP).  
- YOLOv8-nano detector and ByteTrack (or similar) tracker running on Mac using CPU/MPS.[web:202][web:211][web:218]  
- **State String** generator that fuses telemetry + 2D detections:  
  - For each frame interval (~1 Hz for LLM), list objects with class, bounding box (pixels), and stable ID where possible.  
  - Summaries like "3 people detected", "tracked ID_7 near frame center".[web:214]
- LLM tools for **mission logic** and **target-centric orientation**, such as switching from GPS orbit to target-centric yaw control.

#### 4.2.2 Out-of-Scope

- Any use of 2D bounding box size or pixel movement as a distance metric for collision stopping.  
- Depth sensors (RealSense) and spatial grounding in meters (these are Stage 3).  
- Payload actuation.

#### 4.2.3 Functional Requirements

- **FR 2.1 – Vision Pipeline**  
  A background process shall ingest live video frames, run YOLOv8-nano, and track objects (e.g., people) with persistent IDs at ≥ 10–15 FPS on the Mac, using MPS or CPU as appropriate.[web:202][web:211][web:218]

- **FR 2.2 – State String Synthesis**  
  Every 1–2 seconds, the system shall synthesize a text state summary that includes:  
  - Key telemetry (mode, altitude, velocity, battery, GPS health).  
  - Detected objects (class, count, IDs, approximate frame locations such as left/center/right, top/middle/bottom).  
  - Simple event markers (e.g., "new person ID appeared", "tracked ID lost").[web:214]

- **FR 2.3 – LLM Context Injection**  
  The State String shall be injected into the LLM system prompt or context on each main loop, so that it has continuous situational awareness without processing raw images directly.[web:29][web:56]

- **FR 2.4 – Vision-Guided Mission Logic**  
  The LLM shall be allowed to use State String information to:  
  - Switch from a GPS orbit to a target-centric orbit once a target is found.  
  - Decide to loiter longer or terminate a mission based on observed counts.  
  - Request re-orientation (yaw) to keep a target centered in the frame.

- **FR 2.5 – 2D-Vision Distance Restriction**  
  The system shall explicitly **forbid** the use of 2D-only vision (bounding boxes, pixel coordinates) to trigger distance-based stop or collision avoidance, due to unreliability of bounding box scaling as a distance proxy at varying altitude and viewing conditions.[web:210][web:217]

#### 4.2.4 Stage 2 Definition of Done

- User can type:  
  `"Take off, find the person in the red shirt, and orbit them."`  
- The system:
  - Executes takeoff and a GPS search pattern.  
  - Vision pipeline detects humans and assigns stable IDs.  
  - LLM uses the State String to identify a likely "red shirt" target (via class + color cues provided by the detector or precomputed regions).  
  - Once locked, the drone switches to a mode where it maintains a GPS orbit while using yaw adjustments to keep the target near the frame center.  
- All of this uses **real** camera data and detections, with no mocked vision.

---

### 4.3 Stage 3 – Depth, Spatial Reasoning, and Payload ("Hands")

**Goal**: Add depth sensing and spatial reasoning so the LLM can reason about distances and offsets in meters, participate in higher-level avoidance reactions, and control bench-tested payload systems through hardened tools.

#### 4.3.1 In-Scope

- Intel RealSense D435i mounted on the drone, integrated via RPi or Mac.[web:198][web:213]  
- Depth fusion: YOLO detections associated with depth values to produce per-object distance estimates.  
- Extension of the State String with distance metrics (e.g., `distance_m`, approximate 3D position relative to the drone).  
- Higher-level tools that use distances and offsets (e.g., `maintain_offset(target_id, distance_m)`).  
- ESP32-based payload rail with abstracted tools (`aim_gimbal`, `trigger_payload`) for non-human targets (e.g., static props, safe targets), designed and tested on the bench first.

#### 4.3.2 Out-of-Scope

- Any payload use against people or animals.  
- Any attempt to bypass PX4’s own obstacle avoidance or failsafe layers.  
- Fully autonomous emergency services applications (e.g., unsupervised fire response).

#### 4.3.3 Functional Requirements

- **FR 3.1 – Depth-Augmented State String**  
  When the RealSense is active, the State String shall include, for tracked objects, an estimated distance in meters and basic relative pose (e.g., ahead/left/right and above/below).[web:198][web:213]

- **FR 3.2 – Distance-Gated Tools**  
  The LLM may use new tools that require distance (e.g., `maintain_offset(distance_m=8)` or `evaluate_path_safety(distance_m)`), but only when the State String indicates that valid depth data are available.

- **FR 3.3 – LLM-Supported Avoidance Reactions**  
  The LLM may trigger `stop_movement()` when the State String reports nearby obstacles with valid distance metrics (e.g., `distance_m < threshold`), complementing PX4’s lower-level avoidance.

- **FR 3.4 – Payload Tools and Kinematics**  
  Payload control tools shall be defined as static Python functions (e.g., in `kinematics.py` and `payload/esp32_interface.py`) that expose parameters like `angle_deg` or `duration_ms`.  
  The LLM may call these tools to perform kinematic calculations and send commands, but is not allowed to generate arbitrary ESP32 code on the fly in flight-critical contexts.[web:29][web:56]

- **FR 3.5 – Bench-First Policy for Payload**  
  All payload behaviors shall be prototyped and validated on a bench setup (no props, static mount) before being deployed on the flying platform.

#### 4.3.4 Stage 3 Definition of Done

- The system can maintain a distance-based offset from a non-human target using depth data and tracking, adjusting position to keep a safe separation while keeping the target in view.  
- Depth-augmented State String allows the LLM to trigger `stop_movement()` in clearly unsafe configurations while PX4’s failsafes remain active.  
- Payload tools operate reliably on bench tests and can be triggered in tightly controlled field scenarios against inanimate targets.

---

## 5. Non-Functional Requirements

### 5.1 Safety and Failsafes

- **NFR 5.1.1 – Heartbeat Resilience**  
  Offboard control must respect PX4’s requirement for continuous setpoint streaming; if the heartbeat fails, PX4 must automatically transition to a configured safe mode (e.g., Position Hold or RTL) per `COM_OBL_RC_ACT` and related parameters.[web:45][web:33]

- **NFR 5.1.2 – EKF & Sensor Health**  
  Missions must be blocked if EKF or sensor checks fail PX4 preflight requirements.[web:184][web:190]

- **NFR 5.1.3 – RC Dominance**  
  Manual control via RC transmitter must always be able to take over from the LLM-controlled offboard mode.

- **NFR 5.1.4 – No Human-Target Payloads**  
  Payload tools must be designed and documented only for interaction with inanimate targets or the environment; no human-target payload use cases are permitted.

### 5.2 Latency & Performance

- **NFR 5.2.1 – End-to-End Command Latency**  
  From user command → LLM → validated tools → first setpoint update, latency should be ≤ 2 s under normal conditions.

- **NFR 5.2.2 – Vision Throughput**  
  YOLOv8-nano + tracking on Mac M3 must sustain at least 10 FPS at a modest resolution (e.g., 416–640 px), which is feasible on Apple silicon using MPS with careful configuration.[web:202][web:211][web:218]

### 5.3 Autonomy & Connectivity Architecture

- **NFR 5.3.1 – Cloud LLM Primary (Updated)**  
  Core autonomy (flight planning, mission logic, vision analysis) uses Kimi K2.5 via Fireworks AI cloud API. Local LLM fallback is optional for future enhancement. Phone cellular data provides reliable connectivity. Cost: ~$0.10 per 15-minute flight.

- **NFR 5.3.2 – Offline Safety**  
  Hard reflexes (20Hz heartbeat, PX4 failsafes, GuardianProcess) must function without internet. If cloud LLM becomes unavailable:
  - Pause mission and enter "hold position" mode
  - Do not execute new LLM-planned maneuvers
  - Maintain RTL capability using cached mission context
  - RC override always works regardless of connectivity

- **NFR 5.3.3 – Progressive Confirmation**  
  Mission execution requires confirmation at multiple levels:
  - **Pre-flight**: User confirms mission plan generated from natural language + Maps context
  - **Pre-arm**: User confirms after live camera check + telemetry review
  - **Mid-flight exceptions**: System asks "Stop or continue?" when people detected, geofence warnings, or safety margins exceeded
  - **Timeout behavior**: 10-second confirmation window; no response → default to "hold position"

- **NFR 5.3.4 – Human-in-the-Loop Override**  
  At any point, user can issue commands that override LLM suggestions:
  - "Abort mission" → immediate RTL
  - "Take control" → switch to manual/position mode
  - "Widen orbit" → adjust current mission parameters
  - RC transmitter switch has ultimate priority over all software decisions

### 5.4 Budget & Hardware Constraints

- **NFR 5.4.1 – Total Drone Hardware Budget**  
  New purchases for the airframe, flight controller, companion computer, camera, RC link, and basic batteries must not exceed approximately USD 500, relying heavily on second-hand or discounted components, recognizing that some items like the MacBook are already owned.[web:195][web:196][web:197][web:207]

- **NFR 5.4.2 – Future Depth Hardware**  
  Depth hardware (e.g., Intel RealSense D435i) is considered Stage 3 and may push the budget beyond the initial USD 500 if acquired later; Stage 1–2 should be achievable within the budget assuming used deals.[web:198][web:206]

---

## 6. Success Metrics

- **Stage 1**: Reliable execution of basic natural language missions (takeoff/goto/land) with clean logs, no Offboard timeouts, and safe RC overrides.
- **Stage 2**: Closed-loop missions where vision detections genuinely alter mission behavior (e.g., switching into and out of target-centric orbit), with stable tracking in realistic outdoor conditions.
- **Stage 3**: Depth-enhanced missions where distance-aware tools operate correctly and payload tools run reliably in bench tests and limited field trials.

---

## 7. Out-of-Scope for This PRD

- Multi-UAV coordination (fleet missions).  
- BVLOS (Beyond Visual Line-of-Sight) operations or regulatory compliance.  
- Cloud-model-only autonomy.  
- Full fire-scene response or emergency services deployment (can be revisited as a separate product concept once the avatar architecture is proven).

