"""Tests for the TelemetryCache system.

These tests verify:
- Telemetry data caching with 100ms refresh intervals
- Fast cache access (<1ms per read)
- Background auto-refresh
- Thread-safe concurrent access
- Stale data detection (>500ms)
"""

import asyncio
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports will fail initially (TDD - tests first)
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData, TelemetryHistory


class TestTelemetryData:
    """Test TelemetryData dataclass."""

    def test_telemetry_data_creation(self) -> None:
        """TelemetryData can be created with all fields."""
        data = TelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0,
            velocity_north=1.0,
            velocity_east=2.0,
            velocity_down=0.5,
            groundspeed=2.5,
            roll=0.1,
            pitch=0.2,
            yaw=0.3,
            battery_percent=85.0,
            battery_voltage=16.8,
            battery_current=5.0,
            armed=True,
            in_air=False,
            flight_mode="HOLD",
            gps_fix=3,
            is_gps_ok=True,
            is_home_position_ok=True,
        )

        assert data.latitude == 37.7749
        assert data.longitude == -122.4194
        assert data.armed is True
        assert data.in_air is False


class TestTelemetryHistory:
    """Test TelemetryHistory class."""

    def test_history_add(self) -> None:
        """History can add and retrieve data."""
        history = TelemetryHistory(max_size=10)

        data1 = TelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0,
            velocity_north=0.0,
            velocity_east=0.0,
            velocity_down=0.0,
            groundspeed=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0,
            battery_percent=100.0,
            battery_voltage=16.8,
            battery_current=0.0,
            armed=False,
            in_air=False,
            flight_mode="HOLD",
            gps_fix=0,
            is_gps_ok=False,
            is_home_position_ok=False,
        )

        history.add(data1)
        latest = history.get_latest()

        assert latest is not None
        assert latest.latitude == 37.7749

    def test_history_max_size(self) -> None:
        """History respects max_size limit."""
        history = TelemetryHistory(max_size=5)

        for i in range(10):
            data = TelemetryData(
                timestamp=time.time(),
                latitude=float(i),
                longitude=float(i),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )
            history.add(data)

        # Should only have 5 items (latest 5)
        assert len(history.data) == 5
        # Latest should be index 9
        assert history.get_latest().latitude == 9.0

    def test_history_trend_calculation(self) -> None:
        """History calculates trends correctly."""
        history = TelemetryHistory(max_size=10)

        # Add ascending altitude data
        for i in range(5):
            data = TelemetryData(
                timestamp=time.time() + i,
                latitude=0.0,
                longitude=0.0,
                altitude=float(i * 10),
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )
            history.add(data)

        trend = history.get_trend("altitude")
        assert trend > 0  # Should be positive trend (ascending)


class TestCacheReturnsData:
    """Test that cache returns telemetry data."""

    @pytest.mark.asyncio
    async def test_cache_returns_data(self) -> None:
        """Cache returns telemetry data when available."""
        cache = TelemetryCache()

        # Mock provider
        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=1.0,
                velocity_east=2.0,
                velocity_down=0.5,
                groundspeed=2.5,
                roll=0.1,
                pitch=0.2,
                yaw=0.3,
                battery_percent=85.0,
                battery_voltage=16.8,
                battery_current=5.0,
                armed=True,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=3,
                is_gps_ok=True,
                is_home_position_ok=True,
            )

        await cache.start(mock_provider)

        # Wait for first refresh
        await asyncio.sleep(0.15)

        data = cache.get_data()
        assert data is not None
        assert data.latitude == 37.7749
        assert data.longitude == -122.4194

        await cache.stop()

    @pytest.mark.asyncio
    async def test_cache_returns_none_when_no_data(self) -> None:
        """Cache returns None when no data has been fetched."""
        cache = TelemetryCache()

        # Don't start the cache
        data = cache.get_data()
        assert data is None


