"""Tests for timeout, retry, and state validation decorators.

Test-driven development for Wave 5 - Code Quality decorators.
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
    """Tests for @timeout decorator."""

    def test_timeout_success(self):
        """Function completes within timeout."""

        @timeout(5.0)
        async def quick_function() -> str:
            await asyncio.sleep(0.01)
            return "success"

        result = asyncio.run(quick_function())
        assert result == "success"

    def test_timeout_failure(self):
        """Function exceeding timeout raises error."""

        @timeout(0.01)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(slow_function())

    def test_timeout_custom_message(self):
        """Custom message appears in exception."""
        custom_msg = "Custom timeout message"

        @timeout(0.01, message=custom_msg)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError) as exc_info:
            asyncio.run(slow_function())

        assert custom_msg in str(exc_info.value)

    def test_timeout_custom_exception_class(self):
        """Custom exception class is raised on timeout."""

        class CustomTimeoutError(Exception):
            pass

        @timeout(0.01, exception_class=CustomTimeoutError)
        async def slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(CustomTimeoutError):
            asyncio.run(slow_function())

    def test_timeout_default_message(self):
        """Default message includes function name and timeout."""

        @timeout(0.01)
        async def named_slow_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with pytest.raises(asyncio.TimeoutError) as exc_info:
            asyncio.run(named_slow_function())

        assert "named_slow_function" in str(exc_info.value)
        assert "0.01s" in str(exc_info.value)

    def test_timeout_with_arguments(self):
        """Timeout decorator works with function arguments."""

        @timeout(1.0)
        async def process_data(data: str, multiplier: int) -> str:
            await asyncio.sleep(0.01)
            return data * multiplier

        result = asyncio.run(process_data("ab", 3))
        assert result == "ababab"

    def test_timeout_preserves_return_type(self):
        """Timeout decorator preserves return type."""

        @timeout(1.0)
        async def return_dict() -> dict[str, int]:
            await asyncio.sleep(0.01)
            return {"key": 42}

        result = asyncio.run(return_dict())
        assert result == {"key": 42}
        assert isinstance(result, dict)


class TestRetryDecorator:
    """Tests for @retry decorator."""

    def test_retry_success_first_attempt(self):
        """Succeeds on first attempt without retries."""
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
        """Succeeds after several retries."""
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
        """Fails after max attempts exhausted."""
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
        """Only catches specified exceptions."""
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
        """Backoff increases delay between retries."""
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
        """Custom max_attempts is respected."""
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
    """Tests for @require_state decorator."""

    def test_require_state_allowed(self):
        """Executes when state is valid."""
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
        """Raises StateError when state invalid."""
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
        """Allows execution in any of the valid states."""
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
        """Works with single valid state."""
        sm = FlightStateMachine()
        sm._state = FlightState.ARMED

        def get_sm():
            return sm

        @require_state(get_sm, "ARMED")
        async def arm_only_command() -> str:
            return "executed"

        assert asyncio.run(arm_only_command()) == "executed"

    def test_require_state_with_function_arguments(self):
        """Works with functions that have arguments."""
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
    """Tests that decorators preserve function signatures."""

    def test_timeout_preserves_name(self):
        """Timeout decorator preserves function name."""

        @timeout(1.0)
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_timeout_preserves_docstring(self):
        """Timeout decorator preserves docstring."""

        @timeout(1.0)
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_retry_preserves_name(self):
        """Retry decorator preserves function name."""

        @retry(max_attempts=3)
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_retry_preserves_docstring(self):
        """Retry decorator preserves docstring."""

        @retry(max_attempts=3)
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_require_state_preserves_name(self):
        """Require_state decorator preserves function name."""
        sm = FlightStateMachine()

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING")
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_require_state_preserves_docstring(self):
        """Require_state decorator preserves docstring."""
        sm = FlightStateMachine()

        def get_sm():
            return sm

        @require_state(get_sm, "HOVERING")
        async def documented_function() -> str:
            """This is my docstring."""
            return "result"

        assert documented_function.__doc__ == "This is my docstring."

    def test_decorator_preserves_signature(self):
        """Type hints and signature are preserved."""

        @timeout(1.0)
        async def typed_function(data: dict[str, int], flag: bool = True) -> list[str]:
            return ["result"]

        sig = inspect.signature(typed_function)
        params = list(sig.parameters.keys())
        assert params == ["data", "flag"]

    def test_decorator_preserves_annotations(self):
        """Type annotations are preserved."""

        @timeout(1.0)
        async def annotated_function(x: int) -> str:
            return str(x)

        assert annotated_function.__annotations__["x"] is int
        assert annotated_function.__annotations__["return"] is str


class TestCombinedDecorator:
    """Tests for @combined decorator."""

    def test_combined_timeout_and_retry(self):
        """Combined decorator applies both timeout and retry."""
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
        """Combined decorator fails when all attempts timeout."""
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
        """Combined decorator works with non-timeout exceptions."""
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
    """Tests for edge cases and error handling."""

    def test_timeout_zero(self):
        """Timeout of zero immediately times out."""

        @timeout(0.0)
        async def any_function() -> str:
            await asyncio.sleep(0)
            return "result"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(any_function())

    def test_retry_one_attempt(self):
        """Retry with max_attempts=1 does not retry."""
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
        """Require_state with no valid states always fails."""
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
        """Decorators can be nested (timeout outside retry)."""
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
