# Failure Mode Analysis: Edge Cases and Recovery Procedures

## Executive Summary

This document catalogs critical failure modes for the Project Avatar AI-drone interface, including network, sensor, control, and LLM failure scenarios. Each failure mode includes a decision tree for rapid diagnosis and recovery procedures.

**Classification Levels:**
- **CRITICAL**: Immediate loss of vehicle control or safety risk
- **HIGH**: Significant degradation requiring immediate action
- **MEDIUM**: Degraded performance with defined recovery path
- **LOW**: Informational, monitoring recommended

---

## 1. Network Failures

### 1.1 Mid-Flight WiFi Drop

**Severity**: CRITICAL  
**Detection Latency**: 100ms - 2s  
**Typical Trigger**: Range exceed, interference, access point failure

#### Symptoms
- MAVSDK heartbeat timeout (>500ms)
- Connection status: `ConnectionState.DISCONNECTED`
- In-flight with active offboard mode

#### Decision Tree
```
START: WiFi Connection Lost
│
├─ Is vehicle in OFFBOARD mode?
│  ├─ YES → [CRITICAL PATH]
│  │   ├─ Time since last heartbeat > HOLD_TIMEOUT (0.5s)?
│  │   │  ├─ YES → PX4 activates HOLD mode automatically
│  │   │  │   ├─ Connection restored within 5s?
│  │   │  │   │  ├─ YES → Resume mission after re-establishing offboard
│  │   │  │   │  └─ NO → Initiate RTL (Return to Launch)
│  │   │  │   └─ Altitude > RTL_ALT_MIN?
│  │   │  │       ├─ YES → Execute RTL
│  │   │  │       └─ NO → Execute LAND at current position
│  │   │  └─ NO → Continue monitoring, log warning
│  │   └─ Connection restored?
│  │       ├─ YES → Verify PX4 mode, re-engage offboard if safe
│  │       └─ NO → Escalate to emergency landing
│  └─ NO → [NON-CRITICAL PATH]
│      ├─ Vehicle in manual/position mode?
│      │  ├─ YES → Operator has control, monitor for reconnection
│      │  └─ NO → Log telemetry loss, wait for reconnect
│      └─ Auto-recovery configured?
│          ├─ YES → Activate failsafe sequence
│          └─ NO → Manual intervention required
│
END: Connection restored OR Emergency landing initiated
```

#### Recovery Procedures

**Immediate (0-2s)**:
1. Set `offboard.setpoint_hold = true` (if connection persists briefly)
2. Log telemetry snapshot for post-analysis
3. Activate local failsafe buffer on companion computer

**Short-term (2-10s)**:
1. Attempt reconnection with exponential backoff
2. If reconnected: Verify system health before resuming
3. If failed: Trigger autonomous failsafe

**Emergency (>10s)**:
1. Command RTL via MAVLink (if radio backup exists)
2. If no backup: Vehicle executes PX4-native failsafe

#### Prevention
- Dual-band WiFi (2.4GHz + 5GHz) with automatic switching
- Directional antenna on ground station
- Connection quality prediction: Signal strength -85dBm threshold

---

### 1.2 Intermittent Packet Loss

**Severity**: HIGH  
**Detection Latency**: 50-200ms  
**Typical Trigger**: Congestion, multipath fading, partial interference

#### Symptoms
- Inconsistent heartbeat intervals (jitter >100ms)
- Command acknowledgments delayed or missing
- Telemetry stream gaps

#### Decision Tree
```
START: Detect Intermittent Packet Loss
│
├─ Calculate packet loss rate
│  ├─ > 20% loss → [DEGRADED MODE]
│  │   ├─ Is mission critical phase? (takeoff, landing, precision maneuver)
│  │   │  ├─ YES → Reduce operation complexity
│  │   │  │   ├─ Abort precision operations
│  │   │  │   ├─ Switch to POSITION or HOLD mode
│  │   │  │   └─ Reduce command frequency (Hz)
│  │   │  └─ NO → Continue with degraded performance
│  │   └─ Enable redundant command channels?
│  │       ├─ YES → Switch to secondary link (4G/5G/radio)
│  │       └─ NO → Increase command redundancy (send 2x)
│  │
│  ├─ 5-20% loss → [MONITORING MODE]
│  │   ├─ Increase heartbeat frequency
│  │   ├─ Enable packet acknowledgment tracking
│  │   ├─ Log pattern for interference analysis
│  │   └─ Alert operator of degraded link quality
│  │
│  └─ < 5% loss → [NORMAL MONITORING]
│      └─ Continue, log metrics
│
├─ Packet loss pattern analysis
│  ├─ Bursty loss (clustered) → Likely interference burst
│  │   └─ Predictive: Avoid affected frequency/time slots
│  ├─ Random loss → Congestion or weak signal
│  │   └─ Reduce bandwidth, increase FEC
│  └─ Periodic loss → Scheduled interference source
│      └─ Log and avoid specific timing
│
END: Continue with adaptive quality OR switch to backup link
```

#### Recovery Procedures

**Adaptive Strategies**:
1. **Command Batching**: Group non-critical commands
2. **Redundancy**: Send critical commands 2-3x with deduplication
3. **FEC (Forward Error Correction)**: Enable MAVLink2 signing + FEC
4. **Rate Adaptation**: Reduce telemetry rate from 50Hz to 10Hz

**Hard Thresholds**:
```python
PACKET_LOSS_THRESHOLDS = {
    "warning": 0.05,      # 5% - Log only
    "degraded": 0.15,     # 15% - Reduce complexity
    "critical": 0.25,     # 25% - Abort operation
    "emergency": 0.40     # 40% - Emergency landing
}
```

---

### 1.3 Half-Open Connections

**Severity**: HIGH  
**Detection Latency**: 5-30s  
**Typical Trigger**: NAT timeout, asymmetric routing, zombie sockets

#### Symptoms
- Socket appears connected but no data flows
- No TCP RST/FIN received
- MAVLink heartbeat appears stale but socket open

#### Decision Tree
```
START: Suspect Half-Open Connection
│
├─ Connection state check
│  ├─ Socket reports "ESTABLISHED"
│  │   ├─ Last successful MAVLink message timestamp > 5s?
│  │   │  ├─ YES → [STALE CONNECTION DETECTED]
│  │   │  │   ├─ Send ping/heartbeat request
│  │   │  │   │  ├─ Response received?
│  │   │  │   │   │  ├─ YES → False positive, reset timer
│  │   │  │   │   │  └─ NO → Confirmed half-open
│  │   │  │   │  └─ Force socket close and reconnect
│  │   │  │   └─ In critical flight phase?
│  │   │   │       ├─ YES → Activate failsafe immediately
│  │   │   │       │   └─ Command HOLD/RTL via alternate link
│  │   │   │       └─ NO → Reconnect normally
│  │   │  └─ NO → Connection healthy
│  └─ Socket reports other state → Handle per standard procedure
│
├─ Prevention check
│  ├─ TCP keepalive enabled? (interval < 30s)
│  ├─ MAVLink heartbeat timeout configured?
│  └─ Connection watchdog active?
│
END: Connection validated OR re-established
```

#### Recovery Procedures

**Detection Mechanism**:
```python
# Connection health monitoring
last_heartbeat_time = get_last_mavlink_timestamp()
if (current_time - last_heartbeat_time) > STALE_CONNECTION_TIMEOUT:
    connection_health = "STALE"
    force_reconnect()
```

**Prevention**:
1. Enable TCP keepalive: `TCP_KEEPIDLE=10, TCP_KEEPINTVL=5, TCP_KEEPCNT=3`
2. Application-level heartbeat every 1s
3. Connection watchdog thread independent of main control loop

---

### 1.4 UDP Amplification Attack (Security)

**Severity**: CRITICAL  
**Detection Latency**: Real-time  
**Typical Trigger**: Malicious traffic, misconfigured upstream

#### Symptoms
- Sudden bandwidth saturation
- Legitimate packets dropped
- MAVLink message flooding

#### Decision Tree
```
START: Detect Potential Amplification Attack
│
├─ Bandwidth analysis
│  ├─ Ingress traffic > 10x normal baseline?
│  │  ├─ YES → [ATTACK SUSPECTED]
│  │   │   ├─ Source IP analysis
│  │   │   │  ├─ Multiple spoofed sources → DDoS/amplification
│  │   │   │   │   └─ Activate rate limiting immediately
│  │   │   │   └─ Single source → Potential misconfiguration
│  │   │   │       └─ Block source IP, alert operator
│  │   │   ├─ Legitimate control link affected?
│  │   │   │  ├─ YES → [CRITICAL]
│  │   │   │   │   ├─ Switch to secondary authenticated link
│  │   │   │   │   ├─ If no secondary → Emergency RTL
│  │   │   │   │   └─ Log attack signature for forensics
│  │   │   │  └─ NO → Continue with rate limiting
│  │   │   └─ Enable MAVLink signing verification
│  │   └─ NO → Normal traffic spike, monitor
│
├─ Rate limiting activation
│  ├─ Source IP whitelist (known GCS only)
│  ├─ Packet rate limiting per source
│  ├─ MAVLink message validation (drop malformed)
│  └─ Connection migration to alternate port/protocol
│
END: Attack mitigated OR switched to secure backup link
```

