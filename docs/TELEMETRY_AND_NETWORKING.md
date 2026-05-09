# Telemetry & Networking Architecture

**Project Avatar** | May 2026 | Version 1.0.0

## 1. Overview

The Avatar telemetry and networking stack connects the drone to ground control (LLM, PWA, QGroundControl) over WiFi via an ESP32-S3 bridge. This document specifies the data flows, message schemas, update rates, bandwidth budget, link monitoring, and fallback strategies.

### 1.1 Architecture Diagram

```
                          WiFi 2.4GHz (~50m range)
┌──────────────────────────────────────────────────────────────────┐
│                        GROUND STATION                            │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  MCP Server  │   │  Phone PWA   │   │  QGroundControl      │ │
│  │  (Python)    │   │  (React)     │   │  (backup)            │ │
│  │              │   │              │   │                      │ │
│  │  UDP:14551   │   │  WS:8080     │   │  UDP:14550           │ │
│  │  MAVLink raw │   │  JSON stream │   │  MAVLink raw         │ │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘ │
│         │                  │                       │             │
│         └──────────────────┼───────────────────────┘             │
│                            │ UDP/TCP                            │
└────────────────────────────┼────────────────────────────────────┘
                             │
                    ┌────────┴──────────┐
                    │   ESP32-S3 Bridge  │  MAVLink ↔ WiFi relay
                    │                    │
                    │  WiFi AP mode      │  SSID: avatar-xxxx
                    │  DHCP server       │  IP: 192.168.4.1
                    │  MAVLink forwarder │  UDP:14550 → UART
                    │  Telemetry relay   │  WS:8080 for JSON stream
                    │  Weight: 2g        │
                    │  Power: 300mA @3.3V│
                    └────────┬───────────┘
                             │ UART 115200 baud (4-wire)
                    ┌────────┴───────────┐
                    │  ArduPilot FC      │
                    │  (MicoAir H743)    │
                    │                    │
                    │  TELEM1 port       │  Serial 1
                    │  SRx parameters    │  Message rate control
                    │  FRSky passthrough │
                    └────────────────────┘
```

### 1.2 Communication Layers

| Layer | Protocol | Transport | Bandwidth | Latency | Reliability |
|-------|----------|-----------|-----------|---------|-------------|
| Flight Control | MAVLink v2 | UDP (WiFi) → UART | ~8 KB/s | <20ms | CRITICAL |
| Telemetry Stream | MAVLink v2 | UDP (WiFi) → UART | ~5 KB/s | <50ms | HIGH |
| FPV Video | WebRTC / RTSP | WiFi | ~500 KB/s | <100ms | MEDIUM |
| PWA Telemetry | JSON over WebSocket | WiFi → ESP32 WS server | ~2 KB/s | <100ms | MEDIUM |
| PWA Commands | JSON over WebSocket | WiFi → ESP32 → MAVLink | <1 KB/s | <100ms | HIGH |

---

## 2. Telemetry Data Schema

### 2.1 Message Types and Update Rates

The telemetry system publishes MAVLink messages at configurable rates via ArduPilot SRx parameters.

| MAVLink Message | Rate (Hz) | Size (bytes) | Source | Contents |
|-----------------|-----------|-------------|--------|----------|
| HEARTBEAT | 1 | 9 | FC | type, autopilot, base_mode, custom_mode, system_status |
| GLOBAL_POSITION_INT | 10 | 28 | GPS/FC | lat (1e7°), lon (1e7°), alt (mm), relative_alt (mm), vx/vy/vz (cm/s), hdg (cdeg) |
| ATTITUDE | 10 | 28 | IMU | roll/pitch/yaw (rad), rollspeed/pitchspeed/yawspeed (rad/s) |
| BATTERY_STATUS | 1 | 36 | FC ADC | voltages[], current_battery (10mA), battery_remaining (%), consumption (mAh) |
| VFR_HUD | 10 | 20 | FC | airspeed (m/s), groundspeed (m/s), heading (deg), throttle (%), alt (m), climb (m/s) |
| GPS_RAW_INT | 5 | 30 | GPS | fix_type, satellites_visible, lat/lon/alt, hdop, vdop, cog (cdeg), vel (cm/s) |
| SYS_STATUS | 1 | 31 | FC | onboard_control_sensors, load (d%), voltage_battery (mV), current_battery (10mA), drop_rate_comm |
| RC_CHANNELS | 5 | 42 | RX | RC channel values (for manual override detection) |
| MISSION_CURRENT | 0.5 | 6 | FC | Current waypoint index |
| STATUSTEXT | on-change | variable | FC | Human-readable status messages (errors, warnings) |
| COMMAND_ACK | on-command | 3 | FC | Command acknowledgement |
| LOCAL_POSITION_NED | 10 | 28 | EKF | x/y/z (m), vx/vy/vz (m/s) — local frame |

