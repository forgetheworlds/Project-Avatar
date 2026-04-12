"""Type Protocols for MCP server components.

This module defines strict Protocol classes for type checking and interface
contracts in the MCP server layer. All protocols are runtime_checkable for
runtime isinstance checks.

Example:
    from avatar.mcp_server.protocols import ToolHandlerProtocol

    class MyTool:
        @property
        def name(self) -> str:
            return "my_tool"

        @property
        def description(self) -> str:
            return "Does something useful"

        async def __call__(self, **kwargs) -> dict:
            return {"result": "success"}

    # Runtime check
    assert isinstance(MyTool(), ToolHandlerProtocol)
"""

from typing import Any, Optional, Protocol, runtime_checkable


# =============================================================================
# Protocol Classes
# =============================================================================


@runtime_checkable
class ToolHandlerProtocol(Protocol):
    """Protocol for MCP tool handlers.

    Implementations must provide async invocation, name, and description
    properties for registration with the MCP server.
    """

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with the given arguments.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            Dictionary containing the tool result
        """
        ...

    @property
    def name(self) -> str:
        """Return the tool name for MCP registration.

        Returns:
            Unique tool identifier string
        """
        ...

    @property
    def description(self) -> str:
        """Return the tool description for MCP registration.

        Returns:
            Human-readable description of tool functionality
        """
        ...


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Protocol for tool registries.

    Implementations must manage a collection of tool handlers
    and provide lookup capabilities.
    """

    def register(self, tool: ToolHandlerProtocol) -> None:
        """Register a tool handler.

        Args:
            tool: Tool handler implementing ToolHandlerProtocol

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        ...

    def get(self, name: str) -> Optional[ToolHandlerProtocol]:
        """Get a tool handler by name.

        Args:
            name: Tool name to look up

        Returns:
            Tool handler if found, None otherwise
        """
        ...

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of registered tool names
        """
        ...

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was found and removed, False otherwise
        """
        ...


@runtime_checkable
class ConfirmationProviderProtocol(Protocol):
    """Protocol for confirmation providers.

    Implementations must handle user confirmation requests for
dangerous operations and provide confirmation level queries.
    """

    async def request_confirmation(self, context: dict[str, Any]) -> bool:
        """Request confirmation from the user.

        Args:
            context: Dictionary containing:
                - operation: str - Operation identifier
                - description: str - Human-readable description
                - risk_level: str - Risk level (low, medium, high, critical)
                - params: dict - Operation parameters

        Returns:
            True if confirmed, False if denied or timeout
        """
        ...

    def is_confirmation_required(self, operation: str) -> bool:
        """Check if an operation requires confirmation.

        Args:
            operation: Operation identifier

        Returns:
            True if confirmation is required for this operation
        """
        ...

    def get_risk_level(self, operation: str) -> str:
        """Get the risk level for an operation.

        Args:
            operation: Operation identifier

        Returns:
            Risk level string (low, medium, high, critical)
        """
        ...


@runtime_checkable
class TelemetryBroadcasterProtocol(Protocol):
    """Protocol for telemetry broadcasters.

    Implementations must provide periodic telemetry broadcasting
    and access to the latest telemetry snapshot.
    """

    async def start_broadcast(self, interval_s: float = 1.0) -> None:
        """Start the telemetry broadcast loop.

        Args:
            interval_s: Broadcast interval in seconds (default: 1.0)
        """
        ...

    async def stop_broadcast(self) -> None:
        """Stop the telemetry broadcast loop."""
        ...

    def get_latest_telemetry(self) -> dict[str, Any]:
        """Get the latest telemetry snapshot.

        Returns:
            Dictionary containing latest telemetry data
        """
        ...

    def is_broadcasting(self) -> bool:
        """Check if broadcasting is active.

        Returns:
            True if broadcast loop is running, False otherwise
        """
        ...


@runtime_checkable
class GuardianProcessProtocol(Protocol):
    """Protocol for the Guardian safety process.

    Implementations must provide the core GuardianProcess validation
    that all tools must pass through before execution.
    """

    async def validate(self, operation: str, params: dict[str, Any]) -> tuple[bool, str]:
        """Validate an operation through the Guardian process.

        Args:
            operation: Operation identifier
            params: Operation parameters

        Returns:
            Tuple of (is_valid, reason) where is_valid is True if
            the operation passes all safety checks, False otherwise.
        """
        ...

    def is_operation_allowed(self, state: str, operation: str) -> bool:
        """Check if an operation is allowed in the current state.

        Args:
            state: Current flight state
            operation: Operation to check

        Returns:
            True if operation is allowed in the given state
        """
        ...


@runtime_checkable
class FlightStateMachineProtocol(Protocol):
    """Protocol for the flight state machine.

    Implementations must manage flight state transitions
    according to safety rules.
    """

    @property
    def current_state(self) -> str:
        """Return the current flight state.

        Returns:
            Current state identifier string
        """
        ...

    async def transition_to(
        self, new_state: str, context: Optional[dict[str, Any]] = None
    ) -> bool:
        """Attempt to transition to a new state.

        Args:
            new_state: Target state identifier
            context: Optional context for the transition

        Returns:
            True if transition was successful, False otherwise
        """
        ...

    def is_transition_allowed(self, from_state: str, to_state: str) -> bool:
        """Check if a transition is allowed.

        Args:
            from_state: Source state
            to_state: Target state

        Returns:
            True if transition is allowed
        """
        ...

    def get_allowed_operations(self, state: str) -> list[str]:
        """Get list of operations allowed in a state.

        Args:
            state: State to query

        Returns:
            List of allowed operation identifiers
        """
        ...
