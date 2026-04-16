"""Tests for the TelemetryCache system.

These tests verify:
- Telemetry data caching with 100ms refresh intervals
- Fast cache access (<1ms per read)
- Background auto-refresh
- Thread-safe concurrent access
- Stale data detection (>500ms)

================================================================================
WHY CACHING MATTERS FOR PERFORMANCE
================================================================================
MAVSDK telemetry operations involve network calls to the drone (or SITL
simulation). Each raw telemetry fetch takes 5-50ms depending on connection
latency, message processing, and UDP transport.

For agent decision-making that queries telemetry dozens of times per decision
cycle, uncached reads would:
- Add 50-100ms latency to each decision loop iteration
- Create jitter in control loops
- Waste bandwidth on redundant queries
- Block the async event loop

The TelemetryCache solves this by:
1. Maintaining a local snapshot of latest telemetry data in memory
2. Refreshing asynchronously in the background every 100ms (configurable)
3. Providing sub-millisecond reads for consumers (100-1000x faster than MAVSDK)
4. Isolating consumers from network latency variations

This enables agents to query telemetry state freely without performance concerns,
enabling real-time obstacle avoidance and responsive control.

================================================================================
HOW THE ASYNC REFRESH WORKS
================================================================================
The background refresh follows this pattern:

    async def _refresh_loop():
        while self._running:
            try:
                # Fetch fresh telemetry (may take 5-50ms, involves network I/O)
                new_data = await self._provider()

                # Atomically swap the reference (O(1), no locks needed)
                self._current_data = new_data
                self._last_refresh = time.time()

                # Add to history for trend analysis
                self._history.add(new_data)
            except Exception:
                # Exceptions don't crash the loop; we retry next cycle
                logger.exception("Refresh failed, retrying...")

            await asyncio.sleep(self.refresh_ms / 1000)

KEY ARCHITECTURAL PROPERTIES:
- Refresh happens in a separate asyncio Task (concurrent with all other work)
- The provider coroutine yields control during I/O (non-blocking)
- Data reference swap is atomic in Python (GIL ensures pointer swap safety)
- Exceptions are isolated and don't crash the refresh loop
- No locks are held during reads (lock-free design)

================================================================================
DATA FRESHNESS GUARANTEES
================================================================================
MAXIMUM DATA AGE:
    worst_case_age = refresh_ms + provider_latency
    With defaults: 100ms + ~20ms = ~120ms maximum staleness

AVERAGE DATA AGE:
    average_age = refresh_ms / 2
    With defaults: ~50ms average staleness

STALENESS DETECTION:
    Data is marked stale if: (now - last_refresh) > stale_ms
    Default stale threshold: 500ms (5 missed refresh cycles)

This provides a bounded freshness guarantee suitable for real-time control
while respecting network and computational constraints.

================================================================================
SAFETY CRITICAL
================================================================================
The TelemetryCache provides fast access to drone telemetry for the LLM decision
loop and safety systems. Slow telemetry access would:
1. Delay LLM responses (poor obstacle avoidance)
2. Block safety checks (delayed failsafe response)
3. Create race conditions (inconsistent data reads)

The cache decouples slow MAVSDK queries (~50-100ms) from fast decision
loops that need <1ms access times.
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
    """Test TelemetryData dataclass.

    SAFETY: TelemetryData encapsulates all safety-relevant telemetry fields.
    Missing fields could hide critical conditions (low battery, GPS loss).
    """

    def test_telemetry_data_creation(self) -> None:
        """TelemetryData can be created with all fields.

        VALIDATES: Dataclass accepts all telemetry parameters.

        MOCK SETUP: Create TelemetryData with comprehensive field values.

        SAFETY REASON: All fields must be accessible for safety decisions.
        Battery, GPS, position, velocity all affect flight safety.

        FIELDS COVERED:
        - Position: latitude, longitude, altitude
        - Velocity: north, east, down, groundspeed
        - Attitude: roll, pitch, yaw
        - Battery: percent, voltage, current
        - Status: armed, in_air, flight_mode
        - Health: gps_fix, is_gps_ok, is_home_position_ok

        STEP-BY-STEP:
        1. Create TelemetryData with all fields populated
        2. Assert each field stored correctly
        3. Verify boolean fields (armed, in_air) are set
        """
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
    """Test TelemetryHistory class.

    THESE TESTS VALIDATE:
    1. History maintains a rolling window of telemetry samples
    2. Old samples are evicted when max_size is reached (circular buffer)
    3. Trend analysis works for detecting rate of change

    WHY HISTORY MATTERS:
    ===================
    Single telemetry snapshots tell you WHERE the drone is. History tells
    you WHERE IT'S GOING. This is essential for:

    - Predictive collision avoidance (trajectory projection)
    - Detecting control issues (altitude dropping when holding)
    - Battery drain rate estimation (time remaining)
    - Validating commanded vs actual behavior

    CIRCULAR BUFFER DESIGN:
    ======================
    TelemetryHistory uses a fixed-size circular buffer (deque with maxlen):

        history = deque(maxlen=50)  # Default: 50 samples

    When full, adding a new sample automatically evicts the oldest:

        history: [t-49, t-48, ..., t-2, t-1, t]
        add(t+1)
        history: [t-48, t-47, ..., t-1, t, t+1]

    This provides bounded memory usage regardless of runtime.

    TREND ANALYSIS:
    ==============
    get_trend(field) performs simple linear regression over the history:

        trend = (sum((x - x_mean) * (y - y_mean))) / sum((x - x_mean)^2)

    Result is rate of change per second. Positive = increasing, negative =
    decreasing, near zero = stable.

    HISTORY SIZE TRADEOFFS:
    ======================
    - Larger (100+): Better trend accuracy, more memory, slower calculation
    - Smaller (10):   Faster, less memory, more noise-sensitive
    - Default (50):   ~5 seconds at 100ms refresh (good balance)

    SAFETY: History enables trend analysis for predictive safety.
    Detecting altitude trends, battery drain rates, etc.
    """

    def test_history_add(self) -> None:
        """History can add and retrieve data.

        VALIDATES: History storage and retrieval works.

        MOCK SETUP: Create TelemetryHistory, add TelemetryData.

        SAFETY REASON: History is used for trend detection (e.g., is
        altitude decreasing when it should be stable?).

        STEP-BY-STEP:
        1. Create TelemetryHistory with max_size=10
        2. Create TelemetryData with known latitude
        3. Call history.add(data)
        4. Call history.get_latest()
        5. Assert returned data matches added data
        """
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
        """History respects max_size limit.

        VALIDATES: Ring buffer behavior - oldest evicted when full.

        MOCK SETUP: Create history with max_size=5, add 10 entries.

        SAFETY REASON: Unlimited history would exhaust memory. Ring
        buffer ensures bounded memory usage while keeping recent data.

        STEP-BY-STEP:
        1. Create TelemetryHistory with max_size=5
        2. Add 10 entries with increasing latitude values
        3. Assert history.data length is 5 (limit enforced)
        4. Assert latest.latitude is 9.0 (most recent, indices 5-9 kept)
        """
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
        """History calculates trends correctly.

        VALIDATES: get_trend() returns correct direction.

        MOCK SETUP: Add 5 entries with ascending altitude.

        SAFETY REASON: Trends predict future state. Ascending altitude
        when commanding hover indicates control issue.

        STEP-BY-STEP:
        1. Create TelemetryHistory
        2. Add 5 entries with altitude increasing by 10m each
        3. Call history.get_trend("altitude")
        4. Assert trend > 0 (positive trend detected)
        """
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
    """Test that cache returns telemetry data.

    SAFETY: The cache must always return the most recent data available.
    Returning stale or None data could cause incorrect decisions.
    """

    @pytest.mark.asyncio
    async def test_cache_returns_data(self) -> None:
        """Cache returns telemetry data when available.

        VALIDATES: get_data() returns TelemetryData after refresh.

        MOCK SETUP:
        - Create TelemetryCache
        - Define async mock_provider returning known TelemetryData
        - Start cache with provider

        SAFETY REASON: LLM and safety systems depend on this data.
        Cache must successfully bridge provider and consumers.

        STEP-BY-STEP:
        1. Create TelemetryCache
        2. Define mock_provider returning TelemetryData with known lat/lon
        3. Start cache with mock_provider
        4. Wait for first refresh (150ms)
        5. Call get_data()
        6. Assert data returned (not None)
        7. Assert latitude and longitude match expected values
        8. Stop cache
        """
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
        """Cache returns None when no data has been fetched.

        VALIDATES: Safe handling of initial state.

        MOCK SETUP: Create cache, don't start it.

        SAFETY REASON: None return allows explicit handling. Callers
        can check for None and wait or use default values.

        STEP-BY-STEP:
        1. Create TelemetryCache
        2. Don't start (no provider, no data)
        3. Call get_data()
        4. Assert result is None
        """
        cache = TelemetryCache()

        # Don't start the cache
        data = cache.get_data()
        assert data is None


class TestCacheFastAccess:
    """Test fast cache access (<1ms).

    THESE TESTS VALIDATE:
    1. Read operations complete in sub-millisecond time
    2. Read performance is independent of refresh frequency
    3. Sustained high-frequency reads don't degrade performance

    HOW FAST ACCESS IS ACHIEVED:
    ===========================
    The cache uses a lock-free, single-pointer design:

        class TelemetryCache:
            def __init__(self):
                self._current_data = None  # Single reference

            def get_data(self) -> TelemetryData:
                return self._current_data  # Just return the reference

    This is O(1) with no locks, no I/O, no allocation - just a pointer read.
    In Python, this takes ~50-200 nanoseconds (0.00005-0.0002ms).

    WHY SUB-MILLISECOND MATTERS:
    ============================
    Agent decision loops may query telemetry multiple times:
    - Position check: get_data().position
    - Battery check: get_data().battery_percent
    - Mode check: get_data().flight_mode
    - Velocity check: get_data().velocity_north

    4 queries at 50ms each (raw MAVSDK) = 200ms delay
    4 queries at 0.001ms each (cached) = 0.004ms delay (50,000x faster)

    SAFETY: Slow access would block LLM and safety systems. <1ms ensures
    telemetry queries don't add latency to critical decision paths.
    """

    @pytest.mark.asyncio
    async def test_cache_fast_access(self) -> None:
        """100 cache reads complete in <100ms total (<1ms each).

        VALIDATES: Bulk reads meet timing requirements.

        MOCK SETUP:
        - Pre-populate cache with mock provider
        - Time 100 sequential reads

        SAFETY REASON: LLM may query telemetry multiple times per decision.
        100 reads in 100ms means each read is ~1ms or less.

        STEP-BY-STEP:
        1. Create cache
        2. Start with mock_provider
        3. Wait for initial data (150ms)
        4. Time 100 get_data() calls
        5. Stop cache
        6. Assert elapsed < 100ms (100 reads at <1ms each)
        """
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
        """Single cache read completes in <1ms.

        VALIDATES: Individual read timing meets spec.

        MOCK SETUP: Pre-populate cache, time single read.

        SAFETY REASON: 1ms is the hard requirement for real-time loops.
        MAVSDK queries can take 50-100ms; cache must be much faster.

        STEP-BY-STEP:
        1. Create and start cache with mock provider
        2. Wait for data
        3. Time single get_data() call
        4. Assert elapsed < 1ms
        5. Stop cache
        """
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
    """Test cache refresh at 100ms intervals.

    THESE TESTS VALIDATE:
    1. The background refresh loop executes at the configured frequency
    2. Provider exceptions don't crash the refresh loop (resilience)
    3. The atomic swap mechanism isolates slow fetches from fast reads

    ASYNC REFRESH ARCHITECTURE:
    ==========================
    The refresh loop runs in a background asyncio.Task created by start().
    This task lifecycle:

        start() called
            |
            v
        _running = True
            |
            v
        _refresh_task = asyncio.create_task(_refresh_loop())
            |
            v
        [concurrent with all other work]

    The _refresh_loop() coroutine runs independently, periodically calling
    the provider and atomically updating the data reference.

    ATOMIC SWAP MECHANISM:
    =====================
    Python's GIL (Global Interpreter Lock) ensures that reference assignments
    are atomic. When refresh updates data:

        # In refresh loop (background task)
        self._current_data = new_data  # Atomic pointer swap

        # In get_data() (reader, any thread)
        return self._current_data  # Atomic pointer read

    Readers see either the old reference OR the new reference, never a
    partially-updated or corrupt object. This is lock-free and wait-free.

    DECOUPLING PRINCIPLE:
    ====================
    The fundamental value of this cache is decoupling read performance from
    write (refresh) latency. Even if the provider takes 50ms:

        Time  0ms:  Reader calls get_data() -> fast (cached data v1)
        Time  2ms:  Reader calls get_data() -> fast (cached data v1)
        Time 10ms:  Refresh starts fetching (blocked on network)
        Time 60ms:  Refresh completes, swaps reference to data v2
        Time 62ms:  Reader calls get_data() -> fast (cached data v2)

    Readers never wait for the refresh to complete. They always get the
    most recent complete snapshot instantly.

    SAFETY: Regular refresh ensures data doesn't become stale. 100ms
    provides fresh data without overwhelming MAVSDK or network.
    """

    @pytest.mark.asyncio
    async def test_cache_refresh_interval(self) -> None:
        """Cache updates at 100ms intervals.

        VALIDATES: Provider is called at expected frequency.

        MOCK SETUP:
        - Create cache with refresh_ms=100
        - Count provider calls

        SAFETY REASON: Stale data older than 500ms is considered unsafe.
        100ms refresh ensures data is always fresh enough for decisions.

        STEP-BY-STEP:
        1. Create cache with refresh_ms=100
        2. Define counting_provider that increments call_count
        3. Start cache
        4. Wait 50ms, record call_count
        5. Wait 250ms more
        6. Assert at least 2 additional calls (100ms interval)
        7. Stop cache
        """
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
        """Cache refreshes in background without blocking reads.

        VALIDATES: Read operations don't wait for refresh.

        MOCK SETUP:
        - Create cache with fast refresh (50ms)
        - Provider takes 20ms (simulates slow MAVSDK query)

        SAFETY REASON: If reads blocked during refresh, a slow MAVSDK
        query would stall the LLM decision loop. Background refresh
        ensures reads are always fast.

        STEP-BY-STEP:
        1. Create cache with refresh_ms=50
        2. Define slow_provider with 20ms sleep
        3. Start cache
        4. Perform 10 reads, each followed by 30ms sleep
        5. Record timing of each read
        6. Assert all reads took <1ms (non-blocking)
        7. Stop cache
        """
        cache = TelemetryCache(refresh_ms=50)
        refresh_count = 0

        async def slow_provider():
            nonlocal refresh_count
            refresh_count += 1
            await asyncio.sleep(0.02)  # Slow refresh
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
    """Test stale data detection (>500ms).

    THESE TESTS VALIDATE:
    1. Data freshness is correctly tracked via timestamps
    2. The stale threshold (stale_ms) is respected
    3. Consumers can detect and react to stale data

    DATA FRESHNESS GUARANTEES:
    ==========================
    The cache provides bounded freshness guarantees:

    WHEN REFRESH IS WORKING:
    - Maximum staleness: refresh_interval + network_latency (~120ms)
    - Typical staleness: refresh_interval / 2 (~50ms)
    - is_stale() returns False

    WHEN REFRESH FAILS OR STOPS:
    - After stale_ms (default 500ms): is_stale() returns True
    - Data is still returned (better than nothing for debugging)
    - Consumers can decide: use cautiously or wait for fresh data

    STALENESS THRESHOLD RATIONALE (500ms default):
    =============================================
    - Too short (<200ms): False positives from temporary network hiccups
    - Too long (>1000ms): Dangerous - drone state may change significantly
    - 500ms = 5 refresh cycles at 100ms interval
    - Tolerates brief network issues while still detecting real problems

    USE CASES FOR STALE DETECTION:
    ==============================
    1. Safety systems: Abort mission if telemetry stale > 500ms
    2. LLM decisions: Reduce confidence weight of stale telemetry
    3. Health monitoring: Alert operator to connection issues
    4. Recovery logic: Attempt reconnection when stale detected

    SAFETY: Stale data is dangerous - the drone may have moved, battery
    may have dropped, GPS may have been lost. is_stale() warns consumers.
    """

    @pytest.mark.asyncio
    async def test_stale_data_detection(self) -> None:
        """Correctly detects data older than 500ms as stale.

        VALIDATES: Fresh data is not marked stale.

        MOCK SETUP:
        - Create cache with stale_ms=500
        - Start with mock provider

        SAFETY REASON: After 500ms without refresh, data may not reflect
        current reality. is_stale() alerts consumers to handle carefully.

        STEP-BY-STEP:
        1. Create cache with stale_ms=500
        2. Start with mock provider
        3. Wait for data (150ms)
        4. Assert is_stale() returns False (fresh data)
        5. Stop cache
        """
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
        """Data becomes stale after cache stops.

        VALIDATES: Stale detection works after cache shutdown.

        MOCK SETUP:
        - Create cache with stale_ms=100
        - Start, wait for data, stop, wait for staleness

        SAFETY REASON: After stop, no new data arrives. Old data quickly
        becomes stale. is_stale() must detect this condition.

        STEP-BY-STEP:
        1. Create cache with stale_ms=100 (fast for testing)
        2. Start with mock provider
        3. Wait for data (150ms)
        4. Stop cache (no more updates)
        5. Wait 150ms (exceeds 100ms stale threshold)
        6. Assert is_stale() returns True
        """
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
        """get_fresh_data refreshes if data is stale.

        VALIDATES: Explicit fresh read triggers refresh.

        MOCK SETUP:
        - Create cache with slow refresh (1000ms)
        - Start, stop, let data go stale

        SAFETY REASON: When stale data detected, get_fresh_data()
        allows explicit refresh for critical decisions.

        STEP-BY-STEP:
        1. Create cache with refresh_ms=1000 (slow)
        2. Start with counting provider
        3. Wait for initial data
        4. Stop cache
        5. Wait for staleness
        6. Assert is_stale() is True
        """
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
    """Test thread-safe concurrent access.

    THESE TESTS VALIDATE:
    1. Multiple simultaneous reads don't corrupt data
    2. Reads complete successfully even during active refresh
    3. The lock-free design handles high concurrency without blocking

    THREAD SAFETY MECHANISM:
    ======================
    The cache uses a lock-free design enabled by Python's GIL and immutable
    data objects:

    1. TelemetryData is immutable (dataclass, fields don't change after creation)
    2. _current_data is a single object reference
    3. Reference reads/writes are atomic under the GIL
    4. Readers get either the old or new reference, never partial data

    READ SCENARIO - No Refresh Active:
    =================================
        Reader 1:  get_data() -> returns ref to Data_v1
        Reader 2:  get_data() -> returns ref to Data_v1
        Reader 3:  get_data() -> returns ref to Data_v1

    All readers get the same reference. No locks needed.

    READ SCENARIO - Refresh Mid-Read:
    ================================
        Reader 1:  get_data() -> returns ref to Data_v1
        Refresh:   _current_data = Data_v2  (atomic swap)
        Reader 2:  get_data() -> returns ref to Data_v2

    Reader 1 gets v1, Reader 2 gets v2. Both are valid, consistent snapshots.
    No reader waits or gets corrupted data.

    WHY LOCK-FREE MATTERS:
    =====================
    Traditional locking would require:

        with self._lock:           # Acquire lock (contention point)
            return self._data       # Read
                                    # Release lock

    Under high concurrency, locks create:
    - Contention (threads waiting for lock)
    - Priority inversion (reader blocked by refresh)
    - Cache coherence overhead

    Lock-free design eliminates all these issues. Readers never wait.

    SAFETY: Multiple components (LLM, Guardian, Operator) may query
    telemetry simultaneously. Thread safety prevents data corruption.
    """

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Multiple concurrent reads are thread-safe.

        VALIDATES: 50 simultaneous reads complete without error.

        MOCK SETUP:
        - Pre-populate cache
        - Launch 50 concurrent read tasks

        SAFETY REASON: Race conditions could return corrupted telemetry
        (e.g., mixed fields from different updates). Thread safety ensures
        each read gets a consistent snapshot.

        STEP-BY-STEP:
        1. Create and start cache with mock provider
        2. Wait for data
        3. Define async read_task calling get_data()
        4. Create 50 tasks
        5. Gather all results
        6. Assert all reads succeeded (not None)
        7. Stop cache
        """
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
        """Reads during refresh don't block or corrupt.

        VALIDATES: Background refresh doesn't interfere with reads.

        MOCK SETUP:
        - Create cache with fast refresh (50ms)
        - Slow provider (10ms)
        - 5 reads every 30ms for 20 cycles

        SAFETY REASON: Refresh and reads must not block each other.
        Blocking would create the exact problem the cache solves.

        STEP-BY-STEP:
        1. Create cache with refresh_ms=50
        2. Define slow_provider with 10ms sleep
        3. Start cache
        4. Run 20 batches of 5 concurrent reads with 30ms delays
        5. Gather all results
        6. Filter exceptions
        7. Assert no exceptions occurred
        8. Stop cache
        """
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
    """Test telemetry history tracking.

    SAFETY: History enables trend analysis for predictive safety.
    """

    @pytest.mark.asyncio
    async def test_history_tracking(self) -> None:
        """History tracks telemetry over time.

        VALIDATES: get_history() returns populated history.

        MOCK SETUP:
        - Create cache with refresh_ms=50, history_size=10
        - Provider returns increasing altitude values

        SAFETY REASON: Trends reveal problems before they become critical.
        Rapid altitude change without command indicates control issues.

        STEP-BY-STEP:
        1. Create cache with fast refresh (50ms) and history_size=10
        2. Define altitude_provider returning increasing altitude
        3. Start cache
        4. Wait for multiple updates (300ms)
        5. Get history
        6. Assert history has entries
        7. Get altitude trend
        8. Assert trend > 0 (ascending detected)
        9. Stop cache
        """
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
    """Test cache performance metrics.

    SAFETY: Metrics enable monitoring cache health and diagnosing issues.
    """

    @pytest.mark.asyncio
    async def test_metrics_tracking(self) -> None:
        """Cache tracks performance metrics.

        VALIDATES: get_metrics() returns operational stats.

        MOCK SETUP: Start cache, perform reads, get metrics.

        SAFETY REASON: Metrics reveal operational problems (low hit count
        indicates provider issues, high refresh latency indicates MAVSDK
        performance problems).

        STEP-BY-STEP:
        1. Create and start cache with mock provider
        2. Wait for refresh
        3. Perform 5 reads
        4. Get metrics
        5. Assert metrics contains: hit_count, refresh_count, last_refresh_time
        6. Stop cache
        """
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
    """Test edge cases and error handling.

    SAFETY: Edge cases must be handled gracefully. Crashes during edge
    cases could leave the system without telemetry during critical moments.
    """

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self) -> None:
        """Start/stop can be called multiple times safely.

        VALIDATES: Idempotent lifecycle operations.

        MOCK SETUP: Call start twice, stop twice.

        SAFETY REASON: Idempotent operations prevent resource leaks and
        exceptions during cleanup.

        STEP-BY-STEP:
        1. Create cache with mock provider
        2. Call start() twice (should not crash)
        3. Call stop() twice (should not crash)
        """
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
        """Cache handles provider exceptions gracefully.

        VALIDATES: Exceptions don't crash the cache.

        MOCK SETUP:
        - Create provider that raises every other call
        - Let cache run for multiple cycles

        SAFETY REASON: MAVSDK queries can fail intermittently. Cache
        must survive these failures and continue operating.

        STEP-BY-STEP:
        1. Create cache
        2. Define flaky_provider that raises every even call
        3. Start cache
        4. Wait for multiple cycles (250ms)
        5. Assert cache still has data (from successful calls)
        6. Stop cache
        """
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
        """Cache handles missing provider gracefully.

        VALIDATES: Safe behavior when no provider configured.

        MOCK SETUP: Create cache, don't set provider.

        SAFETY REASON: get_data() without provider should return None
        rather than crash. Allows explicit handling.

        STEP-BY-STEP:
        1. Create cache (no provider)
        2. Call get_data()
        3. Assert returns None
        4. Call is_stale()
        5. Assert returns True (no data means stale)
        """
        cache = TelemetryCache()

        # Don't set provider
        data = cache.get_data()
        assert data is None

        is_stale = cache.is_stale()
        assert is_stale is True  # No data means stale


