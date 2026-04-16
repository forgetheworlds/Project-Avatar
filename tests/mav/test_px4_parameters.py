"""Tests for PX4 Parameter Manager.

Validates parameter definitions, read/write operations, and safety verification.
"""

# =============================================================================
# IMPORTS AND MODULE UNDER TEST
# =============================================================================
# These tests validate the PX4ParameterManager which handles PX4 flight controller
# configuration. PX4 parameters are persistent settings stored in the flight
# controller that control everything from failsafe behavior to geofence limits.
# Getting these wrong can result in crashes or flyaways.

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional

from avatar.mav.px4_parameters import (
    # Parameter category dictionaries - each groups related safety settings
    CRITICAL_PARAMETERS,        # All safety params combined (master list)
    OFFBOARD_FAILSAFE_PARAMS,   # Offboard control loss behavior
    RC_FAILSAFE_PARAMS,         # Radio control loss behavior
    BATTERY_FAILSAFE_PARAMS,    # Low battery actions
    GEOFENCE_PARAMS,            # Geofence boundaries
    DATA_LINK_PARAMS,           # Data link loss behavior
    # Metadata and types
    PARAMETER_DESCRIPTIONS,     # Human-readable descriptions
    PARAMETER_TYPES,            # int vs float type definitions
    # Core classes and functions
    ParameterStatus,            # Dataclass for validation results
    PX4ParameterManager,        # Main manager class
    PX4ParameterError,          # Custom exception
    SafetyError,                # Safety-specific errors
    quick_safety_check,         # Convenience function
    format_parameter_status,    # Output formatting
)


# =============================================================================
# FIXTURES - Mock Setup for Testing
# =============================================================================
# We use mocks to simulate MAVSDK interactions without needing a real drone.
# This allows fast, repeatable tests without hardware dependencies.


@pytest.fixture
def mock_drone():
    """Create a mock MAVSDK System with param module.

    The param module provides:
    - get_param_int(): Read integer parameters from PX4
    - get_param_float(): Read float parameters from PX4
    - set_param_int(): Write integer parameters to PX4
    - set_param_float(): Write float parameters to PX4

    These methods interact with PX4's parameter database over MAVLink.
    """
    drone = MagicMock()

    # Mock param module with AsyncMock since MAVSDK calls are async
    drone.param = MagicMock()
    drone.param.get_param_int = AsyncMock()
    drone.param.get_param_float = AsyncMock()
    drone.param.set_param_int = AsyncMock()
    drone.param.set_param_float = AsyncMock()

    return drone


@pytest.fixture
def parameter_manager(mock_drone):
    """Create a PX4ParameterManager with mocked drone.

    The manager provides a high-level interface for:
    - Reading/writing parameters with type safety
    - Validating configuration against expected values
    - Caching to reduce MAVLink traffic
    - Generating safety reports
    """
    return PX4ParameterManager(mock_drone)


# =============================================================================
# PARAMETER DEFINITIONS TESTS
# =============================================================================
# These tests validate that all safety-critical parameters are properly defined.
# Each parameter controls a specific safety behavior in the flight controller.


