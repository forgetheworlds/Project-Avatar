"""Tests for the hold tool - Position hold with drift detection.

WHAT THESE TESTS VALIDATE:
    These tests verify the hold() MCP tool which commands the drone to maintain
    its current position for a specified duration while monitoring for drift.
    Key capabilities tested:
    - Position hold with configurable duration
    - Position tolerance monitoring (default ±1m)
    - Automatic state transition to HOVERING
    - Drift detection and reporting
    - Auto RTL (Return to Launch) on excessive drift when enabled

WHY THESE TESTS MATTER:
    The hold tool is critical for mission execution. When an LLM commands a drone
    to "wait here and look for targets," the hold tool maintains position. Without
    proper hold functionality:
    - The drone could drift into obstacles
    - Camera gimbal tracking would be inaccurate
    - Search patterns would be ineffective
    - Safety geofences could be violated

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific hold behaviors:
    - Duration tests: Hold completes after specified time, no drift detected
    - Drift detection: When simulated position moves beyond tolerance, drift is flagged
    - State transitions: Flight state machine transitions to HOVERING during hold
    - Auto RTL: When drift exceeds tolerance AND auto_rtl_on_drift=True, triggers RTL
    - Tolerance: Different tolerance values correctly affect drift detection sensitivity

Test-driven development for Task 12: hold Tool

Coverage:
- Position hold with configurable duration
- Position tolerance monitoring (±1m default)
- Automatic state transition to HOVERING
- Drift detection and correction
- Auto RTL on drift when enabled
"""

import asyncio
import time
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from avatar.mav.state_machine import FlightState, FlightStateMachine
from avatar.mcp_server.tools.flight_tools import (
    FlightTools,
    haversine_distance,
    hold,
    set_state_machine,
    set_telemetry_cache,
)


# =============================================================================
# MOCK TELEMETRY CLASSES
# =============================================================================
# These classes simulate telemetry data for testing without requiring
# a real drone connection. They provide controlled, reproducible test data.


@dataclass
class MockTelemetryData:
    """Mock telemetry data structure simulating real drone telemetry.

    WHAT: Represents a snapshot of drone state at a specific time.
    WHY: Real telemetry requires SITL running; mocks enable fast, reliable tests.
    HOW: Test cases create sequences of these to simulate drone movement.

    Attributes:
        timestamp: Unix timestamp when this data was "captured"
        latitude: GPS latitude in decimal degrees
        longitude: GPS longitude in decimal degrees
        altitude: Altitude above takeoff point in meters (default 10m hover)
        velocity_north: Northward velocity in m/s (default 0 for hold)
        velocity_east: Eastward velocity in m/s (default 0 for hold)
        velocity_down: Downward velocity in m/s (positive = descending)
        groundspeed: Total ground speed in m/s
        roll: Roll angle in degrees
        pitch: Pitch angle in degrees
        yaw: Heading in degrees (0 = North)
        battery_percent: Remaining battery percentage
        battery_voltage: Battery voltage in volts
        battery_current: Current draw in amps
        armed: Whether motors are armed
        in_air: Whether drone is airborne
        flight_mode: Current PX4 flight mode string
        gps_fix: GPS fix type (3 = 3D fix)
        is_gps_ok: Whether GPS data is valid
        is_home_position_ok: Whether home position is set
    """

    timestamp: float
    latitude: float
    longitude: float
    altitude: float = 10.0
    velocity_north: float = 0.0
    velocity_east: float = 0.0
    velocity_down: float = 0.0
    groundspeed: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    battery_percent: float = 100.0
    battery_voltage: float = 16.8
    battery_current: float = 0.0
    armed: bool = True
    in_air: bool = True
    flight_mode: str = "HOLD"
    gps_fix: int = 3
    is_gps_ok: bool = True
    is_home_position_ok: bool = True


