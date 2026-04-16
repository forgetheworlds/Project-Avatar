"""Test configuration for tools tests.

WHAT IS CONFTEST.PY?
--------------------
conftest.py is a special pytest file that pytest automatically discovers and loads
before running any tests in the same directory or subdirectories. Think of it as
a "configuration + fixtures" file that sets up the testing environment.

Key characteristics:
- Automatically loaded by pytest - no imports needed
- Applies to all tests in the same folder and subfolders
- Can define fixtures, hooks, and modify test behavior
- Great for shared setup code that multiple tests need

WHAT ARE FIXTURES?
------------------
Fixtures are pytest's way of providing test dependencies. They handle:
- Setup: Preparing the environment/objects needed for tests
- Teardown: Cleaning up after tests complete (even if they fail)
- Reuse: Same setup can be shared across multiple tests
- Scope control: Fixtures can run once per test, module, or entire test session

How fixtures work:
1. You define a fixture using the @pytest.fixture decorator
2. Tests request fixtures by including them as function parameters
3. pytest automatically calls the fixture, yields the value, then cleans up
4. The 'yield' statement separates setup (before yield) from teardown (after yield)

SETUP/TEARDOWN PATTERN
----------------------
Fixtures use Python generators (the 'yield' keyword) for setup/teardown:

    @pytest.fixture
    def my_fixture():
        # SETUP: Runs before the test
        resource = create_resource()
        yield resource  # Provides the resource to the test
        # TEARDOWN: Runs after the test (even if it failed!)
        resource.cleanup()

This file uses a special pattern - module-level mocks installed before imports.
Unlike fixtures with setup/teardown, these mocks are installed immediately when
pytest imports this conftest.py file.

WHAT THIS CONFTEST PROVIDES
-----------------------------
This conftest.py provides module-level mocking for:
1. mavsdk - The MAVSDK drone communication library (complex C++ bindings)
2. psutil - System resource monitoring library

Both are mocked so tools tests can run without these heavy dependencies installed.
"""

import sys
from unittest.mock import MagicMock

# =============================================================================
# MAVSDK MOCK SETUP (Module-Level)
# =============================================================================
# This file uses a special pattern: mocking BEFORE any imports happen.
# Why? Because mavsdk is a heavy dependency with C++ bindings that may not be
# installed in CI/test environments. By mocking it in conftest.py, we ensure
# the mock is in sys.modules BEFORE any test files import mavsdk.

# Create a mock mavsdk module using MagicMock
# MagicMock automatically creates attributes/methods when accessed - perfect
# for mocking complex libraries without knowing all their internals.
mock_mavsdk = MagicMock()
mock_mavsdk.System = MagicMock  # Mock the main System class
mock_mavsdk.asyncio = MagicMock()  # Mock asyncio submodule

# Mock mavsdk.action - contains flight control actions (arm, takeoff, land, etc.)
mock_action = MagicMock()
mock_action.Action = MagicMock  # Mock the Action class
mock_mavsdk.action = mock_action

# Mock mavsdk.telemetry - provides drone sensor data
mock_telemetry = MagicMock()
mock_telemetry.Telemetry = MagicMock  # Main telemetry class
mock_telemetry.Position = MagicMock  # GPS position data
mock_telemetry.VelocityNed = MagicMock  # Velocity in North-East-Down frame
mock_telemetry.AttitudeEuler = MagicMock  # Roll/pitch/yaw angles
mock_telemetry.Battery = MagicMock  # Battery status
mock_telemetry.Health = MagicMock  # System health (GPS, home position, etc.)
mock_telemetry.FlightMode = MagicMock  # Current flight mode
mock_telemetry.Odometry = MagicMock  # Position + velocity combined
mock_telemetry.LandedState = MagicMock  # On ground, taking off, landing, in air
mock_mavsdk.telemetry = mock_telemetry

# Mock mavsdk.offboard - for offboard control (position/velocity setpoints)
mock_offboard = MagicMock()
mock_offboard.Offboard = MagicMock  # Main offboard control class
mock_offboard.PositionNedYaw = MagicMock  # Position setpoint with yaw
mock_offboard.VelocityNedYaw = MagicMock  # Velocity setpoint with yaw
mock_offboard.VelocityBodyYawspeed = MagicMock  # Body-frame velocity
mock_mavsdk.offboard = mock_offboard

# Mock mavsdk.core - core connection management
mock_core = MagicMock()
mock_core.Core = MagicMock  # Connection state management
mock_mavsdk.core = mock_core

# Mock mavsdk.mission - waypoint mission support
mock_mission = MagicMock()
mock_mission.Mission = MagicMock  # Mission management
mock_mavsdk.mission = mock_mission

# Mock mavsdk.geofence - safety boundaries
mock_geofence = MagicMock()
mock_geofence.Geofence = MagicMock  # Geofence management
mock_mavsdk.geofence = mock_geofence

# Mock mavsdk.param - parameter configuration
mock_param = MagicMock()
mock_param.Param = MagicMock  # Parameter read/write
mock_mavsdk.param = mock_param

# =============================================================================
# INSTALL MAVSDK MOCKS INTO SYS.MODULES
# =============================================================================
# This is the critical step: we inject our mocks into Python's module system.
# When test files do 'from mavsdk import X', they get our mocks instead.
# This allows tools tests to run without needing the actual MAVSDK installed.

sys.modules["mavsdk"] = mock_mavsdk
sys.modules["mavsdk.action"] = mock_action
sys.modules["mavsdk.telemetry"] = mock_telemetry
sys.modules["mavsdk.offboard"] = mock_offboard
sys.modules["mavsdk.core"] = mock_core
sys.modules["mavsdk.mission"] = mock_mission
sys.modules["mavsdk.geofence"] = mock_geofence
sys.modules["mavsdk.param"] = mock_param

# =============================================================================
# PSUTIL MOCK SETUP (For Resource Monitoring Tests)
# =============================================================================
# Also mock psutil which is used for system resource monitoring.
# This prevents tests from needing the actual psutil library installed.

mock_psutil = MagicMock()

# Mock cpu_percent() - returns percentage of CPU usage
mock_psutil.cpu_percent = MagicMock(return_value=50.0)

# Mock virtual_memory() - returns memory statistics
# We return a mock object with a 'percent' attribute (memory usage %)
mock_psutil.virtual_memory = MagicMock(return_value=MagicMock(percent=60.0))

# Mock sensors_temperatures() - returns hardware temperatures
# Returns empty dict as default (no temperature sensors available)
mock_psutil.sensors_temperatures = MagicMock(return_value={})

# Install psutil mock into sys.modules
sys.modules["psutil"] = mock_psutil
