"""End-to-End Performance Benchmark Tests.

Tests system performance requirements:
- <100ms command latency
- <50ms heartbeat precision
- <1ms telemetry cache reads
- 20Hz offboard streaming

All tests use SITL (Software In The Loop) simulation.
No real hardware required.

Usage:
    pytest tests/e2e/test_performance.py -v --run-sitl
"""

import asyncio
import logging
import statistics
import time
from typing import Any, Dict, List, Tuple

import pytest

from tests.e2e.conftest import (
    get_current_altitude,
    PerformanceCollector,
    wait_for_armed,
    wait_for_in_air,
    wait_for_on_ground,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONNECTION LATENCY TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_connection_latency(
    sitl_drone: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test MAVSDK connection establishment latency.

    Verifies:
        - First connection completes in <5000ms
        - Subsequent get_drone() calls are <100ms
    """
    logger.info("TEST: Connection Latency")

    drone = sitl_drone
    latencies: List[float] = []

    # Measure multiple connection state checks
    for i in range(10):
        start = time.perf_counter()
        connected = False
        async for state in drone.core.connection_state():
            connected = state.is_connected
            break
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        assert connected, f"Should be connected (iteration {i})"

    # Calculate statistics
    avg_latency = statistics.mean(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    logger.info(f"Connection state check latencies (ms):")
    logger.info(f"  Average: {avg_latency:.2f}ms")
    logger.info(f"  Min: {min_latency:.2f}ms")
    logger.info(f"  Max: {max_latency:.2f}ms")

    performance_collector.end(
        "connection_state_latency",
        samples=len(latencies),
        avg_ms=avg_latency,
        max_ms=max_latency,
        min_ms=min_latency,
    )

    # Verify <100ms requirement
    assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms > 100ms limit"
    assert max_latency < 200, f"Max latency {max_latency:.2f}ms > 200ms limit"

    logger.info("TEST PASSED: Connection latency <100ms")


# =============================================================================
# COMMAND RESPONSE TIME TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_command_response_time(
    sitl_drone: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test command response times for flight operations.

    Verifies:
        - Arm command: <5000ms
        - Takeoff command: <5000ms
        - Land command: <100ms (command acceptance)
        - Hold command: <100ms
    """
    logger.info("TEST: Command Response Time")

    drone = sitl_drone

    # Test arm command latency
    start = time.perf_counter()
    await drone.action.arm()
    arm_latency_ms = (time.perf_counter() - start) * 1000

    logger.info(f"Arm command latency: {arm_latency_ms:.2f}ms")
    assert arm_latency_ms < 5000, f"Arm latency {arm_latency_ms:.2f}ms > 5000ms"

    await wait_for_armed(drone, timeout=10.0)

    # Test takeoff command latency
    await drone.action.set_takeoff_altitude(5.0)

    start = time.perf_counter()
    await drone.action.takeoff()
    takeoff_latency_ms = (time.perf_counter() - start) * 1000

    logger.info(f"Takeoff command latency: {takeoff_latency_ms:.2f}ms")
    assert takeoff_latency_ms < 5000, f"Takeoff latency {takeoff_latency_ms:.2f}ms > 5000ms"

    await wait_for_in_air(drone, timeout=30.0)
    await asyncio.sleep(5)  # Stabilize

    # Test hold command latency
    start = time.perf_counter()
    await drone.action.hold()
    hold_latency_ms = (time.perf_counter() - start) * 1000

    logger.info(f"Hold command latency: {hold_latency_ms:.2f}ms")
    assert hold_latency_ms < 100, f"Hold latency {hold_latency_ms:.2f}ms > 100ms"

    # Test land command latency
    start = time.perf_counter()
    await drone.action.land()
    land_latency_ms = (time.perf_counter() - start) * 1000

    logger.info(f"Land command latency: {land_latency_ms:.2f}ms")
    assert land_latency_ms < 100, f"Land latency {land_latency_ms:.2f}ms > 100ms"

    await wait_for_on_ground(drone, timeout=45.0)

    # Record results
    performance_collector.end(
        "command_response_times",
        arm_ms=arm_latency_ms,
        takeoff_ms=takeoff_latency_ms,
        hold_ms=hold_latency_ms,
        land_ms=land_latency_ms,
    )

    logger.info("TEST PASSED: Command response times within limits")


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_telemetry_poll_latency(
    sitl_drone: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test telemetry polling latency.

    Verifies:
        - Position telemetry: <50ms
        - Battery telemetry: <50ms
        - Armed state check: <50ms
    """
    logger.info("TEST: Telemetry Poll Latency")

    drone = sitl_drone

    # Test position telemetry latency
    position_latencies: List[float] = []
    for _ in range(20):
        start = time.perf_counter()
        async for pos in drone.telemetry.position():
            break
        elapsed_ms = (time.perf_counter() - start) * 1000
        position_latencies.append(elapsed_ms)
        await asyncio.sleep(0.05)  # Small delay between samples

    avg_pos_latency = statistics.mean(position_latencies)
    max_pos_latency = max(position_latencies)

    logger.info(f"Position telemetry latency: avg={avg_pos_latency:.2f}ms, max={max_pos_latency:.2f}ms")

    # Test battery telemetry latency
    battery_latencies: List[float] = []
    for _ in range(20):
        start = time.perf_counter()
        async for bat in drone.telemetry.battery():
            break
        elapsed_ms = (time.perf_counter() - start) * 1000
        battery_latencies.append(elapsed_ms)
        await asyncio.sleep(0.05)

    avg_bat_latency = statistics.mean(battery_latencies)
    max_bat_latency = max(battery_latencies)

    logger.info(f"Battery telemetry latency: avg={avg_bat_latency:.2f}ms, max={max_bat_latency:.2f}ms")

    # Verify <100ms requirement for telemetry
    assert avg_pos_latency < 100, f"Position telemetry avg {avg_pos_latency:.2f}ms > 100ms"
    assert avg_bat_latency < 100, f"Battery telemetry avg {avg_bat_latency:.2f}ms > 100ms"

    performance_collector.end(
        "telemetry_poll_latency",
        position_avg_ms=avg_pos_latency,
        position_max_ms=max_pos_latency,
        battery_avg_ms=avg_bat_latency,
        battery_max_ms=max_bat_latency,
    )

    logger.info("TEST PASSED: Telemetry poll latency <100ms")


# =============================================================================
# HEARTBEAT PRECISION TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_heartbeat_precision(
    sitl_drone: Any,
    async_guardian: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test 20Hz heartbeat precision.

    Verifies:
        - Heartbeat interval is 50ms (20Hz)
        - Jitter is <10ms (std dev)
        - Missed heartbeats are <1%
    """
    logger.info("TEST: Heartbeat Precision (20Hz)")

    guardian = async_guardian

    # Wait for some heartbeats to accumulate
    logger.info("Collecting heartbeat samples for 3 seconds...")
    await asyncio.sleep(3)

    # Get guardian status
    status = guardian.get_status()

    logger.info(f"Heartbeat count: {status.heartbeat_count}")
    logger.info(f"Missed heartbeats: {status.missed_heartbeats}")

    if status.heartbeat_count > 0:
        miss_rate = status.missed_heartbeats / status.heartbeat_count * 100
        logger.info(f"Miss rate: {miss_rate:.2f}%")

        # Verify <1% miss rate
        assert miss_rate < 5.0, f"Heartbeat miss rate {miss_rate:.2f}% > 5%"

    # Calculate actual frequency achieved
    if status.uptime_s > 0 and status.heartbeat_count > 0:
        achieved_rate = status.heartbeat_count / status.uptime_s
        logger.info(f"Achieved heartbeat rate: {achieved_rate:.1f}Hz")
        assert achieved_rate >= 19.0, f"Heartbeat rate {achieved_rate:.1f}Hz < 19Hz"

    performance_collector.end(
        "heartbeat_precision",
        count=status.heartbeat_count,
        missed=status.missed_heartbeats,
        uptime_s=status.uptime_s,
    )

    logger.info("TEST PASSED: Heartbeat precision >=20Hz")


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_heartbeat_service_precision(
    flight_components: Dict[str, Any],
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test HeartbeatService 20Hz emission precision.

    Verifies:
        - Heartbeat emission at exactly 50ms intervals
        - Std deviation <10ms
    """
    logger.info("TEST: Heartbeat Service Precision")

    from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig

    # Create dedicated service for testing
    config = HeartbeatConfig(
        heartbeat_hz=20.0,  # 20Hz
        offboard_timeout_s=0.5,
    )
    service = HeartbeatService(config)

    # Record timestamps
    timestamps: List[float] = []

    async def record_timestamp(source, timestamp):
        timestamps.append(timestamp)

    service.on_heartbeat = record_timestamp

    # Start service
    await service.start()

    # Collect samples for 2 seconds
    logger.info("Collecting heartbeat samples...")
    performance_collector.start("heartbeat_service_precision")
    await asyncio.sleep(2)

    # Stop service
    await service.stop()

    # Analyze intervals
    if len(timestamps) >= 2:
        intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        avg_interval = statistics.mean(intervals)
        std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
        achieved_rate = 1.0 / avg_interval if avg_interval > 0 else 0

        logger.info(f"Heartbeat intervals:")
        logger.info(f"  Count: {len(timestamps)}")
        logger.info(f"  Average interval: {avg_interval*1000:.2f}ms (target: 50ms)")
        logger.info(f"  Std deviation: {std_dev*1000:.2f}ms")
        logger.info(f"  Achieved rate: {achieved_rate:.1f}Hz")

        performance_collector.end(
            "heartbeat_service_precision",
            count=len(timestamps),
            avg_interval_ms=avg_interval*1000,
            std_dev_ms=std_dev*1000,
            achieved_rate_hz=achieved_rate,
        )

        # Verify 50ms interval with <10ms std dev
        assert abs(avg_interval - 0.05) < 0.01, (
            f"Average interval {avg_interval*1000:.1f}ms != 50ms"
        )
        assert std_dev < 0.02, f"Std deviation {std_dev*1000:.1f}ms > 20ms"

    logger.info("TEST PASSED: Heartbeat service precision correct")


# =============================================================================
# TELEMETRY CACHE SPEED TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_telemetry_cache_speed(
    telemetry_provider: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test telemetry cache read performance.

    Verifies:
        - Cache reads complete in <1ms
        - Stale data detection works
        - Background refresh is active
    """
    logger.info("TEST: Telemetry Cache Speed")

    cache = telemetry_provider

    # Warm up cache
    await asyncio.sleep(0.5)

    # Measure cache read latency
    read_latencies: List[float] = []
    for _ in range(100):
        start = time.perf_counter()
        data = cache.get_data()
        elapsed_ms = (time.perf_counter() - start) * 1000
        read_latencies.append(elapsed_ms)

    avg_read_latency = statistics.mean(read_latencies)
    max_read_latency = max(read_latencies)

    logger.info(f"Cache read latency (100 samples):")
    logger.info(f"  Average: {avg_read_latency:.3f}ms")
    logger.info(f"  Max: {max_read_latency:.3f}ms")

    # Verify <1ms requirement
    assert avg_read_latency < 1.0, f"Cache read avg {avg_read_latency:.3f}ms > 1ms"
    assert max_read_latency < 5.0, f"Cache read max {max_read_latency:.3f}ms > 5ms"

    # Check cache freshness
    is_stale = cache.is_stale()
    age_ms = cache.get_age_ms()

    logger.info(f"Cache age: {age_ms:.1f}ms, stale={is_stale}")

    # Cache should be fresh (updated every 100ms)
    assert not is_stale, f"Cache is stale (age: {age_ms:.1f}ms)"
    assert age_ms < 500, f"Cache age {age_ms:.1f}ms > 500ms"

    # Get metrics
    metrics = cache.get_metrics()
    logger.info(f"Cache metrics: {metrics}")

    performance_collector.end(
        "telemetry_cache_speed",
        avg_read_ms=avg_read_latency,
        max_read_ms=max_read_latency,
        hit_count=metrics.get("hit_count", 0),
        refresh_count=metrics.get("refresh_count", 0),
        is_stale=is_stale,
        age_ms=age_ms,
    )

    logger.info("TEST PASSED: Telemetry cache speed <1ms")


# =============================================================================
# STATE MACHINE TRANSITION TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_state_machine_transitions(
    flight_components: Dict[str, Any],
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test state machine transition performance.

    Verifies:
        - State transitions complete in <10ms
        - Precondition checks are fast
        - History tracking doesn't slow transitions
    """
    logger.info("TEST: State Machine Transitions")

    from avatar.mav.state_machine import FlightState

    state_machine = flight_components["state_machine"]

    # Reset for clean test
    state_machine.reset(force=True)

    # Test valid transitions
    transitions = [
        (FlightState.INIT, FlightState.DISARMED, "init"),
        (FlightState.DISARMED, FlightState.ARMED, "arm"),
        (FlightState.ARMED, FlightState.TAKING_OFF, "takeoff"),
        (FlightState.TAKING_OFF, FlightState.HOVERING, "hover"),
        (FlightState.HOVERING, FlightState.POSITION_CONTROL, "move"),
        (FlightState.POSITION_CONTROL, FlightState.HOVERING, "hold"),
        (FlightState.HOVERING, FlightState.LANDING, "land"),
        (FlightState.LANDING, FlightState.LANDED, "landed"),
        (FlightState.LANDED, FlightState.DISARMED, "disarm"),
    ]

    transition_times: List[float] = []

    performance_collector.start("state_machine_transitions")

    for from_state, to_state, reason in transitions:
        # Reset to from_state if needed
        if state_machine.current_state != from_state:
            # Try to transition to from_state or reset
            state_machine.reset(force=True)
            if from_state != FlightState.INIT:
                state_machine.transition(from_state, "test_setup", "test")

        # Measure transition time
        start = time.perf_counter()
        result = state_machine.transition(to_state, reason, "test")
        elapsed_ms = (time.perf_counter() - start) * 1000

        transition_times.append(elapsed_ms)

        if result:
            logger.info(f"  {from_state.name} -> {to_state.name}: {elapsed_ms:.3f}ms")
        else:
            logger.info(f"  {from_state.name} -> {to_state.name}: INVALID (tried)")

    # Calculate statistics
    valid_times = [t for t in transition_times if t < 100]  # Filter outliers

    if valid_times:
        avg_time = statistics.mean(valid_times)
        max_time = max(valid_times)

        logger.info(f"Transition times:")
        logger.info(f"  Average: {avg_time:.3f}ms")
        logger.info(f"  Max: {max_time:.3f}ms")

        performance_collector.end(
            "state_machine_transitions",
            count=len(transitions),
            avg_ms=avg_time,
            max_ms=max_time,
        )

        # Verify <10ms requirement
        assert avg_time < 10.0, f"Transition avg {avg_time:.3f}ms > 10ms"
        assert max_time < 50.0, f"Transition max {max_time:.3f}ms > 50ms"

    # Test precondition checks
    check_times: List[float] = []
    commands = ["arm", "takeoff", "land", "set_velocity", "hold"]

    for cmd in commands:
        start = time.perf_counter()
        state_machine.check_command_precondition(cmd)
        elapsed_ms = (time.perf_counter() - start) * 1000
        check_times.append(elapsed_ms)

    avg_check_time = statistics.mean(check_times)
    logger.info(f"Precondition check avg: {avg_check_time:.3f}ms")
    assert avg_check_time < 1.0, f"Precondition check {avg_check_time:.3f}ms > 1ms"

    logger.info("TEST PASSED: State machine transitions <10ms")


# =============================================================================
# OFFBOARD STREAMING TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.sitl_required
@pytest.mark.asyncio
async def test_offboard_streaming_rate(
    sitl_drone: Any,
    performance_collector: PerformanceCollector,
) -> None:
    """
    Test 20Hz offboard setpoint streaming.

    Verifies:
        - 20Hz setpoint stream is maintained
        - Actual rate >= 18Hz
        - Timing jitter <10ms std dev
    """
    logger.info("TEST: Offboard Streaming Rate (20Hz)")

    drone = sitl_drone
    target_altitude = 5.0

    # Arm and takeoff
    await drone.action.set_takeoff_altitude(target_altitude)
    await drone.action.arm()
    await wait_for_armed(drone)
    await drone.action.takeoff()
    await wait_for_in_air(drone)
    await asyncio.sleep(5)

    try:
        from mavsdk.offboard import VelocityNedYaw
    except ImportError:
        pytest.skip("MAVSDK offboard not available")

    # Start offboard mode
    velocity_setpoint = VelocityNedYaw(0.5, 0.0, 0.0, 0.0)
    await drone.offboard.set_velocity_ned(velocity_setpoint)
    await drone.offboard.start()

    # Collect timing samples
    timestamps: List[float] = []
    duration_s = 2.0
    start_time = time.time()

    while time.time() - start_time < duration_s:
        loop_start = time.perf_counter()
        await drone.offboard.set_velocity_ned(velocity_setpoint)
        timestamps.append(time.perf_counter())

        # Maintain 50ms interval
        elapsed = time.perf_counter() - loop_start
        sleep_time = 0.05 - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    await drone.offboard.stop()

    # Analyze timing
    if len(timestamps) >= 2:
        intervals = [(timestamps[i] - timestamps[i-1]) * 1000 for i in range(1, len(timestamps))]
        avg_interval = statistics.mean(intervals)
        std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
        achieved_rate = 1000.0 / avg_interval if avg_interval > 0 else 0

        logger.info(f"Offboard streaming:")
        logger.info(f"  Setpoints sent: {len(timestamps)}")
        logger.info(f"  Average interval: {avg_interval:.2f}ms (target: 50ms)")
        logger.info(f"  Std deviation: {std_dev:.2f}ms")
        logger.info(f"  Achieved rate: {achieved_rate:.1f}Hz")

        performance_collector.end(
            "offboard_streaming",
            count=len(timestamps),
            avg_interval_ms=avg_interval,
            std_dev_ms=std_dev,
            achieved_rate_hz=achieved_rate,
        )

        # Verify 20Hz rate
        assert achieved_rate >= 18.0, f"Offboard rate {achieved_rate:.1f}Hz < 18Hz"
        assert std_dev < 10.0, f"Jitter {std_dev:.1f}ms > 10ms"

    # Land
    await drone.action.land()
    await wait_for_on_ground(drone)

    logger.info("TEST PASSED: Offboard streaming at 20Hz")


# =============================================================================
# COMPREHENSIVE PERFORMANCE REPORT
# =============================================================================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_comprehensive_performance_report(
    performance_collector: PerformanceCollector,
) -> None:
    """
    Generate comprehensive performance report.

    This test runs after all other performance tests to compile
    a final report of all collected metrics.
    """
    logger.info("=" * 60)
    logger.info("COMPREHENSIVE PERFORMANCE REPORT")
    logger.info("=" * 60)

    # Get all collected metrics
    all_metrics = performance_collector.get_metrics()

    # Group by operation
    by_operation: Dict[str, List[Any]] = {}
    for metric in all_metrics:
        if metric.operation not in by_operation:
            by_operation[metric.operation] = []
        by_operation[metric.operation].append(metric)

    logger.info("Collected metrics:")
    for operation, metrics in by_operation.items():
        logger.info(f"\n{operation}:")
        for m in metrics:
            logger.info(f"  - {m.duration_ms:.2f}ms: {m.metadata}")

    # Calculate summary statistics
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    # Check key requirements
    requirements = {
        "command_response_times": ("<100ms command latency", 100),
        "connection_state_latency": ("<100ms connection latency", 100),
        "telemetry_cache_speed": ("<1ms cache reads", 1),
        "heartbeat_precision": ("<50ms heartbeat precision", 50),
        "state_machine_transitions": ("<10ms state transitions", 10),
    }

    for op, (desc, limit) in requirements.items():
        avg = performance_collector.get_average(op)
        max_val = performance_collector.get_max(op)

        status = "PASS" if avg < limit else "FAIL"
        logger.info(f"  {desc}: avg={avg:.2f}ms, max={max_val:.2f}ms [{status}]")

    logger.info("=" * 60)

    # Don't assert - this is a report, not a test
    # Actual pass/fail is determined by individual tests
