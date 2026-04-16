"""E2E Test Configuration and Fixtures.

WHAT IS CONFTEST.PY?
--------------------
conftest.py is a special pytest file that pytest automatically discovers and loads
before running any tests in the same directory or subdirectories. It provides:
- Shared fixtures (test dependencies)
- Custom pytest hooks (modify test behavior)
- Command-line options
- Test markers

Key characteristics:
- Automatically loaded by pytest - no imports needed in test files
- Applies to all tests in the same folder and subfolders
- Can define fixtures that multiple tests can share
- Great for common setup like database connections, test data, or mocking

WHAT ARE FIXTURES?
------------------
Fixtures are pytest's way of providing test dependencies. They handle:
- Setup: Preparing the environment/objects needed for tests
- Teardown: Cleaning up after tests complete (even if they fail)
- Reuse: Same setup can be shared across multiple tests
- Scope control: Fixtures can run once per test, module, or entire test session

Fixture scope levels (decorator argument):
- @pytest.fixture(scope="function") - Runs once per test function (default)
- @pytest.fixture(scope="class") - Runs once per test class
- @pytest.fixture(scope="module") - Runs once per test module (file)
- @pytest.fixture(scope="session") - Runs once for entire test run

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
        # SETUP: Runs before the test - create resources, connect to services
        resource = create_resource()
        yield resource  # Provides the resource to the test
        # TEARDOWN: Runs after the test completes (even if it failed!)
        resource.cleanup()

For async fixtures (common with drone control):

    @pytest.fixture
    async def async_fixture():
        # SETUP
        connection = await connect_to_drone()
        yield connection
        # TEARDOWN
        await connection.disconnect()

WHAT THIS CONFTEST PROVIDES
-----------------------------
This conftest.py provides fixtures for end-to-end testing with a real or simulated
drone (PX4 SITL - Software In The Loop). It includes:

1. pytest_addoption() - Custom command-line flags (--run-sitl, --mock-mode)
2. pytest_configure() - Custom test markers (e2e, mission, failsafe, etc.)
3. PerformanceCollector class - Measure operation timing
4. Multiple fixtures for drone connection and flight components

All fixtures require the --run-sitl flag to execute against real SITL.
Without --run-sitl, tests are skipped or run with mocks (if mock_mode is enabled).
"""

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import pytest

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
# Configure logging so we can see what's happening during E2E tests.
# This is especially useful for debugging drone connection issues.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
# These constants define default values for SITL testing.
# They can be overridden via environment variables.

SITL_CONNECTION_URL = os.getenv("SITL_URL", "udp://:14540")
PX4_SITL_DIR = os.getenv("PX4_SITL_DIR", "PX4-Autopilot")
DEFAULT_TAKEOFF_ALTITUDE = 5.0  # meters
CONNECTION_TIMEOUT = 30.0  # seconds
GPS_LOCK_TIMEOUT = 60.0  # seconds
ARM_TIMEOUT = 10.0  # seconds
TAKEOFF_TIMEOUT = 30.0  # seconds
LAND_TIMEOUT = 45.0  # seconds
VELOCITY_TIMEOUT = 5.0  # seconds


# =============================================================================
# PYTEST CONFIGURATION HOOKS
# =============================================================================
# These functions are pytest hooks - they modify pytest's behavior.
# Hooks are automatically called by pytest at specific points.


def pytest_addoption(parser: Any) -> None:
    """Add custom command-line options for E2E tests.

    This hook runs during pytest startup and lets us add custom CLI flags.
    Test functions can access these via the 'request' fixture.

    Options added:
        --run-sitl: Actually connect to SITL (without this, E2E tests skip)
        --mock-mode: Use mocks when SITL unavailable (for CI)
        --sitl-timeout: Global timeout for SITL operations
    """
    # Guard against duplicate option registration
    try:
        parser.addoption(
            "--run-sitl",
            action="store_true",
            default=False,
            help="Run tests against real SITL (requires PX4 SITL running)",
        )
    except ValueError:
        pass  # Already registered
    try:
        parser.addoption(
            "--mock-mode",
            action="store_true",
            default=False,
            help="Use mocks when SITL is not available (for CI without SITL)",
        )
    except ValueError:
        pass  # Already registered
    parser.addoption(
        "--sitl-timeout",
        action="store",
        default=300,
        type=int,
        help="Global timeout for SITL operations in seconds",
    )


