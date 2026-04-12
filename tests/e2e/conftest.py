"""E2E Test Configuration and Fixtures.

Provides fixtures for SITL integration testing including:
- SITL session lifecycle management
- Connected drone fixtures
- Guardian and state machine fixtures
- Performance measurement utilities

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

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
# PYTEST CONFIGURATION
# =============================================================================


def pytest_addoption(parser: Any) -> None:
    """Add custom command-line options for E2E tests."""
    parser.addoption(
        "--run-sitl",
        action="store_true",
        default=False,
        help="Run tests against real SITL (requires PX4 SITL running)",
    )
    parser.addoption(
        "--mock-mode",
        action="store_true",
        default=False,
        help="Use mocks when SITL is not available (for CI without SITL)",
    )
    parser.addoption(
        "--sitl-timeout",
        action="store",
        default=300,
        type=int,
        help="Global timeout for SITL operations in seconds",
    )


# =============================================================================
# TEST MARKERS
# =============================================================================


def pytest_configure(config: Any) -> None:
    """Configure custom markers."""
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


@dataclass
class PerformanceMetrics:
    """Performance measurement results."""
    operation: str
    duration_ms: float
    timestamp: float
    metadata: Dict[str, Any]


class PerformanceCollector:
    """Collect and analyze performance metrics during tests."""

    def __init__(self) -> None:
        self._metrics: List[PerformanceMetrics] = []
        self._start_times: Dict[str, float] = {}

    def start(self, operation: str) -> None:
        """Start timing an operation."""
        self._start_times[operation] = time.perf_counter()

    def end(self, operation: str, **metadata: Any) -> PerformanceMetrics:
        """End timing an operation and record metrics."""
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
        """Get collected metrics."""
        if operation:
            return [m for m in self._metrics if m.operation == operation]
        return self._metrics.copy()

    def get_average(self, operation: str) -> float:
        """Get average duration for an operation."""
        metrics = self.get_metrics(operation)
        if not metrics:
            return 0.0
        return sum(m.duration_ms for m in metrics) / len(metrics)

    def get_max(self, operation: str) -> float:
        """Get maximum duration for an operation."""
        metrics = self.get_metrics(operation)
        if not metrics:
            return 0.0
        return max(m.duration_ms for m in metrics)

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
        self._start_times.clear()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def sitl_config(request: Any) -> Dict[str, Any]:
    """Session-wide SITL configuration."""
    return {
        "run_sitl": request.config.getoption("--run-sitl"),
        "mock_mode": request.config.getoption("--mock-mode"),
        "timeout": request.config.getoption("--sitl-timeout"),
        "connection_url": SITL_CONNECTION_URL,
    }


@pytest.fixture(scope="session")
def performance_collector() -> PerformanceCollector:
    """Session-wide performance metrics collector."""
    return PerformanceCollector()


@pytest.fixture
async def mavsdk_drone(
    sitl_config: Dict[str, Any]
) -> AsyncGenerator[Any, None]:
    """
    Create a real MAVSDK drone connection for E2E tests.

    Yields:
        MAVSDK System instance connected to SITL.

    Skips:
        If --run-sitl is not specified.
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
    """
    Connected SITL drone with GPS lock and health checks.

    Yields:
        MAVSDK System instance ready for flight operations.
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
    """
    Initialize and provide all flight control components.

    Returns:
        Dictionary with initialized components:
        - guardian: GuardianProcess instance
        - state_machine: FlightStateMachine instance
        - escalation_matrix: EscalationMatrix instance
        - telemetry_cache: TelemetryCache instance
        - connection_manager: ConnectionManager instance
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
    """
    Flight tools instance configured for E2E testing.

    Yields:
        FlightTools instance ready for flight commands.
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
    """
    AsyncGuardian instance for 20Hz safety monitoring.

    Yields:
        AsyncGuardian instance ready for monitoring.
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
    """
    Telemetry cache with live SITL data provider.

    Yields:
        TelemetryCache instance with active background refresh.
    """
    cache = flight_components["telemetry_cache"]

    async def fetch_telemetry() -> Any:
        """Fetch telemetry from SITL."""
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


async def wait_for_armed(drone: Any, timeout: float = ARM_TIMEOUT) -> bool:
    """Wait until drone is armed."""
    start_time = time.time()
    async for armed in drone.telemetry.armed():
        if armed:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_disarmed(drone: Any, timeout: float = ARM_TIMEOUT) -> bool:
    """Wait until drone is disarmed."""
    start_time = time.time()
    async for armed in drone.telemetry.armed():
        if not armed:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_in_air(drone: Any, timeout: float = TAKEOFF_TIMEOUT) -> bool:
    """Wait until drone is in the air."""
    start_time = time.time()
    async for in_air in drone.telemetry.in_air():
        if in_air:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def wait_for_on_ground(drone: Any, timeout: float = LAND_TIMEOUT) -> bool:
    """Wait until drone is on the ground."""
    start_time = time.time()
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            return True
        if time.time() - start_time > timeout:
            return False
        await asyncio.sleep(0.1)
    return False


async def get_current_altitude(drone: Any) -> float:
    """Get current relative altitude."""
    async for position in drone.telemetry.position():
        return position.relative_altitude_m
    return 0.0


async def get_current_position(drone: Any) -> Tuple[float, float]:
    """Get current latitude and longitude."""
    async for pos in drone.telemetry.position():
        return (pos.latitude_deg, pos.longitude_deg)
    return (0.0, 0.0)


async def measure_latency(
    operation: callable,
    *args: Any,
    **kwargs: Any
) -> Tuple[Any, float]:
    """Measure latency of an operation."""
    start = time.perf_counter()
    result = await operation(*args, **kwargs)
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms
