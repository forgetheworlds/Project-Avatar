# Project Boat — Claude Research Report

**Date:** 2026-07-28
**Status:** Research complete, design decisions required before CAD finalization

---

## TL;DR — Your Questions Answered

| Question | Answer |
|----------|--------|
| Can I print it and assemble it? | **Yes**, but with bolted joints + epoxy (not just snap-fits). Plan 2-4 weeks of printing. |
| Catamaran vs monohull? | **Catamaran** — self-righting, prints in segments, fast on calm water. |
| Single vs twin motors? | **Single motor + rudder** for budget. Twin motors if you want differential steering and redundancy. |
| Jet drive vs prop? | **Prop** — 20-30% more efficient, cheaper, easier to assemble. |
| What motor? | **3660 2600KV brushless**, $15-22 on AliExpress (with ESC combo). |
| What battery? | **3S 2200mAh 45C LiPo**, $5-7. |
| Budget? | **$75-100** total for electronics. PLA is free from library. |
| Latency? | **10-35ms** phone→ESP32→servo. 50Hz control loop is sufficient for boats. |
| Will PLA survive in water? | **Yes, if epoxy-coated.** PLA degrades over years without coating, but with epoxy it lasts indefinitely. |

---

## 1. Hull Shape: Catamaran vs Monohull

### Catamaran (Current Design) — RECOMMENDED

| Advantage | Details |
|-----------|---------|
| Self-righting | Wide beam + sealed deck = inherently stable. Flips back up. |
| Printability | Two narrow hulls that fit easily on S3 bed. Each hull is a series of segments. |
| Speed | Low wetted surface area = less drag. Easily planes. |
| Stability | No ballast needed. Stable at rest and at speed. |
| Assembly | Two identical hulls (print once, mirror for port/starboard) |

| Disadvantage | Details |
|--------------|---------|
| Bridge deck slap | Waves hitting the cross-deck in chop = noise + drag. Minimize with 80mm+ tunnel clearance. |
| Windage | Higher profile catches more wind (less relevant for RC). |
| Complexity | Two hulls + cross-deck = more parts to join. |

### Monohull (Deep V)

| Advantage | Details |
|-----------|---------|
| Wave handling | Superior in choppy conditions |
| Simplicity | One hull to print and seal |
| Lower cost | Fewer parts, less joining material |

| Disadvantage | Details |
|--------------|---------|
| Not self-righting | Needs ballast (dead weight) or it capsizes |
| Harder to print | Full beam (150mm+) on the bed, or more segments |
| Slower in calm water | More wetted surface = more drag |