def pytest_configure(config: Any) -> None:
    """Configure custom markers.

    This hook registers custom markers that tests can use with @pytest.mark.
    Markers let us categorize and selectively run tests.

    Markers registered:
        e2e: End-to-end integration tests
        mission: Full mission tests
        failsafe: Tests that trigger failsafe conditions
        performance: Benchmark/performance tests
        sitl_required: Tests requiring running SITL
    """
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end integration tests"
    )
    config.addinivalue_line(
        "markers", "mission: marks tests as full mission tests"
    )
    config.addinivalue_line(
        "markers", "failsafe: marks tests as failsafe trigger tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance benchmark tests"
    )
    config.addinivalue_line(
        "markers", "sitl_required: marks tests that require running SITL"
    )


# =============================================================================
# HELPER CLASSES
# =============================================================================
# These classes support the fixtures but aren't fixtures themselves.


@dataclass
class PerformanceMetrics:
    """Performance measurement results.

    Attributes:
        operation: Name of the operation measured
        duration_ms: How long the operation took in milliseconds
        timestamp: When the measurement was taken (Unix timestamp)
        metadata: Additional data about the operation
    """
    operation: str
    duration_ms: float
    timestamp: float
    metadata: Dict[str, Any]


class PerformanceCollector:
    """Collect and analyze performance metrics during tests.

    This helper class tracks timing of operations across multiple tests.
    It's used by the performance_collector fixture to provide shared
    metrics collection.

    Example usage in a test:
        def test_takeoff(performance_collector, sitl_drone):
            performance_collector.start("takeoff")
            await sitl_drone.action.takeoff()
            metric = performance_collector.end("takeoff", altitude=5.0)
            assert metric.duration_ms < 5000  # Should complete in 5 seconds
    """

    def __init__(self) -> None:
        """Initialize the collector with empty metrics storage."""
        self._metrics: List[PerformanceMetrics] = []
        self._start_times: Dict[str, float] = {}

    def start(self, operation: str) -> None:
        """Start timing an operation.

        Args:
            operation: Unique name for this operation (used to match start/end)
        """
        self._start_times[operation] = time.perf_counter()

    def end(self, operation: str, **metadata: Any) -> PerformanceMetrics:
        """End timing an operation and record metrics.

        Args:
            operation: Name of the operation (must match a previous start() call)
            **metadata: Additional data to store with the metric

        Returns:
            PerformanceMetrics object with timing results

        Raises:
            ValueError: If start() wasn't called for this operation
        """
        if operation not in self._start_times:
            raise ValueError(f"Operation {operation} was not started")

        duration_s = time.perf_counter() - self._start_times[operation]
        duration_ms = duration_s * 1000

        metric = PerformanceMetrics(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            metadata=metadata,
        )
        self._metrics.append(metric)
        del self._start_times[operation]

        return metric

    def get_metrics(self, operation: Optional[str] = None) -> List[PerformanceMetrics]:
        """Get collected metrics.

        Args:
            operation: If specified, only return metrics for this operation name

        Returns:
            List of PerformanceMetrics objects
        """
        if operation:
            return [m for m in self._metrics if m.operation == operation]
        return self._metrics.copy()

    def get_average(self, operation: str) -> float:
        """Get average duration for an operation.

        Args:
            operation: Operation name to average

        Returns:
            Average duration in milliseconds, or 0.0 if no metrics
        """
        metrics = self.get_metrics(operation)
        if not metrics:
            return 0.0
        return sum(m.duration_ms for m in metrics) / len(metrics)

    def get_max(self, operation: str) -> float:
        """Get maximum duration for an operation.

        Args:
            operation: Operation name to find max for

        Returns:
            Maximum duration in milliseconds, or 0.0 if no metrics
        """
        metrics = self.get_metrics(operation)
        if not metrics:
            return 0.0
        return max(m.duration_ms for m in metrics)

    def clear(self) -> None:
        """Clear all metrics. Useful between test suites."""
        self._metrics.clear()
        self._start_times.clear()


# =============================================================================
# FIXTURES
# =============================================================================
# Below are the fixtures that tests can request by adding them as parameters.
# Each fixture is documented with: what it provides, its scope, and setup/teardown.