class MockTelemetryCache:
    """Mock telemetry cache that simulates the real telemetry system.

    WHAT: Simulates the TelemetryCache that stores latest drone telemetry.
    WHY: Allows tests to inject specific telemetry sequences to trigger behaviors.
    HOW: Can return fixed data or iterate through a sequence to simulate movement.

    Usage:
        # Fixed position (no drift)
        cache._data = MockTelemetryData(...)

        # Simulated movement (drift detection)
        cache.set_sequence([
            MockTelemetryData(timestamp=t1, lat=37.0, lon=-122.0),  # Start
            MockTelemetryData(timestamp=t2, lat=37.001, lon=-122.0),  # Drift north
        ])
    """

    def __init__(self, data=None):
        """Initialize cache with optional fixed data."""
        self._data = data
        self._sequence = []
        self._index = 0

    def set_sequence(self, sequence):
        """Set a sequence of telemetry data points to simulate movement.

        WHAT: Configures the cache to return sequential data on each get_data() call.
        WHY: Simulates drone drift over time for drift detection tests.
        HOW: Each call to get_data() returns next item; last item repeats.
        """
        self._sequence = sequence
        self._index = 0

    def get_data(self):
        """Get current telemetry data.

        WHAT: Returns either fixed data or next item from sequence.
        WHY: Simulates the real telemetry cache interface.
        HOW: If sequence set, advances through it; otherwise returns fixed data.
        """
        if self._sequence:
            if self._index < len(self._sequence):
                data = self._sequence[self._index]
                self._index += 1
                return data
            return self._sequence[-1]
        return self._data


# =============================================================================
# PYTEST FIXTURES
# =============================================================================
# Fixtures provide consistent test setup with proper initial states.


@pytest.fixture
def state_machine():
    """Create a state machine in FLYING state for hold tests.

    WHAT: Provides a FlightStateMachine initialized through the full startup sequence.
    WHY: Hold tool requires FLYING or similar state; tests need consistent start state.

    HOW IT WORKS - STEP BY STEP:
        1. Creates new FlightStateMachine (starts in INIT)
        2. Transitions: INIT -> DISARMED (startup complete)
        3. Transitions: DISARMED -> ARMED (operator command)
        4. Transitions: ARMED -> TAKING_OFF (takeoff initiated)
        5. Transitions: TAKING_OFF -> HOVERING (takeoff complete)
        6. Transitions: HOVERING -> FLYING (movement)
        7. Returns machine in FLYING state

    Returns:
        FlightStateMachine in FLYING state, ready for hold command.
    """
    sm = FlightStateMachine()
    # Transition to FLYING state (can execute hold command)
    sm.transition(FlightState.DISARMED, "startup", "test")
    sm.transition(FlightState.ARMED, "arm", "test")
    sm.transition(FlightState.TAKING_OFF, "takeoff", "test")
    sm.transition(FlightState.HOVERING, "hover", "test")
    sm.transition(FlightState.FLYING, "movement", "test")
    return sm


@pytest.fixture
def telemetry_cache():
    """Create a mock telemetry cache for testing.

    WHAT: Provides empty MockTelemetryCache instance.
    WHY: Tests need to inject specific telemetry data for their scenarios.
    HOW: Returns fresh cache; test must populate _data or set_sequence().
    """
    return MockTelemetryCache()


@pytest.fixture
def flight_tools(state_machine, telemetry_cache):
    """Create flight tools with mocked dependencies.

    WHAT: Provides configured FlightTools instance with mocked state and telemetry.
    WHY: Isolates tests from real drone connection while maintaining realistic interfaces.

    HOW IT WORKS:
        1. Injects state_machine into global state via set_state_machine()
        2. Injects telemetry_cache into global state via set_telemetry_cache()
        3. Creates FlightTools instance that uses these mocks
        4. Returns configured tools ready for testing

    Returns:
        FlightTools instance with mocked state machine and telemetry cache.
    """
    set_state_machine(state_machine)
    set_telemetry_cache(telemetry_cache)
    tools = FlightTools(state_machine=state_machine)
    return tools


# =============================================================================
# TEST CLASSES - DURATION TESTING
# =============================================================================