**Total downstream bandwidth:** ~13 KB/s (telemetry only, no FPV)

### 2.2 Python Telemetry Dataclass

The `MavlinkBridge` normalizes raw MAVLink into a `Telemetry` dataclass:

```python
@dataclass
class Telemetry:
    # Position (from GLOBAL_POSITION_INT)
    lat: float          # Decimal degrees
    lon: float          # Decimal degrees
    alt: float          # Relative altitude, meters

    # Attitude (from ATTITUDE)
    roll: float         # Degrees
    pitch: float        # Degrees
    yaw: float          # Degrees
    heading: float      # Degrees (from GPS course-over-ground)

    # Velocity (from GLOBAL_POSITION_INT)
    vx: float           # m/s, north
    vy: float           # m/s, east
    vz: float           # m/s, down
    groundspeed: float  # m/s
    airspeed: float     # m/s
    climb: float        # m/s

    # Battery (from BATTERY_STATUS)
    battery_voltage: float       # Volts
    battery_current: float       # Amps
    battery_remaining: int       # Percent (0–100)

    # State (from HEARTBEAT)
    armed: bool
    mode: str                    # "GUIDED", "CIRCLE", "LAND", "RTL", etc.
    gps_fix: int                 # 0=no fix, 3=3D fix
    gps_sats: int                # Number of satellites

    # Link health
    heartbeat_age_s: float       # Seconds since last heartbeat
    timestamp: float             # Unix timestamp of last position update
```

### 2.3 Telemetry JSON Format

The MCP server exposes telemetry as JSON via `get_telemetry()`:

```json
{
  "status": "success",
  "telemetry": {
    "position": {"lat": 43.5890, "lon": -79.6441},
    "altitude_m": 10.5,
    "attitude": {"roll": 2.1, "pitch": -1.3, "yaw": 45.7, "heading": 44.2},
    "velocity": {"vx": 0.5, "vy": 0.3, "vz": 0.1, "groundspeed": 2.1, "airspeed": 1.8, "climb": 0.1},
    "battery": {"voltage": 16.2, "current": 3.5, "remaining_pct": 78},
    "state": {"armed": true, "mode": "CIRCLE", "gps_fix": 3, "gps_sats": 14},
    "link": {"heartbeat_age_s": 0.1}
  },
  "state": {
    "state": "ORBITING",
    "is_airborne": true,
    "context": {
      "target_description": "person in red shirt",
      "target_acquired": true,
      "shots_fired": 3,
      "protect_zone": {"center": [43.589, -79.644], "radius_m": 20}
    }
  },
  "payloads": {
    "splash_0": {
      "health": {
        "status": "OK",
        "power": {"voltage_v": 12.0, "current_ma": 200.0, "rail_enabled": true},
        "faults": [],
        "payload_specific": {
          "pan_angle_deg": 45.0,
          "tilt_angle_deg": 110.0,
          "pump_active": false,
          "reservoir_ml": 12.5,
          "fire_count": 3,
          "deadzone_px": 30
        }
      },
      "state": "ACTIVE",
      "type": "splash"
    }
  }
}
```

---

## 3. Networking Architecture

