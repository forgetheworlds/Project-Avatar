# Flight Control Tools Gap Analysis

**Analysis Date:** 2026-04-12  
**Last Updated:** 2026-04-13  
**Task:** Compare current MCP flight tool implementation vs architecture requirements  
**Current Status:** Core tool surface implemented; Phase 0.5 system readiness remains gated by the real MCP SITL smoke test

---

## Executive Summary

The flight control MCP server now implements the core tool surface required for the SITL flight spine. Overall Phase 0.5 readiness is not claimed until `tests/e2e/test_mcp_sitl_smoke.py --run-sitl` passes with PX4 running.

| Priority | Tool | Status | Implementation |
|----------|------|--------|----------------|
| CRITICAL | `set_velocity` | **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| HIGH | `fly_body_offset` | **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| HIGH | `hold` | **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| MEDIUM | `get_status` | **IMPLEMENTED** | `avatar/mcp_server/tools/telemetry_tools.py` |
| DONE | `arm_and_takeoff` | IMPLEMENTED | `avatar/mcp_server/tools/flight_tools.py` |
| DONE | `goto_gps` | IMPLEMENTED | `avatar/mcp_server/tools/flight_tools.py` |
| DONE | `land` | IMPLEMENTED | `avatar/mcp_server/tools/flight_tools.py` |
| DONE | `rtl` | IMPLEMENTED | `avatar/mcp_server/tools/flight_tools.py` |
| DONE | `get_telemetry` | IMPLEMENTED | `avatar/mcp_server/tools/telemetry_tools.py` |

---

## Critical Tools - IMPLEMENTATION STATUS

### 1. `set_velocity` - RESOLVED

**Status:** **IMPLEMENTED** in `avatar/mcp_server/tools/flight_tools.py`

**Implementation Notes:**
- Full offboard mode implementation with 20Hz streaming
- MAVSDK `Offboard.set_velocity_ned()` integration
- State machine integration for VELOCITY_CONTROL transitions
- Geofence validation during velocity commands
- Drift-corrected timing for precise 20Hz heartbeat

**Why It Was Critical:**
- Required for **real-time flight control** (not just waypoint navigation)
- Essential for **orbit maneuvers**, **person tracking**, and **dynamic obstacle avoidance**
- Enables smooth velocity-based movement instead of position setpoints
- Foundation for reactive control (responds to vision/YOLO input in real-time)
- Required for Stage 2 (Vision System) - cannot do person tracking without velocity control

**Architecture Specification:**
```json
{
  "name": "set_velocity",
  "description": "Set velocity setpoints in North-East-Down (NED) coordinate frame",
  "parameters": {
    "required": ["north_m_s", "east_m_s", "down_m_s"],
    "properties": {
      "north_m_s": { "type": "number", "min": -25.0, "max": 25.0 },
      "east_m_s": { "type": "number", "min": -25.0, "max": 25.0 },
      "down_m_s": { "type": "number", "min": -10.0, "max": 10.0 },
      "yaw_rate_deg_s": { "type": "number", "min": -90.0, "max": 90.0, "default": 0.0 },
      "yaw_heading_deg": { "type": "number", "min": 0.0, "max": 360.0 },
      "duration_s": { "type": "number", "min": 0.0, "max": 300.0, "default": 0.0 },
      "coordinate_frame": { "enum": ["ned", "body"], "default": "ned" },
      "acceleration_limit_m_s2": { "type": "number", "min": 0.5, "max": 10.0, "default": 2.0 }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL"],
    "mutex": ["goto_gps", "fly_body_offset", "land", "rtl"]
  }
}
```

**MAVSDK Async Operations Required:**
1. `drone.offboard.set_velocity_ned(VelocityNedYaw)` - Primary velocity control
2. `drone.offboard.set_velocity_body(VelocityBodyYawspeed)` - Body-frame velocity (optional)
3. `drone.offboard.start()` - Must start offboard mode before velocity commands
4. Offboard mode requires **continuous setpoint streaming** at 20Hz minimum

**Implementation Complexity:** HIGH
- Requires offboard mode management (different from standard action commands)
- Must stream setpoints continuously at 20Hz (not fire-and-forget)
- Need background task for setpoint streaming
- Must handle offboard loss failsafe (COM_OF_LOSS_T = 500ms)
- Requires switching from action-based control to offboard control
- Geofence projection validation more complex (predictive checking)

**Usage Examples:**
```python
# Orbit maneuver (continuous velocity updates)
await set_velocity(north_m_s=5, east_m_s=0, down_m_s=0, yaw_rate_deg_s=30)

# Track moving person (update 5-10Hz based on YOLO position)
await set_velocity(north_m_s=2, east_m_s=1, down_m_s=0)

# Smooth approach to target
await set_velocity(north_m_s=3, east_m_s=2, down_m_s=-0.5, duration_s=5.0)
```

