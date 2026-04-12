"""Pytest fixtures for drone testing.

Provides reusable fixtures for SITL drone connection and mock safety guardian.
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import source modules for fixtures
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.vision.mock_detector import MockDetector, Detection


# =============================================================================
# ASYNC TEST SUPPORT
# =============================================================================


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# SITL DRONE FIXTURES
# =============================================================================


@pytest.fixture
async def sitl_drone() -> AsyncGenerator[MagicMock, None]:
    """
    Create a mocked drone System instance for testing without SITL.

    This fixture provides a fully mocked MAVSDK System object that simulates
    drone behavior for unit tests. Use this for testing without a running
    SITL instance.

    Yields:
        Mocked System instance with realistic telemetry responses.

    Example:
        async def test_something(sitl_drone):
            await sitl_drone.action.arm()
            sitl_drone.action.arm.assert_called_once()
    """
    drone = MagicMock()

    # Mock connection state
    connection_state = MagicMock()
    connection_state.is_connected = True
    connection_state.uuid = "test-drone-001"

    # Create async iterator for connection_state
    async def mock_connection_state():
        yield connection_state

    drone.core.connection_state = mock_connection_state

    # Mock telemetry
    async def mock_position():
        pos = MagicMock()
        pos.latitude_deg = 37.7749
        pos.longitude_deg = -122.4194
        pos.relative_altitude_m = 10.0
        pos.absolute_altitude_m = 50.0
        yield pos

    async def mock_armed():
        yield True

    async def mock_in_air():
        yield True

    async def mock_battery():
        bat = MagicMock()
        bat.remaining_percent = 85.0
        bat.voltage_v = 22.4
        yield bat

    async def mock_flight_mode():
        yield MagicMock(value="HOLD")

    async def mock_health():
        health = MagicMock()
        health.is_global_position_ok = True
        health.is_home_position_ok = True
        health.is_gyrometer_calibration_ok = True
        health.is_accelerometer_calibration_ok = True
        health.is_magnetometer_calibration_ok = True
        health.is_level_calibration_ok = True
        health.is_local_position_ok = True
        yield health

    async def mock_velocity_ned():
        vel = MagicMock()
        vel.north_m_s = 0.0
        vel.east_m_s = 0.0
        vel.down_m_s = 0.0
        yield vel

    async def mock_attitude_euler():
        att = MagicMock()
        att.roll_deg = 0.0
        att.pitch_deg = 0.0
        att.yaw_deg = 0.0
        yield att

    # Attach telemetry mocks
    drone.telemetry.position = mock_position
    drone.telemetry.armed = mock_armed
    drone.telemetry.in_air = mock_in_air
    drone.telemetry.battery = mock_battery
    drone.telemetry.flight_mode = mock_flight_mode
    drone.telemetry.health = mock_health
    drone.telemetry.velocity_ned = mock_velocity_ned
    drone.telemetry.attitude_euler = mock_attitude_euler

    # Mock action methods
    drone.action.arm = AsyncMock()
    drone.action.disarm = AsyncMock()
    drone.action.takeoff = AsyncMock()
    drone.action.land = AsyncMock()
    drone.action.return_to_launch = AsyncMock()
    drone.action.hold = AsyncMock()
    drone.action.set_takeoff_altitude = AsyncMock()
    drone.action.get_takeoff_altitude = AsyncMock(return_value=10.0)

    yield drone


# =============================================================================
# SAFETY GUARDIAN FIXTURES
# =============================================================================


@pytest.fixture
def mock_guardian() -> GuardianProcess:
    """
    Create a GuardianProcess instance with default limits.

    Yields:
        GuardianProcess instance ready for safety testing.

    Example:
        def test_altitude(mock_guardian):
            is_valid, reason = mock_guardian.validate_command({
                "altitude_amsl_m": 150.0  # Exceeds 120m limit
            })
            assert not is_valid
    """
    limits = HardLimits()
    guardian = GuardianProcess(limits)
    guardian.set_home(37.7749, -122.4194)  # San Francisco
    return guardian


@pytest.fixture
def custom_limits() -> HardLimits:
    """
    Create customizable HardLimits for specific test scenarios.

    Yields:
        HardLimits instance with default values that can be modified.

    Example:
        def test_custom_limit(custom_limits):
            custom_limits.max_altitude_amsl_m = 50.0
            guardian = GuardianProcess(custom_limits)
            # Now 50m is the limit
    """
    return HardLimits()


# =============================================================================
# VISION PIPELINE FIXTURES
# =============================================================================


@pytest.fixture
def mock_detector() -> MockDetector:
    """
    Create a MockDetector instance for testing.

    Yields:
        MockDetector with deterministic behavior enabled.

    Example:
        def test_detection(mock_detector):
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = mock_detector.detect(frame)
            assert len(detections) > 0
    """
    return MockDetector(
        confidence_threshold=0.5,
        num_detections=3,
        deterministic=True
    )


@pytest.fixture
def sample_detection() -> Detection:
    """
    Create a sample Detection object for testing.

    Yields:
        Detection instance with typical values.

    Example:
        def test_state_string(sample_detection):
            from avatar.vision.state_string import generate_state_string
            state = generate_state_string([sample_detection])
            assert "person" in state
    """
    return Detection(
        label="person",
        confidence=0.85,
        bbox=[0.2, 0.3, 0.1, 0.15],
        class_id=1
    )


# =============================================================================
# TEST FRAME FIXTURES
# =============================================================================


@pytest.fixture
def sample_frame():
    """
    Create a sample numpy frame for vision testing.

    Yields:
        numpy array with shape (480, 640, 3).
    """
    import numpy as np
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_pil_image():
    """
    Create a sample PIL Image for vision testing.

    Yields:
        PIL Image with size (640, 480).
    """
    from PIL import Image
    import numpy as np
    # Create a simple RGB image
    array = np.zeros((480, 640, 3), dtype=np.uint8)
    array[100:200, 100:200] = [255, 0, 0]  # Red square
    return Image.fromarray(array, mode='RGB')


# =============================================================================
# MCP SERVER FIXTURES
# =============================================================================


@pytest.fixture
def mcp_server_config():
    """
    Create MCP server configuration for testing.

    Yields:
        Dict with server configuration values.
    """
    from avatar.mcp_server.server import DroneMCPServerConfig
    return DroneMCPServerConfig(
        system_address="udp://:14540",
        max_retries=1,
        retry_delay_s=0.1,
        health_timeout_s=5.0
    )


@pytest.fixture
async def mock_drone_connection():
    """
    Create a mocked DroneConnection for MCP server testing.

    Yields:
        Mocked DroneConnection instance.
    """
    from avatar.mav.connection import DroneConnection, ConnectionConfig

    # Create connection with mocked System
    config = ConnectionConfig(
        system_address="udp://:14540",
        max_retries=1,
        health_timeout_s=5.0
    )

    conn = DroneConnection(config)

    # Mock the drone System
    mock_drone = MagicMock()

    async def mock_connection_state():
        state = MagicMock()
        state.is_connected = True
        yield state

    async def mock_health():
        health = MagicMock()
        health.is_global_position_ok = True
        health.is_home_position_ok = True
        yield health

    async def mock_position():
        pos = MagicMock()
        pos.latitude_deg = 37.7749
        pos.longitude_deg = -122.4194
        pos.relative_altitude_m = 0.0
        pos.absolute_altitude_m = 0.0
        yield pos

    mock_drone.core.connection_state = mock_connection_state
    mock_drone.telemetry.health = mock_health
    mock_drone.telemetry.position = mock_position

    # Mock action methods
    mock_drone.action.arm = AsyncMock()
    mock_drone.action.disarm = AsyncMock()
    mock_drone.action.takeoff = AsyncMock()
    mock_drone.action.land = AsyncMock()
    mock_drone.action.return_to_launch = AsyncMock()
    mock_drone.action.hold = AsyncMock()
    mock_drone.action.set_takeoff_altitude = AsyncMock()

    conn.drone = mock_drone
    conn._connected = True

    return conn
