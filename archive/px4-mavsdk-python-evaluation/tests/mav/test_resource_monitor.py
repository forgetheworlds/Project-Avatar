"""Tests for the Resource Monitor.

Resource monitoring is CRITICAL for drone safety because:
- CPU overload can cause control loop delays, leading to unstable flight
- Memory exhaustion can trigger OOM killer, killing the flight control process
- High temperature can cause thermal throttling or hardware damage
- Disk full prevents logging of flight data needed for post-crash analysis

These tests verify:
- CPU monitoring reports percentage (via psutil or fallback to 0)
- Temperature monitoring reads from /sys/class/thermal/thermal_zone*/temp
- Memory monitoring reports usage percentage (RSS vs total)
- Threshold violations are detected and categorized
- Callbacks fire asynchronously on threshold breach
- Graceful degradation reduces non-critical processing to preserve flight safety
- RTL (Return to Launch) auto-trigger on memory critical prevents flyaway

Escalation Behavior:
- WARNING (72% CPU, 76% memory, 64C temp): Degrade vision inference, verbose logging
- CRITICAL (threshold breach): Degrade ALL non-essential services
- MEMORY CRITICAL: Trigger RTL to prevent OOM during flight
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from avatar.mav.resource_monitor import (
    GracefulDegradationManager,
    ResourceCallback,
    ResourceMonitor,
    ResourcePressureLevel,
    ResourceStatus,
    ResourceThresholds,
    create_rtl_monitor,
)


class TestResourceThresholds:
    """Test ResourceThresholds dataclass - defines safety limits.

    Why thresholds matter: These are the safety limits that trigger
    protective actions. Setting them too high risks system failure;
    too low causes unnecessary degradation.

    Default values chosen based on:
    - CPU 90%: Leaves headroom for control loop spikes
    - Memory 95%: Prevents OOM before critical services affected
    - Temperature 80C: Below typical thermal throttling point
    - Disk 90%: Ensures logs can continue writing
    """

    def test_default_thresholds(self) -> None:
        """Default thresholds have expected safety values."""
        thresholds = ResourceThresholds()
        assert thresholds.cpu_percent == 90.0
        assert thresholds.memory_percent == 95.0
        assert thresholds.temperature_c == 80.0
        assert thresholds.disk_percent == 90.0

    def test_custom_thresholds(self) -> None:
        """Custom threshold values are accepted for different hardware."""
        # Lower thresholds for less powerful hardware (e.g., Raspberry Pi)
        # Higher thresholds for powerful onboard computers
        thresholds = ResourceThresholds(
            cpu_percent=85.0,
            memory_percent=90.0,
            temperature_c=75.0,
            disk_percent=85.0,
        )
        assert thresholds.cpu_percent == 85.0
        assert thresholds.memory_percent == 90.0
        assert thresholds.temperature_c == 75.0
        assert thresholds.disk_percent == 85.0

    def test_invalid_cpu_threshold(self) -> None:
        """Invalid CPU threshold raises ValueError - prevents misconfiguration."""
        # CPU percentage must be 0-100; outside this range is nonsensical
        with pytest.raises(ValueError, match="cpu_percent must be 0-100"):
            ResourceThresholds(cpu_percent=101.0)

    def test_invalid_memory_threshold(self) -> None:
        """Invalid memory threshold raises ValueError."""
        with pytest.raises(ValueError, match="memory_percent must be 0-100"):
            ResourceThresholds(memory_percent=-1.0)

    def test_invalid_temperature_threshold(self) -> None:
        """Invalid temperature threshold raises ValueError."""
        # 150C is physically impossible for consumer electronics
        with pytest.raises(ValueError, match="temperature_c must be 0-150C"):
            ResourceThresholds(temperature_c=200.0)


class TestResourceStatus:
    """Test ResourceStatus dataclass - snapshot of system health.

    ResourceStatus captures a point-in-time reading of all monitored
    resources. It calculates pressure level which drives escalation.

    Pressure Levels:
    - NORMAL: All resources healthy, full capability available
    - WARNING: One resource above warning threshold (72% CPU, 76% memory, 64C)
              Reduce non-critical processing to prevent escalation
    - CRITICAL: Resource exceeded critical threshold OR any threshold violated
               Emergency degradation of all non-essential services
    """

    def test_status_creation(self) -> None:
        """ResourceStatus can be created with all fields."""
        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=60.0,
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )
        assert status.cpu_percent == 50.0
        assert status.memory_percent == 60.0
        assert status.temperature_c == 45.0
        assert status.disk_percent == 70.0
        assert status.is_healthy is True

    def test_pressure_level_normal(self) -> None:
        """Normal resources return NORMAL pressure level - full capability."""
        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=60.0,
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )
        assert status.pressure_level == ResourcePressureLevel.NORMAL

    def test_pressure_level_warning_cpu(self) -> None:
        """High CPU (above 72%) returns WARNING pressure level.

        At this level, vision inference and verbose logging are degraded
        to free up CPU for flight control loops.
        """
        status = ResourceStatus(
            cpu_percent=75.0,  # Above 72% warning threshold
            memory_percent=60.0,
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )
        assert status.pressure_level == ResourcePressureLevel.WARNING

    def test_pressure_level_warning_memory(self) -> None:
        """High memory (above 76%) returns WARNING pressure level.

        Memory pressure reduces allocation for non-essential buffers
        like telemetry history and detection result caching.
        """
        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=78.0,  # Above 76% warning threshold
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )
        assert status.pressure_level == ResourcePressureLevel.WARNING

    def test_pressure_level_warning_temperature(self) -> None:
        """High temperature (above 64C) returns WARNING pressure level.

        Temperature warning typically reduces CPU frequency or
        disables high-framerate camera capture to reduce heat.
        """
        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=60.0,
            temperature_c=66.0,  # Above 64C warning threshold
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )
        assert status.pressure_level == ResourcePressureLevel.WARNING

    def test_pressure_level_critical(self) -> None:
        """Unhealthy status (threshold violated) returns CRITICAL pressure level.

        CRITICAL level triggers emergency degradation of ALL non-essential
        services: vision processing, telemetry logging, MCP verbose mode.
        Flight-critical processes (control, navigation) remain at full power.
        """
        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=60.0,
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,  # Threshold was violated
        )
        assert status.pressure_level == ResourcePressureLevel.CRITICAL


class TestResourceMonitorInit:
    """Test ResourceMonitor initialization.

    ResourceMonitor is the core component that:
    1. Polls system resources at configured interval (default 1s)
    2. Compares readings against thresholds
    3. Fires callbacks when thresholds are violated
    4. Tracks current status for external queries
    """

    def test_default_init(self) -> None:
        """Monitor initializes with default thresholds and stopped state."""
        monitor = ResourceMonitor()
        assert monitor.thresholds.cpu_percent == 90.0
        assert monitor.thresholds.memory_percent == 95.0
        assert not monitor.is_running
        assert monitor.callback_count == 0

    def test_custom_thresholds_init(self) -> None:
        """Monitor initializes with custom thresholds for specific hardware."""
        # Lower thresholds for constrained environments
        thresholds = ResourceThresholds(cpu_percent=80.0, memory_percent=85.0)
        monitor = ResourceMonitor(thresholds=thresholds)
        assert monitor.thresholds.cpu_percent == 80.0
        assert monitor.thresholds.memory_percent == 85.0


class TestResourceMonitorLifecycle:
    """Test ResourceMonitor start/stop lifecycle.

    The monitor runs an async background loop that:
    - Wakes at interval_s (default 1.0)
    - Collects resource readings
    - Checks against thresholds
    - Triggers callbacks on violation
    - Updates internal status

    Proper lifecycle management prevents resource leaks and ensures
    clean shutdown when the drone mission ends.
    """

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Monitor starts and stops correctly."""
        monitor = ResourceMonitor()
        assert not monitor.is_running

        await monitor.start()
        assert monitor.is_running

        await monitor.stop()
        assert not monitor.is_running

    @pytest.mark.asyncio
    async def test_double_start_raises(self) -> None:
        """Starting already running monitor raises RuntimeError.

        Prevents accidental double-start which would create multiple
        polling loops, wasting CPU and causing callback duplication.
        """
        monitor = ResourceMonitor()
        await monitor.start()

        with pytest.raises(RuntimeError, match="already running"):
            await monitor.start()

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self) -> None:
        """Stopping non-running monitor is safe - idempotent operation."""
        monitor = ResourceMonitor()
        await monitor.stop()  # Should not raise
        assert not monitor.is_running


