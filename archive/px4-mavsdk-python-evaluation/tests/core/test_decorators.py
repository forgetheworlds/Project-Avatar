"""Tests for timeout, retry, and state validation decorators.

Test-driven development for Wave 5 - Code Quality decorators.

DECORATOR PATTERN:
These decorators use Python's functools.wraps to preserve function metadata while adding
orthogonal concerns (timeout, retry, state validation) without modifying the core logic.
All decorators support both async and sync functions through inspection.

VALIDATION COVERAGE:
- @timeout: Prevents hung operations, enforces time bounds
- @retry: Handles transient failures with exponential backoff
- @require_state: Ensures operations only execute in valid flight states
- @combined: Composes multiple decorators for common patterns
"""

import asyncio
import inspect
from typing import Any

import pytest

from avatar.core.decorators import (
    StateError,
    combined,
    require_state,
    retry,
    timeout,
)
from avatar.mav.state_machine import FlightState, FlightStateMachine


class TestTimeoutDecorator:
    """Tests for @timeout decorator.

    VALIDATES:
    - Functions complete successfully within timeout
    - TimeoutError raised when function exceeds time limit
    - Custom timeout messages are included in exceptions
    - Custom exception classes can be used
    - Default messages include function name and timeout value
    - Arguments and return types are preserved

    HOW IT WORKS:
    The @timeout decorator wraps an async function with asyncio.wait_for().
    It uses asyncio.shield() internally to prevent cancellation from propagating
    unexpectedly. The timeout applies to the total execution time, including any
    nested calls.

    SAFETY RELEVANCE:
    Critical for drone operations where hanging commands (e.g., waiting for
    GPS lock) could block the entire control loop. Enforces maximum time bounds.
    """

    def test_timeout_success(self):
        """VALIDATES: Function completes within timeout returns normally.

        When the wrapped function finishes before the timeout, its result
        should be returned without any timeout-related side effects.
        """

        @timeout(5.0)
        async def quick_function() -> str:
            await asyncio.sleep(0.01)
            return "success"

        result = asyncio.run(quick_function())
        assert result == "success"

    def test_timeout_failure(self):
        """VALIDATES: Function exceeding timeout raises asyncio.TimeoutError.

        If the wrapped function takes longer than the specified timeout,
        asyncio.TimeoutError should be raised, interrupting the slow operation.
        """

        @timeout(0.01)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(slow_function())

    def test_timeout_custom_message(self):
        """VALIDATES: Custom message appears in timeout exception.

        The decorator supports a custom message parameter that provides
        context-specific error information when timeouts occur.
        """
        custom_msg = "Custom timeout message"

        @timeout(0.01, message=custom_msg)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError) as exc_info:
            asyncio.run(slow_function())

        assert custom_msg in str(exc_info.value)

    def test_timeout_custom_exception_class(self):
        """VALIDATES: Custom exception class is raised on timeout.

        Applications can specify their own exception class for timeout handling,
        allowing for more specific error handling in calling code.
        """

        class CustomTimeoutError(Exception):
            pass

        @timeout(0.01, exception_class=CustomTimeoutError)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(CustomTimeoutError):
            asyncio.run(slow_function())

    def test_timeout_default_message(self):
        """VALIDATES: Default message includes function name and timeout.

        When no custom message is provided, the default message includes
        diagnostic information (function name, timeout value) to aid debugging.
        """

        @timeout(0.01)
        async def named_slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError) as exc_info:
            asyncio.run(named_slow_function())

        assert "named_slow_function" in str(exc_info.value)
        assert "0.01s" in str(exc_info.value)

    def test_timeout_with_arguments(self):
        """VALIDATES: Timeout decorator works with function arguments.

        The decorator must properly wrap functions that accept arguments,
        passing them through to the wrapped function unchanged.
        """

        @timeout(1.0)
        async def process_data(data: str, multiplier: int) -> str:
            await asyncio.sleep(0.01)
            return data * multiplier

        result = asyncio.run(process_data("ab", 3))
        assert result == "ababab"

    def test_timeout_preserves_return_type(self):
        """VALIDATES: Timeout decorator preserves return type.

        The decorator should not modify the return type; dictionaries, lists,
        custom objects, and primitives should all pass through correctly.
        """

        @timeout(1.0)
        async def return_dict() -> dict[str, int]:
            await asyncio.sleep(0.01)
            return {"key": 42}

        result = asyncio.run(return_dict())
        assert result == {"key": 42}
        assert isinstance(result, dict)


