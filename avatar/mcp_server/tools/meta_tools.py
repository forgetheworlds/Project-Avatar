"""Meta tools for MCP server health and operation management.

These tools provide server-level functionality for health checks and
operation control, independent of drone operations.

Tools:
    - ping: Check server liveness (health check)
    - cancel_operation: Cancel a running long-running operation

What Are Meta Tools?
    Meta tools are administrative tools that manage the MCP server itself
    rather than controlling the drone. They provide:

    1. Health Monitoring: ping() allows clients to verify the server is
       responsive without needing drone connectivity.

    2. Operation Control: cancel_operation() enables graceful cancellation
       of long-running tasks (e.g., extended orbit patterns).

Why These Tools Matter:
    - Cloud LLM Timeout Prevention: Kimi K2.5 and other cloud LLMs have
      timeouts. ping() keeps the connection alive during long operations.

    - Graceful Interruption: Users can cancel operations mid-flight without
      abrupt emergency stops. The operation completes its current loop
      iteration and exits cleanly.

    - Debugging: ping() timestamp and uptime help diagnose timing issues
      and verify server responsiveness during development.

Design Philosophy:
    - Zero Drone Dependencies: These tools work even without a drone
      connection, making them reliable health indicators.

    - Non-Blocking: Both operations complete in < 10ms, never blocking
      the MCP message loop.

    - Thread-Safe: Operation tracking uses asyncio.Event which is
      inherently safe for concurrent access.

Usage Patterns:

    Health Monitoring (Client-Side):
        # Client polls every 30 seconds to keep connection alive
        while mission_active:
            response = await call_tool("ping", {})
            if not response.get("pong"):
                logger.error("Server not responding!")
                break
            await asyncio.sleep(30)

    Operation Cancellation (User-Initiated):
        # User requests abort during long orbit
        operation_id = "orbit_target_12345"

        # The orbit_target tool checks its event each iteration:
        # while not cancel_event.is_set():
        #     ... do orbit step ...
        #     await asyncio.sleep(0.1)

        # User cancels:
        result = await call_tool("cancel_operation", {"operation_id": operation_id})
        # Result: {"cancelled": true, "operation_id": "orbit_target_12345"}

RFC 3339 Timestamp Format:
    The ping() tool uses RFC 3339 format for timestamps (e.g., "2026-04-16T12:00:00Z").
    This is the Internet Standard for timestamps, compatible with:
    - JSON serialization
    - ISO 8601 parsers
    - Most programming language date libraries
    - Human readability

Operation Tracking Architecture:
    The cancel_operation tool uses a global dictionary mapping operation IDs
    to asyncio.Event objects:

    _operations: dict[str, asyncio.Event] = {
        "orbit_12345": <Event set=False>,
        "search_67890": <Event set=False>,
    }

    Long-running tools integrate like this:

    async def some_long_tool(operation_id: str, ...):
        # Register operation
        cancel_event = asyncio.Event()
        register_operation(operation_id, cancel_event)

        try:
            while not cancel_event.is_set():
                # ... do work ...
                await asyncio.sleep(0.1)
            return {"success": True, "cancelled": True}
        finally:
            unregister_operation(operation_id)

    The event-based approach is:
    - Non-blocking: Setting an event is O(1)
    - Thread-safe: asyncio.Event handles concurrent access
    - Clean: Tools check the event naturally in their loop
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ==============================================================================
# SERVER START TIME - For uptime calculation
# ==============================================================================
# Tracks when this module was loaded, which approximates server start time.
# Used by ping() to report how long the server has been running.

_SERVER_START_TIME: float = time.monotonic()
_SERVER_START_TIMESTAMP: str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def rfc3339_now() -> str:
    """Get current timestamp in RFC 3339 format.

    RFC 3339 is the Internet Standard for timestamps in protocols.
    Format: "2026-04-16T12:00:00Z" (UTC with 'Z' suffix)

    This format is:
    - Human-readable
    - ISO 8601 compatible
    - JSON-serializable
    - Timezone-explicit (always UTC/Z)

    Returns:
        Current timestamp string in RFC 3339 format.

    Example:
        >>> rfc3339_now()
        '2026-04-16T12:34:56.789Z'
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ==============================================================================
# OPERATION TRACKING - For cancel_operation tool
# ==============================================================================
# Global registry of active operations that can be cancelled.
# Maps operation_id -> asyncio.Event

_operations: Dict[str, asyncio.Event] = {}


