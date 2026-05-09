# Splash MCP Tool Server — LLM Drone Control

MCP (Model Context Protocol) server that gives an LLM (Hermes) the ability to control
the Splash water-gun drone. Bridges MCP → MAVLink commands for ArduPilot.

## Architecture

```
LLM (Hermes)
    │  MCP protocol (JSON-RPC over stdio)
    ▼
mcp_server.py  ← FastMCP server, 12 tools
    │
    ▼
state_machine.py  ← Thread-safe state machine (IDLE→ARMED→FLYING→...)
    │
    ▼
mavlink_bridge.py  ← pymavlink UDP/TCP connection manager
    │
    ▼
ArduPilot (SITL or real hardware via ESP32 WiFi bridge)
```

## Files

| File | Purpose |
|------|---------|
| `mcp_server.py` | FastMCP server with 12 tools, resources, lazy MAVLink connect |
| `mavlink_bridge.py` | pymavlink connection, telemetry, MAVLink commands |
| `state_machine.py` | Thread-safe drone state machine with transition guards |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

## 12 MCP Tools

| # | Tool | Description | Precondition |
|---|------|-------------|--------------|
| 1 | `arm()` | Arm motors | IDLE or DISARMED |
| 2 | `takeoff(altitude_meters)` | Take off to altitude | ARMED |
| 3 | `land()` | Land at current position | Airborne |
| 4 | `goto(lat, lon, alt)` | Fly to GPS coordinates | Airborne |
| 5 | `orbit(center_lat, center_lon, radius_m, altitude_m)` | Orbit a point | Airborne |
| 6 | `get_telemetry()` | Return position, altitude, battery, attitude | Any |
| 7 | `get_camera_feed()` | Return camera/frame info (placeholder) | Any |
| 8 | `identify_target(description)` | Set target description for CV | Any |
| 9 | `engage_target()` | Activate track+aim+fire | Airborne + target set |
| 10 | `protect_mode(center_lat, center_lon, radius_m)` | Orbit + detect + fire | Airborne |
| 11 | `disarm()` | Emergency disarm | ANY |
| 12 | `rtb()` | Return to home (RTL) | Airborne |

## State Machine

```
IDLE ──► ARMED ──► TAKING_OFF ──► FLYING ──► ORBITING
  ▲                      │            │  ▲          │
  │                      ▼            ▼  │          ▼
  ◄── LANDING ◄─── RETURNING ◄─── ENGAGING ◄──
  
DISARMED ◄── (emergency from any state)
ERROR    ◄── (fault / lost connection)
```

## Quick Start

### 1. Install dependencies

```bash
cd splash/control
pip install -r requirements.txt
```

### 2. Start SITL simulator (separate terminal)

```bash
cd ../sim
./launch.sh --headless
```

Wait for `Got MAVLink msg: COMMAND_LONG...` or similar heartbeat message.

### 3. Start the MCP server

```bash
python mcp_server.py
```

The server connects lazily to MAVLink on the first tool call, so you can
start SITL after the server if needed.

### 4. Configure with Hermes (Claude Desktop / Codex / other MCP client)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "splash-drone": {
      "command": "python",
      "args": ["/path/to/Project-Avatar/splash/control/mcp_server.py"],
      "env": {
        "SIM_MODE": "true"
      }
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_MODE` | `true` | `true` = UDP to SITL, `false` = TCP to ESP32 bridge |
| `SIM_HOST` | `127.0.0.1` | SITL host IP |
| `SIM_PORT` | `14551` | SITL MAVLink port (scripts port) |
| `REAL_HOST` | `192.168.4.1` | ESP32 WiFi bridge IP |
| `REAL_PORT` | `14550` | ESP32 MAVLink TCP port |

## Real Hardware Mode

When `SIM_MODE=false`, the bridge connects via TCP to the ESP32-S3 WiFi bridge
that forwards MAVLink serial data from the flight controller.

```bash
SIM_MODE=false python mcp_server.py
```

## MCP Resources

The server exposes two informational resources for client introspection:

- `splash://state` — Current drone state machine + context
- `splash://health` — Connection health + telemetry summary

## Testing Without SITL

The state machine and validation logic work standalone. You can invoke tools
and see state transition validation without a MAVLink connection (the bridge
will fail to connect, but state guards and parameter validation work).

## Project Avatar

- **Mission:** Splash — water gun drone for Senior Assassins
- **Hardware:** 3.5" quad, ArduPilot, ESP32-S3 WiFi bridge, MicoAir H743 FC
- **LLM Control:** MCP tools → UDP → MAVLink → ArduPilot
- **CV Pipeline:** YOLOv8 + ByteTrack + pan-tilt servo turret (see `../cv/`)
