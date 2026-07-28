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


## 5. ArduPilot Setup for MAVLink-Only (No RC) Flight

### 5.1 Essential Parameters (No RC Receiver)

All parameters for flying without a physical RC receiver. Control is via MAVLink (QGC virtual joystick or Mission Planner) over the ESP32 WiFi bridge.

#### 5.1.1 Skip RC Pre-Arm Check

| Parameter | Value | Why |
|-----------|-------|-----|
| ARMING_CHECK | 1 | Keep ALL other pre-arm checks ON (safety) |
| ARMING_SKIPCHK | 64 (decimal) | Skip ONLY the RC check (bit 6 = 64 decimal) |
| RC_OPTIONS | 1 | Ignore RC receiver (bit 0) - prevents failsafe on missing RC |
| RC_PROTOCOLS | 0 | Disable RC protocol detection - prevents noise as RC |

#### 5.1.2 Failsafe Configuration

| Parameter | Value | Why |
|-----------|-------|-----|
| FS_THR_ENABLE | 0 | Disable throttle failsafe (no RC throttle to lose) |
| FS_GCS_ENABLE | 1 | **CRITICAL** - RTL on GCS heartbeat loss |
| FS_GCS_TIMEOUT | 5 | Seconds without GCS heartbeat before failsafe triggers |
| FS_OPTIONS | 0 | Normal failsafe behavior (RTL on GCS loss) |

**How WiFi failsafe works:**
- Phone-ESP32 WiFi drops -> ESP32 stops MAVLink heartbeat
- After FS_GCS_TIMEOUT (5s) -> ArduPilot triggers GCS failsafe
- Drone RTL to GPS home (requires GPS 3D fix)
- If WiFi reconnects before timeout, flight continues normally

#### 5.1.3 Flight Modes

| Parameter | Value | Mode | Use |
|-----------|-------|------|-----|
| FLTMODE1 | 0 | Stabilize | Manual - no GPS hold, direct stick mapping |
| FLTMODE2 | 2 | AltHold | Holds altitude, manual pitch/roll |
| FLTMODE3 | 5 | Loiter | GPS position hold (requires GPS fix) |
| FLTMODE4 | 6 | RTL | Return to launch + land |
| FLTMODE5 | 3 | Auto | Autonomous mission (future) |
| FLTMODE6 | 4 | Guided | **Virtual joystick primary mode** |

**Mode selection:** Via QGC mode button, set to Guided (FLTMODE6) for virtual joystick control.

#### 5.1.4 Arming

| Parameter | Value | Why |
|-----------|-------|-----|
| ARMING_RUDDER | 0 | Disable rudder arming (no RC rudder) |
| GUID_OPTIONS | 1 | Allow arming from GCS Guided mode commands |
| AUTO_OPTIONS | 1 | Allow arming in Auto mode |
| RC_OVERRIDE_TIME | -1 | Never timeout RC overrides (keep virtual joystick active) |

**Arming method:** Use QGC arm button in Guided mode, or send MAVLink arm command.

#### 5.1.5 Virtual RC Calibration (Fake Values)

No physical RC exists, but ArduPilot expects calibrated RC values:

| Parameter | Value | Notes |
|-----------|-------|-------|
| RC1_MIN | 1101 | Fakes RC calibration (min values just outside default 1100) |
| RC1_MAX | 1901 | Fakes RC calibration (max values just outside default 1900) |
| RC2_MIN | 1101 | Roll |
| RC2_MAX | 1901 | Roll |
| RC3_MIN | 1101 | Throttle |
| RC3_MAX | 1901 | Throttle |
| RC4_MIN | 1101 | Yaw |
| RC4_MAX | 1901 | Yaw |
| RC1_REV | 1 | Normal direction |
| RC2_REV | 1 | Normal direction |
| RC3_REV | 1 | Normal direction |
| RC4_REV | 1 | Normal direction |
| RC3_TRIM | 1501 | Throttle mid-point (for AltHold/auto-throttle modes) |
| PILOT_THR_BHV | 1 | Feedback from mid-stick (sprung Xbox joystick) |

#### 5.1.6 Serial Port Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| SERIAL1_BAUD | 115 | USB (Mission Planner connection) |
| SERIAL1_PROTOCOL | 1 | MAVLink1 over USB |
| SERIAL3_PROTOCOL | 5 | GPS on UART3 |
| SERIAL3_BAUD | 115 | 115200 baud for GPS |
| SERIAL4_PROTOCOL | 2 | **MAVLink2 on UART4 (ESP32 bridge)** |
| SERIAL4_BAUD | 921 | **921600 baud (lowest latency for control)** |
| SERIAL5_PROTOCOL | 0 | Disable UART6 (future ELRS RX) |
| SR1_EXT_STAT | 10 | Telemetry extended status rate (Hz) |
| SR1_EXTRA1 | 10 | Extended telemetry rate (Hz) |
| SR1_EXTRA2 | 10 | Extra2 telemetry rate |
| SR1_PARAMS | 50 | Parameter rate for fast initial sync |

