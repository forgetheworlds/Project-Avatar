# First Flight Test Procedures

## Document Information
- **Purpose**: Comprehensive first flight test procedures for drone flight test pilots
- **Version**: 1.0
- **Last Updated**: 2026-04-09
- **Classification**: Flight Test Protocol

---

## Overview

This document provides a systematic approach to conducting a first flight test of an unmanned aerial system (UAS). The progressive testing methodology minimizes risk while validating airworthiness and flight control systems.

---

## 1. PRE-FLIGHT CHECKLIST

### 1.1 Hardware Inspection

#### Structural Integrity
- [ ] Fuselage/tubes: No cracks, delamination, or stress marks
- [ ] Landing gear: Secured, proper alignment, shock absorption functional
- [ ] Arms/mounts: All fasteners present and torqued to spec
- [ ] Gimbal/camera mount: Secure, gimbal moves freely without binding
- [ ] Payload mounts: Locked and balanced

#### Propulsion System
- [ ] Motors: All screws tight, bell spins freely, no bearing noise
- [ ] Props: Correct orientation, no nicks/chips/cracks, balanced (if tested)
- [ ] ESCs: Signal wires secure, power connections tight, no visible damage
- [ ] Motor direction: Verified correct for each motor (CW/CCW)

#### Electrical Systems
- [ ] Battery: Charged to storage voltage minimum (3.8V/cell), no swelling
- [ ] Power distribution: XT90/connector seated firmly
- [ ] Wiring harness: No exposed conductors, strain relief adequate
- [ ] BEC/output: 5V rail measuring correctly
- [ ] Current sensor: Calibration verified

#### Sensors & Peripherals
- [ ] GPS/RTK antenna: Clear view of sky, connector seated
- [ ] Airspeed sensor (if equipped): Pitot tube unobstructed
- [ ] Magnetometer: No interference from added equipment
- [ ] Barometer: Ventilation clear (tape removed)
- [ ] RC receiver: Antenna positioned correctly, bound and verified
- [ ] Telemetry radio: Range test completed, link quality verified

### 1.2 Software Verification

#### Flight Controller Firmware
- [ ] Firmware version verified against expected build
- [ ] Airframe type correctly selected in parameters
- [ ] Parameter reset to defaults completed (first flight only)
- [ ] Custom parameters loaded and verified
- [ ] Mixer/motor geometry correct for frame type

#### Calibration Status
- [ ] Accelerometer calibrated (all 6 orientations)
- [ ] Gyroscope calibration completed at operating temperature
- [ ] Magnetometer calibrated (rotate in figure-8 pattern)
- [ ] RC transmitter calibrated (all channels, endpoints set)
- [ ] ESCs synchronized/calibrated if required

#### Sensor Health Check
```
QGroundControl/Mission Planner Verification:
- [ ] CPU load < 30% at idle
- [ ] RAM usage acceptable (< 80%)
- [ ] GPS: 3D fix with 8+ satellites, HDOP < 2.0
- [ ] Compass variance within acceptable range
- [ ] Barometric altitude reading stable
- [ ] Vibration levels acceptable (see section 3)
- [ ] Pre-arm checks passing (no red errors)
```

#### Safety Systems
- [ ] Failsafe parameters configured (see section 1.4)
- [ ] Geofence defined (if used)
- [ ] Maximum altitude limit set
- [ ] Maximum distance limit set
- [ ] Battery failsafe levels configured

### 1.3 Control Link Test

#### RC Transmitter Verification
- [ ] Mode switch (MANUAL/STABILIZED/POSITION) functional
- [ ] Arm/disarm switch responds correctly
- [ ] Throttle responds: motor RPM increases with stick input
- [ ] Roll/Pitch sticks: verified correct directions
- [ ] Yaw stick: verified correct rotation direction
- [ ] Kill switch or emergency stop functional (if equipped)

#### Directional Verification (CRITICAL)
| Control Input | Expected Response | Verified |
|--------------|-------------------|----------|
| Right roll stick | Aircraft rolls right (right side down) | [ ] |
| Forward pitch stick | Nose pitches down | [ ] |
| Right yaw stick | Nose yaws right (CW from above) | [ ] |
| Throttle up | All motors increase RPM proportionally | [ ] |

#### Ground Control Station (GCS) Test
- [ ] Telemetry link established at 10m distance
- [ ] Heartbeat message receiving at 1Hz
- [ ] Command upload functional (test with simple mission)
- [ ] Parameter read/write functional
- [ ] Real-time position/orientation displaying correctly

