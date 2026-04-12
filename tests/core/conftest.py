"""Test configuration for core tests.

Handles mocking of mavsdk before any imports happen.
"""

import sys
from unittest.mock import MagicMock

# Create mock mavsdk module before any imports
mock_mavsdk = MagicMock()
mock_mavsdk.System = MagicMock
mock_mavsdk.asyncio = MagicMock()

# Mock mavsdk.action
mock_action = MagicMock()
mock_action.Action = MagicMock
mock_mavsdk.action = mock_action

# Mock mavsdk.telemetry
mock_telemetry = MagicMock()
mock_telemetry.Telemetry = MagicMock
mock_telemetry.Position = MagicMock
mock_telemetry.VelocityNed = MagicMock
mock_telemetry.AttitudeEuler = MagicMock
mock_telemetry.Battery = MagicMock
mock_telemetry.Health = MagicMock
mock_telemetry.FlightMode = MagicMock
mock_telemetry.Odometry = MagicMock
mock_telemetry.LandedState = MagicMock
mock_mavsdk.telemetry = mock_telemetry

# Mock mavsdk.offboard
mock_offboard = MagicMock()
mock_offboard.Offboard = MagicMock
mock_offboard.PositionNedYaw = MagicMock
mock_offboard.VelocityNedYaw = MagicMock
mock_offboard.VelocityBodyYawspeed = MagicMock
mock_offboard.OffboardError = Exception
mock_mavsdk.offboard = mock_offboard

# Mock mavsdk.core
mock_core = MagicMock()
mock_core.Core = MagicMock
mock_mavsdk.core = mock_core

# Mock mavsdk.mission
mock_mission = MagicMock()
mock_mission.Mission = MagicMock
mock_mavsdk.mission = mock_mission

# Mock mavsdk.geofence
mock_geofence = MagicMock()
mock_geofence.Geofence = MagicMock
mock_mavsdk.geofence = mock_geofence

# Mock mavsdk.param
mock_param = MagicMock()
mock_param.Param = MagicMock
mock_mavsdk.param = mock_param

# Install the mock
sys.modules["mavsdk"] = mock_mavsdk
sys.modules["mavsdk.action"] = mock_action
sys.modules["mavsdk.telemetry"] = mock_telemetry
sys.modules["mavsdk.offboard"] = mock_offboard
sys.modules["mavsdk.core"] = mock_core
sys.modules["mavsdk.mission"] = mock_mission
sys.modules["mavsdk.geofence"] = mock_geofence
sys.modules["mavsdk.param"] = mock_param
