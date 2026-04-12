# Flight State Machine Analysis - Current Gaps

**Project:** Avatar Drone System  
**Date:** 2026-04-11  
**Analysis Type:** Architecture Gap Documentation  

---

## Executive Summary

The current MCP server implementation (`avatar/mcp_server/server.py`) has **no flight state tracking**, **no state transition validation**, and **no command preconditions**. This document identifies the required state machine and maps where it should be integrated.

**Current State:** "Blind" command sending - any tool can be called regardless of actual drone state.  
**Required State:** Full state machine with validated transitions per PX4 and safety requirements.

---

## 1. Required State Machine Architecture

### 1.1 State Transition Diagram

```
                              +-----------+
                              |   INIT    |
                              +-----+-----+
                                    |
                                    | System Ready
                                    v
                           +----------------+
                           |   DISARMED   |
                           +-------+--------+
                                   |
                                   | Pre-flight checks passed
                                   | + Arm command
                                   v
                            +-------------+
                            |    ARMED    |
                            +------+------+
                                   |
           +-----------------------+-----------------------+
           |                       |                       |
           | Takeoff complete      | Mode switch           | LLM activation
           v                       v                       v
    +-------------+        +--------------+         +--------------+
    |  FLYING     |<------|  POSITION    |<------|  OFFBOARD    |
    |  (generic)  | Mode  |  (GPS hold)  | Mode  |   (LLM)      |
    +------+------+       +------+-------+       +------+-------+
           |                     |                      |
           +---------------------+----------------------+
                                 |
           +---------------------+---------------------+
           |                     |                     |
           | Hold command        | RTL trigger         | Land command
           v                     v                     v
    +-------------+      +--------------+      +-------------+
    |    HOLD     |      |     RTL      |      |    LAND     |
    |  (Loiter)   |      |(Return Home) |      |(Descend)    |
    +------+------+      +------+-------+      +------+------+
           |                    |                      |
           | Resume             | Home reached         | Ground touch
           v                    v                      v
           +--------------------+---> +------------+
                                    |  DISARMED  |
                                    +------------+
```

### 1.2 State Definitions

| State | Description | PX4 Mode Equivalent |
|-------|-------------|---------------------|
| `INIT` | System boot, initializing sensors and connections | Pre-flight |
| `DISARMED` | On ground, motors off, awaiting arming | Disarmed |
| `ARMED` | Motors enabled, on ground, ready for takeoff | Armed |
| `TAKING_OFF` | Ascending to takeoff altitude | Takeoff |
| `HOVERING` | At fixed position/altitude, no movement | Hold/Loiter |
| `FLYING` | Generic in-air state (parent for flight modes) | - |
| `POSITION_CONTROL` | GPS position hold mode | Position |
| `VELOCITY_CONTROL` | Velocity setpoint control | Offboard velocity |
| `HOLD` | Emergency hover/loiter | Hold |
| `RTL` | Return to launch position | Return |
| `LANDING` | Controlled descent | Land |
| `EMERGENCY` | Critical failure state | Terminate/Disarm |

### 1.3 Complete State Transitions Table

| From State | Valid Transitions | Trigger Condition |
|------------|-------------------|-------------------|
| `INIT` | `DISARMED`, `ERROR` | Systems nominal / Critical failure |
| `DISARMED` | `ARMED` | Pre-flight checks passed + arm command |
| `ARMED` | `TAKING_OFF`, `DISARMED`, `ERROR` | Takeoff cmd / Disarm cmd / Failure |
| `TAKING_OFF` | `HOVERING`, `LANDING`, `ERROR` | Altitude reached / Abort / Failure |
| `HOVERING` | `POSITION_CONTROL`, `VELOCITY_CONTROL`, `RTL`, `LANDING`, `HOLD` | Mode selection |
| `POSITION_CONTROL` | `HOVERING`, `VELOCITY_CONTROL`, `RTL`, `LANDING`, `HOLD` | Mode change / Failsafe |
| `VELOCITY_CONTROL` | `POSITION_CONTROL`, `HOVERING`, `RTL`, `LANDING`, `HOLD` | Mode change / Failsafe |
| `HOLD` | `POSITION_CONTROL`, `VELOCITY_CONTROL`, `RTL`, `LANDING` | Operator/LLM command, >60s auto-RTL |
| `RTL` | `LANDING`, `POSITION_CONTROL` (abort) | Home reached / Battery permits abort |
| `LANDING` | `DISARMED`, `ERROR` | Ground touch / Failure |
| `ERROR` | `DISARMED` (if safe), `EMERGENCY` | Recovery / Catastrophic |

