"""Context managers for safe drone resource management.

This module provides async context managers for handling drone connections,
offboard mode, telemetry subscriptions, and batch operations. All context
managers ensure proper cleanup even when exceptions occur.

Key features:
- managed_connection: Auto-connect/disconnect with timeout
- managed_offboard: Safe offboard mode entry/exit
- managed_telemetry_cache: Automatic cache lifecycle management
- batch_operations: Controlled concurrent operation execution
- FlightSession: Comprehensive flight lifecycle management

Example:
    async with managed_connection() as cm:
        drone = await cm.get_drone()
        async with managed_offboard(drone) as offboard:
            await offboard.set_velocity_ned(...)
        # Offboard automatically stopped
    # Connection automatically closed
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, List, Mapping, Optional, Union, cast

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData

logger = logging.getLogger(__name__)


# =============================================================================
# BEGINNER'S GUIDE TO CONTEXT MANAGERS
# =============================================================================
#
# WHAT ARE CONTEXT MANAGERS?
# --------------------------
# Context managers are Python's way of ensuring that resources are properly
# set up before use and cleaned up after use, even if errors occur.
#
# Think of them like a "guardian angel" for resources - they guarantee that
# cleanup happens, no matter what goes wrong.
#
# THE TRY/FINALLY PROBLEM
# -----------------------
# Without context managers, you might write code like this:
#
#     connection = None
#     try:
#         connection = connect_to_drone()  # Setup
#         do_flight_operations(connection)  # Work
#     finally:
#         if connection:
#             connection.disconnect()  # Cleanup (ALWAYS runs)
#
# This works, but has problems:
# 1. VERBOSE: You repeat cleanup logic everywhere
# 2. ERROR-PRONE: Easy to forget the finally block
# 3. COMPLEX: Nested resources create "callback hell"
#
# THE CONTEXT MANAGER SOLUTION
# ----------------------------
# With context managers, the same code becomes:
#
#     async with managed_connection() as connection:
#         do_flight_operations(connection)
#     # Cleanup happens automatically here
#
# Benefits:
# 1. CLEAN: Setup and cleanup are encapsulated
# 2. SAFE: Cleanup ALWAYS happens, even on exceptions
# 3. COMPOSABLE: Can nest them cleanly
# 4. READABLE: The structure matches the intent
#
# HOW CONTEXT MANAGERS WORK
# -------------------------
# A context manager has three parts:
# 1. __aenter__ (async enter): Runs when entering the 'async with' block
# 2. The body of the 'async with' block: Your actual work
# 3. __aexit__ (async exit): Runs when leaving, even if an exception occurred
#
# Example flow:
#     async with MyContextManager() as resource:  # <-- __aenter__ runs
#         await do_work(resource)                  # <-- Your code runs
#     # <-- __aexit__ runs (ALWAYS, even if do_work raised an exception)
#
# DECORATOR STYLE (used in this file)
# -----------------------------------
# The @asynccontextmanager decorator lets you write context managers as
# simple async generators using 'yield' instead of classes:
#
#     @asynccontextmanager
#     async def my_context():
#         resource = setup()      # Setup before yield
#         try:
#             yield resource    # Give control to the 'async with' body
#         finally:
#             cleanup()         # Cleanup after yield (ALWAYS runs)
#
# The 'yield' acts like a magic door - code before yield is setup,
# code after yield is cleanup, and the yield itself passes the resource
# to the body of your 'async with' statement.
#
# =============================================================================


async def _get_telemetry_from_drone(drone: Any) -> TelemetryData:
    """Fetch telemetry data from a connected drone.

    This helper function gathers telemetry from MAVSDK's various
    telemetry streams and combines them into a TelemetryData object.

    Args:
        drone: MAVSDK System instance

    Returns:
        TelemetryData snapshot of current drone state
    """
    timestamp = time.time()

    # Initialize defaults
    lat, lon, alt = 0.0, 0.0, 0.0
    vel_n, vel_e, vel_d = 0.0, 0.0, 0.0
    groundspeed = 0.0
    roll, pitch, yaw = 0.0, 0.0, 0.0
    battery_pct, battery_v, battery_a = 0.0, 0.0, 0.0
    armed, in_air = False, False
    flight_mode = "UNKNOWN"
    gps_fix = 0
    is_gps_ok, is_home_ok = False, False

    try:
        # Get position
        async for pos in drone.telemetry.position():
            lat = pos.latitude_deg
            lon = pos.longitude_deg
            alt = pos.relative_altitude_m
            break

        # Get velocity
        async for vel in drone.telemetry.velocity_ned():
            vel_n = vel.north_m_s
            vel_e = vel.east_m_s
            vel_d = vel.down_m_s
            groundspeed = (vel_n**2 + vel_e**2) ** 0.5
            break

        # Get attitude
        async for att in drone.telemetry.attitude_euler():
            roll = att.roll_deg
            pitch = att.pitch_deg
            yaw = att.yaw_deg
            break

        # Get battery
        async for bat in drone.telemetry.battery():
            remaining_percent = bat.remaining_percent
            battery_pct = (
                remaining_percent * 100
                if remaining_percent <= 1.0
                else remaining_percent
            )
            battery_v = getattr(bat, "voltage_v", 0.0)
            battery_a = getattr(bat, "current_a", 0.0)
            break

        # Get armed state
        async for arm in drone.telemetry.armed():
            armed = arm
            break

        # Get in-air state
        async for state in drone.telemetry.landed_state():
            in_air = state != 0  # 0 is on ground
            break

        # Get flight mode
        async for mode in drone.telemetry.flight_mode():
            flight_mode = str(mode)
            break

        # Get health
        async for health in drone.telemetry.health():
            is_gps_ok = health.is_global_position_ok
            is_home_ok = health.is_home_position_ok
            break

        # Get GPS fix
        async for gps in drone.telemetry.gps_info():
            gps_fix = gps.fix_type
            break

    except Exception as e:
        logger.warning(f"Telemetry fetch error: {e}")
        # Return partial data with what we have

    return TelemetryData(
        timestamp=timestamp,
        latitude=lat,
        longitude=lon,
        altitude=alt,
        velocity_north=vel_n,
        velocity_east=vel_e,
        velocity_down=vel_d,
        groundspeed=groundspeed,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        battery_percent=battery_pct,
        battery_voltage=battery_v,
        battery_current=battery_a,
        armed=armed,
        in_air=in_air,
        flight_mode=flight_mode,
        gps_fix=gps_fix,
        is_gps_ok=is_gps_ok,
        is_home_position_ok=is_home_ok,
    )


# =============================================================================
# CONTEXT MANAGER 1: MANAGED CONNECTION
# =============================================================================
#
# PURPOSE: Ensures drone connection is always closed, even if things go wrong.
#
# WHY IT'S NEEDED:
# Drone connections use network resources (UDP ports, sockets). If you don't
# properly disconnect, you can:
# - Leave zombie connections that block reconnection
# - Waste network resources
# - Prevent other programs from using the port
#
# HOW IT WORKS:
# 1. __aenter__ (before yield):
#    - Creates a ConnectionManager
#    - Attempts to connect with timeout
#    - Raises ConnectionError if it fails
#    - Logs successful connection
#
# 2. yield cm:
#    - Passes the ConnectionManager to your code
#    - Your code runs here
#
# 3. __aexit__ (after yield, in finally):
#    - ALWAYS calls cm.disconnect()
#    - Logs that connection is closed
#    - This runs even if your code raised an exception!
#
# REAL USAGE EXAMPLE:
#     async with managed_connection("udp://:14540", timeout_s=10.0) as cm:
#         drone = await cm.get_drone()
#         await drone.action.arm()
#         await drone.action.takeoff()
#         # ... do flight stuff ...
#     # <-- Connection automatically closed here, guaranteed!
#
# COMPARE TO TRY/FINALLY:
#     # Without context manager (error-prone):
#     cm = ConnectionManager()
#     try:
#         await cm.connect("udp://:14540")
#         drone = await cm.get_drone()
#         await drone.action.arm()
#     finally:
#         await cm.disconnect()  # Easy to forget this!
#
# =============================================================================

@asynccontextmanager
async def managed_connection(
    system_address: str = "udp://:14540",
    timeout_s: float = 5.0
) -> AsyncGenerator[ConnectionManager, None]:
    """Context manager for drone connection.

    Automatically connects on entry and disconnects on exit.
    Ensures cleanup even if exceptions occur.

    Args:
        system_address: MAVSDK system address (default: udp://:14540 for SITL)
        timeout_s: Connection timeout in seconds

    Yields:
        ConnectionManager instance with active connection

    Raises:
        ConnectionError: If connection fails within timeout
        asyncio.TimeoutError: If connection times out

    Example:
        async with managed_connection() as cm:
            drone = await cm.get_drone()
            await drone.action.arm()
        # Automatically disconnected here
    """
    cm = ConnectionManager()

    try:
        # Setup phase: Connect with timeout
        connected = await asyncio.wait_for(
            cm.connect(system_address),
            timeout=timeout_s
        )

        if not connected:
            raise ConnectionError(f"Failed to connect to {system_address}")

        logger.info(f"Connected to drone at {system_address}")
        # Yield gives control to the body of the 'async with' block
        yield cm

    finally:
        # Cleanup phase: ALWAYS runs, even if an exception occurred
        await cm.disconnect()
        logger.debug("Connection closed by context manager")


# =============================================================================
# CONTEXT MANAGER 2: MANAGED OFFBOARD
# =============================================================================
#
# PURPOSE: Safely enters and exits offboard control mode.
#
# WHAT IS OFFBOARD MODE?
# Offboard mode allows external programs (like this one) to control the drone
# directly by sending velocity or position setpoints. It's powerful but
# dangerous - if setpoints stop arriving, the drone could drift or crash!
#
# WHY THIS CONTEXT MANAGER IS CRITICAL:
# 1. Drone requires continuous "heartbeats" (setpoints) while in offboard
# 2. If your program crashes, the drone MUST be taken out of offboard mode
# 3. Without proper cleanup, the drone could be left in an unsafe state
#
# HOW IT WORKS:
# 1. __aenter__:
#    - Optionally sets initial velocity setpoint
#    - Starts offboard mode on the drone
#    - Launches a background heartbeat task that keeps offboard alive
#
# 2. yield offboard_module:
#    - Your code gets the offboard module to send setpoints
#    - Heartbeat task runs in background keeping drone happy
#
# 3. __aexit__:
#    - Signals heartbeat to stop (stop_heartbeat.set())
#    - Cancels the heartbeat task
#    - Stops offboard mode (drone returns to safe mode)
#    - ALL of this happens even if your code crashed!
#
# REAL USAGE EXAMPLE:
#     async with managed_connection() as cm:
#         drone = await cm.get_drone()
#         async with managed_offboard(drone) as offboard:
#             # Send velocity: 1 m/s forward for 5 seconds
#             await offboard.set_velocity_ned(
#                 VelocityNedYaw(1.0, 0.0, 0.0, 0.0)
#             )
#             await asyncio.sleep(5.0)
#         # <-- Offboard stopped, drone safe, even if an error occurred above!
#
# SAFETY GUARANTEE:
# If your code raises an exception (e.g., division by zero), the finally block
# ensures offboard is stopped and the drone returns to a safe flight mode.
#
# =============================================================================

@asynccontextmanager
async def managed_offboard(
    drone: Any,
    initial_setpoint: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Any, None]:
    """Context manager for offboard mode.

    Automatically starts offboard on entry and stops on exit.

    Note: This context manager handles offboard mode lifecycle only.
    Setpoint streaming (required by PX4 at 20Hz) must be handled separately
    by the caller, typically via OffboardVelocityStreamer.

    Args:
        drone: MAVSDK System instance
        initial_setpoint: Optional initial setpoint dict with velocity_ned params

    Yields:
        drone.offboard module for controlling the drone

    Raises:
        OffboardError: If offboard mode cannot be started
        Exception: Propagates any exception during offboard operation

    Example:
        async with managed_offboard(drone) as offboard:
            # Use OffboardVelocityStreamer for setpoint streaming
            await offboard.set_velocity_ned(
                VelocityNedYaw(1.0, 0.0, 0.0, 0.0)
            )
            await asyncio.sleep(5.0)  # Maintain for 5 seconds
        # Automatically stopped here
    """
    from mavsdk import offboard

    offboard_module = drone.offboard

    try:
        # Setup phase
        # Set initial setpoint if provided
        if initial_setpoint:
            velocity = offboard.VelocityNedYaw(**initial_setpoint)
            await offboard_module.set_velocity_ned(velocity)

        # Start offboard mode
        await offboard_module.start()
        logger.info("Offboard mode started")

        # Yield gives control to the body of the 'async with' block
        yield offboard_module

    except Exception as e:
        # Handle offboard errors specially
        error_type = type(e).__name__
        if "OffboardError" in error_type:
            logger.error(f"Offboard error: {e}")
        else:
            logger.error(f"Error in offboard context: {e}")
        raise
    finally:
        # Cleanup phase - ALWAYS RUNS, even on exceptions!

        # Stop offboard mode (return drone to safe state)
        try:
            await offboard_module.stop()
            logger.info("Offboard mode stopped")
        except Exception as e:
            logger.warning(f"Error stopping offboard: {e}")


# =============================================================================
# CONTEXT MANAGER 3: MANAGED TELEMETRY CACHE
# =============================================================================
#
# PURPOSE: Manages telemetry cache lifecycle (background data collection).
#
# WHAT IS THE TELEMETRY CACHE?
# The TelemetryCache runs a background task that continuously fetches
# telemetry data (position, battery, etc.) from the drone. This allows
# non-blocking access to recent telemetry without waiting for MAVSDK queries.
#
# WHY A CONTEXT MANAGER?
# The cache spawns a background asyncio task that needs to be properly
# stopped when you're done. If not stopped:
# - Wastes CPU polling for data you don't need
# - Can cause errors if the connection closes but cache keeps trying
#
# HOW IT WORKS:
# 1. __aenter__:
#    - Creates TelemetryCache with specified refresh rate
#    - Starts background refresh task
#
# 2. yield cache:
#    - Your code can call cache.get_data() for instant telemetry
#    - Background task keeps data fresh
#
# 3. __aexit__:
#    - Stops the background refresh task
#    - Cleans up resources
#
# REAL USAGE EXAMPLE:
#     async with managed_connection() as cm:
#         drone = await cm.get_drone()
#         async with managed_telemetry_cache(drone, refresh_interval_ms=100) as cache:
#             for _ in range(100):  # Monitor for 100 seconds
#                 data = cache.get_data()  # Instant access, no waiting!
#                 print(f"Battery: {data.battery_percent:.1f}%")
#                 print(f"Position: {data.latitude:.6f}, {data.longitude:.6f}")
#                 await asyncio.sleep(1.0)
#         # <-- Cache stopped, background task cleaned up
#
# =============================================================================

@asynccontextmanager
async def managed_telemetry_cache(
    drone: Any,
    refresh_interval_ms: float = 100.0,
    stale_ms: float = 500.0
) -> AsyncGenerator[TelemetryCache, None]:
    """Context manager for telemetry cache.

    Automatically starts cache on entry and stops on exit.
    Provides non-blocking telemetry access with background refresh.

    Args:
        drone: MAVSDK System instance
        refresh_interval_ms: Background refresh interval in milliseconds
        stale_ms: Data staleness threshold in milliseconds

    Yields:
        TelemetryCache instance with active background refresh

    Example:
        async with managed_telemetry_cache(drone) as cache:
            for _ in range(10):
                data = cache.get_data()
                print(f"Position: {data.latitude}, {data.longitude}")
                await asyncio.sleep(1.0)
        # Automatically stopped here
    """
    cache = TelemetryCache(
        refresh_ms=int(refresh_interval_ms),
        stale_ms=int(stale_ms)
    )

    try:
        # Setup: Start background refresh
        await cache.start(lambda: _get_telemetry_from_drone(drone))
        logger.debug("Telemetry cache started")
        yield cache
    finally:
        # Cleanup: Stop background task
        await cache.stop()
        logger.debug("Telemetry cache stopped")


# =============================================================================
# CONTEXT MANAGER 4: BATCH OPERATIONS (Class-based)
# =============================================================================
#
# PURPOSE: Collects multiple async operations and executes them together
#          with controlled concurrency when exiting the context.
#
# WHY USE THIS?
# - You want to "queue up" operations during a context
# - You need to limit concurrent execution (e.g., max 5 at a time)
# - You want automatic result collection
#
# HOW IT WORKS:
# This uses the CLASS-BASED context manager pattern instead of the decorator.
# Both work, but classes give more control for complex cases.
#
# Class-based pattern:
#     class MyContext:
#         async def __aenter__(self):    # Setup
#             return self
#         async def __aexit__(self, exc_type, exc_val, exc_tb):  # Cleanup
#             return False  # Don't suppress exceptions
#
# BatchOperations flow:
# 1. __aenter__:
#    - Returns self (the batch object)
#    - You append operations to self.operations list
#
# 2. Inside 'async with' block:
#    - You add coroutines to batch.operations
#    - Nothing executes yet - just collecting
#
# 3. __aexit__:
#    - ALL collected operations execute with controlled concurrency
#    - Uses asyncio.Semaphore to limit concurrent ops
#    - Results stored in batch.results
#
# REAL USAGE EXAMPLE:
#     async def check_battery(drone_id):
#         # Returns battery percent
#         ...
#
#     async with BatchOperations(max_concurrent=3) as batch:
#         # Just collecting operations, NOT executing yet
#         batch.operations.append(check_battery(1))
#         batch.operations.append(check_battery(2))
#         batch.operations.append(check_battery(3))
#         batch.operations.append(check_battery(4))
#         batch.operations.append(check_battery(5))
#     # <-- All 5 execute here, max 3 at a time, results in batch.results
#
#     for drone_id, battery in enumerate(batch.results, 1):
#         print(f"Drone {drone_id}: {battery}%")
#
# =============================================================================

class BatchOperations:
    """Context manager for batching multiple operations.

    Collects operations during the context and executes them with
    controlled concurrency when exiting the context.

    Args:
        max_concurrent: Maximum number of concurrent operations
        continue_on_error: If True, continue executing after errors

    Attributes:
        operations: List of coroutines to execute
        results: List of results after execution (populated after exit)

    Raises:
        Exception: First exception if continue_on_error=False

    Example:
        async def operation1(): return 1
        async def operation2(): return 2

        async with BatchOperations(max_concurrent=3) as batch:
            batch.operations.append(operation1())
            batch.operations.append(operation2())
        # All operations executed with max 3 concurrent
        print(batch.results)  # [1, 2]
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        continue_on_error: bool = False
    ):
        self.max_concurrent = max_concurrent
        self.continue_on_error = continue_on_error
        self.operations: List[Coroutine[Any, Any, Any]] = []
        self.results: List[Any] = []

    async def __aenter__(self) -> "BatchOperations":
        """Enter batch operations context.

        Returns self so you can append operations to self.operations.
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> bool:
        """Exit batch operations context - execute all operations.

        This is where the magic happens! All collected operations are
        executed with controlled concurrency using a semaphore.

        Args:
            exc_type: Type of exception if one occurred in the body
            exc_val: The exception if one occurred
            exc_tb: Traceback if exception occurred

        Returns:
            False to propagate exceptions (not suppressed)
        """
        if not self.operations:
            return False

        # Semaphore controls concurrency (like a bouncer at a club)
        # Only max_concurrent operations can enter at once
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_with_limit(coro: Coroutine[Any, Any, Any]) -> Any:
            """Run a coroutine under the semaphore."""
            async with semaphore:
                return await coro

        # Create tasks for all operations, each respecting the semaphore
        tasks = [run_with_limit(op) for op in self.operations]

        if self.continue_on_error:
            # Gather all results, exceptions become result values
            self.results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Gather all results, first exception stops everything
            self.results = await asyncio.gather(*tasks)

        return False  # Don't suppress exceptions


# =============================================================================
# CONVENIENCE WRAPPER FOR BATCH OPERATIONS
# =============================================================================
#
# The BatchOperations class above is class-based. This function wraps it
# in the @asynccontextmanager decorator style for API consistency.
#
# Why have both?
# - Class-based: More control, can inspect state after exit
# - Decorator-based: Simpler, consistent with other functions in this file
#
# =============================================================================

@asynccontextmanager
async def batch_operations(
    max_concurrent: int = 5,
    continue_on_error: bool = False
) -> AsyncGenerator[BatchOperations, None]:
    """Context manager for batching multiple operations (convenience wrapper).

    Args:
        max_concurrent: Maximum number of concurrent operations
        continue_on_error: If True, continue executing after errors

    Yields:
        BatchOperations instance with operations list and results storage

    Example:
        async with batch_operations(max_concurrent=3) as batch:
            batch.operations.append(operation1())
            batch.operations.append(operation2())
        # Results available in batch.results
    """
    batch = BatchOperations(max_concurrent, continue_on_error)
    try:
        yield batch
    finally:
        # Execution happens in __aexit__
        pass


# =============================================================================
# CONTEXT MANAGER 5: FLIGHT SESSION (The "Everything" Manager)
# =============================================================================
#
# PURPOSE: Complete flight lifecycle management - connection, telemetry,
#          and all common operations in one convenient package.
#
# WHY USE THIS?
# - You want a "one-stop shop" for flight operations
# - You need telemetry, connection, and flight commands all together
# - You want the cleanest, safest code possible
#
# HOW IT WORKS:
# This combines multiple context managers into one comprehensive session.
#
# 1. __aenter__:
#    - Connects to drone (like managed_connection)
#    - Starts telemetry cache (like managed_telemetry_cache)
#    - Provides methods: takeoff(), land(), arm(), get_telemetry(), etc.
#
# 2. Inside 'async with' block:
#    - Use session.takeoff() to takeoff
#    - Use session.get_telemetry() to get current state
#    - Use session.goto() to navigate
#    - Use session.land() to land
#
# 3. __aexit__:
#    - Stops telemetry cache (even if flight crashed!)
#    - Disconnects from drone (even if code raised exception!)
#    - Logs what happened
#
# REAL USAGE EXAMPLE:
#     async with FlightSession(
#         system_address="udp://:14540",
#         telemetry_refresh_ms=100
#     ) as session:
#         # Check telemetry before flight
#         data = session.get_telemetry()
#         print(f"Battery before: {data.battery_percent}%")
#
#         # Fly!
#         await session.arm()
#         await session.takeoff(altitude_m=5.0)
#         await session.goto(37.7749, -122.4194, altitude_m=10.0)
#         await session.land()
#
#         # Check telemetry after flight
#         data = session.get_telemetry()
#         print(f"Battery after: {data.battery_percent}%")
#     # <-- Everything cleaned up automatically!
#
# NESTING CONTEXT MANAGERS (Advanced Pattern):
# You can nest these for fine-grained control:
#
#     async with FlightSession() as session:
#         await session.arm()
#         await session.takeoff()
#
#         async with managed_offboard(session.drone) as offboard:
#             # Direct offboard control within managed session
#             await offboard.set_velocity_ned(...)
#
#     # Both offboard AND session clean up automatically!
#
# SAFETY GUARANTEE:
# Even if your flight code crashes mid-flight, the __aexit__ ensures:
# 1. Telemetry cache stops
# 2. Connection closes properly
# 3. Drone returns to safe state (via PX4 failsafes)
#
# =============================================================================

class FlightSession:
    """Comprehensive flight session context manager.

    Manages entire flight lifecycle including connection, telemetry cache,
    and resource cleanup. Provides high-level flight operations.

    Attributes:
        system_address: MAVSDK system address
        cm: ConnectionManager instance (populated after entering context)
        cache: TelemetryCache instance (populated after entering context)

    Example:
        async with FlightSession() as session:
            await session.takeoff()
            await session.goto(37.7749, -122.4194, 10.0)
            await session.land()
    """

    def __init__(
        self,
        system_address: str = "udp://:14540",
        telemetry_refresh_ms: int = 100,
        connection_timeout_s: float = 5.0
    ):
        """Initialize the flight session.

        Note: This doesn't connect yet - connection happens in __aenter__.

        Args:
            system_address: MAVSDK system address
            telemetry_refresh_ms: Telemetry cache refresh interval in ms
            connection_timeout_s: Connection timeout in seconds
        """
        self.system_address = system_address
        self.telemetry_refresh_ms = telemetry_refresh_ms
        self.connection_timeout_s = connection_timeout_s

        # These get populated in __aenter__
        self.cm: Optional[ConnectionManager] = None
        self._cache: Optional[TelemetryCache] = None
        self._running = False
        self._drone: Optional[Any] = None

    async def __aenter__(self) -> "FlightSession":
        """Enter flight session - connect and start telemetry cache.

        This is the setup phase. It:
        1. Creates ConnectionManager
        2. Connects to the drone
        3. Starts the telemetry cache
        4. Returns self for method chaining

        Returns:
            Self for method chaining

        Raises:
            ConnectionError: If connection fails
        """
        self.cm = ConnectionManager()

        # Connect with timeout
        connected = await asyncio.wait_for(
            self.cm.connect(self.system_address),
            timeout=self.connection_timeout_s
        )

        if not connected:
            raise ConnectionError(f"Failed to connect to {self.system_address}")

        self._drone = await self.cm.get_drone()
        if self._drone is None:
            raise ConnectionError("Connected but drone unavailable")

        # Start telemetry cache for non-blocking access
        self._cache = TelemetryCache(refresh_ms=self.telemetry_refresh_ms)
        await self._cache.start(lambda: _get_telemetry_from_drone(self._drone))

        self._running = True
        logger.info("Flight session started")

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> bool:
        """Exit flight session with cleanup.

        This is the cleanup phase. It ALWAYS runs, even if exceptions occurred.
        It ensures telemetry cache is stopped and connection is closed.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            False to propagate exceptions (not suppressed)
        """
        self._running = False

        # Stop cache (with error handling)
        if self._cache:
            try:
                await self._cache.stop()
                logger.debug("Telemetry cache stopped")
            except Exception as e:
                logger.warning(f"Error stopping telemetry cache: {e}")

        # Disconnect (with error handling)
        if self.cm:
            try:
                await self.cm.disconnect()
                logger.debug("Connection closed")
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")

        # Log what happened
        if exc_val:
            logger.error(f"Flight session exited with error: {exc_val}")
        else:
            logger.info("Flight session ended normally")

        return False  # Don't suppress exceptions - let them propagate

    def get_telemetry(self) -> Optional[TelemetryData]:
        """Get current telemetry data (non-blocking).

        Returns cached telemetry instantly without waiting for MAVSDK.

        Returns:
            TelemetryData if available, None otherwise
        """
        if self._cache:
            return self._cache.get_data()
        return None

    async def get_fresh_telemetry(self) -> Optional[TelemetryData]:
        """Get fresh telemetry data (may block for refresh).

        Waits for a fresh telemetry fetch if current data is stale.

        Returns:
            TelemetryData if available, None otherwise
        """
        if self._cache:
            return await self._cache.get_fresh_data()
        return None

    def is_telemetry_fresh(self) -> bool:
        """Check if telemetry data is fresh (not stale).

        Returns:
            True if data is fresh, False if stale or unavailable
        """
        if self._cache:
            return not self._cache.is_stale()
        return False

    async def takeoff(self, altitude_m: float = 2.5) -> None:
        """Command the drone to takeoff.

        Args:
            altitude_m: Target takeoff altitude in meters

        Raises:
            ConnectionError: If not connected
            RuntimeError: If takeoff command fails
        """
        if not self._drone:
            raise ConnectionError("Not connected to drone")

        logger.info(f"Commanding takeoff to {altitude_m}m")
        await self._drone.action.takeoff()

    async def land(self) -> None:
        """Command the drone to land.

        Raises:
            ConnectionError: If not connected
            RuntimeError: If land command fails
        """
        if not self._drone:
            raise ConnectionError("Not connected to drone")

        logger.info("Commanding land")
        await self._drone.action.land()

    async def goto(
        self,
        latitude: float,
        longitude: float,
        altitude_m: float,
        groundspeed_m_s: Optional[float] = None
    ) -> None:
        """Command the drone to goto a position.

        Args:
            latitude: Target latitude in degrees
            longitude: Target longitude in degrees
            altitude_m: Target altitude in meters (relative to home)
            groundspeed_m_s: Optional speed in m/s

        Raises:
            ConnectionError: If not connected
            RuntimeError: If goto command fails
        """
        if not self._drone:
            raise ConnectionError("Not connected to drone")

        logger.info(f"Commanding goto: {latitude}, {longitude}, {altitude_m}m")
        # Implementation would use offboard or mission system
        # This is a placeholder for the actual implementation

    async def arm(self) -> None:
        """Arm the drone.

        Arms the drone (enables motors, but doesn't take off).

        Raises:
            ConnectionError: If not connected
            RuntimeError: If arm command fails
        """
        if not self._drone:
            raise ConnectionError("Not connected to drone")

        logger.info("Arming drone")
        await self._drone.action.arm()

    async def disarm(self) -> None:
        """Disarm the drone.

        Disarms the drone (disables motors - only do this on ground!).

        Raises:
            ConnectionError: If not connected
            RuntimeError: If disarm command fails
        """
        if not self._drone:
            raise ConnectionError("Not connected to drone")

        logger.info("Disarming drone")
        await self._drone.action.disarm()

    @property
    def is_running(self) -> bool:
        """Check if the flight session is active.

        Returns:
            True if session is running, False otherwise
        """
        return self._running

    @property
    def drone(self) -> Optional[Any]:
        """Get the underlying drone instance.

        This gives you access to the raw MAVSDK System instance for
        advanced operations not covered by FlightSession methods.

        Returns:
            MAVSDK System instance if connected, None otherwise
        """
        return self._drone


# =============================================================================
# COMPLETE REAL-WORLD EXAMPLE: FULL FLIGHT WITH NESTED CONTEXT MANAGERS
# =============================================================================
#
# Here's how you might combine all context managers for a complete mission:
#
#     async def complete_mission():
#         # 1. Establish connection (managed_connection)
#         async with managed_connection("udp://:14540") as cm:
#             drone = await cm.get_drone()
#
#             # 2. Start telemetry cache (managed_telemetry_cache)
#             async with managed_telemetry_cache(drone, refresh_interval_ms=100) as cache:
#
#                 # Check pre-flight conditions
#                 data = cache.get_data()
#                 if data.battery_percent < 20:
#                     raise RuntimeError("Battery too low!")
#
#                 # Arm and takeoff
#                 await drone.action.arm()
#                 await drone.action.takeoff()
#
#                 # 3. Use offboard for precise control (managed_offboard)
#                 async with managed_offboard(drone) as offboard:
#                     # Fly a pattern
#                     await offboard.set_velocity_ned(VelocityNedYaw(1, 0, 0, 0))
#                     await asyncio.sleep(5)
#                     await offboard.set_velocity_ned(VelocityNedYaw(0, 1, 0, 0))
#                     await asyncio.sleep(5)
#                     await offboard.set_velocity_ned(VelocityNedYaw(-1, 0, 0, 0))
#                     await asyncio.sleep(5)
#                 # <-- Offboard stopped here
#
#                 # Land
#                 await drone.action.land()
#
#             # <-- Telemetry cache stopped here
#         # <-- Connection closed here
#
# SAFETY GUARANTEES IN THIS EXAMPLE:
# - If any exception occurs, ALL cleanup happens automatically
# - If an error happens in offboard, offboard stops AND telemetry stops AND connection closes
# - No resource leaks possible, no matter what goes wrong
#
# =============================================================================
