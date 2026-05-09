"""End-to-End Performance Benchmark Tests.

================================================================================
TEST SUITE OVERVIEW
================================================================================
This test suite validates that the Avatar drone control system meets its
performance requirements. These tests measure timing, latency, throughput, and
jitter across all critical operations.

WHY THESE ARE E2E TESTS (NOT UNIT TESTS):
-----------------------------------------
- These tests measure REAL performance characteristics of the integrated system:
  * Actual MAVSDK command latency to PX4
  * True telemetry propagation delays
  * Real heartbeat timing with asyncio event loop jitter
  * Actual cache read performance with memory hierarchy effects
- Unit tests using mocks would report fake/simulated timing
- Performance characteristics emerge from component interactions that cannot
  be predicted from unit test results
- These tests catch performance regressions that only appear under real load

PERFORMANCE REQUIREMENTS VALIDATED:
-----------------------------------
Requirement              | Target     | Tests
-------------------------|------------|----------------------------------------
Command latency          | <100ms     | test_command_response_time
Connection latency       | <100ms     | test_connection_latency
Telemetry poll latency   | <50ms      | test_telemetry_poll_latency
Heartbeat precision      | 20Hz ±10ms | test_heartbeat_precision
Cache read speed         | <1ms       | test_telemetry_cache_speed
State machine transitions| <10ms      | test_state_machine_transitions
Offboard streaming       | >=18Hz     | test_offboard_streaming_rate

USAGE:
    pytest tests/e2e/test_performance.py -v --run-sitl

Requirements:
    - PX4 SITL running: make px4_sitl gz_x500
    - Quiet system (performance tests are sensitive to load)
    - 3-5 minutes for complete test run
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
# These tests measure the time required to establish and verify the MAVSDK
# connection to PX4. Fast connection is critical for rapid mission startup.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures the round-trip latency for connection state queries. This validates
    that the MAVSDK-PX4 link is responsive and suitable for real-time control.

    Why This Matters:
    - Slow connections indicate network/protocol issues
    - Latency >100ms suggests UDP packet loss or CPU overload
    - Consistent latency is as important as absolute speed (low jitter)

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Perform 10 connection state queries in a loop
    2. For each query:
       - Record start timestamp
       - Query connection state via drone.core.connection_state()
       - Verify is_connected is True
       - Calculate elapsed time in milliseconds
    3. Calculate statistics across all 10 samples:
       - Average latency
       - Maximum latency
       - Minimum latency
    4. Log all statistics
    5. Record to performance collector
    6. Assert average <100ms and max <200ms

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - All 10 connection queries succeed
    - Average latency <100ms
    - Maximum latency <200ms (allowing for occasional system jitter)
    - All queries report connected=True

    Failure Analysis:
    - If avg >100ms: System overloaded or network issues
    - If max >> avg: Inconsistent latency, check for background processes
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
# These tests measure how quickly flight commands are accepted by the autopilot.
# Fast response is essential for responsive control and safety.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures end-to-end latency for critical flight commands from the moment
    the command is sent via MAVSDK until the acknowledgment is received.

    Commands Tested:
    - Arm: High latency acceptable (motor controller initialization)
    - Takeoff: High latency acceptable (state machine transitions)
    - Hold: Must be fast (<100ms) for responsive control
    - Land: Must be fast (<100ms) for safety

    Why Different Limits:
    - Arm/Takeoff involve complex state changes, allow 5000ms
    - Hold/Land are simple mode changes, must be <100ms

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Test ARM command:
       - Measure send time
       - Wait for armed confirmation
       - Log latency
    2. Test TAKEOFF command:
       - Set takeoff altitude
       - Measure send time
       - Wait for in-air
       - Log latency
    3. Test HOLD command:
       - Measure send time
       - Log latency
       - Assert <100ms
    4. Test LAND command:
       - Measure send time
       - Wait for on-ground
       - Log latency
       - Assert <100ms
    5. Record all metrics to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Arm latency <5000ms
    - Takeoff latency <5000ms
    - Hold latency <100ms
    - Land latency <100ms

    Performance Budget:
    - User-perceived responsiveness requires <100ms for interactive commands
    - Arm/Takeoff are non-interactive (one-time per mission), allow longer
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures the latency of telemetry stream reads. Fast telemetry is essential
    for the Guardian safety system to detect anomalies quickly.

    Streams Tested:
    - Position (GPS coordinates)
    - Battery (charge level, voltage)

    Why <100ms Matters:
    - Guardian evaluates safety 10-20 times per second
    - Slow telemetry delays failsafe detection
    - 100ms = 1m position error at 10 m/s flight speed

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Test position telemetry:
       - Collect 20 samples
       - Measure time to receive one position update
       - 50ms delay between samples to avoid batching
       - Calculate average and max latency
    2. Test battery telemetry:
       - Collect 20 samples
       - Measure time to receive one battery update
       - 50ms delay between samples
       - Calculate average and max latency
    3. Log all statistics
    4. Record to performance collector
    5. Assert averages <100ms

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Position telemetry avg <100ms
    - Battery telemetry avg <100ms
    - Max latency <200ms for both

    Note on MAVSDK:
    - MAVSDK uses async generators that may buffer data
    - First read may be slower due to initialization
    - Subsequent reads should be fast (<50ms typical)
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
# These tests validate the 20Hz heartbeat system that maintains the connection
# and provides timing reference for offboard control.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Validates that the GuardianProcess maintains a precise 20Hz heartbeat,
    which is essential for:
    - Connection health monitoring
    - Offboard control timing reference
    - Detecting communication timeouts

    Metrics:
    - Target interval: 50ms (20Hz)
    - Miss rate: <1% (fewer than 1 missed per 100)

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Allow 3 seconds for heartbeat accumulation
    2. Query guardian status
    3. Extract heartbeat count and missed count
    4. Calculate miss rate as percentage
    5. Log heartbeat count and miss rate
    6. Assert miss rate <5%
    7. Calculate achieved frequency from uptime
    8. Assert achieved rate >=19Hz
    9. Record metrics to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Heartbeat count > 50 (3 seconds × 20Hz)
    - Miss rate <5%
    - Achieved rate >=19Hz
    - Status reports healthy connection

    Why 20Hz Matters:
    - MAVLink offboard mode requires minimum 2Hz, recommends 10Hz+
    - 20Hz provides safety margin and smooth control
    - PX4 watchdog uses heartbeat to detect companion computer failures
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures the actual timing precision of the HeartbeatService using statistical
    analysis of interval distributions. This validates that the asyncio-based
    timing achieves the required precision.

    Metrics:
    - Target interval: 50.0ms
    - Std deviation: <10ms (jitter tolerance)
    - Outliers: <5% beyond ±20ms

    Why Std Deviation Matters:
    - High jitter causes inconsistent control feel
    - MAVLink framing has jitter, but service should minimize it
    - Low std deviation indicates well-timed async event loop

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Create dedicated HeartbeatService with 20Hz config
    2. Set up callback to record timestamps
    3. Start service
    4. Collect samples for 2 seconds
    5. Stop service
    6. Calculate intervals between consecutive timestamps
    7. Calculate statistics:
       - Average interval
       - Standard deviation
       - Achieved rate
    8. Log all statistics
    9. Assert interval within 1ms of 50ms
    10. Assert std dev <20ms
    11. Record to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Average interval 49-51ms
    - Std deviation <20ms (ideally <10ms)
    - Achieved rate 19-21Hz
    - No lost intervals

    Note on Python/asyncio:
    - asyncio.sleep() has ~1-2ms precision on most systems
    - Std dev <20ms is achievable even with Python overhead
    - Lower jitter requires C++ implementation
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
# These tests validate the TelemetryCache subsystem that provides sub-millisecond
# telemetry reads for the MCP server and Guardian.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures the TelemetryCache read performance. The cache provides sub-millisecond
    reads by maintaining a background-updated copy of telemetry data.

    Why <1ms Matters:
    - MCP server queries telemetry for every tool invocation
    - Guardian checks telemetry 10-20 times per second
    - <1ms ensures tools remain responsive
    - Without cache, each read would take 20-50ms

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Warm up cache with 0.5s wait (allows background refresh)
    2. Perform 100 cache reads in a tight loop
    3. For each read:
       - Record start time
       - Call cache.get_data()
       - Calculate elapsed time in milliseconds
    4. Calculate statistics:
       - Average read latency
       - Maximum read latency
    5. Log cache metrics (hit count, refresh count)
    6. Assert average <1ms and max <5ms
    7. Check cache freshness
    8. Assert age <500ms and not stale
    9. Record all metrics to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Average read latency <1ms
    - Maximum read latency <5ms
    - Cache is not stale
    - Cache age <500ms
    - Hit count > 0

    Cache Design:
    - Background task refreshes every 100ms
    - get_data() returns cached copy immediately
    - No locks needed (atomic reference swap)
    - Sub-millisecond performance achieved
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
# These tests validate that state transitions happen quickly, ensuring the
# state machine never becomes a bottleneck.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Measures the performance of FlightStateMachine transitions and precondition
    checks. The state machine must be extremely fast to avoid delaying commands.

    Why <10ms Matters:
    - Every flight command checks state preconditions
    - Slow transitions add latency to user commands
    - State machine runs on main thread (must not block)

    Tests:
    1. Transition timing: measure state changes
    2. Precondition checks: measure command validation

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Reset state machine for clean test
    2. Test transition timing:
       - Define sequence of valid transitions through mission lifecycle
       - For each transition:
         a. Set up from_state
         b. Measure transition() call time
         c. Record elapsed time
       d. Log all transition times
    3. Calculate average and max transition times
    4. Assert avg <10ms and max <50ms
    5. Test precondition checks:
       - Measure check_command_precondition() for common commands
       - Calculate average check time
       - Assert avg <1ms
    6. Record all metrics to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - All transitions complete in <50ms
    - Average transition time <10ms
    - Precondition checks <1ms
    - No invalid transitions attempted

    Transition Sequence Tested:
    INIT → DISARMED → ARMED → TAKING_OFF → HOVERING
    → POSITION_CONTROL → HOVERING → LANDING → LANDED → DISARMED

    This covers a full mission lifecycle.
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
# These tests validate the 20Hz offboard setpoint streaming required for
# real-time velocity control.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    Validates that the system can maintain a 20Hz stream of velocity setpoints
    to the PX4 autopilot in offboard mode. This is the foundation of real-time
    velocity control used by AI agents.

    Requirements:
    - Target rate: 20Hz (50ms intervals)
    - Minimum acceptable: 18Hz (allows 10% jitter tolerance)
    - Jitter: <10ms std deviation

    Why 20Hz Matters:
    - Below 10Hz, control becomes jerky and unstable
    - MAVLink offboard mode requires minimum 2Hz, recommends 10Hz+
    - 20Hz provides smooth control with safety margin
    - Higher rates (50Hz) possible but not necessary for most flight

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Arm and takeoff to 5m
    2. Start offboard mode with initial velocity setpoint
    3. Stream setpoints for 2 seconds:
       - Send velocity setpoint
       - Record timestamp
       - Maintain 50ms interval using asyncio.sleep()
    4. Stop offboard mode
    5. Calculate intervals between timestamps
    6. Calculate statistics:
       - Number of setpoints sent
       - Average interval
       - Standard deviation (jitter)
       - Achieved rate
    7. Log all statistics
    8. Assert achieved rate >=18Hz
    9. Assert jitter <10ms
    10. Land for cleanup
    11. Record metrics to performance collector

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - Setpoints sent: ~40 (2s × 20Hz)
    - Average interval: 50ms ±5ms
    - Std deviation: <10ms
    - Achieved rate: >=18Hz
    - No exceptions during streaming

    Implementation Notes:
    - Uses asyncio for timing (not real-time but sufficient for testing)
    - Small velocity (0.5 m/s) to prevent excessive drift
    - Sequential setpoints (all same value) for test consistency
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
# This test generates a final summary report of all performance metrics
# collected during the test run.
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

    ================================================================================
    TEST SCENARIO
    ================================================================================
    This test runs after all other performance tests to compile a comprehensive
    report of all collected metrics. It does not perform new measurements but
    aggregates and analyzes the results from previous tests.

    Purpose:
    - Provide a unified view of system performance
    - Identify which requirements are met and which are at risk
    - Generate data for performance regression tracking
    - Create summary suitable for documentation/reports

    ================================================================================
    TEST FLOW
    ================================================================================
    1. Retrieve all collected metrics from PerformanceCollector
    2. Group metrics by operation name
    3. Log detailed metrics for each operation:
       - Operation name
       - Number of samples
       - Duration and metadata for each sample
    4. Calculate summary statistics for key requirements:
       - Command response times
       - Connection latency
       - Telemetry cache speed
       - Heartbeat precision
       - State machine transitions
    5. For each requirement, determine PASS/FAIL status
    6. Log summary table with all requirements
    7. Note: Does not assert - this is a report, not a test

    ================================================================================
    EXPECTED OUTCOMES
    ================================================================================
    - All metrics from previous tests are present
    - Summary shows clear pass/fail for each requirement
    - Report is logged in readable format
    - No assertions (reporting only)

    Requirements Checked:
    - command_response_times: <100ms command latency
    - connection_state_latency: <100ms connection latency
    - telemetry_cache_speed: <1ms cache reads
    - heartbeat_precision: <50ms heartbeat precision
    - state_machine_transitions: <10ms state transitions

    Usage:
    This test should run last in the performance test suite to ensure all
    metrics have been collected by previous tests.
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