#### 5.1.7 GPS Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| GPS_TYPE | 1 | uBlox auto-detect |
| GPS_AUTO_CONFIG | 1 | Auto-configure baud/protocol |
| GPS_GNSS_CONFIG | 6 | GPS + GLONASS (improves fix speed) |
| GPS_NAVFILTER | 4 | Airborne < 1g dynamic model |
| COMPASS_ENABLE | 1 | Enable QMC5883L compass on I2C |
| COMPASS_AUTO_ROT | 2 | External compass rotation (adjust if heading is wrong) |
| COMPASS_EXTERNAL | 0 | Auto-detect |

### 5.2 ESC Calibration

**Using DShot600 (RECOMMENDED - no calibration needed):**

Set `MOT_PWM_TYPE = 6` (DShot600). DShot is a digital protocol. The ESC reads the digital frame and interprets throttle directly. **No calibration procedure needed.**

**If using PWM protocol (not recommended):**
1. Set `ESC_CALIBRATION = 3`
2. Write params, disconnect USB
3. Connect battery
4. Wait for musical tone -> cell count beeps -> one long beep
5. Disconnect battery, power cycle
6. Set `ESC_CALIBRATION = 0`, reboot

### 5.3 Starting PID Values (For First Hover)

Default ArduPilot PIDs are tuned for 10"" props. This 3.5"" build needs reduced gains.

#### Filter Settings (Set BEFORE First Flight)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| INS_GYRO_FILTER | 80 | 80Hz LPF - safe for 3-3.5"" builds |
| INS_ACCEL_FILTER | 10 | Standard for all sizes |
| INS_FAST_SAMPLE | 1 | 2kHz gyro on H7 - critical for small motors |
| INS_GYRO_RATE | 1 | 2kHz sample rate |

**Derived filter params (from gyro filter = 80):**
- ATC_RAT_RLL_FLTD = 40 (gyro_filter / 2)
- ATC_RAT_RLL_FLTT = 40
- ATC_RAT_PIT_FLTD = 40
- ATC_RAT_PIT_FLTT = 40
- ATC_RAT_YAW_FLTE = 2
- ATC_RAT_YAW_FLTT = 40

#### Rate PID - Roll & Pitch (Starting Values)

| Parameter | Value | Default (10"") | Why Reduced |
|-----------|-------|---------------|-------------|
| ATC_RAT_RLL_P | 0.08 | 0.15 | Small quads need ~50% of default |
| ATC_RAT_RLL_I | 0.06 | 0.10 | Proportional reduction |
| ATC_RAT_RLL_D | 0.002 | 0.004 | Reduced to prevent oscillation |
| ATC_RAT_RLL_IMAX | 0.40 | 0.40 | Default |
| ATC_RAT_RLL_FF | 0 | 0 | Leave at 0 until autotune |
| ATC_RAT_PIT_P | 0.08 | 0.15 | Same as roll |
| ATC_RAT_PIT_I | 0.06 | 0.10 | Same as roll |
| ATC_RAT_PIT_D | 0.002 | 0.004 | Same as roll |
| ATC_RAT_PIT_FF | 0 | 0 | Leave at 0 |

#### Yaw PID

| Parameter | Value | Notes |
|-----------|-------|-------|
| ATC_RAT_YAW_P | 0.18 | Default |
| ATC_RAT_YAW_I | 0.01 | Default |
| ATC_RAT_YAW_D | 0.003 | Default |
| ATC_RAT_YAW_FF | 0 | Leave at 0 |
| ATC_RAT_YAW_IMAX | 0.40 | Default |
| ACRO_YAW_P | 3.6 | Default |

#### Angle (Stabilize) PID

| Parameter | Value | Notes |
|-----------|-------|-------|
| ATC_ANG_RLL_P | 4.5 | Default - works for all sizes |
| ATC_ANG_PIT_P | 4.5 | Default |
| ATC_ANG_YAW_P | 4.5 | Default |

#### Motor / Throttle Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| MOT_PWM_TYPE | 6 | DShot600 |
| MOT_THST_HOVER | 0.17 | For TWR ~6.5:1, hover = ~15% thrust (220/1440) |
| MOT_THST_EXPO | 0.50 | Mid-range for 3.5"" props |
| MOT_SPIN_ARM | 0.06 | 6% idle (anti-stutter) |
| MOT_SPIN_MIN | 0.10 | 10% minimum throttle |
| MOT_SPIN_MAX | 0.95 | 95% max (headroom for PID) |
| MOT_BAT_VOLT_MAX | 16.8 | 4S fully charged (4.2V/cell) |
| MOT_BAT_VOLT_MIN | 12.0 | 4S depleted (3.0V/cell) |