### 3.1 ESP32-S3 WiFi Bridge

The ESP32-S3 serves as the sole communication bridge between the drone and ground.

| Property | Value |
|----------|-------|
| Module | XIAO ESP32-S3 (Seeed Studio) |
| Weight | 2g |
| Power | 3.3V @ 300mA (from FC BEC) |
| WiFi | 802.11 b/g/n, 2.4GHz, AP mode |
| SSID | `avatar-XXXX` (last 4 of MAC) |
| IP | 192.168.4.1 (static) |
| DHCP Range | 192.168.4.10–192.168.4.50 |
| Range | ~50m line-of-sight (stock antenna), ~100m with external |
| Max clients | 4 |
| UART | 115200 baud, 8N1, TELEM1 port |

#### ESP32 Bridge Functions

1. **MAVLink Passthrough** (primary): Forwards all MAVLink packets bidirectionally between UART (FC) and UDP to ground clients.
2. **WebSocket Telemetry Server** (port 8080): Streams parsed telemetry as JSON for the PWA.
3. **Video Relay** (future): Forwards RTSP/WebRTC FPV feed from Hawkeye camera.
4. **OTA Updates**: ESP32 firmware updatable over WiFi.

#### ESP32 Firmware Pseudocode

```cpp
// Telemetry packets: UART → UDP broadcast to all clients
// Command packets: UDP → UART (from any client)
// WebSocket: JSON telemetry stream + command reception

WiFiServer wsServer(8080);      // WebSocket for PWA
WiFiUDP udp;                    // MAVLink UDP relay on 14550

void setup() {
    WiFi.softAP("avatar-XXXX", "avatar1234");
    Serial2.begin(115200, SERIAL_8N1, RX2, TX2);  // UART to FC
    udp.begin(14550);
    wsServer.begin();
}

void loop() {
    // Forward FC → WiFi (downlink)
    while (Serial2.available()) {
        uint8_t c = Serial2.read();
        mavlink_parse_char(MAVLINK_COMM_0, c, &msg, &status);
        if (status == MAVLINK_FRAMING_OK) {
            // UDP broadcast to all clients
            udp.beginPacket(broadcastIP, 14550);
            udp.write(buf, len);
            udp.endPacket();

            // Also push to WebSocket clients as JSON
            if (msg.msgid == MAVLINK_MSG_ID_GLOBAL_POSITION_INT)
                wsBroadcast(telemetryToJSON(msg));
        }
    }

    // Forward WiFi → FC (uplink)
    // (received UDP packets → UART)
}
```

### 3.2 WiFi Topology

```
                    Internet
                        │
                        ▼
              ┌─────────────────┐
              │  MacBook/Phone  │  ← Ground control
              │  (WiFi client)  │     Must disconnect from home WiFi
              │                 │     and connect to drone's AP
              │  MCP Server     │     when in flight.
              │  PWA Browser    │
              │  QGroundControl │
              └────────┬────────┘
                       │ WiFi client mode
                       │ IP: 192.168.4.x (DHCP)
              ┌────────▼────────┐
              │  ESP32-S3       │  ← Drone AP
              │  SSID: avatar-* │
              │  192.168.4.1    │
              └────────┬────────┘
                       │ UART
              ┌────────▼────────┐
              │  ArduPilot FC   │
              └─────────────────┘
```

**Key constraint**: Ground station must connect to the drone's WiFi AP, meaning it loses internet access. For LLM control via Hermes, the LLM runs locally (on laptop) or the drone connects to a phone hotspot instead (ESP32 in STA mode).

### 3.3 Dual-Mode WiFi (ESP32)

For LLM integration scenarios where internet is needed:

| Mode | ESP32 Role | Ground Station | Internet | Use Case |
|------|-----------|----------------|----------|----------|
| **AP Mode** (default) | Drone is AP | Connects as client | No | Local MCP + PWA, no cloud LLM |
| **STA Mode** | Drone connects to phone hotspot | Phone runs hotspot | Yes | LLM on phone/cloud, PWA on phone |
| **STA+AP** (future) | Both | Ground connects to drone | Via phone | Best: PWA direct, LLM via internet |

