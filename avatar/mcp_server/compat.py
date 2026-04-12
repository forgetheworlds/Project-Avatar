"""Backward compatibility layer for MCP server API migration.

This module provides compatibility shims to ensure old API calls continue working
while migration to the new ConnectionManager-based API is in progress.

Migration Guide:
    OLD API (deprecated):
        from avatar.mav.connection import DroneConnection, ConnectionConfig
        conn = DroneConnection()
        await conn.connect()
        drone = conn.drone

    NEW API (recommended):
        from avatar.mav.connection_manager import ConnectionManager
        cm = ConnectionManager()
        await cm.connect()
        drone = await cm.get_drone()

    OLD API (deprecated):
        from avatar.mcp_server.server import DroneMCPServer
        server = DroneMCPServer()

    NEW API (recommended):
        from avatar.mcp_server.server_fastmcp import DroneMCPServer
        server = DroneMCPServer()

Deprecation Warnings:
    All deprecated classes and functions emit DeprecationWarning via the
    warnings module. Set PYTHONWARNINGS=default to see them.

Version:
    This compatibility layer was introduced in v0.2.0.
    Target removal: v0.4.0 (minimum 2 versions with deprecation warnings)
"""

import asyncio
import json
import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Import new API
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mav.connection import ConnectionConfig as NewConnectionConfig
from avatar.mcp_server.tools.flight_tools import FlightTools, FlightToolsConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.state_machine import FlightStateMachine

# Re-export ConnectionConfig for backward compatibility
ConnectionConfig = NewConnectionConfig

logger = logging.getLogger(__name__)

# Module-level warning tracking to avoid duplicate warnings
_warned_classes: set[str] = set()
_warned_functions: set[str] = set()


def _emit_deprecation_warning(name: str, alternative: str, version: str = "0.2.0") -> None:
    """Emit a deprecation warning with migration guidance.

    Args:
        name: Name of the deprecated item.
        alternative: Suggested replacement API.
        version: Version when deprecation started.
    """
    if name in _warned_classes or name in _warned_functions:
        return

    if "class" in name.lower():
        _warned_classes.add(name)
    else:
        _warned_functions.add(name)

    warnings.warn(
        f"{name} is deprecated since v{version} and will be removed in v0.4.0. "
        f"Use {alternative} instead. "
        f"See avatar/mcp_server/compat.py for migration guide.",
        DeprecationWarning,
        stacklevel=3,
    )


# =============================================================================
# DroneConnection Shim
# =============================================================================


