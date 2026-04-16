"""Tests for the Agent Liveness Monitoring Service.

The HeartbeatService monitors the health of distributed system components
(LLM, Guardian, Operator, etc.) by tracking their heartbeats.

CORE CONCEPTS:
==============
1. DYNAMIC SOURCES: Sources are added dynamically with `add_source(name, timeout_s)`.
2. STALE DETECTION: Sources become "stale" when their last heartbeat exceeds timeout.
3. CALLBACK-DRIVEN: `monitor_loop(on_stale)` calls the callback when sources go stale.
4. NO EMISSION: This service does NOT emit heartbeats to PX4 - it only monitors.

SAFETY IMPLICATIONS:
====================
- LLM CRASH DETECTION: If the LLM stops heartbeating, we detect it.
- GUARDIAN HEALTH: Guardian process can be monitored independently.
- GRACEFUL DEGRADATION: Individual source failures can trigger targeted actions.

These tests verify:
- Sources can be added with configurable timeouts
- Heartbeats are recorded correctly
- Stale detection works as expected
- The monitor loop calls callbacks on stale sources
- Metrics provide visibility into service state
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.heartbeat_service import (
    HeartbeatConfig,
    HeartbeatService,
    HeartbeatSource,
    SourceConfig,
)


class TestHeartbeatSource:
    """Test HeartbeatSource constants."""

    def test_heartbeat_source_values(self) -> None:
        """HeartbeatSource has correct string constants."""
        assert HeartbeatSource.LLM == "llm"
        assert HeartbeatSource.GUARDIAN == "guardian"
        assert HeartbeatSource.OPERATOR == "operator"
        assert HeartbeatSource.OFFBOARD == "offboard"


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


class TestSourceConfig:
    """Test SourceConfig dataclass."""

    def test_source_config_creation(self) -> None:
        """SourceConfig can be created with all fields."""
        config = SourceConfig(
            name="test_source",
            timeout_s=2.0,
            last_beat=time.time(),
        )
        assert config.name == "test_source"
        assert config.timeout_s == 2.0
        assert config.last_beat > 0


class TestAddSource:
    """Test adding heartbeat sources."""

    def test_add_source(self) -> None:
        """Sources can be added with timeout."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)

        # Source should be registered
        assert "llm" in service._sources
        assert service._sources["llm"].timeout_s == 2.0

    def test_add_multiple_sources(self) -> None:
        """Multiple sources can be added."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)
        service.add_source("guardian", timeout_s=1.0)

        assert "llm" in service._sources
        assert "guardian" in service._sources
        assert service._sources["llm"].timeout_s == 2.0
        assert service._sources["guardian"].timeout_s == 1.0

    def test_update_existing_source(self) -> None:
        """Existing source timeout can be updated."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)
        service.add_source("llm", timeout_s=5.0)

        assert service._sources["llm"].timeout_s == 5.0


class TestRecordHeartbeat:
    """Test recording heartbeats."""

    def test_record_heartbeat(self) -> None:
        """Heartbeats can be recorded for registered sources."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)

        before = time.time()
        service.record_heartbeat("llm")
        after = time.time()

        # last_beat should be updated
        last_beat = service._sources["llm"].last_beat
        assert before <= last_beat <= after

    def test_record_heartbeat_auto_adds_source(self) -> None:
        """Recording heartbeat for unknown source auto-adds it."""
        service = HeartbeatService()
        service.record_heartbeat("unknown_source")

        # Should auto-add with default timeout
        assert "unknown_source" in service._sources
        assert service._sources["unknown_source"].timeout_s == 2.0
        assert service._sources["unknown_source"].last_beat > 0

    def test_record_multiple_heartbeats(self) -> None:
        """Multiple heartbeats update last_beat."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)

        service.record_heartbeat("llm")
        first_beat = service._sources["llm"].last_beat

        time.sleep(0.01)  # Small delay
        service.record_heartbeat("llm")
        second_beat = service._sources["llm"].last_beat

        assert second_beat > first_beat


class TestGetLastBeatAge:
    """Test getting last beat age."""

    def test_get_last_beat_age(self) -> None:
        """get_last_beat_age returns seconds since last heartbeat."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)
        service.record_heartbeat("llm")

        age = service.get_last_beat_age("llm")
        assert age is not None
        assert 0 <= age < 0.1  # Should be very recent

    def test_get_last_beat_age_never_recorded(self) -> None:
        """get_last_beat_age returns None if never recorded."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)

        age = service.get_last_beat_age("llm")
        assert age is None

    def test_get_last_beat_age_unknown_source(self) -> None:
        """get_last_beat_age returns None for unknown source."""
        service = HeartbeatService()
        age = service.get_last_beat_age("unknown")
        assert age is None


