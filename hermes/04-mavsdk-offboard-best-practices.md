# MAVSDK-Python Offboard Velocity Control Best Practices

**Research Date:** 2026-04-13  
**For:** Project Avatar SITL-to-Hardware Build  
**Status:** Critical findings for OffboardVelocityStreamer implementation

---

## Critical Requirements (Non-Negotiable)

### 1. Setpoint Pre-Streaming Rule
**YOU MUST** call a setpoint setter (`set_velocity_ned()` or `set_velocity_body()`) **BEFORE** calling `offboard.start()`.

> "Client code must specify a setpoint before starting Offboard mode" — MAVSDK Docs

```python
# CORRECT pattern
await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))  # null setpoint
await drone.offboard.start()  # Now safe to start

# WRONG pattern
await drone.offboard.start()  # FAILS - no setpoint established
```

### 2. Minimum Setpoint Rate
- **PX4 requires:** minimum 2Hz setpoint stream
- **MAVSDK provides:** automatic 20Hz resend internally
- **Avatar target:** 20Hz custom stream for precise control

### 3. Coordinate Frame Behavior

| Frame | Method | Reference | 4th Parameter | Use Case |
|-------|--------|-----------|---------------|----------|
| **NED** | `set_velocity_ned()` | Absolute (North, East, Down) | **yaw_deg** (0=North, 90=East, 180=South, 270=West) | Compass-directed movement |
| **Body** | `set_velocity_body()` | Vehicle-relative (front, right, down) | **yawspeed_deg_s** (positive=cw) | Obstacle avoidance, relative maneuvers |

**Note:** Up/Down (3rd component) is identical in both: **positive = DOWN, negative = UP**

---

## Working Implementation Pattern

```python
from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed, VelocityNedYaw

async def velocity_control_demo():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    
    # Wait for connection and health
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            break
    
    # Arm first
    await drone.action.arm()
    
    # === CRITICAL: Set initial setpoint BEFORE starting offboard ===
    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
    
    # Start offboard mode
    try:
        await drone.offboard.start()
    except OffboardError as error:
        print(f"Offboard start failed: {error._result.result}")
        await drone.action.disarm()
        return
    
    # Now stream velocity commands at your desired rate
    try:
        # Example: Fly forward 5 m/s with 30°/s clockwise rotation (circle)
        await drone.offboard.set_velocity_body(VelocityBodyYawspeed(5.0, 0.0, 0.0, 30.0))
        await asyncio.sleep(10)  # 10 seconds of circling
        
        # Stop movement
        await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        await asyncio.sleep(2)
        
    finally:
        # === CRITICAL: Always stop offboard cleanly ===
        try:
            await drone.offboard.stop()
        except OffboardError as error:
            print(f"Offboard stop warning: {error._result.result}")
        
        # Land
        await drone.action.land()
```

---

## Common Pitfalls and Solutions

### Pitfall 1: Offboard Fails to Start
**Symptoms:** `OffboardError` with result code on start

**Causes:**
- No setpoint set before start (most common)
- Drone not armed
- No GPS position estimate (EKF not ready)
- Vehicle not in acceptable pre-flight state

**Solutions:**
```python
# Always check health before attempting offboard
async for health in drone.telemetry.health():
    if health.is_global_position_ok and health.is_home_position_ok:
        break

# Always set null setpoint first
await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
```

### Pitfall 2: PX4 Exits Offboard Unexpectedly
**Symptoms:** Drone stops responding to velocity commands, switches to Hold mode

**Causes:**
- Setpoint stream dropped below 2Hz
- COM_OF_LOSS_T timeout exceeded (default 0.5s on Avatar)
- External mode change (GCS, RC)
- Failsafe triggered (low battery, geofence, etc.)

**Solutions:**
- Implement 20Hz streaming loop with drift compensation (PreciseSleeper)
- Monitor flight mode via telemetry
- Have failsafe callback ready (Guardian integration)

### Pitfall 3: Confusing Yaw vs Yawspeed
**Symptoms:** Drone rotates unexpectedly or not at all

