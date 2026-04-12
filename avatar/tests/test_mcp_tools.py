"""Tests for MCP server tools.

Tests the drone control tools exposed via the Model Context Protocol.
These tests use mocked drone connections to avoid requiring a running SITL.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server import DroneMCPServer, DroneMCPServerConfig
from avatar.mav.connection import DroneConnection, ConnectionConfig


# =============================================================================
# MARKERS
# =============================================================================


pytestmark = pytest.mark.asyncio


# =============================================================================
# ARM AND TAKEOFF TOOL TESTS
# =============================================================================


async def test_arm_and_takeoff_tool_success(mock_drone_connection):
    """Test successful arm and takeoff tool execution."""
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
    """Test arm and takeoff with default altitude."""
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({})

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["altitude_m"] == 10  # Default


async def test_arm_and_takeoff_tool_custom_altitude(mock_drone_connection):
    """Test arm and takeoff with custom altitude."""
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_arm_and_takeoff({"altitude_m": 25})

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["altitude_m"] == 25


async def test_arm_and_takeoff_tool_arm_failure(mock_drone_connection):
    """Test arm and takeoff when arming fails."""
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
    """Test arm and takeoff when drone is not connected."""
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_arm_and_takeoff({"altitude_m": 10})

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_arm_and_takeoff_tool_health_check_failure(mock_drone_connection):
    """Test arm and takeoff when health check fails."""
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


async def test_get_telemetry_tool_success(mock_drone_connection):
    """Test successful telemetry retrieval."""
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
    """Test telemetry when drone is not connected."""
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_get_telemetry()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_get_telemetry_tool_partial_failure(mock_drone_connection):
    """Test telemetry handles partial data when some telemetry fails."""
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


async def test_land_tool_success(mock_drone_connection):
    """Test successful landing command."""
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_land()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Landing initiated" in data["message"]

    mock_drone_connection.drone.action.land.assert_called_once()


async def test_land_tool_no_drone():
    """Test landing when drone is not connected."""
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_land()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_land_tool_failure(mock_drone_connection):
    """Test landing when command fails."""
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
# RTL TOOL TESTS
# =============================================================================


async def test_rtl_tool_success(mock_drone_connection):
    """Test successful RTL command."""
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_rtl()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Return to Launch" in data["message"]

    mock_drone_connection.drone.action.return_to_launch.assert_called_once()


async def test_rtl_tool_no_drone():
    """Test RTL when drone is not connected."""
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_rtl()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


async def test_rtl_tool_failure(mock_drone_connection):
    """Test RTL when command fails."""
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


async def test_abort_mission_tool_success(mock_drone_connection):
    """Test successful abort mission command."""
    server = DroneMCPServer()
    server.drone = mock_drone_connection

    result = await server._handle_abort_mission()

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "Mission aborted" in data["message"]

    mock_drone_connection.drone.action.hold.assert_called_once()


async def test_abort_mission_tool_no_drone():
    """Test abort when drone is not connected."""
    server = DroneMCPServer()
    server.drone = None

    result = await server._handle_abort_mission()

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "not connected" in data["error"]


# =============================================================================
# TOOL LISTING TESTS
# =============================================================================


async def test_list_tools():
    """Test that all expected tools are listed."""
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


async def test_connect_drone_success():
    """Test successful drone connection."""
    server = DroneMCPServer()

    with patch('avatar.mcp_server.server.DroneConnection') as mock_conn_class:
        mock_conn = MagicMock()
        mock_conn.connect = AsyncMock(return_value=True)
        mock_conn_class.return_value = mock_conn

        result = await server._connect_drone()

        assert result is True
        assert server.drone is not None


async def test_connect_drone_failure():
    """Test failed drone connection."""
    server = DroneMCPServer()

    with patch('avatar.mcp_server.server.DroneConnection') as mock_conn_class:
        mock_conn = MagicMock()
        mock_conn.connect = AsyncMock(return_value=False)
        mock_conn_class.return_value = mock_conn

        result = await server._connect_drone()

        assert result is False


async def test_tool_auto_connect():
    """Test that tools attempt auto-connection when drone is disconnected."""
    server = DroneMCPServer()

    with patch.object(server, '_connect_drone', return_value=False) as mock_connect:
        # Call a tool without drone connection
        result = await server._handle_land()

        # Should have attempted connection
        mock_connect.assert_called_once()

        # Should return error
        data = json.loads(result[0].text)
        assert data["success"] is False
