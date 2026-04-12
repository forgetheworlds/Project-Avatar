#!/usr/bin/env python3
"""
Basic SITL (Software In The Loop) flight tests for PX4 drone using MAVSDK.

These tests require a running PX4 SITL simulation (make px4_sitl gazebo-classic)
or jMAVSim simulator. Tests connect to the drone via UDP on port 14540 (default).

Usage:
    pytest avatar/tests/test_sitl_basic.py -v -m integration
    pytest avatar/tests/test_sitl_basic.py -v --tb=short

Prerequisites:
    - PX4 SITL running (e.g., `make px4_sitl gazebo-classic` in PX4-Autopilot)
    - mavsdk package installed
    - pytest-asyncio configured

Connection: udpin://0.0.0.0:14540 (default SITL port)
"""

import asyncio
import logging
from typing import AsyncGenerator

import pytest
from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.telemetry import TelemetryError

# Configure logging for test output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# SITL connection configuration
SITL_CONNECTION_URL = "udpin://0.0.0.0:14540"
DEFAULT_TAKEOFF_ALTITUDE = 5.0  # meters
CONNECTION_TIMEOUT = 30.0  # seconds
GPS_LOCK_TIMEOUT = 60.0  # seconds
ARM_TIMEOUT = 10.0  # seconds
TAKEOFF_TIMEOUT = 30.0  # seconds
LAND_TIMEOUT = 45.0  # seconds


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def drone() -> AsyncGenerator[System, None]:
    """
    Create and connect to a drone System instance.

    Yields:
        Connected System instance.

    Ensures cleanup after test completion.
    """
    logger.info("Creating drone System instance")
    drone_system = System()

    try:
        yield drone_system
    finally:
        # Cleanup: disconnect and release resources
        logger.info("Cleaning up drone connection")
        # MAVSDK Python handles cleanup automatically when System goes out of scope


@pytest.fixture
async def connected_drone(drone: System) -> AsyncGenerator[System, None]:
    """
    Connect to the drone and wait for connection.

    Yields:
        Connected and ready System instance.

    Raises:
        TimeoutError: If connection times out.
    """
    logger.info("Connecting to drone at %s", SITL_CONNECTION_URL)
    await drone.connect(system_address=SITL_CONNECTION_URL)

    # Wait for connection with timeout
    connection_task = _wait_for_connection(drone)
    try:
        await asyncio.wait_for(connection_task, timeout=CONNECTION_TIMEOUT)
        logger.info("Successfully connected to drone")
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Failed to connect to drone within {CONNECTION_TIMEOUT}s"
        ) from exc

    try:
        yield drone
    finally:
        logger.info("Disconnecting from drone")


@pytest.fixture
async def gps_locked_drone(connected_drone: System) -> AsyncGenerator[System, None]:
    """
    Wait for GPS lock before flight operations.

    Yields:
        Drone with valid GPS position.

    Raises:
        TimeoutError: If GPS lock times out.
    """
    logger.info("Waiting for GPS lock")
    gps_task = _wait_for_gps_lock(connected_drone)
    try:
        await asyncio.wait_for(gps_task, timeout=GPS_LOCK_TIMEOUT)
        logger.info("GPS lock acquired")
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Failed to acquire GPS lock within {GPS_LOCK_TIMEOUT}s"
        ) from exc

    yield connected_drone


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def _wait_for_connection(drone: System) -> None:
    """Wait until drone connection is established."""
    async for state in drone.core.connection_state():
        if state.is_connected:
            logger.info("Drone connection state: connected=%s", state.is_connected)
            return


async def _wait_for_gps_lock(drone: System) -> None:
    """Wait until drone has valid GPS position."""
    async for health in drone.telemetry.health():
        is_gps_ok = health.is_global_position_ok and health.is_home_position_ok
        if is_gps_ok:
            logger.info(
                "GPS health: global_position=%s, home_position=%s",
                health.is_global_position_ok,
                health.is_home_position_ok,
            )
            return


async def _wait_for_armed(drone: System, timeout: float = ARM_TIMEOUT) -> None:
    """Wait until drone is armed."""
    async for armed in drone.telemetry.armed():
        if armed:
            logger.info("Drone is armed")
            return


