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

# WHAT ARE PROTOCOL CLASSES?
# --------------------------
# Protocol classes (defined via typing.Protocol) enable "structural subtyping"
# in Python - a formal way to say "if it walks like a duck and talks like a duck,
# it IS a duck" without forcing inheritance.
#
# Traditional inheritance:
#   class BaseTool: pass
#   class ArmTool(BaseTool): pass  # ArmTool IS-A BaseTool
#
# Protocol approach:
#   class ToolHandler(Protocol):
#       @property
#       def name(self) -> str: ...
#       async def __call__(self, **kwargs) -> dict: ...
#
#   class ArmTool:  # No inheritance!
#       @property
#       def name(self) -> str: return "arm"
#       async def __call__(self, **kwargs) -> dict: ...
#
#   # ArmTool satisfies ToolHandler WITHOUT inheriting!
#
# @runtime_checkable DECORATOR:
# -----------------------------
# This decorator enables runtime isinstance() checks. Without it,
# protocols only work for static type checking. With it, you can:
#   if isinstance(my_tool, ToolHandlerProtocol):
#       # my_tool is guaranteed to have name, description, and __call__
#
# WHY THIS MATTERS FOR MCP SERVERS:
# ---------------------------------
# 1. Plugin Architecture: New tools can be added without modifying core code
# 2. Testability: Mock tools don't need to inherit from base classes
# 3. Safety: Type checker ensures all tools have required properties
# 4. Flexibility: Same tool can satisfy multiple protocols


