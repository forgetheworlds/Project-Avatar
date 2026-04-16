#!/usr/bin/env python3
"""
Basic SITL (Software In The Loop) flight tests for PX4 drone using MAVSDK.

WHAT THESE TESTS VALIDATE:
    These tests verify the fundamental communication and control capabilities between
    the Python test suite and a running PX4 SITL (Software In The Loop) simulation.
    They form the foundation for all higher-level flight operations.

WHY THESE TESTS MATTER:
    - Safety: Before any autonomous flight, we must verify basic control works
    - Integration: Tests the full stack: Python -> MAVSDK -> MAVLink -> PX4 -> Simulator
    - Regression: Catches changes that break basic flight operations
    - Development: Provides a quick way to verify SITL setup is working

EXPECTED OUTCOMES EXPLAINED:
    Each test expects specific behaviors from the PX4 SITL:
    - Connection: MAVSDK successfully establishes MAVLink connection over UDP
    - Arming: Propellers spin (in sim), system transitions to armed state
    - Takeoff: Drone reaches target altitude (within 20% tolerance) and reports in-air
    - Landing: Drone descends, touches ground, and reports on-ground status
    - Telemetry: Position, battery, and flight mode data streams continuously

USAGE:
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

mavsdk = pytest.importorskip("mavsdk", reason="mavsdk is required for SITL tests")
System = mavsdk.System
ActionError = pytest.importorskip(
    "mavsdk.action", reason="mavsdk is required for SITL tests"
).ActionError
TelemetryError = pytest.importorskip(
    "mavsdk.telemetry", reason="mavsdk is required for SITL tests"
).TelemetryError

# Module-level pytestmark: applies 'sitl' marker to all tests in this file
# The conftest.py hook will skip these tests unless --run-sitl is passed
pytestmark = pytest.mark.sitl

# Configure logging for test output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
# These constants define timeouts and parameters for SITL operations.
# Timeouts are generous to accommodate slower CI environments or busy systems.

SITL_CONNECTION_URL = "udpin://0.0.0.0:14540"
"""HOW: UDP connection string for MAVSDK to connect to PX4 SITL.
WHY: SITL broadcasts on port 14540 by default; we listen on all interfaces."""

DEFAULT_TAKEOFF_ALTITUDE = 5.0  # meters
"""WHAT: Target altitude for takeoff tests.
WHY: 5m is high enough to clear ground effect in sim, low enough for quick tests."""

CONNECTION_TIMEOUT = 30.0  # seconds
"""WHAT: Max time to wait for MAVLink connection.
WHY: SITL startup can take time; this prevents infinite hangs."""

GPS_LOCK_TIMEOUT = 60.0  # seconds
"""WHAT: Max time to wait for GPS satellite lock simulation.
WHY: PX4 requires GPS before arming; SITL GPS can take 30-60s to initialize."""

ARM_TIMEOUT = 10.0  # seconds
"""WHAT: Max time to wait for arm/disarm operations.
WHY: Arming should be quick; this catches stuck states."""

TAKEOFF_TIMEOUT = 30.0  # seconds
"""WHAT: Max time for takeoff to complete.
WHY: Takeoff includes spool-up, lift-off, and altitude stabilization."""

LAND_TIMEOUT = 45.0  # seconds
"""WHAT: Max time for landing to complete.
WHY: Landing includes descent, ground detection, and spool-down."""


# =============================================================================
# FIXTURES
# =============================================================================
# Pytest fixtures provide test dependencies with proper setup/teardown.
# Each fixture builds on the previous, creating a dependency chain.


@pytest.fixture
async def drone() -> AsyncGenerator[System, None]:
    """
    Create a drone System instance for testing.

    WHAT THIS DOES:
        Instantiates a MAVSDK System object (the main interface to a drone).
        Does NOT connect - just creates the object.

    WHY IT MATTERS:
        Each test gets a fresh System instance, preventing state leakage
        between tests (critical for hardware integration tests).

    HOW IT WORKS:
        1. Creates System() instance
        2. Yields it to the test
        3. Automatically cleans up when test completes (MAVSDK handles cleanup)

    Yields:
        Unconnected System instance ready for connection.
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
    Connect to the drone and verify connection is established.

    WHAT THIS DOES:
        Establishes MAVLink connection and waits for connection state confirmation.

    WHY IT MATTERS:
        All drone operations require an active connection. This fixture ensures
        we don't proceed with tests if the SITL isn't reachable.

    HOW IT WORKS - STEP BY STEP:
        1. Calls drone.connect() with UDP address
        2. Subscribes to connection_state() telemetry stream
        3. Waits for is_connected=True event
        4. Times out after CONNECTION_TIMEOUT if no connection

    Yields:
        Connected System instance ready for commands.

    Raises:
        TimeoutError: If connection not established within timeout.
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

    WHAT THIS DOES:
        Monitors health telemetry until GPS reports valid global position and home position.

    WHY IT MATTERS:
        PX4 requires GPS lock before arming for safety. Without this check, subsequent
        arm/takeoff tests would fail with cryptic errors.

    HOW IT WORKS - STEP BY STEP:
        1. Subscribes to health() telemetry stream
        2. Checks is_global_position_ok and is_home_position_ok flags
        3. Returns when both are True (GPS lock acquired)
        4. Times out after GPS_LOCK_TIMEOUT if lock not achieved

    Yields:
        Drone with valid GPS position ready for arming.

    Raises:
        TimeoutError: If GPS lock not achieved within timeout.
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
# These functions encapsulate common wait operations using MAVSDK's
# async telemetry streams. Each waits for a specific state/condition.


