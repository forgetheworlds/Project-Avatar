"""
Agent-Agnostic MCP Interface for Project Avatar

This __init__.py exports the Model Context Protocol (MCP) interface for
controlling autonomous drones with any AI agent (Claude Code, OpenCode, etc.)

================================================================================
WHAT IS __init__.py? (For Beginners)
================================================================================

This file is Python's way of saying "this folder is a package." When you:

    from avatar.mcp_server import AvatarMCPServer

Python runs this file and uses the imports below to find AvatarMCPServer.

Think of it like a restaurant menu - it shows you what's available without
making you walk into the kitchen to see how it's made.

================================================================================
WHAT IS MCP? (Model Context Protocol)
================================================================================

MCP is a protocol for AI agents to interact with external tools. In this case:

    AI Agent (Claude, OpenCode, etc.)
           ↓ MCP Protocol
    AvatarMCPServer (this package)
           ↓ MAVSDK
         PX4 Drone

The server exposes "tools" that AI agents can call:
    - arm_drone()
    - takeoff(altitude=10)
    - goto_location(lat, lon, alt)
    - land()
    - get_telemetry()

================================================================================
WHY WE EXPORT THESE COMPONENTS
================================================================================

1. SERVER COMPONENTS (Architecture 2.0)
   - AvatarMCPServer: Main server class that runs the MCP protocol
   - AvatarMCPServerConfig: Configuration for the server
   -> These are what most users need to start the server

2. PROTOCOLS (Abstract Interfaces)
   - ToolHandlerProtocol: Interface for command handlers
   - GuardianProcessProtocol: Interface for safety validation
   - TelemetryBroadcasterProtocol: Interface for telemetry streaming
   - FlightStateMachineProtocol: Interface for flight state management
   -> Protocols enable:
     * Type checking (catch errors before running)
     * Testing (mock implementations)
     * Documentation (clear contracts)

3. BACKWARD COMPATIBILITY (Deprecated)
   - DroneMCPServer, DroneConnection: Old API (v0.3.x)
   - arm(), takeoff(), land_legacy(): Legacy functions
   -> These let old code keep working while users migrate

================================================================================
ARCHITECTURE 2.0 COMPONENTS
================================================================================

AvatarMCPServer wires these together:

    ┌─────────────────────────────────────────┐
    │         AvatarMCPServer                 │
    │  ┌─────────────────────────────────┐   │
    │  │      ConnectionManager          │   │ ← Singleton MAVSDK connection
    │  │     (persistent, thread-safe)   │   │
    │  └─────────────────────────────────┘   │
    │  ┌─────────────────────────────────┐   │
    │  │       TelemetryCache            │   │ ← 100ms refresh, non-blocking
    │  │    (async, thread-safe)         │   │
    │  └─────────────────────────────────┘   │
    │  ┌─────────────────────────────────┐   │
    │  │      HeartbeatService           │   │ ← 20Hz for PX4 offboard mode
    │  └─────────────────────────────────┘   │
    │  ┌─────────────────────────────────┐   │
    │  │     FlightStateMachine          │   │ ← Validated state transitions
    │  │   (ARMED → TAKEOFF → MISSION)   │   │
    │  └─────────────────────────────────┘   │
    │  ┌─────────────────────────────────┐   │
    │  │       AsyncGuardian             │   │ ← 20Hz safety monitoring
    │  │   (RTL triggers, kill switch)   │   │
    │  └─────────────────────────────────┘   │
    └─────────────────────────────────────────┘

================================================================================
HOW IMPORTS WORK HERE
================================================================================

Notice the try/except around server imports? This is "lazy loading":

    try:
        from avatar.mcp_server.server import AvatarMCPServer, ...
        _SERVER_AVAILABLE = True
    except ImportError:
        AvatarMCPServer = None
        _SERVER_AVAILABLE = False

WHY? The 'mcp' package has dependencies that might not be installed.
Without this guard, 'import avatar.mcp_server' would FAIL if MCP
isn't installed, even if you only wanted to import protocols.

HOW TO CHECK:
    from avatar.mcp_server import _SERVER_AVAILABLE
    if _SERVER_AVAILABLE:
        from avatar.mcp_server import AvatarMCPServer

================================================================================
PACKAGE STRUCTURE
================================================================================

avatar/mcp_server/
├── __init__.py              <- This file - public API
├── server.py                <- AvatarMCPServer main implementation
├── connection_manager.py    <- MAVSDK connection singleton
├── telemetry_cache.py         <- Cached telemetry (100ms refresh)
├── flight_state_machine.py  <- Validated flight states
├── protocols.py             <- Abstract interfaces (Protocols)
├── compat.py                <- Backward compatibility shims
├── tools/                   <- MCP tool definitions
│   ├── arm_tool.py
│   ├── takeoff_tool.py
│   └── ...
└── handlers/                <- Tool implementation
    ├── arm_handler.py
    └── ...

================================================================================
USAGE EXAMPLES
================================================================================

# Basic server setup (Architecture 2.0)
from avatar.mcp_server import AvatarMCPServer, AvatarMCPServerConfig

config = AvatarMCPServerConfig(
    system_address="udp://:14540",
    telemetry_refresh_ms=100,
    heartbeat_hz=20.0,
)
server = AvatarMCPServer(config)
await server.initialize()
await server.run()

# Protocol imports for type hints
from avatar.mcp_server import ToolHandlerProtocol, GuardianProcessProtocol

def my_handler() -> ToolHandlerProtocol:
    ...

# Backward compatibility (deprecated)
from avatar.mcp_server import DroneMCPServer, arm, takeoff
"""

