# Drone Failsafe Hierarchy Design

## Project Avatar - Safety Systems Architecture

**Date:** 2026-04-09  
**Version:** 1.0  
**Classification:** Safety-Critical Design Document

---

## Executive Summary

This document defines the complete failsafe hierarchy for Project Avatar, a Raspberry Pi 5-based LLM-driven drone control system running on PX4. The design implements a **4-layer safety architecture** with clear priority ordering, state transitions, and recovery procedures.

---

## Part 1: PX4 Failsafe Priorities (Native Layer)

### 1.1 Severity Hierarchy (Most Severe First)

When multiple failsafes trigger simultaneously, PX4 selects the **most severe** action:

| Priority | Severity Level | Actions |
|----------|---------------|---------|
| 1 | **Flight Termination** | Kill motors immediately (parachute deploy if equipped) |
| 2 | **Disarm** | Cut motor power, descend under any remaining lift |
| 3 | **Land Mode** | Controlled descent to ground at current position |
| 4 | **Return Mode (RTL)** | Navigate to home position, then land |
| 5 | **Hold Mode (Loiter)** | Hover in place at current position |
| 6 | **Warning** | Alert operator, continue current operation |
| 7 | **None/Disabled** | No action taken |

### 1.2 Failsafe Trigger Matrix

| Failsafe Type | Trigger Condition | Primary Parameter | Action Options |
|---------------|-------------------|-------------------|----------------|
| **Battery Critical** | Capacity < BAT_EMERGEN_THR | COM_LOW_BAT_ACT | Warning → Return → Land |
| **Battery Low** | Capacity < BAT_LOW_THR | COM_LOW_BAT_ACT | Warning → Return → Land |
| **RC Loss** | No signal > COM_RC_LOSS_T | NAV_RCL_ACT | Disabled, Loiter, Return, Land, Disarm, Terminate |
| **Geofence Breach** | Exceed GF_MAX_HOR_DIST / GF_MAX_VER_DIST | GF_ACTION | None, Warning, Hold, Return, Terminate, Land |
| **Offboard Loss** | No MAVLink > COM_OF_LOSS_T | COM_OBL_RC_ACT | Position, Altitude, Manual, Return, Land, Hold |
| **Data Link Loss** | No GCS heartbeat > COM_DL_LOSS_T | NAV_DLL_ACT | Hold, Return, Land, Terminate, Disarm |
| **Mission Failure** | Navigation error | N/A | RTL or Land |
| **High Wind** | Wind speed > threshold | COM_WIND_WARN | Warning, Return, Land |
| **Position Loss** | GPS/position estimate invalid | COM_POSCTL_NAVL | Altitude, Manual, Land |

### 1.3 Critical PX4 Parameters

```yaml
# Offboard Failsafe Configuration
COM_OBL_RC_ACT: 3        # Action when offboard lost (0=Position, 3=Return, 4=Land)
COM_OF_LOSS_T: 0.5        # Timeout in seconds before offboard failsafe (default: 0.5)

# RC Loss Configuration  
COM_RC_LOSS_T: 0.5        # Timeout before RC loss declared (seconds)
NAV_RCL_ACT: 2            # RC loss action (0=Disabled, 2=Return, 3=Land, 5=Terminate)
COM_RCL_EXCEPT: 4         # Ignore RC loss in specific modes (bitmask: 4=Offboard)

# Battery Failsafe
BAT_LOW_THR: 0.25         # Low battery threshold (25%)
BAT_CRIT_THR: 0.15        # Critical battery threshold (15%)
BAT_EMERGEN_THR: 0.10    # Emergency battery threshold (10%)
COM_LOW_BAT_ACT: 2        # Low battery action (1=Return, 2=Land)

# Geofence
GF_MAX_HOR_DIST: 1000     # Max horizontal distance from home (m)
GF_MAX_VER_DIST: 150      # Max vertical distance from home (m)
GF_ACTION: 3              # Geofence breach action (3=Return, 4=Terminate, 5=Land)

# Data Link Loss
COM_DL_LOSS_T: 10         # Data link timeout (seconds)
NAV_DLL_ACT: 2            # Data link loss action (1=Hold, 2=Return, 3=Land)

# Delay Before Action
COM_FAIL_ACT_T: 0.5       # Delay before failsafe action execution
```