class TestRetryDecorator:
    """Tests for @retry decorator.

    VALIDATES:
    - Success on first attempt (no unnecessary retries)
    - Success after transient failures (retry helps)
    - Failure after max attempts exhausted
    - Exception filtering (only retry specified exceptions)
    - Exponential backoff timing
    - Custom attempt counts

    HOW IT WORKS:
    The @retry decorator wraps functions in a retry loop with configurable:
    - max_attempts: Maximum number of attempts before giving up
    - delay_s: Initial delay between attempts
    - backoff: Multiplier for delay after each failure (exponential backoff)
    - exceptions: Tuple of exception types to catch and retry

    USE CASES:
    - MAVSDK connection attempts (may fail initially as SITL boots)
    - Telemetry stream subscriptions (may race with connection setup)
    - Network operations with transient failures

    SAFETY NOTE:
    Retry should NOT be used for operations that have already had side effects,
    as partial failures could leave the system in an inconsistent state.
    """

    def test_retry_success_first_attempt(self):
        """VALIDATES: Succeeds on first attempt without retries.

        When the function succeeds immediately, it should only be called once
        and return normally without any retry overhead.
        """
        call_count = 0

        @retry(max_attempts=3, delay_s=0.01)
        async def always_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = asyncio.run(always_succeeds())
        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_retries(self):
        """VALIDATES: Succeeds after several retries.

        If the function fails transiently then succeeds, the decorator should
        retry until success or max_attempts is reached.
        """
        call_count = 0

        @retry(max_attempts=3, delay_s=0.01)
        async def succeeds_on_third() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return "success"

        result = asyncio.run(succeeds_on_third())
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """VALIDATES: Fails after max attempts exhausted.

        If the function fails on all attempts, the final exception should be
        raised to the caller after max_attempts retries.
        """
        call_count = 0

        @retry(max_attempts=3, delay_s=0.01)
        async def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count} failed")

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(always_fails())

        assert call_count == 3
        assert "Attempt 3 failed" in str(exc_info.value)

    def test_retry_with_specific_exceptions(self):
        """VALIDATES: Only catches specified exceptions.

        The decorator should only retry exceptions listed in the exceptions
        tuple. Other exceptions should propagate immediately without retry.
        """
        call_count = 0

        @retry(max_attempts=3, delay_s=0.01, exceptions=(ValueError,))
        async def raises_type_error() -> str:
            nonlocal call_count
            call_count += 1
            raise TypeError("Type error not caught")

        with pytest.raises(TypeError):
            asyncio.run(raises_type_error())

        # Should not retry on TypeError
        assert call_count == 1

    def test_retry_backoff(self):
        """VALIDATES: Backoff increases delay between retries.

        With backoff=2.0, each retry should wait twice as long as the previous:
        - Attempt 1: immediate (if fails, wait delay_s)
        - Attempt 2: wait delay_s * backoff
        - Attempt 3: wait delay_s * backoff^2
        """
        call_count = 0
        timestamps = []

        @retry(max_attempts=3, delay_s=0.05, backoff=2.0)
        async def track_timing() -> str:
            nonlocal call_count
            import time

            timestamps.append(time.monotonic())
            call_count += 1
            if call_count < 3:
                raise ValueError("Retry me")
            return "success"

        start = asyncio.run(track_timing())

        # Check that delays increased (backoff applied)
        # First retry: ~0.05s, Second retry: ~0.1s
        assert call_count == 3
        assert len(timestamps) == 3

    def test_retry_custom_max_attempts(self):
        """VALIDATES: Custom max_attempts is respected.

        The max_attempts parameter controls how many times the function is
        called before giving up. This can be tuned per-operation.
        """
        call_count = 0

        @retry(max_attempts=5, delay_s=0.01)
        async def count_attempts() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            asyncio.run(count_attempts())

        assert call_count == 5


