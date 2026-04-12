# Safety Architecture Gap Analysis: Project Avatar

**Date:** 2026-04-11  
**Task:** #14 - Compare Guardian implementation vs required 4-layer safety architecture  
**Status:** CRITICAL GAPS IDENTIFIED

---

## Executive Summary

The current Guardian implementation is a basic prototype that implements only 20% of the required safety architecture. Critical missing components include the 20Hz heartbeat, state consistency monitoring, resource monitoring, and the escalation matrix. **This system is NOT flight-safe in its current state.**

---

## Required 4-Layer Architecture (from failsafe_hierarchy.md)

```
Layer 1: PX4 Hard Reflexes (<100ms) - Firmware-level, non-negotiable
Layer 2: Guardian Process (~10ms) - 20Hz heartbeat, state consistency, resource monitor
Layer 3: LLM Reactions (1-3s) - Intelligent adaptive responses
Layer 4: Operator Override (RC) - Human-in-the-loop ultimate authority
```

---

## Current Guardian Implementation Analysis

### File: `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mav/guardian.py`

**Current Implementation (Lines 1-234):**
- `HardLimits` dataclass (lines 15-27): altitude, distance, battery, heartbeat_timeout, speed
- `GuardianProcess` class (lines 30-233): basic validation and heartbeat tracking

### What IS Implemented (Working)

| Feature | Status | Notes |
|---------|--------|-------|
| Hard limits validation | **PARTIAL** | Only basic bounds checking |
| Heartbeat tracking | **PARTIAL** | Single timeout value only |
| Geofence (distance) | **YES** | Haversine calculation present |
| Home position mgmt | **YES** | set_home() method exists |
| Command validation | **PARTIAL** | altitude, distance, speed, battery |

---

## Layer-by-Layer Gap Analysis

### LAYER 1: PX4 Hard Reflexes (<100ms)

**Status:** Configuration-defined, not code-enforced

**Current State:**
- Guardian does NOT configure PX4 parameters
- No parameter validation at startup
- No MAVLink parameter write functionality

**Critical PX4 Parameters (MUST BE CONFIGURED):**

```yaml
# Offboard Loss Failsafe (CRITICAL)
COM_OBL_RC_ACT: 3           # Return mode on offboard timeout (0=Position, 3=Return, 4=Land)
COM_OF_LOSS_T: 0.5          # 500ms timeout before offboard failsafe triggers
COM_OBL_ACT: 1              # Hold mode if in Hold/Loiter when offboard lost

# RC Loss Protection
COM_RC_LOSS_T: 0.5          # 500ms RC timeout before failsafe
NAV_RCL_ACT: 2              # RC loss action (0=Disabled, 2=Return, 3=Land, 5=Terminate)
COM_RCL_EXCEPT: 4           # Ignore RC loss in Offboard mode (bitmask: 4=Offboard)

# Battery Failsafes
BAT_LOW_THR: 0.25           # Low battery threshold (25%)
BAT_CRIT_THR: 0.15          # Critical battery threshold (15%)
BAT_EMERGEN_THR: 0.10      # Emergency battery threshold (10%)
COM_LOW_BAT_ACT: 2          # Low battery action (1=Return, 2=Land)
COM_ARM_BAT_MIN: 0.40       # Minimum battery to arm (40%)

# Geofencing (Hard Envelope)
GF_MAX_HOR_DIST: 500        # Max horizontal distance from home (meters)
GF_MAX_VER_DIST: 120        # Max vertical distance from home (meters)
GF_ACTION: 3                # Geofence breach action (3=Return, 4=Terminate, 5=Land)
GF_ALTMODE: 0               # Check against absolute altitude

# Data Link Loss
COM_DL_LOSS_T: 5.0          # Data link timeout (seconds)
NAV_DLL_ACT: 2              # Data link loss action (1=Hold, 2=Return, 3=Land)

# Position Loss
COM_POSCTL_NAVL: 0          # Position loss nav mode (0=Altitude, 1=Manual, 2=Land)

# Pre-arm Checks
COM_ARM_MAG_ANG: 45         # Maximum compass heading error (degrees)
COM_ARM_MAG_STR: 0.15       # Maximum compass strength deviation
COM_ARM_EKF_VEL: 0.5        # Maximum EKF velocity variance
COM_ARM_EKF_POS: 0.5        # Maximum EKF position variance
COM_ARM_IMU_ACC: 0.15       # Maximum accelerometer inconsistency
COM_ARM_IMU_GYR: 0.25       # Maximum gyro inconsistency

# Delay Before Action
COM_FAIL_ACT_T: 0.5         # Delay before failsafe action execution
```

