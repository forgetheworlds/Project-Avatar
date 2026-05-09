# Project Avatar — System Architecture

**May 2026** | Sub-250g autonomous drone with LLM control. First mission: Splash (water gun).

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MISSION CONTROL                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────┐    │
│  │ Phone PWA │   │ LLM/Hermes│   │ QGroundControl      │    │
│  │ (React)   │   │ (MCP)     │   │ (manual backup)     │    │
│  └────┬─────┘   └────┬──────┘   └──────────┬───────────┘    │
│       │              │                     │                │
│       └──────────────┼─────────────────────┘                │
│                      │ WiFi UDP                             │
└──────────────────────┼──────────────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   ESP32-S3      │  ← WiFi→MAVLink bridge
              │   (UART bridge) │     $7.49, 2g
              └────────┬────────┘
                       │ UART (115200 baud)
              ┌────────┴────────┐
              │  ArduPilot FC   │  ← MicoAir H743 AIO
              │  (flight stack) │     $59, 10g
              └──┬──────┬───────┘
                 │      │
          ┌──────┴──┐ ┌─┴──────────┐
          │ GPS     │ │ ESC (35A)   │
          │ GM10 V3 │ │ 4-in-1      │
          └─────────┘ └─┬───────────┘
                        │
                 ┌──────┴──────┐
                 │ 4× 1505     │
                 │ 3800KV      │
                 │ motors      │
                 └─────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     PAYLOAD BUS                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────┐    │
│  │ Pan/Tilt │   │ Pump     │   │ Hawkeye Thumb 4K     │    │
│  │ MG90S x2 │   │ MOSFET   │   │ (camera feed)         │    │
│  └──────────┘   └──────────┘   └──────────────────────┘    │
│                                                             │
│  Standard interface: I2C/PWM + 12V power + mechanical mount │
└─────────────────────────────────────────────────────────────┘
```

---

## Communication Stack

| Layer | Protocol | Transport | Notes |
|-------|----------|-----------|-------|
| LLM → drone | MCP tools → JSON → UDP | WiFi | Hermes calls MCP server |
| Phone → drone | MAVLink over WiFi | UDP via ESP32 | QGroundControl or custom PWA |
| FC → ESP32 | MAVLink v2 | UART 115200 | Bidirectional telemetry |
| FC → ESC | DShot300 | PWM | Motor control |
| FC → GPS | UBX binary | UART | M10Q GPS |
| CV → targeting | Internal IPC | Python objects | MacBook local |
| Targeting → MCP | HTTP/WS | localhost | Fire commands to MCP server |

---

## Subsystem Specifications

### 1. Flight Controller (ArduPilot)
- **Hardware:** MicoAir H743 AIO (STM32H743, BMI270 IMU, 35A 4-in-1 ESC)
- **Firmware:** ArduPilot Copter 4.6+
- **Features:** GPS waypoints, position hold, RTH, geofence, auto-land
- **Parameters:** Tuned for 3.5" frame, 1505 motors, 4S

### 2. ESP32 WiFi Bridge
- **Hardware:** XIAO ESP32-S3
- **Role:** MAVLink↔UDP passthrough, WiFi AP for phone/LLM connection
- **Power:** 3.3V from FC BEC
- **Range:** ~50m (WiFi), upgradeable with external antenna

### 3. Computer Vision (MacBook M3)
- **Detection:** YOLOv8n person detection @ 30fps
- **Tracking:** ByteTrack multi-object tracker
- **Color Filter:** HSV thresholding for team jersey identification
- **Aiming:** Kalman-filtered bbox center → servo pan/tilt angles
- **Fire Logic:** Distance < 3m AND target centered in deadzone

### 4. MCP Tool Server
- **Framework:** FastMCP (Python)
- **Tools:** arm, takeoff, land, goto, orbit, get_telemetry, get_camera_feed, identify_target, engage_target, protect_mode, disarm, rtb
- **Bridge:** pymavlink → UDP in SIM mode, UART via ESP32 in real mode
- **State Machine:** IDLE → ARMED → FLYING → ORBITING → ENGAGING → RETURNING

### 5. Splash Payload
- **Pump:** 12V micro diaphragm, MOSFET-switched
- **Pan/Tilt:** 2× MG90S metal gear servos, PCA9685 I2C controller
- **Reservoir:** 15ml syringe, quick-release mount
- **Nozzle:** 3D printed stream nozzle
- **Weight:** ~50g total, detachable for sub-250g compliance

### 6. Mobile Control (Future PWA)
- **Stack:** React + TypeScript, WebRTC for FPV feed
- **Features:** Live telemetry, target selection, mode switching, virtual joysticks, emergency stop
- **Connection:** WiFi to ESP32, MAVLink over WebSocket

---

## Data Flow: Protection Mode

```
1. User/LLM: protect_mode(center_lat, center_lon, radius=30m)
2. MCP Server: validates, sets state = ORBITING
3. ArduPilot: generates orbit waypoints, begins circling
4. Camera: streams frames to MacBook CV pipeline
5. CV: detects persons → tracks → checks if inside geofence
6. If target detected in zone:
   a. CV calculates pan/tilt angles
   b. Sends via MCP to servo controller
   c. When locked + in range → FIRE
   d. Pump MOSFET triggered for 0.5s burst