class TestParameterDefinitions:
    """Validate parameter definition dictionaries.

    PX4 parameters are key-value pairs stored in the flight controller's
    persistent memory. They control behavior during:
    - Offboard control loss (COM_* params)
    - RC link loss (NAV_RCL_* params)
    - Battery emergencies (BAT_* params)
    - Geofence violations (GF_* params)
    - Data link loss (COM_DL_* params)

    WHY THIS MATTERS: Incorrect parameters can cause:
    - Drone not responding to offboard commands
    - Flyaway on communication loss (wrong failsafe action)
    - Crash on low battery (no auto-land)
    - Violation of altitude/position limits (no geofence)
    """

    def test_critical_parameters_defined(self):
        """All critical safety parameters must be defined.

        CRITICAL_PARAMETERS combines all safety params into one master dict.
        This ensures we don't miss any safety configuration.

        Categories covered:
        - Offboard failsafe: What to do when MAVSDK commands stop
        - RC failsafe: Behavior when pilot radio disconnects
        - Battery failsafe: Actions at low/critical battery levels
        - Geofence: Virtual boundaries to contain the drone
        - Data link: Actions when telemetry disconnects
        """
        # Should have parameters from all categories
        assert len(CRITICAL_PARAMETERS) > 0

        # Verify all categories are represented in master list
        offboard_keys = set(OFFBOARD_FAILSAFE_PARAMS.keys())
        rc_keys = set(RC_FAILSAFE_PARAMS.keys())
        battery_keys = set(BATTERY_FAILSAFE_PARAMS.keys())
        geofence_keys = set(GEOFENCE_PARAMS.keys())
        datalink_keys = set(DATA_LINK_PARAMS.keys())

        critical_keys = set(CRITICAL_PARAMETERS.keys())

        # Each category must be a subset of critical parameters
        assert offboard_keys <= critical_keys, "Offboard params not in critical"
        assert rc_keys <= critical_keys, "RC params not in critical"
        assert battery_keys <= critical_keys, "Battery params not in critical"
        assert geofence_keys <= critical_keys, "Geofence params not in critical"
        assert datalink_keys <= critical_keys, "Data link params not in critical"

    def test_critical_parameters_values_are_valid(self):
        """All parameter values must be numeric.

        PX4 expects numeric values (int or float). Invalid types would
        cause MAVSDK errors or undefined behavior.

        Most parameters are positive, except GF_ALTMODE which uses
        0/1 enum values (0=absolute altitude, 1=relative to home).
        """
        for name, value in CRITICAL_PARAMETERS.items():
            assert isinstance(value, (int, float)), f"{name} has invalid type {type(value)}"
            assert value >= 0 or name in ["GF_ALTMODE"], f"{name} has unexpected negative value"

    def test_parameter_descriptions_exist(self):
        """All critical parameters must have descriptions.

        Descriptions are displayed in safety reports and help operators
        understand what each parameter controls. Without descriptions,
        safety checks become meaningless numbers.
        """
        for name in CRITICAL_PARAMETERS.keys():
            assert name in PARAMETER_DESCRIPTIONS, f"{name} missing description"
            assert len(PARAMETER_DESCRIPTIONS[name]) > 0, f"{name} has empty description"

    def test_parameter_types_defined(self):
        """All critical parameters must have type definitions.

        PX4 stores parameters as either int or float. Using the wrong
        type can cause precision loss (storing 0.5 as int gives 0)
        or overflow (large ints as floats may lose precision).

        The type determines which MAVSDK method to use:
        - "int" -> get_param_int() / set_param_int()
        - "float" -> get_param_float() / set_param_float()
        """
        for name in CRITICAL_PARAMETERS.keys():
            assert name in PARAMETER_TYPES, f"{name} missing type definition"
            assert PARAMETER_TYPES[name] in ["int", "float"], f"{name} has invalid type"

    def test_offboard_failsafe_values(self):
        """Offboard failsafe parameters have correct expected values.

        Offboard mode is when the drone is controlled by MAVSDK/API commands
        rather than RC transmitter. These parameters define what happens
        if offboard commands stop arriving.

        COM_OBL_RC_ACT = 3 (Return mode on offboard timeout)
        - If offboard commands stop, switch to Return-to-Launch (RTL)
        - Value 3 = RTL mode (safe return home)

        COM_OF_LOSS_T = 0.5 (500ms timeout)
        - Wait only 500ms before triggering failsafe
        - Short timeout ensures quick response to comm loss

        COM_OBL_ACT = 1 (Hold mode)
        - Initial action when offboard lost: enter Hold mode
        - Value 1 = Hold (hover in place before RTL)
        """
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OBL_RC_ACT"] == 3
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OF_LOSS_T"] == 0.5
        assert OFFBOARD_FAILSAFE_PARAMS["COM_OBL_ACT"] == 1

    def test_battery_failsafe_values(self):
        """Battery failsafe parameters have correct expected values.

        These define progressive emergency actions as battery depletes.
        Set conservatively for safety (alerts well before critical).

        BAT_LOW_THR = 0.25 (Low battery at 25% remaining)
        - Triggers low battery warning
        - Should return to home soon after this

        BAT_CRIT_THR = 0.15 (Critical at 15% remaining)
        - Immediate landing required
        - May start emergency descent

        BAT_EMERGEN_THR = 0.10 (Emergency at 10% remaining)
        - Force land regardless of position
        - May cut motors if unable to land

        COM_ARM_BAT_MIN = 0.40 (Minimum 40% to arm)
        - Prevents takeoff with low battery
        - Safety margin for planned mission

        COM_LOW_BAT_ACT = 2 (Action: Land)
        - Value 2 = Land mode (descend at current position)
        - Alternative: 1=Return (RTL), 0=Warning only (dangerous!)
        """
        assert BATTERY_FAILSAFE_PARAMS["BAT_LOW_THR"] == 0.25
        assert BATTERY_FAILSAFE_PARAMS["BAT_CRIT_THR"] == 0.15
        assert BATTERY_FAILSAFE_PARAMS["BAT_EMERGEN_THR"] == 0.10
        assert BATTERY_FAILSAFE_PARAMS["COM_ARM_BAT_MIN"] == 0.40
        assert BATTERY_FAILSAFE_PARAMS["COM_LOW_BAT_ACT"] == 2

    def test_geoffence_values(self):
        """Geofence parameters have correct expected values.

        Geofence creates a virtual cylinder that the drone cannot leave.
        Critical for safety and legal compliance (especially altitude).

        GF_MAX_HOR_DIST = 500 (500m horizontal limit)
        - Maximum distance from home point in meters
        - Beyond this, RTL is triggered

        GF_MAX_VER_DIST = 120 (120m vertical limit)
        - Maximum altitude in meters
        - 120m keeps under FAA 400ft limit (with margin)

        GF_ACTION = 3 (Action: RTL)
        - Value 3 = Return to Launch
        - Other values: 1=Warning, 2=Hold, 4=Terminate (kill motors!)

        GF_ALTMODE = 0 (Alt mode: absolute)
        - Value 0 = Absolute altitude (AMSL)
        - Value 1 = Relative to home (safer for ground obstacles)
        """
        assert GEOFENCE_PARAMS["GF_MAX_HOR_DIST"] == 500
        assert GEOFENCE_PARAMS["GF_MAX_VER_DIST"] == 120
        assert GEOFENCE_PARAMS["GF_ACTION"] == 3
        assert GEOFENCE_PARAMS["GF_ALTMODE"] == 0

    def test_rc_failsafe_values(self):
        """RC failsafe parameters have correct expected values.

        Defines behavior when pilot radio control link is lost.
        Critical for maintaining control authority.

        COM_RC_LOSS_T = 0.5 (500ms RC timeout)
        - Time without RC signal before failsafe triggers
        - Short timeout for quick response

        NAV_RCL_ACT = 2 (RTL action)
        - Value 2 = Return to Launch
        - Drone returns home if pilot loses control

        COM_RCL_EXCEPT = 4 (Bitmask: 4 = ignore RC loss in Offboard)
        - When in offboard mode, don't RTL on RC loss
        - Allows autonomous missions without RC link
        - Critical for pure offboard/API control
        """
        assert RC_FAILSAFE_PARAMS["COM_RC_LOSS_T"] == 0.5
        assert RC_FAILSAFE_PARAMS["NAV_RCL_ACT"] == 2
        assert RC_FAILSAFE_PARAMS["COM_RCL_EXCEPT"] == 4

    def test_data_link_values(self):
        """Data link failsafe parameters have correct expected values.

        Data link is the telemetry connection (MAVLink over radio/WiFi).
        Different from RC - this is the ground station connection.

        COM_DL_LOSS_T = 5.0 (5 second timeout)
        - Longer than RC timeout (5s vs 0.5s)
        - Allows for brief telemetry dropouts
        - Still returns home if connection truly lost

        NAV_DLL_ACT = 2 (RTL action)
        - Value 2 = Return to Launch
        - Ensures drone returns if ground station disconnects
        """
        assert DATA_LINK_PARAMS["COM_DL_LOSS_T"] == 5.0
        assert DATA_LINK_PARAMS["NAV_DLL_ACT"] == 2


