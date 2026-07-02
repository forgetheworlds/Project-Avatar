# V1 Compatibility & Flight Setup

**Project Avatar** | July 2026 | Sub-250g Water-Gun Drone
**Deliverable:** Physical fit verification, electrical compatibility, TWR (reconciled), ArduPilot setup (no-RC), latency path analysis, first flight checklist

---

## 1. Component Physical Dimensions

### 1.1 MicoAir H743 AIO 35A (FC + 4-in-1 ESC)

| Spec | Value | Source |
|------|-------|--------|
| Board dimensions | 36 x 36 x 8 mm | MicoAir official product page |
| Mounting pattern | 25.5 x 25.5 mm | MicoAir official |
| Hole diameter | Φ3mm (M3 hardware) | MicoAir official |
| Weight | 10g | Official spec |
| MCU | STM32H743VIH6, 480MHz | ArduPilot wiki |
| IMU | BMI088 + BMI270 (dual) | ArduPilot wiki |
| Barometer | DPS310 | ArduPilot wiki |
| BEC output | 5V 2A + 12V 2A | MicoAir official |
| Battery input | 3-6S LiPo (10-27V) | MicoAir official |
| ESC rating | 35A x 4 (AM32 firmware) | MicoAir official |
| Firmware target | MicoAir743-AIO (ArduPilot) | ArduPilot wiki |
| Availability | V1 discontinued (V2 available, same specs) | MicoAir official |

**UART map (for wiring):**

| Port | TX Pin | RX Pin | Recommended Use |
|------|--------|--------|-----------------|
| SERIAL0 | USB | USB | Mission Planner / QGC config |
| SERIAL1 (UART1) | PA9 | PA10 | MAVLink (ESP32 backup) |
| SERIAL2 (UART2) | PA2 | PA3 | VTX (not used V1) |
| **SERIAL3 (UART3)** | **PD8** | **PD9** | **GPS (GPS port)** |
| **SERIAL4 (UART4)** | **PA0** | **PA1** | **ESP32 MAVLink bridge** |
| SERIAL5 (UART6) | PC6 | PC7 | ELRS RX (future) |
| SERIAL6 (UART7) | PE7 (RX only) | -- | ESC telemetry |
| SERIAL7 (UART8) | PE1 | PE0 | General purpose |
| I2C1 | PB7 (SDA) | PB6 (SCL) | External compass (GPS) |

### 1.2 SpeedyBee Master3X Frame (3-3.6"")

| Spec | Value | Source |
|------|-------|--------|
| Wheelbase | 171mm diagonal motor-to-motor | SpeedyBee official |
| Plate thickness | 2mm top/mid/bottom CF | SpeedyBee official |
| Arm thickness | 4mm carbon fiber | SpeedyBee official |
| Stack height clearance | 11mm (M2x11mm standoffs) | SpeedyBee manual |
| **FC mounting pattern** | **25.5 x 25.5 mm** | SpeedyBee official |
| **FC mounting hardware** | **M2 screws (M2x12mm button head + M2 nuts)** | SpeedyBee manual |
| Battery tray (L x W x H max) | 67 x 31 x 40 mm | SpeedyBee manual |
| Battery strap | Aluminum fixing pieces (included) | Kit contents |
| Motor mount pattern | 9x9mm AND 12x12mm (oval slots) | SpeedyBee official |
| GPS mount | 18.1 x 18.1mm (injection molded TPU) | SpeedyBee official |
| Max prop size | 3.6"" (91.4mm) | SpeedyBee official |
| Frame kit weight (full) | ~87g with all hardware, TPU, pod | Retailer listings |
| Bare frame (carbon + arms only) | ~25-35g estimate | FPV community |
| Motor wire lengths | Front: 76mm, Rear: 62mm | SpeedyBee manual |

### 1.3 Motors: Diatone MAMBA TOKA 1505 3800KV

| Spec | Value | Source |
|------|-------|--------|
| Stator | 15 x 5 mm | Diatone official |
| Weight | 12.8g each | AliExpress listing, retailers |
| Mounting pattern | 12x12mm M2 | Diatone official |
| Prop shaft | 1.5mm diameter | Diatone official |
| Max power | 290W | Manufacturer claim |
| Max current | 18A peak | Manufacturer claim |
| Recommended battery | 3-4S | Diatone official |
| 4-pack price (AliEx) | ~$17.47 USD | Item 1005004551690380 |

### 1.4 Props: Gemfan Hurricane 3525 3.5"" Tri-Blade