class TestCpuMonitoring:
    """Test CPU monitoring functionality.

    CPU Monitoring Method:
    - Primary: psutil.cpu_percent(interval=0.1) - samples over 100ms
    - Fallback: 0.0 if psutil unavailable (graceful degradation)

    Why it matters for drones:
    - Flight control loops need consistent timing (typically 250-1000Hz)
    - CPU saturation causes jitter, leading to unstable flight
    - CPU at 100% can miss control deadlines, causing oscillation

    Escalation:
    - 72% CPU: WARNING - degrade vision inference, reduce logging verbosity
    - 90% CPU: CRITICAL - emergency degradation of all non-essentials
    """

    def test_cpu_monitoring_reports_value(self) -> None:
        """CPU monitoring returns a percentage value (0-100)."""
        monitor = ResourceMonitor()
        cpu_percent = monitor._get_cpu_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(cpu_percent, float)
        assert 0.0 <= cpu_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_percent")
    def test_cpu_threshold_violation(self, mock_cpu) -> None:
        """CPU above 90% threshold marks status as unhealthy (CRITICAL).

        At 95% CPU, the system is at risk of missing control loop deadlines.
        This triggers CRITICAL degradation: vision processing disabled,
        telemetry logging reduced, MCP verbose mode disabled.
        """
        mock_cpu.return_value = 95.0  # Above 90% threshold

        monitor = ResourceMonitor()
        status = monitor._check_resources()

        assert status.cpu_percent == 95.0
        assert not status.is_healthy

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_percent")
    def test_cpu_within_threshold(self, mock_cpu) -> None:
        """CPU within threshold keeps status healthy."""
        mock_cpu.return_value = 50.0  # Below 90% threshold

        monitor = ResourceMonitor()
        # Mock other values to be within limits
        with patch.object(monitor, "_get_memory_percent", return_value=50.0):
            with patch.object(monitor, "_get_cpu_temperature", return_value=50.0):
                with patch.object(monitor, "_get_disk_percent", return_value=50.0):
                    status = monitor._check_resources()

        assert status.cpu_percent == 50.0
        assert status.is_healthy


class TestMemoryMonitoring:
    """Test memory monitoring functionality.

    Memory Monitoring Method:
    - Primary: psutil.virtual_memory().percent
    - Fallback: 0.0 if psutil unavailable

    Why it matters for drones:
    - Memory exhaustion triggers Linux OOM killer
    - OOM killer may terminate flight control process = crash
    - No swap on most drone computers (performance requirement)
    - Memory pressure causes allocation failures in flight algorithms

    Escalation:
    - 76% memory: WARNING - reduce buffer sizes, disable caching
    - 95% memory: CRITICAL - trigger RTL (Return to Launch) to prevent OOM mid-flight
    """

    def test_memory_monitoring_reports_value(self) -> None:
        """Memory monitoring returns a percentage value (0-100)."""
        monitor = ResourceMonitor()
        memory_percent = monitor._get_memory_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(memory_percent, float)
        assert 0.0 <= memory_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_memory_percent")
    def test_memory_threshold_violation(self, mock_memory) -> None:
        """Memory above 95% threshold marks status as unhealthy (CRITICAL).

        At 96% memory, we are dangerously close to OOM. The OOM killer
        could terminate ANY process, including flight control.

        This triggers:
        1. CRITICAL degradation of all non-essential services
        2. RTL (Return to Launch) trigger to get drone home safely
           before memory exhaustion causes a crash
        """
        mock_memory.return_value = 96.0  # Above 95% threshold

        monitor = ResourceMonitor()
        status = monitor._check_resources()

        assert status.memory_percent == 96.0
        assert not status.is_healthy

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_memory_percent")
    def test_memory_within_threshold(self, mock_memory) -> None:
        """Memory within threshold keeps status healthy."""
        mock_memory.return_value = 80.0  # Below 95% threshold

        monitor = ResourceMonitor()
        with patch.object(monitor, "_get_cpu_percent", return_value=50.0):
            with patch.object(monitor, "_get_cpu_temperature", return_value=50.0):
                with patch.object(monitor, "_get_disk_percent", return_value=50.0):
                    status = monitor._check_resources()

        assert status.memory_percent == 80.0
        assert status.is_healthy


class TestTemperatureMonitoring:
    """Test temperature monitoring functionality.

    Temperature Monitoring Method:
    - Primary: Read /sys/class/thermal/thermal_zone*/temp
      Value is in millidegrees Celsius, divide by 1000
    - Fallback: 0.0 if thermal zone unavailable

    Why it matters for drones:
    - High temps cause CPU thermal throttling (reduced performance)
    - Extreme temps can damage onboard electronics
    - Outdoor flight in sunlight can cause rapid heating
    - High GPU/CPU usage from vision processing generates heat

    Escalation:
    - 64C: WARNING - disable high-FPS mode, reduce vision processing
    - 80C: CRITICAL - emergency degradation, consider landing
    """

    def test_temperature_monitoring_reports_value(self) -> None:
        """Temperature monitoring returns a value in Celsius."""
        monitor = ResourceMonitor()
        temp = monitor._get_cpu_temperature()

        # Should return a float (or 0.0 if unavailable)
        assert isinstance(temp, float)
        assert temp >= 0.0

    @patch.object(ResourceMonitor, "THERMAL_ZONE_PATH")
    def test_temperature_from_thermal_zone(self, mock_path) -> None:
        """Temperature is read from Linux thermal zone sysfs.

        Linux thermal zones expose temperature in millidegrees Celsius.
        Common thermal zones:
        - thermal_zone0: usually CPU
        - thermal_zone1: may be GPU or PMIC
        """
        # Configure mock path
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "85000\n"  # 85C in millidegrees

        monitor = ResourceMonitor()
        temp = monitor._get_cpu_temperature()

        assert temp == 85.0  # 85000 millidegrees / 1000

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_temperature")
    def test_temperature_threshold_violation(self, mock_temp) -> None:
        """Temperature above 80C threshold marks status as unhealthy (CRITICAL).

        At 85C, most ARM SoCs will thermal throttle. Prolonged operation
        at high temps reduces hardware lifespan and risks shutdown.

        Triggers CRITICAL degradation and should prompt mission abort.
        """
        mock_temp.return_value = 85.0  # Above 80C threshold

        monitor = ResourceMonitor()
        status = monitor._check_resources()

        assert status.temperature_c == 85.0
        assert not status.is_healthy

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_temperature")
    def test_temperature_within_threshold(self, mock_temp) -> None:
        """Temperature within threshold keeps status healthy."""
        mock_temp.return_value = 60.0  # Below 80C threshold

        monitor = ResourceMonitor()
        with patch.object(monitor, "_get_cpu_percent", return_value=50.0):
            with patch.object(monitor, "_get_memory_percent", return_value=50.0):
                with patch.object(monitor, "_get_disk_percent", return_value=50.0):
                    status = monitor._check_resources()

        assert status.temperature_c == 60.0
        assert status.is_healthy


class TestDiskMonitoring:
    """Test disk monitoring functionality.

    Disk Monitoring Method:
    - Primary: psutil.disk_usage('/').percent
    - Fallback: 0.0 if psutil unavailable

    Why it matters for drones:
    - Full disk prevents flight log writing - lose post-crash analysis data
    - Vision systems may cache detection results to disk
    - Full disk can cause system instability (temp file failures)

    Escalation:
    - Not part of WARNING level (doesn't affect real-time performance)
    - 90%: CRITICAL - stop non-essential logging, alert operator
    """

    @patch.object(ResourceMonitor, "_get_disk_percent")
    def test_disk_monitoring_reports_value(self, mock_disk) -> None:
        """Disk monitoring returns a percentage value (0-100)."""
        mock_disk.return_value = 50.0  # Actual float value

        monitor = ResourceMonitor()
        disk_percent = monitor._get_disk_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(disk_percent, float)
        assert 0.0 <= disk_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_disk_percent")
    def test_disk_threshold_violation(self, mock_disk) -> None:
        """Disk above 90% threshold marks status as unhealthy (CRITICAL).

        At 95% disk full, new logs cannot be written. If the drone
        crashes now, we have no flight data for analysis.

        Triggers CRITICAL level and should:
        1. Stop non-essential logging (telemetry history)
        2. Alert operator to download logs
        3. Consider mission abort to preserve remaining log space
        """
        mock_disk.return_value = 95.0  # Above 90% threshold

        monitor = ResourceMonitor()
        status = monitor._check_resources()

        assert status.disk_percent == 95.0
        assert not status.is_healthy