# =============================================================================
# PARAMETERSTATUS DATACLASS TESTS
# =============================================================================
# ParameterStatus captures the result of validating a parameter against
# its expected value. Used throughout the safety verification system.


class TestParameterStatus:
    """Test ParameterStatus dataclass.

    ParameterStatus tracks validation results:
    - name: Parameter name (e.g., "COM_OF_LOSS_T")
    - expected_value: What value should be set
    - actual_value: What value was read from drone
    - is_valid: Whether actual matches expected (within tolerance)
    - description: Human-readable explanation
    - message: Error/warning message if invalid
    """

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
        """Can create ParameterStatus without optional message.

        Message field is optional - empty string default means
        no issues or warnings to report.
        """
        status = ParameterStatus(
            name="COM_OBL_RC_ACT",
            expected_value=3.0,
            actual_value=1.0,
            is_valid=False,
            description="Test",
        )
        assert status.message == ""  # Default value


# =============================================================================
# PX4PARAMETERMANAGER INITIALIZATION TESTS
# =============================================================================
# Tests for creating and configuring the parameter manager.


class TestParameterManagerInit:
    """Test PX4ParameterManager initialization.

    The manager requires a MAVSDK System instance (drone) and maintains:
    - Reference to drone for MAVLink communication
    - Parameter cache to avoid repeated reads
    - Tolerance values for float comparison
    """

    def test_manager_initialization(self, mock_drone):
        """Manager initializes with drone reference.

        On creation:
        - Stores drone reference for MAVSDK calls
        - Initializes empty parameter cache
        - Marks cache as invalid (needs population)
        """
        manager = PX4ParameterManager(mock_drone)
        assert manager.drone == mock_drone
        assert manager._param_cache == {}
        assert manager._cache_valid is False

    def test_manager_tolerances_set(self, mock_drone):
        """Manager has tolerance constants defined.

        Float parameters use tolerance comparison because:
        - MAVLink may truncate precision
        - PX4 internal representation may differ slightly
        - Direct equality would cause false negatives

        FLOAT_TOLERANCE = 0.001 (absolute tolerance)
        FLOAT_RELATIVE_TOLERANCE = 0.001 (relative tolerance)
        """
        manager = PX4ParameterManager(mock_drone)
        assert manager.FLOAT_TOLERANCE == 0.001
        assert manager.FLOAT_RELATIVE_TOLERANCE == 0.001


