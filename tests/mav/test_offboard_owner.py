"""Tests for the OffboardOwner mutual exclusion system.

These tests verify:
- Mutual exclusion for PX4 offboard setpoint streaming
- Singleton pattern for consistent ownership across modules
- Thread-safe async acquire/release operations
- Re-entrant acquisition (same owner can reacquire)

================================================================================
WHY MUTUAL EXCLUSION MATTERS FOR FLIGHT SAFETY
================================================================================
PX4 offboard mode requires a single stream of setpoint commands. If multiple
components try to send setpoints simultaneously:

1. COMMAND CONFLICT: Component A sends velocity, Component B sends position
   - PX4 receives mixed commands
   - Drone behaves unpredictably
   - Potential crash or flyaway

2. STREAM INTERRUPTION: Component A stops streaming, Component B starts
   - Gap in commands > 0.5s triggers offboard exit
   - Drone enters failsafe (hover or land)
   - Mission interrupted unexpectedly

3. PRIORITY CONFUSION: Two "autopilot" modules both think they're in control
   - Neither releases ownership
   - Both send conflicting commands
   - Control authority undefined

The OffboardOwner solves this by:
1. Requiring explicit acquisition before offboard control
2. Preventing multiple simultaneous owners
3. Providing clear ownership tracking via current_owner()
4. Supporting re-entrant acquisition (same owner can reacquire safely)

================================================================================
HOW THE ACQUIRE/RELEASE PROTOCOL WORKS
================================================================================
Before any component enters offboard mode:

    owner = get_offboard_owner()
    if not await owner.acquire("flight_tools"):
        current = owner.current_owner()
        raise OffboardConflictError(f"Offboard owned by {current}")

    try:
        # Enter offboard mode
        await drone.offboard.set_position(...)
        await drone.offboard.start()

        # Send setpoints...
        await drone.offboard.set_position_ned(position_ned)

    finally:
        # Exit offboard mode
        await drone.offboard.stop()
        await owner.release("flight_tools")

KEY ARCHITECTURAL PROPERTIES:
- acquire() is async (can be called from async context)
- Internal lock prevents race conditions
- Re-entrant: same owner calling acquire() returns True
- release() is idempotent: safe to call multiple times
- current_owner() is sync (fast status check)

================================================================================
SINGLETON PATTERN RATIONALE
================================================================================
Offboard ownership must be process-global. If each module created its own
OffboardOwner instance, they would have independent locks and could both
"acquire" simultaneously - defeating the purpose.

The singleton ensures:
- All modules share the same lock
- Ownership state is consistent across the process
- Single source of truth for who controls offboard

get_offboard_owner() returns the singleton instance, creating it on first call.

================================================================================
INTEGRATION WITH OTHER COMPONENTS
================================================================================
OffboardOwner integrates with:

1. FLIGHT TOOLS: Primary offboard control for missions
   - Acquires "flight_tools" ownership
   - Sends position/velocity setpoints

2. CINEMATIC SHOTS: Orbit, follow, etc.
   - Acquires "cinematic_tools" ownership
   - Sends position setpoints with gimbal commands

3. GUARDIAN: Safety override
   - Can steal ownership in emergency (future enhancement)
   - Has priority over other components

4. MCP SERVER: Agent control interface
   - Checks ownership before offboard commands
   - Reports conflict to agent if owned elsewhere

================================================================================
SAFETY CRITICAL
================================================================================
The OffboardOwner prevents a critical safety failure mode: multiple control
sources sending conflicting commands. Without mutual exclusion:

- Two modules could both believe they're in control
- Commands would conflict or alternate unpredictably
- Drone behavior becomes undefined
- Safety systems (obstacle avoidance) could be overridden

The lock provides a single, clear owner for offboard control.
"""

import asyncio

import pytest

from avatar.mav.offboard_owner import OffboardOwner, get_offboard_owner