### Verdict
**Catamaran wins for your use case.** Self-righting is critical for a remote boat (you can't walk over and flip it). The two-hull design also prints more easily on the S3.

---

## 2. Structural: How to Join Printed Segments

### Critical Finding: Snap-Fits Alone Will Fail

> "Relying on snap-fits alone is highly discouraged for the primary hull structure, as wave-induced shear stress easily deforms plastic clips and compromises the seam." — RC community consensus

### Recommended Joint Method: Bolted + Epoxy Sealed

| Step | Method | Purpose |
|------|--------|---------|
| 1 | **Lap joint or tongue-and-groove** | Alignment + large bonding surface area |
| 2 | **M4 bolts through printed channels** | Primary structural fastener (reversible!) |
| 3 | **Slow-cure epoxy (30-min G/flex)** | Waterproof seal + structural bond |
| 4 | **Fiberglass tape over exterior seams** | Prevents water ingress at joints |
| 5 | **XTC-3D or marine epoxy coat entire hull** | Seals PLA porosity, adds strength |

### Why Bolted (Not Glued) Joints

| Factor | Glued | Bolted |
|--------|-------|--------|
| Reversibility | Can't reprint a section if it breaks | Unbolt, reprint, rebolt |
| Strength | Strong if done right | Strong + mechanical backup |
| Alignment | Needs clamps during cure | Bolts self-align |
| Waterproofing | Epoxy seals the joint | Epoxy + bolt compression |

### Joint Design Specs

```
┌─────────────────────────────────┐
│   Segment A                    │
│   ┌────────────────────────┐   │
│   │  5mm overlap surface   │   │ ← Flat mating face, sanded 120-grit
│   │  ○ M4 bolt channel     │   │ ← 4.5mm hole, M4 bolt through
│   │  ○ M4 bolt channel     │   │
│   └────────────────────────┘   │
│          ↕ 0.15mm gap          │ ← Filled with thickened epoxy
│   ┌────────────────────────┐   │
│   │  5mm overlap surface   │   │
│   │  ○ M4 bolt channels     │   │
│   │  ○ M4 bolt channels     │   │
│   └────────────────────────┘   │
│   Segment B                    │
└─────────────────────────────────┘
         ↕ External: fiberglass tape + epoxy
```

### Surface Prep Protocol

1. Sand mating surfaces with 120-220 grit in multiple directions
2. Clean with isopropyl alcohol
3. Apply thin sealing coat of epoxy to both faces (let soak 10-15 min)
4. Apply thickened epoxy (epoxy + silica filler)
5. Press together, insert M4 bolts, tighten
6. After cure: fiberglass tape over exterior seam

---

## 3. Propulsion: Prop vs Jet vs Twin

### Head-to-Head Comparison

| Metric | Single Prop | Twin Prop | Jet Drive |
|--------|------------|-----------|-----------|
| **Thrust** | 4-5 kg (1x 3660) | 4-6 kg (2x 2845) | 3-4 kg (1x 3660) |
| **Efficiency** | 100% baseline | ~95% (two props) | 70-80% (30% loss in housing) |
| **Cost** | $25-30 motor+ESC | $30-40 (2x motors+ESCs) | $25-30 motor+ESC + $15 impeller |
| **Top Speed** | 30-40 km/h | 25-35 km/h | 15-25 km/h |
| **Steering** | Rudder + servo ($5) | Differential thrust (free!) | Nozzle servo ($5) |
| **Assembly** | Simple shaft+prop | 2x shafts+props | Complex: impeller+stator+nozzle |
| **Debris** | Tolerates weeds | Tolerates weeds | Clogs on leaves/twigs |
| **Maintenance** | Replace bent props | Replace bent props | Replace worn wear ring |
| **Redundancy** | None | One motor dies, limp home | None |

### Why Twin Prop Wins for Your Use Case

1. **Differential thrust = free steering** — deletes rudder, servo, and linkage
2. **Redundancy** — one motor dies, you limp home on the other
3. **Chop performance** — when one hull ventilates (lifts out of water), the other still pushes
4. **Same cost** as single motor setup (~$30-40 total)
5. **The boat becomes the cannon turret** — fixed-forward cannon, aim by turning

### What the Research Says

From RCBoatHQ: *"Jets are more forgiving of impacts, props are more forgiving of debris."*

Propellers give **20-30% higher thrust efficiency** than jet drives at low-to-moderate speeds. For a small lake boat, props are clearly better.

### If You Go Single Prop (Budget Option)

- **3660 2600KV** motor + **60-80A waterproof ESC** + **38-40mm prop**
- Add rudder + SG90 servo for steering
- Simpler to assemble, proven design
- Total: ~$25-30 for motor/ESC/prop + $5 servo

### If You Go Twin Prop (Recommended)

- **2x 2845 3000KV** motors + **2x 60A ESCs** + **2x 30mm props**
- Differential thrust for steering (no rudder)
- More complex wiring but more capable
- Total: ~$30-40 for motors/ESCs/props

---

## 4. Motor and Battery Sizing

### Motor: 3660 2600KV (Single) or 2x 2845 3000KV (Twin)

| Spec | 3660 (Single) | 2x 2845 (Twin) |
|------|---------------|-----------------|
| Size | 36mm dia x 60mm length | 28mm dia x 45mm length each |
| KV | 2600 | 3000 |
| Battery | 3S (11.1V) | 3S (11.1V) |
| Prop | 38-40mm | 30mm each |
| Thrust | 4-5 kg | 4-6 kg combined |
| Weight | ~200g | ~120g each |
| Price (AliExpress) | $12-18 | $8-12 each |

### Battery: 3S 2200mAh 45C LiPo

| Config | Weight | Cruise Runtime | Full Throttle | Price |
|--------|--------|----------------|---------------|-------|
| 3S 2200mAh 45C | 170g | 5-8 min | 2-3 min | $5-7 |
| 3S 3300mAh 45C | 250g | 8-12 min | 3-4 min | $8-10 |
| 2S 3300mAh 45C | 165g | 10-18 min | 3-5 min | $5-7 |

**Recommendation:** Start with **3S 2200mAh** (lighter, cheaper). Upgrade to 3300mAh if you want longer runs.

### ESC: 60-80A Waterproof

From Hobbywing SeaKing V4 chart:

| ESC | Max Boat Length | Current | Price |
|-----|----------------|---------|-------|
| SeaKing 60A V4 | 60cm | 60A/200A peak | ~$15 |
| SeaKing 90A V4 | 80cm | 90A/360A peak | ~$20 |

**Budget option:** Generic waterproof 60-80A ESC from AliExpress, $3-9.

---

## 5. Control Loop Architecture

### Latency Budget (Phone to ESP32 to Servo)

| Stage | Latency | Optimization |
|-------|---------|-------------|
| Phone app processing | 1-3 ms | Minimize JSON overhead |
| WiFi (local network) | 2-10 ms | Disable power save, dedicated channel |
| ESP32 parse + compute | 1-2 ms | Binary protocol, async handler |
| PID computation | <1 ms | Trivial at 50Hz |
| PWM cycle to servo | 0-20 ms | One PWM cycle delay |
| **Total** | **~10-35 ms** | **Well within 50ms budget** |

### Three-Layer Control Architecture

```
LAYER 3: LLM (Ground Station) — 0.2-0.5 Hz
  "Steer toward the red buoy"
  Runs on MacBook. Sends high-level goals every 2-5 seconds.
  Uses still JPEG frames + telemetry JSON.

LAYER 2: Guardian (ESP32) — 10-50 Hz
  PID heading hold, rate limiting, fail-safe
  Independent of LLM — runs continuously.
  Smooths incoming commands into trajectories.
  500ms timeout — cut throttle + center steering.

LAYER 1: Hardware — 50 Hz PWM
  Servo position, ESC throttle
  Direct LEDC PWM output, no computation.
  Physical boat (inherently damped by water).
```

### Why 50Hz is Enough for Boats

| System | Natural Frequency | Required Control Rate | Why |
|--------|------------------|----------------------|-----|
| Small boat | 0.03-0.3 Hz | **10-50 Hz** | Water damping, slow dynamics |
| Drone | 20-100 Hz | 400-1000 Hz | Inherently unstable, fast aerodynamics |
| Robot arm | 10-100 Hz | 1000-10000 Hz | High precision, force control |

Boats are **100x slower than drones**. The water provides massive damping. 50Hz is ArduPilot Rover standard — proven sufficient.

### PID Heading Hold (Twin-Prop Differential)

```
rudder_output = Kp * heading_error + Ki * integral(error) + Kd * d(error)/dt

Where:
  heading_error = target_heading - current_heading
  (use atan2(sin, cos) for wrapping at 180 degrees)

Starting PID values (tune in water):
  Kp = 1.0    (0.1-5.0 range)
  Ki = 0.05   (0.0-0.5 range)
  Kd = 0.5    (0.0-3.0 range)

Dead band: 2-3 degrees around target (prevents jitter)
Output clamp: -100 to +100 (maps to motor differential)
```

### Critical WiFi Optimization

```cpp
// In ESP32 setup():
WiFi.setSleep(false);  // MANDATORY — disables power save
// or: esp_wifi_set_ps(WIFI_PS_NONE);

// Use binary protocol, not JSON:
// struct Cmd { uint8_t throttle; int8_t rudder; } — 2 bytes
// vs JSON: {"action":"throttle","value":50} — 30+ bytes
```

### Code-as-Policies (Google DeepMind)

Waddle Labs is defunct. The closest relevant work:

**"Code as Policies" (Google DeepMind, 2022)**
- Paper: arXiv:2209.07753
- Architecture: LLM generates executable Python code from natural language
- Two-layer: LLM planning (low frequency) -> motor APIs (high frequency)
- Code contains loops and conditionals for closed-loop recovery
- **Directly applicable** — the LLM generates "go to waypoint X" code, ESP32 executes the PID loop

---

## 6. Cost Breakdown (Under $100)

### Option A: Single Motor + Rudder (Budget Champion)

| Component | Specification | Source | Price (USD) |
|-----------|--------------|--------|-------------|
| Motor + ESC | 3660 2600KV + 80A waterproof combo | AliExpress | $18-22 |
| Battery | 3S 2200mAh 45C LiPo XT60 | AliExpress | $5-7 |
| Servo | SG90 (rudder steering) | AliExpress | $2-3 |
| Rudder + linkage | 3D printed + M3 hardware | Library print + hardware store | $3-5 |
| Propeller | 38-40mm 2-blade | AliExpress | $2-4 |
| Shaft + coupler | 4mm brass tube + set screw | Hardware store | $3-5 |
| ESP32 DevKit | 30-pin WiFi + PWM | AliExpress | $3-5 |
| Water pump | 12V bilge pump | AliExpress | $8-12 |
| GPS | NEO-6M | AliExpress | $8-10 |
| Compass | HMC5883L | AliExpress | $2-3 |
| Misc hardware | M3/M4 bolts, nuts, silicone | Hardware store | $5-10 |
| Epoxy | XTC-3D or West System 105 | Amazon/hardware | $10-15 |
| PLA filament | 2-3 kg (library rate $0.12/g) | Library | $0* |
| **TOTAL** | | | **$69-101** |

*Library printing = free or near-free with membership.

### Option B: Twin Motor (Recommended)

| Component | Specification | Source | Price (USD) |
|-----------|--------------|--------|-------------|
| Motors (2x) | 2845 3000KV brushless | AliExpress | $16-24 |
| ESCs (2x) | 60A waterproof | AliExpress | $6-18 |
| Battery | 3S 3300mAh 45C LiPo XT60 | AliExpress | $8-10 |
| Props (2x) | 30mm 3-blade | AliExpress | $4-6 |
| Shafts (2x) | 4mm brass tube | Hardware store | $4-6 |
| ESP32 DevKit | 30-pin WiFi + PWM | AliExpress | $3-5 |
| Water pump | 12V bilge pump | AliExpress | $8-12 |
| GPS | NEO-6M | AliExpress | $8-10 |
| Compass | HMC5883L | AliExpress | $2-3 |
| Misc hardware | M3/M4 bolts, nuts, silicone | Hardware store | $5-10 |
| Epoxy | XTC-3D or West System 105 | Amazon/hardware | $10-15 |
| PLA filament | 2-3 kg | Library | $0* |
| **TOTAL** | | | **$74-119** |

---

## 7. Printability on Ultimaker S3

### Segmentation Plan

Each pontoon: 4 segments x 2 pontoons = **8 hull segments**
Cross-deck: 2 halves = **2 deck segments**
Electronics tray + cannon + standoff: 3 parts
**Total: ~13 parts to print**

### Print Time Estimates

| Settings | Per Segment | Total (13 parts) | Calendar Time |
|----------|------------|-------------------|---------------|
| **Fast** (0.2mm, 60% infill, 3 walls) | 6-12 hrs | 80-160 hrs | 3-7 days |
| **Standard** (0.15mm, 80% infill, 4 walls) | 10-20 hrs | 130-260 hrs | 5-11 days |
| **Waterproof** (0.12mm, 100% infill, 5 walls) | 20-40 hrs | 260-520 hrs | 11-22 days |

### Recommended Print Settings

| Parameter | Value | Why |
|-----------|-------|-----|
| Layer height | 0.15mm | Good balance of speed and adhesion |
| Wall count | 4-6 | Multiple barriers against water |
| Infill | 80% gyroid | Structural + water resistance |
| Temperature | 215-225C | Better layer bonding |
| Flow rate | 102-105% | Eliminates micro-gaps |
| Print speed | 40-50 mm/s | Better fusion |
| Cooling fan | 40% | Better adhesion |

---

## Sources

| Source | Key Finding |
|--------|-------------|
| RCGroups waterproofing thread | Epoxy coat over PLA works; acetone wipe first |
| BoatDesign.net engineering thread | 6kg PLA core canoe held 80kg; 100% infill for hull |
| RCBoatHQ jet vs prop guide | Props 20-30% more efficient; jets clog on debris |
| Arctic Challenge build log | 10 segments, bolted not glued, O-ring seals |
| Code as Policies (arXiv:2209.07753) | LLM generates code, low-freq planning + high-freq control |
| ESP-IDF LEDC docs | 1-40MHz PWM, 1-20 bit resolution |
| ArduPilot Rover params | 50Hz control loop, PID tuning procedure |
| AliExpress motor/ESC combos | 3660+80A combo $18-22; 2845 $8-12 each |
| Smooth-On XTC-3D | 2:1 mix, 1oz/100sqin, 3.5hr cure, PLA compatible |
| Wikipedia PLA | Glass transition 60-65C, hydrolysis degradation |
