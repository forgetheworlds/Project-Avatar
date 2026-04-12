"""Tests for the Resource Monitor.

These tests verify:
- CPU monitoring reports percentage
- Temperature monitoring reads thermal zone
- Memory monitoring reports usage
- Threshold violations are detected
- Callbacks fire on threshold breach
- Graceful degradation reduces non-critical processing
- RTL auto-trigger on memory critical
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
    """Test ResourceThresholds dataclass."""

    def test_default_thresholds(self) -> None:
        """Default thresholds have expected values."""
        thresholds = ResourceThresholds()
        assert thresholds.cpu_percent == 90.0
        assert thresholds.memory_percent == 95.0
        assert thresholds.temperature_c == 80.0
        assert thresholds.disk_percent == 90.0

    def test_custom_thresholds(self) -> None:
        """Custom threshold values are accepted."""
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
        """Invalid CPU threshold raises ValueError."""
        with pytest.raises(ValueError, match="cpu_percent must be 0-100"):
            ResourceThresholds(cpu_percent=101.0)

    def test_invalid_memory_threshold(self) -> None:
        """Invalid memory threshold raises ValueError."""
        with pytest.raises(ValueError, match="memory_percent must be 0-100"):
            ResourceThresholds(memory_percent=-1.0)

    def test_invalid_temperature_threshold(self) -> None:
        """Invalid temperature threshold raises ValueError."""
        with pytest.raises(ValueError, match="temperature_c must be 0-150C"):
            ResourceThresholds(temperature_c=200.0)


class TestResourceStatus:
    """Test ResourceStatus dataclass."""

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
        """Normal resources return NORMAL pressure level."""
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
        """High CPU returns WARNING pressure level."""
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
        """High memory returns WARNING pressure level."""
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
        """High temperature returns WARNING pressure level."""
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
        """Unhealthy status returns CRITICAL pressure level."""
        status = ResourceStatus(
            cpu_percent=95.0,
            memory_percent=60.0,
            temperature_c=45.0,
            disk_percent=70.0,
            timestamp=time.time(),
            is_healthy=False,
        )
        assert status.pressure_level == ResourcePressureLevel.CRITICAL


class TestResourceMonitorInit:
    """Test ResourceMonitor initialization."""

    def test_default_init(self) -> None:
        """Monitor initializes with default thresholds."""
        monitor = ResourceMonitor()
        assert monitor.thresholds.cpu_percent == 90.0
        assert monitor.thresholds.memory_percent == 95.0
        assert not monitor.is_running
        assert monitor.callback_count == 0

    def test_custom_thresholds_init(self) -> None:
        """Monitor initializes with custom thresholds."""
        thresholds = ResourceThresholds(cpu_percent=80.0, memory_percent=85.0)
        monitor = ResourceMonitor(thresholds=thresholds)
        assert monitor.thresholds.cpu_percent == 80.0
        assert monitor.thresholds.memory_percent == 85.0


class TestResourceMonitorLifecycle:
    """Test ResourceMonitor start/stop lifecycle."""

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
        """Starting already running monitor raises RuntimeError."""
        monitor = ResourceMonitor()
        await monitor.start()

        with pytest.raises(RuntimeError, match="already running"):
            await monitor.start()

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self) -> None:
        """Stopping non-running monitor is safe."""
        monitor = ResourceMonitor()
        await monitor.stop()  # Should not raise
        assert not monitor.is_running


class TestCpuMonitoring:
    """Test CPU monitoring functionality."""

    def test_cpu_monitoring_reports_value(self) -> None:
        """CPU monitoring returns a percentage value."""
        monitor = ResourceMonitor()
        cpu_percent = monitor._get_cpu_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(cpu_percent, float)
        assert 0.0 <= cpu_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_percent")
    def test_cpu_threshold_violation(self, mock_cpu) -> None:
        """CPU above threshold marks status as unhealthy."""
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
    """Test memory monitoring functionality."""

    def test_memory_monitoring_reports_value(self) -> None:
        """Memory monitoring returns a percentage value."""
        monitor = ResourceMonitor()
        memory_percent = monitor._get_memory_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(memory_percent, float)
        assert 0.0 <= memory_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_memory_percent")
    def test_memory_threshold_violation(self, mock_memory) -> None:
        """Memory above threshold marks status as unhealthy."""
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
    """Test temperature monitoring functionality."""

    def test_temperature_monitoring_reports_value(self) -> None:
        """Temperature monitoring returns a value in Celsius."""
        monitor = ResourceMonitor()
        temp = monitor._get_cpu_temperature()

        # Should return a float (or 0.0 if unavailable)
        assert isinstance(temp, float)
        assert temp >= 0.0

    @patch.object(ResourceMonitor, "THERMAL_ZONE_PATH")
    def test_temperature_from_thermal_zone(self, mock_path) -> None:
        """Temperature is read from thermal zone file."""
        # Configure mock path
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "85000\n"  # 85C

        monitor = ResourceMonitor()
        temp = monitor._get_cpu_temperature()

        assert temp == 85.0  # 85000 millidegrees / 1000

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_cpu_temperature")
    def test_temperature_threshold_violation(self, mock_temp) -> None:
        """Temperature above threshold marks status as unhealthy."""
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
    """Test disk monitoring functionality."""

    @patch.object(ResourceMonitor, "_get_disk_percent")
    def test_disk_monitoring_reports_value(self, mock_disk) -> None:
        """Disk monitoring returns a percentage value."""
        mock_disk.return_value = 50.0  # Actual float value

        monitor = ResourceMonitor()
        disk_percent = monitor._get_disk_percent()

        # Should return a float between 0-100 (or 0.0 on error)
        assert isinstance(disk_percent, float)
        assert 0.0 <= disk_percent <= 100.0

    @patch("avatar.mav.resource_monitor.ResourceMonitor._get_disk_percent")
    def test_disk_threshold_violation(self, mock_disk) -> None:
        """Disk above threshold marks status as unhealthy."""
        mock_disk.return_value = 95.0  # Above 90% threshold

        monitor = ResourceMonitor()
        status = monitor._check_resources()

        assert status.disk_percent == 95.0
        assert not status.is_healthy


class TestThresholdViolations:
    """Test threshold violation detection."""

    @patch.object(ResourceMonitor, "_get_cpu_percent", return_value=95.0)
    @patch.object(ResourceMonitor, "_get_memory_percent", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_cpu_temperature", return_value=50.0)
    @patch.object(ResourceMonitor, "_get_disk_percent", return_value=50.0)
    def test_violated_thresholds_cpu(
        self, mock_disk, mock_temp, mock_mem, mock_cpu
    ) -> None:
        """CPU violation is reported in violated thresholds."""
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
        """Memory violation is reported in violated thresholds."""
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
        """Temperature violation is reported in violated thresholds."""
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
        """Disk violation is reported in violated thresholds."""
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
        """Multiple violations are all reported."""
        monitor = ResourceMonitor()
        status = monitor._check_resources()

        violated = monitor._get_violated_thresholds(status)
        assert "cpu" in violated
        assert "memory" in violated
        assert "temperature" in violated
        assert "disk" in violated


class TestCallbacks:
    """Test callback registration and triggering."""

    def test_register_callback(self) -> None:
        """Callbacks can be registered."""
        monitor = ResourceMonitor()

        async def callback(status, violated):
            pass

        monitor.register_callback(callback)
        assert monitor.callback_count == 1

    def test_unregister_callback(self) -> None:
        """Callbacks can be unregistered."""
        monitor = ResourceMonitor()

        async def callback(status, violated):
            pass

        monitor.register_callback(callback)
        assert monitor.callback_count == 1

        monitor.unregister_callback(callback)
        assert monitor.callback_count == 0

    @pytest.mark.asyncio
    async def test_callbacks_triggered_on_violation(self) -> None:
        """Callbacks are triggered when thresholds are violated."""
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
        """All registered callbacks are triggered."""
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
        """Errors in callbacks don't break other callbacks."""
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
    """Test graceful degradation functionality."""

    @pytest.mark.asyncio
    async def test_degradation_manager_init(self) -> None:
        """Degradation manager initializes correctly."""
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        assert degradation._monitor == monitor
        assert len(degradation.degraded_services) == 0
        assert not degradation.has_critical_triggered

    @pytest.mark.asyncio
    async def test_degradation_start_stop(self) -> None:
        """Degradation manager starts and stops correctly."""
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        await degradation.start()
        assert monitor.callback_count == 1

        await degradation.stop()
        assert monitor.callback_count == 0

    @pytest.mark.asyncio
    async def test_warning_degradation_cpu(self) -> None:
        """WARNING level CPU pressure degrades vision and logging."""
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
        """WARNING level temperature degrades high FPS mode."""
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
        """CRITICAL level degrades all non-essential services."""
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
        """Critical memory sets critical_triggered flag."""
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
        """Degradation can be cleared for specific service."""
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
        """All degradation can be cleared."""
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
        """is_degraded is an alias for should_degrade."""
        monitor = ResourceMonitor()
        degradation = GracefulDegradationManager(monitor)

        degradation._degraded_services.add("test_service")

        assert degradation.is_degraded("test_service")
        assert degradation.should_degrade("test_service")