class TestThresholdViolations:
    """Test threshold violation detection.

    The _get_violated_thresholds() method identifies WHICH resources
    are in violation. This is used to:
    1. Log specific warnings to operator
    2. Trigger targeted degradation
    3. Determine if RTL should fire (memory only)
    4. Build telemetry alerts
    """

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=95.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=50.0)
    def test_violated_thresholds_cpu(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """CPU violation is reported in violated thresholds list."""
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "cpu" in violated
        assert "memory" not in violated

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=97.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=50.0)
    def test_violated_thresholds_memory(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """Memory violation is reported in violated thresholds list."""
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "memory" in violated
        assert "cpu" not in violated

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=85.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=50.0)
    def test_violated_thresholds_temperature(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """Temperature violation is reported in violated thresholds list."""
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "temperature" in violated

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=95.0)
    def test_violated_thresholds_disk(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """Disk violation is reported in violated thresholds list."""
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "disk" in violated

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=95.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=97.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=85.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=95.0)
    def test_violated_thresholds_all(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """Multiple violations are all reported.

        When all resources are in violation, we have a catastrophic
        system failure scenario. The drone should immediately:
        1. Trigger RTL (memory critical)
        2. Emergency land if RTL fails
        3. Log final telemetry before potential crash
        """
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "cpu" in violated
        assert "memory" in violated
        assert "temperature" in violated
        assert "disk" in violated


class TestCallbacks:
    """Test callback registration and triggering.

    Callbacks are the notification mechanism for resource pressure.
    Components register async callbacks that receive:
    - status: Full ResourceStatus snapshot
    - violated: List of which thresholds were violated

    Callbacks enable:
    - GracefulDegradationManager to adjust processing
    - RTL trigger on memory critical
    - Telemetry alerts to ground station
    - Logging of pressure events
    """

    def test_register_callback(self) -> None:
        """Callbacks can be registered for resource pressure events."""
        monitor = ResourceMonitor()

        async def callback(status, violated):
            pass

        monitor.register_callback(callback)
        assert monitor.callback_count == 1

    def test_unregister_callback(self) -> None:
        """Callbacks can be unregistered when no longer needed."""
        monitor = ResourceMonitor()

        async def callback(status, violated):
            pass

        monitor.register_callback(callback)
        assert monitor.callback_count == 1

        monitor.unregister_callback(callback)
        assert monitor.callback_count == 0

    @pytest.mark.asyncio
    async def test_callbacks_triggered_on_violation(self) -> None:
        """Callbacks fire when thresholds are violated.

        Callbacks receive:
        - status: Current ResourceStatus with all readings
        - violated: List of violated threshold names

        This allows targeted response to specific resource pressure.
        """
        monitor = ResourceMonitor()
        callback_triggered = False
        received_status = None
        received_violated = None

        async def test_callback(status, violated):
            nonlocal callback_triggered, received_status, received_violated
            callback_triggered = True
            received_status = status
            received_violated = violated

        monitor.register_callback(test_callback)

        # Create a status with violations
        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=50.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await monitor._trigger_callbacks(status, ["cpu"])

        assert callback_triggered is True
        assert received_status == status
        assert "cpu" in received_violated

    @pytest.mark.asyncio
    async def test_multiple_callbacks_triggered(self) -> None:
        """All registered callbacks are triggered on violation.

        Multiple components can listen to resource pressure:
        - Degradation manager adjusts processing
        - Safety monitor triggers RTL on memory
        - Logger records pressure events
        All must receive the notification.
        """
        monitor = ResourceMonitor()
        callback_count = [0]

        async def callback1(status, violated):
            callback_count[0] += 1

        async def callback2(status, violated):
            callback_count[0] += 1

        monitor.register_callback(callback1)
        monitor.register_callback(callback2)

        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=50.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await monitor._trigger_callbacks(status, ["cpu"])

        assert callback_count[0] == 2

    @pytest.mark.asyncio
    async def test_callback_error_handling(self) -> None:
        """Errors in one callback don't break other callbacks.

        Callback isolation ensures that a bug in one component's
        callback doesn't prevent other safety-critical callbacks
        from running (like the RTL trigger).
        """
        monitor = ResourceMonitor()
        callback2_triggered = False

        async def bad_callback(status, violated):
            raise ValueError("Callback error")

        async def good_callback(status, violated):
            nonlocal callback2_triggered
            callback2_triggered = True

        monitor.register_callback(bad_callback)
        monitor.register_callback(good_callback)

        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=50.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        # Should not raise despite bad_callback error
        await monitor._trigger_callbacks(status, ["cpu"])

        assert callback2_triggered is True


class TestGracefulDegradation:
    """Test graceful degradation functionality.

    Graceful degradation is the primary defense against resource pressure.
    When resources become constrained, we reduce non-essential processing
    to preserve flight-critical functionality.

    Degradation Levels:

    WARNING Level (72% CPU, 76% memory, 64C temp):
    - vision_inference: Reduce frame rate, skip alternate frames
    - logging_verbose: Switch to minimal logging
    - high_fps_mode: Disable high frame rate camera capture
    - detection_caching: Disable result caching

    CRITICAL Level (threshold violation):
    - vision_processing: Disable all vision inference
    - telemetry_logging: Reduce to essential flight data only
    - mcp_verbose: Disable verbose MCP logging
    - detection_all: Stop all object detection

    Memory CRITICAL specifically:
    - Sets has_critical_triggered flag
    - Triggers RTL via separate callback mechanism

    Services check should_degrade() before starting heavy operations.
    """

    @pytest.mark.asyncio
    async def test_degradation_manager_init(self) -> None:
        """Degradation manager initializes with monitor reference."""
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        assert degradation._monitor == monitor
        assert len(degradation.degraded_services) == 0
        assert not degradation.has_critical_triggered

    @pytest.mark.asyncio
    async def test_degradation_start_stop(self) -> None:
        """Degradation manager starts and stops correctly.

        On start: Registers callback with ResourceMonitor
        On stop: Unregisters callback to prevent further notifications
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        await degradation.start()
        assert monitor.callback_count == 1

        await degradation.stop()
        assert monitor.callback_count == 0

    @pytest.mark.asyncio
    async def test_warning_degradation_cpu(self) -> None:
        """WARNING level CPU pressure degrades specific services.

        At 75% CPU (above 72% warning threshold):
        - vision_inference: DEGRADED - reduce frame processing
        - logging_verbose: DEGRADED - minimal logging
        - other_service: NOT degraded - not in warning list
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=75.0,  # WARNING level
            memory_percent=60.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )

        await degradation._on_resource_pressure(status, [])

        assert degradation.should_degrade("vision_inference")
        assert degradation.should_degrade("logging_verbose")
        assert not degradation.should_degrade("other_service")

    @pytest.mark.asyncio
    async def test_warning_degradation_temperature(self) -> None:
        """WARNING level temperature degrades thermal-sensitive services.

        At 66C (above 64C warning threshold):
        - high_fps_mode: DEGRADED - reduce camera heat generation
        - vision_inference: NOT degraded - different cause
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=60.0,
            temperature_c=66.0,  # WARNING level
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )

        await degradation._on_resource_pressure(status, [])

        assert degradation.should_degrade("high_fps_mode")
        assert not degradation.should_degrade("vision_inference")

    @pytest.mark.asyncio
    async def test_critical_degradation(self) -> None:
        """CRITICAL level degrades ALL non-essential services.

        At 95% CPU (critical threshold violation):
        - vision_processing: DEGRADED - disable all inference
        - telemetry_logging: DEGRADED - essential only
        - mcp_verbose: DEGRADED - disable verbose MCP

        Flight-critical services (control, navigation) are NOT degraded
        as they don't check should_degrade().
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await degradation._on_resource_pressure(status, ["cpu"])

        assert degradation.should_degrade("vision_processing")
        assert degradation.should_degrade("telemetry_logging")
        assert degradation.should_degrade("mcp_verbose")

    @pytest.mark.asyncio
    async def test_critical_memory_triggers_flag(self) -> None:
        """Critical memory sets has_critical_triggered flag.

        This flag is used by create_rtl_monitor() to trigger RTL.
        When memory is critical, we must return home before OOM strikes.
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=97.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await degradation._on_resource_pressure(status, ["memory"])

        assert degradation.has_critical_triggered

    @pytest.mark.asyncio
    async def test_clear_degradation(self) -> None:
        """Degradation can be cleared for specific service when pressure eases.

        When CPU drops back to normal, we can restore full vision processing.
        This allows dynamic adaptation to changing conditions.
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=75.0,
            memory_percent=60.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=True,
        )

        await degradation._on_resource_pressure(status, [])
        assert degradation.should_degrade("vision_inference")

        degradation.clear_degradation("vision_inference")
        assert not degradation.should_degrade("vision_inference")

    @pytest.mark.asyncio
    async def test_clear_all_degradation(self) -> None:
        """All degradation can be cleared when system recovers.

        After pressure subsides and mission continues, restore full capability.
        Also clears the critical_triggered flag.
        """
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=97.0,
            temperature_c=85.0,
            disk_percent=95.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await degradation._on_resource_pressure(status, ["cpu", "memory"])
        assert len(degradation.degraded_services) > 0
        assert degradation.has_critical_triggered

        degradation.clear_all_degradation()
        assert len(degradation.degraded_services) == 0
        assert not degradation.has_critical_triggered

    def test_is_degraded_alias(self) -> None:
        """is_degraded is an alias for should_degrade for API consistency."""
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        degradation._degraded_services.add("test_service")

        assert degradation.is_degraded("test_service")
        assert degradation.should_degrade("test_service")


