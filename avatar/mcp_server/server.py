"""
Avatar MCP Server - Agent-agnostic Model Context Protocol interface.

Exposes drone control tools to any MCP-compatible AI agent (Claude Code, OpenCode, etc.).
Architecture 2.0: Cloud LLM + Agent-Agnostic MCP + PX4 SITL Simulation.

Key Components:
    - ConnectionManager: Singleton for persistent MAVSDK connection
    - TelemetryCache: 100ms refresh non-blocking telemetry access
    - HeartbeatService: 20Hz emission for offboard mode safety
    - FlightStateMachine: Validated state transitions
    - AsyncGuardian: 20Hz safety monitoring with failsafe triggers
    - FlightTools: High-level flight control operations

Lifecycle:
    1. initialize(): Connect to drone, start services
    2. run(): Process MCP protocol messages
    3. shutdown(): Graceful cleanup in reverse order

Example:
    server = AvatarMCPServer()
    await server.initialize()
    await server.run()
    # Or for programmatic control:
    await server.shutdown()
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import MagicMock

# MCP imports with graceful fallback for testing
# MCP (Model Context Protocol) is required for production but may not be installed in test environments
try:
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.lowlevel.server import NotificationOptions
    from mcp.server.models import InitializationOptions
    _MCP_AVAILABLE = True
except ImportError:
    # MCP not available - create mock classes for testing
    _MCP_AVAILABLE = False

    class Server:  # type: ignore
        """Mock MCP Server for testing without mcp module."""
        def __init__(self, name: str) -> None:
            self.name = name

        def list_tools(self) -> Any:
            def decorator(func: Any) -> Any: return func
            return decorator

        def call_tool(self) -> Any:
            def decorator(func: Any) -> Any: return func
            return decorator

        def get_capabilities(self, **kwargs):  # type: ignore
            return {}

        async def run(self, *args, **kwargs):  # type: ignore
            pass

    class types:  # type: ignore
        class TextContent:
            def __init__(self, type: str = "text", text: str = "") -> None:
                self.type = type
                self.text = text

        class Tool:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

    class NotificationOptions:  # type: ignore
        pass

    class InitializationOptions:  # type: ignore
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)


# Core components - singleton pattern enforced
from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData
from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig, HeartbeatSource
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mav.guardian_async import AsyncGuardian, GuardianConfig, SafetyAction
from avatar.core.context_managers import _get_telemetry_from_drone

# Tool modules
from avatar.mcp_server.tools.flight_tools import (
    FlightTools, FlightToolsConfig,
    arm_and_takeoff, land, rtl, abort_mission, goto_gps,
    fly_body_offset, set_velocity, hold,
    set_state_machine, set_telemetry_cache,
)
from avatar.mcp_server.tools.telemetry_tools import get_telemetry
from avatar.mcp_server.tools.vision_tools import detect_objects, get_detected_objects

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _create_mock_velocity_ned_yaw(
    north_m_s: float, east_m_s: float, down_m_s: float, yaw_deg: float
) -> Any:
    """Create a mock VelocityNedYaw for type checking without mavsdk import."""
    mock = MagicMock()
    mock.north_m_s = north_m_s
    mock.east_m_s = east_m_s
    mock.down_m_s = down_m_s
    mock.yaw_deg = yaw_deg
    return mock


@dataclass
class AvatarMCPServerConfig:
    """Configuration for AvatarMCPServer.

    Attributes:
        system_address: MAVSDK system address (default: udp://:14540 for SITL)
        connection_timeout_s: Timeout for initial connection
        telemetry_refresh_ms: Telemetry cache refresh interval in milliseconds
        heartbeat_hz: Heartbeat emission frequency (default: 20Hz)
        enable_guardian: Whether to enable AsyncGuardian monitoring
        enable_auto_failsafe: Whether to auto-trigger failsafe on critical issues
        max_retries: Maximum connection retry attempts
        retry_delay_s: Delay between connection retries in seconds
    """

    system_address: str = "udp://:14540"
    connection_timeout_s: float = 30.0
    telemetry_refresh_ms: int = 100  # 100ms as per requirements
    heartbeat_hz: float = 20.0  # 20Hz as per requirements
    enable_guardian: bool = True
    enable_auto_failsafe: bool = True
    max_retries: int = 3
    retry_delay_s: float = 1.0


class AvatarMCPServer:
    """
    Avatar MCP Server - Main entry point for drone MCP interface.

    This server provides a complete integration layer that:
    - Manages a singleton ConnectionManager for persistent drone connection
    - Maintains a TelemetryCache with 100ms refresh for fast data access
    - Emits 20Hz heartbeats required for PX4 offboard mode
    - Tracks flight state with a validated FlightStateMachine
    - Monitors safety with AsyncGuardian's concurrent monitoring tasks

    All tools share the same component instances (singleton pattern), ensuring
    consistent state and eliminating duplicate resource usage.

    Usage:
        server = AvatarMCPServer()
        await server.initialize()
        await server.run()  # Runs until shutdown signal

    Or with custom config:
        config = AvatarMCPServerConfig(
            system_address="serial:///dev/ttyUSB0:921600",
            telemetry_refresh_ms=50,  # Faster refresh
        )
        server = AvatarMCPServer(config)
        await server.initialize()
    """

    def __init__(self, config: Optional[AvatarMCPServerConfig] = None):
        """Initialize the Avatar MCP server.

        Args:
            config: Server configuration. Uses defaults if not provided.

        Note:
            This constructor does not establish connections or start services.
            Call initialize() to fully start the server.
        """
        self.config = config or AvatarMCPServerConfig()
        self.server = Server("avatar-mcp")

        # Core components - all singletons or shared instances
        self.connection_manager: ConnectionManager = ConnectionManager()
        self.telemetry_cache: TelemetryCache = TelemetryCache(
            refresh_ms=self.config.telemetry_refresh_ms,
            stale_ms=500,  # 500ms stale threshold
            history_size=100,
        )
        self.heartbeat_service: HeartbeatService = HeartbeatService(
            config=HeartbeatConfig(
                heartbeat_hz=self.config.heartbeat_hz,
                offboard_timeout_s=0.5,
                warning_threshold_s=0.3,
                emit_heartbeat=True,
            )
        )
        self.state_machine: FlightStateMachine = FlightStateMachine()
        self.guardian: AsyncGuardian = AsyncGuardian(
            connection_manager=self.connection_manager,
            heartbeat_service=self.heartbeat_service,
            state_machine=self.state_machine,
            config=GuardianConfig(
                heartbeat_interval_s=1.0 / self.config.heartbeat_hz,
                offboard_timeout_s=0.5,
                auto_failsafe=self.config.enable_auto_failsafe,
                enable_heartbeat_emit=False,  # Service handles this
                enable_resource_monitor=True,
                enable_state_monitor=True,
                enable_vio_monitor=True,
                enable_network_monitor=True,
            ),
        )

        # Flight tools with shared state machine
        self.flight_tools = FlightTools(
            config=FlightToolsConfig(
                system_address=self.config.system_address,
                max_retries=self.config.max_retries,
                retry_delay_s=self.config.retry_delay_s,
                health_timeout_s=self.config.connection_timeout_s,
            ),
            state_machine=self.state_machine,
        )

        # Set global references for tool functions
        set_state_machine(self.state_machine)
        set_telemetry_cache(self.telemetry_cache)

        # Runtime state
        self._initialized = False
        self._shutdown_event = asyncio.Event()
        self._tasks: Set[asyncio.Task[Any]] = set()

        # Set up MCP handlers
        self._setup_handlers()

        logger.info("AvatarMCPServer initialized (components created, not yet started)")

    def _setup_handlers(self) -> None:
        """Set up MCP protocol handlers for tool registration and execution."""

        @self.server.list_tools()  # type: ignore[untyped-decorator]
        async def handle_list_tools() -> List[types.Tool]:
            """List available drone control tools."""
            return [
                # Flight control tools
                types.Tool(
                    name="arm_and_takeoff",
                    description=(
                        "Arm the drone and takeoff to a specified altitude. "
                        "The drone must be connected and have GPS lock before calling. "
                        "Returns success/failure status and altitude reached. "
                        "Default altitude: 10m. Max: 120m (FAA Part 107 limit)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "altitude_m": {
                                "type": "number",
                                "description": "Target takeoff altitude in meters",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 120,
                            }
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="get_telemetry",
                    description=(
                        "Get current drone telemetry from cache (fast, non-blocking). "
                        "Returns position, velocity, attitude, battery, flight mode. "
                        "Cache refreshes every 100ms. Check is_stale field."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                types.Tool(
                    name="land",
                    description=(
                        "Command the drone to land at its current position. "
                        "The drone will descend vertically and disarm after landing. "
                        "Safe to call from any flying state."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                types.Tool(
                    name="rtl",
                    description=(
                        "Return to Launch (RTL) - fly back to home position and land. "
                        "Use this for failsafe recovery or mission completion. "
                        "Requires home position to be set."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                types.Tool(
                    name="abort_mission",
                    description=(
                        "Abort the current mission and make the drone hover in place. "
                        "Use for emergency stops or when you need to pause operations. "
                        "The drone will remain hovering until a new command is issued."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Optional reason for abort (for logging)",
                            }
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="goto_gps",
                    description=(
                        "Navigate to GPS coordinates. "
                        "Drone must be in flying state (HOVERING, FLYING, etc.). "
                        "Will transition to POSITION_CONTROL state."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lat": {
                                "type": "number",
                                "description": "Target latitude in degrees (-90 to 90)",
                            },
                            "lon": {
                                "type": "number",
                                "description": "Target longitude in degrees (-180 to 180)",
                            },
                            "alt_m": {
                                "type": "number",
                                "description": "Target altitude in meters (0 = current altitude)",
                                "default": 0,
                            },
                            "speed_ms": {
                                "type": "number",
                                "description": "Travel speed in m/s",
                                "default": 5.0,
                                "minimum": 0.1,
                                "maximum": 15.0,
                            },
                        },
                        "required": ["lat", "lon"],
                    },
                ),
                types.Tool(
                    name="fly_body_offset",
                    description=(
                        "Fly to body-relative offset position. "
                        "Moves forward/back, left/right, up/down relative to current heading. "
                        "Body frame: +forward=X, +right=Y. "
                        "Requires flying state. Transitions to POSITION_CONTROL."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "forward_m": {
                                "type": "number",
                                "description": "Distance forward (positive) or back (negative) in meters",
                                "default": 0.0,
                            },
                            "right_m": {
                                "type": "number",
                                "description": "Distance right (positive) or left (negative) in meters",
                                "default": 0.0,
                            },
                            "up_m": {
                                "type": "number",
                                "description": "Distance up (positive) or down (negative) in meters",
                                "default": 0.0,
                            },
                            "yaw_align": {
                                "type": "boolean",
                                "description": "If True, align yaw to movement direction",
                                "default": False,
                            },
                            "speed_m_s": {
                                "type": "number",
                                "description": "Approach speed in m/s",
                                "default": 5.0,
                                "minimum": 0.1,
                                "maximum": 15.0,
                            },
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="set_velocity",
                    description=(
                        "Set velocity setpoint in NED frame (offboard mode). "
                        "CRITICAL: Must maintain 20Hz stream or PX4 triggers failsafe. "
                        "Max horizontal: 15 m/s. Max vertical: 3 m/s. "
                        "Requires flying state. Transitions to VELOCITY_CONTROL."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "north_m_s": {
                                "type": "number",
                                "description": "Velocity north (positive) / south (negative) in m/s",
                                "default": 0.0,
                            },
                            "east_m_s": {
                                "type": "number",
                                "description": "Velocity east (positive) / west (negative) in m/s",
                                "default": 0.0,
                            },
                            "down_m_s": {
                                "type": "number",
                                "description": "Velocity down (positive) / up (negative) in m/s",
                                "default": 0.0,
                            },
                            "yaw_deg": {
                                "type": "number",
                                "description": "Absolute yaw angle in degrees (0=north, 90=east)",
                                "default": 0.0,
                            },
                            "duration_s": {
                                "type": "number",
                                "description": "Duration to maintain setpoint in seconds",
                                "default": 1.0,
                                "minimum": 0.1,
                                "maximum": 10.0,
                            },
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="hold",
                    description=(
                        "Hold position with monitoring. "
                        "Enters HOVERING state and monitors for position drift. "
                        "Optionally auto-triggers RTL if drift exceeds tolerance."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "duration_s": {
                                "type": "number",
                                "description": "Duration to hold position in seconds",
                                "default": 5.0,
                                "minimum": 1.0,
                                "maximum": 60.0,
                            },
                            "position_tolerance_m": {
                                "type": "number",
                                "description": "Allowed position drift in meters",
                                "default": 1.0,
                                "minimum": 0.1,
                                "maximum": 10.0,
                            },
                            "auto_rtl_on_drift": {
                                "type": "boolean",
                                "description": "If True, RTL when drift exceeds tolerance",
                                "default": False,
                            },
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="detect_objects",
                    description=(
                        "Detect objects in camera frame using YOLO. "
                        "Returns detected objects with bounding boxes and confidence."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "confidence_threshold": {
                                "type": "number",
                                "description": "Minimum detection confidence (0.0-1.0)",
                                "default": 0.5,
                            },
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="get_detected_objects",
                    description=(
                        "Get currently detected objects from cache. "
                        "Returns last detection results without running new inference."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                types.Tool(
                    name="get_status",
                    description=(
                        "Get comprehensive server status. "
                        "Returns connection state, flight state, guardian status, "
                        "telemetry cache metrics, and heartbeat metrics."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ]

        @self.server.call_tool()  # type: ignore[untyped-decorator]
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[types.TextContent]:
            """Handle tool execution requests.

            Args:
                name: Name of the tool to execute.
                arguments: Tool arguments from the caller.

            Returns:
                List of TextContent with the result.
            """
            try:
                # Ensure server is initialized
                if not self._initialized:
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps({
                                "success": False,
                                "error": "Server not initialized. Call initialize() first.",
                            }),
                        )
                    ]

                # Route to appropriate handler
                result = await self._route_tool(name, arguments)
                return [types.TextContent(type="text", text=result)]

            except Exception as e:
                logger.exception(f"Error executing tool {name}")
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": str(e),
                        }),
                    )
                ]

    async def _route_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Route tool call to appropriate handler.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            JSON string result.
        """
        # Flight control tools
        if name == "arm_and_takeoff":
            return await arm_and_takeoff(arguments.get("altitude_m", 10.0))

        elif name == "land":
            return await land()

        elif name == "rtl":
            return await rtl()

        elif name == "abort_mission":
            return await abort_mission(arguments.get("reason", ""))

        elif name == "goto_gps":
            return await goto_gps(
                lat=arguments.get("lat", 0.0),
                lon=arguments.get("lon", 0.0),
                alt_m=arguments.get("alt_m", 0.0),
                speed_ms=arguments.get("speed_ms", 5.0),
            )

        elif name == "fly_body_offset":
            return await fly_body_offset(
                forward_m=arguments.get("forward_m", 0.0),
                right_m=arguments.get("right_m", 0.0),
                up_m=arguments.get("up_m", 0.0),
                yaw_align=arguments.get("yaw_align", False),
                speed_m_s=arguments.get("speed_m_s", 5.0),
            )

        elif name == "set_velocity":
            return await set_velocity(
                north_m_s=arguments.get("north_m_s", 0.0),
                east_m_s=arguments.get("east_m_s", 0.0),
                down_m_s=arguments.get("down_m_s", 0.0),
                yaw_deg=arguments.get("yaw_deg", 0.0),
                duration_s=arguments.get("duration_s", 1.0),
            )

        elif name == "hold":
            return await hold(
                duration_s=arguments.get("duration_s", 5.0),
                position_tolerance_m=arguments.get("position_tolerance_m", 1.0),
                auto_rtl_on_drift=arguments.get("auto_rtl_on_drift", False),
            )

        # Telemetry tools
        elif name == "get_telemetry":
            return await get_telemetry()

        # Vision tools
        elif name == "detect_objects":
            return await detect_objects(arguments.get("confidence_threshold", 0.5))

        elif name == "get_detected_objects":
            return await get_detected_objects()

        # Status tool
        elif name == "get_status":
            return json.dumps(self.get_status())

        else:
            return json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    async def initialize(self) -> bool:
        """Initialize all components and start services.

        This method:
        1. Connects to the drone via ConnectionManager
        2. Starts the TelemetryCache with the configured refresh interval
        3. Starts the HeartbeatService with 20Hz emission
        4. Initializes the FlightStateMachine
        5. Starts the AsyncGuardian monitoring

        Returns:
            True if initialization successful, False otherwise.
        """
        if self._initialized:
            logger.debug("Server already initialized")
            return True

        try:
            logger.info("Initializing Avatar MCP Server...")

            # Step 1: Connect to drone
            logger.info(f"Connecting to drone at {self.config.system_address}...")
            connected = await self.connection_manager.connect(
                system_address=self.config.system_address,
                max_retries=self.config.max_retries,
                retry_delay_s=self.config.retry_delay_s,
            )
            if not connected:
                logger.error("Failed to connect to drone")
                return False
            logger.info("Connected to drone successfully")

            # Step 2: Start telemetry cache
            logger.info(f"Starting telemetry cache ({self.config.telemetry_refresh_ms}ms refresh)...")

            async def telemetry_provider() -> TelemetryData:
                """Provider function that fetches from drone via ConnectionManager."""
                drone = await self.connection_manager.get_drone()
                if drone is None:
                    raise ConnectionError("Drone not connected")
                return await _get_telemetry_from_drone(drone)

            await self.telemetry_cache.start(telemetry_provider)
            logger.info("Telemetry cache started")

            # Step 3: Start heartbeat service (20Hz)
            logger.info(f"Starting heartbeat service ({self.config.heartbeat_hz}Hz)...")
            await self.heartbeat_service.start()
            logger.info("Heartbeat service started")

            # Step 4: Initialize state machine from telemetry
            logger.info("Initializing state machine...")
            await self._sync_state_machine_from_telemetry()
            logger.info(f"State machine initialized: {self.state_machine.current_state_name}")

            # Step 5: Start guardian monitoring
            if self.config.enable_guardian:
                logger.info("Starting AsyncGuardian monitoring...")
                await self.guardian.start()
                logger.info("Guardian monitoring started")

            self._initialized = True
            logger.info("Avatar MCP Server initialized successfully")
            return True

        except Exception as e:
            logger.exception(f"Initialization failed: {e}")
            # Cleanup on failure
            await self._cleanup_partial()
            return False

    async def _sync_state_machine_from_telemetry(self) -> None:
        """Sync state machine from current telemetry."""
        try:
            # Get fresh telemetry data
            data = await self.telemetry_cache.get_fresh_data(max_age_ms=1000)
            if data:
                self.state_machine.sync_from_telemetry({
                    "armed": data.armed,
                    "in_air": data.in_air,
                    "landed": not data.in_air,
                })
            else:
                # No telemetry yet, start in INIT state
                self.state_machine.transition(
                    FlightState.INIT, "initialization", "system"
                )
        except Exception as e:
            logger.warning(f"Could not sync state machine from telemetry: {e}")
            # Default to INIT
            self.state_machine.transition(
                FlightState.INIT, "initialization_fallback", "system"
            )

    async def _cleanup_partial(self) -> None:
        """Cleanup partial initialization on failure."""
        logger.info("Cleaning up partial initialization...")

        try:
            await self.telemetry_cache.stop()
        except Exception as e:
            logger.warning(f"Error stopping telemetry cache: {e}")

        try:
            await self.heartbeat_service.stop()
        except Exception as e:
            logger.warning(f"Error stopping heartbeat service: {e}")

        try:
            await self.guardian.stop()
        except Exception as e:
            logger.warning(f"Error stopping guardian: {e}")

        try:
            await self.connection_manager.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting: {e}")

    async def shutdown(self) -> None:
        """Graceful shutdown of all components.

        Cleanup order (reverse of initialization):
        1. Stop AsyncGuardian monitoring
        2. Stop HeartbeatService
        3. Stop TelemetryCache
        4. Disconnect from drone
        5. Reset state
        """
        if not self._initialized:
            logger.debug("Server not initialized, nothing to shutdown")
            return

        logger.info("Shutting down Avatar MCP Server...")

        # Step 1: Stop guardian (safety monitoring first)
        if self.config.enable_guardian:
            logger.info("Stopping guardian...")
            try:
                await self.guardian.stop()
                logger.info("Guardian stopped")
            except Exception as e:
                logger.warning(f"Error stopping guardian: {e}")

        # Step 2: Stop heartbeat service
        logger.info("Stopping heartbeat service...")
        try:
            await self.heartbeat_service.stop()
            logger.info("Heartbeat service stopped")
        except Exception as e:
            logger.warning(f"Error stopping heartbeat service: {e}")

        # Step 3: Stop telemetry cache
        logger.info("Stopping telemetry cache...")
        try:
            await self.telemetry_cache.stop()
            logger.info("Telemetry cache stopped")
        except Exception as e:
            logger.warning(f"Error stopping telemetry cache: {e}")

        # Step 4: Disconnect from drone
        logger.info("Disconnecting from drone...")
        try:
            await self.connection_manager.disconnect()
            logger.info("Disconnected from drone")
        except Exception as e:
            logger.warning(f"Error disconnecting from drone: {e}")

        # Reset state
        self._initialized = False
        self._shutdown_event.set()

        logger.info("Avatar MCP Server shutdown complete")

    async def run(self) -> None:
        """Run the MCP server using stdio transport.

        This is the main entry point for the server. It starts
        listening for MCP protocol messages on stdin/stdout.

        Note:
            This method blocks until the server is shutdown.
            Call initialize() before calling run().
        """
        if not self._initialized:
            logger.error("Server not initialized. Call initialize() first.")
            raise RuntimeError("Server not initialized. Call initialize() first.")

        if not _MCP_AVAILABLE:
            raise RuntimeError(
                "MCP module not available. Install with: pip install mcp"
            )

        logger.info("Starting Avatar MCP Server (stdio transport)")

        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="avatar-mcp",
                    server_version="0.2.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status.

        Returns:
            Dictionary containing:
            - initialized: Whether server is initialized
            - connection: ConnectionManager state and health
            - telemetry: TelemetryCache metrics
            - heartbeat: HeartbeatService metrics
            - state_machine: Current flight state
            - guardian: Guardian status (if enabled)
        """
        status: Dict[str, Any] = {
            "initialized": self._initialized,
            "connection": {
                "state": self.connection_manager.state.name,
                "health": {
                    "is_healthy": self.connection_manager.health.is_healthy,
                    "gps_lock": self.connection_manager.health.gps_lock,
                    "home_position_set": self.connection_manager.health.home_position_set,
                    "error_count": self.connection_manager.health.error_count,
                },
            },
            "telemetry": self.telemetry_cache.get_metrics(),
            "heartbeat": self.heartbeat_service.get_metrics(),
            "state_machine": {
                "current_state": self.state_machine.current_state_name,
                "is_flying": self.state_machine.is_flying,
                "is_armed": self.state_machine.is_armed,
            },
        }

        if self.config.enable_guardian:
            guardian_status = self.guardian.get_status()
            # Convert Alert dataclasses to dicts for JSON serialization
            alerts_list = [
                {
                    "level": alert.level,
                    "source": alert.source,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                    "action_taken": alert.action_taken,
                }
                for alert in guardian_status.alerts
            ]
            # Convert ResourceMetrics to dict
            resource_metrics = {
                "cpu_percent": guardian_status.resource_metrics.cpu_percent,
                "memory_percent": guardian_status.resource_metrics.memory_percent,
                "temperature_celsius": guardian_status.resource_metrics.temperature_celsius,
                "timestamp": guardian_status.resource_metrics.timestamp,
            }
            # Convert VIOMetrics to dict
            vio_metrics = {
                "position_variance": guardian_status.vio_metrics.position_variance,
                "velocity_variance": guardian_status.vio_metrics.velocity_variance,
                "tracking_quality": guardian_status.vio_metrics.tracking_quality,
                "is_valid": guardian_status.vio_metrics.is_valid,
                "timestamp": guardian_status.vio_metrics.timestamp,
            }

            status["guardian"] = {
                "is_running": guardian_status.is_running,
                "active_monitors": guardian_status.active_monitors,
                "last_heartbeat": guardian_status.last_heartbeat,
                "alerts": alerts_list,
                "resource_metrics": resource_metrics,
                "vio_metrics": vio_metrics,
                "missed_heartbeats": guardian_status.missed_heartbeats,
                "heartbeat_count": guardian_status.heartbeat_count,
                "uptime_s": guardian_status.uptime_s,
            }

        return status

    async def __aenter__(self) -> "AvatarMCPServer":
        """Async context manager entry.

        Automatically initializes the server on entry.
        """
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - ensures shutdown."""
        await self.shutdown()


# Legacy DroneMCPServer for backward compatibility
class DroneMCPServer(AvatarMCPServer):
    """Legacy alias for AvatarMCPServer."""

    def __init__(self, config: Optional[AvatarMCPServerConfig] = None):
        """Initialize with deprecation warning."""
        logger.warning(
            "DroneMCPServer is deprecated, use AvatarMCPServer instead"
        )
        super().__init__(config)


async def main() -> None:
    """Main entry point for running the server."""
    server = AvatarMCPServer()

    # Initialize server
    if not await server.initialize():
        logger.error("Server initialization failed, exiting")
        return

    try:
        # Run server
        await server.run()
    finally:
        # Ensure shutdown
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
