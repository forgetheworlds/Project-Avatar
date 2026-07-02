# Avatar Splash — Water Control Mechanism: Deep Research

**Date:** 2026-06-30
**Task:** t_ddcc8c7d (Task 2 - Water Control Mechanism)
**Researcher:** Researcher profile (Hermes)
**Confidence:** MEDIUM (65-75%) — Web research from DuckDuckGo/ddgs (Tavily rate-limited), existing code analysis, and physics first principles. Some component weights are estimated from similar products.

---

## Executive Summary

The Splash water gun payload needs a **<50g total** system (pump + servos + reservoir + nozzle) that can fire water at human targets 3-15m away from a drone. The existing code (`~/Project-Avatar/splash/payload/splash_payload.py`) assumes 2x MG90S servos, a PCA9685 controller, IRLZ44N MOSFET, 15ml syringe reservoir, and an unspecified 15g pump. This research evaluates real-world pump options, nozzle designs, servo sizing, ballistics, firing logic, and a ground-testable prototype.

**Critical finding:** No off-the-shelf pump under 15g delivers both the flow rate AND pressure needed for a stream that reaches 15m. The 50g budget forces a tradeoff: accept **short range (3-5m)** with a micro centrifugal pump, or switch to a **pre-charged pressure system** (Super Soaker-style) for longer range.

---

## 1. Water Pump Comparison

### Candidate Pumps Evaluated

| Pump Type | Model | Voltage | Flow Rate | Pressure (Head) | Weight | Cost | Source |
|-----------|-------|---------|-----------|-----------------|--------|------|--------|
| Micro Submersible (centrifugal) | Generic 3-6V DC | 2.5-6V | 120L/h (2L/min=33ml/s) | 1.1m head (0.11 bar) | ~20-28g | ~$4 | Amazon/AliExpress |
| Micro Diaphragm | FTVOGUE 0.4-1L/min | 12V | 0.4-1L/min (7-17ml/s) | 3 bar (43 psi) | 239g | ~$15 | Amazon.ca |
| Micro Diaphragm | R385 Mini | 6-12V | 1.5-1.8L/min (25-30ml/s) | ~2 bar (30 psi) | 110g | ~$10 | Walmart/AliEx |
| Brushless Diaphragm | 3.5L/min spray drone pump | 12V (3S) | 3.5L/min (58ml/s) | ~4 bar | 29g | ~$20 | RCDrone.top |
| Mini Peristaltic | ATO 130mL/min | 3V/12V | 130mL/min (2ml/s) | Self-priming | ~10g | ~$8 | ATO.com |
| DIY motor + impeller | Custom 3D printed | 3.7-7.4V | Unknown (~50ml/s est) | Unknown | ~5-10g | ~$2 | DIY |
| Pre-charged syringe | Plunger + spring | N/A (servo valve) | Burst: ~15ml/0.5s | ~2-5 bar (manual pump) | ~5g extra | ~$1 | DIY |

### Micro Submersible Pump (3-6V) — Best for weight/flow

The **3-6V DC micro submersible pump** (commonly sold for fountains, aquariums, DIY cooling) is the strongest candidate for the sub-50g budget:
- **Flow:** 120L/h theoretical (in free flow). With a nozzle restriction, expect 0.5-1L/min (8-17ml/s) at the nozzle.
- **Pressure:** Only 1.1m max head = 0.11 bar = 1.6 psi. This is very low.
- **Weight:** ~20-28g (unverified from listings, estimated from similar brushed DC pump dimensions)
- **Current:** 220mA at 5V = 1.1W
- **Priming:** NOT self-priming. Must be below water level in reservoir. Running dry for >30s may damage it.
- **Size:** ~45mm x 30mm x 25mm (approx)
- **Cost:** $3-5 USD on AliExpress, ~$8 on Amazon.ca
- **Con:** Low pressure means short range, stream breaks into droplets quickly.

### Micro Diaphragm Pump (Brushless 29g) — Surprising find