class TestHoldDuration:
    """Tests for hold duration functionality.

    WHAT THESE TESTS VALIDATE:
        - Hold tool respects the requested duration
        - Returns accurate elapsed time
        - Short durations work correctly
        - No false drift detection with fixed positions

    WHY THESE TESTS MATTER:
        Duration accuracy is critical for mission timing. If hold(10s) returns
        after 5s, search patterns fail. If it takes 20s, missions run inefficiently.
    """

    @pytest.mark.asyncio
    async def test_hold_duration(self, flight_tools, state_machine, telemetry_cache):
        """Test that hold respects specified duration.

        WHAT THIS TEST VALIDATES:
            When commanding hold for 0.5 seconds, the operation completes
            in approximately that time (within tolerance), reports success,
            and detects no drift (since position is fixed).

        EXPECTED OUTCOMES:
            - success=True in result
            - Elapsed time >= duration - 0.1s (accounting for processing overhead)
            - duration_s field matches requested duration
            - was_drift_detected=False (fixed position = no drift)
            - max_drift_m=0.0 (exactly at hold position)

        HOW IT WORKS - STEP BY STEP:
            1. Creates fixed position telemetry at San Francisco coordinates
            2. Injects fixed position into telemetry cache
            3. Records start time
            4. Calls flight_tools.hold(duration_s=0.5)
            5. Calculates elapsed time
            6. Asserts all expected outcomes in result dict
        """
        # Setup telemetry at fixed position
        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        duration = 0.5  # Short duration for test

        start_time = time.time()
        result = await flight_tools.hold(duration_s=duration)
        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed >= duration - 0.1  # Allow small timing variance
        assert result["duration_s"] == duration
        assert result["was_drift_detected"] is False
        assert result["max_drift_m"] == 0.0  # No drift with fixed position

    @pytest.mark.asyncio
    async def test_hold_duration_short(self, flight_tools, telemetry_cache):
        """Test that very short hold durations work correctly.

        WHAT THIS TEST VALIDATES:
            Even sub-second holds complete successfully without errors.
            This tests edge case handling for minimal durations.

        EXPECTED OUTCOMES:
            - success=True
            - Elapsed time >= duration - 0.05s
            - duration_s matches requested value

        HOW IT WORKS:
            Similar to test_hold_duration but with 0.1s duration,
            verifying the system handles very short holds gracefully.
        """
        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        duration = 0.1

        start_time = time.time()
        result = await flight_tools.hold(duration_s=duration)
        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed >= duration - 0.05
        assert result["duration_s"] == duration


# =============================================================================
# TEST CLASSES - DRIFT DETECTION
# =============================================================================


class TestDriftDetection:
    """Tests for drift detection functionality.

    WHAT THESE TESTS VALIDATE:
        - Hold tool detects when drone position drifts from hold point
        - Drift distance is calculated accurately using haversine formula
        - Small variations within tolerance don't trigger false positives
        - Large movements are correctly flagged as drift

    WHY THESE TESTS MATTER:
        Drift detection is the primary safety feature of hold. Without it,
        wind or control issues could move the drone into danger while the
        system thinks it's holding position. Accurate detection enables
        corrective action or emergency RTL.
    """

    @pytest.mark.asyncio
    async def test_drift_detection(self, flight_tools, state_machine, telemetry_cache):
        """Test that position drift is correctly detected and measured.

        WHAT THIS TEST VALIDATES:
            When the drone moves ~22m north during a hold, the system:
            - Detects drift occurred (was_drift_detected=True)
            - Reports max drift > 10m (approximately correct)
            - Still completes the hold (success=True with tolerance 20m)

        EXPECTED OUTCOMES:
            - success=True (because tolerance was set to 20m)
            - was_drift_detected=True (22m exceeds default 1m tolerance)
            - max_drift_m > 10.0 (roughly half of 22m movement)

        HOW IT WORKS - STEP BY STEP:
            1. Creates a sequence of 4 telemetry points showing northward drift:
               - t=0.0s: lat=37.7749 (hold start position)
               - t=0.1s: lat=37.7749 (still at start)
               - t=0.2s: lat=37.7750 (~11m north)
               - t=0.3s: lat=37.7751 (~22m north)
            2. Injects sequence into telemetry cache
            3. Calls hold with 20m tolerance (to allow completion)
            4. Verifies drift was detected and measured
        """
        # Create a sequence showing drift
        base_time = time.time()
        sequence = [
            MockTelemetryData(
                timestamp=base_time,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.1,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.2,
                latitude=37.7750,  # ~11m north
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.3,
                latitude=37.7751,  # ~22m north
                longitude=-122.4194,
            ),
        ]
        telemetry_cache.set_sequence(sequence)

        result = await flight_tools.hold(duration_s=0.3, position_tolerance_m=20.0)

        assert result["success"] is True
        assert result["was_drift_detected"] is True
        assert result["max_drift_m"] > 10.0  # Should have drifted > 10m

    @pytest.mark.asyncio
    async def test_no_drift_with_stable_position(self, flight_tools, telemetry_cache):
        """Test that small position variations don't trigger false drift.

        WHAT THIS TEST VALIDATES:
            When position variations are within tolerance (~0.1m), the system
            does not flag drift. This prevents noise from triggering false alerts.

        EXPECTED OUTCOMES:
            - success=True
            - was_drift_detected=False (variations within 1m tolerance)
            - max_drift_m < 1.0 (actual drift is tiny)

        HOW IT WORKS:
            1. Creates sequence of 5 points with tiny lat movements (0.000001 deg ≈ 0.1m)
            2. Runs hold with 1m tolerance
            3. Verifies no drift detected
        """
        base_time = time.time()
        # Small variations within tolerance
        sequence = [
            MockTelemetryData(
                timestamp=base_time + i * 0.1,
                latitude=37.7749 + (i * 0.000001),  # Tiny movement ~0.1m
                longitude=-122.4194,
            )
            for i in range(5)
        ]
        telemetry_cache.set_sequence(sequence)

        result = await flight_tools.hold(duration_s=0.4, position_tolerance_m=1.0)

        assert result["success"] is True
        assert result["was_drift_detected"] is False
        assert result["max_drift_m"] < 1.0