#### Recovery Procedures

**Immediate Mitigation**:
1. Enable MAVLink2 packet signing (reject unsigned)
2. Whitelist known ground station IPs
3. Rate limit: Max 1000 packets/sec per source
4. Drop packets > MTU size (fragmentation attack)

**Long-term**:
1. Implement TLS wrapper for MAVLink
2. Certificate-based mutual authentication
3. VPN tunnel for all control traffic

---

## 2. Sensor Failures

### 2.1 GPS Spoofing / Jamming

**Severity**: CRITICAL  
**Detection Latency**: 1-5s  
**Typical Trigger**: Intentional interference, multi-path in urban canyon

#### Symptoms
- Position jump > 10m between samples
- HDOP > 5.0 while reporting "good" fix
- Velocity vector inconsistent with IMU
- Multiple satellites with identical signal strength (spoofing signature)

#### Decision Tree
```
START: GPS Anomaly Detected
│
├─ Jamming Detection
│  ├─ GPS signal strength (CN0) < 30 dB-Hz?
│  │  ├─ YES → [JAMMING SUSPECTED]
│  │   │   ├─ GPS fix quality degrading?
│  │   │   │  ├─ YES → 2D fix or no fix
│  │   │   │   │   ├─ Duration < DEAD_RECKONING_LIMIT (30s)?
│  │   │   │   │   │  ├─ YES → Continue on IMU dead reckoning
│  │   │   │   │   │   │   ├─ Altitude hold from barometer
│  │   │   │   │   │   │   └─ Position hold from optical flow (if available)
│  │   │   │   │   │  └─ NO → GPS failsafe activation
│  │   │   │   │   │      ├─ Altitude > RTL_MIN?
│  │   │   │   │   │      │  ├─ YES → RTL with estimated position
│  │   │   │   │   │      │  └─ NO → LAND at estimated position
│  │   │   │   │   │      └─ Log jamming event, alert operator
│  │   │   │   └─ NO → Monitor closely
│  │   └─ NO → Check for spoofing
│
├─ Spoofing Detection
│  ├─ Position jump > MAX_VELOCITY * dt * SAFETY_FACTOR?
│  │  ├─ YES → [SPOOFING SUSPECTED]
│  │   │   ├─ Validate against:
│  │   │   │   ├─ IMU integration (position delta check)
│  │   │   │   ├─ Optical flow (if available)
│  │   │   │   ├─ Magnetometer (heading consistency)
│  │   │   │   └─ Barometer (altitude sanity)
│  │   │   ├─ Validation passes?
│  │   │   │  ├─ YES → False alarm, update position
│  │   │   │  └─ NO → [SPOOFING CONFIRMED]
│  │   │   │      ├─ Reject GPS position
│  │   │   │      ├─ Switch to dead reckoning
│  │   │   │      ├─ Alert: "GPS SPOOFING - MANUAL CONTROL REQUIRED"
│  │   │   │      └─ If autonomous: Land immediately
│  │   └─ NO → GPS appears valid
│
├─ Multi-sensor validation
│  ├─ GPS vs IMU divergence > threshold?
│  ├─ GPS velocity vs airspeed (if available) mismatch?
│  └─ Satellite constellation sanity check
│
END: GPS validated OR rejected, fallback active
```

#### Recovery Procedures

**Immediate Response**:
```python
GPS_VALIDATION_THRESHOLD = {
    "max_position_jump_m": 10.0,
    "max_velocity_jump_ms": 5.0,
    "min_cn0_dbhz": 30,
    "max_hdop": 5.0,
    "max_imu_divergence_m": 15.0
}

if gps_spoofing_detected():
    px4.set_gps_failsafe(GPSFailsafeMode.REJECT_POSITION)
    px4.activate_dead_reckoning(timeout_sec=30)
    alert_operator("GPS SPOOFING - MANUAL CONTROL")
```

**Fallback Hierarchy**:
1. GPS + RTK (primary)
2. GPS + IMU fusion (secondary)
3. IMU dead reckoning (30s limit)
4. Optical flow + IMU (if available)
5. Manual control only (RC override)

---

### 2.2 Magnetometer Interference

**Severity**: HIGH  
**Detection Latency**: Real-time  
**Typical Trigger**: Power lines, metal structures, onboard electronics

#### Symptoms
- Heading drift during hover
- Yaw instability in position hold
- Mag field strength > 1.5x or < 0.5x of calibration value
- Compass variance in EKF innovations

#### Decision Tree
```
START: Magnetometer Anomaly
│
├─ Field Strength Check
│  ├─ |current_field - calibrated_field| > 0.5 * calibrated_field?
│  │  ├─ YES → [MAG INTERFERENCE DETECTED]
│  │   │   ├─ Interference source identified?
│  │   │   │  ├─ External (power lines, building)
│  │   │   │  │  ├─ Move away possible?
│  │   │   │  │  │  ├─ YES → Execute escape maneuver
│  │   │   │  │  │  │   └─ Use GPS course over ground for heading
│  │   │   │  │  │  └─ NO → Degrade to attitude-only mode
│  │   │   │  │  └─ Heading source: GPS COG (requires motion)
│  │   │   │  └─ Internal (wiring, payload)
│  │   │   │      ├─ Re-calibrate magnetometer in current config
│  │   │   │      ├─ Move high-current wires away from mag
│  │   │   │      └─ If persistent: Disable internal mag, use external
│  │   └─ Severity assessment
│  │       ├─ Mild (0.5-1.0x deviation) → Log warning
│  │       ├─ Moderate (1.0-2.0x) → Degrade yaw accuracy
│  │       └─ Severe (>2.0x) → Mag rejected, GPS-based heading only
│  │
│  └─ NO → Check variance
│      ├─ EKF mag innovation variance > threshold?
│      │  ├─ YES → Mag weight reduced in EKF
│      │  └─ NO → Mag healthy
│
├─ Operational impact
│  ├─ Position hold affected (yaw drift)?
│  │  ├─ YES → Switch to HEADING_HOLD mode (maintain last good heading)
│  └─ Navigation to waypoint affected?
│      ├─ YES → Require minimum speed for GPS course over ground
│
END: Mag interference managed OR heading source switched
```

#### Recovery Procedures

**Immediate**:
1. Reduce mag weight in EKF (increase `EKF2_MAG_NOISE`)
2. Use GPS course over ground as heading reference (requires forward motion)
3. Switch to `HEADING_HOLD` mode (maintain last known good heading)

**Calibration**:
```bash
# Re-calibrate with current onboard configuration
mavlink magcal start
# Or force external mag only
param set CAL_MAG0_EN 0
param set CAL_MAG1_EN 1  # External
```

---

### 2.3 Barometer Ground Effect

**Severity**: MEDIUM  
**Detection Latency**: 2-10s  
**Typical Trigger**: Low-altitude hover, ground proximity < 3m

#### Symptoms
- Altitude hold drift near ground
- Barometric pressure reading increases (appears to descend)
- EKF altitude variance increases
- Vehicle "sinks" during hover near surface

#### Decision Tree
```
START: Altitude Anomaly Near Ground
│
├─ Ground Effect Detection
│  ├─ Altitude < GROUND_EFFECT_ALT (3m)?
│  │  ├─ YES → [CHECK GROUND EFFECT]
│  │   │   ├─ Baro pressure increasing (appearing to descend)?
│  │   │   │  ├─ YES → Ground effect pressure disturbance likely
│  │   │   │   │   ├─ Landing mode active?
│  │   │   │   │   │  ├─ YES → Expected behavior, use rangefinder for final approach
│  │   │   │   │   │  └─ NO → Altitude hold mode
│  │   │   │   │   │      ├─ Rangefinder available?
│  │   │   │   │   │      │  ├─ YES → Switch to rangefinder primary
│  │   │   │   │   │      │  │   └─ Quality check: range < max_valid_range?
│  │   │   │   │   │      │  │       ├─ YES → Use rangefinder altitude
│  │   │   │   │   │      │  │       └─ NO → Blend baro + GPS altitude
│  │   │   │   │   │      └─ NO → Use GPS altitude (less accurate but ground-effect-free)
│  │   │   │   │   └─ Increase hover throttle margin
│  │   │   │   └─ NO → Check other altitude sources
│  │   └─ NO → Not in ground effect zone
│
├─ Multi-altitude fusion
│  ├─ Baro: Affected by ground effect
│  ├─ GPS: Ground-effect-free but less accurate
│  ├─ Rangefinder: Best for low altitude (< 10m)
│  └─ EKF blending weight adjustment based on conditions
│
END: Altitude source optimized for current conditions
```