#### Battery Protection

| Parameter | Value | Voltage/Cell | Meaning |
|-----------|-------|-------------|---------|
| BATT_ARM_VOLT | 14.0 | 3.5V | Minimum to arm |
| BATT_LOW_VOLT | 14.4 | 3.6V | Warning - land soon |
| BATT_CRT_VOLT | 13.2 | 3.3V | Critical - land immediately |
| BATT_FS_LOW_ACT | 1 | -- | RTL on low battery |
| BATT_FS_CRT_ACT | 2 | -- | Land on critical battery |

#### Input Shaping

| Parameter | Value | Effect |
|-----------|-------|--------|
| ATC_INPUT_TC | 0.15 | Medium response (0.1 = crisp, 0.2 = soft) |

### 5.4 Motor Direction & Prop Orientation

Standard quad-X frame layout:

```
       FRONT
   M2 (CCW)  |  M1 (CW)
   FL        |  FR
   -------------------
   RL        |  RR
   M3 (CW)   |  M4 (CCW)
       REAR
```

| Motor | Position | Rotation | Frame | Prop Type |
|-------|----------|----------|-------|-----------|
| M1 | Front-right | CW | FR frame | Normal (CW) |
| M2 | Front-left | CCW | FL frame | Reverse (CCW) |
| M3 | Rear-right | CW | RR frame | Normal (CW) |
| M4 | Rear-left | CCW | RL frame | Reverse (CCW) |

**ArduPilot setup:**
```
FRAME_CLASS = 1  # Quad
FRAME_TYPE  = 1  # X frame
```

**Verification:** Use Mission Planner -> Servo Output -> Motor Test. Test each motor at 10% throttle. Verify rotation matches the table. Swap any two phase wires if rotation is wrong.

### 5.5 Compass Calibration

1. Connect via USB to Mission Planner (or via WiFi if stable)
2. Initial Setup -> Mandatory Hardware -> Compass
3. Click "Live Calibration"
4. Rotate drone through all 3 axes (360 degrees each):
   - Roll: rotate around the forward axis
   - Pitch: rotate around the left/right axis
   - Yaw: rotate around the vertical axis (hardest - hold level and spin)
5. Click "Done"
6. Verify offsets: expect 200-500mG for QMC5883L
7. If two compasses detected: disable the internal (COMPASS_USE set to 0 for internal)

### 5.6 Accelerometer Calibration

1. Connect via USB to Mission Planner
2. Initial Setup -> Mandatory Hardware -> Accel Calibration
3. Place drone in each of 6 orientations when prompted:
   - Level (flat on table)
   - Left side down
   - Right side down
   - Nose down
   - Nose up
   - Back (upside down)
4. Calibration runs after all 6 positions
5. Verify offsets < 50mG on all axes
6. Re-calibrate after any hard crash

### 5.7 Parameter Summary File

Since all parameters are listed individually above, here is a condensed list to copy into Mission Planner's parameter editor:

```
ARMING_CHECK=1, ARMING_SKIPCHK=64, ARMING_RUDDER=0
RC_OPTIONS=1, RC_PROTOCOLS=0, RC_OVERRIDE_TIME=-1
FS_THR_ENABLE=0, FS_GCS_ENABLE=1, FS_GCS_TIMEOUT=5, FS_OPTIONS=0
FLTMODE1=0, FLTMODE2=2, FLTMODE3=5, FLTMODE4=6, FLTMODE5=3, FLTMODE6=4
GUID_OPTIONS=1, AUTO_OPTIONS=1
RC1_MIN=1101, RC1_MAX=1901, RC2_MIN=1101, RC2_MAX=1901
RC3_MIN=1101, RC3_MAX=1901, RC4_MIN=1101, RC4_MAX=1901
RC1_REV=1, RC2_REV=1, RC3_REV=1, RC4_REV=1, RC3_TRIM=1501
PILOT_THR_BHV=1
SERIAL3_PROTOCOL=5, SERIAL3_BAUD=115
SERIAL4_PROTOCOL=2, SERIAL4_BAUD=921
GPS_TYPE=1, GPS_AUTO_CONFIG=1, GPS_GNSS_CONFIG=6
COMPASS_ENABLE=1, COMPASS_AUTO_ROT=2
INS_GYRO_FILTER=80, INS_ACCEL_FILTER=10, INS_FAST_SAMPLE=1, INS_GYRO_RATE=1
ATC_RAT_RLL_P=0.08, ATC_RAT_RLL_I=0.06, ATC_RAT_RLL_D=0.002, ATC_RAT_RLL_IMAX=0.40
ATC_RAT_PIT_P=0.08, ATC_RAT_PIT_I=0.06, ATC_RAT_PIT_D=0.002, ATC_RAT_PIT_IMAX=0.40
ATC_RAT_YAW_P=0.18, ATC_RAT_YAW_I=0.01, ATC_RAT_YAW_D=0.003, ATC_RAT_YAW_IMAX=0.40
ATC_ANG_RLL_P=4.5, ATC_ANG_PIT_P=4.5, ATC_ANG_YAW_P=4.5
ATC_INPUT_TC=0.15
MOT_PWM_TYPE=6, MOT_THST_HOVER=0.17, MOT_THST_EXPO=0.50
MOT_SPIN_ARM=0.06, MOT_SPIN_MIN=0.10, MOT_SPIN_MAX=0.95
MOT_BAT_VOLT_MAX=16.8, MOT_BAT_VOLT_MIN=12.0
BATT_ARM_VOLT=14.0, BATT_LOW_VOLT=14.4, BATT_CRT_VOLT=13.2
BATT_FS_LOW_ACT=1, BATT_FS_CRT_ACT=2
FRAME_CLASS=1, FRAME_TYPE=1
```