### 3.4 Bandwidth Budget

| Stream | Downlink (drone→ground) | Uplink (ground→drone) | Notes |
|--------|------------------------|----------------------|-------|
| MAVLink telemetry | 10 KB/s | — | Continuous |
| MAVLink commands | — | 0.5 KB/s | Burst only |
| MAVLink params | 1 KB/s (on request) | 0.5 KB/s | Manual |
| FPV video (H.264, 480p) | 200 KB/s | — | Future, via separate UDP |
| WebSocket JSON telemetry | 2 KB/s | — | For PWA |
| **Total (no FPV)** | **~13 KB/s** | **~1 KB/s** | Safe within WiFi limits |
| **Total (with FPV)** | **~213 KB/s** | **~1 KB/s** | WiFi can handle; test latency |

**WiFi 2.4GHz 802.11n theoretical:** 150 Mbps (18.75 MB/s). Real-world: ~5–10 Mbps. Even with FPV, we use ~1.7 Mbps — well within limits.

---

## 4. Link Monitoring & Resilience

### 4.1 Link Quality Metrics

| Metric | Source | Healthy Range | Action on Degradation |
|--------|--------|---------------|----------------------|
| Heartbeat age | MAVLink HEARTBEAT | <1s | >3s: warning, >5s: auto RTL |
| RSSI | ESP32 WiFi | >-70 dBm | <-80 dBm: "low signal" warning |
| Packet loss | MAVLink seq gaps | <1% | >5%: reduce telemetry rate |
| GPS fix | GPS_RAW_INT.fix_type | 3 (3D fix) | <3: disable auto missions |
| GPS HDOP | GPS_RAW_INT.eph | <2.0 | >3.0: degrade to loiter |
| Battery | BATTERY_STATUS | >20% | <20%: RTB warning, <10%: force land |

### 4.2 Failsafe Hierarchy

```
Level 1: Telemetry degraded (heartbeat >3s)
  → Log warning, notify LLM/operator
  → Reduce message rates (SRx params halved)

Level 2: Link lost (heartbeat >5s)
  → ArduPilot auto-triggers RTL (FS_GCS_ENABLE=1)
  → Payloads emergency-stopped
  → Drone returns to home position

Level 3: GPS lost (fix_type < 3)
  → Auto-switch to ALT_HOLD + LAND
  → Requires manual recovery

Level 4: Critical battery (<10%)
  → Force LAND at current position
  → Ignore all commands except disarm
```

### 4.3 MAVLink Message Rate Control

ArduPilot SRx parameters control telemetry rates per serial port:

```
SR1_RAW_SENS  = 5   (5 Hz)   — IMU, baro
SR1_EXT_STAT  = 2   (2 Hz)   — GPS, attitude
SR1_RC_CHAN   = 5   (5 Hz)   — RC channels
SR1_POSITION  = 10  (10 Hz)  — global position
SR1_EXTRA1    = 10  (10 Hz)  — attitude
SR1_EXTRA2    = 5   (5 Hz)   — battery, VFR_HUD
SR1_EXTRA3    = 1   (1 Hz)   — system status
SR1_PARAMS    = 0   (0 Hz)   — only on request
```

These are set once during FC configuration and can be adjusted dynamically via `MAV_CMD_DO_SET_MESSAGE_INTERVAL`.

---

## 5. PWA Telemetry Stream

### 5.1 Design

The PWA needs real-time telemetry without parsing MAVLink binary. Two approaches:

**Option A: WebSocket JSON from ESP32**
- ESP32 runs WebSocket server on port 8080
- Parses MAVLink → JSON → broadcasts to connected PWA clients
- Pro: PWA is simple (JSON only), no pymavlink needed
- Con: ESP32 CPU load, limited to basic messages