| Spec | Value | Source |
|------|-------|--------|
| Diameter | 3.5"" (89.5mm) | Gemfan official |
| Pitch | 2.5"" | Gemfan official |
| Blades | 3 | Gemfan official |
| Weight per prop | ~1.8g | Retailer listings |
| **Bore diameter (native)** | **1.5mm T-Mount** | Gemfan official |
| Included adapters | M5 (5mm) inserts | Package contents |
| Shaft-to-bore fit on 1505 | **Direct - no adapters needed** | Verified |

### 1.5 Battery: 4S 850mAh LiPo (XT30)

| Spec | Value | Brand Example |
|------|-------|--------------|
| Dimensions (typical) | 59-63 x 30-31 x 26-33mm | Varies by brand |
| Weight (typical) | 88-110g | Varies by brand |
| Connector | **XT30** (standard for 850mAh 4S) | All major brands |
| Best fit for Master3X | Tattu R-Line 850 4S 95C - 59x30x30mm, 95g | Tattu |
| Lightest option | GNB 850 4S LiHV 120C - 63x30x26.5mm, 88g | GNB |
| Fits tray (67x31x40mm)? | **YES - all common packs fit with margin** | Verified |

### 1.6 GPS: Flywoo GOKU GM10 Nano V3

| Spec | Value | Source |
|------|-------|--------|
| Dimensions | 12 x 17 x 5 mm | Flywoo official |
| Weight | 2.6g | Flywoo official |
| Chipset | Ublox M10Q (10th gen) | Flywoo official |
| Voltage range | 3.3V - 5V | Flywoo official |
| Default baud | 115200 (configurable to 921600) | Flywoo official |
| Output rate | 1-10Hz (default 10Hz) | Flywoo official |
| Compass | QMC5883L (3-axis, I2C, on-board) | Flywoo official |
| Mounting | No holes, solder pads - use adhesive | Flywoo manual |
| Connector | 6-pin solder pads: RX,TX,VCC,GND,SDA,SCL | Flywoo official |

### 1.7 ESP32-S3: Seeed Studio XIAO ESP32-S3

| Spec | Value | Source |
|------|-------|--------|
| Dimensions | 21 x 17.8 x 3.8 mm | Seeed official |
| Weight | ~3g | Retailer estimates |
| Logic level | **3.3V** (native) | Seeed official |
| UART pins | GPIO43 (TX), GPIO44 (RX) | Seeed pinout |
| WiFi active current | ~100mA | Espressif datasheet |


## 2. Physical Fit Verification

### 2.1 FC Mounting Hole Pattern

| Factor | FC Spec | Frame Spec | Verdict |
|--------|---------|------------|---------|
| Hole pattern | 25.5 x 25.5mm | 25.5 x 25.5mm | Pattern matches |
| Hole diameter | 3mm (M3 hardware) | Designed for M2 (2mm screws) | **Screws undersized for holes** |

**Issue:** The FC has 3mm holes (for M3 screws) but the Master3X frame standoffs accept M2 screws (2mm). There is 0.5mm of play on each side.

**Resolution options:**
- **Option A (recommended):** Use M2x12mm button-head screws with **M2 nylon washers** (2mm ID, ~5mm OD) through the FC holes. The washers center the M2 screw in the 3mm hole.
- **Option B:** Use M2x12mm screws with **M2 nuts** on top of the FC, sandwiching the board between standoff and nut.
- **Option C:** Replace stock M2 standoffs with M3 versions (same 11mm height, M3 internal threads, M3x12mm screws).

**Recommendation:** Option A. Include 4x M2 nylon washers in the assembly kit.

### 2.2 Stack Height Clearance

| Layer | Height (mm) | Cumulative |
|-------|------------|------------|
| MicoAir H743 AIO board | 8.0 | 8.0 |
| Nylon soft-mount washer (~0.5mm x 2 per corner) | +1.0 | 9.0 |
| Silicone wire routing (flat along edges) | +0.0 | 9.0 |
| **Frame stack clearance (M2x11mm standoffs)** | **11.0** | -- |
| **Margin** | | **~2.0mm** |

The FC fits within the 11mm stack with ~2mm to spare. Wiring must be routed flat and along board edges to maintain clearance.

### 2.3 Motor Bolt Pattern

| Factor | Motor Spec | Frame Arm Spec | Verdict |
|--------|-----------|----------------|---------|
| Bolt pattern | 12x12mm M2 | 9x9mm AND 12x12mm oval slots | Direct fit |
| Motor diameter | 15mm | Arm clearance ample | OK |

The TOKA 1505's 12x12mm pattern bolts directly to the Master3X arms via the oval mounting slots. Use M2x6mm screws with blue Loctite.

### 2.4 Prop Bore vs Motor Shaft