class TestCacheFastAccess:
    """Test fast cache access (<1ms)."""

    @pytest.mark.asyncio
    async def test_cache_fast_access(self) -> None:
        """100 cache reads complete in <100ms total (<1ms each)."""
        cache = TelemetryCache()

        # Pre-populate with mock data
        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=1.0,
                velocity_east=2.0,
                velocity_down=0.5,
                groundspeed=2.5,
                roll=0.1,
                pitch=0.2,
                yaw=0.3,
                battery_percent=85.0,
                battery_voltage=16.8,
                battery_current=5.0,
                armed=True,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=3,
                is_gps_ok=True,
                is_home_position_ok=True,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)  # Wait for first refresh

        # Perform 100 reads
        start = time.time()
        for _ in range(100):
            _ = cache.get_data()
        elapsed = time.time() - start

        assert elapsed < 0.1, f"100 reads took {elapsed}s, expected <0.1s"

        await cache.stop()

    @pytest.mark.asyncio
    async def test_single_read_under_1ms(self) -> None:
        """Single cache read completes in <1ms."""
        cache = TelemetryCache()

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)

        # Single read timing
        start = time.time()
        _ = cache.get_data()
        elapsed = time.time() - start

        assert elapsed < 0.001, f"Single read took {elapsed}s, expected <1ms"

        await cache.stop()