---

## 2. Current Implementation Gaps

### 2.1 Gap #1: No State Tracking

**Current State in `server.py`:**
```python
class DroneMCPServer:
    def __init__(self, config: DroneMCPServerConfig | None = None):
        self.config = config or DroneMCPServerConfig()
        self.server = Server("drone-mcp")
        self.drone: DroneConnection | None = None
        self.guardian = GuardianProcess()
        # MISSING: self.current_state = FlightState.DISARMED
```

**Gap:** The server has no `current_flight_state` attribute. It cannot track:
- Whether the drone is armed or disarmed
- Current flight mode/phase
- Whether takeoff has completed
- Whether landing is in progress

**Where State Should Be Tracked:**
1. **Primary:** `DroneMCPServer` class instance variable
2. **Secondary:** `DroneConnection` class for telemetry-based state inference
3. **Validation:** `GuardianProcess` for state transition validation

### 2.2 Gap #2: No Transition Validation

**Current State:** Commands execute without checking if the transition is valid.

Example from `_handle_land()`:
```python
async def _handle_land(self) -> list[types.TextContent]:
    # NO STATE CHECK - can call land() while already on ground
    # NO STATE CHECK - can call land() while disarmed
    await drone.action.land()
```

**Required Validation per Failsafe Hierarchy:**
| Command | Required State | Invalid From States |
|---------|----------------|---------------------|
| `arm_and_takeoff` | `DISARMED` | `ARMED`, `FLYING`, `TAKING_OFF`, `ERROR` |
| `land` | `FLYING`, `HOVERING`, `POSITION_CONTROL` | `DISARMED`, `LANDING`, `INIT` |
| `rtl` | `FLYING`, `HOVERING`, `POSITION_CONTROL` | `DISARMED`, `LANDING`, `INIT` |
| `abort_mission` | `FLYING`, `POSITION_CONTROL`, `VELOCITY_CONTROL` | `DISARMED`, `INIT`, `LANDING` |

**Impact:** Without validation:
- Can send `arm()` when already armed (PX4 may reject, but unclear response)
- Can send `land()` when already on ground (no-op but confusing telemetry)
- Can send `rtl()` during critical landing phase (could be dangerous)

### 2.3 Gap #3: No State-Based Command Precondition Checking

**Required Preconditions from `failsafe_hierarchy.md`:**

| Action | Preconditions | Validation Required |
|--------|---------------|-------------------|
| Arm | GPS lock, home position set, pre-flight checks passed | `health.is_global_position_ok`, `health.is_home_position_ok` |
| Takeoff | Armed state, valid altitude > 0, battery > 25% | State == ARMED, telemetry.battery_percent |
| Enter OFFBOARD | Position hold active, offboard setpoint stream ready | State == POSITION_CONTROL, offboard heartbeat active |
| Land | In-air state, altitude < 120m, not already landing | State in [FLYING, HOVERING], in_air == True |
| RTL | In-air state, home position valid, battery > 15% | State in [FLYING, HOVERING], home_ok == True |

**Current Gap:** The server only validates through `GuardianProcess.validate_command()` which checks safety limits but NOT state preconditions.

### 2.4 Gap #4: No Failsafe State Injection

**Required from `failsafe_hierarchy.md` Section 4.3:**

Any state can transition to failsafe states:
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

**Current Gap:** The server has no mechanism to:
1. Monitor for failsafe triggers
2. Automatically transition states when PX4 triggers failsafe
3. Block LLM commands when in failsafe state
4. Handle state inconsistencies between RPi and PX4

### 2.5 Gap #5: No Mission Phase Tracking

**Required from `mission_planning_patterns.md` Section 2.2:**

Flight phases with constraints:
- `takeoff`: 0-30m AGL, max 60s, transitions to `climb` or `abort_landing`
- `climb`: 20-120m AGL, max 120s, transitions to `mission` or `return_home`
- `mission`: 30-400m AGL, terrain clearance 20m, max 1800s
- `return_home`: 30-120m AGL, max 600s, transitions to `landing` or `hold`
- `landing`: 0-30m AGL, max descent 2m/s, transitions to `landed` or `go_around`