### 1.4 Multiple Trigger Resolution

When multiple failsafes activate simultaneously, PX4 applies **severity escalation**:

```
Example Scenarios:
- RC Loss (Return) + Battery Low (Land) → Land (more severe)
- Geofence Breach (Return) + Battery Critical (Land) → Land
- Offboard Loss (Position) + RC Loss (Return) → Return
- Any failsafe + Flight Termination → Terminate
```

**Key Rule:** The failsafe system continuously evaluates all conditions and executes the highest-severity active action.

---

## Part 2: Layered Safety Architecture

### 2.1 Layer 1: PX4 Hard Reflexes (Unconditional)

**Purpose:** Hardware-level safety that cannot be overridden by software

| Component | Trigger | Response | Overrideable |
|-----------|---------|----------|--------------|
| **Watchdog Timer** | System freeze > 500ms | Disarm motors | No |
| **Hard Limits** | Roll/Pitch > 60°, Yaw rate > 180°/s | Attitude limit enforcement | No |
| **Hardware Failsafe** | PWM signal loss on all channels | Pre-programmed RTL | No |
| **Catastrophic Battery** | Voltage < 3.0V/cell | Immediate disarm | No |
| **Motor Failure Detection** | RPM deviation > 30% | Emergency protocols | No |

**Characteristics:**
- Execute in flight controller firmware
- Latency: < 10ms
- No RPi/LLM involvement
- Always take precedence over all other layers

### 2.2 Layer 2: Guardian Process (RPi-Based)

**Purpose:** Intelligent monitoring and intervention running on Raspberry Pi 5

| Guardian Module | Monitors | Trigger Conditions | Actions |
|-----------------|----------|-------------------|---------|
| **Heartbeat Monitor** | LLM process, PX4 connection | No heartbeat > 2s | Initiate RTL |
| **Command Validator** | LLM MAVLink commands | Velocity > 15m/s, Altitude < 2m, Distance > 500m | Reject + Alert |
| **State Consistency** | PX4 reported state vs expected | Discrepancy > 3s | Initiate Hold |
| **VIO Sanity Check** | Visual odometry data | Sudden position jump > 10m | Switch to GPS |
| **Resource Monitor** | RPi CPU/Temp/Memory | CPU > 90%, Temp > 80°C, RAM > 95% | Graceful degradation |
| **Network Monitor** | WiFi/Companion Link | Connection loss > 5s | Initiate RTL |

**Guardian State Machine:**
```
NORMAL ──[anomaly detected]──> GUARDED ──[escalation]──> INTERVENTION
   ↑                              │                           │
   └────────[all clear]──────────┘────────[manual recovery]──┘
```

**Guardian Actions by Severity:**

| Level | Condition | Guardian Action | PX4 Command |
|-------|-----------|-----------------|-------------|
| 1 | Minor anomaly | Log, alert operator | None |
| 2 | Moderate risk | Override LLM commands | Change to Hold mode |
| 3 | Significant risk | Disable LLM input | Initiate RTL |
| 4 | Critical risk | Emergency intervention | Initiate Land mode |
| 5 | Catastrophic | Last resort | Disarm (if safe altitude) |

### 2.3 Layer 3: LLM Reactions (Conditional)

**Purpose:** Intelligent adaptive responses based on context and scenario analysis

**LLM Authority Scope:**

| Action Type | LLM Authority | Conditions |
|-------------|---------------|------------|
| **Navigation** | Full | Within geofence, battery > 30%, clear airspace |
| **Speed Control** | Limited | Max 10m/s (guardian override at 15m/s) |
| **Altitude Changes** | Limited | Min 5m AGL, max 120m AGL |
| **Mission Planning** | Full | Pre-approved waypoint sets only |
| **Emergency RTL** | None | Guardian/PX4 only |
| **Land Now** | None | Guardian/PX4 only |
| **Mode Changes** | Limited | Position, Hold allowed; Manual requires authorization |

**LLM Decision Triggers:**