# =============================================================================
# TEST CLASSES - STATE TRANSITIONS
# =============================================================================


class TestStateTransition:
    """Tests for automatic state transition to HOVERING.

    WHAT THESE TESTS VALIDATE:
        - Hold command transitions state machine to HOVERING
        - Transition works from various flight states
        - State is correctly reported in result

    WHY THESE TESTS MATTER:
        The state machine tracks what the drone is doing. If hold doesn't
        update state, other tools might think the drone is still in FLYING
        state and send conflicting commands.
    """

    @pytest.mark.asyncio
    async def test_state_transition_to_hovering(self, flight_tools, state_machine, telemetry_cache):
        """Test that hold transitions state to HOVERING.

        WHAT THIS TEST VALIDATES:
            Starting from FLYING state, after hold() completes:
            - Result state field shows "HOVERING"
            - state_machine.current_state is FlightState.HOVERING

        EXPECTED OUTCOMES:
            - Initial state is FLYING
            - success=True
            - result["state"] == "HOVERING"
            - state_machine.current_state == FlightState.HOVERING

        HOW IT WORKS:
            1. Verify initial FLYING state
            2. Set fixed telemetry
            3. Call hold()
            4. Assert state transitions occurred
        """
        assert state_machine.current_state == FlightState.FLYING

        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        result = await flight_tools.hold(duration_s=0.2)

        assert result["success"] is True
        assert result["state"] == "HOVERING"
        assert state_machine.current_state == FlightState.HOVERING

    @pytest.mark.asyncio
    async def test_state_transition_from_position_control(self, flight_tools, state_machine, telemetry_cache):
        """Test that hold can transition from POSITION_CONTROL state.

        WHAT THIS TEST VALIDATES:
            Hold works correctly even when coming from position control mode,
            properly transitioning through states.

        EXPECTED OUTCOMES:
            - Can transition from POSITION_CONTROL to HOVERING
            - Final state is HOVERING
        """
        # Set up in POSITION_CONTROL state
        state_machine._state = FlightState.POSITION_CONTROL
        assert state_machine.current_state == FlightState.POSITION_CONTROL

        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        result = await flight_tools.hold(duration_s=0.2)

        assert result["success"] is True
        assert state_machine.current_state == FlightState.HOVERING


# =============================================================================
# TEST CLASSES - AUTO RTL ON DRIFT
# =============================================================================