#### Recovery Procedures

**Sensor Prioritization**:
| Altitude Range | Primary Source | Secondary |
|---------------|----------------|-----------|
| < 3m (landing) | Rangefinder | Baro |
| 3-10m | Rangefinder / GPS blend | Baro |
| > 10m | GPS | Baro |

**Parameters**:
```
EKF2_HGT_MODE = 1  # Range finder as primary when available
EKF2_RNG_AID = 1   # Enable range finder aiding
MPC_ALT_MODE = 1   # Altitude mode: range finder below threshold
```

---

### 2.4 Camera Obscuration

**Severity**: MEDIUM-HIGH (depends on autonomy level)  
**Detection Latency**: Real-time  
**Typical Trigger**: Fog, rain, lens contamination, sun glare

#### Symptoms
- Computer vision confidence drop
- Feature tracking failure
- Visual odometry divergence
- Exposure/saturation warnings

#### Decision Tree
```
START: Camera Vision Degraded
│
├─ Obscuration Type Detection
│  ├─ Image quality metrics analysis
│  │  ├─ Mean luminance < 20 OR > 230? (under/over exposure)
│  │  │  ├─ YES → [LIGHTING ISSUE]
│  │  │   │   ├─ Auto-exposure responding?
│  │  │   │   │  ├─ YES → Wait for adjustment (max 2s)
│  │   │   │   │   │  ├─ Quality improves?
│  │   │   │   │   │   │  ├─ YES → Continue
│  │   │   │   │   │   │  └─ NO → Switch to non-visual navigation
│  │   │   │   │   └─ NO → Manual exposure adjustment
│  │   │   │   └─ Lighting cannot be compensated → Non-visual fallback
│  │   │
│  │   ├─ Feature count < MIN_FEATURES (50)?
│  │   │  ├─ YES → [FEATURE POOR ENVIRONMENT]
│  │   │   │   ├─ Optical flow available?
│  │   │   │   │  ├─ YES → Check flow quality
│  │   │   │   │   │  ├─ Quality > 50%?
│  │   │   │   │   │   │  ├─ YES → Use optical flow for velocity
│  │   │   │   │   │   │  └─ NO → Switch to IMU-only dead reckoning
│  │   │   │   │   └─ NO → GPS + IMU only
│  │   │   │   └─ Visual odometry timeout → Position uncertainty growing
│  │   │   │       ├─ Uncertainty < MAX_SAFE_UNCERTAINTY?
│  │   │   │       │  ├─ YES → Continue, alert operator
│  │   │   │       │  └─ NO → Switch to GPS hold or RTL
│  │   │
│  │   └─ Motion blur detected (feature streaking)?
│  │       ├─ YES → [MOTION BLUR]
│  │        │   ├─ Reduce maximum speed
│  │        │   ├─ Increase camera shutter speed (if manual)
│  │        │   └─ Wait for hover (blur reduces when stationary)
│  │
│  └─ Physical obscuration (rain, fog, dirt)
│      ├─ Lens contamination detected?
│      │  ├─ YES → Alert: "Clean camera lens"
│      │  └─ Atmospheric (fog/rain)
│          ├─ Visibility < 100m?
│          │  ├─ YES → [FLIGHT VISIBILITY MINIMUM]
│          │   │   ├─ VLOS operation?
│          │   │   │  ├─ YES → Reduce range, maintain visual contact
│          │   │   │  └─ NO → BVLOS not permitted in these conditions
│          │   │   └─ Autonomous landing capability?
│          │   │       ├─ YES → GPS-based precision landing
│          │   │       └─ NO → Manual landing required
│          │   └─ NO → Continue with degraded visual performance
│
END: Vision source switched OR degraded operation mode active
```

#### Recovery Procedures

**Sensor Fallback Hierarchy**:
1. Visual-Inertial Odometry (primary)
2. Optical Flow + IMU (reduced accuracy)
3. GPS + IMU (lowest accuracy, always available)

**Operational Limits**:
```python
VISION_QUALITY_THRESHOLDS = {
    "min_features": 50,
    "min_quality_percent": 50,
    "max_position_uncertainty_m": 5.0,
    "max_velocity_uncertainty_ms": 1.0,
    "min_luminance": 20,
    "max_luminance": 230
}
```

---

## 3. Control Failures

### 3.1 Offboard Mode Rejection

**Severity**: CRITICAL  
**Detection Latency**: 100ms  
**Typical Trigger**: Preconditions not met, mode switch blocked

#### Symptoms
- `offboard.start()` returns failure
- PX4 rejects mode switch command
- Vehicle remains in previous mode (POSCTL, HOLD)
- NACK received for mode change request

#### Decision Tree
```
START: Offboard Mode Switch Failed
│
├─ Rejection Cause Analysis
│  ├─ Vehicle armed?
│  │  ├─ NO → [ARMING REQUIRED]
│  │   │   ├─ Pre-arm checks passing?
│  │   │   │  ├─ YES → Arm vehicle, retry offboard
│  │   │   │  └─ NO → [PRE-ARM FAILURE]
│  │   │   │       ├─ Check system health:
│  │   │   │       │   ├─ Sensor calibration valid?
│  │   │   │       │   ├─ GPS lock adequate?
│  │   │   │       │   ├─ Battery > minimum?
│  │   │   │       │   └─ EKF position estimate valid?
│  │   │   │       └─ Fix failing checks, then arm
│  │
│  ├─ Offboard setpoints being received?
│  │  ├─ NO → [NO SETPOINTS]
│  │   │   ├─ Start sending valid setpoints BEFORE mode switch
│  │   │   ├─ Setpoint rate > 2Hz (PX4 requirement)
│  │   │   └─ Setpoint type valid (position/velocity/attitude)
│  │   │   └─ Retry mode switch after 100ms of valid setpoints
│  │
│  ├─ RC loss / Safety switch active?
│  │  ├─ YES → [SAFETY INTERLOCK]
│  │   │   ├─ RC failsafe configured for offboard?
│  │   │   │  ├─ YES → Verify RC link or disable RC checks (risk assessment)
│  │   │   │  └─ NO → Cannot enter offboard without RC backup
│  │   │   ├─ Safety switch engaged?
│  │   │   │  ├─ YES → Disengage safety switch
│  │   │   │  └─ NO → Check parameter COM_OBL_RC_ACT
│  │
│  ├─ Flight termination active?
│  │  ├─ YES → [FLIGHT TERMINATION]
│  │   │   └─ Cannot recover - vehicle disabled
│  │
│  └─ EKF position estimate invalid?
│      ├─ YES → [NO POSITION ESTIMATE]
│       │   ├─ GPS lock quality
│       │   ├─ Vision position valid?
│       │   └─ Wait for valid position estimate
│
├─ Retry Strategy
│  ├─ Attempt 1: Fix identified issue, retry immediately
│  ├─ Attempt 2: Re-initialize MAVSDK connection, retry
│  ├─ Attempt 3: Reboot autopilot (if safe/landed)
│  └─ Fallback: Use POSITION mode with manual override
│
END: Offboard active OR fallback mode engaged
```

#### Recovery Procedures

**Preconditions Checklist**:
```python
OFFBOARD_PREREQUISITES = [
    "vehicle_armed == True",
    "valid_position_estimate == True",
    "offboard_setpoints_active == True",
    "setpoint_rate_hz >= 2.0",
    "rc_failsafe_configured OR rc_link_active",
    "safety_switch_off == True",
    "flight_termination_off == True"
]
```

**PX4 Parameters**:
```
COM_OBL_RC_ACT = 0  # RC loss action: 0=position mode, 1=terminate
COM_OBL_ACT = 0     # Offboard loss action: 0=hold, 1=land, 2=RTL
COM_RCL_EXCEPT = 4  # RC loss exceptions (bitmask)
```

---

### 3.2 Setpoint Timeout Edge Cases

**Severity**: HIGH  
**Detection Latency**: 500ms (COM_OF_LOSS_T)  
**Typical Trigger**: Control loop lag, network jitter, computation delay

#### Symptoms
- PX4 drops to HOLD mode mid-flight
- `setpoint_timeout` in PX4 logs
- Vehicle stops responding to new commands
- Intermittent: works sometimes, fails others