```yaml
Weather Response:
  - Wind > 12 m/s: Reduce max speed, consider RTL
  - Visibility < 100m: Initiate immediate RTL
  - Precipitation detected: Land at nearest safe site

Traffic Response:
  - Aircraft detected within 500m: Hold position, await clearance
  - Collision course predicted: Execute evasive maneuver (within limits)

Battery Response:
  - Battery < 35%: Begin return planning
  - Battery < 25%: Initiate RTL immediately
  - Battery < 20%: Request emergency landing site

Navigation Response:
  - GPS degradation: Switch to VIO primary
  - VIO failure: Switch to GPS, reduce speed
  - Both degraded: Initiate emergency hold, assess RTL viability
```

### 2.4 Layer 4: Operator Override (RC)

**Purpose:** Human-in-the-loop ultimate authority

| Control Method | Priority | Conditions |
|---------------|----------|------------|
| **RC Mode Switch** | Absolute | Any mode switch immediately active |
| **GCS Override** | High | MAVLink mode change command accepted |
| **Emergency Stop** | Absolute | Physical kill switch on RC |
| **Geofence Override** | Conditional | Requires explicit authorization code |

**RC Override Hierarchy:**

```
1. KILL SWITCH (Aux channel)
   └─ Immediate disarm, all other commands ignored

2. MODE SWITCH (Main switch)
   └─ Position / Altitude / Manual / RTL / Land / Hold
   └─ Overrides all autonomous/LLM commands

3. FLIGHT MODES (Individual switches)
   └─ Mission / Offboard / Return / Follow Me
   
4. GCS COMMANDS
   └─ Mode changes, waypoints, RTL commands
   └─ Can be disabled via COM_GCS_EN parameter
```

---

## Part 3: Decision Matrices

### 3.1 RTL vs Land vs Hold Decision Matrix

| Scenario | Battery | RC Status | Position Valid | Decision |
|----------|---------|-----------|----------------|----------|
| Normal operation | > 35% | Connected | Yes | Continue mission |
| RC lost, good battery | > 35% | Lost | Yes | RTL |
| RC lost, low battery | 20-35% | Lost | Yes | RTL (expedited) |
| RC lost, critical battery | < 20% | Lost | Yes | Land immediately |
| Geofence breach, good conditions | > 35% | Connected | Yes | RTL |
| Geofence breach, low battery | < 25% | Connected | Yes | Land at nearest safe |
| Position lost, GPS degraded | > 35% | Connected | Degraded | Hold, attempt recovery |
| Position lost completely | > 35% | Connected | No | Land (manual takeover) |
| LLM anomaly detected | > 35% | Connected | Yes | Guardian: Hold → Assess |
| High wind + low battery | < 30% | Connected | Yes | Land immediately |
| Multiple failures | Any | Any | Any | Most severe action |

### 3.2 LLM Input vs Safety Override Matrix

| Condition | LLM Input | Guardian Action | PX4 Action |
|-----------|-----------|-----------------|------------|
| Normal flight | Accepted | Monitor | Execute |
| Command exceeds limits | Rejected | Alert operator | Ignore |
| LLM process crash | N/A | Initiate RTL | Execute RTL |
| LLM suggests unsafe action | Overridden | Block + Alert | Execute safe alternative |
| Guardian-LLM conflict | Overridden | Authority | Follow Guardian |
| RPi resource exhaustion | Ignored | Initiate RTL | Execute RTL |
| Network latency > 500ms | Queued | Monitor | Continue last valid |
| VIO divergence detected | Filtered | Request correction | Reduced trust weight |

### 3.3 Recovery Procedures

**From RTL State:**
```
Entry: Any failsafe triggers RTL
During RTL: 
  - Monitor battery consumption to home
  - If battery < 15% during RTL: Switch to Land immediately
  - If home position invalid: Land at current position
Exit:
  - Automatic: Arrival at home + landing complete
  - Manual: Operator switches to Position/Manual mode
  - Abort: Guardian/LLM commands alternative if battery permits
```

**From Land State:**
```
Entry: Critical battery, operator command, or waypoint reached
During Land:
  - Descent at 1-2 m/s (terrain dependent)
  - Monitor for ground contact
  - Cannot be aborted below 5m AGL
Exit:
  - Automatic: Disarm on ground detection
  - Emergency: Operator kill switch
```

**From Hold State:**
```
Entry: Temporary anomaly, operator command, or LLM request
During Hold:
  - Maintain position with GPS + barometer
  - Guardian monitors for escalation
  - LLM may plan next action
Exit:
  - Automatic: Resume mission (if applicable)
  - Manual: Operator mode change
  - Escalation: Guardian initiates RTL if condition persists > 60s
```