---

### 2. `fly_body_offset` - RESOLVED

**Status:** **IMPLEMENTED** in `avatar/mcp_server/tools/flight_tools.py`

**Implementation Notes:**
- Body-frame to NED coordinate transformation implemented
- Uses yaw angle from telemetry to calculate global target
- Delegates to `goto_gps` after coordinate conversion
- Supports yaw alignment options (maintain, align_with_direction, custom)
- Geofence validation on computed target position

**Why It Was High Priority:**
- Enables **relative movement** in body frame (forward/right/up from current orientation)
- Critical for **obstacle avoidance** ("move left 2m to avoid tree")
- Needed for **precision maneuvers** ("advance 5m toward target")
- Natural for LLM commands (humans think in body-relative terms)

**Architecture Specification:**
```json
{
  "name": "fly_body_offset",
  "description": "Fly to position relative to current body frame (forward, right, up)",
  "parameters": {
    "required": ["forward_m", "right_m", "up_m"],
    "properties": {
      "forward_m": { "type": "number", "min": -100.0, "max": 100.0 },
      "right_m": { "type": "number", "min": -100.0, "max": 100.0 },
      "up_m": { "type": "number", "min": -50.0, "max": 50.0 },
      "speed_m_s": { "type": "number", "min": 0.5, "max": 15.0, "default": 5.0 },
      "yaw_behavior": { "enum": ["maintain", "align_with_direction", "custom"], "default": "maintain" },
      "custom_yaw_deg": { "type": "number", "min": 0.0, "max": 360.0 }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL"],
    "mutex": ["goto_gps", "land", "rtl"],
    "geofence_destination_check": true
  }
}
```

**MAVSDK Async Operations Required:**
1. `drone.telemetry.attitude_euler()` - Get current yaw to calculate direction
2. `drone.telemetry.position()` - Get current position as reference
3. **Math**: Convert body-frame offset to global coordinates:
   ```python
   # yaw is in degrees, convert to radians
   yaw_rad = math.radians(current_yaw)
   # forward = north component when yaw=0
   delta_north = forward_m * math.cos(yaw_rad) - right_m * math.sin(yaw_rad)
   delta_east = forward_m * math.sin(yaw_rad) + right_m * math.cos(yaw_rad)
   target_lat = current_lat + delta_north / 111320
   target_lon = current_lon + delta_east / (111320 * math.cos(math.radians(current_lat)))
   ```
4. `drone.action.goto_location(target_lat, target_lon, target_alt, yaw)` - Execute movement

**Implementation Complexity:** MEDIUM
- Requires coordinate frame transformation (body -> NED -> GPS)
- Can use existing `goto_gps` infrastructure after coordinate conversion
- Must validate destination geofence before execution
- Simpler than `set_velocity` (position-based, not continuous streaming)

**Usage Examples:**
```python
# Move forward 5 meters (toward current heading)
await fly_body_offset(forward_m=5, right_m=0, up_m=0)

# Sidestep left 3 meters, climb 2 meters
await fly_body_offset(forward_m=0, right_m=-3, up_m=2)

# Retreat 10 meters backward
await fly_body_offset(forward_m=-10, right_m=0, up_m=0)
```

---

### 3. `hold` - RESOLVED

**Status:** **IMPLEMENTED** in `avatar/mcp_server/tools/flight_tools.py`

**Implementation Notes:**
- PX4 HOLD/Loiter mode integration via `drone.action.hold()`
- Duration management with drift monitoring
- Position tolerance checking during hold
- Support for auto-RTL on excessive drift
- Interruptible via state machine commands

**Why It Was High Priority:**
- **Position hold with duration** is essential for photo/video capture
- Required for **progressive confirmation workflow** (hold while confirming)
- Used when **people detected** (stop and wait)
- Standard maneuver in mission templates

**Architecture Specification:**
```json
{
  "name": "hold",
  "description": "Hold current position and altitude for specified duration",
  "parameters": {
    "required": ["duration_s"],
    "properties": {
      "duration_s": { "type": "number", "min": 1.0, "max": 3600.0 },
      "position_tolerance_m": { "type": "number", "min": 0.1, "max": 5.0, "default": 1.0 },
      "yaw_behavior": { "enum": ["maintain", "face_north", "rotate_continuous", "follow_gimbal"], "default": "maintain" },
      "accept_external_commands": { "type": "boolean", "default": true }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL"],
    "mutex_lock": true,
    "blocks": ["goto_gps", "fly_body_offset", "set_velocity"]
  }
}
```

**MAVSDK Async Operations Required:**
1. `drone.action.hold()` - Initiate position hold (PX4 HOLD mode)
2. `asyncio.sleep(duration_s)` - Wait for hold duration
3. Monitor position with `drone.telemetry.position()` for tolerance checking

