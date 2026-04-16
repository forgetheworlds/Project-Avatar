"""Telemetry Cache System for non-blocking telemetry access.

This module provides a thread-safe telemetry cache with background refresh
to eliminate blocking telemetry fetches from MAVSDK.

WHY CACHING MATTERS (Performance Architecture):
-----------------------------
MAVSDK telemetry calls can take 10-100ms due to:
- Network latency to the drone (UDP/TCP round-trips)
- MAVLink message processing overhead
- PX4 internal state aggregation

If the main control loop or LLM agent blocks on every telemetry fetch,
the system becomes unresponsive. A 100ms telemetry fetch means:
- Control loop frequency drops to 10Hz maximum
- LLM agent can't respond to user queries while waiting
- Vision processing stalls during flight mode changes

THE SOLUTION: Background Refresh Architecture
---------------------------------------------
This cache implements a "reader-writer" pattern where:

1. BACKGROUND WRITER (async refresh loop):
   - Runs independently at 100ms intervals
   - Handles all slow MAVSDK calls
   - Updates shared cache with fresh data
   - Continues even if individual fetches fail (graceful degradation)

2. FAST READER (get_data()):
   - Returns cached data in <1ms (just a dictionary lookup)
   - Never blocks on network or MAVSDK
   - Always available for control loops and agents

3. STALENESS MONITORING:
   - Tracks when data was last updated
   - Detects if provider is failing (stale > 500ms)
   - Allows callers to decide: use stale data or wait for fresh

This architecture separates the "slow I/O" concern from the "fast decision"
concern, enabling real-time performance even with unreliable telemetry sources.

Key features:
- 100ms background refresh interval
- <1ms cache read access
- Thread-safe concurrent access
- Stale data detection (>500ms)
- Historical data tracking with trend analysis

Example:
    cache = TelemetryCache()
    await cache.start(telemetry_provider)

    # Fast non-blocking access - control loop stays responsive
    data = cache.get_data()  # <1ms

    # Check staleness if freshness matters for safety decisions
    if cache.is_stale():
        logger.warning("Using stale telemetry data - proceed with caution")

    await cache.stop()
"""

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Deque, Dict, Optional

logger = logging.getLogger(__name__)

# Type alias for the telemetry provider function.
# This is typically an async function that calls MAVSDK telemetry methods
# and returns a populated TelemetryData dataclass.
# Example: async def get_telemetry() -> TelemetryData: ...
TelemetryProvider = Callable[[], Coroutine[Any, Any, "TelemetryData"]]


@dataclass
class TelemetryData:
    """Complete telemetry snapshot with all essential flight data.

    This dataclass represents a single point-in-time snapshot of the drone's
    state. It's designed to be:
    1. Immutable (created fresh on each refresh, never modified)
    2. Serializable (can be sent to LLM agents or logged)
    3. Complete (all critical flight data in one object)

    The immutability is key to thread safety - once created, a TelemetryData
    instance won't change, so multiple readers can safely access it without
    locks on the data itself.

    Attributes:
        timestamp: Unix timestamp when data was captured (time.time())
        latitude: GPS latitude in degrees
        longitude: GPS longitude in degrees
        altitude: Altitude above home in meters
        velocity_north: Velocity north component in m/s
        velocity_east: Velocity east component in m/s
        velocity_down: Velocity down component in m/s
        groundspeed: Total ground speed in m/s
        roll: Roll angle in radians
        pitch: Pitch angle in radians
        yaw: Yaw angle in radians (0 = North, increases clockwise)
        battery_percent: Battery percentage (0-100)
        battery_voltage: Battery voltage in volts
        battery_current: Battery current in amps (negative = discharging)
        armed: Whether the vehicle is armed (motors active)
        in_air: Whether the vehicle is in the air (flying)
        flight_mode: Current flight mode string (e.g., "Hold", "Mission")
        gps_fix: GPS fix type (0-6, where 3+ is 3D fix)
        is_gps_ok: Whether GPS is healthy enough for navigation
        is_home_position_ok: Whether home position is set (required for RTL)
    """

    timestamp: float
    latitude: float
    longitude: float
    altitude: float
    velocity_north: float
    velocity_east: float
    velocity_down: float
    groundspeed: float
    roll: float
    pitch: float
    yaw: float
    battery_percent: float
    battery_voltage: float
    battery_current: float
    armed: bool
    in_air: bool
    flight_mode: str
    gps_fix: int
    is_gps_ok: bool
    is_home_position_ok: bool


