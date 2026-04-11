PROJECT AVATAR
Stage 1 Control Spine
Research & Planning Brief

Principal Systems Architect | Initial Research & Planning Phase

Classification: Internal Engineering Document

Date: April 2026

I
Executive Summary Table of Contents
Source Document Assessment
2.1 What the Documents Got Right.................................................................................
2.1.1 Latency-Bounded Autonomy Hierarchy
2.1.2 RC Override as Absolute Priority
2.1.3 Offboard Heartbeat as Independent Subsystem................................................
2.1.4 Local-First Constraint
2.2 Critical Gaps and Oversimplifications
2.2.1 MAVSDK-Python's gRPC Architecture Is Unmentioned
2.2.2 PX4 Offboard Requirements Are Underspecified
2.2.3 Ollama Tool-Calling Reliability Is Assumed, Not Researched
2.2.4 RPi Bridge Complexity Is Radically Simplified
2.2.5 fly_body_offset Is Far More Complex Than Presented
2.2.6 GPS-Only Navigation Limitations Are Handwaved
Subsystem Deep-Dive: MAVSDK-Python Async Architecture
3.1 The gRPC Split Architecture
3.2 Critical Failure Modes
3.2.1 Silent Connection Failure (GitHub Issue #133)
3.2.2 Indefinite Hang After System Discovery (GitHub Issue #759)
3.2.3 Orphan mavsdk_server Safety Hazard (GitHub Issue #374)
3.2.4 Telemetry Subscriptions Silently Stopping (GitHub Issue #321)
3.2.5 Blocking the Event Loop Produces Stale Telemetry
3.3 Thread Safety and Event Loop Constraints
Subsystem Deep-Dive: PX4 Offboard Mode Constraints
4.1 Exact Entry Requirements
4.2 Failsafe Chain and Parameter Configuration.............................................................
4.3 GPS Degradation Impact on Offboard Mode II
4.4 Position vs. Velocity Setpoint Tradeoffs
Subsystem Deep-Dive: Raspberry Pi Serial Bridging
5.1 UART vs. USB: The Definitive Answer
5.2 mavlink-router as the Bridge Daemon.....................................................................
5.3 RPi Power and Thermal Considerations
Subsystem Deep-Dive: Ollama Local Function Calling
6.1 Model Selection for Tool-Calling Reliability
6.2 Quantization Impact on Tool-Calling Fidelity
6.3 Mandatory Validation Architecture
6.4 Performance on M3 MacBook Pro Under Concurrent Load
Boundary Analysis: Mac-RPi-Pixhawk Communication Chain
7.1 Latency Budget and Packet Loss
7.2 WiFi Configuration Requirements
7.3 The Video-MAVLink Contention Problem
GPS-Only Navigation: Performance Realities
8.1 Accuracy and Drift Characteristics
8.2 Implications for Stage 1 Tool Design
Consolidated Risk Matrix
Architectural Recommendations for Stage
10.1 Recommended Hardware Architecture
10.2 Recommended Software Architecture
10.3 Revised PX4 Parameter Configuration
10 .4 LLM Integration Recommendations
10.5 fly_body_offset Implementation Strategy
10.6 Forward-Looking Architectural Awareness
1. Executive Summary
This document constitutes the Principal Systems Architect's initial research and planning
brief for Stage 1 of Project Avatar: the Control Spine. Stage 1 is defined as the GPS-only,
LLM-to-MAVSDK-to-PX4 control chain with no vision, depth, or payload subsystems. The
purpose of this brief is to cross-reference three source documents (the PRD, Roadmap, and
Technical Background), validate their assumptions against real-world subsystem behaviors,
identify gaps and hidden failure modes, and produce actionable architectural
recommendations before a single line of code is written.

The source documents are generally well-structured and demonstrate sound high-level
architectural thinking, particularly in their separation of autonomy into latency-bounded
layers (Hard Reflex, LLM Reaction, Mission/Operator) and their insistence that the LLM
never owns the millisecond reflex loop. However, deep research into the actual real-world
behavior of each critical subsystem reveals significant oversimplifications, undocumented
failure modes, and architectural decisions that will encounter severe friction upon contact
with physical hardware. The most consequential findings involve: MAVSDK-Python's
underlying gRPC architecture and its orphan-process safety implications, PX4's exacting
requirements for offboard mode entry that go well beyond what the documents describe,
Ollama's function-calling reliability gaps with quantized 8B models, and the nuanced
physics of GPS-only navigation that the documents treat as a solved problem.

This brief is organized into four layers. First, an assessment of what the source documents
got right and where they fall short. Second, deep-dive research reports on each critical
subsystem. Third, a boundary analysis of the Mac-to-RPi-to-Pixhawk communication chain.
Fourth, a consolidated risk matrix and revised architectural recommendations. Every finding
is grounded in community-reported issues, official documentation, and published research.
The goal is to ensure that the Stage 1 architecture we build is resilient, well-understood, and
does not paint us into an architectural corner for the precision phases that follow.

2. Source Document Assessment
2.1 What the Documents Got Right.................................................................................
The three source documents demonstrate several areas of strong architectural judgment that
should be preserved and reinforced throughout implementation. These correct decisions
form the scaffolding upon which the rest of the system must be built, and it is worth
enumerating them explicitly so that they are not inadvertently compromised during
implementation pressure.

2.1.1 Latency-Bounded Autonomy Hierarchy
The PRD's distinction between Hard Reflex (under 100ms, PX4-owned), LLM Reaction (1-
3 seconds, text-driven), and Mission/Operator (seconds to minutes, human-driven) is
architecturally sound and aligns with established patterns in the LLM-UAV research
literature, specifically the NeLV framework's five-component separation and the findings of
the 2025 survey paper on LLM-UAV integration. The documents correctly identify that the
LLM should control waypoints and mission-level goals, never raw motor commands or rate-
level control. This separation must be enforced not just in documentation but in the actual
software architecture through hard API boundaries that prevent the LLM from ever directly
accessing low-level control interfaces.

2.1.2 RC Override as Absolute Priority
All three documents consistently treat RC transmitter override as the supreme safety
mechanism, referencing COM_OBL_RC_ACT and related PX4 parameters. This is correct
and non-negotiable. The RC transmitter must always be able to seize control from the
offboard system, and the PX4 parameter chain for this behavior must be configured and
tested on the bench before any outdoor flight. The documents correctly identify that this is a
PX4-level guarantee, not a software-level policy, which means it survives even if the Python
orchestrator crashes completely.

2.1.3 Offboard Heartbeat as Independent Subsystem................................................
The recognition that the offboard heartbeat must continue streaming even when the LLM is
blocked or slow is a critical architectural insight. FR 1.2 and FR 1.4 in the PRD explicitly
require that the heartbeat manager holds the last valid setpoint during LLM processing, and
the Technical Background recommends a dedicated asyncio task or background thread for
this purpose. This pattern of decoupling the safety-critical heartbeat from the variable-
latency LLM loop is essential for safe operation and should be implemented as a hard process
boundary, not a shared-thread cooperative multitasking arrangement.

2.1.4 Local-First Constraint
The insistence on running the LLM locally on the MacBook Pro rather than relying on cloud
APIs is a wise constraint that eliminates network latency, API rate limits, and connectivity
dependencies from the control loop. The documents correctly identify Ollama as the serving
framework and Llama 3 as the model family, and they acknowledge the memory and
performance implications of running inference alongside other processes on unified Apple
Silicon memory.

2.2 Critical Gaps and Oversimplifications
Despite the sound high-level thinking, the documents contain numerous gaps that, if left
unaddressed, will cause significant delays and potential safety incidents during
implementation. The following subsections detail the most consequential omissions and
oversimplifications, organized by subsystem.

2.2.1 MAVSDK-Python's gRPC Architecture Is Unmentioned
The most significant oversight across all three documents is the complete absence of any
mention that MAVSDK-Python is not a native Python MAVLink library. In reality,
MAVSDK-Python is a gRPC client wrapper around a C++ backend process called
mavsdk_server, which is automatically spawned when a System() object is created. Every
API call traverses two process boundaries (Python to gRPC to C++ to MAVLink) and two
IPC layers. This architecture introduces failure modes that a naive asyncio implementation
will not anticipate, including: silent connection failures where connect() returns without
error but the system never reports CONNECTED (GitHub Issue #133), indefinite hangs after
system discovery (Issue #759), inability to reconnect to a restarted mavsdk_server (Issue
#299), and critically, orphan mavsdk_server processes that continue sending setpoints even
after the Python script crashes (Issue #374). The last point is a safety issue of the highest
order: if the Python process dies, the orphaned C++ backend may continue commanding the
drone with no way to stop it from the Python side. The only mitigation is RC override or
battery failsafe. The documents treat MAVSDK-Python as a simple async library, which it
emphatically is not.

2.2.2 PX4 Offboard Requirements Are Underspecified
The documents mention that PX4 requires setpoints at 2Hz or higher and that streaming must
begin before entering offboard mode, but they miss several critical details. First, PX
requires both OffboardControlMode and TrajectorySetpoint messages to be streamed, not
just setpoints alone. Users on PX4 Discuss report immediate offboard-loss failsafes despite
receiving setpoint messages, because they were not also sending the control mode message.
Second, the pre-arm streaming requirement is at least one full second of continuous setpoints
before PX4 will allow arming in offboard mode, but the documents do not specify this exact
timing. Third, COM_OF_LOSS_T defaults to zero seconds, meaning PX4 executes the
offboard-loss failsafe immediately upon detecting a gap, with no grace period. Fourth, if RC
is not available and offboard is lost, the fallback action is controlled by COM_OBL_ACT
(not COM_OBL_RC_ACT), and these two parameters have different defaults and different
semantics. Fifth, the documents do not mention that SET_GPS_GLOBAL_INT is not a valid
offboard control message for PX4, which means any mission planning that uses GPS
coordinates must convert to local NED before sending setpoints.

2.2.3 Ollama Tool-Calling Reliability Is Assumed, Not Researched
The documents assume that Ollama's tool-calling feature works reliably with Llama 3 8B
and mention function-calling as a straightforward integration point. In reality, Ollama's tool-
calling has significant reliability issues that are well-documented across multiple GitHub
repositories and community forums. Malformed JSON in tool call arguments is an active,
unfixed issue (LangChain Issue #34746). Hallucinated tool parameters, where the model
invents values that do not match the provided schema, are reported in LiteLLM Issue #5617.
Multi-turn tool calling is described as completely broken for many Ollama models via the
native API (OpenClaw Issue #46679). Low memory conditions cause the model to fall back
from tool calling to text responses entirely (Ollama Issue #8344). These are not edge cases;
they represent fundamental reliability challenges that must be addressed with a robust
validation layer, JSON repair, retry logic, and potentially the use of purpose-built tool-
calling fine-tunes such as Llama 3 Groq Tool Use, which achieves 89% accuracy on the
Berkeley Function Calling Leaderboard versus significantly worse performance from
generic Llama 3.1 8B.

2.2.4 RPi Bridge Complexity Is Radically Simplified
The documents describe the RPi as a simple MAVLink bridge that routes UDP between PX
and the Mac, mentioning mavlink-router or MAVProxy as options without investigating
their real-world characteristics. MAVProxy is a Python-based ground control station with
60 - 90% CPU usage under load on constrained hardware, making it entirely unsuitable as a
headless embedded bridge. mavlink-router is the correct choice (C-based, 1-3% CPU), but
the documents miss the critical configuration details: USB autosuspend on the RPi can
silently kill serial connections to the Pixhawk, requiring kernel parameter changes; the RPi's
mini-UART has clock stability issues above 115200 baud that require dtoverlay
reconfiguration; and the Pixhawk's USB connection has a safety feature that prevents arming
when USB is connected by default, which means the production connection must use UART
(TELEM2) at 921600 baud, not USB. The documents mention both USB and UART as
options without clarifying that USB is only suitable for prototyping and UART is required
for flight.

2.2.5 fly_body_offset Is Far More Complex Than Presented
The tool schema includes fly_body_offset(forward_m, right_m, up_m), which requires
converting body-frame offsets to GPS coordinates. The documents do not address the
substantial challenges of this conversion. The transformation requires the current heading
from telemetry, but heading during GPS-only hover relies on magnetometer + gyroscope
fusion, which is susceptible to magnetic interference from the drone's own motors and ESCs.
A 5-degree heading error at a 20-meter forward offset produces a 1.74-meter lateral error.
Furthermore, MAVSDK-Python's offboard plugin does not expose a set_position_body()
API, meaning the conversion must either be done manually on the ground station (with the

attendant heading-error risks) or raw MAVLink messages must be sent with
MAV_FRAME_BODY_NED, which bypasses MAVSDK's high-level API and introduces
its own complexity. The documents treat this tool as a straightforward mapping from natural
language to coordinates, when in reality it is one of the most technically challenging tools in
the Stage 1 schema.

2.2.6 GPS-Only Navigation Limitations Are Handwaved
The documents acknowledge that Stage 1 uses only GPS, IMU, and barometer, but they do
not quantify the actual performance limitations. Consumer-grade GPS receivers such as the
u-blox NEO-M8N achieve 2.0-2.5 meter CEP in static, open-sky conditions, but dynamic
accuracy during drone flight is typically worse. GPS-only hover produces a characteristic
drift circle of 1-3 meters in calm wind and 3-5 meters in moderate wind, with a figure-8 or
circular oscillation pattern as the position controller continuously overcorrects. GPS velocity
(Doppler-based) is significantly more accurate than GPS position (0.05 m/s versus 2.5 m),
and PX4's EKF heavily weights GPS velocity for velocity estimation. However, GPS
accuracy degrades severely near buildings, trees, and at low altitudes due to multipath errors
that can introduce positioning errors of 5-15+ meters. The documents do not address these
limitations, their impact on the precision of goto_gps commands, or the implications for
body-frame offset calculations.

3. Subsystem Deep-Dive: MAVSDK-Python Async Architecture
3.1 The gRPC Split Architecture
MAVSDK-Python is architecturally distinct from what the source documents imply. Rather
than being a native Python MAVLink implementation, it is a gRPC client wrapper around a
C++ backend process called mavsdk_server. When a System() object is instantiated in
Python, the library spawns this backend process automatically. Every subsequent API call
follows the path: Python asyncio code, gRPC over localhost TCP to mavsdk_server, C++
MAVLink processing, and finally serial or UDP transmission to the flight controller. This
dual-process architecture introduces latency overhead (typically 1-3ms per call for the gRPC
hop) and, more critically, multiple independent failure domains that must be managed
explicitly.

3.2 Critical Failure Modes
3.2.1 Silent Connection Failure (GitHub Issue #133)
The drone.connect() coroutine can return successfully without raising an exception, yet the
connection_state() telemetry topic may never report a CONNECTED status. This occurs

because the gRPC backend's system discovery is asynchronous and completes independently
of the Python-side connect() call resolving. The implication is that any code that assumes
connection success after await drone.connect() without independently verifying connection
state is operating on an invalid assumption. The required pattern is to subscribe to
drone.core.connection_state() and wait for a CONNECTED callback with an explicit
timeout, treating the initial connect() call as merely the beginning of the discovery process.

3.2.2 Indefinite Hang After System Discovery (GitHub Issue #759)
The await drone.connect() call can hang indefinitely after the backend logs that a system has
been discovered. This is a race condition in the gRPC communication layer that was reported
as recently as April 2025 and remains a known issue. The mitigation is mandatory: every
connect() call must be wrapped in asyncio.wait_for() with a reasonable timeout (30 seconds
is recommended), and retry logic must be implemented to handle this condition. The Python
process must never block forever on a connect() call, as this would freeze the entire asyncio
event loop including the heartbeat task.

3.2.3 Orphan mavsdk_server Safety Hazard (GitHub Issue #374)
This is the single most dangerous finding in this brief. Once offboard.start() is called,
MAVSDK internally spawns a cothread within mavsdk_server that continuously resends the
last setpoint at 20Hz, independent of the Python process. If the Python script crashes after
offboard.start(), this cothread continues sending setpoints, preventing PX4's offboard-loss
failsafe from triggering. The drone will continue flying to the last commanded setpoint with
no ability to stop it from the Python side. The only mitigations are: RC override via
COM_OBL_RC_ACT, battery failsafe, or an external watchdog process that detects the
Python process death and kills the mavsdk_server process. This finding alone mandates that
RC must always be active and configured during offboard operations, and that a hardware-
level watchdog must be implemented as a distinct process from the MAVSDK application.

3.2.4 Telemetry Subscriptions Silently Stopping (GitHub Issue #321)
Telemetry subscriptions for position, attitude, battery, and other topics can silently stop
receiving updates at random times during flight. No exception is raised and no error callback
fires; the async iteration simply ceases to produce new values. This was reported in March
2021 and has not been definitively resolved. The suspected root cause is silent gRPC stream
breakage when the C++ backend encounters MAVLink parsing errors. The architectural
implication is that a telemetry health watchdog must be implemented that monitors the
freshness of received data and triggers a reconnection if data becomes stale. Relying on
passive subscription without active health monitoring is unsafe.

3.2.5 Blocking the Event Loop Produces Stale Telemetry
If any blocking operation (synchronous I/O, CPU-intensive computation, or an await that
does not yield) blocks the asyncio event loop, telemetry data queues up in the gRPC stream
and becomes stale. A user reported in May 2025 on PX4 Discuss that their telemetry was
slow and stale because a blocking call elsewhere in their code was preventing the event loop
from consuming telemetry data at the rate it was received. This means that every component
of the Stage 1 system that interacts with MAVSDK must be strictly non-blocking. Any CPU-
intensive work (LLM inference, JSON parsing, logging) must be offloaded to
asyncio.to_thread() or a separate process. This is particularly challenging because Ollama's
HTTP API is inherently blocking (HTTP request/response), and YOLO inference (in later
stages) is CPU/GPU-intensive.

3.3 Thread Safety and Event Loop Constraints
MAVSDK-Python's gRPC stubs are bound to the event loop that created them and cannot
be used from a different loop. This means that if the orchestrator uses a framework with its
own event loop (such as a web server for a dashboard), MAVSDK must run in the same loop
or use asyncio.run_coroutine_threadsafe() to schedule calls across loop boundaries. The
maintainer explicitly advises using a separate thread for blocking operations and
communicating with the main loop via run_coroutine_threadsafe(). The System() object
itself cannot be passed between processes, which means the MAVSDK client must run in a
single process. These constraints significantly shape the viable software architectures for the
orchestrator.

4. Subsystem Deep-Dive: PX4 Offboard Mode Constraints
4.1 Exact Entry Requirements
PX4 Offboard mode has exacting entry requirements that the source documents
underspecify. Before PX4 will allow arming in offboard mode or switching to offboard mode
while already flying, it requires continuous setpoint streaming for at least one full second.
During this pre-arm period, both the OffboardControlMode message and the
TrajectorySetpoint message must be streamed simultaneously. Sending only setpoint
messages without the control mode message is insufficient and will cause PX4 to reject the
mode switch with an immediate offboard-loss failsafe. The streaming rate must be
maintained at a minimum of 2Hz (500ms between messages), though a rate of 10-20Hz is
strongly recommended to provide margin for timing jitter. The correct operational sequence
is: first, set an initial setpoint via the chosen API; second, call offboard.start() to begin the
internal resender; third, wait at least one to two seconds to satisfy the pre-arm requirement;
fourth, arm the vehicle or switch to offboard mode.

4.2 Failsafe Chain and Parameter Configuration.............................................................
The PX4 offboard failsafe chain operates as follows. When the setpoint rate drops below
2Hz, PX4 waits COM_OF_LOSS_T seconds (default: 0, meaning immediate execution) and
then checks whether RC is available. If RC is available, it executes the action configured in
COM_OBL_RC_ACT. If RC is not available, it executes the action configured in
COM_OBL_ACT. These two parameters have different defaults: COM_OBL_RC_ACT
defaults to Position mode (value 0), while COM_OBL_ACT defaults to Land mode (value
4). The critical edge case is that setting COM_OBL_RC_ACT to Position mode when GPS
is marginal will cause the drone to attempt position mode without an adequate position
estimate, potentially leading to uncontrolled flight. For Stage 1, the recommended
configuration is COM_OBL_RC_ACT = 6 (Hold) and COM_OBL_ACT = 4 (Land), with
COM_OF_LOSS_T = 1 to provide a one-second grace period before failsafe execution.

Parameter Recommended
Value
Behavior Rationale
COM_OBL_RC_ACT 6 (Hold) Hold position when RC
available
Safest option with
RC in hand
COM_OBL_ACT 4 (Land) Descend and land when no
RC
Autonomous safe
recovery
COM_OF_LOSS_T 1 second Grace period before failsafe Tolerance for brief
jitter
NAV_RCL_EXCEPT 1 RC loss does not trigger
during offboard
Prevent RC-loss
failsafe conflicting
with offboard
NAV_DLL_ACT 3 (RTL) Return on data link loss Safe recovery for
Mac-WiFi
disconnection
4.3 GPS Degradation Impact on Offboard Mode
When GPS signal quality degrades below acceptable levels during offboard flight, PX4's
EKF detects the inconsistency between predicted and measured position through innovation
checks. If the innovations exceed the configured thresholds (controlled by
EKF2_GPS_CHECK and related parameters), the GPS is temporarily rejected, the position
estimate quality downgrades, and the Position Loss Failsafe fires. In offboard mode
specifically, this results in a blind land: the drone descends straight down using only
barometer and IMU data, with no horizontal position control. Critically, this happens even
if the system is sending velocity-only setpoints that do not strictly require GPS, because PX

requires a valid position estimate for offboard mode regardless of the setpoint type. The
architectural implication is that the orchestrator must monitor GPS health in real time
(satellite count, HDOP, fix type) and should preemptively switch to a safe mode before EKF
rejection occurs, rather than waiting for the failsafe to trigger.

4.4 Position vs. Velocity Setpoint Tradeoffs
For Stage 1 waypoint missions, position setpoints are the natural choice because the drone
automatically stops at the specified coordinate and PX4 applies internal trajectory
smoothing. However, users report high-jerk transitions between waypoints when using
position setpoints, particularly at closely-spaced waypoints. For the fly_body_offset tool
specifically, velocity setpoints in body frame may be more appropriate than position
setpoints in global frame, as they are more intuitive and less affected by position drift. The
tradeoff is that velocity setpoints require explicit zero-velocity commands to stop, and the
system must manage the transition from velocity-mode offsets back to position-mode
holding. This is an architectural decision that should be made during the initial
implementation phase, not discovered during integration testing.

5. Subsystem Deep-Dive: Raspberry Pi Serial Bridging
5.1 UART vs. USB: The Definitive Answer
After extensive research, the conclusion is unambiguous: UART via TELEM2 at 921600
baud is the only production-viable connection between the RPi and the Pixhawk. USB

appears simpler (plug-and-play, no wiring), but it carries three致命 liabilities. First, PX

prevents arming when a USB cable is connected by default (the ARMING_CHECK = USB
parameter), which is a safety feature designed to prevent accidental arming during bench
programming. While this can be disabled, doing so removes a safety layer. Second, USB
connections on the RPi are prone to random disconnects caused by the Linux kernel's USB
autosuspend power management, which can suspend the USB port and drop the serial
connection mid-flight. Third, USB CDC devices on the Pixhawk have higher latency and
lower reliability than dedicated UART connections because the USB stack adds overhead
and the cable acts as an antenna for EMI from the motors and ESCs.

UART via TELEM2 requires more initial setup (wiring, baud rate configuration, level
shifting considerations) but provides a connection that is architecturally superior in every
dimension for flight operations: lower and more consistent latency, no autosuspend risk, no
arming restriction, better EMI resistance with shielded twisted-pair wiring, and galvanic
isolation options. The RPi 4's GPIO UART operates at 3.3V, which matches the Pixhawk's
UART levels, eliminating the need for level shifters. However, the default mini-UART on

GPIO pins 14 and 15 has clock stability issues above 115200 baud because it uses a clock
derived from the VPU. To use 921600 baud, the system configuration must swap UART
(PL011, stable) and UART1 (mini-UART, unstable) via dtoverlay=disable-bt in config.txt.

5.2 mavlink-router as the Bridge Daemon.....................................................................
mavlink-router is a lightweight C daemon specifically designed for routing MAVLink
between serial ports and network endpoints. Its CPU usage on RPi 4 is 1-3%, compared to
MAVProxy's 60-90% under load. It should be configured as a systemd service that starts
automatically on boot, connecting to the Pixhawk via UART and exposing a UDP endpoint
for the Mac. A typical configuration routes the serial connection at 921600 baud to a local
UDP endpoint on port 14540 (for the Mac's MAVSDK connection) and optionally to port
14550 (for QGroundControl monitoring). mavlink-router has no built-in message filtering,
meaning all MAVLink messages from the Pixhawk are forwarded to all endpoints. This is
acceptable for Stage 1 (telemetry bandwidth is low) but may become a concern when high-
rate streams are added in later stages.

5.3 RPi Power and Thermal Considerations
The RPi 4 requires 5V at 3A minimum, and undervoltage causes USB disconnects, SD card
corruption, and WiFi instability. Power must be supplied from a dedicated BEC on the flight
controller's power bus, with an LC filter to reduce ripple from the motor ESCs. The BEC
output must be clean enough to avoid introducing noise into the RPi's ADC and USB circuits.
Thermally, the RPi 4 begins throttling at 80 degrees Celsius, with CPU frequency dropping
to 1.5GHz (soft throttle) and then to 1.0GHz (hard throttle) at 85 degrees. On a drone with
limited natural convection, direct sunlight plus mavlink-router processing can push
temperatures into the throttle zone. An aluminum heatsink case oriented to receive prop-
wash airflow is the minimum thermal management strategy.

6. Subsystem Deep-Dive: Ollama Local Function Calling
6.1 Model Selection for Tool-Calling Reliability
The source documents specify Llama 3 served via Ollama but do not differentiate between
model variants for tool-calling performance. This distinction is critical. Generic Llama 3.
8B has moderate tool-calling capability with significant variability. The purpose-built Llama
3 Groq Tool Use variant (available in 8B and 70B sizes) achieves 89.06% accuracy on the
Berkeley Function Calling Leaderboard, making it the highest-accuracy 8B tool-calling
model available on Ollama. For a robotics application where malformed tool calls can
command physical actuators to dangerous positions, this 20-30% accuracy improvement

over generic models is not merely a quality-of-life enhancement but a safety requirement.
The Stage 1 implementation should use llama3-groq-tool-use:8b as the primary model and
fall back to generic Llama 3.1 only for non-flight-critical reasoning tasks.

6.2 Quantization Impact on Tool-Calling Fidelity
Quantization level directly affects the reliability of structured output, and the documents do
not address this tradeoff. Research on LLaVA-1.5-7B quantization reveals that Q4_K_M
produces a bimodal quality distribution where some tasks score near-perfect while others
score near-zero, a pattern that is particularly dangerous for safety-critical structured output
where consistency is paramount. Q5_K_M represents the minimum acceptable quantization
for tool-calling in safety-critical applications, with Q8_0 preferred if memory allows. On a
MacBook Pro with 18GB unified memory, Q5_K_M consumes approximately 5.7GB for
the model weights plus 2-8GB for the KV cache depending on context length, leaving
sufficient memory for YOLO and MAVSDK processes. Q4_K_M should be categorically
rejected for any command that controls physical actuators.

Quantization Memory (8B) JSON Validity Tool Call Quality Recommendation
Q4_K_M ~4.9 GB 85 - 92% Bimodal -
dangerous
Reject for flight
commands
Q5_K_M ~5.7 GB 90 - 95% Good Minimum for
safety-critical
Q8_0 ~8.5 GB 95 - 98% Very Good Preferred if memory
allows
F16 ~16 GB 97 - 99% Best Too large for
concurrent
processes
6.3 Mandatory Validation Architecture
Given the documented reliability issues with Ollama's tool-calling (malformed JSON,
hallucinated parameters, multi-turn breakage, memory-dependent failure), the orchestrator
must implement a multi-layer validation architecture between LLM output and actuator
command execution. The first layer is a JSON repair library (such as json_repair in Python)
that attempts to fix common formatting errors before schema validation. The second layer is
strict JSON Schema validation that rejects any tool call with unknown tool names, missing
required parameters, out-of-range values, or incorrect types. The third layer is a semantic
safety validator that checks parameter values against hard limits (maximum altitude,
maximum distance, geofence boundaries) regardless of what the LLM requested. If any layer

fails, the error must be fed back to the LLM with the original tools and conversation context
for a retry, up to a maximum of three attempts. After three failed attempts, the system must
default to a safe state (hold position, request human clarification) rather than executing a
potentially malformed command.

6.4 Performance on M3 MacBook Pro Under Concurrent Load
Apple Silicon uses unified memory shared between CPU, GPU (Metal), and Neural Engine.
Ollama running Llama 3 8B at Q5_K_M consumes approximately 5.7GB for model weights
plus 2-8GB for the KV cache. Running concurrently with YOLOv8-nano (~0.5-1GB GPU
memory) and MAVSDK (~0.2-0.5GB) on an 18GB MacBook Pro leaves approximately 3-
7GB of headroom, which is tight but workable if the Ollama context is kept small (4096-
8192 tokens instead of the full 128K context). A typical tool call response of 50-200 tokens
takes 1.5-7 seconds for generation on M3 Pro. With tool validation and retry, worst-case
latency per command is 10- 30 seconds. This is acceptable for Stage 1's high-level mission
planning but reinforces that the LLM must never be in the control loop for time-critical
operations. Temperature must be set to 0 for deterministic tool calling, and repeat_penalty
should be 1.1-1.2 to prevent repetitive tool-call loops.

7. Boundary Analysis: Mac-RPi-Pixhawk Communication Chain
7.1 Latency Budget and Packet Loss
The end-to-end communication chain from Mac to Pixhawk traverses three hops: Mac to
RPi over WiFi UDP, RPi internal processing by mavlink-router, and RPi to Pixhawk over
UART. Measured latencies for each hop are: WiFi UDP at 1-5ms (LAN), mavlink-router
processing at under 0.1ms, and UART at 115200 baud approximately 1-3ms per MAVLink
message. The total bridge latency is typically 3-15ms, which is well within PX4's 2Hz
(500ms) requirement for offboard setpoints. However, WiFi UDP packet loss of 5-10% is
common during outdoor operations due to interference, line-of-sight obstruction, and
antenna orientation changes during flight. MAVLink is designed to tolerate some packet loss
through sequence-number-based detection, but excessive losses cause heartbeat timeouts,
dropped setpoints triggering offboard failsafe, and telemetry gaps. The most dangerous
failure mode is not total link loss (which triggers well-defined failsafes) but intermittent
high-loss that causes the setpoint stream to drop below 2Hz without triggering a data-link-
loss failsafe.

7.2 WiFi Configuration Requirements
The RPi 4's internal WiFi antenna has limited range (approximately 100m in open air) with
no external connector. For outdoor drone operations, the WiFi configuration must be
carefully optimized. The 5GHz band is strongly preferred over 2.4GHz due to less crowding
and fewer interference sources in outdoor environments. The Mac should create the WiFi
hotspot with the RPi as a client, rather than the RPi acting as an access point, to avoid the
RPi managing WiFi association overhead during flight. WiFi power management must be
disabled (iwconfig wlan0 power off) to prevent power-saving mode from adding latency
spikes. Channel selection should use channels 36-64 (low 5GHz UNII-1 band) which are
DFS-free and typically less congested. The RPi should be configured with a static IP address
to avoid DHCP delays during boot. If operations extend beyond approximately 100m, a USB
WiFi adapter with an external high-gain antenna is required.

7.3 The Video-MAVLink Contention Problem
Although video streaming is a Stage 2 concern, the Stage 1 architecture must account for the
bandwidth contention that will arise when video and MAVLink share the same WiFi link.
MAVLink telemetry consumes 1-5 KB/s, which is negligible on its own. Video streaming
at even modest quality consumes 2-30 Mbps. The RPi 4's internal WiFi ceiling is
approximately 50-100 Mbps in practice, meaning video can easily saturate the link and cause
MAVLink telemetry to experience packet loss and increased jitter. The Stage 1 architecture
should either plan for a separate communication channel (such as a 433MHz radio link for
MAVLink with WiFi dedicated to video) or implement QoS prioritization that ensures small
MAVLink packets are transmitted ahead of video frames. This is an architectural decision
with hardware budget implications that must be made in Stage 1, not retrofitted in Stage 2.

8. GPS-Only Navigation: Performance Realities
8.1 Accuracy and Drift Characteristics
Consumer-grade GPS receivers such as the u-blox NEO-M8N achieve 2.0-2.5 meter circular
error probable (CEP) in static, open-sky conditions with GPS and GLONASS. Vertical
accuracy is approximately 3.0-4.5 meters. GPS velocity, derived from Doppler shift of the
carrier signal, is dramatically more accurate at approximately 0.05 m/s. During hover, GPS-
only position control produces a drift circle of 1 - 3 meters in calm wind and 3-5 meters in
moderate wind, with a characteristic oscillation pattern as the position controller
continuously overcorrects for GPS measurement noise. The position estimate quality
degrades substantially near buildings, trees, and at low altitudes due to multipath errors: 4- 8
meters under light tree cover, 5-15+ meters in urban canyons, and potential complete fix loss
under dense canopy. PX4's EKF2 fuses GPS position and velocity with IMU data, heavily
weighting GPS velocity for velocity estimation while using GPS position primarily to correct

accumulated IMU drift. When GPS quality degrades, EKF2 innovation checks may
temporarily reject GPS, causing the position estimate to degrade to IMU-only drift rates of
meters per second.

8.2 Implications for Stage 1 Tool Design
The GPS accuracy limitations have direct implications for every tool in the Stage 1 schema.
goto_gps commands are only as accurate as the GPS itself, meaning a goto to a specific
latitude/longitude will arrive within approximately 2-3 meters of the target in ideal
conditions, not at the exact coordinate. fly_body_offset commands accumulate heading-
dependent lateral errors proportional to the offset distance. The hold() command will not
produce a stationary hover but rather a 1-3 meter drift circle. The land() command will land
at the current GPS position, which may be several meters from the intended landing point.
These are not software bugs but physical realities of GPS-only navigation. The orchestrator
should set realistic expectations in the LLM's system prompt, and the validation layer should
not reject commands that are within the achievable accuracy envelope.

9. Consolidated Risk Matrix
The following matrix consolidates all identified risks, their severity, likelihood, and
recommended mitigations. Risks are ordered by a composite severity score that considers
both impact and probability.

Risk Severity Likelihood Mitigation
Orphan mavsdk_server
continues commanding
drone after Python crash
Critical Medium External watchdog process + RC always
active
LLM hallucinates tool call
with dangerous parameters
Critical High Multi-layer validation + semantic safety
bounds
WiFi dropout causes
offboard failsafe mid-
mission
High Medium COM_OF_LOSS_T grace period + heartbeat
on RPi
Ollama malformed JSON
blocks command execution
High High JSON repair library + retry with error
feedback
GPS multipath near
buildings causes erratic
flight
High Medium Pre-flight GPS quality check + HDOP
monitoring
RPi USB serial disconnect
from autosuspend
High Medium Use UART not USB + disable autosuspend
in kernel
Risk Severity Likelihood Mitigation
Multi-turn Ollama tool
calling breaks agent loop
Medium High Limit to single-shot tool calls where possible
Heading error corrupts
body-frame offset
Medium Medium Limit offset distance to <10m + compass
calibration
Thermal throttling on RPi
causes latency spikes
Medium Low Heatsink + prop-wash orientation + mavlink-
router
Memory pressure from
concurrent Ollama + YOLO
Medium Medium Small context window + KV cache
quantization
Video+MAVLink WiFi
contention in Stage 2
Medium High Separate radio link or QoS prioritization
RPi power brownout from
insufficient BEC
High Low Dedicated 5V/3A BEC + LC filter
10. Architectural Recommendations for Stage 1
10.1 Recommended Hardware Architecture
The Pixhawk-to-RPi connection must use UART (TELEM2) at 921600 baud, not USB. The
RPi must run mavlink-router as a systemd service for the MAVLink bridge, not MAVProxy.
The Mac connects to the RPi via WiFi UDP on port 14540. QGroundControl connects on
port 14550 for monitoring. RC is always active during offboard operations. A dedicated
5V/3A BEC with LC filtering powers the RPi from the flight battery. An aluminum heatsink
with prop-wash orientation provides thermal management.

10.2 Recommended Software Architecture
The orchestrator must run as a single Python asyncio process on the Mac. MAVSDK-Python
connects to the RPi's UDP endpoint. The offboard heartbeat runs as a dedicated asyncio task
with a shared current_target state variable. The LLM agent runs in a separate thread or
process, communicating with the main loop via thread-safe queues. All MAVSDK calls must
be wrapped in asyncio.wait_for() with timeouts. A connection health watchdog monitors
telemetry freshness and triggers reconnection on stale data. An external watchdog process
monitors the main Python process and kills mavsdk_server on crash. Signal handlers
(SIGTERM, SIGINT) must implement graceful shutdown: stop offboard, land or RTL, close
connections, kill orphan processes.

10.3 Revised PX4 Parameter Configuration
The following PX4 parameters must be configured before any Stage 1 outdoor flight:
COM_OBL_RC_ACT = 6 (Hold when RC available), COM_OBL_ACT = 4 (Land when
no RC), COM_OF_LOSS_T = 1 (1-second grace period), SERIAL2_PROTOCOL = 1
(MAVLink 2 on TELEM2), SERIAL2_BAUD = 921600, NAV_RCL_EXCEPT = 1 (RC
loss exception during offboard), NAV_DLL_ACT = 3 (RTL on data link loss), and
CBRK_SUPPLY_CHK = 894416 or equivalent to disable USB supply check if using USB
for prototyping. All failsafe behaviors must be tested on the bench (no props) before any
outdoor flight, simulating: offboard heartbeat stop, GPS disconnect, RC loss, and low
battery.

10 .4 LLM Integration Recommendations
The model selection should prioritize llama3-groq-tool-use:8b over generic Llama 3.1 for
its superior tool-calling accuracy. Quantization should be Q5_K_M minimum, with Q8_
preferred. Temperature must be 0 for deterministic output. The context window should be
kept at 4096-8192 tokens to reduce memory pressure. The tool count should not exceed 10
tools for an 8B model. The system prompt must include explicit negative instructions (only
use provided tools, never invent new tools or parameters). Few-shot examples of correct tool
calls should be included in the system prompt. A mandatory JSON repair and schema
validation layer must sit between LLM output and command execution, with a maximum of
three retries before defaulting to a safe state.

10.5 fly_body_offset Implementation Strategy
The fly_body_offset tool should be implemented using MAV_FRAME_BODY_NED in
raw MAVLink SET_POSITION_TARGET_LOCAL_NED messages, allowing PX4 to
perform the body-to-global frame rotation internally rather than performing the conversion
on the ground station. This avoids the heading-error problem entirely. However, this requires
sending raw MAVLink messages outside of MAVSDK's high-level offboard API, which
adds complexity. An alternative approach is to limit body-frame offset distances to less than
10 meters (where heading-induced lateral error is manageable at approximately 1 meter) and
perform the conversion on the ground station using the most recent heading from telemetry.
Regardless of approach, the heading estimate quality should be monitored in real time, and
body-frame offset commands should be rejected if compass health degrades.

10.6 Forward-Looking Architectural Awareness
While this brief is strictly scoped to Stage 1, the architecture must be designed with
awareness of the precision endgame. The control spine built in Stage 1 will carry forward
through all subsequent stages. Key forward-looking considerations include: the command
validation layer should be designed as a pluggable pipeline that can accommodate new tool

types (depth-gated commands, payload commands) without structural changes; the telemetry
architecture should support additional data streams (video, depth) without disrupting the
heartbeat loop; and the LLM agent's context management should be designed to
accommodate the state string expansion that comes with vision and depth integration. The
most important forward-looking decision is ensuring that the offboard heartbeat is absolutely
decoupled from the LLM loop at the process level, not the thread level, so that adding
computationally expensive vision processing in Stage 2 cannot interfere with the safety-
critical heartbeat.
