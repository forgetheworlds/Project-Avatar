# Flight Controller Architecture Deep Dive

## Executive Summary

This document provides a comprehensive technical analysis of PX4 flight controller architecture, MAVLink protocol, MAVSDK abstractions, and safety-critical design patterns essential for building a secure MCP server for autonomous drone control. Understanding these systems is critical because:

- **Timing is safety**: Control loops run at 250Hz (rate), 50Hz (position), with offboard timeouts measured in seconds
- **State machines guard life**: Commander module's arming FSM, failsafe triggers, and mode transitions prevent catastrophic failures
- **Trust but verify**: Every external command must be validated, acknowledged, and monitored for timeout

---

## 1. PX4 Flight Stack Architecture

### 1.1 System Layers

PX4 consists of three architectural layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │  Navigator  │ │   Commander  │ │    EKF2     │ │  FlightModeManager  │   │
│  │  (Missions) │ │  (State FSM) │ │ (Estimator) │ │  (Setpoint Gen)   │   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘   │
└─────────┼───────────────┼───────────────┼──────────────────┼────────────────┘
          │               │               │                  │
┌─────────┼───────────────┼───────────────┼──────────────────┼────────────────┐
│         │               │               │                  │                │
│  MIDDLEWARE LAYER (uORB Message Bus)                        │                │
│         │               │               │                  │                │
│         ▼               ▼               ▼                  ▼                │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    uORB PUBLISH/SUBSCRIBE BUS                       │  │
│  │     (thread-safe, shared memory, pub/sub async messaging)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │               │               │                  │                │
└─────────┼───────────────┼───────────────┼──────────────────┼────────────────┘
          │               │               │                  │
┌─────────┼───────────────┼───────────────┼──────────────────┼────────────────┐
│  BOARD SUPPORT LAYER (Drivers, Work Queues, NuttX/POSIX)                     │
│         │               │               │                  │                │
│         ▼               ▼               ▼                  ▼                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │  IMU/GPS    │ │   PWM Out   │ │   MAVLink   │ │   Control Allocator │   │
│  │   Drivers   │ │   Drivers   │ │   Streamer  │ │    (Mixing)       │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Modules and Responsibilities

#### Commander Module (`src/modules/commander/Commander.cpp`)
The central state machine managing vehicle lifecycle:

**Arming State Machine:**
```
DISARMED ──[pre-flight checks pass]──► STANDBY ──[arm command]──► ARMED
    │                                      │                      │
    │                                      │                      │
    │◄────────[disarm/failsafe]────────────┘◄─────────────────────┘
```

**Key States:**
- `DISARMED`: Motors off, no control outputs
- `STANDBY`: Ready to arm, pre-flight checks complete
- `ARMED`: Motors active, flight control engaged

**Published Topics:**
- `vehicle_status`: Navigation state, arming status, failsafe flags
- `actuator_armed`: Hardware arming signal to output drivers
- `vehicle_command_ack`: Command acknowledgment responses

#### Navigator Module
Generates mission trajectory from waypoints:
- Subscribes to: `vehicle_global_position`, `mission`
- Publishes: `position_setpoint_triplet` (current, previous, next waypoint)
- Runs at mission planning rate (typically 5-10Hz)

#### FlightModeManager (`src/modules/flight_mode_manager/FlightModeManager.cpp`)
Converts high-level mode commands to trajectory setpoints:

```cpp
// From source: runs at 50Hz (limit to every other local_position update)
_vehicle_local_position_sub.set_interval_us(20_ms);  // 50 Hz
```

**Flight Task Hierarchy:**
```
FlightTask (base)
├── Manual
│   ├── Stabilized
│   ├── Altitude
│   └── Position
├── Auto
│   ├── FollowTarget
│   ├── Orbit
│   └── Mission
└── Offboard
    └── External setpoint handling
```

**Key Function:**
```cpp
void FlightModeManager::generateTrajectorySetpoint(
    const float dt,
    const vehicle_local_position_s& vehicle_local_position
);
```

#### Position Controller (`src/modules/mc_pos_control/MulticopterPositionControl.cpp`)
Cascaded P-PID position/velocity controller:

```
Position Setpoint ──► Position Error ──► P Controller ──► Velocity Setpoint
                                                             │
                                                             ▼
Position Estimate ◄── Velocity Error ◄── PID Controller ◄── Velocity Setpoint (saturated)
                                                             │
                                                             ▼
                                                    Thrust Vector + Attitude Setpoint
```

**Update Rate:** Scheduled on `nav_and_controllers` work queue, 50Hz typical

**Key Parameters:**
- `MPC_XY_P`: Position P gain
- `MPC_XY_VEL_P/I/D`: Velocity PID gains
- `MPC_XY_CRUISE`: Horizontal cruise velocity
- `MPC_Z_VEL_MAX_UP/DN`: Vertical velocity limits