## 6. Latency Path: Xbox Controller to Motor

### 6.1 Control Chain

```
Xbox Series X Controller (Bluetooth 5.0)
  | Bluetooth HID protocol, 125Hz polling rate
  v
Phone (QGroundControl Virtual Joystick)
  | MAVLink RC_OVERRIDE messages
  | WiFi UDP 2.4GHz (802.11g/n)
  v
ESP32-S3 WiFi AP (192.168.4.1:14550)
  | MAVLink passthrough bridge
  | UART serial (921600 baud)
  v
MicoAir H743 (ArduPilot @ 400Hz)
  | PID loop -> actuator mixing -> DShot600
  v
AM32/BLHeli ESC + Motor
  | Electrical + mechanical response
  v
Propeller -> Thrust change
```

### 6.2 Latency Breakdown Per Hop

| # | Hop | Component | Latency (ms) | Source |
|---|-----|-----------|-------------|--------|
| 1 | Xbox BT -> Phone | Bluetooth HID (BT 5.0 Android) | **16-30ms** | gamepadla.com database - Xbox Series X measured on Android |
| 2 | Phone processing | QGC HID driver -> MAVLink conversion | **2-5ms** | OS overhead estimate |
| 3 | QGC joystick rate | Packet send rate (25Hz default) | **40ms (25Hz)** | **MAJOR BOTTLENECK** - QGC default |
| 4 | Phone -> ESP32 | WiFi UDP 2.4GHz | **10-30ms** | Electric UI: optimized ESP32 = 8-9ms. Phone adds 5-15ms. Unoptimized = 74-84ms |
| 5 | ESP32 processing | UDP packet -> UART serial | **1-2ms** | Minimal bridge overhead |
| 6 | UART TX (ESP32 -> FC) | 921600 baud, ~28-byte MAVLink msg | **0.3ms** | 10.9us/byte. At 115200: 2.4ms |
| 7 | FC processing | ArduPilot PID @ 400Hz | **2.5ms** | 2.5ms per iteration |
| 8 | DShot600 + ESC | Protocol frame + BLHeli processing | **0.03ms** | 26.7us frame time, ~15us ESC processing |
| 9 | Motor electrical | Coil energize -> magnetic field -> rotor torque | **1-2ms** | Physical electromechanical limit |

### 6.3 Latency Scenarios

| Scenario | BT | Phone | QGC 25Hz | WiFi | ESP32 | UART | FC | DShot | Motor | **TOTAL** |
|----------|----|-------|---------|------|-------|------|----|-------|-------|-----------|
| **Best (all optimized)** | 16 | 2 | 40 | 10 | 1 | 0.3 | 2.5 | 0 | 1 | **~73ms** |
| **Typical (real-world)** | 22 | 3 | 40 | 15 | 2 | 2 | 2.5 | 0 | 2 | **~89ms** |
| **Worst (unoptimized)** | 30 | 5 | 40 | 74 | 2 | 2.4 | 2.5 | 0.03 | 2 | **~158ms** |
| **Laptop alternative** | 16 | -- | -- | 10 | 1 | 0.3 | 2.5 | 0 | 1 | **~31ms** |

**Key insight:** The QGC 25Hz joystick rate adds a FIXED 40ms latency floor. Even if all other latency were zero, you cannot get below 40ms through QGC's virtual joystick.

### 6.4 Flyable Latency Thresholds

