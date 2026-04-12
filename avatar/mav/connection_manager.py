"""Singleton ConnectionManager for MAVSDK drone connections.

This module provides a singleton connection manager that eliminates
per-command connection latency by maintaining a persistent connection
to the drone.

Key features:
- Singleton pattern: One connection across all imports
- Fast access: <100ms for get_drone() after initial connect
- Auto-reconnect: Automatically recovers from connection loss
- Health monitoring: Background task tracks connection health
- Thread-safe: asyncio.Lock for concurrent access

Example:
    cm = ConnectionManager()
    await cm.connect("udp://:14540")

    # Fast access after first connection
    drone = await cm.get_drone()  # <100ms

    # Use drone for MAVSDK operations
    await drone.action.arm()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from unittest.mock import MagicMock

try:
    from mavsdk import System
except ImportError:
    # Fallback for testing without mavsdk installed
    class System:  # type: ignore
        """Mock System class for testing."""

        def __init__(self) -> None:
            self.core = MagicMock()
            self.telemetry = MagicMock()

        async def connect(self, system_address: str) -> None:
            pass

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state machine states."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DEGRADED = auto()
    RECONNECTING = auto()
    ERROR = auto()


@dataclass
class ConnectionHealth:
    """Connection health metrics."""

    is_healthy: bool = False
    last_heartbeat: float = field(default_factory=lambda: 0.0)
    gps_lock: bool = False
    home_position_set: bool = False
    error_count: int = 0
    last_error: Optional[str] = None


class ConnectionManager:
    """Singleton connection manager for MAVSDK drone connections.

    This class ensures only one connection to the drone exists across
    the entire application, eliminating 2-5s per-command latency.

    Usage:
        cm = ConnectionManager()
        await cm.connect("udp://:14540")
        drone = await cm.get_drone()  # Fast access
    """

    _instance: Optional["ConnectionManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    # Type annotations for instance variables set in __new__ and __init__
    _initialized: bool
    _drone: Optional[System]
    _state: ConnectionState
    _health: ConnectionHealth
    _system_address: str
    _health_check_interval_s: float
    _reconnect_delay_s: float
    _max_reconnect_attempts: int
    _health_task: Optional[asyncio.Task[Any]]
    _stop_health_monitor: asyncio.Event
    _connection_lock: asyncio.Lock
    _connecting_event: Optional[asyncio.Event]

    def __new__(cls) -> "ConnectionManager":
        """Enforce singleton pattern.

        Returns:
            The singleton ConnectionManager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the connection manager (only runs once due to singleton)."""
        if self._initialized:
            return

        self._drone: Optional[System] = None
        self._state = ConnectionState.DISCONNECTED
        self._health = ConnectionHealth()
        self._system_address: str = "udp://:14540"
        self._health_check_interval_s: float = 1.0
        self._reconnect_delay_s: float = 2.0
        self._max_reconnect_attempts: int = 5
        self._health_task: Optional[asyncio.Task[Any]] = None
        self._stop_health_monitor = asyncio.Event()
        self._connection_lock = asyncio.Lock()
        self._connecting_event: Optional[asyncio.Event] = None

        self._initialized = True
        logger.debug("ConnectionManager initialized")

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def health(self) -> ConnectionHealth:
        """Current connection health."""
        return self._health

    async def connect(
        self,
        system_address: str = "udp://:14540",
        max_retries: int = 3,
        retry_delay_s: float = 1.0
    ) -> bool:
        """Connect to the drone with retry logic.

        Args:
            system_address: MAVSDK system address (default: udp://:14540 for SITL)
            max_retries: Maximum number of connection attempts
            retry_delay_s: Delay between retry attempts in seconds

        Returns:
            True if connection successful, False otherwise
        """
        async with self._connection_lock:
            # If already connecting, wait for it to complete
            if self._state == ConnectionState.CONNECTING and self._connecting_event:
                logger.debug("Connection already in progress, waiting...")
                await self._connecting_event.wait()
                # State may have changed after waiting, so check again
                return self._state == ConnectionState.CONNECTED  # type: ignore[comparison-overlap]

            # If already connected, return True
            if self._state == ConnectionState.CONNECTED and self._drone is not None:
                logger.debug("Already connected")
                return True

            # Start connecting
            self._state = ConnectionState.CONNECTING
            self._system_address = system_address
            self._connecting_event = asyncio.Event()

        # Perform connection outside lock to allow concurrent get_drone calls
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Connection attempt {attempt}/{max_retries} to {system_address}"
                )

                drone = await self._do_connect(system_address)

                if drone:
                    async with self._connection_lock:
                        self._drone = drone
                        self._state = ConnectionState.CONNECTED
                        self._health.is_healthy = True
                        self._health.error_count = 0
                        self._health.last_error = None

                    # Start health monitoring
                    self._start_health_monitor()

                    # Signal completion
                    if self._connecting_event:
                        self._connecting_event.set()

                    logger.info("Connected to drone successfully")
                    return True

            except Exception as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                self._record_error(str(e))

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay_s)

        # Connection failed
        async with self._connection_lock:
            self._state = ConnectionState.ERROR
            if self._connecting_event:
                self._connecting_event.set()

        logger.error("Failed to connect after all retries")
        return False

    async def _do_connect(self, system_address: str) -> Optional[System]:
        """Perform the actual MAVSDK connection.

        Args:
            system_address: MAVSDK system address

        Returns:
            Connected System instance or None if connection failed
        """
        drone = System()
        await drone.connect(system_address=system_address)

        # Wait for connection confirmation
        async for state in drone.core.connection_state():
            if state.is_connected:
                return drone
            break  # Only check first state

        return None

    async def disconnect(self) -> None:
        """Disconnect from the drone and cleanup resources."""
        async with self._connection_lock:
            logger.info("Disconnecting from drone")

            # Stop health monitoring
            self._stop_health_monitor.set()
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass

            # Reset state
            self._drone = None
            self._state = ConnectionState.DISCONNECTED
            self._health = ConnectionHealth()
            self._stop_health_monitor.clear()
            self._connecting_event = None

            logger.info("Disconnected from drone")

    async def get_drone(self) -> Optional[System]:
        """Get the drone instance (fast, non-blocking).

        Returns:
            System instance if connected, None otherwise.
            This is the fast path - should complete in <100ms after first connect.
        """
        # Fast path - just return the drone if connected
        if self._state == ConnectionState.CONNECTED and self._drone is not None:
            return self._drone

        # If not connected, try to reconnect
        if self._state in (ConnectionState.DISCONNECTED, ConnectionState.ERROR):
            logger.debug("Not connected, attempting auto-reconnect")
            success = await self.connect(self._system_address)
            if success:
                return self._drone

        return None

    async def ensure_connected(self) -> System:
        """Get drone or raise ConnectionError.

        Returns:
            System instance if connected

        Raises:
            ConnectionError: If not connected and auto-reconnect failed
        """
        drone = await self.get_drone()
        if drone is None:
            raise ConnectionError(
                f"Not connected to drone (state: {self._state.name})"
            )
        return drone

    def _start_health_monitor(self) -> None:
        """Start the background health monitoring task."""
        if self._health_task is None or self._health_task.done():
            self._stop_health_monitor.clear()
            self._health_task = asyncio.create_task(self._health_monitor())
            logger.debug("Health monitoring started")

    async def _health_monitor(self) -> None:
        """Background task to monitor connection health.

        Monitors:
        - Heartbeat from drone
        - GPS lock status
        - Home position status
        - Overall health from telemetry
        """
        logger.debug("Health monitor running")

        while not self._stop_health_monitor.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_health_monitor.wait(),
                    timeout=self._health_check_interval_s
                )
                break  # Stop requested
            except asyncio.TimeoutError:
                pass  # Continue with health check

            if self._drone is None or self._state != ConnectionState.CONNECTED:
                continue

            try:
                # Check health via telemetry
                healthy = await self._check_health()

                if not healthy and self._state == ConnectionState.CONNECTED:
                    logger.warning("Health check failed, marking degraded")
                    self._state = ConnectionState.DEGRADED

                    # Trigger auto-reconnect
                    asyncio.create_task(self._auto_reconnect())

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                self._record_error(str(e))

        logger.debug("Health monitor stopped")

    async def _check_health(self) -> bool:
        """Check drone health via telemetry.

        Returns:
            True if healthy, False otherwise
        """
        if self._drone is None:
            return False

        try:
            # Check health from telemetry (one-shot)
            async for health in self._drone.telemetry.health():
                self._health.is_healthy = (
                    health.is_global_position_ok and health.is_home_position_ok
                )
                self._health.gps_lock = health.is_global_position_ok
                self._health.home_position_set = health.is_home_position_ok
                self._health.last_heartbeat = asyncio.get_event_loop().time()
                return self._health.is_healthy

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

        return False

    async def _auto_reconnect(self) -> None:
        """Attempt to auto-reconnect when connection is lost."""
        if self._state == ConnectionState.RECONNECTING:
            return  # Already reconnecting

        self._state = ConnectionState.RECONNECTING
        logger.info("Starting auto-reconnect...")

        for attempt in range(1, self._max_reconnect_attempts + 1):
            try:
                logger.debug(f"Reconnect attempt {attempt}/{self._max_reconnect_attempts}")

                drone = await self._do_connect(self._system_address)

                if drone:
                    async with self._connection_lock:
                        self._drone = drone
                        self._state = ConnectionState.CONNECTED
                        self._health.is_healthy = True

                    logger.info("Auto-reconnect successful")
                    return

            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt} failed: {e}")
                self._record_error(str(e))

            await asyncio.sleep(self._reconnect_delay_s)

        # Reconnect failed
        async with self._connection_lock:
            self._state = ConnectionState.ERROR

        logger.error("Auto-reconnect failed after all attempts")

    def _update_health(
        self,
        is_healthy: bool,
        gps_lock: bool = False,
        home_position_set: bool = False
    ) -> None:
        """Update health metrics (for testing)."""
        self._health.is_healthy = is_healthy
        self._health.gps_lock = gps_lock
        self._health.home_position_set = home_position_set
        self._health.last_heartbeat = asyncio.get_event_loop().time()

    def _record_error(self, error_message: str) -> None:
        """Record an error in health metrics."""
        self._health.error_count += 1
        self._health.last_error = error_message

    async def __aenter__(self) -> "ConnectionManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures disconnect."""
        await self.disconnect()