**From Emergency/Disarm:**
```
Entry: Catastrophic failure or kill switch
Post-Disarm:
  - Log all flight data
  - Alert operator with location
  - Initiate recovery beacon if equipped
Recovery:
  - Manual inspection required
  - Root cause analysis before next flight
  - System health check mandatory
```

### 3.4 Manual Mode Priority

**Manual Mode Override Conditions:**

| Trigger | Auto-Activation | Pilot Authority |
|---------|-----------------|-----------------|
| RC signal restored after loss | Yes (if COM_RCL_EXCEPT allows) | Full |
| LLM command rejected > 3x | Alert only | Pilot decides |
| Guardian intervention | Alert + Status | Pilot can override Guardian |
| Operator switch flip | Yes | Immediate |
| GCS mode command | Yes | Immediate |

**Manual Mode Precedence:**
```
1. Physical RC transmitter (always wins if active)
2. GCS joystick/control (if enabled)
3. Autonomous systems (LLM + Guardian)
```

---

## Part 4: Complete State Machine

### 4.1 High-Level System States

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROJECT AVATAR STATE MACHINE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────┐
                              │  INIT    │
                              └────┬─────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
              ┌─────────┐    ┌──────────┐   ┌──────────┐
              │ ARMED   │    │  DISARM  │   │  ERROR   │
              └────┬────┘    └──────────┘   └──────────┘
                   │
        ┌──────────┼──────────┬──────────┬──────────┐
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐
   │MANUAL  │ │POSITION│ │OFFBOARD │ │  RTL   │ │  LAND   │
   │(RC)    │ │(GPS)   │ │(LLM)    │ │        │ │         │
   └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬────┘
        │          │          │          │          │
        └──────────┴──────────┴──────────┴──────────┘
                              │
                              ▼
                        ┌──────────┐
                        │  HOLD    │
                        │ (Loiter) │
                        └────┬─────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   EMERGENCY    │
                    │ (Terminate/    │
                    │   Disarm)      │
                    └────────────────┘
```

### 4.2 Detailed State Transitions

#### State: INIT
```yaml
Entry: Power on, system boot
Actions:
  - Initialize sensors
  - Load parameters
  - Establish RPi <-> PX4 link
  - Start LLM process
  - Start Guardian process
Valid Transitions:
  - DISARM: All systems nominal
  - ERROR: Critical failure detected
Exit: System ready for arming
```

#### State: DISARMED
```yaml
Entry: From INIT or after landing
Actions:
  - Log flight summary
  - Allow parameter changes
  - Monitor battery charge
Valid Transitions:
  - ARMED: Pre-flight checks passed + operator command
  - ERROR: System fault detected
```

#### State: ARMED
```yaml
Entry: Operator arm command + all checks passed
Actions:
  - Enable motor control
  - Initialize flight modes
  - Activate all failsafe monitors
Valid Transitions:
  - MANUAL: RC mode switch
  - POSITION: Mode switch / LLM request
  - OFFBOARD: LLM activation command
  - ERROR: Critical system failure
  - DISARMED: Operator disarm
```

#### State: MANUAL (RC)
```yaml
Entry: RC mode switch or manual override
Actions:
  - Direct stick-to-servo mapping
  - LLM inputs ignored
  - Guardian monitors only
Valid Transitions:
  - POSITION: Operator mode change
  - OFFBOARD: Operator authorization + LLM ready
  - RTL: Operator command or failsafe
  - LAND: Operator command
  - DISARMED: On ground + disarm command
Triggers:
  - RC Loss → RTL (unless COM_RCL_EXCEPT)
  - Kill Switch → DISARMED (emergency)
```

#### State: POSITION (GPS)
```yaml
Entry: Mode switch from any armed state
Actions:
  - Position hold via GPS
  - Velocity commands accepted
  - LLM inputs accepted (if enabled)
Valid Transitions:
  - MANUAL: RC override
  - OFFBOARD: LLM activation
  - HOLD: Temporary stop
  - RTL: Failsafe or command
  - LAND: Command or failsafe
Triggers:
  - Position Loss → Altitude mode → Land
  - Battery Low → RTL
  - Geofence Breach → RTL