def register_operation(operation_id: str, cancel_event: asyncio.Event) -> None:
    """Register an operation for cancellation tracking.

    Long-running tools should call this at the start of their execution
    to enable cancellation via cancel_operation().

    Args:
        operation_id: Unique identifier for this operation instance.
        cancel_event: asyncio.Event that will be set when cancelled.

    Example:
        async def long_orbit(operation_id: str, ...):
            cancel_event = asyncio.Event()
            register_operation(operation_id, cancel_event)

            try:
                while not cancel_event.is_set():
                    # ... do orbit step ...
                    await asyncio.sleep(0.1)
                return {"success": True, "cancelled": True}
            finally:
                unregister_operation(operation_id)
    """
    _operations[operation_id] = cancel_event
    logger.debug(f"Registered operation: {operation_id}")


def unregister_operation(operation_id: str) -> None:
    """Unregister an operation after completion.

    Should be called when an operation finishes (successfully, with error,
    or via cancellation) to clean up the tracking dictionary.

    Args:
        operation_id: The operation to remove from tracking.

    Note:
        Safe to call even if operation_id was never registered.
    """
    if operation_id in _operations:
        del _operations[operation_id]
        logger.debug(f"Unregistered operation: {operation_id}")


def get_operation_event(operation_id: str) -> Optional[asyncio.Event]:
    """Get the cancellation event for an operation.

    Args:
        operation_id: The operation to look up.

    Returns:
        asyncio.Event if operation exists, None otherwise.
    """
    return _operations.get(operation_id)


def list_active_operations() -> Dict[str, bool]:
    """List all active operations and their cancellation status.

    Returns:
        Dict mapping operation_id -> is_cancelled for all tracked operations.
    """
    return {
        op_id: event.is_set()
        for op_id, event in _operations.items()
    }


# ==============================================================================
# PING TOOL - Server liveness check
# ==============================================================================

def ping() -> Dict[str, Any]:
    """Check server liveness and return status information.

    This is a lightweight health check that verifies the MCP server is
    responsive without requiring drone connectivity. It's useful for:

    1. Connection Keep-Alive: Prevent cloud LLM timeouts during long operations
    2. Health Monitoring: Verify server is running and responsive
    3. Timing Debugging: Check server uptime and timestamp accuracy

    The ping tool has these MCP annotations:
    - readOnlyHint=True: Does not modify any state
    - destructiveHint=False: Cannot cause damage
    - idempotentHint=True: Multiple calls have same result
    - openWorldHint=False: Only affects this server

    Returns:
        Dict with liveness status and server metrics:

        {
            "pong": true,                        # Always true if server is running
            "timestamp": "2026-04-16T12:00:00Z", # Current time in RFC 3339
            "uptime_s": 123.45,                  # Server uptime in seconds
            "active_operations": 2               # Number of tracked operations
        }

    Performance:
        - Response time: < 1ms (no I/O, just memory reads)
        - Memory: O(1) - constant regardless of system state

    Example MCP call:
        >>> result = ping()
        >>> print(result["pong"])
        True
        >>> print(result["uptime_s"])
        3600.5  # Server has been running for ~1 hour
    """
    # Calculate uptime using monotonic clock for accuracy
    # monotonic clock is immune to system time changes (NTP, DST, etc.)
    uptime_s = time.monotonic() - _SERVER_START_TIME

    # Count active operations for diagnostics
    active_count = len(_operations)

    return {
        "pong": True,
        "timestamp": rfc3339_now(),
        "uptime_s": round(uptime_s, 2),
        "start_time": _SERVER_START_TIMESTAMP,
        "active_operations": active_count,
    }


async def async_ping() -> str:
    """Async wrapper for ping() that returns JSON string for MCP.

    MCP tools must be async and return JSON strings for transport.
    This wrapper adapts the synchronous ping() for the MCP interface.

    Returns:
        JSON string with ping response.

    Example:
        >>> result = await async_ping()
        >>> print(result)
        '{"pong": true, "timestamp": "2026-04-16T12:00:00Z", "uptime_s": 123.45}'
    """
    result = ping()
    return json.dumps(result, indent=2)


# ==============================================================================
# CANCEL OPERATION TOOL - Graceful operation termination
# ==============================================================================

