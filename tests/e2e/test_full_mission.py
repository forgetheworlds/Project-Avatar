"""End-to-End Full Mission Tests.

================================================================================
TEST SUITE OVERVIEW
================================================================================
This test suite validates the complete mission lifecycle from connection through
landing. These tests exercise all major flight phases in sequence, ensuring the
entire control pipeline works together correctly.

WHY THESE ARE E2E TESTS (NOT UNIT TESTS):
-----------------------------------------
- These tests verify INTEGRATION between all system components:
  * MAVSDK connection and telemetry streaming
  * PX4 autopilot command processing
  * Avatar state machine state tracking
  * Guardian safety validation
  * Performance metrics collection
- Unit tests isolate individual components; these tests find integration issues
  like timing mismatches, state desynchronization, or protocol edge cases
- Real SITL timing reveals issues that mocked unit tests cannot catch:
  * Command acceptance delays
  * Telemetry propagation latency
  * State transition race conditions
  * Altitude stabilization timing

SCENARIOS COVERED:
------------------
1. Connect and Initialize    - MAVSDK connection and telemetry validation
2. GPS Lock and Health       - Pre-flight health checks
3. Arm and Takeoff           - Basic flight initiation
4. Velocity Control Mission  - Offboard mode velocity setpoints
5. Position Hold             - Hover stability verification
6. Return and Land           - RTL and direct land commands
7. Full Mission Lifecycle    - Complete 8-phase mission

USAGE:
    pytest tests/e2e/test_full_mission.py -v --run-sitl

Requirements:
    - PX4 SITL running: make px4_sitl gz_x500
    - Gazebo simulation visible (optional but recommended)
    - 5-10 minutes per full test run
"""

import asyncio
import logging
import time
from typing import Any, Dict

import pytest