#### Rate Controller (`src/modules/mc_rate_control/MulticopterRateControl.cpp`)
Inner-most control loop for angular rates:

```cpp
// From source: registered on rate_ctrl work queue (highest priority)
WorkItem(MODULE_NAME, px4::wq_configurations::rate_ctrl)
```

**Update Pattern:**
```cpp
// Triggered by gyro updates
if (_vehicle_angular_velocity_sub.update(&angular_velocity)) {
    const float dt = constrain((now - _last_run) * 1e-6f, 0.000125f, 0.02f);
    // PID rate control with integrator limiting
}
```

**PID Structure:**
```cpp
_rate_control.setPidGains(
    Vector3f(roll_p, pitch_p, yaw_p),    // Proportional
    Vector3f(roll_i, pitch_i, yaw_i),    // Integral
    Vector3f(roll_d, pitch_d, yaw_d)     // Derivative
);
_rate_control.setIntegratorLimit(Vector3f(int_lim));  // Anti-windup
```

#### Control Allocator
Transforms torque/thrust commands to actuator outputs:

**Input:** `vehicle_torque_setpoint`, `vehicle_thrust_setpoint`
**Output:** `actuator_motors` (normalized -1..1 or 0..1)

```
Torque X/Y/Z ──┐
               ├──► Control Allocator ──► Mixer Matrix ──► Motor Outputs
Thrust Z ──────┘
```

### 1.3 uORB Message Bus

**Architecture:**
- Asynchronous publish/subscribe messaging
- Shared memory within unified address space
- Thread-safe with lock-free single-reader/writer semantics
- Supports interrupt context publishing (not subscribing)

**Message Definition (`.msg` files):**
```protobuf
uint64 timestamp  # REQUIRED: microseconds since boot
float32[3] position
float32[3] velocity
float32[3] acceleration
float32 yaw
float32 yawspeed
# TOPICS: trajectory_setpoint, vehicle_local_position
```

**Key Topics for Offboard Control:**
| Topic | Publisher | Subscriber | Rate |
|-------|-----------|------------|------|
| `offboard_control_mode` | MavlinkReceiver | FlightModeManager | On setpoint |
| `trajectory_setpoint` | FlightModeManager/Offboard | mc_pos_control | 50Hz |
| `vehicle_attitude_setpoint` | mc_pos_control/mc_att_control | mc_rate_control | 50Hz |
| `vehicle_rates_setpoint` | mc_att_control | mc_rate_control | 250Hz |
| `vehicle_angular_velocity` | sensors | mc_rate_control | 250-1000Hz |

### 1.4 Work Queue System

**Purpose:** Cooperative multitasking without blocking operations

**Priority Hierarchy (from WorkQueueManager.hpp):**
```cpp
static constexpr wq_config_t rate_ctrl{"wq:rate_ctrl", 3150, 0};        // Highest
static constexpr wq_config_t nav_and_controllers{"wq:nav_and_controllers", 2240, -13};
static constexpr wq_config_t hp_default{"wq:hp_default", 2800, -18};
static constexpr wq_config_t lp_default{"wq:lp_default", 1920, -50};    // Lowest
```

**Module Assignments:**
- `rate_ctrl`: mc_rate_control, VehicleAngularVelocity, ControlAllocator
- `nav_and_controllers`: FlightModeManager, mc_pos_control, EKF2, sensors
- `hp_default`: ManualControl, rc_update, mag_burn_in
- `lp_default`: load_mon, esc_battery, events

**Scheduling Pattern:**
```cpp
class Module : public WorkItem {
    void Run() override {
        // Non-blocking execution
        // Poll subscriptions, compute, publish
        // Yield to next work item
    }
};
```

---

## 2. MAVLink Protocol Deep Dive

### 2.1 Message Structure

**MAVLink 2 Frame Format (14 bytes overhead):**
```
+------+--------+--------+--------+----------------+---------+-----------+--------+
| STX  | LEN    | INCOMP | COMPAT | SEQ  | SYSID | COMPID | MSGID   | PAYLOAD | CK   |
| 0xFD | 0-255  | 0-255  | 0-255  | 0-255 | 0-255 | 0-255 | 0-16777215| 0-255B | 2B   |
+------+--------+--------+--------+----------------+---------+-----------+--------+
| 1B   | 1B     | 1B     | 1B     | 1B    | 1B    | 1B     | 3B      | nB      | 2B   |
```

**Key Fields:**
- `SEQ`: Sequence number for detecting packet loss
- `SYSID`: System identifier (1-255, 0= broadcast)
- `COMPID`: Component identifier (MAV_COMP_ID_*)
- `MSGID`: Message type identifier

### 2.2 Command Protocol (COMMAND_LONG / COMMAND_INT)