**Current Gap:** Commands are context-free. The server doesn't track:
- Which phase of flight we're in
- Phase-specific altitude/speed constraints
- Phase timeout monitoring
- Phase-appropriate transitions

---

## 3. Recommended Implementation

### 3.1 State Tracking Integration Points

```python
# In DroneMCPServer.__init__
self.current_state = FlightState.INIT  # Enum of states
self.state_history = []  # Stack for recovery analysis
self.state_lock = asyncio.Lock()  # Thread-safe state changes
self.last_state_update = time.time()

# In handle_call_tool - pre-command state validation
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    # NEW: State validation
    valid, error = await self._validate_state_transition(name)
    if not valid:
        return [types.TextContent(type="text", text=json.dumps({
            "success": False, 
            "error": f"Invalid state for command: {error}"
        }))]
    
    # ... existing command execution
```

### 3.2 State Validation Rules to Implement

| Rule ID | Check | Location | Priority |
|---------|-------|----------|----------|
| SV-001 | `arm()` requires `DISARMED` state | `_handle_arm_and_takeoff()` | Critical |
| SV-002 | `takeoff()` requires `ARMED` state | `_handle_arm_and_takeoff()` | Critical |
| SV-003 | `land()` requires `in_air == True` | `_handle_land()` | High |
| SV-004 | `rtl()` requires `home_position_ok == True` | `_handle_rtl()` | High |
| SV-005 | `abort()` requires state in `[FLYING, POSITION_CONTROL, OFFBOARD]` | `_handle_abort_mission()` | Medium |
| SV-006 | Offboard commands require `POSITION_CONTROL` first | (new offboard handler) | Critical |

### 3.3 State Machine Update Locations

| File | Function | State Update Needed |
|------|----------|-------------------|
| `server.py` | `_handle_arm_and_takeoff()` | `DISARMED` → `ARMED` → `TAKING_OFF` |
| `server.py` | `_monitor_takeoff()` | `TAKING_OFF` → `HOVERING` |
| `server.py` | `_handle_land()` | `FLYING` → `LANDING` → `DISARMED` |
| `server.py` | `_handle_rtl()` | `FLYING` → `RTL` → `LANDING` → `DISARMED` |
| `server.py` | `_handle_abort_mission()` | Any → `HOLD` |
| `server.py` | (new) `_monitor_telemetry()` | Continuous state sync from PX4 |

### 3.4 Telemetry-Based State Synchronization

**Required:** Background task to sync state from PX4 telemetry:

```python
async def _state_monitor(self) -> None:
    """Background task to sync server state with PX4 reported state."""
    async for flight_mode in drone.telemetry.flight_mode():
        async for armed in drone.telemetry.armed():
            async for in_air in drone.telemetry.in_air():
                # Map PX4 states to internal state machine
                new_state = self._map_px4_state(flight_mode, armed, in_air)
                if new_state != self.current_state:
                    await self._transition_state(new_state, source="telemetry")
```

---

## 4. Critical Safety Gaps

### 4.1 Gap: Command in Wrong State Causes Undefined Behavior

**Scenario:** LLM calls `arm_and_takeoff()` when already flying.
- Current: PX4 may reject or interpret as new command
- Risk: Mid-air disarm attempt, confusing telemetry
- Mitigation: Add `current_state` check at entry of every command handler

### 4.2 Gap: No State Tracking for Concurrent Commands

**Scenario:** LLM sends `land()` then `rtl()` immediately after.
- Current: Both commands sent to PX4, undefined behavior
- Risk: PX4 mode thrashing, unstable flight
- Mitigation: State transition validation + command queue with state gating

### 4.3 Gap: Failsafe State Changes Not Reflected

**Scenario:** PX4 triggers RTL due to RC loss, but server still thinks it's in POSITION mode.
- Current: Server state and PX4 state diverge
- Risk: LLM issues commands thinking it has control when failsafe is active
- Mitigation: Continuous telemetry monitoring + state reconciliation

---

## 5. Implementation Priority

### Phase 1: Critical (Safety)
1. Add `current_state` tracking to `DroneMCPServer`
2. Add state validation to `arm_and_takeoff()` - must be `DISARMED`
3. Add state validation to `land()` - must be `in_air`
4. Add telemetry-based state sync background task