**Implementation Complexity:** LOW
- Simple wrapper around existing `drone.action.hold()`
- Add duration management with `asyncio.sleep()`
- Optional: background task to monitor position tolerance
- Can reuse `abort_mission` logic to interrupt hold early

**Usage Examples:**
```python
# Hold for 10 seconds (photo capture)
await hold(duration_s=10)

# Hold indefinitely until next command
await hold(duration_s=3600)  # 1 hour max

# Precise hold for video
await hold(duration_s=30, position_tolerance_m=0.5)
```

**Note:** Current implementation has `abort_mission` which calls `drone.action.hold()` but doesn't support duration. Need to add duration parameter and blocking behavior.

---

### 4. `get_status` - RESOLVED

**Status:** **IMPLEMENTED** in `avatar/mcp_server/tools/telemetry_tools.py`

**Implementation Notes:**
- Unified status aggregation from telemetry cache, battery, health checks
- State string generation for LLM consumption (human-readable summary)
- GPS info integration (fix type, satellites, hdop)
- Home position tracking
- Active command and execution status
- Geofence status monitoring

**Why It Was Medium Priority:**
- `get_telemetry` already exists and provides most data
- `get_status` is essentially a **unified interface** combining telemetry + battery + health
- Architecture specifies richer response format with state strings
- Nice-to-have for consistency, but not blocking flight operations

**Current vs Required:**

| Component | Current (`get_telemetry`) | Required (`get_status`) |
|-----------|---------------------------|-------------------------|
| Position | latitude, longitude, alt | lat, lon, alt, heading |
| Velocity | north, east, down, speed | north, east, down, groundspeed |
| Attitude | roll, pitch, yaw | roll, pitch, yaw |
| Battery | remaining_percent | percent, voltage, current, remaining_mah, time_remaining, warning_level |
| Flight State | flight_mode string | flight_state enum (DISARMED, HOVERING, etc.) |
| System Health | Partial via get_health_status | overall status + sensor array |
| GPS | Not included | fix_type, satellites, hdop, vdop |
| Armed/In-Air | Yes | Yes (as armed boolean) |
| Home Position | Not included | lat, lon, alt |
| Active Command | Not included | command, execution_id, progress |
| Geofence | Not included | enabled, violation_imminent, distance |

**Architecture Specification:**
```json
{
  "name": "get_status",
  "description": "Retrieve comprehensive drone status including position, battery, flight mode, and system health",
  "parameters": {
    "include_telemetry": { "type": "boolean", "default": true },
    "include_mission_status": { "type": "boolean", "default": true },
    "include_sensor_health": { "type": "boolean", "default": false }
  },
  "returns": {
    "state_string": "HOVERING at 15m AGL, 73% battery, GPS 12 sats",
    "flight_state": "HOVERING",
    "armed": true,
    "position": { "lat", "lon", "alt_m", "relative_alt_m", "heading_deg" },
    "home_position": { "lat", "lon", "alt_m" },
    "velocity": { "north_m_s", "east_m_s", "down_m_s", "groundspeed_m_s" },
    "attitude": { "roll_deg", "pitch_deg", "yaw_deg" },
    "battery": { "percent", "voltage_v", "current_a", "remaining_mah", "time_remaining_s", "warning_level" },
    "gps": { "fix_type", "satellites", "hdop", "vdop" },
    "system_health": { "overall", "sensors": [...] },
    "geofence_status": { "enabled", "violation_imminent", "distance_to_boundary_m" }
  }
}
```

**MAVSDK Async Operations Required:**
Same as current `get_telemetry` plus:
1. `drone.telemetry.battery()` - For voltage, current details
2. `drone.telemetry.gps_info()` - For satellite count, fix type
3. `drone.telemetry.health()` - For system health (already in get_health_status)

**Implementation Complexity:** LOW
- Mostly aggregation of existing telemetry functions
- Add state string generation
- Add GPS info retrieval
- Add home position tracking

**Recommendation:**
- Enhance existing `get_telemetry` to match architecture, OR
- Create `get_status` as composite that calls `get_telemetry`, `get_battery_status`, `get_health_status`
- Keep `get_telemetry` for lightweight polling (20Hz compatible)
- Use `get_status` for comprehensive state (slower, 1-2Hz)

---

## Implementation Roadmap - COMPLETED

### Phase 1: Critical for Stage 1 - COMPLETE
1. ✅ **`hold`** - IMPLEMENTED in flight_tools.py
2. ✅ **`fly_body_offset`** - IMPLEMENTED in flight_tools.py

### Phase 2: Critical for Stage 2 - COMPLETE
3. ✅ **`set_velocity`** - IMPLEMENTED in flight_tools.py
   - Offboard mode implementation complete
   - 20Hz heartbeat architecture integrated
   - Foundation for person tracking and orbit ready