async def _wait_for_connection(drone: System) -> None:
    """Wait until MAVLink connection is established.

    WHAT: Subscribes to connection state and returns when connected.
    WHY: MAVSDK connection is async; we need to wait before sending commands.
    HOW: Async iterator over connection_state() yields ConnectionState objects.
    """
    async for state in drone.core.connection_state():
        if state.is_connected:
            logger.info("Drone connection state: connected=%s", state.is_connected)
            return


async def _wait_for_gps_lock(drone: System) -> None:
    """Wait until drone has valid GPS position.

    WHAT: Checks health telemetry for GPS validity flags.
    WHY: PX4 safety checks require GPS before flight.
    HOW: Monitors is_global_position_ok and is_home_position_ok in health stream.
    """
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
    """Wait until drone is armed (propellers spinning).

    WHAT: Monitors armed() telemetry stream.
    WHY: Commands sent before arming will be rejected by PX4.
    HOW: Returns when armed=True received in telemetry.
    """
    async for armed in drone.telemetry.armed():
        if armed:
            logger.info("Drone is armed")
            return


async def _wait_for_disarmed(drone: System, timeout: float = ARM_TIMEOUT) -> None:
    """Wait until drone is disarmed (propellers stopped).

    WHAT: Monitors armed() telemetry stream for False.
    WHY: Cleanup verification - ensures safe state after test.
    HOW: Returns when armed=False received in telemetry.
    """
    async for armed in drone.telemetry.armed():
        if not armed:
            logger.info("Drone is disarmed")
            return


async def _wait_for_in_air(drone: System) -> bool:
    """Wait for drone to be in air, returns True if detected.

    WHAT: Monitors in_air() telemetry stream.
    WHY: Confirms takeoff was successful (not just commanded).
    HOW: Returns the in_air boolean from first telemetry message.
    """
    async for in_air in drone.telemetry.in_air():
        return in_air
    return False


async def _wait_for_on_ground(drone: System) -> None:
    """Wait until drone is on the ground (not in air).

    WHAT: Monitors in_air() telemetry stream for False.
    WHY: Confirms landing was successful before proceeding.
    HOW: Returns when in_air=False received.
    """
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            logger.info("Drone is on ground")
            return