### Phase 2: High (Correctness)
5. Add full state transition table validation
6. Add mission phase tracking (takeoff → climb → mission → return → land)
7. Add failsafe state injection handling
8. Add state history for debugging

### Phase 3: Medium (Completeness)
9. Add OFFBOARD mode state machine
10. Add velocity/position control state transitions
11. Add emergency state handling
12. Add state reconciliation after disconnect/reconnect

---

## 6. References

1. **Failsafe Hierarchy:** `/Users/muadhsambul/Downloads/Project-Avatar/research/02-safety-failsafe/failsafe_hierarchy.md`
   - Section 4: Complete State Machine
   - Section 4.2: Detailed State Transitions
   - Section 4.3: Failsafe State Injection

2. **Mission Planning:** `/Users/muadhsambul/Downloads/Project-Avatar/research/03-software-architecture/mission_planning_patterns.md`
   - Section 2.2: Altitude Bands per Phase
   - Section 2.3: Timeout per Mission Phase
   - Section 2.4: Abort Conditions

3. **Current Implementation:** `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mcp_server/server.py`
   - Lines 43-70: No state tracking in class init
   - Lines 279-387: arm_and_takeoff with no state validation
   - Lines 493-545: land() with no state validation
   - Lines 547-602: rtl() with no state validation

---

## Appendix: State Enum Definition (Recommended)

```python
from enum import Enum, auto

class FlightState(Enum):
    """Flight state machine states per PX4 failsafe hierarchy."""
    INIT = auto()                # System boot
    DISARMED = auto()            # On ground, motors off
    ARMED = auto()               # Motors enabled, on ground
    TAKING_OFF = auto()          # Ascending
    HOVERING = auto()            # Position hold at altitude
    POSITION_CONTROL = auto()    # GPS position control mode
    VELOCITY_CONTROL = auto()   # Velocity setpoint mode (offboard)
    MISSION_EXECUTION = auto()   # Following waypoints
    HOLD = auto()               # Emergency loiter
    RTL = auto()                # Return to launch
    LANDING = auto()            # Controlled descent
    LANDED = auto()             # On ground, landed
    EMERGENCY = auto()          # Critical failure
    ERROR = auto()              # System error

class FlightStateMachine:
    """Validates and executes state transitions."""
    
    TRANSITIONS = {
        FlightState.INIT: [FlightState.DISARMED, FlightState.ERROR],
        FlightState.DISARMED: [FlightState.ARMED, FlightState.ERROR],
        FlightState.ARMED: [FlightState.TAKING_OFF, FlightState.DISARMED, FlightState.ERROR],
        FlightState.TAKING_OFF: [FlightState.HOVERING, FlightState.LANDING, FlightState.ERROR],
        FlightState.HOVERING: [
            FlightState.POSITION_CONTROL, FlightState.VELOCITY_CONTROL,
            FlightState.HOLD, FlightState.RTL, FlightState.LANDING
        ],
        FlightState.POSITION_CONTROL: [
            FlightState.HOVERING, FlightState.VELOCITY_CONTROL,
            FlightState.HOLD, FlightState.RTL, FlightState.LANDING
        ],
        FlightState.VELOCITY_CONTROL: [
            FlightState.POSITION_CONTROL, FlightState.HOVERING,
            FlightState.HOLD, FlightState.RTL, FlightState.LANDING
        ],
        FlightState.HOLD: [
            FlightState.POSITION_CONTROL, FlightState.VELOCITY_CONTROL,
            FlightState.RTL, FlightState.LANDING
        ],
        FlightState.RTL: [FlightState.LANDING, FlightState.POSITION_CONTROL, FlightState.HOVERING],
        FlightState.LANDING: [FlightState.LANDED, FlightState.ERROR, FlightState.EMERGENCY],
        FlightState.LANDED: [FlightState.DISARMED, FlightState.ERROR],
        FlightState.ERROR: [FlightState.DISARMED, FlightState.EMERGENCY],
        FlightState.EMERGENCY: [FlightState.DISARMED],  # Requires manual reset
    }
    
    FAILSAFE_OVERRIDES = {
        # Any state can transition to these on failsafe trigger
        "rc_loss": FlightState.RTL,
        "low_battery": FlightState.RTL,
        "critical_battery": FlightState.LANDING,
        "geofence_breach": FlightState.RTL,
        "kill_switch": FlightState.EMERGENCY,
    }
```