@pytest.fixture(scope="session")
def sitl_config(request: Any) -> Dict[str, Any]:
    """Session-wide SITL configuration.

    WHAT IT PROVIDES:
        A dictionary with SITL test configuration parsed from command-line options.

    SCOPE: session
        This fixture runs once for the entire test session (all tests).
        All tests share the same configuration dictionary.

    CONTENTS:
        - run_sitl (bool): Whether --run-sitl flag was passed
        - mock_mode (bool): Whether --mock-mode flag was passed
        - timeout (int): Value from --sitl-timeout
        - connection_url (str): MAVSDK connection URL from env or default

    USAGE IN TESTS:
        def test_something(sitl_config):
            if not sitl_config["run_sitl"]:
                pytest.skip("SITL not enabled")
            drone = await connect(sitl_config["connection_url"])
    """
    return {
        "run_sitl": request.config.getoption("--run-sitl"),
        "mock_mode": request.config.getoption("--mock-mode"),
        "timeout": request.config.getoption("--sitl-timeout"),
        "connection_url": SITL_CONNECTION_URL,
    }


@pytest.fixture(scope="session")
def performance_collector() -> PerformanceCollector:
    """Session-wide performance metrics collector.

    WHAT IT PROVIDES:
        A PerformanceCollector instance for tracking operation timing across tests.

    SCOPE: session
        Single instance shared across all tests. This allows comparing metrics
        across multiple tests or calculating averages.

    SETUP: Creates a new PerformanceCollector instance
    TEARDOWN: None needed (stateless except for metrics list)

    USAGE IN TESTS:
        def test_operation(performance_collector, sitl_drone):
            performance_collector.start("arm")
            await sitl_drone.action.arm()
            metric = performance_collector.end("arm")
            assert metric.duration_ms < 2000

    ANALYSIS AFTER TESTS:
        avg = performance_collector.get_average("arm")
        print(f"Average arm time: {avg}ms")
    """
    return PerformanceCollector()


@pytest.fixture
async def mavsdk_drone(
    sitl_config: Dict[str, Any]
) -> AsyncGenerator[Any, None]:
    """Create a real MAVSDK drone connection for E2E tests.

    WHAT IT PROVIDES:
        A MAVSDK System instance connected to SITL (Software In The Loop).
        This is a real drone connection for end-to-end testing.

    SCOPE: function (default)
        Creates a fresh connection for each test to ensure isolation.

    SETUP:
        1. Checks if --run-sitl flag was passed (skips if not)
        2. Imports MAVSDK System class
        3. Connects to drone at SITL_CONNECTION_URL
        4. Waits for connection state confirmation
        5. Yields the connected drone instance

    TEARDOWN:
        MAVSDK handles disconnection automatically, but we log the disconnect.
        The 'finally' block ensures cleanup even if the test fails.

    SKIPS:
        - If --run-sitl is not specified
        - If MAVSDK is not installed
        - If connection to SITL fails

    USAGE IN TESTS:
        async def test_flight(mavsdk_drone):
            drone = mavsdk_drone
            await drone.action.arm()
            await drone.action.takeoff()
    """
    if not sitl_config["run_sitl"]:
        pytest.skip("Use --run-sitl to execute E2E tests against real SITL")

    try:
        from mavsdk import System
    except ImportError:
        pytest.skip("MAVSDK not installed")

    drone = System()
    logger.info(f"Connecting to SITL at {sitl_config['connection_url']}")

    try:
        await drone.connect(system_address=sitl_config["connection_url"])

        # Wait for connection with timeout
        connected = False
        async for state in drone.core.connection_state():
            if state.is_connected:
                connected = True
                logger.info(f"Connected to drone: UUID={state.uuid}")
                break
            break  # Only check first state

        if not connected:
            pytest.skip("Could not connect to SITL - ensure PX4 SITL is running")

        yield drone

    finally:
        # Cleanup - MAVSDK handles disconnection automatically
        logger.info("Disconnecting from drone")


