# Project Avatar - Memory Index

## Patterns

- [Drone MCP Server](patterns/drone-mcp-server.json) - Agent-agnostic drone control via MCP
- [MAVSDK Offboard Control](patterns/mavsdk-offboard-control.json) - NED coordinate waypoint navigation

## Learnings

- [MCP NotificationOptions Fix](learnings/mcp-notificationoptions-import.json) - SDK 1.x import path
- [PX4 macOS SITL Workaround](learnings/px4-macos-sitl-unstable.json) - Direct binary execution

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