**COMMAND_LONG (for float params):**
```cpp
mavlink_command_long_t cmd;
cmd.target_system = 1;
cmd.target_component = 1;
cmd.command = MAV_CMD_NAV_TAKEOFF;  // 22
cmd.param1 = pitch_angle;           // Minimum pitch
cmd.param7 = altitude;              // Takeoff altitude
```

**COMMAND_INT (for coordinate precision):**
```cpp
mavlink_command_int_t cmd;
cmd.command = MAV_CMD_NAV_WAYPOINT;
cmd.param1 = hold_time;             // Seconds at waypoint
cmd.x = lat_int;                    // Latitude * 1e7 (int32)
cmd.y = lon_int;                    // Longitude * 1e7 (int32)
cmd.z = altitude;                   // Altitude (float)
cmd.frame = MAV_FRAME_GLOBAL_INT;
```

**Command Acknowledgment Pattern:**
```
Sender                    Receiver
  │                          │
  ├─ COMMAND_LONG/INT ─────►│
  │◄─ COMMAND_ACK (PENDING)─┤  (optional for long ops)
  │                          │
  │◄─ COMMAND_ACK (ACCEPTED)─┤  or (FAILED, UNSUPPORTED, DENIED)
```

**Result Codes:**
- `MAV_RESULT_ACCEPTED` (0): Command executed
- `MAV_RESULT_TEMPORARILY_REJECTED` (1): Busy, retry later
- `MAV_RESULT_DENIED` (2): Command invalid in current state
- `MAV_RESULT_UNSUPPORTED` (3): Command not implemented
- `MAV_RESULT_FAILED` (4): Execution failed

### 2.3 Offboard Control Setpoints

