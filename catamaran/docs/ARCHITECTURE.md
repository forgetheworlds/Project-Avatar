# Project Boat — System Architecture

## 1. Overview

Monohull deep-V boat, 3D-printed jet drive, ESP32-S3 onboard compute, MacBook ground station. Phone as WiFi hotspot for local LAN.

```
┌─────────────────────────────────────────────────────┐
│                  GROUND STATION (MacBook)            │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ Guardian Process (1-10Hz)                     │   │
│  │ - Skill validation (bounds, timeouts)         │   │
│  │ - Vision: YOLO-nano on QVGA frames (80ms)    │   │
│  │ - Camera frame selection (5-10fps)            │   │
│  └──────────────────┬───────────────────────────┘   │
│                     │                               │
│  ┌──────────────────┴───────────────────────────┐   │
│  │ LLM Pilot (local model, 0.2-1Hz)             │   │
│  │ - 8-9B Q4 on MacBook (25-30 tok/s)           │   │
│  │ - JSON setpoints (20-40 tokens, ~1-1.5s)     │   │
│  │ - Code-as-policy for pre-mission planning     │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ Phone PWA (Human Override)                    │   │
│  │ - Big red STOP, manual joystick               │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │ WiFi LAN (phone hotspot)
┌──────────────────────┼──────────────────────────────┐
│                BOAT (ESP32-S3)                       │
│                                                     │
│  ┌────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ MPU-6050   │  │ Water     │  │ 2838 Brushless │  │
│  │ IMU (I2C)  │  │ Sensor    │  │ + 35A ESC     │  │
│  │            │  │ (ADC)     │  │ (PWM GPIO 13) │  │
│  └─────┬──────┘  └─────┬─────┘  └───────┬───────┘  │
│        │               │                 │          │
│  ┌─────┴───────────────┴─────────────────┴────────┐ │
│  │           ESP32-S3 (240MHz dual-core)           │ │
│  │  Core 0: 50Hz PID (heading hold → PWM)         │ │
│  │  Core 1: 10Hz guardian (GPS, failsafe, geofence)│ │
│  └─────────────────────┬──────────────────────────┘ │
│                        │                            │
│  ┌──────────┐  ┌───────┴──────┐  ┌──────────────┐  │
│  │ SG90     │  │ 5V Pump     │  │ NEO-6M GPS   │  │
│  │ Nozzle   │  │ (MOSFET)    │  │ (UART2)      │  │
│  │ (PWM 12) │  │ (GPIO 14)   │  │ (optional)   │  │
│  └──────────┘  └─────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 2. Why ESP32-S3 Only

| Option | Cost | Latency | Works? |
|--------|------|---------|--------|
| Pi Zero + Arduino | ~$30 | Two devices, serial bridge | Overkill |
| ESP32 (plain) | ~$4 | Good | Works but no PSRAM for camera |
| **ESP32-S3** | **~$7** | **Best** | **✅ Dual-core, PSRAM, USB-C** |

ESP32-S3 absorbs the entire Guardian function that required a separate Pi Zero in Avatar:
- **Dual-core 240MHz** — PID on core 0, guardian on core 1
- **8MB PSRAM** — camera frame buffering
- **WiFi** — WebSocket server, phone hotspot client
- **16 PWM channels** — ESC, nozzle servo, pump
- **2x 12-bit ADC** — battery voltage, water sensor
- **I2C** — MPU-6050 IMU
- **USB-C** — direct programming, no FTDI needed

## 3. Communication Protocol

### WiFi Topology
**Phone = hotspot.** Boat and MacBook join the phone's LAN. Not ESP32 softAP (causes 200ms packet clusters on second client connection).

| Channel | Transport | Direction | Content |
|---------|-----------|-----------|---------|
| Commands | WebSocket JSON | Phone/MacBook → ESP32 | throttle, steer, cannon |
| Telemetry | WebSocket JSON | ESP32 → Phone/MacBook | heading, battery, GPS |
| Vision | MJPEG HTTP | ESP32 → MacBook | QVGA @ 5-10fps |

### Command Format

```json
{"action":"throttle","value":50}    // -100 to 100
{"action":"steer","value":-30}      // -90 to 90 (nozzle angle)
{"action":"cannon","value":1}       // 0 or 1 (pump on/off)
```

### Telemetry Format

```json
{"heading":215.0,"bat":11.2,"lat":43.5,"lon":-79.6,"fix":3,"sats":8}
```

## 4. Control Loop Hierarchy

| Loop | Runs On | Frequency | Latency | Role |
|------|---------|-----------|---------|------|
| L0 Hardware | ESC + wiring | 0ms | 0ms | Brake, servo stops, fuse |
| L1 Stabilization | ESP32 core 0 | 50Hz | 20ms | PID heading-hold, PWM output |
| L2 Guardian | ESP32 core 1 | 10Hz | 100ms | GPS, geofence, 2s failsafe |
| L3 Ground Guardian | MacBook | 1-10Hz | 0.1-1s | Skill validation, vision |
| L4 LLM Pilot | MacBook | 0.2-1Hz | 1-3.5s | Mission goals |
| L5 Human | Phone PWA | ~250ms | 300ms | Override |

**Fail-safe:** No command for 2s → throttle zero, nozzle center.

## 5. Power System

```
3S LiPo (11.1V nom, 12.6V full, 9.0V empty)
  ├── XT60 connector
  │   ├── ESC (direct) → 2838 Motor
  │   └── BEC (5V/3A) → ESP32-S3 + servo + pump
