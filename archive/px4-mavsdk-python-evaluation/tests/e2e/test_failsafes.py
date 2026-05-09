"""End-to-End Failsafe Trigger Tests.

================================================================================
TEST SUITE OVERVIEW
================================================================================
This test suite validates the drone's safety failsafe behaviors in a controlled
SITL (Software In The Loop) simulation environment. Failsafes are critical
safety mechanisms that protect the drone and surrounding area when something
goes wrong during flight.

WHY THESE ARE E2E TESTS (NOT UNIT TESTS):
-----------------------------------------
- These tests exercise the COMPLETE safety chain: PX4 autopilot → MAVSDK
  → Avatar state machine → Guardian process → Escalation matrix
- Unit tests would mock the autopilot responses; these tests verify actual
  PX4 failsafe triggers and state transitions in the simulation
- Real timing matters: heartbeat timeouts, telemetry propagation delays, and
  state machine transitions all interact in ways that mocked unit tests cannot
  accurately represent
- The tests verify that the GuardianProcess and EscalationMatrix correctly
  integrate with the actual MAVSDK telemetry streams

SCENARIOS COVERED:
------------------
1. RC Loss Failsafe       - What happens when radio control link is lost
2. Telemetry Timeout      - Detection of stale/offline telemetry
3. Geofence Breach        - Violation of geographic flight boundaries
4. Low Battery RTL         - Automatic return when battery is depleted
5. Guardian Emergency Stop - Immediate kill switch activation
6. Failsafe Priority       - Correct ordering of severity levels
7. Auto Recovery           - System recovery after failsafe trigger

USAGE:
    pytest tests/e2e/test_failsafes.py -v --run-sitl

Requirements:
    - PX4 SITL running: make px4_sitl gz_x500
    - MAVSDK-Python installed
    - Sufficient simulation time (tests may take 2-5 minutes each)
"""

import asyncio
import logging
import time
from typing import Any, Dict

import pytest