```

#### State: OFFBOARD (LLM)
```yaml
Entry: LLM sends offboard activation command
Actions:
  - Accept MAVLink setpoints from RPi
  - Guardian validates all commands
  - LLM processes vision + plans actions
Valid Transitions:
  - POSITION: LLM release or Guardian override
  - MANUAL: RC override (immediate)
  - RTL: Offboard loss timeout / failsafe
  - HOLD: LLM request temporary hold
  - LAND: LLM request landing
Triggers:
  - Offboard Loss (COM_OF_LOSS_T): → COM_OBL_RC_ACT (default: RTL)
  - RC Loss: → RTL (if COM_RCL_EXCEPT off)
  - Guardian Intervenes: → POSITION or RTL
  - LLM Crash: Guardian → RTL after 2s
```

#### State: RTL (Return to Launch)
```yaml
Entry: Failsafe trigger or operator command
Actions:
  - Navigate to home position
  - Climb to RTL altitude if needed
  - Land at home when reached
Valid Transitions:
  - LAND: Home reached or battery critical
  - POSITION: Operator override (if safe)
  - MANUAL: RC override (if safe)
  - DISARMED: Landing complete
Interrupts:
  - Battery < BAT_CRIT_THR during RTL: → LAND immediately
  - New failsafe (higher severity): → That action
```

#### State: LAND
```yaml
Entry: Failsafe, operator command, or RTL completion
Actions:
  - Controlled descent
  - Monitor ground contact
  - Prepare for disarm
Valid Transitions:
  - DISARMED: Ground detected + timeout
  - POSITION: Abort above 5m (operator only)
Non-Interruptible:
  - Below 5m AGL: Must complete landing
```

#### State: HOLD (Loiter)
```yaml
Entry: Operator command, LLM request, or temporary failsafe
Actions:
  - Maintain position/altitude
  - Monitor all systems
  - Await further instructions
Valid Transitions:
  - Any flight mode: Operator, LLM, or Guardian
Timeout:
  - > 60s in Hold: Guardian may escalate to RTL
```

#### State: EMERGENCY
```yaml
Entry: Catastrophic failure, kill switch, flight termination
Actions:
  - Immediate disarm or parachute
  - Log black box data
  - Alert operator
Valid Transitions:
  - DISARMED: After impact/ground contact
  - ERROR: Recovery assessment
Final State: Requires manual reset
```

#### State: ERROR
```yaml
Entry: Unrecoverable system fault
Actions:
  - Log fault codes
  - Notify operator
  - Safe state if possible
Valid Transitions:
  - DISARMED: If ground-safe
  - EMERGENCY: If in-flight
Recovery: Power cycle + diagnostic
```

### 4.3 Failsafe State Injection

**Any state can transition to failsafe states:**

```
Current State ──[trigger]──> Failsafe State

MANUAL ──[RC Loss]──────────> RTL
POSITION ──[Battery Low]────> RTL
OFFBOARD ──[LLM Crash]──────> RTL (via Guardian)
OFFBOARD ──[Offboard Loss]──> RTL (PX4 native)
ANY ──[Geofence]────────────> RTL (or Terminate if severe)
ANY ──[Kill Switch]─────────> EMERGENCY (Disarm)
ANY ──[Critical Battery]────> LAND
ANY ──[Position Loss]───────> ALTITUDE ──[continue loss]──> LAND
```

---

## Part 5: Implementation Parameters

### 5.1 Recommended PX4 Configuration

```ini
# Safety Configuration for Project Avatar

# RC Failsafe
COM_RC_LOSS_T: 0.5           # Quick detection
NAV_RCL_ACT: 2               # Return mode on RC loss
COM_RCL_EXCEPT: 4            # Ignore RC loss in Offboard (we handle via Guardian)

# Offboard Failsafe
COM_OBL_RC_ACT: 3            # Return mode (RTL) when offboard lost
COM_OF_LOSS_T: 0.5           # 500ms timeout
COM_FAIL_ACT_T: 0.5          # 500ms delay before action

# Battery Failsafe
BAT_LOW_THR: 0.30            # Conservative 30% low
BAT_CRIT_THR: 0.20           # 20% critical
BAT_EMERGEN_THR: 0.10        # 10% emergency
COM_LOW_BAT_ACT: 2           # Land on low battery