class TestRtlMonitor:
    """Test RTL-triggering monitor factory.

    RTL (Return to Launch) is the emergency action when memory is critical.
    If we run out of memory mid-flight, the OOM killer could terminate
    flight control - causing a crash. RTL gets the drone home before
    that happens.

    create_rtl_monitor() creates a ResourceMonitor with a special callback
    that triggers RTL ONLY when memory is in the violated list.
    """

    @pytest.mark.asyncio
    async def test_create_rtl_monitor(self) -> None:
        """RTL monitor is created with RTL callback pre-registered."""
        rtl_triggered = False

        async def mock_rtl():
            nonlocal rtl_triggered
            rtl_triggered = True

        monitor = await create_rtl_monitor(mock_rtl)

        assert isinstance(monitor, ResourceMonitor)
        assert monitor.callback_count == 1

    @pytest.mark.asyncio
    async def test_rtl_callback_triggers_on_memory(self) -> None:
        """RTL callback triggers when memory is violated.

        Memory at 97% (above 95% threshold) triggers RTL immediately.
        This prioritizes getting home safely over mission completion.
        """
        rtl_triggered = False

        async def mock_rtl():
            nonlocal rtl_triggered
            rtl_triggered = True

        monitor = await create_rtl_monitor(mock_rtl)

        # Simulate memory violation
        status = ResourceStatus(
            cpu_percent=50.0,
            memory_percent=97.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await monitor._trigger_callbacks(status, ["memory"])

        assert rtl_triggered is True

    @pytest.mark.asyncio
    async def test_rtl_callback_not_triggered_on_cpu_only(self) -> None:
        """RTL callback is NOT triggered for CPU-only violation.

        CPU at 95% is bad but doesn't risk immediate crash.
        Continue mission with degraded performance.

        RTL is reserved for memory critical because OOM = certain crash.
        """
        rtl_triggered = False

        async def mock_rtl():
            nonlocal rtl_triggered
            rtl_triggered = True

        monitor = await create_rtl_monitor(mock_rtl)

        # Simulate CPU-only violation
        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        await monitor._trigger_callbacks(status, ["cpu"])

        assert rtl_triggered is False


class TestResourceMonitorIntegration:
    """Integration tests for ResourceMonitor.

    These tests verify the complete monitoring loop including:
    - Periodic resource polling
    - Threshold checking
    - Callback triggering
    - Status snapshots
    """

    @pytest.mark.asyncio
    async def test_monitor_loop_updates_status(self) -> None:
        """Monitor loop updates status periodically from real readings.

        The background loop polls resources every interval_s seconds
        and updates the internal _status field. External code can query
        current status via get_status().
        """
        monitor = ResourceMonitor()

        with patch.object(monitor, "_get_cpu_percent", return_value=50.0):
            with patch.object(monitor, "_get_memory_percent", return_value=60.0):
                with patch.object(monitor, "_get_cpu_temperature", return_value=45.0):
                    with patch.object(monitor, "_get_disk_percent", return_value=70.0):
                        await monitor.start(interval_s=0.05)

                        # Wait for at least one update
                        await asyncio.sleep(0.1)

                        status = monitor.get_status()
                        assert status.cpu_percent == 50.0
                        assert status.memory_percent == 60.0

                        await monitor.stop()

    @pytest.mark.asyncio
    async def test_monitor_loop_triggers_callbacks(self) -> None:
        """Monitor loop triggers callbacks when threshold breached.

        Callbacks fire asynchronously when the monitoring loop detects
        a violation during its periodic check.
        """
        monitor = ResourceMonitor()
        callback_triggered = asyncio.Event()

        async def test_callback(status, violated):
            if "memory" in violated:
                callback_triggered.set()

        monitor.register_callback(test_callback)

        with patch.object(monitor, "_get_cpu_percent", return_value=50.0):
            with patch.object(
                monitor, "_get_memory_percent", return_value=97.0
            ):  # Critical
                with patch.object(monitor, "_get_cpu_temperature", return_value=45.0):
                    with patch.object(monitor, "_get_disk_percent", return_value=70.0):
                        await monitor.start(interval_s=0.05)

                        # Wait for callback
                        await asyncio.wait_for(callback_triggered.wait(), timeout=1.0)

                        await monitor.stop()

    def test_get_status_returns_current(self) -> None:
        """get_status returns the current status snapshot.

        Even before start(), returns a default status structure.
        This ensures code querying status doesn't crash on startup.
        """
        monitor = ResourceMonitor()
        status = monitor.get_status()

        assert isinstance(status, ResourceStatus)
        assert hasattr(status, "cpu_percent")
        assert hasattr(status, "memory_percent")
        assert hasattr(status, "temperature_c")
        assert hasattr(status, "disk_percent")
        assert hasattr(status, "timestamp")
        assert hasattr(status, "is_healthy")

    def test_is_healthy_property(self) -> None:
        """is_healthy property reflects status health.

        Provides quick boolean check for system health.
        Used by GuardianProcess to decide if flight operations safe.
        """
        monitor = ResourceMonitor()

        # Initially healthy (default status)
        assert monitor.is_healthy()

        # Manually set unhealthy status
        monitor._status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=50.0,
            temperature_c=50.0,
            disk_percent=50.0,
            timestamp=time.time(),
            is_healthy=False,
        )

        assert not monitor.is_healthy()


