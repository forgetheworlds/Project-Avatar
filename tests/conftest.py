"""
Root conftest.py - Pytest Configuration File
============================================

WHAT IS CONFTEST.PY?
--------------------
conftest.py is a special pytest file that pytest automatically discovers and loads.
It contains shared fixtures, hooks, and configuration that can be used by ALL tests
in the same directory and subdirectories.

Think of conftest.py as a "shared toolbox" for your tests - anything defined here
is available to any test file without needing to import it.

KEY CONCEPTS FOR BEGINNERS:
----------------------------
1. FIXTURES: Reusable setup/teardown objects for tests
   - Think of fixtures as "test dependencies" that pytest prepares for you
   - Instead of writing setup code in every test, define it once as a fixture
   - pytest automatically injects fixtures into tests that request them

2. FIXTURE SCOPES: Control when fixtures are created and destroyed
   - function (default): Created for each test, destroyed after
   - class: Created once per test class, shared by all methods
   - module: Created once per test file
   - package: Created once per test package
   - session: Created once for the entire test run (used below)

3. AUTO-USE: Fixtures can run automatically for every test
   - Use @pytest.fixture(autouse=True) to run without explicit request

EXAMPLE FLOW:
-------------
Without fixtures:
    def test_drone():
        drone = connect_to_drone()  # Setup (repeated in every test!)
        assert drone.is_connected
        drone.disconnect()          # Cleanup (easy to forget!)

With fixtures:
    @pytest.fixture
    def drone():
        d = connect_to_drone()      # Setup
        yield d                      # Hand to test
        d.disconnect()               # Cleanup (guaranteed to run!)

    def test_drone(drone):          # pytest injects the fixture
        assert drone.is_connected    # No setup code needed!

LEARNING RESOURCES:
------------------
- pytest fixtures: https://docs.pytest.org/en/stable/fixture.html
- conftest.py: https://docs.pytest.org/en/stable/fixture.html#conftest-py-sharing-fixtures-across-multiple-files
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import source modules for fixtures
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.vision.mock_detector import MockDetector, Detection


# =============================================================================
# SESSION-SCOPED FIXTURES
# =============================================================================
# Session-scoped fixtures are created ONCE for the entire test run.
# Use for expensive resources like database connections, config files,
# or in this case, hypothesis settings that should be consistent.


@pytest.fixture(scope="session")
def hypothesis_settings():
    """
    Provide hypothesis settings for property-based tests.

    WHAT IS HYPOTHESIS?
    -------------------
    Hypothesis is a Python library for property-based testing. Instead of
    writing specific test cases, you write properties that should always
    hold true, and Hypothesis generates test cases automatically.

    EXAMPLE OF PROPERTY-BASED TESTING:
    ----------------------------------
    Instead of:
        def test_addition():
            assert add(2, 3) == 5  # One specific case

    You write:
        from hypothesis import given, strategies as st

        @given(st.integers(), st.integers())  # Test ALL integers
        def test_addition_commutative(a, b):
            assert add(a, b) == add(b, a)  # Property: order doesn't matter

    THIS FIXTURE:
    -------------
    Configures how many examples Hypothesis should generate per test.
    - max_examples=50: Generate 50 random test cases per property test
    - Can be overridden via command line or environment variables

    USAGE IN TESTS:
    ---------------
        from hypothesis import given, settings
        import hypothesis.strategies as st

        @given(st.integers())
        @settings(**hypothesis_settings)  # Apply session settings
        def test_my_property(x):
            assert x + 0 == x

    Returns:
        hypothesis.settings object with max_examples=50
    """
    from hypothesis import settings
    return settings(max_examples=50)


# =============================================================================
# ASYNC TEST SUPPORT
# =============================================================================
# Python's asyncio requires an event loop to run coroutines.
# pytest-asyncio provides this, but we can customize the event loop here.


@pytest.fixture
def event_loop():
    """
    Create an event loop for async tests.

    WHY THIS IS NEEDED:
    -------------------
    Async/await tests need an event loop to run coroutines. pytest-asyncio
    provides a default event loop, but creating a custom one allows:
    1. Better control over loop lifecycle
    2. Ensuring fresh loop per test (isolation)
    3. Custom loop policies if needed

    ASYNC FIXTURE FLOW:
    -------------------
    1. Test requests async fixture (like sitl_drone below)
    2. pytest sees 'async def' and knows to use event loop
    3. This fixture creates the loop
    4. pytest-asyncio runs the coroutine
    5. Test executes with async support

    YIELD PATTERN FOR CLEANUP:
    --------------------------
    The yield followed by loop.close() ensures:
    - Loop is available during the test
    - Loop is properly closed after test (no resource leaks)
    - Even if test fails, close() is called

    Usage:
        This is automatically used by pytest-asyncio, no need to request
        it explicitly in tests.
    """
    loop = asyncio.new_event_loop()  # Create fresh event loop
    yield loop                        # Provide to test
    loop.close()                      # Cleanup: ensure loop is closed


# =============================================================================
# SITL DRONE FIXTURES
# =============================================================================
# SITL (Software-In-The-Loop) simulates PX4 flight controller on your computer.
# These fixtures provide MOCKED drone objects for fast, isolated unit tests
# without needing the actual SITL simulator running.


@pytest.fixture
async def sitl_drone() -> AsyncGenerator[MagicMock, None]:
    """
    Create a mocked drone System instance for testing without SITL.

    WHAT IS THIS FIXTURE?
    ---------------------
    Provides a fully mocked MAVSDK System object that behaves like a real drone
    but doesn't require PX4 SITL to be running. Perfect for fast unit tests.

    WHY USE MOCKS?
    --------------
    1. Speed: No need to start simulator (~10 seconds saved per test)
    2. Isolation: Tests don't fail due to simulation issues
    3. Control: Can simulate any condition (low battery, GPS loss, etc.)
    4. CI/CD: Tests run in environments without simulator

    WHAT IS ASYNC GENERATOR?
    ------------------------
    The 'AsyncGenerator' type hint means this fixture:
    1. Is an async function (can use await)
    2. Uses yield (can have setup and teardown)
    3. Returns the yielded value to the test

    MOCK STRUCTURE:
    ---------------
    The mocked drone mirrors MAVSDK's structure:
    - drone.core (connection info)
    - drone.telemetry (sensor data streams)
    - drone.action (flight commands)

    Each telemetry method is an async generator because MAVSDK uses
    Python's async generators to stream continuous data (like a real
    drone constantly sending telemetry).

    Yields:
        MagicMock: A mocked MAVSDK System with realistic telemetry:
            - Position: San Francisco coordinates at 10m altitude
            - Armed: True (drone ready to fly)
            - In Air: True (drone flying)
            - Battery: 85% at 22.4V
            - Flight Mode: HOLD
            - Health: All sensors OK
            - Velocity: 0 m/s in all axes (hovering)
            - Attitude: Level (0 deg roll/pitch/yaw)

    Example Usage:
        async def test_arm(sitl_drone):
            # sitl_drone is automatically injected by pytest
            await sitl_drone.action.arm()
            sitl_drone.action.arm.assert_called_once()

        async def test_telemetry(sitl_drone):
            async for position in sitl_drone.telemetry.position:
                assert position.latitude_deg == 37.7749
                break  # Only need first value

    NOTE ON ASYNC ITERATORS:
    ------------------------
    MAVSDK telemetry methods return async iterators (values over time).
    We mock these as async generators using 'yield' inside async def.

    To consume in tests:
        async for value in drone.telemetry.position:
            # Use value
            break  # Exit after first value

    Or use avatar.mav.telemetry_utils.async_iterator_to_list()
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

    # Mock telemetry streams (async generators that yield sensor data)
    # In real MAVSDK, these stream continuously. We yield once for testing.

    async def mock_position():
        """Simulate GPS position at San Francisco coordinates."""
        pos = MagicMock()
        pos.latitude_deg = 37.7749      # San Francisco latitude
        pos.longitude_deg = -122.4194   # San Francisco longitude
        pos.relative_altitude_m = 10.0  # 10m above takeoff point
        pos.absolute_altitude_m = 50.0   # 50m above sea level
        yield pos

    async def mock_armed():
        """Simulate armed state (drone motors ready)."""
        yield True

    async def mock_in_air():
        """Simulate in-air state (drone is flying)."""
        yield True

    async def mock_battery():
        """Simulate battery at 85% charge, 22.4V."""
        bat = MagicMock()
        bat.remaining_percent = 85.0
        bat.voltage_v = 22.4
        yield bat

    async def mock_flight_mode():
        """Simulate HOLD mode (hovering in place)."""
        yield MagicMock(value="HOLD")

    async def mock_health():
        """Simulate all health checks passing."""
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
        """Simulate zero velocity (hovering)."""
        vel = MagicMock()
        vel.north_m_s = 0.0
        vel.east_m_s = 0.0
        vel.down_m_s = 0.0
        yield vel

    async def mock_attitude_euler():
        """Simulate level attitude (0 degrees roll/pitch/yaw)."""
        att = MagicMock()
        att.roll_deg = 0.0
        att.pitch_deg = 0.0
        att.yaw_deg = 0.0
        yield att

    # Attach telemetry mocks to drone
    drone.telemetry.position = mock_position
    drone.telemetry.armed = mock_armed
    drone.telemetry.in_air = mock_in_air
    drone.telemetry.battery = mock_battery
    drone.telemetry.flight_mode = mock_flight_mode
    drone.telemetry.health = mock_health
    drone.telemetry.velocity_ned = mock_velocity_ned
    drone.telemetry.attitude_euler = mock_attitude_euler

    # Mock action methods with AsyncMock
    # AsyncMock allows: await drone.action.arm()
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
# The GuardianProcess validates all drone commands for safety.
# These fixtures provide pre-configured guardians for testing safety rules.