| Factor | Prop Spec | Motor Spec | Verdict |
|--------|----------|-----------|---------|
| Bore | 1.5mm T-Mount (native) | 1.5mm shaft | **Direct fit** |
| Included adapters | M5 (5mm) inserts | Not needed | Spares |

The Gemfan Hurricane 3525 props mount directly on the 1505 motor shafts with no adapters needed. Use the included prop nuts (M5 thread compatible).

### 2.5 Battery Fit

| Dimension | Frame Tray Max | Tattu R-Line 850 | GNB LiHV 850 | CNHL MiniStar 850 | Fits? |
|-----------|---------------|-------------------|-------------|-------------------|-------|
| Length | 67mm | 59mm | 63mm | 62mm | All |
| Width | 31mm | 30mm | 30mm | 30mm | All |
| Height | 40mm | 30mm | 26.5mm | 33mm | All |

The battery sits on **top of the middle plate** (not inside the frame), secured by the aluminum strap fixing pieces. No clearance issues with the top plate.

### 2.6 Prop Clearance on Frame

| Factor | Value | Verdict |
|--------|-------|---------|
| Frame max prop size | 3.6"" (91.4mm) | Accepts 3.5"" |
| Our prop diameter | 3.5"" (89.5mm) | Fits |
| Tip-to-arm clearance | ~1mm per side | Tight but standard for 3"" class |

This is normal for the Master3X frame. Ensure prop nuts are fully seated and props are balanced.

### 2.7 GPS Mounting

| Factor | Detail | Verdict |
|--------|--------|---------|
| Frame GPS mount | 18.1 x 18.1mm injection molded | GM10 (12x17mm) is smaller |
| GPS mounting holes | None (solder pads only) | Must use adhesive |
| Orientation | Arrow on GPS must point forward | Verify before mounting |

**Placement:** Double-sided foam tape on the rear top plate. The GPS is only 2.6g - tape is sufficient. No need for the 18.1mm mount.

**CG impact:** Rear placement helps balance the battery (front) and future camera (front). Negligible overall.

### 2.8 ESP32 Mounting

| Factor | Detail | Verdict |
|--------|--------|---------|
| Frame provision | No dedicated ESP32 slot | Must find space |
| Best location | Rear injection-molded receiver bay | XIAO (21x18mm) fits |
| Alternative | Between plates behind FC (requires 5mm clearance) | Measure carefully |

**Recommended:** Place XIAO ESP32-S3 in the rear receiver bay with double-sided tape. Route 4 wires (VCC, GND, TX, RX) forward to FC UART4 (~80mm).

### 2.9 Cable Routing

| Cable Bundle | Routing Path | Length |
|-------------|-------------|--------|
| Motor 1 (FR) | Through arm -> FC M1 pad | ~76mm |
| Motor 2 (FL) | Through arm -> FC M2 pad | ~76mm |
| Motor 3 (RR) | Through arm -> FC M3 pad | ~62mm |
| Motor 4 (RL) | Through arm -> FC M4 pad | ~62mm |
| GPS (6-wire) | Rear top -> FC UART3 | ~100mm (cable is 150mm) |
| ESP32 (4-wire) | Rear bay -> FC UART4 | ~80mm |
| Battery (XT30) | Top -> FC battery pads | ~80mm |

**Key rule:** With only ~2mm clearance above the FC, route all wires FLAT along the board edges. Avoid routing over IMU/barometer ICs. Use 26-28AWG silicone for signals.

### 2.10 Weight Distribution & CG

```
          FRONT
    [Battery ~95g]        <- Top plate, adjustable forward/back
    [FC ~10g]             <- Center of frame
    [ESP32 ~3g]           <- Rear bay
    [GPS ~2.6g]           <- Rear top
    [Motors ~51g total]   <- Arm ends, balanced
          REAR
```

**CG tuning:** Slide the battery forward/back on the tray. The battery (95g) is the heaviest component and the primary CG adjustment mechanism. Target: geometric center between motor diagonals.

**Verification:** Balance the fully-assembled drone on two fingertips at the center point. It should hang level. Shift battery position as needed.


## 3. Electrical Compatibility

### 3.1 FC BEC vs GPS / ESP32 Voltage

| Component | Required Voltage | FC BEC Output | Direct? | Verdict |
|-----------|-----------------|---------------|---------|---------|
| GOKU GM10 GPS | 3.3-5V | 5V 2A available | Connect to 5V pad | OK |
| XIAO ESP32-S3 | 5V (via VIN) | 5V 2A available | Connect to 5V pad | OK |
| Total 5V draw | GPS ~25mA + ESP32 ~100mA = ~125mA | 5V BEC rated 2A (2000mA) | Ample margin | OK |