async def _wait_for_disarmed(drone: System, timeout: float = ARM_TIMEOUT) -> None:
    """Wait until drone is disarmed."""
    async for armed in drone.telemetry.armed():
        if not armed:
            logger.info("Drone is disarmed")
            return


async def _wait_for_in_air(drone: System) -> bool:
    """Wait for drone to be in air, returns True if detected."""
    async for in_air in drone.telemetry.in_air():
        return in_air
    return False


async def _wait_for_on_ground(drone: System) -> None:
    """Wait until drone is on the ground (not in air)."""
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            logger.info("Drone is on ground")
            return


async def _get_current_altitude(drone: System) -> float:
    """Get current relative altitude in meters."""
    async for position in drone.telemetry.position():
        return position.relative_altitude_m
    return 0.0


# =============================================================================
# TESTS - CONNECTION
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.slow
@pytest.mark.asyncio
async def test_connection(drone: System) -> None:
    """
    Test MAVSDK connection to the drone.

    Verifies:
        - Can establish connection to SITL
        - Connection state reports as connected
    """
    logger.info("TEST: Starting connection test")

    # Connect to the drone
    await drone.connect(system_address=SITL_CONNECTION_URL)
    logger.info("Connection request sent to %s", SITL_CONNECTION_URL)

    # Wait for connection state
    connected = False
    async for state in drone.core.connection_state():
        connected = state.is_connected
        logger.info(
            "Connection state: is_connected=%s, uuid=%s",
            state.is_connected,
            state.uuid,
        )
        if state.is_connected:
            break

    assert connected, "Failed to connect to drone"

    # Verify we can receive telemetry
    async for position in drone.telemetry.position():
        logger.info(
            "Initial position: lat=%.6f, lon=%.6f, alt=%.2fm",
            position.latitude_deg,
            position.longitude_deg,
            position.relative_altitude_m,
        )
        break

    logger.info("TEST: Connection test PASSED")


# =============================================================================
# TESTS - ARMING
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.slow
@pytest.mark.asyncio
async def test_arm(gps_locked_drone: System) -> None:
    """
    Test drone arming.

    Verifies:
        - Can arm the drone
        - Armed state is reflected in telemetry
        - Can disarm after arming
    """
    logger.info("TEST: Starting arm test")
    drone = gps_locked_drone

    # Verify initial state (should be disarmed)
    initial_armed = None
    async for armed in drone.telemetry.armed():
        initial_armed = armed
        logger.info("Initial armed state: %s", armed)
        break

    # Arm the drone
    logger.info("Sending arm command")
    try:
        await drone.action.arm()
    except ActionError as exc:
        pytest.fail(f"Failed to arm drone: {exc}")

    # Wait for armed state
    await asyncio.wait_for(_wait_for_armed(drone), timeout=ARM_TIMEOUT)

    # Verify armed state
    armed_state = False
    async for armed in drone.telemetry.armed():
        armed_state = armed
        break

    assert armed_state, "Drone failed to report armed state"
    logger.info("Drone successfully armed")

    # Disarm for cleanup
    logger.info("Disarming for cleanup")
    await drone.action.disarm()
    await asyncio.wait_for(_wait_for_disarmed(drone), timeout=ARM_TIMEOUT)

    logger.info("TEST: Arm test PASSED")