# =============================================================================
# GET PARAMETER TESTS
# =============================================================================
# Tests for reading parameters from the flight controller.
# Uses MAVSDK param module with type-aware method selection.


class TestGetParameter:
    """Test parameter reading functionality.

    Reading parameters uses MAVSDK:
    - get_param_int() for integer parameters
    - get_param_float() for float parameters

    The manager automatically selects the correct method based on
    PARAMETER_TYPES dictionary lookup.
    """

    @pytest.mark.asyncio
    async def test_get_int_parameter(self, parameter_manager, mock_drone):
        """Can read integer parameters.

        Integer parameters (COM_OBL_RC_ACT=3) are read via get_param_int()
        but returned as float for uniform handling.
        """
        mock_drone.param.get_param_int.return_value = 3

        result = await parameter_manager.get_parameter("COM_OBL_RC_ACT")

        assert result == 3.0  # Returned as float for uniform type
        mock_drone.param.get_param_int.assert_called_once_with("COM_OBL_RC_ACT")

    @pytest.mark.asyncio
    async def test_get_float_parameter(self, parameter_manager, mock_drone):
        """Can read float parameters.

        Float parameters (COM_OF_LOSS_T=0.5) use get_param_float().
        These are typically timeouts and thresholds.
        """
        mock_drone.param.get_param_float.return_value = 0.5

        result = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result == 0.5
        mock_drone.param.get_param_float.assert_called_once_with("COM_OF_LOSS_T")

    @pytest.mark.asyncio
    async def test_get_parameter_caches_result(self, parameter_manager, mock_drone):
        """Parameter reads are cached.

        Caching reduces MAVLink traffic:
        - First read: Query from PX4 over MAVLink
        - Subsequent reads: Return cached value
        - Cache invalidated on parameter write

        This is important because:
        - MAVLink has limited bandwidth
        - Parameter reads are slow (round-trip to FC)
        - Multiple checks shouldn't repeat queries
        """
        mock_drone.param.get_param_float.return_value = 0.5

        # First read - queries PX4
        result1 = await parameter_manager.get_parameter("COM_OF_LOSS_T")
        # Second read - uses cache, no MAVLink call
        result2 = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result1 == result2 == 0.5
        # Should only call MAVSDK once
        assert mock_drone.param.get_param_float.call_count == 1

    @pytest.mark.asyncio
    async def test_get_parameter_returns_none_on_error(self, parameter_manager, mock_drone):
        """Returns None when parameter read fails.

        Read failures can occur due to:
        - Connection lost (USB/telemetry disconnect)
        - Parameter doesn't exist on this PX4 version
        - MAVLink timeout

        None indicates "could not determine value" for safety checks.
        """
        mock_drone.param.get_param_float.side_effect = Exception("Connection lost")

        result = await parameter_manager.get_parameter("COM_OF_LOSS_T")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_parameter_unknown_type_defaults_float(self, parameter_manager, mock_drone):
        """Unknown parameters default to float type.

        If a parameter isn't in PARAMETER_TYPES, we assume float.
        This is safer because:
        - Float can represent int values (3.0)
        - Int cannot represent float values (0.5)
        - Most custom parameters are floats
        """
        mock_drone.param.get_param_float.return_value = 1.5

        # Parameter not in PARAMETER_TYPES
        result = await parameter_manager.get_parameter("UNKNOWN_PARAM")

        assert result == 1.5
        mock_drone.param.get_param_float.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_parameters(self, parameter_manager, mock_drone):
        """Can read all critical parameters.

        get_all_parameters() reads every parameter in CRITICAL_PARAMETERS.
        Used for comprehensive safety verification.

        Returns dict: {param_name: value_or_None}
        """
        # Setup mocks to return expected values
        mock_drone.param.get_param_int.return_value = 3
        mock_drone.param.get_param_float.return_value = 0.5

        results = await parameter_manager.get_all_parameters()

        # Should have all critical parameters
        assert len(results) == len(CRITICAL_PARAMETERS)
        assert all(name in results for name in CRITICAL_PARAMETERS.keys())
        assert parameter_manager._cache_valid is True