#### Decision Tree
```
START: Setpoint Timeout Detected
│
├─ Timeout Pattern Analysis
│  ├─ Single timeout event?
│  │  ├─ YES → [TRANSIENT ISSUE]
│  │   │   ├─ Network jitter > 500ms?
│  │   │   │  ├─ YES → Increase timeout tolerance (temporarily)
│  │   │   │   │   └─ param set COM_OF_LOSS_T 1.0  (from 0.5)
│  │   │   │   └─ NO → Application lag
│  │   │   │       └─ Profile control loop latency
│  │   │   └─ Setpoint stream restored?
│  │   │       ├─ YES → Resume normal operation
│  │   │       └─ NO → Check setpoint generation
│  │
│  ├─ Repeated timeouts?
│  │  ├─ YES → [SYSTEMIC ISSUE]
│  │   │   ├─ Setpoint generation rate check
│  │   │   │  ├─ < 2Hz? → [CRITICAL]
│  │   │   │   │   └─ Fix: Increase generation rate or use setpoint queue
│  │   │   │  └─ 2-10Hz? → Marginal
│  │   │   │      └─ Increase to minimum 10Hz recommended
│  │   │   │  └─ > 10Hz? → Healthy rate
│  │   │   │      └─ Check for burstiness (irregular intervals)
│  │   │   ├─ Network path analysis
│  │   │   │  ├─ Latency spikes > 200ms?
│  │   │   │  │  ├─ YES → Enable traffic shaping, prioritize MAVLink
│  │   │   │  │  └─ NO → Check MAVLink buffering
│  │   │   │  └─ Packet loss causing gaps?
│  │   │   │      ├─ YES → See Section 1.2 (Intermittent Packet Loss)
│  │   │
│  ├─ Timeout duration analysis
│  │  ├─ < 1s → Brief glitch, auto-recover
│  ├─ 1-5s → PX4 HOLD mode engaged
│  │  ├─ > 5s → Failsafe escalation (LAND or RTL per COM_OBL_ACT)
│  │
│  └─ Recovery action
│      ├─ PX4 in HOLD mode → Re-send setpoints, re-activate offboard
│      ├─ PX4 in LAND mode → Can abort if altitude permits
│      └─ PX4 in RTL → Override with manual mode or new offboard session
│
END: Setpoint stream stable OR failsafe mode active
```

#### Recovery Procedures

**Prevention**:
```python
# Control loop timing requirements
SETPOINT_REQUIREMENTS = {
    "min_rate_hz": 10,           # Minimum healthy rate
    "max_interval_ms": 100,       # Maximum gap between setpoints
    "buffer_size": 5,            # Setpoint queue for smoothing
    "timeout_margin_ms": 200     # Safety margin below PX4 timeout
}

# Adaptive timeout adjustment
px4_timeout_ms = get_com_of_loss_t() * 1000
our_send_interval_ms = 1000 / setpoint_rate_hz
safety_margin = px4_timeout_ms - our_send_interval_ms

if safety_margin < 200:
    increase_setpoint_rate()
    or_increase_px4_timeout(com_of_loss_t + 0.5)
```

---

### 3.3 PX4 Mode Transition Failures

**Severity**: HIGH  
**Detection Latency**: 500ms  
**Typical Trigger**: Invalid state transitions, preconditions not met

#### Symptoms
- Mode switch command acknowledged but not executed
- Vehicle in unexpected mode
- NACK or no response to mode change
- Transition succeeds but immediately reverts

#### Decision Tree
```
START: Mode Transition Failed
│
├─ Transition Validity Check
│  ├─ Is transition allowed per state machine?
│  │  ├─ NO → [INVALID TRANSITION]
│  │   │   ├─ Current mode → Target mode
│  │   │   │  ├─ LANDED → OFFBOARD? NO (must arm first)
│  │   │   │  ├─ STABILIZE → OFFBOARD? NO (arm required)
│  │   │   │  ├─ ACRO → POSCTL? YES (valid)
│  │   │   │  ├─ OFFBOARD → AUTO? YES (valid)
│  │   │   │  └─ Any → OFFBOARD? Only if armed + setpoints
│  │   │   └─ Required intermediate steps:
│  │   │       ├─ Unarmed target → Arm first
│  │   │       ├─ Offboard target → Send setpoints first
│  │   │       └─ Auto mission target → Upload mission first
│  │
│  ├─ Mode reversion after switch?
│  │  ├─ YES → [IMMEDIATE REVERSION]
│  │   │   ├─ Precondition lost during transition?
│  │   │   │  ├─ GPS lost while entering POSCTL?
│  │   │   │  ├─ RC lost while entering manual mode?
│  │   │   │  └─ Setpoints stopped while in offboard?
│  │   │   ├─ Health check failure during transition
│  │   │   │  └─ Fix underlying issue, retry
│  │
│  ├─ Mode command not acknowledged?
│  │  ├─ YES → [COMMAND FAILURE]
│  │   │   ├─ MAVLink link healthy?
│  │   │   │  ├─ NO → See Section 1.x (Network failures)
│  │   │   │  ├─ YES → Command sequence number correct?
│  │   │   │  │  ├─ NO → Reset command counter
│  │   │   │  │  └─ YES → PX4 not accepting commands (reboot required?)
│  │
│  └─ Specific mode issues
│      ├─ OFFBOARD fails → Check Section 3.1
│      ├─ AUTO fails → Check mission valid, geofence
│      ├─ RTL fails → Check home position set, GPS
│      └─ LAND fails → Usually succeeds (ultimate failsafe)
│
END: Valid mode transition OR identified blocking issue
```

#### Recovery Procedures

**Safe Mode Transition Sequences**:
```
Ground Start:      DISARMED → ARM → STABILIZE/ACRO → POSCTL → OFFBOARD
In-Flight Change:  OFFBOARD → POSCTL (safe) → OFFBOARD (resume)
Emergency:         ANY → LAND (always permitted when armed)
Failsafe:          ANY → RTL (if home position set)
```

**Mode Monitoring**:
```python
target_mode = FlightMode.OFFBOARD
max_retries = 3
retry_delay_ms = 500

for attempt in range(max_retries):
    result = await px4.set_flight_mode(target_mode)
    if result.success:
        await asyncio.sleep(0.1)  # Allow transition
        current = await px4.get_flight_mode()
        if current == target_mode:
            return ModeSwitchResult.SUCCESS
    await asyncio.sleep(retry_delay_ms / 1000)

return ModeSwitchResult.FAILED
```

---

### 3.4 Actuator Saturation

**Severity**: HIGH (can lead to loss of control)  
**Detection Latency**: Real-time  
**Typical Trigger**: Extreme attitudes, high winds, mechanical limits

#### Symptoms
- Motor outputs at 0% or 100% for > 100ms
- Control loops fighting (integrator windup)
- Desired vs actual attitude divergence
- "Twitching" or oscillation in one axis

#### Decision Tree
```
START: Actuator Saturation Detected
│
├─ Saturation Analysis
│  ├─ Which actuators saturated?
│  │  ├─ Throttle (all motors at limit)
│  │   │   ├─ Upper saturation (100%)
│  │   │   │  ├─ Cause: Maximum climb rate exceeded?
│  │   │   │  │  ├─ YES → Reduce climb rate demand
│  │   │   │  │  │   └─ Increase maximum collective if mechanically safe
│  │   │   │  │  └─ NO → Check for motor/ESC failure
│  │   │   │  │      ├─ One motor at 100%, others lower?
│  │   │   │  │      │  ├─ YES → [MOTOR FAILURE]
│  │   │   │  │      │   │   └─ Activate motor failure handling
│  │   │   │  │      │   │       ├─ Hex/Octo: Continue flight degraded
│  │   │   │  │      │   │       └─ Quad: Emergency landing required
│  │   │   │  │      └─ NO → All motors at limit
│  │   │   │          └─ Reduce demands or land
│  │   │   │
│  │   │   └─ Lower saturation (0%)
│  │   │       ├─ Maximum descent rate exceeded?
│  │   │       │  ├─ YES → Reduce descent rate (ground effect risk)
│  │   │       │  └─ NO → Check for propeller clipping
│  │   │       └─ In descent landing?
│  │   │           ├─ YES → Expected near touchdown
│  │   │           └─ NO → Reduce negative climb demand
│  │
│  ├─ Individual motor saturation (yaw/pitch/roll mixing)
│  │  ├─ Roll saturation (left/right motors at opposite limits)
│  │   │   ├─ Aggressive roll rate demanded?
│  │   │   │  ├─ YES → Reduce max roll rate / acceleration
│  │   │   │  └─ NO → Check CG imbalance
│  │   │   │      ├─ Asymmetric mass distribution?
│  │   │   │      │  ├─ YES → Re-trim or redistribute payload
│  │   │   │      └─ Mechanical issue (bent arm, different props)?
│  │   │   │          ├─ YES → Land and inspect
│  │   │   │          └─ NO → Wind gust compensation
│  │
│  ├─ Saturation duration
│  │  ├─ < 500ms → Transient, monitor
│  │  ├─ 500ms-2s → Reduce aggressiveness
│  │  └─ > 2s → [PERSISTENT SATURATION]
│  │      ├─ Reduce control gains temporarily
│  │      ├─ Limit maximum rates/accelerations
│  │      └─ If flight-critical → Land immediately
│
├─ Recovery Actions
│  ├─ Immediate: Reduce commanded rates/accelerations
│  ├─ Integrator reset: Clear windup in PID controllers
│  ├─ Gain scheduling: Reduce P/I gains when near limits
│  └─ Emergency: Land if saturation prevents stable flight
│
END: Saturation resolved OR emergency landing initiated
```