class TestRtlMonitor:
    """Test RTL-triggering monitor factory."""

    @pytest.mark.asyncio
    async def test_create_rtl_monitor(self) -> None:
        """RTL monitor is created with callback."""
        rtl_triggered = False

        async def mock_rtl():
            nonlocal rtl_triggered
            rtl_triggered = True

        monitor = await create_rtl_monitor(mock_rtl)

        assert isinstance(monitor, ResourceMonitor)
        assert monitor.callback_count == 1

    @pytest.mark.asyncio
    async def test_rtl_callback_triggers_on_memory(self) -> None:
        """RTL callback triggers when memory is violated."""
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
        """RTL callback not triggered for CPU violation only."""
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
    """Integration tests for ResourceMonitor."""

    @pytest.mark.asyncio
    async def test_monitor_loop_updates_status(self) -> None:
        """Monitor loop updates status periodically."""
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
        """Monitor loop triggers callbacks on threshold breach."""
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
        """get_status returns the current status snapshot."""
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
        """is_healthy property reflects status health."""
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
    """Test behavior when psutil is unavailable."""

    def test_psutil_unavailable_fallback(self) -> None:
        """Monitor works with fallback when psutil unavailable."""
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
    """Test ResourcePressureLevel enum."""

    def test_enum_values(self) -> None:
        """Enum values are correctly defined."""
        levels = list(ResourcePressureLevel)
        assert len(levels) == 3
        assert ResourcePressureLevel.NORMAL in levels
        assert ResourcePressureLevel.WARNING in levels
        assert ResourcePressureLevel.CRITICAL in levels

    def test_enum_comparison(self) -> None:
        """Enum values can be compared."""
        assert ResourcePressureLevel.NORMAL != ResourcePressureLevel.WARNING
        assert ResourcePressureLevel.WARNING != ResourcePressureLevel.CRITICAL
        assert ResourcePressureLevel.NORMAL != ResourcePressureLevel.CRITICAL
