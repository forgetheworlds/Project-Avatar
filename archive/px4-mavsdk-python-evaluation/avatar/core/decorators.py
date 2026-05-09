"""Timeout and retry decorators for async operations.

Provides decorators for managing async operations with automatic timeout handling,
exponential backoff retry logic, and state machine validation.

================================================================================
WHAT ARE DECORATORS? (For Beginners)
================================================================================

Decorators are a Python feature that lets you "wrap" a function with another
function. Think of them like a sticker you put on a function that changes how
it behaves, without changing the function's code itself.

Basic concept:
    @some_decorator
    def my_function():
        pass

Is equivalent to:
    my_function = some_decorator(my_function)

Why use decorators?
1. Reuse code - Write the logic once, apply it to many functions
2. Keep functions clean - Each function does one thing, decorators handle cross-cutting concerns
3. Add behavior transparently - Functions work the same way, but with added capabilities

Common use cases:
- Adding timeouts (this file!)
- Retrying failed operations (this file!)
- Logging when functions are called
- Checking permissions before execution
- Caching results

================================================================================
HOW THESE DECORATORS WORK
================================================================================

All decorators in this file follow a similar pattern:

1. OUTER FUNCTION: Receives decorator arguments (like @timeout(5.0))
   - Returns the actual decorator

2. DECORATOR: Receives the function being decorated
   - Creates a wrapper function
   - Returns the wrapper

3. WRAPPER: Replaces the original function
   - Gets called instead of the original
   - Adds the new behavior (timeout, retry, etc.)
   - Calls the original function at the right time

The @functools.wraps decorator preserves the original function's name and docstring.

================================================================================
USAGE IN THIS PROJECT
================================================================================

These decorators are essential for drone operations because:

1. NETWORK OPERATIONS ARE UNRELIABLE
   - Drone commands go over WiFi/MAVLink
   - Packets can be lost, connections can drop
   - Retry logic ensures commands eventually get through

2. OPERATIONS MUST NOT HANG FOREVER
   - If a drone doesn't respond, we need to know quickly
   - Timeout prevents infinite waiting
   - Critical for safety and responsiveness

3. STATE VALIDATION PREVENTS CRASHES
   - Can't take off if already flying
   - Can't land if not airborne
   - State checking prevents dangerous operations

Example from this codebase:
    @retry(max_attempts=3, delay_s=0.5)
    @timeout(5.0)
    async def arm_drone():
        # If this fails, retry up to 3 times
        # If it takes longer than 5 seconds, raise TimeoutError
        pass
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

# TypeVar is a generic type marker. F represents any callable (function/method).
# This helps type checkers understand that the decorator preserves the function signature.
F = TypeVar("F", bound=Callable[..., Any])


class StateError(Exception):
    """Raised when operation not allowed in current state.

    Example: Trying to land when drone is already on ground.
    """

    pass


def timeout(
    seconds: float,
    exception_class: type = asyncio.TimeoutError,
    message: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator that adds timeout to async function.

    WHAT IT DOES:
    -------------
    Wraps an async function so that if it takes longer than 'seconds',
    it raises an exception instead of waiting forever.

    HOW IT WORKS:
    -------------
    1. The outer function (timeout) receives the configuration (seconds, etc.)
    2. It returns a 'decorator' function that will receive the actual function
    3. The decorator creates a 'wrapper' async function
    4. The wrapper uses asyncio.wait_for() to enforce the time limit
    5. If the function finishes in time, return its result
    6. If time expires, raise the specified exception with a descriptive message

    WHY IT'S USEFUL FOR DRONES:
    ---------------------------
    - Network delays can make operations hang indefinitely
    - We need to detect failures quickly for safety
    - User expects responsiveness - 30 seconds with no response is bad UX
    - Allows fallback behavior: "If no response in 5s, try alternative"

    Args:
        seconds: Timeout in seconds. Function must complete within this time.
        exception_class: Exception to raise on timeout. Default: asyncio.TimeoutError
        message: Custom timeout message. Default: "{function_name} timed out after {seconds}s"

    Returns:
        Decorated function with timeout enforcement

    EXAMPLES:
    ---------

    Basic usage - 5 second timeout:

        @timeout(5.0)
        async def fetch_data() -> dict:
            # If this takes longer than 5 seconds, raises TimeoutError
            data = await drone.get_telemetry()
            return data

    Custom message for debugging:

        @timeout(2.0, message="Connection to drone timed out - check WiFi")
        async def connect_drone() -> bool:
            await drone.connect()
            return True

    Custom exception type:

        class DroneConnectionError(Exception):
            pass

        @timeout(10.0, exception_class=DroneConnectionError)
        async def critical_operation():
            # Raises DroneConnectionError instead of TimeoutError
            pass

    Real-world drone example:

        @timeout(3.0, message="Arm command timeout - check safety switch")
        async def arm_drone(drone: System) -> None:
            # PX4 requires safety switch or parameter to arm
            # If pilot hasn't pressed safety switch, this could hang
            await drone.action.arm()
    """

    def decorator(func: F) -> F:
        # @functools.wraps preserves the original function's metadata
        # Without this, wrapper.__name__ would be "wrapper" instead of the real function name
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # asyncio.wait_for runs the coroutine with a deadline
            # If the deadline passes, it raises asyncio.TimeoutError
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                # Create a descriptive message for debugging
                msg = message or f"{func.__name__} timed out after {seconds}s"
                # Raise the user-specified exception class (or default TimeoutError)
                raise exception_class(msg)

        return wrapper  # type: ignore[return-value]

    return decorator