**Gap Severity:** CRITICAL
- No Layer 1 enforcement in Guardian
- No startup parameter verification
- No MAVLink interface to write safety parameters

---

### LAYER 2: Guardian Process (~10ms / 20Hz)

**Status:** PROTOTYPE - NOT PRODUCTION READY

#### Missing Component #1: 20Hz Heartbeat

**Required:**
- Heartbeat interval: 0.05s (50ms) for 20Hz
- Guardian must emit heartbeat at 20Hz
- Must monitor LLM process heartbeat at 20Hz
- Offboard timeout: 0.5s (10 missed heartbeats)

**Current Implementation:**
```python
# Lines 26, 69, 154-179 in guardian.py
heartbeat_timeout_s: float = 2.0  # WRONG: Should be 0.5s for offboard
_last_heartbeat: float = time.time()  # WRONG: No 20Hz timing
check_heartbeat()  # WRONG: 2-second timeout, not 50ms
```

**Implementation Requirements:**
```python
# Required additions:
GUARDIAN_HEARTBEAT_HZ = 20
GUARDIAN_HEARTBEAT_INTERVAL = 1.0 / GUARDIAN_HEARTBEAT_HZ  # 0.05s
OFFBOARD_TIMEOUT_S = 0.5  # 10 missed heartbeats

# Async heartbeat task
async def heartbeat_emitter(self):
    while self._running:
        self._emit_heartbeat()
        await asyncio.sleep(GUARDIAN_HEARTBEAT_INTERVAL)

async def heartbeat_monitor(self):
    while self._running:
        if time.time() - self._last_llm_heartbeat > OFFBOARD_TIMEOUT_S:
            await self._initiate_rtl("LLM heartbeat timeout")
        await asyncio.sleep(GUARDIAN_HEARTBEAT_INTERVAL)
```

**Gap Severity:** CRITICAL
- 2s timeout is 4x too long for offboard safety
- No 20Hz async loop structure
- No distinction between Guardian heartbeat and LLM heartbeat

---

#### Missing Component #2: State Consistency Monitor

**Required (from failsafe_hierarchy.md lines 119-122, 237-240):**
- Monitor PX4 reported state vs expected state
- Detect discrepancy > 3 seconds
- Action: Initiate Hold mode
- Check: armed/disarmed state, flight mode, position validity

**Current Implementation:** NONE

**Implementation Requirements:**
```python
@dataclass
class ExpectedState:
    armed: bool
    flight_mode: str
    timestamp: float

class GuardianProcess:
    def __init__(self):
        self._expected_state: Optional[ExpectedState] = None
        self._state_consistency_threshold_s = 3.0
        
    async def state_consistency_check(self, px4_state: DroneState):
        """Verify PX4 state matches expected state"""
        if self._expected_state is None:
            return True
            
        discrepancy_time = time.time() - self._expected_state.timestamp
        
        # Check armed state mismatch
        if px4_state.armed != self._expected_state.armed:
            if discrepancy_time > self._state_consistency_threshold_s:
                await self._initiate_hold("State inconsistency: armed mismatch")
                return False
                
        # Check flight mode mismatch
        if px4_state.flight_mode != self._expected_state.flight_mode:
            if discrepancy_time > self._state_consistency_threshold_s:
                await self._initiate_hold("State inconsistency: mode mismatch")
                return False
                
        return True
```

**Gap Severity:** HIGH
- No state tracking in current Guardian
- No expected vs actual comparison
- No discrepancy timeout handling

---

#### Missing Component #3: Resource Monitor

**Required (from failsafe_hierarchy.md lines 124, 611-618):**
- Monitor RPi CPU, Temperature, Memory
- Thresholds: CPU > 90%, Temp > 80°C, RAM > 95%
- Action: Graceful degradation or RTL

**Current Implementation:** NONE

