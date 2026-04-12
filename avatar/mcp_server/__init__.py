# Agent-agnostic MCP interface

from avatar.mcp_server.protocols import (
    ConfirmationProviderProtocol,
    FlightStateMachineProtocol,
    GuardianProcessProtocol,
    TelemetryBroadcasterProtocol,
    ToolHandlerProtocol,
    ToolRegistryProtocol,
)

__all__ = [
    "ConfirmationProviderProtocol",
    "FlightStateMachineProtocol",
    "GuardianProcessProtocol",
    "TelemetryBroadcasterProtocol",
    "ToolHandlerProtocol",
    "ToolRegistryProtocol",
]