#### Recovery Procedures

**Saturation Detection**:
```python
SATURATION_THRESHOLDS = {
    "motor_min": 0.05,      # 5% - near minimum
    "motor_max": 0.95,      # 95% - near maximum
    "duration_critical_ms": 2000,
    "duration_warning_ms": 500
}

def check_saturation(motor_outputs: List[float]) -> SaturationStatus:
    max_output = max(motor_outputs)
    min_output = min(motor_outputs)

    if max_output > SATURATION_THRESHOLDS["motor_max"]:
        return SaturationStatus.UPPER
    elif min_output < SATURATION_THRESHOLDS["motor_min"]:
        return SaturationStatus.LOWER
    return SaturationStatus.NONE
```

**Gain Reduction**:
```python
if saturation_detected:
    # Temporary gain reduction to prevent windup
    mc_pitchrate_p *= 0.8
    mc_pitchrate_i *= 0.5
    mc_rollrate_p *= 0.8
    mc_rollrate_i *= 0.5
    alert_operator("Actuator saturation - gains reduced")
```

---

## 4. LLM Failures

### 4.1 Hallucinated Tool Calls

**Severity**: CRITICAL  
**Detection Latency**: Real-time (per call)  
**Typical Trigger**: LLM generates invalid function calls, wrong parameters

#### Symptoms
- Function name doesn't exist in registry
- Parameters outside valid ranges (e.g., altitude < 0)
- Missing required parameters
- Type mismatches (string vs number)

#### Decision Tree
```
START: Tool Call Validation
│
├─ Function Name Validation
│  ├─ Function name in registered_tools?
│  │  ├─ NO → [HALLUCINATED FUNCTION]
│  │   │   ├─ Similar name exists? (fuzzy match)
│  │   │   │  ├─ YES → Suggest correction: "Did you mean 'hover_drone'?"
│  │   │   │   │   └─ Log hallucination pattern for model tuning
│  │   │   │  └─ NO → Reject with: "Function 'X' not available"
│  │   │   │      └─ Available functions: [list valid options]
│  │   │   ├─ Log hallucination event
│  │   │   └─ Do NOT execute fallback - safety risk
│  │   └─ YES → Continue to parameter validation
│
├─ Parameter Schema Validation
│  ├─ Required parameters present?
│  │  ├─ NO → [MISSING PARAMETERS]
│  │   │   ├─ Ask LLM to provide missing: altitude, duration, etc.
│  │   │   └─ If critical parameter missing → Reject call
│  │
│  ├─ Parameter types correct?
│  │  ├─ NO → [TYPE MISMATCH]
│  │   │   ├─ Attempt coercion (safe conversions only)
│  │   │   │  ├─ String "10" → Number 10: YES (safe)
│  │   │   │  ├─ Number 10 → String "10": YES (safe)
│  │   │   │  ├─ Invalid string "abc" → Number: NO (unsafe)
│  │   │   │   │   └─ Reject: "Invalid value for altitude"
│  │   │   │  └─ Null/undefined required param: NO (unsafe)
│  │   │   │      └─ Reject with parameter name
│  │
│  ├─ Parameter values in valid ranges?
│  │  ├─ NO → [RANGE VIOLATION]
│  │   │   ├─ Safety-critical parameter?
│  │   │   │  ├─ YES → Clamp to safe range, log warning
│  │   │   │   │   ├─ Altitude < 0 → Clamp to 2m (safety floor)
│  │   │   │   │   ├─ Speed > max → Clamp to max_speed
│  │   │   │   │   └─ Position outside geofence → Clamp to boundary
│  │   │   │  └─ NO → Reject and explain valid range
│  │
│  └─ Enum values valid?
│      ├─ NO → [INVALID ENUM]
│       │   └─ Reject with: "Invalid mode. Valid: [STABILIZE, POSCTL, OFFBOARD]"
│
├─ Safety Constraint Validation
│  ├─ Would execution violate geofence?
│  │  ├─ YES → Reject: "Target outside authorized flight area"
│  ├─ Would execution exceed altitude limit?
│  │  ├─ YES → Reject: "Target exceeds maximum altitude"
│  ├─ Would execution enter no-fly zone?
│  │  ├─ YES → Reject: "Cannot navigate to restricted area"
│  └─ Battery sufficient for commanded action?
│      ├─ NO → Reject: "Insufficient battery for requested operation"
│
END: Tool call validated OR rejected with clear error
```

#### Recovery Procedures

**Validation Pipeline**:
```python
class ToolValidator:
    def validate(self, tool_call: dict) -> ValidationResult:
        # 1. Function exists
        func_name = tool_call.get("name")
        if func_name not in self.registry:
            return ValidationResult.fail(f"Unknown function: {func_name}")

        # 2. Schema validation
        schema = self.registry[func_name].schema
        try:
            validate(instance=tool_call["parameters"], schema=schema)
        except ValidationError as e:
            return ValidationResult.fail(f"Invalid parameters: {e.message}")

        # 3. Safety constraints
        constraints = self.registry[func_name].safety_constraints
        violation = constraints.check(tool_call["parameters"])
        if violation:
            return ValidationResult.fail(f"Safety violation: {violation}")

        return ValidationResult.pass_()
```

**Hallucination Patterns to Watch**:
- Function names: `fly_to`, `goto`, `move_drone` (wrong names)
- Parameter hallucinations: `speed_of_sound`, `quantum_mode`
- Non-existent drone IDs or positions

---

### 4.2 Infinite Loops in Reasoning

**Severity**: HIGH  
**Detection Latency**: 10-60s  
**Typical Trigger**: Circular logic, unbounded iteration, contradictory constraints

#### Symptoms
- Repeated identical or similar tool calls
- No progress toward goal after N attempts
- Oscillating between same states/decisions
- LLM response exceeds token limit repeatedly

#### Decision Tree
```
START: Detect Reasoning Loop
│
├─ Loop Detection Patterns
│  ├─ Identical tool call sequence repeated?
│  │  ├─ YES → [EXACT LOOP]
│  │   │   ├─ Sequence length: N calls
│  │   │   ├─ Repeats: M times
│  │   │   └─ Pattern: [hover] → [move_north] → [hover] → [move_south] → ...
│  │   │       ├─ Opposing commands? (move_north vs move_south)
│  │   │       │  ├─ YES → Goal conflict detected
│  │   │       │   │   └─ Clarify with user: "You requested both N and S movement"
│  │   │       │  └─ NO → Stuck on obstacle
│  │   │       │      └─ Escalate: "Unable to reach target, obstacle detected"
│  │
│  ├─ Similar but not identical calls (fuzzy loop)?
│  │  ├─ YES → [CONVERGENCE FAILURE]
│  │   │   ├─ Actions converging toward same state?
│  │   │   │  ├─ YES → Optimization stuck in local minimum
│  │   │   │   │   └─ Randomize or use different strategy
│  │   │   │  └─ NO → Progress too slow
│  │   │   │      └─ Timeout approaching?
│  │   │   │          ├─ YES → Escalate to human
│  │   │   │          └─ NO → Continue with progress monitoring
│  │
│  ├─ Token limit exhaustion?
│  │  ├─ YES → [CONTEXT OVERFLOW]
│  │   │   ├─ Conversation history too long?
│  │   │   │  ├─ YES → Summarize and compress history
│  │   │   │   │   └─ Retain: goal, current state, key decisions
│  │   │   │   │   └─ Discard: intermediate reasoning, failed attempts
│  │   │   │  └─ NO → Single response too verbose
│  │   │   │      └─ Request concise response, limit max_tokens
│  │
│  └─ Time-based loop detection
│      ├─ No progress in last T seconds?
│      │  ├─ YES → [TIMEOUT LOOP]
│      │   │   ├─ Interrupt and ask: "How can I help you proceed?"
│      │   │   └─ Offer: reset, simplify goal, or human takeover
│
├─ Loop Recovery Strategies
│  ├─ Strategy 1: Break symmetry
│  │  └─ Add randomization or different approach
│  ├─ Strategy 2: Goal simplification
│  │  └─ Reduce scope: "Let's start with just hovering first"
│  ├─ Strategy 3: Constraint relaxation
│  │  └─ Remove conflicting requirements temporarily
│  ├─ Strategy 4: State reset
│  │  └─ Clear conversation, restart with current state summary
│  └─ Strategy 5: Human escalation
│      └─ "I'm having difficulty with this task. Would you like to take over?"
│
END: Loop broken OR human intervention requested
```

#### Recovery Procedures

