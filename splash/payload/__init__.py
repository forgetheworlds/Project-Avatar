"""
splash/payload/__init__.py — Public API for the payload interface system.

Exports:
    PayloadState          — Enum: lifecycle states
    BasePayload           — Abstract base class for all payloads
    PayloadInfo           — Dataclass: payload metadata
    PayloadRegistry       — Discovery, registration, health monitoring
    SplashPayload         — Concrete water-gun payload implementation

Usage:
    from splash.payload import PayloadRegistry, SplashPayload

    registry = PayloadRegistry(known_payloads=[SplashPayload])
    registry.scan_bus()
    registry.activate("splash_0")
    registry.execute("splash_0", "fire", {"duration_ms": 500})

Project Avatar — Modular payload interface system.
"""

from splash.payload.base_payload import (
    PayloadState,
    BasePayload,
    PayloadInfo,
    PayloadHealth,
    PayloadCommandResult,
)
from splash.payload.payload_registry import (
    PayloadRegistry,
    PayloadNotReadyError,
    PayloadFaultError,
    PayloadPowerLimitError,
)
from splash.payload.splash_payload import SplashPayload

__all__ = [
    # State & base
    "PayloadState",
    "BasePayload",
    "PayloadInfo",
    "PayloadHealth",
    "PayloadCommandResult",
    # Registry
    "PayloadRegistry",
    "PayloadNotReadyError",
    "PayloadFaultError",
    "PayloadPowerLimitError",
    # Concrete payloads
    "SplashPayload",
]
