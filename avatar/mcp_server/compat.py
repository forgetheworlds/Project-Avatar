"""
Backward Compatibility Layer for MCP Server API Migration

This module provides compatibility shims to ensure old API calls continue working
while migration to the new ConnectionManager-based architecture is in progress.
It serves as a bridge between the deprecated DroneConnection API and the modern
ConnectionManager-based implementation.

ARCHITECTURE ROLE:
------------------
This module sits at the API COMPATIBILITY LAYER in the Avatar architecture:

    OLD API (v0.1.x)                    NEW API (v0.2.0+)
    =================                   ===================
    DroneConnection          ------>   ConnectionManager (singleton)
    DroneMCPServer           ------>   AvatarMCPServer (FastMCP-based)
    arm(drone_id)            ------>   arm_and_takeoff(altitude_m)
    takeoff(altitude)        ------>   arm_and_takeoff(altitude_m)
    * individual functions   ------>   FlightTools class methods

    compat.py acts as the translation layer between these APIs

Purpose:
    1. Allow existing code to run without immediate modification
    2. Emit deprecation warnings to guide developers toward new API
    3. Provide migration utilities and documentation
    4. Ensure zero-downtime API upgrades

Design Philosophy:
    - Shim classes wrap new implementations and expose old interfaces
    - All deprecated items emit DeprecationWarning via warnings module
    - One-to-one API compatibility - old signatures still work
    - Internal delegation to new ConnectionManager/AvatarMCPServer

MIGRATION GUIDE:
----------------
OLD API (deprecated - will be removed in v0.4.0):
    # Connection management
    from avatar.mcp_server.compat import DroneConnection, ConnectionConfig
    conn = DroneConnection()
    await conn.connect()
    drone = conn.drone

    # Server usage
    from avatar.mcp_server.server import DroneMCPServer
    server = DroneMCPServer()

NEW API (recommended):
    # Connection management - singleton pattern
    from avatar.mav.connection_manager import ConnectionManager
    cm = ConnectionManager()
    await cm.connect()
    drone = await cm.get_drone()  # Async access to drone instance

    # Server usage - FastMCP based
    from avatar.mcp_server.server import AvatarMCPServer
    server = AvatarMCPServer()

    # Flight control - consolidated tools class
    from avatar.mcp_server.tools.flight_tools import FlightTools
    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=10)

DEPRECATION WARNINGS:
---------------------
All deprecated classes and functions emit DeprecationWarning via the Python
warnings module. To see these warnings:

    Command line:
        export PYTHONWARNINGS=default
        python your_script.py

    In Python code:
        import warnings
        warnings.filterwarnings("default", category=DeprecationWarning)

Version Timeline:
    - v0.2.0: Compat layer introduced, deprecation warnings added (current)
    - v0.3.0: Continued support, enhanced warnings
    - v0.4.0: Deprecated APIs removed (target removal version)

Migration Utilities:
    - check_api_compatibility(): Returns dict of deprecated items and replacements
    - get_migration_guide(): Returns formatted multi-line migration guide string

IMPORTANT NOTES:
----------------
1. The compat layer adds minimal overhead - most calls are simple delegation

2. ConnectionManager uses a singleton pattern (one global connection).
   The DroneConnection shim stores config and passes it to ConnectionManager.

3. Legacy 'drone_id' parameters are ignored - ConnectionManager manages
   a single active connection. Multi-drone support requires architecture
   changes beyond this compat layer.

4. Health monitoring in ConnectionManager is automatic and continuous.
   The wait_for_health() shim polls the health property for compatibility.

5. Some legacy return fields (drone_id, version) are added to maintain
   API compatibility but contain no meaningful data.

USAGE EXAMPLES:
---------------
Legacy code continues to work:
    from avatar.mcp_server.compat import DroneConnection  # Shim provides compat

    conn = DroneConnection()
    success = await conn.connect()
    # DeprecationWarning emitted, but function works

Checking migration status programmatically:
    from avatar.mcp_server import compat

    status = compat.check_api_compatibility()
    print(f"Deprecated items: {len(status['deprecated_items'])}")
    print(f"Target removal: {status['target_removal']}")

Getting migration help:
    guide = compat.get_migration_guide()
    print(guide)  # Full formatted guide
"""