**Implementation Requirements:**
```python
import psutil

@dataclass
class ResourceThresholds:
    cpu_percent: float = 90.0
    memory_percent: float = 95.0
    temperature_c: float = 80.0
    disk_percent: float = 90.0

class GuardianProcess:
    async def resource_monitor(self):
        """Monitor RPi resources and trigger degradation if needed"""
        while self._running:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.resource_thresholds.cpu_percent:
                await self._degrade_performance(f"CPU critical: {cpu_percent}%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > self.resource_thresholds.memory_percent:
                await self._initiate_rtl(f"Memory critical: {memory.percent}%")
            
            # Temperature (RPi-specific)
            temp = self._get_cpu_temperature()
            if temp > self.resource_thresholds.temperature_c:
                await self._degrade_performance(f"Temperature critical: {temp}°C")
            
            await asyncio.sleep(1.0)  # Check every second
    
    def _get_cpu_temperature(self) -> float:
        """Read RPi CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read()) / 1000.0
        except:
            return 0.0
```

**Gap Severity:** HIGH
- No resource monitoring in current code
- No graceful degradation logic
- No thermal protection for RPi5

---

#### Missing Component #4: VIO Sanity Check

**Required (from failsafe_hierarchy.md line 123):**
- Monitor Visual Odometry data
- Detect sudden position jump > 10m
- Action: Switch to GPS primary

**Current Implementation:** NONE

---

#### Missing Component #5: Network Monitor

**Required (from failsafe_hierarchy.md line 125):**
- Monitor WiFi/Companion Link
- Connection loss > 5s triggers RTL

**Current Implementation:** NONE

---

#### Missing Component #6: Guardian State Machine

**Required (from failsafe_hierarchy.md lines 127-132, 136-143):**

```
State Machine:
NORMAL ──[anomaly detected]──> GUARDED ──[escalation]──> INTERVENTION
   ↑                              │                           │
   └────────[all clear]──────────┘────────[manual recovery]──┘

Guardian Actions by Severity:
Level 1: Minor anomaly → Log, alert operator
Level 2: Moderate risk → Override LLM commands (Hold mode)
Level 3: Significant risk → Disable LLM input (RTL)
Level 4: Critical risk → Emergency intervention (Land)
Level 5: Catastrophic → Disarm (if safe altitude < 10m)
```

**Current Implementation:** NONE
- No state tracking
- No severity levels
- No escalation matrix

---

#### Missing Component #7: Async Architecture

**Required (from failsafe_hierarchy.md lines 591-618):**

```python
# Guardian Process Core Logic
guardian_config = {
    "heartbeat_interval": 0.05,       # 20Hz
    "offboard_timeout": 0.5,            # 500ms for LLM
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
        "level_6": "emergency_disarm"
    },
    "resource_thresholds": {
        "cpu_percent": 90,
        "memory_percent": 95,
        "temperature_c": 80,
        "disk_percent": 90
    }
}
```

**Current Implementation:**
```python
# Lines 59-69 in guardian.py - Synchronous only
class GuardianProcess:
    def __init__(self, limits: Optional[HardLimits] = None):
        self.limits = limits or HardLimits()
        self._home_lat: Optional[float] = None
        self._home_lon: Optional[float] = None
        self._last_heartbeat: float = time.time()
```

**Gap Severity:** CRITICAL
- No asyncio integration
- No concurrent monitoring tasks
- No proper timing for 20Hz operations

---

### LAYER 3: LLM Reactions (1-3s)

**Status:** NOT IMPLEMENTED IN GUARDIAN

The Guardian is NOT responsible for Layer 3, but must enforce constraints:

**LLM Constraints Guardian Must Enforce (from failsafe_hierarchy.md lines 622-649):**

```yaml
# LLM Operational Boundaries
check_in_guardian:
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

**Current Guardian HardLimits (lines 16-27):**
```python
@dataclass(frozen=True)
class HardLimits:
    max_altitude_amsl_m: float = 120.0      # OK
    max_distance_from_home_m: float = 500.0 # OK
    min_battery_rtl_percent: float = 25.0   # OK but not enforced for LLM planning
    heartbeat_timeout_s: float = 2.0         # WRONG: Should be 0.5s
    max_speed_m_s: float = 15.0            # OK
    # MISSING: min_altitude_agl, velocity_z, acceleration, battery thresholds