```

Voltage divider: Battery+ → 10kΩ → GPIO 34 → 4.7kΩ → GND
- 12.6V → 2.85V at GPIO 34 (safe for ESP32 ADC)

## 6. GPIO Pinout

| GPIO | Connection | Signal | Notes |
|------|-----------|--------|-------|
| 13 | ESC | PWM 50Hz | 2838 brushless motor |
| 12 | Nozzle servo | PWM 50Hz | SG90, jet nozzle steering |
| 14 | Pump MOSFET | Digital out | Water cannon on/off |
| 34 | Battery divider | ADC input | Voltage sense |
| 35 | Water sensor | ADC input | Ingress detection |
| 21 | MPU-6050 SDA | I2C data | IMU |
| 22 | MPU-6050 SCL | I2C clock | IMU |
| 16 | GPS TX | UART2 RX | NEO-6M (optional) |
| 17 | GPS RX | UART2 TX | NEO-6M (optional) |

## 7. Self-Righting: Flood Chamber

```
Upright (normal):              Capsized (flooded):
┌──────────────┐              ┌──────────────┐
│ Electronics  │              │ Waterline    │
│ Bay (sealed) │              │ ─────────── │
│──────────────│              │ Electronics  │
│   Flood      │ ← empty     │ Bay (sealed) │
│   Chamber    │              │──────────────│
│──────────────│              │   Flood      │ ← flooded
│   Ballast    │              │   Chamber    │   (water weight)
│   (battery)  │              │──────────────│
└──────────────┘              │   Ballast    │
                              └──────────────┘
                              → rolls back upright
```

Sealed side chamber with hole near waterline. Capsized → floods → offset weight rolls boat back. Throttle burst clears water.

## 8. Project Structure

```
catamaran/
├── CLAUDE.md
├── docs/
│   ├── MASTER_BRIEFING.md
│   └── ARCHITECTURE.md          ← this file
├── hardware/
│   ├── cad/                     # build123d Python sources + STEP exports
│   │   ├── hull/                # Deep-V monohull segments
│   │   ├── jetdrive/            # FJD jet drive (28mm)
│   │   ├── electronics/         # ESP32 tray, battery mount
│   │   └── cannon/              # Water cannon assembly
│   └── bom/
│       └── BOM.md
├── firmware/
│   └── boat_control.ino         # ESP32-S3 firmware
├── software/
│   ├── phone_app/               # PWA: index.html + app.js
│   └── ground_station/
│       └── gcs.py               # Python ground station
├── research/
│   └── designs/jdobry-waterjet/ # OpenSCAD jet drive reference
└── scripts/
```