def retry(
    max_attempts: int = 3,
    delay_s: float = 1.0,
    backoff: float = 2.0,
    exceptions: Optional[Tuple[type[BaseException], ...]] = None,
) -> Callable[[F], F]:
    """Decorator that retries async function on failure.

    WHAT IT DOES:
    -------------
    If the decorated function raises an exception, wait a bit, then try again.
    Keeps trying up to max_attempts times before giving up and raising the error.

    HOW IT WORKS:
    -------------
    1. The wrapper loops from 1 to max_attempts
    2. On each iteration, it tries to run the original function
    3. If successful, returns the result immediately
    4. If an exception occurs:
       - If this was the last attempt, re-raise the exception
       - Otherwise, log the failure, wait 'delay_s' seconds, then retry
       - Multiply delay by 'backoff' for exponential backoff (1s, 2s, 4s, 8s...)

    EXPONENTIAL BACKOFF EXPLAINED:
    ------------------------------
    Instead of waiting the same time between retries, we double the wait each time.
    This prevents overwhelming a struggling system while still retrying quickly at first.

    With delay_s=1.0 and backoff=2.0:
        Attempt 1 fails -> wait 1.0 seconds -> try again
        Attempt 2 fails -> wait 2.0 seconds -> try again
        Attempt 3 fails -> wait 4.0 seconds -> try again
        Attempt 4 fails -> give up, raise the exception

    WHY IT'S USEFUL FOR DRONES:
    ---------------------------
    - MAVLink packets can be lost due to interference
    - WiFi connections can be flaky
    - Transient failures are common in robotics
    - Better to retry 3 times than fail immediately
    - Essential for autonomous operations with no human operator

    Args:
        max_attempts: Maximum number of attempts. Must be >= 1.
        delay_s: Initial delay between retries in seconds. First retry waits this long.
        backoff: Multiplier for delay after each failure. 2.0 = double each time.
        exceptions: Tuple of exceptions to catch and retry. Default: catch all Exception.

    Returns:
        Decorated function with retry logic

    EXAMPLES:
    ---------

    Basic retry - 3 attempts with 1 second delay:

        @retry(max_attempts=3, delay_s=1.0)
        async def send_command() -> bool:
            # If this fails, waits 1s, tries again
            # If fails again, waits 1s, tries again
            # If fails third time, raises the exception
            await drone.action.takeoff()
            return True

    Exponential backoff for network calls:

        @retry(max_attempts=5, delay_s=0.5, backoff=2.0)
        async def upload_mission():
            # Retry quickly at first (0.5s), then slower (1s, 2s, 4s)
            # Good for operations that might temporarily overload the system
            await drone.mission.upload_mission(mission_plan)

    Retry only specific exceptions:

        @retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        async def connect():
            # Only retries on ConnectionError or TimeoutError
            # ValueError or other exceptions are raised immediately
            await drone.connect()

    Real-world drone example - GPS command with retries:

        @retry(
            max_attempts=5,
            delay_s=0.5,
            backoff=1.5,
            exceptions=(CommandError,)
        )
        async def set_gps_origin(drone: System, lat: float, lon: float) -> None:
            # GPS commands can fail if satellites not yet acquired
            # Retry with increasing delays to give GPS time to lock
            await drone.param.set_param_float("GPS_LAT", lat)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Track delay for exponential backoff
            current_delay = delay_s
            # If no exceptions specified, catch all Exception types
            retry_exceptions = exceptions if exceptions is not None else (Exception,)

            # Loop through attempts
            for attempt in range(1, max_attempts + 1):
                try:
                    # Try to execute the function
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    # The function raised an exception we should retry on
                    if attempt == max_attempts:
                        # This was the last attempt - log and raise
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Not the last attempt - log warning and retry
                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    # Wait before next attempt
                    await asyncio.sleep(current_delay)
                    # Increase delay for next attempt (exponential backoff)
                    current_delay *= backoff

            # Should never reach here - we either return or raise above
            raise RuntimeError(f"Retry loop exhausted for {func.__name__}")

        return wrapper  # type: ignore[return-value]

    return decorator


def require_state(
    state_machine_getter: Callable[[], Any],
    *valid_states: str,
) -> Callable[[F], F]:
    """Decorator that validates state machine state before execution.

    WHAT IT DOES:
    -------------
    Checks that the drone (or system) is in an allowed state before executing
    the function. If not, raises StateError immediately without running the function.

    HOW IT WORKS:
    -------------
    1. The decorator receives a callable that returns the state machine instance
    2. It also receives a list of valid state names (e.g., "HOVERING", "FLYING")
    3. When the decorated function is called:
       - Get the current state machine via state_machine_getter()
       - Check if current_state_name is in valid_states
       - If not, raise StateError with a helpful message
       - If yes, execute the original function normally

    WHY IT'S USEFUL FOR DRONES:
    ---------------------------
    - Prevents dangerous operations (landing while already on ground)
    - Enforces state machine rules automatically
    - Catches bugs early - fail fast instead of undefined behavior
    - Self-documents which states allow which operations
    - Essential for safety-critical autonomous systems

    Args:
        state_machine_getter: Callable that returns the state machine instance.
                             Usually a lambda or function reference.
        *valid_states: State names that permit execution. Variable arguments.

    Returns:
        Decorated function with state validation

    Raises:
        StateError: If current state is not in valid_states

    EXAMPLES:
    ---------

    Basic state checking:

        def get_state_machine():
            return drone.state_machine

        @require_state(get_state_machine, "HOVERING", "FLYING")
        async def set_velocity(north: float, east: float) -> bool:
            # Only executes if drone is HOVERING or FLYING
            # Raises StateError if drone is LANDED, TAKING_OFF, etc.
            await drone.offboard.set_velocity_ned(north, east, 0)
            return True

    Using lambda for cleaner syntax:

        @require_state(lambda: drone.state_machine, "LANDED")
        async def arm() -> None:
            # Only arm if safely on ground
            await drone.action.arm()

    Multiple valid states:

        @require_state(get_drone_sm, "HOVERING", "FLYING", "MISSION")
        async def take_photo() -> bytes:
            # Can take photos while hovering, flying, or in mission mode
            return await camera.capture()

    Real-world drone example - Safe takeoff:

        @require_state(lambda: drone.state_machine, "LANDED")
        async def takeoff(drone: System, altitude: float) -> None:
            # Safety: Prevent takeoff if already flying
            # This catches programming errors where takeoff() is called twice
            await drone.action.takeoff()
            await drone.set_altitude(altitude)

    Error handling:

        @require_state(get_sm, "FLYING")
        async def land() -> None:
            await drone.action.land()

        try:
            await land()
        except StateError as e:
            print(f"Cannot land: {e}")  # "Cannot execute land in state HOVERING..."
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get the state machine instance
            sm = state_machine_getter()
            # Get current state name
            current = sm.current_state_name

            # Check if current state is allowed
            if current not in valid_states:
                # Not in a valid state - raise descriptive error
                raise StateError(
                    f"Cannot execute {func.__name__} in state {current}. "
                    f"Required: {valid_states}"
                )

            # State is valid - execute the function
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def combined(
    timeout_seconds: float,
    max_attempts: int = 3,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    retry_exceptions: Optional[Tuple[type[BaseException], ...]] = None,
) -> Callable[[F], F]:
    """Combined decorator with timeout and retry functionality.

    WHAT IT DOES:
    -------------
    Applies both timeout and retry in a single decorator. Each retry attempt
    gets its own timeout. This is the most common pattern for drone operations.

    HOW IT WORKS:
    -------------
    1. Creates a timeout-decorated version of the function first (inner layer)
    2. Wraps that with retry logic (outer layer)
    3. Result: Each attempt has a time limit, and failed attempts are retried

    Execution flow for @combined(timeout_seconds=5.0, max_attempts=3):

        Call function
            -> Start Attempt 1
                -> Start 5-second timer
                -> Execute function
                -> If timeout: raise TimeoutError -> caught by retry
                -> If success: return result
            -> If Attempt 1 failed:
                -> Wait retry_delay seconds
                -> Start Attempt 2 with fresh 5-second timer
                -> ...repeat...
            -> If all 3 attempts fail: raise final exception

    WHY IT'S USEFUL FOR DRONES:
    ---------------------------
    - Most drone operations need BOTH guarantees:
      * "Don't wait forever" (timeout)
      * "Don't give up on first failure" (retry)
    - Network operations are both slow AND unreliable
    - This decorator combines both patterns cleanly
    - Reduces boilerplate in drone command methods

    Args:
        timeout_seconds: Timeout for each individual attempt. Must be > 0.
        max_attempts: Maximum retry attempts. Default: 3.
        retry_delay: Initial delay between retries in seconds. Default: 1.0.
        retry_backoff: Backoff multiplier for retry delays. Default: 2.0.
        retry_exceptions: Exceptions to catch and retry. Default: all Exception.

    Returns:
        Decorated function with combined timeout and retry logic

    EXAMPLES:
    ---------

    Basic combined usage:

        @combined(timeout_seconds=5.0, max_attempts=3)
        async def connect_with_retry() -> bool:
            # Tries up to 3 times
            # Each attempt has a 5 second timeout
            await drone.connect()
            return True

    Tuned for quick operations:

        @combined(timeout_seconds=1.0, max_attempts=5, retry_delay=0.2)
        async def send_heartbeat():
            # Fast timeout (1s), many retries (5), quick between retries (0.2s)
            await drone.send_heartbeat()

    Tuned for slow operations:

        @combined(
            timeout_seconds=30.0,
            max_attempts=2,
            retry_delay=5.0,
            retry_backoff=1.0  # No exponential backoff, consistent 5s delay
        )
        async def upload_mission(mission: MissionPlan):
            # Mission upload can be slow, give it 30s
            # Only retry once after 5 seconds
            await drone.mission.upload_mission(mission)

    Real-world drone example - Critical connection:

        @combined(
            timeout_seconds=10.0,
            max_attempts=5,
            retry_delay=2.0,
            retry_backoff=2.0,
            retry_exceptions=(ConnectionError, asyncio.TimeoutError)
        )
        async def establish_connection(drone: System, address: str) -> None:
            # Critical: Connection must succeed for mission to work
            # - Each attempt gets 10 seconds
            # - Retry up to 5 times (50 seconds total max)
            # - Exponential backoff: 2s, 4s, 8s, 16s between attempts
            # - Only retry on connection/timeout errors
            await drone.connect(system_address=address)

    STACKING DECORATORS EXPLAINED:
    ------------------------------

    You can stack decorators manually instead of using combined:

        @retry(max_attempts=3)
        @timeout(5.0)
        async def my_func():
            pass

    Order matters! Decorators execute bottom-to-top:

        @retry      <-- 3. Retry catches timeout, waits, tries again
        @timeout    <-- 2. Timeout wraps the function, limits execution time
        async def   <-- 1. Original function

    So combined(timeout, retry) creates: retry(timeout(function))

    This is correct: timeout first, then retry wrapping it.
    """

    def decorator(func: F) -> F:
        # Apply timeout first (inner layer)
        # This creates: timed_func = timeout(timeout_seconds)(func)
        timed_func = timeout(timeout_seconds)(func)

        # Apply retry on top (outer layer)
        # This creates: retry_wrapper = retry(...)(timed_func)
        return retry(
            max_attempts=max_attempts,
            delay_s=retry_delay,
            backoff=retry_backoff,
            exceptions=retry_exceptions,
        )(timed_func)

    return decorator


