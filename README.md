# Project Avatar - LLM-Driven Autonomous Drone

**Architecture 2.0** - Cloud LLM (Kimi K2.5) + Agent-Agnostic MCP + Full Simulation Pre-Validation

An autonomous drone system controlled by natural language via **any AI agent** (Claude Code, OpenCode, etc.), using **cloud multimodal LLM** (Kimi K2.5 via Fireworks AI) for mission planning and **PX4 SITL simulation** for pre-hardware validation.

---

## 🎯 What's New in Architecture 2.0

| Feature | v1.0 (Old) | v2.0 (Current) |
|---------|------------|----------------|
| **LLM** | Local Llama 3 8B (25-40 tok/s) | **Cloud Kimi K2.5** (200 tok/s, 8x faster) |
| **Vision** | YOLO only | **Hybrid**: YOLO real-time + Kimi cloud analysis |
| **Interface** | OpenCode only | **Any MCP agent** (Claude Code, OpenCode, etc.) |
| **Pre-Validation** | None | **Phase 0.5**: Full SITL simulation before hardware |
| **Protocol** | Custom | **Standard MCP** (Model Context Protocol) |

**Key Innovation**: Complete software stack validated in **PX4 SITL + Gazebo simulation** before buying hardware. Demo video proves concept before budget commitment.

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

| Resource | Description |
|----------|-------------|
| **[Phase 0.5 Summary](./PHASE_0_5_SUMMARY.md)** | **NEW** - Completion report and test results |
| **[SITL Setup Guide](./docs/sitl_setup.md)** | **NEW** - Step-by-step installation |
| **[Phase 0.5 Plan](./research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md)** | 3-week simulation roadmap |
| **[Agent Connection Guide](./research/03-software-architecture/AGENT_CONNECTION_QUICKSTART.md)** | Connect Claude Code, OpenCode, or any MCP agent |
| **[PRD](./research/01-core-project/project_avatar_prd.md)** | Full product requirements - Stages 1/2/3 |
| **[Roadmap](./research/01-core-project/project_avatar_roadmap.md)** | Complete schedule: Phase 0.5 → Stage 0 → Stage 1/2/3 |
| **[Decisions](./research/DECISIONS.md)** | Architectural decisions (Kimi, MCP, SITL) |
| **[MCP Architecture](./research/03-software-architecture/mcp_agent_agnostic_design.md)** | Agent-agnostic design details |

---

## 🚀 Current Status

### Phase 0.5: Virtual Drone (Pre-Hardware) - **COMPLETE**

**Status**: ✅ **COMPLETE** - All software validated in simulation

**Goal**: Build and validate complete software stack in PX4 SITL + Gazebo simulation before hardware arrives.

**Completed Timeline**:
- **Week -3**: ✅ Gazebo SITL setup + basic flight tests
- **Week -2**: ✅ MCP server + Kimi integration + end-to-end pipeline
- **Week -1**: ✅ Vision simulation + Google Maps + demo video ready
- **Week 0**: ✅ Hardware transition scripts prepared

**Deliverables**:
- [x] Working agent-agnostic MCP server
- [x] Kimi K2.5 integration with multimodal vision
- [x] Progressive confirmation workflow
- [x] Google Maps pre-flight planning
- [x] **Demo video** (4-5 min) - See [PHASE_0_5_SUMMARY.md](./PHASE_0_5_SUMMARY.md)
- [x] Hardware transition scripts

**Why Phase 0.5?**
- ✅ Software bugs caught in sim don't crash real drones
- ✅ Kimi integration validated without hardware risk
- ✅ Demo video proves concept before budget spent
- ✅ Software "flight-ready" before parts arrive

**See**: [PHASE_0_5_SUMMARY.md](./PHASE_0_5_SUMMARY.md) for complete results

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

# Basic SITL connectivity test
python tests/test_sitl_basic.py

# Full integration test (requires FIREWORKS_API_KEY)
export FIREWORKS_API_KEY="your-key"
python tests/test_kimi_integration.py

# All Phase 0.5 tests
python -m pytest tests/phase05/ -v
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `arm_and_takeoff(altitude_m)` | Arm and take off |
| `goto_gps(lat, lon, alt_m)` | Fly to coordinates |
| `fly_body_offset(forward, right, up)` | Relative movement |
| `hold_position(seconds)` | Hold current position |
| `land()` | Land at current position |
| `rtl()` | Return to launch |
| `get_telemetry()` | Get position/velocity |
| `capture_frame()` | Camera snapshot |
| `abort_mission(reason)` | Emergency RTL |
| `plan_mission(request)` | Natural language planning |

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

**Phase 0.5 Deliverable**: 4-5 minute screen recording

**Script**:
1. **Intro** (0:00-0:30): Split screen showing Gazebo + Agent chat
2. **Connection** (0:30-1:00): Agent connects, telemetry displayed
3. **Mission** (1:00-2:30): Natural language → Kimi planning → mission execution
4. **Exception** (2:30-3:30): Person detected → confirmation dialog → abort
5. **Landing** (3:30-4:00): Safe RTL and landing

**Recording**: QuickTime Player screen capture (Gazebo + Terminal side-by-side)

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
├── avatar/                    # Core implementation
│   ├── mcp_server/           # Agent-agnostic MCP server
│   │   ├── server.py         # Main MCP server
│   │   └── confirmation.py   # Progressive confirmation
│   ├── llm/                  # LLM integration
│   │   └── kimi_client.py    # Fireworks AI client
│   ├── vision/               # Vision pipeline
│   │   └── mock_detector.py  # Simulated detections
│   ├── planning/             # Mission planning
│   │   └── maps_integration.py
│   └── utils/                # Utilities
│       └── flight_recorder.py
├── tests/                    # Test suite
│   ├── test_sitl_basic.py
│   ├── test_kimi_integration.py
│   └── test_safety_scenarios.py
├── PX4-Autopilot/            # PX4 SITL (submodule)
├── research/                 # Design documents
│   ├── 01-core-project/      # Roadmap, PRD
│   ├── 02-safety-failsafe/   # Safety architecture
│   ├── 03-software-architecture/
│   ├── 04-vision-perception/
│   └── DECISIONS.md          # Decision audit trail
├── docs/                     # Documentation
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
| End-to-end Command | < 3s | **~2s** (test in sim) |
| SITL Realtime Factor | 1.0 | **1.0** (Gazebo) |

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