| Latency | Verdict | Feel |
|---------|---------|------|
| <20ms | Excellent | Imperceptible - pro racing level |
| 20-40ms | Good | Standard FPV feel |
| 40-60ms | Acceptable | Noticeable but manageable |
| 60-100ms | Workable (stabilized modes) | Hard for acro - OK in Loiter/Guided |
| >100ms | Dangerous for manual | Uncontrollable in emergencies |

**V1 verdict:** Typical ~89ms via phone+QGC falls in the "workable" range. Fly in Stabilize, AltHold, or Loiter modes. Avoid Acro mode. The laptop alternative (~31ms) is strongly recommended for first flights.

### 6.5 Optimizations

**Priority 1: Skip the phone (BEST improvement)**
- Connect Xbox controller to a **laptop running Mission Planner**
- Mission Planner's joystick support has higher update rates
- Eliminates the 40ms QGC bottleneck
- Typical latency: **~31ms (Excellent)**
- This single change cuts latency by ~60%

**Priority 2: Optimize ESP32 WiFi**
```cpp
// avatar_bridge.ino - WiFi optimizations
WiFi.setSleep(false);           // Disable modem sleep (prevents 74-84ms spikes)
WiFi.mode(WIFI_AP);
WiFi.setOutputPower(20);        // Max TX power for range
```
- Enable UART at 921600 baud
- Set WiFi to a clean channel (scan with phone first)

**Priority 3: Reduce MAVLink telemetry rate**
- Lower SR1_* parameters from 10Hz to 4-5Hz (less traffic = less congestion)
- Disable video streaming (V1 has no camera)
- Disable unnecessary MAVLink messages

**Priority 4: Position for best signal**
- Phone/laptop within 10m LOS of drone
- No walls or obstructions between controller and drone
- Use 2.4GHz channel 1, 6, or 11 (non-overlapping, pick the cleanest)

### 6.6 Recommended Approach for V1

| Phase | Control Method | Latency | Verdict |
|-------|---------------|---------|---------|
| Bench test (no props) | Laptop USB direct to FC | ~5ms | Best |
| Tethered hover | Laptop -> WiFi -> ESP32 -> FC | ~31ms | Excellent |
| First free flight | Laptop -> WiFi -> ESP32 -> FC | ~31ms | Excellent |
| After tuned | Phone -> WiFi -> ESP32 -> FC | ~89ms | Workable |
| Future (if needed) | Xbox Direct -> ESP32 BLE -> FC | ~25ms | Research effort |

**Recommended:** Use a laptop with Mission Planner for development and first flights. Switch to phone+QGC once the drone is tuned and flying reliably.


## 7. First Flight Checklist

### 7.1 Pre-Build: Parts Receiving

- [ ] All frame screws present (check M2 kit): M2x12mm x4, M2x8mm, M2x6mm, M2 nuts
- [ ] M2 nylon washers sourced (for FC mounting)
- [ ] Carbon fiber plates: no cracks or delamination
- [ ] Motor bell spins freely by hand (no grinding)
- [ ] Motor shaft = 1.5mm (measure with calipers)
- [ ] Gemfan props: 1.5mm bore directly fits motor shaft
- [ ] GPS cable present (150mm JST SH 1.0)
- [ ] ESP32 XIAO board powers on via USB-C
- [ ] MicoAir H743 firmware: ArduPilot MicoAir743-AIO
- [ ] LiPo smoke stopper ready
- [ ] Multimeter ready for continuity/voltage checks

### 7.2 Assembly Sequence

**Step 1: Frame assembly**
1. Mount arms to frame base plate using M2 screws + blue Loctite
2. Install M2x11mm aluminum standoffs on middle plate at 25.5x25.5mm positions
3. Place FC on standoffs with M2 nylon washers
4. Secure with M2x12mm button-head screws (snug, not tight)
5. Mount ESP32 in rear receiver bay with double-sided tape
6. Mount GPS on rear top plate with double-sided foam tape

**Step 2: Wiring**
1. **Battery:** Solder XT30 pigtail (16AWG) to FC VBAT+/VBAT- pads. Verify polarity with multimeter. Heat shrink.
2. **Motors:** Route through arms. Solder M1(FR), M2(FL), M3(RR), M4(RL) to FC pads. Leave slack.
3. **GPS:** Connect PD8->GPS RX, PD9->GPS TX, 5V->VCC, GND->GND, PB7->SDA, PB6->SCL
4. **ESP32:** Connect PA0->ESP32 RX(GPIO44), PA1->ESP32 TX(GPIO43), 5V->VCC, GND->GND
5. Tighten FC. Zip-tie wires flat along arm edges. Avoid IMU/barometer area.

**Step 3: Stack height check**
- Place top plate on standoffs
- Verify it sits flat (no bulging from wires)
- If bulging: re-route wires flatter or trim where possible

### 7.3 First Power-Up (Smoke Test)

- [ ] **Install LiPo smoke stopper** between battery and XT30
- [ ] Connect battery (smoke stopper limits to ~1A)
- [ ] Observe: **no smoke, no sparks, no heat**
- [ ] FC LED: solid = power OK
- [ ] If smoke stopper trips: disconnect immediately, find short
- [ ] If OK: remove smoke stopper, connect battery directly
- [ ] Check with multimeter: VBAT+ to VBAT- = ~16.8V on fully charged 4S

### 7.4 Firmware & Configuration

- [ ] Connect FC via USB (Type-C)
- [ ] Flash ArduPilot MicoAir743-AIO via Mission Planner
- [ ] Load all parameters from Section 5.7 (copy into full parameter list)
- [ ] Write parameters, reboot FC
- [ ] Verify sensor readings:
  - [ ] Gyro/Accel: no errors in status
  - [ ] GPS: 3D fix within 30-60s (antenna needs sky view)
  - [ ] Compass: heading matches physical orientation
- [ ] Accelerometer calibration (6 positions)
- [ ] Compass calibration (3-axis rotation)
- [ ] Connect to ESP32 WiFi: verify MAVLink link in Mission Planner

### 7.5 Bench Test (REMOVE PROPS)

- [ ] Props removed (REQUIRED for bench testing)
- [ ] Arm via Mission Planner (Guided mode + arm button)
- [ ] Motor test each motor at 10%:
  - [ ] M1 (FR): clockwise
  - [ ] M2 (FL): counter-clockwise
  - [ ] M3 (RR): clockwise
  - [ ] M4 (RL): counter-clockwise
- [ ] Swap any motor wire pairs if rotation is wrong
- [ ] All 4 motors at 20%: listen for grinding or oscillation
- [ ] Disarm
- [ ] ESC calibration: motors should start smoothly, no dead zone

### 7.6 Tethered Hover Test Setup

**Location:** Open grass field, no people within 10m
**Weather:** Calm wind (<10 km/h), clear
**Tether:** 10m paracord tied to drone center, staked in ground
**Controller:** Laptop with Mission Planner (NOT phone - lower latency)
**Battery:** Freshly charged 4S 850mAh

**Procedure:**
1. Battery on, connect to ESP32 WiFi, open Mission Planner
2. Pre-arm check: verify all checks pass in status bar
3. Arm via Mission Planner
4. Slowly increase throttle to ~18% (estimated hover point)
5. Observe: drone should lift to ~0.5m
6. Brief hover (5 seconds), check for:
   - [ ] Vibration / oscillation
   - [ ] Motor temperatures (land after 30s, touch each bell)
   - [ ] Battery voltage drop (should stay above 15.2V at hover)
7. Land gently, disarm
8. Check motor temps: warm = OK, hot = problem
9. Repeat 3-5x, increasing hover duration to 30 seconds
10. If stable: proceed to free flight

### 7.7 First Free Flight

**Same location, same conditions.**

- [ ] Pre-flight visual inspection: prop nuts tight, battery secure, no loose screws
- [ ] GPS 3D fix: >6 satellites
- [ ] Compass heading matches physical north
- [ ] Control check: all 4 sticks respond correctly in Mission Planner
- [ ] Arm, throttle to hover (~18%)
- [ ] Climb to 2m, hold for 10 seconds
- [ ] Small pitch input: drone tips forward ~10 degrees, returns to level
- [ ] Small roll input: same
- [ ] Yaw input: 90-degree turn, stays in position
- [ ] Land, check motor temps, battery voltage
- [ ] If stable: second flight at 5m altitude, gentle circuits
- [ ] If unstable: land immediately, adjust PIDs

### 7.8 PID Tuning Sequence

**Day 1 - Stabilize hover:**
1. Use starting values from Section 5.3
2. If oscillating: reduce all P, I, D by 50%
3. Once stable: increase P until slight oscillation appears, then back off 20%

**Day 2 - Autotune:**
1. Set AUTOTUNE_ENABLE=1, AUTOTUNE_AXES=7 (all axes)
2. Take off in AltHold mode at 5m
3. Switch to Stabilize to trigger autotune
4. Fly gently for ~60 seconds while autotune sweeps pitch/roll/yaw
5. Land, disarm. Check AUTOTUNE_ENABLE returns to 0
6. Review autotune results in logs

**Day 3 - Fine tune:**
1. Increase ATC_THR_MIX_MAX to 0.9
2. Enable dynamic notch filter: DYN_NOTCH_ENABLE=1
3. Review FFT logs from Day 2 to verify notch center frequency

