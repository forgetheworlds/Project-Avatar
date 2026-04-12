"""Telemetry Cache System for non-blocking telemetry access.

This module provides a thread-safe telemetry cache with background refresh
to eliminate blocking telemetry fetches from MAVSDK.

Key features:
- 100ms background refresh interval
- <1ms cache read access
- Thread-safe concurrent access
- Stale data detection (>500ms)
- Historical data tracking with trend analysis

Example:
    cache = TelemetryCache()
    await cache.start(telemetry_provider)

    # Fast non-blocking access
    data = cache.get_data()  # <1ms

    # Check staleness
    if cache.is_stale():
        logger.warning("Using stale telemetry data")

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

# Type alias for the telemetry provider function
TelemetryProvider = Callable[[], Coroutine[Any, Any, "TelemetryData"]]


@dataclass
class TelemetryData:
    """Complete telemetry snapshot.

    Attributes:
        timestamp: Unix timestamp when data was captured
        latitude: GPS latitude in degrees
        longitude: GPS longitude in degrees
        altitude: Altitude above home in meters
        velocity_north: Velocity north component in m/s
        velocity_east: Velocity east component in m/s
        velocity_down: Velocity down component in m/s
        groundspeed: Total ground speed in m/s
        roll: Roll angle in radians
        pitch: Pitch angle in radians
        yaw: Yaw angle in radians
        battery_percent: Battery percentage (0-100)
        battery_voltage: Battery voltage in volts
        battery_current: Battery current in amps
        armed: Whether the vehicle is armed
        in_air: Whether the vehicle is in the air
        flight_mode: Current flight mode string
        gps_fix: GPS fix type (0-6, where 3+ is 3D fix)
        is_gps_ok: Whether GPS is healthy
        is_home_position_ok: Whether home position is set
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
    """Historical data storage with trend analysis.

    Attributes:
        max_size: Maximum number of data points to store
        data: Deque of TelemetryData points
    """

    max_size: int = 100
    data: Deque[TelemetryData] = field(default_factory=lambda: deque(maxlen=100))

    def __post_init__(self) -> None:
        """Initialize the deque with correct max_size."""
        if not hasattr(self, '_initialized'):
            self.data: Deque[TelemetryData] = deque(maxlen=self.max_size)
            self._initialized = True

    def add(self, data: TelemetryData) -> None:
        """Add a telemetry data point to history.

        Args:
            data: TelemetryData to add
        """
        self.data.append(data)

    def get_latest(self) -> Optional[TelemetryData]:
        """Get the most recent data point.

        Returns:
            Latest TelemetryData or None if empty
        """
        if not self.data:
            return None
        return self.data[-1]

    def get_trend(self, field: str) -> float:
        """Calculate trend for a numeric field.

        Uses linear regression over the stored data points to determine
        if the value is increasing, decreasing, or stable.

        Args:
            field: Name of the field to analyze (e.g., "altitude")

        Returns:
            Trend value (positive = increasing, negative = decreasing,
                        zero = stable). Returns 0.0 if insufficient data.
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
    """Thread-safe cache with background refresh.

    This class maintains a cached copy of telemetry data that is refreshed
    in the background at configurable intervals. All read operations are
    non-blocking and complete in <1ms.

    Attributes:
        DEFAULT_REFRESH_MS: Default refresh interval (100ms)
        DEFAULT_STALE_MS: Default stale data threshold (500ms)

    Example:
        cache = TelemetryCache(refresh_ms=100, stale_ms=500)
        await cache.start(telemetry_provider)

        # Fast access anywhere in the application
        data = cache.get_data()
        if data:
            print(f"Altitude: {data.altitude}")

        await cache.stop()
    """

    DEFAULT_REFRESH_MS = 100
    DEFAULT_STALE_MS = 500

    def __init__(
        self,
        refresh_ms: int = DEFAULT_REFRESH_MS,
        stale_ms: int = DEFAULT_STALE_MS,
        history_size: int = 100,
    ) -> None:
        """Initialize the telemetry cache.

        Args:
            refresh_ms: Background refresh interval in milliseconds
            stale_ms: Data staleness threshold in milliseconds
            history_size: Maximum number of historical data points
        """
        self.refresh_ms = refresh_ms
        self.stale_ms = stale_ms
        self._history_size = history_size

        # Core data storage with thread-safe lock
        self._data: Optional[TelemetryData] = None
        self._data_lock = threading.RLock()

        # History tracking
        self._history = TelemetryHistory(max_size=history_size)

        # Background refresh task
        self._refresh_task: Optional[asyncio.Task[Any]] = None
        self._stop_event = asyncio.Event()
        self._provider: Optional[TelemetryProvider] = None

        # Metrics tracking
        self._hit_count = 0
        self._refresh_count = 0
        self._last_refresh_time: Optional[float] = None
        self._metrics_lock = threading.Lock()

        # State tracking
        self._started = False
        self._start_lock = asyncio.Lock()

    async def start(self, provider: TelemetryProvider) -> None:
        """Start the background refresh loop.

        Args:
            provider: Async function that returns TelemetryData

        Note:
            Can be called multiple times safely (idempotent).
        """
        async with self._start_lock:
            if self._started:
                logger.debug("TelemetryCache already started")
                return

            self._provider = provider
            self._stop_event.clear()

            # Perform initial fetch immediately
            await self._refresh_once()

            # Start background refresh task
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            self._started = True

            logger.debug(
                f"TelemetryCache started with {self.refresh_ms}ms refresh interval"
            )

    async def stop(self) -> None:
        """Stop the background refresh loop.

        Note:
            Can be called multiple times safely (idempotent).
            Stops immediately without waiting for current refresh.
        """
        async with self._start_lock:
            if not self._started:
                return

            # Signal stop
            self._stop_event.set()

            # Cancel the refresh task
            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass

            self._refresh_task = None
            self._started = False

            logger.debug("TelemetryCache stopped")

    def get_data(self) -> Optional[TelemetryData]:
        """Get current telemetry data (non-blocking, <1ms).

        Returns:
            TelemetryData if available, None otherwise.
            May return stale data - check is_stale() if freshness matters.

        Performance:
            This operation completes in <1ms regardless of network
            or MAVSDK latency.
        """
        with self._data_lock:
            data = self._data

        with self._metrics_lock:
            self._hit_count += 1

        return data

    async def get_fresh_data(self, max_age_ms: Optional[int] = None) -> Optional[TelemetryData]:
        """Get data, refreshing first if stale.

        Args:
            max_age_ms: Maximum acceptable age in milliseconds.
                       Defaults to stale_ms if not specified.

        Returns:
            TelemetryData if available, None otherwise.

        Note:
            This may trigger a synchronous refresh if data is stale,
            making it slower than get_data().
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
        """Check if cached data is stale.

        Returns:
            True if data is older than stale_ms or no data available,
            False if data is fresh.
        """
        with self._data_lock:
            if self._data is None:
                return True

            age_ms = (time.time() - self._data.timestamp) * 1000
            return age_ms > self.stale_ms

    def get_history(self) -> TelemetryHistory:
        """Get the telemetry history tracker.

        Returns:
            TelemetryHistory instance for trend analysis.
        """
        return self._history

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics.

        Returns:
            Dictionary with:
            - hit_count: Total cache read operations
            - refresh_count: Total background refreshes
            - last_refresh_time: Timestamp of last refresh or None
            - is_stale: Current stale status
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

        Runs continuously until stop() is called.
        Handles exceptions gracefully to keep the loop running.
        """
        refresh_interval_s = self.refresh_ms / 1000.0

        while not self._stop_event.is_set():
            try:
                # Wait for the refresh interval or until stopped
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=refresh_interval_s
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Normal refresh interval

                # Perform refresh
                if not self._stop_event.is_set():
                    await self._refresh_once()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telemetry refresh error: {e}")
                # Continue running - don't let errors kill the loop

    async def _refresh_once(self) -> None:
        """Perform a single refresh operation.

        Fetches new data from the provider and updates the cache.
        Handles provider exceptions gracefully.
        """
        if self._provider is None:
            return

        try:
            # Fetch from provider
            data = await self._provider()

            # Update cache with lock
            with self._data_lock:
                self._data = data

            # Add to history
            self._history.add(data)

            # Update metrics
            with self._metrics_lock:
                self._refresh_count += 1
                self._last_refresh_time = time.time()

        except Exception as e:
            logger.warning(f"Telemetry fetch failed: {e}")
            # Don't update cache on error - keep existing data
            # This allows graceful degradation to slightly stale data

    async def __aenter__(self) -> "TelemetryCache":
        """Async context manager entry.

        Note: Provider must be set separately before entering context.
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> None:
        """Async context manager exit - ensures stop."""
        await self.stop()
