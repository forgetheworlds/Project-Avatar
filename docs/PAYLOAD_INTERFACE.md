# Payload Interface Specification

**Project Avatar** | May 2026 | Version 1.0.0

## 1. Overview

The Payload Interface defines the standard contract between the Avatar drone platform and any swappable payload module. Every payload — whether a water gun, camera, spotlight, speaker, or sensor array — implements the same lifecycle, communication protocol, and hardware abstraction.

### 1.1 Design Principles

- **Plug-and-play**: New payloads require zero changes to the flight stack, MCP server, or PWA
- **Safety-first**: Every payload has an emergency power cut (<50ms) independent of software
- **Discoverable**: The registry auto-detects attached payloads on boot
- **Power-budgeted**: Activating too many payloads is prevented, not discovered mid-flight
- **SIM-first**: All payloads work identically in simulation and on real hardware

### 1.2 Scope

This document specifies:
- Mechanical, electrical, and data interfaces
- Payload lifecycle (discover → init → activate → operate → deactivate → teardown)
- Command protocol (actions, parameters, results)
- Health monitoring contract
- Error handling and fault recovery
- Registry behavior and power budgeting

---

## 2. Physical Interface

### 2.1 Mechanical Mount

| Property | Spec |
|----------|------|
| Mount type | Quick-release dovetail (3D printed PLA/PETG) |
| Mount weight | ≤ 9g (included in payload mass budget) |
| Payload max mass | 50g (for sub-250g AUW compliance) |
| Mount latch | Spring-loaded, positive-lock, tool-free |
| Vibration isolation | 4× M2 silicone grommets |

