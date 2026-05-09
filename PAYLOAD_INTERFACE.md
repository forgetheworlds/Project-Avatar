# Project Avatar — Modular Payload Interface

**May 2026** | Standardized abstraction layer for payloads (water gun, camera, spotlight, speaker, sensor) to plug into the drone platform without flight-stack changes.

---

## 1. Design Philosophy

The payload interface is a **hardware abstraction layer (HAL)** that decouples the MCP control server from the specific hardware of any given payload. This means:

- The flight controller, MAVLink bridge, and state machine have **zero** payload-specific code.
- Adding a new payload (e.g., spotlight, speaker) requires **only** implementing the `BasePayload` abstract class and registering it.
- The MCP server discovers payloads at runtime — no hardcoded wiring.

---

## 2. Standard Physical Interface

### 2.1 Power Bus

| Parameter | Specification |
|-----------|---------------|
| Voltage | 12V nominal (4S LiPo: 12.6–16.8V operating range) |
| Current | **2A continuous maximum** per payload port |
| Protection | Polyfuse + reverse-polarity diode per port |
| Switching | MOSFET high-side switch per port, controlled by `PAYLOAD_EN_n` GPIO |
| Emergency cut | Hardware crowbar on emergency line, <50ms cut time |

### 2.2 Data Bus

| Bus | Usage | Notes |
|-----|-------|-------|
| **I2C (primary)** | Servo controllers (PCA9685), sensors, payload MCUs | 100/400 kHz, 7-bit addressing |
| **GPIO** | Discrete enables, MOSFET triggers, status LEDs | 3.3V logic, 4mA max per pin |
| **UART (fallback)** | Higher-bandwidth payloads (camera stream, audio) | 115200 baud default |

### 2.3 Mechanical Mount

| Parameter | Specification |
|-----------|---------------|
| Maximum payload mass | **50g** (including mount plate) |
| Mount pattern | 4× M2 bolts on 25mm × 25mm grid |
| CG envelope | Payload CG must stay within 30mm of FC center in all axes |
| Quick-release | Spring-loaded dovetail latch, tool-free swap |
| Connector | 8-pin JST-GH: VCC, GND, SDA, SCL, GPIO1, GPIO2, UART_TX, UART_RX |

### 2.4 Connector Pinout (JST-GH 8-pin)

```
Pin 1: VCC     — 12V power (switched)
Pin 2: GND     — Power ground
Pin 3: SDA     — I2C data
Pin 4: SCL     — I2C clock
Pin 5: GPIO0   — General-purpose I/O (3.3V)
Pin 6: GPIO1   — General-purpose I/O (3.3V)
Pin 7: UART_TX — UART transmit (3.3V)
Pin 8: UART_RX — UART receive (3.3V)
```

---

## 3. Payload Lifecycle

Every payload must implement the following lifecycle. The MCP server drives transitions through the PayloadRegistry.

```
  ┌──────────┐
  │ UNKNOWN  │  ← Payload not yet discovered
  └────┬─────┘
       │ discover()          [classmethod — detects hardware presence]
  ┌────▼─────┐
  │ DETECTED │  ← Hardware found, not initialized
  └────┬─────┘
       │ initialize()        [set up I2C, GPIO, alloc resources]
  ┌────▼─────┐
  │  READY   │  ← Initialized, not powered
  └────┬─────┘
       │ activate()          [enable power, arm outputs]
  ┌────▼─────┐
  │  ACTIVE  │  ← Fully operational
  └────┬─────┘
       │ deactivate()        [graceful shutdown]
  ┌────▼─────┐
  │  READY   │  (loop back)
  └────┬─────┘
       │ teardown()          [release all resources]
  ┌────▼─────┐
  │ TEARDOWN │
  └──────────┘

  ANY STATE ──► emergency_stop() ──► FAULTED  (cuts power, hardware-level)
```

### 3.1 Lifecycle Methods (Abstract Contract)