@pytest.fixture
def mock_guardian() -> GuardianProcess:
    """
    Create a GuardianProcess instance with default limits.

    WHAT IS GUARDIAN PROCESS?
    -------------------------
    The GuardianProcess validates all drone commands before execution.
    It enforces safety limits like:
    - Maximum altitude (120m default, aviation safety)
    - Geofence boundaries (stay within defined area)
    - Speed limits
    - Battery thresholds

    WHY HAVE A GUARDIAN?
    --------------------
    LLM-driven drones could receive dangerous commands:
    - "Fly to 10,000 feet" (exceeds altitude limits)
    - "Fly 50km away" (exceeds range)
    - "Fly through the building" (obstacle violation)

    The guardian blocks these BEFORE they reach the drone.

    THIS FIXTURE:
    -------------
    Creates a guardian with default HardLimits at San Francisco home position.
    Tests can validate commands against safety rules.

    Yields:
        GuardianProcess: Pre-configured guardian with:
            - Home: San Francisco (37.7749, -122.4194)
            - Default altitude limit: 120m
            - Default speed limits
            - All safety checks enabled

    Example Usage:
        def test_altitude_limit(mock_guardian):
            # Try to fly too high (150m exceeds 120m limit)
            is_valid, reason = mock_guardian.validate_command({
                "altitude_amsl_m": 150.0
            })
            assert not is_valid           # Should reject
            assert "altitude" in reason   # Reason mentions altitude

        def test_valid_command(mock_guardian):
            # Valid altitude within limits
            is_valid, _ = mock_guardian.validate_command({
                "altitude_amsl_m": 50.0
            })
            assert is_valid
    """
    limits = HardLimits()
    guardian = GuardianProcess(limits)
    guardian.set_home(37.7749, -122.4194)  # San Francisco coordinates
    return guardian