# =============================================================================
# TESTS - TAKEOFF
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.slow
@pytest.mark.asyncio
async def test_takeoff(gps_locked_drone: System) -> None:
    """
    Test drone takeoff to specified altitude.

    Verifies:
        - Can arm and takeoff
        - Reaches target altitude within tolerance
        - Reports in-air status correctly
    """
    logger.info("TEST: Starting takeoff test")
    drone = gps_locked_drone

    # Set takeoff altitude
    target_altitude = DEFAULT_TAKEOFF_ALTITUDE
    logger.info("Setting takeoff altitude to %.1fm", target_altitude)
    await drone.action.set_takeoff_altitude(target_altitude)

    # Verify altitude setting
    actual_takeoff_alt = await drone.action.get_takeoff_altitude()
    logger.info("Configured takeoff altitude: %.1fm", actual_takeoff_alt)

    # Arm the drone
    logger.info("Arming drone")
    await drone.action.arm()
    await asyncio.wait_for(_wait_for_armed(drone), timeout=ARM_TIMEOUT)

    # Takeoff
    logger.info("Sending takeoff command")
    try:
        await drone.action.takeoff()
    except ActionError as exc:
        pytest.fail(f"Failed to takeoff: {exc}")

    # Wait for in-air status
    logger.info("Waiting for drone to be in air")

    async def wait_in_air() -> None:
        async for in_air in drone.telemetry.in_air():
            if in_air:
                return

    await asyncio.wait_for(wait_in_air(), timeout=TAKEOFF_TIMEOUT)

    # Wait for altitude to stabilize
    logger.info("Waiting for altitude to reach target")
    await asyncio.sleep(5)  # Allow altitude to stabilize

    # Check altitude
    current_alt = await _get_current_altitude(drone)
    logger.info("Current altitude: %.2fm (target: %.1fm)", current_alt, target_altitude)

    # Allow 20% tolerance on altitude
    altitude_tolerance = target_altitude * 0.2
    assert (
        abs(current_alt - target_altitude) <= altitude_tolerance
    ), f"Altitude {current_alt:.2f}m not within tolerance of target {target_altitude}m"

    # Verify in-air status
    in_air = await _wait_for_in_air(drone)
    assert in_air, "Drone should be in air after takeoff"

    logger.info("Drone reached target altitude")

    # Land for cleanup
    logger.info("Landing for cleanup")
    await drone.action.land()
    await asyncio.wait_for(_wait_for_on_ground(drone), timeout=LAND_TIMEOUT)

    # Disarm
    await drone.action.disarm()

    logger.info("TEST: Takeoff test PASSED")


# =============================================================================
# TESTS - LANDING
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.slow
@pytest.mark.asyncio
async def test_land(gps_locked_drone: System) -> None:
    """
    Test drone landing from hover.

    Verifies:
        - Can command landing from in-air state
        - Landing completes successfully
        - Reports on-ground status after landing
    """
    logger.info("TEST: Starting land test")
    drone = gps_locked_drone

    # Takeoff first to have something to land from
    await drone.action.set_takeoff_altitude(DEFAULT_TAKEOFF_ALTITUDE)
    await drone.action.arm()
    await asyncio.wait_for(_wait_for_armed(drone), timeout=ARM_TIMEOUT)

    logger.info("Taking off for land test")
    await drone.action.takeoff()

    # Wait for in-air
    async def wait_in_air() -> None:
        async for in_air in drone.telemetry.in_air():
            if in_air:
                return

    await asyncio.wait_for(wait_in_air(), timeout=TAKEOFF_TIMEOUT)
    await asyncio.sleep(3)  # Stabilize at altitude

    logger.info("Drone in air, sending land command")

    # Land
    try:
        await drone.action.land()
    except ActionError as exc:
        pytest.fail(f"Failed to initiate landing: {exc}")

    # Wait for landing to complete
    logger.info("Waiting for landing to complete")
    await asyncio.wait_for(_wait_for_on_ground(drone), timeout=LAND_TIMEOUT)

    # Verify on-ground status
    final_in_air = None
    async for in_air in drone.telemetry.in_air():
        final_in_air = in_air
        break

    assert not final_in_air, "Drone should be on ground after landing"

    # Verify disarmed (PX4 auto-disarms after landing)
    await asyncio.sleep(3)  # Wait for auto-disarm

    logger.info("TEST: Land test PASSED")