**Loop Detection Metrics**:
```python
LOOP_DETECTION = {
    "max_similar_calls": 3,        # Same call pattern limit
    "similarity_threshold": 0.9,    # Jaccard/sequence similarity
    "max_time_without_progress": 30,  # Seconds
    "max_token_exhaustions": 2,     # Before summarization
    "action_history_size": 10       # For pattern matching
}

def detect_loop(action_history: List[Action]) -> Optional[LoopType]:
    # Check for exact cycles
    for cycle_len in range(2, len(action_history) // 2 + 1):
        if is_cyclic(action_history, cycle_len):
            return LoopType.EXACT_CYCLE

    # Check for convergence (actions becoming more similar)
    if convergence_score(action_history) > LOOP_DETECTION["similarity_threshold"]:
        return LoopType.CONVERGENCE

    # Check time without state change
    if time_since_last_state_change() > LOOP_DETECTION["max_time_without_progress"]:
        return LoopType.TIMEOUT

    return None
```

---

### 4.3 JSON Parsing Failures

**Severity**: HIGH  
**Detection Latency**: Real-time  
**Typical Trigger**: Malformed LLM output, encoding issues, truncation

#### Symptoms
- `json.loads()` throws exception
- Missing closing braces/brackets
- Invalid escape sequences
- Truncated output (mid-value)

#### Decision Tree
```
START: JSON Parse Failed
│
├─ Error Type Analysis
│  ├─ Unexpected end of input (truncation)?
│  │  ├─ YES → [TRUNCATION]
│  │   │   ├─ Can detect valid prefix?
│  │   │   │  ├─ YES → Attempt to complete
│  │   │   │   │   └─ Add missing closing: ], }, "
│  │   │   │   │   └─ Validate partial reconstruction
│  │   │   │  └─ NO → Request regeneration
│  │   │   └─ Cause: max_tokens too low?
│  │   │       ├─ YES → Increase max_tokens, retry
│  │   │       └─ NO → Output naturally long, use compression
│  │
│  ├─ Invalid escape sequence?
│  │  ├─ YES → [ENCODING ISSUE]
│  │   │   ├─ Common: newlines in strings, unescaped quotes
│  │   │   └─ Fix: Pre-process with escape function
│  │   │       ├─ Replace raw newlines with \n
│  │   │       ├─ Escape unescaped quotes
│  │   │       └─ Remove control characters
│  │
│  ├─ Invalid character / encoding?
│  │  ├─ YES → [ENCODING CORRUPTION]
│  │   │   ├─ UTF-8 decode error?
│  │   │   │  ├─ YES → Use 'replace' or 'ignore' error handler
│  │   │   │  └─ NO → Binary data in output?
│  │   │   │      └─ Sanitize: keep only printable ASCII + UTF-8
│  │
│  ├─ Schema mismatch?
│  │  ├─ YES → [STRUCTURE ERROR]
│  │   │   ├─ Expected object, got array?
│  │   │   ├─ Missing required keys?
│  │   │   └─ Type errors (string vs number)?
│  │   │       └─ Attempt repair OR reject and request fix
│  │
│  └─ Completely unparseable?
│      ├─ YES → [TOTAL FAILURE]
│       │   ├─ Extract intent with regex (emergency fallback)
│       │   │  ├─ Partial extraction succeeds?
│       │   │   │  ├─ YES → Execute with extracted data, warn user
│       │   │   │  └─ NO → Reject and request reformatted output
│       │   └─ Log for prompt engineering review
│
├─ Recovery Strategy Selection
│  ├─ Auto-repairable? → Apply fix, validate, proceed
│  ├─ Needs regeneration? → Increase max_tokens, retry
│  ├─ Pattern detected? → Update prompt template
│  └─ Unrecoverable? → Clear error to user, request manual input
│
END: JSON parsed OR graceful degradation applied
```

#### Recovery Procedures

**Progressive Parsing Strategy**:
```python
import json
import re

def robust_parse(llm_output: str) -> dict:
    # Attempt 1: Direct parse
    try:
        return json.loads(llm_output)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Truncation repair
    repaired = attempt_completion(llm_output)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Attempt 3: Sanitize and parse
    sanitized = sanitize_json(llm_output)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # Attempt 4: Extract tool call with regex (emergency)
    emergency = extract_tool_call_regex(llm_output)
    if emergency:
        return emergency

    raise JSONParseFailure("All parsing attempts failed")

def attempt_completion(partial: str) -> str:
    # Count open braces/brackets
    opens = partial.count('{') + partial.count('[')
    closes = partial.count('}') + partial.count(']')

    # Add missing closing characters
    while opens > closes:
        if partial.rstrip()[-1] in ['"', '']:
            partial += '"'
        partial += '}' if '{' in partial else ']'
        closes += 1

    return partial
```

---

### 4.4 Safety Override Confusion

**Severity**: CRITICAL  
**Detection Latency**: Real-time  
**Typical Trigger**: LLM misunderstands safety system responses

#### Symptoms
- LLM attempts to override safety limits
- LLM ignores or questions safety rejections
- LLM generates commands that bypass validation
- User and LLM in conflict over safety

#### Decision Tree
```
START: Safety Override Attempt Detected
│
├─ Override Attempt Classification
│  ├─ LLM explicitly requests bypass?
│  │  ├─ YES → [EXPLICIT OVERRIDE REQUEST]
│  │   │   ├─ Justification provided?
│  │   │   │  ├─ YES → [EVALUATE JUSTIFICATION]
│  │   │   │   │   ├─ Emergency situation (immediate danger)?
│  │   │   │   │   │  ├─ YES → [EMERGENCY PROTOCOL]
│  │   │   │   │   │   │   ├─ Human explicitly authorized?
│  │   │   │   │   │   │   │  ├─ YES → Log exception, execute with monitoring
│  │   │   │   │   │   │   │   │   └─ Require: operator_id, timestamp, justification
│  │   │   │   │   │   │   │   └─ NO → Cannot bypass, offer alternatives
│  │   │   │   │   │   │   │       └─ Emergency landing, manual mode, etc.
│  │   │   │   │   │   └─ NO → Not an emergency
│  │   │   │   │   │       └─ Reject: "Safety limits cannot be overridden"
│  │   │   │   └─ NO → [NO JUSTIFICATION]
│  │   │       └─ Reject with explanation of safety constraint
│  │
│  ├─ LLM rephrases request to avoid trigger?
│  │  ├─ YES → [CIRCUMVENTION ATTEMPT]
│  │   │   ├─ Semantic equivalence check
│  │   │   │  ├─ Same outcome as blocked request?
│  │   │   │   │  ├─ YES → Reject: "This request has the same effect as the blocked action"
│  │   │   │   │  └─ NO → Different request, evaluate normally
│  │   │   └─ Log pattern for policy review
│  │
│  ├─ LLM confused by safety rejection?
│  │  ├─ YES → [EDUCATION OPPORTUNITY]
│  │   │   ├─ Explain constraint clearly
│  │   │   ├─ Offer alternative approaches
│  │   │   └─ Clarify that safety system is absolute
│  │
│  └─ User overriding LLM with unsafe request?
│      ├─ YES → [USER OVERRIDE]
│       │   ├─ User explicitly accepts liability?
│       │   │  ├─ YES → Log, require confirmation code, execute
│       │   │  └─ NO → Maintain safety block
│
├─ Safety System Response
│  ├─ Absolute constraints (never override):
│  │   ├─ Geofence violations
│  │   ├─ Altitude ceiling
│  │   ├─ No-fly zones
│  │   └─ Actuator saturation limits
│  ├─ Overrideable with authorization:
│  │   ├─ Speed limits (emergency response)
│  │   ├─ Battery reserve (critical mission)
│  │   └─ Range limits (search and rescue)
│  └─ Soft constraints (can be adjusted):
│      ├─ Conservative landing margins
│      ├─ Extra verification steps
│      └─ Notification frequency
│
END: Safety maintained OR authorized exception logged
```

#### Recovery Procedures

**Safety Override Protocol**:
```python
SAFETY_LEVELS = {
    "ABSOLUTE": {"overridable": False},  # Geofence, altitude
    "CRITICAL": {"overridable": True, "requires": ["human_auth", "emergency_code"]},
    "ADVISORY": {"overridable": True, "requires": ["acknowledgment"]},
}

def handle_override_request(request: SafetyRequest) -> Response:
    constraint = get_safety_constraint(request)

    if constraint.level == "ABSOLUTE":
        return Response.reject(
            "This safety limit cannot be overridden under any circumstances. "
            "Alternative: [suggest safe alternative]"
        )

    if constraint.level == "CRITICAL":
        if request.has_human_authorization() and request.emergency_code_valid():
            log_security_event("SAFETY_OVERRIDE_EXECUTED", request)
            return Response.allow_with_monitoring(constraint)
        return Response.reject(
            "This action requires emergency authorization. "
            "Contact supervisor and provide incident code."
        )

    # Advisory - can be adjusted
    return Response.allow_with_adjustment(constraint, request.modified_parameters)
```

---

## 5. Recovery Procedures

### 5.1 Fail-safe to Manual

**Trigger**: Critical system failure, operator request, safety violation  
**Goal**: Transfer control to human operator immediately

#### Decision Tree
```
START: Fail-safe to Manual Initiated
│
├─ Current State Assessment
│  ├─ In flight?
│  │  ├─ NO (on ground) → Disarm immediately
│  │   │   └─ Log event, await manual inspection
│  │
│  ├─ YES (in flight) → [FLIGHT MANUAL TRANSFER]
│  │   ├─ RC link active?
│  │   │  ├─ YES → [RC HANDOVER]
│  │   │   │   ├─ Signal quality > 50%?
│  │   │   │   │  ├─ YES → Switch to POSCTL mode
│  │   │   │   │   │   └─ Announce: "RC control active"
│  │   │   │   │   └─ NO → [WEAK RC]
│  │   │   │       ├─ Range < 100m?
│  │   │   │       │  ├─ YES → Operator should move closer
│  │   │   │       │  └─ NO → Switch to ALTCTL (less demanding)
│  │   │   │       └─ Monitor closely, prepare emergency landing
│  │   │   │
│  │   │   └─ Gamepad/Companion computer manual mode?
│  │   │       ├─ YES → Activate direct manual control
│  │   │       └─ NO → RC required for manual
│  │   │
│  │   ├─ NO RC link → [NO MANUAL LINK]
│  │   │   ├─ Autonomous landing possible?
│  │   │   │  ├─ YES → Activate precision landing
│  │   │   │   │   ├─ GPS + Baro healthy?
│  │   │   │   │   │  ├─ YES → GPS landing at home position
│  │   │   │   │   │  └─ NO → Optical flow/rangefinder landing
│  │   │   │   └─ Monitor descent, prepare for emergency
│  │   │   │
│  │   │   └─ GPS precision landing available?
│  │   │       ├─ YES → LAND mode at home position
│  │   │       └─ NO → [EMERGENCY LANDING REQUIRED]
│  │   │           └─ See Section 5.2
│
├─ Mode Transition Execution
│  ├─ From OFFBOARD → POSCTL (if RC) or LAND (autonomous)
│  ├─ From AUTO → POSCTL (if RC) or LAND
│  ├─ From any → STABILIZE (last resort manual)
│  └─ Set LED pattern: Manual mode indicator
│
├─ Post-Transfer Actions
│  ├─ Continuous telemetry to ground station
│  ├─ Reduced automation assistance (if requested)
│  └─ Standby for operator commands
│
END: Manual control active OR autonomous landing initiated
```

#### Procedure Details

**RC Handover Checklist**:
1. Verify RC transmitter powered on
2. Verify RC mode switch in POSCTL position
3. Confirm signal strength > 50%
4. Command mode switch to POSCTL
5. Announce handover complete
6. Monitor for 10s to confirm stable control

**Without RC**:
1. Activate LAND mode with home position
2. Reduce descent rate to 1 m/s maximum
3. Monitor altitude and ground proximity
4. At 2m altitude: Slow to 0.5 m/s
5. At touchdown: Disarm after 1s ground contact

---

### 5.2 Emergency Landing

**Trigger**: Critical failure, low battery, loss of control, safety violation  
**Goal**: Land vehicle safely at current location or home position

#### Decision Tree
```
START: Emergency Landing Initiated
│
├─ Landing Site Selection
│  ├─ Home position reachable AND safe?
│  │  ├─ YES → [RTL LANDING]
│  │   │   ├─ Battery sufficient for RTL + landing?
│  │   │   │  ├─ YES → Execute RTL
│  │   │   │   │   └─ Climb to RTL_ALT (if below)
│  │   │   │   │   └─ Navigate to home position
│  │   │   │   │   └─ Descend at home position
│  │   │   │   └─ NO → [DIRECT LANDING - Insufficient battery]
│  │
│  ├─ Current location suitable for landing?
│  │  ├─ YES → [LAND NOW]
│  │   │   ├─ LAND mode available?
│  │   │   │  ├─ YES → Activate LAND
│  │   │   │   │   └─ Controlled descent at current position
│  │   │   │   └─ NO → [MANUAL DESCENT]
│  │   │       ├─ Use POSITION mode with zero velocity
│  │   │       ├─ Reduce altitude gradually
│  │   │       └─ Disarm at touchdown
│  │   │
│  │   └─ Precision landing available?
│  │       ├─ YES → Use GPS + rangefinder for accuracy
│  │       └─ NO → GPS-only landing (accuracy ~3-5m)
│  │
│  └─ Current location unsuitable (water, obstacle, crowd)?
│      ├─ YES → [ALTERNATE LANDING SITE]
│       │   ├─ Nearest safe area identified?
│       │   │  ├─ YES → Navigate to safe area, then land
│       │   │   │   └─ May require brief RTL then offset
│       │   │  └─ NO → [FORCED LANDING]
│       │   │      ├─ Choose least dangerous option
│       │   │      ├─ Minimize horizontal velocity
│       │   │      ├-> Reduce descent rate as much as possible
│       │   │      └─ Alert emergency services if in populated area
│
├─ Landing Execution
│  ├─ Descent Phase
│  │   ├─ Altitude > 10m: Descent rate 2 m/s
│  │   ├─ Altitude 5-10m: Descent rate 1 m/s
│  │   ├─ Altitude 2-5m: Descent rate 0.5 m/s
│  │   └─ Altitude < 2m: Descent rate 0.3 m/s, ground effect compensation
│  │
│  ├─ Abort Conditions (during descent)
│  │   ├─ Obstacle detected → Ascend 5m, reassess
│  │   ├─ Wind shear detected → Pause descent, stabilize
│  │   └─ RC recovered → Allow operator abort/redirect
│  │
│  └─ Touchdown Detection
│      ├─ Landing detector: Velocity < 0.3 m/s AND altitude stable
│      ├─ Barometer: Pressure increase sustained
│      ├─ IMU: Z-acceleration spike (impact)
│      └─ Disarm: 1s after touchdown confirmation
│
├─ Post-Landing
│  ├─ Disarm motors
│  ├─ Stop propellers
│  ├─ Save flight log and blackbox
│  ├─ Alert operator: "Emergency landing complete at [location]"
│  └─ Enter post-flight safe state
│
END: Vehicle landed and disarmed OR abort to alternate
```

#### PX4 Parameters for Emergency Landing

```
MPC_LAND_SPEED = 0.7          # m/s - Maximum descent rate
MPC_LAND_ALT1 = 10.0          # m - Slow down altitude 1
MPC_LAND_ALT2 = 5.0           # m - Slow down altitude 2
MPC_LAND_ALT3 = 1.0           # m - Final approach altitude
COM_DISARM_LAND = 2.0         # s - Auto-disarm after landing
LNDMC_Z_VEL_MAX = 0.50        # m/s - Max vertical velocity for landing
LNDMC_XY_VEL_MAX = 1.5        # m/s - Max horizontal velocity for landing
```

---

### 5.3 In-Air Restart Procedures

**Trigger**: Critical software failure, watchdog timeout, operator command  
**Goal**: Restart flight software while maintaining vehicle stability

#### Decision Tree
```
START: In-Air Restart Required
│
├─ Restart Type Determination
│  ├─ Companion computer only (PX4 healthy)?
│  │  ├─ YES → [COMPANION RESTART]
│  │   │   ├─ PX4 in stable mode (POSCTL/HOLD/ALTCTL)?
│  │   │   │  ├─ YES → Safe to restart companion
│  │   │   │   │   └─ Switch PX4 to HOLD mode
│  │   │   │   │   └─ Restart companion software
│  │   │   │   │   └─ PX4 continues on last setpoint (HOLD)
│  │   │   │   │   └─ Reconnect MAVSDK after restart
│  │   │   │   │   └─ Resume control if desired
│  │   │   │   └─ NO → [PX4 NOT STABLE]
│  │   │       ├─ Can switch to stable mode first?
│  │   │       │  ├─ YES → Switch, then restart
│  │   │       │  └─ NO → Cannot restart - unstable
│  │
│  ├─ PX4 reboot required?
│  │  ├─ YES → [AUTOPILOT RESTART - EXTREME RISK]
│  │   │   ├─ Vehicle type?
│  │   │   │  ├─ Fixed-wing → Glide path possible
│  │   │   │   │   └─ Navigate to landing zone before reboot
│  │   │   │   │   └─ Reboot in-air only as last resort
│  │   │   │   └─ Multicopter → [QUAD/HEXA/OCTO REBOOT]
│  │   │       ├─ Hardware supports in-air restart?
│  │   │       │  ├─ YES → Some FCUs maintain PWM during reboot
│  │   │       │   │   └─ Set HOLD throttle before reboot
│  │   │       │   │   └─ Reboot duration < 5s?
│  │   │       │   │       ├─ YES → May maintain attitude
│  │   │       │   │       └─ NO → Fall
│  │   │       │   └─ NO → [IN-AIR REBOOT IMPOSSIBLE]
│  │   │           ├─ Must land before reboot
│  │   │           └─ Emergency landing (see 5.2)
│  │
│  ├─ Hot-swapping to backup companion?
│  │  ├─ YES → [BACKUP ACTIVATION]
│  │   │   ├─ Backup system healthy?
│  │   │   │  ├─ YES → Switch MAVLink to backup
│  │   │   │   │   └─ Backup takes control seamlessly
│  │   │   │   └─ NO → Primary must stay active
│  │   │   └─ Dual-system architecture required
│  │
│  └─ Partial restart (process level)?
│      ├─ YES → [PROCESS RESTART]
│       │   ├─ Restart specific service (LLM, vision, etc.)
│       │   ├─ Core control process stays running
│       │   └─ Graceful handover maintained
│
├─ Pre-Restart Checklist
│  ├─ Vehicle in stable flight condition
│  ├─ Altitude > 20m (margin for recovery)
│  ├─ Battery > 30% (post-restart reserve)
│  ├─ GPS lock solid (recovery navigation)
│  ├─ RC link active (human backup)
│  └─ Landing site identified (if restart fails)
│
├─ Post-Restart Actions
│  ├─ Verify all systems initialized
│  ├─ Check sensor health
│  ├─ Re-establish position estimate
│  ├─ Re-engage control gradually
│  └─ Resume mission or RTL
│
END: Restart successful OR emergency landing initiated
```