class DroneConnection:
    """Backward-compatible shim for DroneConnection.

    This class wraps ConnectionManager to provide the old DroneConnection API
    while internally using the new singleton connection manager.

    DEPRECATED: Use ConnectionManager instead.

    Migration:
        OLD:
            from avatar.mav.connection import DroneConnection, ConnectionConfig
            config = ConnectionConfig(system_address="udp://:14540")
            conn = DroneConnection(config)
            await conn.connect()
            drone = conn.drone

        NEW:
            from avatar.mav.connection_manager import ConnectionManager
            cm = ConnectionManager()
            await cm.connect("udp://:14540")
            drone = await cm.get_drone()
    """

    def __init__(self, config: Optional[NewConnectionConfig] = None):
        """Initialize the compatibility shim.

        Args:
            config: Legacy ConnectionConfig (preserved for API compatibility,
                   but ConnectionManager uses its own config).
        """
        _emit_deprecation_warning(
            "DroneConnection class",
            "ConnectionManager from avatar.mav.connection_manager"
        )

        self.config = config or NewConnectionConfig()
        self._cm = ConnectionManager()
        self._drone: Optional[Any] = None

        # Store config for ConnectionManager to use
        self._cm._system_address = self.config.system_address
        self._cm._max_reconnect_attempts = self.config.max_retries
        self._cm._reconnect_delay_s = self.config.retry_delay_s

    @property
    def drone(self) -> Optional[Any]:
        """Get the MAVSDK System instance (compatibility property).

        Returns:
            System instance if connected, None otherwise.
        """
        if self._cm._state == ConnectionState.CONNECTED:
            return self._cm._drone
        return None

    @property
    def is_connected(self) -> bool:
        """Check if connected (compatibility property).

        Returns:
            True if connected, False otherwise.
        """
        return self._cm.state == ConnectionState.CONNECTED

    async def connect(self) -> bool:
        """Connect to the drone (delegates to ConnectionManager).

        Returns:
            True if connection successful, False otherwise.
        """
        _emit_deprecation_warning(
            "DroneConnection.connect()",
            "ConnectionManager.connect()"
        )

        success = await self._cm.connect(
            system_address=self.config.system_address,
            max_retries=self.config.max_retries,
            retry_delay_s=self.config.retry_delay_s,
        )

        if success:
            self._drone = self._cm._drone

        return success

    async def wait_for_health(self) -> bool:
        """Wait for GPS/gyro calibration and home position.

        Returns:
            True if health checks pass, False otherwise.
        """
        _emit_deprecation_warning(
            "DroneConnection.wait_for_health()",
            "ConnectionManager.health.is_healthy"
        )

        # ConnectionManager auto-monitors health
        # Poll briefly for compatibility
        for _ in range(30):  # 30 seconds max
            if self._cm.health.is_healthy:
                return True
            await asyncio.sleep(1)

        return False

    async def disconnect(self) -> None:
        """Disconnect from the drone (delegates to ConnectionManager)."""
        _emit_deprecation_warning(
            "DroneConnection.disconnect()",
            "ConnectionManager.disconnect()"
        )

        await self._cm.disconnect()
        self._drone = None


# =============================================================================
# Legacy Tool Function Wrappers
# =============================================================================

# These wrappers maintain the exact old signatures and return types


