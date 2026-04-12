"""Timeout and retry decorators for async operations.

Provides decorators for managing async operations with automatic timeout handling,
exponential backoff retry logic, and state machine validation.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class StateError(Exception):
    """Raised when operation not allowed in current state."""

    pass


def timeout(
    seconds: float,
    exception_class: type = asyncio.TimeoutError,
    message: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator that adds timeout to async function.

    Args:
        seconds: Timeout in seconds
        exception_class: Exception to raise on timeout
        message: Custom timeout message

    Returns:
        Decorated function with timeout enforcement

    Example:
        @timeout(5.0)
        async def fetch_data() -> dict:
            # ... async operation ...
            return data

        @timeout(2.0, message="Connection to drone timed out")
        async def connect_drone() -> bool:
            # ... connection logic ...
            return True
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                msg = message or f"{func.__name__} timed out after {seconds}s"
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

    Args:
        max_attempts: Maximum number of attempts
        delay_s: Initial delay between retries in seconds
        backoff: Multiplier for delay after each failure
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry(max_attempts=3, delay_s=0.5)
        async def send_command() -> bool:
            # ... may fail temporarily ...
            return True
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay_s
            retry_exceptions = exceptions if exceptions is not None else (Exception,)

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # Should never reach here
            raise RuntimeError(f"Retry loop exhausted for {func.__name__}")

        return wrapper  # type: ignore[return-value]

    return decorator


def require_state(
    state_machine_getter: Callable[[], Any],
    *valid_states: str,
) -> Callable[[F], F]:
    """Decorator that validates state machine state before execution.

    Args:
        state_machine_getter: Callable that returns state machine instance
        valid_states: State names that permit execution

    Returns:
        Decorated function with state validation

    Raises:
        StateError: If current state is not in valid_states

    Example:
        def get_state_machine():
            return drone.state_machine

        @require_state(get_state_machine, "HOVERING", "FLYING")
        async def set_velocity(north: float, east: float) -> bool:
            # Only executes if in HOVERING or FLYING state
            return True
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            sm = state_machine_getter()
            current = sm.current_state_name

            if current not in valid_states:
                raise StateError(
                    f"Cannot execute {func.__name__} in state {current}. "
                    f"Required: {valid_states}"
                )

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

    Applies both timeout and retry decorators in a single decorator.
    The function will be retried with backoff, and each attempt
    will have the specified timeout.

    Args:
        timeout_seconds: Timeout for each attempt
        max_attempts: Maximum retry attempts
        retry_delay: Initial delay between retries
        retry_backoff: Backoff multiplier for retry delays
        retry_exceptions: Exceptions to catch and retry

    Returns:
        Decorated function with combined timeout and retry logic

    Example:
        @combined(timeout_seconds=5.0, max_attempts=3)
        async def connect_with_retry() -> bool:
            # Tries up to 3 times, each with 5 second timeout
            return True
    """

    def decorator(func: F) -> F:
        # Apply timeout first (inner), then retry (outer)
        timed_func = timeout(timeout_seconds)(func)
        return retry(
            max_attempts=max_attempts,
            delay_s=retry_delay,
            backoff=retry_backoff,
            exceptions=retry_exceptions,
        )(timed_func)

    return decorator