# =============================================================================
# SET PARAMETER TESTS
# =============================================================================
# Tests for writing parameters to the flight controller.
# Writing parameters requires arming state check (cannot write while armed).


class TestSetParameter:
    """Test parameter writing functionality.

    Writing parameters:
    - Uses set_param_int() or set_param_float()
    - Requires drone to be disarmed (safety feature)
    - Invalidates cache (values changed)
    - Persists to PX4 EEPROM (survives reboot)
    """

    @pytest.mark.asyncio
    async def test_set_int_parameter(self, parameter_manager, mock_drone):
        """Can write integer parameters.

        Integer writes used for:
        - Action enums (what mode to enter)
        - Boolean flags (0/1 values)
        - Discrete settings
        """
        mock_drone.param.set_param_int.return_value = None

        result = await parameter_manager.set_parameter("COM_OBL_RC_ACT", 3)

        assert result is True
        mock_drone.param.set_param_int.assert_called_once_with("COM_OBL_RC_ACT", 3)

    @pytest.mark.asyncio
    async def test_set_float_parameter(self, parameter_manager, mock_drone):
        """Can write float parameters.

        Float writes used for:
        - Timeouts (seconds)
        - Thresholds (battery %, distances)
        - Continuous values
        """
        mock_drone.param.set_param_float.return_value = None

        result = await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.5)

        assert result is True
        mock_drone.param.set_param_float.assert_called_once_with("COM_OF_LOSS_T", 0.5)

    @pytest.mark.asyncio
    async def test_set_parameter_invalidates_cache(self, parameter_manager, mock_drone):
        """Setting parameter invalidates the cache.

        When a parameter is written:
        1. Cache is marked invalid
        2. Next read will query PX4 (not use stale cache)
        3. Ensures verification reads actual written value

        This prevents the "write succeeded but verify failed" bug where
        we read old cached values instead of new values.
        """
        # Pre-populate cache
        parameter_manager._param_cache["COM_OF_LOSS_T"] = 0.5
        parameter_manager._cache_valid = True

        await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.3)

        assert parameter_manager._cache_valid is False

    @pytest.mark.asyncio
    async def test_set_parameter_returns_false_on_error(self, parameter_manager, mock_drone):
        """Returns False when parameter write fails.

        Write failures can occur due to:
        - Drone is armed (PX4 blocks writes while armed)
        - Connection lost
        - Invalid value (out of range)
        - Read-only parameter
        """
        mock_drone.param.set_param_float.side_effect = Exception("Write failed")

        result = await parameter_manager.set_parameter("COM_OF_LOSS_T", 0.5)

        assert result is False


