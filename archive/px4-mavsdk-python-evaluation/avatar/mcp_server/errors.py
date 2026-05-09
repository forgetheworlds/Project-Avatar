"""ErrorCode enum and structured error envelope for MCP server.

This module defines the D2.1 error handling contract that provides
structured error responses for all MCP tools. The ErrorCode enum
is a signature contract that downstream waves depend on.

Example:
    >>> from avatar.mcp_server.errors import ErrorCode, to_error_envelope
    >>> envelope = to_error_envelope(
    ...     ErrorCode.GUARDIAN_VIOLATION,
    ...     "Altitude exceeds safety limit",
    ...     recoverable=False,
    ...     suggested_action="Reduce altitude below 120m",
    ... )
    >>> envelope["isError"]
    True
    >>> envelope["error"]["code"]
    'GUARDIAN_VIOLATION'
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Structured error codes for MCP tool responses.

    These codes categorize all possible error conditions in the drone
    control system, enabling consistent error handling across the stack.

    Categories:
        safety: Guardian violations, preflight blocks, offboard conflicts
        operator: Confirmation issues, user cancellations
        mavlink: MAVSDK communication errors
        runtime: Provider issues, quota limits, internal errors
        mission: Invalid mission specs, altitude ambiguity
        parameter: PX4 parameter lookup/validation errors
        input: Schema validation failures

    Attributes:
        GUARDIAN_VIOLATION: Safety gatekeeper rejected operation
        OFFBOARD_OWNERSHIP_CONFLICT: OffboardOwner already acquired
        CONFIRMATION_REQUIRED: Operation needs user confirmation
        CONFIRMATION_EXPIRED: Confirmation token timed out
        MAV_COMMAND_REJECTED: Drone rejected MAVLink command
        MAV_TIMEOUT: MAVLink command timed out
        MAV_NOT_CONNECTED: No connection to drone
        PREFLIGHT_BLOCKED: Preflight checks failed
        PROVIDER_UNAVAILABLE: External provider unavailable
        QUOTA_EXCEEDED: API quota or resource limit exceeded
        INVALID_MISSION: Mission definition is invalid
        MISSION_SPEC_ERROR: Mission spec parsing/formatting error
        ALTITUDE_DOMAIN_AMBIGUOUS: Altitude reference frame unclear
        PARAMETER_NOT_FOUND: PX4 parameter does not exist
        PARAMETER_OUT_OF_RANGE: Parameter value outside bounds
        CANCELLED: Operation cancelled by user
        INTERNAL_ERROR: Unexpected internal error
        NOT_IMPLEMENTED: Feature not yet implemented
        SCHEMA_VALIDATION_FAILED: Input schema validation failed
    """

    GUARDIAN_VIOLATION = "GUARDIAN_VIOLATION"
    OFFBOARD_OWNERSHIP_CONFLICT = "OFFBOARD_OWNERSHIP_CONFLICT"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_EXPIRED = "CONFIRMATION_EXPIRED"
    MAV_COMMAND_REJECTED = "MAV_COMMAND_REJECTED"
    MAV_TIMEOUT = "MAV_TIMEOUT"
    MAV_NOT_CONNECTED = "MAV_NOT_CONNECTED"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INVALID_MISSION = "INVALID_MISSION"
    MISSION_SPEC_ERROR = "MISSION_SPEC_ERROR"
    ALTITUDE_DOMAIN_AMBIGUOUS = "ALTITUDE_DOMAIN_AMBIGUOUS"
    PARAMETER_NOT_FOUND = "PARAMETER_NOT_FOUND"
    PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"
    CANCELLED = "CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"


# Category mapping for error codes
# Each code maps to one of: safety, operator, mavlink, runtime, mission, parameter, input
_CODE_CATEGORY: dict[ErrorCode, str] = {
    # Safety category - Guardian and critical safety issues
    ErrorCode.GUARDIAN_VIOLATION: "safety",
    ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT: "safety",
    ErrorCode.PREFLIGHT_BLOCKED: "safety",
    # Operator category - User interaction issues
    ErrorCode.CONFIRMATION_REQUIRED: "operator",
    ErrorCode.CONFIRMATION_EXPIRED: "operator",
    ErrorCode.CANCELLED: "operator",
    # MAVLink category - Drone communication issues
    ErrorCode.MAV_COMMAND_REJECTED: "mavlink",
    ErrorCode.MAV_TIMEOUT: "mavlink",
    ErrorCode.MAV_NOT_CONNECTED: "mavlink",
    # Mission category - Mission planning issues
    ErrorCode.INVALID_MISSION: "mission",
    ErrorCode.MISSION_SPEC_ERROR: "mission",
    ErrorCode.ALTITUDE_DOMAIN_AMBIGUOUS: "mission",
    # Parameter category - PX4 parameter issues
    ErrorCode.PARAMETER_NOT_FOUND: "parameter",
    ErrorCode.PARAMETER_OUT_OF_RANGE: "parameter",
    # Input category - User input validation
    ErrorCode.SCHEMA_VALIDATION_FAILED: "input",
    # Runtime category - System/runtime issues
    ErrorCode.PROVIDER_UNAVAILABLE: "runtime",
    ErrorCode.QUOTA_EXCEEDED: "runtime",
    ErrorCode.INTERNAL_ERROR: "runtime",
    ErrorCode.NOT_IMPLEMENTED: "runtime",
}


def to_error_envelope(
    code: ErrorCode,
    message: str,
    *,
    recoverable: bool,
    suggested_action: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a structured error envelope for MCP tool responses.

    This function produces a consistent error response format that all
    MCP tools should use when returning error conditions.

    Args:
        code: ErrorCode enum value identifying the error type
        message: Human-readable error description
        recoverable: Whether the operation can be retried or recovered
        suggested_action: Optional hint for how to resolve the error
        details: Optional additional context (e.g., timeout values, parameter bounds)

    Returns:
        Dictionary with the following structure:
        {
            "isError": True,
            "error": {
                "code": "<ErrorCode value>",
                "category": "<category from _CODE_CATEGORY>",
                "message": "<provided message>",
                "recoverable": <provided boolean>,
                "suggestedAction": "<optional suggestion>",  # only if provided
                "details": {...}  # only if provided
            }
        }

    Example:
        >>> envelope = to_error_envelope(
        ...     ErrorCode.PARAMETER_OUT_OF_RANGE,
        ...     "MPC_Z_VEL_MAX_UP must be between 0.5 and 10.0 m/s",
        ...     recoverable=True,
        ...     suggested_action="Set value within valid range",
        ...     details={"min": 0.5, "max": 10.0, "provided": 15.0},
        ... )
        >>> envelope["error"]["category"]
        'parameter'
    """
    error_obj: dict[str, Any] = {
        "code": code.value,
        "category": _CODE_CATEGORY[code],
        "message": message,
        "recoverable": recoverable,
    }

    # Add optional fields only when provided
    if suggested_action is not None:
        error_obj["suggestedAction"] = suggested_action

    if details is not None:
        error_obj["details"] = details

    return {
        "isError": True,
        "error": error_obj,
    }
