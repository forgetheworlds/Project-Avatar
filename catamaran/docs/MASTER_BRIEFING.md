# Project Boat — Master Briefing

> **LLM-Controlled Autonomous RC Boat with Water Cannon**
> Monohull deep-V, jet drive, ESP32-S3, ~$130 CAD (friend prints)
> Status: Phase 0 — CAD Design

---

## 1. What It Is

A fully 3D-printed RC boat you control from your phone, with LLM autonomous control as a later phase. The boat is a monohull deep-V with a 3D-printed jet drive, powered by a single 2838 brushless motor. It has a water cannon that fires lake water. All intelligence runs on your MacBook; the ESP32-S3 handles only real-time control.

**Why monohull + jet drive?**
- Monohull self-rights via flood chamber (catamaran cannot — stable inverted)
- Jet drive eliminates hull penetrations (#1 leak source in home-built boats)
- Single motor is simpler, cheaper, and gives a clean PID plant

## 2. Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Hull | Monohull deep-V, 400-500mm | Self-righting flood chamber, fewer joints, better in chop |
| Drive | 3D-printed jet drive (FJD) | Zero hull penetrations, free (printed with hull) |
| Motor | 2838 brushless + 35A ESC | Right-sized for 1.4kg hull, water-cooled |
| Battery | 3S 2200mAh LiPo | ~47min patrol, upgrade to 5200mAh later |
| Onboard | ESP32-S3 (not Pi, not Arduino) | Dual-core 240MHz absorbs Guardian + PID |
| WiFi | Phone hotspot (not ESP32 softAP) | Prevents 200ms packet clusters |
| LLM | Local model on MacBook | ~1-1.5s vs 3.5s cloud API |
| Printing | Friend's printer | Saves ~$33 CAD, no 8hr cap, can use PETG |
| IMU | MPU-6050 | Heading hold, pitch/roll |
| Steering | SG90 on jet nozzle | Replaces rudder entirely |

## 3. Budget

| Category | Friend Print | Notes |
|----------|-------------|-------|
| Printed parts (353g PLA) | $7 | Retail PLA $20/kg |
| Motor + ESC combo | $38 | Surpass KK 2838 + 35A + water-cooling |
| Battery + charger | $30-41 | 3S 2200mAh + USB balance charger |
| Electronics (ESP32-S3, IMU, etc.) | $31 | ~7 components |
| Water cannon | $11 | 5V pump + MOSFET + tubing |
| Waterproofing | $23 | XTC-3D epoxy + silicone |
| Hardware | $10 | Screws, glands, foam |
| **Total** | **~$130 CAD** | |

> Already own battery+charger? **~$95 CAD**. Library prints instead of friend? **~$165 CAD**.
> Full purchase list: [`BOM.md`](BOM.md).

## 4. Control Architecture

```
L0: Hardware     — ESC brake, servo stops, fuse            [0ms, physics]
L1: PID          — ESP32 core 0, 50Hz, heading hold        [20ms]
L2: Guardian     — ESP32 core 1, 10Hz, failsafe, GPS       [100ms]
L3: Ground       — MacBook, 1-10Hz, vision, skills         [0.1-1s]
L4: LLM          — MacBook, 0.2-1Hz, mission goals         [1-3.5s]
L5: Human        — Phone PWA, STOP button                  [300ms]
```

**Fail-safe:** No command for 2s → throttle zero, nozzle center.

## 5. Phases

| Phase | What | Status |
|-------|------|--------|
| 0 | CAD design (monohull + jet + electronics) | **Done — ready to print** |
| 1 | Print + assemble + waterproof | Planned |
| 2 | Phone PWA control via WiFi | Planned |
| 3 | LLM autonomous control | Future |
| 4 | Skill library + multi-agent | Future |

## 6. Critical Constraints

- **Library printer:** PLA only, $0.12/g, $2/job, 8hr cap → use friend's printer instead
- **Friend's printer:** Retail PLA $20/kg, no time limit, can use PETG
- **Budget:** $130 CAD with friend, $165 with library
- **Self-righting:** Flood chamber (NOT catamaran geometry)
- **Waterproofing:** XTC-3D epoxy coat mandatory — PLA is porous along layer lines
- **Test protocol:** Bench → bathtub flip test → pond → tethered autonomy → full LLM

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Leak into electronics bay | Medium | $60 electronics | Sealed box + gasket + water sensor + paper-towel test |
| WiFi range shorter than expected | Medium | Lost boat | External antenna + 2s failsafe + GPS RTH |
| PLA cracks on impact | High | $5 bow reprint | Foam-filled bow, sacrificial nose, keep g-code handy |
| Flood chamber volume wrong | Low | Doesn't self-right | Bathtub flip test before lake |
| Phone hotspot disconnects | Medium | Mission pause | Boat holds station safely, old spare phone as dedicated hotspot |

## 8. Sources

- RCGroups: 3D printed boat waterproofing, jet drives, forum discussions
- BoatDesign.net: PLA hull engineering, segment joining
- RCBoatHQ: jet vs propeller comparison
- Code as Policies (arXiv:2209.07753): LLM robot control architecture
- HLA paper (AAMAS 2024): hierarchical agent latency analysis
- Mississauga Library makerspace: pricing, constraints
- EXHOBBY: catamaran vs monohull vs hydroplane guide
- Snapmaker blog: waterproofing testing methods