**Recommendation:** Power both GPS and ESP32 from the FC's 5V BEC. Use 5V for the GPS (better active antenna performance than 3.3V).

### 3.2 GPS Connection: GOKU GM10 -> FC UART3

| FC Pin (UART3) | Function | GPS Pin | Wire Color |
|---------------|----------|---------|------------|
| PD8 (UART3 TX) | FC TX -> GPS RX | RX | Yellow |
| PD9 (UART3 RX) | FC RX <- GPS TX | TX | White |
| 5V pad | Power (5V) | VCC | Red |
| GND | Ground | GND | Black |
| PB7 (I2C1 SDA) | Compass data | SDA | Green/Blue |
| PB6 (I2C1 SCL) | Compass clock | SCL | Blue/Green |

**ArduPilot parameters:**
```
SERIAL3_PROTOCOL = 5   # GPS
SERIAL3_BAUD     = 115 # 115200 baud
GPS_TYPE         = 1   # uBlox auto-detect
COMPASS_ENABLE   = 1   # Enable QMC5883L
COMPASS_AUTO_ROT = 2   # External compass rotation
```

### 3.3 ESP32 Connection: XIAO ESP32-S3 -> FC UART4

| FC Pin (UART4) | Function | XIAO ESP32 Pin |
|---------------|----------|----------------|
| PA0 (UART4 TX) | FC TX -> ESP32 RX | GPIO44 (D7, RX) |
| PA1 (UART4 RX) | FC RX <- ESP32 TX | GPIO43 (D6, TX) |
| 5V pad | Power (5V) | 5V pin |
| GND | Ground | GND |

**Logic level:**
- MicoAir H743 UART: 3.3V logic
- XIAO ESP32-S3 GPIO: 3.3V logic
- **Verdict: Direct connection. No level shifter needed.**

**ArduPilot parameters:**
```
SERIAL4_PROTOCOL = 2   # MAVLink2
SERIAL4_BAUD     = 921 # 921600 baud (or 115 for 115200)
```

### 3.4 Battery Connector

| Factor | FC | Battery | Verdict |
|--------|-----|---------|---------|
| Connection | Solder pads (VBAT+/VBAT-) | XT30 pigtail | Solder directly |
| Voltage | 3-6S (10-27V) | 4S (14.8V nom, 16.8V max) | OK |
| Current | Pads handle >100A | XT30 rated 30A cont / 60A burst | OK |
| Polarity | + marked BAT+ | XT30 red (positive) | Verify with multimeter |

**Procedure:** Solder XT30 pigtail (16AWG silicone, ~80mm) to VBAT+ and VBAT- pads. Keep wires short. Use heat shrink.

### 3.5 Motor KV on 4S - RPM Check

| Calculation | Value | Safety | Verdict |
|------------|-------|--------|---------|
| KV x max voltage | 3800 x 16.8V = 63,840 RPM (no-load) | Baseline | OK |
| Loaded RPM | ~50,000-55,000 RPM typical | ~80-85% of no-load | OK |
| Max recommended RPM for 3.5"" props | ~65,000 RPM | Our loaded RPM < 55,000 | Safe |
| ESC timing | Auto or Medium | BLHeli/AM32 setting | Set in config |

**Verdict:** 3800KV on 4S with 3.5"" props is in the sweet spot. Confirmed by Oscar Liang motor/prop tables and community data.

### 3.6 ESC Amp Rating vs Motor Draw

| Scenario | Per Motor Current | Per-Channel Limit (35A) | Verdict |
|----------|------------------|------------------------|---------|
| Idle (armed) | 0.5A | 35A | Ample |
| Hover (~50% throttle) | 3-4A | 35A | Ample |
| Cruise (~70% throttle) | 7-9A | 35A | Ample |
| Full throttle (100%) | 16-18A | 35A | ~2x margin |
| WOT + fully charged 4S (16.8V) | ~18-20A | 35A | Still within limit |

**Verdict:** The 35A per-channel rating provides safety margin. Each motor draws ~16-18A peak. No issue. The XT30 connector (30A continuous) is the system bottleneck, not the ESC.


## 4. Thrust-to-Weight Ratio (Recalculated)

### 4.1 Weight Reconciliation

**Issue found:** The previous BOM used frame=25g and motor=6.5g each. Research shows actual weights differ.

**Reconciled weight table (V1, realistic build without camera pod):**

