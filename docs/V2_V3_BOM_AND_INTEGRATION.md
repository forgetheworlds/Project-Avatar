# V2 & V3 Complete BOM with Integration Analysis

**Project Avatar** | July 5, 2026
**Status:** Complete -- all prices researched via Tavily + AliExpress (medium-high confidence)
**Currency:** CAD | **Exchange rate:** 1 USD = 1.40 CAD (July 2026)

---

## Table of Contents

1. [V2 BOM -- Camera + Human Tracking](#1-v2-bom--camera--human-tracking)
2. [V3 BOM -- Splash Water Gun Payload](#2-v3-bom--splash-water-gun-payload)
3. [Weight Budget Across All Versions](#3-weight-budget-across-all-versions)
4. [V1 to V2 Integration Analysis](#4-v1--v2-integration-analysis)
5. [V2 to V3 Integration Analysis](#5-v2--v3-integration-analysis)
6. [Go/No-Go Criteria](#6-gono-go-criteria)
7. [Sub-250g Compliance Strategy](#7-sub-250g-compliance-strategy)
8. [Decision Matrix](#8-decision-matrix)

---

## 1. V2 BOM -- Camera + Human Tracking

### Design Goal

Add a lightweight camera to the V1 drone so the ground-station MacBook can receive a live video feed for YOLO-based human tracking and auto-aim. The camera must weigh <25g, stream over WiFi or analog video, and mount on the Master3X frame without major modifications.

### Part 1.1: Primary Camera -- RunCam Thumb 2 (RECOMMENDED)

| Field | Value |
|-------|-------|
| **Part** | RunCam Thumb 2 WiFi FPV Camera |
| **AliExpress** | Search "RunCam Thumb 2 WiFi" (~5-65 USD) |
| **Price (USD)** | ~0 USD |
| **Price (CAD)** | **~4 CAD** |
| **Weight** | ~22g (with case) |
| **Resolution** | 1080p @ 60fps recording, WiFi streaming at 720p |
| **WiFi Latency** | ~100-200ms (typical for action cam WiFi) |
| **Power** | Internal LiPo battery (~30 min recording), charges via USB-C |
| **Mounting** | Standard 1/4"-20 tripod mount or 3D printed adapter |
| **Compatible?** | Yes -- self-contained, no extra battery needed |
| **Alternatives** | Hawkeye Thumb Pro WiFi (~0 USD, ~16g, fewer streaming reports) |

**Key advantage:** RunCam Thumb 2 has proven WiFi streaming for real-time video -- the Hawkeye Thumb's WiFi is mainly for file transfer, not live streaming. The RunCam is the safer choice for the CV pipeline.

### Part 1.2: Budget Alternative -- ESP32-CAM

| Field | Value |
|-------|-------|
| **Part** | ESP32-CAM Development Board (OV2640) |
| **AliExpress** | Search "ESP32-CAM OV2640" (~-10 USD) |
| **Price (USD)** | ~ USD |
| **Price (CAD)** | **~1 CAD** |
| **Weight** | ~10g (with camera + antenna) |
| **Resolution** | 640x480 (VGA) max over WiFi |
| **WiFi Latency** | ~150-300ms |
| **Power** | 5V via USB or FC BEC (~310mA active) |
| **Compatible?** | Warning -- VGA resolution limits human detection range to <5m |
| **Notes** | Good for proof-of-concept but low res hurts YOLO detection at range |

### Part 1.3: Mounting Hardware

| Field | Value |
|-------|-------|
| **Part** | 3D printed camera mount (Master3X-specific) |
| **Price** | /usr/bin/bash CAD (library or self-print) |
| **Weight** | ~3g (PLA/PETG) |
| **Design** | Mounts on front top plate, centered between arms |
| **Alternative** | Double-sided 3M VHB tape + zip tie (temporary) |

### Part 1.4: Additional Video Relay ESP32 (if needed)

| Field | Value |
|-------|-------|
| **Part** | Seeed Studio XIAO ESP32-S3 (SECOND unit) |
| **AliExpress** | Search "XIAO ESP32-S3" (~0-12 USD ea) |
| **Price (CAD)** | **~5 CAD** (already in V1 BOM as backup/spare) |
| **Weight** | ~3g |
| **Role** | If RunCam WiFi conflicts with control link, use 2nd ESP32 as video relay |

### Part 1.5: 2S 300mAh LiPo Battery (Optional)

| Field | Value |
|-------|-------|
| **Part** | 300mAh 2S 7.4V LiPo (XT30 or JST) |
| **AliExpress** | https://www.aliexpress.com/item/1005003834564359.html (~7 USD) |
| **Price (CAD)** | **~4 CAD** |
| **Weight** | ~19g |
| **When needed** | Only if camera cannot run on internal battery. RunCam has internal battery. SKIP for V2. |

### V2 BOM Cost Summary

| Item | USD | CAD | Weight (g) | Qty |
|------|-----|-----|------------|-----|
| RunCam Thumb 2 | 0 | 4 | 22 | 1 |
| 3D printed mount | /usr/bin/bash | /usr/bin/bash | 3 | 1 |
| **V2 Camera Subtotal** | **0** | **4** | **25** | - |

---

## 2. V3 BOM -- Splash Water Gun Payload

### Design Goal

Add a sub-100g detachable water gun payload: micro pump, pan-tilt servos, reservoir, nozzle. Must fire water 3-5m with aim controlled by the CV pipeline. Entire payload detachable for sub-250g compliance.

### CRITICAL FINDING: No pump under 15g delivers both flow rate AND pressure for range

The original research target was a "15g pump" but no off-the-shelf sub-15g pump exists that can fire a stream >3m at useful pressure. The lightest viable pump is the R385/R365 at ~30g.

### Part 2.1: Micro Diaphragm Pump -- R385/R365

| Field | Value |
|-------|-------|
| **Part** | R385/R365 DC Diaphragm Pump 6-12V |
| **AliExpress** | https://www.aliexpress.com/item/1005010178771529.html (~ USD) |
| **Price (USD)** | ~ USD |
| **Price (CAD)** | **~0 CAD** |
| **Weight** | ~30g |
| **Flow Rate** | 1.5-1.8 L/min (25-30 ml/s free flow) |
| **Pressure** | ~2 bar (30 psi) -- enough for 3-5m stream |
| **Current Draw** | <500mA at 12V |
| **Voltage** | 6-12V DC (works on 2S-3S) |
| **Size** | ~50mm x 30mm x 25mm |
| **Alternative 1** | 3-6V micro submersible pump (~25g, ~ USD) -- lower pressure, shorter range (1-3m) |
| **Alternative 2** | Pre-charged pressure system (~5g extra) -- best range but limited shots per charge |

### Part 2.2: Pan-Tilt Servos -- MG90S Metal Gear (x2)

| Field | Value |
|-------|-------|
| **Part** | MG90S Micro Servo Metal Gear (x2) |
| **AliExpress** | https://www.aliexpress.com/item/1005004550692203.html (~-3 USD ea) |
| **Price (CAD)** | **~ CAD** (2-pack) |
| **Weight** | ~13g each = **26g total** |
| **Torque** | 1.8 kg-cm at 6V |
| **Speed** | 0.10-0.18 sec/60 deg |
| **Voltage** | 4.8-6.0V |
| **Material** | Metal gears (essential for nozzle back-pressure) |
| **Alternative** | SG90 plastic gear (~9g, .50 USD) -- gears strip under firing load. NOT recommended. |

### Part 2.3: Reservoir -- 15ml Luer-Lock Syringe

| Field | Value |
|-------|-------|
| **Part** | 15ml Luer-Lock Syringe |
| **Price (CAD)** | **~ CAD** (Amazon or pharmacy) |
| **Weight (empty)** | ~5g |
| **Weight (full)** | ~20g (+15g water) |
| **Alternative** | IV bag (~3g empty, up to 100ml) -- longer missions, harder to mount |

### Part 2.4: Nozzle

| Field | Value |
|-------|-------|
| **Part** | 3D Printed Stream Nozzle (conical, ~1mm orifice) |
| **STL Source** | MakerWorld "HydroBlaster" (adapt) or Thingiverse "water rocket nozzle" |
| **Price** | **/usr/bin/bash CAD** (self-print at library) |
| **Weight** | ~2g |
| **Design** | 1mm diameter orifice, 10 deg converging cone |
| **Alternative** | Brass M3 fitting with drilled 1mm hole (~ CAD, 3g) -- more durable |

### Part 2.5: MOSFET -- IRFZ44N

| Field | Value |
|-------|-------|
| **Part** | IRFZ44N N-Channel MOSFET (TO-220) |
| **AliExpress** | Search "IRFZ44N" (~/usr/bin/bash.50 USD) |
| **Price (CAD)** | **~ CAD** |
| **Weight** | ~2g |
| **Rating** | 55V, 49A (massively over-specced for 0.5A pump = zero heat) |
| **Drive** | Gate driven by ESP32 GPIO or FC AUX output |

**IMPORTANT:** Add a 1N4007 flyback diode across the pump terminals. Without it, the inductive kick from the motor will destroy the MOSFET on every shutoff.

### Part 2.6: Servo Controller -- PCA9685

| Field | Value |
|-------|-------|
| **Part** | PCA9685 16-Channel 12-bit PWM/Servo Driver (I2C) |
| **AliExpress** | https://www.aliexpress.com/item/32753750943.html (~-4 USD) |
| **Price (CAD)** | **~ CAD** |
| **Weight** | ~5g (with pin headers) |
| **I2C Address** | 0x40 (default) -- no conflict with GPS compass on separate FC bus |
| **Notes** | Drives both MG90S servos + 14 spare channels. 12-bit = 4us resolution at 60Hz. |

### Part 2.7: Silicone Tubing

| Field | Value |
|-------|-------|
| **Part** | Silicone tubing 3mm ID x 5mm OD |
| **AliExpress** | https://www.aliexpress.com/item/1005011839040630.html (~ USD for 1m) |
| **Price (CAD)** | **~ CAD** |
| **Weight** | ~1g (need ~30cm) |
| **Compatible?** | Yes -- 3mm ID fits syringe luer-lock. 5mm OD fits R385 pump barbs |

### Part 2.8: JST Connectors + Wiring

| Field | Value |
|-------|-------|
| **Part** | JST 2.0mm (PH) + 1.25mm (ZH) connectors with wire |
| **AliExpress** | Mixed kits (-5 USD) |
| **Price (CAD)** | **~ CAD** |
| **Weight** | ~3g total |
| **Needed for** | Servo connections (3-pin), pump power (2-pin), MOSFET gate signal |

### Part 2.9: Payload Battery -- 2S 300mAh LiPo

| Field | Value |
|-------|-------|
| **Part** | 300mAh 2S 7.4V LiPo (XT30) |
| **AliExpress** | https://www.aliexpress.com/item/1005003834564359.html (~7 USD) |
| **Price (CAD)** | **~4 CAD** |
| **Weight** | ~19g |
| **Purpose** | Dedicated power for pump + servos (keeps flight battery for drone only) |
| **Current analysis** | Pump: ~0.5A. 2x servos active: ~0.4A. Total: ~0.9A. 300mAh battery = ~20 min firing. Sufficient. |

### Part 2.10: 3D Printed Payload Mount

| Field | Value |
|-------|-------|
| **Part** | Dovetail quick-release mount (PLA/PETG) |
| **Price** | **/usr/bin/bash CAD** (library or self-print) |
| **Weight** | ~5g |
| **Design** | Slides onto Master3X bottom plate, spring-loaded latch |

### V3 BOM Cost Summary

| # | Item | USD | CAD | Weight (g) |
|---|------|-----|-----|-----------|
| 2.1 | R385 micro diaphragm pump |  | 0 | 30.0 |
| 2.2 | MG90S servo x2 |  |  | 26.0 |
| 2.3 | 15ml syringe reservoir |  |  | 5.0 |
| 2.4 | 3D printed nozzle | /usr/bin/bash | /usr/bin/bash | 2.0 |
| 2.5 | IRFZ44N MOSFET |  |  | 2.0 |
| 2.6 | 1N4007 flyback diode | /usr/bin/bash | /usr/bin/bash | 0.5 |
| 2.7 | PCA9685 servo driver |  |  | 5.0 |
| 2.8 | Silicone tubing (30cm) |  |  | 1.0 |
| 2.9 | JST connectors + wire |  |  | 3.0 |
| 2.10 | 2S 300mAh LiPo battery | 7 | 4 | 19.0 |
| 2.11 | 3D printed mount | /usr/bin/bash | /usr/bin/bash | 5.0 |
| **V3 Payload Subtotal** | **8** | **1** | **98.5g** | |

---

## 3. Weight Budget Across All Versions

### 3.1 V1 Base Weight (Reconciled from Compatibility Doc)

| Component | Weight (g) |
|-----------|-----------|
| Frame (Master3X full kit: carbon + hardware + TPU) | 40.0 |
| Motors (Diatone 1505 3800KV x4 @ 12.8g ea) | 51.2 |
| FC+ESC (MicoAir H743 AIO 35A) | 10.0 |
| Props (Gemfan 3.5" tri-blade x4 @ 1.8g ea) | 7.2 |
| Battery (4S 850mAh) | 95.0 |
| GPS (GOKU GM10 Nano V3) | 2.6 |
| ESP32-S3 (XIAO) -- bridge | 3.0 |
| Wiring + connectors + solder + hardware | 10.0 |
| **V1 AUW (Reconciled)** | **219.0g** |

### 3.2 V2 Added Weight (Camera + Tracking)

| Component | Weight (g) |
|-----------|-----------|
| RunCam Thumb 2 camera | 22.0 |
| 3D printed camera mount | 3.0 |
| Extra wiring | 1.0 |
| **V2 Added Weight** | **26.0g** |
| **V2 AUW** | **245.0g** |

> V2 is under 250g with 5g margin.

### 3.3 V3 Added Weight (Water Gun Payload - Dry)

| Component | Weight (g) |
|-----------|-----------|
| R385 diaphragm pump | 30.0 |
| MG90S servo x2 | 26.0 |
| Syringe reservoir (empty) | 5.0 |
| 3D printed nozzle | 2.0 |
| IRFZ44N MOSFET + diode | 2.5 |
| PCA9685 servo driver | 5.0 |
| Silicone tubing | 1.0 |
| JST connectors + wiring | 3.0 |
| 2S 300mAh LiPo battery | 19.0 |
| 3D printed mount + hardware | 5.0 |
| **V3 Payload Dry Weight** | **98.5g** |
| **V3 AUW (dry)** | **343.5g** |

### 3.4 V3 with Water (Loaded for Mission)

| Component | Weight (g) |
|-----------|-----------|
| V3 dry AUW | 343.5 |
| Water (15ml syringe full) | 15.0 |
| **V3 AUW (fully loaded)** | **358.5g** |

### 3.5 Cumulative Weight Summary

| Version | AUW | Sub-250g? | TWR @ 360g/motor | TWR @ 450g/motor | Notes |
|---------|-----|-----------|------------------|------------------|-------|
| V1 (reconciled) | 219g | Yes (31g margin) | 6.6:1 | 8.2:1 | Manual flight via Xbox |
| V2 (camera) | 245g | Yes (5g margin) | 5.9:1 | 7.3:1 | Camera + tracking |
| V3 dry | 344g | No (94g over) | 4.2:1 | 5.2:1 | Detach payload for sub-250g |
| V3 loaded | 359g | No (109g over) | 4.0:1 | 5.0:1 | Water in reservoir |

### 3.6 Critical TWR Thresholds

| TWR Range | Verdict | Flight Feel |
|-----------|---------|-------------|
| <2:1 | Unsafe | Cannot maintain hover |
| 2:1 | Minimum | Hard to fly, no wind margin |
| 3:1 | Adequate | Gentle, slow maneuvers |
| 4:1 | Good | Responsive, safe |
| >5:1 | Excellent | Acro-capable |

**All versions exceed 4:1 TWR even with conservative 360g/motor thrust.** The drone remains flyable at all stages.

---

## 4. V1 to V2 Integration Analysis

### Q1: How does adding camera weight affect flight time and PID tuning?

**Weight impact:** V1 (219g) to V2 (245g) = +26g (+12%).

**Flight time impact:**
- Hover throttle increases from ~17% to ~19%
- Cruise current increases from ~12A to ~13.5A
- Flight time (4S 850mAh):
  - V1: ~8 min cruise / ~5 min aggressive
  - V2: ~6.5 min cruise / ~4 min aggressive
- Reduction: ~15-20% flight time. Still viable for a 3-4 min mission window.

**PID impact:**
- Higher inertia means lower natural frequency -> existing PIDs may feel slightly sluggish
- Starting PIDs at 50% of default (already set) provide headroom
- **Do NOT retune PIDs for V2 alone** -- proceed directly to V3 and tune once with full payload
- If oscillation appears: reduce P gain by 10-20% and test
- If sluggish: increase P gain by 10-15% until crisp

**Recommendation:** Keep V1 PIDs for V2. Run autotune after V3 is assembled to have one set of tuned PIDs.

### Q2: Where does the camera mount on the Master3X frame?

**Camera placement options:**

| Position | Pros | Cons |
|----------|------|------|
| Front top plate (RECOMMENDED) | Forward view, good CG, clean mounting | Camera exposed, slightly forward CG |
| Rear top plate | Protected by arms | Rear-heavy, bad for CG |
| Below frame (belly mount) | Lowest CG, protected | Ground clearance, limited downward view |

**Recommended:** Mount RunCam Thumb 2 on the **front top plate**, centered between the two front arms, using a 3D printed wedge mount with ~15 deg downward tilt.

**Fit check:**
- Master3X top plate: ~67mm x 31mm
- RunCam Thumb 2: ~32mm x 25mm x 20mm
- GPS module: rear top (fits within 18x18mm TPU mount)
- **Camera fits alongside battery** (battery on mid plate, camera on top plate -- different levels). No interference.

### Q3: How does video stream from camera to MacBook? Latency?

**Streaming path:**
RunCam Thumb 2 -> WiFi AP mode (2.4GHz 802.11n) -> MacBook -> OpenCV -> YOLO -> tracking

**Latency breakdown:**

| Hop | Component | Latency (ms) |
|-----|-----------|-------------|
| 1 | Camera sensor capture | 16-33 (30-60fps) |
| 2 | Camera internal encoding | 15-30 |
| 3 | Camera WiFi TX | 30-80 |
| 4 | MacBook WiFi RX + decode | 5-15 |
| 5 | OpenCV frame read + preprocess | 2-5 |
| 6 | YOLO inference (M3, 384x640, CoreML) | 15-25 |
| 7 | Tracking (BoT-SORT) association | 5-10 |
| 8 | Aim command to MAVLink | 2-5 |
| 9 | WiFi to ESP32 -> UART to FC | 10-30 |
| **Total pipeline** | | **~100-210ms** |

**Verdict:** ~100-210ms total. Workable for stabilized tracking but not acrobatic. Camera WiFi latency (30-80ms) is the dominant bottleneck.

**Optimizations:**
1. Use 720p@30fps (lower resolution = less WiFi bandwidth = lower latency)
2. Keep MacBook within 5m of drone
3. Disable camera recording (stream-only mode)
4. Use separate WiFi networks: RunCam on one SSID, control bridge on XIAO ESP32 AP

### Q4: Can the single ESP32-S3 handle both MAVLink AND video relay?

**Short answer: No -- not well.**

The XIAO ESP32-S3 is a WiFi AP bridging MAVLink UDP to UART. Adding video relay would split WiFi airtime and risk control packet loss.

**Solution:** MacBook connects to TWO WiFi networks simultaneously:
1. ESP32 bridge AP (192.168.4.1) for MAVLink control
2. RunCam Thumb 2 AP for video stream

MacOS handles multi-WiFi connection. No additional hardware needed.

### Q5: Does the extra battery for camera create CG issues?

**No extra battery needed.** The RunCam Thumb 2 has an internal LiPo battery with ~30 min recording -- sufficient for a 4-6 min flight.

CG shift from V1 to V2 (camera only):
- Camera (22g) on front top plate
- CG shifts forward by ~3mm
- Compensate by sliding 4S battery rearward by 3-5mm
- **CG impact: Negligible -- within tunable range**

### Q6: What ArduPilot mode changes are needed for guided/track flight?

| Parameter | V1 Setting | V2/V3 Setting | Why |
|-----------|-----------|---------------|-----|
| FLTMODE6 | 4 (Guided) | 4 (Guided) | No change |
| GUID_OPTIONS | 1 | 1 | No change |
| AVOID_ENABLE | 0 | 2 | Enable MAVLink-based avoidance (future) |
| RC_OVERRIDE_TIME | -1 | -1 | No change |

**For person tracking:** No ArduPilot mode change needed. MacBook runs YOLO -> calculates offset -> sends MAVLink position targets in GUIDED mode. The FC never leaves GUIDED during auto-aim.

### Q7: Does TWR stay above 2:1 from V1 to V2?

| Scenario | AUW | Thrust | TWR | Verdict |
|----------|-----|--------|-----|---------|
| V1 @ 360g/motor | 219g | 1,440g | 6.6:1 | Excellent |
| V2 @ 360g/motor | 245g | 1,440g | 5.9:1 | Excellent |
| V2 @ 300g/motor (pessimistic) | 245g | 1,200g | 4.9:1 | Good |

**TWR remains above 4:1 in worst case.** No flight performance concerns.

---

## 5. V2 to V3 Integration Analysis

### Q1: Adding ~100g payload -- flight characteristics?

**V2 (245g) to V3 loaded (359g) = +114g (+47%) -- SIGNIFICANT.**

| Aspect | V2 | V3 loaded | Delta |
|--------|-----|-----------|-------|
| Hover throttle | ~19% | ~27% | +8% |
| Vertical acceleration | ~12 m/s2 | ~7 m/s2 | -42% |
| Max climb rate | ~12 m/s | ~7 m/s | -42% |
| Braking distance | ~3m | ~5m | +67% |
| Agility | Responsive | Sluggish | Noticeable |

**Manageable -- TWR still 4.0:1 at worst (well above 2:1 minimum).**

### Q2: Does pump vibration affect flight stability?

R385 diaphragm pump operates at ~5000-8000 RPM (83-133 Hz) -- below typical prop frequency (200-400 Hz). Vibration amplitude is low.

**Mitigation:**
1. Mount pump with TPU vibration dampers (3D printed flexible spacers, 0.5mm)
2. Keep V1 filter settings (INS_GYRO_FILTER=80, dynamic notch)
3. If wobble appears: enable DYN_NOTCH_ENABLE=1
4. Ground test: run pump while monitoring gyro z-axis noise in Mission Planner

**Verdict: Low risk. Standard isolation + existing filters should handle it.**

### Q3: Where does the water payload mount? CG impact?

**Recommended:** Bottom plate using 3D printed dovetail mount (existing M2 holes).
- Payload hangs ~15mm below frame
- CG shifts **down ~8mm** (stabilizing) and **aft ~5mm**
- Compensate by sliding battery forward 5mm

**Ground clearance:** ~30mm below frame -- sufficient for grass landings, risky on hard surfaces. Hand-catch landing recommended.

### Q4: Power analysis -- 2S battery for pump + servos?

| Component | Current @ 7.4V |
|-----------|----------------|
| R385 pump | ~0.5A |
| MG90S servo x2 (active) | ~0.4A |
| PCA9685 | ~0.005A |
| **Total (firing)** | **~0.9A** |

**300mAh battery = ~20 min continuous firing.** Real mission: ~10-20 seconds of firing total. **Negligible drain.**

**Could share flight battery?** MicoAir H743 has 12V 2A BEC. Viable for development but risk to flight battery. **Dedicated 2S battery recommended for production.**

### Q5: PCA9685 I2C address conflicts?

| Device | Bus | Address | Conflict? |
|--------|-----|---------|-----------|
| PCA9685 | ESP32 I2C (GPIO) | 0x40 | - |
| QMC5883L compass | FC I2C (UART3) | 0x0D | Different bus - no conflict |

**Wiring:** PCA9685 SDA->ESP32 GPIO41, SCL->ESP32 GPIO42, VCC->5V, GND->common.

### Q6: CG shift as water is fired?

15ml water = 15g = 4% of total AUW (359g).

- Reservoir ~20mm behind center
- CG shift when full = 15g x 20mm / 359g = **0.84mm aft**
- After full fire, CG moves forward by 0.84mm

**Below threshold of perceptible impact (<1mm).** No compensation needed.

### Q7: V3 still under 250g? Still flyable?

| Scenario | AUW | TWR | Flyable? |
|----------|-----|-----|----------|
| V3 dry | 344g | 4.2:1 | Yes -- good TWR |
| V3 loaded (15ml) | 359g | 4.0:1 | Yes -- adequate |
| V3 pessimistic | 359g | 3.3:1 | Yes -- above 2:1 |

**V3 is NOT sub-250g** (over by 109g). But **TWR exceeds 4:1** in all scenarios.

**V3 flying characteristics:**
- ~7m/s vertical climb (vs ~12m/s V2)
- ~4 min flight time with payload
- Hand-catch landing required
- Fly in Loiter mode for stability

---

## 6. Go/No-Go Criteria

### V1 to V2 Go/No-Go

**GO to V2 if ALL of:**
- [ ] V1 manual flight successful (tethered hover + free flight)
- [ ] V1 PID tuning complete (no oscillation across flight envelope)
- [ ] ESP32 MAVLink bridge reliable (no packet loss, <50ms latency)
- [ ] GPS lock reliable (3D fix within 60s, >8 satellites)
- [ ] RTL tested and functional
- [ ] Battery: >5 min flight time on 4S 850mAh
- [ ] V1 AUW confirmed <230g (weigh on scale)
- [ ] RunCam Thumb 2 purchased and bench-tested for WiFi stream

**NO-GO if ANY of:**
- [ ] V1 flight unstable (oscillation, drift, failsafe triggers)
- [ ] ESP32 bridge drops MAVLink connection during flight
- [ ] GPS fails to maintain lock in flight
- [ ] Flight time <3 min on fresh battery
- [ ] Camera WiFi causes MAVLink interference (video stream disrupts control)

### V2 to V3 Go/No-Go

**GO to V3 if ALL of:**
- [ ] V2 camera stream reliable (stable WiFi, <200ms latency, 720p@30fps)
- [ ] MacBook YOLO pipeline detects persons at 10m+
- [ ] MacBook tracking (BoT-SORT) maintains ID through gentle maneuvers
- [ ] V2 flight time >4 min with camera active
- [ ] CG verified within tunable range (battery adjustment sufficient)
- [ ] Pump bench-tested: flow rate adequate, no leaks
- [ ] Servo pan-tilt range verified +/-90 deg
- [ ] PCA9685 to ESP32 I2C communication verified
- [ ] MOSFET switching verified (pump on/off via ESP32 GPIO)
- [ ] Payload mount designed and 3D printed

**NO-GO if ANY of:**
- [ ] Camera WiFi latency >300ms (causes tracking lag)
- [ ] YOLO fails to detect persons at 5m (resolution or model issue)
- [ ] V2 flight time <3 min (insufficient mission window)
- [ ] Pump flow <10ml/s (stream too weak for 3m range)
- [ ] Servos jitter or fail to hold position under pump vibration
- [ ] Payload mount causes frame flex or vibration
- [ ] V3 TWR <3:1 on thrust stand measurement

### V3 to Mission Go/No-Go

**GO to mission if ALL of:**
- [ ] V3 loaded test flight stable in Loiter mode (5 min)
- [ ] Auto-aim pipeline: camera -> YOLO -> servo correction cycle <200ms
- [ ] Aim accuracy: servo aims nozzle within 5 deg of target at 5m
- [ ] Firing accuracy: 3 of 5 shots hit a 1m target at 5m
- [ ] Pump fires reliably, no priming issues
- [ ] MOSFET + battery: no overheating after 10 rapid trigger pulls
- [ ] RTL works with full payload (weight + CG verified)
- [ ] Hand-catch landing practiced and reliable

---

## 7. Sub-250g Compliance Strategy

### The Core Problem

V3 AUW (359g) exceeds the 250g limit by 109g. This triggers Transport Canada registration requirements.

### Strategy: Detachable Payload

The water gun payload mounts via a **quick-release dovetail** (3D printed). The drone can fly as:

| Mode | Config | Weight | Compliance | Use Case |
|------|--------|--------|-----------|----------|
| Practice / Testing | V2 (no payload) | 245g | Sub-250g (no registration) | PID tuning, camera testing, daily practice |
| Mission | V3 with payload | 359g | Over 250g (need registration) | School game, actual water firing |
| Empty mission | V3 dry (no water) | 344g | Over 250g | Payload testing without water |

### Recommended Approach

1. **Get registered anyway** (~ CAD for 5 years, basic pilot exam is online open-book)
2. **Fly V2 for daily practice** (sub-250g, no restrictions)
3. **Add V3 payload only for game days** (registered drone, designated safety zone)
4. **Fly V3 only in controlled areas** (no people within 30m per Canadian regs for 250g-1kg drones)

### Weight Reduction Options (if sub-250g V3 is essential)

| Weight Save | Method | Impact | Feasibility |
|------------|--------|--------|-------------|
| -19g | Remove dedicated 2S battery, power payload from FC BEC | Pump at 12V (better), risk to flight battery | Medium |
| -13g | Replace MG90S with SG90 (plastic gear) | Gears strip under load | Low |
| -10g | Replace R385 with micro submersible pump | Range drops to 1-3m | High |
| -8g | Use 4S 650mAh instead of 850mAh | Flight time drops to ~4 min | Medium |
| -5g | Remove PCA9685, use ESP32 PWM direct | Code change needed | Medium |

**Conclusion: Sub-250g V3 is NOT achievable with current water gun payload.** The detachable payload approach is the correct strategy: fly sub-250g for practice, add payload for game days with proper registration.

---

## 8. Decision Matrix

### Recommended Build Path

V1 (manual flight) -> if success -> V2 (camera + tracking) -> if success -> V3 (water gun)

### Hardware Ordering Priority

| Priority | Parts | Cost (CAD) | Order From | Timeline |
|----------|-------|-----------|------------|----------|
| P0 (V2) | RunCam Thumb 2 | 4 | Amazon.ca | 3-7 days |
| P1 (V3 dev) | R385 pump + MG90S x2 + PCA9685 + IRFZ44N + diode | 6 | AliExpress | 2-5 weeks |
| P2 (V3 flight) | 2S 300mAh LiPo + JST kit + tubing + syringe | 7 | AliExpress | 2-5 weeks |
| P3 (printing) | 3D printed mount + nozzle + camera mount | /usr/bin/bash | Library | 1-2 days |

### Total V2+V3 Additional Cost

| Category | CAD |
|----------|-----|
| V2 camera (RunCam Thumb 2) | 4 |
| V3 payload (pump + servos + controller + battery + misc) | 1 |
| **V2+V3 Total (AliEx + Amazon.ca)** | **45 CAD** |
| **Grand total (V1 78 + V2+V3 45)** | **~23 CAD** |

### Confidence Assessment

| Aspect | Confidence | Rationale |
|--------|-----------|-----------|
| Part pricing (AliExpress) | MEDIUM (70%) | Prices fluctuate; current within +/-25% |
| Part weights | MEDIUM (65%) | Estimated from similar products; weigh on arrival |
| TWR calculations | HIGH (85%) | Conservative estimates; 360g/motor is below community data |
| Integration analysis | HIGH (80%) | Based on published tech specs and similar builds |
| Sub-250g compliance | HIGH (90%) | V2 confirmed under 250g; V3 confirmed over |
| Camera WiFi latency | MEDIUM (60%) | Estimates from community reports; test with actual unit |

---

## Appendix A: AliExpress Cart Links

| Part | AliExpress Link (Search) | Est. USD |
|------|-------------------------|----------|
| RunCam Thumb 2 | Search "RunCam Thumb 2 WiFi" | 0 |
| R385 diaphragm pump | https://www.aliexpress.com/item/1005010178771529.html |  |
| MG90S servo 2-pack | https://www.aliexpress.com/item/1005004550692203.html |  |
| PCA9685 servo driver | https://www.aliexpress.com/item/32753750943.html |  |
| IRFZ44N MOSFET | Search "IRFZ44N" on AliExpress |  |
| 2S 300mAh LiPo | https://www.aliexpress.com/item/1005003834564359.html | 7 |
| Silicone tubing 3mm ID | https://www.aliexpress.com/item/1005011839040630.html |  |
| JST connector kit | Search "JST connector kit 2.0mm 1.25mm" |  |
| ESP32-CAM | Search "ESP32-CAM OV2640" on AliExpress |  |

## Appendix B: Existing V1 Parts Reused in V2/V3

| V1 Part | Used in V2? | Used in V3? |
|---------|-------------|-------------|
| MicoAir H743 AIO 35A | Same FC | Same FC (servos on UART5) |
| Master3X Frame | Camera on top plate | Payload on bottom plate |
| Diatone 1505 3800KV motors | Same motors | Same motors (TWR still >4:1) |
| Gemfan 3.5" props | Same props | Same props |
| 4S 850mAh battery | Same battery | Same battery |
| GOKU GM10 GPS | Same GPS | Same GPS |
| XIAO ESP32-S3 (first) | MAVLink bridge | MAVLink bridge |
| XIAO ESP32-S3 (backup) | Not needed | Not needed (separate WiFi networks) |

---

*Document compiled July 5, 2026. Research sources: Tavily API searches of AliExpress listings, Oscar Liang FPV hardware reviews, SpeedyBee Master3X frame specs, RunCam Thumb 2 product specs, R385/R365 pump datasheets, MG90S servo specs, IRFZ44N datasheet, PCA9685 datasheet, existing water-control research, existing cv-pipeline research. Confidence levels noted per section above.*
