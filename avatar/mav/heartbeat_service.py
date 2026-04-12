"""20Hz Heartbeat Service for offboard mode safety.

This module provides a 20Hz heartbeat service critical for maintaining PX4 offboard mode.
PX4 requires a continuous 20Hz heartbeat (50ms intervals) or the COM_OF_LOSS_T
failsafe will trigger. This service maintains that heartbeat while tracking multiple
heartbeat sources for distributed system safety.

Key features:
- 20Hz heartbeat emission (50ms precision)
- 500ms offboard timeout (10 missed beats)
- <50ms latency between scheduled and actual emission
- Automatic failsafe trigger on timeout
- Multiple heartbeat sources tracked separately

Example:
    service = HeartbeatService()
    await service.start()

    # Record heartbeats from various sources
    service.record_heartbeat(HeartbeatSource.LLM, time.time())
    service.record_heartbeat(HeartbeatSource.GUARDIAN, time.time())

    # Check source health
    if not service.is_source_healthy(HeartbeatSource.LLM):
        logger.warning("LLM heartbeat lost!")

    await service.stop()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

# Type aliases for callbacks
HeartbeatCallback = Callable[["HeartbeatSource", float], Coroutine[Any, Any, None]]
FailsafeCallback = Callable[["HeartbeatSource"], Coroutine[Any, Any, None]]
WarningCallback = Callable[["HeartbeatSource", float], Coroutine[Any, Any, None]]


class HeartbeatSource(Enum):
    """Sources of heartbeat signals.

    Multiple sources can emit heartbeats, and each is tracked independently.
    If any critical source times out, the failsafe callback is triggered.
    """

    GUARDIAN = "guardian"
    LLM = "llm"
    OPERATOR = "operator"
    OFFBOARD = "offboard"


class HeartbeatState(Enum):
    """State of a heartbeat source."""

    HEALTHY = auto()
    WARNING = auto()
    TIMEOUT = auto()
    STOPPED = auto()


@dataclass
class HeartbeatConfig:
    """Configuration for the heartbeat service.

    Attributes:
        heartbeat_hz: Target heartbeat frequency (default: 20.0 = 50ms intervals)
        offboard_timeout_s: Time before a source is considered timed out (default: 0.5s)
        warning_threshold_s: Time before warning callback is triggered (default: 0.3s)
        emit_heartbeat: Whether to emit heartbeats or just monitor (default: True)
    """

    heartbeat_hz: float = 20.0
    offboard_timeout_s: float = 0.5
    warning_threshold_s: float = 0.3
    emit_heartbeat: bool = True


@dataclass
class SourceStatus:
    """Status of a single heartbeat source.

    Attributes:
        last_beat: Unix timestamp of last heartbeat
        state: Current state of the source
        missed_beats: Number of consecutive missed beats
        total_beats: Total number of beats received
    """

    last_beat: float
    state: HeartbeatState
    missed_beats: int
    total_beats: int


class HeartbeatService:
    """20Hz heartbeat service for offboard mode safety.

    This service maintains a 20Hz heartbeat (50ms intervals) required by PX4
    for offboard mode operation. It also tracks multiple heartbeat sources
    and triggers failsafe callbacks if any critical source times out.

    Attributes:
        DEFAULT_HEARTBEAT_HZ: Default heartbeat frequency (20Hz)
        DEFAULT_OFFBOARD_TIMEOUT_S: Default offboard timeout (0.5s)

    Example:
        service = HeartbeatService()
        service.on_failsafe = lambda source: print(f"Failsafe: {source}")
        await service.start()

        # Main loop records heartbeats
        while running:
            service.record_heartbeat(HeartbeatSource.LLM, time.time())
            await asyncio.sleep(0.05)  # 20Hz

        await service.stop()
    """

    DEFAULT_HEARTBEAT_HZ = 20.0
    DEFAULT_OFFBOARD_TIMEOUT_S = 0.5

    def __init__(self, config: Optional[HeartbeatConfig] = None) -> None:
        """Initialize the heartbeat service.

        Args:
            config: Configuration for the service. Uses defaults if not provided.
        """
        self.config = config or HeartbeatConfig()

        # Calculate interval from Hz
        self._interval_s = 1.0 / self.config.heartbeat_hz

        # Source tracking
        self._sources: Dict[HeartbeatSource, SourceStatus] = {}
        self._sources_lock = asyncio.Lock()

        # Tasks
        self._emit_task: Optional[asyncio.Task[Any]] = None
        self._monitor_task: Optional[asyncio.Task[Any]] = None
        self._stop_event = asyncio.Event()

        # State
        self._running = False
        self._start_time: float = 0.0
        self._emit_count = 0

        # Callbacks (can be overridden)
        self.on_heartbeat: Optional[HeartbeatCallback] = None
        self.on_failsafe: Optional[FailsafeCallback] = None
        self.on_warning: Optional[WarningCallback] = None

    @property
    def is_running(self) -> bool:
        """Whether the service is currently running."""
        return self._running

    async def start(self) -> None:
        """Start the heartbeat emitter and monitor loops.

        This method is idempotent - calling it multiple times when already
        running will not create duplicate tasks.
        """
        if self._running:
            logger.debug("HeartbeatService already running")
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._emit_count = 0

        # Start emitter if configured
        if self.config.emit_heartbeat:
            self._emit_task = asyncio.create_task(self._emit_loop())
            logger.debug("Heartbeat emitter started")

        # Start monitor
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.debug("Heartbeat monitor started")

        self._running = True
        logger.info(f"HeartbeatService started ({self.config.heartbeat_hz}Hz)")

    async def stop(self) -> None:
        """Stop the heartbeat service and cleanup resources.

        This method is idempotent - calling it multiple times is safe.
        """
        if not self._running:
            logger.debug("HeartbeatService already stopped")
            return

        # Signal stop
        self._stop_event.set()
        self._running = False

        # Cancel emitter task
        if self._emit_task and not self._emit_task.done():
            self._emit_task.cancel()
            try:
                await self._emit_task
            except asyncio.CancelledError:
                pass
            self._emit_task = None

        # Cancel monitor task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("HeartbeatService stopped")

    def record_heartbeat(self, source: HeartbeatSource, timestamp: float) -> None:
        """Record a heartbeat from a source.

        Args:
            source: The source of the heartbeat
            timestamp: Unix timestamp when heartbeat was received
        """
        # Update source status
        if source in self._sources:
            status = self._sources[source]
            status.last_beat = timestamp
            status.missed_beats = 0
            status.total_beats += 1
            # State will be updated by monitor
        else:
            self._sources[source] = SourceStatus(
                last_beat=timestamp,
                state=HeartbeatState.HEALTHY,
                missed_beats=0,
                total_beats=1,
            )

        logger.debug(f"Heartbeat recorded from {source.value} at {timestamp}")

    def get_last_heartbeat(self, source: HeartbeatSource) -> Optional[float]:
        """Get the timestamp of the last heartbeat from a source.

        Args:
            source: The heartbeat source to check

        Returns:
            Unix timestamp of last heartbeat, or None if no heartbeats recorded
        """
        if source in self._sources:
            return self._sources[source].last_beat
        return None

    def is_source_healthy(self, source: HeartbeatSource) -> bool:
        """Check if a heartbeat source is within timeout.

        Args:
            source: The heartbeat source to check

        Returns:
            True if source has heartbeat within timeout, False otherwise
        """
        if source not in self._sources:
            return False

        status = self._sources[source]
        age = time.time() - status.last_beat

        return age < self.config.offboard_timeout_s

    def get_metrics(self) -> Dict[str, Any]:
        """Return performance statistics.

        Returns:
            Dictionary containing:
            - emit_count: Total number of heartbeats emitted
            - uptime_s: Service uptime in seconds
            - sources: Dict of source metrics (state, missed_beats, total_beats)
        """
        uptime = time.time() - self._start_time if self._start_time > 0 else 0

        sources_metrics = {}
        for source, status in self._sources.items():
            sources_metrics[source.value] = {
                "state": status.state.name,
                "missed_beats": status.missed_beats,
                "total_beats": status.total_beats,
                "last_beat_age_s": time.time() - status.last_beat,
            }

        return {
            "emit_count": self._emit_count,
            "uptime_s": uptime,
            "sources": sources_metrics,
            "config": {
                "heartbeat_hz": self.config.heartbeat_hz,
                "offboard_timeout_s": self.config.offboard_timeout_s,
                "warning_threshold_s": self.config.warning_threshold_s,
            },
        }

    async def _emit_loop(self) -> None:
        """Emit heartbeat at 20Hz (50ms intervals).

        This loop runs continuously until stop() is called. It maintains
        precise 50ms intervals using asyncio.sleep().
        """
        logger.debug(f"Starting emit loop at {self.config.heartbeat_hz}Hz")

        next_emit_time = time.time()

        while not self._stop_event.is_set():
            try:
                # Record emission time
                emit_time = time.time()
                self._emit_count += 1

                # Call heartbeat callback if set
                if self.on_heartbeat:
                    try:
                        await self.on_heartbeat(HeartbeatSource.OFFBOARD, emit_time)
                    except Exception as e:
                        logger.warning(f"Heartbeat callback error: {e}")

                # Calculate next emission time
                next_emit_time += self._interval_s

                # Sleep until next emission (with precision)
                sleep_time = next_emit_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    # We're behind schedule - emit immediately
                    logger.warning(f"Heartbeat emission behind schedule by {-sleep_time:.3f}s")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat emit loop error: {e}")
                # Don't let errors kill the loop
                await asyncio.sleep(self._interval_s)

        logger.debug("Emit loop stopped")

    async def _monitor_loop(self) -> None:
        """Monitor heartbeat sources for timeout.

        This loop checks all registered sources every 50ms and:
        1. Updates source state based on time since last beat
        2. Triggers warning callback when approaching timeout
        3. Triggers failsafe callback on timeout
        """
        logger.debug("Starting monitor loop")

        check_interval = min(self._interval_s, 0.05)  # Check at least every 50ms

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(check_interval)

                if self._stop_event.is_set():
                    break

                # Check all sources
                current_time = time.time()

                for source, status in list(self._sources.items()):
                    age = current_time - status.last_beat

                    # Update state based on age
                    new_state = status.state

                    if age >= self.config.offboard_timeout_s:
                        new_state = HeartbeatState.TIMEOUT
                        status.missed_beats = int(age / self._interval_s)

                        # Trigger failsafe (once per timeout)
                        if status.state != HeartbeatState.TIMEOUT:
                            logger.warning(
                                f"Heartbeat timeout for {source.value} "
                                f"({age:.3f}s > {self.config.offboard_timeout_s}s)"
                            )
                            if self.on_failsafe:
                                try:
                                    await self.on_failsafe(source)
                                except Exception as e:
                                    logger.warning(f"Failsafe callback error: {e}")

                    elif age >= self.config.warning_threshold_s:
                        # Trigger warning once when entering WARNING state
                        if status.state != HeartbeatState.WARNING:
                            logger.warning(
                                f"Heartbeat warning for {source.value} "
                                f"({age:.3f}s > {self.config.warning_threshold_s}s)"
                            )
                            if self.on_warning:
                                try:
                                    await self.on_warning(source, age)
                                except Exception as e:
                                    logger.warning(f"Warning callback error: {e}")

                        new_state = HeartbeatState.WARNING

                    else:
                        new_state = HeartbeatState.HEALTHY

                    status.state = new_state

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                # Continue running despite errors

        # Mark all sources as stopped
        for status in self._sources.values():
            status.state = HeartbeatState.STOPPED

        logger.debug("Monitor loop stopped")

    async def __aenter__(self) -> "HeartbeatService":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> None:
        """Async context manager exit - ensures stop."""
        await self.stop()