# =============================================================================
# PARAMETER VALIDATION TESTS
# =============================================================================
# Tests for comparing expected vs actual parameter values.
# Core to safety verification - determines if drone is safe to fly.


class TestParameterValidation:
    """Test parameter check functionality.

    check_parameter() compares expected vs actual values:
    - Integers: Must match exactly
    - Floats: Must be within tolerance (0.001)

    Returns ParameterStatus with validation result.
    """

    def test_check_int_parameter_exact_match(self, parameter_manager):
        """Integer parameters require exact match.

        Integer params are discrete values (action enums, modes).
        There is no "close enough" - 3 (RTL) vs 1 (Hold) is a safety issue.
        """
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 3)

        assert status.is_valid is True
        assert status.expected_value == 3.0
        assert status.actual_value == 3.0

    def test_check_int_parameter_mismatch(self, parameter_manager):
        """Integer parameter mismatch detected.

        Mismatch means safety behavior is wrong.
        e.g., COM_OBL_RC_ACT=1 (Hold) instead of 3 (RTL)
        means drone won't return home on offboard loss.
        """
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 1)

        assert status.is_valid is False
        assert status.message == "Expected 3, got 1"

    def test_check_float_parameter_with_tolerance(self, parameter_manager):
        """Float parameters use tolerance comparison.

        Floats have precision issues, so we use tolerance:
        - Absolute tolerance: 0.001 (values within 0.001 are equal)
        - Relative tolerance: 0.001 (1% relative difference allowed)

        0.5 vs 0.5001: Within tolerance, considered equal.
        """
        # 0.5 vs 0.5001 - within tolerance
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, 0.5001)

        assert status.is_valid is True

    def test_check_float_parameter_outside_tolerance(self, parameter_manager):
        """Float parameter outside tolerance detected.

        0.5 vs 0.6: Outside tolerance (0.1 difference > 0.001).
        This would indicate wrong timeout value.
        """
        # 0.5 vs 0.6 - outside tolerance
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, 0.6)

        assert status.is_valid is False
        assert "Expected 0.5, got 0.6" in status.message

    def test_check_parameter_none_actual(self, parameter_manager):
        """None actual value results in invalid status.

        If we couldn't read the parameter (None), the check fails.
        "Could not read parameter" message indicates communication issue.
        """
        status = parameter_manager.check_parameter("COM_OF_LOSS_T", 0.5, None)

        assert status.is_valid is False
        assert status.actual_value is None
        assert "Could not read parameter" in status.message

    def test_check_parameter_description_included(self, parameter_manager):
        """Status includes parameter description.

        Description comes from PARAMETER_DESCRIPTIONS and explains
        what the parameter controls in human terms.

        Example: COM_OBL_RC_ACT description includes:
        - "Offboard loss action"
        - "0=disabled, 1=Hold, 2=Land, 3=Return"
        """
        status = parameter_manager.check_parameter("COM_OBL_RC_ACT", 3, 3)

        # Description should be the human-readable description from PARAMETER_DESCRIPTIONS
        assert "Offboard loss action" in status.description
        assert "0=disabled" in status.description  # Part of the description


# =============================================================================
# SAFETY VERIFICATION TESTS
# =============================================================================
# Tests for comprehensive safety parameter verification.
# These are the main entry points for pre-flight safety checks.


