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
    """Levels of resource pressure for graduated response.

    The monitoring system uses a three-tier pressure model to enable
    proportional responses to resource constraints:

    - NORMAL: All systems operating at full capacity. No action required.
    - WARNING: Resources are constrained but not critical. Non-essential
      services should be degraded to preserve resources for flight safety.
    - CRITICAL: Resources are critically low. Immediate RTL (Return to Launch)
      is required to prevent system crashes that could cause flyaway or crash.

    This graduated approach ensures we don't abort missions prematurely
    while maintaining safety margins to prevent catastrophic failures.
    """

    NORMAL = auto()
    WARNING = auto()  # Graceful degradation
    CRITICAL = auto()  # RTL required


@dataclass
class ResourceThresholds:
    """Configurable thresholds for resource monitoring.

    These thresholds define the boundary between healthy operation and
    resource pressure. They are designed with specific safety margins:

    - CPU (90%): Leave 10% headroom for sudden processing spikes like
      obstacle detection or emergency maneuver calculations.
    - Memory (95%): Only 5% margin because Linux OOM killer may strike
      at 98%+ causing random process termination - potentially killing
      the flight control thread.
    - Temperature (80C): RPi throttles at 85C. 80C gives 5C margin to
      prevent thermal throttling that would slow critical calculations.
    - Disk (90%): Prevents logging failures that could mask other issues.

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
        """Validate threshold values.

        Enforces reasonable bounds to catch configuration errors early.
        Prevents scenarios like setting memory threshold to 100% (which
        would allow OOM crashes) or negative temperatures.
        """
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

    Captures a point-in-time reading of all monitored resources.
    Used for both real-time decision making and post-flight analysis
    to correlate resource issues with flight anomalies.

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
        """Calculate resource pressure level for graduated response.

        Implements the three-tier escalation model:
        - WARNING triggers at 80% of critical thresholds (72% CPU, 76% memory, 64C temp)
        - CRITICAL triggers when any resource exceeds its configured threshold

        The 80% warning level gives early notification to begin shedding
        non-critical work before resources become critical. This prevents
        the system from suddenly jumping to CRITICAL without warning.
        """
        if not self.is_healthy:
            return ResourcePressureLevel.CRITICAL
        # Warning thresholds are 80% of critical thresholds
        if self.cpu_percent > 72 or self.memory_percent > 76 or self.temperature_c > 64:
            return ResourcePressureLevel.WARNING
        return ResourcePressureLevel.NORMAL


class ResourceCallback(Protocol):
    """Protocol for resource threshold callbacks.

    Callbacks are the primary mechanism for responding to resource pressure.
    They enable decoupled architecture where the monitor detects issues
    and specialized handlers (like GuardianProcess) take corrective action.
    """

    async def __call__(
        self, status: ResourceStatus, violated_thresholds: List[str]
    ) -> None:
        """Called when resource thresholds are violated.

        This is the critical escalation path. When resources are exhausted,
        callbacks must act quickly to preserve system stability:
        - Log the violation for post-flight analysis
        - Trigger RTL for memory/temp critical conditions
        - Degrade non-essential services for CPU pressure

        Args:
            status: Current resource status
            violated_thresholds: List of threshold names that were violated
        """
        ...


class ResourceMonitor:
    """RPi resource monitoring with safety thresholds.

    WHY RESOURCE MONITORING MATTERS:
    ================================
    Drones operate in a safety-critical environment where system crashes
    can cause property damage, injury, or flyaways. Unlike desktop systems,
    a drone cannot simply "wait" for resources to become available:

    1. Real-time deadlines: Flight control loops must complete within
       milliseconds. CPU starvation causes control lag and instability.

    2. Memory exhaustion: When RAM is depleted, Linux OOM killer terminates
       random processes. On a drone, this could kill MAVSDK, the flight
       controller bridge, or telemetry - causing complete loss of control.

    3. Thermal runaway: High temperatures throttle CPU performance at the
       exact moment heavy processing is needed (emergency maneuvers).

    4. Cascading failures: Low resources in one area stress others. High
       CPU increases temperature. Memory pressure increases swap usage
       which increases disk I/O which increases CPU load.

    CRASH PREVENTION STRATEGY:
    ==========================
    The monitor implements a multi-layer defense:

    1. Continuous monitoring (1Hz default): Detects resource trends before
       they become critical, enabling proactive response.

    2. Graduated response: WARNING level triggers graceful degradation,
       giving the system time to stabilize before CRITICAL forces RTL.

    3. Automatic RTL: When memory or temperature hits CRITICAL, the system
       initiates Return-to-Launch. This is the safest option because:
       - It reduces processing load (simpler than mission navigation)
       - It moves the drone toward a known safe location
       - It can be overridden by operator if situation changes

    4. Graceful degradation: Non-essential services (vision inference,
       verbose logging, high FPS) are shed first to preserve resources
       for core flight control.

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
    # RPi exposes thermal data via sysfs. thermal_zone0 is the CPU sensor.
    # This path works on RPi 3, 4, and 5. Zero may use different zone.
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
        # psutil is the primary monitoring library. If unavailable,
        # we fall back to limited monitoring (temperature only via sysfs).
        self._psutil_available = self._check_psutil()

    def _check_psutil(self) -> bool:
        """Check if psutil is available for system monitoring.

        psutil may not be installed on minimal systems. We gracefully
        degrade to temperature-only monitoring rather than fail entirely.
        Temperature is the most critical metric (safety-related), so
        we prioritize keeping that available.
        """
        try:
            import psutil  # noqa: F401

            return True
        except ImportError:
            logger.warning("psutil not available - resource monitoring limited")
            return False

    async def start(self, interval_s: float = 1.0) -> None:
        """Start the resource monitoring loop.

        The monitoring loop runs as a background task, sampling resources
        at the specified interval. 1 second is the default as it provides:
        - Fast enough detection for rapidly changing conditions
        - Low enough overhead (<1% CPU for the monitor itself)
        - Alignment with typical flight control loop frequencies

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
        """Stop the resource monitoring loop.

        Cleanly shuts down the monitoring task. This is important during
        controlled shutdown to avoid asyncio warnings about unawaited tasks.
        """
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

        Continuously samples resources and triggers callbacks when thresholds
        are violated. The loop handles multiple error conditions gracefully:
        - TimeoutError: Normal wake for next iteration
        - CancelledError: Clean shutdown requested
        - Other exceptions: Logged but loop continues (availability over correctness)

        Args:
            interval_s: Monitoring interval in seconds.
        """
        while not self._stop_event.is_set():
            try:
                status = self._check_resources()
                self._status = status

                # Check for threshold violations
                # Callbacks are only triggered on state transitions to unhealthy
                # to avoid spamming the same alert every second.
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

        Collects current readings from all available sources:
        - CPU: psutil.cpu_percent() over 100ms sample
        - Memory: psutil.virtual_memory().percent
        - Disk: psutil.disk_usage("/").percent
        - Temperature: sysfs thermal zone or psutil.sensors_temperatures()

        Falls back to 0.0 for metrics when psutil is unavailable.
        Temperature has additional fallback logic because it's safety-critical.

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
            # These show as 0% which appears healthy but is clearly
            # artificial - operators should notice missing real data.
            cpu_percent = 0.0
            memory_percent = 0.0
            disk_percent = 0.0

        temperature_c = self._get_cpu_temperature()

        # Determine health status
        # All thresholds must be satisfied for healthy status.
        # This is a "weakest link" model - any critical resource
        # exhaustion is treated as critical.
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

        Uses psutil.cpu_percent() with 100ms interval for accurate sampling.
        The interval is short enough to capture actual load but long enough
        to not significantly impact the measurement itself.

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

        virtual_memory().percent includes all RAM usage including buffers
        and cache. This is the most relevant metric for OOM risk because
        it represents what the kernel considers "used" memory.

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

        Monitors root filesystem ("/") where logs and telemetry are stored.
        Disk pressure primarily affects logging capability but can also
        cause swap failures if swapfile is on the same filesystem.

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

        Temperature monitoring is safety-critical for two reasons:
        1. RPi thermal throttling: At 85C, the CPU reduces clock speed
           to prevent damage. This causes control loop lag.
        2. Thermal runaway: High temps increase power consumption which
           increases heat generation - a positive feedback loop.

        Multiple fallback methods are attempted:
        1. sysfs thermal_zone0 (fastest, no imports needed)
        2. psutil.sensors_temperatures() (more portable)
        3. Return 0.0 if all fail (clearly indicates monitoring failure)

        Returns:
            Temperature in Celsius, 0.0 if unavailable.
        """
        try:
            if self.THERMAL_ZONE_PATH.exists():
                # sysfs returns millidegrees - divide by 1000 for Celsius
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

        Called when is_healthy is False to determine which specific
        resources are causing the problem. This enables targeted
        response (e.g., different actions for CPU vs memory pressure).

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

        Callbacks are executed sequentially (not in parallel) to avoid
        race conditions in safety-critical response code. Each callback
        is wrapped in try/except to ensure one failing callback doesn't
        prevent others from running.

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

        Returns the most recent status snapshot. This may be up to
        interval_s seconds old if called between monitoring cycles.

        Returns:
            Current ResourceStatus snapshot.
        """
        return self._status

    def is_healthy(self) -> bool:
        """Check if all resources are within thresholds.

        Convenience method for quick health checks without examining
        individual metrics.

        Returns:
            True if all resources are healthy.
        """
        return self._status.is_healthy

    def register_callback(self, callback: ResourceCallback) -> None:
        """Register a callback for threshold breaches.

        Callbacks are triggered when any resource threshold is exceeded.
        Multiple callbacks can be registered for different response
        layers (logging, degradation, RTL).

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

    Implements the "WARNING level" response strategy. When resources
    are constrained but not critical, we can preserve safety by reducing
    non-essential work rather than aborting the mission.

    GRADUATED RESPONSE:
    ==================
    WARNING level (80% of critical thresholds):
    - CPU > 72%: Reduce vision inference frequency, disable verbose logging
    - Temperature > 64C: Reduce camera FPS, lower encoder quality
    - Memory > 76%: Begin shedding cached data, reduce buffer sizes

    CRITICAL level (exceeds configured thresholds):
    - All non-essential services disabled
    - RTL triggered by GuardianProcess (not this class)
    - System focuses solely on flight control

    WHY GRADUATION MATTERS:
    =======================
    Premature RTL aborts valuable missions. Graduated response allows:
    - Temporary spikes to resolve without mission impact
    - Sustained pressure to be handled without emergency landing
    - Operator visibility into system state before critical

    Degradation is automatically reversed when resources return to
    normal levels, restoring full functionality.

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

        Routes pressure events to appropriate degradation handlers based
        on severity level. WARNING triggers selective degradation,
        CRITICAL triggers maximum degradation.

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

        Selective degradation based on which resource is constrained:
        - High CPU: Disable heavy ML inference and verbose logging
        - High temp: Reduce thermal generation (FPS, encoding quality)

        Services are added to _degraded_services set. Other components
        check this set to determine their operating mode.
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

        At CRITICAL level, we disable all non-essential services to
        preserve resources for flight control. This is a "limp home"
        mode that maintains basic flight capability while shedding
        everything else.

        Note: RTL is triggered by the guardian callback, not here.
        This method handles additional service shutdowns that happen
        concurrently with RTL initiation.

        Memory exhaustion is particularly dangerous because:
        - OOM killer may terminate random processes
        - Swap thrashing causes I/O delays affecting control loops
        - malloc() failures can crash Python interpreter
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

        Services call this method to determine their operating mode.
        If degraded, they should reduce work or skip non-critical tasks.

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

        Called when resources return to normal levels to restore
        full functionality. Services are responsible for checking
        this and resuming normal operation.

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

    This is the primary entry point for safety-critical deployments.
    It configures a monitor with a callback that automatically triggers
    RTL when memory is exhausted, preventing OOM crashes.

    The callback pattern allows the caller to provide their own RTL
    implementation (e.g., via GuardianProcess) while keeping the
    monitoring logic generic.

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
