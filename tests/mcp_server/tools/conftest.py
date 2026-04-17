"""Test configuration for MCP server tools tests.

This conftest.py provides module-level mocking for MAVSDK and other dependencies.
"""

import sys
from unittest.mock import MagicMock

# =============================================================================
# MAVSDK MOCK SETUP (Module-Level)
# =============================================================================

mock_mavsdk = MagicMock()
mock_mavsdk.System = MagicMock
mock_mavsdk.asyncio = MagicMock()

# Mock mavsdk.offboard
mock_offboard = MagicMock()
mock_offboard.Offboard = MagicMock
mock_offboard.PositionNedYaw = MagicMock
mock_offboard.VelocityNedYaw = MagicMock
mock_offboard.VelocityBodyYawspeed = MagicMock
mock_mavsdk.offboard = mock_offboard

# Mock mavsdk.geofence
mock_geofence = MagicMock()
mock_geofence.Geofence = MagicMock
mock_mavsdk.geofence = mock_geofence

# Mock mavsdk.telemetry
mock_telemetry = MagicMock()
mock_telemetry.Telemetry = MagicMock
mock_mavsdk.telemetry = mock_telemetry

# Mock mavsdk.action
mock_action = MagicMock()
mock_action.Action = MagicMock
mock_mavsdk.action = mock_action

# Install mocks into sys.modules
sys.modules["mavsdk"] = mock_mavsdk
sys.modules["mavsdk.offboard"] = mock_offboard
sys.modules["mavsdk.geofence"] = mock_geofence
sys.modules["mavsdk.telemetry"] = mock_telemetry
sys.modules["mavsdk.action"] = mock_action
