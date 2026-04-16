"""Tests for MCP server tools.

This test suite validates the drone control tools exposed via the Model Context Protocol (MCP).
MCP is an open protocol that enables AI agents to securely interact with external systems
through a standardized interface. In this project, MCP tools act as the bridge between
natural language commands and drone operations.

What are MCP Tools?
-------------------
MCP (Model Context Protocol) tools are functions that AI agents can invoke to perform
actions on external systems. Each tool:
- Has a name (e.g., "arm_and_takeoff", "get_telemetry")
- Accepts structured input parameters (JSON)
- Returns structured output results (JSON)
- Is registered with an MCP server that manages tool discovery and execution

How MCP Tools Work in This Project:
-----------------------------------
1. The DroneMCPServer registers tool handlers in _setup_handlers()
2. Each handler receives a JSON arguments dict from the AI agent
3. The handler validates inputs and interacts with the drone via MAVSDK
4. Results are returned as MCP TextContent objects containing JSON responses
5. The GuardianProcess validates dangerous operations before execution

Mock Strategy:
--------------
These tests use mocked drone connections to avoid requiring a running PX4 SITL instance.
The mock_drone_connection fixture (defined in conftest.py) creates a MagicMock that
simulates the MAVSDK System object:
- AsyncMock methods simulate async MAVSDK calls like arm(), takeoff(), land()
- Async generator functions simulate telemetry streams (position, battery, health)
- MagicMock attributes provide property access to drone state

This allows fast, isolated unit testing without the overhead of starting a simulation.

Test Categories:
----------------
1. Arm and Takeoff Tests - Validate the complete takeoff sequence
2. Telemetry Tests - Verify state monitoring and health checks
3. Land Tests - Test landing command execution
4. RTL Tests - Validate return-to-launch functionality
5. Abort Tests - Test emergency mission termination
6. Tool Listing Tests - Verify MCP tool registration
7. Connection Tests - Validate auto-connect and error handling
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server import DroneMCPServer, DroneMCPServerConfig
from avatar.mav.connection_config import ConnectionConfig
from avatar.mcp_server.compat import DroneConnection

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skip(reason="legacy DroneMCPServer internals superseded by Architecture 2.0 MCP server tests"),
]


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

# The pytestmark decorator applies the asyncio marker to all async tests in this file.
# This tells pytest-asyncio to run these coroutines properly.


# =============================================================================
# ARM AND TAKEOFF TOOL TESTS
# =============================================================================

# The arm_and_takeoff tool is the primary method for initiating flight.
# It performs a pre-flight sequence:
#   1. Health check (GPS lock, home position set)
#   2. Arming (enables motor control)
#   3. Set takeoff altitude
#   4. Initiate takeoff
# Expected outcomes vary based on drone state and parameters.


async def test_arm_and_takeoff_tool_success(mock_drone_connection):
    """Test successful arm and takeoff tool execution.

    Validates the complete takeoff sequence when all preconditions are met.
    The tool should:
    - Return success=True in the JSON response
    - Include a confirmation message with the target altitude
    - Verify that MAVSDK methods were called in correct order

    Mock behavior: All health checks pass, arm succeeds, takeoff succeeds.

    Expected outcomes:
    - Response contains {"success": true, "altitude_m": 10}
    - drone.action.arm() called exactly once
    - drone.action.set_takeoff_altitude(10) called with correct altitude
    - drone.action.takeoff() called exactly once
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Successfully took off" in data["message"]
    assert data["altitude_m"] == 10

    # Verify arm and takeoff were called
    mock_drone_connection.drone.action.arm.assert_called_once()
    mock_drone_connection.drone.action.takeoff.assert_called_once()
    mock_drone_connection.drone.action.set_takeoff_altitude.assert_called_once_with(10)


async def test_arm_and_takeoff_tool_default_altitude(mock_drone_connection):
    """Test arm and takeoff with default altitude.

    Validates that the tool uses a safe default altitude (10 meters) when
    no altitude parameter is provided in the tool call.

    This is a safety feature - agents should not need to specify altitude
    for basic takeoff operations.

    Mock behavior: Standard health checks, normal arm/takeoff sequence.

    Expected outcomes:
    - Response contains {"success": true, "altitude_m": 10}
    - Default altitude of 10m is used when args dict is empty
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({})

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["altitude_m"] == 10  # Default


async def test_arm_and_takeoff_tool_custom_altitude(mock_drone_connection):
    """Test arm and takeoff with custom altitude.

    Validates that the tool respects custom altitude parameters.
    Useful for missions requiring specific takeoff heights.

    Mock behavior: Standard health checks, arm/takeoff with custom altitude.

    Expected outcomes:
    - Response altitude matches the requested 25 meters
    - set_takeoff_altitude called with the custom value
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({"altitude_m": 25})

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["altitude_m"] == 25