```

**Gap Severity:** MEDIUM
- Missing velocity Z limit
- Missing acceleration limits
- Missing AGL (above ground level) checks
- Missing battery planning thresholds

---

### LAYER 4: Operator Override (RC)

**Status:** PX4-handled, Guardian must detect

**Required (from failsafe_hierarchy.md lines 187-210):**
- Guardian must detect RC override
- Immediately yield control
- Log the override event
- Resume monitoring in background

**Current Implementation:** NONE

**Implementation Requirements:**
```python
class GuardianProcess:
    async def rc_override_monitor(self, px4_state: DroneState):
        """Detect RC override and yield control"""
        if px4_state.flight_mode != "OFFBOARD":
            if self._llm_control_active:
                self._llm_control_active = False
                logger.warning(f"RC override detected: mode={px4_state.flight_mode}")
                await self._log_override_event(px4_state)
```

**Gap Severity:** MEDIUM
- Guardian doesn't monitor for RC override
- No yield control logic

---

## Implementation Priority Matrix

| Priority | Component | Layer | Effort | Risk if Missing |
|----------|-----------|-------|--------|-----------------|
| **P0** | 20Hz Heartbeat | 2 | Medium | CRASH |
| **P0** | PX4 Parameter Config | 1 | Low | CRASH |
| **P0** | Async Architecture | 2 | High | CRASH |
| **P1** | Resource Monitor | 2 | Medium | FIRE/HARDWARE DAMAGE |
| **P1** | State Consistency | 2 | Medium | LOSS OF CONTROL |
| **P1** | Escalation Matrix | 2 | Medium | INCIDENT |
| **P2** | VIO Sanity Check | 2 | Low | NAVIGATION FAILURE |
| **P2** | Network Monitor | 2 | Low | COMMS LOSS |
| **P2** | RC Override Detection | 4 | Low | SAFETY |
| **P3** | LLM Constraint Enforcement | 3 | Medium | BAD BEHAVIOR |

---

## Complete Implementation Requirements

### New Files Required

1. **`avatar/mav/guardian_async.py`** - Async Guardian core
2. **`avatar/mav/px4_parameters.py`** - PX4 safety parameter definitions
3. **`avatar/mav/resource_monitor.py`** - RPi resource monitoring
4. **`avatar/mav/state_validator.py`** - State consistency checks

### Modified Files

1. **`avatar/mav/guardian.py`** - Refactor to async with full Layer 2 implementation

### Required Dependencies

```txt
psutil>=5.9.0  # For resource monitoring
asyncio-mqtt>=0.16.0  # For async MAVLink
```

---

## Testing Requirements

Per `failsafe_hierarchy.md` Section 7.1, these tests MUST pass before flight:

| Test ID | Scenario | Current Status |
|---------|----------|----------------|
| F-001 | RC loss during offboard | CANNOT TEST - No 20Hz heartbeat |
| F-002 | LLM crash during mission | CANNOT TEST - No LLM heartbeat monitor |
| F-003 | Battery critical at 300m | PARTIAL - Battery check exists |
| F-004 | Geofence breach | PARTIAL - Distance check exists |
| F-005 | RC loss + low battery | CANNOT TEST |
| F-006 | Kill switch | NOT IMPLEMENTED - Handled by PX4 |
| F-007 | Guardian-LLM conflict | NOT IMPLEMENTED - No escalation matrix |
| F-008 | GPS spoofing | NOT IMPLEMENTED - No VIO sanity check |
| F-009 | RPi thermal throttling | NOT IMPLEMENTED - No resource monitor |
| F-010 | Complete RPi failure | CANNOT TEST - No 20Hz heartbeat |

---

## Recommendations

### Immediate Actions (Pre-Flight Blockers)

1. **DO NOT FLY** with current Guardian implementation
2. Implement 20Hz heartbeat with 500ms offboard timeout
3. Add async architecture with concurrent monitors
4. Add resource monitoring (CPU, temp, memory)
5. Configure all critical PX4 parameters on startup

### Short-term Actions (Before Production)

1. Implement state consistency checking
2. Add escalation matrix and state machine
3. Implement VIO sanity checks
4. Add network monitoring
5. Add RC override detection

### Medium-term Actions (Enhancement)

1. Add predictive battery modeling
2. Implement comprehensive logging
3. Add simulation test harness
4. Create automated safety test suite

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Required Components | 25+ |
| Currently Implemented | ~5 |
| Implementation Percentage | ~20% |
| Critical Gaps | 4 |
| High Priority Gaps | 3 |
| Test Coverage | 20% (2/10 tests possible) |
| Flight Readiness | **NOT READY** |

---

**Document Control:**
- Version: 1.0
- Date: 2026-04-11
- Classification: Safety-Critical
- Next Review: Upon Guardian implementation completion