# ================================================================================
# DECORATOR QUICK REFERENCE
# ================================================================================
#
# @timeout(seconds)
#     - Fails if function takes longer than 'seconds'
#     - Good for: API calls, connections, any operation that might hang
#
# @retry(max_attempts, delay_s, backoff, exceptions)
#     - Retries on failure with exponential backoff
#     - Good for: Network operations, flaky hardware, transient failures
#
# @require_state(getter, *states)
#     - Validates state machine before execution
#     - Good for: Enforcing safety rules, preventing invalid operations
#
# @combined(timeout_seconds, max_attempts, ...)
#     - Timeout + Retry in one decorator
#     - Good for: Most drone operations (the default choice)
#
# ================================================================================
# DECORATOR COMBINATION PATTERNS
# ================================================================================
#
# Pattern 1: Combined (recommended for most operations)
#     @combined(timeout_seconds=5.0, max_attempts=3)
#     async def drone_command():
#         pass
#
# Pattern 2: State + Combined (safety-critical operations)
#     @require_state(get_sm, "FLYING")
#     @combined(timeout_seconds=3.0, max_attempts=3)
#     async def safe_flying_command():
#         pass
#
# Pattern 3: Timeout only (when you don't want retries)
#     @timeout(10.0)
#     async def one_shot_operation():
#         pass
#
# Pattern 4: Retry only (when there's no risk of hanging)
#     @retry(max_attempts=5)
#     async def non_blocking_operation():
#         pass
#
# ================================================================================