The mount provides:
- Mechanical retention (won't detach at 5G maneuver)
- Electrical passthrough (power + data pins engage on mount)
- Orientation key (payload can only mount one way)

### 2.2 Electrical

```
Pin  | Signal       | Voltage  | Max Current | Notes
-----|--------------|----------|-------------|------
  1  | VCC_12V      | 12V (4S) | 2A          | Switched payload power rail
  2  | GND          | 0V       | —           | Common ground
  3  | I2C_SCL      | 3.3V     | —           | 400kHz Fast-mode
  4  | I2C_SDA      | 3.3V     | —           | Pulled up (4.7kΩ on FC)
  5  | UART_TX      | 3.3V     | —           | Optional: payload→FC (115200)
  6  | UART_RX      | 3.3V     | —           | Optional: FC→payload (115200)
  7  | GPIO_0       | 3.3V     | 20mA        | General purpose, interrupt-capable
  8  | GPIO_1       | 3.3V     | 20mA        | General purpose, interrupt-capable
```

- VCC_12V is **switched** — the FC enables it only after payload init succeeds
- I2C bus is **shared** — all payloads on the same bus. Address conflicts must be avoided
- UART is **optional** — only needed for high-bandwidth payloads (camera streaming)

### 2.3 Power Budget

The flight controller BEC provides 5A total for payloads + peripherals.

| Consumer | Current |
|----------|---------|
| GPS + Compass | 150mA |
| ESP32 WiFi Bridge | 300mA |
| RX (ELRS) | 100mA |
| **Remaining for payloads** | **4,450mA** |

Budget per payload:
- Max continuous per payload: 2,000mA
- Surge (burst) per payload: 3,000mA (≤ 500ms)
- Total all payloads: ≤ 4,500mA (enforced by registry)

---

## 3. Software Interface

### 3.1 BasePayload Abstract Class

Every payload inherits from `BasePayload` (`splash/payload/base_payload.py`).

#### Required Properties (metadata)

```python
@property
def payload_type(self) -> str:       # "splash", "camera", "spotlight"
@property
def display_name(self) -> str:       # Human-readable, e.g. "Splash Water Gun"
@property
def version(self) -> str:            # Semver, e.g. "1.0.0"
@property
def mass_g(self) -> float:           # Total mass including mount
@property
def power_max_ma(self) -> int:       # Max continuous current draw
@property
def power_nominal_ma(self) -> int:   # Nominal operating current
@property
def commands(self) -> list[str]:     # Supported action names
@property
def bus_addresses(self) -> dict:     # I2C addresses used, e.g. {"pca9685": 0x40}
```

#### Lifecycle Methods (implemented by base, delegates to subclasses)

| Method | Called by | State change | Description |
|--------|-----------|-------------|-------------|
| `discover()` | Registry | UNKNOWN → DETECTED | Class method. Probe I2C bus. Return True if hardware found. |
| `initialize()` | Registry | DETECTED → READY | Set up I2C devices, GPIOs, peripherals. Calls `_init_hardware()`. |
| `activate()` | Registry | READY → ACTIVE | Enable power rail, arm outputs. Calls `_enable_power()`, `_arm_outputs()`. |
| `deactivate()` | Registry | ACTIVE → READY | Disarm outputs, cut power rail. Calls `_disarm_outputs()`, `_disable_power()`. |
| `emergency_stop()` | Registry / MCP | ANY → FAULTED | Hardware-level power cut. Must complete <50ms. Calls `_emergency_cut()`. |
| `teardown()` | Registry | ANY → TEARDOWN | Release all resources. Calls `_deinit_hardware()`. |
| `health_check()` | Health monitor | — (read-only) | Standardized health report. Calls `_read_health_specific()`. |
| `execute_command()` | Registry / MCP | — | Dispatch payload-specific action. Calls `_execute_impl()`. |

#### Subclass Overrides (implement per payload)

```python
def _init_hardware(self, **kwargs) -> None      # Set up I2C/GPIO/UART
def _deinit_hardware(self) -> None              # Release hardware
def _enable_power(self) -> None                 # Switch power rail ON
def _disable_power(self) -> None                # Switch power rail OFF
def _arm_outputs(self) -> None                  # Enable servo PWM, prime pump, etc.
def _disarm_outputs(self) -> None               # Safe shutdown of outputs
def _emergency_cut(self) -> None                # <50ms hardware power cut
def _read_health_specific(self) -> dict         # Payload-specific health data
def _execute_impl(self, action, params) -> Result  # Command implementation
```

### 3.2 State Machine

```
                    ┌──────────┐
                    │ UNKNOWN  │  ← Initial state
                    └────┬─────┘
                         │ discover() returns True
                    ┌────▼─────┐
                    │ DETECTED │
                    └────┬─────┘
                         │ initialize() success
                    ┌────▼─────┐
            ┌───────│  READY   │◄────────────┐
            │       └────┬─────┘              │
            │            │ activate()    deactivate()
            │       ┌────▼─────┐              │
            │       │  ACTIVE  │──────────────┘
            │       └────┬─────┘
            │            │ emergency_stop()
            │       ┌────▼─────┐
            └───────│ FAULTED  │
                    └────┬─────┘
                         │ teardown()
                    ┌────▼─────┐
                    │ TEARDOWN │  ← Terminal state
                    └──────────┘
```

State transitions are validated:
- UNKNOWN → DETECTED, FAULTED
- DETECTED → READY, FAULTED, TEARDOWN
- READY → ACTIVE, FAULTED, TEARDOWN
- ACTIVE → READY, FAULTED, TEARDOWN
- FAULTED → READY (recovery), TEARDOWN
- TEARDOWN → (terminal)

### 3.3 Command Protocol

All commands use this interface:

```python
@dataclass
class PayloadCommandResult:
    success: bool
    message: str
    data: dict
```

Queries (commands starting with `get_`) can be called from any state except UNKNOWN and TEARDOWN.
Actions require ACTIVE state.

#### Splash Payload Commands

| Command | Args | Description |
|---------|------|-------------|
| `fire` | `duration_ms` (100-2000, default 500) | Activate pump for N ms |
| `aim` | `pan_deg` (0-180), `tilt_deg` (0-180) | Set servo angles |
| `center` | — | Center servos, stop pump |
| `set_deadzone` | `deadzone_px` (5-100) | Configure fire trigger zone |
| `get_status` | — | Full payload state dump |

#### Future Payload Commands (examples)

| Payload | Commands |
|---------|----------|
| Camera | `start_stream`, `stop_stream`, `capture`, `set_resolution`, `get_status` |
| Spotlight | `on`, `off`, `set_brightness`, `strobe`, `get_status` |
| Speaker | `play`, `stop`, `set_volume`, `say`, `get_status` |
| Sensor | `sample`, `start_logging`, `stop_logging`, `get_status` |

---

## 4. Registry

### 4.1 PayloadRegistry

The registry manages all payloads on the drone.

```python
registry = PayloadRegistry(
    known_payloads=[SplashPayload],  # Classes to scan for
    sim_mode=True,                   # SIM vs real hardware
    power_budget_ma=4500,            # Total payload power budget
    health_poll_interval_s=0.1,      # Health check frequency (10Hz)
    on_fault=handle_fault,           # Callback(pid, health) on fault
)

# Boot sequence
discovered = registry.scan_bus()     # Returns list[PayloadInfo]
registry.activate("splash_0")        # Power on, arm outputs

# Mission operations
registry.execute("splash_0", "fire", {"duration_ms": 500})
registry.execute("splash_0", "aim", {"pan_deg": 45, "tilt_deg": 120})

# Shutdown
registry.deactivate_all()
registry.teardown_all()
```

### 4.2 Health Monitor

A daemon thread polls `health_check()` on all active payloads at 10Hz:

- `status == "FAULTED"` → auto-triggers `emergency_stop()` + calls `on_fault` callback
- `status == "DEGRADED"` → logged as warning, mission continues
- Thread auto-stops when no payloads are active
- Health data available via `registry.health_status_all()`

### 4.3 Fault Handling

| Fault | Action | Recovery |
|-------|--------|----------|
| I2C bus error | Mark FAULTED, emergency stop | Power cycle payload |
| Over-current (>2A) | Hardware fuse trip, FAULTED | Replace fuse, check payload |
| Health FAULTED | Auto emergency_stop(), on_fault() callback | Manual reset via teardown() + re-initialize |
| Power budget exceeded | PayloadPowerLimitError raised | Deactivate other payloads first |
| Mount detached | Hall sensor detects, FAULTED | Re-mount, re-initialize |

### 4.4 Critical vs Non-Critical Payloads

- `critical=True` (default): Failure aborts the mission. `registry.critical_payload_failed()` returns True.
- `critical=False`: Failure is logged but mission continues. E.g., a secondary camera.

---

## 5. SIM_MODE vs Real Mode

Every payload works in both modes via the `sim_mode` flag:

| Aspect | SIM_MODE=True | SIM_MODE=False |
|--------|---------------|----------------|
| `discover()` | Always returns True | Probes I2C bus for hardware |
| `_init_hardware()` | No-op | Initializes real I2C/GPIO/UART |
| `_enable_power()` | Logs only | Switches power MOSFET |
| Servo PWM | Tracked in memory | PCA9685 writes |
| Pump GPIO | Tracked in memory | RPi.GPIO output |
| Health data | Returns nominal values | Reads sensors (INA219, thermistor) |

The MCP server, registry, and tests behave identically in both modes.

---

## 6. Adding a New Payload

### Step-by-step

1. Create `mypayload_payload.py` inheriting from `BasePayload`
2. Override all abstract properties and methods
3. Implement `discover()` to probe the I2C bus for your hardware
4. Implement `_execute_impl()` with your payload-specific commands
5. Register with `registry.register_class(MyPayload)`
6. Add to `known_payloads` list in MCP server startup
7. Write tests following `test_payload_interface.py` pattern
8. Document commands in this PAYLOAD_INTERFACE.md

### Template

```python
from splash.payload.base_payload import BasePayload, PayloadCommandResult

class MyPayload(BasePayload):
    @property
    def payload_type(self) -> str: return "mytype"
    @property
    def display_name(self) -> str: return "My Payload"
    # ... override all abstract members

    @classmethod
    def discover(cls, sim_mode=False, **kwargs):
        if sim_mode: return True
        # Probe I2C for your device
        ...

    def _execute_impl(self, action, params):
        if action == "do_thing":
            return PayloadCommandResult(success=True, message="Done")
        ...
```

---

## 7. Safety Considerations

1. **Emergency stop is hardware-level**: `_emergency_cut()` must bypass all software. Direct GPIO toggle.
2. **Power rail is switched**: Payload can be fully de-powered by the FC. No phantom power.
3. **Mount detection**: Hall effect sensor or GPIO short detects if payload is physically attached.
4. **I2C watchdog**: If a payload stops responding on I2C, the bus is reset and payload is faulted.
5. **Thermal protection**: Payloads exceeding 70°C are automatically deactivated.
6. **Reservoir empty**: Splash payload refuses fire when reservoir_ml == 0.
7. **Cooldown enforcement**: Fire commands respect minimum interval to prevent pump burnout.

---

## 8. File Map

```
splash/payload/
├── __init__.py                  # Public API exports
├── base_payload.py              # BasePayload ABC + types (614 lines)
├── payload_registry.py          # PayloadRegistry + health monitor (490 lines)
├── splash_payload.py            # Splash (water gun) implementation (450+ lines)
└── test_payload_interface.py    # Contract validation tests (14 tests)
```

## 9. Related Documents

- `docs/ARCHITECTURE.md` — Full system architecture
- `BLOCKERS_AND_USER_ACTION_ITEMS.md` — Hardware BOM, remaining tasks
- `splash/control/mcp_server.py` — LLM tool server (uses payload registry)
