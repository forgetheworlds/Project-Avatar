"""Resource monitoring for RPi with safety thresholds.

Monitors CPU, memory, temperature, and disk usage with configurable thresholds.
Provides graceful degradation and auto-triggers RTL on critical resource exhaustion.

Example:
    monitor = ResourceMonitor(thresholds=ResourceThresholds())
    await monitor.start()

    # Check current status
    status = monitor.get_status()
    if not status.is_healthy:
        await guardian.initiate_rtl("resource_critical")
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Set, Any, Coroutine, cast

logger = logging.getLogger(__name__)


class ResourcePressureLevel(Enum):
    """Levels of resource pressure for graduated response."""

    NORMAL = auto()
    WARNING = auto()  # Graceful degradation
    CRITICAL = auto()  # RTL required


@dataclass
class ResourceThresholds:
    """Configurable thresholds for resource monitoring.

    Attributes:
        cpu_percent: CPU usage percentage threshold (default: 90.0)
        memory_percent: Memory usage percentage threshold (default: 95.0)
        temperature_c: Temperature threshold in Celsius (default: 80.0)
        disk_percent: Disk usage percentage threshold (default: 90.0)
    """

    cpu_percent: float = 90.0
    memory_percent: float = 95.0
    temperature_c: float = 80.0
    disk_percent: float = 90.0

    def __post_init__(self) -> None:
        """Validate threshold values."""
        if not 0 <= self.cpu_percent <= 100:
            raise ValueError(f"cpu_percent must be 0-100, got {self.cpu_percent}")
        if not 0 <= self.memory_percent <= 100:
            raise ValueError(f"memory_percent must be 0-100, got {self.memory_percent}")
        if self.temperature_c < 0 or self.temperature_c > 150:
            raise ValueError(f"temperature_c must be 0-150C, got {self.temperature_c}")
        if not 0 <= self.disk_percent <= 100:
            raise ValueError(f"disk_percent must be 0-100, got {self.disk_percent}")


@dataclass
class ResourceStatus:
    """Current resource status snapshot.

    Attributes:
        cpu_percent: Current CPU usage percentage
        memory_percent: Current memory usage percentage
        temperature_c: Current temperature in Celsius
        disk_percent: Current disk usage percentage
        timestamp: Unix timestamp of the reading
        is_healthy: True if all resources within thresholds
    """

    cpu_percent: float
    memory_percent: float
    temperature_c: float
    disk_percent: float
    timestamp: float
    is_healthy: bool

    @property
    def pressure_level(self) -> ResourcePressureLevel:
        """Calculate resource pressure level for graduated response."""
        if not self.is_healthy:
            return ResourcePressureLevel.CRITICAL
        # Warning thresholds are 80% of critical thresholds
        if self.cpu_percent > 72 or self.memory_percent > 76 or self.temperature_c > 64:
            return ResourcePressureLevel.WARNING
        return ResourcePressureLevel.NORMAL


class ResourceCallback(Protocol):
    """Protocol for resource threshold callbacks."""

    async def __call__(
        self, status: ResourceStatus, violated_thresholds: List[str]
    ) -> None:
        """Called when resource thresholds are violated.

        Args:
            status: Current resource status
            violated_thresholds: List of threshold names that were violated
        """
        ...


class ResourceMonitor:
    """RPi resource monitoring with safety thresholds.

    Thresholds:
    - CPU > 90%: Degrade performance (reduce processing)
    - Memory > 95%: Trigger RTL (safety-critical)
    - Temperature > 80C: Degrade + warning (throttle performance)
    - Disk > 90%: Warning only (logging may be affected)

    Usage:
        monitor = ResourceMonitor(thresholds=ResourceThresholds())
        await monitor.start()

        # Register callback for threshold breaches
        async def on_threshold_breach(status, violated):
            if "memory" in violated:
                await guardian.initiate_rtl("memory_critical")

        monitor.register_callback(on_threshold_breach)

        # Get current status
        status = monitor.get_status()
        if not status.is_healthy:
            logger.warning(f"Resource pressure: {status.pressure_level}")
    """

    # Thermal zone path for RPi (may vary by model)
    THERMAL_ZONE_PATH = Path("/sys/class/thermal/thermal_zone0/temp")

    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        """Initialize resource monitor.

        Args:
            thresholds: Resource thresholds. Uses defaults if not provided.
        """
        self.thresholds = thresholds or ResourceThresholds()
        self._status = ResourceStatus(
            cpu_percent=0.0,
            memory_percent=0.0,
            temperature_c=0.0,
            disk_percent=0.0,
            timestamp=0.0,
            is_healthy=True,
        )
        self._task: Optional[asyncio.Task[None]] = None
        self._callbacks: List[ResourceCallback] = []
        self._stop_event = asyncio.Event()
        self._running = False

        # Track psutil availability
        self._psutil_available = self._check_psutil()

    def _check_psutil(self) -> bool:
        """Check if psutil is available for system monitoring."""
        try:
            import psutil  # noqa: F401

            return True
        except ImportError:
            logger.warning("psutil not available - resource monitoring limited")
            return False

    async def start(self, interval_s: float = 1.0) -> None:
        """Start the resource monitoring loop.

        Args:
            interval_s: Monitoring interval in seconds (default: 1.0)

        Raises:
            RuntimeError: If already running.
        """
        if self._running:
            raise RuntimeError("ResourceMonitor already running")

        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop(interval_s))
        logger.info(f"ResourceMonitor started (interval={interval_s}s)")

    async def stop(self) -> None:
        """Stop the resource monitoring loop."""
        if not self._running:
            return

        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self._running = False
        logger.info("ResourceMonitor stopped")

    async def _monitor_loop(self, interval_s: float) -> None:
        """Main monitoring loop.

        Args:
            interval_s: Monitoring interval in seconds.
        """
        while not self._stop_event.is_set():
            try:
                status = self._check_resources()
                self._status = status

                # Check for threshold violations
                if not status.is_healthy:
                    violated = self._get_violated_thresholds(status)
                    await self._trigger_callbacks(status, violated)

                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=interval_s
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(interval_s)

    def _check_resources(self) -> ResourceStatus:
        """Check all resource metrics.

        Returns:
            ResourceStatus with current readings and health status.
        """
        timestamp = time.time()

        if self._psutil_available:
            cpu_percent = self._get_cpu_percent()
            memory_percent = self._get_memory_percent()
            disk_percent = self._get_disk_percent()
        else:
            # Fallback values when psutil unavailable
            cpu_percent = 0.0
            memory_percent = 0.0
            disk_percent = 0.0

        temperature_c = self._get_cpu_temperature()

        # Determine health status
        is_healthy = (
            cpu_percent <= self.thresholds.cpu_percent
            and memory_percent <= self.thresholds.memory_percent
            and temperature_c <= self.thresholds.temperature_c
            and disk_percent <= self.thresholds.disk_percent
        )

        return ResourceStatus(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            temperature_c=temperature_c,
            disk_percent=disk_percent,
            timestamp=timestamp,
            is_healthy=is_healthy,
        )

    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage.

        Returns:
            CPU usage percentage (0-100).
        """
        try:
            import psutil

            return cast(float, psutil.cpu_percent(interval=0.1))
        except Exception as e:
            logger.debug(f"Failed to get CPU percent: {e}")
            return 0.0

    def _get_memory_percent(self) -> float:
        """Get current memory usage percentage.

        Returns:
            Memory usage percentage (0-100).
        """
        try:
            import psutil

            return cast(float, psutil.virtual_memory().percent)
        except Exception as e:
            logger.debug(f"Failed to get memory percent: {e}")
            return 0.0

    def _get_disk_percent(self) -> float:
        """Get current disk usage percentage.

        Returns:
            Disk usage percentage (0-100).
        """
        try:
            import psutil

            return cast(float, psutil.disk_usage("/").percent)
        except Exception as e:
            logger.debug(f"Failed to get disk percent: {e}")
            return 0.0

    def _get_cpu_temperature(self) -> float:
        """Read CPU temperature from thermal zone.

        Returns:
            Temperature in Celsius, 0.0 if unavailable.
        """
        try:
            if self.THERMAL_ZONE_PATH.exists():
                temp_millidegrees = int(self.THERMAL_ZONE_PATH.read_text().strip())
                return temp_millidegrees / 1000.0
        except (OSError, ValueError) as e:
            logger.debug(f"Failed to read temperature: {e}")

        # Fallback: try psutil if available
        try:
            import psutil

            temps = psutil.sensors_temperatures()
            if temps:
                # Look for common temperature sensors
                for name, entries in temps.items():
                    if entries:
                        # Return first available temperature
                        return cast(float, entries[0].current)
        except Exception as e:
            logger.debug(f"Failed to get temperature from psutil: {e}")

        return 0.0

    def _get_violated_thresholds(self, status: ResourceStatus) -> List[str]:
        """Get list of violated threshold names.

        Args:
            status: Current resource status.

        Returns:
            List of threshold names that were violated.
        """
        violated = []
        if status.cpu_percent > self.thresholds.cpu_percent:
            violated.append("cpu")
        if status.memory_percent > self.thresholds.memory_percent:
            violated.append("memory")
        if status.temperature_c > self.thresholds.temperature_c:
            violated.append("temperature")
        if status.disk_percent > self.thresholds.disk_percent:
            violated.append("disk")
        return violated

    async def _trigger_callbacks(
        self, status: ResourceStatus, violated_thresholds: List[str]
    ) -> None:
        """Trigger all registered callbacks.

        Args:
            status: Current resource status.
            violated_thresholds: List of violated threshold names.
        """
        for callback in self._callbacks:
            try:
                await callback(status, violated_thresholds)
            except Exception as e:
                logger.error(f"Resource callback error: {e}")

    def get_status(self) -> ResourceStatus:
        """Get current resource status.

        Returns:
            Current ResourceStatus snapshot.
        """
        return self._status

    def is_healthy(self) -> bool:
        """Check if all resources are within thresholds.

        Returns:
            True if all resources are healthy.
        """
        return self._status.is_healthy

    def register_callback(self, callback: ResourceCallback) -> None:
        """Register a callback for threshold breaches.

        Callbacks are triggered when any resource threshold is exceeded.

        Args:
            callback: Async callable receiving (status, violated_thresholds).
        """
        self._callbacks.append(callback)
        logger.debug(f"Registered resource callback (total: {len(self._callbacks)})")

    def unregister_callback(self, callback: ResourceCallback) -> None:
        """Unregister a callback.

        Args:
            callback: Previously registered callback.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Unregistered resource callback (total: {len(self._callbacks)})")

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    @property
    def callback_count(self) -> int:
        """Number of registered callbacks."""
        return len(self._callbacks)


class GracefulDegradationManager:
    """Manages graceful degradation under resource pressure.

    Provides graduated response to resource pressure:
    - WARNING level: Reduce non-critical processing
    - CRITICAL level: Trigger RTL (RTL initiated by ResourceMonitor callback)

    Usage:
        degradation = GracefulDegradationManager(monitor)
        await degradation.start()

        # In processing loops
        if degradation.should_degrade("vision_processing"):
            # Skip non-critical processing
            continue
    """

    def __init__(self, monitor: ResourceMonitor):
        """Initialize degradation manager.

        Args:
            monitor: ResourceMonitor instance to watch.
        """
        self._monitor = monitor
        self._degraded_services: Set[str] = set()
        self._critical_triggered = False

    async def start(self) -> None:
        """Start monitoring for degradation triggers."""
        self._monitor.register_callback(self._on_resource_pressure)
        logger.info("GracefulDegradationManager started")

    async def stop(self) -> None:
        """Stop degradation monitoring."""
        self._monitor.unregister_callback(self._on_resource_pressure)
        logger.info("GracefulDegradationManager stopped")

    async def _on_resource_pressure(
        self, status: ResourceStatus, violated_thresholds: List[str]
    ) -> None:
        """Handle resource pressure callback.

        Args:
            status: Current resource status.
            violated: List of violated threshold names.
        """
        level = status.pressure_level

        if level == ResourcePressureLevel.WARNING:
            self._apply_warning_degradation(status)
        elif level == ResourcePressureLevel.CRITICAL:
            self._apply_critical_degradation(status, violated_thresholds)

    def _apply_warning_degradation(self, status: ResourceStatus) -> None:
        """Apply degradation for WARNING level pressure.

        Reduces non-critical processing when CPU or temperature is high.
        """
        if status.cpu_percent > 72:
            self._degraded_services.add("vision_inference")
            self._degraded_services.add("logging_verbose")
            logger.warning("Degrading: vision inference and verbose logging")

        if status.temperature_c > 64:
            self._degraded_services.add("high_fps_mode")
            logger.warning("Degrading: reducing to lower FPS mode")

    def _apply_critical_degradation(
        self, status: ResourceStatus, violated: List[str]
    ) -> None:
        """Apply degradation for CRITICAL level pressure.

        Note: RTL is triggered by the guardian callback, not here.
        This method handles additional service shutdowns.
        """
        # Degrade everything non-essential
        self._degraded_services.update([
            "vision_processing",
            "telemetry_logging",
            "mcp_verbose",
        ])

        if "memory" in violated and not self._critical_triggered:
            self._critical_triggered = True
            logger.error("CRITICAL: Memory exhaustion - all non-essential services degraded")

    def should_degrade(self, service_name: str) -> bool:
        """Check if a service should be degraded.

        Args:
            service_name: Name of the service to check.

        Returns:
            True if the service should be degraded.
        """
        return service_name in self._degraded_services

    def is_degraded(self, service_name: str) -> bool:
        """Alias for should_degrade."""
        return self.should_degrade(service_name)

    def clear_degradation(self, service_name: str) -> None:
        """Clear degradation for a specific service.

        Args:
            service_name: Service to restore.
        """
        self._degraded_services.discard(service_name)

    def clear_all_degradation(self) -> None:
        """Clear all degradation flags."""
        self._degraded_services.clear()
        self._critical_triggered = False

    @property
    def degraded_services(self) -> List[str]:
        """List of currently degraded services."""
        return list(self._degraded_services)

    @property
    def has_critical_triggered(self) -> bool:
        """True if critical degradation was ever triggered."""
        return self._critical_triggered


# Convenience function for creating RTL-triggering monitor
async def create_rtl_monitor(
    guardian_callback: Callable[[], Coroutine[Any, Any, None]],
    thresholds: Optional[ResourceThresholds] = None,
) -> ResourceMonitor:
    """Create a resource monitor that triggers RTL on critical memory exhaustion.

    Args:
        guardian_callback: Async callable to trigger RTL.
        thresholds: Resource thresholds. Uses defaults if not provided.

    Returns:
        Configured ResourceMonitor instance.
    """
    monitor = ResourceMonitor(thresholds=thresholds)

    async def _rtl_callback(
        status: ResourceStatus, violated: List[str]
    ) -> None:
        if "memory" in violated:
            logger.error("Memory critical - triggering RTL")
            await guardian_callback()

    monitor.register_callback(cast(ResourceCallback, _rtl_callback))
    return monitor