import asyncio
import json
import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# New API Imports (what we delegate to)
# =============================================================================
# These imports bring in the modern implementations that the shims wrap

from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mav.connection_config import ConnectionConfig as NewConnectionConfig
from avatar.mcp_server.tools.flight_tools import FlightTools, FlightToolsConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.state_machine import FlightStateMachine

# Re-export ConnectionConfig for backward compatibility
# This allows: from avatar.mcp_server.compat import ConnectionConfig
# to work when importing via compat layer
# For direct import: from avatar.mav.connection_config import ConnectionConfig
ConnectionConfig = NewConnectionConfig

# Module-level logger
logger = logging.getLogger(__name__)

# =============================================================================
# Deprecation Warning Tracking
# =============================================================================
# Track which warnings have been emitted to avoid console spam
# Each unique class/function only warns once per process

_warned_classes: set[str] = set()      # Classes that have emitted warnings
_warned_functions: set[str] = set()    # Functions that have emitted warnings


def _emit_deprecation_warning(name: str, alternative: str, version: str = "0.2.0") -> None:
    """Emit a standardized deprecation warning with migration guidance.

    This function manages warning deduplication to prevent console spam.
    Each unique name only emits one warning per Python process.

    Args:
        name: Name of the deprecated item (e.g., "DroneConnection class")
        alternative: Suggested replacement API (e.g., "ConnectionManager")
        version: Version when deprecation started (default "0.2.0")

    Side Effects:
        Emits warnings.warn() with DeprecationWarning category if not
        previously warned for this name.

    Thread Safety:
        Not thread-safe for simultaneous first-time calls to same name.
        In practice, this is not an issue as warnings are idempotent.
    """
    if name in _warned_classes or name in _warned_functions:
        return  # Already warned about this item

    # Track to prevent duplicate warnings
    if "class" in name.lower():
        _warned_classes.add(name)
    else:
        _warned_functions.add(name)

    # Emit the actual warning with stacklevel=3 to point at caller
    warnings.warn(
        f"{name} is deprecated since v{version} and will be removed in v0.4.0. "
        f"Use {alternative} instead. "
        f"See avatar/mcp_server/compat.py for migration guide.",
        DeprecationWarning,
        stacklevel=3,
    )


# =============================================================================
# DroneConnection Compatibility Shim
# =============================================================================