#### Critical Warning

**Multicopter PX4 Reboot**:  
Most flight controllers will **lose attitude control** during reboot. This is only viable if:
1. FCU maintains PWM output during boot (rare)
2. Reboot completes in < 3 seconds
3. Vehicle is high enough to recover after free-fall
4. Recovery altitude is sufficient for EKF re-initialization

**Recommended**: Always land before rebooting PX4 on multicopters.

---

### 5.4 Ground Abort Procedures

**Trigger**: Pre-flight failure detection, unsafe conditions, operator decision  
**Goal**: Prevent takeoff, safe shutdown on ground

#### Decision Tree
```
START: Ground Abort Initiated
│
├─ Abort Phase
│  ├─ Pre-arm checks failing?
│  │  ├─ YES → [PRE-FLIGHT ABORT]
│  │   │   ├─ Which check failed?
│  │   │   │  ├─ Calibration → Re-calibrate, retry
│  │   │   │  ├─ GPS → Wait for better lock / check antenna
│  │   │   │  ├─ Battery → Replace/charge battery
│  │   │   │  ├─ Sensor → Inspect, replace if damaged
│  │   │   │  ├─ Configuration → Fix parameters, retry
│  │   │   │  └─ EKF → Check sensor fusion, reboot
│  │   │   └─ Log: Preflight failure reason
│  │
│  ├─ During arming sequence?
│  │  ├─ YES → [ARMING ABORT]
│  │   │   ├─ Disarm immediately
│  │   │   ├─ Secure vehicle (props spinning?)
│  │   │   ├─ Check: Why did we abort?
│  │   │   │   ├─ Unintended arm? → Check stick positions
│  │   │   │   ├─ Anomaly detected? → Investigate
│  │   │   │   └─ Operator abort? → Clear command
│  │   │   └─ Return to disarmed state
│  │
│  ├─ Post-arm, pre-takeoff?
│  │  ├─ YES → [HOLD ABORT]
│  │   │   ├─ Currently in ARMED but not flying
│  │   │   ├─ Immediate disarm
│  │   │   ├─ Log abort reason
│  │   │   └─ Inspect before retry
│  │
│  └─ Takeoff initiated but not airborne?
│      ├─ YES → [TAKEOFF ABORT]
│       │   ├─ Motors at takeoff throttle?
│       │   │  ├─ YES → Reduce throttle to idle
│       │   │  ├─ Props spinning → Disarm when safe
│       │   │  └─ Vehicle tipping/skidding?
│       │   │      ├─ YES → Emergency disarm (risk of damage)
│       │   │      └─ NO → Controlled disarm
│       │   └─ Secure vehicle, investigate cause
│
├─ Post-Abort Investigation
│  ├─ Check system logs for anomalies
│  ├─ Verify all sensor health
│  ├─ Check for physical issues (props, wiring)
│  ├─ Battery voltage under load
│  └─ Environmental factors (wind, ground condition)
│
├─ Return to Service Decision
│  ├─ Issue identified and resolved?
│  │  ├─ YES → Retry preflight, proceed if passing
│  │  └─ NO → [MAINTENANCE REQUIRED]
│      ├─ Safe to retry?
│      │  ├─ YES → Retry with additional monitoring
│      │  └─ NO → Ground vehicle, maintenance required
│
END: Vehicle safe OR retry authorized
```

#### Pre-Arm Check Failures Reference

| Check | Common Causes | Resolution |
|-------|---------------|------------|
| COMPASS | Calibration drift, interference | Re-calibrate, move from metal |
| GPS | Poor lock, < 8 sats, high HDOP | Wait, check antenna, check sky view |
| BATTERY | Low voltage, high current draw | Charge, check connections, load test |
| AIRSPEED | Sensor not calibrated, tubing issue | Calibrate, check pitot tube |
| EKF | Bad position/velocity estimate | Reboot, check GPS, wait for convergence |
| RC | No signal, failsafe active | Power on TX, check binding, range check |
| CONFIG | Missing parameters, version mismatch | Update firmware, load defaults |

---

## Appendix A: Failure Mode Severity Matrix

| Failure Mode | Severity | Detection | Recovery Time | Prevention |
|-------------|----------|-----------|---------------|------------|
| WiFi Drop | CRITICAL | 100ms-2s | 5-30s | Dual-band, directional antenna |
| Packet Loss | HIGH | 50ms | Real-time | FEC, redundant links |
| Half-Open | HIGH | 5-30s | 5s | TCP keepalive, watchdog |
| GPS Spoofing | CRITICAL | 1-5s | 10-60s | Multi-sensor validation |
| Mag Interference | HIGH | Real-time | 5-30s | External mag, calibration |
| Baro Ground Effect | MEDIUM | 2-10s | 2s | Rangefinder priority |
| Camera Obscuration | MEDIUM | Real-time | Variable | Multi-sensor fusion |
| Offboard Rejection | CRITICAL | 100ms | 1-30s | Precondition checklist |
| Setpoint Timeout | HIGH | 500ms | 500ms | 10Hz+ setpoint stream |
| Mode Transition Fail | HIGH | 500ms | 5s | State machine validation |
| Actuator Saturation | HIGH | Real-time | 1-5s | Gain scheduling, margins |
| Hallucinated Tool | CRITICAL | Real-time | N/A | Schema validation |
| Reasoning Loop | HIGH | 10-60s | Variable | Loop detection |
| JSON Parse Fail | HIGH | Real-time | 1s | Progressive parsing |
| Safety Confusion | CRITICAL | Real-time | N/A | Clear constraints |

## Appendix B: Quick Reference Decision Cards

### Emergency: Loss of Connection in Offboard
```
1. Setpoint timeout? → PX4 → HOLD mode (automatic)
2. Connection restored < 5s? → Resume offboard
3. Connection restored 5-30s? → Re-engage offboard after health check
4. Connection > 30s? → RTL initiated
5. No RTL possible? → LAND at current position
```

### Emergency: GPS Failure
```
1. GPS lost? → Check backup sources
2. Optical flow available? → Use OF + IMU
3. IMU only? → Dead reckoning (30s limit)
4. > 30s GPS loss? → Activate failsafe
5. Altitude > RTL_MIN? → RTL (estimated position)
6. Altitude < RTL_MIN? → LAND (estimated position)
```

### Emergency: LLM Control Failure
```
1. Invalid tool call? → Reject, explain error
2. Hallucination pattern? → Log, request clarification
3. Reasoning loop? → Detect, offer reset or simplify
4. Safety override attempt? → Block, explain constraint
5. User request override? → Require explicit authorization
6. Complete failure? → Fail-safe to manual/land
```

---

## Document Control

**Version**: 1.0  
**Author**: Claude  
**Date**: 2025-04-09  
**Classification**: Technical Reference  
**Distribution**: Project Avatar Development Team

**Review Schedule**: Quarterly or after incident  
**Related Documents**:
- `failsafe.md` - PX4 failsafe configuration
- `performance_optimization.md` - Latency and throughput tuning
- `mavsdk_px4_deep_dive.md` - Interface specifications

---

## References

1. PX4 Failsafe Documentation: https://docs.px4.io/main/en/config/safety.html
2. MAVSDK Offboard Control: https://mavsdk.mavlink.io/main/en/cpp/guide/offboard.html
3. MAVLink Command Protocol: https://mavlink.io/en/services/command.html
4. EKF2 Estimation System: https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html
5. Drone Safety Standards: ASTM F3061, ISO 21384