### 1.4 Failsafe Verification

#### RC Failsafe
- [ ] RC loss simulation: Turn off TX → vehicle enters failsafe mode
- [ ] Return-to-launch (RTL) triggered correctly
- [ ] Hover/land option tested if RTL not configured
- [ ] Failsafe timeout duration verified

#### Battery Failsafe
- [ ] Low battery warning threshold set (typically 3.6V/cell)
- [ ] Critical battery action configured (RTL or Land)
- [ ] Emergency battery level set (immediate land)
- [ ] Cell voltage reading accurate (verify with multimeter)

#### Data Link Failsafe
- [ ] Telemetry loss behavior configured
- [ ] GCS heartbeat timeout set (typically 5-10 seconds)
- [ ] Action on link loss: Continue/RTL/Land/Hold

#### Geofence
- [ ] Max altitude fence: Action = RTL or Land
- [ ] Max radius fence: Action = RTL or Hold
- [ ] Test boundary acknowledged by system

---

## 2. PROGRESSIVE TESTING PROTOCOL

### Phase 0: Pre-Test Setup (Ground)

**Location Requirements:**
- Open area: minimum 10m radius clear of obstacles
- Surface: Firm, level ground
- Weather: Wind < 5 m/s, visibility > 1km
- Personnel: Pilot, spotter, data recorder
- Safety: Fire extinguisher rated for LiPo, first aid kit

**Logistics:**
- [ ] GCS laptop charged
- [ ] Test checklist printed
- [ ] Stopwatch available
- [ ] Data logging configured (SD card inserted, logging enabled)

---

### Phase 1: Tethered Test (Props OFF)

**Purpose:** Verify control response without thrust risk

**Setup:**
- [ ] Aircraft secured to ground via rope/strap at CG
- [ ] Slack allows 30-degree tilt in any direction
- [ ] Props removed or secured with prop locks

**Procedure:**
1. Power on aircraft and GCS
2. Arm in MANUAL/ACRO mode
3. Apply small control inputs (10% stick deflection)
4. Verify gimbal/control surfaces move correctly

**Verification:**
| Test | Pass Criteria | Result |
|------|--------------|--------|
| Roll right | Aircraft rolls right within slack limit | [ ] Pass / Fail |
| Pitch forward | Nose pitches down within slack limit | [ ] Pass / Fail |
| Yaw right | Nose yaws right within slack limit | [ ] Pass / Fail |
| Throttle up | Motors armed but no prop rotation | [ ] Pass / Fail |

**Decision:**
- ALL PASS → Proceed to Phase 2
- ANY FAIL → Abort, diagnose control reversal or mixer issue

---

### Phase 2: Spin-up Test (Tethered, Props ON)

**Purpose:** Verify motor spin direction and basic thrust response

**Setup:**
- [ ] Props installed (verified correct rotation)
- [ ] Aircraft secured with 2m rope minimum
- [ ] Rope attached to sturdy anchor point
- [ ] All personnel outside prop arc (2m minimum)

**Safety:**
- [ ] Safety glasses worn by all personnel
- [ ] No loose clothing/jewelry near props
- [ ] Kill switch armed and tested

**Procedure:**
1. Arm in MANUAL mode
2. Apply throttle to 5% → motors spin, verify CW/CCW pattern
3. Apply throttle to 10% → listen for unusual vibrations
4. Apply throttle to 20% → feel for oscillations
5. Yaw input → verify torque response (nose should yaw)
6. Roll/pitch → verify stabilization response

**Verification:**
| Test | Pass Criteria | Result |
|------|--------------|--------|
| Prop rotation | CW/CCW pattern matches diagram | [ ] Pass / Fail |
| Idle throttle | Motors spin smoothly at 5% | [ ] Pass / Fail |
| Vibration check | No unusual noise at 20% | [ ] Pass / Fail |
| Kill switch | Immediate stop on activation | [ ] Pass / Fail |

**Decision:**
- ALL PASS → Proceed to Phase 3
- Vibration detected → Diagnose (see section 4)
- Wrong rotation → Swap any two motor wires

---

### Phase 3: Hover Test (1m Altitude)

**Purpose:** First untethered flight, validate hover stability

**Pre-flight:**
- [ ] Remove all tethers
- [ ] Verify hover mode is STABILIZED or ALTITUDE
- [ ] Position hold mode available but not initially used
- [ ] Spotter positioned with clear view
- [ ] Abort protocol reviewed with all personnel

