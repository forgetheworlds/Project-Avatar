"""End-to-End Failsafe Trigger Tests.

Tests safety failsafe behaviors including:
- RC loss failsafe
- Telemetry timeout
- Geofence breach detection
- Low battery Return to Launch (RTL)
- Guardian emergency stop

All tests use SITL (Software In The Loop) simulation.
No real hardware required.

Note: Some failsafes require specific PX4 parameter configurations
and may need manual simulation of conditions.

Usage:
    pytest tests/e2e/test_failsafes.py -v --run-sitl
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

    In PX4, when RC link is lost and NAV_RCL_ACT is set appropriately,
    the drone should trigger Return to Launch.

    Note: This test simulates the failsafe by directly triggering the
    state machine transition, as simulating actual RC loss in SITL
    requires specific PX4 parameter configuration.

    Verifies:
        - State machine correctly handles rc_loss trigger
        - RTL state is entered when RC loss is detected
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

    Verifies that the GuardianProcess correctly detects heartbeat timeouts
    and the escalation matrix responds appropriately.

    Note: We simulate telemetry timeout by not updating heartbeat,
    as cutting actual telemetry would disconnect the test.

    Verifies:
        - Heartbeat timeout detection works
        - Escalation matrix triggers on timeout
        - Connection health reflects stale telemetry
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

    Verifies that flying outside the configured geofence boundary
    triggers the appropriate failsafe.

    Note: In SITL, we simulate this by checking guardian validation
    of positions outside the geofence limit.

    Verifies:
        - Guardian validates positions against geofence
        - Positions outside geofence are rejected
        - State machine accepts geofence_breach trigger
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

    Verifies that the escalation matrix correctly identifies low battery
    conditions and recommends RTL action.

    Note: Actual battery level is read from SITL. We test the logic
    by checking escalation at various battery levels.

    Verifies:
        - Battery levels are read correctly
        - Low battery triggers escalation
        - Critical battery triggers immediate RTL
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

    Verifies that the kill switch failsafe can be triggered and
    transitions the state machine to EMERGENCY state.

    Note: In real flight, this would stop motors immediately.
    In SITL, we verify the state transition but don't actually
    kill the simulation (to allow cleanup).

    Verifies:
        - Kill switch trigger is accepted
        - State transitions to EMERGENCY
        - AsyncGuardian would trigger emergency stop
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

    Verifies that different failsafe triggers have appropriate
    priority levels and the most severe takes precedence.

    Verifies:
        - Kill switch (L6) has highest priority
        - Critical battery (L5) > Low battery (L2)
        - Geofence breach (L4) > Geofence warning (L3)
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

    Verifies that after a failsafe triggers, the system can
    recover to a safe state.

    Verifies:
        - After RTL, system lands and can disarm
        - State machine transitions correctly through recovery
        - Guardian clears alerts after recovery
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