@dataclass
class TelemetryHistory:
    """Historical data storage with trend analysis for predictive insights.

    Maintains a rolling window of recent telemetry points for:
    1. Trend analysis (is altitude increasing or decreasing?)
    2. Anomaly detection (sudden changes from recent pattern)
    3. LLM context (recent flight path for decision making)

    Uses a deque with maxlen for automatic circular buffer behavior -
    old data is automatically discarded when max_size is reached.

    Attributes:
        max_size: Maximum number of data points to store (default 100)
        data: Deque of TelemetryData points (most recent at end)
    """

    max_size: int = 100
    data: Deque[TelemetryData] = field(default_factory=lambda: deque(maxlen=100))

    def __post_init__(self) -> None:
        """Initialize the deque with correct max_size after dataclass creation.

        The default_factory creates a deque with maxlen=100, but we need to
        ensure it's created with the actual max_size if different from default.
        """
        if not hasattr(self, '_initialized'):
            self.data: Deque[TelemetryData] = deque(maxlen=self.max_size)
            self._initialized = True

    def add(self, data: TelemetryData) -> None:
        """Add a telemetry data point to history.

        Args:
            data: TelemetryData to add. Appended to the right (end) of deque.
                  If deque is full, oldest entry is automatically removed.
        """
        self.data.append(data)

    def get_latest(self) -> Optional[TelemetryData]:
        """Get the most recent data point.

        Returns:
            Latest TelemetryData or None if history is empty.
            The latest is at index -1 (right end of deque).
        """
        if not self.data:
            return None
        return self.data[-1]

    def get_trend(self, field: str) -> float:
        """Calculate trend for a numeric field using linear regression.

        Uses simple linear regression over the stored data points to determine
        if the value is increasing, decreasing, or stable. This is useful for:
        - Predicting battery drain rate
        - Detecting climbing/descending trends
        - Estimating time-to-arrival

        Args:
            field: Name of the field to analyze (e.g., "altitude", "battery_percent")

        Returns:
            Trend value (positive = increasing, negative = decreasing,
                        zero = stable). Returns 0.0 if insufficient data.

        Mathematical approach:
        - Simple linear regression: slope = (n*sum(xy) - sum(x)*sum(y)) / (n*sum(x^2) - sum(x)^2)
        - x = time index (0, 1, 2, ...)
        - y = field values
        """
        if len(self.data) < 2:
            return 0.0

        # Extract values for the specified field
        values = []
        timestamps = []

        for i, data in enumerate(self.data):
            if hasattr(data, field):
                val = getattr(data, field)
                if isinstance(val, (int, float)):
                    values.append(float(val))
                    timestamps.append(float(i))

        if len(values) < 2:
            return 0.0

        # Simple linear regression for trend
        n = len(values)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(timestamps, values))
        sum_x2 = sum(x * x for x in timestamps)

        # Calculate slope (trend)
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope


class TelemetryCache:
    """Thread-safe cache with background refresh for MAVSDK telemetry.

    ARCHITECTURE OVERVIEW:
    --------------------
    This class implements the core caching pattern that makes the system responsive:

         ┌─────────────────┐
         │   Control Loop  │  <-- Calls get_data() (<1ms)
         │   / LLM Agent   │      No blocking, always responsive
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │   Cached Data   │  <-- Protected by _data_lock (RLock)
         │   (TelemetryData)│     Fast read access
         └────────┬────────┘
                  ▲
                  │
         ┌─────────────────┐
         │  Refresh Loop   │  <-- Runs in background (asyncio.Task)
         │  (100ms interval)│     Handles slow MAVSDK calls
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │    MAVSDK       │  <-- Network calls to PX4 (10-100ms)
         │   Telemetry     │
         └─────────────────┘

    THREAD SAFETY EXPLANATION:
    -------------------------
    This class uses multiple locks for different concerns:

    1. _data_lock (RLock - Reentrant Lock):
       - Protects the _data variable (the cached TelemetryData)
       - RLock allows the same thread to acquire it multiple times
       - This prevents race conditions when refresh updates data while get_data reads it
       - The lock is held only for the brief dictionary assignment/retrieval (<1ms)

    2. _metrics_lock (Lock):
       - Protects hit_count, refresh_count counters
       - Separated from _data_lock to avoid holding locks during logging

    3. _start_lock (asyncio.Lock):
       - Async lock for start/stop operations
       - Ensures idempotent start/stop (safe to call multiple times)
       - Prevents race conditions during initialization

    WHY RLock INSTEAD OF STANDARD LOCK?
    -----------------------------------
    RLock (Reentrant Lock) allows the same thread to acquire the lock multiple
    times without deadlocking. This is important because:
    - In complex control flows, the same thread might call get_data() multiple times
    - Python's async/await with threading can cause subtle reentrancy issues
    - RLock is safer when you're not 100% sure about call patterns

    ASYNC REFRESH ARCHITECTURE:
    ---------------------------
    The refresh loop (_refresh_loop) is an asyncio.Task that:
    1. Runs continuously in the background while the cache is started
    2. Uses asyncio.Event (_stop_event) for clean shutdown signaling
    3. Handles exceptions gracefully - one failed fetch doesn't kill the loop
    4. Updates the cache atomically under the _data_lock

    DATA FRESHNESS GUARANTEES:
    --------------------------
    - Best case: Data is <100ms old (just refreshed)
    - Normal case: Data is 100-200ms old (between refreshes)
    - Worst case: Data is >500ms old (provider failing, marked as stale)
    - is_stale() lets callers decide whether to use or wait for fresh data

    Attributes:
        DEFAULT_REFRESH_MS: Default refresh interval (100ms)
        DEFAULT_STALE_MS: Default stale data threshold (500ms)

    Example:
        # Create cache with custom intervals
        cache = TelemetryCache(refresh_ms=100, stale_ms=500)

        # Start background refresh
        await cache.start(telemetry_provider)

        # Fast access anywhere in the application
        data = cache.get_data()
        if data:
            print(f"Altitude: {data.altitude}m (age: {cache.get_age_ms():.0f}ms)")

        # Clean shutdown
        await cache.stop()
    """

    # Default refresh interval: 100ms = 10Hz update rate
    # This balances freshness with MAVSDK/network overhead
    DEFAULT_REFRESH_MS = 100

    # Default stale threshold: 500ms = 5x the refresh interval
    # If no successful refresh for 500ms, data is considered unreliable
    DEFAULT_STALE_MS = 500

    def __init__(
        self,
        refresh_ms: int = DEFAULT_REFRESH_MS,
        stale_ms: int = DEFAULT_STALE_MS,
        history_size: int = 100,
    ) -> None:
        """Initialize the telemetry cache.

        Args:
            refresh_ms: Background refresh interval in milliseconds.
                        Lower = fresher data but more CPU/network load.
                        Higher = less overhead but more staleness.
            stale_ms: Data staleness threshold in milliseconds.
                      If no successful refresh for this long, is_stale() returns True.
            history_size: Maximum number of historical data points for trend analysis.
                          Each point is ~200 bytes, so 100 points = ~20KB.
        """
        self.refresh_ms = refresh_ms
        self.stale_ms = stale_ms
        self._history_size = history_size

        # Core data storage: holds the single most recent TelemetryData snapshot.
        # This is the "hot" data that get_data() returns.
        # Initialized to None until first successful refresh.
        self._data: Optional[TelemetryData] = None

        # RLock protects _data from concurrent access.
        # The refresh loop writes to _data; get_data() reads from _data.
        # Without this lock, readers could get partially-written (corrupted) data.
        self._data_lock = threading.RLock()

        # History tracking: rolling window of recent data points for trend analysis.
        # Separate from _data because it's accessed less frequently.
        self._history = TelemetryHistory(max_size=history_size)

        # Background refresh infrastructure:
        # _refresh_task is the asyncio.Task running _refresh_loop
        # _stop_event signals the loop to terminate cleanly
        # _provider is the async function that fetches fresh telemetry
        self._refresh_task: Optional[asyncio.Task[Any]] = None
        self._stop_event = asyncio.Event()
        self._provider: Optional[TelemetryProvider] = None

        # Metrics tracking: performance counters for monitoring.
        # _hit_count: number of get_data() calls (cache hits)
        # _refresh_count: number of successful background refreshes
        # _last_refresh_time: timestamp of last successful refresh
        # Separate lock (_metrics_lock) to avoid holding _data_lock during metrics updates
        self._hit_count = 0
        self._refresh_count = 0
        self._last_refresh_time: Optional[float] = None
        self._metrics_lock = threading.Lock()

        # State tracking: prevents double-start or double-stop issues.
        # _started: whether the cache is currently running
        # _start_lock: async lock for thread-safe start/stop operations
        self._started = False
        self._start_lock = asyncio.Lock()

    async def start(self, provider: TelemetryProvider) -> None:
        """Start the background refresh loop.

        This method initializes the cache and begins the background refresh task.
        It is idempotent - calling it multiple times is safe.

        Args:
            provider: Async function that returns TelemetryData.
                      This is typically a function that calls MAVSDK telemetry methods.

        Flow:
        1. Acquire _start_lock to prevent concurrent start/stop
        2. Check if already started (return early if so)
        3. Store the provider function
        4. Clear the stop event
        5. Perform initial fetch immediately (so data is available right away)
        6. Start the background refresh task
        7. Mark as started

        Note:
            Can be called multiple times safely (idempotent).
        """
        async with self._start_lock:
            if self._started:
                logger.debug("TelemetryCache already started")
                return

            self._provider = provider
            self._stop_event.clear()

            # Perform initial fetch immediately so callers have data right away.
            # Without this, the first get_data() would return None until the
            # first background refresh completes (up to 100ms later).
            await self._refresh_once()

            # Start background refresh task as an asyncio.Task.
            # This runs _refresh_loop() concurrently with the main program.
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            self._started = True

            logger.debug(
                f"TelemetryCache started with {self.refresh_ms}ms refresh interval"
            )

    async def stop(self) -> None:
        """Stop the background refresh loop.

        This method cleanly shuts down the background refresh task.
        It is idempotent - calling it multiple times is safe.

        Flow:
        1. Acquire _start_lock to prevent concurrent start/stop
        2. Check if started (return early if not)
        3. Signal stop via _stop_event
        4. Cancel the refresh task
        5. Wait for task to complete (handle CancelledError)
        6. Clean up state

        Note:
            Can be called multiple times safely (idempotent).
            Stops immediately without waiting for current refresh to complete.
        """
        async with self._start_lock:
            if not self._started:
                return

            # Signal the refresh loop to stop
            self._stop_event.set()

            # Cancel the refresh task if it's still running
            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling

            self._refresh_task = None
            self._started = False

            logger.debug("TelemetryCache stopped")

    def get_data(self) -> Optional[TelemetryData]:
        """Get current telemetry data (non-blocking, <1ms).

        This is the primary method for accessing telemetry. It is designed to be:
        - Fast: Always returns in <1ms regardless of network conditions
        - Non-blocking: Never waits for MAVSDK or the drone
        - Safe: Thread-safe for concurrent access

        PERFORMANCE CHARACTERISTICS:
        - Lock acquisition: ~0.01ms (RLock is fast for uncontended access)
        - Data copy: ~0.001ms (just returning the reference)
        - Total: <1ms even under heavy load

        Compare to direct MAVSDK calls which can take 10-100ms due to network latency.

        Returns:
            TelemetryData if available, None if cache hasn't been populated yet.
            May return stale data - check is_stale() if freshness matters for safety.

        Thread Safety:
            This method acquires _data_lock briefly to ensure the data reference
            is read atomically. The returned TelemetryData is immutable (dataclass
            with no setters), so it's safe to use after the lock is released.
        """
        with self._data_lock:
            data = self._data

        # Update metrics outside the data lock to minimize lock contention.
        # Metrics are "nice to have" accurate, data must be accurate.
        with self._metrics_lock:
            self._hit_count += 1

        return data

    async def get_fresh_data(self, max_age_ms: Optional[int] = None) -> Optional[TelemetryData]:
        """Get data, refreshing first if stale.

        This method is a hybrid approach: it tries to return cached data quickly,
        but if the data is too old, it triggers a synchronous refresh first.

        Use case: When you need fresh data for a safety-critical decision,
        but want to avoid blocking if data is already fresh.

        Args:
            max_age_ms: Maximum acceptable age in milliseconds.
                       Defaults to stale_ms if not specified.

        Returns:
            TelemetryData if available, None otherwise.

        Performance:
            - If data is fresh: <1ms (same as get_data)
            - If data is stale: 10-100ms (waits for _refresh_once())

        Note:
            This may trigger a synchronous refresh if data is stale,
            making it slower than get_data(). Use sparingly in hot paths.
        """
        max_age = max_age_ms if max_age_ms is not None else self.stale_ms

        # Check if refresh needed
        with self._data_lock:
            if self._data is None:
                needs_refresh = True
            else:
                age_ms = (time.time() - self._data.timestamp) * 1000
                needs_refresh = age_ms > max_age

        if needs_refresh and self._provider:
            await self._refresh_once()

        return self.get_data()

    def is_stale(self) -> bool:
        """Check if cached data is stale (older than stale_ms threshold).

        Data becomes stale when:
        - No successful refresh has occurred (data is None)
        - The last successful refresh was >stale_ms milliseconds ago

        Stale data doesn't mean unusable - you might still use it for
        non-critical decisions while waiting for a fresh refresh.

        Returns:
            True if data is older than stale_ms or no data available,
            False if data is fresh (within stale_ms window).

        Example:
            data = cache.get_data()
            if cache.is_stale():
                logger.warning("Using stale data - fly cautiously")
            # Use data anyway (stale is better than nothing)
        """
        with self._data_lock:
            if self._data is None:
                return True

            age_ms = (time.time() - self._data.timestamp) * 1000
            return age_ms > self.stale_ms

    def get_age_ms(self) -> float:
        """Get the age of cached data in milliseconds.

        Returns:
            Age in milliseconds since last update, or infinity if no data.
            Can be used to make freshness decisions without calling is_stale().

        Example:
            age = cache.get_age_ms()
            if age < 200:
                # Data is very fresh
                pass
        """
        with self._data_lock:
            if self._data is None:
                return float('inf')

            return (time.time() - self._data.timestamp) * 1000

    def get_history(self) -> TelemetryHistory:
        """Get the telemetry history tracker.

        Returns:
            TelemetryHistory instance for trend analysis.
            This provides access to the rolling window of recent data points.

        Use cases:
        - Detecting if drone is climbing/descending
        - Calculating battery drain rate
        - Providing recent flight path to LLM agents
        """
        return self._history

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics for monitoring and debugging.

        Returns:
            Dictionary with:
            - hit_count: Total cache read operations (get_data() calls)
            - refresh_count: Total successful background refreshes
            - last_refresh_time: Timestamp of last successful refresh or None
            - is_stale: Current stale status

        These metrics help diagnose:
        - Cache effectiveness (hit_count vs refresh_count ratio)
        - Health of the telemetry provider (is_stale flag)
        - Timing issues (last_refresh_time)
        """
        with self._metrics_lock:
            with self._data_lock:
                last_refresh = self._last_refresh_time

            return {
                "hit_count": self._hit_count,
                "refresh_count": self._refresh_count,
                "last_refresh_time": last_refresh,
                "is_stale": self.is_stale(),
            }

    async def _refresh_loop(self) -> None:
        """Background task for periodic refresh.

        This is the core of the async refresh architecture. It runs as an
        asyncio.Task concurrently with the main program, continuously fetching
        fresh telemetry data in the background.

        ARCHITECTURE DETAILS:
        --------------------
        - Runs until stop() is called via _stop_event
        - Uses asyncio.wait_for() to implement the refresh interval
        - Handles exceptions gracefully - one bad fetch doesn't kill the loop
        - Updates cache atomically under _data_lock

        THE REFRESH INTERVAL MECHANISM:
        -------------------------------
        We use asyncio.wait_for() on _stop_event.wait() with a timeout:
        - If timeout expires: normal refresh interval, continue loop
        - If _stop_event is set: stop signal received, exit loop
        - This allows both clean shutdown and regular refresh timing

        Exception Handling Strategy:
        - CancelledError: Expected during shutdown, exit cleanly
        - Other exceptions: Log warning, continue loop (graceful degradation)
          This ensures one bad MAVSDK call doesn't crash the entire cache.
        """
        refresh_interval_s = self.refresh_ms / 1000.0

        while not self._stop_event.is_set():
            try:
                # Wait for the refresh interval or until stopped.
                # This pattern allows the loop to respond to stop signals
                # while also maintaining the refresh interval timing.
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=refresh_interval_s
                    )
                    break  # Stop event was set, exit loop
                except asyncio.TimeoutError:
                    pass  # Normal refresh interval, continue to refresh

                # Perform refresh if not stopped
                if not self._stop_event.is_set():
                    await self._refresh_once()

            except asyncio.CancelledError:
                # Task was cancelled (shutdown), exit cleanly
                break
            except Exception as e:
                # Log error but keep loop running - graceful degradation
                logger.warning(f"Telemetry refresh error: {e}")
                # Continue running - don't let errors kill the loop
                # This is important because MAVSDK can have transient failures

    async def _refresh_once(self) -> None:
        """Perform a single refresh operation.

        This method:
        1. Calls the provider function (slow MAVSDK call)
        2. Updates the cache with new data (under _data_lock)
        3. Adds to history for trend analysis
        4. Updates metrics

        THREAD SAFETY NOTE:
        ------------------
        The lock is held only for the brief assignment to _data, not during
        the slow provider call. This ensures readers never block on I/O.

        Error Handling:
        - If provider raises an exception, log it and keep existing data
        - This allows graceful degradation to slightly stale data
        - The is_stale() method will eventually flag the data as too old
        """
        if self._provider is None:
            return

        try:
            # Fetch from provider - this is the slow operation (10-100ms)
            # May raise exception if MAVSDK call fails
            data = await self._provider()

            # Update cache with lock - brief critical section (<1ms)
            with self._data_lock:
                self._data = data

            # Add to history for trend analysis
            self._history.add(data)

            # Update metrics (separate lock to minimize contention)
            with self._metrics_lock:
                self._refresh_count += 1
                self._last_refresh_time = time.time()

        except Exception as e:
            logger.warning(f"Telemetry fetch failed: {e}")
            # Don't update cache on error - keep existing data
            # This allows graceful degradation to slightly stale data
            # Callers can check is_stale() to decide if stale is acceptable

    async def __aenter__(self) -> "TelemetryCache":
        """Async context manager entry.

        Note: Provider must be set separately before entering context.
        Typically used as:
            cache = TelemetryCache()
            await cache.start(provider)
            async with cache:
                # Use cache
                pass
            # Auto-stops on exit
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> None:
        """Async context manager exit - ensures stop is called.

        This guarantees the cache stops even if an exception occurs
        in the context manager body.
        """
        await self.stop()