**Flight Profile:**
```
Timeline:
T+0:00  Arm in STABILIZED mode
T+0:05  Throttle to hover point (typically 50%)
T+0:10  Lift to 1m altitude, level attitude
T+0:15  HOLD POSITION - hands off sticks (except throttle hold)
T+0:30  Small roll input (10%), verify response
T+0:35  Return to level
T+0:40  Small pitch input (10%), verify response
T+0:45  Return to level
T+0:50  Small yaw input (10%), verify response
T+0:55  Return to heading
T+1:00  Descend and land
```

**Data Collection (Section 3):**
- [ ] Vibration levels logged
- [ ] Control loop performance recorded
- [ ] Battery voltage under load noted
- [ ] GPS position drift measured

**Success Criteria:**
- [ ] Stable hover achieved for 30+ seconds
- [ ] No drift in horizontal plane > 0.5m
- [ ] Altitude hold within 0.3m
- [ ] No control oscillations visible
- [ ] Smooth response to stick inputs

**Decision:**
- ALL PASS → Proceed to Phase 4
- Oscillations detected → Land, reduce P gains by 20%
- Drift detected → Check GPS/compass, verify calibration

---

### Phase 4: Position Hold Test

**Purpose:** Verify GPS-based position hold and loiter modes

**Prerequisites:**
- [ ] GPS HDOP < 2.0
- [ ] 10+ satellites locked
- [ ] Compass variance acceptable
- [ ] Hover test completed successfully

**Flight Profile:**
```
Timeline:
T+0:00  Takeoff to 3m altitude in STABILIZED mode
T+0:10  Switch to POSITION HOLD mode
T+0:15  Release all sticks (centered)
T+0:30  Position hold check: drift < 1m radius
T+1:00  Apply small position command (2m forward)
T+1:15  Verify smooth translation to new position
T+1:30  Release sticks, verify position hold
T+2:00  Yaw 90 degrees, verify position maintained
T+2:30  Complete 360-degree yaw test
T+3:00  Descend and land
```

**Verification:**
| Test | Pass Criteria | Result |
|------|--------------|--------|
| Initial hold | Position maintained within 1m radius | [ ] Pass / Fail |
| Position command | Smooth translation to commanded position | [ ] Pass / Fail |
| Yaw during hold | Position maintained during 360-degree yaw | [ ] Pass / Fail |
| Wind rejection | Position maintained in light wind (< 3 m/s) | [ ] Pass / Fail |

**Decision:**
- ALL PASS → Proceed to Phase 5
- Excessive drift → Check GPS/compass, re-calibrate
- Toilet bowling → Compass interference or calibration issue

---

### Phase 5: Waypoint Test

**Purpose:** Validate autonomous waypoint navigation

**Prerequisites:**
- [ ] Position hold test passed
- [ ] Mission uploaded and verified in GCS
- [ ] Geofence configured as safety boundary

**Test Mission (Simple Square):**
```
WP1: Takeoff to 5m altitude
WP2: Move 10m North
WP3: Move 10m East  
WP4: Move 10m South
WP5: Move 10m West (return to WP2 position)
WP6: RTL
```

**Flight Profile:**
```
Timeline:
T+0:00  Takeoff in STABILIZED mode to 5m
T+0:10  Engage MISSION mode
T+0:15  Monitor WP acceptance (acceptance radius = 2m)
T+1:00  WP2 reached: verify position accuracy
T+2:00  WP3 reached: verify position accuracy
T+3:00  WP4 reached: verify position accuracy
T+4:00  WP5 reached: verify position accuracy
T+4:30  RTL initiated automatically
T+5:00  Descent to home position begins
T+5:30  Land and disarm
```

**Verification:**
| Test | Pass Criteria | Result |
|------|--------------|--------|
| WP acceptance | All waypoints accepted within radius | [ ] Pass / Fail |
| Navigation accuracy | < 2m error at each waypoint | [ ] Pass / Fail |
| Heading alignment | Nose points toward next WP | [ ] Pass / Fail |
| RTL execution | Returns to home and lands | [ ] Pass / Fail |
| Altitude control | Maintains commanded altitude | [ ] Pass / Fail |

**Decision:**
- ALL PASS → First flight complete, data analysis phase
- Navigation error > 2m → Check GPS accuracy, wind conditions
- Missed waypoint → Increase acceptance radius, check groundspeed

---

## 3. DATA TO COLLECT

### 3.1 Vibration Levels

**Measurement Points:**
- IMU accelerometer (logged automatically)
- Target: < 30 m/s^2 on all axes during hover

