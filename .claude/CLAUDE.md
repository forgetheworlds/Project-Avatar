# Project Avatar - Claude Code Configuration

## Project Overview

**Project Avatar** is an LLM-driven autonomous drone system controlled by natural language via any AI agent using the Model Context Protocol (MCP).

**Architecture 2.0**: Cloud Kimi K2.5 LLM + Agent-Agnostic MCP + PX4 SITL Simulation

## Current Phase

**Phase 0.5**: Virtual Drone (Pre-Hardware) - Building and validating complete software stack in PX4 SITL + Gazebo simulation.

## Key Technologies

- **PX4 Autopilot**: Flight control & SITL simulation
- **MAVSDK**: Drone communication library
- **Gazebo**: Physics simulation
- **Kimi K2.5** (Fireworks AI): Multimodal LLM for mission planning
- **YOLOv8-nano**: Real-time object detection
- **MCP**: Model Context Protocol for agent communication

## Project Structure

```
Project-Avatar/
├── .claude/           # Claude Code configuration (this directory)
├── research/          # Documentation and planning
│   ├── 01-core-project/
│   ├── 02-hardware-design/
│   └── 03-software-architecture/
├── mcp_server/        # Drone MCP server (to be created)
├── vision/            # YOLO detection pipeline (to be created)
└── scripts/           # Utility scripts (to be created)
```

## Development Guidelines

### Safety First
- ALWAYS test in SITL before real hardware
- NEVER trust LLM with millisecond-level safety decisions
- ALWAYS configure kill switch for real flights
- ALWAYS set geofence before first flight

### Code Style
- Python 3.10+ with type hints
- Async/await for MAVSDK operations
- Docstrings for all public functions
- Pytest for testing

### MCP Server Development
- Use `mcp` Python package for server implementation
- All tools must validate through GuardianProcess
- Progressive confirmation for dangerous operations
- Telemetry broadcasting at 1Hz minimum

## Environment Variables

```bash
# Required for Kimi integration
FIREWORKS_API_KEY=your-key-here

# Optional for pre-flight planning
GOOGLE_MAPS_API_KEY=your-key-here
```

## Quick Commands

### Start SITL Simulation
```bash
cd PX4-Autopilot
make px4_sitl gz_x500
```

### Test MAVSDK Connection
```bash
python -c "
import asyncio
from mavsdk import System

async def test():
    drone = System()
    await drone.connect(system_address='udp://:14540')
    print('Connected to SITL!')

asyncio.run(test())
"
```

## Related Documentation

- [Phase 0.5 Plan](../research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md)
- [Agent Connection Guide](../research/03-software-architecture/AGENT_CONNECTION_QUICKSTART.md)
- [PRD](../research/01-core-project/project_avatar_prd.md)
- [Architecture Decisions](../research/DECISIONS.md)
