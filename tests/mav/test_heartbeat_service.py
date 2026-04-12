"""Tests for the 20Hz Heartbeat Service.

These tests verify:
- Heartbeat emitted at exactly 20Hz (50ms intervals)
- Offboard timeout triggers at 500ms (10 missed beats)
- Latency <50ms between scheduled and actual emission
- Automatic failsafe trigger on timeout
- Multiple heartbeat sources tracked separately
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports will fail initially (TDD - tests first)
from avatar.mav.heartbeat_service import (
    HeartbeatConfig,
    HeartbeatService,
    HeartbeatSource,
    HeartbeatState,
    SourceStatus,
)


class TestHeartbeatEnums:
    """Test enum definitions."""

    def test_heartbeat_source_values(self) -> None:
        """HeartbeatSource enum has correct values."""
        assert HeartbeatSource.GUARDIAN.value == "guardian"
        assert HeartbeatSource.LLM.value == "llm"
        assert HeartbeatSource.OPERATOR.value == "operator"
        assert HeartbeatSource.OFFBOARD.value == "offboard"

    def test_heartbeat_state_values(self) -> None:
        """HeartbeatState enum has correct values."""
        # Just verify they exist and are unique
        states = list(HeartbeatState)
        assert len(states) == 4
        assert HeartbeatState.HEALTHY in states
        assert HeartbeatState.WARNING in states
        assert HeartbeatState.TIMEOUT in states
        assert HeartbeatState.STOPPED in states


class TestHeartbeatConfig:
    """Test HeartbeatConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config has correct values."""
        config = HeartbeatConfig()
        assert config.heartbeat_hz == 20.0
        assert config.offboard_timeout_s == 0.5
        assert config.warning_threshold_s == 0.3
        assert config.emit_heartbeat is True

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = HeartbeatConfig(
            heartbeat_hz=10.0,
            offboard_timeout_s=1.0,
            warning_threshold_s=0.5,
            emit_heartbeat=False,
        )
        assert config.heartbeat_hz == 10.0
        assert config.offboard_timeout_s == 1.0
        assert config.warning_threshold_s == 0.5
        assert config.emit_heartbeat is False


class TestSourceStatus:
    """Test SourceStatus dataclass."""

    def test_source_status_creation(self) -> None:
        """SourceStatus can be created with all fields."""
        status = SourceStatus(
            last_beat=time.time(),
            state=HeartbeatState.HEALTHY,
            missed_beats=0,
            total_beats=100,
        )
        assert status.missed_beats == 0
        assert status.total_beats == 100
        assert status.state == HeartbeatState.HEALTHY


class TestHeartbeatFrequency:
    """Test 20Hz heartbeat emission."""

    @pytest.mark.asyncio
    async def test_heartbeat_frequency(self) -> None:
        """10 beats in 500ms, 40-60ms intervals (20Hz)."""
        service = HeartbeatService()
        beat_times = []

        async def on_heartbeat(source, timestamp):
            beat_times.append(timestamp)

        service.on_heartbeat = on_heartbeat
        await service.start()

        # Wait for 10 beats (should take ~500ms at 20Hz)
        await asyncio.sleep(0.55)

        await service.stop()

        # Should have at least 10 beats
        assert len(beat_times) >= 10, f"Only got {len(beat_times)} beats, expected >= 10"

        # Check intervals between consecutive beats
        intervals = [beat_times[i] - beat_times[i-1] for i in range(1, len(beat_times))]
        for interval in intervals:
            assert 0.04 <= interval <= 0.06, f"Interval {interval}s out of range (expected 40-60ms)"

    @pytest.mark.asyncio
    async def test_heartbeat_latency(self) -> None:
        """Latency <50ms between scheduled and actual emission."""
        service = HeartbeatService()
        latencies = []

        async def on_heartbeat(source, timestamp):
            # Calculate latency from expected 50ms interval
            expected_time = service._start_time + (len(latencies) * 0.05)
            latency = abs(timestamp - expected_time)
            latencies.append(latency)

        service.on_heartbeat = on_heartbeat
        await service.start()

        # Collect several beats
        await asyncio.sleep(0.3)

        await service.stop()

        # Skip first beat (startup variance), check rest
        if len(latencies) > 1:
            max_latency = max(latencies[1:])
            assert max_latency < 0.05, f"Max latency {max_latency}s exceeds 50ms"


class TestOffboardTimeout:
    """Test 500ms offboard timeout."""

    @pytest.mark.asyncio
    async def test_offboard_timeout_triggers_failsafe(self) -> None:
        """500ms timeout triggers failsafe callback."""
        service = HeartbeatService()
        failsafe_triggered = []

        async def on_failsafe(source):
            failsafe_triggered.append(source)

        service.on_failsafe = on_failsafe
        await service.start()

        # Record one heartbeat from LLM source
        service.record_heartbeat(HeartbeatSource.LLM, time.time())

        # Wait for timeout (500ms + small buffer)
        await asyncio.sleep(0.6)

        await service.stop()

        # Failsafe should have been triggered
        assert len(failsafe_triggered) > 0, "Failsafe was not triggered after timeout"
        assert HeartbeatSource.LLM in failsafe_triggered

    @pytest.mark.asyncio
    async def test_no_failsafe_when_heartbeats_continue(self) -> None:
        """No failsafe when heartbeats continue within timeout."""
        service = HeartbeatService()
        failsafe_triggered = []

        async def on_failsafe(source):
            failsafe_triggered.append(source)

        service.on_failsafe = on_failsafe
        await service.start()

        # Record heartbeats every 100ms (well within 500ms timeout)
        for _ in range(8):
            service.record_heartbeat(HeartbeatSource.LLM, time.time())
            await asyncio.sleep(0.1)

        await service.stop()

        # Failsafe should NOT have been triggered
        assert len(failsafe_triggered) == 0, "Failsafe triggered despite regular heartbeats"


class TestMultipleSources:
    """Test multiple heartbeat sources tracked separately."""

    @pytest.mark.asyncio
    async def test_multiple_sources_tracked(self) -> None:
        """LLM and Guardian tracked separately."""
        service = HeartbeatService()

        await service.start()

        # Record from LLM
        llm_time = time.time()
        service.record_heartbeat(HeartbeatSource.LLM, llm_time)

        # Record from Guardian
        guardian_time = time.time()
        service.record_heartbeat(HeartbeatSource.GUARDIAN, guardian_time)

        # Check both are tracked
        assert service.get_last_heartbeat(HeartbeatSource.LLM) == llm_time
        assert service.get_last_heartbeat(HeartbeatSource.GUARDIAN) == guardian_time

        await service.stop()

    @pytest.mark.asyncio
    async def test_source_health_check(self) -> None:
        """is_source_healthy() works for each source."""
        service = HeartbeatService()

        await service.start()

        # Initially not healthy (no heartbeats)
        assert service.is_source_healthy(HeartbeatSource.LLM) is False

        # Record heartbeat
        service.record_heartbeat(HeartbeatSource.LLM, time.time())

        # Now healthy
        assert service.is_source_healthy(HeartbeatSource.LLM) is True

        # Wait for timeout
        await asyncio.sleep(0.6)

        # Should no longer be healthy
        assert service.is_source_healthy(HeartbeatSource.LLM) is False

        await service.stop()

    @pytest.mark.asyncio
    async def test_independent_source_timeouts(self) -> None:
        """Each source times out independently."""
        service = HeartbeatService()
        failsafe_sources = []

        async def on_failsafe(source):
            failsafe_sources.append(source)

        service.on_failsafe = on_failsafe
        await service.start()

        # Record from LLM only
        service.record_heartbeat(HeartbeatSource.LLM, time.time())

        # Wait for timeout
        await asyncio.sleep(0.6)

        await service.stop()

        # Only LLM should have triggered failsafe
        assert HeartbeatSource.LLM in failsafe_sources
        assert HeartbeatSource.GUARDIAN not in failsafe_sources


class TestWarningCallback:
    """Test warning callback for approaching timeout."""

    @pytest.mark.asyncio
    async def test_warning_callback(self) -> None:
        """Warning callback triggered at warning threshold."""
        service = HeartbeatService(
            config=HeartbeatConfig(
                warning_threshold_s=0.1,  # 100ms for fast testing
                offboard_timeout_s=0.5,
            )
        )
        warnings = []

        async def on_warning(source, age):
            warnings.append((source, age))

        service.on_warning = on_warning
        await service.start()

        # Record heartbeat
        service.record_heartbeat(HeartbeatSource.LLM, time.time())

        # Wait for warning to trigger (warning fires every 0.5s when past threshold)
        await asyncio.sleep(0.6)

        await service.stop()

        # Warning should have been triggered
        assert len(warnings) > 0, "Warning callback not triggered"


class TestServiceLifecycle:
    """Test service start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Service starts and stops cleanly."""
        service = HeartbeatService()

        assert service.is_running is False

        await service.start()
        assert service.is_running is True

        await service.stop()
        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_idempotent_start(self) -> None:
        """Multiple starts are handled gracefully."""
        service = HeartbeatService()

        await service.start()
        await service.start()  # Second start should be idempotent

        assert service.is_running is True

        await service.stop()

    @pytest.mark.asyncio
    async def test_idempotent_stop(self) -> None:
        """Multiple stops are handled gracefully."""
        service = HeartbeatService()

        await service.start()
        await service.stop()
        await service.stop()  # Second stop should be idempotent

        assert service.is_running is False


class TestGetMetrics:
    """Test metrics collection."""

    @pytest.mark.asyncio
    async def test_get_metrics(self) -> None:
        """get_metrics() returns performance stats."""
        service = HeartbeatService()

        await service.start()

        # Record some heartbeats
        for _ in range(5):
            service.record_heartbeat(HeartbeatSource.LLM, time.time())
            await asyncio.sleep(0.01)

        metrics = service.get_metrics()

        await service.stop()

        assert "emit_count" in metrics
        assert "sources" in metrics
        assert "uptime_s" in metrics


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_record_heartbeat_while_stopped(self) -> None:
        """Recording heartbeat when stopped doesn't crash."""
        service = HeartbeatService()

        # Don't start, just record
        service.record_heartbeat(HeartbeatSource.LLM, time.time())

        # Should be tracked even when stopped
        assert service.get_last_heartbeat(HeartbeatSource.LLM) is not None

    @pytest.mark.asyncio
    async def test_get_last_heartbeat_unknown_source(self) -> None:
        """Getting heartbeat for unknown source returns None."""
        service = HeartbeatService()

        result = service.get_last_heartbeat(HeartbeatSource.LLM)
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_exceptions_handled(self) -> None:
        """Exceptions in callbacks are handled gracefully."""
        service = HeartbeatService()

        async def failing_callback(source, timestamp):
            raise Exception("Callback error")

        service.on_heartbeat = failing_callback
        await service.start()

        # Should not crash despite callback failure
        await asyncio.sleep(0.1)

        await service.stop()

    @pytest.mark.asyncio
    async def test_rapid_start_stop(self) -> None:
        """Rapid start/stop cycles are handled."""
        service = HeartbeatService()

        for _ in range(5):
            await service.start()
            await asyncio.sleep(0.01)
            await service.stop()

        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_high_frequency_heartbeats(self) -> None:
        """Service handles heartbeats at higher than 20Hz."""
        service = HeartbeatService()

        await service.start()

        # Record heartbeats at 100Hz
        for i in range(100):
            service.record_heartbeat(HeartbeatSource.LLM, time.time())
            await asyncio.sleep(0.01)

        metrics = service.get_metrics()
        await service.stop()

        # Should have tracked all heartbeats
        assert metrics["sources"][HeartbeatSource.LLM.value]["total_beats"] == 100


class TestContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Service works as async context manager."""
        async with HeartbeatService() as service:
            assert service.is_running is True
            service.record_heartbeat(HeartbeatSource.LLM, time.time())

        assert service.is_running is False