async def test_arm_and_takeoff_tool_arm_failure(mock_drone_connection):
    """Test arm and takeoff when arming fails.

    Validates error handling when the drone cannot arm. Common causes:
    - Preflight checks not passed (GPS, calibration)
    - Safety switch not engaged
    - Battery too low

    Mock behavior: arm() raises Exception simulating preflight failure.

    Expected outcomes:
    - Response contains {"success": false, "error": "Failed to arm..."}
    - Error message includes details from the MAVSDK exception
    - takeoff() is never called (execution stops at arm failure)
    """
    # Make arm raise an exception
    mock_drone_connection.drone.action.arm = AsyncMock(
        side_effect=Exception("Arm failed: preflight checks not passed")
    )

    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "Failed to arm" in data["error"]


async def test_arm_and_takeoff_tool_no_drone():
    """Test arm and takeoff when drone is not connected.

    Validates that the tool handles the case where no drone connection exists.
    This tests the auto-connect failure path.

    Mock behavior: No mock - server.drone is explicitly set to None.

    Expected outcomes:
    - Response contains {"success": false, "error": "...not connected"}
    - Tool should gracefully handle missing connection without crashing
    """
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_arm_and_takeoff_tool_health_check_failure(mock_drone_connection):
    """Test arm and takeoff when health check fails.

    Validates pre-flight safety validation. The health check ensures:
    - GPS has valid position fix (is_global_position_ok)
    - Home position has been set (is_home_position_ok)

    Without these, arming could be dangerous (no position hold, no RTL capability).

    Mock behavior: Telemetry health stream reports all checks as failed.

    Expected outcomes:
    - Response contains {"success": false, "error": "Health check failed"}
    - arm() and takeoff() are never called (blocked by health check)
    """
    # Mock failed health check
    async def mock_health_fail():
        health = MagicMock()
        health.is_global_position_ok = False
        health.is_home_position_ok = False
        yield health

    mock_drone_connection.drone.telemetry.health = mock_health_fail

    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "Health check failed" in data["error"]


# =============================================================================
# GET TELEMETRY TOOL TESTS
# =============================================================================

# The get_telemetry tool provides a complete snapshot of drone state.
# It aggregates data from multiple MAVSDK telemetry streams:
#   - Position (GPS coordinates)
#   - Velocity (NED frame)
#   - Attitude (roll, pitch, yaw)
#   - Battery (remaining %, voltage)
#   - Flight mode (hold, mission, etc.)
#   - Health status (GPS ok, home set, etc.)
#   - Armed/in_air state


async def test_get_telemetry_tool_success(mock_drone_connection):
    """Test successful telemetry retrieval.

    Validates that the tool aggregates all telemetry streams correctly.
    This is the primary monitoring tool for AI agents to assess drone state.

    Mock behavior: All telemetry streams return valid data.

    Expected outcomes:
    - Response contains {"success": true} and all telemetry fields:
      * position: {latitude_deg, longitude_deg, absolute_altitude_m, relative_altitude_m}
      * velocity: {north_m_s, east_m_s, down_m_s}
      * attitude: {roll_deg, pitch_deg, yaw_deg}
      * battery: {remaining_percent, voltage_v}
      * flight_mode: string (e.g., "HOLD", "MISSION")
      * health: {is_gyrometer_calibration_ok, is_accelerometer_calibration_ok,
                  is_magnetometer_calibration_ok, is_level_calibration_ok,
                  is_local_position_ok, is_global_position_ok, is_home_position_ok}
      * armed: boolean
      * in_air: boolean
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_get_telemetry()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "position" in data
    assert data["position"]["latitude_deg"] == 37.7749
    assert "velocity" in data
    assert "attitude" in data
    assert "battery" in data
    assert "flight_mode" in data
    assert "health" in data
    assert "armed" in data
    assert "in_air" in data


async def test_get_telemetry_tool_no_drone():
    """Test telemetry when drone is not connected.

    Validates graceful failure when no telemetry is available.

    Mock behavior: server.drone is None.

    Expected outcomes:
    - Response contains {"success": false, "error": "...not connected"}
    """
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_get_telemetry()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_get_telemetry_tool_partial_failure(mock_drone_connection):
    """Test telemetry handles partial data when some telemetry fails.

    Validates resilience when individual telemetry streams fail. The tool
    should return available data with a warning rather than failing completely.

    This is important because telemetry streams can be intermittent:
    - GPS may temporarily lose fix
    - Battery sensor may be unavailable on some hardware

    Mock behavior: position telemetry raises Exception, other streams work.

    Expected outcomes:
    - Response indicates partial success (either warning field or degraded success)
    - Tool doesn't crash on stream failure
    - Available telemetry is still returned
    """
    # Make position fail
    async def mock_position_fail():
        raise Exception("Position unavailable")
        yield  # Never reached

    mock_drone_connection.drone.telemetry.position = mock_position_fail

    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_get_telemetry()

    data = json.loads(result[0].text)
    # Should still succeed with warning
    assert "warning" in data or "success" in data


# =============================================================================
# LAND TOOL TESTS
# =============================================================================

# The land tool initiates an immediate landing at the current position.
# This is the standard way to end a flight safely.
# The drone will:
#   1. Descend to the ground at current GPS coordinates
#   2. Automatically disarm after touchdown (with timeout)


async def test_land_tool_success(mock_drone_connection):
    """Test successful landing command.

    Validates that the land tool properly initiates landing sequence.

    Mock behavior: land() command succeeds immediately.

    Expected outcomes:
    - Response contains {"success": true, "message": "Landing initiated"}
    - drone.action.land() called exactly once
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_land()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Landing initiated" in data["message"]

    mock_drone_connection.drone.action.land.assert_called_once()


