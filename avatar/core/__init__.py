"""Core utilities for Avatar drone system.

Provides decorators, context managers, and utilities for async operations,
timeouts, retries, connection management, and state machine integration.
"""

from .decorators import timeout, retry, require_state, StateError
from .context_managers import (
    managed_connection,
    managed_offboard,
    managed_telemetry_cache,
    batch_operations,
    BatchOperations,
    FlightSession,
)

__all__ = [
    "timeout",
    "retry",
    "require_state",
    "StateError",
    "managed_connection",
    "managed_offboard",
    "managed_telemetry_cache",
    "batch_operations",
    "BatchOperations",
    "FlightSession",
]
