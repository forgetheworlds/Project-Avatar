"""
Avatar MCP Server - Agent-agnostic Model Context Protocol interface.

Exposes drone control tools to any MCP-compatible AI agent (Claude Code, OpenCode, etc.).
Architecture 2.0: Cloud LLM + Agent-Agnostic MCP + PX4 SITL Simulation.

================================================================================
MCP ARCHITECTURE OVERVIEW
================================================================================

The Model Context Protocol (MCP) is an open standard that enables AI agents to
connect to external tools and services. This server implements the MCP protocol
to expose drone control capabilities to any MCP-compatible client.

MCP Communication Flow:
-----------------------
1. Client (Claude Code) starts this server as a subprocess
2. Server communicates via JSON-RPC over stdio (stdin/stdout)
3. Client sends `initialize` request to negotiate protocol version
4. Server responds with capabilities (list of available tools)
5. Client calls `tools/list` to discover available tools
6. Client calls `tools/call` with tool name + arguments
7. Server executes tool and returns result as TextContent
8. Server can also send notifications (progress updates, alerts)

Key MCP Concepts:
-----------------
- **Server**: The process exposing tools (this file)
- **Client**: The AI agent calling tools (Claude Code)
- **Tool**: A function exposed to the client with schema + description
- **Transport**: Communication channel (stdio for this server)
- **Capability**: What the server can do (tools, resources, prompts)

================================================================================
TOOL REGISTRATION ARCHITECTURE
================================================================================

Tools are registered in two phases:

Phase 1: Tool Definition (Schema Declaration)
---------------------------------------------
- In `_setup_handlers()`, we use `@self.server.list_tools()` decorator
- Returns a list of `types.Tool` objects defining:
  - `name`: Unique identifier for the tool (e.g., "arm_and_takeoff")
  - `description`: Human-readable description for the LLM
  - `inputSchema`: JSON Schema defining valid arguments
    - Type information (string, number, boolean)
    - Descriptions for each parameter
    - Default values
    - Validation constraints (min/max, enums)
    - Required vs optional fields

Phase 2: Tool Execution (Handler Routing)
-----------------------------------------
- In `_setup_handlers()`, we use `@self.server.call_tool()` decorator
- Handler receives `name` (tool name) and `arguments` (dict of params)
- `_route_tool()` method maps tool name to actual implementation
- Each tool handler:
  1. Validates server is initialized
  2. Extracts arguments with defaults
  3. Calls the actual tool function
  4. Returns JSON string result

Why This Two-Phase Design?
--------------------------
1. Discovery: Client can list tools without executing them
2. Schema Validation: MCP layer validates args before calling handler
3. LLM Context: Descriptions help LLM choose right tool with right args
4. Type Safety: JSON Schema ensures well-formed inputs

================================================================================
REQUEST/RESPONSE FLOW
================================================================================

Incoming Request Processing:
----------------------------
1. MCP stdio transport receives JSON-RPC message
2. MCP library parses and routes to appropriate handler
3. `handle_call_tool` receives (name, arguments)
4. Server checks `_initialized` flag (returns error if not ready)
5. `_route_tool()` switches on tool name to find handler
6. Handler extracts arguments with `.get()` providing defaults
7. Handler calls async tool function (from tools/ modules)
8. Tool function interacts with drone via ConnectionManager
9. Result is serialized to JSON string
10. JSON wrapped in `types.TextContent` and returned to MCP
11. MCP serializes to JSON-RPC response and writes to stdout

Error Handling Path:
--------------------
1. Try-catch in `handle_call_tool` catches all exceptions
2. Exception logged with `logger.exception()` for debugging
3. Error serialized to JSON: `{"success": false, "error": "..."}`
4. Client receives error as normal response (no transport error)
5. Server continues running, ready for next command

================================================================================
SERVER LIFECYCLE
================================================================================

Startup Sequence (initialize()):
--------------------------------
1. Connect to drone via ConnectionManager (retry logic included)
2. Start TelemetryCache with configured refresh interval (100ms)
3. Start HeartbeatService at 20Hz (required for offboard mode)
4. Sync FlightStateMachine from current telemetry
5. Start AsyncGuardian safety monitoring (if enabled)
6. Set `_initialized = True`

Running Phase (run()):
----------------------
1. Verify initialized state
2. Create stdio_server() context manager for transport
3. Call server.run() with initialization options
4. Server listens for MCP messages until shutdown
5. Each message routed to appropriate handler

Shutdown Sequence (shutdown()):
-------------------------------
1. Stop AsyncGuardian (safety monitoring first)
2. Stop HeartbeatService (20Hz emission)
3. Stop TelemetryCache (data refresh)
4. Disconnect from drone (close MAVSDK connection)
5. Reset state flags
6. Set shutdown event for any waiting tasks

Cleanup on Initialization Failure (_cleanup_partial()):
---------------------------------------------------------
- Called if any initialization step fails
- Stops any services that were started
- Disconnects from drone
- Ensures no dangling resources

================================================================================
CORE COMPONENTS (Singleton Pattern)
================================================================================

ConnectionManager:
------------------
- Singleton managing persistent MAVSDK connection
- Handles connection retry logic and health monitoring
- All tools access drone through this shared instance

TelemetryCache:
---------------
- Non-blocking telemetry access (100ms refresh)
- Decouples tool handlers from slow MAVSDK calls
- Provides fresh/stale data detection

HeartbeatService:
-----------------
- Emits 20Hz heartbeats required for PX4 offboard mode
- Critical safety component - stops = failsafe trigger
- Separate task to avoid blocking tool execution

FlightStateMachine:
-------------------
- Tracks and validates flight state transitions
- Prevents invalid operations (e.g., takeoff when armed)
- Tools check state before executing operations

AsyncGuardian:
--------------
- Concurrent safety monitoring task
- Watches for connection loss, low battery, geofence breach
- Can auto-trigger failsafe actions
- Runs independently of tool execution

================================================================================
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
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import MagicMock

# ==============================================================================
# MCP IMPORTS WITH GRACEFUL FALLBACK
# ==============================================================================
# The MCP (Model Context Protocol) library is required for production use but
# may not be installed in test environments. We provide mock implementations
# that allow the server code to be imported and tested without the actual
# mcp package installed.
#
# This is important for:
# - Unit tests that don't need real MCP transport
# - CI/CD environments without full dependencies
# - Development environments where mcp isn't installed yet

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


# ==============================================================================
# CORE COMPONENT IMPORTS
# ==============================================================================
# All components use singleton pattern or shared instances to ensure
# consistent state across all tool invocations.

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData
from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig, HeartbeatSource
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mav.guardian_async import AsyncGuardian, GuardianConfig, SafetyAction
from avatar.core.context_managers import _get_telemetry_from_drone

# ==============================================================================
# TOOL MODULE IMPORTS
# ==============================================================================
# Tool implementations are organized by category into separate modules.
# This keeps the server file focused on MCP protocol handling while
# the actual drone operations live in specialized modules.

# Flight control: Basic flight operations (arm, takeoff, land, goto, etc.)
from avatar.mcp_server.tools.flight_tools import (
    FlightTools, FlightToolsConfig,
    arm_and_takeoff, land, rtl, abort_mission, goto_gps,
    fly_body_offset, set_velocity, hold,
    set_state_machine, set_telemetry_cache,
)

# Telemetry: Access to drone state data
from avatar.mcp_server.tools.telemetry_tools import get_telemetry
from avatar.mcp_server.tools.telemetry_tools import set_state_machine as set_telemetry_state_machine
from avatar.mcp_server.tools.telemetry_tools import set_telemetry_cache as set_telemetry_telemetry_cache
from avatar.mcp_server.tools.telemetry_tools import set_guardian as set_telemetry_guardian

# Vision: YOLO-based object detection
from avatar.mcp_server.tools.vision_tools import detect_objects, get_detected_objects

# Acrobatics: Advanced maneuvers (flips, rolls, spins)
from avatar.mcp_server.tools.acrobatics import (
    front_flip, back_flip, barrel_roll, yaw_spin,
    loop_maneuver, corkscrew, acrobatic_sequence
)

# Tracking: Target tracking and camera control
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal, point_camera_at, orbit_target,
    track_target, spiral_search
)

# Cinematic: Pre-programmed professional shots
from avatar.mcp_server.tools.cinematic_shots import (
    execute_cinematic_shot, list_cinematic_templates, preview_cinematic_shot
)

# Meta: Server health and operation management
from avatar.mcp_server.tools.meta_tools import (
    ping, async_ping, cancel_operation, async_cancel_operation
)

# Primitives: Low-level position control in NED frame
from avatar.mcp_server.tools.primitives import (
    set_position_ned, SetPositionNedInput, PositionStreamer, PositionToolsConfig
)

# D2.6: ConfirmationManager for human-in-the-loop confirmation
from avatar.mcp_server.confirmation import ConfirmationManager, ConfirmationConfig

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
# Root logger configuration - all modules use this logger hierarchy.
# INFO level for production, DEBUG for development.

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
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


# ==============================================================================
# TOOL DEFINITIONS - Module-level function for introspection
# ==============================================================================

def avatar_mcp_tool_definitions() -> List[Any]:
    """Return the list of all MCP tool definitions for the Avatar server.

    This function is module-level to allow introspection by validation scripts
    without requiring a server instance. It returns the complete list of
    types.Tool objects defining all available drone control capabilities.

    Returns:
        List of types.Tool objects with name, description, inputSchema,
        outputSchema, and annotations.

    Example:
        tools = avatar_mcp_tool_definitions()
        print(f"Server exposes {len(tools)} tools")
        for tool in tools:
            print(f"  - {tool.name}")
    """
    # ==============================================================================
    # COMMON ANNOTATION PATTERNS (D3.2-D3.4)
    # ==============================================================================
    # Annotations provide hints to MCP clients about tool behavior:
    # - readOnlyHint: True if tool only reads data, doesn't modify state
    # - destructiveHint: True if tool can cause irreversible changes
    # - idempotentHint: True if multiple calls have same effect as one
    # - openWorldHint: True if tool interacts with external world

    READ_ONLY_ANNOTATIONS = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    FLIGHT_CONTROL_ANNOTATIONS = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }

    NAVIGATION_ANNOTATIONS = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }

    VISION_ANNOTATIONS = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }

    EMERGENCY_ANNOTATIONS = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }

    # Standard output schema (D3.3)
    STANDARD_OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "isError": {"type": "boolean"},
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "category": {"type": "string"},
                    "message": {"type": "string"},
                    "recoverable": {"type": "boolean"},
                    "suggestedAction": {"type": "string"},
                },
            },
        },
    }

    return [
        # ==============================================================================
        # FLIGHT CONTROL TOOLS - Basic flight operations
        # ==============================================================================
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=EMERGENCY_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=EMERGENCY_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=EMERGENCY_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        # ==============================================================================
        # FLIGHT MODE PRIMITIVE
        # ==============================================================================
        types.Tool(
            name="set_flight_mode",
            description=(
                "Change the PX4 flight mode. "
                "Valid modes: HOLD, OFFBOARD, AUTO_RTL, MANUAL, STABILIZED, ALTCTL, POSCTL, ACRO, ORBIT, AUTO_MISSION, AUTO_LOITER. "
                "HOLD: Loiter at current position. "
                "OFFBOARD: Accept external setpoints (requires active setpoint stream). "
                "AUTO_RTL: Return to launch position and land. "
                "WARNING: Mode changes can interrupt ongoing missions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Target flight mode",
                        "enum": [
                            "UNKNOWN", "MANUAL", "STABILIZED", "ALTCTL", "POSCTL",
                            "OFFBOARD", "AUTO_MISSION", "AUTO_LOITER", "AUTO_RTL",
                            "ACRO", "ORBIT", "HOLD",
                        ],
                    },
                    "submode": {
                        "type": "string",
                        "description": "Optional submode for mode-specific behavior",
                    },
                },
                "required": ["mode"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        # ==============================================================================
        # VISION TOOLS - Object detection and tracking
        # ==============================================================================
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=VISION_ANNOTATIONS,
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=VISION_ANNOTATIONS,
        ),
        # ==============================================================================
        # STATUS TOOLS - Server and drone status
        # ==============================================================================
        types.Tool(
            name="get_server_status",
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
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        types.Tool(
            name="get_drone_status",
            description=(
                "Get drone operational status. "
                "Returns connection state, flight state, and battery level. "
                "Lightweight alternative to get_server_status for quick checks."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        # ==============================================================================
        # META TOOLS - Server health and operation control
        # ==============================================================================
        types.Tool(
            name="ping",
            description=(
                "Check server liveness and health. "
                "Returns pong with timestamp and uptime. "
                "Use for connection keep-alive and health monitoring. "
                "This tool works even without drone connection."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            # MCP annotations for tool behavior hints
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        ),
        types.Tool(
            name="cancel_operation",
            description=(
                "Cancel a running long-running operation gracefully. "
                "The operation will complete its current iteration and exit cleanly. "
                "Use to abort extended operations like orbit_target or spiral_search. "
                "Requires operation_id from the original operation call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "Unique identifier of the operation to cancel",
                    },
                },
                "required": ["operation_id"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        # ==============================================================================
        # ACROBATIC FLIGHT TOOLS - Advanced maneuvers
        # ==============================================================================
        types.Tool(
            name="front_flip",
            description=(
                "Execute a forward 360 deg flip. "
                "WARNING: High-energy maneuver. "
                "Requires minimum 15m altitude and 50% battery. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="back_flip",
            description=(
                "Execute a backward 360 deg flip. "
                "WARNING: High-energy maneuver. "
                "Requires minimum 15m altitude and 50% battery. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="barrel_roll",
            description=(
                "Execute a 360 deg barrel roll (left or right). "
                "WARNING: High-energy maneuver. "
                "Requires minimum 15m altitude and 50% battery. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Direction of roll",
                        "enum": ["left", "right"],
                        "default": "right",
                    }
                },
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="yaw_spin",
            description=(
                "Execute rapid 360 deg yaw rotation. "
                "WARNING: High-energy maneuver. "
                "Requires minimum 15m altitude and 50% battery. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Direction of spin",
                        "enum": ["cw", "ccw"],
                        "default": "cw",
                    },
                    "rotations": {
                        "type": "number",
                        "description": "Number of full 360 deg rotations",
                        "default": 1.0,
                        "minimum": 0.5,
                        "maximum": 5.0,
                    }
                },
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="loop_maneuver",
            description=(
                "Execute a vertical loop (circular climb and dive). "
                "WARNING: High-energy maneuver. "
                "Requires minimum 20m altitude. "
                "Uses full thrust during maneuver. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="corkscrew",
            description=(
                "Execute a corkscrew spiral (combined roll and yaw). "
                "WARNING: High-energy maneuver. "
                "Requires minimum 15m altitude and 50% battery. "
                "Auto-recovers to hover after completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rotations": {
                        "type": "number",
                        "description": "Number of spiral rotations",
                        "default": 1.0,
                        "minimum": 0.5,
                        "maximum": 3.0,
                    }
                },
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="acrobatic_sequence",
            description=(
                "Execute a sequence of acrobatic maneuvers. "
                "Chains multiple maneuvers with 1-second pauses for stabilization. "
                "Supported: front_flip, back_flip, barrel_roll, yaw_spin, loop, corkscrew. "
                "WARNING: Cumulative altitude loss - start high!"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "maneuvers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of maneuver names to execute in sequence",
                    }
                },
                "required": ["maneuvers"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        # ==============================================================================
        # TRACKING AND CAMERA CONTROL TOOLS
        # ==============================================================================
        types.Tool(
            name="set_gimbal",
            description=(
                "Control camera gimbal angles independently of drone. "
                "Set pitch (-90 deg=down, 0 deg=level, 30 deg=up), yaw (-180 deg to 180 deg), "
                "and roll (-45 deg to 45 deg). "
                "Useful for looking at targets while flying."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pitch_deg": {
                        "type": "number",
                        "description": "Pitch angle: -90=down, 0=level, 30=up",
                        "default": -45.0,
                        "minimum": -90.0,
                        "maximum": 30.0,
                    },
                    "yaw_deg": {
                        "type": "number",
                        "description": "Yaw angle relative to drone (-180 to 180)",
                        "default": 0.0,
                        "minimum": -180.0,
                        "maximum": 180.0,
                    },
                    "roll_deg": {
                        "type": "number",
                        "description": "Roll angle (-45 to 45)",
                        "default": 0.0,
                        "minimum": -45.0,
                        "maximum": 45.0,
                    },
                },
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="point_camera_at",
            description=(
                "Point camera at specific GPS coordinates. "
                "Calculates gimbal angles automatically. "
                "Drone stays in position, only camera moves."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lat": {
                        "type": "number",
                        "description": "Target latitude",
                    },
                    "lon": {
                        "type": "number",
                        "description": "Target longitude",
                    },
                    "alt_m": {
                        "type": "number",
                        "description": "Target altitude (optional)",
                    },
                },
                "required": ["lat", "lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="orbit_target",
            description=(
                "Circle around a target while keeping camera locked. "
                "Flies in a circle around target coordinates while "
                "continuously pointing camera at center. "
                "Perfect for cinematic shots or surveillance."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_lat": {
                        "type": "number",
                        "description": "Target latitude",
                    },
                    "target_lon": {
                        "type": "number",
                        "description": "Target longitude",
                    },
                    "target_alt_m": {
                        "type": "number",
                        "description": "Target altitude",
                    },
                    "radius_m": {
                        "type": "number",
                        "description": "Orbit radius in meters",
                        "default": 10.0,
                        "minimum": 5.0,
                        "maximum": 100.0,
                    },
                    "speed_m_s": {
                        "type": "number",
                        "description": "Orbit speed",
                        "default": 3.0,
                        "minimum": 1.0,
                        "maximum": 10.0,
                    },
                    "altitude_offset_m": {
                        "type": "number",
                        "description": "Height above target",
                        "default": 15.0,
                        "minimum": 10.0,
                        "maximum": 50.0,
                    },
                    "clockwise": {
                        "type": "boolean",
                        "description": "Orbit direction",
                        "default": True,
                    },
                    "duration_s": {
                        "type": "number",
                        "description": "Orbit duration",
                        "default": 30.0,
                        "minimum": 5.0,
                        "maximum": 300.0,
                    },
                    "keep_camera_locked": {
                        "type": "boolean",
                        "description": "Keep camera on target",
                        "default": True,
                    },
                },
                "required": ["target_lat", "target_lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="track_target",
            description=(
                "Track and follow a moving target. "
                "Follows targets like snowboarders, cars, or people "
                "while maintaining camera lock. Supports predictive tracking."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_lat": {
                        "type": "number",
                        "description": "Initial target latitude",
                    },
                    "target_lon": {
                        "type": "number",
                        "description": "Initial target longitude",
                    },
                    "target_velocity_north": {
                        "type": "number",
                        "description": "Target velocity north (m/s)",
                        "default": 0.0,
                    },
                    "target_velocity_east": {
                        "type": "number",
                        "description": "Target velocity east (m/s)",
                        "default": 0.0,
                    },
                    "follow_distance_m": {
                        "type": "number",
                        "description": "Distance behind target",
                        "default": 8.0,
                        "minimum": 5.0,
                        "maximum": 30.0,
                    },
                    "altitude_m": {
                        "type": "number",
                        "description": "Tracking altitude",
                        "default": 20.0,
                        "minimum": 15.0,
                        "maximum": 50.0,
                    },
                    "speed_m_s": {
                        "type": "number",
                        "description": "Maximum tracking speed",
                        "default": 8.0,
                        "minimum": 3.0,
                        "maximum": 15.0,
                    },
                    "duration_s": {
                        "type": "number",
                        "description": "Tracking duration",
                        "default": 60.0,
                        "maximum": 300.0,
                    },
                    "predictive": {
                        "type": "boolean",
                        "description": "Use velocity prediction",
                        "default": True,
                    },
                    "tracking_mode": {
                        "type": "string",
                        "description": "Position relative to target",
                        "enum": ["follow", "lead", "side"],
                        "default": "follow",
                    },
                },
                "required": ["target_lat", "target_lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="spiral_search",
            description=(
                "Perform expanding spiral search pattern. "
                "Flies outward spiral while climbing, keeping camera "
                "pointed at center. Useful for search and rescue."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "center_lat": {
                        "type": "number",
                        "description": "Center latitude",
                    },
                    "center_lon": {
                        "type": "number",
                        "description": "Center longitude",
                    },
                    "start_altitude_m": {
                        "type": "number",
                        "description": "Starting altitude",
                        "default": 20.0,
                    },
                    "max_radius_m": {
                        "type": "number",
                        "description": "Maximum spiral radius",
                        "default": 100.0,
                    },
                    "max_altitude_m": {
                        "type": "number",
                        "description": "Maximum altitude",
                        "default": 50.0,
                    },
                    "rotations": {
                        "type": "number",
                        "description": "Number of rotations",
                        "default": 3.0,
                    },
                    "speed_m_s": {
                        "type": "number",
                        "description": "Flight speed",
                        "default": 5.0,
                    },
                },
                "required": ["center_lat", "center_lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        # ==============================================================================
        # CINEMATIC SHOT TOOLS - Pre-programmed professional shots
        # ==============================================================================
        types.Tool(
            name="execute_cinematic_shot",
            description=(
                "Execute a pre-programmed cinematic shot with smooth motion curves. "
                "Professional-quality filming for action sports. "
                "Templates: orbit_close, orbit_wide, follow_close, follow_wide, "
                "reveal_hero, pass_by_low, top_down_dynamic, height_locked_jump, "
                "fpv_dynamic, snowboard_halfpipe, skate_ledge_gap. "
                "Features height-locked tracking (0.2m) for tricks at specific heights."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "Shot template name (e.g., 'orbit_close', 'follow_close')",
                    },
                    "target_lat": {
                        "type": "number",
                        "description": "Target/subject latitude",
                    },
                    "target_lon": {
                        "type": "number",
                        "description": "Target/subject longitude",
                    },
                    "target_alt_m": {
                        "type": "number",
                        "description": "Target altitude (optional, uses current if not set)",
                    },
                    "duration_s": {
                        "type": "number",
                        "description": "Override shot duration (optional)",
                    },
                    "custom_params": {
                        "type": "object",
                        "description": "Custom parameter overrides (optional)",
                    },
                },
                "required": ["template_name", "target_lat", "target_lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="list_cinematic_templates",
            description=(
                "List all available cinematic shot templates with descriptions. "
                "Use this to discover available shots before executing."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        types.Tool(
            name="preview_cinematic_shot",
            description=(
                "Preview a cinematic shot trajectory without executing. "
                "Shows planned path, waypoints, and estimated duration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "Shot template name",
                    },
                    "target_lat": {
                        "type": "number",
                        "description": "Target latitude",
                    },
                    "target_lon": {
                        "type": "number",
                        "description": "Target longitude",
                    },
                },
                "required": ["template_name", "target_lat", "target_lon"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        # ==============================================================================
        # W2a PRIMITIVE TOOLS - Low-level operations
        # ==============================================================================
        types.Tool(
            name="arm",
            description="Arm the drone motors (not takeoff - just arm). Requires confirmation on first arm.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Force arm even if preflight incomplete",
                        "default": False,
                    },
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="disarm",
            description="Disarm the drone motors. Force disarm in-air requires confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Force disarm even if in air",
                        "default": False,
                    },
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=EMERGENCY_ANNOTATIONS,
        ),
        types.Tool(
            name="set_home",
            description="Set the home position for RTL (Return to Launch).",
            inputSchema={
                "type": "object",
                "properties": {
                    "lat_deg": {"type": "number", "description": "Latitude in degrees"},
                    "lon_deg": {"type": "number", "description": "Longitude in degrees"},
                    "alt_m": {"type": "number", "description": "Altitude AMSL in meters"},
                },
                "required": ["lat_deg", "lon_deg"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="set_geofence_polygon",
            description="Set a polygonal geofence. Shrinking requires confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vertices": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat_deg": {"type": "number"},
                                "lon_deg": {"type": "number"},
                            },
                        },
                        "description": "Polygon vertices (min 3)",
                    },
                    "shrink_ok": {"type": "boolean", "default": False},
                },
                "required": ["vertices"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="disable_geofence",
            description="Disable the geofence. Requires confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "confirm": {"type": "boolean", "default": False},
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=EMERGENCY_ANNOTATIONS,
        ),
        types.Tool(
            name="enable_geofence",
            description="Re-enable a previously configured geofence.",
            inputSchema={"type": "object", "properties": {}},
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="set_hard_limits",
            description="Set safety limits for the drone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_altitude_amsl_m": {"type": "number", "default": 120},
                    "max_distance_from_home_m": {"type": "number", "default": 500},
                    "min_battery_rtl_percent": {"type": "number", "default": 25},
                    "max_speed_m_s": {"type": "number", "default": 15},
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="set_velocity_body",
            description="Command velocity in body frame (forward/right/down).",
            inputSchema={
                "type": "object",
                "properties": {
                    "forward_m_s": {"type": "number", "default": 0},
                    "right_m_s": {"type": "number", "default": 0},
                    "down_m_s": {"type": "number", "default": 0},
                    "yaw_rate_deg_s": {"type": "number", "default": 0},
                    "duration_s": {"type": "number", "description": "Duration in seconds"},
                },
                "required": ["duration_s"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="set_velocity_ned",
            description="Command velocity in NED frame (north/east/down).",
            inputSchema={
                "type": "object",
                "properties": {
                    "north_m_s": {"type": "number", "default": 0},
                    "east_m_s": {"type": "number", "default": 0},
                    "down_m_s": {"type": "number", "default": 0},
                    "yaw_deg": {"type": "number"},
                    "duration_s": {"type": "number"},
                },
                "required": ["duration_s"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="set_position_ned",
            description="Command position in NED frame relative to home.",
            inputSchema={
                "type": "object",
                "properties": {
                    "north_m": {"type": "number"},
                    "east_m": {"type": "number"},
                    "down_m": {"type": "number"},
                    "yaw_deg": {"type": "number"},
                    "speed_m_s": {"type": "number", "default": 5},
                },
                "required": ["north_m", "east_m", "down_m"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="set_position_gps",
            description="Command position via GPS coordinates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lat_deg": {"type": "number"},
                    "lon_deg": {"type": "number"},
                    "alt_m": {"type": "number"},
                    "speed_m_s": {"type": "number", "default": 5},
                },
                "required": ["lat_deg", "lon_deg"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="set_yaw",
            description="Command yaw angle (heading).",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaw_deg": {"type": "number", "description": "Target yaw (-180 to 180)"},
                    "yaw_rate_deg_s": {"type": "number", "default": 20},
                    "absolute": {"type": "boolean", "default": True},
                },
                "required": ["yaw_deg"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="set_parameter",
            description="Set a PX4 parameter. Critical parameters require confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                },
                "required": ["name", "value"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="run_preflight",
            description="Run preflight checks and return results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "checks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Checks to run (None = all)",
                    },
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        types.Tool(
            name="submit_operator_confirmation",
            description="Submit operator confirmation for a pending action.",
            inputSchema={
                "type": "object",
                "properties": {
                    "confirmation_id": {"type": "string"},
                    "approved": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["confirmation_id", "approved"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        # ==============================================================================
        # W2a ORCHESTRATOR TOOLS - High-level operations
        # ==============================================================================
        types.Tool(
            name="track_bbox",
            description="Track an object identified by bounding box.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "w": {"type": "number"},
                            "h": {"type": "number"},
                        },
                    },
                    "duration_s": {"type": "number"},
                    "approach_speed_m_s": {"type": "number", "default": 2},
                    "standoff_m": {"type": "number", "default": 5},
                },
                "required": ["bbox", "duration_s"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="orbit_subject_vision",
            description="Orbit around a detected subject using vision.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bbox": {"type": "object"},
                    "radius_m": {"type": "number", "default": 10},
                    "speed_m_s": {"type": "number", "default": 3},
                    "orbits": {"type": "integer", "default": 1},
                    "direction": {"type": "string", "enum": ["cw", "ccw"], "default": "cw"},
                },
                "required": ["bbox"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=FLIGHT_CONTROL_ANNOTATIONS,
        ),
        types.Tool(
            name="execute_waypoint_mission",
            description="Execute a mission with waypoints and behaviors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mission": {"type": "object", "description": "Mission object with waypoints"},
                    "safety_check": {"type": "boolean", "default": True},
                },
                "required": ["mission"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=NAVIGATION_ANNOTATIONS,
        ),
        types.Tool(
            name="log_mission_segment",
            description="Log a segment of a mission for later review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "include_video": {"type": "boolean", "default": False},
                },
                "required": ["name", "duration_s"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        types.Tool(
            name="evaluate_last_command",
            description="Evaluate the result of the last command executed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {"type": "string"},
                    "detailed": {"type": "boolean", "default": False},
                },
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
        types.Tool(
            name="expose_advanced_tracker",
            description="Expose advanced tracking features via MCP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "reset", "configure"],
                    },
                    "config": {"type": "object"},
                },
                "required": ["action"],
            },
            outputSchema=STANDARD_OUTPUT_SCHEMA,
            annotations=READ_ONLY_ANNOTATIONS,
        ),
    ]


# ==============================================================================
# LISTED TOOL NAMES - For compliance testing (D3.14)
# ==============================================================================

LISTED_TOOL_NAMES: List[str] = [
    "arm_and_takeoff",
    "get_telemetry",
    "land",
    "rtl",
    "abort_mission",
    "goto_gps",
    "fly_body_offset",
    "set_velocity",
    "hold",
    "detect_objects",
    "get_detected_objects",
    "get_server_status",
    "get_drone_status",
    "ping",
    "cancel_operation",
    "front_flip",
    "back_flip",
    "barrel_roll",
    "yaw_spin",
    "loop_maneuver",
    "corkscrew",
    "acrobatic_sequence",
    "set_gimbal",
    "point_camera_at",
    "orbit_target",
    "track_target",
    "spiral_search",
    "execute_cinematic_shot",
    "list_cinematic_templates",
    "preview_cinematic_shot",
    # W2a Primitives
    "arm",
    "disarm",
    "set_flight_mode",
    "set_home",
    "set_geofence_polygon",
    "disable_geofence",
    "enable_geofence",
    "set_hard_limits",
    "set_velocity_body",
    "set_velocity_ned",
    "set_position_ned",
    "set_position_gps",
    "set_yaw",
    "set_parameter",
    "run_preflight",
    "submit_operator_confirmation",
    # W2a Orchestrators
    "track_bbox",
    "orbit_subject_vision",
    "execute_waypoint_mission",
    "log_mission_segment",
    "evaluate_last_command",
    "expose_advanced_tracker",
]


# ==============================================================================
# CONFIGURATION DATACLASS
# ==============================================================================

@dataclass
class AvatarMCPServerConfig:
    """Configuration for AvatarMCPServer.

    All parameters have defaults suitable for PX4 SITL simulation.
    Modify these for real hardware deployments.

    Attributes:
        system_address: MAVSDK system address (default: udp://:14540 for SITL)
        connection_timeout_s: Timeout for initial connection
        telemetry_refresh_ms: Telemetry cache refresh interval in milliseconds
        heartbeat_hz: Heartbeat emission frequency (default: 20Hz)
        enable_guardian: Whether to enable AsyncGuardian monitoring
        enable_auto_failsafe: Whether to auto-trigger failsafe on critical issues
        max_retries: Maximum connection retry attempts
        retry_delay_s: Delay between connection retries in seconds
        auto_confirm: D2.6 - Auto-confirm all confirmation requests (no human-in-loop)
        confirmation_ttl_s: D2.6 - Default TTL for confirmation requests
    """

    system_address: str = "udp://:14540"  # Default SITL address
    connection_timeout_s: float = 30.0
    telemetry_refresh_ms: int = 100  # 100ms as per requirements
    heartbeat_hz: float = 20.0  # 20Hz as per PX4 offboard requirements
    enable_guardian: bool = True
    enable_auto_failsafe: bool = True
    max_retries: int = 3
    retry_delay_s: float = 1.0
    connect_on_start: bool = True
    # D2.6: Confirmation configuration
    auto_confirm: bool = False  # Default: require human confirmation
    confirmation_ttl_s: float = 60.0  # Default TTL for confirmations

    @classmethod
    def from_env(cls) -> "AvatarMCPServerConfig":
        """Build server config from environment variables."""
        def env_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            system_address=os.getenv("AVATAR_SYSTEM_ADDRESS", cls.system_address),
            connection_timeout_s=float(
                os.getenv("AVATAR_CONNECTION_TIMEOUT_S", cls.connection_timeout_s)
            ),
            telemetry_refresh_ms=int(
                os.getenv("AVATAR_TELEMETRY_REFRESH_MS", cls.telemetry_refresh_ms)
            ),
            heartbeat_hz=float(os.getenv("AVATAR_HEARTBEAT_HZ", cls.heartbeat_hz)),
            enable_guardian=env_bool("AVATAR_ENABLE_GUARDIAN", cls.enable_guardian),
            enable_auto_failsafe=env_bool(
                "AVATAR_ENABLE_AUTO_FAILSAFE", cls.enable_auto_failsafe
            ),
            max_retries=int(os.getenv("AVATAR_MAX_RETRIES", cls.max_retries)),
            retry_delay_s=float(os.getenv("AVATAR_RETRY_DELAY_S", cls.retry_delay_s)),
            connect_on_start=env_bool("AVATAR_CONNECT_ON_START", cls.connect_on_start),
            # D2.6: Confirmation settings from environment
            auto_confirm=env_bool("AVATAR_AUTO_CONFIRM", cls.auto_confirm),
            confirmation_ttl_s=float(
                os.getenv("AVATAR_CONFIRMATION_TTL_S", cls.confirmation_ttl_s)
            ),
        )


# ==============================================================================
# MAIN SERVER CLASS
# ==============================================================================

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

        This constructor creates all component instances but does NOT start
        any services or establish connections. Call initialize() to fully
        start the server.

        Args:
            config: Server configuration. Uses defaults if not provided.

        Note:
            This constructor does not establish connections or start services.
            Call initialize() to fully start the server.
        """
        self.config = config or AvatarMCPServerConfig()

        # Create the MCP server instance with name "avatar-mcp"
        # This name appears in MCP client logs and debugging output
        self.server = Server("avatar-mcp")

        # ==============================================================================
        # CORE COMPONENTS - SINGLETON PATTERN
        # ==============================================================================
        # These components are shared across all tool invocations.
        # Using singletons ensures consistent state and prevents resource conflicts.

        # ConnectionManager: Manages MAVSDK connection to PX4
        # All drone communication goes through this single connection
        self.connection_manager: ConnectionManager = ConnectionManager()

        # TelemetryCache: Provides fast, non-blocking telemetry access
        # Background task refreshes data every 100ms from the drone
        self.telemetry_cache: TelemetryCache = TelemetryCache(
            refresh_ms=self.config.telemetry_refresh_ms,
            stale_ms=500,  # Data older than 500ms considered stale
            history_size=100,  # Keep last 100 samples for trending
        )

        # HeartbeatService: Emits 20Hz heartbeats for offboard mode
        # PX4 requires minimum 2Hz, we use 20Hz for safety margin
        self.heartbeat_service: HeartbeatService = HeartbeatService(
            config=HeartbeatConfig(
                heartbeat_hz=self.config.heartbeat_hz,
                offboard_timeout_s=0.5,  # Trigger failsafe if no heartbeat for 0.5s
                warning_threshold_s=0.3,  # Warn at 0.3s gap
                emit_heartbeat=True,  # We emit heartbeats (vs just monitoring)
            )
        )

        # FlightStateMachine: Tracks and validates flight state
        # Prevents invalid transitions (e.g., takeoff when already flying)
        self.state_machine: FlightStateMachine = FlightStateMachine()

        # AsyncGuardian: Background safety monitoring
        # Runs concurrent tasks watching for dangerous conditions
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
        self.guardian.on_failsafe = self._handle_guardian_failsafe

        # FlightTools: High-level flight operations
        # Wraps MAVSDK actions in state-machine-aware methods
        self.flight_tools = FlightTools(
            config=FlightToolsConfig(
                system_address=self.config.system_address,
                max_retries=self.config.max_retries,
                retry_delay_s=self.config.retry_delay_s,
                health_timeout_s=self.config.connection_timeout_s,
            ),
            state_machine=self.state_machine,
        )

        # D3.12: Singleton TelemetryTools and VisionTools
        # These are shared across all tool invocations for consistent state
        from avatar.mcp_server.tools.telemetry_tools import TelemetryTools, TelemetryToolsConfig
        from avatar.mcp_server.tools.vision_tools import VisionTools, VisionToolsConfig

        self.telemetry_tools = TelemetryTools(
            config=TelemetryToolsConfig(
                system_address=self.config.system_address,
                max_retries=self.config.max_retries,
                retry_delay_s=self.config.retry_delay_s,
                health_timeout_s=self.config.connection_timeout_s,
            )
        )

        self.vision_tools = VisionTools(
            config=VisionToolsConfig()
        )

        # D2.6: ConfirmationManager for human-in-the-loop confirmation
        # Controls confirmation flow for dangerous operations
        self.confirmation_manager = ConfirmationManager(
            config=ConfirmationConfig(
                timeout_s=self.config.confirmation_ttl_s,
                show_telemetry_details=True,
                require_explicit_abort=False,
            )
        )
        # Configure auto-confirm from environment
        self.confirmation_manager.auto_confirm = self.config.auto_confirm
        self.confirmation_manager.default_ttl_s = self.config.confirmation_ttl_s
        if self.config.auto_confirm:
            logger.info("ConfirmationManager: auto_confirm enabled (no human-in-loop)")

        # Set global references for tool function modules
        # This allows tool functions to access shared state
        set_state_machine(self.state_machine)
        set_telemetry_cache(self.telemetry_cache)
        set_telemetry_state_machine(self.state_machine)
        set_telemetry_telemetry_cache(self.telemetry_cache)
        set_telemetry_guardian(self.guardian)
        # D2.6: Set confirmation manager reference for flight tools
        from avatar.mcp_server.tools.flight_tools import set_confirmation_manager
        set_confirmation_manager(self.confirmation_manager)
        # D3.12: Set singleton TelemetryTools and VisionTools instances
        from avatar.mcp_server.tools.telemetry_tools import set_telemetry_tools_instance
        from avatar.mcp_server.tools.vision_tools import set_vision_tools_instance
        set_telemetry_tools_instance(self.telemetry_tools)
        set_vision_tools_instance(self.vision_tools)

        # ==============================================================================
        # RUNTIME STATE
        # ==============================================================================
        self._initialized = False  # Set to True after successful initialize()
        self._shutdown_event = asyncio.Event()  # Signal for graceful shutdown
        self._tasks: Set[asyncio.Task[Any]] = set()  # Track background tasks

        # ==============================================================================
        # SETUP MCP HANDLERS
        # ==============================================================================
        # Register tool definitions and execution handlers with MCP framework
        # This must be called after creating self.server
        self._setup_handlers()

        logger.info("AvatarMCPServer initialized (components created, not yet started)")

    def _setup_handlers(self) -> None:
        """Set up MCP protocol handlers for tool registration and execution.

        This method registers two key handlers with the MCP server:

        1. list_tools handler: Called by client to discover available tools
           - Returns list of Tool objects with name, description, inputSchema
           - Descriptions help LLM understand when to use each tool
           - Schema enables parameter validation

        2. call_tool handler: Called by client to execute a tool
           - Receives tool name and arguments
           - Validates server is initialized
           - Routes to appropriate handler via _route_tool()
           - Returns result as JSON string wrapped in TextContent

        These handlers are the bridge between MCP protocol messages and
        our drone control implementation.
        """

        # ==============================================================================
        # TOOL LISTING HANDLER
        # ==============================================================================
        # This handler responds to the MCP "tools/list" method.
        # It returns the complete catalog of available tools with their schemas.
        # The client (Claude) uses this to understand what capabilities are available.

        @self.server.list_tools()  # type: ignore[untyped-decorator]
        async def handle_list_tools() -> List[types.Tool]:
            """List available drone control tools.

            Returns:
                List of Tool objects defining all exposed capabilities.
                Each tool includes:
                - name: Unique identifier (used in call_tool)
                - description: Human-readable explanation for LLM
                - inputSchema: JSON Schema for parameter validation
            """
            return avatar_mcp_tool_definitions()

        # ==============================================================================
        # TOOL EXECUTION HANDLER
        # ==============================================================================
        # This handler responds to the MCP "tools/call" method.
        # It routes tool calls to the appropriate implementation function.

        @self.server.call_tool()  # type: ignore[untyped-decorator]
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[Any]:
            """Handle tool execution requests from MCP clients.

            This is the entry point for all drone commands from Claude.
            It validates the server is ready, routes to the appropriate
            handler, and formats the response.

            Args:
                name: Name of the tool to execute (matches Tool.name from list_tools).
                arguments: Tool arguments from the caller (validated against inputSchema).

            Returns:
                List of content items (TextContent for most tools,
                may include ImageContent for vision tools).

            Error Handling:
                All exceptions are caught and returned as error JSON.
                This ensures the server stays running even if a tool fails.
            """
            try:
                # ==============================================================================
                # PRE-EXECUTION VALIDATION
                # ==============================================================================
                # Ensure server is fully initialized before accepting commands.
                # This prevents race conditions during startup.

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

                # ==============================================================================
                # TOOL ROUTING
                # ==============================================================================
                # Delegate to _route_tool which contains the dispatch logic.
                # This separation keeps the handler clean and enables testing.

                result = await self._route_tool(name, arguments)

                # Handle different return types:
                # - List: Vision tools return content lists directly (TextContent + ImageContent)
                # - str: Other tools return JSON strings that need wrapping
                # - dict: Some tools return dicts that need JSON serialization
                if isinstance(result, list):
                    # Vision tools return lists of content items directly
                    return result
                elif isinstance(result, dict):
                    # Handle dict results (e.g., error envelopes)
                    return [types.TextContent(type="text", text=json.dumps(result))]
                else:
                    # String results need wrapping in TextContent
                    return [types.TextContent(type="text", text=result)]

            except Exception as e:
                # Log full exception with traceback for debugging
                logger.exception(f"Error executing tool {name}")

                # Return error as JSON so client can handle it gracefully
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": str(e),
                        }),
                    )
                ]

    async def _route_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Route tool call to appropriate handler implementation.

        This method acts as a switchboard, mapping tool names to the
        actual implementation functions in the tools/ modules.

        Args:
            name: Tool name from the MCP call.
            arguments: Dictionary of arguments from JSON parsing.

        Returns:
            Tool result which can be:
            - str: JSON string for most tools
            - list: List of content items for vision tools
            - dict: Dict for some tools (e.g., error envelopes)

        Design Notes:
            - Each tool extracts arguments with .get() providing defaults
            - This handles optional parameters gracefully
            - JSON Schema validation already occurred in MCP layer
            - Vision tools return lists of content items (TextContent + ImageContent)
        """
        # ==============================================================================
        # FLIGHT CONTROL TOOL HANDLERS
        # ==============================================================================
        # These tools control basic flight operations.
        # All delegate to functions in flight_tools module.

        if name == "arm_and_takeoff":
            # Arm motors and takeoff to specified altitude
            return json.dumps(await self.flight_tools.arm_and_takeoff(
                arguments.get("altitude_m", 10.0)
            ))

        elif name == "land":
            # Land at current position
            return json.dumps(await self.flight_tools.land())

        elif name == "rtl":
            # Return to launch position and land
            return json.dumps(await self.flight_tools.rtl())

        elif name == "abort_mission":
            # Emergency stop - hover in place
            return json.dumps(await self.flight_tools.abort_mission(
                arguments.get("reason", "")
            ))

        elif name == "goto_gps":
            # Navigate to GPS coordinates
            return json.dumps(await self.flight_tools.goto_gps(
                lat=arguments.get("lat", 0.0),
                lon=arguments.get("lon", 0.0),
                alt_m=arguments.get("alt_m", 0.0) or None,
                speed_ms=arguments.get("speed_ms", 5.0),
            ))

        elif name == "fly_body_offset":
            # Move relative to current body frame
            return json.dumps(await self.flight_tools.fly_body_offset(
                forward_m=arguments.get("forward_m", 0.0),
                right_m=arguments.get("right_m", 0.0),
                up_m=arguments.get("up_m", 0.0),
                yaw_align=arguments.get("yaw_align", False),
                speed_m_s=arguments.get("speed_m_s", 5.0),
            ))

        elif name == "set_velocity":
            # Set velocity setpoint in NED frame (offboard mode)
            return json.dumps(await self.flight_tools.set_velocity(
                north_m_s=arguments.get("north_m_s", 0.0),
                east_m_s=arguments.get("east_m_s", 0.0),
                down_m_s=arguments.get("down_m_s", 0.0),
                yaw_deg=arguments.get("yaw_deg", 0.0),
                duration_s=arguments.get("duration_s", 1.0),
            ))

        elif name == "hold":
            # Hold position with optional monitoring
            return json.dumps(await self.flight_tools.hold(
                duration_s=arguments.get("duration_s", 5.0),
                position_tolerance_m=arguments.get("position_tolerance_m", 1.0),
                auto_rtl_on_drift=arguments.get("auto_rtl_on_drift", False),
            ))

        # ==============================================================================
        # TELEMETRY TOOL HANDLERS
        # ==============================================================================

        elif name == "get_telemetry":
            # Get current telemetry from cache
            telemetry = self.telemetry_cache.get_data()
            if telemetry is not None:
                return json.dumps({
                    "success": True,
                    "position": {
                        "latitude_deg": telemetry.latitude,
                        "longitude_deg": telemetry.longitude,
                        "absolute_altitude_m": telemetry.altitude,
                        "relative_altitude_m": telemetry.altitude,
                    },
                    "velocity": {
                        "north_m_s": telemetry.velocity_north,
                        "east_m_s": telemetry.velocity_east,
                        "down_m_s": telemetry.velocity_down,
                        "groundspeed_m_s": telemetry.groundspeed,
                    },
                    "attitude": {
                        "roll_deg": telemetry.roll,
                        "pitch_deg": telemetry.pitch,
                        "yaw_deg": telemetry.yaw,
                    },
                    "battery": {
                        "remaining_percent": telemetry.battery_percent,
                        "voltage_v": telemetry.battery_voltage,
                    },
                    "flight_mode": telemetry.flight_mode,
                    "armed": telemetry.armed,
                    "in_air": telemetry.in_air,
                    "is_stale": self.telemetry_cache.is_stale(),
                    "age_ms": self.telemetry_cache.get_age_ms(),
                })
            return await get_telemetry()

        # ==============================================================================
        # VISION TOOL HANDLERS
        # ==============================================================================

        elif name == "detect_objects":
            # Run YOLO detection
            return await detect_objects(arguments.get("confidence_threshold", 0.5))

        elif name == "get_detected_objects":
            # Get cached detection results
            return await get_detected_objects()

        # ==============================================================================
        # STATUS TOOL HANDLERS
        # ==============================================================================

        elif name == "get_server_status":
            # Return comprehensive server status
            return json.dumps(self.get_status())

        elif name == "get_drone_status":
            # Return lightweight drone status
            return json.dumps(self.get_drone_status())

        # ==============================================================================
        # ACROBATIC TOOL HANDLERS
        # ==============================================================================

        elif name == "front_flip":
            return await front_flip()

        elif name == "back_flip":
            return await back_flip()

        elif name == "barrel_roll":
            return await barrel_roll(arguments.get("direction", "right"))

        elif name == "yaw_spin":
            return await yaw_spin(
                direction=arguments.get("direction", "cw"),
                rotations=arguments.get("rotations", 1.0)
            )

        elif name == "loop_maneuver":
            return await loop_maneuver()

        elif name == "corkscrew":
            return await corkscrew(arguments.get("rotations", 1.0))

        elif name == "acrobatic_sequence":
            return await acrobatic_sequence(
                maneuvers=arguments.get("maneuvers", [])
            )

        # ==============================================================================
        # TRACKING AND CAMERA TOOL HANDLERS
        # ==============================================================================

        elif name == "set_gimbal":
            return await set_gimbal(
                pitch_deg=arguments.get("pitch_deg", -45.0),
                yaw_deg=arguments.get("yaw_deg", 0.0),
                roll_deg=arguments.get("roll_deg", 0.0)
            )

        elif name == "point_camera_at":
            return await point_camera_at(
                lat=arguments.get("lat", 0.0),
                lon=arguments.get("lon", 0.0),
                alt_m=arguments.get("alt_m")
            )

        elif name == "orbit_target":
            return await orbit_target(
                target_lat=arguments.get("target_lat", 0.0),
                target_lon=arguments.get("target_lon", 0.0),
                target_alt_m=arguments.get("target_alt_m"),
                radius_m=arguments.get("radius_m", 10.0),
                speed_m_s=arguments.get("speed_m_s", 3.0),
                altitude_offset_m=arguments.get("altitude_offset_m", 15.0),
                clockwise=arguments.get("clockwise", True),
                duration_s=arguments.get("duration_s", 30.0),
                keep_camera_locked=arguments.get("keep_camera_locked", True)
            )

        elif name == "track_target":
            return await track_target(
                target_lat=arguments.get("target_lat", 0.0),
                target_lon=arguments.get("target_lon", 0.0),
                target_velocity_north=arguments.get("target_velocity_north", 0.0),
                target_velocity_east=arguments.get("target_velocity_east", 0.0),
                follow_distance_m=arguments.get("follow_distance_m", 8.0),
                altitude_m=arguments.get("altitude_m", 20.0),
                speed_m_s=arguments.get("speed_m_s", 8.0),
                duration_s=arguments.get("duration_s", 60.0),
                predictive=arguments.get("predictive", True),
                tracking_mode=arguments.get("tracking_mode", "follow")
            )

        elif name == "spiral_search":
            return await spiral_search(
                center_lat=arguments.get("center_lat", 0.0),
                center_lon=arguments.get("center_lon", 0.0),
                start_altitude_m=arguments.get("start_altitude_m", 20.0),
                max_radius_m=arguments.get("max_radius_m", 100.0),
                max_altitude_m=arguments.get("max_altitude_m", 50.0),
                rotations=arguments.get("rotations", 3.0),
                speed_m_s=arguments.get("speed_m_s", 5.0)
            )

        # ==============================================================================
        # CINEMATIC SHOT TOOL HANDLERS
        # ==============================================================================

        elif name == "execute_cinematic_shot":
            return await execute_cinematic_shot(
                template_name=arguments.get("template_name", ""),
                target_lat=arguments.get("target_lat", 0.0),
                target_lon=arguments.get("target_lon", 0.0),
                target_alt_m=arguments.get("target_alt_m"),
                duration_s=arguments.get("duration_s"),
                custom_params=arguments.get("custom_params"),
            )

        elif name == "list_cinematic_templates":
            return await list_cinematic_templates()

        elif name == "preview_cinematic_shot":
            return await preview_cinematic_shot(
                template_name=arguments.get("template_name", ""),
                target_lat=arguments.get("target_lat", 0.0),
                target_lon=arguments.get("target_lon", 0.0),
            )

        # ==============================================================================
        # META TOOL HANDLERS
        # ==============================================================================

        elif name == "ping":
            # Health check - no drone dependency
            return await async_ping()

        elif name == "cancel_operation":
            # Cancel a long-running operation
            return await async_cancel_operation(
                operation_id=arguments.get("operation_id", "")
            )

        # ==============================================================================
        # PRIMITIVE TOOL HANDLERS - Low-level position control
        # ==============================================================================

        elif name == "set_position_ned":
            # Command position in NED frame using offboard mode
            return await set_position_ned(
                north_m=arguments.get("north_m", 0.0),
                east_m=arguments.get("east_m", 0.0),
                down_m=arguments.get("down_m", -10.0),
                yaw_deg=arguments.get("yaw_deg"),
                speed_m_s=arguments.get("speed_m_s", 5.0),
            )

        else:
            # Unknown tool name - return error
            return json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    async def initialize(self) -> bool:
        """Initialize all components and start services.

        This method performs the full startup sequence:
        1. Connect to drone via ConnectionManager (with retries)
        2. Start TelemetryCache with the configured refresh interval
        3. Start HeartbeatService at 20Hz for offboard mode
        4. Initialize FlightStateMachine from current telemetry
        5. Start AsyncGuardian safety monitoring

        Each step is logged for debugging. If any step fails,
        _cleanup_partial() is called to release resources.

        Returns:
            True if initialization successful, False otherwise.

        Example:
            server = AvatarMCPServer()
            if await server.initialize():
                print("Ready for flight!")
            else:
                print("Failed to start")
        """
        if self._initialized:
            logger.debug("Server already initialized")
            return True

        try:
            logger.info("Initializing Avatar MCP Server...")

            if not self.config.connect_on_start:
                logger.info("Starting in offline MCP discovery mode; drone connection deferred")
                self._initialized = True
                return True

            # ==============================================================================
            # STEP 1: CONNECT TO DRONE
            # ==============================================================================
            # Establish MAVSDK connection to PX4.
            # This is the foundation - everything else depends on this.

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

            # ==============================================================================
            # STEP 2: START TELEMETRY CACHE
            # ==============================================================================
            # Start background task that refreshes telemetry every 100ms.
            # This provides fast, non-blocking access to drone state.

            logger.info(f"Starting telemetry cache ({self.config.telemetry_refresh_ms}ms refresh)...")

            async def telemetry_provider() -> TelemetryData:
                """Provider function that fetches from drone via ConnectionManager."""
                drone = await self.connection_manager.get_drone()
                if drone is None:
                    raise ConnectionError("Drone not connected")
                return await _get_telemetry_from_drone(drone)

            await self.telemetry_cache.start(telemetry_provider)
            logger.info("Telemetry cache started")

            # ==============================================================================
            # STEP 3: START HEARTBEAT SERVICE
            # ==============================================================================
            # Start 20Hz heartbeat emission.
            # REQUIRED for PX4 offboard mode - without this, PX4 triggers failsafe.

            logger.info(f"Starting heartbeat service ({self.config.heartbeat_hz}Hz)...")
            await self.heartbeat_service.start()
            logger.info("Heartbeat service started")

            # ==============================================================================
            # STEP 4: INITIALIZE STATE MACHINE
            # ==============================================================================
            # Sync flight state machine from current telemetry.
            # This ensures state transitions are valid from the start.

            logger.info("Initializing state machine...")
            await self._sync_state_machine_from_telemetry()
            logger.info(f"State machine initialized: {self.state_machine.current_state_name}")

            # ==============================================================================
            # STEP 5: START GUARDIAN MONITORING
            # ==============================================================================
            # Start background safety monitoring.
            # Guardian watches for dangerous conditions and can trigger failsafe.

            if self.config.enable_guardian:
                logger.info("Starting AsyncGuardian monitoring...")
                await self.guardian.start()
                logger.info("Guardian monitoring started")

            self._initialized = True
            logger.info("Avatar MCP Server initialized successfully")
            return True

        except Exception as e:
            logger.exception(f"Initialization failed: {e}")
            # Cleanup on failure to prevent resource leaks
            await self._cleanup_partial()
            return False

    async def _sync_state_machine_from_telemetry(self) -> None:
        """Sync state machine from current telemetry.

        This ensures the state machine reflects reality before accepting
        commands. For example, if drone is already armed, we start in
        ARMED state rather than INIT.
        """
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
        """Cleanup partial initialization on failure.

        Called when initialization fails partway through.
        Stops any services that were started and releases resources.
        """
        logger.info("Cleaning up partial initialization...")

        try:
            await self.telemetry_cache.stop()
        except Exception as e:
            logger.warning(f"Error stopping telemetry cache: {e}")

        try:
            await self.heartbeat_service.stop_async()
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
        1. Stop AsyncGuardian monitoring (safety first)
        2. Stop HeartbeatService (20Hz emission)
        3. Stop TelemetryCache (data refresh)
        4. Disconnect from drone (close MAVSDK)
        5. Reset state flags

        Each step is wrapped in try-catch to ensure we attempt
        all cleanup even if one step fails.
        """
        if not self._initialized:
            logger.debug("Server not initialized, nothing to shutdown")
            return

        logger.info("Shutting down Avatar MCP Server...")

        # ==============================================================================
        # STEP 1: STOP GUARDIAN (safety monitoring first)
        # ==============================================================================
        if self.config.enable_guardian:
            logger.info("Stopping guardian...")
            try:
                await self.guardian.stop()
                logger.info("Guardian stopped")
            except Exception as e:
                logger.warning(f"Error stopping guardian: {e}")

        # ==============================================================================
        # STEP 2: STOP HEARTBEAT SERVICE
        # ==============================================================================
        logger.info("Stopping heartbeat service...")
        try:
            await self.heartbeat_service.stop_async()
            logger.info("Heartbeat service stopped")
        except Exception as e:
            logger.warning(f"Error stopping heartbeat service: {e}")

        # ==============================================================================
        # STEP 3: STOP TELEMETRY CACHE
        # ==============================================================================
        logger.info("Stopping telemetry cache...")
        try:
            await self.telemetry_cache.stop()
            logger.info("Telemetry cache stopped")
        except Exception as e:
            logger.warning(f"Error stopping telemetry cache: {e}")

        # ==============================================================================
        # STEP 4: DISCONNECT FROM DRONE
        # ==============================================================================
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

        This is the main entry point for the server. It:
        1. Verifies the server is initialized
        2. Creates stdio transport for MCP communication
        3. Starts the MCP server with initialization options
        4. Listens for MCP messages until shutdown

        This method blocks until the server is shutdown via signal
        or client disconnection.

        Note:
            This method blocks until the server is shutdown.
            Call initialize() before calling run().

        Example:
            await server.initialize()
            await server.run()  # Blocks here
        """
        if not self._initialized:
            logger.error("Server not initialized. Call initialize() first.")
            raise RuntimeError("Server not initialized. Call initialize() first.")

        if not _MCP_AVAILABLE:
            raise RuntimeError(
                "MCP module not available. Install with: pip install mcp"
            )

        logger.info("Starting Avatar MCP Server (stdio transport)")

        # ==============================================================================
        # STDIO TRANSPORT SETUP
        # ==============================================================================
        # stdio_server() creates stdin/stdout streams for MCP communication.
        # This is the standard transport for MCP servers run as subprocesses.

        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            # Run the server with initialization options
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

    async def _handle_guardian_failsafe(self, action: SafetyAction, reason: str) -> None:
        """Execute a physical MAVSDK recovery action requested by AsyncGuardian."""
        drone = await self.connection_manager.get_drone()
        if drone is None:
            logger.error(
                "Guardian requested %s but no drone is connected: %s",
                action.value,
                reason,
            )
            return

        logger.warning("Executing Guardian failsafe action %s: %s", action.value, reason)

        if action == SafetyAction.RTL:
            await drone.action.return_to_launch()
        elif action == SafetyAction.LAND:
            await drone.action.land()
        elif action == SafetyAction.HOLD:
            await drone.action.hold()
        elif action == SafetyAction.EMERGENCY_STOP:
            terminate = getattr(drone.action, "terminate", None)
            kill = getattr(drone.action, "kill", None)
            if terminate is not None:
                await terminate()
            elif kill is not None:
                await kill()
            else:
                logger.critical("No MAVSDK emergency stop action is available")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status.

        Returns a dictionary containing the current state of all
        components. Useful for health checks and debugging.

        Returns:
            Dictionary containing:
            - initialized: Whether server is initialized
            - connection: ConnectionManager state and health
            - telemetry: TelemetryCache metrics
            - heartbeat: HeartbeatService metrics
            - state_machine: Current flight state
            - guardian: Guardian status (if enabled)

        Example:
            status = server.get_status()
            print(f"Connection: {status['connection']['state']}")
            print(f"Battery: {status['telemetry']['battery_percent']}%")
        """
        status: Dict[str, Any] = {
            "initialized": self._initialized,
            "connection": {
                "mode": "connected" if self.config.connect_on_start else "offline",
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

        # Add guardian status if enabled
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

    def get_drone_status(self) -> Dict[str, Any]:
        """Get lightweight drone operational status.

        Returns connection state, flight state, and battery level.
        Lightweight alternative to get_status() for quick checks.

        Returns:
            Dictionary containing:
            - connection: Connection state (connected/disconnected)
            - flight: Flight state, armed status, in_air status
            - battery: Battery percentage and voltage

        Example:
            status = server.get_drone_status()
            if status["connection"]["connected"]:
                print(f"Battery: {status['battery']['percent']}%")
        """
        telemetry = self.telemetry_cache.get_data()

        return {
            "connection": {
                "connected": self.connection_manager.state.name == "CONNECTED",
                "state": self.connection_manager.state.name,
            },
            "flight": {
                "state": self.state_machine.current_state_name,
                "armed": telemetry.armed if telemetry else False,
                "in_air": telemetry.in_air if telemetry else False,
                "flight_mode": telemetry.flight_mode if telemetry else "UNKNOWN",
            },
            "battery": {
                "percent": telemetry.battery_percent if telemetry else 0.0,
                "voltage_v": telemetry.battery_voltage if telemetry else 0.0,
            },
        }

    # ==============================================================================
    # ASYNC CONTEXT MANAGER SUPPORT
    # ==============================================================================
    # Enables "async with" syntax for automatic initialization and cleanup.
    #
    # Example:
    #     async with AvatarMCPServer() as server:
    #         # Server is initialized here
    #         await server.run()
    #     # Server is automatically shut down here

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


# ==============================================================================
# LEGACY BACKWARD COMPATIBILITY
# ==============================================================================
# DroneMCPServer was the original name. This alias maintains compatibility
# with existing code while encouraging migration to AvatarMCPServer.

class DroneMCPServer(AvatarMCPServer):
    """Legacy alias for AvatarMCPServer.

    Deprecated: Use AvatarMCPServer instead.
    """

    def __init__(self, config: Optional[AvatarMCPServerConfig] = None):
        """Initialize with deprecation warning."""
        logger.warning(
            "DroneMCPServer is deprecated, use AvatarMCPServer instead"
        )
        super().__init__(config)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
# When this file is run directly (python -m avatar.mcp_server.server),
# this main function creates and runs the server.

async def main() -> None:
    """Main entry point for running the server.

    Creates server, initializes it, runs until shutdown.
    Handles cleanup in finally block to ensure resources are released.
    """
    server = AvatarMCPServer(AvatarMCPServerConfig.from_env())

    # Initialize server
    if not await server.initialize():
        logger.error("Server initialization failed, exiting")
        return

    try:
        # Run server - blocks until shutdown
        await server.run()
    finally:
        # Ensure shutdown happens even if run() raises exception
        await server.shutdown()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
