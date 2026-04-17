# Flight Test Engineering: Calibration Procedures

## Document Control
- **Version**: 1.0
- **Date**: 2026-04-09
- **Status**: Draft for Review
- **Classification**: Engineering Technical Documentation

---

## Table of Contents
1. [PX4 Sensor Calibration](#1-px4-sensor-calibration)
2. [Companion Computer Setup](#2-companion-computer-setup)
3. [Operational Calibrations](#3-operational-calibrations)
4. [Validation Flights](#4-validation-flights)
5. [Pre-Flight Checklist Summary](#5-pre-flight-checklist-summary)

---

## 1. PX4 Sensor Calibration

### 1.1 Accelerometer (6-Position Calibration)

**Purpose**: Establish accurate orientation reference and compensate for IMU mounting offsets.

**Prerequisites**:
- [ ] Aircraft fully assembled with all payload
- [ ] Battery installed and charged (>50%)
- [ ] QGroundControl connected via USB or telemetry
- [ ] Aircraft placed on level, stable surface

**Calibration Sequence**:

| Step | Orientation | Axis Facing Up | Hold Time | Notes |
|------|-------------|----------------|-----------|-------|
| 1 | Level | Z+ (nose level, upright) | 3 seconds | Verify level with bubble |
| 2 | Left side down | Y- (roll -90) | 3 seconds | Use consistent reference |
| 3 | Right side down | Y+ (roll +90) | 3 seconds | Mirror of step 2 |
| 4 | Nose up | X+ (pitch +90) | 3 seconds | Tail on ground |
| 5 | Nose down | X- (pitch -90) | 3 seconds | Nose on ground |
| 6 | Inverted | Z- (upside down) | 3 seconds | Use caution with props |

**QGroundControl Procedure**:
```
Vehicle Setup → Sensors → Accelerometer → Start
```

**Verification Criteria**:
- [ ] Calibration completes without timeout errors
- [ ] Offsets < 0.5 m/s on all axes post-calibration
- [ ] Check `SENS_BOARD_X_OFF`, `SENS_BOARD_Y_OFF`, `SENS_BOARD_Z_OFF` in parameter list

**Troubleshooting**:
| Symptom | Cause | Solution |
|---------|-------|----------|
| Timeout on position | Movement during calibration | Hold perfectly still, use stand |
| Large offsets | IMU vibration isolation issue | Check dampening mounts |
| Inconsistent results | Magnetic interference | Move away from metal structures |

---

### 1.2 Gyroscope Calibration

**Purpose**: Establish zero-rate offset for angular velocity measurements.

**Prerequisites**:
- [ ] Aircraft stationary on level surface
- [ ] No vibration sources nearby
- [ ] Motors disarmed

**Procedure**:
1. Navigate to: `Vehicle Setup → Sensors → Gyroscope`
2. Click "Calibrate"
3. Keep aircraft completely still for 10 seconds
4. Wait for completion tone/notification

**Verification**:
- [ ] Check gyro values in QGC analyze widget (should read ~0 deg/s when stationary)
- [ ] Parameter `CAL_GYRO0_ID` shows valid device ID
- [ ] No temperature warnings during calibration

**Post-Calibration Check**:
```
Parameter: IMU_GYRO_CUTOFF (default 30 Hz, adjust for vibration profile)
```

---

### 1.3 Magnetometer Calibration

**Purpose**: Compensate for hard/soft iron distortions and establish magnetic north reference.

**Critical**: Perform away from metal structures, vehicles, or reinforced concrete.

**Minimum Distance Requirements**:
- Vehicles: 30 meters
- Buildings: 15 meters
- Power lines: 50 meters
- Buried metal: Verify with compass app

**3-Axis Calibration Pattern**:

| Step | Movement Pattern | Duration |
|------|----------------|----------|
| 1 | Continuous slow yaw (360°) | 15 seconds |
| 2 | Nose up, continuous yaw | 15 seconds |
| 3 | Nose down, continuous yaw | 15 seconds |
| 4 | Left side down, continuous yaw | 15 seconds |
| 5 | Right side down, continuous yaw | 15 seconds |
| 6 | Inverted, continuous yaw | 15 seconds |

**QGroundControl Procedure**:
```
Vehicle Setup → Sensors → Magnetometer → Start
```

**Interference Checklist**:
- [ ] Remove all metallic objects from pockets
- [ ] No watches, phones, or tools within 2 meters
- [ ] Verify with `compassmot` equivalent if available

**Parameter Verification**:
```
CAL_MAG0_ID    - Device ID (should be non-zero)
CAL_MAG0_ROT   - Rotation relative to autopilot
CAL_MAG0_XOFF  - X offset (should be < 500)
CAL_MAG0_YOFF  - Y offset (should be < 500)
CAL_MAG0_ZOFF  - Z offset (should be < 500)
CAL_MAG0_XSCALE - X scale (should be ~1.0)
CAL_MAG0_YSCALE - Y scale (should be ~1.0)
CAL_MAG0_ZSCALE - Z scale (should be ~1.0)
```

**Post-Calibration Validation**:
1. Power cycle aircraft
2. Check compass heading matches known reference
3. Verify heading stability during 360° slow rotation

---

### 1.4 Airspeed Sensor Calibration (if applicable)

**Purpose**: Establish zero-airspeed reference and compensate for installation effects.

**Prerequisites**:
- [ ] Pitot tube installed with clear line of sight
- [ ] Tubing connected with no kinks or leaks
- [ ] No wind or prop wash during calibration

**Procedure**:
1. Cover pitot tube tip with finger (do not block static ports)
2. Navigate to: `Vehicle Setup → Sensors → Airspeed`
3. Click "Calibrate"
4. Wait for 10-second calibration sequence
5. Uncover pitot when prompted

**Verification**:
- [ ] Pre-flight: 0 m/s reading with aircraft stationary
- [ ] Compare to handheld anemometer if available
- [ ] Check `ASPD_SCALE` parameter is within 1.0 ± 0.2

**Tubing Check**:
```
Pressure Test: Block pitot, apply gentle pressure, verify sensor responds
Leak Test: Pressurize, verify reading holds for 5+ seconds
```

---

### 1.5 RC Transmitter Calibration

**Purpose**: Map transmitter channel ranges to PX4 control inputs.

**Prerequisites**:
- [ ] Transmitter bound to receiver
- [ ] Receiver connected to autopilot
- [ ] All switches in known positions

**Channel Mapping Standard**:

| Channel | Function | Direction | Center | Min | Max |
|---------|----------|-----------|--------|-----|-----|
| 1 | Roll | Right = positive | 1500 | 1000 | 2000 |
| 2 | Pitch | Back = positive | 1500 | 1000 | 2000 |
| 3 | Throttle | Up = positive | ~1100 | 1000 | 2000 |
| 4 | Yaw | Right = positive | 1500 | 1000 | 2000 |
| 5 | Mode switch | Position-based | - | - | - |
| 6 | Aux/Arm | As configured | - | - | - |

**QGroundControl Procedure**:
```
Vehicle Setup → Radio → Calibrate
```

**Stick Calibration Sequence**:
1. Center all sticks and throttle low
2. Click "Next" when prompted for each axis:
   - Throttle minimum → maximum → center
   - Yaw left → right → center
   - Pitch forward → back → center
   - Roll left → right → center
3. Configure all switches through their full range

**Verification**:
- [ ] All channels respond in Radio tab
- [ ] Center positions read 1500 ± 50
- [ ] Endpoints read 1000/2000 ± 80
- [ ] No channel jitter (>10 counts variation)

**Failsafe Configuration**:
```
Parameter: RC_MAP_FAILSAFE - Channel for failsafe trigger
Parameter: RC_FAILS_THR - Threshold for failsafe detection
Test: Turn off TX, verify RTL/land mode engages
```

---

## 2. Companion Computer Setup

### 2.1 Raspberry Pi UART Configuration

**Purpose**: Establish reliable MAVLink communication between RPi and PX4 autopilot.

**Hardware Connections**:
```
RPi GPIO 14 (TX)  → Autopilot RX (Telem 2)
RPi GPIO 15 (RX)  → Autopilot TX (Telem 2)
RPi GND           → Autopilot GND
RPi 5V (optional) → Power if needed
```

**Software Configuration**:

**Step 1: Disable Serial Console**
```bash
sudo raspi-config
# Interface Options → Serial Port → No console, Yes to hardware
```

**Step 2: Configure UART Parameters**
```bash
# Edit /boot/config.txt
dtoverlay=uart0-pi5  # For Pi 5
dtoverlay=uart0      # For Pi 4/3
enable_uart=1
```

**Step 3: Verify UART Device**
```bash
ls -la /dev/ttyAMA0  # Primary UART
ls -la /dev/serial0  # Alias
```

**Step 4: MAVLink Router Setup**
```bash
sudo apt install mavlink-router
# Edit /etc/mavlink-router/main.conf

[UartEndpoint px4]
Device = /dev/ttyAMA0
Baud = 921600

[UdpEndpoint gcs]
Mode = Normal
Address = 192.168.1.100
Port = 14550
```

**PX4 Configuration**:
```
Parameter: MAV_1_CONFIG = TELEM 2
Parameter: MAV_1_MODE = Onboard
Parameter: SER_TEL2_BAUD = 921600
```

**Verification Checklist**:
- [ ] `mavlink status` shows active streams
- [ ] Heartbeat messages received at 1 Hz
- [ ] Command-long messages successfully round-trip
- [ ] No CRC errors or dropped packets

---

### 2.2 Camera Intrinsics Calibration

**Purpose**: Establish accurate lens distortion model and focal length for computer vision.

**Calibration Pattern**: ChArUco board or checkerboard (recommended: 9x6 squares, 20mm spacing)

**Capture Requirements**:
- Minimum 50 images
- Cover all image regions
- Vary distance: 0.5m to 3.0m
- Vary angle: 0° to 60° from normal
- Vary roll/pitch orientations

**Procedure (OpenCV)**:
```python
# Example calibration script
import cv2
import numpy as np

# Calibration flags
flags = cv2.CALIB_RATIONAL_MODEL + cv2.CALIB_THIN_PRISM_MODEL

# Find corners
ret, corners = cv2.findChessboardCorners(gray, (9,6), None)

# Calibrate
ret, K, D, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, image_size, None, None,
    flags=flags
)
```

**Output Parameters**:
```yaml
# camera_calibration.yaml
image_width: 1920
image_height: 1080
camera_name: narrow_stereo
camera_matrix:
  rows: 3
  cols: 3
  data: [fx, 0, cx, 0, fy, cy, 0, 0, 1]
distortion_model: rational_polynomial
distortion_coefficients:
  rows: 1
  cols: 8
  data: [k1, k2, p1, p2, k3, k4, k5, k6]
rectification_matrix:
  rows: 3
  cols: 3
  data: [1, 0, 0, 0, 1, 0, 0, 0, 1]
projection_matrix:
  rows: 3
  cols: 4
  data: [fx, 0, cx, 0, 0, fy, cy, 0, 0, 0, 1, 0]
```

**Quality Metrics**:
| Metric | Acceptable | Good | Excellent |
|--------|------------|------|-----------|
| Reprojection Error | < 1.0 px | < 0.5 px | < 0.3 px |
| Coverage | > 60% | > 80% | > 90% |
| Images Used | > 30 | > 50 | > 100 |

**Verification**:
- [ ] Undistorted straight lines appear straight
- [ ] Reprojection error < 0.5 pixels RMS
- [ ] Parameters saved to ROS/MAVLink camera info topic

---

### 2.3 Timestamp Synchronization

**Purpose**: Align companion computer and autopilot timestamps for accurate data fusion.

**Method**: NTP with PTP (Precision Time Protocol) fallback for microsecond accuracy.

**Configuration**:

**PX4 Side**:
```
Parameter: UAVCAN_PUB_RTCM = Enabled
Parameter: MAV_PROTO_VER = 2 (for microsecond timestamps)
```

**RPi Side**:
```bash
# Install chrony for better NTP
sudo apt install chrony

# Edit /etc/chrony/chrony.conf
server pool.ntp.org iburst
makestep 1.0 3
maxupdateskew 100.0

# Enable hardware timestamping if available
hwtimestamp *
```

**MAVLink Time Synchronization**:
```python
# Send TIMESYNC message
import pymavlink.mavutil as mavutil

master = mavutil.mavlink_connection('/dev/ttyAMA0', baud=921600)

def send_timesync():
    tc1 = int(time.time() * 1e6)  # Current time in microseconds
    ts1 = 0  # Remote timestamp (unknown)
    master.mav.timesync_send(tc1, ts1)
```

**Validation**:
- [ ] `TIMESYNC` round-trip latency < 10ms
- [ ] Clock drift < 1ms per minute
- [ ] Camera trigger timestamps align with IMU

**Testing**:
```bash
# Check current time offset
chronyc tracking

# Expected output:
# Reference ID    : 123.456.789.012
# Stratum         : 2
# Last offset     : +0.000012 seconds
# RMS offset      : 0.000025 seconds
```

---

### 2.4 Network Latency Measurement

**Purpose**: Characterize telemetry link performance for command/response timing.

**Tools**: `ping`, `mavlink ping`, `iperf3`

**Test Configuration**:

**Test 1: ICMP Ping (Baseline)**
```bash
# From GCS to RPi
ping -c 100 -i 0.1 <rpi_ip>

# Expected for WiFi:
# Min: < 5ms
# Avg: < 20ms
# Max: < 100ms
# Packet loss: < 0.1%
```

**Test 2: MAVLink Ping**
```python
import time
from pymavlink import mavutil

master = mavutil.mavlink_connection('udp:0.0.0.0:14550')
latencies = []

for i in range(100):
    start = time.time()
    master.mav.ping_send(int(start * 1e6), 0, 0, 0)
    master.recv_match(type='PING', blocking=True)
    latencies.append((time.time() - start) * 1000)

print(f"Avg latency: {sum(latencies)/len(latencies):.2f} ms")
print(f"Max latency: {max(latencies):.2f} ms")
print(f"99th percentile: {sorted(latencies)[99]:.2f} ms")
```

**Test 3: Bandwidth (iperf3)**
```bash
# On RPi (server)
iperf3 -s -p 5201

# On GCS (client)
iperf3 -c <rpi_ip> -p 5201 -t 30 -i 1

# Key metrics:
# - Bandwidth > 10 Mbps for video
# - Jitter < 5ms for control
# - Loss < 0.5%
```

**Telemetry Link Budget**:

| Link Type | Range | Bandwidth | Latency | Use Case |
|-----------|-------|-----------|---------|----------|
| WiFi (2.4G) | 100m | 20-50 Mbps | 5-50ms | Short range, high bandwidth |
| WiFi (5G) | 50m | 100+ Mbps | 2-20ms | Video streaming |
| 433 MHz | 1km | 10-50 kbps | 50-200ms | Long range telemetry |
| 915 MHz | 500m | 100-500 kbps | 20-100ms | Regulatory compliance |

**Acceptance Criteria**:
- [ ] Command latency < 100ms for manual control
- [ ] Telemetry stream continuous at 10 Hz minimum
- [ ] Video latency < 200ms for FPV
- [ ] Packet loss < 1% at operational range

---

## 3. Operational Calibrations

### 3.1 ESC Synchronization

**Purpose**: Ensure all motors start and run at identical throttle points.

**ESC Types Supported**:
- DShot (150/300/600/1200)
- OneShot125/42
- PWM (400-500 Hz)

**Synchronization Procedure**:

**Step 1: Protocol Configuration**
```
Parameter: PWM_RATE = 400 (for PWM ESCs)
Parameter: DSHOT_CONFIG = DShot600 (for DShot)
```

**Step 2: ESC Programming (if required)**
```
For BLHeli/AM32 ESCs:
1. Connect ESC to programming tool
2. Set min throttle: 1000us
3. Set max throttle: 2000us
4. Enable brake on stop (optional)
5. Set motor direction (CW/CCW)
```

**Step 3: Throttle Range Calibration**
```
Safety: REMOVE PROPELLERS

1. Power on with throttle stick at maximum
2. Wait for musical tone (enter programming mode)
3. Move throttle to minimum
4. Wait for confirmation tone
5. Power cycle to exit
```

**Step 4: Motor Mapping Verification**
```
QGroundControl → Vehicle Setup → Motors

Verify motor order per airframe type:
- Quad X: 1=front-right, 2=back-left, 3=front-left, 4=back-right
- Quad +: 1=front, 2=right, 3=back, 4=left
```

**Step 5: Spin Test**
```
Safety: PROPELLERS REMOVED

1. Arm aircraft
2. Slowly increase throttle to 10%
3. Verify all motors start simultaneously
4. Verify all motors spin at similar RPM (±5%)
5. Check for any vibration or unusual noise
```

**Parameter Verification**:
```
MOT_SLEW_MAX = 0.2 (or lower for smooth starts)
MOT_SPIN_ARM = 0.08 (8% min when armed)
MOT_SPIN_MIN = 0.15 (15% min when flying)
```

---

### 3.2 Motor Thrust Curve Measurement

**Purpose**: Characterize thrust vs throttle for accurate power estimation and control.

**Equipment Required**:
- Thrust stand with load cell (>2x max thrust capacity)
- Power analyzer (voltage/current measurement)
- Tachometer (optical or ESC telemetry)
- Data logger

**Test Points**:
| Throttle % | Points | Reason |
|------------|--------|--------|
| 0-20% | Every 2% | Critical hover region |
| 20-50% | Every 5% | Transition region |
| 50-100% | Every 10% | Maximum thrust |

**Measurement Procedure**:

1. **Mount motor** on thrust stand with correct propeller
2. **Connect** ESC to autopilot output
3. **Configure** data logging in QGroundControl
4. **Record** at each test point:
   - Throttle command (%)
   - Thrust (grams/kg)
   - Current (A)
   - Voltage (V)
   - Power (W)
   - RPM
   - Temperature (motor/ESC)

**Data Analysis**:
```python
# Thrust curve fitting
import numpy as np
from scipy.optimize import curve_fit

# Quadratic model: thrust = a * throttle^2 + b * throttle
def thrust_model(x, a, b):
    return a * x**2 + b * x

# Fit curve
popt, _ = curve_fit(thrust_model, throttle_data, thrust_data)

# Calculate R-squared
r_squared = 1 - (np.sum((thrust_data - thrust_model(throttle_data, *popt))**2) / 
                 np.sum((thrust_data - np.mean(thrust_data))**2))
```

**Expected Results**:
- Thrust approximately proportional to throttle^2 (for fixed-pitch props)
- Efficiency peaks at 60-80% throttle
- Linear region: 20-80% throttle

**PX4 Parameter Update**:
```
THR_MDL_FAC = 0.0 to 1.0 (0 = linear, 1 = quadratic)
Set based on curve fit results
```

---

### 3.3 Hover Throttle Estimation

**Purpose**: Determine throttle required for level hover at operational payload.

**Calculation Method**:

**Step 1: Gather Data**
```
All-up weight (AUW): _______ kg
Number of motors: _______
Maximum thrust per motor: _______ kg
```

**Step 2: Calculate Thrust-to-Weight Ratio**
```
TWR = (Max thrust × Num motors) / AUW

Safe hover TWR: 1.5:1 to 2.0:1
Minimum TWR: 1.2:1
```

**Step 3: Estimate Hover Throttle**
```
Hover thrust = AUW / Num motors per motor
Hover throttle ≈ sqrt(Hover thrust / Max thrust per motor)

Example:
- AUW = 2.0 kg
- 4 motors, 1.0 kg max thrust each
- Hover thrust per motor = 0.5 kg
- Hover throttle = sqrt(0.5/1.0) = 0.707 = 70.7%
```

**Step 4: Flight Test Verification**
```
Procedure:
1. Take off in Position mode
2. Achieve stable hover at 3+ meters
3. Note throttle stick position
4. Check `actuator_outputs` in logs

Acceptance: Hover throttle 40-60% of full range
```

**Parameter Configuration**:
```
MPC_THR_HOVER = Calculated hover throttle (0.0 - 1.0)
MPC_THR_MIN = 0.08 (or thrust curve minimum)
MPC_THR_MAX = 0.90 (reserve for attitude control)
```

---

### 3.4 Current Sensor Calibration

**Purpose**: Ensure accurate battery monitoring and power reporting.

**Calibration Types**:
- Hall effect sensors (integrated in ESCs)
- Shunt resistors (integrated in power modules)
- External power monitors

**Procedure**:

**Step 1: Voltage Calibration**
```
1. Measure battery voltage with multimeter
2. Compare to QGroundControl reading
3. Calculate correction factor:
   
   BAT_V_DIV = (Measured V / Reported V) × Current BAT_V_DIV

Example:
- Measured: 16.8V
- Reported: 16.2V
- Current BAT_V_DIV: 10.1
- New BAT_V_DIV = (16.8/16.2) × 10.1 = 10.47
```

**Step 2: Current Calibration (Load Method)**
```
Equipment: Electronic load or known resistor

1. Set load to draw 5A from battery
2. Wait for stable reading
3. Compare measured vs reported:

   BAT_A_PER_V = (Measured A / Reported A) × Current BAT_A_PER_V

4. Repeat at 10A, 20A for verification
```

**Step 3: Current Calibration (Charge Integration Method)**
```
1. Fully charge battery (note mAh capacity)
2. Fly mission consuming ~50% of capacity
3. Recharge, noting mAh replaced
4. Compare to logged consumption:

   Correction = (Recharged mAh / Logged mAh)
   BAT_A_PER_V = BAT_A_PER_V × Correction
```

**Parameter Summary**:
```
BAT_V_DIV = Voltage divider ratio
BAT_A_PER_V = Current sense A/V
BAT_CAPACITY = Battery capacity in mAh
BAT_CRIT_THR = Critical threshold (%)
BAT_LOW_THR = Low threshold (%)
BAT_EMERGEN_THR = Emergency threshold (%)
```

**Verification**:
- [ ] Voltage accurate to ±0.1V
- [ ] Current accurate to ±5%
- [ ] Remaining capacity tracks actual flight time
- [ ] Warnings trigger at correct thresholds

---

## 4. Validation Flights

### 4.1 Manual Mode Checkout

**Purpose**: Verify basic flight characteristics and control authority before automated modes.

**Prerequisites**:
- [ ] All sensor calibrations complete
- [ ] RC range check complete (>100m)
- [ ] GPS lock (8+ satellites, HDOP < 2.0)
- [ ] Battery at >80% charge
- [ ] Weather conditions acceptable (< 10 m/s wind)
- [ ] Emergency procedures reviewed

**Test Card**:

| Step | Maneuver | Acceptance Criteria | Duration |
|------|----------|---------------------|----------|
| 1 | Takeoff to hover | Smooth ascent, no drift | 10s |
| 2 | Hover | Position hold within 2m | 30s |
| 3 | Pitch forward/back | Smooth response, no oscillation | 10s |
| 4 | Roll left/right | Smooth response, no oscillation | 10s |
| 5 | Yaw CW/CCW | 360° turn in < 10s | 10s |
| 6 | Ascend/descend | Rate 1-3 m/s, smooth | 20s |
| 7 | Figure-8 pattern | Coordinated turns | 60s |
| 8 | Landing | Controlled descent, no bounce | 10s |

**Failure Criteria** (abort test):
- Uncommanded drift > 5m
- Visible oscillation (>2Hz)
- Control latency > 0.5s
- Abnormal sounds or vibrations
- Rapid battery drain (>50% in 5 min)

**Log Analysis**:
```
Key parameters to review:
- vehicle_attitude_setpoint vs vehicle_attitude (tracking error)
- actuator_outputs (saturation check)
- battery_status (current spikes)
- estimator_status (innovation checks)
```

---

### 4.2 Position Hold Stability

**Purpose**: Validate GPS and barometer performance for autonomous hovering.

**Setup**:
- Mode: Position (GPS)
- Altitude: 5-10 meters
- Duration: 5 minutes minimum
- Wind: < 5 m/s

**Stability Metrics**:

| Metric | Target | Acceptable |
|--------|--------|------------|
| Position drift (XY) | < 0.5m | < 2.0m |
| Altitude variation | < 0.3m | < 1.0m |
| Yaw stability | < 2° | < 5° |
| Velocity noise | < 0.1 m/s | < 0.5 m/s |

**Test Procedure**:
1. Take off in Position mode
2. Allow 10s for position lock
3. Release sticks for 5 minutes
4. Record maximum drift distances
5. Test recovery from disturbance (nudge aircraft)

**Parameter Tuning** (if needed):
```
MPC_XY_P = Position proportional gain (default 0.95)
MPC_XY_VEL_P = Velocity proportional gain (default 0.09)
MPC_XY_VEL_I = Velocity integral gain (default 0.02)
MPC_Z_P = Altitude proportional gain (default 1.0)
```

---

### 4.3 Waypoint Following Accuracy

**Purpose**: Validate navigation system and controller performance.

**Test Pattern**: Box pattern with 50m legs

```
    4 ---------- 3
    |            |
    |     X      |  X = Home/Start
    |            |
    1 ---------- 2

    Leg distance: 50m
    Altitude: 30m
    Speed: 5 m/s (slow), 10 m/s (cruise)
```

**Acceptance Criteria**:

| Parameter | Target | Acceptable |
|-----------|--------|------------|
| Cross-track error | < 1.0m | < 3.0m |
| Turn overshoot | < 3.0m | < 5.0m |
| Altitude error | < 1.0m | < 2.0m |
| Speed accuracy | ±0.5 m/s | ±1.0 m/s |
| WP arrival radius | < 2.0m | < 5.0m |

**Mission Upload**:
```
QGroundControl → Plan → Simple Square
- Set appropriate altitude
- Configure speed
- Verify acceptance radius (NAV_ACC_RAD)
```

**Log Analysis**:
```
Compare:
- vehicle_global_position vs position_setpoint_triplet
- Calculate RMS error in NED frame
- Check for systematic bias (indicates mag/tuning issue)
```

---

### 4.4 Return-to-Launch (RTL) Precision

**Purpose**: Validate failsafe behavior and landing accuracy.

**RTL Configuration**:
```
Parameter: RTL_RETURN_ALT = 50m (clear obstacles)
Parameter: RTL_DESCEND_ALT = 15m (landing approach)
Parameter: RTL_LAND_DELAY = 0s (immediate land)
Parameter: RTL_MIN_DIST = 5m (RTL vs Land decision)
```

**Test Scenarios**:

**Scenario 1: Close-Range RTL**:
1. Fly 20m from home
2. Trigger RTL (RC switch or GCS command)
3. Verify:
   - Climb to RTL_RETURN_ALT
   - Straight-line return
   - Descent at home position
   - Controlled landing

**Scenario 2: Long-Range RTL**:
1. Fly 200m from home
2. Trigger RTL
3. Verify navigation accuracy throughout return
4. Check for premature descent

**Scenario 3: RC Failsafe**:
1. Fly 50m from home
2. Turn off RC transmitter
3. Verify automatic RTL engagement
4. Restore RC, verify control regained

**Landing Accuracy Measurement**:
```
Method 1: Visual marker
- Place marker at takeoff position
- Measure landing distance from marker

Method 2: GPS log
- Compare RTL landing position to takeoff
- Calculate horizontal distance
```

**Acceptance Criteria**:
| Metric | Target | Acceptable |
|--------|--------|------------|
| Landing accuracy | < 1.0m | < 3.0m |
| Approach altitude | Within 5m of RTL_DESCEND_ALT | Within 10m |
| Touchdown speed | < 0.5 m/s vertical | < 1.0 m/s |
| RTL completion time | < 2× manual return time | < 3× |

---

## 5. Pre-Flight Checklist Summary

### Complete Pre-Flight Calibration Verification

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| Accelerometer | Level indicator | < 1° on all axes |
| Gyroscope | Stationary check | < 5 deg/s drift |
| Magnetometer | 360° rotation | Smooth heading, no jumps |
| GPS | Satellites visible | 8+, HDOP < 2.0 |
| RC | Monitor check | All channels 1000-2000 |
| Battery | Voltage under load | > nominal - 0.5V |
| ESCs | Motor test | All start simultaneously |
| Companion Computer | Heartbeat check | 1 Hz MAVLink heartbeat |
| Camera | Visual check | Clear image, correct overlay |
| Network | Ping test | < 50ms latency |

### Calibration Sign-Off Log

```
Date: _______________  Aircraft ID: _______________
Pilot/Engineer: _______________  Location: _______________

[ ] PX4 Accelerometer    Initials: _______ Time: _______
[ ] PX4 Gyroscope        Initials: _______ Time: _______
[ ] PX4 Magnetometer     Initials: _______ Time: _______
[ ] PX4 Airspeed         Initials: _______ Time: _______
[ ] RC Transmitter       Initials: _______ Time: _______
[ ] RPi UART Config      Initials: _______ Time: _______
[ ] Camera Calibration   Initials: _______ Time: _______
[ ] Time Sync            Initials: _______ Time: _______
[ ] Network Test         Initials: _______ Time: _______
[ ] ESC Sync             Initials: _______ Time: _______
[ ] Thrust Curves        Initials: _______ Time: _______
[ ] Hover Throttle       Initials: _______ Time: _______
[ ] Current Sensor       Initials: _______ Time: _______

Validation Flights:
[ ] Manual Mode          Initials: _______ Time: _______
[ ] Position Hold        Initials: _______ Time: _______
[ ] Waypoint Follow      Initials: _______ Time: _______
[ ] RTL Precision        Initials: _______ Time: _______

NOTES:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

APPROVED FOR FLIGHT: [ ] YES  [ ] NO  [ ] WITH RESTRICTIONS

Signed: _________________ Date: _________________
```

---

## Appendix A: Quick Reference Tables

### Common PX4 Calibration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| CAL_ACC0_ID | 0 | Accelerometer device ID |
| CAL_ACC0_XOFF | 0.0 | X axis offset |
| CAL_GYRO0_ID | 0 | Gyroscope device ID |
| CAL_MAG0_ID | 0 | Magnetometer device ID |
| CAL_MAG0_ROT | 0 | Rotation from autopilot |
| SENS_BOARD_ROT | 0 | Autopilot orientation |

### Companion Computer Quick Commands

```bash
# UART check
stty -F /dev/ttyAMA0

# MAVLink check
mavlink status

# Time sync check
chronyc tracking

# Network latency
ping -c 10 <ip>
```

### Emergency Procedures

| Condition | Action |
|-----------|--------|
| Loss of RC | Verify RTL engaged |
| Loss of telemetry | Switch to manual, visual control |
| GPS failure | Switch to Altitude mode, manual return |
| Low battery (< 20%) | Land immediately |
| Motor failure | Reduce throttle, attempt controlled descent |
| Flyaway | Switch to manual, cut throttle if needed |

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-09 | Flight Test Engineering | Initial release |

---

*This document contains technical procedures for flight test operations. All tests should be conducted in accordance with local regulations and safety protocols.*