@pytest.fixture
async def sitl_drone(
    mavsdk_drone: Any,
    performance_collector: PerformanceCollector,
) -> AsyncGenerator[Any, None]:
    """Connected SITL drone with GPS lock and health checks.

    WHAT IT PROVIDES:
        A MAVSDK System instance that is fully ready for flight operations:
        - Connected to SITL
        - GPS lock acquired (global_position_ok and home_position_ok)
        - Initial position logged

    SCOPE: function
        Fresh GPS lock check for each test.

    SETUP:
        1. Gets mavsdk_drone (connected drone)
        2. Waits for GPS lock (health.is_global_position_ok)
        3. Logs initial position for debugging
        4. Yields the ready-to-fly drone

    TEARDOWN:
        None explicit - mavsdk_drone handles cleanup

    FAILS:
        If GPS lock not acquired within GPS_LOCK_TIMEOUT (60 seconds)

    DEPENDENCIES:
        - mavsdk_drone: Provides the base connection
        - performance_collector: Available if timing needed (not used directly)

    USAGE IN TESTS:
        async def test_mission(sitl_drone):
            # sitl_drone is already connected and has GPS lock
            await sitl_drone.action.arm()
            await sitl_drone.action.takeoff()
    """
    drone = mavsdk_drone

    # Wait for GPS lock
    logger.info("Waiting for GPS lock...")
    gps_locked = False
    start_time = time.time()

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            gps_locked = True
            logger.info("GPS lock acquired")
            break
        if time.time() - start_time > GPS_LOCK_TIMEOUT:
            pytest.fail(f"GPS lock timeout after {GPS_LOCK_TIMEOUT}s")
        break  # Check once, loop will continue via MAVSDK

    if not gps_locked:
        pytest.fail("GPS lock not available - cannot proceed with flight tests")

    # Collect initial telemetry
    async for position in drone.telemetry.position():
        logger.info(
            f"Initial position: ({position.latitude_deg:.6f}, "
            f"{position.longitude_deg:.6f}), alt={position.relative_altitude_m:.2f}m"
        )
        break

    yield drone