class TestAutoRtlOnDrift:
    """Tests for auto RTL (Return to Launch) on drift functionality.

    WHAT THESE TESTS VALIDATE:
        - When auto_rtl_on_drift=True and drift exceeds tolerance, RTL triggers
        - When auto_rtl_on_drift=False, drift is reported but hold continues
        - RTL state transition occurs correctly

    WHY THESE TESTS MATTER:
        Auto RTL is a critical safety feature. If the drone cannot maintain
        position (high wind, motor failure, etc.), automatically returning
        home could save the vehicle. These tests ensure the safety logic works.
    """

    @pytest.mark.asyncio
    async def test_auto_rtl_on_drift(self, flight_tools, state_machine, telemetry_cache):
        """Test RTL triggers when drift exceeds tolerance with auto_rtl_on_drift=True.

        WHAT THIS TEST VALIDATES:
            With significant drift (~67m) and tight tolerance (5m), when
            auto_rtl_on_drift is enabled, the system:
            - Reports success=False (hold failed due to safety)
            - Reports reason="rtl_triggered_due_to_drift"
            - Transitions state machine to RTL
            - Reports drift distance > tolerance

        EXPECTED OUTCOMES:
            - success=False (safety intervention occurred)
            - reason indicates RTL was triggered
            - drift_m > 5.0 (exceeded tolerance)
            - state_machine.current_state == FlightState.RTL

        HOW IT WORKS:
            1. Creates sequence showing 67m drift in 0.15s
            2. Calls hold with 5m tolerance and auto_rtl_on_drift=True
            3. Verifies safety RTL was triggered
        """
        # Create sequence showing significant drift
        base_time = time.time()
        sequence = [
            MockTelemetryData(
                timestamp=base_time,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.15,
                latitude=37.7755,  # ~67m north - significant drift
                longitude=-122.4194,
            ),
        ]
        telemetry_cache.set_sequence(sequence)

        result = await flight_tools.hold(
            duration_s=0.3,
            position_tolerance_m=5.0,
            auto_rtl_on_drift=True
        )

        assert result["success"] is False
        assert result["reason"] == "rtl_triggered_due_to_drift"
        assert result["drift_m"] > 5.0
        # State should have transitioned to RTL via failsafe
        assert state_machine.current_state == FlightState.RTL

    @pytest.mark.asyncio
    async def test_no_rtl_when_auto_rtl_disabled(self, flight_tools, state_machine, telemetry_cache):
        """Test that RTL does NOT trigger when auto_rtl_on_drift=False.

        WHAT THIS TEST VALIDATES:
            Even with significant drift, when auto_rtl_on_drift is disabled
            (the default), the hold completes normally but reports the drift.

        EXPECTED OUTCOMES:
            - success=True (hold completed despite drift)
            - was_drift_detected=True (drift was noticed)
            - max_drift_m > 5.0 (significant drift occurred)
            - State does NOT transition to RTL

        HOW IT WORKS:
            Same drift sequence as test_auto_rtl_on_drift, but with
            auto_rtl_on_drift=False, verifying hold completes and
            reports drift without triggering emergency RTL.
        """
        base_time = time.time()
        sequence = [
            MockTelemetryData(
                timestamp=base_time,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.15,
                latitude=37.7755,  # Significant drift
                longitude=-122.4194,
            ),
        ]
        telemetry_cache.set_sequence(sequence)

        result = await flight_tools.hold(
            duration_s=0.3,
            position_tolerance_m=5.0,
            auto_rtl_on_drift=False  # Disabled
        )

        # Should complete but mark drift as detected
        assert result["success"] is True
        assert result["was_drift_detected"] is True
        assert result["max_drift_m"] > 5.0


# =============================================================================
# TEST CLASSES - TOLERANCE SETTINGS
# =============================================================================