# Geofence
GF_ACTION: 3                 # Return mode on breach
GF_MAX_HOR_DIST: 500         # 500m radius
GF_MAX_VER_DIST: 120         # 120m altitude

# Data Link
COM_DL_LOSS_T: 5.0           # 5 second tolerance
NAV_DLL_ACT: 2               # Return mode

# Position Loss
COM_POSCTL_NAVL: 0           # Altitude mode first
```

### 5.2 Guardian Implementation Specs

```python
# Guardian Process Core Logic
guardian_config = {
    "heartbeat_interval": 1.0,        # Check LLM every 1 second
    "offboard_timeout": 2.0,            # Initiate RTL after 2s no LLM heartbeat
    "command_limits": {
        "max_velocity_xy": 10.0,        # m/s
        "max_velocity_z": 3.0,          # m/s
        "max_acceleration": 5.0,        # m/s^2
        "min_altitude_agl": 5.0,        # meters above ground
        "max_distance_home": 500.0,     # meters from home
    },
    "escalation_matrix": {
        "level_1": "log_and_alert",
        "level_2": "reject_command",
        "level_3": "assume_control_hold",
        "level_4": "initiate_rtl",
        "level_5": "initiate_land",
        "level_6": "emergency_disarm"    # Only if altitude < 10m
    },
    "resource_thresholds": {
        "cpu_percent": 90,
        "memory_percent": 95,
        "temperature_c": 80,
        "disk_percent": 90
    }
}
```

### 5.3 LLM Safety Constraints

```yaml
# LLM Operational Boundaries
llm_constraints:
  velocity:
    nominal_max: 8.0 m/s
    hard_limit: 15.0 m/s          # Guardian rejects beyond
    override: 10.0 m/s            # LLM self-limits to

  altitude:
    min_agl: 5.0 m                # Never below
    max_agl: 120.0 m              # Regulatory + safety
    hover_preference: 10-30 m     # Normal ops

  distance:
    max_from_home: 400.0 m        # Normal mission
    rtl_planning_start: 300.0 m   # Consider return
    hard_limit: 500.0 m           # Geofence

  battery_response:
    plan_rtl: 35%
    initiate_rtl: 25%
    emergency_land: 15%

  timeout_requirements:
    command_interval: 0.2 s         # 5Hz minimum update
    guardian_heartbeat: 1.0 s       # Guardian health check
    acknowledge_window: 2.0 s       # Command receipt window
```

---

## Part 6: Emergency Procedures

### 6.1 Pre-Flight Safety Checklist

```
□ Battery voltage > 4.0V/cell
□ GPS lock (3D fix minimum)
□ RC transmitter bound and responsive
□ Geofence configured and enabled
□ Failsafe parameters loaded
□ Guardian process running on RPi
□ LLM process responsive
□ VIO/GPS fusion active
□ Telemetry link to GCS active
□ Kill switch functional test
□ RTL path clear of obstacles
□ Emergency landing zones identified
```

### 6.2 In-Flight Emergency Responses

**Emergency Type: Total System Failure**
1. Guardian detects RPi/PX4 communication loss
2. After 2s: Guardian commands RTL via MAVLink
3. If no response: Operator manual RTL via RC
4. If RC unavailable: PX4 native failsafe takes over

**Emergency Type: LLM Hallucination/Rogue Commands**
1. Guardian detects velocity/altitude limit breach
2. Reject command, alert operator
3. If continues: Switch to Hold mode
4. If persists: Initiate RTL
5. Operator can override to Manual anytime

**Emergency Type: GPS/VIO Dual Failure**
1. PX4 switches to altitude mode (barometer only)
2. Guardian alerts operator
3. LLM attempts visual navigation if camera functional
4. If altitude mode unstable: Controlled land
5. Operator must take manual control

**Emergency Type: Mid-Flight Battery Failure**
1. PX4 battery failsafe triggers
2. If > 20%: RTL
3. If 15-20%: Expedited RTL (direct path, no climb)
4. If < 15%: Immediate land at current position
5. LLM suggests nearest safe landing zone if time permits

### 6.3 Post-Emergency Recovery

```
1. Assess vehicle condition
2. Download flight logs (ULog from PX4, Guardian logs from RPi)
3. Identify root cause
4. Implement corrective action
5. Safety review before next flight
6. Update failsafe parameters if needed
```

---

## Part 7: Validation & Testing

### 7.1 Simulation Test Cases

| Test ID | Scenario | Expected Outcome |
|---------|----------|------------------|
| F-001 | RC loss during offboard flight | RTL within 1 second |
| F-002 | LLM crash during mission | Guardian RTL within 2 seconds |
| F-003 | Battery critical at 300m distance | Land at nearest safe, not RTL |
| F-004 | Geofence breach during high wind | RTL + wind compensation |
| F-005 | Simultaneous RC loss + low battery | Land (more severe than RTL) |
| F-006 | Kill switch activation | Immediate disarm |
| F-007 | Guardian-LLM conflict | Guardian wins, operator notified |
| F-008 | GPS spoofing attack | Guardian detects, switch to VIO |
| F-009 | RPi thermal throttling | Guardian degrades LLM, maintains control |
| F-010 | Complete RPi failure | PX4 native failsafe RTL |

### 7.2 Flight Test Protocol

```
Phase 1: Tethered/Ground
  - Test all failsafe triggers
  - Verify parameter loading
  - Guardian integration test

