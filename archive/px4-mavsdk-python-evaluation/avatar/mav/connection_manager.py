"""
Connection Manager for MAVSDK Drone Communication

================================================================================
WHAT THIS MODULE DOES
================================================================================

This module manages the connection between Python code and a PX4 drone using MAVSDK.
Think of it as a 'phone line manager' that:

1. Maintains a single, persistent connection to the drone (instead of reconnecting
   for every command, which would be slow)
2. Automatically reconnects if the connection drops
3. Monitors the drone's health (GPS lock, home position, etc.)
4. Provides fast access to the drone object for sending commands

================================================================================
KEY CONCEPTS FOR BEGINNERS
================================================================================

- MAVSDK: A library that lets Python talk to PX4 drones using the MAVLink protocol
- SITL: Software-In-The-Loop simulation (flying a virtual drone on your computer)
- PX4: The flight control software that runs on the drone
- Connection String: Where to find the drone (e.g., "udp://:14540" for local simulation)
- Async/Await: Python pattern for handling operations that take time (like connecting)

================================================================================
SINGLETON PATTERN (Why Only One ConnectionManager?)
================================================================================

This module uses the 'Singleton' design pattern - only ONE instance of
ConnectionManager can exist. This ensures:

1. All parts of your code use the same drone connection
2. No conflicting commands from multiple connections
3. Consistent state tracking (connected/disconnected)

Example usage:
    # Get the singleton instance
    cm = ConnectionManager()
    await cm.connect("udp://:14540")

    # Anywhere else in your code, same instance
    cm2 = ConnectionManager()  # Same object as cm!
    drone = await cm2.get_drone()  # Fast access

================================================================================
CONNECTION STATES
================================================================================

The connection goes through different states:

    DISCONNECTED  →  CONNECTING  →  CONNECTED  →  DEGRADED  →  RECONNECTING
          ↑_________________________________________________________↓

- DISCONNECTED: No connection yet, or explicitly disconnected
- CONNECTING: Currently trying to establish connection
- CONNECTED: Successfully connected and ready
- DEGRADED: Connection lost, but attempting recovery
- RECONNECTING: Actively trying to reconnect
- ERROR: Connection failed after all retry attempts

================================================================================
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
# asyncio: Python's library for writing concurrent code using async/await syntax
#          Essential for handling multiple drone operations without blocking
import asyncio

# logging: For recording what happens (connection attempts, errors, etc.)
import logging

# dataclasses: Convenient way to create classes that mainly store data
#              ConnectionHealth uses this to track health metrics
from dataclasses import dataclass, field

# enum: For creating named constants (like ConnectionState.DISCONNECTED)
from enum import Enum, auto

# typing: Type hints that help with code clarity and IDE autocomplete
from typing import Any, Optional

# unittest.mock: Used here to create a mock drone when MAVSDK isn't installed
#                This allows testing the connection logic without a real drone
from unittest.mock import MagicMock

# ==============================================================================
# MAVSDK IMPORT (With Fallback)
# ==============================================================================
# We try to import the real MAVSDK System class, but if it's not installed
# (like in a test environment), we create a mock version that has the same
# interface but doesn't actually connect to anything.

try:
    # The real MAVSDK System class - this is what talks to actual drones
    from mavsdk import System
except ImportError:
    # This runs when MAVSDK is not installed - creates a fake System class
    # that lets us test the connection logic without the real library
    class System:  # type: ignore
        """Mock System class for testing without MAVSDK installed.

        This mock has the same methods as the real System but they do nothing.
        It allows the connection manager code to be imported and tested even
        when MAVSDK is not available.
        """

        def __init__(self) -> None:
            # MagicMock creates fake objects that accept any method call
            self.core = MagicMock()
            self.telemetry = MagicMock()

        async def connect(self, system_address: str) -> None:
            # Mock connect method - does nothing but satisfies the interface
            pass

# Create a logger for this module - logs will show as "connection_manager: message"
logger = logging.getLogger(__name__)


# ==============================================================================
# CONNECTION STATE ENUM
# ==============================================================================
# This enum defines all possible states the connection can be in.
# Using an enum (instead of strings like "disconnected") ensures:
# 1. No typos - you can't misspell an enum value
# 2. IDE autocomplete - your editor suggests available states
# 3. Type safety - the code knows what states are valid

class ConnectionState(Enum):
    """Connection state machine states.

    These represent the lifecycle of a drone connection from initial setup
    through connection, operation, potential failures, and reconnection.

    Attributes:
        DISCONNECTED: No active connection (initial state or after disconnect)
        CONNECTING: Currently attempting to establish connection
        CONNECTED: Successfully connected and operational
        DEGRADED: Connection unstable or partially lost
        RECONNECTING: Attempting to recover a lost connection
        ERROR: Permanent connection failure after exhausting retries
    """

    DISCONNECTED = auto()    # Initial state, no connection attempted yet
    CONNECTING = auto()      # Actively trying to connect right now
    CONNECTED = auto()       # Successfully connected, ready for commands
    DEGRADED = auto()        # Connection weak - may have lost telemetry
    RECONNECTING = auto()    # Lost connection, trying to get it back
    ERROR = auto()           # Failed to connect after all retry attempts


# ==============================================================================
# CONNECTION HEALTH DATACLASS
# ==============================================================================
# A dataclass is a simple class that mainly stores data with minimal boilerplate.
# This class tracks the "health" of the drone connection - not just whether
# we're connected, but whether the drone is functioning properly.

@dataclass
class ConnectionHealth:
    """Connection health metrics.

    This dataclass tracks various indicators of connection and drone health.
    It's updated continuously by the health monitoring background task.

    Attributes:
        is_healthy: True if all health checks pass (GPS lock, home position, etc.)
        last_heartbeat: Timestamp (in seconds) of the last successful communication
        gps_lock: True if the drone has a GPS fix (required for autonomous flight)
        home_position_set: True if the drone knows where "home" is (for RTL)
        error_count: Number of errors encountered since connection
        last_error: The most recent error message, if any

    Note:
        'field(default_factory=...)' creates a new value for each instance
        rather than sharing one value across all instances.
    """

    is_healthy: bool = False           # Overall health status
    last_heartbeat: float = field(      # When we last heard from the drone
        default_factory=lambda: 0.0
    )
    gps_lock: bool = False              # Can the drone see GPS satellites?
    home_position_set: bool = False     # Does the drone know where home is?
    error_count: int = 0                # How many errors have occurred?
    last_error: Optional[str] = None    # What was the last error message?


# ==============================================================================
# CONNECTION MANAGER CLASS (The Main Class)
# ==============================================================================
# This is the heart of the module. It manages a single persistent connection
# to the drone using the singleton pattern.

class ConnectionManager:
    """Singleton connection manager for MAVSDK drone connections.

    =============================================================================
    WHAT THIS CLASS DOES
    =============================================================================

    This class ensures only ONE connection to the drone exists across the entire
    application. This is critical because:

    1. MAVSDK connections take 2-5 seconds to establish - we don't want to
       wait that long for every single command
    2. Multiple connections can confuse the drone and cause conflicts
    3. We need consistent tracking of connection state and health

    =============================================================================
    SINGLETON PATTERN EXPLAINED
    =============================================================================

    The singleton pattern ensures only one instance exists. Here's how it works:

        First call to ConnectionManager():
            1. __new__ checks: "Is _instance None?"
            2. Yes! Creates new instance, stores in _instance
            3. __init__ runs and sets up the object

        Second call to ConnectionManager():
            1. __new__ checks: "Is _instance None?"
            2. No! Returns the existing instance
            3. __init__ sees _initialized=True and returns immediately

    Result: cm1 and cm2 point to the SAME object!

    =============================================================================
    USAGE EXAMPLES
    =============================================================================

    Basic connection:
        cm = ConnectionManager()
        success = await cm.connect("udp://:14540")
        if success:
            print("Connected to drone!")

    Fast drone access (after initial connect):
        drone = await cm.get_drone()  # Returns in <100ms
        await drone.action.arm()      # Send command immediately

    Check connection health:
        health = cm.health
        print(f"GPS lock: {health.gps_lock}")
        print(f"Healthy: {health.is_healthy}")

    Context manager (auto-disconnect when done):
        async with ConnectionManager() as cm:
            await cm.connect("udp://:14540")
            drone = await cm.get_drone()
            # ... do work ...
        # Automatically disconnected here!

    =============================================================================
    ATTRIBUTES
    =============================================================================

    Class Attributes (shared across all instances - though there's only one):
        _instance: The singleton instance (None until first creation)
        _lock: asyncio.Lock to prevent race conditions during singleton creation

    Instance Attributes:
        _initialized: True after __init__ runs (prevents re-initialization)
        _drone: The actual MAVSDK System instance (None when disconnected)
        _state: Current ConnectionState (DISCONNECTED, CONNECTED, etc.)
        _health: ConnectionHealth object with current health metrics
        _system_address: The connection string (e.g., "udp://:14540")
        _health_check_interval_s: How often to check health (seconds)
        _reconnect_delay_s: How long to wait between reconnection attempts
        _max_reconnect_attempts: Maximum retries before giving up
        _health_task: The background task that monitors health
        _stop_health_monitor: asyncio.Event to signal health monitor to stop
        _connection_lock: Lock to prevent concurrent connect/disconnect calls
        _connecting_event: Event to signal when connection attempt completes
    """

    # ==========================================================================
    # CLASS-LEVEL ATTRIBUTES (Shared by all instances - part of singleton)
    # ==========================================================================

    _instance: Optional["ConnectionManager"] = None  # The one true instance
    _lock: asyncio.Lock = asyncio.Lock()            # Lock for thread-safe creation

    # ==========================================================================
    # TYPE ANNOTATIONS
    # ==========================================================================
    # These tell Python (and your IDE) what types these instance variables will be.
    # They're set in __new__ and __init__ but declared here for clarity.

    _initialized: bool                      # Has __init__ already run?
    _drone: Optional[System]               # The actual drone connection
    _state: ConnectionState                 # Current connection state
    _health: ConnectionHealth               # Health metrics object
    _system_address: str                    # Where to find the drone
    _health_check_interval_s: float        # Seconds between health checks
    _reconnect_delay_s: float              # Seconds to wait before retry
    _max_reconnect_attempts: int            # How many times to retry
    _health_task: Optional[asyncio.Task[Any]]  # Background health monitor task
    _stop_health_monitor: asyncio.Event    # Signal to stop health monitoring
    _connection_lock: asyncio.Lock          # Prevents concurrent connections
    _connecting_event: Optional[asyncio.Event]  # Signals when connect() finishes

    # ==========================================================================
    # SINGLETON ENFORCEMENT
    # ==========================================================================

    def __new__(cls) -> "ConnectionManager":
        """Create or return the singleton instance.

        This is called BEFORE __init__ and controls instance creation.
        It's what enforces the singleton pattern - only one instance ever exists.

        How it works:
            1. Check if we already have an instance stored in _instance
            2. If not, create one using the parent class's __new__ method
            3. Mark it as not-yet-initialized so __init__ will run
            4. Return the instance (either new or existing)

        Returns:
            The singleton ConnectionManager instance (always the same object)

        Example:
            cm1 = ConnectionManager()
            cm2 = ConnectionManager()
            assert cm1 is cm2  # Same object!
        """
        # Check if we already created an instance
        if cls._instance is None:
            # No instance exists yet - create one
            # super().__new__(cls) creates the actual Python object
            cls._instance = super().__new__(cls)
            # Mark as not initialized so __init__ runs
            cls._instance._initialized = False

        # Return the singleton instance (new or existing)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the connection manager.

        WARNING: Due to the singleton pattern, this only runs ONCE even if you
        call ConnectionManager() multiple times. The _initialized flag prevents
        re-initialization.

        This sets up:
        - The drone connection object (initially None)
        - Connection state (starts as DISCONNECTED)
        - Health tracking object
        - Configuration parameters (connection address, retry settings)
        - Synchronization primitives (locks and events for async safety)
        """
        # If already initialized, do nothing (singleton pattern safety)
        if self._initialized:
            return

        # ----------------------------------------------------------------------
        # CORE CONNECTION STATE
        # ----------------------------------------------------------------------
        # These track the actual drone connection and its status

        self._drone: Optional[System] = None           # No drone connected yet
        self._state = ConnectionState.DISCONNECTED      # Start disconnected
        self._health = ConnectionHealth()               # Fresh health metrics

        # ----------------------------------------------------------------------
        # CONFIGURATION PARAMETERS
        # ----------------------------------------------------------------------
        # These control connection behavior and can be adjusted as needed

        # Connection string: where to find the drone
        # "udp://:14540" means listen on UDP port 14540 (standard SITL port)
        self._system_address: str = "udp://:14540"

        # Health check interval: how often to verify the connection (in seconds)
        # 1.0 means check once per second
        self._health_check_interval_s: float = 1.0

        # Reconnect delay: how long to wait between reconnection attempts
        # 2.0 seconds gives the drone time to recover between attempts
        self._reconnect_delay_s: float = 2.0

        # Maximum reconnection attempts before giving up
        # 5 attempts with 2-second delays = up to 10 seconds of retrying
        self._max_reconnect_attempts: int = 5

        # ----------------------------------------------------------------------
        # BACKGROUND TASK MANAGEMENT
        # ----------------------------------------------------------------------
        # These manage the health monitoring background task

        # The asyncio.Task running the health monitor (None when not running)
        self._health_task: Optional[asyncio.Task[Any]] = None

        # An asyncio.Event used to signal the health monitor to stop
        # Calling .set() on this event tells the monitor to exit its loop
        self._stop_health_monitor = asyncio.Event()

        # ----------------------------------------------------------------------
        # SYNCHRONIZATION PRIMITIVES
        # ----------------------------------------------------------------------
        # These prevent race conditions in async code

        # Lock ensures only one connect/disconnect happens at a time
        # This prevents two parts of your code from connecting simultaneously
        self._connection_lock = asyncio.Lock()

        # Event used to signal when a connection attempt completes
        # This allows other code waiting to connect to be notified
        self._connecting_event: Optional[asyncio.Event] = None

        # ----------------------------------------------------------------------
        # MARK AS INITIALIZED
        # ----------------------------------------------------------------------
        self._initialized = True
        logger.debug("ConnectionManager initialized")

    # ==========================================================================
    # PROPERTIES (Read-only access to internal state)
    # ==========================================================================

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state.

        Returns:
            The current ConnectionState (DISCONNECTED, CONNECTING, CONNECTED, etc.)

        Example:
            cm = ConnectionManager()
            if cm.state == ConnectionState.CONNECTED:
                print("Ready to fly!")
        """
        return self._state

    @property
    def health(self) -> ConnectionHealth:
        """Get the current connection health metrics.

        Returns:
            ConnectionHealth object with current health information including:
            - is_healthy: Overall health status
            - gps_lock: Whether GPS is working
            - home_position_set: Whether home position is known
            - last_heartbeat: When we last heard from the drone
            - error_count: Number of errors encountered

        Example:
            cm = ConnectionManager()
            health = cm.health
            if not health.gps_lock:
                print("Warning: No GPS lock!")
        """
        return self._health

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    async def connect(
        self,
        system_address: str = "udp://:14540",
        max_retries: int = 3,
        retry_delay_s: float = 1.0
    ) -> bool:
        """Connect to the drone with automatic retry logic.

        This is the main method to establish a connection to the drone.
        It handles:
        - Multiple connection attempts with delays between them
        - Concurrency safety (only one connect runs at a time)
        - Detection of already-in-progress connections
        - State updates and health monitoring startup

        Args:
            system_address: MAVSDK connection string (default: "udp://:14540")
                           - "udp://:14540" for local SITL simulation
                           - "serial:///dev/ttyUSB0:57600" for USB telemetry radio
                           - "tcp://192.168.1.10:5760" for WiFi connection
            max_retries: How many times to try connecting before giving up (default: 3)
            retry_delay_s: Seconds to wait between retry attempts (default: 1.0)

        Returns:
            True if connection successful, False if all retries failed

        Raises:
            No exceptions raised directly, but logs warnings/errors on failure

        Example:
            cm = ConnectionManager()
            success = await cm.connect("udp://:14540")
            if success:
                print("Connected!")
            else:
                print("Failed to connect")

        Note:
            If another connect() call is already in progress, this method will
            wait for it to complete and return its result instead of starting
            a new connection attempt.
        """
        # ----------------------------------------------------------------------
        # PHASE 1: CHECK FOR EXISTING CONNECTION ATTEMPTS
        # ----------------------------------------------------------------------
        # Acquire the connection lock to ensure thread safety
        # This prevents multiple connect() calls from running simultaneously
        async with self._connection_lock:

            # Check if we're already trying to connect from another call
            if self._state == ConnectionState.CONNECTING and self._connecting_event:
                logger.debug("Connection already in progress, waiting...")

                # Wait for the existing connection attempt to complete
                # This releases the lock while waiting so other code can run
                await self._connecting_event.wait()

                # After waiting, check if the other attempt succeeded
                # We return its result instead of starting a new attempt
                return self._state == ConnectionState.CONNECTED  # type: ignore[comparison-overlap]

            # Check if we're already connected - no need to reconnect
            if self._state == ConnectionState.CONNECTED and self._drone is not None:
                logger.debug("Already connected")
                return True

            # ------------------------------------------------------------------
            # PHASE 2: START NEW CONNECTION ATTEMPT
            # ------------------------------------------------------------------
            # Set state to CONNECTING so other code knows what's happening
            self._state = ConnectionState.CONNECTING
            # Remember the address we're connecting to
            self._system_address = system_address
            # Create an event to signal when this connection attempt finishes
            # Other code can wait on this event
            self._connecting_event = asyncio.Event()

        # ----------------------------------------------------------------------
        # PHASE 3: ATTEMPT CONNECTION (Outside lock to allow concurrent get_drone)
        # ----------------------------------------------------------------------
        # We release the lock here so other code can call get_drone() while we
        # connect. This prevents blocking the entire application during the
        # 2-5 second connection process.

        # Try connecting up to max_retries times
        for attempt in range(1, max_retries + 1):
            try:
                # Log the attempt
                logger.info(
                    f"Connection attempt {attempt}/{max_retries} to {system_address}"
                )

                # Actually try to connect (this takes 2-5 seconds)
                drone = await self._do_connect(system_address)

                # Check if connection succeeded
                if drone:
                    # ----------------------------------------------------------
                    # SUCCESS! Update state and start monitoring
                    # ----------------------------------------------------------
                    async with self._connection_lock:
                        # Store the connected drone object
                        self._drone = drone
                        # Update state to CONNECTED
                        self._state = ConnectionState.CONNECTED
                        # Reset health metrics
                        self._health.is_healthy = True
                        self._health.error_count = 0
                        self._health.last_error = None

                    # Start the background health monitoring task
                    # This runs independently and watches for connection issues
                    self._start_health_monitor()

                    # Signal that connection is complete
                    # Any code waiting on _connecting_event will wake up
                    if self._connecting_event:
                        self._connecting_event.set()

                    logger.info("Connected to drone successfully")
                    return True

            except Exception as e:
                # Log the failure but don't give up yet
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                # Record the error in health metrics
                self._record_error(str(e))

                # If we have more retries left, wait before trying again
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay_s)

        # ----------------------------------------------------------------------
        # PHASE 4: ALL RETRIES FAILED
        # ----------------------------------------------------------------------
        async with self._connection_lock:
            # Set state to ERROR so other code knows connection failed
            self._state = ConnectionState.ERROR
            # Signal completion (with failure status)
            if self._connecting_event:
                self._connecting_event.set()

        logger.error("Failed to connect after all retries")
        return False

    async def _do_connect(self, system_address: str) -> Optional[System]:
        """Perform the actual MAVSDK connection attempt.

        This internal method does the low-level work of connecting to the drone.
        It's separated from connect() so that connect() can handle retries and
        state management while this method focuses just on the connection.

        Args:
            system_address: MAVSDK connection string (e.g., "udp://:14540")

        Returns:
            Connected System instance if successful, None if connection failed

        Note:
            This method waits for the connection_state to report is_connected=True
            before returning, ensuring the connection is actually established.
        """
        # Create a new MAVSDK System instance
        # Think of this as creating a new "phone" to call the drone
        drone = System()

        # Initiate the connection (non-blocking - returns immediately)
        await drone.connect(system_address=system_address)

        # Wait for confirmation that we're actually connected
        # MAVSDK provides an async iterator that yields connection state changes
        async for state in drone.core.connection_state():
            # Check if this state indicates we're connected
            if state.is_connected:
                # Success! Return the connected drone object
                return drone
            # We only check the first state update, then break
            # If not connected on first update, something went wrong
            break

        # If we get here, the first state update didn't show connected
        # This means the connection attempt failed
        return None

    async def disconnect(self) -> None:
        """Disconnect from the drone and clean up all resources.

        This method:
        1. Stops the health monitoring background task
        2. Clears the drone reference
        3. Resets state to DISCONNECTED
        4. Clears health metrics

        It's safe to call even if not connected - it will simply do nothing
        in that case.

        Example:
            cm = ConnectionManager()
            await cm.connect("udp://:14540")
            # ... do work ...
            await cm.disconnect()  # Clean up

        Note:
            When using the context manager (async with), disconnect is called
            automatically when exiting the context.
        """
        # Acquire lock to ensure thread safety
        async with self._connection_lock:
            logger.info("Disconnecting from drone")

            # ------------------------------------------------------------------
            # STEP 1: STOP HEALTH MONITORING
            # ------------------------------------------------------------------
            # Signal the health monitor to stop
            self._stop_health_monitor.set()

            # If there's a health task running, cancel and wait for it
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()
                try:
                    # Wait for the task to acknowledge cancellation
                    await self._health_task
                except asyncio.CancelledError:
                    # This is expected - the task raises this when cancelled
                    pass

            # ------------------------------------------------------------------
            # STEP 2: RESET ALL STATE
            # ------------------------------------------------------------------
            # Clear the drone reference (allows garbage collection)
            self._drone = None
            # Reset to initial disconnected state
            self._state = ConnectionState.DISCONNECTED
            # Create fresh health metrics
            self._health = ConnectionHealth()
            # Clear the stop event (for next time)
            self._stop_health_monitor.clear()
            # Clear the connecting event
            self._connecting_event = None

            logger.info("Disconnected from drone")

    async def get_drone(self) -> Optional[System]:
        """Get the drone instance (fast, non-blocking access).

        This is the FAST way to access the drone after the initial connection.
        Unlike connect() which takes 2-5 seconds, get_drone() returns in <100ms
        because it just returns the cached drone object.

        If not currently connected, it will attempt auto-reconnect.

        Returns:
            System instance if connected (or reconnection succeeded),
            None if not connected and auto-reconnect failed

        Performance:
            - <100ms when already connected (just returns cached object)
            - 2-5s+ when auto-reconnect is needed

        Example:
            cm = ConnectionManager()
            await cm.connect("udp://:14540")  # Slow: 2-5 seconds

            # Later, in other parts of your code:
            drone = await cm.get_drone()  # Fast: <100ms
            if drone:
                await drone.action.arm()  # Send command immediately
        """
        # ----------------------------------------------------------------------
        # FAST PATH: Already connected
        # ----------------------------------------------------------------------
        # This is the common case - we already have a connection
        # Just return the cached drone object immediately
        if self._state == ConnectionState.CONNECTED and self._drone is not None:
            return self._drone

        # ----------------------------------------------------------------------
        # SLOW PATH: Not connected - try to reconnect
        # ----------------------------------------------------------------------
        # We're not connected, but maybe we can recover
        # Try auto-reconnect if we're disconnected or in error state
        if self._state in (ConnectionState.DISCONNECTED, ConnectionState.ERROR):
            logger.debug("Not connected, attempting auto-reconnect")
            success = await self.connect(self._system_address)
            if success:
                # Reconnection worked - return the drone
                return self._drone

        # Not connected and couldn't reconnect
        return None

    async def ensure_connected(self) -> System:
        """Get the drone instance or raise an exception.

        This is like get_drone() but it raises an exception instead of returning
        None when not connected. Use this when you REQUIRE a connection and want
        to handle the error case with try/except.

        Returns:
            System instance if connected

        Raises:
            ConnectionError: If not connected and auto-reconnect failed.
                               The error message includes the current state.

        Example:
            cm = ConnectionManager()

            try:
                drone = await cm.ensure_connected()
                # If we get here, we have a valid connection
                await drone.action.arm()
            except ConnectionError as e:
                # Handle the error case
                print(f"Cannot fly: {e}")
                return
        """
        # Try to get the drone
        drone = await self.get_drone()

        # If we got None, raise an exception with helpful information
        if drone is None:
            raise ConnectionError(
                f"Not connected to drone (state: {self._state.name})"
            )

        return drone

    # ==========================================================================
    # PRIVATE METHODS (Internal implementation details)
    # ==========================================================================

    def _start_health_monitor(self) -> None:
        """Start the background health monitoring task.

        This creates an asyncio.Task that runs _health_monitor() in the
        background. The task periodically checks:
        - Heartbeat from drone (is it still responding?)
        - GPS lock status (can it navigate?)
        - Home position status (can it return to launch?)

        The task runs until stop is requested via _stop_health_monitor event.
        """
        # Only start if not already running
        if self._health_task is None or self._health_task.done():
            # Clear the stop event (in case it was set from a previous run)
            self._stop_health_monitor.clear()
            # Create and store the background task
            self._health_task = asyncio.create_task(self._health_monitor())
            logger.debug("Health monitoring started")

    async def _health_monitor(self) -> None:
        """Background task that continuously monitors connection health.

        This method runs in a separate asyncio.Task and loops until told to stop.
        Every _health_check_interval_s seconds, it checks the drone's health
        via telemetry and updates the _health metrics.

        Monitored metrics:
        - Heartbeat: When did we last hear from the drone?
        - GPS lock: Does the drone have satellite lock for navigation?
        - Home position: Does the drone know where "home" is for return-to-launch?

        If health check fails, it transitions state to DEGRADED and triggers
        auto-reconnection.

        This is a background task - you don't call it directly. It's started
        by _start_health_monitor() when connection succeeds.
        """
        logger.debug("Health monitor running")

        # Loop until we're told to stop
        while not self._stop_health_monitor.is_set():
            try:
                # Wait for the stop event or the health check interval
                # This waits up to _health_check_interval_s seconds
                await asyncio.wait_for(
                    self._stop_health_monitor.wait(),
                    timeout=self._health_check_interval_s
                )
                # If wait() returned without timeout, stop was requested
                break  # Exit the loop
            except asyncio.TimeoutError:
                # Timeout means the interval passed - time for a health check
                pass

            # Skip health check if we're not connected
            if self._drone is None or self._state != ConnectionState.CONNECTED:
                continue

            try:
                # Perform the actual health check
                healthy = await self._check_health()

                # Vehicle readiness failures are not transport failures. Reconnect
                # only when the health read itself fails and returns None.
                if healthy is None and self._state == ConnectionState.CONNECTED:
                    logger.warning("Health check failed, marking degraded")
                    self._state = ConnectionState.DEGRADED

                    # Trigger auto-reconnect in the background
                    # We use create_task so it runs independently
                    asyncio.create_task(self._auto_reconnect())

            except Exception as e:
                # Log errors but don't stop monitoring - keep trying
                logger.error(f"Health monitor error: {e}")
                self._record_error(str(e))

        logger.debug("Health monitor stopped")

    async def _check_health(self) -> Optional[bool]:
        """Check drone health via MAVSDK telemetry.

        This queries the drone's telemetry to determine if everything is
        working correctly. Specifically checks:
        - is_global_position_ok: GPS lock for navigation
        - is_home_position_ok: Home position set for return-to-launch

        Returns:
            True if healthy (GPS lock AND home position set),
            False if either vehicle readiness check fails,
            None if the telemetry health read itself fails.

        Note:
            This is an async generator consumer - it uses 'async for' to get
            a single telemetry reading, then returns.
        """
        # Can't check health if no drone object
        if self._drone is None:
            return False

        try:
            # Get health from telemetry
            # MAVSDK provides an async iterator that yields health updates
            async for health in self._drone.telemetry.health():
                # Determine overall health from two key indicators:
                # 1. Global position (GPS) - needed for navigation
                # 2. Home position - needed for return-to-launch
                self._health.is_healthy = (
                    health.is_global_position_ok and health.is_home_position_ok
                )

                # Store individual metrics for detailed reporting
                self._health.gps_lock = health.is_global_position_ok
                self._health.home_position_set = health.is_home_position_ok

                # Record when we got this heartbeat
                self._health.last_heartbeat = asyncio.get_event_loop().time()

                # Return the overall health status
                return self._health.is_healthy

        except Exception as e:
            # Log warning but return None - don't crash the monitor
            logger.warning(f"Health check failed: {e}")
            return None

        # Should never reach here (async for always yields at least once)
        return False

    async def _auto_reconnect(self) -> None:
        """Attempt automatic reconnection when connection is lost.

        This is called by the health monitor when it detects a degraded
        connection. It tries to re-establish the connection up to
        _max_reconnect_attempts times with _reconnect_delay_s between tries.

        If successful, state returns to CONNECTED.
        If failed after all retries, state becomes ERROR.

        This method prevents concurrent reconnection attempts by checking
        if already RECONNECTING before starting.
        """
        # Prevent multiple simultaneous reconnection attempts
        if self._state == ConnectionState.RECONNECTING:
            return  # Already trying to reconnect

        # Set state to RECONNECTING so other code knows what's happening
        self._state = ConnectionState.RECONNECTING
        logger.info("Starting auto-reconnect...")

        # Try up to _max_reconnect_attempts times
        for attempt in range(1, self._max_reconnect_attempts + 1):
            try:
                logger.debug(f"Reconnect attempt {attempt}/{self._max_reconnect_attempts}")

                # Attempt the actual connection
                drone = await self._do_connect(self._system_address)

                if drone:
                    # Success! Update state
                    async with self._connection_lock:
                        self._drone = drone
                        self._state = ConnectionState.CONNECTED
                        self._health.is_healthy = True

                    logger.info("Auto-reconnect successful")
                    return  # Exit - we're reconnected!

            except Exception as e:
                # Log failure and record error
                logger.warning(f"Reconnect attempt {attempt} failed: {e}")
                self._record_error(str(e))

            # Wait before next attempt
            await asyncio.sleep(self._reconnect_delay_s)

        # ----------------------------------------------------------------------
        # ALL RECONNECTION ATTEMPTS FAILED
        # ----------------------------------------------------------------------
        async with self._connection_lock:
            self._state = ConnectionState.ERROR

        logger.error("Auto-reconnect failed after all attempts")

    def _update_health(
        self,
        is_healthy: bool,
        gps_lock: bool = False,
        home_position_set: bool = False
    ) -> None:
        """Manually update health metrics (primarily for testing).

        This method allows tests to directly set health values without
        needing an actual drone connection.

        Args:
            is_healthy: Overall health status to set
            gps_lock: GPS lock status to set
            home_position_set: Home position status to set

        Note:
            This updates last_heartbeat to the current time automatically.
        """
        self._health.is_healthy = is_healthy
        self._health.gps_lock = gps_lock
        self._health.home_position_set = home_position_set
        self._health.last_heartbeat = asyncio.get_event_loop().time()

    def _record_error(self, error_message: str) -> None:
        """Record an error in the health metrics.

        This increments the error count and stores the error message.
        Called whenever something goes wrong with the connection.

        Args:
            error_message: The error message to record
        """
        self._health.error_count += 1
        self._health.last_error = error_message

    # ==========================================================================
    # CONTEXT MANAGER SUPPORT
    # ==========================================================================
    # These methods allow using ConnectionManager with 'async with' syntax
    # This ensures disconnect() is called even if an exception occurs

    async def __aenter__(self) -> "ConnectionManager":
        """Async context manager entry point.

        Called when entering 'async with ConnectionManager() as cm:'
        Simply returns self so the context variable holds the manager.

        Returns:
            The ConnectionManager instance

        Example:
            async with ConnectionManager() as cm:
                # cm is the ConnectionManager instance
                await cm.connect("udp://:14540")
                # ... do work ...
            # disconnect() called automatically here!
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit point.

        Called when exiting the 'async with' block, even if an exception
        occurred. Ensures disconnect() is always called for cleanup.

        Args:
            exc_type: Type of exception that occurred (None if no exception)
            exc_val: The exception value (None if no exception)
            exc_tb: Exception traceback (None if no exception)

        Note:
            Does NOT suppress exceptions - they propagate after disconnect.
        """
        await self.disconnect()