The **3.5L/min brushless diaphragm pump** from RCDrone.top is remarkable:
- Only **29g** weight — within our pump budget!
- 12V (3S battery compatible)
- 3.5L/min at ~4 bar pressure
- 92 x 76 x 46mm — bulky but workable
- Electronics switch required (MOSFET compatible)
- **Critically:** This is an agricultural spray pump. Its pressure is enough for real range.
- **Cost:** ~$20 CAD from RCDrone.top (Chinese direct)
- **Con:** Large footprint may not fit on a micro drone, but the weight is acceptable.

### Mini Peristaltic Pump (10g) — Too slow

Peristaltic pumps are self-priming, dry-run tolerant, and very light:
- 130mL/min (2ml/s) — would need 7.5 seconds for one 15ml trigger pull
- Flow too slow for a satisfying water stream

### DIY Motor + Impeller — Unpredictable

A custom pump using a micro coreless motor (like a 8520 drone motor, ~4g) with a 3D printed impeller housing could theoretically work but requires significant development.

### Pre-Charged Pressure System — Best range, limited shots

**Mechanism:** Pressurize the reservoir on the ground (bike pump). Use a servo-actuated valve or micro solenoid valve to release bursts in flight. No pump on drone.

**Pros:**
- Zero pump weight on drone
- High pressure = long range (5-15m)
- Simple firing mechanism

**Cons:**
- Limited shots per charge
- Pressure drops after each shot
- Need ground support equipment (pump)
- Valve adds weight and complexity

### Pump Recommendation

**RECOMMENDATION: Two-tier approach.**

**Tier 1 (ground test, short range):** Use the $4 micro submersible pump (3-6V, ~25g). Cheap, available, works on 1S/2S battery. Gives 3-5m range. Test the control system, auto-aim, firing logic.

**Tier 2 (production, long range):** Switch to a pre-charged pressure system using a 15-30ml syringe and a servo-actuated valve. Pre-pressurize to 2-3 bar with a bike pump before flight. Yields 10-15m range.

---

## 2. Nozzle Engineering

### Spray Patterns

| Pattern | Use Case | Range | Pros | Cons |
|---------|----------|-------|------|------|
| Solid Stream | Precision aim, long range | Longest | Maximum range, less wind drift | Narrow hit area, needs accurate aim |
| Cone/Full | Area denial, close range | Short | Wide coverage, easier to hit | Short range, wastes water |
| Mist/Fog | Visual effect | Very short | Covers large area | Useless for payload hits |

### Nozzle Diameter vs Range

Using Bernoulli's equation: v_nozzle = Cd * sqrt(2 * P / density)

Where:
- Cd = discharge coefficient (~0.6-0.98 for well-designed nozzle)
- P = pressure (Pa)
- density = water density (1000 kg/m3)

**Range approximation** (ideal, no drag): R = v^2 * sin(2*theta) / g
Maximum at 45 deg: R_max = v^2 / g

### Range Table (No Drag)

| Pressure | Nozzle Velocity | Max Range (45 deg, ideal) | Real Range (w/ drag) |
|----------|-----------------|----------------------|---------------------|
| 0.11 bar (micro submersible) | 4.6 m/s | 2.2 m | 1.5-2 m |
| 1 bar (pre-charge light) | 14 m/s | 20 m | 5-8 m |
| 2 bar (pre-charge medium) | 20 m/s | 41 m | 8-12 m |
| 3 bar (pre-charge/diaphragm) | 24.5 m/s | 61 m | 10-15 m |
| 4 bar (brushless diaphragm) | 28 m/s | 82 m | 12-18 m |

**Key insight:** Water droplets experience significant drag. Stream breaks up into droplets within 2-3m of leaving the nozzle at low pressure. At higher pressure, the stream stays coherent longer. Practical effective range is 30-50% of ideal ballistic range.

### Nozzle Options