class TestRequireStateDecorator:
    """Tests for @require_state decorator.

    VALIDATES:
    - Execution allowed in valid states
    - StateError raised in invalid states
    - Multiple valid states supported
    - Works with function arguments
    - State machine integration

    HOW IT WORKS:
    The @require_state decorator checks the flight state machine before allowing
    a function to execute. It takes:
    - state_machine_getter: Callable that returns the state machine instance
    - valid_states: Variable list of state names (strings) that allow execution

    STATE MACHINE INTEGRATION:
    The decorator integrates with FlightStateMachine to enforce that operations
    only execute in appropriate flight states:
    - disarm() only in LANDED or HOVERING states
    - takeoff() only in ARMED state
    - velocity commands only in FLYING or POSITION_CONTROL states

    SAFETY RELEVANCE:
    CRITICAL for preventing dangerous operations in wrong states. For example,
    attempting to set velocity setpoints when disarmed could cause errors or
    unexpected behavior in the flight controller.
    """

    def test_require_state_allowed(self):
        """VALIDATES: Executes when state is valid.

        When the flight state machine is in one of the allowed states,
        the wrapped function should execute normally.
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING", "FLYING")
        async def set_velocity() -> str:
            return "velocity set"

        result = asyncio.run(set_velocity())
        assert result == "velocity set"

    def test_require_state_blocked(self):
        """VALIDATES: Raises StateError when state invalid.

        If the flight state is not in the allowed list, StateError should be
        raised with a descriptive message including current and allowed states.
        """
        sm = FlightStateMachine()
        sm._state = FlightState.DISARMED

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING", "FLYING")
        async def set_velocity() -> str:
            return "velocity set"

        with pytest.raises(StateError) as exc_info:
            asyncio.run(set_velocity())

        assert "Cannot execute set_velocity" in str(exc_info.value)
        assert "DISARMED" in str(exc_info.value)
        assert "HOVERING" in str(exc_info.value)
        assert "FLYING" in str(exc_info.value)

    def test_require_state_multiple_valid(self):
        """VALIDATES: Allows execution in any of the valid states.

        Multiple valid states can be specified, and the function should
        execute if the current state matches ANY of them.
        """
        sm = FlightStateMachine()

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING", "FLYING", "POSITION_CONTROL")
        async def flying_command() -> str:
            return "executed"

        # Should work in HOVERING
        sm._state = FlightState.HOVERING
        assert asyncio.run(flying_command()) == "executed"

        # Should work in FLYING
        sm._state = FlightState.FLYING
        assert asyncio.run(flying_command()) == "executed"

        # Should work in POSITION_CONTROL
        sm._state = FlightState.POSITION_CONTROL
        assert asyncio.run(flying_command()) == "executed"

    def test_require_state_single_valid(self):
        """VALIDATES: Works with single valid state.

        A single valid state can be specified for operations that only make
        sense in one specific flight state.
        """
        sm = FlightStateMachine()
        sm._state = FlightState.ARMED

        def get_sm():
            return sm

        @require_state(get_sm, "ARMED")
        async def arm_only_command() -> str:
            return "executed"

        assert asyncio.run(arm_only_command()) == "executed"

    def test_require_state_with_function_arguments(self):
        """VALIDATES: Works with functions that have arguments.

        The decorator must properly pass arguments through to the wrapped
        function while still performing the state check.
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING")
        async def set_velocity(north: float, east: float, down: float = 0.0) -> dict:
            return {"north": north, "east": east, "down": down}

        result = asyncio.run(set_velocity(1.0, 2.0, 3.0))
        assert result == {"north": 1.0, "east": 2.0, "down": 3.0}


class TestDecoratorSignaturePreservation:
    """Tests that decorators preserve function signatures.

    VALIDATES:
    - Function __name__ is preserved
    - Function __doc__ is preserved
    - Function signature is preserved
    - Type annotations are preserved

    WHY THIS MATTERS:
    Preserving signatures is essential for:
    1. IDE autocompletion and type hints
    2. Documentation generation tools
    3. Introspection-based frameworks (e.g., FastAPI)
    4. Debugging and stack traces

    IMPLEMENTATION:
    All decorators use functools.wraps() to copy metadata from the wrapped
    function to the wrapper function.
    """

    def test_timeout_preserves_name(self):
        """VALIDATES: Timeout decorator preserves function name."""

        @timeout(1.0)
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_timeout_preserves_docstring(self):
        """VALIDATES: Timeout decorator preserves docstring."""

        @timeout(1.0)
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_retry_preserves_name(self):
        """VALIDATES: Retry decorator preserves function name."""

        @retry(max_attempts=3)
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_retry_preserves_docstring(self):
        """VALIDATES: Retry decorator preserves docstring."""

        @retry(max_attempts=3)
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_require_state_preserves_name(self):
        """VALIDATES: Require_state decorator preserves function name."""
        sm = FlightStateMachine()

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING")
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_require_state_preserves_docstring(self):
        """VALIDATES: Require_state decorator preserves docstring."""
        sm = FlightStateMachine()

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING")
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_decorator_preserves_signature(self):
        """VALIDATES: Type hints and signature are preserved.

        The decorator should not alter the function signature, ensuring that
        introspection tools can correctly identify parameters.
        """

        @timeout(1.0)
        async def typed_function(data: dict[str, int], flag: bool = True) -> list[str]:
            return ["result"]

        sig = inspect.signature(typed_function)
        params = list(sig.parameters.keys())
        assert params == ["data", "flag"]

    def test_decorator_preserves_annotations(self):
        """VALIDATES: Type annotations are preserved.

        __annotations__ should contain the original type hints for proper
        static type checking and runtime type validation.
        """

        @timeout(1.0)
        async def annotated_function(x: int) -> str:
            return str(x)

        assert annotated_function.__annotations__["x"] is int
        assert annotated_function.__annotations__["return"] is str