class TestToleranceSetting:
    """Tests for tolerance parameter respect.

    WHAT THESE TESTS VALIDATE:
        - Different tolerance values affect drift detection sensitivity
        - Default tolerance is 1 meter
        - Tolerance is properly compared against calculated drift

    WHY THESE TESTS MATTER:
        Tolerance configures the trade-off between safety and mission flexibility.
        Low tolerance (1m) is strict for precision work. High tolerance (10m)
        allows for windy conditions. Tests verify this configuration works.
    """

    @pytest.mark.asyncio
    async def test_tolerance_setting(self, flight_tools, telemetry_cache):
        """Test that tolerance parameter affects drift detection.

        WHAT THIS TEST VALIDATES:
            Same ~2m drift sequence tested with different tolerances:
            - With 1m tolerance: drift detected (2m > 1m)
            - With 5m tolerance: no drift detected (2m < 5m)

        EXPECTED OUTCOMES:
            - Low tolerance (1m): was_drift_detected=True
            - High tolerance (5m): was_drift_detected=False

        HOW IT WORKS:
            1. Creates sequence with ~2m movement
            2. Runs hold with 1m tolerance -> detects drift
            3. Resets state machine to FLYING
            4. Runs hold with 5m tolerance -> no drift
        """
        base_time = time.time()
        # Create drift of ~2m
        sequence = [
            MockTelemetryData(
                timestamp=base_time,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.15,
                latitude=37.774918,  # ~2m north
                longitude=-122.4194,
            ),
        ]
        telemetry_cache.set_sequence(sequence)

        # With 1m tolerance, should detect drift
        result_low = await flight_tools.hold(
            duration_s=0.2,
            position_tolerance_m=1.0,
            auto_rtl_on_drift=False
        )
        assert result_low["was_drift_detected"] is True

        # Reset state
        flight_tools.state_machine._state = FlightState.FLYING

        # With 5m tolerance, should NOT detect drift
        result_high = await flight_tools.hold(
            duration_s=0.2,
            position_tolerance_m=5.0,
            auto_rtl_on_drift=False
        )
        assert result_high["was_drift_detected"] is False

    @pytest.mark.asyncio
    async def test_default_tolerance(self, flight_tools, telemetry_cache):
        """Test that default tolerance is 1 meter.

        WHAT THIS TEST VALIDATES:
            When tolerance is not explicitly specified, the system uses 1m
            as the default drift detection threshold.

        EXPECTED OUTCOMES:
            - ~1.5m drift is detected with default tolerance
            - was_drift_detected=True

        HOW IT WORKS:
            Creates ~1.5m drift, calls hold WITHOUT tolerance parameter,
            verifies drift is detected (proving default is <1.5m, i.e., 1m).
        """
        base_time = time.time()
        # Create drift of ~1.5m
        sequence = [
            MockTelemetryData(
                timestamp=base_time,
                latitude=37.7749,
                longitude=-122.4194,
            ),
            MockTelemetryData(
                timestamp=base_time + 0.15,
                latitude=37.774914,  # ~1.5m north
                longitude=-122.4194,
            ),
        ]
        telemetry_cache.set_sequence(sequence)

        # Default tolerance is 1m
        result = await flight_tools.hold(duration_s=0.2, auto_rtl_on_drift=False)
        assert result["was_drift_detected"] is True


# =============================================================================
# TEST CLASSES - STATE PRECONDITIONS
# =============================================================================


class TestStatePrecondition:
    """Tests for state precondition checking.

    WHAT THESE TESTS VALIDATE:
        - Hold command requires appropriate flight state (FLYING, HOVERING, etc.)
        - Hold is rejected when in inappropriate states (DISARMED, etc.)
        - Clear error messages explain why hold was rejected

    WHY THESE TESTS MATTER:
        State preconditions prevent dangerous command sequences. You can't
        hold position if the drone is disarmed on the ground. These checks
        catch logic errors in the LLM or mission planning.
    """

    @pytest.mark.asyncio
    async def test_hold_requires_flying_state(self, telemetry_cache):
        """Test that hold requires FLYING or similar state.

        WHAT THIS TEST VALIDATES:
            When state machine is in DISARMED state, hold() returns an error
            instead of attempting to execute (which would be nonsensical).

        EXPECTED OUTCOMES:
            - success=False
            - error field contains explanation
            - error message mentions current state (DISARMED)

        HOW IT WORKS:
            1. Creates fresh state machine in DISARMED state
            2. Sets up fixed telemetry
            3. Calls hold()
            4. Verifies appropriate error response
        """
        # Create state machine in DISARMED state
        sm = FlightStateMachine()
        sm.transition(FlightState.DISARMED, "startup", "test")

        set_state_machine(sm)
        tools = FlightTools(state_machine=sm)

        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        result = await tools.hold(duration_s=0.2)

        assert result["success"] is False
        assert "error" in result
        assert "DISARMED" in result["error"]


# =============================================================================
# TEST CLASSES - DISTANCE CALCULATION
# =============================================================================


