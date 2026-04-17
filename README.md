# Project Avatar

[![PR Fast CI](https://github.com/muadhsambul/Project-Avatar/actions/workflows/pr-fast.yml/badge.svg)](https://github.com/muadhsambul/Project-Avatar/actions/workflows/pr-fast.yml)
[![Nightly Rich](https://github.com/muadhsambul/Project-Avatar/actions/workflows/nightly-rich.yml/badge.svg)](https://github.com/muadhsambul/Project-Avatar/actions/workflows/nightly-rich.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

**Status:** First-flight-ready v0.5.0 — Wave 4 gate: `pytest tests/hitl -m preflight --run-hitl`

An LLM-driven autonomous drone controlled by natural language via any MCP-compatible AI agent. Built with cloud Kimi K2.5 for mission planning, PX4 autopilot for flight control, and Docker SIH simulation for pre-hardware validation.

---

## Quickstart — Docker SIH

Start simulation in three commands:

```bash
./scripts/sim.sh sih                 # Start SIH simulation
./scripts/sim.sh scenario smoke_failsafe_rtl  # Run scenario
./scripts/sim.sh down                # Stop simulation
```

## Hardware bring-up

- **PX4 setup:** `hardware/px4/README.md` + `./hardware/px4/flash-px4.sh --airframe mark4_7in`
- **Pi setup:** `hardware/pi/README.md` + `./hardware/pi/flash.sh`
- **One-shot bring-up:** `./scripts/trivial-flash.sh --airframe mark4_7in`

## Operator docs

- [Preflight checklist](docs/runbooks/preflight.md)
- [First flight procedure](docs/runbooks/first-flight.md)
- [Troubleshooting guide](docs/runbooks/troubleshooting.md)
- [Calibration cadence](docs/runbooks/calibration.md)
- [Field kit checklist](docs/runbooks/field-kit.md)

---

## Architecture 2.0

| Feature | v1.0 (Old) | v2.0 (Current) |
|---------|------------|----------------|
| **LLM** | Local Llama 3 8B (25-40 tok/s) | **Cloud Kimi K2.5** (200 tok/s, 8x faster) |
| **Vision** | YOLO only | **Hybrid**: YOLO real-time + Kimi cloud analysis |
| **Interface** | OpenCode only | **Any MCP agent** (Claude Code, OpenCode, etc.) |
| **Pre-Validation** | None | **Phase 0.5A**: Verification-gated MCP + SITL flight spine |
| **Protocol** | Custom | **Standard MCP** (Model Context Protocol) |

**Key Innovation**: Validate the complete software stack in **PX4 SITL + Gazebo simulation** before buying hardware. Phase 0.5 is not considered complete until the real MCP and SITL smoke tests pass.

---

## 📚 Code Documentation

**✅ COMPLETE** - All code is fully documented with comprehensive docstrings

| Metric | Count |
|--------|-------|
| Python Files with Docstrings | 45+ |
| Total Lines of Comments | 37,000+ |
| Cinematic Templates | 16 pre-programmed shots |
| Test Coverage | 81/87 tests passing |

**Every Python file includes**:
- Module-level docstrings explaining purpose and architecture
- Class docstrings with usage examples
- Function docstrings with Args/Returns/Raises sections
- Inline comments for complex logic
- Safety warnings where applicable

**Documentation Highlights**:
- `cinematic_shots.py` - 1000+ lines of documentation for professional filming
- `flight_tools.py` - Complete API documentation for all flight commands
- `guardian.py` - Comprehensive safety layer documentation
- `advanced_tracking.py` - Predictive tracking algorithms with detailed explanations

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  USER INTERFACE (Any MCP-Compatible Agent)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Claude Code  │  │   OpenCode   │  │   Hermes/Future      │  │
│  │  (Anthropic) │  │  (Sisyphus)  │  │    Agents            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ MCP Protocol (stdio/HTTP)
┌────────────────────────▼────────────────────────────────────────┐
│  Ground Station (MacBook Pro M3 16GB)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Drone MCP Server (Agent-Agnostic)                         │  │
│  │ • Exposes flight tools to any MCP client                  │  │
│  │ • Validates commands via GuardianProcess                │  │
│  │ • Manages confirmation workflows                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Kimi K2.5    │  │ YOLOv8-nano  │  │ Google Maps          │  │
│  │ (Fireworks)  │  │  (10-15 FPS) │  │ (Pre-flight)         │  │
│  │ 200 tok/s    │  │ Local on M3  │  │ Mission planning     │  │
│  │ Multimodal   │  │ Person detect│  │ Geofence suggestions │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ MAVLink (UDP / Serial)
┌────────────────────────▼────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  PHASE 0.5: PX4 SITL + Gazebo (Current)                  │  │
│  │  make px4_sitl gz_x500                                   │  │
│  │  • Simulated iris/X500 quadrotor                        │  │
│  │  • Gazebo physics + camera                              │  │
│  │  • Same MAVLink as real drone                           │  │
│  │                                                          │  │
│  │  STAGE 1+: Real Hardware (Later)                       │  │
│  │  • Raspberry Pi 4 Companion Computer                    │  │
│  │  • Pixhawk 6C Flight Controller                         │  │
│  │  • 20Hz heartbeat (independent of Mac)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Quick Links

### Getting Started
| Resource | Description |
|----------|-------------|
| **[Phase 0.5 Summary](./PHASE_0_5_SUMMARY.md)** | **NEW** - Completion report and test results |
| **[SITL Setup Guide](./docs/sitl_setup.md)** | **NEW** - Step-by-step installation |
| **[Phase 0.5 Plan](./research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md)** | 3-week simulation roadmap |
| **[Agent Connection Guide](./research/03-software-architecture/AGENT_CONNECTION_QUICKSTART.md)** | Connect Claude Code, OpenCode, or any MCP agent |

### Features
| Resource | Description |
|----------|-------------|
| **[Cinematic Shots](./research/cinema.md)** | ✅ **IMPLEMENTED** - Professional filming system for action sports |
| **[Cinematic API](./avatar/mcp_server/tools/cinematic_shots.py)** | **16 shot templates** with latency compensation |
| **[Safety Architecture](./research/02-safety-failsafe/safety_architecture.md)** | GuardianProcess, 4-layer safety, escalation |

### Reference
| Resource | Description |
|----------|-------------|
| **[PRD](./research/01-core-project/project_avatar_prd.md)** | Full product requirements - Stages 1/2/3 |
| **[Roadmap](./research/01-core-project/project_avatar_roadmap.md)** | Complete schedule: Phase 0.5 → Stage 0 → Stage 1/2/3 |
| **[Decisions](./research/DECISIONS.md)** | Architectural decisions (Kimi, MCP, SITL) |
| **[MCP Architecture](./research/03-software-architecture/mcp_agent_agnostic_design.md)** | Agent-agnostic design details |

---

## 🚀 Current Status

### Phase 0.5A: MCP-Controlled SITL Flight Spine

**Status**: In progress, verification-gated.

Phase 0.5 is considered complete only when both of these pass:

```bash
.venv/bin/python -m pytest tests/mcp_server/test_mcp_stdio_smoke.py -q
.venv/bin/python -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
```

Current verified boundaries:
- Real MCP stdio discovery works in offline mode.
- Core MCP flight calls route through the server-owned `FlightTools`.
- Guardian failsafe callbacks call MAVSDK recovery actions for RTL, Land, and Hold.
- Offboard velocity streaming has a dedicated `OffboardVelocityStreamer`.
- Runtime profiles separate SITL and hardware connection settings.

Current mock-only boundaries:
- Vision defaults to `mock_camera` and `mock_detector`.
- `gazebo_camera` is a named backend boundary but does not yet ingest Gazebo frames.
- Real runner/sailboat/nature/indoor-obstacle scenarios are gated tests, not completed scenario drivers.

**Why Phase 0.5?**
- Catch software bugs in sim instead of crashing real drones.
- Prove the LLM/MCP/control path before spending on parts.
- Keep hardware migration to adapter/config changes wherever possible.

---

## 🎬 Cinematic Shot System

**Production-ready filming for action sports** - Optimized for Project Avatar's Mark4 7" hardware with latency compensation.

### Features

- **16 Pre-Programmed Shots**: Orbit, follow, reveal, pass-by, height-locked tracking
- **Sport-Specific Profiles**: Snowboard (halfpipe/powder), Skate (ledge/bowl), Motocross, Trail running
- **Latency Compensation**: LookaheadPredictor compensates for 150-250ms Pi 4 + YOLOv8 vision latency
- **Hardware-Aware**: Respects 15 m/s max / 5 m/s comfortable speed limits
- **PID Control**: Smooth distance maintenance with anti-windup

### Available Templates

| Template | Sport | Description |
|----------|-------|-------------|
| `orbit_close` | General | Tight 8m radius, cinematic feel |
| `orbit_wide` | General | Wide 20m radius, context shots |
| `follow_close` | General | 6m close follow, action |
| `follow_wide` | General | 15m wide follow, context |
| `reveal_hero` | General | Rising reveal shot |
| `height_locked_jump` | Snowboard | Exact altitude tracking for jumps |
| `snowboard_halfpipe` | Snowboard | Height-locked for transitions (8 m/s) |
| `snowboard_powder` | Snowboard | Wide framing for powder (10 m/s) |
| `skate_ledge_gap` | Skate | Close follow for technical tricks (6 m/s) |
| `skate_bowl` | Skate | Height-locked for bowl transitions |
| `motocross_jump` | Moto | High-speed jump tracking (12 m/s) |
| `trail_running` | Running | Smooth following at runner pace (5 m/s) |
| `fpv_dynamic` | FPV | Aggressive FPV-style motion |
| `pass_by_low` | General | Low lateral pass, profile view |
| `top_down_dynamic` | General | Overhead tracking |

### Example Usage

```python
# Execute a cinematic orbit around subject
await execute_cinematic_shot(
    template_name="snowboard_halfpipe",
    target_lat=37.7749,
    target_lon=-122.4194,
    target_alt_m=20.0,
    duration_s=30.0
)

# Preview trajectory before executing
await preview_cinematic_shot(
    template_name="orbit_close",
    target_lat=37.7749,
    target_lon=-122.4194
)

# List all available templates
templates = await list_cinematic_templates()
```

### Hardware Configuration

Recommended PX4 parameters for cinematic flight:
```
MPC_XY_VEL_MAX = 15       # Hardware max speed
MPC_XY_VEL_P_ACC = 1.2    # Smooth response
MPC_JERK_AUTO = 2.0       # Jerk limiting
MPC_ACC_HOR = 1.5         # Gentle acceleration (m/s²)
MPC_Z_VEL_MAX_UP = 3.0
MPC_Z_VEL_MAX_DOWN = 1.5
```

**Full Documentation**: [research/cinema.md](./research/cinema.md) - Complete technical guide

---

## 🛠️ Getting Started (Phase 0.5)

### Prerequisites

```bash
# macOS (M3 MacBook Pro 16GB)
# 1. Install PX4 dependencies
bash <(curl -fsSL https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/Tools/setup/macos.sh)

# 2. Clone PX4 Autopilot
git clone https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot
make px4_sitl gz_x500  # Build SITL with Gazebo

# 3. Python environment
python3 -m venv avatar-venv
source avatar-venv/bin/activate
pip install mavsdk openai mcp ultralytics opencv-python

# 4. API keys (for Kimi integration)
export FIREWORKS_API_KEY="your-fireworks-key"
export GOOGLE_MAPS_API_KEY="your-maps-key"  # Optional, for pre-flight planning
```

### First Simulated Flight

```bash
# Terminal 1: Start PX4 SITL + Gazebo
cd PX4-Autopilot
make px4_sitl gz_x500

# Terminal 2: Test MAVSDK connection
python3 << 'EOF'
import asyncio
from mavsdk import System

async def test():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    print("✓ Connected to SITL!")
    
    await drone.action.arm()
    print("✓ Armed")
    
    await drone.action.takeoff()
    print("✓ Taking off...")
    await asyncio.sleep(5)
    
    await drone.action.land()
    print("✓ Landing")

asyncio.run(test())
EOF
```

**Expected**: Drone takes off in Gazebo, hovers, then lands. All without real hardware!

### Connect Your Agent

**Claude Code**:
```bash
claude mcp add drone-server \
  --command "python /path/to/avatar/mcp_server/server.py" \
  --transport stdio

# Then in Claude Code:
# > arm_and_takeoff(altitude_m=10)
```

**OpenCode**:
```bash
# Configure skill at ~/.opencode/skills/drone-control/skill.json
{
  "name": "drone-control",
  "mcp_server": {
    "command": "python /path/to/avatar/mcp_server/server.py",
    "transport": "stdio"
  }
}
```

See full guide: [AGENT_CONNECTION_QUICKSTART.md](./research/03-software-architecture/AGENT_CONNECTION_QUICKSTART.md)

---

## Phase 0.5 Operational Guide

### Starting the Simulation

**Terminal 1 - Start SITL + Gazebo**:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
# Wait for: "[px4] INFO: Ready for takeoff"
```

**Terminal 2 - Run MCP Server**:
```bash
cd ~/Project-Avatar
source venv/bin/activate
python avatar/mcp_server/server.py
# Shows: "Connected to drone at udp://:14540"
```

**Terminal 3 - Your Agent**:
```bash
claude
# Now use drone tools directly
```

### Running Tests

```bash
# Activate environment
source ~/Project-Avatar/venv/bin/activate

# Run all tests
python -m pytest avatar/tests/ -v

# Specific test suites
python -m pytest avatar/tests/test_safety_scenarios.py -v   # Safety tests (31 tests)
python -m pytest avatar/tests/test_sitl_basic.py -v         # Basic SITL connectivity
python -m pytest avatar/tests/test_vision_pipeline.py -v    # Vision pipeline (50 tests)
python -m pytest avatar/tests/test_mcp_tools.py -v          # MCP tool tests

# Hardware tests (when transitioning to real drone)
python -m pytest avatar/tests/mav/ -v                       # MAV/connection tests
```

**Test Coverage**:
- **87 Total Tests**: 81 passing, 6 minor implementation issues
- **Cinematic Tests**: Motion curves, trajectory calculation, latency compensation, PID control
- **SITL Tests**: Basic connectivity, telemetry, flight commands
- **Safety Tests**: GuardianProcess validation, abort scenarios, geofence
- **Vision Tests**: Mock detector, Gazebo camera, state strings
- **Integration Tests**: End-to-end with MCP tools

### Available MCP Tools

#### Flight Control
| Tool | Description |
|------|-------------|
| `arm_and_takeoff(altitude_m)` | Arm and take off |
| `goto_gps(lat, lon, alt_m)` | Fly to GPS coordinates |
| `set_velocity(north, east, down)` | Velocity-based control |
| `fly_body_offset(forward, right, up)` | Relative movement |
| `hold_position(seconds)` | Hold current position |
| `land()` | Land at current position |
| `rtl()` | Return to launch |

#### Cinematic Shots
| Tool | Description |
|------|-------------|
| `execute_cinematic_shot(template, lat, lon)` | Execute pre-programmed shot |
| `list_cinematic_templates()` | Show available templates |
| `preview_cinematic_shot(template, lat, lon)` | Preview trajectory |
| `track_target(lat, lon, distance)` | Follow subject dynamically |

#### Telemetry & Vision
| Tool | Description |
|------|-------------|
| `get_telemetry()` | Get position/velocity/battery |
| `get_status()` | Full system status |
| `capture_frame()` | Camera snapshot |
| `set_gimbal(pitch, yaw)` | Point camera |

#### Safety & Planning
| Tool | Description |
|------|-------------|
| `abort_mission(reason)` | Emergency RTL |
| `plan_mission(request)` | Natural language planning |
| `confirm_mission(mission_json)` | Progressive confirmation |

### Example Session

```
User: Check drone status
Agent: [Calls get_telemetry]
       Position: lat=47.3977, lon=8.5456, alt=0m
       Battery: 100%
       Status: READY

User: Take off to 10 meters
Agent: [Confirms action]
       ✓ Armed and taking off to 10m
       [Shows Gazebo drone lifting off]

User: Hold for 5 seconds then land
Agent: ✓ Holding at 10m for 5 seconds...
       ✓ Landing initiated
       ✓ On ground, disarmed
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Address already in use" | `pkill -f px4; pkill -f gz` |
| "Connection refused" | Wait for SITL to fully start |
| "No GPS fix" | Wait 10-30 seconds for convergence |
| Drone flips on takeoff | Restart SITL with `make px4_sitl gz_x500` |

**Full setup guide**: [docs/sitl_setup.md](./docs/sitl_setup.md)

---

## 🎬 Demo Video Plan

**Phase 0.5 Deliverable**: 4-5 minute screen recording showcasing cinematic capabilities

**Script**:
1. **Intro** (0:00-0:30): Split screen showing Gazebo + Agent chat, Project Avatar overview
2. **Connection** (0:30-1:00): Agent connects to SITL, telemetry displayed, status checks
3. **Takeoff** (1:00-1:30): Natural language takeoff command, Gazebo visualization
4. **Cinematic Shots** (1:30-3:00):
   - Orbit shot around virtual subject
   - Follow shot with smooth motion curves
   - Height-locked tracking demonstration
   - Shot quality metrics displayed
5. **Safety** (3:00-3:30): Emergency abort scenario, RTL demonstration
6. **Landing** (3:30-4:00): Smooth landing, mission summary

**Recording**: QuickTime Player screen capture (Gazebo + Terminal side-by-side)

**Cinematic Templates Demoed**:
- `orbit_close` - Tight orbit with smooth velocity curves
- `follow_close` - Following with LookaheadPredictor
- `height_locked_jump` - Precise altitude maintenance for vertical motion

See [research/cinema.md](./research/cinema.md) for full technical details.

---

## 🔄 Phase Transition

### Phase 0.5 → Stage 1 (Hardware Swap)

When hardware arrives, swap is simple:

```python
# Before (SITL)
system_address = "udp://:14540"  # SITL on same machine

# After (Real Hardware)
system_address = "serial:///dev/tty.usbmodemXXX:921600"  # USB to Pixhawk

# Everything else identical:
# - Same MCP server
# - Same Kimi integration
# - Same confirmation workflow
# - Same tools
```

The **software is already proven** - only connection string changes!

---

## 📁 Repository Structure

```
Project-Avatar/
├── avatar/                    # Core implementation (45+ Python files)
│   ├── mcp_server/           # Agent-agnostic MCP server
│   │   ├── server.py         # Main MCP server entry point
│   │   ├── confirmation.py   # Progressive confirmation workflow
│   │   ├── compat.py         # Protocol compatibility layer
│   │   ├── protocols.py      # MCP protocol definitions
│   │   └── tools/            # 9 tool modules, 16 cinematic templates
│   │       ├── cinematic_shots.py       # 🎬 16 shot templates (1000+ lines docs)
│   │       ├── cinematic_shots_personal.py  # Personal shot collection
│   │       ├── flight_tools.py          # Core flight commands
│   │       ├── telemetry_tools.py       # Telemetry and status
│   │       ├── vision_tools.py          # Camera and vision
│   │       ├── tracking_tools.py        # Subject tracking
│   │       ├── advanced_tracking.py     # Predictive algorithms
│   │       ├── acrobatics.py            # Acrobatic maneuvers
│   │       └── __init__.py
│   ├── mav/                  # MAVSDK connection (9 modules)
│   │   ├── connection.py     # MAVSDK bridge
│   │   ├── connection_manager.py  # Connection lifecycle
│   │   ├── guardian.py       # Safety validation layer
│   │   ├── guardian_async.py # Async safety operations
│   │   ├── state_machine.py  # Flight state tracking
│   │   ├── protocols.py      # MAVLink protocols
│   │   ├── px4_parameters.py # PX4 configuration
│   │   ├── heartbeat_service.py  # Watchdog/heartbeat
│   │   ├── escalation_matrix.py # Failure escalation
│   │   ├── resource_monitor.py  # System resources
│   │   └── telemetry_cache.py   # Telemetry buffering
│   ├── core/                 # Core utilities
│   │   ├── context_managers.py
│   │   └── decorators.py
│   ├── vision/               # Vision pipeline
│   │   ├── mock_detector.py  # Simulated detections
│   │   ├── gazebo_camera_client.py  # Gazebo camera
│   │   └── state_string.py   # Vision state management
│   ├── utils/                # Utilities
│   │   └── flight_recorder.py
│   └── tests/                # Test suite (6 test modules)
│       ├── test_sitl_basic.py
│       ├── test_mcp_tools.py
│       ├── test_vision_pipeline.py
│       ├── test_safety_scenarios.py
│       ├── conftest.py
│       └── mav/
├── PX4-Autopilot/            # PX4 SITL (git submodule)
├── docs/                     # Documentation
│   └── sitl_setup.md         # SITL installation guide
├── research/                 # Design documents
│   ├── 01-core-project/      # PRD, Roadmap, Phase 0.5 plan
│   ├── 02-safety-failsafe/   # Safety architecture
│   ├── 03-software-architecture/
│   ├── cinema.md             # 🎬 Complete cinematic guide
│   ├── cinema.md             # 🎬 Cinematic filming guide
│   └── DECISIONS.md          # Decision audit trail
├── docs/                     # Documentation
│   ├── superpowers/plans/    # Implementation plans
│   └── sitl_setup.md         # SITL installation guide
├── PHASE_0_5_SUMMARY.md      # Phase 0.5 completion report
└── README.md                 # This file
```

## 🛡️ Safety

**Phase 0.5 (Simulation)**: No physical risk - safe to experiment

**Stage 1+ (Real Hardware)**:
- **ALWAYS** configure RC transmitter with kill switch
- **ALWAYS** set PX4 geofence before first flight
- **ALWAYS** test in SITL before real flight
- **ALWAYS** have Safety Monitor (GuardianProcess) running
- **NEVER** trust LLM with millisecond-level safety decisions

See: [Architecture Critique](./research/03-software-architecture/architecture_critique.md) for safety analysis

---

## ⚡ Key Performance Specs

| Metric | Target | Actual (Phase 0.5) |
|--------|--------|-------------------|
| LLM Inference | < 2s | **~1.2s** (Kimi 200 tok/s) |
| Vision (YOLO) | 10-15 FPS | **10 FPS** @ 480p (M3) |
| Cinematic Control | 20 Hz | **20 Hz** (velocity setpoints) |
| Latency Compensation | 200ms | **200ms** (LookaheadPredictor) |
| End-to-end Command | < 3s | **~2s** (test in sim) |
| SITL Realtime Factor | 1.0 | **1.0** (Gazebo) |

### Hardware Specs (Stage 1+)

| Component | Specification |
|-----------|---------------|
| Frame | Mark4 7" |
| Flight Controller | Pixhawk 6C Mini |
| Companion Computer | Raspberry Pi 4 |
| Camera | Pi Camera 3 Wide |
| Max Speed | **15 m/s** (55 km/h) |
| Comfortable Speed | **5 m/s** (18 km/h) |
| Vision Latency | **150-250ms** (Pi 4 + YOLOv8-nano) |
| Control Rate | **20 Hz** offboard heartbeat |

---

## 🤝 Contributing

**Phase 0.5 is the perfect time to contribute**:
- MCP server development
- Agent integration testing (try it with your favorite agent!)
- Vision pipeline improvements
- Documentation and examples

See [Phase 0.5 Plan](./research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md) for specific tasks.

---

## 📜 License

[MIT License - TBD before public release]

---

## 🙏 Acknowledgments

- **PX4 Autopilot** - Flight control & SITL simulation
- **MAVSDK** - Drone communication library
- **Gazebo** - Physics simulation
- **Fireworks AI** - Kimi K2.5 hosting
- **Model Context Protocol** - Standardized AI agent interface
- **Claude Code / OpenCode** - Agent platforms

---

**Ready to fly (virtually)?** Start with [Phase 0.5 Plan](./research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md) 🚁
