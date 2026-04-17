"""Preflight check primitive MCP tool for Project Avatar.

This module provides the run_preflight primitive tool for MCP-compatible AI agents.
The tool runs standard preflight checks (GPS, battery, home, sensors, connection)
and returns structured results for go/no-go decision making.

Available Tools (MCP functions):
    - run_preflight: Run preflight checks and return results

Architecture:
    The module follows the primitive tools pattern:
    1. Input/output schemas defined with Pydantic v2
    2. Tool schema and annotation functions for MCP registration
    3. Async handler function returning JSON strings

Safety Integration:
    Preflight checks validate:
    - GPS lock quality (required for navigation)
    - Battery level (required for mission duration + RTL margin)
    - Home position (required for RTL safety feature)
    - Sensor calibration (required for stable flight)
    - MAVLink connection (required for all commands)

Example Usage (as MCP tool):
    >>> result = await run_preflight()
    >>> data = json.loads(result)
    >>> if data["all_passed"]:
    ...     print("All checks passed - safe to arm")
    ... else:
    ...     print(f"Checks failed: {data['failures']} failures")

Dependencies:
    - TelemetryCache: Fast access to current drone telemetry
    - GuardianProcess: Safety validation and home position tracking
    - ConnectionManager: MAVLink connection management
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.guardian import GuardianProcess
from avatar.mcp_server.errors import ErrorCode, to_error_envelope

logger = logging.getLogger(__name__)

# Global state references - set by the MCP server at startup
_telemetry_cache: Optional[Any] = None
_guardian: Optional[GuardianProcess] = None
_connection_manager: Optional[ConnectionManager] = None


def set_telemetry_cache(cache: Any) -> None:
    """Set the global telemetry cache reference."""
    global _telemetry_cache
    _telemetry_cache = cache


def set_guardian(guardian: GuardianProcess) -> None:
    """Set the global guardian reference."""
    global _guardian
    _guardian = guardian


def set_connection_manager(cm: ConnectionManager) -> None:
    """Set the global connection manager reference."""
    global _connection_manager
    _connection_manager = cm


def get_telemetry_cache() -> Optional[Any]:
    """Get the global telemetry cache instance."""
    return _telemetry_cache


def get_guardian() -> Optional[GuardianProcess]:
    """Get the global guardian instance."""
    return _guardian


def get_connection_manager() -> Optional[ConnectionManager]:
    """Get the global connection manager instance."""
    return _connection_manager


# =============================================================================
# INPUT/OUTPUT SCHEMAS
# =============================================================================


class RunPreflightInput(BaseModel):
    """Input schema for run_preflight tool.

    Attributes:
        checks: Optional list of specific checks to run. If None, runs all checks.
                Valid check names: 'gps', 'battery', 'home', 'sensors', 'connection'.
    """

    checks: Optional[list[str]] = Field(
        default=None,
        description="Optional list of specific checks to run. None = all checks. "
                    "Valid names: 'gps', 'battery', 'home', 'sensors', 'connection'.",
    )


class PreflightResult(BaseModel):
    """Output schema for run_preflight tool.

    Attributes:
        checks: List of CheckResult objects from the preflight checks.
        all_passed: True if all checks passed (no failures).
        warnings: Number of checks with 'warn' status.
        failures: Number of checks with 'fail' status.
    """

    checks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of preflight check results",
    )
    all_passed: bool = Field(
        default=False,
        description="True if all checks passed (no failures)",
    )
    warnings: int = Field(
        default=0,
        description="Number of checks with 'warn' status",
    )
    failures: int = Field(
        default=0,
        description="Number of checks with 'fail' status",
    )


# =============================================================================
# TOOL SCHEMA FUNCTIONS
# =============================================================================


def run_preflight_tool_schema() -> dict[str, Any]:
    """Return the JSON schema for run_preflight input."""
    return RunPreflightInput.model_json_schema()


def run_preflight_output_schema() -> dict[str, Any]:
    """Return the JSON schema for run_preflight output."""
    return PreflightResult.model_json_schema()


def run_preflight_annotations() -> dict[str, bool]:
    """Return MCP tool annotations for run_preflight.

    Annotations inform the LLM about tool behavior:
    - readOnlyHint: True - only reads telemetry, doesn't modify state
    - destructiveHint: False - no destructive operations
    - idempotentHint: True - same result for same state
    - openWorldHint: False - operates within drone context
    """
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


# =============================================================================
# INTERNAL CHECK FUNCTIONS
# =============================================================================


async def _run_gps_check(
    drone: Any,
    telemetry_cache: Any,
) -> dict[str, Any]:
    """Run GPS fix quality check.

    Args:
        drone: MAVSDK System instance (may be None).
        telemetry_cache: TelemetryCache instance (may be None).

    Returns:
        Dict with name, status, and detail fields.
    """
    status: Literal["pass", "warn", "fail"] = "fail"
    detail = ""

    # Try telemetry cache first (fastest)
    if telemetry_cache is not None:
        data = telemetry_cache.get_data()
        if data is not None:
            gps_fix = getattr(data, "gps_fix", 0) or 0
            is_gps_ok = getattr(data, "is_gps_ok", False)
            if gps_fix >= 3 and is_gps_ok:
                status = "pass"
                detail = f"3D GPS fix (type={gps_fix})"
            elif gps_fix >= 2:
                status = "warn"
                detail = f"2D GPS fix (type={gps_fix}), waiting for 3D"
            else:
                status = "fail"
                detail = f"No GPS lock (type={gps_fix})"
            return {"name": "gps", "status": status, "detail": detail}

    # Fall back to drone telemetry
    if drone is not None:
        try:
            async for health in drone.telemetry.health():
                if health.is_global_position_valid:
                    status = "pass"
                    detail = "GPS position valid"
                else:
                    status = "fail"
                    detail = "GPS position not valid"
                break
        except Exception as e:
            status = "fail"
            detail = f"Could not check GPS: {e}"
    else:
        status = "fail"
        detail = "No telemetry cache or drone connection"

    return {"name": "gps", "status": status, "detail": detail}


async def _run_battery_check(
    drone: Any,
    telemetry_cache: Any,
) -> dict[str, Any]:
    """Run battery level check.

    Args:
        drone: MAVSDK System instance (may be None).
        telemetry_cache: TelemetryCache instance (may be None).

    Returns:
        Dict with name, status, and detail fields.
    """
    status: Literal["pass", "warn", "fail"] = "fail"
    detail = ""

    # Try telemetry cache first (fastest)
    if telemetry_cache is not None:
        data = telemetry_cache.get_data()
        if data is not None:
            battery_percent = getattr(data, "battery_percent", 0.0) or 0.0
            if battery_percent >= 50.0:
                status = "pass"
                detail = f"Battery OK ({battery_percent:.1f}%)"
            elif battery_percent >= 25.0:
                status = "warn"
                detail = f"Battery low ({battery_percent:.1f}%)"
            else:
                status = "fail"
                detail = f"Battery critical ({battery_percent:.1f}%)"
            return {"name": "battery", "status": status, "detail": detail}

    # Fall back to drone telemetry
    if drone is not None:
        try:
            async for battery in drone.telemetry.battery():
                percent = battery.remaining_percent
                if percent >= 50.0:
                    status = "pass"
                    detail = f"Battery OK ({percent:.1f}%)"
                elif percent >= 25.0:
                    status = "warn"
                    detail = f"Battery low ({percent:.1f}%)"
                else:
                    status = "fail"
                    detail = f"Battery critical ({percent:.1f}%)"
                break
        except Exception as e:
            status = "fail"
            detail = f"Could not check battery: {e}"
    else:
        status = "fail"
        detail = "No telemetry cache or drone connection"

    return {"name": "battery", "status": status, "detail": detail}


async def _run_home_check(
    drone: Any,
    guardian: GuardianProcess,
) -> dict[str, Any]:
    """Run home position check.

    Args:
        drone: MAVSDK System instance (may be None).
        guardian: GuardianProcess instance.

    Returns:
        Dict with name, status, and detail fields.
    """
    status: Literal["pass", "warn", "fail"] = "pass"
    detail = ""

    # Check if home position is set in guardian
    if guardian.is_home_set:
        home = guardian.home_position
        if home is not None:
            status = "pass"
            detail = f"Home position set: ({home[0]:.6f}, {home[1]:.6f})"
        else:
            status = "pass"
            detail = "Home position set"
    else:
        # Check if drone has home position
        if drone is not None:
            try:
                async for health in drone.telemetry.health():
                    if health.is_home_position_ok:
                        status = "pass"
                        detail = "Home position OK"
                    else:
                        status = "warn"
                        detail = "Home position not set - will set on arm"
                    break
            except Exception as e:
                status = "warn"
                detail = f"Could not check home: {e}"
        else:
            status = "warn"
            detail = "Home position not set - will set on arm"

    return {"name": "home", "status": status, "detail": detail}


async def _run_sensors_check(
    drone: Any,
) -> dict[str, Any]:
    """Run sensor calibration check.

    Args:
        drone: MAVSDK System instance (may be None).

    Returns:
        Dict with name, status, and detail fields.
    """
    status: Literal["pass", "warn", "fail"] = "fail"
    detail = ""

    if drone is not None:
        try:
            async for health in drone.telemetry.health():
                issues = []
                if not health.is_gyrometer_calibration_ok:
                    issues.append("gyro")
                if not health.is_accelerometer_calibration_ok:
                    issues.append("accel")
                if not health.is_magnetometer_calibration_ok:
                    issues.append("mag")
                if not health.is_level_calibration_ok:
                    issues.append("level")

                if not issues:
                    status = "pass"
                    detail = "All sensors calibrated"
                elif len(issues) <= 1:
                    status = "warn"
                    detail = f"Sensors need calibration: {', '.join(issues)}"
                else:
                    status = "fail"
                    detail = f"Multiple sensors need calibration: {', '.join(issues)}"
                break
        except Exception as e:
            status = "fail"
            detail = f"Could not check sensors: {e}"
    else:
        status = "warn"
        detail = "Cannot check sensors without drone connection"

    return {"name": "sensors", "status": status, "detail": detail}


async def _run_connection_check(
    connection_manager: ConnectionManager,
) -> dict[str, Any]:
    """Run MAVLink connection check.

    Args:
        connection_manager: ConnectionManager instance.

    Returns:
        Dict with name, status, and detail fields.
    """
    status: Literal["pass", "warn", "fail"] = "fail"
    detail = ""

    try:
        conn_state = connection_manager.state
        if hasattr(conn_state, 'name'):
            if conn_state.name == "CONNECTED":
                status = "pass"
                detail = "MAVLink connection established"
            elif conn_state.name == "CONNECTING":
                status = "warn"
                detail = "MAVLink connection in progress"
            else:
                status = "fail"
                detail = f"MAVLink disconnected (state={conn_state.name})"
        else:
            # Try to ensure connection
            drone_check = await connection_manager.ensure_connected()
            if drone_check is not None:
                status = "pass"
                detail = "MAVLink connection established"
            else:
                status = "fail"
                detail = "MAVLink not connected"
    except Exception as e:
        status = "fail"
        detail = f"Connection check failed: {e}"

    return {"name": "connection", "status": status, "detail": detail}


# =============================================================================
# MAIN TOOL IMPLEMENTATION
# =============================================================================


async def run_preflight(checks: Optional[list[str]] = None) -> str:
    """MCP Tool: Run preflight checks and return results.

    Runs standard preflight checks for GPS, battery, home position, sensors,
    and connection. Returns a list of CheckResult objects with overall status.

    When to Use:
        - Before arming the drone
        - At the start of a mission planning phase
        - After extended ground time to verify system health
        - When diagnosing why a previous command failed

    Checks Performed:
        - gps: GPS fix quality (3D fix required for safe flight)
        - battery: Battery level (>=25% required for RTL, >=50% preferred)
        - home: Home position set (required for RTL safety)
        - sensors: Sensor calibration (gyro, accel, mag, level)
        - connection: MAVLink connection status

    Args:
        checks: Optional list of specific checks to run. If None, runs all checks.
                Valid names: 'gps', 'battery', 'home', 'sensors', 'connection'.

    Returns:
        JSON string with PreflightResult:
        {
            "checks": [
                {"name": "gps", "status": "pass", "detail": "3D GPS fix (type=4)"},
                {"name": "battery", "status": "pass", "detail": "Battery OK (85.0%)"},
                ...
            ],
            "all_passed": True,
            "warnings": 0,
            "failures": 0
        }

    Example:
        >>> result = await run_preflight()
        >>> data = json.loads(result)
        >>> if data["all_passed"]:
        ...     print("All checks passed - safe to arm")
        ... else:
        ...     print(f"Checks failed: {data['failures']} failures, {data['warnings']} warnings")

    Note:
        This is a read-only operation that doesn't modify drone state.
        It can be called before or after connection is established.
    """
    # Default to all checks if not specified
    if checks is None:
        checks = ["gps", "battery", "home", "sensors", "connection"]

    # Validate check names
    valid_checks = {"gps", "battery", "home", "sensors", "connection"}
    invalid = [c for c in checks if c not in valid_checks]
    if invalid:
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid check names: {invalid}. Valid names: {valid_checks}",
            recoverable=True,
            suggested_action="Use valid check names or omit to run all checks",
        ))

    # Get dependencies
    telemetry_cache = _telemetry_cache
    guardian = _guardian or GuardianProcess()
    connection_manager = _connection_manager or ConnectionManager()

    # Try to get drone connection
    drone = None
    try:
        drone = await connection_manager.ensure_connected()
    except Exception:
        pass  # Connection not available, run checks with telemetry cache only

    # Run checks
    check_results = []
    warnings = 0
    failures = 0

    for check_name in checks:
        result = None

        if check_name == "gps":
            result = await _run_gps_check(drone, telemetry_cache)
        elif check_name == "battery":
            result = await _run_battery_check(drone, telemetry_cache)
        elif check_name == "home":
            result = await _run_home_check(drone, guardian)
        elif check_name == "sensors":
            result = await _run_sensors_check(drone)
        elif check_name == "connection":
            result = await _run_connection_check(connection_manager)

        if result is not None:
            check_results.append(result)

            if result["status"] == "warn":
                warnings += 1
            elif result["status"] == "fail":
                failures += 1

    all_passed = failures == 0

    # Build output
    output = PreflightResult(
        checks=check_results,
        all_passed=all_passed,
        warnings=warnings,
        failures=failures,
    )

    return json.dumps(output.model_dump())


async def handle_run_preflight(arguments: dict[str, Any]) -> str:
    """Handle run_preflight MCP tool call.

    This is the entry point for the MCP server routing.

    Args:
        arguments: Tool arguments with optional 'checks' list.

    Returns:
        JSON string with preflight results.
    """
    checks = arguments.get("checks")
    return await run_preflight(checks)