@pytest.fixture
def custom_limits() -> HardLimits:
    """
    Create customizable HardLimits for specific test scenarios.

    WHAT IS THIS FIXTURE?
    ---------------------
    Provides a fresh HardLimits object that tests can customize.
    Unlike mock_guardian (which has preset values), this allows
    tests to set specific limits for edge case testing.

    WHEN TO USE:
    ------------
    - Testing edge cases at boundary values
    - Testing with stricter/weaker limits than default
    - Testing specific failure modes

    Yields:
        HardLimits: Fresh limits object with defaults that can be modified:
            - max_altitude_amsl_m: 120.0 (can reduce for testing)
            - max_speed_m_s: 15.0
            - max_distance_from_home_m: 1000.0
            - min_battery_percent: 20.0

    Example Usage:
        def test_strict_altitude_limit(custom_limits):
            # Set very low altitude limit for testing
            custom_limits.max_altitude_amsl_m = 30.0
            guardian = GuardianProcess(custom_limits)

            # This should fail (50m > 30m)
            is_valid, reason = guardian.validate_command({
                "altitude_amsl_m": 50.0
            })
            assert not is_valid

        def test_custom_geofence(custom_limits):
            # Create tiny geofence
            custom_limits.max_distance_from_home_m = 10.0
            guardian = GuardianProcess(custom_limits)
            # Test boundary conditions...
    """
    return HardLimits()


