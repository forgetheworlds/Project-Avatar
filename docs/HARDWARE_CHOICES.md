# Hardware Choices & Pixhawk Comparison

**Project Avatar** | July 2026 | Sub-250g Autonomous Water-Gun Drone

---

## Table of Contents

1. [Current Hardware Choices](#1-current-hardware-choices)
2. [Pixhawk Comparison](#2-pixhawk-comparison)
3. [Build Tradeoffs](#3-build-tradeoffs)
4. [Weight Budget Analysis](#4-weight-budget-analysis)
5. [Decision & Next Steps](#5-decision--next-steps)

---

## 1. Current Hardware Choices

### Design Philosophy

This build targets a **sub-250g autonomous water-gun drone** using ArduPilot. Every component choice balances three constraints:

- **Weight** — must stay under 250g AUW including 50g payload
- **ArduPilot compatibility** — the flight stack determines FC, GPS, and RX choices
- **Cost** — target under $400 CAD ($312 USD baseline)

### Flight Controller: MicoAir H743 AIO 35A

| Spec | Value |
|------|-------|
| MCU | STM32H743 (ARM Cortex-M7, 480MHz) |
| IMU | BMI270 (6-axis) |
| Baro | DPS310 |
| ESC | 35A 4-in-1 BLHeli_S |
| Weight | ~10g |
| Cost | $59 USD / $90 CAD |
| Firmware | ArduPilot Copter 4.6+ |

**Why this chip?** The STM32H743 is the same MCU found in Pixhawk 6C/6X. It runs ArduPilot with full feature support — GPS waypoints, circle mode, geo-fence, RTL, all standard MAVLink commands. At $59 for FC+ESC in one board, this is the best value for a sub-250g build.

**Why AIO (All-In-One) instead of separate FC + ESC?** On a micro quad:
- Saves 5-8g vs separate boards + wiring harness
- Reduces wiring complexity (no ESC signal/power wiring harness)
- Single power input simplifies build
- Fewer solder joints = fewer failure points

**Tradeoff accepted:** AIO means if either FC or ESC fails, the whole board must be replaced. On a micro build with low crash forces, this risk is acceptable.

### Alternative: SpeedyBee F405 Mini

The SpeedyBee F405 Mini ($40 USD / $65 CAD) is the main budget alternative.
- **Pros:** $19 cheaper, smaller community, well-documented on ArduPilot
- **Cons:** F405 has fewer UARTs (4 vs 6 on H743), less flash for firmware features, no DPS310 baro on some versions
- **Verdict:** H743 wins for this build. GPS + ESP32 + ELRS RX + camera telemetry needs 4 UARTs minimum. The H743's 6 UARTs give headroom for all peripherals without multiplexing.

### Frame: SpeedyBee Master3X (3-3.6")

| Spec | Value |
|------|-------|
| Size | 3" to 3.6" props |
| Weight | ~25g (frame only) |
| Material | 4mm carbon fiber |
| Features | Modular payload plate, TPU mounts |
| Cost | $30 USD / $45 CAD |

**Why this frame?** At 3" prop size, this hits the sweet spot for sub-250g builds:
- Large enough for 3.5" props (good thrust efficiency)
- Small enough to stay under 250g with payload
- Modular payload plate = easy water gun mounting
- TPU vibration-dampening mounts = better IMU readings
- 4mm arms = durable enough for crash testing

The iFlight XL3 V5 ($49 CAD) and Flywoo GOKU ($39 CAD) are alternatives but lack the Master3X's integrated payload mounting options.

### Motors: 1505 3800KV x4

| Spec | Value |
|------|-------|
| Size | 1505 (15mm stator, 5mm height) |
| KV | 3800KV |
| Configuration | 4S LiPo |
| Props | 3.5" tri-blade |
| Total weight | ~26g (6.5g each) |
| Cost | $36 USD / $68 CAD (set of 4) |

**Why 1505 3800KV?** From Oscar Liang's motor/prop table and confirmed by the splash research:
- 3.5" freestyle on 4S uses 1404/1504/1604 motors at 3500-4000KV
- 1505 at 3800KV provides the best thrust-to-weight ratio for a 245g AUW build
- Higher KV than 3600 gives more aggressive throttle response (good for quick maneuvers)
- 1505 is lighter than 1507 (used on heavier builds) while still providing sufficient thrust

**Alternative considered:** SpeedyBee 1507 3600KV ($19 USD each) offers more torque for the water payload but adds ~8g total. If thrust proves marginal with the 50g payload, 1507 is the upgrade path.

### Props: Gemfan 3.5" Tri-Blade x8
- 3.5" diameter matches the motor KV and frame size optimally
- Tri-blade gives better grip and smoother flight than bi-blade
- 8 packs = 2 full sets for spares
- $8 USD / $14 CAD

### GPS: GOKU GM10 Nano V3

| Spec | Value |
|------|-------|
| Chipset | Ublox M10Q |
| Weight | 2.6g (with compass) |
| Features | GPS + GLONASS + Compass |
| Fix time | ~30s cold start |
| Accuracy | ~1.5m CEP |
| Cost | $25 USD / $40 CAD |

**Why this GPS?** At 2.6g it is the lightest ArduPilot-compatible GPS+compass module available. The GOKU GM10 is the same unit used in geofrancis's sub-250g build. Essential for waypoint navigation, circle mode, RTL, and the protect-mode autonomous orbit.

**Critical for autonomous mode:** Without GPS, the drone cannot do position-hold or waypoint navigation. GPS is non-negotiable for the splash mission.

### ESP32-S3 WiFi Bridge: XIAO ESP32-S3 x2

| Spec | Value |
|------|-------|
| Module | Seeed Studio XIAO ESP32-S3 |
| Weight | 2g each |
| Role | MAVLink bridge UDP (one primary, one backup) |
| Cost | $15 USD / $27 CAD each |

The ESP32-S3 runs a MAVLink passthrough bridge — forwarding telemetry from the FC's UART to any ground station (MacBook, phone PWA, QGroundControl) over WiFi. The second unit serves as a backup/spare.

**Why not a dedicated telemetry radio?** ELRS telemetry (CRSF protocol) is limited to ~100 bytes/s — insufficient for the camera CV pipeline. WiFi gives ~13 KB/s bandwidth for full telemetry + camera frames. The sacrifice is range (~50m) vs 1km+ for LoRa-based radios — acceptable for a school-game drone.

### ELRS Receiver: Nano RX 2.4GHz
- Provides RC override for safety (RTH switch, disarm)
- 2.4GHz ELRS = low latency, good range
- $15 USD / $25 CAD

Backup control channel. Primary control is via MAVLink over WiFi through the MCP/LLM server, but RC provides:
- Emergency failsafe trigger (RTH on signal loss)
- Manual override during testing
- Compliance with Canadian drone regs (RC override required)

### Battery: 4S 850mAh LiPo x2

| Spec | Value |
|------|-------|
| Cells | 4S (14.8V nominal) |
| Capacity | 850mAh |
| Discharge | 70C continuous |
| Weight | ~95g each |
| Cost | $30 USD / $60 CAD (pair) |

**Why 4S 850mAh?** This is the standard battery for 3.5" freestyle builds:
- 850mAh is the max capacity that stays within the sub-250g weight budget
- 4S voltage drives 3800KV motors at their efficiency sweet spot
- 70C = 59.5A continuous, well above the 35A ESC limit
- Two batteries = ~7 min flight time each, enough for multiple engagement cycles

**Range estimate:** At 245g AUW with 850mAh 4S on 1505 3800KV motors with 3.5" props:
- Hover current: ~3-4A per motor (~12-16A total)
- Flight time: ~4-6 min aggressive / ~7-8 min cruising
- CV + pump additional draw: ~1.5A for ESP32 + pump
- **Effective mission time: ~4-5 minutes per battery**

### Camera: Hawkeye Thumb 4K

| Spec | Value |
|------|-------|
| Resolution | 4K (can stream 1080p) |
| Weight | ~18g |
| Features | Gyroflow stabilization, WiFi stream |
| Cost | $60 USD / $70 CAD |

**Why this camera?** The Hawkeye Thumb 4K is one of the lightest HD cameras with WiFi streaming capability. Key factors:
- Gyroflow stabilization handles drone vibration better than electronic-only stabilization
- WiFi streaming at 1080p feeds the MacBook CV pipeline for person detection
- 4K recording for post-mission review

**Risk:** Mixed reports on gyro sync reliability with WiFi streaming. The RunCam Thumb 2 ($80 CAD) is a proven fallback.

### Payload Components

#### Micro Pump: 3-6V DC Micro Submersible
- Weight: ~20-28g (estimate from similar units)
- Flow: ~120L/h (33ml/s) in free flow
- Pressure: 1.1m head (~0.11 bar / 1.6 psi)
- Expected range: 3-5m with stream nozzle
- Cost: ~$8 CAD

**Selection rationale:** At under 30g, this is the only pump that fits the sub-50g payload budget while providing adequate flow. The tradeoff is low pressure — range is limited to ~3-5m. See the water control research (`docs/research/avatar-water-control.md`) for the full analysis including the alternative pre-charged pressure system for longer range.

#### Servos: MG90S Metal Gear x2
- Weight: 13g each (metal gears vs SG90's 9g plastic)
- Function: Pan + Tilt for water gun aiming
- Cost: $6 CAD each

Metal gears are chosen over SG90's plastic gears because the water nozzle creates back-pressure on the tilt servo. Plastic gears would strip under repeated firing loads.

#### Reservoir: 15ml Luer-Lock Syringe
- Weight: 5g empty, ~20g full
- Quick-release mount via dovetail
- 15ml gives ~4-8 triggers per fill (depending on burst duration)
- Cost: ~$1 CAD

#### Nozzle: 3D Printed Stream Nozzle
- Weight: ~2g
- Self-printed at Mississauga Central Library (free)
- Stream restriction matched to pump flow rate
- Alternative: brass nozzle ($7 CAD) for durability

#### MOSFET: IRFZ44N N-Channel
- Drives the pump (PWM-switched via FC I/O or ESP32 GPIO)
- Cost: ~$2 CAD (from Sayal Electronics Mississauga)
- Rating: 55V, 49A — massively over-specced, which means zero heat generation at the pump's ~1A draw

### Quick-Release Payload Mount
- 3D printed dovetail mount (PLA/PETG)
- Spring-loaded latch
- Mass: ~5g (counted in payload budget)
- Enables detachment of the water gun for sub-250g compliance when not in mission mode

Without the payload (pump + servos + reservoir + nozzle = ~50g), the drone weighs ~200g, comfortably under 250g.

---

## 2. Pixhawk Comparison

### Background: Why This Comparison Exists

The current build uses an **AIO (All-In-One) flight controller** — MicoAir H743 AIO that integrates FC + ESC on one board. Pixhawk is the other major ArduPilot/PX4 hardware ecosystem: modular flight controllers with separate ESC, typically used on larger drones (250mm+).

Earlier Avatar architecture research (see `archive/px4-mavsdk-python-evaluation/`) used a **Pixhawk 6C + Raspberry Pi + PX4 stack** concept. The current build pivoted to AIO + ArduPilot to hit the sub-250g weight target. But understanding when Pixhawk makes sense is important for future scaling.

### Pixhawk Models Considered

| Model | MCU | IMU | Weight (g) | Cost (CAD) | ArduPilot | PX4 |
|-------|-----|-----|------------|------------|-----------|-----|
| **Pixhawk 4** | STM32F765 | ICM-20689 | ~30 | $180-220 | Yes | Yes |
| **Pixhawk 6C** | STM32H743 | BMI088 | ~20 | $160-200 | Yes | Yes |
| **Pixhawk 6X** | STM32H757 | BMI088 | ~25 | $280-350 | Yes | Yes |
| **Holybro Durandal** | STM32H753 | ICM-20602 | ~20 | $180-220 | Yes | Yes |
| **Cube Orange+** | STM32H753 | ICM-20948 | ~35 | $350-450 | Yes | Yes |

All weights are **FC-only** — Pixhawk also needs a separate ESC ($30-60), PDB ($10-20), and wiring harness ($5-10). Total Pixhawk stack weight: ~50-70g before motors.

### Comparison Matrix: Pixhawk vs Current AIO

| Factor | MicoAir H743 AIO | Pixhawk 6C | Winner |
|--------|------------------|------------|--------|
| **Total FC weight** | ~10g (FC+ESC) | ~40-50g (FC + 4-in-1 ESC + PDB) | **AIO** |
| **Total FC cost** | ~$90 CAD | ~$300 CAD | **AIO** |
| **MCU** | STM32H743 | STM32H743 (same) | Tie |
| **ArduPilot compat** | Full (Copter 4.6+) | Full (Copter 4.6+) | Tie |
| **PX4 compatibility** | Not supported | Full | **Pixhawk** |
| **UARTs available** | 6 | ~5-6 | Tie |
| **I2C ports** | 1 (shared bus) | 2+ (dedicated) | **Pixhawk** |
| **CAN bus** | No | Yes | **Pixhawk** |
| **Servo/PWM outs** | 6 (via ESC pads) | 8+ (dedicated) | **Pixhawk** |
| **RC input** | SBUS/PPM | SBUS/PPM/CRSF (native) | **Pixhawk** |
| **Safety switch** | No | Yes (hardware) | **Pixhawk** |
| **Power redundancy** | No (single BEC) | Yes (dual power inputs) | **Pixhawk** |
| **Current sensing** | Built-in | Optional external | Tie |
| **Community support** | Moderate (niche) | Excellent (standard) | **Pixhawk** |
| **Availability in CAN** | Rotor Village ($90) | Rotor Village or Holybro | Tie |
| **Repair/Replace** | Replace whole board | Modular (replace one part) | **Pixhawk** |
| **Peripheral expansion** | Limited | Excellent (CAN, I2C, debug) | **Pixhawk** |
| **Sub-250g feasible** | Yes (proven) | Difficult (too heavy) | **AIO** |

### When Pixhawk Makes Sense

Pixhawk-class FCs are the right choice when:

1. **Drone > 250g** — On a 5" or larger frame, the 30-40g weight penalty of Pixhawk is negligible (2-5% of AUW instead of 15-20%)

2. **PX4 firmware needed** — Pixhawk is designed for PX4; some features (advanced multi-sensor fusion, VTOL support) work better on PX4 than ArduPilot

3. **Multiple sensors needed** — Pixhawk's CAN bus supports external sensors (lidar, optical flow, airspeed) that the AIO board cannot

4. **Research/development platform** — Pixhawk's debug headers, redundancy options, and ecosystem make it the right choice for a drone you expect to grow

5. **Flight safety is critical** — Pixhawk's dual power inputs, hardware safety switch, and modular repair reduce the chance of a single-point failure

6. **Companion computer needed** — Pixhawk's TELEM2 port directly powers and communicates with a Raspberry Pi, making it the natural choice for companion-computer architectures

### When AIO Flight Controller Wins

Compact AIO FCs are the right choice when:

1. **Sub-250g build** — The 30-40g weight savings of AIO is the difference between a 245g and 280g AUW. For sub-250g, AIO is essentially required.

2. **Cost-sensitive build** — AIO at $59 is 4x cheaper than Pixhawk + ESC + PDB. For a school-game drone that may crash, AIO is the pragmatic choice.

3. **Simple build with limited peripherals** — If you only need GPS + ELRS RX + camera + payload servos, the AIO's 6 UARTs are sufficient

4. **Single-purpose drone** — If the drone is built for one mission (splash), AIO has everything needed without expansion overhead

5. **Rapid prototyping** — AIO boards are cheap enough to keep a spare. When you crash hard, $59 beats $200+ to get back in the air.

6. **SITL-first development** — If most logic is tested in simulation before flying, the AIO's lack of debug ports is irrelevant

### Recommendation for THIS Project

**Decision: Stick with MicoAir H743 AIO for now.**

**Rationale:**
1. This drone MUST be sub-250g (no registration, simpler rules for school game)
2. The AIO saves 30-40g — this is the difference between passing and failing the weight target
3. For $59, we can keep a spare AIO on hand. A $200 Pixhawk + $60 ESC is 4x the crash cost
4. We do not need PX4 — ArduPilot does everything we need (waypoints, orbit, RTL, geofence)
5. We do not need a companion computer (CV runs on the ground-station MacBook, not onboard)
6. The 6 UARTs are sufficient for GPS + ESP32 + ELRS RX + camera + servos

**When would we switch?** If the drone were to become a multi-mission platform (>250g, companion computer onboard, PX4 needed for advanced features), a Pixhawk 6C or 6X would be the upgrade path.

---

## 3. Build Tradeoffs

### The Core Tension

Every gram saved goes into one of three competing priorities:

1. **Payload capacity** — heavier water gun = more range and capacity, but pushes AUW over 250g
2. **Flight time** — larger battery gives more flight time, but adds weight
3. **Control reliability** — redundant systems add weight but improve safety

### Tradeoff 1: Battery Size vs Weight

| Battery | Weight | Flight Time | Impact on AUW |
|---------|--------|-------------|---------------|
| 4S 650mAh | ~72g | ~3-4 min | 222g AUW (lightest) |
| **4S 850mAh** | ~95g | ~5-6 min | 245g AUW (best balance) |
| 4S 1050mAh | ~115g | ~7-8 min | 265g AUW (over 250g!) |

**Decision:** 850mAh gives the maximum flight time that still keeps us under 250g. The ~5 minute mission window means each sortie has ~2 minutes of loiter time after accounting for takeoff, transit, engagement, and landing.

We mitigate this by carrying two batteries — land, swap, and relaunch in under 60 seconds.

### Tradeoff 2: Payload Weight vs Flight Performance

| Payload Config | Weight Added | Effect on Flight |
|----------------|-------------|-----------------|
| No payload | 0g | ~200g dry — acrobatic, 7+ min flight |
| **Water gun (detachable)** | ~50g | ~250g AUW — stable, ~5 min flight |
| Full water (15ml) | ~65g | ~265g AUW — sluggish, over 250g |

**Key insight:** The 50g payload reduces thrust-to-weight ratio from ~5:1 to ~4:1. This is still well within safe margins (minimum acceptable: 2:1). The drone will be less agile but still fully controllable.

The **detachable quick-release mount** solves the weight problem by offloading the water gun for non-mission flights. For testing, fly dry at 200g. For missions, attach the 50g payload.

### Tradeoff 3: WiFi Control Range vs Telemetry Bandwidth

| Control Link | Range | Bandwidth | Use |
|-------------|-------|-----------|-----|
| WiFi (ESP32 AP) | ~50m LOS | ~13 KB/s telemetry | Primary control + CV video |
| ELRS 2.4GHz RC | ~1km | 100 bytes/s | Safety failsafe only |

**Decision:** WiFi for primary control enables the CV pipeline (video frames to person detection to auto-aim to fire) but limits range to ~50m LOS. This is acceptable for a school-field game where the action radius is ~30m.

**Risk mitigation:** ELRS RC provides failsafe RTH if WiFi link drops. The RC link has 20x the range and is independent of the WiFi network.

### Tradeoff 4: GPS vs No GPS

Without GPS, the drone saves 2.6g and ~$40 CAD but loses all autonomous capability:
- No position hold = must hover manually
- No waypoint navigation = cannot orbit a GPS coordinate
- No RTL = lost-link leads to crash, not safe return
- No protect mode

**Decision:** GPS is non-negotiable for the autonomous splash mission. The 2.6g penalty is worth every gram for the safety and capability it enables.

### Tradeoff 5: Camera Weight vs CV Quality

| Camera | Weight | CV Feed | Cost |
|--------|--------|---------|------|
| Hawkeye Thumb 4K | ~18g | 1080p WiFi stream | $70 CAD |
| Hawkeye Thumb 2 | ~17g | 1080p WiFi stream | $80 CAD |
| RunCam Thumb 2 | ~22g | 1080p WiFi stream | $99 CAD |
| ESP32-CAM | ~8g | VGA WiFi stream | $15 CAD |

The ESP32-CAM at 8g would save 10g but delivers only VGA (640x480) over WiFi with high latency — making person detection at range (>5m) unreliable. The Hawkeye Thumb's 1080p feed is worth the 10g premium for reliable CV at the 15m engagement range.

---

## 4. Weight Budget Analysis

```
+------------------------------------------------------+
|              WEIGHT BUDGET (total)                    |
+------------------------------------------------------+
|                                                       |
|  Airframe components:                                 |
|   Frame (SpeedyBee Master3X)         25g              |
|   Motors (1505 3800KV x4)            26g              |
|   FC+ESC (MicoAir H743 AIO)          10g              |
|   Props (3.5" tri-blade x4)           6g              |
|                                                       |
|  Power:                                                |
|   Battery (4S 850mAh)                95g              |
|                                                       |
|  Avionics:                                             |
|   GPS (GOKU GM10 Nano V3)             3g              |
|   ELRS RX + antenna                   3g              |
|   ESP32-S3 x2                         4g              |
|                                                       |
|  Payload (permanent):                                  |
|   Hawkeye Thumb 4K + mount           22g              |
|                                                       |
|  Misc:                                                 |
|   Wiring + hardware                    6g              |
|                                                       |
+-------------------------------------------------------+
|  DRY TOTAL (no payload)             200g              |
+-------------------------------------------------------+
|                                                       |
|  Water Gun Payload (detachable):     ~50g             |
|    Pump (12V micro submersible)      28g              |
|    MG90S servo x2                    26g              |
|    Syringe reservoir (empty)          5g              |
|    Nozzle + tubing                    5g              |
|    Mount dovetail (3D printed)        5g              |
|    Wiring                             5g              |
|    Total payload: ~74g before                        |
|    weight optimization                               |
+-------------------------------------------------------+
|  TOTAL WITH PAYLOAD                ~250-274g          |
+-------------------------------------------------------+
```

**The 50g payload target is very tight.** The current best-estimate component weights for the water gun sum to ~74g — exceeding the budget by ~24g. Weight reduction priorities:

1. **Reduce pump weight:** Find a lighter micro pump (target <15g). The 28g submersible is the heaviest single component. Consider drill-powered or 3D-printed impeller designs to save 15g.
2. **Single servo:** Replace pan+tilt with a fixed pan, single tilt servo. Saves 13g at the cost of manual yaw pointing via drone rotation.
3. **Reservoir only when full:** The 5g syringe is negligible, but 15ml of water adds 15g. Fly with 5-10ml for shorter missions.

**With all optimizations:** Target 245-250g is achievable. Without optimization: ~274g AUW — 24g over the legal limit, which defeats the purpose of sub-250g/no-registration compliance.

---

## 5. Decision & Next Steps

- **Decision:** Continue with the MicoAir H743 AIO 35A. The sub-250g requirement is non-negotiable for the school-game use case, and the AIO's 30-40g weight advantage over Pixhawk is the deciding factor. Pixhawk 6C/6X is the upgrade path for a future >250g version with onboard companion computer.

- **Next action:** (1) Finalize pump selection — find a sub-15g micro pump or switch to pre-charged pressure system to hit the 50g payload target. (2) Purchase the BOM split across Canadian vendors and AliExpress as documented in `docs/research/avatar-canadian-sourcing.md`.

- **Deadline:** Build starts week of July 7, 2026. Orders placed within 48 hours.

- **Who should handle next:** Muadh — authorize purchases against budget. Researcher can compile vendor cart links on request.

---

## Related Documents

- [Current BOM & Blockers](../BLOCKERS_AND_USER_ACTION_ITEMS.md) — purchase checklist
- [Canadian Hardware Sourcing](research/avatar-canadian-sourcing.md) — vendor-specific pricing and links
- [System Architecture](ARCHITECTURE.md) — full system overview
- [Water Control Research](research/avatar-water-control.md) — pump comparison and ballistics
- [Drone Control Research](research/avatar-drone-control.md) — PID tuning and autonomous patterns
- [CV Pipeline Research](research/avatar-cv-pipeline.md) — YOLO tracking benchmarks
- [Payload Interface](PAYLOAD_INTERFACE.md) — payload mount and communication spec