class TestHaversineDistance:
    """Tests for haversine distance calculation.

    WHAT THESE TESTS VALIDATE:
        The haversine_distance() function correctly calculates great-circle
        distance between two GPS coordinates on Earth's surface.

    WHY THESE TESTS MATTER:
        Accurate distance calculation is essential for drift detection.
        Simple Euclidean distance doesn't work on a sphere. Haversine formula
        accounts for Earth's curvature.
    """

    def test_haversine_same_point(self):
        """Test that distance between identical coordinates is 0.

        WHAT: haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        EXPECTED: 0.0 meters (same point)
        """
        dist = haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert dist == 0.0

    def test_haversine_known_distance(self):
        """Test that haversine produces reasonable distances for known separation.

        WHAT: Distance from San Francisco to Oakland (~16km)
        EXPECTED: Between 10km and 20km (roughly correct)

        This is a sanity check that the formula is working correctly,
        not a precise verification (we're not testing the math library).
        """
        # San Francisco to Oakland is roughly 16km
        dist = haversine_distance(
            37.7749, -122.4194,  # San Francisco
            37.8044, -122.2712   # Oakland
        )
        # Should be roughly 13-16km
        assert 10000 < dist < 20000

    def test_haversine_small_distance(self):
        """Test that haversine works accurately for small distances.

        WHAT: ~1 meter movement in latitude
        EXPECTED: Result between 0.5m and 2m

        Small distances are what drift detection actually uses, so
        accuracy at this scale is critical.
        """
        # ~1m north
        lat_offset = 0.000009  # roughly 1m in latitude
        dist = haversine_distance(
            37.7749, -122.4194,
            37.7749 + lat_offset, -122.4194
        )
        assert 0.5 < dist < 2.0  # Should be roughly 1m


# =============================================================================
# TEST CLASSES - MCP WRAPPER
# =============================================================================


class TestHoldMCPFunction:
    """Tests for the MCP tool wrapper function.

    WHAT THESE TESTS VALIDATE:
        The hold() function exposed to MCP returns properly formatted
        JSON strings that can be parsed by the agent.

    WHY THESE TESTS MATTER:
        MCP tools communicate via JSON. If the wrapper returns malformed
        JSON or raw Python objects, the agent cannot process the result.
    """

    @pytest.mark.asyncio
    async def test_hold_mcp_wrapper(self, state_machine, telemetry_cache):
        """Test that MCP wrapper returns valid JSON string.

        WHAT THIS TEST VALIDATES:
            The hold() function (the MCP entry point) returns a string that
            can be parsed as valid JSON containing expected result fields.

        EXPECTED OUTCOMES:
            - Result is a string (not a dict)
            - json.loads() succeeds without exception
            - Parsed result contains success, duration_s, max_drift_m fields

        HOW IT WORKS:
            1. Configures state machine and telemetry
            2. Calls hold() directly (the MCP wrapper, not FlightTools.hold)
            3. Parses result as JSON
            4. Validates structure
        """
        set_state_machine(state_machine)
        set_telemetry_cache(telemetry_cache)

        fixed_position = MockTelemetryData(
            timestamp=time.time(),
            latitude=37.7749,
            longitude=-122.4194,
        )
        telemetry_cache._data = fixed_position

        result_json = await hold(duration_s=0.2)

        import json
        result = json.loads(result_json)
        assert result["success"] is True
        assert "duration_s" in result
        assert "max_drift_m" in result


# =============================================================================
# TEST CLASSES - ERROR HANDLING
# =============================================================================


class TestHoldErrorHandling:
    """Tests for error handling in hold.

    WHAT THESE TESTS VALIDATE:
        The hold tool handles error conditions gracefully without crashing,
        returning informative error messages.

    WHY THESE TESTS MATTER:
        Real flights encounter errors (lost telemetry, comms issues, etc.).
        The tool must fail gracefully and return errors the LLM can understand
        and potentially recover from.
    """

    @pytest.mark.asyncio
    async def test_hold_without_telemetry(self, flight_tools, telemetry_cache):
        """Test graceful handling when telemetry is unavailable.

        WHAT THIS TEST VALIDATES:
            When telemetry_cache has no data (None), the hold tool handles
            this gracefully without raising unhandled exceptions.

        EXPECTED OUTCOMES:
            - Does not raise exception
            - Returns a dictionary with success/error fields
            - Either succeeds by trying to get from drone, or fails gracefully

        HOW IT WORKS:
            1. Sets telemetry_cache._data to None
            2. Calls hold()
            3. Verifies result is a valid dict (no crash)
        """
        telemetry_cache._data = None

        # Should handle gracefully without crashing
        result = await flight_tools.hold(duration_s=0.2)

        # Without telemetry, it will try to get from drone
        # If no drone connection, it will return an error
        # But it shouldn't crash
        assert isinstance(result, dict)
        assert "success" in result