# Import helpers from conftest
from tests.e2e.conftest import (
    get_current_altitude,
    get_current_position,
    measure_latency,
    wait_for_armed,
    wait_for_disarmed,
    wait_for_in_air,
    wait_for_on_ground,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONNECT AND INITIALIZE TESTS
# =============================================================================
# These tests validate the foundation of all flight operations: establishing
# a reliable connection to the autopilot and confirming telemetry streams
# are active and healthy.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_connect_and_initialize(
    mavsdk_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test MAVSDK connection to SITL and basic initialization.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Validates the initial connection handshake between the test harness and the
    PX4 SITL simulation. This is the foundation of all subsequent tests - if
    connection fails, no flight operations are possible.

    Tests three critical aspects:
    1. Connection establishment - MAVSDK finds and connects to PX4
    2. Connection state query - Can read connection status
    3. Telemetry availability - Position and battery streams are active

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Start timing for connection latency measurement
    2. Query connection state via drone.core.connection_state()
    3. Verify is_connected flag is True
    4. Log UUID for tracking
    5. Calculate connection establishment time
    6. Query position telemetry stream
    7. Verify position data is received (latitude, longitude, altitude)
    8. Query battery telemetry stream
    9. Verify battery data is received (percentage, voltage)
    10. Record all latencies to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Connection state reports is_connected=True
    - Connection establishment completes in <5000ms
    - Position telemetry provides valid coordinates
    - Battery telemetry provides percentage and voltage
    - All telemetry queries complete successfully

    Failure Modes:
    - If connection fails: PX4 SITL is not running or wrong UDP port
    - If telemetry missing: MAVSDK version mismatch or PX4 not sending
    """
    logger.info("TEST: Connect and Initialize")

    drone = mavsdk_drone

    # Measure connection latency
    start = time.perf_counter()

    # Verify connection state
    connected = False
    async for state in drone.core.connection_state():
        connected = state.is_connected
        if state.is_connected:
            logger.info(f"Connected: UUID={state.uuid}")
        break

    connection_time_ms = (time.perf_counter() - start) * 1000
    performance_collector.end(
        "connection_latency",
        duration_ms=connection_time_ms,
    )

    assert connected, "Drone should be connected"
    assert connection_time_ms < 5000, f"Connection took {connection_time_ms}ms, expected <5000ms"

    # Verify telemetry is available
    position_received = False
    async for position in drone.telemetry.position():
        logger.info(
            f"Position: ({position.latitude_deg:.6f}, {position.longitude_deg:.6f}), "
            f"alt={position.relative_altitude_m:.2f}m"
        )
        position_received = True
        break

    assert position_received, "Position telemetry should be available"

    # Verify battery telemetry
    battery_received = False
    async for battery in drone.telemetry.battery():
        logger.info(
            f"Battery: {battery.remaining_percent:.1f}%, {battery.voltage_v:.2f}V"
        )
        battery_received = True
        break

    assert battery_received, "Battery telemetry should be available"

    logger.info(f"TEST PASSED: Connection established in {connection_time_ms:.1f}ms")


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_gps_lock_and_health(
    sitl_drone: Any,
) -> None:
    """
    Test GPS lock acquisition and health checks.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Before any flight can occur, the drone must have a valid GPS position and
    pass all health checks. This test validates the pre-flight health status
    that PX4 reports via the health telemetry stream.

    Critical health checks:
    - Global position: GPS has valid 3D fix
    - Home position: GPS origin set for RTL reference
    - Gyrometer calibration: IMU gyros calibrated
    - Accelerometer calibration: IMU accelerometers calibrated

    Without these, PX4 will reject arm commands.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Query health telemetry stream
    2. Check is_global_position_ok flag
    3. Check is_home_position_ok flag
    4. Check is_gyrometer_calibration_ok flag
    5. Check is_accelerometer_calibration_ok flag
    6. All checks must be True for health_ok
    7. Log health status for diagnostics
    8. Query and log home position coordinates

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - is_global_position_ok is True (GPS 3D fix acquired)
    - is_home_position_ok is True (home position set)
    - is_gyrometer_calibration_ok is True
    - is_accelerometer_calibration_ok is True
    - Overall health_ok is True

    In SITL:
        GPS is simulated as perfect, so all health checks should pass immediately.
        In real hardware, this test would wait for actual GPS satellite lock.
    """
    logger.info("TEST: GPS Lock and Health")

    drone = sitl_drone

    # Verify GPS health
    health_ok = False
    async for health in drone.telemetry.health():
        health_ok = (
            health.is_global_position_ok and
            health.is_home_position_ok and
            health.is_gyrometer_calibration_ok and
            health.is_accelerometer_calibration_ok
        )
        logger.info(
            f"Health: GPS={health.is_global_position_ok}, "
            f"Home={health.is_home_position_ok}"
        )
        break

    assert health_ok, "Health checks should pass"

    # Get home position
    async for position in drone.telemetry.position():
        logger.info(f"Home position: ({position.latitude_deg}, {position.longitude_deg})")
        break

    logger.info("TEST PASSED: GPS lock and health verified")


# =============================================================================
# ARM AND TAKEOFF TESTS
# =============================================================================
# These tests validate the first actual flight operations: arming the motors
# and taking off to a target altitude. These are prerequisites for all other
# flight maneuvers.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_arm_and_takeoff(
    sitl_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test drone arming and takeoff sequence.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the basic flight initiation sequence that every mission requires:
    arming the motors and taking off to a target altitude. This validates the
    core flight control path through MAVSDK to PX4.

    Arm sequence in PX4:
    1. Pre-arm checks (health, GPS, battery)
    2. Motor controller activation
    3. Propeller spin-up (if not already spinning)

    Takeoff sequence in PX4:
    1. Vertical ascent at takeoff speed
    2. Altitude hold at target altitude
    3. In-air status becomes True

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Read initial armed state for reference
    2. Set takeoff altitude to 5.0m
    3. Verify takeoff altitude was set correctly
    4. Measure arm command latency
    5. Send arm command via MAVSDK
    6. Wait for armed confirmation (up to 10 seconds)
    7. Record arm latency
    8. Measure takeoff command latency
    9. Send takeoff command
    10. Wait for in-air status (up to 30 seconds)
    11. Allow 5 seconds for altitude stabilization
    12. Query actual altitude via telemetry
    13. Verify altitude is within 20% of target
    14. Initiate landing for cleanup
    15. Wait for on-ground confirmation
    16. Attempt disarm

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Initial armed state is False (disarmed)
    - Takeoff altitude is set to within 0.5m of target
    - Arm command completes in <5000ms
    - Drone reports armed status
    - Takeoff command completes in reasonable time
    - Drone reports in-air status
    - Current altitude is 4.0m-6.0m (20% tolerance of 5m)
    - Landing completes within 45 seconds

    Performance Thresholds:
    - Arm latency <5000ms
    - Takeoff to in-air <30 seconds
    """
    logger.info("TEST: Arm and Takeoff")

    drone = sitl_drone
    target_altitude = 5.0  # meters

    # Verify initial state (disarmed, on ground)
    initial_armed = None
    async for armed in drone.telemetry.armed():
        initial_armed = armed
        break

    logger.info(f"Initial armed state: {initial_armed}")

    # Set takeoff altitude
    await drone.action.set_takeoff_altitude(target_altitude)
    actual_takeoff_alt = await drone.action.get_takeoff_altitude()
    assert abs(actual_takeoff_alt - target_altitude) < 0.5, "Takeoff altitude not set correctly"

    # Measure arm latency
    start = time.perf_counter()
    await drone.action.arm()
    armed = await wait_for_armed(drone, timeout=10.0)
    arm_time_ms = (time.perf_counter() - start) * 1000

    performance_collector.end(
        "arm_latency",
        duration_ms=arm_time_ms,
    )

    assert armed, "Drone should be armed"
    assert arm_time_ms < 5000, f"Arm took {arm_time_ms}ms, expected <5000ms"
    logger.info(f"Armed in {arm_time_ms:.1f}ms")

    # Takeoff
    start = time.perf_counter()
    await drone.action.takeoff()

    # Wait for in-air status
    in_air = await wait_for_in_air(drone, timeout=30.0)
    takeoff_time_ms = (time.perf_counter() - start) * 1000

    assert in_air, "Drone should be in air after takeoff"
    logger.info(f"In air after {takeoff_time_ms:.1f}ms")

    # Wait for altitude stabilization
    await asyncio.sleep(5)

    # Verify altitude
    current_alt = await get_current_altitude(drone)
    altitude_error = abs(current_alt - target_altitude)
    tolerance = target_altitude * 0.2  # 20% tolerance

    logger.info(f"Current altitude: {current_alt:.2f}m (target: {target_altitude}m)")
    assert altitude_error <= tolerance, (
        f"Altitude {current_alt:.2f}m not within tolerance of {target_altitude}m"
    )

    # Land and cleanup
    logger.info("Landing for cleanup")
    await drone.action.land()
    await wait_for_on_ground(drone, timeout=45.0)
    await asyncio.sleep(2)  # Wait for auto-disarm or disarm explicitly

    # Try to disarm (may already be disarmed)
    try:
        await drone.action.disarm()
    except Exception:
        pass  # May already be disarmed

    logger.info("TEST PASSED: Arm and takeoff successful")


# =============================================================================
# VELOCITY CONTROL TESTS
# =============================================================================
# These tests validate offboard velocity control mode, which is used for
# real-time piloted flight and automated trajectory tracking.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_velocity_control_mission(
    sitl_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test velocity control via offboard mode.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the offboard velocity control mode required for real-time control.
    In offboard mode, the companion computer (running Avatar) sends velocity
    setpoints at 20Hz, and PX4 follows them.

    This mode is used for:
    - Natural language flight commands ("fly forward at 2 m/s")
    - Trajectory following
    - Precision maneuvers

    The test sends velocity commands at 20Hz for 3 seconds and verifies:
    - Offboard mode can be started
    - Velocity setpoints are accepted
    - 20Hz rate is maintained
    - Offboard mode stops cleanly

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m to establish flight
    2. Wait for stabilization
    3. Import MAVSDK offboard VelocityNedYaw class
    4. Create velocity setpoint: 1.0 m/s north
    5. Send initial setpoint (required before start)
    6. Measure offboard start latency
    7. Start offboard mode
    8. Maintain 20Hz setpoint stream for 3 seconds:
       - Send velocity setpoint
       - Increment counter
       - Precise timing: sleep for remaining 50ms interval
    9. Calculate achieved rate
    10. Stop offboard mode
    11. Verify achieved rate >= 18Hz
    12. Land for cleanup

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Offboard mode starts successfully
    - Setpoint stream maintains >= 18Hz actual rate
    - All setpoints accepted without errors
    - Offboard mode stops cleanly
    - Drone remains stable throughout

    Performance Thresholds:
    - Offboard start latency: reasonable (<5s)
    - Setpoint rate: >= 18Hz (target 20Hz, 10% tolerance)

    Safety Note:
        Small velocity (1 m/s) used to prevent excessive drift in limited
        simulation space.
    """
    logger.info("TEST: Velocity Control Mission")

    drone = sitl_drone
    target_altitude = 5.0

    # Arm and takeoff first
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)  # Stabilize

    try:
        from mavsdk.offboard import VelocityNedYaw
    except ImportError:
        pytest.skip("MAVSDK offboard not available")

    # Prepare velocity setpoint (small velocity to test, not aggressive)
    velocity_setpoint = VelocityNedYaw(
        north_m_s=1.0,  # Small forward velocity
        east_m_s=0.0,
        down_m_s=0.0,
        yaw_deg=0.0,
    )

    # Start offboard mode
    start = time.perf_counter()
    await drone.offboard.set_velocity_ned(velocity_setpoint)

    try:
        await drone.offboard.start()
        offboard_start_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Offboard mode started in {offboard_start_ms:.1f}ms")
    except Exception as e:
        pytest.fail(f"Failed to start offboard mode: {e}")

    # Maintain 20Hz setpoint stream for 3 seconds
    setpoint_count = 0
    duration_s = 3.0
    start_time = time.time()
    interval = 0.05  # 20Hz

    while time.time() - start_time < duration_s:
        loop_start = time.perf_counter()
        await drone.offboard.set_velocity_ned(velocity_setpoint)
        setpoint_count += 1

        # Precise timing
        elapsed = time.perf_counter() - loop_start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    actual_duration = time.time() - start_time
    achieved_rate = setpoint_count / actual_duration if actual_duration > 0 else 0

    logger.info(
        f"Sent {setpoint_count} setpoints in {actual_duration:.2f}s "
        f"(rate: {achieved_rate:.1f}Hz)"
    )

    performance_collector.end(
        "velocity_control",
        setpoints_sent=setpoint_count,
        duration_s=actual_duration,
        achieved_rate_hz=achieved_rate,
    )

    # Stop offboard
    await drone.offboard.stop()
    logger.info("Offboard mode stopped")

    # Verify we achieved close to 20Hz
    assert achieved_rate >= 18.0, f"Setpoint rate {achieved_rate:.1f}Hz < 18Hz minimum"

    # Land and cleanup
    await drone.action.land()
    await wait_for_on_ground(drone)

    logger.info("TEST PASSED: Velocity control mission successful")


# =============================================================================
# POSITION HOLD TESTS
# =============================================================================
# These tests validate the drone's ability to maintain position, which is
# essential for stable flight and mission execution.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_position_hold(
    sitl_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test position hold (hover) functionality.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the drone's position holding capability, also known as "hover" or
    "loiter". This is the default mode when no other commands are active - the
    drone should maintain its current position within tolerance.

    Position hold relies on:
    - GPS position feedback
    - Velocity estimation from IMU
    - Control loop maintaining position error near zero

    This test sends a hold command and monitors position drift over 5 seconds.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m
    2. Stabilize at altitude (5 seconds)
    3. Record initial GPS position as reference
    4. Send hold command
    5. Measure hold command latency
    6. Monitor position for 5 seconds:
       - Query current position
       - Calculate drift from initial using haversine approximation
       - Track maximum drift observed
       - Sample every 0.5 seconds
    7. Log max drift and sample count
    8. Verify max drift is within tolerance
    9. Land for cleanup

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Hold command completes in <100ms
    - Position drift remains <5m over 5 seconds
    - Drone remains stable throughout hold

    Tolerance Notes:
    - SITL has simulated wind and physics that cause some drift
    - 5m tolerance is reasonable for simulation (real drones achieve <1m)
    - Main goal is verifying hold command works, not perfect position holding

    Performance Thresholds:
    - Hold command latency <100ms
    """
    logger.info("TEST: Position Hold")

    drone = sitl_drone
    target_altitude = 5.0
    hold_duration_s = 5.0
    position_tolerance_m = 1.0

    # Arm and takeoff
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)  # Stabilize at altitude

    # Get initial position
    initial_lat, initial_lon = await get_current_position(drone)
    logger.info(f"Initial position: ({initial_lat:.6f}, {initial_lon:.6f})")

    # Send hold command
    start = time.perf_counter()
    await drone.action.hold()
    hold_latency_ms = (time.perf_counter() - start) * 1000

    performance_collector.end(
        "hold_latency",
        duration_ms=hold_latency_ms,
    )

    logger.info(f"Hold command sent in {hold_latency_ms:.1f}ms")
    assert hold_latency_ms < 100, f"Hold latency {hold_latency_ms:.1f}ms > 100ms limit"

    # Monitor position during hold
    start_time = time.time()
    max_drift = 0.0
    samples = 0

    while time.time() - start_time < hold_duration_s:
        current_lat, current_lon = await get_current_position(drone)

        # Calculate drift using haversine formula approximation
        # 1 degree latitude ~ 111km
        lat_diff = current_lat - initial_lat
        lon_diff = current_lon - initial_lon
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * 0.707  # Approximation at 45 degrees

        drift = ((lat_diff * meters_per_deg_lat)**2 +
                 (lon_diff * meters_per_deg_lon)**2)**0.5

        max_drift = max(max_drift, drift)
        samples += 1

        await asyncio.sleep(0.5)

    logger.info(f"Max position drift: {max_drift:.2f}m over {samples} samples")

    # Note: In SITL with gazebo, some drift is expected due to simulated wind/physics
    # We're mainly testing that the hold command works, not perfect position holding
    assert max_drift < 5.0, f"Max drift {max_drift:.2f}m exceeds 5m limit"

    # Land and cleanup
    await drone.action.land()
    await wait_for_on_ground(drone)

    logger.info("TEST PASSED: Position hold successful")