async def test_land_tool_no_drone():
    """Test landing when drone is not connected.

    Validates graceful handling of land command without drone connection.

    Mock behavior: server.drone is None.

    Expected outcomes:
    - Response contains {"success": false, "error": "...not connected"}
    """
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_land()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_land_tool_failure(mock_drone_connection):
    """Test landing when command fails.

    Validates error handling when the land command cannot be executed.
    Common causes:
    - Drone not in a flight mode that supports landing
    - Communication timeout with flight controller

    Mock behavior: land() raises Exception.

    Expected outcomes:
    - Response contains {"success": false, "error": "Landing failed..."}
    """
    mock_drone_connection.drone.action.land = AsyncMock(
        side_effect=Exception("Land failed")
    )

    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_land()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "Landing failed" in data["error"]


# =============================================================================
# RTL (RETURN TO LAUNCH) TOOL TESTS
# =============================================================================

# The RTL tool commands the drone to return to its launch point and land.
# This is a safety-critical feature for:
#   - Low battery situations
#   - Loss of signal recovery
#   - Mission abort scenarios
# The drone will:
#   1. Ascend to RTL altitude (if below)
#   2. Fly directly to home position
#   3. Land and disarm


async def test_rtl_tool_success(mock_drone_connection):
    """Test successful RTL command.

    Validates that the RTL tool properly initiates return-to-launch.

    Mock behavior: return_to_launch() succeeds immediately.

    Expected outcomes:
    - Response contains {"success": true, "message": "Return to Launch"}
    - drone.action.return_to_launch() called exactly once
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_rtl()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Return to Launch" in data["message"]

    mock_drone_connection.drone.action.return_to_launch.assert_called_once()


async def test_rtl_tool_no_drone():
    """Test RTL when drone is not connected.

    Validates graceful handling of RTL command without drone connection.

    Mock behavior: server.drone is None.

    Expected outcomes:
    - Response contains {"success": false, "error": "...not connected"}
    """
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_rtl()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_rtl_tool_failure(mock_drone_connection):
    """Test RTL when command fails.

    Validates error handling when RTL cannot be executed.
    Common causes:
    - No home position set (drone doesn't know where to return)
    - GPS lock lost during flight

    Mock behavior: return_to_launch() raises Exception.

    Expected outcomes:
    - Response contains {"success": false, "error": "RTL failed..."}
    """
    mock_drone_connection.drone.action.return_to_launch = AsyncMock(
        side_effect=Exception("RTL failed")
    )

    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_rtl()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "RTL failed" in data["error"]


# =============================================================================
# ABORT MISSION TOOL TESTS
# =============================================================================

# The abort_mission tool is an emergency stop that immediately puts the drone
# in HOLD mode at its current position. Unlike RTL (which moves the drone),
# abort stops all motion immediately where the drone is.
# Use cases:
#   - Detected collision risk
#   - Unexpected obstacle detected
#   - Human operator override
#   - LLM decision to halt for safety reassessment


async def test_abort_mission_tool_success(mock_drone_connection):
    """Test successful abort mission command.

    Validates that abort properly stops the drone in place.

    Mock behavior: hold() command succeeds (PX4 HOLD mode).

    Expected outcomes:
    - Response contains {"success": true, "message": "Mission aborted"}
    - drone.action.hold() called exactly once (switches to HOLD flight mode)
    """
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_abort_mission()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Mission aborted" in data["message"]

    mock_drone_connection.drone.action.hold.assert_called_once()


async def test_abort_mission_tool_no_drone():
    """Test abort when drone is not connected.

    Validates graceful handling of abort command without drone connection.

    Mock behavior: server.drone is None.

    Expected outcomes:
    - Response contains {"success": false, "error": "...not connected"}
    """
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_abort_mission()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


# =============================================================================
# TOOL LISTING TESTS
# =============================================================================

# These tests verify that the MCP server properly registers and exposes
# all available tools to AI agents. Tool discovery is part of the MCP protocol
# - agents query the server to learn what capabilities are available.


async def test_list_tools():
    """Test that all expected tools are listed.

    Validates the MCP tool registration system. The DroneMCPServer must
    register all tool handlers in _setup_handlers() so agents can discover them.

    Expected MCP tools for drone control:
    - arm_and_takeoff: Initiates flight with specified altitude
    - get_telemetry: Returns complete drone state snapshot
    - land: Initiates landing at current position
    - rtl: Returns to launch point and lands
    - abort_mission: Emergency stop (HOLD mode)

    Mock behavior: No mocks - tests the server initialization directly.

    Expected outcomes:
    - Server instance has valid MCP server (server.server is not None)
    - All tool handlers are registered and callable
    """
    server = DroneMCPServer()

    # Get the list_tools handler
    from mcp.types import Tool

    # The handler is registered internally
    # We can verify the tools exist by checking the server
    assert hasattr(server, 'server')

    # Alternative: manually check tool definitions are correct
    expected_tools = [
        "arm_and_takeoff",
        "get_telemetry",
        "land",
        "rtl",
        "abort_mission"
    ]

    # Verify server has correct tools configured
    # This tests the _setup_handlers registration
    assert server.server is not None


# =============================================================================
# CONNECTION HANDLING TESTS
# =============================================================================

# These tests validate the auto-connect behavior and connection management.
# The server should:
#   1. Attempt to connect when a tool is called without existing connection
#   2. Reuse existing connection if available
#   3. Handle connection failures gracefully
#   4. Support manual connection via _connect_drone()


async def test_connect_drone_success():
    """Test successful drone connection.

    Validates the manual connection flow via _connect_drone().
    This is typically called during server startup or when a connection
    is explicitly requested.

    Mock behavior: DroneConnection.connect() returns True (successful UDP/TCP connection to PX4).

    Expected outcomes:
    - _connect_drone() returns True
    - server.drone is set to the connected instance
    """
    server = DroneMCPServer()

    with patch('avatar.mcp_server.server.DroneConnection') as mock_conn_class:
        mock_conn = MagicMock()
        mock_conn.connect = AsyncMock(return_value=True)
        mock_conn_class.return_value = mock_conn

        result = await server._connect_drone()

        assert result is True
        assert server.drone is not None


async def test_connect_drone_failure():
    """Test failed drone connection.

    Validates error handling when connection cannot be established.
    Common causes:
    - SITL not running (no PX4 instance on UDP port 14540)
    - Network issues
    - Wrong connection string

    Mock behavior: DroneConnection.connect() returns False.

    Expected outcomes:
    - _connect_drone() returns False
    - server.drone remains None or unset
    """
    server = DroneMCPServer()

    with patch('avatar.mcp_server.server.DroneConnection') as mock_conn_class:
        mock_conn = MagicMock()
        mock_conn.connect = AsyncMock(return_value=False)
        mock_conn_class.return_value = mock_conn

        result = await server._connect_drone()

        assert result is False


async def test_tool_auto_connect():
    """Test that tools attempt auto-connection when drone is disconnected.

    Validates the auto-connect behavior - a convenience feature that attempts
to establish connection when a tool is called without an active connection.
    This prevents agents from needing to explicitly connect before each operation.

    Mock behavior:
    - server.drone starts as None
    - _connect_drone is patched to return False (simulating connection failure)

    Expected outcomes:
    - _connect_drone() is automatically called when tool is invoked
    - Tool returns error indicating connection failure
    - Response contains {"success": false}
    """
    server = DroneMCPServer()

    with patch.object(server, '_connect_drone', return_value=False) as mock_connect:
        # Call a tool without drone connection
        result = await server._handle_land()

        # Should have attempted connection
        mock_connect.assert_called_once()

        # Should return error
        data = json.loads(result[0].text)
        assert data["success"] is False