class TestSafetyVerification:
    """Test comprehensive safety verification.

    verify_safety_parameters() is the main pre-flight check:
    1. Reads all CRITICAL_PARAMETERS from PX4
    2. Compares each to expected value
    3. Returns list of ParameterStatus
    4. All must be valid for safe flight

    configure_safety_parameters() sets all parameters:
    1. Writes each CRITICAL_PARAMETER to PX4
    2. Verifies write succeeded
    3. Returns validation results
    """

    @pytest.mark.asyncio
    async def test_verify_safety_parameters_all_valid(self, parameter_manager, mock_drone):
        """All parameters valid when matching expected.

        This is the "happy path" - drone is correctly configured.
        All safety parameters match expected values.
        """
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
        """Detects invalid parameters.

        This test simulates a misconfigured drone:
        - COM_OBL_RC_ACT = 1 (Hold) instead of 3 (RTL)
        - This is dangerous - drone won't return home!

        The test verifies:
        1. Invalid parameter is detected
        2. Other parameters still validated
        3. Returns detailed status for each
        """
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
        """Configure sets all parameters to expected values.

        This is the "fix" operation - writes all safety parameters
        to their correct values, then verifies they were set.

        Used when:
        - Initial drone setup
        - After parameter reset
        - Safety check failed, need to fix
        """
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
        """Diff detection returns only invalid parameters.

        get_parameter_diff() is used to see what's wrong:
        - Returns only parameters that don't match expected
        - Empty list means everything is correct
        - Useful for incremental fixing
        """
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
# CATEGORY-SPECIFIC VERIFICATION TESTS
# =============================================================================
# Tests for checking specific safety categories independently.
# Allows partial verification (e.g., just geofence for outdoor flight).


class TestCategoryVerification:
    """Test category-specific verification methods.

    Each category has its own verify method:
    - verify_offboard_failsafe(): API/MAVSDK control safety
    - verify_battery_failsafe(): Power management
    - verify_geofence(): Boundary enforcement
    - verify_rc_failsafe(): Radio control backup
    - verify_data_link_failsafe(): Telemetry monitoring

    These allow checking specific aspects without full verification.
    """

    @pytest.mark.asyncio
    async def test_verify_offboard_failsafe(self, parameter_manager, mock_drone):
        """Verify offboard failsafe parameters.

        Critical for Avatar because we use offboard (MAVSDK) control.
        Wrong settings here could cause:
        - Drone continuing without commands (freeze)
        - Wrong action on comm loss (hold vs RTL)
        - Too long timeout (delayed response)
        """
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
        """Verify battery failsafe parameters.

        Prevents crashes from power loss:
        - Return home at 25% (time to get back)
        - Land at 15% (emergency)
        - Force land at 10% (imminent crash)
        - Block arming below 40% (prevent low-battery takeoff)
        """
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
        """Verify geofence parameters.

        Geofence is a virtual safety cage:
        - 500m radius: Prevents flyaway
        - 120m altitude: Legal compliance (under 400ft)
        - RTL action: Returns home if violated

        Essential for:
        - Legal operation
        - Preventing loss of control
        - Safety buffer around obstacles
        """
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
        """Verify RC failsafe parameters.

        RC failsafe provides pilot backup:
        - 500ms timeout: Quick response
        - RTL action: Return if pilot loses control
        - COM_RCL_EXCEPT=4: Allow offboard without RC

        Important even for autonomous because:
        - Pilot may need to take over
        - RC is ultimate override authority
        """
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
        """Verify data link failsafe parameters.

        Data link (telemetry) is ground station connection:
        - 5 second timeout: Allows brief dropouts
        - RTL action: Return if ground station lost

        Different from RC - this is the API/GCS connection.
        Losing data link means no telemetry and no ground control.
        """
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
# UTILITY METHOD TESTS
# =============================================================================
# Tests for helper methods that process and summarize validation results.