class TestAcquireRelease:
    """Test acquire and release operations.

    SAFETY: Acquire/release must be atomic. Race conditions could allow
    multiple owners, defeating the mutual exclusion guarantee.
    """

    @pytest.mark.asyncio
    async def test_acquire_release_single_owner(self) -> None:
        """acquire returns True if lock obtained or already held.

        VALIDATES: Basic acquire/release cycle works correctly.

        MOCK SETUP: Create OffboardOwner, acquire with ID, verify owner.

        SAFETY REASON: Single owner ensures command authority is clear.
        Multiple owners would send conflicting commands.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("flight_tools")
        3. Assert returns True (lock obtained)
        4. Assert current_owner() == "flight_tools"
        5. Call release("flight_tools")
        6. Assert current_owner() is None
        """
        owner = OffboardOwner()
        assert await owner.acquire("flight_tools") is True
        assert owner.current_owner() == "flight_tools"
        await owner.release("flight_tools")
        assert owner.current_owner() is None

    @pytest.mark.asyncio
    async def test_acquire_returns_true_if_already_held(self) -> None:
        """acquire returns True if caller already holds the lock (re-entrant).

        VALIDATES: Re-entrant acquisition works correctly.

        MOCK SETUP: Same owner calls acquire twice.

        SAFETY REASON: Re-entrant acquire allows the same component to
        safely re-acquire if its control flow passes through acquire()
        multiple times. This is common in nested function calls.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a")
        3. Assert returns True
        4. Call acquire("a") again (same owner)
        5. Assert returns True (re-entrant allowed)
        6. Assert current_owner() == "a" (unchanged)
        """
        owner = OffboardOwner()
        assert await owner.acquire("a") is True
        assert await owner.acquire("a") is True  # Re-entrant
        assert owner.current_owner() == "a"
        await owner.release("a")

    @pytest.mark.asyncio
    async def test_acquire_returns_false_if_another_holds(self) -> None:
        """acquire returns False if another owner holds it.

        VALIDATES: Mutual exclusion prevents multiple owners.

        MOCK SETUP: One owner acquires, another tries to acquire.

        SAFETY REASON: This is the core safety property - preventing
        multiple simultaneous owners. False return indicates conflict.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a") -> True
        3. Call acquire("b") -> False (different owner)
        4. Assert current_owner() == "a" (unchanged)
        """
        owner = OffboardOwner()
        assert await owner.acquire("a") is True
        assert await owner.acquire("b") is False  # Different owner
        assert owner.current_owner() == "a"
        await owner.release("a")

    @pytest.mark.asyncio
    async def test_release_clears_holder_if_caller_matches(self) -> None:
        """release clears holder if caller matches current owner.

        VALIDATES: Only the owner can release their lock.

        MOCK SETUP: Owner acquires, same owner releases.

        SAFETY REASON: Only the owner should be able to release their
        lock. This prevents accidental release by unrelated components.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a")
        3. Call release("a")
        4. Assert current_owner() is None
        """
        owner = OffboardOwner()
        await owner.acquire("a")
        await owner.release("a")
        assert owner.current_owner() is None

    @pytest.mark.asyncio
    async def test_release_does_nothing_if_caller_does_not_match(self) -> None:
        """release does nothing if caller is not the current owner.

        VALIDATES: Non-owner cannot release the lock.

        MOCK SETUP: "a" acquires, "b" tries to release.

        SAFETY REASON: Prevents accidental or malicious release by
        components that don't own the lock.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a")
        3. Call release("b") (non-owner)
        4. Assert current_owner() == "a" (unchanged)
        """
        owner = OffboardOwner()
        await owner.acquire("a")
        await owner.release("b")  # Non-owner release
        assert owner.current_owner() == "a"
        await owner.release("a")


class TestSecondAcquireFailsUntilRelease:
    """Test that second acquire fails until first owner releases.

    SAFETY: This is the core mutual exclusion property. Without it,
    multiple components could both believe they're in control.
    """

    @pytest.mark.asyncio
    async def test_second_acquire_fails_until_release(self) -> None:
        """Second acquire fails until first owner releases.

        VALIDATES: Full acquire/release cycle with handoff.

        MOCK SETUP:
        - "a" acquires
        - "b" fails to acquire
        - "a" releases
        - "b" can now acquire

        SAFETY REASON: Tests the complete ownership handoff sequence.
        Ensures that after release, another owner can take control.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a") -> True
        3. Call acquire("b") -> False
        4. Assert current_owner() == "a"
        5. Call release("a")
        6. Call acquire("b") -> True
        7. Assert current_owner() == "b"
        """
        owner = OffboardOwner()
        assert await owner.acquire("a") is True
        assert await owner.acquire("b") is False
        assert owner.current_owner() == "a"
        await owner.release("a")
        assert await owner.acquire("b") is True
        assert owner.current_owner() == "b"
        await owner.release("b")


class TestCurrentOwner:
    """Test current_owner query.

    SAFETY: current_owner provides visibility into ownership state.
    Critical for diagnostics and conflict reporting.
    """

    def test_current_owner_returns_none_initially(self) -> None:
        """current_owner returns None when no owner exists.

        VALIDATES: Initial state is correctly unowned.

        MOCK SETUP: Create OffboardOwner, check current_owner.

        SAFETY REASON: None indicates no owner, allowing components
        to safely acquire without conflict.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call current_owner()
        3. Assert returns None
        """
        owner = OffboardOwner()
        assert owner.current_owner() is None

    @pytest.mark.asyncio
    async def test_current_owner_returns_holder_name(self) -> None:
        """current_owner returns the current holder name.

        VALIDATES: Owner tracking works correctly.

        MOCK SETUP: Acquire with known ID, check current_owner.

        SAFETY REASON: Knowing who owns the lock enables:
        - Conflict reporting (tell agent who owns offboard)
        - Diagnostics (debug why offboard failed)
        - Recovery (can alert owner to release)

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("flight_tools")
        3. Call current_owner()
        4. Assert returns "flight_tools"
        """
        owner = OffboardOwner()
        await owner.acquire("flight_tools")
        assert owner.current_owner() == "flight_tools"
        await owner.release("flight_tools")