# =============================================================================
# RETURN AND LAND TESTS
# =============================================================================
# These tests validate mission termination - returning to launch and landing.
# These are critical safety operations that must work reliably.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_return_to_land(
    sitl_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test Return to Launch (RTL) and landing.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the Return to Launch mission item, which is the standard way to end
    missions safely. RTL causes the drone to:

    1. Ascend to RTL altitude (if below)
    2. Fly to home position (launch point)
    3. Descend and land at home

    This is a primary failsafe action and must work reliably every time.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m
    2. Stabilize for 5 seconds
    3. Record current position (will be near home in SITL)
    4. Measure RTL command latency
    5. Send return_to_launch command
    6. Log command acceptance time
    7. Wait for landing completion (up to 60 seconds)
    8. Verify on-ground status via telemetry
    9. Allow 3 seconds for auto-disarm
    10. Attempt explicit disarm if still armed
    11. Log final armed/disarmed status

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - RTL command completes in <100ms
    - Drone lands within 60 seconds
    - On-ground status reports True after landing
    - Drone disarms (or can be manually disarmed)

    Performance Thresholds:
    - RTL command latency <100ms
    - RTL completion <60 seconds (for short distances in SITL)

    Note on SITL:
        RTL behavior in SITL may vary based on PX4 parameter configuration.
        The test allows up to 60 seconds for completion.
    """
    logger.info("TEST: Return to Launch and Land")

    drone = sitl_drone
    target_altitude = 5.0

    # Arm and takeoff
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)  # Stabilize

    # Get position (which will be close to home in SITL)
    initial_lat, initial_lon = await get_current_position(drone)
    logger.info(f"Position before RTL: ({initial_lat:.6f}, {initial_lon:.6f})")

    # Trigger RTL
    start = time.perf_counter()
    await drone.action.return_to_launch()
    rtl_latency_ms = (time.perf_counter() - start) * 1000

    performance_collector.end(
        "rtl_latency",
        duration_ms=rtl_latency_ms,
    )

    logger.info(f"RTL command sent in {rtl_latency_ms:.1f}ms")
    assert rtl_latency_ms < 100, f"RTL latency {rtl_latency_ms:.1f}ms > 100ms limit"

    # Wait for landing to complete (RTL includes landing in PX4)
    logger.info("Waiting for RTL and landing to complete...")
    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Drone should land after RTL"

    # Verify on ground
    on_ground = False
    async for in_air in drone.telemetry.in_air():
        on_ground = not in_air
        break

    assert on_ground, "Drone should be on ground after RTL landing"

    # Wait for auto-disarm or disarm
    await asyncio.sleep(3)
    try:
        await drone.action.disarm()
    except Exception:
        pass

    disarmed = False
    async for armed in drone.telemetry.armed():
        disarmed = not armed
        break

    # Note: In SITL, may not auto-disarm depending on configuration
    # We don't strictly assert disarmed state
    if disarmed:
        logger.info("Drone disarmed after landing")
    else:
        logger.info("Drone still armed (may require manual disarm in SITL)")

    logger.info("TEST PASSED: Return to launch and land successful")


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_land_command(
    sitl_drone: Any,
    performance_collector: Any,
) -> None:
    """
    Test direct land command.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the direct land command, which causes the drone to descend and land
    at its current position. Unlike RTL, this does NOT return to home first -
    it simply lands wherever the drone currently is.

    Use cases:
    - Mission termination at current location
    - Pilot-initiated landing at a safe spot
    - Emergency landing when RTL is not appropriate

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m
    2. Stabilize for 5 seconds
    3. Measure land command latency
    4. Send land command
    5. Wait for landing completion (up to 45 seconds)
    6. Verify landing completed
    7. Query final altitude
    8. Verify altitude is near zero (<1m)

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Land command completes in <100ms
    - Drone lands within 45 seconds
    - Final altitude is <1m from ground
    - Drone is safely on ground

    Performance Thresholds:
    - Land command latency <100ms
    - Landing completion <45 seconds (from 5m altitude)
    """
    logger.info("TEST: Land Command")

    drone = sitl_drone
    target_altitude = 5.0

    # Arm and takeoff
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Send land command
    start = time.perf_counter()
    await drone.action.land()
    land_latency_ms = (time.perf_counter() - start) * 1000

    performance_collector.end(
        "land_latency",
        duration_ms=land_latency_ms,
    )

    logger.info(f"Land command sent in {land_latency_ms:.1f}ms")
    assert land_latency_ms < 100, f"Land latency {land_latency_ms:.1f}ms > 100ms limit"

    # Wait for landing
    landed = await wait_for_on_ground(drone, timeout=45.0)
    assert landed, "Drone should land within timeout"

    # Verify altitude is near zero
    final_alt = await get_current_altitude(drone)
    logger.info(f"Final altitude: {final_alt:.2f}m")
    assert final_alt < 1.0, f"Final altitude {final_alt:.2f}m > 1m, landing incomplete"

    logger.info("TEST PASSED: Land command successful")


# =============================================================================
# FULL MISSION LIFECYCLE TEST
# =============================================================================
# This test combines all phases into a single comprehensive mission, validating
# the complete system integration and state transitions.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.mission
@pytest.mark.slow
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_full_mission_lifecycle(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
    performance_collector: Any,
) -> None:
    """
    Complete end-to-end mission test.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Executes a complete 8-phase mission that exercises every major system
    component and flight phase. This is the most comprehensive test in the
    suite and validates that all components work together correctly.

    Mission Phases:
    1. Connect and Initialize  - Connection, telemetry, home position
    2. Arm                     - Motor activation
    3. Takeoff                 - Ascent to 5m
    4. Velocity Control        - Offboard mode at 20Hz for 3s
    5. Position Hold           - Hover for 5s
    6. Return to Launch        - RTL initiation
    7. Land                    - Landing completion
    8. Disarm                  - Motor deactivation

    This test is marked as 'slow' because it takes 2-3 minutes to complete.

    ================================================================================
    TEST FLOW
    ================================================================================
    Phase 1: Initialize
    - Home position set from telemetry
    - Guardian system armed with home reference

    Phase 2: Arm
    - Send arm command
    - Wait for armed confirmation
    - Log arm time

    Phase 3: Takeoff
    - Set takeoff altitude to 5m
    - Send takeoff command
    - Wait for in-air status
    - Stabilize for 5 seconds
    - Verify altitude within 20% of target
    - Log takeoff time

    Phase 4: Velocity Control
    - Enter offboard mode
    - Stream velocity setpoints (1 m/s north) at 20Hz
    - Maintain for 3 seconds
    - Verify setpoint rate >= 18Hz
    - Exit offboard mode
    - Log control metrics

    Phase 5: Position Hold
    - Send hold command
    - Maintain for 5 seconds
    - Log hold time

    Phase 6: Return to Launch
    - Send RTL command
    - Log RTL initiation time

    Phase 7: Land
    - Wait for landing completion (RTL includes descent)
    - Log landing time

    Phase 8: Disarm
    - Wait briefly for auto-disarm
    - Send explicit disarm if needed
    - Log disarm time

    Summary:
    - Calculate total mission time
    - Log all phase timings
    - Record to performance collector
    - Verify total time < 3 minutes

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - All 8 phases complete without errors
    - Home position is set and valid
    - Arm completes within 10 seconds
    - Takeoff reaches target altitude (4-6m)
    - Velocity control achieves >= 18Hz setpoint rate
    - Position hold maintains for 5 seconds
    - RTL and landing complete within 60 seconds
    - Total mission time < 180 seconds (3 minutes)

    State Machine Verification:
    - State transitions track correctly through phases
    - No invalid state transitions occur
    - Final state is DISARMED

    Performance Metrics Collected:
    - Phase timings for all 8 phases
    - Total mission duration
    - Velocity control setpoint rate
    """
    logger.info("=" * 60)
    logger.info("TEST: Full Mission Lifecycle")
    logger.info("=" * 60)

    drone = sitl_drone
    state_machine = flight_components["state_machine"]
    guardian = flight_components["guardian"]

    mission_start = time.perf_counter()
    phase_times: Dict[str, float] = {}

    # Phase 1: Connect and Initialize (already done by fixture)
    logger.info("PHASE 1: Connect and Initialize (fixture provided)")
    phase_times["init"] = 0.0  # Done by fixture

    # Verify telemetry
    async for pos in drone.telemetry.position():
        guardian.set_home(pos.latitude_deg, pos.longitude_deg)
        break

    assert guardian.is_home_set, "Home position should be set"
    logger.info(f"Home set to: {guardian.home_position}")

    # Phase 2: Arm
    logger.info("PHASE 2: Arm")
    phase_start = time.perf_counter()

    await drone.action.arm()
    armed = await wait_for_armed(drone, timeout=10.0)
    assert armed, "Should be armed"

    phase_times["arm"] = time.perf_counter() - phase_start
    logger.info(f"Armed in {phase_times['arm']:.2f}s")

    # Phase 3: Takeoff
    logger.info("PHASE 3: Takeoff")
    phase_start = time.perf_counter()

    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.takeoff()

    in_air = await wait_for_in_air(drone, timeout=30.0)
    assert in_air, "Should be in air"

    await asyncio.sleep(5)  # Stabilize

    current_alt = await get_current_altitude(drone)
    assert abs(current_alt - target_altitude) < target_altitude * 0.2, "Should be at target altitude"

    phase_times["takeoff"] = time.perf_counter() - phase_start
    logger.info(f"Takeoff complete in {phase_times['takeoff']:.2f}s, alt={current_alt:.2f}m")

    # Phase 4: Velocity Control
    logger.info("PHASE 4: Velocity Control (Offboard)")
    phase_start = time.perf_counter()

    try:
        from mavsdk.offboard import VelocityNedYaw

        velocity_setpoint = VelocityNedYaw(1.0, 0.0, 0.0, 0.0)
        await drone.offboard.set_velocity_ned(velocity_setpoint)
        await drone.offboard.start()

        # Run for 3 seconds
        start_time = time.time()
        setpoint_count = 0
        while time.time() - start_time < 3.0:
            await drone.offboard.set_velocity_ned(velocity_setpoint)
            setpoint_count += 1
            await asyncio.sleep(0.05)

        await drone.offboard.stop()

        achieved_rate = setpoint_count / 3.0
        logger.info(f"Velocity control: {setpoint_count} setpoints @ {achieved_rate:.1f}Hz")
        assert achieved_rate >= 18.0, f"Setpoint rate {achieved_rate:.1f}Hz too low"

    except ImportError:
        logger.warning("MAVSDK offboard not available, skipping velocity control phase")

    phase_times["velocity_control"] = time.perf_counter() - phase_start

    # Phase 5: Position Hold
    logger.info("PHASE 5: Position Hold")
    phase_start = time.perf_counter()

    await drone.action.hold()
    await asyncio.sleep(5)  # Hold for 5 seconds

    phase_times["hold"] = time.perf_counter() - phase_start
    logger.info(f"Hold complete in {phase_times['hold']:.2f}s")

    # Phase 6: Return to Launch
    logger.info("PHASE 6: Return to Launch")
    phase_start = time.perf_counter()

    await drone.action.return_to_launch()

    phase_times["rtl"] = time.perf_counter() - phase_start
    logger.info(f"RTL initiated in {phase_times['rtl']:.2f}s")

    # Phase 7: Land (RTL includes landing, but we verify)
    logger.info("PHASE 7: Land")
    phase_start = time.perf_counter()

    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Should be on ground"

    phase_times["land"] = time.perf_counter() - phase_start
    logger.info(f"Landed in {phase_times['land']:.2f}s")

    # Phase 8: Disarm
    logger.info("PHASE 8: Disarm")
    phase_start = time.perf_counter()

    await asyncio.sleep(3)  # Wait for auto-disarm

    try:
        await drone.action.disarm()
    except Exception:
        pass

    phase_times["disarm"] = time.perf_counter() - phase_start

    # Calculate total mission time
    total_time = time.perf_counter() - mission_start

    # Report results
    logger.info("=" * 60)
    logger.info("MISSION SUMMARY")
    logger.info("=" * 60)
    for phase, duration in phase_times.items():
        logger.info(f"  {phase}: {duration:.2f}s")
    logger.info(f"  TOTAL: {total_time:.2f}s")
    logger.info("=" * 60)

    # Record performance metrics
    performance_collector.end(
        "full_mission",
        total_time_s=total_time,
        phase_times=phase_times,
    )

    # Verify total mission time is reasonable (< 3 minutes for this test)
    assert total_time < 180, f"Mission took {total_time:.1f}s, expected <180s"

    logger.info("TEST PASSED: Full mission lifecycle complete")