@runtime_checkable
class ToolHandlerProtocol(Protocol):
    """Protocol for MCP tool handlers.

    Implementations must provide async invocation, name, and description
    properties for registration with the MCP server.

    TYPE SAFETY GUARANTEE:
    ----------------------
    This protocol ensures ANY tool (arm, takeoff, land, or custom)
    provides the three essential pieces MCP needs:
    1. name - for the AI to reference the tool
    2. description - for the AI to understand when to use it
    3. __call__ - the actual execution logic

    The static type checker will catch missing properties BEFORE runtime.

    USAGE EXAMPLE:
    --------------
    class TakeoffTool:
        @property
        def name(self) -> str:
            return "takeoff"

        @property
        def description(self) -> str:
            return "Take off to specified altitude (requires confirmation if >10m)"

        async def __call__(self, altitude: float = 5.0, **kwargs) -> dict:
            # Guardian validation happens before this is called
            result = await drone.takeoff(altitude=altitude)
            return {"status": "success", "altitude": altitude}

    # Register with server:
    server.register_tool(TakeoffTool())  # Type-safe registration

    # The MCP server can now:
    # 1. List this tool to the AI with name and description
    # 2. Execute it when the AI calls takeoff(altitude=10)
    # 3. Trust the return type is a dictionary
    """

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with the given arguments.

        WHY ASYNC:
        ----------
        All tool calls are async because drone operations involve
        network I/O (MAVSDK), waiting for state changes, and timeouts.
        Async allows multiple tools to be "in flight" concurrently.

        WHY **kwargs:
        -------------
        Different tools need different parameters (altitude, speed,
        waypoint coordinates). **kwargs provides flexibility while
        still being type-checkable via Protocol implementations.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            Dictionary containing the tool result
        """
        ...

    @property
    def name(self) -> str:
        """Return the tool name for MCP registration.

        WHY THIS MATTERS:
        -----------------
        The AI uses this name to invoke the tool. If it's inconsistent
        between registration and the AI's prompt, the AI will try to
        call non-existent tools. Type safety ensures this property exists.

        Returns:
            Unique tool identifier string
        """
        ...

    @property
    def description(self) -> str:
        """Return the tool description for MCP registration.

        WHY THIS MATTERS:
        -----------------
        This description is sent to the LLM to help it understand
        WHEN and HOW to use the tool. A clear description directly
        impacts the AI's ability to use your drone correctly.

        Good: "Take off to specified altitude. Requires confirmation if >10m."
        Bad: "Takeoff tool"

        Returns:
            Human-readable description of tool functionality
        """
        ...


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Protocol for tool registries.

    Implementations must manage a collection of tool handlers
    and provide lookup capabilities.

    TYPE SAFETY GUARANTEE:
    ----------------------
    Ensures the registry can accept, store, and retrieve any
    object satisfying ToolHandlerProtocol. No need to know the
    concrete class - only that it has name, description, and __call__.

    WHY SEPARATE REGISTRY FROM SERVER:
    ----------------------------------
    Separation of concerns:
    - Registry: Knows HOW to store and lookup tools
    - Server: Knows HOW to expose them via MCP protocol
    - Tools: Know WHAT they do

    This allows swapping registry implementations (dict-based,
    database-backed, etc.) without changing the server.

    USAGE EXAMPLE:
    --------------
    class SimpleRegistry:
        def __init__(self):
            self._tools: dict[str, ToolHandlerProtocol] = {}

        def register(self, tool: ToolHandlerProtocol) -> None:
            if tool.name in self._tools:
                raise ValueError(f"Tool {tool.name} already registered")
            self._tools[tool.name] = tool

        def get(self, name: str) -> Optional[ToolHandlerProtocol]:
            return self._tools.get(name)

        def list_tools(self) -> list[str]:
            return list(self._tools.keys())

        def unregister(self, name: str) -> bool:
            if name in self._tools:
                del self._tools[name]
                return True
            return False

    # Type-safe usage:
    registry: ToolRegistryProtocol = SimpleRegistry()
    registry.register(TakeoffTool())  # OK - satisfies ToolHandlerProtocol
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

        WHY Optional RETURN:
        --------------------
        Tools may not exist (AI could hallucinate a tool name).
        Optional forces the caller to handle the None case,
            preventing AttributeError crashes.

        Args:
            name: Tool name to look up

        Returns:
            Tool handler if found, None otherwise
        """
        ...

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        WHY THIS MATTERS:
        -----------------
        The MCP server sends this list to the AI on connection.
        The AI uses these names to decide which tools are available.

        Returns:
            List of registered tool names
        """
        ...

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name.

        WHY BOOL RETURN:
        ---------------
        Unregistration may fail (tool doesn't exist). Returning bool
        instead of raising exceptions allows graceful handling.

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

    TYPE SAFETY GUARANTEE:
    ----------------------
    Ensures all confirmation systems (CLI prompts, GUI dialogs,
    remote approvals via mobile app) provide the same interface.
    The flight control logic doesn't care HOW confirmation happens,
    only THAT it happens consistently.

    WHY CONFIRMATION LEVELS:
    ------------------------
    Risk levels (low/medium/high/critical) allow graduated response:
    - low: Auto-approve (e.g., status query)
    - medium: Log but proceed (e.g., 5m takeoff)
    - high: Require explicit confirmation (e.g., 50m altitude change)
    - critical: Multi-factor confirmation (e.g., flying beyond geofence)

    USAGE EXAMPLE:
    --------------
    class CliConfirmationProvider:
        def request_confirmation(self, context: dict) -> bool:
            risk = context.get('risk_level', 'low')
            if risk == 'low':
                return True  # Auto-approve

            print(f"\n⚠️  {context['operation']}: {context['description']}")
            print(f"Risk level: {risk}")
            response = input("Proceed? [y/N]: ")
            return response.lower() == 'y'

        def is_confirmation_required(self, operation: str) -> bool:
            return operation in {'arm', 'takeoff', 'land', 'rtl'}

        def get_risk_level(self, operation: str) -> str:
            risk_map = {
                'status': 'low',
                'takeoff': 'medium',
                'arm': 'high',
                'geofence_disable': 'critical'
            }
            return risk_map.get(operation, 'medium')

    # Guardian uses this provider:
    guardian = GuardianProcess(confirmation_provider=CliConfirmationProvider())
    """

    async def request_confirmation(self, context: dict[str, Any]) -> bool:
        """Request confirmation from the user.

        WHY ASYNC:
        ----------
        Confirmation may involve network I/O (push notification,
        waiting for web dashboard response) or timeouts.

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

        WHY THIS MATTERS:
        -----------------
        Not all operations need confirmation. Reading telemetry
        is safe; arming motors is not. This check allows the
        GuardianProcess to fast-path safe operations.

        Args:
            operation: Operation identifier

        Returns:
            True if confirmation is required for this operation
        """
        ...

    def get_risk_level(self, operation: str) -> str:
        """Get the risk level for an operation.

        WHY RISK LEVELS:
        ---------------
        Risk levels enable intelligent handling:
        - UI can color-code (green/yellow/red)
        - Logging can escalate on high/critical
        - Auto-approval can apply to low-risk only

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

    TYPE SAFETY GUARANTEE:
    ----------------------
    Multiple broadcaster implementations (WebSocket, MQTT,
    HTTP SSE, local logging) all satisfy the same interface.
    The telemetry system can switch between them without
    changing the rest of the code.

    WHY BROADCAST PATTERN:
    ---------------------
    The broadcaster pushes telemetry to all connected clients
    (ground station, logging system, AI monitor) without
    each client polling. More efficient and responsive.

    USAGE EXAMPLE:
    --------------
    class WebSocketBroadcaster:
        def __init__(self):
            self._clients: list[WebSocket] = []
            self._latest: dict = {}
            self._running = False

        async def start_broadcast(self, interval_s: float = 1.0) -> None:
            self._running = True
            while self._running:
                telemetry = await gather_telemetry()
                self._latest = telemetry
                for client in self._clients:
                    await client.send_json(telemetry)
                await asyncio.sleep(interval_s)

        async def stop_broadcast(self) -> None:
            self._running = False

        def get_latest_telemetry(self) -> dict[str, Any]:
            return self._latest.copy()

        def is_broadcasting(self) -> bool:
            return self._running

    # Usage:
    broadcaster: TelemetryBroadcasterProtocol = WebSocketBroadcaster()
    await broadcaster.start_broadcast(interval_s=0.5)  # 2Hz update rate
    """

    async def start_broadcast(self, interval_s: float = 1.0) -> None:
        """Start the telemetry broadcast loop.

        WHY CONFIGURABLE INTERVAL:
        --------------------------
        Different use cases need different rates:
        - Flight: 1-10Hz for real-time control
        - Logging: 0.1Hz for long-duration records
        - Testing: Configurable for reproducibility

        Args:
            interval_s: Broadcast interval in seconds (default: 1.0)
        """
        ...

    async def stop_broadcast(self) -> None:
        """Stop the telemetry broadcast loop."""
        ...

    def get_latest_telemetry(self) -> dict[str, Any]:
        """Get the latest telemetry snapshot.

        WHY THIS MATTERS:
        -----------------
        Clients joining mid-flight need current state immediately,
        not waiting for the next broadcast interval.

        Returns:
            Dictionary containing latest telemetry data
        """
        ...

    def is_broadcasting(self) -> bool:
        """Check if broadcasting is active.

        WHY THIS MATTERS:
        -----------------
        Flight control can verify telemetry is flowing before
        starting critical operations. No telemetry = abort.

        Returns:
            True if broadcast loop is running, False otherwise
        """
        ...


