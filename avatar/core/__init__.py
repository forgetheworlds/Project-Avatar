"""
Core Utilities for Avatar Drone System

This __init__.py exports shared utilities: decorators, context managers,
and helpers for async operations, timeouts, retries, and state management.

================================================================================
WHAT IS __init__.py? (For Beginners)
================================================================================

This file makes 'avatar.core' a proper Python package. When you:

    from avatar.core import timeout, retry

Python runs this file and uses the imports below to find 'timeout' and 'retry'.

Think of __init__.py like a catalog that tells Python:
    "When someone asks for X from this package, look in file Y"

================================================================================
WHY WE EXPORT THESE UTILITIES
================================================================================

The 'core' package contains shared building blocks used by other packages.
We export:

1. DECORATORS (from decorators.py)
   - @timeout(seconds): Fail if function takes too long
   - @retry(attempts, delay): Retry on failure
   - @require_state(state): Only run in specific flight state
   -> These wrap functions to add cross-cutting behavior

2. CONTEXT MANAGERS (from context_managers.py)
   - managed_connection(): Auto-connect/disconnect to drone
   - managed_offboard(): Safe entry/exit from offboard mode
   - managed_telemetry_cache(): Auto-start/stop telemetry
   - FlightSession(): Complete flight lifecycle management
   -> These handle setup/cleanup automatically (with 'async with')

WHY THESE? Safety-critical drone code needs:
   - Timeouts (don't hang forever waiting for drone)
   - Retries (network is unreliable)
   - State validation (don't arm if already armed)
   - Cleanup guarantees (disconnect even if error occurs)

================================================================================
HOW IMPORTS WORK HERE
================================================================================

There are THREE ways to write imports in __init__.py:

1. Absolute imports (what we use for cross-module imports):
   from avatar.core.decorators import timeout

2. Relative imports (what we use for same-package imports):
   from .decorators import timeout
   The dot '.' means "this package"

3. Direct module imports (rare, for complex cases):
   import avatar.core.decorators as decorators

WHY MIX ABSOLUTE AND RELATIVE?
   - Relative imports (.decorators) are shorter for same-package
   - Absolute imports (avatar.core.X) are clearer for cross-package
   - Both work the same, it's a style choice

IMPORT CHAIN EXAMPLE:
--------------------------
Your code:          from avatar.core import timeout
                          ↓
This __init__.py:    from .decorators import timeout
                          ↓
decorators.py:      def timeout(seconds: int): ...
                          ↓
Decorator applied:  @timeout(30)
                    async def connect_to_drone(): ...

================================================================================
WHAT ARE DECORATORS?
================================================================================

Decorators are functions that wrap other functions to add behavior:

    @timeout(30)           # ← This decorator
    async def connect():   # ← Wraps this function
        ...

Is equivalent to:
    connect = timeout(30)(connect)

Think of decorators like adding a jacket:
    - The original function stays the same
    - The decorator adds a layer around it
    - Multiple decorators = multiple layers

OUR DECORATORS:
    @timeout(30)        # Raises TimeoutError after 30 seconds
    @retry(3, delay=1)  # Retry 3 times with 1-second delays
    @require_state(State.ARMED)  # Only run if drone is armed

================================================================================
WHAT ARE CONTEXT MANAGERS?
================================================================================

Context managers handle setup and cleanup automatically:

    async with managed_connection(drone) as conn:
        await conn.arm()
        # ... do work ...
    # <-- connection auto-closes here, even if error occurred!

Think of context managers like a hotel room:
    - 'async with' = checking in (setup happens)
    - Inside block = using the room (your code runs)
    - Exit block = checking out (cleanup happens, guaranteed!)

OUR CONTEXT MANAGERS:
    managed_connection():     Connect to drone, disconnect on exit
    managed_offboard():        Enter offboard mode, exit cleanly
    managed_telemetry_cache(): Start telemetry, stop on exit
    FlightSession():          Full flight lifecycle management

================================================================================
PACKAGE STRUCTURE
================================================================================

avatar/core/
├── __init__.py              <- This file - public API exports
├── decorators.py            <- @timeout, @retry, @require_state
├── context_managers.py      <- managed_connection, FlightSession
└── (other utility modules)  <- Internal helpers (not exported)

================================================================================
USAGE EXAMPLES
================================================================================

# --- Decorators ---
from avatar.core import timeout, retry, require_state

@timeout(30)  # Must complete within 30 seconds
@retry(3, delay=1.0)  # Retry 3 times on failure
async def connect_to_drone():
    ...

# --- Context Managers ---
from avatar.core import managed_connection, FlightSession

# Simple connection management
async with managed_connection(drone) as conn:
    await conn.arm()
    await conn.takeoff(10)

# Full flight session
async with FlightSession(drone) as session:
    await session.arm()
    await session.takeoff(10)
    await session.goto(47.0, -122.0, 10)
    await session.land()
"""

# =============================================================================
# ACTUAL IMPORTS
# =============================================================================

# We use RELATIVE imports (starting with .) because these are in the same package
# '.decorators' = 'avatar/core/decorators.py'
# '.context_managers' = 'avatar/core/context_managers.py'

# --- Decorators ---
# These wrap functions to add cross-cutting behavior
from .decorators import (
    timeout,       # @timeout(seconds) - fail if takes too long
    retry,         # @retry(attempts, delay) - retry on failure
    require_state, # @require_state(state) - validate flight state
    StateError,    # Exception raised by @require_state on failure
)

# --- Context Managers ---
# These handle setup/cleanup with 'async with' syntax
from .context_managers import (
    managed_connection,      # Auto-connect/disconnect to drone
    managed_offboard,        # Safe offboard mode entry/exit
    managed_telemetry_cache, # Auto-start/stop telemetry
    batch_operations,        # Batch multiple operations
    BatchOperations,         # Class for batch operation management
    FlightSession,           # Complete flight lifecycle context
)

# =============================================================================
# PUBLIC API DEFINITION
# =============================================================================

__all__ = [
    # ============================ Decorators ==================================
    "timeout",       # Fail operations that exceed time limit
    "retry",         # Automatically retry failed operations
    "require_state", # Enforce valid flight state before execution
    "StateError",    # Exception for state validation failures

    # ========================= Context Managers ===============================
    "managed_connection",      # Safe drone connection handling
    "managed_offboard",        # Safe offboard mode transitions
    "managed_telemetry_cache", # Automatic telemetry lifecycle
    "batch_operations",        # Group multiple drone commands
    "BatchOperations",         # Batch operations manager class
    "FlightSession",           # Full flight session management
]

# NOTE: We intentionally DON'T export everything from the core modules.
# Only the most commonly used utilities are in __all__.
# For advanced usage, import directly from the submodule:
#     from avatar.core.decorators import some_advanced_decorator