# =============================================================================
# ACTUAL IMPORTS
# =============================================================================

# --- Protocols (Abstract Interfaces) ---
# These define WHAT components must do, not HOW they do it
# Use for type hints, testing mocks, and clear documentation
from avatar.mcp_server.protocols import (
    ConfirmationProviderProtocol,    # Interface: ask_user_for_confirmation()
    FlightStateMachineProtocol,        # Interface: transition(), get_state()
    GuardianProcessProtocol,           # Interface: validate(), monitor()
    TelemetryBroadcasterProtocol,      # Interface: broadcast(), subscribe()
    ToolHandlerProtocol,               # Interface: handle(), validate()
    ToolRegistryProtocol,              # Interface: register(), get_tool()
)

# --- Main Server Components (Architecture 2.0) ---
# Wrapped in try/except because 'mcp' package is optional
# Without this, importing anything from this package would fail
# if the MCP dependencies aren't installed
try:
    from avatar.mcp_server.server import (
        AvatarMCPServer,                # Main MCP server class
        AvatarMCPServerConfig,          # Configuration dataclass
        avatar_mcp_tool_definitions,    # Tool introspection function
    )
    _SERVER_AVAILABLE = True     # Flag: can use full server
except ImportError:
    # MCP module not available - server components won't be importable
    # We set to None and use 'type: ignore' because type checkers
    # don't understand dynamic imports
    AvatarMCPServer = None       # type: ignore
    AvatarMCPServerConfig = None  # type: ignore
    avatar_mcp_tool_definitions = None  # type: ignore
    _SERVER_AVAILABLE = False

# --- Backward Compatibility Shims (DEPRECATED) ---
# These exist to keep old code working during migration to Architecture 2.0
# They will be REMOVED in version 0.4.0
from avatar.mcp_server.compat import (
    # Old server classes (replaced by AvatarMCPServer)
    DroneConnection,         # Legacy connection wrapper
    DroneMCPServer,          # Legacy server (v0.3.x)
    DroneMCPServerConfig,    # Legacy config
    ConnectionConfig,        # Legacy connection settings

    # Old command functions (replaced by tool-based system)
    arm,                     # Legacy arm command
    takeoff,                 # Legacy takeoff command
    arm_and_takeoff_legacy,  # Legacy combo command
    get_telemetry,           # Legacy telemetry getter
    land_legacy,             # Legacy land command
    rtl_legacy,              # Legacy return-to-launch
    abort_mission_legacy,    # Legacy abort command

    # Migration helpers
    check_api_compatibility,  # Check if code needs updating
    get_migration_guide,      # Print migration instructions
)

# =============================================================================
# PUBLIC API DEFINITION
# =============================================================================

__all__ = [
    # ========================== Server Components =============================
    "AvatarMCPServer",                # Main server class (Architecture 2.0)
    "AvatarMCPServerConfig",          # Server configuration
    "avatar_mcp_tool_definitions",    # Tool introspection for validation

    # ============================= Protocols ==================================
    "ConfirmationProviderProtocol",    # User confirmation interface
    "FlightStateMachineProtocol",      # Flight state management
    "GuardianProcessProtocol",         # Safety validation
    "TelemetryBroadcasterProtocol",    # Telemetry streaming
    "ToolHandlerProtocol",             # Command handlers
    "ToolRegistryProtocol",            # Tool registration

    # ===================== Backward Compatibility =============================
    # WARNING: These are DEPRECATED and will be removed in v0.4.0
    "DroneConnection",
    "DroneMCPServer",
    "DroneMCPServerConfig",
    "ConnectionConfig",
    "arm",
    "takeoff",
    "arm_and_takeoff_legacy",
    "get_telemetry",
    "land_legacy",
    "rtl_legacy",
    "abort_mission_legacy",
    "check_api_compatibility",   # Check if you need to migrate
    "get_migration_guide",       # Get migration instructions
]