**Option B: WebSocket JSON from MCP Server** (recommended)
- MCP server (on laptop) parses MAVLink → JSON
- WebSocket server streams to PWA
- Pro: Full telemetry, payload status, state machine context
- Con: Requires MCP server running (laptop-based)

### 5.2 WebSocket Telemetry Protocol

Connect: `ws://{mcp_host}:8888/telemetry`

**Client → Server** (subscribe):
```json
{"type": "subscribe", "channels": ["telemetry", "payloads", "alerts"]}
```

**Server → Client** (stream):
```json
{
  "type": "telemetry",
  "timestamp": 1746776123.456,
  "data": {
    "position": {"lat": 43.589, "lon": -79.644},
    "altitude_m": 10.5,
    "attitude": {"roll": 2.1, "pitch": -1.3, "yaw": 45.7},
    "groundspeed": 2.1,
    "battery_pct": 78,
    "mode": "CIRCLE",
    "armed": true,
    "gps_sats": 14,
    "heartbeat_age_s": 0.1
  }
}
```

```json
{
  "type": "payloads",
  "timestamp": 1746776123.456,
  "data": {
    "splash_0": {
      "pan_deg": 45.0,
      "tilt_deg": 110.0,
      "pump_active": false,
      "reservoir_ml": 12.5,
      "fire_count": 3
    }
  }
}
```

```json
{
  "type": "alert",
  "timestamp": 1746776123.456,
  "severity": "warning",
  "message": "Battery at 18% — consider RTB"
}
```

---

## 6. FPV Video (Future)

### 6.1 Video Pipeline

```
Hawkeye Thumb 4K → ESP32-S3 WiFi → WebRTC → PWA Browser
                   (via USB UVC)
```

The Hawkeye camera outputs UVC over USB. ESP32-S3 streams H.264 via WebRTC to the PWA browser at 480p 30fps (~200 KB/s).

### 6.2 Latency Budget

| Segment | Latency |
|---------|---------|
| Camera capture | ~33ms (30fps) |
| H.264 encode | ~20ms |
| ESP32 relay | ~5ms |
| WiFi transmission | ~2ms |
| Browser decode | ~10ms |
| **Total glass-to-glass** | **~70ms** |

Target: <100ms total, acceptable for FPV.

---

## 7. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Open WiFi AP | WPA2-PSK with strong password. SSID not broadcast (hidden). |
| Command injection | MAVLink sysid filtering: only accept commands from authorized system IDs |
| Telemetry eavesdropping | WPA2 encryption on WiFi layer. No plaintext telemetry over air. |
| ESP32 firmware tampering | Signed OTA updates, secure boot |
| Denial of service | Max 4 WiFi clients. Rate-limit UDP. |

---

## 8. Implementation Status

| Component | Status | File |
|-----------|--------|------|
| MAVLink bridge (UDP) | ✅ Complete | `splash/control/mavlink_bridge.py` (596 lines) |
| Telemetry dataclass | ✅ Complete | `splash/control/mavlink_bridge.py` — `Telemetry` |
| Telemetry background thread | ✅ Complete | `splash/control/mavlink_bridge.py` — `_telemetry_loop` |
| MCP get_telemetry() tool | ✅ Complete | `splash/control/mcp_server.py` — tool #6 |
| ESP32 firmware | ⬜ Pending | ESP32 MAVLink bridge (C++) |
| WebSocket telemetry server | ⬜ Pending | For PWA streaming |
| FPV video relay | ⬜ Pending | WebRTC from Hawkeye |
| Link monitoring alerts | ⬜ Pending | Heartbeat watchdog, RSSI display |
| PWA telemetry dashboard | ⬜ Pending | React component (Task 4) |

---

## 9. Related Documents

- `docs/ARCHITECTURE.md` — Full system architecture
- `docs/PAYLOAD_INTERFACE.md` — Payload spec
- `splash/control/mavlink_bridge.py` — MAVLink bridge implementation
- `splash/control/mcp_server.py` — MCP tool server (tools #6, #7, #13)
- `BLOCKERS_AND_USER_ACTION_ITEMS.md` — Hardware BOM