### Phase 3: Nice-to-Have - COMPLETE
4. ✅ **`get_status`** - IMPLEMENTED in telemetry_tools.py
   - Unified telemetry interface complete
   - State string generation implemented

---

## MAVSDK Offboard Mode Considerations

The `set_velocity` tool requires **Offboard mode**, which is fundamentally different from other flight tools:

| Aspect | Action Mode (current) | Offboard Mode (needed for set_velocity) |
|--------|----------------------|----------------------------------------|
| Command Type | Position setpoints | Velocity/acceleration setpoints |
| Streaming | Fire-and-forget | Continuous 20Hz required |
| PX4 Mode | POSCTL or AUTO | OFFBOARD |
| Failsafe | Standard | COM_OF_LOSS_T timeout (500ms) |
| Latency Tolerance | Seconds | Milliseconds |
| Use Case | Waypoint navigation | Real-time control |

**Key Implementation Requirements:**
1. **Offboard manager class** that streams setpoints at 20Hz
2. **Priority scheduling** (DEC-007) - offboard thread never blocked
3. **Automatic fallback** to HOLD mode if stream stops
4. **Geofence projection** - check if velocity command will exit geofence
5. **Smooth transitions** from position control to velocity control

---

## Architecture Decisions Impact

Per DECISIONS.md:

- **DEC-004 (MAVSDK-Python)**: All tools use MAVSDK async API (confirmed in current implementation)
- **DEC-007 (Asyncio Priority)**: `set_velocity` must use dedicated thread for 20Hz streaming
- **DEC-008 (JSON Tool Schema)**: All tools must match schema in `tool_schema_design.md`
- **DEC-009 (GuardianProcess)**: All commands validated through GuardianProcess (confirmed)
- **DEC-016 (MCP Server)**: `set_velocity` listed as required MCP tool

The `set_velocity` tool is explicitly listed in DEC-016 as a required MCP Server Tool, confirming its critical priority.

---

## Testing Strategy

### Unit Tests Required:
1. `fly_body_offset` - Test coordinate transformation math
2. `hold` - Test duration management and interruption
3. `set_velocity` - Test offboard mode lifecycle, geofence projection
4. `get_status` - Test data aggregation

### SITL Integration Tests:
1. Velocity square pattern (north -> east -> south -> west)
2. Body offset box pattern
3. Hold with position tolerance validation
4. Mixed mode: goto_gps -> hold -> set_velocity -> land

---

## Phase 0.5 Implementation Complete

| Tool | Priority | Status | Implementation Location |
|------|----------|--------|------------------------|
| `set_velocity` | CRITICAL | ✅ **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| `fly_body_offset` | HIGH | ✅ **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| `hold` | HIGH | ✅ **IMPLEMENTED** | `avatar/mcp_server/tools/flight_tools.py` |
| `get_status` | MEDIUM | ✅ **IMPLEMENTED** | `avatar/mcp_server/tools/telemetry_tools.py` |

### Implementation Summary

All 9 core flight tools operational as of 2026-04-12:

**Basic Flight:**
- `arm_and_takeoff` - State-validated arming with altitude control
- `land` - Controlled descent with ground detection
- `rtl` - Return-to-launch with home position validation

**Navigation:**
- `goto_gps` - GPS waypoint navigation with geofence checking
- `fly_body_offset` - Body-relative movement with coordinate transformation

**Real-Time Control:**
- `set_velocity` - Offboard velocity control with 20Hz heartbeat streaming

**Position Control:**
- `hold` - Position hold with duration and drift monitoring

**Telemetry:**
- `get_telemetry` - Real-time position, velocity, attitude
- `get_status` - Unified system status with state strings
- `get_battery_status` - Detailed battery monitoring
- `get_health_status` - System health checks

### Files Implemented

- `avatar/mcp_server/server.py` - MCP server with tool registration
- `avatar/mcp_server/tools/flight_tools.py` - 8 flight control tools
- `avatar/mcp_server/tools/telemetry_tools.py` - 4 telemetry tools
- `avatar/mcp_server/tools/vision_tools.py` - 4 vision/camera tools

### Key Technical Achievements

1. **Offboard Mode Implementation:** `set_velocity` with 20Hz streaming via dedicated asyncio task
2. **State Machine Integration:** All tools validate preconditions via `FlightStateMachine`
3. **Guardian Validation:** All commands pass through `GuardianProcess` safety checks
4. **Coordinate Transformation:** `fly_body_offset` with yaw-aware NED conversion
5. **Geofence Enforcement:** Distance and altitude limits on all movement tools
6. **Telemetry Caching:** 20Hz telemetry stream with 1Hz client updates

**Next Steps:**
- Integration testing with SITL
- Vision system integration (Stage 2)
- Documentation update for operational procedures