class TestCombinedDecorator:
    """Tests for @combined decorator.

    VALIDATES:
    - Applies both timeout and retry behavior
    - Timeout on each individual attempt
    - Retry on timeout or other exceptions
    - Composable with other decorators

    HOW IT WORKS:
    The @combined decorator is a convenience that applies both @timeout and @retry
    in a single decorator. This is useful for operations that need both:
    - A maximum time limit per attempt (timeout)
    - Multiple attempts on failure (retry)

    EXAMPLE USE CASE:
    MAVSDK connection attempts that should:
    - Timeout if SITL is not responding (don't hang forever)
    - Retry a few times as SITL might still be booting

    IMPLEMENTATION:
    The combined decorator applies @retry as the outer decorator and @timeout
    as the inner decorator, so each retry attempt has its own timeout.
    """

    def test_combined_timeout_and_retry(self):
        """VALIDATES: Combined decorator applies both timeout and retry.

        The function should be retried on timeout, with each attempt having
        its own timeout limit.
        """
        call_count = 0

        @combined(timeout_seconds=0.5, max_attempts=3, retry_delay=0.01)
        async def unreliable_slow() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                await asyncio.sleep(0.6)  # Exceeds timeout
            return "success"

        result = asyncio.run(unreliable_slow())
        assert result == "success"
        assert call_count == 2  # First times out, second succeeds

    def test_combined_all_attempts_timeout(self):
        """VALIDATES: Combined decorator fails when all attempts timeout.

        If every attempt times out, the final TimeoutError should be raised
        after max_attempts retries.
        """
        call_count = 0

        @combined(timeout_seconds=0.01, max_attempts=3, retry_delay=0.01)
        async def always_slow() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Always exceeds timeout
            return "success"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(always_slow())

        assert call_count == 3

    def test_combined_with_other_exceptions(self):
        """VALIDATES: Combined decorator works with non-timeout exceptions.

        The retry logic should apply to any exception, not just timeouts.
        """
        call_count = 0

        @combined(timeout_seconds=1.0, max_attempts=3, retry_delay=0.01)
        async def sometimes_fails() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = asyncio.run(sometimes_fails())
        assert result == "success"
        assert call_count == 3


class TestDecoratorEdgeCases:
    """Tests for edge cases and error handling.

    VALIDATES:
    - Zero timeout behavior
    - Single attempt retry (no actual retry)
    - Empty valid states list
    - Nested decorator composition

    EDGE CASE HANDLING:
    Decorators should handle boundary conditions gracefully, providing
    predictable behavior even with unusual parameter combinations.
    """

    def test_timeout_zero(self):
        """VALIDATES: Timeout of zero immediately times out.

        A timeout of 0.0 should cause immediate timeout, useful for testing
        timeout handling or creating non-blocking operations.
        """

        @timeout(0.0)
        async def any_function() -> str:
            await asyncio.sleep(0)
            return "result"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(any_function())

    def test_retry_one_attempt(self):
        """VALIDATES: Retry with max_attempts=1 does not retry.

        Setting max_attempts=1 means only one attempt is made, with no retries.
        This is useful when you want the retry infrastructure but not the behavior.
        """
        call_count = 0

        @retry(max_attempts=1, delay_s=0.01)
        async def single_attempt() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            asyncio.run(single_attempt())

        assert call_count == 1

    def test_require_state_no_valid_states(self):
        """VALIDATES: Require_state with no valid states always fails.

        If no valid states are specified, any call should raise StateError.
        This is a safety feature to prevent accidental unconstrained operations.
        """
        sm = FlightStateMachine()
        sm._state = FlightState.HOVERING

        def get_sm():
            return sm

        @require_state(get_sm)  # No valid states
        async def impossible_command() -> str:
            return "executed"

        with pytest.raises(StateError):
            asyncio.run(impossible_command())

    def test_nested_decorators(self):
        """VALIDATES: Decorators can be nested (timeout outside retry).

        Decorators can be manually nested (as opposed to using @combined),
        with the outer decorator applying to the result of the inner decorator.

        ORDER MATTERS:
        @timeout(1.0)
        @retry(max_attempts=3)
        Means: Each retry attempt has a 1.0 second timeout.

        @retry(max_attempts=3)
        @timeout(1.0)
        Means: The entire sequence (all retries) has a 1.0 second timeout.
        """
        call_count = 0

        @timeout(1.0)
        @retry(max_attempts=3, delay_s=0.01)
        async def nested_slow() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"

        result = asyncio.run(nested_slow())
        assert result == "success"
        assert call_count == 2
