# Project Avatar: Decision Log

**Purpose**: Maintain an auditable trail of all architectural and design decisions for this drone system.

**Format**: Each decision includes context, options considered, decision made, rationale, trade-offs, and consequences.

---

## Table of Contents

- [Safety & Failsafe](#safety--failsafe)
- [Architecture & Control](#architecture--control)
- [LLM & AI Integration](#llm--ai-integration)
- [Vision & Perception](#vision--perception)
- [Software & Implementation](#software--implementation)
- [Hardware & Physical](#hardware--physical)
- [Marketplace & Procurement](#marketplace--procurement)

---

## Safety & Failsafe

### DEC-001: 4-Layer Safety Architecture [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Architecture defined, GuardianProcess specified, documented in safety hierarchy

**Context**: LLM-controlled drones require multiple independent safety layers to prevent AI errors from causing physical harm.

**Options Considered**:
1. Single-layer safety (LLM only) — ❌ Rejected: Too risky
2. 2-layer (PX4 + LLM) — ❌ Rejected: No intermediate validation
3. **4-layer hierarchy** — ✅ Selected

**Decision**: Implement 4-layer safety: PX4 Hard Reflexes (<100ms) → Guardian Process (~10ms) → LLM Reactions (1-3s) → Operator Override (RC)

**Rationale**:
- Defense in depth: Multiple independent checks
- Latency-appropriate: Faster layers handle emergencies
- Human override: Ultimate authority always available
- Fail-secure: Lower layers default to safe state

**Trade-offs**:
- Increased system complexity
- More code to maintain
- Higher resource usage on companion computer

**Consequences**:
- GuardianProcess class must validate all LLM commands
- Hard limits defined as immutable configuration
- Operator RC transmitter has kill switch capability

**Related**: See `02-safety-failsafe/failsafe_hierarchy.md`

---

### DEC-002: PX4 Parameter Configuration for Safety [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Parameter set defined, ready for SITL and hardware configuration

**Decision**: Configure PX4 with conservative failsafe parameters:

```yaml
COM_OBL_RC_ACT: 3        # RTL on offboard loss
COM_OF_LOSS_T: 0.5       # 500ms timeout (2Hz minimum)
GF_MAX_HOR_DIST: 500     # Geofence: 500m from home
GF_MAX_VER_DIST: 120     # Geofence: 120m altitude
BAT_CRIT_THR: 0.20       # RTL at 20% battery
BAT_EMERGEN_THR: 0.15    # Land at 15% battery
```

**Rationale**: These values provide safe margins for VLOS (Visual Line of Sight) operations while maintaining operational flexibility.

**Consequences**: Drone will RTL if:
- Offboard setpoints stop for >500ms
- Distance from home exceeds 500m
- Altitude exceeds 120m AGL
- Battery drops below thresholds

---

### DEC-003: Heartbeat Location on RPi (Not Mac) [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Architecture decision documented, asyncio patterns defined

**Context**: Where should the 20Hz offboard heartbeat run?

**Options Considered**:
1. Run heartbeat on Mac, send via WiFi to RPi → MAVSDK → PX4
2. **Run heartbeat on RPi directly** — ✅ Selected

**Decision**: Heartbeat MUST run on Raspberry Pi, not Mac/ground station.

**Rationale**: If WiFi drops while heartbeat runs on Mac:
- Setpoints stop reaching PX4
- COM_OF_LOSS_T (500ms) triggers
- Drone enters failsafe → falls

**Trade-offs**:
- More complex software architecture on RPi
- Harder to debug (no direct logs on Mac)
- Requires reliable RPi software

**Consequences**:
- Asyncio priority scheduler must ensure heartbeat never blocked
- GuardianProcess runs on RPi
- Mac runs high-level mission planning only

**Related**: See `03-software-architecture/python_asyncio_patterns.md`

---

## Architecture & Control

### DEC-004: MAVSDK-Python Over ROS2 [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - MAVSDK-Python selected, all development proceeding with this SDK

**Context**: Need to choose drone SDK for PX4 control.

**Options Considered**:

| Option | Latency | Complexity | Ecosystem | Decision |
|--------|---------|------------|-----------|----------|
| ROS2 | 7.1ms | High | Large | ❌ Rejected |
| **MAVSDK-Python** | **2.8ms** | **Low** | Moderate | ✅ Selected |

**Decision**: Use MAVSDK-Python instead of ROS2.

**Rationale**:
1. **Lower Latency**: 2.8ms vs 7.1ms (2.5x faster control loop)
2. **Simpler Architecture**: Direct asyncio, no ROS2 middleware
3. **Less Overhead**: No DDS, no node graph, smaller memory footprint
4. **Direct Control**: MAVSDK → MAVLink → PX4 (no intermediate layers)

**Trade-offs Accepted**:
- Smaller ecosystem than ROS2
- Less industry standard (ROS2 more common in research)
- Fewer off-the-shelf packages

**Consequences**:
- All drone control code uses MAVSDK-Python asyncio API
- No ROS2 dependencies in project
- Must implement any needed ROS2-equivalent functionality ourselves

**Related**: See `01-core-project/ros2_vs_mavsdk.md`

---

### DEC-005: Three-Stage Development Roadmap [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Roadmap defined, currently executing Stage 1 (Control Spine) via Phase 0.5

**Decision**: Build system in three sequential stages:

```
Stage 1: Control Spine (GPS-only navigation)
  └── Goal: Reliable offboard control, hover, waypoint following
  └── Duration: 4-6 weeks
  └── Hardware: RPi 4, Pixhawk, basic telemetry

Stage 2: Vision System (Person detection + tracking)
  └── Goal: Real-time person detection, follow mode, orbit
  └── Duration: 6-8 weeks
  └── Hardware: + Pi Camera Module 3 Wide

Stage 3: Depth & Payload (Obstacle avoidance, gimbal)
  └── Goal: Indoor navigation, advanced shots, payload delivery
  └── Duration: 8-10 weeks
  └── Hardware: + OAK-D-Lite, gimbal
```

**Rationale**: Staged approach allows validation at each layer before adding complexity. Stage 1 must be bulletproof before adding vision.

**Consequences**:
- Current focus: Stage 1 only
- Vision code exists but integration deferred
- Hardware purchases staged to match development

**Related**: See `01-core-project/implementation_roadmap.md`

---

## LLM & AI Integration

### DEC-015: Kimi K2.5 via Fireworks AI (Cloud LLM) [DECIDED]

**Date**: 2026-04-11

**Status**: DECIDED - Architecture approved, implementation pending Phase 0.5 integration

**Context**: Original plan used local Llama 3 8B on MacBook M3 16GB, but this provides only ~25-40 tok/s with limited reasoning capability. Need faster inference with better vision and tool-calling reliability.

**Options Considered**:
1. **Local Llama 3 8B** — ❌ Rejected: 7B model insufficient for spatial navigation, multimodal interpretation, and reliable tool calling
2. **Local larger model (70B)** — ❌ Rejected: Doesn't fit in 16GB MacBook memory
3. **Kimi K2.5 via Fireworks AI** — ✅ Selected: 200 tok/s, native multimodal, frontier reasoning

**Decision**: Replace local LLM with Kimi K2.5 via Fireworks AI API.

**Configuration**:
```python
client = openai.OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=api_key
)
model = "accounts/fireworks/models/kimi-k2-5"
```

**Rationale**:
- **Speed**: 200 tok/s vs 25-40 tok/s (8x faster)
- **Capability**: Frontier model with better reasoning for navigation decisions
- **Multimodal**: Native vision support—can analyze drone camera frames directly
- **Tool Calling**: Dramatically more reliable than 7B local models
- **Cost**: ~$0.80-1.00/1M tokens = ~$0.10 per 15-min flight (negligible)

**Trade-offs**:
- **Cloud dependency**: Requires internet connectivity via phone cellular data
- **Latency**: 1-2s round-trip vs local inference
- **Privacy**: Video frames sent to cloud API
- **Offline limitation**: Cannot fly missions without connectivity (acceptable for Phase 1)

**Mitigations**:
- 20Hz heartbeat on RPi continues regardless of LLM connectivity
- Graceful degradation: pause mission if cloud unavailable
- Phone cellular provides reliable connectivity
- Local YOLO continues detecting even if cloud drops

**Consequences**:
- All LLM inference moved to cloud API
- MacBook runs YOLO + API client only (no model loading)
- Must handle API failures and timeouts gracefully
- 128K context window supports full flight history

**Related**: Supersedes NFR 5.3.1 (Local LLM Required) for core autonomy

---

### DEC-016: Agent-Agnostic MCP Server Architecture [IMPLEMENTING]

**Date**: 2026-04-11

**Status**: IMPLEMENTING - Server architecture defined, tools specified, development in progress

**Context**: User wants to control drone through natural language via AI agents, but needs the system to work with ANY MCP-compatible agent (OpenCode/Sisyphus, Hermes, OpenClaw, Claude Desktop, etc.), not be locked to a specific platform.

**Options Considered**:
1. **Direct Python scripts** — ❌ Rejected: No chat interface, requires technical knowledge
2. **Web UI** — ❌ Rejected: Separate interface, context switching
3. **Agent-specific integration (OpenCode only)** — ❌ Rejected: Vendor lock-in, not portable
4. **Agent-agnostic MCP Server** — ✅ Selected: Works with any MCP-compatible agent

**Decision**: Build **agent-agnostic Model Context Protocol (MCP) server** that exposes drone control tools to ANY LLM agent supporting MCP.

**Architecture**:
```
User → Any MCP Agent (OpenCode, Hermes, Claude, etc.) → Drone MCP Server → Kimi K2.5 (optional) → MAVLink → Drone
                                        ↓
                                   GuardianProcess
```

**Design Principles**:
- **Agent Agnostic**: Works with any MCP-compatible client
- **LLM Agnostic**: Can use Kimi, GPT-4, Claude, or local models
- **Portable**: Same server works across different agent platforms
- **Standard Protocol**: Uses official MCP specification

**MCP Server Tools** (exposed to any agent):
- `arm_and_takeoff(altitude_m: float)`
- `goto_gps(lat: float, lon: float, alt_m: float, speed_ms: float = 5.0)`
- `set_velocity(vx: float, vy: float, vz: float, yaw_rate: float = 0.0)`
- `fly_body_offset(forward_m: float, right_m: float, up_m: float)`
- `hold_position(seconds: float = 0.0)`
- `land()`
- `rtl()`  // Return to Launch
- `capture_frame() → Image`  // For multimodal LLMs
- `get_telemetry() → TelemetryData`
- `abort_mission(reason: str)`
- `get_mission_status() → MissionState`
- `plan_mission(natural_language_request: str) → MissionPlan`

**Rationale**:
- **Portability**: Works with any MCP-compatible agent (Claude Desktop, OpenCode, Hermes, OpenClaw, etc.)
- **Future-proof**: Not tied to specific vendor
- **Interoperability**: Standard protocol enables ecosystem compatibility
- **Flexibility**: User can switch agents without changing drone software
- **Decoupled**: Drone logic separate from agent implementation

**Trade-offs**:
- Requires MCP server implementation
- Agents must support MCP protocol
- Slightly more complex than direct integration

**Mitigations**:
- MCP SDKs available for Python, TypeScript, etc.
- Well-documented protocol with growing ecosystem
- Can provide wrapper scripts for non-MCP agents

**Consequences**:
- Implement `drone_mcp_server` using official MCP SDK
- JSON schemas define tool interfaces (agent-agnostic)
- GuardianProcess validates all commands before execution
- Agent handles conversation flow; server handles drone control
- Can support multiple simultaneous agent connections (if needed)

**Agent Examples**:
| Agent | MCP Support | Usage |
|-------|-------------|-------|
| Claude Desktop | ✅ Native | `claude mcp add drone-server` |
| OpenCode | ✅ Via skills | Skill configuration |
| Hermes | ✅ Planned | Configuration file |
| OpenClaw | ✅ Planned | MCP connector |
| Custom scripts | ✅ Via SDK | Python MCP client |

**Related**: See `03-software-architecture/mcp_server_design.md`

---

### DEC-021: Code Documentation (Comprehensive Comments)

**Date**: 2026-04-12

**Context**: As the codebase grows with MCP server, vision pipeline, and safety systems, maintaining code clarity is critical. Future maintainers (including ourselves) need to understand not just WHAT the code does, but WHY architectural choices were made.

**Options Considered**:
1. **Minimal comments** — ❌ Rejected: Code intent unclear, hard to onboard new contributors
2. **Docstrings only** — ❌ Rejected: Insufficient for complex async/mission logic
3. **Comprehensive comments** — ✅ Selected: Every non-trivial block explained

**Decision**: All code must include comprehensive comments covering:
- **Function docstrings**: Purpose, args, returns, raises, examples
- **Module headers**: Overview, architecture context, key classes/functions
- **Inline comments**: WHY not WHAT (explain intent, not mechanics)
- **Decision references**: Link to DEC-XXX when implementing architecture decisions
- **TODO/FIXME markers**: Tracked issues with context

**Comment Standards**:
```python
# Good: Explains intent and reasoning
# Heartbeat MUST run on RPi, not Mac. If WiFi drops while heartbeat
# runs on Mac, COM_OF_LOSS_T (500ms) triggers failsafe → drone falls.
# See DEC-003 for full rationale.
async def heartbeat_loop(drone: System) -> None:

# Bad: States the obvious
# This function sends heartbeat messages
async def heartbeat_loop(drone: System) -> None:
```

**Rationale**:
- **Knowledge preservation**: Prevents loss of context during team transitions
- **Safety critical**: Drone code requires understanding safety implications
- **Async complexity**: Coroutine flows are non-obvious without explanation
- **Onboarding speed**: New contributors can understand codebase in days not weeks

**Trade-offs**:
- Slightly more time spent writing code
- Comment maintenance burden when refactoring
- Risk of comment/code drift if not updated

**Mitigations**:
- Code review checks comment quality
- Self-documenting naming conventions reduce comment needs
- Link to DECISIONS.md for architectural context (single source of truth)

**Consequences**:
- All modules have header comments explaining purpose
- All public functions have Google-style docstrings
- Inline comments explain non-obvious logic and safety implications
- Complex async flows documented with sequence comments

**Related**: See DEC-003, DEC-007, DEC-009 for referenced decisions

---

### DEC-022: Cinematic Shots Implementation

**Date**: 2026-04-12

**Context**: Project Avatar needs to capture professional-quality aerial footage. Cinematic shots require precise coordinated movement of both drone and gimbal, with smooth motion profiles that are difficult to achieve with manual control.

**Options Considered**:
1. **Manual piloting via RC** — ❌ Rejected: Requires skilled pilot, inconsistent results
2. **Pre-programmed waypoints** — ❌ Rejected: Too rigid, no subject tracking
3. **LLM-orchestrated cinematic primitives** — ✅ Selected: Natural language to cinematic shots

**Decision**: Implement cinematic shot primitives as MCP tools that Kimi can orchestrate:

**Shot Types**:
| Shot | Description | Parameters |
|------|-------------|------------|
| `orbit(subject, radius, speed)` | Circle around subject | radius_m, altitude_m, speed_deg/s, direction (cw/ccw) |
| `dolly_zoom(subject, start_dist, end_dist)` | Vertigo effect | start_m, end_m, altitude_m, duration_s |
| `reveal(subject, start_offset, end_pos)` | Uncover subject | start_offset_m, end_pos (orbit/above/side), speed_m_s |
| `follow(subject, distance, height)` | Track moving subject | distance_m, height_m, lead_distance_m |
| `spiral(subject, start_radius, end_radius, rotations)` | Ascending/descending spiral | start_r, end_r, rotations, direction |
| `crane(subject, start_alt, end_alt, distance)` | Vertical reveal | start_alt_m, end_alt_m, distance_m |

**Implementation Architecture**:
```
User: "Orbit the cabin at 30m with slow cinematic speed"
↓
Kimi parses → `orbit(subject="cabin", radius=30, speed=10)`
↓
MCP Server validates parameters through GuardianProcess
↓
Trajectory generator creates smooth motion profile
↓
Waypoint follower executes with gimbal synchronization
↓
Telemetry feedback adjusts for wind/position errors
```

**Motion Profiles**:
- All movements use s-curve acceleration (smooth jerk-free motion)
- Gimbal pitch/yaw synchronized with drone movement
- Speed limits enforced by GuardianProcess hard limits
- Emergency abort maintains shot continuity if possible

**Rationale**:
- **Professional output**: Smooth, repeatable cinematic shots
- **Natural language**: "Orbit slowly" → precise motion
- **Safety**: GuardianProcess validates all trajectories before execution
- **Composable**: Shots can be chained (orbit → dolly zoom → follow)

**Trade-offs**:
- Complex trajectory planning required
- Subject tracking needs vision integration (Stage 2)
- Wind compensation affects shot smoothness

**Consequences**:
- `cinematic_shot()` MCP tool with shot type enum
- TrajectoryGenerator class for motion profiles
- Gimbal synchronization module (Stage 3)
- Shot templates in mission planning system

**Related**: To be implemented in Stage 2 (vision) and Stage 3 (gimbal)

---

### DEC-017: Hybrid Vision Architecture (YOLO + Kimi Frames) [DECIDED]

**Date**: 2026-04-11

**Status**: DECIDED - Architecture approved, deferred to Stage 2 (Vision System)

**Context**: Need to balance real-time detection with LLM vision capabilities. Sending every frame to Kimi is expensive and slow; using only local YOLO limits LLM situational awareness.

**Options Considered**:
1. **All frames to Kimi** — ❌ Rejected: High cost, 1-2s latency per frame, impractical
2. **YOLO only, no Kimi vision** — ❌ Rejected: LLM lacks visual context for decisions
3. **Hybrid approach** — ✅ Selected: YOLO for real-time detection + selective frames to Kimi

**Decision**: Implement hybrid vision pipeline:

```
Camera Stream (30 FPS)
    ↓
Frame Sampling (every 3rd frame = 10 FPS for YOLO)
    ↓
YOLOv8-nano on Mac (80ms inference)
    ↓
State String generated (every 1-2s)
    ↓
├─→ Kimi receives State String (text telemetry + detections)
│
└─→ Selective frames sent to Kimi:
    - Every 3-5 seconds (continuous monitoring)
    - On-demand when YOLO detects people
    - When Kimi requests "show me current view"
    - When entering new mission phase
```

**Rationale**:
- YOLO provides real-time detection (10-15 FPS) locally
- Kimi gets periodic visual context without overwhelming API
- On-demand frames for critical decisions
- Cost-effective: ~$0.10/flight vs $5+/flight for continuous streaming

**Trade-offs**:
- 3-5s gap between visual updates to Kimi
- LLM may miss fast-moving events between frames
- More complex orchestration logic required

**Consequences**:
- `capture_frame()` tool for on-demand snapshots
- Frame buffer management in orchestrator
- Vision pipeline produces both State String (fast) and frame captures (slow)
- Kimi must handle stale frame context appropriately

---

### DEC-018: Progressive Confirmation Workflow [DECIDED]

**Date**: 2026-04-11

**Status**: DECIDED - Workflow specified, implementation pending MCP server completion

**Context**: User wants confirmation before executing missions, but workflow needs to balance safety with usability. Too many interruptions are annoying; too few are dangerous.

**Options Considered**:
1. **Pre-flight only** — ❌ Rejected: No mid-mission safety checks
2. **Every action** — ❌ Rejected: Too interruptive, ruins flow
3. **Progressive confirmation** — ✅ Selected: Context-appropriate confirmation levels

**Decision**: Implement 3-tier confirmation system:

**Level 1: Pre-Flight Mission Confirmation**
- Kimi analyzes request + Google Maps context
- Generates mission plan (template, parameters, estimated duration)
- Shows: map preview + flight path + safety check results
- User confirms before arming

**Level 2: Pre-Arm Live Check**
- After mission confirmation, drone ready to arm
- Show live camera view + telemetry
- "Camera check: Scene looks clear. Arm and execute?"
- 10-second countdown with abort option

**Level 3: Exception-Based Mid-Flight**
- Normal waypoint transitions: auto-execute
- Ask confirmation when:
  * People detected within safety radius
  * Geofence warning
  * Weather/battery marginal
  * Mission plan deviation >20%

**Example Exception Flow**:
```
[YOLO detects people 10m away]
↓
Kimi: "People detected 10m ahead. Recommend holding position."
↓
Sisyphus to User: "⚠️ People detected 10m away. Stop or continue?"
↓
User: "stop" → Drone holds position
User: "continue" → Mission resumes with wider safety buffer
User: [no response 10s] → Auto-hold (fail-safe)
```

**Rationale**:
- Confirmation matched to risk level
- Pre-flight for planning safety
- Mid-flight only for genuine exceptions
- Default-safe: timeout → hold position

**Consequences**:
- `confirmation_required` parameter in mission templates
- Timeout handling in orchestrator (default: hold)
- Chat UI shows mission preview + live video
- All confirmations logged for audit

---

### DEC-019: Google Maps for Pre-Flight Planning Only [DECIDED]

**Date**: 2026-04-11

**Status**: DECIDED - Integration approach defined, pending MCP server implementation

**Context**: User wants to "cross-reference where it is with Google Maps to understand the area." Maps provide valuable context but have limitations for real-time flight.

**Options Considered**:
1. **Live Maps queries during flight** — ❌ Rejected: Adds 1-2s latency per query, unreliable mid-mission
2. **Pre-flight only + offline cache** — ✅ Selected: Plan with context, fly without dependency

**Decision**: Use Google Maps MCP for pre-flight mission planning only, cache relevant data locally.

**Workflow**:
```
User: "orbit the park at 20m"
↓
Query Google Maps: "park boundaries, nearby obstacles, safe airspace"
↓
Kimi analyzes: "Park is 150m across, recommend 35m orbit radius, 
              altitude 25m to clear trees, geofence at park edges"
↓
Generate mission plan with Maps-derived context
↓
Cache: Park polygon, recommended geofence, nearest landing zones
↓
Flight executes using cached data (no live Maps dependency)
```

**Maps Data Used For**:
- Area size estimation (orbit radius calculation)
- Obstacle awareness (buildings, towers nearby)
- Legal context (airspace restrictions, populated areas)
- Landing zone identification
- Geofence boundary suggestions

**Maps Data NOT Used For**:
- Real-time obstacle avoidance (static data, no dynamic obstacles)
- Collision prevention (2D only, no tree height, no moving objects)
- Mid-mission replanning (too slow)

**Rationale**:
- Maps provide valuable planning context
- Static data sufficient for mission planning
- Avoids cloud dependency during flight
- Aligns with hybrid vision approach

**Trade-offs**:
- No live map updates during flight (road closures, construction not reflected)
- Drone cannot ask "what's near me now" mid-flight
- Requires pre-flight planning phase

**Consequences**:
- Maps MCP queries happen during mission planning phase only
- Relevant map data cached in mission context
- Flight operates on cached plan + live vision
- Mission templates include pre-flight planning stage

---

### DEC-020: Phase 0.5 – Full SITL Pre-Validation [IMPLEMENTING]

**Date**: 2026-04-11 (Updated: 2026-04-12)

**Context**: Before investing in hardware, need to validate complete software stack works end-to-end. Want to test Kimi integration, MCP workflows, confirmation flows, and produce demo video.

**Options Considered**:
1. **Start with hardware immediately** — ❌ Rejected: Risk of crashes while debugging software
2. **Lightweight jMAVSim only** — ❌ Rejected: No vision support, limited realism
3. **Full Gazebo SITL with everything** — ✅ Selected: Complete validation environment

**Decision**: Implement comprehensive Phase 0.5 using PX4 SITL + Gazebo simulation with ALL components before hardware purchase.

**Status**: IN PROGRESS - Foundation complete (PX4 SITL + Gazebo setup, MAVSDK connection validated). Integration phase active (MCP server architecture defined, Kimi integration planned).

**Phase 0.5 Scope (3 weeks)**:
```
Week -3: Foundation
- PX4 SITL + Gazebo setup
- MAVSDK connection validation
- Basic flight command testing

Week -2: Integration
- Agent-agnostic MCP server
- Kimi K2.5 integration
- End-to-end pipeline: User → Agent → Kimi → MCP → SITL
- Progressive confirmation workflow

Week -1: Advanced Features
- Gazebo camera + mock vision pipeline
- Google Maps pre-flight planning
- Exception handling (person detected → confirmation)
- Safety scenario testing
- Screen recording + demo video production

Week 0: Transition
- Hardware swap preparation
- Configuration management (SITL vs hardware)
- Documentation and test results
```

**Phase 0.5 Deliverables**:
1. **Working Software Stack**:
   - Agent-agnostic MCP server with all tools
   - Kimi integration with multimodal vision
   - Confirmation workflow (pre-flight + exceptions)
   - Maps integration for planning
   - Flight recording system

2. **Comprehensive Testing**:
   - Integration tests (7 test suites)
   - Performance benchmarks (latency <2s)
   - Safety scenario validation
   - 50+ simulated missions

3. **Demo Video** (4-5 minutes):
   - Screen recording of Gazebo + Agent chat
   - Natural language mission execution
   - Exception handling demonstration
   - Proof of concept before hardware spend

4. **Documentation**:
   - Complete setup guides
   - Test results and metrics
   - Hardware swap procedures

**SITL Configuration**:
```bash
# Full simulation with camera
make px4_sitl gz_x500_depth

# MAVLink: udp://:14540 (same as real RPi)
# Camera: Simulated RGB feed from Gazebo
# Physics: Realistic quadrotor dynamics
```

**What Phase 0.5 Tests**:
✅ All MCP tools and workflows
✅ Kimi LLM planning and tool calling
✅ Agent compatibility (Claude Code, OpenCode, etc.)
✅ Progressive confirmation UX
✅ Vision pipeline architecture (with mock detections)
✅ Google Maps integration
✅ Exception handling and safety systems
✅ Mission recording and logging
✅ End-to-end latency (<2s budget)

**What Phase 0.5 Cannot Test**:
❌ Real YOLO performance on real video
❌ Actual drone physics (weight, wind response)
❌ RF link quality and range
❌ RC transmitter hardware
❌ Real-world obstacle avoidance

**Rationale**:
- **Risk Reduction**: Software bugs caught in sim don't crash real drones
- **Rapid Iteration**: Fast feedback loop for UX refinement
- **Demo Value**: Video proves concept before budget commitment
- **Parallel Development**: Software ready when hardware arrives
- **Safety**: All integration issues resolved before first flight

**Trade-offs**:
- 3-week time investment before hardware
- SITL setup complexity (PX4 build, Gazebo)
- Synthetic vision not identical to real world
- Additional learning curve for simulation

**Mitigations**:
- Phase 0.5 runs parallel with hardware sourcing (not serial)
- Well-documented SITL setup (PX4 docs + this project)
- Mock vision sufficient for mission logic testing
- Graduated testing: sim → HITL → real flight

**Consequences**:
- Software stack complete and validated before Stage 1
- Hardware swap is configuration change only (same code)
- First real flight uses proven software
- Demo video enables feedback and iteration
- Bug fixes happen in simulation (safe, fast, cheap)

**Hardware Transition**:
```bash
# SITL connection
system_address="udp://:14540"

# Hardware connection (after Phase 0.5)
# Just change connection string:
# system_address="serial:///dev/tty.usbmodemXXX:921600"
# Everything else identical
```

**Related**: 
- `01-core-project/PHASE_0_5_FULL_SITL_PLAN.md` (detailed 3-week plan)
- `05-testing-validation/hitl_sitl_simulation.md` (SITL research)
- SITL setup in PX4 documentation

---

## Vision & Perception

### DEC-006: YOLOv8-nano + ByteTrack for Person Tracking [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Vision architecture defined, deferred to Stage 2 implementation

**Context**: Need real-time person detection on Raspberry Pi 4.

**Options Considered**:
1. YOLOv8-large — ❌ Rejected: Too slow for Pi (seconds per frame)
2. **YOLOv8-nano** — ✅ Selected: 3.2M params, ~80ms inference

**Tracking Options**:
1. DeepSORT — ❌ Rejected: Requires ReID model (heavier)
2. **ByteTrack** — ✅ Selected: Motion-based, lighter, ~1-2ms overhead

**Decision**: YOLOv8-nano with ByteTrack at 640x480, 10-15 FPS.

**Configuration**:
```python
config = {
    "track_thresh": 0.4,      # Detection confidence
    "match_thresh": 0.8,      # IoU matching
    "track_buffer": 60,       # 6 seconds occlusion tolerance @ 10 FPS
    "frame_rate": 10
}
```

**Rationale**:
- Nano model fits Pi 4 memory (~150MB)
- ByteTrack handles occlusion without appearance features
- 6-second occlusion recovery sufficient for drone tracking

**Trade-offs**:
- Lower accuracy than larger YOLO models
- Shorter detection range (15-40m at 640x640)
- No re-identification (can't recover after long occlusion)

**Consequences**:
- Detection optimized for people only (class=[0])
- Frame rate target: 10-15 FPS (not 30)
- Memory budget: ~50-60MB per vision stream

**Related**: See `04-vision-perception/yolo_tracking_integration.md`

---

## Software & Implementation

### DEC-007: Asyncio Priority Scheduling [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Priority scheduler architecture defined, documented in asyncio patterns

**Context**: Need to ensure critical tasks (heartbeat) never blocked by CPU-bound work (vision, LLM).

**Decision**: Implement 5-level priority scheduler with CPU isolation.

**Priority Levels**:
```python
class Priority(IntEnum):
    CRITICAL = 0    # 20Hz heartbeat - NEVER blocked
    HIGH = 1        # Telemetry (<10ms)
    MEDIUM = 2      # Vision inference (<50ms)
    LOW = 3         # LLM inference (1-3s)
    BACKGROUND = 4  # Logging (best effort)
```

**CPU Isolation**:
```python
vision_executor = ProcessPoolExecutor(max_workers=1)
llm_executor = ProcessPoolExecutor(max_workers=1)
```

**Rationale**:
- Heartbeat at 20Hz requires exactly 50ms period
- YOLO inference blocks event loop for ~80ms
- Process pools isolate GIL-sensitive work

**Consequences**:
- All CPU-bound work must use run_in_executor()
- Deadline violations logged for post-flight analysis
- Critical tasks have dedicated event loop time

**Related**: See `03-software-architecture/python_asyncio_patterns.md`

---

### DEC-008: JSON Tool Schema for LLM Control [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - Schema structure defined, being used in MCP server implementation

**Context**: Need structured interface for LLM to control drone safely.

**Decision**: Define strict JSON schemas with validation, preconditions, and safety checks.

**Schema Structure**:
```json
{
  "name": "arm_and_takeoff",
  "parameters": { /* JSON Schema */ },
  "preconditions": {
    "required_state": "DISARMED",
    "battery_min_percent": 20,
    "gps_fix_required": true
  },
  "postconditions": {
    "expected_state": "HOVERING",
    "timeout_seconds": 30
  },
  "safety_checks": {
    "geofence_check": true,
    "battery_check": true
  }
}
```

**Rationale**:
- Structured validation prevents hallucinated commands
- Preconditions ensure system state appropriate
- Layered safety: JSON schema → preconditions → GuardianProcess

**Consequences**:
- All LLM tools must have defined schemas
- ToolValidator class enforces validation flow
- GuardianProcess has final approval authority

**Related**: See `03-software-architecture/tool_schema_design.md`

---

### DEC-009: GuardianProcess as Command Gatekeeper [IMPLEMENTED]

**Date**: 2026-04-10

**Status**: IMPLEMENTED - GuardianProcess architecture defined, hard limits specified, being implemented in MCP server

**Decision**: Implement GuardianProcess class that validates ALL commands before execution.

**Hard Limits** (immutable):
```python
@dataclass(frozen=True)
class HardLimits:
    max_altitude_amsl_m: float = 120.0
    max_distance_from_home_m: float = 500.0
    min_battery_rtl_percent: float = 25.0
    max_wind_speed_ms: float = 12.0
```

**Rationale**:
- Software-level validation before PX4 receives command
- Can intercept dangerous commands mid-flight
- Serves as Layer 2 in 4-layer safety architecture

**Consequences**:
- Every command flows through: LLM → ToolValidator → GuardianProcess → MAVSDK → PX4
- GuardianProcess can trigger RTL on violation
- Logs all validation decisions

**Related**: See `02-safety-failsafe/failsafe_hierarchy.md`

---

## Hardware & Physical

### DEC-010: Raspberry Pi 4 as Companion Computer

**Date**: 2026-04-10

**Decision**: Use Raspberry Pi 4 (4GB) as onboard companion computer.

**Rationale**:
- Sufficient for MAVSDK-Python + YOLO-nano
- Large ecosystem and community
- Easy development and debugging
- Low power consumption

**Trade-offs**:
- Limited compute for larger vision models
- Requires active cooling for sustained load
- USB 2.0 bandwidth limitations for cameras

**Consequences**:
- YOLO model limited to nano variant
- Must use half-precision (FP16) inference
- Frame resolution capped at 640x480

---

### DEC-011: Pixhawk 6C Mini as Flight Controller

**Date**: 2026-04-10

**Decision**: Use Pixhawk 6C Mini with PX4 firmware.

**Rationale**:
- Proven reliability in research and commercial applications
- Excellent PX4 support and documentation
- Built-in safety features (failsafe modes)
- Good companion computer integration

**Related**: See `06-hardware/complete_hardware_manifest.md`

---

## Process Decisions

### DEC-012: Research Organization Structure

**Date**: 2026-04-10

**Decision**: Organize research into categorized subdirectories:

```
research/
├── 01-core-project/          # Master briefing, roadmap, requirements
├── 02-safety-failsafe/       # Safety hierarchy, geofencing, hard limits
├── 03-software-architecture/ # Asyncio patterns, tool schemas
├── 04-vision-perception/     # YOLO, ByteTrack, depth estimation
├── 05-testing-validation/    # Test procedures, validation plans
├── 06-hardware/              # Hardware manifest, setup guides
├── 07-references/            # External docs, vendor specs
├── 08-decisions/             # This file - decision audit trail
└── 09-changes/               # CHANGES_MADE.md - change log
```

**Rationale**:
- Logical flow from core → safety → software → vision → testing → hardware
- Numbered prefixes ensure consistent ordering
- Audit trail files (decisions, changes) in dedicated directories

**Consequences**:
- All research documents have permanent locations
- New research follows established categorization
- Decisions and changes tracked separately from research content

---

## Marketplace & Procurement

### DEC-013: Accept >250g Drone Weight (Canadian Compliance)

**Date**: 2026-04-10

**Context**: Canadian drone regulations have 250g threshold for micro vs small drones. Need to determine if Project Avatar can/should stay under this limit.

**Options Considered**:
1. **Stay under 250g** — ❌ Rejected: Cannot lift RPi 4 + camera + battery with sufficient thrust
2. **Accept >250g, register and certify** — ✅ Selected

**Decision**: Accept that Project Avatar will be ~900g (small drone category), register with Transport Canada, and obtain Basic Operations certificate.

**Rationale**:
- Canadian "operating weight" includes everything at takeoff (frame + battery + payload) [1]
- Minimum viable build: ~450g even with Pi Zero 2W and minimal battery
- 7" frame + 2807 motors + 6S battery + RPi 4 = ~900g
- Registration ($5) and Basic certificate (free exam) are minor hurdles
- <250g builds lack thrust for reliable Project Avatar operation

**Trade-offs**:
- Must register drone ($5)
- Must pass Basic exam (35 questions, 65% pass)
- More operational restrictions (VLOS, 30m from people)
- Cannot fly over people without Advanced certificate

**Consequences**:
- Hunt for 7" frames on Marketplace without 250g constraint
- After purchase: register drone, mark with registration number
- Pilot must obtain Basic certificate before first flight
- Maintain flight logs for all operations

**Related**: See `10-marketplace-hunting/03-canadian-drone-laws.md`

---

### DEC-014: 7" Frame with 2807 Motors (Thrust-Focused Selection)

**Date**: 2026-04-10

**Context**: User emphasized "main factor is the thrust power". Need to find Marketplace drone with sufficient TWR (thrust-to-weight ratio) for Project Avatar payload.

**Options Considered**:
1. 5" freestyle frame + 2207 motors — ❌ Rejected: TWR OK but frame too small, tight build
2. **7" long-range frame + 2807 motors** — ✅ Selected
3. 10" cinelifter + 3110 motors — ❌ Rejected: Overkill, harder to find, expensive

**Decision**: Target 7" frames (iFlight Chimera7, HGLRC Rekon7) with 2807 1300-1500KV motors on 6S battery.

**Thrust Calculation**:
- 2807 1300KV on 6S: ~1900g thrust per motor
- 4 motors: ~7600g total thrust
- AUW with payload: ~900g
- **TWR: 8.4:1** (exceeds 3:1 ideal target)

**Rationale**:
- 8:1+ TWR provides responsive control and safety margin
- 7" frames have space for RPi 4 + Pixhawk + battery
- 2807 motors common on Marketplace (popular for long-range)
- 6S battery provides voltage headroom

**Trade-offs**:
- Heavier than 5" (more inertia)
- More expensive than smaller frames
- Requires 30.5x30.5mm FC mount (verify before buying)

**Consequences**:
- Search Marketplace for "7 inch drone", "Chimera7", "2807 motors"
- Must verify FC mount pattern (30.5x30.5mm for Pixhawk 6C Mini)
- Battery weight significant (~400-500g for 6S 4000mAh)
- TWR calculation required for every candidate

**Related**: See `10-marketplace-hunting/02-thrust-calculator.md`

---

## How to Add New Decisions

When making a new architectural or design decision:

1. Create a new DEC-XXX entry in appropriate section
2. Include: Date, Context, Options Considered, Decision, Rationale, Trade-offs, Consequences
3. Cross-reference related research documents
4. Update this TOC if adding new section

**Template**:
```markdown
### DEC-XXX: [Brief Title]

**Date**: YYYY-MM-DD

**Context**: [Why this decision was needed]

**Options Considered**:
1. [Option A] — [Decision]
2. [Option B] — [Decision]

**Decision**: [What was decided]

**Rationale**: [Why this choice]

**Trade-offs**: [What was given up]

**Consequences**: [What must be done as a result]

**Related**: See `[path/to/doc.md]`
```

---

*Last Updated: 2026-04-12*  
*Total Decisions: 22*

[1] Transport Canada Drone Operation Categories: https://tc.canada.ca/en/aviation/drone-safety/learn-rules-you-fly-your-drone/drone-operation-categories-pilot-certificates