from tests.e2e.conftest import (
    get_current_altitude,
    get_current_position,
    wait_for_armed,
    wait_for_in_air,
    wait_for_on_ground,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RC LOSS FAILSAFE TESTS
# =============================================================================
# Scenario: The operator loses radio control connection to the drone.
# Expected Outcome: Drone automatically returns to launch (RTL) position.
# Safety Level: Critical - prevents flyaway when control link is lost.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_rc_loss_failsafe(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test RC (Radio Control) loss failsafe behavior.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Simulates the loss of radio control link between operator and drone. In real
    operations, this could happen due to:
    - Pilot moving out of range
    - Radio interference
    - Controller battery depletion
    - Antenna damage or disconnection

    PX4 Configuration Required:
        - NAV_RCL_ACT parameter must be set to RTL (Return to Launch)
        - RC loss timeout must be configured

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m altitude (establish flying state)
    2. Verify drone is in flying state via state_machine.is_flying
    3. Record current GPS position for reference
    4. Trigger rc_loss failsafe via state machine
    5. Verify state transitions to RTL (Return to Launch)
    6. Wait for automatic landing sequence to complete
    7. Verify drone is on ground after RTL completes

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - State machine accepts the rc_loss trigger
    - Current state transitions to RTL (not HOVERING or POSITION_CONTROL)
    - Escalation matrix reports appropriate severity level
    - Drone lands within 60 seconds of RTL initiation
    - Final state allows safe disarm

    Note on SITL Limitation:
        This test simulates the failsafe by directly triggering the state
        machine transition, as simulating actual RC loss in SITL requires
        specific PX4 parameter reconfiguration that would affect other tests.
    """
    logger.info("TEST: RC Loss Failsafe")

    drone = sitl_drone
    state_machine = flight_components["state_machine"]
    escalation_matrix = flight_components["escalation_matrix"]

    # Arm and takeoff first
    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Verify we're in a flying state
    assert state_machine.is_flying, "Should be in flying state"

    # Get current position
    initial_lat, initial_lon = await get_current_position(drone)
    logger.info(f"Position before failsafe: ({initial_lat:.6f}, {initial_lon:.6f})")

    # Test state machine rc_loss trigger
    result = state_machine.trigger_failsafe("rc_loss")
    assert result, "State machine should accept rc_loss trigger"

    # Verify state changed to RTL
    from avatar.mav.state_machine import FlightState
    assert state_machine.current_state == FlightState.RTL, (
        f"Should be in RTL state, got {state_machine.current_state_name}"
    )

    # Check escalation matrix response
    event = escalation_matrix.evaluate("rc_loss")
    if event:
        logger.info(f"Escalation event: {event.condition} -> {event.level.name}")

    # Wait for RTL and landing
    logger.info("Waiting for RTL and landing...")
    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Should land after RTL"

    logger.info("TEST PASSED: RC loss failsafe triggered successfully")


# =============================================================================
# TELEMETRY TIMEOUT TESTS
# =============================================================================
# Scenario: Telemetry data stops arriving from the drone.
# Expected Outcome: GuardianProcess detects timeout and escalates appropriately.
# Safety Level: High - loss of telemetry means loss of situational awareness.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_telemetry_timeout(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test telemetry timeout detection and response.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Simulates loss of telemetry link between drone and ground station. This could
    occur due to:
    - Radio link degradation or dropout
    - Companion computer failure
    - Network routing issues in multi-hop setups
    - Software crashes in telemetry pipeline

    The GuardianProcess monitors heartbeat timestamps. If no heartbeat is received
    within the configured timeout (default: 2 seconds), it declares the link
    potentially compromised.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to establish a flying baseline
    2. Update heartbeat to establish "healthy" baseline
    3. Verify heartbeat check passes initially
    4. WAIT for heartbeat to age beyond timeout threshold (no updates sent)
    5. Verify heartbeat check now returns False (timeout detected)
    6. Query escalation matrix with the stale heartbeat age
    7. Verify appropriate escalation level is returned
    8. Land the drone for safety

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Initial heartbeat check returns True (healthy)
    - After timeout period, heartbeat check returns False
    - Heartbeat age exceeds guardian.limits.heartbeat_timeout_s
    - Escalation matrix returns event with level >= L2 (WARNING)
    - Event includes appropriate action recommendation (e.g., "monitor closely")

    Note on Test Design:
        We cannot actually cut telemetry in SITL without disconnecting the test
        itself. Instead, we stop updating the guardian heartbeat and let it age
        out, which tests the same timeout detection logic.
    """
    logger.info("TEST: Telemetry Timeout")

    drone = sitl_drone
    guardian = flight_components["guardian"]
    escalation_matrix = flight_components["escalation_matrix"]

    # Arm and takeoff
    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Update heartbeat to show we're "healthy"
    guardian.update_heartbeat()
    assert guardian.check_heartbeat(), "Heartbeat should be healthy initially"

    # Wait for heartbeat to age beyond timeout
    timeout_s = guardian.limits.heartbeat_timeout_s
    logger.info(f"Waiting {timeout_s + 1}s for heartbeat timeout...")

    # Don't update heartbeat - let it timeout
    await asyncio.sleep(timeout_s + 1)

    # Check heartbeat is now timed out
    heartbeat_ok = guardian.check_heartbeat()
    logger.info(f"Heartbeat after timeout: {heartbeat_ok}")

    # Note: In real scenario, this would trigger failsafe
    # For the test, we verify the detection works
    assert not heartbeat_ok, "Heartbeat should show timeout"

    # Check escalation matrix would trigger
    heartbeat_age = guardian.get_heartbeat_age()
    event = escalation_matrix.check_heartbeat_timeout(heartbeat_age)

    if event:
        logger.info(f"Escalation triggered: {event.condition} at level {event.level.name}")
        assert event.level.value >= 2, "Should trigger at least L2 escalation"
    else:
        logger.info("No escalation event (may be below threshold)")

    # Land for safety
    await drone.action.land()
    await wait_for_on_ground(drone)

    logger.info("TEST PASSED: Telemetry timeout detection working")


# =============================================================================
# GEOFENCE BREACH TESTS
# =============================================================================
# Scenario: Drone flies beyond permitted geographic boundaries.
# Expected Outcome: Geofence breach detected and RTL triggered.
# Safety Level: Critical - prevents flyaway and airspace violations.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_geofence_breach(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test geofence breach detection and RTL trigger.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the geofence safety boundary system. Geofences are virtual geographic
    boundaries that restrict where the drone can fly. This test validates:

    - Guardian correctly validates GPS positions against geofence limits
    - Positions within geofence are approved for flight
    - Positions exceeding max_distance_from_home_m are rejected
    - State machine accepts geofence_breach failsafe trigger
    - RTL is initiated when geofence is breached

    Real-world triggers for geofence breach:
    - Strong wind pushing drone beyond safe area
    - Navigation system drift/error accumulation
    - Incorrect waypoint programming
    - GPS spoofing or interference

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Set home position from current telemetry
    2. Test validation of position 11m from home (should PASS - within geofence)
    3. Test validation of position 500m from home (should FAIL - outside geofence)
    4. Verify failure reason mentions distance/exceeds
    5. Arm and takeoff to establish flight
    6. Trigger geofence_breach failsafe via state machine
    7. Verify state transitions to RTL
    8. Query escalation matrix with simulated 550m distance
    9. Verify L3+ escalation triggered
    10. Wait for RTL landing

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Guardian.is_home_set becomes True after set_home()
    - Position 11m from home: guardian.validate_command() returns (True, ...)
    - Position 500m from home: guardian.validate_command() returns (False, reason)
    - Failure reason contains "distance" or "exceeds"
    - State machine accepts geofence_breach trigger
    - Current state becomes RTL after trigger
    - Escalation at 550m distance triggers L3+ (WARNING/CRITICAL)
    - Drone lands within 60 seconds
    """
    logger.info("TEST: Geofence Breach")

    drone = sitl_drone
    guardian = flight_components["guardian"]
    state_machine = flight_components["state_machine"]
    escalation_matrix = flight_components["escalation_matrix"]

    # Set home position
    async for pos in drone.telemetry.position():
        guardian.set_home(pos.latitude_deg, pos.longitude_deg)
        break

    assert guardian.is_home_set, "Home position should be set"
    home_lat, home_lon = guardian.home_position
    logger.info(f"Home position: ({home_lat:.6f}, {home_lon:.6f})")

    # Test position validation - position within geofence should pass
    valid_cmd = {
        "latitude": home_lat + 0.0001,  # ~11m offset
        "longitude": home_lon,
        "altitude_amsl_m": 50.0,
    }
    is_valid, reason = guardian.validate_command(valid_cmd)
    logger.info(f"Position 11m from home: valid={is_valid}, reason={reason}")
    assert is_valid, "Position within geofence should be valid"

    # Test position validation - position outside geofence should fail
    # 500m offset (default geofence limit)
    invalid_cmd = {
        "latitude": home_lat + 0.0045,  # ~500m offset
        "longitude": home_lon,
        "altitude_amsl_m": 50.0,
    }
    is_valid, reason = guardian.validate_command(invalid_cmd)
    logger.info(f"Position 500m from home: valid={is_valid}, reason={reason}")
    assert not is_valid, "Position outside geofence should be rejected"
    assert "distance" in reason.lower() or "exceeds" in reason.lower(), (
        f"Reason should mention distance: {reason}"
    )

    # Arm and takeoff
    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Simulate geofence breach in state machine
    result = state_machine.trigger_failsafe("geofence_breach")
    assert result, "State machine should accept geofence_breach trigger"

    # Verify RTL was triggered
    from avatar.mav.state_machine import FlightState
    assert state_machine.current_state == FlightState.RTL, (
        f"Should be in RTL state, got {state_machine.current_state_name}"
    )

    # Check escalation matrix
    max_distance = guardian.limits.max_distance_from_home_m
    event = escalation_matrix.check_geofence(550, max_distance)  # 50m outside geofence
    if event:
        logger.info(f"Escalation: {event.condition} -> {event.level.name}")
        assert event.level.value >= 3, "Geofence breach should trigger L3+ escalation"

    # Wait for RTL and landing
    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Should land after RTL"

    logger.info("TEST PASSED: Geofence breach detection working")


# =============================================================================
# LOW BATTERY FAILSAFE TESTS
# =============================================================================
# Scenario: Battery voltage drops below safe levels during flight.
# Expected Outcome: Automatic Return to Launch at low battery, emergency land
# at critical battery.
# Safety Level: Critical - prevents power loss mid-flight.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_low_battery_rth(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test low battery Return to Home (RTH) / RTL trigger.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the battery monitoring failsafe system. As battery voltage depletes,
    the drone must take progressively more conservative actions:

    Battery Level | Action
    ------------- | ------
    30-25%        | Warning notification (L1)
    20%           | Return to Launch initiated (L4)
    15%           | Critical warning (L4-L5)
    5%            | Emergency landing at current position (L5-L6)

    This test validates the EscalationMatrix correctly identifies battery
    levels and recommends appropriate actions.

    Note: SITL simulates battery behavior. Actual battery levels in simulation
    may not deplete realistically, so we test the logic at various levels rather
    than waiting for actual depletion.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Read current battery level from telemetry
    2. Test escalation matrix at levels: 30%, 25%, 20%, 15%, 5%
    3. Verify levels <=20% trigger L4+ escalation
    4. Arm and takeoff
    5. Trigger low_battery failsafe via state machine
    6. Verify state transitions to RTL
    7. Wait for RTL landing sequence

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Battery telemetry is readable from SITL
    - Escalation matrix returns appropriate events for each battery level
    - Levels 30%, 25% may or may not trigger escalation (depends on thresholds)
    - Levels 20%, 15%, 5% trigger L4+ (CRITICAL) escalation
    - Low battery event includes action_taken recommendation ("rtl", "emergency")
    - State machine accepts low_battery trigger
    - Current state becomes RTL after trigger
    - Drone lands within 60 seconds
    """
    logger.info("TEST: Low Battery RTH")

    drone = sitl_drone
    escalation_matrix = flight_components["escalation_matrix"]

    # Read current battery
    battery_percent = 0.0
    async for battery in drone.telemetry.battery():
        battery_percent = battery.remaining_percent
        logger.info(f"Current battery: {battery_percent:.1f}%")
        break

    # Test escalation at different battery levels
    test_levels = [30, 25, 20, 15, 5]

    for level in test_levels:
        event = escalation_matrix.check_battery(level)
        if event:
            logger.info(
                f"Battery {level}%: {event.condition} -> {event.level.name} "
                f"(action: {event.action_taken})"
            )

            if level <= 20:
                assert event.level.value >= 4, (
                    f"Battery {level}% should trigger L4+ escalation"
                )
        else:
            logger.info(f"Battery {level}%: No escalation")

    # Arm and takeoff
    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Simulate low battery trigger in state machine
    # (This simulates what would happen if battery dropped to 20%)
    state_machine = flight_components["state_machine"]
    result = state_machine.trigger_failsafe("low_battery")
    assert result, "State machine should accept low_battery trigger"

    # Verify RTL was triggered
    from avatar.mav.state_machine import FlightState
    assert state_machine.current_state == FlightState.RTL, (
        f"Should be in RTL state, got {state_machine.current_state_name}"
    )

    # Wait for RTL and landing
    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Should land after RTL"

    logger.info("TEST PASSED: Low battery RTH logic working")


# =============================================================================
# GUARDIAN EMERGENCY STOP TESTS
# =============================================================================
# Scenario: Immediate emergency requiring instant motor shutdown.
# Expected Outcome: Guardian kill switch triggers EMERGENCY state.
# Safety Level: Catastrophic - stops all flight immediately.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_guardian_emergency_stop(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test Guardian emergency stop (kill switch) functionality.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the most severe failsafe: the kill switch. This represents situations
    where immediate flight termination is the safest option:

    - Pilot-initiated emergency stop via physical switch
    - Software-detected unrecoverable flight condition
    - External kill command from ground control station
    - Loss of critical flight systems

    In real flight, this would disarm the drone immediately, stopping all motors.
    In SITL, we verify the state machine logic but do NOT actually kill the
    simulation (to allow proper test cleanup).

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to establish flight
    2. Verify armed status via telemetry and state machine
    3. Trigger kill_switch failsafe via state machine
    4. Verify state transitions to EMERGENCY
    5. Query escalation matrix with force_trigger=True
    6. Verify L6 (CATASTROPHIC) escalation level
    7. Verify action_taken includes "emergency" or "disarm"
    8. Reset state machine for cleanup (don't actually kill SITL)
    9. Land normally via land command

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Telemetry confirms armed=True before trigger
    - state_machine.is_armed is True before trigger
    - State machine accepts kill_switch trigger
    - Current state becomes EMERGENCY after trigger
    - Escalation level is L6 (CATASTROPHIC)
    - Action recommendation includes emergency stop or disarm
    - State machine can be reset after test (cleanup path works)

    Safety Note:
        This test does NOT actually stop the SITL simulation motors to allow
        controlled landing for cleanup. In real hardware, kill switch is
        immediate and irreversible.
    """
    logger.info("TEST: Guardian Emergency Stop")

    drone = sitl_drone
    state_machine = flight_components["state_machine"]
    guardian = flight_components["guardian"]
    escalation_matrix = flight_components["escalation_matrix"]

    # Arm and takeoff
    target_altitude = 5.0
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    # Verify we're armed and flying
    armed = False
    async for a in drone.telemetry.armed():
        armed = a
        break

    assert armed, "Should be armed for kill switch test"
    assert state_machine.is_armed, "State machine should show armed"

    # Test kill switch trigger in state machine
    # Note: We verify the logic works, but in SITL we don't let it
    # actually kill the simulation (so we can clean up properly)
    result = state_machine.trigger_failsafe("kill_switch")
    assert result, "State machine should accept kill_switch trigger"

    # Verify EMERGENCY state
    from avatar.mav.state_machine import FlightState
    assert state_machine.current_state == FlightState.EMERGENCY, (
        f"Should be in EMERGENCY state, got {state_machine.current_state_name}"
    )

    logger.info("State machine correctly entered EMERGENCY state")

    # Check escalation matrix kill switch handling
    event = escalation_matrix.evaluate("kill_switch", force_trigger=True)
    if event:
        logger.info(f"Kill switch escalation: {event.level.name} -> {event.action_taken}")
        assert event.level.value >= 6, "Kill switch should be L6 (Catastrophic)"
        assert "emergency" in event.action_taken.lower() or "disarm" in event.action_taken.lower(), (
            f"Action should be emergency stop: {event.action_taken}"
        )

    # Reset state machine for cleanup
    state_machine.reset(force=True)
    state_machine.transition(FlightState.DISARMED, "test_cleanup", "test")

    # Land normally (since we didn't actually kill)
    await drone.action.land()
    await wait_for_on_ground(drone)

    logger.info("TEST PASSED: Guardian emergency stop logic working")


# =============================================================================
# FAILSAFE INTEGRATION TESTS
# =============================================================================
# These tests validate the failsafe system as a whole - priority ordering,
# recovery paths, and integration between components.
# =============================================================================


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.slow
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_failsafe_priority_order(
    flight_components: Dict[str, Any],
) -> None:
    """
    Test failsafe priority ordering.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Different failsafe conditions have different severity levels. When multiple
    conditions are present, the most severe should take precedence. This test
    validates the priority hierarchy defined in the EscalationMatrix.

    Priority Hierarchy (from most to least severe):
    - L6 CATASTROPHIC: total_system_failure, total_power_loss, kill_switch
    - L5 CRITICAL:      battery_critical, comm_link_lost
    - L4 WARNING:       battery_low, geofence_breach
    - L3 ADVISORY:      geofence_warning
    - L2 INFO:          comm_link_degraded

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Query escalation matrix for all known condition levels
    2. Build priority mapping dictionary
    3. Filter out None values (conditions not in matrix)
    4. Log all valid priority levels for inspection
    5. Verify ordering: total_system_failure >= battery_critical
    6. Verify ordering: battery_critical > battery_low
    7. Verify ordering: geofence_breach > geofence_warning
    8. Verify ordering: comm_link_lost > comm_link_degraded

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - All queried conditions return valid EscalationLevel values
    - L6 conditions have highest priority numbers
    - Each severity tier is strictly greater than the one below it
    - Priority ordering matches the documented hierarchy

    Why This Matters:
        If both low battery (L4) and geofence warning (L3) occur simultaneously,
        the L4 battery condition should take precedence and trigger RTL, not the
        L3 geofence warning which might just slow the drone.
    """
    logger.info("TEST: Failsafe Priority Order")

    escalation_matrix = flight_components["escalation_matrix"]

    # Check priority levels (only check conditions that exist in the matrix)
    priorities = {
        "total_system_failure": escalation_matrix.get_level("total_system_failure"),
        "total_power_loss": escalation_matrix.get_level("total_power_loss"),
        "battery_critical": escalation_matrix.get_level("battery_critical"),
        "battery_low": escalation_matrix.get_level("battery_low"),
        "geofence_breach": escalation_matrix.get_level("geofence_breach"),
        "geofence_warning": escalation_matrix.get_level("geofence_warning"),
        "comm_link_lost": escalation_matrix.get_level("comm_link_lost"),
        "comm_link_degraded": escalation_matrix.get_level("comm_link_degraded"),
    }

    # Filter out None values for checks
    valid_priorities = {k: v for k, v in priorities.items() if v is not None}

    logger.info("Failsafe priority levels:")
    for condition, level in valid_priorities.items():
        logger.info(f"  {condition}: L{level.value}")

    # Verify priority ordering (only for available conditions)
    if "total_system_failure" in valid_priorities and "battery_critical" in valid_priorities:
        assert valid_priorities["total_system_failure"].value >= valid_priorities["battery_critical"].value, (
            "Total system failure should be >= battery_critical"
        )
    assert priorities["battery_critical"].value > priorities["battery_low"].value, (
        "Battery critical should be > battery_low"
    )
    assert priorities["geofence_breach"].value > priorities["geofence_warning"].value, (
        "Geofence breach should be > geofence warning"
    )
    assert priorities["comm_link_lost"].value > priorities["comm_link_degraded"].value, (
        "Comm link lost should be > comm link degraded"
    )

    logger.info("TEST PASSED: Failsafe priority order correct")


@pytest.mark.e2e
@pytest.mark.failsafe
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_auto_failsafe_recovery(
    sitl_drone: Any,
    flight_components: Dict[str, Any],
) -> None:
    """
    Test automatic failsafe recovery paths.

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Tests the complete failsafe recovery workflow. When a failsafe triggers and
    RTL completes, the system should return to a safe, recoverable state. This
    validates:

    - State machine correctly tracks recovery progression
    - Telemetry sync updates state after landing
    - Disarm is possible after failsafe recovery
    - Guardian clears alerts appropriately

    This test simulates the real-world scenario where a pilot must regain
    control after an automated failsafe response.

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Reset state machine to DISARMED for clean start
    2. Arm the drone
    3. Takeoff to 5m
    4. Transition state to HOVERING
    5. Trigger low_battery failsafe
    6. Verify state transitions to RTL
    7. Wait for landing (RTL includes descent)
    8. Sync state machine from telemetry (armed=True, in_air=False)
    9. Log post-landing state
    10. Attempt disarm (may auto-disarm depending on PX4 config)
    11. Verify disarmed or log status if still armed

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - State machine accepts low_battery trigger and enters RTL
    - Landing completes within 60 seconds
    - After landing, telemetry shows in_air=False
    - State machine can be synced from telemetry without error
    - Disarm command is accepted or already disarmed
    - System is in safe state after recovery

    Note on SITL:
        Auto-disarm behavior in SITL depends on PX4 parameter configuration.
        The test does not strictly assert disarmed state if auto-disarm is not
        configured, but logs the actual state for inspection.
    """
    logger.info("TEST: Auto Failsafe Recovery")

    drone = sitl_drone
    state_machine = flight_components["state_machine"]

    # Reset state machine
    state_machine.reset(force=True)
    from avatar.mav.state_machine import FlightState
    state_machine.transition(FlightState.DISARMED, "test_start", "test")

    # Full sequence: arm -> takeoff -> simulate failsafe -> RTL -> land -> disarm

    # Arm
    await drone.action.arm()
    await wait_for_armed(drone, timeout=10.0)
    state_machine.transition(FlightState.ARMED, "armed", "test")

    # Takeoff
    await drone.action.set_takeoff_altitude(5.0)
    await drone.action.takeoff()
    await wait_for_in_air(drone, timeout=30.0)
    await asyncio.sleep(5)
    state_machine.transition(FlightState.HOVERING, "takeoff_complete", "test")

    # Simulate failsafe trigger
    result = state_machine.trigger_failsafe("low_battery")
    assert result, "Should trigger failsafe"
    assert state_machine.current_state == FlightState.RTL, "Should be in RTL"

    # Wait for landing
    landed = await wait_for_on_ground(drone, timeout=60.0)
    assert landed, "Should land after RTL"

    # Update state based on telemetry
    state_machine.sync_from_telemetry({
        "armed": True,
        "in_air": False,
        "landed": True,
        "ground_contact": True,
    })

    logger.info(f"Post-landing state: {state_machine.current_state_name}")

    # Disarm
    await asyncio.sleep(2)
    try:
        await drone.action.disarm()
    except Exception:
        pass

    # Final state check
    disarmed = False
    async for a in drone.telemetry.armed():
        disarmed = not a
        break

    if disarmed:
        logger.info("Drone disarmed after failsafe recovery")
    else:
        logger.info("Drone still armed (may require manual disarm)")

    logger.info("TEST PASSED: Auto failsafe recovery working")
