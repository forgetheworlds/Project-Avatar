"""Tests for the hold tool.

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


@dataclass
class MockTelemetryData:
    """Mock telemetry data for testing."""

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
    """Mock telemetry cache for testing."""

    def __init__(self, data=None):
        self._data = data
        self._sequence = []
        self._index = 0

    def set_sequence(self, sequence):
        """Set a sequence of telemetry data points."""
        self._sequence = sequence
        self._index = 0

    def get_data(self):
        """Get current telemetry data."""
        if self._sequence:
            if self._index < len(self._sequence):
                data = self._sequence[self._index]
                self._index += 1
                return data
            return self._sequence[-1]
        return self._data


@pytest.fixture
def state_machine():
    """Create a state machine in FLYING state for hold tests."""
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
    """Create a mock telemetry cache."""
    return MockTelemetryCache()


@pytest.fixture
def flight_tools(state_machine, telemetry_cache):
    """Create flight tools with mocked dependencies."""
    set_state_machine(state_machine)
    set_telemetry_cache(telemetry_cache)
    tools = FlightTools(state_machine=state_machine)
    return tools


class TestHoldDuration:
    """Tests for hold duration functionality."""

    @pytest.mark.asyncio
    async def test_hold_duration(self, flight_tools, state_machine, telemetry_cache):
        """Holds for specified duration."""
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
        """Holds for very short duration."""
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


class TestDriftDetection:
    """Tests for drift detection functionality."""

    @pytest.mark.asyncio
    async def test_drift_detection(self, flight_tools, state_machine, telemetry_cache):
        """Detects position drift correctly."""
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
        """No drift detected when position is stable."""
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


class TestStateTransition:
    """Tests for automatic state transition to HOVERING."""

    @pytest.mark.asyncio
    async def test_state_transition_to_hovering(self, flight_tools, state_machine, telemetry_cache):
        """Transitions to HOVERING state on hold."""
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
        """Can transition to HOVERING from POSITION_CONTROL."""
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


class TestAutoRtlOnDrift:
    """Tests for auto RTL on drift functionality."""

    @pytest.mark.asyncio
    async def test_auto_rtl_on_drift(self, flight_tools, state_machine, telemetry_cache):
        """Triggers RTL when drift exceeds tolerance and auto_rtl_on_drift is True."""
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
        """Does not RTL when auto_rtl_on_drift is False (default)."""
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


class TestToleranceSetting:
    """Tests for tolerance parameter respect."""

    @pytest.mark.asyncio
    async def test_tolerance_setting(self, flight_tools, telemetry_cache):
        """Respects tolerance parameter for drift detection."""
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
        """Default tolerance is 1 meter."""
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


class TestStatePrecondition:
    """Tests for state precondition checking."""

    @pytest.mark.asyncio
    async def test_hold_requires_flying_state(self, telemetry_cache):
        """Hold requires FLYING or similar state."""
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


class TestHaversineDistance:
    """Tests for haversine distance calculation."""

    def test_haversine_same_point(self):
        """Distance between same point is 0."""
        dist = haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert dist == 0.0

    def test_haversine_known_distance(self):
        """Haversine produces reasonable distances."""
        # San Francisco to Oakland is roughly 16km
        dist = haversine_distance(
            37.7749, -122.4194,  # San Francisco
            37.8044, -122.2712   # Oakland
        )
        # Should be roughly 13-16km
        assert 10000 < dist < 20000

    def test_haversine_small_distance(self):
        """Haversine works for small distances."""
        # ~1m north
        lat_offset = 0.000009  # roughly 1m in latitude
        dist = haversine_distance(
            37.7749, -122.4194,
            37.7749 + lat_offset, -122.4194
        )
        assert 0.5 < dist < 2.0  # Should be roughly 1m


class TestHoldMCPFunction:
    """Tests for the MCP tool wrapper function."""

    @pytest.mark.asyncio
    async def test_hold_mcp_wrapper(self, state_machine, telemetry_cache):
        """MCP wrapper function returns JSON string."""
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


class TestHoldErrorHandling:
    """Tests for error handling in hold."""

    @pytest.mark.asyncio
    async def test_hold_without_telemetry(self, flight_tools, telemetry_cache):
        """Handles missing telemetry gracefully."""
        telemetry_cache._data = None

        # Should handle gracefully without crashing
        result = await flight_tools.hold(duration_s=0.2)

        # Without telemetry, it will try to get from drone
        # If no drone connection, it will return an error
        # But it shouldn't crash
        assert isinstance(result, dict)
        assert "success" in result