Phase 2: Hover Box (5m altitude)
  - RC loss test
  - Manual override test
  - Kill switch test

Phase 3: Expanded Flight
  - Offboard mode test
  - LLM command limits test
  - Battery failsafe test (simulated)
  - Geofence test

Phase 4: Edge Cases
  - Dual GPS/VIO failure (simulated)
  - Communication degradation
  - Multiple simultaneous failures
```

---

## Appendix A: Parameter Quick Reference

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| COM_OBL_RC_ACT | 0 | 3 | Offboard loss → RTL |
| COM_OF_LOSS_T | 0.5 | 0.5 | 500ms offboard timeout |
| COM_RC_LOSS_T | 0.5 | 0.5 | 500ms RC loss timeout |
| NAV_RCL_ACT | 2 | 2 | RC loss → RTL |
| COM_RCL_EXCEPT | 0 | 4 | Ignore RC loss in Offboard |
| BAT_LOW_THR | 0.25 | 0.30 | 30% low threshold |
| BAT_CRIT_THR | 0.15 | 0.20 | 20% critical threshold |
| COM_LOW_BAT_ACT | 1 | 2 | Low battery → Land |
| GF_ACTION | 1 | 3 | Geofence → RTL |
| GF_MAX_HOR_DIST | - | 500 | 500m radius |
| COM_DL_LOSS_T | 10 | 5 | 5s data link timeout |
| NAV_DLL_ACT | 2 | 2 | Data link → RTL |

---

## Appendix B: Decision Flowchart

```
                    ┌─────────────────────┐
                    │  FLIGHT IN PROGRESS │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌──────────┐     ┌──────────┐     ┌──────────┐
       │RC Active │     │Anomaly   │     │Normal    │
       │          │     │Detected  │     │          │
       └────┬─────┘     └────┬─────┘     └────┬─────┘
            │                │                │
            ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │RC MODE SWITCH│  │GUARDIAN EVAL │  │LLM OPERATES  │
    │IMMEDIATE     │  │              │  │NORMAL MISSION│
    └──────┬───────┘  └──────┬───────┘  └──────────────┘
           │                 │
           │        ┌────────┴────────┐
           │        │                 │
           │        ▼                 ▼
           │  ┌──────────┐     ┌──────────┐
           │  │SEVERITY  │     │MINOR     │
           │  │HIGH      │     │          │
           │  └────┬─────┘     └────┬─────┘
           │       │                │
           │       ▼                ▼
           │  ┌──────────┐     ┌──────────┐
           │  │INITIATE  │     │LOG/ALERT │
           │  │FAILSAFE  │     │CONTINUE  │
           │  └──────────┘     └──────────┘
           │
           ▼
    ┌──────────────┐
    │MANUAL OVERRIDE│
    │TAKES PRECEDENCE│
    └──────────────┘
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-09 | Safety Systems Engineer | Initial release |

**Review Schedule:** Quarterly or after any safety incident
**Next Review:** 2026-07-09

---

*This document is part of Project Avatar safety certification package. All modifications require safety review approval.*