**Analysis:**
```
Vibration Thresholds:
- < 15 m/s^2: Excellent
- 15-30 m/s^2: Good
- 30-50 m/s^2: Acceptable (monitor closely)
- > 50 m/s^2: UNACCEPTABLE - diagnose and fix
```

**Diagnosis if High:**
- [ ] Prop balance check
- [ ] Motor mounting bolt torque
- [ ] Frame resonance (check for loose components)
- [ ] Gimbal isolation (if equipped)

### 3.2 Control Loop Performance

**Logged Parameters:**
- `vehicle_attitude` - Actual roll/pitch/yaw
- `vehicle_attitude_setpoint` - Desired roll/pitch/yaw
- `actuator_controls` - Control outputs

**Analysis:**
```
Performance Metrics:
- Setpoint tracking error < 5 degrees
- No sustained oscillations (> 2 cycles)
- Overshoot < 20% of commanded change
- Settling time < 2 seconds
```

**Tuning Indicators:**
- Overshoot only → Reduce D gain slightly
- Oscillations → Reduce P gain
- Sluggish response → Increase P gain
- Noise in control outputs → Check vibration levels

### 3.3 Battery Consumption

**Measurements:**
| Phase | Voltage (V) | Current (A) | Power (W) | Time |
|-------|-------------|-------------|-----------|------|
| Pre-flight | | | | |
| Hover @ 1m | | | | |
| Position hold | | | | |
| Waypoint nav | | | | |
| RTL descent | | | | |
| Post-flight | | | | |

**Calculations:**
```
Hover efficiency: ___ W/kg
Hover current: ___ A
Flight time estimate at hover: ___ minutes
```

### 3.4 GPS Accuracy

**Measurements:**
- HDOP during flight: ___
- Satellites visible: ___
- EPH (horizontal position error): ___ m
- EPV (vertical position error): ___ m

**Position Hold Accuracy:**
```
Radius Analysis:
- 1-minute hold radius: ___ m
- Maximum excursion: ___ m
- Standard deviation: ___ m
```

### 3.5 RC Range

**Test Method:**
1. Start at aircraft position
2. Walk away while maintaining telemetry link
3. Note distance when:
   - RSSI drops below -85 dBm
   - Control inputs lag
   - Telemetry becomes intermittent

**Results:**
```
Reliable control range: ___ m
Telemetry range: ___ m
Minimum operational range: ___ m (should be > 500m)
```

---

## 4. ABORT CRITERIA

### Immediate Land Criteria

**PILOT AUTHORITY:** Pilot in Command has absolute authority to abort at any time for any safety concern.

#### Critical Aborts (Land Immediately)
| Condition | Pilot Action |
|-----------|--------------|
| Control reversal | Switch to MANUAL mode if safe, otherwise kill switch |
| Severe oscillations (> 20 deg) | Kill switch or emergency land |
| Motor failure | Kill switch, prepare for crash landing |
| Uncommanded yaw (> 45 deg/s) | Kill switch |
| Rapid altitude loss | Full throttle, attempt recovery |
| Complete telemetry loss | Assume failsafe active, monitor visually |
| Smoke or fire | Kill switch, evacuate, use fire extinguisher |
| Structural failure | Kill switch |
| Flyaway (uncontrolled departure) | Kill switch if in range, track on GCS |

#### Controlled Aborts (Execute Landing)
| Condition | Response |
|-----------|----------|
| Elevated vibration (> 40 m/s^2) | Controlled descent and land |
| Position drift > 3m | Land manually, do not use position hold |
| GPS degradation (HDOP > 3) | Switch to STABILIZED, land |
| Battery voltage sag (> 0.3V under load) | Land immediately |
| GCS anomaly | Land using RC only |
| High wind warning (> 8 m/s) | Land before conditions worsen |

### Unusual Vibrations

**Vibration Signature Analysis:**
```
Low frequency (10-30 Hz):  →  Prop imbalance or loose mount
Mid frequency (50-100 Hz): →  Motor bearing issue or ESC sync problem
High frequency (> 200 Hz): →  Electrical noise or IMU issue

Immediate Actions:
1. Note frequency in log
2. Land immediately if > 50 m/s^2
3. Inspect props and motors before next flight
```

### Control Oscillations

**Oscillation Severity:**
| Magnitude | Frequency | Action |
|-----------|-----------|--------|
| < 5 deg | < 1 Hz | Monitor, tune after flight |
| 5-10 deg | 1-2 Hz | Consider landing, log for tuning |
| 10-20 deg | 2-3 Hz | Land immediately |
| > 20 deg | Any | Kill switch, emergency land |