@runtime_checkable
class GuardianProcessProtocol(Protocol):
    """Protocol for the Guardian safety process.

    Implementations must provide the core GuardianProcess validation
    that all tools must pass through before execution.

    TYPE SAFETY GUARANTEE:
    ----------------------
    Ensures all Guardian implementations (strict for production,
    relaxed for testing, mock for simulation) provide the same
    safety validation interface. This is CRITICAL for safety -
    the type system helps prevent bypassing the Guardian.

    WHAT IS THE GUARDIAN?
    ---------------------
    The Guardian is a safety gatekeeper that sits between the AI
    and the drone. EVERY tool call flows through it:

    AI Request → Guardian.validate() → [Confirm if needed] → Execute
                      ↓
              [Reject if unsafe]

    WHY A SEPARATE PROTOCOL:
    ------------------------
    The Guardian is the most safety-critical component. Separating
    its protocol ensures:
    1. Multiple implementations (strict/lenient/test)
    2. Cannot be accidentally bypassed (type checker enforces usage)
    3. Clear contract for what safety checks are required

    USAGE EXAMPLE:
    --------------
    class StrictGuardian:
        def __init__(self, confirm_provider: ConfirmationProviderProtocol):
            self._confirm = confirm_provider
            self._state = "DISARMED"

        async def validate(self, operation: str, params: dict) -> tuple[bool, str]:
            # Check if operation allowed in current state
            if not self.is_operation_allowed(self._state, operation):
                return False, f"Operation {operation} not allowed in {self._state}"

            # Get confirmation if needed
            if self._confirm.is_confirmation_required(operation):
                context = {
                    "operation": operation,
                    "description": f"Execute {operation}",
                    "risk_level": self._confirm.get_risk_level(operation),
                    "params": params
                }
                if not await self._confirm.request_confirmation(context):
                    return False, "User denied confirmation"

            return True, "Approved by Guardian"

        def is_operation_allowed(self, state: str, operation: str) -> bool:
            rules = {
                "DISARMED": {"arm", "status"},
                "ARMED": {"takeoff", "disarm", "status"},
                "FLYING": {"land", "rtl", "goto", "status"}
            }
            return operation in rules.get(state, set())

    # ALL tools use the Guardian:
    guardian: GuardianProcessProtocol = StrictGuardian(confirm_provider)
    ok, reason = await guardian.validate("arm", {})
    if not ok:
        raise SafetyError(f"Guardian rejected: {reason}")
    """

    async def validate(self, operation: str, params: dict[str, Any]) -> tuple[bool, str]:
        """Validate an operation through the Guardian process.

        WHY THIS IS ASYNC:
        ------------------
        Validation may require user confirmation (which involves
        waiting for a response), database lookups, or external
        safety service calls.

        WHY (bool, str) RETURN:
        ----------------------
        Every validation result includes BOTH a pass/fail decision
        AND an explanation. Prevents silent rejections and helps
        debugging safety issues.

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

        WHY STATE MATTERS:
        ------------------
        Drones have strict operational states:
        - Can't takeoff if already flying
        - Can't arm if already armed
        - Can't land if disarmed

        State-based rules prevent physically impossible or
        dangerous operations.

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

    TYPE SAFETY GUARANTEE:
    ----------------------
    All state machine implementations (simple enum-based,
    complex hierarchical, or external FSM library wrappers)
    provide the same interface for state transitions.

    WHY A STATE MACHINE:
    --------------------
    Drone flight has distinct, mutually exclusive states:
    - DISARMED: Motors off, safe to approach
    - ARMED: Motors on but not flying
    - TAKING_OFF: Transition to airborne
    - HOVERING: Stationary in air
    - FLYING: Moving under control
    - LANDING: Transition to ground
    - EMERGENCY: Something went wrong

    The state machine enforces valid transitions:
    DISARMED → ARMED → TAKING_OFF → FLYING → LANDING → DISARMED
    (No jumping from DISARMED directly to FLYING!)

    USAGE EXAMPLE:
    --------------
    class SimpleStateMachine:
        def __init__(self):
            self._state = "DISARMED"
            # Define valid transitions
            self._transitions = {
                "DISARMED": {"arm": "ARMED"},
                "ARMED": {"takeoff": "TAKING_OFF", "disarm": "DISARMED"},
                "TAKING_OFF": {"complete": "HOVERING", "abort": "LANDING"},
                "HOVERING": {"move": "FLYING", "land": "LANDING"},
                "FLYING": {"hover": "HOVERING", "land": "LANDING", "rtl": "RTL"},
                "LANDING": {"complete": "DISARMED"},
                "RTL": {"complete": "HOVERING", "land": "LANDING"}
            }
            self._allowed_ops = {
                "DISARMED": {"arm", "status"},
                "ARMED": {"takeoff", "disarm", "status"},
                "HOVERING": {"goto", "land", "rtl", "status"},
                "FLYING": {"goto", "land", "rtl", "status"}
            }

        @property
        def current_state(self) -> str:
            return self._state

        async def transition_to(self, new_state: str, context: Optional[dict] = None) -> bool:
            if self.is_transition_allowed(self._state, new_state):
                self._state = new_state
                return True
            return False

        def is_transition_allowed(self, from_state: str, to_state: str) -> bool:
            return to_state in self._transitions.get(from_state, {}).values()

        def get_allowed_operations(self, state: str) -> list[str]:
            return list(self._allowed_ops.get(state, []))

    # Usage in flight controller:
    fsm: FlightStateMachineProtocol = SimpleStateMachine()
    print(f"Current: {fsm.current_state}")  # DISARMED
    await fsm.transition_to("ARMED")  # Valid
    print(f"Current: {fsm.current_state}")  # ARMED
    await fsm.transition_to("FLYING")  # Invalid! Must go through TAKING_OFF
    """

    @property
    def current_state(self) -> str:
        """Return the current flight state.

        WHY A PROPERTY:
        ---------------
        State is intrinsic to the machine - it doesn't take
        arguments and always reflects current reality. Property
        semantics (not method call) indicate this.

        Returns:
            Current state identifier string
        """
        ...

    async def transition_to(
        self, new_state: str, context: Optional[dict[str, Any]] = None
    ) -> bool:
        """Attempt to transition to a new state.

        WHY ASYNC:
        ----------
        State transitions may involve:
        - Waiting for physical completion (takeoff detected)
        - Network calls to update external state
        - User confirmation for major transitions

        WHY BOOL RETURN:
        ---------------
        Transitions can fail (invalid transition, confirmation
        denied, hardware error). Returning bool instead of
        raising exceptions allows graceful handling.

        WHY OPTIONAL CONTEXT:
        ---------------------
        Context carries extra data for the transition:
        - takeoff: target altitude
        - goto: destination coordinates
        - emergency: error details

        Args:
            new_state: Target state identifier
            context: Optional context for the transition

        Returns:
            True if transition was successful, False otherwise
        """
        ...

    def is_transition_allowed(self, from_state: str, to_state: str) -> bool:
        """Check if a transition is allowed.

        WHY EXPOSE THIS SEPARATELY:
        ---------------------------
        GuardianProcess needs to check transitions WITHOUT
        attempting them. Separate query allows pre-validation.

        Args:
            from_state: Source state
            to_state: Target state

        Returns:
            True if transition is allowed
        """
        ...

    def get_allowed_operations(self, state: str) -> list[str]:
        """Get list of operations allowed in a state.

        WHY THIS MATTERS:
        -----------------
        The MCP server can tell the AI which tools are currently
        available. If hovering, "takeoff" isn't offered. This helps
        the LLM make better decisions.

        Args:
            state: State to query

        Returns:
            List of allowed operation identifiers
        """
        ...
