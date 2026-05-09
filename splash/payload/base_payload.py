"""
base_payload.py — Abstract base class and types for the payload interface.

Defines the full lifecycle contract that every payload must implement.
Payloads plug into the drone via I2C/PWM + 12V power + mechanical mount.

Constraints:
    • Sub-250g drone: payloads ≤ 50g including mount
    • Power: 12V (4S) bus, 2A continuous max per payload
    • Data: I2C primary, GPIO secondary, UART fallback
    • Safety: emergency_deactivate() must cut power within 50ms
    • Must work in SIM_MODE and real hardware mode

Project Avatar — Modular payload interface system.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger("splash.payload.base")


# ==============================================================================
# PayloadState — Lifecycle states
# ==============================================================================

class PayloadState(Enum):
    """Payload lifecycle states.

    UNKNOWN   → Not yet discovered
    DETECTED  → Hardware found on bus, not initialized
    READY     → Initialized, not powered/active
    ACTIVE    → Fully operational
    FAULTED   → Emergency-stopped or error
    TEARDOWN  → Resources released
    """
    UNKNOWN   = auto()
    DETECTED  = auto()
    READY     = auto()
    ACTIVE    = auto()
    FAULTED   = auto()
    TEARDOWN  = auto()

    def is_operational(self) -> bool:
        """True if payload can accept commands."""
        return self in (PayloadState.READY, PayloadState.ACTIVE)

    def is_active(self) -> bool:
        """True if payload is powered and running."""
        return self == PayloadState.ACTIVE


# ==============================================================================
# PayloadInfo — Static metadata
# ==============================================================================

@dataclass
class PayloadInfo:
    """Static metadata for a payload type.

    Used by the registry for discovery, power budgeting, and capability
    advertising to the MCP server / LLM.
    """
    payload_id: str                     # Unique instance ID, e.g. "splash_0"
    payload_type: str                   # Human-readable type, e.g. "splash"
    display_name: str                   # e.g. "Splash Water Gun"
    version: str = "1.0.0"
    mass_g: float = 0.0                 # Total mass including mount
    power_max_ma: int = 0               # Max continuous current draw (mA)
    power_nominal_ma: int = 0           # Nominal current draw (mA)
    commands: List[str] = field(default_factory=list)  # Supported action names
    bus_addresses: Dict[str, int] = field(default_factory=dict)  # I2C addr map
    critical: bool = True               # If True, failure aborts mission
    mount_required: bool = True         # Quick-release mount must be latched

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload_id": self.payload_id,
            "payload_type": self.payload_type,
            "display_name": self.display_name,
            "version": self.version,
            "mass_g": self.mass_g,
            "power_max_ma": self.power_max_ma,
            "power_nominal_ma": self.power_nominal_ma,
            "commands": self.commands,
            "bus_addresses": self.bus_addresses,
            "critical": self.critical,
            "mount_required": self.mount_required,
        }


# ==============================================================================
# PayloadHealth — Runtime health report
# ==============================================================================

@dataclass
class PayloadHealth:
    """Standard health report returned by health_check().

    status: "OK", "DEGRADED", or "FAULTED"
    """
    status: str = "OK"                  # "OK" | "DEGRADED" | "FAULTED"
    power_voltage_v: float = 0.0        # Measured rail voltage
    power_current_ma: float = 0.0       # Measured current draw
    power_rail_enabled: bool = False    # Is the payload power rail on?
    temperature_c: float = 0.0          # Payload temperature (optional)
    uptime_s: float = 0.0               # Seconds since activate()
    faults: List[str] = field(default_factory=list)
    payload_specific: Dict[str, Any] = field(default_factory=dict)
    simulated: bool = False             # True when in SIM_MODE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "power": {
                "voltage_v": round(self.power_voltage_v, 2),
                "current_ma": round(self.power_current_ma, 1),
                "rail_enabled": self.power_rail_enabled,
            },
            "temperature_c": round(self.temperature_c, 1),
            "uptime_s": round(self.uptime_s, 1),
            "faults": self.faults,
            "payload_specific": self.payload_specific,
            "simulated": self.simulated,
        }


# ==============================================================================
# PayloadCommandResult
# ==============================================================================

@dataclass
class PayloadCommandResult:
    """Standard result from execute_command()."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            **self.data,
        }