| Parameter | Frame | Behavior |
|-----------|-------|----------|
| `yaw_deg` | NED | Vehicle turns TO face this heading (0=North, 90=East) |
| `yawspeed_deg_s` | Body | Vehicle rotates AT this rate (positive=cw, negative=ccw) |

### Pitfall 4: Z-Axis Confusion
**Remember:** Positive = DOWN (toward ground), Negative = UP (away from ground)

```python
# Go UP at 2 m/s
await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, -2.0, 0.0))

# Go DOWN at 1 m/s
await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 1.0, 0.0))
```

---

## Asyncio and Cancellation

### Proper Cleanup Pattern

```python
async def safe_velocity_streamer(drone, setpoint, duration_s):
    """Stream velocity with proper cleanup on cancellation."""
    started = False
    setpoint_count = 0
    
    try:
        # Pre-stream initial setpoint
        await drone.offboard.set_velocity_body(setpoint)
        await drone.offboard.start()
        started = True
        
        start_time = time.monotonic()
        next_send = start_time
        
        while time.monotonic() - start_time < duration_s:
            await drone.offboard.set_velocity_body(setpoint)
            setpoint_count += 1
            next_send += 0.05  # 20Hz
            sleep_s = next_send - time.monotonic()
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)
                
    except asyncio.CancelledError:
        # Re-raise to let parent handle
        raise
    finally:
        # ALWAYS stop offboard, even on exception
        if started:
            try:
                await drone.offboard.stop()
            except Exception as e:
                logger.warning(f"Offboard stop warning: {e}")
```

---

## For Avatar's OffboardVelocityStreamer

### Recommended Implementation

```python
# From avatar/mav/offboard_streamer.py - validated pattern

async def stream_for(self, drone, velocity_setpoint, duration_s):
    setpoint_count = 0
    started = False
    
    try:
        # CRITICAL: Pre-stream before entering offboard
        await drone.offboard.set_velocity_ned(velocity_setpoint)
        await drone.offboard.start()
        started = True
        
        start_time = time.monotonic()
        next_send_time = start_time
        
        while time.monotonic() - start_time < duration_s:
            await drone.offboard.set_velocity_ned(velocity_setpoint)
            setpoint_count += 1
            
            # Precise 20Hz timing (matches Avatar HeartbeatService)
            next_send_time += self.interval_s  # 0.05s for 20Hz
            sleep_s = next_send_time - time.monotonic()
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)
        
        return setpoint_count
        
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f"Offboard streaming failed: {exc}")
        return setpoint_count
    finally:
        # CRITICAL: Clean stop
        if started:
            try:
                await drone.offboard.stop()
            except Exception as exc:
                logger.warning(f"Failed to stop offboard: {exc}")
```

### Testing Checklist

- [ ] Test with null setpoint (0,0,0,0) before start
- [ ] Test 20Hz timing accuracy (±2ms tolerance)
- [ ] Test cancellation handling (Ctrl+C, task.cancel())
- [ ] Test offboard.stop() in finally block
- [ ] Test behavior when PX4 rejects offboard (no GPS, etc.)
- [ ] Test with SITL: `make px4_sitl gz_x500`

---

## References

1. MAVSDK Offboard Guide: https://mavsdk.mavlink.io/main/en/cpp/guide/offboard.html
2. MAVSDK-Python Examples: https://github.com/mavlink/MAVSDK-Python/blob/main/examples/
3. PX4 Offboard Mode: https://docs.px4.io/main/en/flight_modes/offboard.html
4. Project Avatar OffboardVelocityStreamer: `avatar/mav/offboard_streamer.py`

---

## Key Takeaways for Avatar

1. **Always pre-stream** a setpoint before `offboard.start()`
2. **Use 20Hz** for Avatar's streaming (matches Guardian heartbeat)
3. **Clean up in `finally:`** — always call `offboard.stop()`
4. **Monitor health** before entering offboard (GPS, EKF ready)
5. **Handle cancellation** properly for responsive control
6. **Test with SITL first** — offboard bugs are expensive in hardware

**Confidence:** High — based on official MAVSDK docs, validated examples, and Project Avatar architecture requirements.
