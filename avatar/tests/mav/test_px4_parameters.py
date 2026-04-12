"""Tests for PX4 Parameter Manager.

Validates parameter definitions, read/write operations, and safety verification.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional

from avatar.mav.px4_parameters import (
    CRITICAL_PARAMETERS,
    OFFBOARD_FAILSAFE_PARAMS,
    RC_FAILSAFE_PARAMS,
    BATTERY_FAILSAFE_PARAMS,
    GEOFENCE_PARAMS,
    DATA_LINK_PARAMS,
    PARAMETER_DESCRIPTIONS,
    PARAMETER_TYPES,
    ParameterStatus,
    PX4ParameterManager,
    PX4ParameterError,
    SafetyError,
    quick_safety_check,
    format_parameter_status,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_drone():
    """Create a mock MAVSDK System with param module."""
    drone = MagicMock()

    # Mock param module
    drone.param = MagicMock()
    drone.param.get_param_int = AsyncMock()
    drone.param.get_param_float = AsyncMock()
    drone.param.set_param_int = AsyncMock()
    drone.param.set_param_float = AsyncMock()

    return drone


@pytest.fixture
def parameter_manager(mock_drone):
    """Create a PX4ParameterManager with mocked drone."""
    return PX4ParameterManager(mock_drone)


# =============================================================================
# Parameter Definitions Tests
# =============================================================================


class TestParameterDefinitions:
    """Validate parameter definition dictionaries."""

    def test_critical_parameters_defined(self):
        """All critical safety parameters must be defined."""
        # Should have parameters from all categories
        assert len(CRITICAL_PARAMETERS) > 0

        # Verify all categories are represented
        offboard_keys = set(OFFBOARD_FAILSAFE_PARAMS.keys())
        rc_keys = set(RC_FAILSAFE_PARAMS.keys())
        battery_keys = set(BATTERY_FAILSAFE_PARAMS.keys())
        geofence_keys = set(GEOFENCE_PARAMS.keys())
        datalink_keys = set(DATA_LINK_PARAMS.keys())

        critical_keys = set(CRITICAL_PARAMETERS.keys())

        assert offboard_keys <= critical_keys, "Offboard params not in critical"
        assert rc_keys <= critical_keys, "RC params not in critical"
        assert battery_keys <= critical_keys, "Battery params not in critical"
        assert geofence_keys <= critical_keys, "Geofence params not in critical"
        assert datalink_keys <= critical_keys, "Data link params not in critical"

    def test_critical_parameters_values_are_valid(self):
        """All parameter values must be numeric."""
        for name, value in CRITICAL_PARAMETERS.items():
            assert isinstance(value, (int, float)), f"{name} has invalid type {type(value)}"
            assert value >= 0 or name in ["GF_ALTMODE"], f"{name} has unexpected negative value"

    def test_parameter_descriptions_exist(self):
        """All critical parameters must have descriptions."""
        for name in CRITICAL_PARAMETERS.keys():
            assert name in PARAMETER_DESCRIPTIONS, f"{name} missing description"
            assert len(PARAMETER_DESCRIPTIONS[name]) > 0, f"{name} has empty description"

    def test_parameter_types_defined(self):
        """All critical parameters must have type definitions."""
        for name in CRITICAL_PARAMETERS.keys():
            assert name in PARAMETER_TYPES, f"{name} missing type definition"
            assert PARAMETER_TYPES[name] in ["int", "float"], f"{name} has invalid type"

    def test_offboard_failsafe_values(self):
        """Offboard failsafe parameters have correct expected values."""
        # COM_OBL_RC_ACT = 3 (Return mode on offboard timeout)
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OBL_RC_ACT"] == 3
        # COM_OF_LOSS_T = 0.5 (500ms timeout)
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OF_LOSS_T"] == 0.5
        # COM_OBL_ACT = 1 (Hold mode)
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OBL_ACT"] == 1

    def test_battery_failsafe_values(self):
        """Battery failsafe parameters have correct expected values."""
        # Low battery 25%
        assert BATTERY_FAILSAFE_PARAMS["BAT_LOW_THR"] == 0.25
        # Critical 15%
        assert BATTERY_FAILSAFE_PARAMS["BAT_CRIT_THR"] == 0.15
        # Emergency 10%
        assert BATTERY_FAILSAFE_PARAMS["BAT_EMERGEN_THR"] == 0.10
        # Min to arm 40%
        assert BATTERY_FAILSAFE_PARAMS["COM_ARM_BAT_MIN"] == 0.40
        # Action: Land
        assert BATTERY_FAILSAFE_PARAMS["COM_LOW_BAT_ACT"] == 2

    def test_geofence_values(self):
        """Geofence parameters have correct expected values."""
        # 500m horizontal
        assert GEOFENCE_PARAMS["GF_MAX_HOR_DIST"] == 500
        # 120m vertical
        assert GEOFENCE_PARAMS["GF_MAX_VER_DIST"] == 120
        # Action: RTL
        assert GEOFENCE_PARAMS["GF_ACTION"] == 3
        # Alt mode: absolute
        assert GEOFENCE_PARAMS["GF_ALTMODE"] == 0

    def test_rc_failsafe_values(self):
        """RC failsafe parameters have correct expected values."""
        # 500ms RC timeout
        assert RC_FAILSAFE_PARAMS["COM_RC_LOSS_T"] == 0.5
        # RTL action
        assert RC_FAILSAFE_PARAMS["NAV_RCL_ACT"] == 2
        # Ignore RC loss in Offboard (bitmask value 4)
        assert RC_FAILSAFE_PARAMS["COM_RCL_EXCEPT"] == 4

    def test_data_link_values(self):
        """Data link failsafe parameters have correct expected values."""
        # 5 second timeout
        assert DATA_LINK_PARAMS["COM_DL_LOSS_T"] == 5.0
        # RTL action
        assert DATA_LINK_PARAMS["NAV_DLL_ACT"] == 2


# =============================================================================
# ParameterStatus Dataclass Tests
# =============================================================================


class TestParameterStatus:
    """Test ParameterStatus dataclass."""

    def test_parameter_status_creation(self):
        """Can create ParameterStatus with all fields."""
        status = ParameterStatus(
            name="COM_OF_LOSS_T",
            expected_value=0.5,
            actual_value=0.5,
            is_valid=True,
            description="Test parameter",
            message="",
        )
        assert status.name == "COM_OF_LOSS_T"
        assert status.expected_value == 0.5
        assert status.actual_value == 0.5
        assert status.is_valid is True
        assert status.description == "Test parameter"

    def test_parameter_status_without_message(self):
        """Can create ParameterStatus without optional message."""
        status = ParameterStatus(
            name="COM_OBL_RC_ACT",
            expected_value=3.0,
            actual_value=1.0,
            is_valid=False,
            description="Test",
        )
        assert status.message == ""  # Default value


# =============================================================================
# PX4ParameterManager Initialization Tests
# =============================================================================


class TestParameterManagerInit:
    """Test PX4ParameterManager initialization."""

    def test_manager_initialization(self, mock_drone):
        """Manager initializes with drone reference."""
        manager = PX4ParameterManager(mock_drone)
        assert manager.drone == mock_drone
        assert manager._param_cache == {}
        assert manager._cache_valid is False

    def test_manager_tolerances_set(self, mock_drone):
        """Manager has tolerance constants defined."""
        manager = PX4ParameterManager(mock_drone)
        assert manager.FLOAT_TOLERANCE == 0.001
        assert manager.FLOAT_RELATIVE_TOLERANCE == 0.001


# =============================================================================
# Get Parameter Tests
# =============================================================================


class TestGetParameter:
    """Test parameter reading functionality."""

    @pytest.mark.asyncio
    async def test_get_int_parameter(self, parameter_manager, mock_drone):
        """Can read integer parameters."""
        mock_drone.param.get_param_int.return_value = 3

        result = await parameter_manager.get_parameter("COM_OBL_RC_ACT")

        assert result == 3.0  # Returned as float
        mock_drone.param.get_param_int.assert_called_once_with("COM_OBL_RC_ACT")

    @pytest.mark.asyncio
    async def test_get_float_parameter(self, parameter_manager, mock_drone):
        """Can read float parameters."""
        mock_drone.param.get_param_float.return_value = 0.5

        result = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result == 0.5
        mock_drone.param.get_param_float.assert_called_once_with("COM_OF_LOSS_T")

    @pytest.mark.asyncio
    async def test_get_parameter_caches_result(self, parameter_manager, mock_drone):
        """Parameter reads are cached."""
        mock_drone.param.get_param_float.return_value = 0.5

        # First read
        result1 = await parameter_manager.get_parameter("COM_OF_LOSS_T")
        # Second read should use cache
        result2 = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result1 == result2 == 0.5
        # Should only call MAVSDK once
        assert mock_drone.param.get_param_float.call_count == 1

    @pytest.mark.asyncio
    async def test_get_parameter_returns_none_on_error(self, parameter_manager, mock_drone):
        """Returns None when parameter read fails."""
        mock_drone.param.get_param_float.side_effect = Exception("Connection lost")

        result = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_parameter_unknown_type_defaults_float(self, parameter_manager, mock_drone):
        """Unknown parameters default to float type."""
        mock_drone.param.get_param_float.return_value = 1.5

        # Parameter not in PARAMETER_TYPES
        result = await parameter_manager.get_parameter("UNKNOWN_PARAM")

        assert result == 1.5
        mock_drone.param.get_param_float.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_parameters(self, parameter_manager, mock_drone):
        """Can read all critical parameters."""
        # Setup mocks to return expected values
        mock_drone.param.get_param_int.return_value = 3
        mock_drone.param.get_param_float.return_value = 0.5

        results = await parameter_manager.get_all_parameters()

        # Should have all critical parameters
        assert len(results) == len(CRITICAL_PARAMETERS)
        assert all(name in results for name in CRITICAL_PARAMETERS.keys())
        assert parameter_manager._cache_valid is True


# =============================================================================
# Set Parameter Tests
# =============================================================================


class TestSetParameter:
    """Test parameter writing functionality."""

    @pytest.mark.asyncio
    async def test_set_int_parameter(self, parameter_manager, mock_drone):
        """Can write integer parameters."""
        mock_drone.param.set_param_int.return_value = None

        result = await parameter_manager.set_parameter("COM_OBL_RC_ACT", 3)

        assert result is True
        mock_drone.param.set_param_int.assert_called_once_with("COM_OBL_RC_ACT", 3)

    @pytest.mark.asyncio
    async def test_set_float_parameter(self, parameter_manager, mock_drone):
        """Can write float parameters."""
        mock_drone.param.set_param_float.return_value = None

        result = await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.5)

        assert result is True
        mock_drone.param.set_param_float.assert_called_once_with("COM_OF_LOSS_T", 0.5)

    @pytest.mark.asyncio
    async def test_set_parameter_invalidates_cache(self, parameter_manager, mock_drone):
        """Setting parameter invalidates the cache."""
        # Pre-populate cache
        parameter_manager._param_cache["COM_OF_LOSS_T"] = 0.5
        parameter_manager._cache_valid = True

        await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.3)

        assert parameter_manager._cache_valid is False

    @pytest.mark.asyncio
    async def test_set_parameter_returns_false_on_error(self, parameter_manager, mock_drone):
        """Returns False when parameter write fails."""
        mock_drone.param.set_param_float.side_effect = Exception("Write failed")

        result = await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.5)

        assert result is False


# =============================================================================
# Parameter Validation Tests
# =============================================================================


class TestParameterValidation:
    """Test parameter check functionality."""

    def test_check_int_parameter_exact_match(self, parameter_manager):
        """Integer parameters require exact match."""
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 3)

        assert status.is_valid is True
        assert status.expected_value == 3.0
        assert status.actual_value == 3.0

    def test_check_int_parameter_mismatch(self, parameter_manager):
        """Integer parameter mismatch detected."""
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 1)

        assert status.is_valid is False
        assert status.message == "Expected 3, got 1"

    def test_check_float_parameter_with_tolerance(self, parameter_manager):
        """Float parameters use tolerance comparison."""
        # 0.5 vs 0.5001 - within tolerance
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, 0.5001)

        assert status.is_valid is True

    def test_check_float_parameter_outside_tolerance(self, parameter_manager):
        """Float parameter outside tolerance detected."""
        # 0.5 vs 0.6 - outside tolerance
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, 0.6)

        assert status.is_valid is False
        assert "Expected 0.5, got 0.6" in status.message

    def test_check_parameter_none_actual(self, parameter_manager):
        """None actual value results in invalid status."""
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, None)

        assert status.is_valid is False
        assert status.actual_value is None
        assert "Could not read parameter" in status.message

    def test_check_parameter_description_included(self, parameter_manager):
        """Status includes parameter description."""
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 3)

        # Description should be the human-readable description from PARAMETER_DESCRIPTIONS
        assert "Offboard loss action" in status.description
        assert "0=disabled" in status.description  # Part of the description


# =============================================================================
# Safety Verification Tests
# =============================================================================


class TestSafetyVerification:
    """Test comprehensive safety verification."""

    @pytest.mark.asyncio
    async def test_verify_safety_parameters_all_valid(self, parameter_manager, mock_drone):
        """All parameters valid when matching expected."""
        # Setup mocks to return expected values
        async def mock_get_int(name):
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_safety_parameters()

        assert len(results) == len(CRITICAL_PARAMETERS)
        assert all(r.is_valid for r in results)

    @pytest.mark.asyncio
    async def test_verify_safety_parameters_some_invalid(self, parameter_manager, mock_drone):
        """Detects invalid parameters."""
        # Setup to return wrong value for one parameter
        async def mock_get_int(name):
            if name == "COM_OBL_RC_ACT":
                return 1  # Wrong! Should be 3
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_safety_parameters()

        com_obl = [r for r in results if r.name == "COM_OBL_RC_ACT"][0]
        assert com_obl.is_valid is False

        # Others should be valid
        others = [r for r in results if r.name != "COM_OBL_RC_ACT"]
        assert all(r.is_valid for r in others)

    @pytest.mark.asyncio
    async def test_configure_safety_parameters(self, parameter_manager, mock_drone):
        """Configure sets all parameters to expected values."""
        # Track what was set
        set_values: Dict[str, float] = {}

        async def mock_set_int(name, value):
            set_values[name] = float(value)

        async def mock_set_float(name, value):
            set_values[name] = float(value)

        # Return the expected values (simulating successful write)
        async def mock_get_int(name):
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.set_param_int = mock_set_int
        mock_drone.param.set_param_float = mock_set_float
        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.configure_safety_parameters()

        # All should be valid (successful write + matching read)
        assert all(r.is_valid for r in results)
        # All critical parameters should have been set
        assert all(name in set_values for name in CRITICAL_PARAMETERS.keys())

    @pytest.mark.asyncio
    async def test_parameter_diff_detection(self, parameter_manager, mock_drone):
        """Diff detection returns only invalid parameters."""
        # Setup one wrong parameter
        async def mock_get_int(name):
            if name == "COM_OBL_RC_ACT":
                return 1  # Wrong!
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        diff = await parameter_manager.get_parameter_diff()

        assert len(diff) == 1
        assert diff[0].name == "COM_OBL_RC_ACT"


# =============================================================================
# Category-Specific Verification Tests
# =============================================================================


class TestCategoryVerification:
    """Test category-specific verification methods."""

    @pytest.mark.asyncio
    async def test_verify_offboard_failsafe(self, parameter_manager, mock_drone):
        """Verify offboard failsafe parameters."""
        async def mock_get_int(name):
            return int(OFFBOARD_FAILSAFE_PARAMS.get(name, 0))

        async def mock_get_float(name):
            return float(OFFBOARD_FAILSAFE_PARAMS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_offboard_failsafe()

        assert len(results) == len(OFFBOARD_FAILSAFE_PARAMS)
        assert all(r.is_valid for r in results)

    @pytest.mark.asyncio
    async def test_verify_battery_failsafe(self, parameter_manager, mock_drone):
        """Verify battery failsafe parameters."""
        async def mock_get_int(name):
            return int(BATTERY_FAILSAFE_PARAMS.get(name, 0))

        async def mock_get_float(name):
            return float(BATTERY_FAILSAFE_PARAMS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_battery_failsafe()

        assert len(results) == len(BATTERY_FAILSAFE_PARAMS)
        assert all(r.is_valid for r in results)

    @pytest.mark.asyncio
    async def test_verify_geofence(self, parameter_manager, mock_drone):
        """Verify geofence parameters."""
        async def mock_get_int(name):
            return int(GEOFENCE_PARAMS.get(name, 0))

        async def mock_get_float(name):
            return float(GEOFENCE_PARAMS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_geofence()

        assert len(results) == len(GEOFENCE_PARAMS)
        assert all(r.is_valid for r in results)

    @pytest.mark.asyncio
    async def test_verify_rc_failsafe(self, parameter_manager, mock_drone):
        """Verify RC failsafe parameters."""
        async def mock_get_int(name):
            return int(RC_FAILSAFE_PARAMS.get(name, 0))

        async def mock_get_float(name):
            return float(RC_FAILSAFE_PARAMS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_rc_failsafe()

        assert len(results) == len(RC_FAILSAFE_PARAMS)
        assert all(r.is_valid for r in results)

    @pytest.mark.asyncio
    async def test_verify_data_link_failsafe(self, parameter_manager, mock_drone):
        """Verify data link failsafe parameters."""
        async def mock_get_int(name):
            return int(DATA_LINK_PARAMS.get(name, 0))

        async def mock_get_float(name):
            return float(DATA_LINK_PARAMS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        results = await parameter_manager.verify_data_link_failsafe()

        assert len(results) == len(DATA_LINK_PARAMS)
        assert all(r.is_valid for r in results)


# =============================================================================
# Utility Method Tests
# =============================================================================


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_is_safety_configured_all_valid(self, parameter_manager):
        """Returns True when all parameters valid."""
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 2.0, True, "Test 2"),
        ]
        assert parameter_manager.is_safety_configured(results) is True

    def test_is_safety_configured_some_invalid(self, parameter_manager):
        """Returns False when any parameter invalid."""
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 1.0, False, "Test 2"),
        ]
        assert parameter_manager.is_safety_configured(results) is False

    def test_get_safety_summary_all_valid(self, parameter_manager):
        """Summary correct when all valid."""
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 2.0, True, "Test 2"),
        ]
        summary = parameter_manager.get_safety_summary(results)

        assert summary["total_parameters"] == 2
        assert summary["valid_count"] == 2
        assert summary["invalid_count"] == 0
        assert summary["is_safe"] is True
        assert summary["invalid_parameters"] == []

    def test_get_safety_summary_with_invalid(self, parameter_manager):
        """Summary lists invalid parameters."""
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 1.0, False, "Test 2", "Mismatch"),
        ]
        summary = parameter_manager.get_safety_summary(results)

        assert summary["total_parameters"] == 2
        assert summary["valid_count"] == 1
        assert summary["invalid_count"] == 1
        assert summary["is_safe"] is False
        assert len(summary["invalid_parameters"]) == 1
        assert summary["invalid_parameters"][0]["name"] == "P2"

    def test_clear_cache(self, parameter_manager):
        """Clear cache removes all cached data."""
        parameter_manager._param_cache = {"P1": 1.0, "P2": 2.0}
        parameter_manager._cache_valid = True

        parameter_manager.clear_cache()

        assert parameter_manager._param_cache == {}
        assert parameter_manager._cache_valid is False


# =============================================================================
# Standalone Function Tests
# =============================================================================


class TestStandaloneFunctions:
    """Test standalone utility functions."""

    @pytest.mark.asyncio
    async def test_quick_safety_check(self, mock_drone):
        """Quick check returns boolean and results."""
        async def mock_get_int(name):
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        is_safe, results = await quick_safety_check(mock_drone)

        assert is_safe is True
        assert len(results) == len(CRITICAL_PARAMETERS)

    def test_format_parameter_status_valid(self):
        """Format valid status nicely."""
        status = ParameterStatus("COM_OF_LOSS_T", 0.5, 0.5, True, "Timeout")
        formatted = format_parameter_status(status)

        assert "[OK]" in formatted
        assert "COM_OF_LOSS_T" in formatted
        assert "0.5000" in formatted
        assert "Timeout" in formatted

    def test_format_parameter_status_invalid(self):
        """Format invalid status with failure indicator."""
        status = ParameterStatus("COM_OBL_RC_ACT", 3.0, 1.0, False, "Action")
        formatted = format_parameter_status(status)

        assert "[FAIL]" in formatted
        assert "COM_OBL_RC_ACT" in formatted


# =============================================================================
# Integration-Like Tests
# =============================================================================


class TestIntegrationScenarios:
    """Test realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_preflight_safety_check_workflow(self, parameter_manager, mock_drone):
        """Complete pre-flight safety check workflow."""
        # Drone has correct parameters
        async def mock_get_int(name):
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        # 1. Verify all parameters
        results = await parameter_manager.verify_safety_parameters()

        # 2. Check if safe to fly
        is_safe = parameter_manager.is_safety_configured(results)
        assert is_safe is True

        # 3. Get summary for logging
        summary = parameter_manager.get_safety_summary(results)
        assert summary["is_safe"] is True

    @pytest.mark.asyncio
    async def test_parameter_mismatch_workflow(self, parameter_manager, mock_drone):
        """Handle parameter mismatch scenario."""
        # Drone has wrong offboard action
        async def mock_get_int(name):
            if name == "COM_OBL_RC_ACT":
                return 1  # Wrong - should be 3
            return int(CRITICAL_PARAMETERS.get(name, 0))

        async def mock_get_float(name):
            return float(CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        # Check safety
        results = await parameter_manager.verify_safety_parameters()
        is_safe = parameter_manager.is_safety_configured(results)

        assert is_safe is False

        # Get diff
        diff = await parameter_manager.get_parameter_diff()
        assert len(diff) == 1
        assert diff[0].name == "COM_OBL_RC_ACT"

    @pytest.mark.asyncio
    async def test_end_to_end_configuration(self, parameter_manager, mock_drone):
        """Configure parameters from scratch."""
        # Track what gets set
        current_values: Dict[str, float] = {}

        async def mock_set_int(name, value):
            current_values[name] = float(value)

        async def mock_set_float(name, value):
            current_values[name] = float(value)

        async def mock_get_int(name):
            return int(current_values.get(name, CRITICAL_PARAMETERS.get(name, 0)))

        async def mock_get_float(name):
            return current_values.get(name, CRITICAL_PARAMETERS.get(name, 0))

        mock_drone.param.set_param_int = mock_set_int
        mock_drone.param.set_param_float = mock_set_float
        mock_drone.param.get_param_int = mock_get_int
        mock_drone.param.get_param_float = mock_get_float

        # Configure
        results = await parameter_manager.configure_safety_parameters()

        # Verify all were set
        for name, expected in CRITICAL_PARAMETERS.items():
            assert name in current_values, f"{name} was not set"
            assert current_values[name] == float(expected), f"{name} has wrong value"

        # All results should be valid
        assert all(r.is_valid for r in results)
