"""Agent Liveness Monitoring Service.

This module provides heartbeat monitoring for tracking the health of
distributed system components (LLM, Guardian, Operator, etc.). It monitors
multiple heartbeat sources and triggers callbacks when sources become stale.

KEY CONCEPTS:
-------------
1. AGENT-LIVENESS ONLY: This service does NOT emit heartbeats to PX4.
   It only tracks heartbeats from external sources.

2. DYNAMIC SOURCES: Sources are added dynamically with configurable timeouts.
   Each source has its own timeout threshold.

3. STALE DETECTION: Sources become "stale" when their last heartbeat exceeds
   the configured timeout.

4. CALLBACK-DRIVEN: The monitor loop calls the provided on_stale callback
   when sources become stale, allowing the caller to take action.

USAGE:
------
    service = HeartbeatService()
    service.add_source("llm", timeout_s=2.0)
    service.add_source("guardian", timeout_s=1.0)

    async def on_stale(stale_sources: list[str]):
        logger.warning(f"Stale sources: {stale_sources}")

    # Start monitoring
    monitor_task = asyncio.create_task(
        service.monitor_loop(on_stale)
    )

    # Record heartbeats from components
    service.record_heartbeat("llm")
    service.record_heartbeat("guardian")

    # Check source health
    age = service.get_last_beat_age("llm")
    stale = service.stale_sources()

    # Cleanup
    monitor_task.cancel()
    await monitor_task
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HeartbeatState:
    """Enumeration of heartbeat connection states.

    Used to indicate the current health of a heartbeat source.
    """

    CONNECTED = "connected"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass
class SourceConfig:
    """Configuration for a heartbeat source.

    Attributes:
        name: Unique identifier for the source.
        timeout_s: Seconds without heartbeat before considered stale.
        last_beat: Unix timestamp of last heartbeat (0 if never).
    """

    name: str
    timeout_s: float
    last_beat: float = 0.0


@dataclass
class SourceStatus:
    """Status of a single heartbeat source.

    Provides detailed health information for a specific source.

    Attributes:
        name: Source identifier.
        state: Current connection state.
        last_beat: Timestamp of last heartbeat (0 if never).
        age_s: Seconds since last heartbeat.
        timeout_s: Configured timeout threshold.
        is_healthy: Whether source is within timeout.
    """

    name: str
    state: str
    last_beat: float = 0.0
    age_s: Optional[float] = None
    timeout_s: float = 2.0
    is_healthy: bool = True


class HeartbeatSource:
    """Enumeration of heartbeat source identifiers.

    Used to identify the origin of heartbeats in the monitoring system.
    """

    LLM = "llm"
    GUARDIAN = "guardian"
    OPERATOR = "operator"
    TELEMETRY = "telemetry"
    OFFBOARD = "offboard"
    MANUAL_CONTROL = "manual_control"


@dataclass
class HeartbeatConfig:
    """Configuration for HeartbeatService behavior.

    Used when creating a HeartbeatService for PX4 offboard mode support.

    Attributes:
        heartbeat_hz: Frequency of heartbeat emission (default: 20Hz for PX4).
        offboard_timeout_s: Seconds without heartbeat before offboard failsafe (default: 0.5s).
        warning_threshold_s: Seconds without heartbeat before warning (default: 0.3s).
        emit_heartbeat: Whether to emit heartbeats (vs just monitoring).
        check_interval_s: How often to check for stale sources (default: 0.05s).
    """

    heartbeat_hz: float = 20.0
    offboard_timeout_s: float = 0.5
    warning_threshold_s: float = 0.3
    emit_heartbeat: bool = True
    check_interval_s: float = 0.05


class HeartbeatService:
    """Agent-liveness monitoring service.

    Tracks heartbeats from multiple distributed sources and detects when
    sources become stale (no heartbeat within timeout).

    This service is designed for:
    - Monitoring LLM inference loop health
    - Monitoring Guardian process health
    - Monitoring Operator connection health
    - Any other distributed component health tracking

    Example:
        service = HeartbeatService()
        service.add_source("llm", timeout_s=2.0)
        service.add_source("guardian", timeout_s=1.0)

        async def on_stale(sources):
            print(f"Stale: {sources}")

        task = asyncio.create_task(service.monitor_loop(on_stale))

        # Components call this regularly
        service.record_heartbeat("llm")

        # Check health
        if service.stale_sources():
            print("Some sources are stale!")

        task.cancel()
    """

    def __init__(self, config: Optional[HeartbeatConfig] = None) -> None:
        """Initialize the heartbeat service with optional config.

        Args:
            config: Optional HeartbeatConfig for service behavior.
                   If not provided, uses default values.
        """
        self._config = config or HeartbeatConfig()
        self._sources: Dict[str, SourceConfig] = {}
        self._sources_lock = asyncio.Lock()
        self._running = False
        self._stop_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task[Any]] = None

    @property
    def config(self) -> HeartbeatConfig:
        """Get the heartbeat service configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Whether the monitor loop is running."""
        return self._running

    def add_source(self, name: str, timeout_s: float) -> None:
        """Register a new heartbeat source.

        Sources are tracked independently with their own timeout thresholds.

        Args:
            name: Unique identifier for this source.
            timeout_s: Seconds without heartbeat before considered stale.

        Example:
            service.add_source("llm", timeout_s=2.0)
            service.add_source("guardian", timeout_s=1.0)
        """
        if name in self._sources:
            logger.warning(f"Source '{name}' already exists, updating timeout")
            self._sources[name].timeout_s = timeout_s
        else:
            self._sources[name] = SourceConfig(
                name=name,
                timeout_s=timeout_s,
                last_beat=0.0,  # Never recorded
            )
            logger.debug(f"Added heartbeat source '{name}' with timeout {timeout_s}s")

    def record_heartbeat(self, name: str) -> None:
        """Record a heartbeat from a source.

        Updates the last_beat timestamp for the named source.
        Safe to call even if source not registered (will log warning).

        Args:
            name: Name of the source sending the heartbeat.

        Example:
            # In your LLM inference loop
            service.record_heartbeat("llm")

            # In your Guardian monitoring loop
            service.record_heartbeat("guardian")
        """
        timestamp = time.time()

        if name not in self._sources:
            logger.warning(
                f"Heartbeat from unknown source '{name}'. "
                f"Call add_source() first."
            )
            # Auto-add with default timeout
            self._sources[name] = SourceConfig(
                name=name,
                timeout_s=2.0,  # Default 2 second timeout
                last_beat=timestamp,
            )
        else:
            self._sources[name].last_beat = timestamp

        logger.debug(f"Heartbeat recorded from '{name}' at {timestamp}")

    def get_last_beat_age(self, name: str) -> Optional[float]:
        """Get seconds since last heartbeat from a source.

        Args:
            name: Name of the source to check.

        Returns:
            Seconds since last heartbeat, or None if source never recorded.
            Returns float('inf') if source doesn't exist.

        Example:
            age = service.get_last_beat_age("llm")
            if age is None:
                print("LLM has never sent a heartbeat")
            elif age > 2.0:
                print(f"LLM heartbeat is {age}s old")
        """
        if name not in self._sources:
            return None

        last_beat = self._sources[name].last_beat
        if last_beat == 0.0:
            return None  # Never recorded

        return time.time() - last_beat

    def stale_sources(self) -> List[str]:
        """Get list of sources that have exceeded their timeout.

        A source is stale if:
        - It has recorded at least one heartbeat (last_beat > 0)
        - Time since last heartbeat exceeds timeout_s

        Returns:
            List of source names that are stale.

        Example:
            stale = service.stale_sources()
            if "llm" in stale:
                print("LLM is unresponsive!")
        """
        now = time.time()
        stale: List[str] = []

        for name, config in self._sources.items():
            # Skip sources that have never recorded
            if config.last_beat == 0.0:
                continue

            age = now - config.last_beat
            if age > config.timeout_s:
                stale.append(name)

        return stale

    async def monitor_loop(
        self,
        on_stale: Callable[[List[str]], Awaitable[None]],
        check_interval_s: float = 0.05,
    ) -> None:
        """Continuously monitor sources and call on_stale when sources become stale.

        This loop runs until cancelled. It checks all sources at the specified
        interval and calls the on_stale callback with the list of stale sources.

        Args:
            on_stale: Async callback called with list of stale source names.
                     Called whenever sources transition from healthy to stale.
            check_interval_s: How often to check sources (default 50ms).

        Example:
            async def handle_stale(sources):
                logger.warning(f"Stale sources: {sources}")
                # Take action - trigger failsafe, alert operator, etc.

            task = asyncio.create_task(
                service.monitor_loop(handle_stale)
            )

            # Later...
            task.cancel()
            await task

        Note:
            The callback is called on state transitions (edge-triggered),
            not continuously while stale. This prevents callback spam.
        """
        self._running = True
        self._stop_event.clear()

        # Track which sources were stale on last check (for edge detection)
        previously_stale: set = set()

        logger.info("HeartbeatService monitor loop started")

        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.sleep(check_interval_s)

                    if self._stop_event.is_set():
                        break

                    current_stale = set(self.stale_sources())

                    # Find newly stale sources (edge detection)
                    newly_stale = current_stale - previously_stale

                    if newly_stale:
                        stale_list = list(newly_stale)
                        logger.warning(f"Sources became stale: {stale_list}")

                        try:
                            await on_stale(stale_list)
                        except Exception as e:
                            logger.error(f"on_stale callback error: {e}")

                    previously_stale = current_stale

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Monitor loop error: {e}")

        finally:
            self._running = False
            logger.info("HeartbeatService monitor loop stopped")

    def stop(self) -> None:
        """Signal the monitor loop to stop.

        Sets the stop event, which causes monitor_loop to exit on next check.
        """
        self._stop_event.set()

    async def start(self) -> None:
        """Start the heartbeat service.

        Begins monitoring sources. This method is idempotent.
        """
        if self._running:
            logger.debug("HeartbeatService already running")
            return

        logger.info("HeartbeatService started")

        # Start the monitor loop as a background task
        async def _default_on_stale(sources: List[str]) -> None:
            logger.warning(f"Heartbeat sources became stale: {sources}")

        self._monitor_task = asyncio.create_task(
            self.monitor_loop(_default_on_stale, check_interval_s=self._config.check_interval_s)
        )

    async def stop_async(self) -> None:
        """Async stop - signals stop and waits for monitor to exit."""
        self._stop_event.set()

        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
            except asyncio.TimeoutError:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("HeartbeatService stopped")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for all sources.

        Returns:
            Dict with source metrics:
            - sources: Dict of source_name -> {age, timeout, last_beat}
            - stale_count: Number of currently stale sources

        Example:
            metrics = service.get_metrics()
            print(f"LLM age: {metrics['sources']['llm']['age']}s")
        """
        now = time.time()

        sources_metrics = {}
        for name, config in self._sources.items():
            age = None
            if config.last_beat > 0:
                age = now - config.last_beat

            sources_metrics[name] = {
                "age": age,
                "timeout_s": config.timeout_s,
                "last_beat": config.last_beat,
                "is_stale": age is not None and age > config.timeout_s,
            }

        return {
            "sources": sources_metrics,
            "stale_count": len(self.stale_sources()),
        }

    async def __aenter__(self) -> "HeartbeatService":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - signals stop."""
        self.stop()