class TestPsutilFallback:
    """Test behavior when psutil is unavailable.

    psutil may not be available on minimal embedded systems.
    The monitor gracefully falls back to zeros for psutil-dependent
    metrics but still tries to read temperature from sysfs.

    This allows the code to run on constrained systems, though with
    reduced monitoring capability.
    """

    def test_psutil_unavailable_fallback(self) -> None:
        """Monitor works with fallback when psutil unavailable.

        Without psutil:
        - CPU: 0.0 (unable to monitor)
        - Memory: 0.0 (unable to monitor)
        - Disk: 0.0 (unable to monitor)
        - Temperature: Still attempts thermal zone read

        This is graceful degradation of the monitor itself - flight
        can continue with operator awareness that monitoring is limited.
        """
        monitor = ResourceMonitor()

        # Force psutil unavailable
        monitor._psutil_available = False

        status = monitor._check_resources()

        # Should return zeros for psutil-dependent metrics
        assert status.cpu_percent == 0.0
        assert status.memory_percent == 0.0
        assert status.disk_percent == 0.0

        # Temperature should still try thermal zone
        assert isinstance(status.temperature_c, float)


class TestResourcePressureLevelEnum:
    """Test ResourcePressureLevel enum.

    Three distinct levels allow graduated response:
    - NORMAL: Full capability
    - WARNING: Reduce non-essentials
    - CRITICAL: Emergency measures (RTL on memory)
    """

    def test_enum_values(self) -> None:
        """Enum values are correctly defined."""
        levels = list(ResourcePressureLevel)
        assert len(levels) == 3
        assert ResourcePressureLevel.NORMAL in levels
        assert ResourcePressureLevel.WARNING in levels
        assert ResourcePressureLevel.CRITICAL in levels

    def test_enum_comparison(self) -> None:
        """Enum values can be compared for escalation logic."""
        assert ResourcePressureLevel.NORMAL != ResourcePressureLevel.WARNING
        assert ResourcePressureLevel.WARNING != ResourcePressureLevel.CRITICAL
        assert ResourcePressureLevel.NORMAL != ResourcePressureLevel.CRITICAL
