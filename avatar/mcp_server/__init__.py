# Agent-agnostic MCP interface for Project Avatar.
#
# This module provides a Model Context Protocol (MCP) interface for controlling
# autonomous drones. It is designed to be agent-agnostic, meaning any MCP-compatible
# AI agent (Claude Code, OpenCode, etc.) can connect and control the drone.
#
# Architecture 2.0 Components:
#     - AvatarMCPServer: Main server that wires all components together
#     - ConnectionManager: Singleton for persistent MAVSDK connection
#     - TelemetryCache: 100ms refresh non-blocking telemetry access
#     - HeartbeatService: 20Hz emission for PX4 offboard mode
#     - FlightStateMachine: Validated state transitions
#     - AsyncGuardian: 20Hz safety monitoring with failsafe triggers
#
# Example:
#     from avatar.mcp_server import AvatarMCPServer, AvatarMCPServerConfig
#
#     config = AvatarMCPServerConfig(
#         system_address="udp://:14540",
#         telemetry_refresh_ms=100,
#         heartbeat_hz=20.0,
#     )
#     server = AvatarMCPServer(config)
#     await server.initialize()
#     await server.run()  # Process MCP protocol messages

from avatar.mcp_server.protocols import (
    ConfirmationProviderProtocol,
    FlightStateMachineProtocol,
    GuardianProcessProtocol,
    TelemetryBroadcasterProtocol,
    ToolHandlerProtocol,
    ToolRegistryProtocol,
)

# Main server components (Architecture 2.0) - lazy import to avoid MCP dependency issues
try:
    from avatar.mcp_server.server import (
        AvatarMCPServer,
        AvatarMCPServerConfig,
    )
    _SERVER_AVAILABLE = True
except ImportError:
    # MCP module not available - server components won't be importable
    AvatarMCPServer = None  # type: ignore
    AvatarMCPServerConfig = None  # type: ignore
    _SERVER_AVAILABLE = False

# Backward compatibility shims (deprecated, will be removed in v0.4.0)
from avatar.mcp_server.compat import (
    DroneConnection,
    DroneMCPServerConfig,
    DroneMCPServer,
    ConnectionConfig,
    arm,
    takeoff,
    arm_and_takeoff_legacy,
    get_telemetry,
    land_legacy,
    rtl_legacy,
    abort_mission_legacy,
    check_api_compatibility,
    get_migration_guide,
)

__all__ = [
    # Server Components (Architecture 2.0)
    "AvatarMCPServer",
    "AvatarMCPServerConfig",

    # Protocols
    "ConfirmationProviderProtocol",
    "FlightStateMachineProtocol",
    "GuardianProcessProtocol",
    "TelemetryBroadcasterProtocol",
    "ToolHandlerProtocol",
    "ToolRegistryProtocol",

    # Compatibility shims (deprecated)
    "DroneConnection",
    "DroneMCPServerConfig",
    "DroneMCPServer",
    "ConnectionConfig",
    "arm",
    "takeoff",
    "arm_and_takeoff_legacy",
    "get_telemetry",
    "land_legacy",
    "rtl_legacy",
    "abort_mission_legacy",
    "check_api_compatibility",
    "get_migration_guide",
]