```python
@classmethod
def discover(cls, i2c_bus=None, sim_mode=False) -> bool:
    """Detect if this payload is physically present on the bus.
       Must return within 100ms. No side effects."""
    ...

def initialize(self, **config) -> bool:
    """Set up hardware: configure I2C devices, allocate GPIOs, start threads.
       Called once after discovery. Returns True on success."""
    ...

def activate(self) -> bool:
    """Enable payload power rail, arm outputs, transition to ACTIVE state.
       Must verify power rail is stable before returning."""
    ...

def deactivate(self) -> bool:
    """Graceful power-down: stop outputs, disable rail.
       Returns True when power is confirmed off."""
    ...

def emergency_stop(self) -> bool:
    """Hardware-level emergency power cut. Must complete within 50ms.
       Overrides all software locks. Irreversible until re-initialize()."""
    ...

def health_check(self) -> dict:
    """Return health status: {'status': 'OK'|'DEGRADED'|'FAULTED', ...}
       Must not block. Called at 10Hz by health monitor."""
    ...

def teardown(self) -> None:
    """Release all hardware resources, close file handles, stop threads.
       Idempotent — safe to call multiple times."""
    ...
```

### 3.2 Optional Command Interface

```python
def execute_command(self, action: str, params: dict = None) -> dict:
    """Payload-specific command dispatch. Returns {'status': '...', ...}.
       Default implementation: raise NotImplementedError for unknown actions."""
    ...
```

---

## 4. Communication Contract (MCP Server ↔ Payload)

### 4.1 Discovery and Registration

```
┌─────────────┐     ┌──────────────────┐
│ MCP Server  │────▶│ PayloadRegistry  │
│  (startup)  │     │                  │
│             │     │ scan_bus()       │
│             │     │  → calls         │
│             │     │  PayloadClass    │
│             │     │  .discover()     │
│             │     │  for each known  │
│             │     │  payload type    │
│             │◀────│                  │
│             │     │ returns:         │
│             │     │  List[PayloadInfo]│
└─────────────┘     └──────────────────┘
```

The registry is initialized at MCP server startup with a list of known payload classes:

```python
from splash.payload import SplashPayload, CameraPayload, SpotlightPayload, ...

registry = PayloadRegistry(
    known_payloads=[SplashPayload, CameraPayload, SpotlightPayload, ...],
    sim_mode=SIM_MODE,
)
registry.scan_bus()  # discovers what's attached
```

### 4.2 Control Flow

```python
# Activate a payload for a mission
payload_id = "splash_0"
registry.activate(payload_id)

# Execute payload-specific action
registry.execute(payload_id, "fire", {"duration_ms": 500})

# Or for aiming (called by CV pipeline targeting)
registry.execute(payload_id, "set_pan_tilt", {"pan": 15.0, "tilt": -5.0})

# Deactivate
registry.deactivate(payload_id)
```

### 4.3 Health Monitoring Contract

The MCP server's health monitor thread polls each active payload at **10Hz**:

```python
for payload in registry.active_payloads():
    status = payload.health_check()
    if status["status"] == "FAULTED":
        logger.critical(f"Payload {payload.id} FAULTED: {status}")
        payload.emergency_stop()
        registry.mark_faulted(payload.id)
        # Decision: can we continue the mission?
        if registry.critical_payload_failed():
            bridge.rtb()  # abort mission
```

Payloads must respond to `health_check()` within **20ms**. The registry enforces a watchdog timer.

### 4.4 MCP Tools Integration

The MCP server tools (`engage_target`, `protect_mode`) route through the payload interface:

```python
# OLD (hardcoded): bridge.engage_target_mode()
# NEW:
p = registry.get_active_payload("splash")
if p:
    registry.execute("splash", "activate_turret")
```

### 4.5 Error Protocol

When a payload fails:

1. `health_check()` returns `{'status': 'FAULTED', 'reason': '...'}`
2. Registry calls `emergency_stop()` on the faulted payload
3. Payload power rail is hardware-disabled via GPIO
4. Registry logs the incident with timestamp
5. The MCP server determines mission impact:
   - **Non-critical payload** (e.g., sensor): log warning, continue
   - **Critical payload** (e.g., the only payload): RTB
6. Faulted payloads cannot be reactivated without calling `initialize()` again

---

## 5. Standard Payload Health Report

```python
{
    "status": "OK" | "DEGRADED" | "FAULTED",
    "power": {
        "voltage_v": 12.1,        # measured rail voltage
        "current_ma": 450,        # measured current draw
        "rail_enabled": True
    },
    "temperature_c": 38.5,        # payload temperature (if sensor)
    "uptime_s": 142.0,           # seconds since activate()
    "faults": [],                 # list of fault strings
    "payload_specific": {         # optional payload-specific data
        "shots_remaining": 12,
        "servo_pan_angle": 15.0,
        ...
    }
}
```

---

## 6. Splash Payload Specification

### 6.1 Hardware

| Component | Spec | Interface |
|-----------|------|-----------|
| Pan servo | MG90S, 180° range | PCA9685 channel 0 |
| Tilt servo | MG90S, 180° range | PCA9685 channel 1 |
| Pump MOSFET | IRLZ44N N-channel | GPIO0 (3.3V gate) |
| Reservoir | 15ml syringe, quick-release | Mechanical |
| Nozzle | 3D-printed stream nozzle | Fixed mount |
| Total mass | ~48g (with mount) | Sub-50g compliant |

### 6.2 I2C Addresses

| Device | Address |
|--------|---------|
| PCA9685 | 0x40 |

### 6.3 Commands

| Action | Params | Description |
|--------|--------|-------------|
| `set_pan_tilt` | `{"pan": deg, "tilt": deg}` | Move turret |
| `fire` | `{"duration_ms": 500}` | Activate pump for N ms |
| `fire_burst` | `{"count": 3, "duration_ms": 200, "interval_ms": 400}` | Burst fire |
| `center_turret` | `{}` | Return pan/tilt to center (0°, 0°) |
| `set_pump` | `{"state": "on"|"off"}` | Manual pump control |
| `get_shots_remaining` | `{}` | Returns estimated shots |

---

## 7. Future Payloads

| Payload | Hardware | Interface | Mass Est. |
|---------|----------|-----------|-----------|
| **Camera-only** (Hawkeye Thumb 4K) | Built-in camera | UART/WiFi video stream | 15g |
| **Spotlight** | 3W LED array + lens | GPIO PWM dimming | 20g |
| **Speaker** | 3W amp + micro speaker | I2S audio or GPIO tone | 18g |
| **Sensor** | BME280 temp/humidity/pressure | I2C (0x76) | 5g |

Each implements `BasePayload` and is discovered/registered identically to Splash.

---

## 8. SIM_MODE Behavior

When `SIM_MODE=true`:

- `discover()` always returns `True` (pretends hardware present)
- `initialize()` is a no-op (returns True)
- `activate()` / `deactivate()` simulate power switching (returns True)
- `health_check()` returns `{"status": "OK", "simulated": True}`
- `emergency_stop()` returns True immediately
- All servo/pump commands log the action but don't touch hardware

When `SIM_MODE=false`:

- All hardware operations are real
- `discover()` scans I2C bus for expected addresses
- Timeouts are enforced
- Emergency stop uses actual GPIO toggling

---

## 9. Implementation Files

```
splash/payload/
├── __init__.py              # Public API exports
├── base_payload.py          # Abstract BasePayload, PayloadState enum
├── payload_registry.py      # PayloadRegistry, health monitor, fault handling
├── splash_payload.py        # Concrete SplashPayload (water gun)
├── test_payload_interface.py # Contract validation tests
```

---

## 10. Safety Notes

- **Emergency stop is hardware-level**: it must work even if the companion computer has hung. The emergency GPIO line activates a physical crowbar on the payload power rail.
- **Payloads cannot arm the drone**: payload activation is gated on drone state (must be ARMED or FLYING).
- **Firing is gated on state**: the `fire` command is rejected unless the drone is in ENGAGING state.
- **Power budget**: The registry tracks total payload power consumption. If the sum exceeds the BEC rating (5A), newly added payloads are rejected.
- **Mount integrity**: Payloads must report if the mount quick-release is no longer latched (via a simple contact sensor on GPIO).