async def arm(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy arm function.

    This was the old pre-takeoff arm command. Now handled automatically
    by arm_and_takeoff. Maintained for API compatibility.

    Args:
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status and message.
    """
    _emit_deprecation_warning(
        "arm()",
        "arm_and_takeoff() from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=0.0)  # Just arm, no takeoff

    # Convert to legacy return format
    return {
        "success": result.get("success", False),
        "message": result.get("message", "Arm command processed"),
        "drone_id": drone_id,
    }


async def takeoff(altitude: float) -> Dict[str, Any]:
    """DEPRECATED: Legacy takeoff function.

    This was the old separate takeoff command. Now part of arm_and_takeoff.
    Maintained for API compatibility.

    Args:
        altitude: Target takeoff altitude in meters.

    Returns:
        Dict with success status and altitude reached.
    """
    _emit_deprecation_warning(
        "takeoff(altitude)",
        "arm_and_takeoff(altitude_m) from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=altitude)

    # Return in legacy format
    return {
        "success": result.get("success", False),
        "altitude_m": result.get("altitude_m", altitude),
        "message": result.get("message", ""),
    }


async def arm_and_takeoff_legacy(
    altitude_m: float = 10.0,
    drone_id: str = "default"
) -> Dict[str, Any]:
    """DEPRECATED: Legacy arm_and_takeoff with drone_id parameter.

    Args:
        altitude_m: Target takeoff altitude in meters.
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status, message, and altitude.
    """
    _emit_deprecation_warning(
        "arm_and_takeoff(altitude_m, drone_id)",
        "arm_and_takeoff(altitude_m) from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=altitude_m)

    # Add legacy fields
    result["drone_id"] = drone_id
    result["version"] = "legacy_compat"

    return result


async def get_telemetry(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy get_telemetry with drone_id parameter.

    Args:
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with telemetry data.
    """
    _emit_deprecation_warning(
        "get_telemetry(drone_id)",
        "get_telemetry() from avatar.mcp_server.tools.telemetry_tools"
    )

    # Import here to avoid circular imports
    from avatar.mcp_server.tools.telemetry_tools import get_telemetry as new_get_telemetry

    result_json = await new_get_telemetry()
    result: Dict[str, Any] = json.loads(result_json)
    result["drone_id"] = drone_id

    return result


async def land_legacy(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy land with drone_id parameter.

    Args:
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status.
    """
    _emit_deprecation_warning(
        "land(drone_id)",
        "land() from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.land()

    result["drone_id"] = drone_id
    result["version"] = "legacy_compat"

    return result


async def rtl_legacy(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy RTL with drone_id parameter.

    Args:
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status.
    """
    _emit_deprecation_warning(
        "rtl(drone_id)",
        "rtl() from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.rtl()

    result["drone_id"] = drone_id
    result["version"] = "legacy_compat"

    return result


async def abort_mission_legacy(
    reason: str = "",
    drone_id: str = "default"
) -> Dict[str, Any]:
    """DEPRECATED: Legacy abort_mission with drone_id parameter.

    Args:
        reason: Reason for abort.
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status.
    """
    _emit_deprecation_warning(
        "abort_mission(reason, drone_id)",
        "abort_mission(reason) from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.abort_mission(reason=reason if reason else None)

    result["drone_id"] = drone_id
    result["version"] = "legacy_compat"

    return result


# =============================================================================
# Legacy Server Config Shim
# =============================================================================


@dataclass
class DroneMCPServerConfig:
    """DEPRECATED: Legacy server configuration.

    Kept for compatibility with code that creates custom configs.
    Internally converted to FlightToolsConfig.

    Migration:
        OLD:
            from avatar.mcp_server.server import DroneMCPServerConfig
            config = DroneMCPServerConfig(system_address="udp://:14540")

        NEW:
            from avatar.mcp_server.tools.flight_tools import FlightToolsConfig
            config = FlightToolsConfig(system_address="udp://:14540")
    """

    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        """Emit deprecation warning after initialization."""
        _emit_deprecation_warning(
            "DroneMCPServerConfig",
            "FlightToolsConfig from avatar.mcp_server.tools.flight_tools"
        )

    def to_flight_tools_config(self) -> FlightToolsConfig:
        """Convert to new FlightToolsConfig format.

        Returns:
            FlightToolsConfig with equivalent settings.
        """
        return FlightToolsConfig(
            system_address=self.system_address,
            max_retries=self.max_retries,
            retry_delay_s=self.retry_delay_s,
            health_timeout_s=self.health_timeout_s,
        )


# =============================================================================
# Utility Functions for Migration
# =============================================================================


def check_api_compatibility() -> Dict[str, Any]:
    """Check API compatibility status.

    Returns information about deprecated APIs and migration status.

    Returns:
        Dict with compatibility status and migration guidance.
    """
    return {
        "compat_version": "0.2.0",
        "target_removal": "0.4.0",
        "deprecated_items": [
            {
                "name": "DroneConnection",
                "replacement": "ConnectionManager",
                "module": "avatar.mav.connection_manager",
            },
            {
                "name": "DroneMCPServerConfig",
                "replacement": "FlightToolsConfig",
                "module": "avatar.mcp_server.tools.flight_tools",
            },
            {
                "name": "arm(drone_id)",
                "replacement": "arm_and_takeoff(altitude_m)",
                "module": "avatar.mcp_server.tools.flight_tools",
            },
            {
                "name": "takeoff(altitude)",
                "replacement": "arm_and_takeoff(altitude_m)",
                "module": "avatar.mcp_server.tools.flight_tools",
            },
            {
                "name": "*_legacy functions",
                "replacement": "Remove drone_id parameter from standard functions",
                "module": "avatar.mcp_server.tools.flight_tools",
            },
        ],
        "migration_guide": (
            "See avatar/mcp_server/compat.py for detailed migration guide. "
            "Set PYTHONWARNINGS=default to see deprecation warnings."
        ),
    }


def get_migration_guide() -> str:
    """Get formatted migration guide.

    Returns:
        Multi-line string with migration instructions.
    """
    return """
================================================================================
MCP SERVER API MIGRATION GUIDE
================================================================================

DEPRECATION NOTICE:
    The old DroneConnection-based API is deprecated as of v0.2.0.
    It will be removed in v0.4.0 (minimum 2 versions with warnings).

QUICK REFERENCE:

1. Connection Management:

    OLD:
        from avatar.mav.connection import DroneConnection, ConnectionConfig
        config = ConnectionConfig(system_address="udp://:14540")
        conn = DroneConnection(config)
        await conn.connect()
        drone = conn.drone

    NEW:
        from avatar.mav.connection_manager import ConnectionManager
        cm = ConnectionManager()
        await cm.connect("udp://:14540")
        drone = await cm.get_drone()  # Fast access after first connect

2. Flight Control:

    OLD:
        from avatar.mcp_server.server import DroneMCPServer
        server = DroneMCPServer()
        result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    NEW:
        from avatar.mcp_server.tools.flight_tools import FlightTools
        tools = FlightTools()
        result = await tools.arm_and_takeoff(altitude_m=10)

3. Tool Functions:

    OLD (with drone_id):
        result = await arm(drone_id="drone1")
        result = await land(drone_id="drone1")

    NEW:
        result = await arm_and_takeoff()  # Uses ConnectionManager singleton
        result = await land()

DEPRECATION WARNINGS:
    Set PYTHONWARNINGS=default environment variable to see all warnings:
        export PYTHONWARNINGS=default

    Or in Python:
        import warnings
        warnings.filterwarnings("default", category=DeprecationWarning)

COMPATIBILITY LAYER:
    The compat.py module provides shims that:
    - Convert old API calls to new API internally
    - Emit deprecation warnings
    - Maintain return type compatibility
    - Support legacy parameter names (e.g., drone_id)

VERSION TIMELINE:
    v0.2.0: Compat layer introduced, deprecation warnings added
    v0.3.0: Continued support, enhanced warnings
    v0.4.0: Deprecated APIs removed (target)

================================================================================
"""


# =============================================================================
# Legacy Server Shim
# =============================================================================


class DroneMCPServer:
    """DEPRECATED: Legacy server class.

    Kept for compatibility with code that imports DroneMCPServer.
    Internally uses AvatarMCPServer.

    Migration:
        OLD:
            from avatar.mcp_server.server import DroneMCPServer
            server = DroneMCPServer()

        NEW:
            from avatar.mcp_server.server import AvatarMCPServer
            server = AvatarMCPServer()
    """

    def __init__(self, config: Optional[DroneMCPServerConfig] = None) -> None:
        """Initialize with deprecation warning.

        Args:
            config: Legacy config (converted to new format).
        """
        _emit_deprecation_warning(
            "DroneMCPServer",
            "AvatarMCPServer from avatar.mcp_server.server"
        )
        # Import here to avoid circular import
        from avatar.mcp_server.server import AvatarMCPServer as NewServer
        from avatar.mcp_server.server import AvatarMCPServerConfig as NewConfig

        if config:
            new_config = NewConfig(
                system_address=config.system_address,
                max_retries=config.max_retries,
                retry_delay_s=config.retry_delay_s,
                connection_timeout_s=config.health_timeout_s,
            )
            self._server = NewServer(new_config)
        else:
            self._server = NewServer()

    def __getattr__(self, name: str) -> Any:
        """Delegate all attribute access to the wrapped server."""
        return getattr(self._server, name)


# Export list for __all__
__all__ = [
    # Shim classes
    "DroneConnection",
    "DroneMCPServerConfig",
    "ConnectionConfig",
    "DroneMCPServer",

    # Legacy tool functions
    "arm",
    "takeoff",
    "arm_and_takeoff_legacy",
    "get_telemetry",
    "land_legacy",
    "rtl_legacy",
    "abort_mission_legacy",

    # Utility functions
    "check_api_compatibility",
    "get_migration_guide",
]