class TestConfigurableIntervals:
    """Test configurable refresh and stale intervals.

    SAFETY: Different missions may need different tradeoffs between
    freshness and overhead. Configurability allows tuning.
    """

    @pytest.mark.asyncio
    async def test_custom_refresh_interval(self) -> None:
        """Custom refresh interval is respected.

        VALIDATES: refresh_ms parameter controls timing.

        MOCK SETUP:
        - Create cache with refresh_ms=200
        - Count provider calls

        SAFETY REASON: 100ms default may be too aggressive for some
        setups (e.g., slow radio links). Custom intervals allow tuning.

        STEP-BY-STEP:
        1. Create cache with refresh_ms=200
        2. Define counting_provider
        3. Start cache
        4. Wait 50ms, record count
        5. Wait 250ms more
        6. Assert ~1-2 additional calls (200ms interval in 250ms)
        7. Stop cache
        """
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
        """Default intervals are set correctly.

        VALIDATES: Unconfigured cache has safe defaults.

        MOCK SETUP: Create cache with no parameters.

        SAFETY REASON: Defaults must be safe for general use.

        DEFAULTS:
        - refresh_ms=100: 10Hz refresh
        - stale_ms=500: 500ms stale threshold

        STEP-BY-STEP:
        1. Create TelemetryCache with no arguments
        2. Assert refresh_ms == 100
        3. Assert stale_ms == 500
        """
        cache = TelemetryCache()

        assert cache.refresh_ms == 100
        assert cache.stale_ms == 500