class DroneConnection:
    """Backward-compatible shim for the deprecated DroneConnection class.

    This class wraps ConnectionManager to provide the old DroneConnection API
    while internally using the new singleton-based connection manager.

    DEPRECATION NOTICE:
        This class is deprecated as of v0.2.0 and will be removed in v0.4.0.
        Use ConnectionManager from avatar.mav.connection_manager instead.

    Migration Path:
        OLD (deprecated):
            from avatar.mcp_server.compat import DroneConnection, ConnectionConfig
            config = ConnectionConfig(system_address="udp://:14540")
            conn = DroneConnection(config)
            await conn.connect()
            drone = conn.drone

        NEW (recommended):
            from avatar.mav.connection_manager import ConnectionManager
            cm = ConnectionManager()
            await cm.connect("udp://:14540")
            drone = await cm.get_drone()

    Implementation Notes:
        - Stores config locally but delegates to ConnectionManager singleton
        - drone property returns None if ConnectionManager not connected
        - is_connected checks ConnectionManager state
        - All methods emit deprecation warnings

    Attributes:
        config: The ConnectionConfig passed to __init__ (stored for compat)
        _cm: Internal ConnectionManager singleton instance
        _drone: Cached drone reference (updated on successful connect)
    """

    def __init__(self, config: Optional[NewConnectionConfig] = None):
        """Initialize the compatibility shim.

        Args:
            config: Legacy ConnectionConfig. Preserved for API compatibility
                   but ConnectionManager maintains its own internal config.
                   The system_address is extracted and stored for connect().
        """
        _emit_deprecation_warning(
            "DroneConnection class",
            "ConnectionManager from avatar.mav.connection_manager"
        )

        self.config = config or NewConnectionConfig()
        self._cm = ConnectionManager()  # Get singleton instance
        self._drone: Optional[Any] = None

        # Extract config values for ConnectionManager to use
        # These are stored as 'private' attributes that ConnectionManager
        # may access if configured to do so
        self._cm._system_address = self.config.system_address
        self._cm._max_reconnect_attempts = self.config.max_retries
        self._cm._reconnect_delay_s = self.config.retry_delay_s

    @property
    def drone(self) -> Optional[Any]:
        """Get the MAVSDK System instance (compatibility property).

        This property provides the same interface as the original DroneConnection
        but retrieves the drone from ConnectionManager internally.

        Returns:
            MAVSDK System instance if ConnectionManager is connected,
            None otherwise.

        Note:
            Unlike the original implementation, this returns None rather than
            a disconnected System instance when not connected.
        """
        if self._cm._state == ConnectionState.CONNECTED:
            return self._cm._drone
        return None

    @property
    def is_connected(self) -> bool:
        """Check if connected (compatibility property).

        Returns:
            True if ConnectionManager state is CONNECTED, False otherwise.
        """
        return self._cm.state == ConnectionState.CONNECTED

    async def connect(self) -> bool:
        """Connect to the drone (delegates to ConnectionManager).

        Args:
            None - uses config from __init__

        Returns:
            True if connection successful, False otherwise.

        Side Effects:
            Emits deprecation warning.
            Updates internal _drone cache on success.
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

        ConnectionManager provides automatic health monitoring via the health
        property. This shim polls that property for backward compatibility.

        Args:
            None

        Returns:
            True if health checks pass, False if timeout exceeded.

        Implementation:
            Polls cm.health.is_healthy for up to 30 seconds (backward compat
            behavior). The modern approach uses cm.health directly without
            explicit waiting.
        """
        _emit_deprecation_warning(
            "DroneConnection.wait_for_health()",
            "ConnectionManager.health.is_healthy"
        )

        # ConnectionManager auto-monitors health continuously
        # We poll briefly for backward compatibility
        for _ in range(30):  # 30 seconds max
            if self._cm.health.is_healthy:
                return True
            await asyncio.sleep(1)

        return False

    async def disconnect(self) -> None:
        """Disconnect from the drone (delegates to ConnectionManager).

        Side Effects:
            Emits deprecation warning.
            Clears internal _drone cache.
        """
        _emit_deprecation_warning(
            "DroneConnection.disconnect()",
            "ConnectionManager.disconnect()"
        )

        await self._cm.disconnect()
        self._drone = None


# =============================================================================
# Legacy Tool Function Wrappers
# =============================================================================
# These functions maintain the exact old signatures and return types
# They delegate to FlightTools and reformat results for compatibility