**Oscillation Types:**
- Roll oscillation: Reduce MC_ROLL_P by 20%
- Pitch oscillation: Reduce MC_PITCH_P by 20%
- Yaw oscillation: Check MC_YAW_P and motor balance
- Coupled oscillation: Reduce all P gains by 15%

### Unexpected Behavior

**Behavior Log:**
| Time | Behavior Observed | Pilot Response | Outcome |
|------|-------------------|----------------|---------|
| | | | |
| | | | |

---

## 5. SUCCESS CRITERIA

### Minimum First Flight Success

All criteria must be met for test to be considered successful:

| Criterion | Threshold | Measured | Pass |
|-----------|-----------|----------|------|
| Stable hover duration | > 60 seconds | ___ s | [ ] |
| Position hold accuracy | < 2m radius | ___ m | [ ] |
| Altitude hold accuracy | < 0.5m | ___ m | [ ] |
| Vibration levels | < 30 m/s^2 | ___ m/s^2 | [ ] |
| Control response | No oscillations | N/A | [ ] |
| Battery voltage | > 3.6V/cell minimum | ___ V | [ ] |
| GPS accuracy | HDOP < 2.0 | ___ | [ ] |

### Extended Success Criteria (Waypoint Test)

| Criterion | Threshold | Measured | Pass |
|-----------|-----------|----------|------|
| Waypoint accuracy | < 2m error | ___ m | [ ] |
| Heading alignment | Points to next WP | Y/N | [ ] |
| Smooth navigation | No overshoot > 3m | ___ m | [ ] |
| RTL execution | Returns and lands | Y/N | [ ] |

### Post-Flight Assessment

**Airworthiness Determination:**
```
[ ] AIRWORTHY - All tests passed, approved for expanded flight envelope
[ ] CONDITIONAL - Minor issues noted, restricted operations approved
[ ] NOT AIRWORTHY - Significant issues, further work required
```

**Restrictions if Conditional:**
- Maximum altitude: ___ m
- Maximum distance: ___ m
- Weather limits: ___ m/s wind
- Required modes: ___
- Additional monitoring: ___

---

## 6. POST-FLIGHT PROCEDURES

### Data Download
- [ ] Flight log downloaded from SD card
- [ ] GCS telemetry log saved
- [ ] Photos of aircraft condition taken
- [ ] Vibration analysis completed

### Aircraft Inspection
- [ ] Visual inspection for stress cracks
- [ ] Motor temperature check (warm is OK, hot is not)
- [ ] Prop condition check
- [ ] Battery voltage verification
- [ ] Fastener torque check (random sample)

### Documentation
- [ ] Test log completed (this document)
- [ ] Issues logged in tracking system
- [ ] Parameter changes documented
- [ ] Next flight requirements defined

---

## APPENDIX A: Quick Reference Card

```
PRE-FLIGHT (Ground):
1. Props OFF - tether test
2. Props ON - spin-up test  
3. Control directions verified
4. Failsafe tested
5. GPS 3D fix confirmed

IN-FLIGHT (Abort Triggers):
- Oscillations > 20 deg → LAND NOW
- Vibration > 50 m/s^2 → LAND NOW
- Uncommanded yaw > 45 deg/s → KILL SWITCH
- Battery < 3.5V/cell → LAND NOW
- Control reversal → KILL SWITCH

SUCCESS CHECK:
[ ] 60s stable hover
[ ] Position within 2m
[ ] Clean RTL
[ ] No oscillations
```

---

## APPENDIX B: Emergency Procedures

### Loss of Control
1. Activate kill switch (if equipped)
2. If no kill switch: Throttle to minimum
3. If still uncontrolled: Power off TX (trigger failsafe RTL)

### Flyaway
1. Note direction and altitude
2. Activate RTL via GCS if link available
3. Track on GCS map for recovery
4. If battery critical: Note last known position

### Crash
1. Pilot: Secure scene, check for fire
2. Spotter: Call emergency services if injuries
3. Do not approach until LiPo fire risk assessed
4. Document crash site with photos
5. Secure wreckage for investigation

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Pilot in Command | | | |
| Safety Observer | | | |
| Data Recorder | | | |
| Test Director | | | |

**Test Location:** ___________________________________

**Weather:** ___________________________________

**Total Flight Time:** ___________________________________

---

*Document Version 1.0 - Generated 2026-04-09*
