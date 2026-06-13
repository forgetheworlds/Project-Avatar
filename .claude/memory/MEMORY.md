# Project Avatar - Memory Index

## Patterns

- [Drone MCP Server](patterns/drone-mcp-server.json) - Agent-agnostic drone control via MCP
- [MAVSDK Offboard Control](patterns/mavsdk-offboard-control.json) - NED coordinate waypoint navigation

## Learnings

- [MCP NotificationOptions Fix](learnings/mcp-notificationoptions-import.json) - SDK 1.x import path
- [PX4 macOS SITL Workaround](learnings/px4-macos-sitl-unstable.json) - Direct binary execution
- [PMW3901 Optical Flow Battle-Tested](learnings/pmw3901-optical-flow-battle-tested.json) - $15 indoor position hold solution
- [Hawkeye Thumb 4K Gyroflow Unknown](learnings/hawkeye-thumb-4k-gyroflow-unknown.json) - Critical camera uncertainty
- [ESP32-S3 Dual-Core CV Feasible](learnings/esp32-s3-dualcore-cv-feasible.json) - Onboard CV offload validated
- [Water Pump Ballistics + Brownout Risk](learnings/water-pump-ballistics-brownout-risk.json) - ~3m range, needs ground test
- [ESP32 Drone Ecosystem Exploding May 2026](learnings/esp32-drone-ecosystem-exploding-may2026.json) - 5 new projects, web-based standard emerging
- [Anti-Slosh Critical Flight Safety](learnings/anti-slosh-critical-flight-safety.json) - #1 failure mode for liquid drones — baffles mandatory
- [TrackingPanTiltCam Turret Mode Reference](learnings/trackingpantiltcam-turret-mode-reference.json) - Production YOLOv8 turret codebase for Splash
- [MG90S Metal Gear Servo Mandatory](learnings/mg90s-metal-gear-servo-mandatory.json) - SG90 plastic strips in every build — avoid
- [Diaphragm Pump Preferred](learnings/diaphragm-pump-preferred-for-splash.json) - Self-priming, high pressure, dry-run safe
- [Isolated Power Rails Mandatory](learnings/isolated-power-rails-mandatory.json) - Every project without this failed

## Decisions

- [Architecture Clarification](architecture-clarification.md) - Claude Code IS the agent with Kimi K2.5 backend

## Key Files

| Category | Location |
|----------|----------|
| Patterns | `.claude/memory/patterns/` |
| Learnings | `.claude/memory/learnings/` |
| Decisions | `.claude/memory/decisions/` |
| Solutions | `docs/solutions/` |

## Quick Reference

**Start SITL:**
```bash
cd PX4-Autopilot
PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4
```

**Test Connection:**
```bash
source venv/bin/activate
python -c "from mavsdk import System; ..."
```

**Start MCP Server:**
```bash
source venv/bin/activate
python -m avatar.mcp_server.server
```

**Fly Mission:**
- `/fly "takeoff hover land"` - Basic test
- `/fly "orbit 15m"` - Square pattern
- `/fly "loop"` - Figure-8 pattern