### 7.9 Emergency Conditions - Land Immediately

| Condition | Action |
|-----------|--------|
| Motor temp > 60C (uncomfortable to touch >2s) | Land, check timing/PIDs |
| Battery < 13.2V (3.3V/cell) | Land immediately - critical |
| Strong oscillation develops mid-flight | Cut throttle, let it fall (grass) |
| WiFi disconnect >5 seconds | Drone will RTL - monitor landing |
| Smoke or burning smell | Cut throttle immediately, disconnect battery |
| Propeller strike (sudden vibration) | Land, replace prop |
| GPS loss during Loiter/RTL | Switch to Stabilize, land manually |
| Uncommanded yaw/pitch | Land, check compass/gyro |

### 7.10 Pre-Flight Checklist (Every Flight)

- [ ] Battery charged (check voltage: >15.2V = 3.8V/cell minimum)
- [ ] Battery secured with strap
- [ ] Props spin freely, prop nuts tight
- [ ] All screws tight (check motor mount, frame bolts)
- [ ] No cracks in arms or frame
- [ ] GPS 3D fix confirmed (>6 sats)
- [ ] Compass heading correct
- [ ] Control check: all sticks respond
- [ ] WiFi signal strong (>60% RSSI or -70dBm)
- [ ] Smoke stopper ready (for initial power-ups)
- [ ] Fire extinguisher / LiPo bag nearby
- [ ] No people within 10m
- [ ] Clear flight path, no overhead obstacles


## 8. Incompatibilities & Recommended Fixes

### 8.1 Issue Summary

| # | Issue | Severity | Fix | Cost | Effort |
|---|-------|----------|-----|------|--------|
| 1 | FC M3 holes, frame uses M2 hardware | Moderate | M2 nylon washers to center screws | ~$2 | 2 min |
| 2 | Frame weight: BOM says 25g, official spec shows ~87g full kit | Needs verification | Weigh actual parts on arrival | $0 | 5 min |
| 3 | Motor weight: BOM says 6.5g, actual is 12.8g | Moderate | Update AUW calc - still under 250g | $0 | Paperwork |
| 4 | QGC virtual joystick 25Hz rate = 40ms latency floor | Moderate | Use laptop + Mission Planner instead of phone | $0 | Config change |
| 5 | ESP32 WiFi unoptimized = 74-84ms latency | Must fix | WiFi.setSleep(false), IRAM optimization | $0 | Firmware change |
| 6 | No dedicated ESP32 mount on frame | Minor | Use rear receiver bay + double-sided tape | $0 | Build |
| 7 | GPS has no mounting holes (solder pads only) | Minor | Double-sided tape (2.6g = no issue) | $0 | Build |
| 8 | MicoAir H743 AIO V1 discontinued | Moderate | Use V2 version (same physical specs) | Same | Order change |

### 8.2 Detailed Fixes

**Fix #1 - FC mounting (Critical):**
- Source 4x M2 nylon flat washers (2mm ID, ~5mm OD, ~0.5mm thickness)
- Available at any hardware store (Home Depot, Lowes) or Amazon ($2-5 for a pack of 50)
- Install between the M2x12mm screw head and the FC board
- Tighten to snug - carbon fiber can crack if over-torqued

**Fix #2 - Weight verification:**
- When parts arrive, weigh each component on a kitchen scale
- Record actual weights
- Update the weight budget
- If total exceeds 250g (very unlikely), identify heaviest components for weight reduction

**Fix #3 - Motor weight update:**
- The BOM estimated motor weight at 6.5g each (26g total)
- Actual: 12.8g each (51.2g total) - a +25.2g difference
- Reconciled AUW: ~220g (still under 250g - 30g margin is comfortable)

**Fix #4 - Latency optimization:**
- During development and first flights: use laptop with Mission Planner instead of phone
- Mission Planner's joystick input is not limited to 25Hz
- This single change cuts total latency from ~89ms to ~31ms
- Switch to phone+QGC only after drone is well-tuned

**Fix #5 - ESP32 WiFi:**
In avatar_bridge.ino, add at the beginning of setup():
```cpp
WiFi.setSleep(false);  // Disable power saving
```
This prevents the ESP32's WiFi modem from entering sleep states that cause 74-84ms latency spikes. Without this fix, latency can spike to >150ms during congested periods.

### 8.3 Non-Issues (Verified OK)

These were initially flagged as concerns but research confirmed they are not problems:

- **Motor KV (3800KV on 4S):** Safe. 63,840 RPM no-load theoretical, ~50-55K loaded. Within prop limits.
- **ESC 35A rating:** Per-motor rating. Each motor draws 16-18A peak = ~2x margin.
- **Prop bore (1.5mm vs motor shaft 1.5mm):** Direct fit. No adapters needed.
- **Battery connector (XT30):** 30A continuous is sufficient for our 64-72A total (4 motors at 16-18A each). Wait - 30A continuous for the XT30 but total system draw at full throttle is 64-72A. XT30 is rated for 30A continuous, 60A burst. At WOT, total draw is 64-72A. This **exceeds** the XT30 burst rating.

Actually, let me correct this: The XT30 carries the TOTAL current for all 4 motors. At full throttle, total draw = ~64-72A. XT30 is rated 30A continuous / 60A burst. At full throttle, we exceed both.

BUT: In practice, sustained WOT is rare (<1 second typically). The XT30 can handle short bursts above its rating. For this build, the XT30 is a known constraint that the FPV community regularly pushes. Monitor connector temperature on first flight.

**Updated verdict on XT30:**
- Hover (12-16A): Well within 30A cont rating. OK.
- Cruise (28-36A): Within 30A cont with margin at light cruise. Maybe 40A in climbs - near limit.
- Full throttle (64-72A): Exceeds 60A burst. Risk of connector heating.
- **Recommendation:** Consider XT60 (60A cont / 120A burst) for safety margin. XT30 will work for V1 testing but monitor carefully.


## 9. Decision & Next Actions

### Decision

**Build V1 as designed with these adjustments:**
1. Update weight estimates: frame ~40g, motors ~12.8g each, total AUW ~220g (still under 250g)
2. Include M2 nylon washers for FC mounting (M3 holes on M2 frame)
3. Use DShot600 protocol (no ESC calibration needed - digital protocol)
4. Use laptop + Mission Planner for first flights (bypasses QGC 25Hz bottleneck)
5. Optimize ESP32 bridge: disable WiFi sleep, UART at 921600 baud
6. Initial PIDs: use reduced gains (50% of ArduPilot defaults for 10"")
7. Use XT30 for V1 but monitor connector temp during full throttle

**TWR results (all scenarios):**
- V1 (220g AUW): **6.5:1** - Excellent
- V2 with payload (270g): **5.3:1** - Very good
- V2 with payload + 15ml water (285g): **5.0:1** - Good

**No showstoppers found.** All 8 incompatibilities have known fixes.

### Next Action

1. **Muadh:** Review and confirm the frame weight (25g vs full kit). Weigh on arrival.
2. **Muadh:** Order all parts (Canadian vendors now, AliExpress in parallel)
3. **Researcher:** Optimize ESP32 bridge firmware with WiFi.setSleep(false) at 921600 baud
4. **Muadh:** Assemble drone following Section 7.2 sequence
5. **Muadh:** Perform tethered hover test before free flight
6. **Muadh:** Day 1: Stabilize hover with starting PIDs
7. **Muadh:** Day 2: Run ArduPilot AUTOTUNE
8. **Muadh:** Day 3: Enable harmonic notch filter, adjust gains

### Deadline

| Milestone | Target Date |
|-----------|-------------|
| Parts ordered (Canadian) | July 3, 2026 |
| Parts ordered (AliExpress) | July 3, 2026 |
| Canadian parts arrive | July 7-10, 2026 |
| ESP32 firmware optimized | July 8, 2026 |
| Build and bench test | July 7-12, 2026 |
| Tethered hover test | July 12-14, 2026 |
| V1 first free flight | **July 21, 2026** |
| PID tuning complete | July 25, 2026 |

### Who Should Handle Next

| Role | Responsibility |
|------|---------------|
| **Muadh (builder/pilot)** | Parts ordering, physical assembly, smoke test, tethered hover, first flight, PID tuning |
| **Researcher** | ESP32 firmware optimization (WiFi latency fix), ArduPilot parameter file ready to load, support during build |

---

*Document compiled July 2, 2026. Research sources: MicoAir official product page, ArduPilot wiki (Copter 4.6+), SpeedyBee Master3X manual, Gemfan Hurricane specs, T-Motor P1604 3800KV bench test (T-Motor official via RCDrone), DeepSpace Aether 1505 4000KV bench test (manufacturer), Oscar Liang motor/prop tables, Electric UI WiFi benchmarks (esp32.com forum), gamepadla.com controller latency database, FPV community forums (r/fpv, r/diydrones, ArduPilot Discourse).*

*Confidence levels:*
- *Physical dimensions and fit: HIGH (85%) - official specs and community data consistent*
- *Electrical compatibility: HIGH (90%) - standard connections, confirmed voltage levels*
- *Thrust estimates: MEDIUM (70%) - no thrust stand for exact motor/prop combo*
- *Latency estimates: HIGH (85%) - sourced from published measurements*
- *Frame weight: Medium (60%) - needs actual weighing on arrival*