**SET_POSITION_TARGET_LOCAL_NED (Message #84):**
```cpp
mavlink_set_position_target_local_ned_t sp;
sp.time_boot_ms = current_time;
sp.target_system = 1;
sp.coordinate_frame = MAV_FRAME_LOCAL_NED;  // or MAV_FRAME_BODY_NED
sp.type_mask = POSITION_TARGET_TYPEMASK_X_IGNORE |  // Define what's controlled
               POSITION_TARGET_TYPEMASK_Y_IGNORE |
               POSITION_TARGET_TYPEMASK_VX_IGNORE;
sp.x = north_position;       // meters
sp.y = east_position;
sp.z = down_position;       // Positive down (NED convention)
sp.vx = north_velocity;      // m/s
sp.vy = east_velocity;
sp.vz = down_velocity;
sp.afx = north_accel;        // m/s^2
sp.afy = east_accel;
sp.afz = down_accel;
sp.yaw = yaw_angle;          // radians
sp.yaw_rate = yaw_velocity;  // rad/s
```

**Type Mask Bits (POSITION_TARGET_TYPEMASK_*):**
| Bit | Flag | Description |
|-----|------|-------------|
| 0 | X_IGNORE | Ignore position X |
| 1 | Y_IGNORE | Ignore position Y |
| 2 | Z_IGNORE | Ignore position Z |
| 3 | VX_IGNORE | Ignore velocity X |
| 4 | VY_IGNORE | Ignore velocity Y |
| 5 | VZ_IGNORE | Ignore velocity Z |
| 6 | AX_IGNORE | Ignore acceleration X |
| 7 | AY_IGNORE | Ignore acceleration Y |
| 8 | AZ_IGNORE | Ignore acceleration Z |
| 9 | FORCE_SET | Use force instead of acceleration |
| 10 | YAW_IGNORE | Ignore yaw |
| 11 | YAW_RATE_IGNORE | Ignore yaw rate |

**SET_ATTITUDE_TARGET (Message #82):**
```cpp
mavlink_set_attitude_target_t att;
att.time_boot_ms = current_time;
att.target_system = 1;
att.type_mask = ATTITUDE_TARGET_TYPEMASK_BODY_ROLL_RATE_IGNORE |
                ATTITUDE_TARGET_TYPEMASK_BODY_PITCH_RATE_IGNORE;
att.q[4] = {w, x, y, z};        // Quaternion (NED frame)
att.body_roll_rate = 0;           // rad/s (ignored by mask)
att.body_pitch_rate = 0;        // rad/s
att.body_yaw_rate = yaw_rate;   // rad/s
att.thrust = thrust_normalized; // 0..1
```

### 2.4 Heartbeat Protocol

**Message #0 - System Presence:**
```cpp
mavlink_heartbeat_t hb;
hb.type = MAV_TYPE_QUADROTOR;           // or MAV_TYPE_GENERIC for GCS
hb.autopilot = MAV_AUTOPILOT_PX4;       // Flight stack identifier
hb.base_mode = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED |
                 MAV_MODE_FLAG_STABILIZE_ENABLED;
hb.custom_mode = PX4_CUSTOM_MAIN_MODE_OFFBOARD;  // PX4-specific
hb.system_status = MAV_STATE_ACTIVE;
```

**Timing Requirements:**
- **Send Rate:** 1Hz minimum for all systems
- **Timeout Detection:** 4-5 missed heartbeats = connection lost
- **Critical:** Heartbeats must be sent from same thread as commands

**Offboard Mode Activation Flow:**
```
Companion Computer                            PX4 Autopilot
      │                                             │
      ├─ Continuous 2Hz Setpoint Stream ───────────►│ (required before arming)
      │                                             │
      ├─ HEARTBEAT (1Hz) ─────────────────────────►│
      │                                             │
      │   [After 1 second of valid setpoints]     │
      │                                             │
      ├─ COMMAND_LONG: NAV_GUIDED_ENABLE ─────────►│
      │◄─ COMMAND_ACK: ACCEPTED ───────────────────┤
      │                                             │
      ├─ Continuous Setpoints (min 2Hz) ─────────►│ (required continuously)
      │                                             │
      │   [Timeout: COM_OF_LOSS_T seconds]        │
      │                                             │
      │   Without setpoints: PX4 exits offboard   │
      │   and executes failsafe (COM_OBL_RC_ACT)  │
```

### 2.5 Offboard Timeout and Failsafe

**Critical Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `COM_OF_LOSS_T` | 0.5s | Offboard loss timeout |
| `COM_OBL_RC_ACT` | 0 | Failsafe action (0=Position, 1=Altitude, 2=Manual, 3=Return, 4=Land) |
| `COM_OBL_ACT` | 1 | Offboard loss action without RC (same options) |

**Setpoint Stream Requirements:**
- **Minimum Rate:** 2Hz continuous while in offboard mode
- **Pre-arming:** Must send setpoints for >1 second before mode switch
- **Type:** Position, velocity, acceleration, attitude, or body rates
- **Coordinate Frame:** MAV_FRAME_LOCAL_NED or MAV_FRAME_BODY_NED

---

## 3. MAVSDK Architecture

### 3.1 System Overview

MAVSDK provides a high-level async API over MAVLink:

```
┌────────────────────────────────────────────────────────────┐
│                    Application Code                        │
├────────────────────────────────────────────────────────────┤
│  MAVSDK (C++)          │   MAVSDK-Python (asyncio wrapper) │
│  ┌────────────┐        │   ┌────────────┐                  │
│  │ Mavsdk API │◄───────┼───┤  Python API│                  │
│  │ (gRPC)     │        │   │  (async)   │                  │
│  └─────┬──────┘        │   └────────────┘                  │
├────────┼───────────────┼───────────────────────────────────┤
│        │               │                                   │
│  ┌─────▼─────┐        │   mavsdk_server (C++ backend)     │
│  │  gRPC     │        │   - Connects via UDP/TCP/Serial   │
│  │  Bridge   │        │   - Manages MAVLink protocol      │
│  └─────┬─────┘        │   - Streams telemetry             │
│        │               │                                   │
├────────┼───────────────┼───────────────────────────────────┤
│  MAVLink Protocol Layer                                    │
│  ┌─────▼─────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Connection│  │   Plugins   │  │   System Discovery  │  │
│  │ (UDP/TCP) │  │ Action, Offboard, Telemetry, Mission │  │
│  └───────────┘  └─────────────┘  └─────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 3.2 Plugin System

**Client Plugins (for controlling drones):**
| Plugin | Purpose | Key Methods |
|--------|---------|-------------|
| `Action` | Basic flight commands | `arm()`, `takeoff()`, `land()`, `goto_location()` |
| `Offboard` | Precise external control | `start()`, `set_position_ned()`, `set_velocity_ned()` |
| `Telemetry` | Sensor data streaming | `position()`, `battery()`, `flight_mode()` async generators |
| `Mission` | Waypoint navigation | `upload_mission()`, `start_mission()` |
| `Geofence` | Boundary enforcement | `upload_geofence()` |
| `Param` | Parameter tuning | `set_param_float()`, `get_param_float()` |

### 3.3 Async/Await Patterns

**Connection Establishment:**
```python
from mavsdk import System

drone = System()
await drone.connect(system_address="udpin://0.0.0.0:14540")

# Wait for connection
async for state in drone.core.connection_state():
    if state.is_connected:
        break

# Wait for health checks
async for health in drone.telemetry.health():
    if health.is_global_position_ok and health.is_home_position_ok:
        break
```

**Streaming Telemetry (Generator Pattern):**
```python
async def print_battery(drone):
    async for battery in drone.telemetry.battery():
        print(f"Battery: {battery.remaining_percent:.1f}%")

async def print_position(drone):
    async for position in drone.telemetry.position():
        print(f"Position: {position.latitude_deg}, {position.longitude_deg}")

# Run multiple streams concurrently
tasks = [
    asyncio.create_task(print_battery(drone)),
    asyncio.create_task(print_position(drone)),
]
await asyncio.Event().wait()  # Run forever
```

### 3.4 Offboard Control Implementation

**Setpoint Types:**
```python
from mavsdk.offboard import PositionNedYaw, VelocityNedYaw, AccelerationNed

# Position control
pos = PositionNedYaw(10.0, 5.0, -3.0, 45.0)  # N, E, D (positive down), yaw
await drone.offboard.set_position_ned(pos)

# Velocity control
vel = VelocityNedYaw(2.0, 0.0, 0.0, 0.0)  # m/s North, East, Down
await drone.offboard.set_velocity_ned(vel)

# Acceleration control (combined with velocity)
acc = AccelerationNed(0.5, 0.0, 0.0)
```

**Offboard Lifecycle:**
```python
# 1. Set initial setpoint (required before starting)
await drone.offboard.set_position_ned(PositionNedYaw(0, 0, 0, 0))

# 2. Start offboard mode
try:
    await drone.offboard.start()
except OffboardError as error:
    print(f"Failed to start offboard: {error._result.result}")
    await drone.action.disarm()
    return

# 3. Send setpoints continuously (min 2Hz)
while True:
    await drone.offboard.set_position_ned(new_position)
    await asyncio.sleep(0.1)  # 10Hz

# 4. Stop offboard
await drone.offboard.stop()  # Returns to Hold mode
```

### 3.5 Error Handling

**Result Codes:**
```python
from mavsdk.offboard import OffboardError

# Result enum values:
# UNKNOWN = 0
# SUCCESS = 1
# NO_SYSTEM = 2
# CONNECTION_ERROR = 3
# BUSY = 4
# COMMAND_DENIED = 5
# TIMEOUT = 6
```

**Retry Pattern:**
```python
async def safe_offboard_start(drone, max_retries=3):
    for i in range(max_retries):
        try:
            await drone.offboard.start()
            return True
        except OffboardError:
            if i < max_retries - 1:
                await asyncio.sleep(0.5)
    return False
```

---

## 4. Safety-Critical Design Patterns

### 4.1 Watchdog and Heartbeat Requirements

**Companion Computer Responsibilities:**
```python
class OffboardSafetyMonitor:
    def __init__(self):
        self.last_setpoint_time = 0
        self.min_setpoint_rate = 2.0  # Hz
        self.timeout_threshold = 0.5    # seconds (COM_OF_LOSS_T)

    async def setpoint_watchdog(self, drone):
        """Ensures setpoints are sent above minimum rate"""
        while True:
            elapsed = time.time() - self.last_setpoint_time
            if elapsed > self.timeout_threshold:
                await self.handle_timeout(drone)
            await asyncio.sleep(0.1)

    async def send_setpoint(self, drone, setpoint):
        """Safe setpoint sending with tracking"""
        await drone.offboard.set_position_ned(setpoint)
        self.last_setpoint_time = time.time()
```

**PX4 Offboard Loss Detection (from source):**
```cpp
// mavlink_receiver.cpp - publishes offboard_control_mode with each setpoint
offboard_control_mode_s ocm{};
ocm.position = !matrix::Vector3f(setpoint.position).isAllNan();
ocm.velocity = !matrix::Vector3f(setpoint.velocity).isAllNan();
ocm.acceleration = !matrix::Vector3f(setpoint.acceleration).isAllNan();
ocm.timestamp = hrt_absolute_time();
_offboard_control_mode_pub.publish(ocm);

// Commander monitors COM_OF_LOSS_T timeout on offboard_control_mode topic
```

### 4.2 Failsafe State Machines

**Commander Failsafe Hierarchy:**
```
FLIGHT_TERMINATION (highest priority)
    │
    ├── Critical battery (BAT_EMERGEN_THR)
    ├── Flight termination switch (CBRK_FLIGHTTERM=0)
    └── Geofence violation (GF_ACTION=6)
    │
RETURN_TO_LAUNCH
    │
    ├── RC loss (NAV_RCL_ACT=1)
    ├── Data link loss (NAV_DLL_ACT=1)
    └── Low battery (BAT_CRIT_THR)
    │
LAND
    │
    ├── Offboard loss with no RC (COM_OBL_ACT=4)
    ├── Position estimate loss
    └── Descent mode
    │
HOLD/LOITER
    │
    └── Temporary failsafes
```

**Failsafe Parameter Matrix:**
| Parameter | Default | Options | When Used |
|-----------|---------|---------|-----------|
| `COM_OF_LOSS_T` | 0.5s | 0.0-60.0 | Offboard timeout threshold |
| `COM_OBL_RC_ACT` | 0 | 0-5 | Action when offboard lost with RC |
| `COM_OBL_ACT` | 1 | 0-5 | Action when offboard lost without RC |
| `NAV_RCL_ACT` | 2 | 0-5 | RC loss action |
| `NAV_DLL_ACT` | 0 | 0-5 | Data link loss action |
| `GF_ACTION` | 1 | 0-6 | Geofence breach action |

### 4.3 Command Acknowledgment and Retry

**MAVLink Command Pattern with Retry:**
```python
async def send_command_with_retry(mavlink_connection, command, max_retries=5, timeout=1.0):
    for attempt in range(max_retries):
        # Send command with confirmation increment
        mavlink_connection.mav.command_long_send(
            target_system=1,
            target_component=1,
            command=command,
            confirmation=attempt,  # Increment for retries
            param1=0, param2=0, param3=0, param4=0,
            param5=0, param6=0, param7=0
        )

        # Wait for acknowledgment
        ack = await asyncio.wait_for(
            wait_for_ack(mavlink_connection, command),
            timeout=timeout
        )

        if ack and ack.result == MAV_RESULT_ACCEPTED:
            return True

        # Exponential backoff
        await asyncio.sleep(0.1 * (2 ** attempt))

    return False
```

### 4.4 Resource Limits and Rate Limiting

**uORB Queue Length (from source):**
```protobuf
# Messages with queue to prevent dropped commands
uint64 timestamp
# ORB_QUEUE_LENGTH 4  (power of 2 for efficient modulo)
```

**MAVSDK Rate Limiting:**
```python
import asyncio
from mavsdk import System

class RateLimiter:
    def __init__(self, min_interval):
        self.min_interval = min_interval
        self.last_send = 0

    async def send_limited(self, drone, setpoint):
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_send
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        await drone.offboard.set_position_ned(setpoint)
        self.last_send = asyncio.get_event_loop().time()

# Usage: limit to 10Hz (0.1s interval)
limiter = RateLimiter(0.1)
await limiter.send_limited(drone, setpoint)
```

---

## 5. Real-Time Control Theory

### 5.1 Control Loop Timing

**Standard PX4 Update Rates:**
| Controller | Rate | Work Queue | Trigger | Latency Target |
|------------|------|------------|---------|----------------|
| Rate Controller | 250Hz-1000Hz | `rate_ctrl` | Gyro update | <1ms |
| Attitude Controller | 250Hz | `rate_ctrl` | Attitude estimator | <2ms |
| Position Controller | 50Hz | `nav_and_controllers` | Local position | <5ms |
| Flight Mode Manager | 50Hz | `nav_and_controllers` | Position callback | <10ms |
| Navigator | 10Hz | `nav_and_controllers` | Mission updates | <50ms |
| Commander | 10Hz | - | Various | <100ms |

**Rate Controller Implementation (from source):**
```cpp
// mc_rate_control/MulticopterRateControl.cpp
bool MulticopterRateControl::init() {
    // Register callback on gyro topic (250-1000Hz)
    if (!_vehicle_angular_velocity_sub.registerCallback()) {
        return false;
    }
    return true;
}

void MulticopterRateControl::Run() {
    // Triggered by gyro update
    vehicle_angular_velocity_s angular_velocity;
    if (_vehicle_angular_velocity_sub.update(&angular_velocity)) {
        // dt calculation with bounds
        const float dt = math::constrain(
            ((now - _last_run) * 1e-6f),  // Convert us to seconds
            0.000125f,   // Min: 125us (8kHz max)
            0.02f        // Max: 20ms (50Hz min)
        );
        // ... PID computation
    }
}
```

### 5.2 Setpoint vs Actuator Control

**Control Hierarchy:**
```
┌────────────────────────────────────────────────────────────────┐
│  SETPOINT LEVEL (External commands)                              │
│  - Position (X, Y, Z)                                          │
│  - Velocity (Vx, Vy, Vz)                                       │
│  - Acceleration (Ax, Ay, Az)                                   │
├────────────────────────────────────────────────────────────────┤
│  FLIGHT TASK (Setpoint generation)                             │
│  - Converts high-level to trajectory_setpoint                  │
│  - Handles smoothing, limits, feasibility                      │
├────────────────────────────────────────────────────────────────┤
│  POSITION CONTROLLER                                           │
│  - P loop: position → velocity                                 │
│  - PID loop: velocity → acceleration                           │
│  - Output: thrust vector + attitude_setpoint                   │
├────────────────────────────────────────────────────────────────┤
│  ATTITUDE CONTROLLER                                           │
│  - P loop: quaternion error → rate_setpoint                  │
│  - Output: vehicle_rates_setpoint                              │
├────────────────────────────────────────────────────────────────┤
│  RATE CONTROLLER                                               │
│  - PID loop: rate_error → torque_setpoint                    │
│  - Output: vehicle_torque_setpoint                             │
├────────────────────────────────────────────────────────────────┤
│  CONTROL ALLOCATOR                                             │
│  - Converts torque/thrust → actuator_motors                  │
│  - Handles saturation, priority, failure                     │
├────────────────────────────────────────────────────────────────┤
│  OUTPUT DRIVERS                                                │
│  - actuator_motors → PWM/DShot                              │
│  - Rate: 50-400Hz depending on protocol                     │
└────────────────────────────────────────────────────────────────┘
```

### 5.3 Control Mode Cascading

**Position/Velocity/Acceleration Mixing (from MAVLink handling):**
```cpp
// mavlink_receiver.cpp
offboard_control_mode_s ocm{};

// Determine control mode from setpoint contents
ocm.position = !matrix::Vector3f(setpoint.position).isAllNan();
ocm.velocity = !matrix::Vector3f(setpoint.velocity).isAllNan();
ocm.acceleration = !matrix::Vector3f(setpoint.acceleration).isAllNan();

// Position controller uses this to determine which loops to close
// Priority: position → velocity → acceleration
```

**Position Controller Cascaded Loops:**
```
Position Error ──► P Gain ──► Velocity Setpoint ──► Saturation
                                                  │
                                                  ▼
Velocity Error ──► PID ──► Acceleration Setpoint
                              │
                              ▼
                    ┌─────────────────┐
                    │ Control Math    │
                    │ a = T/m (tilt) │
                    └────────┬────────┘
                             │
                             ▼
                    Thrust + Attitude Setpoint
```

### 5.4 Trajectory Generation

**Flight Task Smoothing (from FlightModeManager):**
```cpp
// Generate trajectory with jerk limits
void FlightModeManager::generateTrajectorySetpoint(
    const float dt,
    const vehicle_local_position_s& local_pos
) {
    if (_current_task.task) {
        // Task computes setpoint with internal smoothing
        _current_task.task->update();
        _trajectory_setpoint_pub.publish(_current_task.task->getTrajectorySetpoint());
    }
}
```

**Jerk-Limited Trajectory:**
- Input: Target position/velocity
- Output: Smooth trajectory respecting `MPC_JERK_MAX`
- Benefit: Reduces motor wear, improves tracking

---

## 6. Key Insights for MCP Server Design

### 6.1 Critical Safety Requirements

**MUST Implement:**
1. **Continuous setpoint stream at >= 2Hz** while in offboard mode
2. **Pre-flight health checks** before arming (GPS, position estimate, battery)
3. **Timeout detection** and failsafe activation (COM_OF_LOSS_T)
4. **Command acknowledgment** waiting with retry logic
5. **Heartbeat sending** at 1Hz from same thread as commands
6. **Geofence validation** before takeoff

**MUST NOT Do:**
1. Send setpoints before entering offboard mode (will be rejected)
2. Rely on offboard mode for < 1 second before arming (activation fails)
3. Skip health checks (will result in rejected arm/takeoff)
4. Exceed position controller limits without parameter adjustment
5. Ignore MAV_RESULT_DENIED (indicates unsafe state)

### 6.2 Latency Budget for MCP

**Timing Chain:**
```
LLM Decision    Network    MCP Server    MAVSDK    PX4 Rate    Motor
    │             │           │           │        Ctrl       │
    │ 50-500ms    │  10ms     │   5ms     │  4ms   │   2ms   │
    ├─────────────┼───────────┼───────────┼────────┼───────┤
    │                                                    │
    │◄──────────── Total: ~70-520ms round trip ────────►│
```

**Implications:**
- LLM decisions must be **predictive**, not reactive
- Use **velocity commands** for immediate response
- Position commands for **trajectory planning**
- **Never** use LLM for emergency stop (use direct GuardianProcess)

### 6.3 Recommended MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server Process                           │
├─────────────────────────────────────────────────────────────────┤
│  GuardianProcess                                                 │
│  ├── Continuous telemetry monitoring (1Hz)                       │
│  ├── Safety limit validation                                     │
│  └── Emergency stop capability                                   │
├─────────────────────────────────────────────────────────────────┤
│  MissionControl                                                  │
│  ├── High-level mission state                                    │
│  ├── Mode transitions (guided by GuardianProcess)                  │
│  └── Failsafe action coordination                                │
├─────────────────────────────────────────────────────────────────┤
│  FlightControl                                                   │
│  ├── Setpoint generation (min 2Hz)                               │
│  ├── Trajectory validation                                       │
│  └── Rate limiting                                               │
├─────────────────────────────────────────────────────────────────┤
│  MAVSDK Client                                                   │
│  ├── Connection management                                       │
│  ├── Async command execution                                     │
│  └── Telemetry streaming                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Parameter Safety Limits for MCP

**Recommended Conservative Values:**
| Parameter | Conservative | Max Safe | Description |
|-----------|--------------|----------|-------------|
| `MPC_XY_CRUISE` | 3 m/s | 10 m/s | Horizontal cruise |
| `MPC_XY_VEL_MAX` | 5 m/s | 15 m/s | Max horizontal velocity |
| `MPC_Z_VEL_MAX_UP` | 1 m/s | 5 m/s | Max ascent rate |
| `MPC_Z_VEL_MAX_DN` | 0.5 m/s | 3 m/s | Max descent rate |
| `MPC_TILTMAX_AIR` | 30 deg | 45 deg | Max tilt angle |
| `MPC_JERK_MAX` | 2 m/s³ | 20 m/s³ | Max jerk |
| `COM_OF_LOSS_T` | 0.5s | 5.0s | Offboard timeout |

### 6.5 Validation Checklist for MCP Tools

**Pre-Flight:**
- [ ] GPS lock (3D fix minimum)
- [ ] Position estimate valid
- [ ] Battery > threshold
- [ ] No pre-arm errors
- [ ] Geofence configured
- [ ] Home position set

**Pre-Offboard:**
- [ ] Setpoint stream active > 1 second
- [ ] Offboard mode switch acknowledged
- [ ] Heartbeat being sent

**In-Flight:**
- [ ] Setpoints sent at >= 2Hz
- [ ] Telemetry healthy
- [ ] Within geofence
- [ ] Battery remaining

---

## 7. Reference Links

### PX4 Documentation
- [PX4 Architecture Overview](https://docs.px4.io/main/en/concept/architecture.html)
- [Offboard Mode](https://docs.px4.io/main/en/flight_modes/offboard.html)
- [Flight Tasks](https://docs.px4.io/main/en/concept/flight_tasks.html)
- [Control Allocator](https://docs.px4.io/main/en/concept/control_allocator.html)
- [uORB Messaging](https://docs.px4.io/main/en/middleware/uorb.html)
- [Safety Configuration](https://docs.px4.io/main/en/config/safety.html)

### MAVLink Documentation
- [MAVLink Protocol](https://mavlink.io/en/)
- [Heartbeat Protocol](https://mavlink.io/en/services/heartbeat.html)
- [Command Protocol](https://mavlink.io/en/services/command.html)
- [Message Definitions](https://mavlink.io/en/messages/common.html)
- [PyMAVLink Guide](https://mavlink.io/en/mavgen_python/)

### MAVSDK Documentation
- [MAVSDK Python](https://mavsdk.mavlink.io/main/en/python/)
- [Offboard Plugin](https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_offboard.html)

### PX4 Source Code (Local)
- `PX4-Autopilot/src/modules/commander/Commander.cpp`
- `PX4-Autopilot/src/modules/mc_pos_control/MulticopterPositionControl.cpp`
- `PX4-Autopilot/src/modules/mc_rate_control/MulticopterRateControl.cpp`
- `PX4-Autopilot/src/modules/flight_mode_manager/FlightModeManager.cpp`
- `PX4-Autopilot/src/modules/mavlink/mavlink_receiver.cpp`
- `PX4-Autopilot/platforms/common/px4_work_queue/WorkQueueManager.hpp`

---

## 8. Summary Tables

### Offboard Control Setpoint Matrix

| Control Type | MAVLink Message | uORB Topic | Type Mask | Frequency |
|--------------|-----------------|------------|-----------|-----------|
| Position | SET_POSITION_TARGET_LOCAL_NED | trajectory_setpoint | Ignore vel/accel | 2-50Hz |
| Velocity | SET_POSITION_TARGET_LOCAL_NED | trajectory_setpoint | Ignore pos/accel | 2-50Hz |
| Acceleration | SET_POSITION_TARGET_LOCAL_NED | trajectory_setpoint | Ignore pos/vel | 2-50Hz |
| Attitude | SET_ATTITUDE_TARGET | vehicle_attitude_setpoint | Ignore rates | 2-50Hz |
| Body Rates | SET_ATTITUDE_TARGET | vehicle_rates_setpoint | Set rates only | 2-50Hz |

### Critical Safety Parameters

| Parameter | Default | Safe Range | MCP Server Must |
|-----------|---------|------------|-----------------|
| COM_OF_LOSS_T | 0.5s | 0.5-5.0s | Verify setpoint rate |
| COM_OBL_RC_ACT | 0 | 0-5 | Know failsafe action |
| NAV_RCL_ACT | 2 | 0-5 | Handle RC loss |
| GF_ACTION | 1 | 0-6 | Configure geofence |
| MPC_XY_VEL_MAX | 8.0 | 1-20 | Limit velocity cmds |
| MPC_Z_VEL_MAX_UP | 3.0 | 0.5-8 | Limit climb rate |

### Work Queue Priorities

| Queue | Priority | Modules | Use Case |
|-------|----------|---------|----------|
| rate_ctrl | 0 (highest) | Rate ctrl, Gyro, Allocator | Real-time control |
| nav_and_controllers | -13 | Position ctrl, EKF2, Sensors | Navigation |
| hp_default | -18 | Manual control, RC | User input |
| lp_default | -50 | Battery, Load monitor | Diagnostics |

---

*Document generated for Project Avatar - Phase 0.5 MCP Server Development*
