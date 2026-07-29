# Project Boat — Claude Code Configuration

## Overview

Project Boat is a fully 3D-printed, LLM-controlled RC boat with a water cannon. Monohull (Deep V) design with jet drive, controlled via phone PWA over WiFi, with LLM autonomous control from a MacBook ground station.

## Architecture

**Single-motor monohull with jet drive, ESP32-S3 onboard, MacBook ground station.**

- **Hull:** 400-500mm deep-V monohull, printed in PLA in 2-3 interlocking segments
- **Self-righting:** Flood chamber mechanism (not catamaran geometry)
- **Propulsion:** 3D-printed jet drive (FJD design), zero hull penetrations
- **Motor:** Surpass Hobby KK 2838 brushless + 35A waterproof ESC + water-cooling jacket (~$38 CAD)
- **Steering:** SG90 servo on steerable jet nozzle (replaces rudder)
- **Compute:** ESP32-S3 (not plain ESP32) — handles PWM, PID, failsafe, WiFi
- **Ground station:** MacBook — Guardian, vision, LLM agent
- **Phone:** PWA control app, also serves as WiFi hotspot for boat+laptop LAN
- **Water cannon:** 5V submersible pump, aim with boat heading

## Critical Design Decisions (DO NOT DEVIATE)

- **Hull shape: Monohull (Deep V)** — NOT catamaran. Catamarans cannot self-right when flipped (stable inverted). Monohull with flood chamber self-rights.
- **Drive: 3D-printed jet drive** — NOT propeller. Eliminates hull penetrations (#1 leak source). Open-source FJD designs on RCGroups.
- **Motor: 2838 brushless** (Surpass Hobby KK combo) — NOT 3660 (overkill for 1.4kg hull)
- **Battery: 3S 2200mAh LiPo** — upgrade to 5200mAh for longer patrol
- **Onboard: ESP32-S3** — NOT plain ESP32, NOT Pi Zero, NOT Arduino. Dual-core 240MHz absorbs Guardian + PID.
- **WiFi: Phone as hotspot** — NOT ESP32 softAP (causes 200ms packet clusters)
- **LLM: Local on MacBook** — NOT cloud API (1-1.5s vs 3.5s)
- **Printing: Friend's printer** — NOT library (saves ~$33 CAD, no 8hr cap, can use PETG)

## Hardware

| Component | Specification | Source | Price (CAD) |
|-----------|--------------|--------|-------------|
| Motor + ESC | 2838 brushless + 35A waterproof + water-cooling jacket | qwinout.com | $38 |
| Battery | 3S 2200mAh 45C LiPo XT60 | AliExpress | $18-25 |
| ESP32-S3 | DevKit USB-C (N8R8 with PSRAM for camera) | AliExpress | $7 |
| Servo | SG90 (nozzle steering) | AliExpress | $4 |
| IMU | MPU-6050 (heading hold) | AliExpress | $4 |
| Water sensor | Rain/water-level module | AliExpress | $2 |
| GPS | NEO-6M (optional, for waypoint RTH) | AliExpress | $10 |
| Jet drive | 3D printed FJD design (28mm) | RCGroups/Printables | $0 |
| Water cannon | 5V submersible pump + MOSFET + tubing | AliExpress | $11 |
| Charger | 2S/3S USB balance charger | Amazon | $12-16 |
| Wiring | Silicone wire, XT60, heat-shrink, sealant | Mixed | $8 |
| PLA | ~250g for monohull (friend's printer) | Retail PLA | $5 |
| **Total** | | | **~$117-150** |

## Pin Assignments (ESP32-S3)

| Function | GPIO | Protocol | Notes |
|----------|------|----------|-------|
| ESC (motor) | 13 | PWM 50Hz | ledc channel 0 |
| Nozzle servo | 12 | PWM 50Hz | ledc channel 1 |
| Pump MOSFET | 14 | Digital | Gate; interlock throttle <30% + water dry |
| Battery ADC | 4 | Analog (ADC1) | 10k+4.7k divider — **not** GPIO 34 |
| Water sensor | 5 | Analog (ADC1) | **not** GPIO 35 (PSRAM conflict on N8R8) |
| I2C SDA | 8 | I2C | MPU-6050 (+ optional QMC5883L) |
| I2C SCL | 9 | I2C | DevKitC-1 defaults; GPIO 22 does not exist on S3 |
| GPS RX/TX | 17/18 | UART2 | Optional NEO-6M |

> CAD printables live in `hardware/fable-cad/` (`DESIGN.md`).

## Control Architecture

```
L0: Hardware reflexes     — ESC brake, servo stops, battery fuse          [0ms, physics]
L1: Stabilization PID     — ESP32 core 0, 50Hz, IMU heading-hold         [20ms]
L2: Onboard guardian      — ESP32 core 1, 10Hz, GPS/geofence/failsafe   [100ms]
L3: Ground guardian       — MacBook, 1-10Hz, skill validation, vision    [0.1-1s]
L4: LLM pilot             — MacBook local model, 0.2-1Hz, mission goals  [1-3.5s]
L5: Human override        — Phone PWA, big red STOP button               [300ms]
```

**Key rule:** Anything that must react in under 1 second lives on the boat. LLM steers the mission, never the hull.

## Phase Plan

| Phase | What | Status |
|-------|------|--------|
| 0 | CAD design (monohull + jet drive + electronics) | In progress |
| 1 | Print + assemble + waterproof | Planned |
| 2 | Phone PWA control via WiFi | Planned |
| 3 | LLM autonomous control via ground station | Future |
| 4 | Skill library + multi-agent coordination | Future |

## Repository Structure

```
catamaran/
├── CLAUDE.md              # This file
├── docs/                  # Design docs, specs
│   ├── ARCHITECTURE.md    # System architecture
│   └── MASTER_BRIEFING.md # Full project spec
├── hardware/
│   ├── fable-cad/         # Printable build123d sources + STEP/STL
│   │   ├── hull/          # Monohull deep-V segments
│   │   ├── jetdrive/      # 3D printed jet drive
│   │   ├── deck/          # Mid + stern lids
│   │   ├── electronics/   # ESP32 tray + battery cradle
│   │   ├── cannon/        # Water cannon + optional turret
│   │   ├── print/         # Consolidated STLs for slicer
│   │   └── DESIGN.md      # CAD design contract
│   └── bom/               # Bill of materials
├── firmware/              # ESP32-S3 firmware
├── software/
│   ├── ground_station/    # Guardian, vision, LLM
│   └── phone_app/         # PWA control
└── research/              # Design research, sources
```