async def cancel_operation(operation_id: str) -> Dict[str, Any]:
    """Cancel a running long-running operation.

    This tool requests graceful cancellation of an operation identified by
    its operation_id. The operation will complete its current loop iteration
    and exit cleanly.

    How Cancellation Works:
    1. Long-running tools register an asyncio.Event when they start
    2. The tool checks event.is_set() each loop iteration
    3. When cancel_operation() is called, we set the event
    4. The tool sees the flag and exits its loop cleanly
    5. The tool unregisters itself on exit

    This approach is:
    - Non-blocking: Setting an event is immediate
    - Thread-safe: asyncio.Event handles concurrent access
    - Graceful: Tool finishes current iteration before exiting

    Args:
        operation_id: Unique identifier of the operation to cancel.
                     This is typically generated when the operation starts
                     and returned in the operation's initial response.

    Returns:
        Dict with cancellation result:

        Success case:
        {
            "cancelled": true,
            "operation_id": "orbit_12345",
            "message": "Cancellation signal sent"
        }

        Not found case:
        {
            "cancelled": false,
            "error": "operation not found",
            "operation_id": "unknown_id",
            "active_operations": ["orbit_12345", "search_67890"]
        }

    Safety Notes:
        - Cancellation is graceful, not immediate
        - The tool will complete its current iteration
        - Safe to call even if operation already completed
        - Multiple calls to same operation_id are safe

    Example Usage:
        # Start a long operation
        result = await orbit_target(..., operation_id="orbit_001")
        # User wants to abort after 30 seconds
        cancel_result = await cancel_operation("orbit_001")
        # Result: {"cancelled": true, "operation_id": "orbit_001"}
    """
    event = _operations.get(operation_id)

    if event is None:
        # Operation not found - may have already completed
        return {
            "cancelled": False,
            "error": "operation not found",
            "operation_id": operation_id,
            "active_operations": list(_operations.keys()),
        }

    # Check if already cancelled
    if event.is_set():
        return {
            "cancelled": True,
            "operation_id": operation_id,
            "message": "Operation already cancelled",
        }

    # Set the cancellation event
    # This is non-blocking - the operation will see this on next loop
    event.set()
    logger.info(f"Cancellation requested for operation: {operation_id}")

    return {
        "cancelled": True,
        "operation_id": operation_id,
        "message": "Cancellation signal sent",
    }


async def async_cancel_operation(operation_id: str) -> str:
    """Async wrapper for cancel_operation() that returns JSON string for MCP.

    This is the actual entry point registered with the MCP server.
    It adapts cancel_operation() for the MCP JSON string interface.

    Args:
        operation_id: ID of the operation to cancel.

    Returns:
        JSON string with cancellation result.

    Example:
        >>> result = await async_cancel_operation("orbit_12345")
        >>> print(result)
        '{"cancelled": true, "operation_id": "orbit_12345", "message": "Cancellation signal sent"}'
    """
    result = await cancel_operation(operation_id)
    return json.dumps(result, indent=2)


# ==============================================================================
# UTILITY FUNCTIONS - For integration with other tools
# ==============================================================================

def generate_operation_id(prefix: str = "op") -> str:
    """Generate a unique operation ID.

    Creates a unique identifier for tracking operations. Uses timestamp
    and random suffix to ensure uniqueness.

    Args:
        prefix: Prefix for the ID (e.g., "orbit", "search", "track").
               Helps identify the operation type in logs.

    Returns:
        Unique operation ID string.

    Example:
        >>> generate_operation_id("orbit")
        'orbit_20260416_123456_abc123'

        >>> generate_operation_id("search")
        'search_20260416_123456_def456'
    """
    import random
    import string

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    return f"{prefix}_{timestamp}_{suffix}"


def create_cancellable_context(operation_id: str) -> asyncio.Event:
    """Create a cancellation context for a long-running operation.

    This is a convenience function that creates an asyncio.Event and
    registers it for cancellation tracking. Use this at the start of
    long-running operations.

    Args:
        operation_id: Unique identifier for this operation.

    Returns:
        asyncio.Event that will be set if cancellation is requested.

    Example:
        async def my_long_tool():
            op_id = generate_operation_id("mytool")
            cancel_event = create_cancellable_context(op_id)

            try:
                while not cancel_event.is_set():
                    # ... do work ...
                    await asyncio.sleep(0.1)
                return {"success": True, "cancelled": True, "operation_id": op_id}
            finally:
                unregister_operation(op_id)
    """
    cancel_event = asyncio.Event()
    register_operation(operation_id, cancel_event)
    return cancel_event