class TestSingletonPattern:
    """Test singleton pattern for global ownership.

    SAFETY: Singleton ensures all modules share the same ownership state.
    Without singleton, each module's instance would have independent state.
    """

    def test_singleton_returns_same_instance(self) -> None:
        """get_offboard_owner returns same instance each call.

        VALIDATES: Singleton pattern works correctly.

        MOCK SETUP: Call get_offboard_owner twice.

        SAFETY REASON: Singleton ensures consistent ownership across
        the entire process. All modules see the same lock state.

        STEP-BY-STEP:
        1. Call get_offboard_owner() -> instance1
        2. Call get_offboard_owner() -> instance2
        3. Assert instance1 is instance2 (same object)
        """
        instance1 = get_offboard_owner()
        instance2 = get_offboard_owner()
        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_singleton_state_shared_across_calls(self) -> None:
        """Singleton state is shared across all get_offboard_owner calls.

        VALIDATES: State is truly global, not per-instance.

        MOCK SETUP:
        - Get singleton, acquire
        - Get singleton again, check owner

        SAFETY REASON: If each call returned a new instance, state
        would not be shared and mutual exclusion would fail.

        STEP-BY-STEP:
        1. Call get_offboard_owner() -> owner1
        2. Call acquire("a") on owner1
        3. Call get_offboard_owner() -> owner2
        4. Assert owner2.current_owner() == "a" (shared state)
        """
        owner1 = get_offboard_owner()
        # Clear any previous state
        await owner1.release("a")
        await owner1.release("b")

        await owner1.acquire("a")
        owner2 = get_offboard_owner()
        assert owner2.current_owner() == "a"

        # Cleanup
        await owner2.release("a")


class TestConcurrentAccess:
    """Test thread-safe concurrent access.

    SAFETY: Acquire/release must be atomic under concurrent access.
    Race conditions could allow multiple owners.
    """

    @pytest.mark.asyncio
    async def test_concurrent_acquire_only_one_succeeds(self) -> None:
        """Concurrent acquires - only one should succeed.

        VALIDATES: Lock prevents race conditions.

        MOCK SETUP:
        - Launch 10 concurrent acquire tasks
        - Each tries to acquire with unique ID

        SAFETY REASON: Under concurrent access, the lock must ensure
        only one task becomes owner. Others must fail.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Define 10 concurrent acquire tasks
        3. Gather results
        4. Assert exactly one True result
        5. Assert current_owner is the winner
        """
        owner = OffboardOwner()

        async def try_acquire(idx: int) -> bool:
            return await owner.acquire(f"owner_{idx}")

        # Launch 10 concurrent acquires
        tasks = [try_acquire(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Exactly one should succeed
        successful = sum(1 for r in results if r is True)
        assert successful == 1

        # Clean up
        for i in range(10):
            await owner.release(f"owner_{i}")


class TestEdgeCases:
    """Test edge cases and error handling.

    SAFETY: Edge cases must be handled gracefully. Crashes during edge
    cases could leave the system without proper offboard control.
    """

    @pytest.mark.asyncio
    async def test_release_is_idempotent(self) -> None:
        """release can be called multiple times safely.

        VALIDATES: Safe cleanup behavior.

        MOCK SETUP: Acquire, release twice.

        SAFETY REASON: Idempotent release prevents exceptions during
        cleanup. Components can safely call release in finally blocks.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("a")
        3. Call release("a")
        4. Call release("a") again (should not crash)
        5. Assert current_owner() is None
        """
        owner = OffboardOwner()
        await owner.acquire("a")
        await owner.release("a")
        await owner.release("a")  # Should not crash
        assert owner.current_owner() is None

    @pytest.mark.asyncio
    async def test_empty_string_owner_id(self) -> None:
        """Empty string is a valid owner ID (though not recommended).

        VALIDATES: No crashes on unusual input.

        MOCK SETUP: Acquire and release with empty string.

        SAFETY REASON: Code shouldn't crash on edge case inputs.
        Empty string is valid but should be discouraged.

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. Call acquire("") -> True
        3. Assert current_owner() == ""
        4. Call release("")
        5. Assert current_owner() is None
        """
        owner = OffboardOwner()
        assert await owner.acquire("") is True
        assert owner.current_owner() == ""
        await owner.release("")
        assert owner.current_owner() is None

    @pytest.mark.asyncio
    async def test_ownership_transfer(self) -> None:
        """Ownership can be transferred between components.

        VALIDATES: Handoff sequence works correctly.

        MOCK SETUP:
        - "a" acquires
        - "a" releases
        - "b" acquires
        - "b" releases
        - "c" acquires

        SAFETY REASON: Ownership transfer is a normal operation during
        mission transitions (e.g., cinematic -> manual -> RTL).

        STEP-BY-STEP:
        1. Create OffboardOwner
        2. "a" acquires -> True
        3. "a" releases
        4. "b" acquires -> True
        5. "b" releases
        6. "c" acquires -> True
        7. Verify each step
        """
        owner = OffboardOwner()

        # First owner
        assert await owner.acquire("a") is True
        assert owner.current_owner() == "a"
        await owner.release("a")

        # Second owner
        assert await owner.acquire("b") is True
        assert owner.current_owner() == "b"
        await owner.release("b")

        # Third owner
        assert await owner.acquire("c") is True
        assert owner.current_owner() == "c"
        await owner.release("c")