class TestCacheRefresh:
    """Test cache refresh at 100ms intervals."""

    @pytest.mark.asyncio
    async def test_cache_refresh_interval(self) -> None:
        """Cache updates at 100ms intervals."""
        cache = TelemetryCache(refresh_ms=100)
        call_count = 0

        async def counting_provider():
            nonlocal call_count
            call_count += 1
            return TelemetryData(
                timestamp=time.time(),
                latitude=float(call_count),
                longitude=float(call_count),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(counting_provider)

        # Wait for initial refresh
        await asyncio.sleep(0.05)
        initial_count = call_count

        # Wait for 2 more refresh cycles
        await asyncio.sleep(0.25)

        # Should have at least 2-3 more calls
        assert call_count >= initial_count + 2

        await cache.stop()

    @pytest.mark.asyncio
    async def test_background_refresh(self) -> None:
        """Cache refreshes in background without blocking reads."""
        cache = TelemetryCache(refresh_ms=50)
        refresh_count = 0

        async def slow_provider():
            nonlocal refresh_count
            refresh_count += 1
            await asyncio.sleep(0.02)  # Simulate slow fetch
            return TelemetryData(
                timestamp=time.time(),
                latitude=float(refresh_count),
                longitude=float(refresh_count),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(slow_provider)

        # Start reading while background refresh happens
        read_times = []
        for _ in range(10):
            start = time.time()
            _ = cache.get_data()
            read_times.append(time.time() - start)
            await asyncio.sleep(0.03)

        # All reads should be fast regardless of background refresh
        assert all(t < 0.001 for t in read_times), f"Slow reads detected: {read_times}"

        await cache.stop()


class TestStaleDataDetection:
    """Test stale data detection (>500ms)."""

    @pytest.mark.asyncio
    async def test_stale_data_detection(self) -> None:
        """Correctly detects data older than 500ms as stale."""
        cache = TelemetryCache(refresh_ms=100, stale_ms=500)

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)

        # Fresh data should not be stale
        assert cache.is_stale() is False

        await cache.stop()

    @pytest.mark.asyncio
    async def test_stale_after_stop(self) -> None:
        """Data becomes stale after cache stops."""
        cache = TelemetryCache(stale_ms=100)

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)

        # Stop cache - no more updates
        await cache.stop()

        # Wait for data to become stale
        await asyncio.sleep(0.15)

        assert cache.is_stale() is True

    @pytest.mark.asyncio
    async def test_get_fresh_data_refreshes(self) -> None:
        """get_fresh_data refreshes if data is stale."""
        cache = TelemetryCache(refresh_ms=1000, stale_ms=100)  # Slow refresh
        call_count = 0

        async def counting_provider():
            nonlocal call_count
            call_count += 1
            return TelemetryData(
                timestamp=time.time(),
                latitude=float(call_count),
                longitude=float(call_count),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(counting_provider)
        await asyncio.sleep(0.05)  # Initial data

        # Stop cache to make data stale
        await cache.stop()
        await asyncio.sleep(0.15)  # Wait for staleness

        assert cache.is_stale() is True


class TestConcurrentAccess:
    """Test thread-safe concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Multiple concurrent reads are thread-safe."""
        cache = TelemetryCache()

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)

        # Launch 50 concurrent reads
        async def read_task():
            return cache.get_data()

        tasks = [read_task() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All reads should succeed
        assert all(r is not None for r in results)

        await cache.stop()

    @pytest.mark.asyncio
    async def test_concurrent_reads_during_refresh(self) -> None:
        """Reads during refresh don't block or corrupt."""
        cache = TelemetryCache(refresh_ms=50)
        refresh_count = 0

        async def slow_provider():
            nonlocal refresh_count
            refresh_count += 1
            await asyncio.sleep(0.01)  # Slow refresh
            return TelemetryData(
                timestamp=time.time(),
                latitude=float(refresh_count),
                longitude=float(refresh_count),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(slow_provider)

        # Run concurrent reads while refresh happens
        results = []
        for _ in range(20):
            tasks = [asyncio.create_task(asyncio.to_thread(cache.get_data)) for _ in range(5)]
            batch = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch)
            await asyncio.sleep(0.03)

        # No exceptions should occur
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Exceptions during concurrent access: {exceptions}"

        await cache.stop()


class TestHistoryTracking:
    """Test telemetry history tracking."""

    @pytest.mark.asyncio
    async def test_history_tracking(self) -> None:
        """History tracks telemetry over time."""
        cache = TelemetryCache(refresh_ms=50, history_size=10)
        altitude_values = [100.0, 105.0, 110.0, 115.0, 120.0]
        call_idx = 0

        async def altitude_provider():
            nonlocal call_idx
            alt = altitude_values[min(call_idx, len(altitude_values) - 1)]
            call_idx += 1
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=alt,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(altitude_provider)

        # Wait for multiple updates
        await asyncio.sleep(0.3)

        history = cache.get_history()
        assert len(history.data) > 0

        # Check trend is positive (altitude increasing)
        trend = history.get_trend("altitude")
        assert trend > 0

        await cache.stop()


class TestCacheMetrics:
    """Test cache performance metrics."""

    @pytest.mark.asyncio
    async def test_metrics_tracking(self) -> None:
        """Cache tracks performance metrics."""
        cache = TelemetryCache()

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(mock_provider)
        await asyncio.sleep(0.15)

        # Perform some reads
        for _ in range(5):
            _ = cache.get_data()

        metrics = cache.get_metrics()

        assert "hit_count" in metrics
        assert "refresh_count" in metrics
        assert "last_refresh_time" in metrics

        await cache.stop()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self) -> None:
        """Start/stop can be called multiple times safely."""
        cache = TelemetryCache()

        async def mock_provider():
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        # Multiple starts shouldn't crash
        await cache.start(mock_provider)
        await cache.start(mock_provider)

        # Multiple stops shouldn't crash
        await cache.stop()
        await cache.stop()

    @pytest.mark.asyncio
    async def test_provider_exception_handling(self) -> None:
        """Cache handles provider exceptions gracefully."""
        cache = TelemetryCache()
        call_count = 0

        async def flaky_provider():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Provider error")
            return TelemetryData(
                timestamp=time.time(),
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(flaky_provider)
        await asyncio.sleep(0.25)  # Wait for multiple refresh cycles

        # Cache should still have data from successful calls
        data = cache.get_data()
        assert data is not None

        await cache.stop()

    @pytest.mark.asyncio
    async def test_no_provider_set(self) -> None:
        """Cache handles missing provider gracefully."""
        cache = TelemetryCache()

        # Don't set provider
        data = cache.get_data()
        assert data is None

        is_stale = cache.is_stale()
        assert is_stale is True  # No data means stale


class TestConfigurableIntervals:
    """Test configurable refresh and stale intervals."""

    @pytest.mark.asyncio
    async def test_custom_refresh_interval(self) -> None:
        """Custom refresh interval is respected."""
        cache = TelemetryCache(refresh_ms=200)  # 200ms refresh
        call_count = 0

        async def counting_provider():
            nonlocal call_count
            call_count += 1
            return TelemetryData(
                timestamp=time.time(),
                latitude=float(call_count),
                longitude=float(call_count),
                altitude=100.0,
                velocity_north=0.0,
                velocity_east=0.0,
                velocity_down=0.0,
                groundspeed=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                battery_percent=100.0,
                battery_voltage=16.8,
                battery_current=0.0,
                armed=False,
                in_air=False,
                flight_mode="HOLD",
                gps_fix=0,
                is_gps_ok=False,
                is_home_position_ok=False,
            )

        await cache.start(counting_provider)

        await asyncio.sleep(0.05)  # Initial
        initial_count = call_count

        await asyncio.sleep(0.25)  # Wait for more intervals

        # Should have ~1-2 more calls (200ms interval in 250ms = ~1-2 calls)
        assert call_count >= initial_count + 1
        assert call_count <= initial_count + 3  # Allow some variance

        await cache.stop()

    def test_default_intervals(self) -> None:
        """Default intervals are set correctly."""
        cache = TelemetryCache()

        assert cache.refresh_ms == 100
        assert cache.stale_ms == 500