@pytest.fixture
def flight_components(sitl_config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize and provide all flight control components.

    WHAT IT PROVIDES:
        A dictionary containing initialized flight control components:
        - guardian: GuardianProcess instance (safety limits)
        - state_machine: FlightStateMachine instance (flight state tracking)
        - escalation_matrix: EscalationMatrix instance (failure escalation)
        - telemetry_cache: TelemetryCache instance (telemetry buffering)
        - connection_manager: ConnectionManager instance (connection handling)
        - heartbeat_service: HeartbeatService instance (keepalive)
        - limits: HardLimits instance (safety boundaries)

    SCOPE: function
        Fresh component set for each test to ensure clean state.

    SETUP:
        1. Imports all flight control components
        2. Creates instances with test configurations
        3. Resets state machine to initial state
        4. Returns dictionary of components

    TEARDOWN:
        None explicit - Python garbage collection handles cleanup

    USAGE IN TESTS:
        def test_safety(flight_components):
            guardian = flight_components["guardian"]
            state_machine = flight_components["state_machine"]
            assert guardian.check_limits()
    """
    # Import components
    from avatar.mav.guardian import GuardianProcess, HardLimits
    from avatar.mav.state_machine import FlightStateMachine
    from avatar.mav.escalation_matrix import EscalationMatrix
    from avatar.mav.telemetry_cache import TelemetryCache
    from avatar.mav.connection_manager import ConnectionManager
    from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig

    # Create components
    limits = HardLimits()
    guardian = GuardianProcess(limits)
    state_machine = FlightStateMachine()
    escalation_matrix = EscalationMatrix()
    telemetry_cache = TelemetryCache()
    connection_manager = ConnectionManager()
    heartbeat_service = HeartbeatService(
        HeartbeatConfig(heartbeat_hz=20.0)  # 20Hz
    )

    # Reset state machine to initial state
    state_machine.reset(force=True)
    state_machine.transition(
        state_machine.current_state.__class__,
        "test_setup",
        "test",
    )

    return {
        "guardian": guardian,
        "state_machine": state_machine,
        "escalation_matrix": escalation_matrix,
        "telemetry_cache": telemetry_cache,
        "connection_manager": connection_manager,
        "heartbeat_service": heartbeat_service,
        "limits": limits,
    }


@pytest.fixture
async def flight_tools(
    sitl_config: Dict[str, Any],
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> AsyncGenerator[Any, None]:
    """Flight tools instance configured for E2E testing.

    WHAT IT PROVIDES:
        A FlightTools instance ready for flight commands. This is the high-level
        interface that MCP tools use to control the drone.

    SCOPE: function
        Fresh FlightTools for each test.

    SETUP:
        1. Creates FlightToolsConfig with SITL settings
        2. Creates FlightTools instance with hard limits and state machine
        3. Yields the configured tools

    TEARDOWN:
        Calls tools.disconnect() to clean up connections.

    DEPENDENCIES:
        - sitl_config: For connection URL and timeouts
        - sitl_drone: Provides the drone connection
        - flight_components: Provides hard limits and state machine

    USAGE IN TESTS:
        async def test_flight_tools(flight_tools):
            result = await flight_tools.arm_drone()
            assert result.success
            result = await flight_tools.takeoff(altitude=5.0)
            assert result.success
    """
    from avatar.mcp_server.tools.flight_tools import FlightTools, FlightToolsConfig

    config = FlightToolsConfig(
        system_address=sitl_config["connection_url"],
        max_retries=3,
        retry_delay_s=1.0,
        health_timeout_s=30.0,
        default_takeoff_altitude_m=DEFAULT_TAKEOFF_ALTITUDE,
    )

    tools = FlightTools(
        config=config,
        hard_limits=flight_components["limits"],
        state_machine=flight_components["state_machine"],
    )

    yield tools

    # Cleanup
    await tools.disconnect()


@pytest.fixture
async def async_guardian(
    flight_components: Dict[str, Any],
) -> AsyncGenerator[Any, None]:
    """AsyncGuardian instance for 20Hz safety monitoring.

    WHAT IT PROVIDES:
        An AsyncGuardian instance that performs high-frequency safety monitoring
        at 20Hz. This is the production safety system.

    SCOPE: function
        Fresh guardian for each test to ensure clean monitoring state.

    SETUP:
        1. Creates AsyncGuardian with test configuration
        2. Sets auto_failsafe=False to prevent automatic actions during tests
        3. Starts the guardian monitoring loop

    TEARDOWN:
        Stops the guardian monitoring loop to prevent background activity.

    DEPENDENCIES:
        - flight_components: Provides connection_manager, heartbeat_service,
          and state_machine

    CONFIGURATION:
        - heartbeat_interval_s: 0.05 (20Hz monitoring)
        - offboard_timeout_s: 0.5 (fail if offboard stops responding)
        - auto_failsafe: False (manual control in tests)

    USAGE IN TESTS:
        async def test_safety_monitor(async_guardian, flight_tools):
            await async_guardian.start()
            # Run test operations
            violations = async_guardian.get_violations()
            assert len(violations) == 0
    """
    from avatar.mav.guardian_async import AsyncGuardian, GuardianConfig

    guardian = AsyncGuardian(
        connection_manager=flight_components["connection_manager"],
        heartbeat_service=flight_components["heartbeat_service"],
        state_machine=flight_components["state_machine"],
        config=GuardianConfig(
            heartbeat_interval_s=0.05,  # 20Hz
            offboard_timeout_s=0.5,
            auto_failsafe=False,  # Don't auto-execute in tests
        ),
    )

    # Start monitoring
    await guardian.start()
    logger.info("AsyncGuardian started for E2E testing")

    yield guardian

    # Cleanup
    await guardian.stop()
    logger.info("AsyncGuardian stopped")


@pytest.fixture
async def telemetry_provider(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> AsyncGenerator[Any, None]:
    """Telemetry cache with live SITL data provider.

    WHAT IT PROVIDES:
        A TelemetryCache instance that is actively fetching live telemetry
        from the SITL drone in the background.

    SCOPE: function
        Fresh cache and fetcher for each test.

    SETUP:
        1. Gets TelemetryCache from flight_components
        2. Defines fetch_telemetry() async function that:
           - Fetches position, velocity, battery from SITL
           - Fetches armed state, in_air state, flight mode
           - Returns TelemetryData object
        3. Starts the cache with the fetch function

    TEARDOWN:
        Stops the telemetry cache to prevent background fetching.

    DEPENDENCIES:
        - sitl_drone: Provides telemetry streams
        - flight_components: Provides the TelemetryCache instance

    USAGE IN TESTS:
        async def test_telemetry(telemetry_provider):
            # telemetry_provider is a TelemetryCache with live data
            data = telemetry_provider.get_latest()
            assert data.battery_percent > 0
            assert data.is_gps_ok
    """
    cache = flight_components["telemetry_cache"]

    async def fetch_telemetry() -> Any:
        """Fetch telemetry from SITL.

        This inner function is called repeatedly by the TelemetryCache
        to refresh data. It fetches all available telemetry types from
        the SITL drone.
        """
        from avatar.mav.telemetry_cache import TelemetryData

        drone = sitl_drone

        # Fetch all telemetry data
        position = None
        velocity = None
        battery = None
        armed = False
        in_air = False
        flight_mode = "UNKNOWN"

        async for pos in drone.telemetry.position():
            position = pos
            break

        async for vel in drone.telemetry.velocity_ned():
            velocity = vel
            break

        async for bat in drone.telemetry.battery():
            battery = bat
            break

        async for arm in drone.telemetry.armed():
            armed = arm
            break

        async for air in drone.telemetry.in_air():
            in_air = air
            break

        async for mode in drone.telemetry.flight_mode():
            flight_mode = str(mode)
            break

        return TelemetryData(
            timestamp=time.time(),
            latitude=position.latitude_deg if position else 0.0,
            longitude=position.longitude_deg if position else 0.0,
            altitude=position.relative_altitude_m if position else 0.0,
            velocity_north=velocity.north_m_s if velocity else 0.0,
            velocity_east=velocity.east_m_s if velocity else 0.0,
            velocity_down=velocity.down_m_s if velocity else 0.0,
            groundspeed=(velocity.north_m_s**2 + velocity.east_m_s**2)**0.5 if velocity else 0.0,
            roll=0.0,  # Could fetch from attitude if needed
            pitch=0.0,
            yaw=0.0,
            battery_percent=battery.remaining_percent if battery else 0.0,
            battery_voltage=battery.voltage_v if battery else 0.0,
            battery_current=0.0,
            armed=armed,
            in_air=in_air,
            flight_mode=flight_mode,
            gps_fix=3,  # Assume 3D fix
            is_gps_ok=True,
            is_home_position_ok=True,
        )

    # Start telemetry cache
    await cache.start(fetch_telemetry)
    logger.info("Telemetry cache started with SITL provider")

    yield cache

    # Cleanup
    await cache.stop()
    logger.info("Telemetry cache stopped")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# These are utility functions (not fixtures) that tests can import and use.


async def wait_for_armed(drone: Any, timeout: float = ARM_TIMEOUT) -> bool:
    """Wait until drone is armed.

    Polls the armed telemetry at 10Hz until armed or timeout.

    Args:
        drone: MAVSDK System instance
        timeout: Maximum seconds to wait

    Returns:
        True if armed, False if timeout
    """
    start_time = time.time()
    async for armed in drone.telemetry.armed():
        if armed:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_disarmed(drone: Any, timeout: float = ARM_TIMEOUT) -> bool:
    """Wait until drone is disarmed.

    Polls the armed telemetry at 10Hz until disarmed or timeout.

    Args:
        drone: MAVSDK System instance
        timeout: Maximum seconds to wait

    Returns:
        True if disarmed, False if timeout
    """
    start_time = time.time()
    async for armed in drone.telemetry.armed():
        if not armed:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_in_air(drone: Any, timeout: float = TAKEOFF_TIMEOUT) -> bool:
    """Wait until drone is in the air.

    Polls the in_air telemetry at 10Hz until true or timeout.

    Args:
        drone: MAVSDK System instance
        timeout: Maximum seconds to wait

    Returns:
        True if in air, False if timeout
    """
    start_time = time.time()
    async for in_air in drone.telemetry.in_air():
        if in_air:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_on_ground(drone: Any, timeout: float = LAND_TIMEOUT) -> bool:
    """Wait until drone is on the ground.

    Polls the in_air telemetry at 10Hz until false or timeout.

    Args:
        drone: MAVSDK System instance
        timeout: Maximum seconds to wait

    Returns:
        True if on ground, False if timeout
    """
    start_time = time.time()
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def get_current_altitude(drone: Any) -> float:
    """Get current relative altitude.

    Args:
        drone: MAVSDK System instance

    Returns:
        Relative altitude in meters, or 0.0 if unavailable
    """
    async for position in drone.telemetry.position():
        return position.relative_altitude_m
    return 0.0


async def get_current_position(drone: Any) -> Tuple[float, float]:
    """Get current latitude and longitude.

    Args:
        drone: MAVSDK System instance

    Returns:
        Tuple of (latitude, longitude) in degrees, or (0.0, 0.0) if unavailable
    """
    async for pos in drone.telemetry.position():
        return (pos.latitude_deg, pos.longitude_deg)
    return (0.0, 0.0)


async def measure_latency(
    operation: callable,
    *args: Any,
    **kwargs: Any
) -> Tuple[Any, float]:
    """Measure latency of an async operation.

    Args:
        operation: Async function to measure
        *args: Arguments to pass to operation
        **kwargs: Keyword arguments to pass to operation

    Returns:
        Tuple of (operation_result, duration_ms)
    """
    start = time.perf_counter()
    result = await operation(*args, **kwargs)
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms
