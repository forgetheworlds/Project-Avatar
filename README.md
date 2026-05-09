# Project Avatar

**LLM-controlled autonomous modular drone platform.** Sub-250g. First mission: Splash (water gun drone).

## Status

9/9 subsystems complete — ready for hardware integration.

| System | Status | Path |
|--------|--------|------|
| CV Pipeline | ✅ YOLOv8 + ByteTrack + targeting | `splash/cv/` |
| MCP Tool Server | ✅ 13 LLM tools + MAVLink bridge | `splash/control/` |
| Payload Interface | ✅ Modular BasePayload + Registry + Splash | `splash/payload/` |
| State Machine | ✅ Thread-safe with transition guards | `splash/control/state_machine.py` |
| Telemetry WS | ✅ JSON WebSocket streamer for PWA | `splash/control/telemetry_ws_server.py` |
| PWA Frontend | ✅ React + TypeScript + PWA | `pwa/` |
| SITL Simulation | ✅ ArduPilot SITL + launch scripts | `sim/` |
| Validation | ✅ 20 tests (14 payload + 6 sim) | `sim/sim_validation.py` |
| Documentation | ✅ Architecture + Payload + Telemetry specs | `docs/` |

## Quick Start

```bash
# Simulation
cd sim && ./launch.sh --headless          # Start ArduPilot SITL

# MCP Server (another terminal)
cd splash/control && python3 mcp_server.py  # 13 LLM tools

# PWA Frontend (another terminal)
cd pwa && npm run dev                     # Dev server :5173

# Validation
python3 sim/sim_validation.py --mock      # 6 scenarios
```

## Architecture

```
LLM (Hermes) → MCP Server → MAVLink → ArduPilot FC → Payload Bus
Phone PWA → WebSocket → Telemetry Streamer → MAVLink Bridge
```

## Hardware BOM

$312 total — see `BLOCKERS_AND_USER_ACTION_ITEMS.md`

## License

MIT
