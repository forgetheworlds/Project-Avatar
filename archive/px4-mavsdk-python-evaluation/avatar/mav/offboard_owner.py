"""Mutual exclusion for PX4 offboard setpoint streaming.

This module provides a singleton-based ownership system for coordinating
access to PX4's offboard mode. Only one component at a time can safely
send setpoint commands to the drone.

================================================================================
WHY MUTUAL EXCLUSION MATTERS
================================================================================
PX4 offboard mode requires a continuous stream of setpoint commands
(position, velocity, or attitude). If multiple components try to control
offboard simultaneously:

1. COMMAND CONFLICT: Different setpoints would conflict
   - One sends position, another sends velocity
   - PX4 receives mixed commands
   - Drone behavior becomes unpredictable

2. STREAM INTERRUPTION: Multiple streams would interleave
   - Setpoints from different sources mix
   - Control frequency may appear correct but content conflicts
   - Safety hazard - drone could move unexpectedly

3. ACCOUNTABILITY: No clear owner means no clear responsibility
   - Which component should stop streaming?
   - Who is responsible for the drone's behavior?

The OffboardOwner solves this by:
- Requiring explicit acquisition before offboard control
- Preventing multiple simultaneous owners
- Providing clear ownership tracking
- Supporting re-entrant acquisition (same owner can reacquire)

================================================================================
USAGE PATTERN
================================================================================
Before entering offboard mode:

    owner = get_offboard_owner()

    # Try to acquire ownership
    if not await owner.acquire("flight_tools"):
        current = owner.current_owner()
        raise RuntimeError(f"Offboard already owned by {current}")

    try:
        # Enter offboard mode
        await drone.offboard.start()
        await drone.offboard.set_position_ned(position_ned)

        # ... perform mission ...

    finally:
        # Exit offboard mode and release ownership
        await drone.offboard.stop()
        await owner.release("flight_tools")

================================================================================
SINGLETON RATIONALE
================================================================================
Offboard ownership must be process-global. If different modules created
separate OffboardOwner instances, each would have independent state and
could all "acquire" simultaneously - defeating mutual exclusion.

get_offboard_owner() returns the singleton instance, creating it on first
call. All modules share the same ownership state.

================================================================================
THREAD SAFETY
================================================================================
The OffboardOwner uses asyncio.Lock for thread-safe operation:
- acquire() and release() are async methods
- Internal state is protected by the lock
- Safe for concurrent access from multiple asyncio tasks

Note: This is designed for asyncio concurrency (single-threaded, cooperative
multitasking), not multi-threading. The asyncio.Lock ensures atomicity in
the async context.

================================================================================
INTEGRATION POINTS
================================================================================
- Flight tools: Primary mission control
- Cinematic tools: Orbit, follow, and other shot types
- Guardian: Safety override (can request ownership in emergency)
- MCP server: Agent interface to offboard control

All must acquire ownership before sending offboard commands.
"""

from __future__ import annotations

import asyncio
from typing import Optional

# Module-level singleton storage
_singleton: Optional[OffboardOwner] = None


class OffboardOwner:
    """Mutual exclusion for PX4 offboard setpoint streaming.

    This class ensures only one component at a time can control the drone
    in offboard mode. It uses an asyncio.Lock for thread-safe operation
    and supports re-entrant acquisition (same owner can call acquire
    multiple times).

    Attributes:
        _lock: Asyncio lock protecting internal state.
        _holder: Current owner ID, or None if unowned.

    Example:
        >>> owner = OffboardOwner()
        >>> await owner.acquire("flight_tools")
        True
        >>> owner.current_owner()
        'flight_tools'
        >>> await owner.release("flight_tools")
        >>> owner.current_owner()
        None

    Safety:
        Always check acquire() return value before entering offboard mode.
        Always release ownership when exiting offboard mode.
    """

    def __init__(self) -> None:
        """Initialize OffboardOwner with no holder.

        Creates an unowned lock. The first caller to acquire() becomes
        the owner. Subsequent callers receive False until release().
        """
        self._lock: asyncio.Lock = asyncio.Lock()
        self._holder: Optional[str] = None

    async def acquire(self, owner_id: str) -> bool:
        """Attempt to acquire offboard ownership.

        Returns True if:
        - No current owner (lock obtained)
        - Caller is already the current owner (re-entrant)

        Returns False if:
        - Another owner currently holds the lock

        Args:
            owner_id: Unique identifier for the calling component.
                      Used for tracking and conflict reporting.

        Returns:
            bool: True if ownership acquired or already held, False if
                  another owner holds the lock.

        Example:
            >>> owner = OffboardOwner()
            >>> await owner.acquire("flight_tools")
            True  # Acquired successfully
            >>> await owner.acquire("flight_tools")
            True  # Re-entrant, already owned
            >>> await owner.acquire("cinematic")
            False  # Another owner holds it

        Safety:
            Always check the return value before entering offboard mode.
            If False, report conflict to caller/operator.
        """
        async with self._lock:
            if self._holder is None:
                # No current owner - acquire lock
                self._holder = owner_id
                return True
            if self._holder == owner_id:
                # Re-entrant acquisition - already own it
                return True
            # Another owner holds the lock
            return False

    async def release(self, owner_id: str) -> None:
        """Release offboard ownership.

        Only releases if the caller matches the current owner.
        If caller is not the owner, this is a no-op (idempotent).

        Args:
            owner_id: Identifier of the caller attempting to release.

        Example:
            >>> owner = OffboardOwner()
            >>> await owner.acquire("a")
            True
            >>> await owner.release("b")  # Non-owner release
            >>> owner.current_owner()
            'a'  # Still owned by 'a'
            >>> await owner.release("a")  # Owner release
            >>> owner.current_owner()
            None

        Safety:
            Safe to call multiple times. Always call in finally block
            when exiting offboard mode.
        """
        async with self._lock:
            if self._holder == owner_id:
                self._holder = None

    def current_owner(self) -> Optional[str]:
        """Get the current offboard owner.

        Returns:
            Optional[str]: Owner ID if held, None if unowned.

        Example:
            >>> owner = OffboardOwner()
            >>> owner.current_owner()
            None
            >>> await owner.acquire("flight_tools")
            True
            >>> owner.current_owner()
            'flight_tools'

        Note:
            This is a synchronous method for fast status checks.
            It does not acquire the internal lock - the GIL ensures
            reference reads are atomic in Python.
        """
        return self._holder


def get_offboard_owner() -> OffboardOwner:
    """Get the singleton OffboardOwner instance.

    Creates the singleton on first call, returns the same instance
    on subsequent calls. All modules share the same ownership state.

    Returns:
        OffboardOwner: The singleton ownership manager.

    Example:
        >>> owner1 = get_offboard_owner()
        >>> owner2 = get_offboard_owner()
        >>> owner1 is owner2
        True

    Safety:
        Always use this function to get the OffboardOwner instance.
        Creating separate instances would defeat mutual exclusion.
    """
    global _singleton
    if _singleton is None:
        _singleton = OffboardOwner()
    return _singleton