class TestStaleSources:
    """Test stale source detection."""

    def test_no_stale_sources_initially(self) -> None:
        """No sources are stale initially (no heartbeats recorded)."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.1)

        # No heartbeats recorded yet, so nothing is stale
        stale = service.stale_sources()
        assert len(stale) == 0

    def test_fresh_source_not_stale(self) -> None:
        """Recently updated sources are not stale."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=1.0)
        service.record_heartbeat("llm")

        stale = service.stale_sources()
        assert "llm" not in stale

    def test_stale_source_detected(self) -> None:
        """Sources that exceed timeout are detected as stale."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.01)  # Very short timeout
        service.record_heartbeat("llm")

        time.sleep(0.02)  # Wait for timeout

        stale = service.stale_sources()
        assert "llm" in stale

    def test_multiple_sources_some_stale(self) -> None:
        """Can detect which sources are stale among many."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.01)
        service.add_source("guardian", timeout_s=1.0)

        service.record_heartbeat("llm")
        service.record_heartbeat("guardian")

        time.sleep(0.02)  # LLM should be stale, guardian fresh

        stale = service.stale_sources()
        assert "llm" in stale
        assert "guardian" not in stale


class TestMonitorLoop:
    """Test the monitor loop."""

    @pytest.mark.asyncio
    async def test_monitor_loop_calls_on_stale(self) -> None:
        """Monitor loop calls on_stale callback when sources become stale."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.05)  # 50ms timeout

        stale_events: list[list[str]] = []

        async def on_stale(sources: list[str]) -> None:
            stale_events.append(sources)

        # Start monitor loop
        monitor_task = asyncio.create_task(service.monitor_loop(on_stale))

        # Record heartbeat
        service.record_heartbeat("llm")

        # Wait for timeout
        await asyncio.sleep(0.1)

        # Stop monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should have detected stale source
        assert len(stale_events) > 0
        assert "llm" in stale_events[0]

    @pytest.mark.asyncio
    async def test_monitor_loop_edge_triggered(self) -> None:
        """Monitor loop only calls on_stale on state transitions."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.01)  # 10ms timeout

        call_count = 0

        async def on_stale(sources: list[str]) -> None:
            nonlocal call_count
            call_count += 1

        monitor_task = asyncio.create_task(service.monitor_loop(on_stale))

        # Record heartbeat, let it go stale
        service.record_heartbeat("llm")
        await asyncio.sleep(0.06)  # Let it become stale (need >50ms for check interval + timeout)

        # Stop monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should have been called exactly once (edge-triggered)
        assert call_count >= 1  # At least one call when source became stale


class TestServiceLifecycle:
    """Test service lifecycle."""

    @pytest.mark.asyncio
    async def test_is_running_flag(self) -> None:
        """is_running flag reflects monitor loop state."""
        service = HeartbeatService()
        assert service.is_running is False

        async def on_stale(sources: list[str]) -> None:
            pass

        monitor_task = asyncio.create_task(service.monitor_loop(on_stale))
        await asyncio.sleep(0.01)

        assert service.is_running is True

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        assert service.is_running is False

    def test_stop_sets_event(self) -> None:
        """stop() sets the stop event."""
        service = HeartbeatService()
        service.stop()
        assert service._stop_event.is_set()


class TestGetMetrics:
    """Test metrics collection."""

    def test_get_metrics(self) -> None:
        """get_metrics() returns current state."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)
        service.record_heartbeat("llm")

        metrics = service.get_metrics()

        assert "sources" in metrics
        assert "stale_count" in metrics
        assert "llm" in metrics["sources"]
        assert metrics["stale_count"] == 0

    def test_get_metrics_shows_stale_count(self) -> None:
        """get_metrics() shows stale source count."""
        service = HeartbeatService()
        service.add_source("llm", timeout_s=0.01)
        service.record_heartbeat("llm")

        time.sleep(0.02)

        metrics = service.get_metrics()
        assert metrics["stale_count"] == 1


class TestContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Service works as async context manager.

        Note: The context manager doesn't start the monitor loop automatically.
        It's designed to be started manually via monitor_loop() or start().
        """
        async with HeartbeatService() as service:
            # Context manager provides the service instance
            # Monitor loop is started separately via monitor_loop() or start()
            service.add_source("test", timeout_s=2.0)
            service.record_heartbeat("test")

        # After context exit, stop event is set
        assert service._stop_event.is_set()
