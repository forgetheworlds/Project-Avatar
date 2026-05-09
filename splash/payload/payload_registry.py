"""
payload_registry.py — Payload discovery, registration, and health monitoring.

Handles:
  • Bus scanning: calls discover() on each known payload class
  • Registration: assigns payload IDs, tracks instances
  • Activation/deactivation with power budget enforcement
  • Health monitoring: periodic health_check() polling at 10Hz
  • Fault handling: emergency_stop on failure, mission-abort decisions
  • Command dispatch: route payload-specific commands

Project Avatar — Modular payload interface system.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Type

from splash.payload.base_payload import (
    BasePayload,
    PayloadState,
    PayloadInfo,
    PayloadHealth,
    PayloadCommandResult,
)

logger = logging.getLogger("splash.payload.registry")


# ==============================================================================
# Registry exceptions
# ==============================================================================

class PayloadNotReadyError(Exception):
    """Payload is not in a state that allows the requested operation."""

class PayloadFaultError(Exception):
    """Payload is in FAULTED state and cannot be used."""

class PayloadPowerLimitError(Exception):
    """Activation would exceed the total power budget."""


# ==============================================================================
# PayloadRegistry
# ==============================================================================

class PayloadRegistry:
    """Central registry for all payloads on the drone.

    Usage:
        registry = PayloadRegistry(
            known_payloads=[SplashPayload, CameraPayload],
            sim_mode=True,
            power_budget_ma=5000,
        )
        registry.scan_bus()
        registry.activate("splash_0")
        registry.execute("splash_0", "fire", {"duration_ms": 500})

    The optional health monitor thread polls all active payloads at
    configurable frequency and invokes a callback on fault detection.
    """

    # Maximum total payload current (mA). 5A is a safe BEC budget on a
    # 4S setup after accounting for FC, GPS, RX, and ESP32 (~1.5A).
    DEFAULT_POWER_BUDGET_MA = 5000

    # Health monitor poll interval in seconds
    DEFAULT_HEALTH_POLL_INTERVAL_S = 0.1  # 10 Hz

    def __init__(
        self,
        known_payloads: Optional[List[Type[BasePayload]]] = None,
        sim_mode: bool = True,
        power_budget_ma: int = DEFAULT_POWER_BUDGET_MA,
        health_poll_interval_s: float = DEFAULT_HEALTH_POLL_INTERVAL_S,
        on_fault: Optional[Callable[[str, PayloadHealth], None]] = None,
    ) -> None:
        """
        Args:
            known_payloads: List of payload classes to scan for.
            sim_mode: If True, all hardware ops are simulated.
            power_budget_ma: Maximum total payload current in mA.
            health_poll_interval_s: Health monitor poll interval.
            on_fault: Callback(payload_id, health) on fault detection.
        """
        self._known_classes: List[Type[BasePayload]] = list(known_payloads or [])
        self._sim_mode = sim_mode
        self._power_budget_ma = power_budget_ma
        self._health_poll_interval_s = health_poll_interval_s
        self._on_fault = on_fault

        # Registered payloads: payload_id → BasePayload instance
        self._payloads: Dict[str, BasePayload] = {}
        self._lock = threading.Lock()

        # Health monitor
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop = threading.Event()

        logger.info(
            f"PayloadRegistry initialized: {len(self._known_classes)} known types, "
            f"budget={power_budget_ma}mA, sim={sim_mode}"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_class(self, payload_class: Type[BasePayload]) -> None:
        """Add a payload class to the known list."""
        if payload_class not in self._known_classes:
            self._known_classes.append(payload_class)
            logger.info(f"Registered payload class: {payload_class.__name__}")

    def scan_bus(self, **bus_kwargs: Any) -> List[PayloadInfo]:
        """Scan the hardware bus for all known payload types.

        Calls cls.discover() for each known payload class. Assigns a
        unique payload_id to each discovered instance and registers it.

        In SIM_MODE, all payloads are "discovered" (for testing).

        Args:
            **bus_kwargs: Passed to cls.discover() (e.g., i2c_bus).

        Returns:
            List of PayloadInfo for all discovered payloads.
        """
        discovered: List[PayloadInfo] = []

        with self._lock:
            for cls in self._known_classes:
                try:
                    if cls.discover(sim_mode=self._sim_mode, **bus_kwargs):
                        # Assign instance ID
                        count = sum(
                            1 for p in self._payloads.values()
                            if isinstance(p, cls)
                        )
                        instance_id = f"{cls.__name__.replace('Payload', '').lower()}_{count}"

                        # Instantiate
                        instance = cls(
                            payload_id=instance_id,
                            sim_mode=self._sim_mode,
                        )

                        # Initialize
                        if instance.initialize(**bus_kwargs):
                            self._payloads[instance_id] = instance
                            info = instance.get_info()
                            discovered.append(info)
                            logger.info(
                                f"Discovered: {info.display_name} ({instance_id}) "
                                f"— {info.mass_g}g, {info.power_max_ma}mA max"
                            )
                        else:
                            logger.warning(
                                f"Discovery found {cls.__name__} but init failed."
                            )
                    else:
                        logger.debug(f"{cls.__name__} not found on bus.")
                except Exception as e:
                    logger.error(f"Error scanning {cls.__name__}: {e}")

        logger.info(
            f"Bus scan complete: {len(discovered)} payload(s) found "
            f"(sim={self._sim_mode})"
        )
        return discovered

    # ------------------------------------------------------------------
    # Payload access
    # ------------------------------------------------------------------

    def get(self, payload_id: str) -> Optional[BasePayload]:
        """Get a registered payload by ID."""
        with self._lock:
            return self._payloads.get(payload_id)

    def list_all(self) -> List[PayloadInfo]:
        """Return PayloadInfo for all registered payloads."""
        with self._lock:
            return [p.get_info() for p in self._payloads.values()]

    def list_active(self) -> List[PayloadInfo]:
        """Return PayloadInfo for active payloads."""
        with self._lock:
            return [
                p.get_info() for p in self._payloads.values()
                if p.state == PayloadState.ACTIVE
            ]

    def list_ready(self) -> List[PayloadInfo]:
        """Return PayloadInfo for ready (initialized, not active) payloads."""
        with self._lock:
            return [
                p.get_info() for p in self._payloads.values()
                if p.state == PayloadState.READY
            ]

    def get_payloads_of_type(self, payload_type: str) -> List[BasePayload]:
        """Get all registered payloads of a given type."""
        with self._lock:
            return [
                p for p in self._payloads.values()
                if p.payload_type == payload_type
            ]

    # ------------------------------------------------------------------
    # Activation / Deactivation
    # ------------------------------------------------------------------

    def activate(self, payload_id: str) -> bool:
        """Activate a payload (power on, arm outputs).

        Enforces the total power budget. If activating this payload
        would exceed the budget, raises PayloadPowerLimitError.

        Returns True on success.
        """
        with self._lock:
            payload = self._payloads.get(payload_id)
            if payload is None:
                raise PayloadNotReadyError(f"Payload '{payload_id}' not registered.")

            if payload.state == PayloadState.ACTIVE:
                logger.info(f"[{payload_id}] Already active.")
                return True

            if payload.state == PayloadState.FAULTED:
                raise PayloadFaultError(
                    f"Payload '{payload_id}' is FAULTED: {payload.fault_reason}"
                )

            if payload.state != PayloadState.READY:
                raise PayloadNotReadyError(
                    f"Payload '{payload_id}' is {payload.state.name}, not READY."
                )

            # Check power budget
            current_draw = self._total_active_power_ma_locked()
            if current_draw + payload.power_max_ma > self._power_budget_ma:
                raise PayloadPowerLimitError(
                    f"Activating '{payload_id}' ({payload.power_max_ma}mA) "
                    f"would exceed budget: {current_draw}mA active + "
                    f"{payload.power_max_ma}mA > {self._power_budget_ma}mA"
                )

        # Activate outside lock (may take time)
        success = payload.activate()

        # Start health monitor if first active payload
        if success:
            self._ensure_monitor_running()

        return success

    def deactivate(self, payload_id: str) -> bool:
        """Gracefully deactivate a payload."""
        with self._lock:
            payload = self._payloads.get(payload_id)
            if payload is None:
                logger.warning(f"deactivate: '{payload_id}' not found.")
                return False

        return payload.deactivate()

    def deactivate_all(self) -> None:
        """Deactivate all active payloads (e.g., on mission end)."""
        with self._lock:
            active_ids = [
                pid for pid, p in self._payloads.items()
                if p.state == PayloadState.ACTIVE
            ]
        for pid in active_ids:
            self.deactivate(pid)

    def emergency_stop_all(self) -> None:
        """Emergency-stop all payloads."""
        with self._lock:
            ids = list(self._payloads.keys())
        for pid in ids:
            self.emergency_stop(pid)

    def emergency_stop(self, payload_id: str) -> bool:
        """Emergency-stop a specific payload."""
        with self._lock:
            payload = self._payloads.get(payload_id)
        if payload:
            return payload.emergency_stop()
        return False

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def execute(
        self,
        payload_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> PayloadCommandResult:
        """Execute a command on a specific payload.

        Args:
            payload_id: Target payload ID.
            action: Command name (must be in payload's commands list).
            params: Optional parameters dict.

        Returns:
            PayloadCommandResult.
        """
        with self._lock:
            payload = self._payloads.get(payload_id)
            if payload is None:
                return PayloadCommandResult(
                    success=False,
                    message=f"Payload '{payload_id}' not registered.",
                )

        return payload.execute_command(action, params)

    # ------------------------------------------------------------------
    # Fault handling
    # ------------------------------------------------------------------

    def mark_faulted(self, payload_id: str, reason: str = "") -> None:
        """Explicitly mark a payload as faulted."""
        with self._lock:
            payload = self._payloads.get(payload_id)
            if payload and payload.state != PayloadState.FAULTED:
                payload._fault_reason = reason or "manually marked faulted"
                payload._transition(PayloadState.FAULTED)
                logger.error(f"[{payload_id}] Marked FAULTED: {payload._fault_reason}")

    def critical_payload_failed(self) -> bool:
        """Check if any critical (mission-essential) payload has faulted."""
        with self._lock:
            for p in self._payloads.values():
                if p.state == PayloadState.FAULTED and p.critical:
                    return True
        return False

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    def _ensure_monitor_running(self) -> None:
        """Start the health monitor thread if not already running."""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._health_monitor_loop,
                daemon=True,
                name="payload-health",
            )
            self._monitor_thread.start()
            logger.info("Health monitor started.")

    def _health_monitor_loop(self) -> None:
        """Background thread: poll health_check() on all active payloads."""
        while not self._monitor_stop.is_set():
            active_snapshot: List[BasePayload] = []
            with self._lock:
                active_snapshot = [
                    p for p in self._payloads.values()
                    if p.state == PayloadState.ACTIVE
                ]

            if not active_snapshot:
                # No active payloads — stop the monitor
                logger.info("Health monitor: no active payloads, stopping.")
                break

            for payload in active_snapshot:
                try:
                    health = payload.health_check()
                    if health.status == "FAULTED":
                        logger.error(
                            f"[{payload.payload_id}] Health FAULTED: "
                            f"faults={health.faults}"
                        )
                        payload.emergency_stop()
                        with self._lock:
                            payload._transition(PayloadState.FAULTED)

                        if self._on_fault:
                            try:
                                self._on_fault(payload.payload_id, health)
                            except Exception:
                                logger.exception("on_fault callback failed")

                    elif health.status == "DEGRADED":
                        logger.warning(
                            f"[{payload.payload_id}] Health DEGRADED: "
                            f"{health.faults}"
                        )
                except Exception:
                    logger.exception(
                        f"[{payload.payload_id}] health_check() raised exception"
                    )
                    # Mark as faulted on exception
                    try:
                        payload.emergency_stop()
                    except Exception:
                        pass
                    with self._lock:
                        payload._transition(PayloadState.FAULTED)

            self._monitor_stop.wait(self._health_poll_interval_s)

        self._monitor_thread = None
        logger.info("Health monitor stopped.")

    def stop_health_monitor(self) -> None:
        """Stop the health monitor thread."""
        self._monitor_stop.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3.0)

    def health_status_all(self) -> Dict[str, Dict[str, Any]]:
        """Return health report for all registered payloads."""
        result = {}
        with self._lock:
            for pid, payload in self._payloads.items():
                try:
                    health = payload.health_check()
                    result[pid] = {
                        "health": health.to_dict(),
                        "state": payload.state.name,
                        "type": payload.payload_type,
                    }
                except Exception as e:
                    result[pid] = {
                        "health": {"status": "FAULTED", "faults": [str(e)]},
                        "state": "FAULTED",
                        "type": payload.payload_type,
                    }
        return result

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def teardown_all(self) -> None:
        """Teardown all payloads: deactivate, release resources."""
        self.stop_health_monitor()
        with self._lock:
            ids = list(self._payloads.keys())
        for pid in ids:
            try:
                with self._lock:
                    p = self._payloads.get(pid)
                if p:
                    p.teardown()
            except Exception:
                logger.exception(f"Teardown failed for {pid}")
        with self._lock:
            self._payloads.clear()
        logger.info("All payloads torn down.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _total_active_power_ma_locked(self) -> int:
        """Total power draw of active payloads (must hold lock)."""
        total = 0
        for p in self._payloads.values():
            if p.state == PayloadState.ACTIVE:
                total += p.power_max_ma
        return total

    @property
    def total_active_power_ma(self) -> int:
        """Public read of total active power draw."""
        with self._lock:
            return self._total_active_power_ma_locked()

    @property
    def payload_count(self) -> int:
        """Number of registered payloads."""
        with self._lock:
            return len(self._payloads)