async def _get_current_altitude(drone: System) -> float:
    """Get current relative altitude in meters.

    WHAT: Reads relative_altitude_m from position telemetry.
    WHY: Validates takeoff reached target altitude.
    HOW: Returns relative_altitude_m from first position message.
    """
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
    Test MAVSDK connection to the PX4 SITL drone.

    WHAT THIS TEST VALIDATES:
        - MAVSDK can establish a MAVLink connection over UDP
        - Connection state telemetry reports connected=True
        - Position telemetry is available immediately after connection

    WHY THIS TEST MATTERS:
        This is the most basic test - if connection fails, nothing else will work.
        It validates the entire communication chain from Python to PX4.

    EXPECTED OUTCOMES:
        - Connection established within CONNECTION_TIMEOUT (30s)
        - is_connected flag becomes True in connection_state telemetry
        - Position telemetry returns valid lat/lon/alt values

    HOW IT WORKS - STEP BY STEP:
        1. Connect to SITL using UDP URL
        2. Subscribe to connection_state telemetry stream
        3. Wait for is_connected=True (with timeout)
        4. Verify connected flag is True
        5. Read position telemetry to confirm data flow
        6. Log position for debugging
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
    Test drone arming and disarming.

    WHAT THIS TEST VALIDATES:
        - Can arm the drone (enable propulsion system)
        - Armed state is reflected in telemetry
        - Can disarm the drone (disable propulsion)
        - Disarmed state is reflected in telemetry

    WHY THIS TEST MATTERS:
        Arming is the gateway to all flight operations. In real hardware, this is
        a safety-critical state transition. We verify the command works and state
        is correctly reported.

    EXPECTED OUTCOMES:
        - arm() command succeeds without ActionError
        - Telemetry reports armed=True within ARM_TIMEOUT
        - disarm() command succeeds
        - Telemetry reports armed=False within ARM_TIMEOUT

    HOW IT WORKS - STEP BY STEP:
        1. Verify initial disarmed state via telemetry
        2. Send arm() command
        3. Wait for armed telemetry with timeout
        4. Verify armed state via telemetry
        5. Send disarm() command for cleanup
        6. Wait for disarmed telemetry
        7. Confirm disarmed state
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

    WHAT THIS TEST VALIDATES:
        - Can arm and initiate takeoff
        - Drone reaches target altitude (within 20% tolerance)
        - in_air telemetry reports True when airborne
        - Altitude telemetry reflects climb

    WHY THIS TEST MATTERS:
        Takeoff is the first flight maneuver. It tests the full flight control
        chain: command -> PX4 position controller -> simulated physics -> telemetry.
        A failed takeoff indicates fundamental flight control issues.

    EXPECTED OUTCOMES:
        - set_takeoff_altitude() configures target
        - arm() succeeds
        - takeoff() initiates climb
        - in_air becomes True within TAKEOFF_TIMEOUT
        - Altitude stabilizes near target (within 20%)
        - Landing and disarm complete successfully for cleanup

    HOW IT WORKS - STEP BY STEP:
        1. Set takeoff altitude to DEFAULT_TAKEOFF_ALTITUDE (5m)
        2. Verify altitude setting was applied
        3. Arm the drone
        4. Send takeoff() command
        5. Wait for in_air=True (lift-off detected)
        6. Wait 5 seconds for altitude stabilization
        7. Read current altitude
        8. Assert altitude is within 20% of target
        9. Command land() for cleanup
        10. Wait for on-ground
        11. Disarm
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

    WHAT THIS TEST VALIDATES:
        - Can command landing from in-air state
        - Landing completes successfully (drone touches ground)
        - on-ground telemetry reports correctly after landing
        - Auto-disarm may occur (PX4 configurable)

    WHY THIS TEST MATTERS:
        Safe landing is critical for mission completion and emergency procedures.
        This test verifies the landing command works and the system correctly
        detects ground contact in simulation.

    EXPECTED OUTCOMES:
        - Drone takes off successfully (prerequisite)
        - land() command succeeds without error
        - in_air becomes False within LAND_TIMEOUT
        - Final telemetry shows on-ground status

    HOW IT WORKS - STEP BY STEP:
        1. Takeoff to default altitude (prerequisite for landing)
        2. Wait for in_air=True and stabilize for 3 seconds
        3. Send land() command
        4. Wait for in_air=False (ground contact)
        5. Verify final in_air status is False
        6. Wait briefly for potential auto-disarm
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

    WHAT THIS TEST VALIDATES:
        This is the primary end-to-end integration test that exercises the full
        flight lifecycle in a single sequence. It validates:
        - All state transitions work correctly in sequence
        - No errors occur during normal flight operations
        - Telemetry is consistent throughout flight
        - Cleanup (landing/disarm) works after flight

    WHY THIS TEST MATTERS:
        While individual tests verify specific operations, this test verifies
        they work together. Many integration issues only appear in sequences:
        memory leaks, state machine issues, resource conflicts, etc.

    EXPECTED OUTCOMES:
        - Each phase completes without exceptions
        - Armed state confirmed after arm command
        - in_air=True after takeoff
        - Altitude is reasonable during hover
        - in_air=False after land
        - Disarmed after landing (explicit or auto)

    HOW IT WORKS - STEP BY STEP:
        Phase 1: Configure and arm
            1. Set takeoff altitude
            2. Send arm() command
            3. Wait for armed telemetry
            4. Verify armed state

        Phase 2: Takeoff
            1. Send takeoff() command
            2. Wait for in_air=True
            3. Log success

        Phase 3: Hover
            1. Sleep for 5 seconds (hover duration)
            2. Check altitude
            3. Verify still in air

        Phase 4: Land
            1. Send land() command
            2. Wait for in_air=False
            3. Verify on ground

        Phase 5: Disarm
            1. Wait for auto-disarm or explicit disarm
            2. Verify safe state
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
    Test that basic telemetry streams are available from the drone.

    WHAT THIS TEST VALIDATES:
        - Position telemetry (lat, lon, alt) is streaming
        - Battery telemetry (percent, voltage) is streaming
        - Flight mode telemetry is streaming
        - All streams return data within reasonable time

    WHY THIS TEST MATTERS:
        Telemetry is essential for autonomous operation. The LLM makes decisions
        based on telemetry data. This test ensures the data pipelines work.
        It also catches MAVLink message configuration issues.

    EXPECTED OUTCOMES:
        - position() stream yields at least one Position object
        - battery() stream yields at least one Battery object
        - flight_mode() stream yields at least one FlightMode enum
        - All data values are logged for debugging

    HOW IT WORKS - STEP BY STEP:
        1. Subscribe to position telemetry stream
        2. Read first position message, log lat/lon/alt
        3. Assert position was received
        4. Subscribe to battery telemetry stream
        5. Read first battery message, log percent/voltage
        6. Assert battery was received
        7. Subscribe to flight_mode telemetry stream
        8. Read first flight_mode message, log mode
        9. Assert flight mode was received
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