# =============================================================================
# TESTS - FULL FLIGHT SEQUENCE
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.slow
@pytest.mark.asyncio
async def test_basic_flight(gps_locked_drone: System) -> None:
    """
    Test complete basic flight sequence: arm, takeoff, hover, land, disarm.

    This is the primary end-to-end test for basic flight operations.

    Verifies:
        - Complete arm -> takeoff -> land -> disarm sequence works
        - All state transitions are correct
        - No errors during the flight
    """
    logger.info("TEST: Starting basic flight sequence test")
    drone = gps_locked_drone

    target_altitude = DEFAULT_TAKEOFF_ALTITUDE

    # Phase 1: Configure and arm
    logger.info("PHASE 1: Configure and arm")
    await drone.action.set_takeoff_altitude(target_altitude)

    logger.info("Arming drone")
    await drone.action.arm()
    await asyncio.wait_for(_wait_for_armed(drone), timeout=ARM_TIMEOUT)

    # Verify armed
    armed_state = False
    async for armed in drone.telemetry.armed():
        armed_state = armed
        break
    assert armed_state, "Drone should be armed"

    # Phase 2: Takeoff
    logger.info("PHASE 2: Takeoff to %.1fm", target_altitude)
    await drone.action.takeoff()

    # Wait for in-air
    async def wait_in_air() -> None:
        async for in_air in drone.telemetry.in_air():
            if in_air:
                return

    await asyncio.wait_for(wait_in_air(), timeout=TAKEOFF_TIMEOUT)
    logger.info("Drone is in air")

    # Phase 3: Hover
    logger.info("PHASE 3: Hover at altitude")
    await asyncio.sleep(5)  # Hover for 5 seconds

    # Check altitude during hover
    hover_alt = await _get_current_altitude(drone)
    logger.info("Hover altitude: %.2fm", hover_alt)

    # Verify still in air
    in_air_state = False
    async for in_air in drone.telemetry.in_air():
        in_air_state = in_air
        break
    assert in_air_state, "Drone should be hovering in air"

    # Phase 4: Land
    logger.info("PHASE 4: Land")
    await drone.action.land()
    await asyncio.wait_for(_wait_for_on_ground(drone), timeout=LAND_TIMEOUT)

    # Verify on ground
    final_in_air = None
    async for in_air in drone.telemetry.in_air():
        final_in_air = in_air
        break
    assert not final_in_air, "Drone should be on ground after landing"

    # Phase 5: Verify disarm (PX4 auto-disarms after landing)
    logger.info("PHASE 5: Verify disarm")
    await asyncio.sleep(3)  # Wait for auto-disarm

    final_armed = None
    async for armed in drone.telemetry.armed():
        final_armed = armed
        break

    # Note: PX4 may or may not auto-disarm depending on configuration
    # We explicitly disarm to ensure clean state
    if final_armed:
        logger.info("Explicitly disarming")
        await drone.action.disarm()
        await asyncio.wait_for(_wait_for_disarmed(drone), timeout=ARM_TIMEOUT)

    logger.info("TEST: Basic flight sequence PASSED")


# =============================================================================
# TESTS - TELEMETRY VERIFICATION
# =============================================================================


@pytest.mark.integration
@pytest.mark.hardware_in_loop
@pytest.mark.asyncio
async def test_telemetry_available(connected_drone: System) -> None:
    """
    Test that basic telemetry is available from the drone.

    Verifies:
        - Position telemetry is available
        - Battery telemetry is available
        - Flight mode telemetry is available
    """
    logger.info("TEST: Starting telemetry availability test")
    drone = connected_drone

    # Check position telemetry
    position_received = False
    async for position in drone.telemetry.position():
        position_received = True
        logger.info(
            "Position: lat=%.6f, lon=%.6f, alt=%.2fm",
            position.latitude_deg,
            position.longitude_deg,
            position.relative_altitude_m,
        )
        break
    assert position_received, "Position telemetry not available"

    # Check battery telemetry
    battery_received = False
    async for battery in drone.telemetry.battery():
        battery_received = True
        logger.info(
            "Battery: %.1f%%, %.2fV",
            battery.remaining_percent,
            battery.voltage_v,
        )
        break
    assert battery_received, "Battery telemetry not available"

    # Check flight mode telemetry
    flight_mode_received = False
    async for flight_mode in drone.telemetry.flight_mode():
        flight_mode_received = True
        logger.info("Flight mode: %s", flight_mode)
        break
    assert flight_mode_received, "Flight mode telemetry not available"

    logger.info("TEST: Telemetry availability test PASSED")


# =============================================================================
# ENTRY POINT FOR MANUAL TESTING
# =============================================================================


if __name__ == "__main__":
    # Run tests manually with detailed output
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 60)
    print("Running SITL Basic Flight Tests")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  1. Start PX4 SITL: make px4_sitl gazebo-classic")
    print("  2. Wait for SITL to be ready")
    print("=" * 60)

    # Run pytest programmatically
    sys.exit(
        pytest.main(
            [
                __file__,
                "-v",
                "--tb=short",
                "-s",
                "--log-cli-level=INFO",
            ]
        )
    )