1. **3D Printed (PLA/Resin)** — Convergent nozzle (0.6-1.2mm exit, 3-4mm inlet). Smooth internal profile. Post-process for finish.
2. **Brass Aquarium Nozzle** — 3mm barb to 1mm outlet, threaded, $3-5 on Amazon.ca. Best off-shelf option.
3. **Brass Misting Nozzle** — $0.50 on AliExpress. Produces mist, not stream.
4. **Hypodermic Needle (blunt, 18-22 gauge)** — 0.7-1.2mm ID, smooth bore, $0.10 each. Excellent nozzle.
5. **Printer Coolant Nozzle (3D print remix)** — Convergent design, 0.8-1.0mm outlet. Free STL files.

### Nozzle Recommendation

For ground testing: **Brass aquarium nozzle (1mm outlet, 3mm barb)** — $4 on Amazon.ca.

For production: **3D printed convergent nozzle (0.8mm exit)** + blunt hypodermic needle. Print in resin.

**Optimal diameter:** 0.7-1.0mm. Smaller = more range but less flow per second. Larger = more water but shorter range.

---

## 3. Aiming Mechanism — Pan-Tilt Servo Design

### Servo Comparison

| Spec | SG90 (Plastic Gear) | MG90S (Metal Gear) |
|------|--------------------|--------------------|
| Weight | 9g | 13g (9g claimed, 13g actual) |
| Torque @ 4.8V | 1.8 kg-cm | 2.0 kg-cm |
| Torque @ 6V | 2.2 kg-cm | 2.6 kg-cm |
| Speed @ 6V | 0.10s/60 deg | 0.08s/60 deg |
| Gears | Plastic (nylon) | Metal (brass/steel) |
| Cost | $3-4 | $5-7 |
| Durability | Strips easily under load | Much better for continuous use |

### Payload Moment Calculation

**Pan servo (yaw):** Payload (~45g) at ~3cm radius.
Torque = 0.045 * 9.8 * 0.03 * sin(max tilt) = ~0.013 N.m = ~0.13 kg-cm

**Tilt servo (pitch):** Payload at ~4cm radius.
Torque = 0.045 * 9.8 * 0.04 * cos(tilt) = ~0.018 N.m max = ~0.18 kg-cm

Both SG90 (1.8 kg-cm) and MG90S (2.0+ kg-cm) have **10-15x margin** over static torque.

### Prop Wash Analysis

Prop wash from 4x 1505 3800KV motors at hover: estimated **4-8 m/s** downward air velocity.

**Drag force:** F_drag = 0.5 * 1.225 * 36 * 1.0 * 0.0012 = 0.026 N
**Drag moment on tilt servo:** M = 0.026 * 0.04 = 0.001 N.m = ~0.01 kg-cm

**Verdict:** >100x margin. Both SG90 and MG90S hold position easily against prop wash.

### Recommendation

**MG90S for both pan and tilt.** The existing code's choice is correct — metal gears handle vibration better, reduce slop over time. Use PCA9685 at 50Hz.

3D print a custom bracket integrating servo mounts, pump bracket, and reservoir clip (saves ~5g over generic pan-tilt kit).

---

## 4. Firing Logic Design

### Trigger Sequence

1. IDLE STATE — Servos holding, pump OFF, MOSFET gate LOW
2. AIM — Set servo angles, wait 150ms settle
3. FIRE — Check reservoir > 0ml, set MOSFET HIGH, wait duration_ms, set LOW, update reservoir
4. BURST MODE — While target in deadzone: aim, fire 200ms, wait 300ms, re-acquire
   - ~2 shots/sec, ~4ml per 2-shot cycle
   - 15ml reservoir = ~7s burst fire = ~14 shots
5. EMPTY — Block fire commands, send telemetry

### Timing Parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Pump prime time | 50-100ms | Centrifugal pump reaches pressure quickly |
| Min fire duration | 100ms | Safety floor |
| Default burst | 300-500ms | Visible stream at ~3-5ml per shot |
| Max fire duration | 2000ms | Reservoir conservation |
| Servo settle | 150ms | MG90S @ 60 deg takes ~80ms, add margin |
| Between bursts | 300ms | Let stream settle |
| Deadzone (default) | 30px | From existing code |

### Flow Rate Assumptions

For micro submersible pump (120L/h free flow, nozzle-restricted):
- **Free flow:** 33 ml/s
- **Through 1mm nozzle:** Est. 8-15 ml/s
- **Code currently uses:** 1 ml/s (too conservative)
- **Recommended update:** 10 ml/s, 200-500ms burst = 2-5ml per shot

**Reservoir capacity:**
- 15ml syringe = 3-7 shots
- 30ml syringe = 7-15 shots

### Pre-Charged Logic (Production v2)

1. Fill and pressurize on ground (2-3 bar)
2. FIRE = Open servo-actuated valve for 100-300ms
3. Each shot releases 3-10ml depending on pressure and valve time
4. Pressure drops with each shot — ballistics change
5. Simple approach: count shots and warn, accept trajectory change

---

## 5. Ballistics for 3-15m Range

### Governing Physics

Three regimes:
- **Regime 1: Coherent stream** (0-3m) — Behaves as solid jet, mild drag
- **Regime 2: Breakup zone** (3-8m) — Rayleigh-Plateau instability, droplets form, drag spikes
- **Regime 3: Mist** (8m+) — Fine droplets, high drag, minimal impact

### Ballistic Calculation (No Drag)

R = v^2 * sin(2*theta) / g

At 45 deg: R = v^2 / 9.81

| System | Exit Velocity | Ideal Range (45 deg) | Real Range |
|--------|--------------|-------------------|------------|
| Micro submersible (0.11 bar) | 4.6 m/s | 2.2m | 1.5-2m |
| Pre-charge 1 bar | 14 m/s | 20m | 5-8m |
| Pre-charge 2 bar | 20 m/s | 41m | 8-12m |
| Diaphragm 4 bar | 28 m/s | 82m | 12-18m |

### Lead Calculation for Moving Targets

Lead angle: theta_lead = arctan(v_target * t_flight / range)

| Range | ToF | Walking (1.5 m/s) | Running (3 m/s) |
|-------|-----|-------------------|-----------------|
| 3m | 0.6s | 17 deg | 31 deg |
| 5m | 1.0s | 17 deg | 31 deg |
| 10m | 2.0s | 17 deg | 31 deg |

**Simplification:** Lead angle is nearly constant (~17 deg walking, ~31 deg running) because range and ToF scale similarly.

**Implementation:** CV system tracks target velocity. Simple approximation: add 20% of target lateral velocity (m/s) as pan angle offset (degrees).

### Crosswind Effect

- 1mm droplet: drifts ~0.5m in 2m/s crosswind over 10m travel
- 2mm droplet: drifts ~0.3m in same conditions
- Larger nozzle = larger droplets = less wind drift
- Wind >5 m/s makes precision aiming impractical

### Ballistics Recommendation

1. **Ground test:** Micro submersible pump, accept 2-3m range
2. **Production:** Pre-charge to 2-3 bar, test at 5-10m
3. **Lead calc:** Simple velocity-based lead, 2D Kalman filter on target
4. **Wind limit:** 10 km/h (2.8 m/s) crosswind max for acceptable accuracy

---

## 6. Ground-Testable Prototype Under $25

### Parts List

| Item | Spec | Source | Cost | Weight |
|------|------|--------|------|--------|
| Micro submersible pump | 3-6V DC, 120L/h | Amazon/AliExpress | $4 | ~25g |
| MG90S servo (x2) | Metal gear, 13g | Amazon.ca | $6/pair | 26g |
| PCA9685 servo driver | I2C, 16-ch | Amazon.ca | $3 | 2g |
| IRLZ44N MOSFET | Logic-level | Amazon.ca | $1 | 2g |
| 15ml syringe | Luer-lock | Pharmacy | $1 | 5g |
| Silicone tubing | 4mm ID, 1m | Amazon | $3 | 3g |
| Brass aquarium nozzle | 1mm outlet | Amazon.ca | $4 | 5g |
| Protoboard + wires | Perfboard | Amazon | $3 | 5g |
| **Total** | | | **$25** | **~73g** |

If ESP32, breadboard, wires, LiPo already on hand from Avatar, subtract $5-10 from cost.

### Desk Test Wiring

ESP32 GPIO17 (BCM) -> IRLZ44N Gate
IRLZ44N Drain -> Pump negative
IRLZ44N Source -> GND
Pump positive -> 5V

ESP32 SDA(GPIO21) -> PCA9685 SDA
ESP32 SCL(GPIO22) -> PCA9685 SCL
PCA9685 CH0 -> MG90S pan
PCA9685 CH1 -> MG90S tilt
PCA9685 VCC -> 5V, GND -> GND

Water: Reservoir -> silicone tube -> pump -> tube -> nozzle

### Test Procedure

1. **Phase 1 — Servo test:** Sweep pan/tilt servos, confirm PCA9685 comms, measure accuracy.
2. **Phase 2 — Pump test:** Submerge inlet in water, fire GPIO HIGH, measure ml/5s and stream range.
3. **Phase 3 — Aiming test:** Laser pointer on nozzle, measure actual vs commanded aim at 2m.
4. **Phase 4 — Ballistics test:** Fire at grid at 1m, 2m, 3m distance. Plot drop vs distance.
5. **Phase 5 — Burst test:** Auto-fire 10x 300ms bursts. Measure depletion and consistency.

---

## 7. Verification Against Existing Code

The existing `splash_payload.py` assumptions vs research:

| Code Assumption | Research Verdict | Action |
|----------------|-----------------|--------|
| 2x MG90S servos | CORRECT — Metal gear needed | Keep |
| PCA9685 @ 0x40 | CORRECT — Standard I2C addr | Keep |
| IRLZ44N MOSFET | CORRECT — Logic-level | Keep (code is right, splash research said IRFZ44N which is wrong) |
| 15ml syringe | OK for prototype | Keep for now |
| 50g total weight | OPTIMISTIC — 60-75g real | Revise to 70g |
| Pump 15g | UNREALISTIC — 25g min | Revise |
| 1ml/s flow rate | CONSERVATIVE — ~10ml/s real | Update to 10ml/s |
| 0.5ml per 500ms | CONSERVATIVE — ~5ml real | Update |
| 15ml = 30 shots | HOPEFUL — 3-5 shots real | Update |

---

## Decision

**Use the micro submersible pump (3-6V, ~$4, ~25g) for ground testing.** It is the only pump that fits the weight budget and is available cheaply. Accept 3m effective range. For production range (15m), switch to a pre-charged pressure system with servo-actuated valve.

**Servos:** MG90S for both pan and tilt. Already specified in code, confirmed correct by research — 10x torque margin, metal gears for vibration resistance.

**Nozzle:** 0.8mm 3D printed convergent nozzle or 1mm brass aquarium nozzle (~$4 on Amazon.ca).

## Next Action

1. Order ground test parts: micro submersible pump, MG90S servos, PCA9685, IRLZ44N, silicone tubing, brass nozzle (~$25 total)
2. Build desk test rig per wiring diagram
3. Run Phase 1-5 test procedure
4. Based on results, decide on pre-charge pressure system for v2

## Deadline

Parts ordered within 1 week. Desk test within 2 weeks. Production water system decision by end of July.

## Who Should Handle Next

**Muadh (build)** — Order parts, assemble desk test rig, write test scripts.
**Researcher (if needed)** — Deeper dive on pre-charge valve mechanisms (solenoid vs servo vs spring-loaded), CO2 cartridge feasibility for v2.
