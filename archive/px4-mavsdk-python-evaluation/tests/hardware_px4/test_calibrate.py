"""Tests for PX4 calibration script.

Validates:
1. Calibration step order is correct
2. Mock System can be used for testing
3. Calibration sequence runs without error
"""

import asyncio
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestCalibrationSequence:
    """Test calibration step order and definitions."""

    def test_calibration_sequence_order(self) -> None:
        """Calibration steps must be in the correct order.

        Order is important because:
        - Accel calibration updates sensor orientation
        - Gyro should be calibrated after accel
        - Mag requires level orientation
        - Level refines accel results
        """
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        kinds = [step.kind for step in CALIBRATION_SEQUENCE]

        # Expected order
        expected = [
            CalibrationKind.ACCEL,
            CalibrationKind.GYRO,
            CalibrationKind.MAG,
            CalibrationKind.LEVEL,
            CalibrationKind.RC,
            CalibrationKind.MOTOR,
        ]

        assert kinds == expected, f"Wrong order: {kinds}"

    def test_accel_is_first(self) -> None:
        """Accelerometer must be first in sequence."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        assert CALIBRATION_SEQUENCE[0].kind == CalibrationKind.ACCEL

    def test_gyro_is_second(self) -> None:
        """Gyroscope must be second in sequence."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        assert CALIBRATION_SEQUENCE[1].kind == CalibrationKind.GYRO

    def test_motor_is_last(self) -> None:
        """Motor calibration must be last (requires arming)."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        assert CALIBRATION_SEQUENCE[-1].kind == CalibrationKind.MOTOR

    def test_all_required_steps_marked(self) -> None:
        """Critical calibration steps should be marked as required."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        required_kinds = {
            CalibrationKind.ACCEL,
            CalibrationKind.GYRO,
            CalibrationKind.MAG,
            CalibrationKind.MOTOR,
        }

        for step in CALIBRATION_SEQUENCE:
            if step.kind in required_kinds:
                assert step.required, f"{step.kind} should be marked required"


class TestCalibrationInstructions:
    """Test calibration instruction display."""

    def test_accel_has_instructions(self) -> None:
        """Accelerometer calibration should have positioning instructions."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        accel_step = next(
            s for s in CALIBRATION_SEQUENCE if s.kind == CalibrationKind.ACCEL
        )

        assert len(accel_step.instructions) > 0
        # Should mention 6 positions
        assert any("Position 6" in i for i in accel_step.instructions)

    def test_gyro_has_stationary_instruction(self) -> None:
        """Gyro calibration should instruct to keep drone stationary."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        gyro_step = next(
            s for s in CALIBRATION_SEQUENCE if s.kind == CalibrationKind.GYRO
        )

        instructions_text = " ".join(gyro_step.instructions).lower()
        assert "stationary" in instructions_text or "still" in instructions_text

    def test_motor_has_safety_warning(self) -> None:
        """Motor calibration should warn about removing props."""
        from hardware.px4.calibrate import CALIBRATION_SEQUENCE, CalibrationKind

        motor_step = next(
            s for s in CALIBRATION_SEQUENCE if s.kind == CalibrationKind.MOTOR
        )

        instructions_text = " ".join(motor_step.instructions).lower()
        assert "prop" in instructions_text or "remove" in instructions_text


class TestMockSystemCalibration:
    """Test calibration with mocked MAVSDK System."""

    @pytest.fixture
    def mock_drone(self) -> MagicMock:
        """Create a mock MAVSDK System for testing."""
        drone = MagicMock()

        # Mock calibration plugin
        drone.calibration = MagicMock()

        # Mock async generators for calibration progress
        async def mock_calibrate_accel():
            yield MagicMock(progress=0.0)
            yield MagicMock(progress=0.5)
            yield MagicMock(progress=1.0)

        async def mock_calibrate_gyro():
            yield MagicMock(progress=0.0)
            yield MagicMock(progress=1.0)

        async def mock_calibrate_mag():
            yield MagicMock(progress=0.0)
            yield MagicMock(progress=1.0)

        drone.calibration.calibrate_acceleration = mock_calibrate_accel
        drone.calibration.calibrate_gyro = mock_calibrate_gyro
        drone.calibration.calibrate_magnetometer = mock_calibrate_mag

        # Mock core for connection state
        drone.core = MagicMock()

        async def mock_connection_state():
            yield MagicMock(is_connected=True)

        drone.core.connection_state = mock_connection_state

        return drone

    @pytest.mark.asyncio
    async def test_calibrate_accel_with_mock(self, mock_drone: MagicMock) -> None:
        """Accelerometer calibration should run with mock drone."""
        from hardware.px4.calibrate import calibrate_accel

        result = await calibrate_accel(mock_drone)

        assert result.success
        assert "Accelerometer calibration" in result.message

    @pytest.mark.asyncio
    async def test_calibrate_gyro_with_mock(self, mock_drone: MagicMock) -> None:
        """Gyroscope calibration should run with mock drone."""
        from hardware.px4.calibrate import calibrate_gyro

        result = await calibrate_gyro(mock_drone)

        assert result.success
        assert "Gyroscope calibration" in result.message

    @pytest.mark.asyncio
    async def test_calibrate_mag_with_mock(self, mock_drone: MagicMock) -> None:
        """Magnetometer calibration should run with mock drone."""
        from hardware.px4.calibrate import calibrate_mag

        result = await calibrate_mag(mock_drone)

        assert result.success
        assert "Magnetometer calibration" in result.message


class TestDryRunCalibration:
    """Test dry-run calibration mode."""

    def test_dry_run_no_connection(self) -> None:
        """Dry-run should not require MAVSDK connection."""
        from hardware.px4.calibrate import run_calibration

        results = asyncio.run(
            run_calibration(
                system_address="udp://:14540",
                dry_run=True,
            )
        )

        # Should return results without error
        assert len(results) > 0

        # All should be marked as dry-run
        for result in results:
            assert "[DRY-RUN]" in result.message

    def test_dry_run_specific_step(self) -> None:
        """Dry-run can target specific calibration step."""
        from hardware.px4.calibrate import (
            run_calibration,
            CalibrationKind,
        )

        results = asyncio.run(
            run_calibration(
                system_address="udp://:14540",
                steps=[CalibrationKind.ACCEL],
                dry_run=True,
            )
        )

        # Should only have accel result
        assert len(results) == 1
        assert results[0].kind == CalibrationKind.ACCEL