# ==============================================================================
# BasePayload — Abstract payload interface
# ==============================================================================

class BasePayload(ABC):
    """Abstract base class for all drone payloads.

    Every payload must implement the full lifecycle:
        discover() → initialize() → activate() → deactivate() → teardown()
                                            ↕
                                      emergency_stop()

    Subclasses override _init_hardware() and _deinit_hardware() for
    device-specific setup. The base class manages state transitions
    and the common lifecycle.

    Constructor args:
        payload_id:    Unique instance ID, e.g. "splash_0"
        sim_mode:      If True, all hardware ops are simulated
        config:        Payload-specific configuration dict
    """

    # ------------------------------------------------------------------
    # Subclass overrides (metadata)
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def payload_type(self) -> str:
        """Short type string, e.g. 'splash', 'camera', 'spotlight'."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. 'Splash Water Gun'."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string, e.g. '1.0.0'."""
        ...

    @property
    @abstractmethod
    def mass_g(self) -> float:
        """Total mass in grams including mount hardware."""
        ...

    @property
    @abstractmethod
    def power_max_ma(self) -> int:
        """Maximum continuous current draw in milliamps."""
        ...

    @property
    @abstractmethod
    def power_nominal_ma(self) -> int:
        """Nominal operating current draw in milliamps."""
        ...

    @property
    @abstractmethod
    def commands(self) -> List[str]:
        """List of supported action names for execute_command()."""
        ...

    @property
    @abstractmethod
    def bus_addresses(self) -> Dict[str, int]:
        """I2C addresses used by this payload, e.g. {'pca9685': 0x40}."""
        ...

    @property
    def critical(self) -> bool:
        """If True, failure of this payload should abort the mission."""
        return True

    @property
    def mount_required(self) -> bool:
        """If True, quick-release mount must be latched for activation."""
        return True

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(
        self,
        payload_id: str,
        sim_mode: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.payload_id = payload_id
        self.sim_mode = sim_mode
        self.config = config or {}

        self._state = PayloadState.UNKNOWN
        self._activate_time: float = 0.0
        self._fault_reason: str = ""

        # Hardware handles (set by subclasses in _init_hardware)
        self._i2c_bus = None
        self._gpio_pins: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    @property
    def state(self) -> PayloadState:
        return self._state

    @property
    def fault_reason(self) -> str:
        return self._fault_reason

    def _transition(self, to_state: PayloadState) -> None:
        """Internal state transition with validation."""
        valid = {
            PayloadState.UNKNOWN:  {PayloadState.DETECTED, PayloadState.FAULTED},
            PayloadState.DETECTED: {PayloadState.READY, PayloadState.FAULTED,
                                    PayloadState.TEARDOWN},
            PayloadState.READY:    {PayloadState.ACTIVE, PayloadState.FAULTED,
                                    PayloadState.TEARDOWN},
            PayloadState.ACTIVE:   {PayloadState.READY, PayloadState.FAULTED,
                                    PayloadState.TEARDOWN},
            PayloadState.FAULTED:  {PayloadState.READY, PayloadState.TEARDOWN},
            PayloadState.TEARDOWN: set(),
        }

        allowed = valid.get(self._state, set())
        if to_state not in allowed:
            logger.warning(
                f"[{self.payload_id}] Invalid transition: "
                f"{self._state.name} → {to_state.name}. Forcing."
            )

        old = self._state
        self._state = to_state
        logger.info(f"[{self.payload_id}] State: {old.name} → {to_state.name}")

    # ------------------------------------------------------------------
    # Lifecycle methods — public API
    # ------------------------------------------------------------------

    @classmethod
    @abstractmethod
    def discover(cls, sim_mode: bool = False, **kwargs: Any) -> bool:
        """Detect if this payload type is physically present on the bus.

        Must return within 100ms. No side effects on hardware.
        In SIM_MODE, always returns True.

        Args:
            sim_mode: If True, simulate hardware presence.
            **kwargs: Bus handles (i2c_bus, gpio_controller, etc.)

        Returns:
            True if payload hardware is detected and addressable.
        """
        ...

    def initialize(self, **kwargs: Any) -> bool:
        """Initialize hardware and transition to READY state.

        Calls _init_hardware() which subclasses override.
        Must be called after discover() returns True.

        Returns:
            True if initialization succeeded.
        """
        if self._state not in (PayloadState.DETECTED, PayloadState.UNKNOWN):
            logger.warning(
                f"[{self.payload_id}] initialize() called from {self._state.name}, "
                "forcing re-init"
            )

        try:
            self._init_hardware(**kwargs)
            self._transition(PayloadState.READY)
            logger.info(f"[{self.payload_id}] Initialized and READY.")
            return True
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Initialization failed: {e}")
            self._fault_reason = f"init: {e}"
            self._transition(PayloadState.FAULTED)
            return False

    def activate(self) -> bool:
        """Enable payload power rail and transition to ACTIVE state.

        Subclasses override _enable_power() and _arm_outputs().
        Verifies power rail is stable before returning.
        """
        if self._state not in (PayloadState.READY,):
            logger.error(
                f"[{self.payload_id}] Cannot activate from {self._state.name}. "
                "Must be READY."
            )
            return False

        try:
            self._enable_power()
            self._arm_outputs()
            self._activate_time = time.time()
            self._transition(PayloadState.ACTIVE)
            logger.info(f"[{self.payload_id}] Activated.")
            return True
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Activation failed: {e}")
            self._fault_reason = f"activate: {e}"
            self._transition(PayloadState.FAULTED)
            return False

    def deactivate(self) -> bool:
        """Graceful power-down: disable outputs, cut power rail.

        Returns to READY state. Subclasses override _disarm_outputs()
        and _disable_power().
        """
        if self._state not in (PayloadState.ACTIVE, PayloadState.READY):
            logger.warning(
                f"[{self.payload_id}] deactivate() from {self._state.name}"
            )

        try:
            self._disarm_outputs()
            self._disable_power()
            if self._state != PayloadState.FAULTED:
                self._transition(PayloadState.READY)
            logger.info(f"[{self.payload_id}] Deactivated.")
            return True
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Deactivation failed: {e}")
            self._fault_reason = f"deactivate: {e}"
            self._transition(PayloadState.FAULTED)
            return False

    def emergency_stop(self) -> bool:
        """Hardware-level emergency power cut. Must complete within 50ms.

        Overrides all software locks. Transitions to FAULTED.
        Subclasses override _emergency_cut().
        """
        logger.warning(f"[{self.payload_id}] EMERGENCY STOP triggered!")

        try:
            self._emergency_cut()
            self._transition(PayloadState.FAULTED)
            if not self._fault_reason:
                self._fault_reason = "emergency_stop"
            logger.warning(f"[{self.payload_id}] Emergency stop complete.")
            return True
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Emergency stop failed: {e}")
            self._fault_reason = f"emergency_stop failed: {e}"
            self._transition(PayloadState.FAULTED)
            return False

    def health_check(self) -> PayloadHealth:
        """Return a standardized health report.

        Subclasses override _read_health().
        Must not block — called at 10Hz by health monitor.
        """
        try:
            uptime = time.time() - self._activate_time if self._activate_time > 0 else 0.0
            specific = self._read_health_specific()

            return PayloadHealth(
                status=specific.get("status", "OK"),
                power_voltage_v=specific.get("power_voltage_v", 12.0),
                power_current_ma=specific.get("power_current_ma", 0.0),
                power_rail_enabled=(self._state == PayloadState.ACTIVE),
                temperature_c=specific.get("temperature_c", 0.0),
                uptime_s=uptime,
                faults=self._fault_reason and [self._fault_reason] or [],
                payload_specific=specific.get("payload_specific", {}),
                simulated=self.sim_mode,
            )
        except Exception as e:
            logger.exception(f"[{self.payload_id}] health_check failed: {e}")
            return PayloadHealth(
                status="FAULTED",
                faults=[f"health_check: {e}"],
                simulated=self.sim_mode,
            )

    def teardown(self) -> None:
        """Release all hardware resources. Idempotent."""
        try:
            if self._state in (PayloadState.ACTIVE, PayloadState.READY):
                self.deactivate()
            self._deinit_hardware()
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Teardown error: {e}")
        finally:
            self._transition(PayloadState.TEARDOWN)
            logger.info(f"[{self.payload_id}] Teardown complete.")

    # ------------------------------------------------------------------
    # Command interface
    # ------------------------------------------------------------------

    def execute_command(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> PayloadCommandResult:
        """Dispatch a payload-specific command.

        The base implementation checks that the payload is ACTIVE (unless
        the action is a query) and delegates to _execute_impl().

        Args:
            action: Command name, must be in self.commands list.
            params: Optional dict of parameters.

        Returns:
            PayloadCommandResult with success, message, and data.
        """
        params = params or {}

        if action not in self.commands:
            return PayloadCommandResult(
                success=False,
                message=f"Unknown command '{action}'. "
                        f"Supported: {self.commands}",
            )

        # Queries don't require ACTIVE state
        is_query = action.startswith("get_")
        if not is_query and self._state != PayloadState.ACTIVE:
            return PayloadCommandResult(
                success=False,
                message=f"Cannot execute '{action}': payload is {self._state.name}. "
                        "Must be ACTIVE.",
            )

        try:
            return self._execute_impl(action, params)
        except Exception as e:
            logger.exception(f"[{self.payload_id}] Command '{action}' failed: {e}")
            return PayloadCommandResult(
                success=False,
                message=f"Command '{action}' failed: {e}",
            )

    # ------------------------------------------------------------------
    # Payload metadata
    # ------------------------------------------------------------------

    def get_info(self) -> PayloadInfo:
        """Return static metadata for this payload instance."""
        return PayloadInfo(
            payload_id=self.payload_id,
            payload_type=self.payload_type,
            display_name=self.display_name,
            version=self.version,
            mass_g=self.mass_g,
            power_max_ma=self.power_max_ma,
            power_nominal_ma=self.power_nominal_ma,
            commands=list(self.commands),
            bus_addresses=dict(self.bus_addresses),
            critical=self.critical,
            mount_required=self.mount_required,
        )

    # ==================================================================
    # SUBCLASS OVERRIDES — Hardware-specific implementations
    # ==================================================================

    @abstractmethod
    def _init_hardware(self, **kwargs: Any) -> None:
        """Set up I2C devices, allocate GPIOs, configure peripherals.

        Called by initialize(). Raise exception on failure.
        In SIM_MODE, this should be a no-op.
        """
        ...

    @abstractmethod
    def _deinit_hardware(self) -> None:
        """Release all hardware resources.

        Called by teardown(). Must be idempotent.
        """
        ...

    @abstractmethod
    def _enable_power(self) -> None:
        """Enable the payload power rail (switch on MOSFET).

        Must verify voltage is stable before returning.
        Raise exception on failure.
        """
        ...

    @abstractmethod
    def _disable_power(self) -> None:
        """Disable the payload power rail (switch off MOSFET).

        Must verify voltage drops to 0. Raise exception on failure.
        """
        ...

    @abstractmethod
    def _arm_outputs(self) -> None:
        """Arm payload outputs after power-on.

        E.g., enable servo PWM, prime pump, start video stream.
        """
        ...

    @abstractmethod
    def _disarm_outputs(self) -> None:
        """Safely disarm outputs before power-off.

        E.g., center servos, stop pump, flush buffers.
        """
        ...

    @abstractmethod
    def _emergency_cut(self) -> None:
        """Hardware-level emergency power cut.

        Must complete within 50ms. Direct GPIO toggle preferred.
        Overrides all software state.
        """
        ...

    @abstractmethod
    def _read_health_specific(self) -> Dict[str, Any]:
        """Read payload-specific health data.

        Returns dict with keys:
            status: "OK" | "DEGRADED" | "FAULTED"
            power_voltage_v: float
            power_current_ma: float
            temperature_c: float
            payload_specific: dict
        """
        ...

    @abstractmethod
    def _execute_impl(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> PayloadCommandResult:
        """Implement payload-specific command logic.

        Args:
            action: Command name (validated to be in self.commands).
            params: Command parameters.

        Returns:
            PayloadCommandResult.
        """
        ...