class TestUtilityMethods:
    """Test utility and helper methods.

    These methods help interpret validation results:
    - is_safety_configured(): Boolean "can we fly?"
    - get_safety_summary(): Detailed statistics
    - clear_cache(): Reset for fresh reads
    """

    def test_is_safety_configured_all_valid(self, parameter_manager):
        """Returns True when all parameters valid.

        is_safety_configured() answers: "Is it safe to fly?"
        Returns True only if ALL parameters are valid.
        """
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 2.0, True, "Test 2"),
        ]
        assert parameter_manager.is_safety_configured(results) is True

    def test_is_safety_configured_some_invalid(self, parameter_manager):
        """Returns False when any parameter invalid.

        Single invalid parameter = unsafe to fly.
        Safety is all-or-nothing - partial configuration is dangerous.
        """
        results = [
            ParameterStatus("P1", 1.0, 1.0, True, "Test 1"),
            ParameterStatus("P2", 2.0, 1.0, False, "Test 2"),
        ]
        assert parameter_manager.is_safety_configured(results) is False

    def test_get_safety_summary_all_valid(self, parameter_manager):
        """Summary correct when all valid.

        get_safety_summary() returns statistics:
        - total_parameters: How many were checked
        - valid_count: How many passed
        - invalid_count: How many failed
        - is_safe: Boolean overall status
        - invalid_parameters: List of failed ones with details
        """
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
        """Summary lists invalid parameters.

        When parameters fail, summary includes:
        - Name of each failed parameter
        - Expected vs actual values
        - Error messages
        - Descriptions
        """
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
        """Clear cache removes all cached data.

        clear_cache() is used when:
        - External changes may have modified parameters
        - Need fresh reads for critical verification
        - Preparing for a new session

        Resets cache to empty and marks as invalid.
        """
        parameter_manager._param_cache = {"P1": 1.0, "P2": 2.0}
        parameter_manager._cache_valid = True

        parameter_manager.clear_cache()

        assert parameter_manager._param_cache == {}
        assert parameter_manager._cache_valid is False


# =============================================================================
# STANDALONE FUNCTION TESTS
# =============================================================================
# Tests for module-level convenience functions.


class TestStandaloneFunctions:
    """Test standalone utility functions.

    These provide simple interfaces for common operations:
    - quick_safety_check(): One-call verification
    - format_parameter_status(): Pretty printing
    """

    @pytest.mark.asyncio
    async def test_quick_safety_check(self, mock_drone):
        """Quick check returns boolean and results.

        quick_safety_check() is the simplest interface:
        - Input: drone (MAVSDK System)
        - Output: (is_safe, results_list)

        Used when you just need a yes/no answer.
        """
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
        """Format valid status nicely.

        format_parameter_status() creates human-readable output:
        - [OK] or [FAIL] indicator
        - Parameter name
        - Expected and actual values
        - Description

        Used in CLI output and logs.
        """
        status = ParameterStatus("COM_OF_LOSS_T", 0.5, 0.5, True, "Timeout")
        formatted = format_parameter_status(status)

        assert "[OK]" in formatted
        assert "COM_OF_LOSS_T" in formatted
        assert "0.5000" in formatted
        assert "Timeout" in formatted

    def test_format_parameter_status_invalid(self):
        """Format invalid status with failure indicator.

        Invalid statuses show:
        - [FAIL] indicator (attention-grabbing)
        - Expected vs actual values (show the mismatch)
        - Error message (explain what's wrong)
        """
        status = ParameterStatus("COM_OBL_RC_ACT", 3.0, 1.0, False, "Action")
        formatted = format_parameter_status(status)

        assert "[FAIL]" in formatted
        assert "COM_OBL_RC_ACT" in formatted


# =============================================================================
# INTEGRATION-LIKE TESTS
# =============================================================================
# End-to-end workflow tests simulating real usage scenarios.


class TestIntegrationScenarios:
    """Test realistic usage scenarios.

    These tests simulate complete workflows:
    - Pre-flight safety check
    - Parameter mismatch detection and fixing
    - End-to-end configuration
    """

    @pytest.mark.asyncio
    async def test_preflight_safety_check_workflow(self, parameter_manager, mock_drone):
        """Complete pre-flight safety check workflow.

        Typical pre-flight sequence:
        1. Connect to drone
        2. Verify all safety parameters
        3. Check if safe to fly
        4. Log summary for records
        5. Only arm if safe
        """
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
        """Handle parameter mismatch scenario.

        When safety check fails:
        1. Run verification (detects failures)
        2. Check is_safe (should be False)
        3. Get diff (list of what's wrong)
        4. Fix the issues
        5. Re-verify
        """
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
        """Configure parameters from scratch.

        Initial setup workflow:
        1. Create manager connected to drone
        2. Run configure_safety_parameters()
        3. Verify all parameters were set
        4. Confirm all validations pass

        This is run on new drones or after parameter reset.
        """
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