# =============================================================================
# VISION PIPELINE FIXTURES
# =============================================================================
# The vision system uses YOLO for object detection.
# These fixtures provide mock detectors for testing without loading real models.


@pytest.fixture
def mock_detector() -> MockDetector:
    """
    Create a MockDetector instance for testing.

    WHAT IS MOCK DETECTOR?
    ----------------------
    MockDetector simulates YOLO object detection without loading a real model.
    It's much faster and produces deterministic (repeatable) results.

    WHY USE MOCK DETECTOR?
    ----------------------
    1. Speed: Real YOLO models take seconds to load
    2. Determinism: Same input always produces same output
    3. Control: Can simulate specific scenarios (many objects, no objects, etc.)
    4. No GPU needed: Runs on any machine

    THIS FIXTURE:
    -------------
    Creates a MockDetector with:
    - confidence_threshold: 0.5 (filter low-confidence detections)
    - num_detections: 3 (generate 3 fake objects per frame)
    - deterministic: True (same results every time)

    Yields:
        MockDetector: Configured detector that generates fake detections.

    Example Usage:
        def test_detection_filtering(mock_detector):
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = mock_detector.detect(frame)
            assert len(detections) == 3  # Fixture configured for 3

        def test_state_generation(mock_detector):
            # Generate state string from detections
            from avatar.vision.state_string import generate_state_string
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections = mock_detector.detect(frame)
            state = generate_state_string(detections)
            assert "person" in state  # Mock generates person detections
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

    WHAT IS A DETECTION?
    --------------------
    Detection represents a single object found by the vision system:
    - label: What was detected ("person", "car", "tree")
    - confidence: How sure the model is (0.0 to 1.0)
    - bbox: Bounding box [x_center, y_center, width, height] in normalized coords (0-1)
    - class_id: Numeric class identifier

    BOUNDING BOX FORMAT:
    --------------------
    [0.2, 0.3, 0.1, 0.15] means:
    - x_center: 20% from left edge
    - y_center: 30% from top edge
    - width: 10% of image width
    - height: 15% of image height

    Yields:
        Detection: A person detection with:
            - label: "person"
            - confidence: 0.85 (85% sure)
            - bbox: [0.2, 0.3, 0.1, 0.15] (center-left area)
            - class_id: 1

    Example Usage:
        def test_state_string(sample_detection):
            from avatar.vision.state_string import generate_state_string
            state = generate_state_string([sample_detection])
            assert "person" in state
            assert "85%" in state or "0.85" in state

        def test_detection_attributes(sample_detection):
            assert sample_detection.label == "person"
            assert sample_detection.confidence > 0.8
            assert len(sample_detection.bbox) == 4
    """
    return Detection(
        label="person",
        confidence=0.85,
        bbox=[0.2, 0.3, 0.1, 0.15],  # x_center, y_center, width, height
        class_id=1
    )


# =============================================================================
# TEST FRAME FIXTURES
# =============================================================================
# These fixtures provide sample image data for testing the vision pipeline.


@pytest.fixture
def sample_frame():
    """
    Create a sample numpy frame for vision testing.

    WHAT IS THIS FIXTURE?
    ---------------------
    Provides a blank numpy array simulating a camera frame.
    Shape is (height, width, channels) = (480, 640, 3) for VGA RGB image.

    IMAGE FORMATS:
    --------------
    - Shape: (H, W, C) = (rows, cols, color channels)
    - 480 rows (height), 640 columns (width), 3 channels (RGB)
    - dtype: uint8 (unsigned 8-bit integer, values 0-255)
    - Black frame (all zeros)

    Yields:
        numpy.ndarray: Black image array with shape (480, 640, 3)

    Example Usage:
        def test_detector_on_black_frame(mock_detector, sample_frame):
            # Even on black frame, mock detector returns fake detections
            detections = mock_detector.detect(sample_frame)
            assert len(detections) > 0

        def test_image_processing(sample_frame):
            from avatar.vision.utils import resize_frame
            resized = resize_frame(sample_frame, target_size=(320, 240))
            assert resized.shape == (240, 320, 3)
    """
    import numpy as np
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_pil_image():
    """
    Create a sample PIL Image for vision testing.

    WHAT IS THIS FIXTURE?
    ---------------------
    Provides a PIL (Pillow) Image object with a simple pattern.
    PIL Images are often used for pre-processing before converting to numpy.

    THE TEST IMAGE:
    ---------------
    - Size: 640x480 pixels
    - Black background with red square in upper-left quadrant
    - Red square: rows 100-200, columns 100-200

    Yields:
        PIL.Image.Image: RGB image with red square pattern

    Example Usage:
        def test_pil_to_numpy_conversion(sample_pil_image):
            import numpy as np
            array = np.array(sample_pil_image)
            assert array.shape == (480, 640, 3)
            # Check red pixel
            assert array[150, 150, 0] == 255  # Red channel

        def test_image_resize(sample_pil_image):
            resized = sample_pil_image.resize((320, 240))
            assert resized.size == (320, 240)
    """
    from PIL import Image
    import numpy as np
    # Create a simple RGB image (black with red square)
    array = np.zeros((480, 640, 3), dtype=np.uint8)
    array[100:200, 100:200] = [255, 0, 0]  # Red square at (100,100) to (200,200)
    return Image.fromarray(array, mode='RGB')


# =============================================================================
# MCP SERVER FIXTURES
# =============================================================================
# MCP (Model Context Protocol) allows AI agents to control the drone.
# These fixtures provide server configurations and mocked connections.


@pytest.fixture
def mcp_server_config():
    """
    Create MCP server configuration for testing.

    WHAT IS MCP?
    ------------
    Model Context Protocol (MCP) is a protocol for AI agents to interact
    with external systems. Project Avatar's MCP server exposes drone
    control tools to any MCP-compatible AI agent (Claude, Cursor, etc.).

    MCP SERVER CONFIGURATION:
    -------------------------
    - system_address: MAVSDK connection string (udp://:14540 for SITL)
    - max_retries: Connection retry attempts
    - retry_delay_s: Seconds between retries
    - health_timeout_s: Maximum seconds to wait for health checks

    THIS FIXTURE:
    -------------
    Creates a test-friendly configuration with short timeouts for fast tests.

    Yields:
        DroneMCPServerConfig: Server config with test values:
            - system_address: "udp://:14540" (SITL default)
            - max_retries: 1 (fail fast in tests)
            - retry_delay_s: 0.1 (fast retries)
            - health_timeout_s: 5.0 (short timeout)

    Example Usage:
        def test_server_initialization(mcp_server_config):
            from avatar.mcp_server.server import DroneMCPServer
            server = DroneMCPServer(mcp_server_config)
            assert server.config.system_address == "udp://:14540"
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

    WHAT IS DRONE CONNECTION?
    -------------------------
    DroneConnection manages the MAVSDK connection to the drone.
    It handles connection lifecycle, reconnection, and health monitoring.

    THIS FIXTURE:
    -------------
    Creates a DroneConnection with a mocked underlying MAVSDK System.
    The mock provides realistic telemetry without real hardware.

    MOCK SETUP:
    -----------
    - Connection: Always reports connected
    - Health: All sensors OK
    - Position: San Francisco at ground level
    - Actions: All commands mocked with AsyncMock

    Yields:
        DroneConnection: Connected connection with mocked drone:
            - _connected: True
            - drone: MagicMock with telemetry and actions
            - Configured for udp://:14540 (SITL default)

    Example Usage:
        async def test_mcp_arm_command(mock_drone_connection):
            from avatar.mcp_server.tools import arm_drone
            result = await arm_drone(mock_drone_connection)
            assert result.success is True
            mock_drone_connection.drone.action.arm.assert_called_once()

        async def test_telemetry_stream(mock_drone_connection):
            async for position in mock_drone_connection.drone.telemetry.position:
                assert position.latitude_deg == 37.7749
                break
    """
    from avatar.mav.connection_config import ConnectionConfig
    from avatar.mcp_server.compat import DroneConnection

    # Create connection with test-friendly config
    config = ConnectionConfig(
        system_address="udp://:14540",
        max_retries=1,
        health_timeout_s=5.0
    )

    conn = DroneConnection(config)

    # Create a fully mocked MAVSDK System
    mock_drone = MagicMock()

    # Mock async telemetry streams
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

    # Attach mocks
    mock_drone.core.connection_state = mock_connection_state
    mock_drone.telemetry.health = mock_health
    mock_drone.telemetry.position = mock_position

    # Mock all action methods
    mock_drone.action.arm = AsyncMock()
    mock_drone.action.disarm = AsyncMock()
    mock_drone.action.takeoff = AsyncMock()
    mock_drone.action.land = AsyncMock()
    mock_drone.action.return_to_launch = AsyncMock()
    mock_drone.action.hold = AsyncMock()
    mock_drone.action.set_takeoff_altitude = AsyncMock()

    # Install mock into connection
    conn.drone = mock_drone
    conn._connected = True

    return conn


# =============================================================================
# PYTEST HOOKS FOR SITL MARKER
# =============================================================================
# These hooks implement the --run-sitl flag and 'sitl' marker behavior.
# SITL tests require PX4 SITL simulator to be running, so they are skipped
# by default unless explicitly enabled with --run-sitl.


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-sitl command line option.

    WHAT THIS DOES:
        Registers the --run-sitl flag with pytest's argument parser.
        This flag allows users to explicitly enable SITL integration tests.

    WHY IT MATTERS:
        SITL tests require the PX4 simulator to be running. Without this flag,
        these tests would fail or hang in environments without SITL.

    Usage:
        pytest --run-sitl  # Run all tests including SITL tests
        pytest             # Skip SITL tests (default behavior)
    """
    # Check if option already registered (e.g., by e2e/conftest.py)
    try:
        parser.addoption(
            "--run-sitl",
            action="store_true",
            default=False,
            help="Run SITL integration tests (requires PX4 SITL running)",
        )
    except ValueError:
        # Option already registered by another conftest
        pass


def pytest_configure(config: pytest.Config) -> None:
    """Configure the 'sitl' marker.

    WHAT THIS DOES:
        Registers the 'sitl' marker with pytest's marker system.
        This allows using @pytest.mark.sitl on test functions.

    WHY IT MATTERS:
        Pytest requires markers to be registered before use (with --strict-markers).
        This hook ensures the marker is properly defined.

    Usage in tests:
        @pytest.mark.sitl
        def test_flight(): ...

        pytestmark = pytest.mark.sitl  # Module-level for all tests in file
    """
    config.addinivalue_line(
        "markers",
        "sitl: marks tests that require PX4 SITL and --run-sitl",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip SITL tests unless --run-sitl flag is provided.

    WHAT THIS DOES:
        Called after test collection, before test execution.
        Adds a skip marker to any test with the 'sitl' keyword/mark
        unless the --run-sitl flag was provided.

    WHY IT MATTERS:
        This is the enforcement mechanism - it ensures SITL tests are
        automatically skipped by default, protecting CI and local dev
        environments from tests that require the simulator.

    HOW IT WORKS:
        1. Check if --run-sitl flag was passed
        2. If yes: do nothing (allow SITL tests to run)
        3. If no: add skip marker to all items with 'sitl' keyword
    """
    if config.getoption("--run-sitl"):
        return  # User explicitly wants to run SITL tests

    # Create skip marker with descriptive reason
    skip_sitl = pytest.mark.skip(
        reason="SITL tests require PX4 SITL running and --run-sitl flag"
    )

    # Apply skip marker to all SITL-marked tests
    for item in items:
        if "sitl" in item.keywords:
            item.add_marker(skip_sitl)


# =============================================================================
# HOOK FUNCTIONS (Additional Examples)
# =============================================================================
# You can also define other pytest hooks in conftest.py to customize
# test behavior. These run at specific points in the test lifecycle.


# =============================================================================
# ADDING NEW FIXTURES - QUICK REFERENCE
# =============================================================================
#
# To add a new fixture:
#
# 1. Choose the right scope:
#    @pytest.fixture                    # Fresh for each test
#    @pytest.fixture(scope="module")     # Once per test file
#    @pytest.fixture(scope="session")   # Once for all tests
#
# 2. Define setup and teardown with yield:
#    @pytest.fixture
#    def my_resource():
#        resource = create()  # Setup
#        yield resource       # Hand to test
#        resource.cleanup()   # Teardown (always runs!)
#
# 3. For async fixtures, use async def:
#    @pytest.fixture
#    async def async_resource():
#        resource = await create_async()
#        yield resource
#        await resource.cleanup()
#
# 4. Request fixtures in tests by naming them:
#    def test_something(my_resource):  # pytest injects the fixture
#        assert my_resource.is_ready
#
# 5. Fixtures can request other fixtures:
#    @pytest.fixture
#    def dependent_fixture(mock_guardian):
#        # mock_guardian is automatically provided
#        return create_with_guardian(mock_guardian)