async def arm(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy arm function.

    This was the old pre-takeoff arm command. In the new architecture,
    arming is handled automatically by arm_and_takeoff(). This function
    is maintained for API compatibility with code that calls arm() separately.

    DEPRECATION NOTICE:
        Use arm_and_takeoff() from avatar.mcp_server.tools.flight_tools instead.

    Args:
        drone_id: Legacy drone identifier (ignored in new architecture
                 which uses ConnectionManager singleton)

    Returns:
        Dict with success status, message, and drone_id for compatibility.
        Format: {"success": bool, "message": str, "drone_id": str}

    Implementation:
        Delegates to FlightTools.arm_and_takeoff(altitude_m=0.0) which arms
        but does not take off when altitude is 0.
    """
    _emit_deprecation_warning(
        "arm()",
        "arm_and_takeoff() from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=0.0)  # Just arm, no takeoff

    # Convert to legacy return format with added drone_id field
    return {
        "success": result.get("success", False),
        "message": result.get("message", "Arm command processed"),
        "drone_id": drone_id,  # Added for backward compatibility
    }


async def takeoff(altitude: float) -> Dict[str, Any]:
    """DEPRECATED: Legacy takeoff function.

    This was the old separate takeoff command. In the new architecture,
    takeoff is combined with arming in arm_and_takeoff(). This function
    is maintained for code that calls takeoff() separately.

    DEPRECATION NOTICE:
        Use arm_and_takeoff(altitude_m) from flight_tools instead.

    Args:
        altitude: Target takeoff altitude in meters above home position.

    Returns:
        Dict with success status, altitude reached, and message.
        Format: {"success": bool, "altitude_m": float, "message": str}

    Implementation:
        Delegates to FlightTools.arm_and_takeoff(altitude_m=altitude).
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

    This is the old signature that included a drone_id parameter. The new
    API removes drone_id as ConnectionManager manages a single connection.

    DEPRECATION NOTICE:
        Use arm_and_takeoff(altitude_m) without drone_id parameter.

    Args:
        altitude_m: Target takeoff altitude in meters.
        drone_id: Legacy drone identifier (ignored, uses ConnectionManager).

    Returns:
        Dict with success status, message, altitude, and legacy compatibility
        fields (drone_id, version).
    """
    _emit_deprecation_warning(
        "arm_and_takeoff(altitude_m, drone_id)",
        "arm_and_takeoff(altitude_m) from avatar.mcp_server.tools.flight_tools"
    )

    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m=altitude_m)

    # Add legacy fields for complete API compatibility
    result["drone_id"] = drone_id
    result["version"] = "legacy_compat"

    return result


async def get_telemetry(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy get_telemetry with drone_id parameter.

    DEPRECATION NOTICE:
        Use get_telemetry() without parameters from telemetry_tools.

    Args:
        drone_id: Legacy drone identifier (ignored).

    Returns:
        Dict with telemetry data and legacy drone_id field.

    Implementation:
        Delegates to new telemetry_tools.get_telemetry() and adds drone_id.
    """
    _emit_deprecation_warning(
        "get_telemetry(drone_id)",
        "get_telemetry() from avatar.mcp_server.tools.telemetry_tools"
    )

    # Import here to avoid circular imports at module level
    from avatar.mcp_server.tools.telemetry_tools import get_telemetry as new_get_telemetry

    result_json = await new_get_telemetry()
    result: Dict[str, Any] = json.loads(result_json)
    result["drone_id"] = drone_id  # Add legacy field

    return result


async def land_legacy(drone_id: str = "default") -> Dict[str, Any]:
    """DEPRECATED: Legacy land with drone_id parameter.

    DEPRECATION NOTICE:
        Use land() without parameters from flight_tools.

    Args:
        drone_id: Legacy drone identifier (ignored).

    Returns:
        Dict with success status and legacy compatibility fields.
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
    """DEPRECATED: Legacy RTL (Return to Launch) with drone_id parameter.

    DEPRECATION NOTICE:
        Use rtl() without parameters from flight_tools.

    Args:
        drone_id: Legacy drone identifier (ignored).

    Returns:
        Dict with success status and legacy compatibility fields.
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

    DEPRECATION NOTICE:
        Use abort_mission(reason) without drone_id from flight_tools.

    Args:
        reason: Reason for abort (passed through to new API).
        drone_id: Legacy drone identifier (ignored).

    Returns:
        Dict with success status and legacy compatibility fields.
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
# Legacy Server Configuration Shim
# =============================================================================

@dataclass
class DroneMCPServerConfig:
    """DEPRECATED: Legacy server configuration dataclass.

    Kept for compatibility with code that creates custom server configurations.
    Internally converted to FlightToolsConfig when used.

    DEPRECATION NOTICE:
        Use FlightToolsConfig from avatar.mcp_server.tools.flight_tools instead.

    Migration:
        OLD:
            from avatar.mcp_server.server import DroneMCPServerConfig
            config = DroneMCPServerConfig(system_address="udp://:14540")

        NEW:
            from avatar.mcp_server.tools.flight_tools import FlightToolsConfig
            config = FlightToolsConfig(system_address="udp://:14540")

    Attributes:
        system_address: MAVLink connection string (passed through)
        max_retries: Connection retry attempts (passed through)
        retry_delay_s: Seconds between retries (passed through)
        health_timeout_s: Health check timeout (passed through)
    """

    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        """Emit deprecation warning after dataclass initialization."""
        _emit_deprecation_warning(
            "DroneMCPServerConfig",
            "FlightToolsConfig from avatar.mcp_server.tools.flight_tools"
        )

    def to_flight_tools_config(self) -> FlightToolsConfig:
        """Convert to new FlightToolsConfig format.

        This method allows code to explicitly migrate configs:
            old_config = DroneMCPServerConfig(...)
            new_config = old_config.to_flight_tools_config()

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
    """Check API compatibility status and migration progress.

    Returns structured information about deprecated APIs and their replacements.
    Useful for programmatically checking what needs migration.

    Returns:
        Dict containing:
            - compat_version: Version when compat layer was introduced
            - target_removal: Version when deprecated APIs will be removed
            - deprecated_items: List of dicts with name, replacement, module
            - migration_guide: Brief pointer to full documentation

    Example:
        status = check_api_compatibility()
        for item in status['deprecated_items']:
            print(f"{item['name']} -> {item['replacement']}")
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
    """Get formatted migration guide as a multi-line string.

    Returns:
        Complete migration guide with examples and timeline.
        Print this string to display the full guide to users.

    Example:
        guide = get_migration_guide()
        print(guide)
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

    OLD (deprecated):
        from avatar.mcp_server.compat import DroneConnection, ConnectionConfig
        config = ConnectionConfig(system_address="udp://:14540")
        conn = DroneConnection(config)
        await conn.connect()
        drone = conn.drone

    Note: The original import from avatar.mav.connection has been removed.
    Use avatar.mcp_server.compat for the shim or avatar.mav.connection_config for ConnectionConfig.

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
    """DEPRECATED: Legacy server class shim.

    Kept for compatibility with code that imports DroneMCPServer from the
    old server module. Internally delegates to AvatarMCPServer.

    DEPRECATION NOTICE:
        Use AvatarMCPServer from avatar.mcp_server.server instead.

    Migration:
        OLD:
            from avatar.mcp_server.server import DroneMCPServer
            server = DroneMCPServer()

        NEW:
            from avatar.mcp_server.server import AvatarMCPServer
            server = AvatarMCPServer()

    Implementation:
        Uses __getattr__ delegation to forward all attribute access to the
        wrapped AvatarMCPServer instance. This provides complete API compatibility.
    """

    def __init__(self, config: Optional[DroneMCPServerConfig] = None) -> None:
        """Initialize with deprecation warning and create wrapped server.

        Args:
            config: Legacy DroneMCPServerConfig (converted to new format).
                   If None, AvatarMCPServer uses its defaults.
        """
        _emit_deprecation_warning(
            "DroneMCPServer",
            "AvatarMCPServer from avatar.mcp_server.server"
        )

        # Import here to avoid circular import at module level
        from avatar.mcp_server.server import AvatarMCPServer as NewServer
        from avatar.mcp_server.server import AvatarMCPServerConfig as NewConfig

        # Convert legacy config to new format if provided
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
        """Delegate all attribute access to the wrapped server.

        This enables complete API compatibility - any attribute access on
        this shim is forwarded to the actual AvatarMCPServer instance.

        Args:
            name: Attribute name being accessed.

        Returns:
            Attribute from wrapped AvatarMCPServer.
        """
        return getattr(self._server, name)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Shim classes that replace old implementations
    "DroneConnection",           # -> ConnectionManager
    "DroneMCPServerConfig",      # -> FlightToolsConfig
    "ConnectionConfig",          # Re-export from connection module
    "DroneMCPServer",            # -> AvatarMCPServer

    # Legacy tool functions with drone_id parameters
    "arm",                       # Use arm_and_takeoff()
    "takeoff",                   # Use arm_and_takeoff()
    "arm_and_takeoff_legacy",    # Remove drone_id parameter
    "get_telemetry",             # Remove drone_id parameter
    "land_legacy",               # Remove drone_id parameter
    "rtl_legacy",                # Remove drone_id parameter
    "abort_mission_legacy",      # Remove drone_id parameter

    # Utility functions for migration assistance
    "check_api_compatibility",   # Get migration status
    "get_migration_guide",       # Get full guide text
]