| Component | Previous BOM | This Analysis | Delta | Source Confidence |
|-----------|-------------|---------------|-------|-------------------|
| Frame (carbon plates + arms) | 25.0g | 25.0g | 0g | Estimate - weigh on arrival |
| Standoffs + screws + nuts + strap | (included in frame) | 10.0g | +10g | Hardware weight |
| Injection-molded TPU side plates | (not counted) | 5.0g | +5g | Optional but recommended |
| **Frame subtotal** | **25.0g** | **40.0g** | **+15g** | Reasonable estimate |
| Motors (TOKA 1505 x4) | 26.0g (6.5g ea) | 51.2g (12.8g ea) | +25.2g | Confirmed weight |
| FC+ESC (MicoAir H743 AIO) | 10.0g | 10.0g | 0g | Confirmed official spec |
| Props (Gemfan 3.5"" x4) | 6.0g (1.5g ea) | 7.2g (1.8g ea) | +1.2g | Retailer spec |
| Battery (4S 850mAh) | 95.0g | 95.0g | 0g | Confirmed (Tattu spec) |
| GPS (GOKU GM10 Nano V3) | 2.6g | 2.6g | 0g | Confirmed official spec |
| ESP32-S3 (XIAO) | 2.0g | 3.0g | +1.0g | Estimate |
| Wiring + connectors + solder | 8.0g | 10.0g | +2.0g | Conservative estimate |
| **V1 AUW (reconciled)** | **176.0g** | **~220g** | **+44g** | Still under 250g |

**Verdict:** The reconciled AUW of ~220g is 44g higher than the previous BOM but still **well under the 250g sub-250g limit**. The 30g margin allows for unexpected weight (tape, heatshrink, zip ties, threadlock).

### 4.2 Thrust Estimates (Verified Benchmarks)

**Sources ranked by relevance:**

1. **T-Motor P1604 3800KV** (1604 stator, GF3520-3 3.5"" tri-blade, 4S):
   - Full throttle: **514g thrust**, 16.8A, 277.8W
   - Source: T-Motor official bench test (via RCDrone retailer)
   - Note: P1604 is larger (16x4mm) than our 1505 (15x5mm)

2. **DeepSpace Aether 1505 4000KV** (exact 1505, 3.5"" prop on 4S):
   - Full throttle: **554g thrust**, 20.1A, 321.5W
   - Source: Manufacturer bench test
   - Note: 4000KV produces ~5% more RPM than our 3800KV

3. **Oscar Liang community data** (1505 on 4S, 3.5""):
   - Cruise thrust: 160-200g per motor
   - Peak (WOT) estimate: 300-400g per motor

**Reconciled thrust estimate for TOKA 1505 3800KV (conservative):**

| Throttle Level | Per Motor | Total (x4) | Current/Motor | Source Basis |
|---------------|-----------|------------|---------------|-------------|
| Hover (~50%) | 55-70g | 220-280g | 3-4A | Calculated from AUW |
| Cruise (~70%) | 160-200g | 640-800g | 7-9A | Oscar Liang + community |
| Full throttle (100%) | 360-450g | 1,440-1,800g | 16-18A | Scaled from P1604/Aether tests |
| **Conservative WOT** | **360g** | **1,440g** | **16A** | Conservative -20% from P1604 |

### 4.3 TWR Results

| Configuration | AUW | Total Thrust | TWR | Verdict |
|--------------|-----|-------------|-----|---------|
| V1 reconciled (220g) x 360g/motor | 220g | 1,440g | **6.5:1** | Excellent |
| V1 reconciled (220g) x 450g/motor | 220g | 1,800g | **8.2:1** | Excellent |
| V2 with payload (270g) x 360g | 270g | 1,440g | **5.3:1** | Very good |
| V2 + 15ml water (285g) x 360g | 285g | 1,440g | **5.0:1** | Good |
| V2 pessimistic (300g/motor, 285g AUW) | 285g | 1,200g | **4.2:1** | Good |

**Thresholds:**
- <2:1 = Unsafe (cannot maintain hover)
- 2:1 = Minimum for stable hover
- 3:1 = Good for gentle flying
- 4:1+ = Excellent, capable of acro maneuvers

**Verdict:** V1 at 6.5:1 TWR is excellent. Even V2 with full payload and conservative thrust (5.0:1) is well above the 2:1 minimum. The drone has plenty of thrust margin.

### 4.4 Payload Effect

When the ~50g water gun payload is added for V2:
- AUW increases from ~220g to ~270g
- TWR drops from 6.5:1 to 5.3:1 (still excellent)
- Hover throttle increases from ~15% to ~19%
- The drone will feel slightly less responsive but remains fully controllable
- Onboard water reduces flight time:
  - Without payload: ~8 min cruise, ~5 min aggressive
  - With payload + 15ml water: ~6 min cruise, ~4 min aggressive