7. After engagement, resume orbit
8. On low battery or command → RTB
```

---

## State Machine

```
                    ┌─────────┐
                    │  IDLE   │
                    └────┬────┘
                         │ arm()
                    ┌────▼────┐
                    │  ARMED  │
                    └────┬────┘
                         │ takeoff()
                    ┌────▼────┐
                    │ FLYING  │
                    └────┬────┘
               ┌─────────┼─────────┐
               │         │         │
          goto()    orbit()   engage_target()
               │         │         │
          ┌────▼──┐ ┌───▼────┐ ┌──▼────────┐
          │GOTOING│ │ORBITING│ │ ENGAGING   │
          └───────┘ └───┬────┘ └──┬─────────┘
                        │         │ fire!
                   target in zone │
                        │    ┌────▼────┐
                        └────►  AIM   │
                             └────┬────┘
                                  │ locked
                             ┌────▼────┐
                             │  FIRE   │──► back to ORBIT
                             └─────────┘

    ANY STATE ──► disarm() or RTB ──► RETURNING ──► IDLE
    ANY STATE ──► low battery ──► RETURNING ──► IDLE
```

---

## Safety Architecture

| Layer | Mechanism |
|-------|-----------|
| Hardware | ArduPilot failsafe: loss of RC → RTH, low battery → land |
| Hardware | Physical disarm switch on drone |
| Software | MCP tools validate state before executing |
| Software | Geofence: max altitude, max radius from home |
| Software | Fire lock: won't fire unless in ENGAGING state |
| Network | Lost link → ArduPilot auto RTH after 5s |
| Manual | Phone emergency stop button (MCP disarm tool) |

---

## File Map

```
splash/
├── cv/
│   ├── main.py              — CV pipeline entry point
│   ├── detector.py          — YOLOv8 + HSV color filter
│   ├── tracker.py           — ByteTrack wrapper
│   ├── targeting.py         — Aim calculation + fire logic
│   └── test_cv.py           — Test harness
├── control/
│   ├── mcp_server.py        — FastMCP 13-tool server (payload-integrated)
│   ├── mavlink_bridge.py    — pymavlink connection
│   └── state_machine.py     — Drone state management
├── payload/
│   ├── __init__.py          — Public API exports
│   ├── base_payload.py      — Abstract BasePayload (614 lines)
│   ├── payload_registry.py  — Discovery, registration, health (490 lines)
│   ├── splash_payload.py    — Splash water gun implementation (450+ lines)
│   └── test_payload_interface.py — 14 validation tests

sim/
├── launch.sh                — ArduPilot SITL launcher
└── mavlink_control.py       — MAVLink test script

docs/
├── ARCHITECTURE.md          — Full system architecture
└── PAYLOAD_INTERFACE.md     — Payload spec and contract

build/                       — BOMs, wiring diagrams
BLOCKERS_AND_USER_ACTION_ITEMS.md
