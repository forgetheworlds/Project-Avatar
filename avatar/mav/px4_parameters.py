"""PX4 safety parameter configuration and validation.

Provides parameter definitions, read/write functionality, and safety verification
for Layer 1 (PX4 hard reflexes) of the 4-layer safety architecture.

Reference: https://docs.px4.io/main/en/advanced_config/parameter_reference.html
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import MagicMock

try:
    from mavsdk import System
except ImportError:
    # Fallback for testing without mavsdk installed
    class System:  # type: ignore
        """Mock System class for testing."""

        def __init__(self) -> None:
            self.param = MagicMock()

logger = logging.getLogger(__name__)

# =============================================================================
# CRITICAL SAFETY PARAMETER DEFINITIONS
# =============================================================================

# Offboard Loss Failsafe (CRITICAL - Layer 1)
# These parameters ensure the drone returns home if offboard control is lost
OFFBOARD_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # Primary offboard loss action: Return mode (RTL) on offboard timeout
    "COM_OBL_RC_ACT": 3,
    # Timeout before offboard failsafe triggers (500ms for fast response)
    "COM_OF_LOSS_T": 0.5,
    # Action when offboard lost in Hold/Loiter: Hold mode
    "COM_OBL_ACT": 1,
}

# RC Loss Protection
# Ensures drone can safely handle RC link loss during offboard operations
RC_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # RC loss timeout (500ms)
    "COM_RC_LOSS_T": 0.5,
    # RC loss action: Return to Launch (RTL)
    "NAV_RCL_ACT": 2,
    # RC loss exceptions: Ignore RC loss in Offboard mode
    "COM_RCL_EXCEPT": 4,
}

# Battery Failsafes
# Multi-level battery protection to prevent in-flight power loss
BATTERY_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # Low battery threshold (25%)
    "BAT_LOW_THR": 0.25,
    # Critical battery threshold (15%)
    "BAT_CRIT_THR": 0.15,
    # Emergency battery threshold (10%)
    "BAT_EMERGEN_THR": 0.10,
    # Low battery action: Land immediately
    "COM_LOW_BAT_ACT": 2,
    # Minimum battery to arm (40%)
    "COM_ARM_BAT_MIN": 0.40,
}

# Geofencing
# Spatial boundaries to prevent flyaway
GEOFENCE_PARAMS: Dict[str, Union[int, float]] = {
    # Maximum horizontal distance from home (meters)
    "GF_MAX_HOR_DIST": 500,
    # Maximum vertical distance from home (meters)
    "GF_MAX_VER_DIST": 120,
    # Geofence breach action: Return to Launch
    "GF_ACTION": 3,
    # Geofence altitude mode: Check absolute altitude
    "GF_ALTMODE": 0,
}

# Data Link Loss
# Failsafe for loss of telemetry/ground station connection
DATA_LINK_PARAMS: Dict[str, Union[int, float]] = {
    # Data link timeout (seconds)
    "COM_DL_LOSS_T": 5.0,
    # Data link loss action: Return to Launch
    "NAV_DLL_ACT": 2,
}

# Combined critical parameters for full safety configuration
CRITICAL_PARAMETERS: Dict[str, Union[int, float]] = {
    **OFFBOARD_FAILSAFE_PARAMS,
    **RC_FAILSAFE_PARAMS,
    **BATTERY_FAILSAFE_PARAMS,
    **GEOFENCE_PARAMS,
    **DATA_LINK_PARAMS,
}

# Parameter metadata for human-readable descriptions
PARAMETER_DESCRIPTIONS: Dict[str, str] = {
    # Offboard
    "COM_OBL_RC_ACT": "Offboard loss action (0=disabled, 1=hold, 2=land, 3=return)",
    "COM_OF_LOSS_T": "Offboard loss timeout (seconds)",
    "COM_OBL_ACT": "Offboard action in Hold/Loiter (0=hold, 1=land)",
    # RC
    "COM_RC_LOSS_T": "RC loss timeout (seconds)",
    "NAV_RCL_ACT": "RC loss action (0=disabled, 1=hold, 2=RTL, 3=land, 4=terminate)",
    "COM_RCL_EXCEPT": "RC loss exceptions (bitmask, 4=offboard)",
    # Battery
    "BAT_LOW_THR": "Low battery threshold (0-1 ratio)",
    "BAT_CRIT_THR": "Critical battery threshold (0-1 ratio)",
    "BAT_EMERGEN_THR": "Emergency battery threshold (0-1 ratio)",
    "COM_LOW_BAT_ACT": "Low battery action (0=warning, 1=RTL, 2=land, 3=terminate)",
    "COM_ARM_BAT_MIN": "Minimum battery to arm (0-1 ratio)",
    # Geofence
    "GF_MAX_HOR_DIST": "Max horizontal distance from home (meters)",
    "GF_MAX_VER_DIST": "Max vertical distance from home (meters)",
    "GF_ACTION": "Geofence breach action (0=warning, 1=hold, 2=land, 3=RTL)",
    "GF_ALTMODE": "Geofence altitude mode (0=absolute, 1=relative)",
    # Data Link
    "COM_DL_LOSS_T": "Data link loss timeout (seconds)",
    "NAV_DLL_ACT": "Data link loss action (0=disabled, 1=hold, 2=RTL, 3=land)",
}

# Parameter types (int or float) - needed because MAVSDK has separate methods
PARAMETER_TYPES: Dict[str, str] = {
    # Offboard - all are integers
    "COM_OBL_RC_ACT": "int",
    "COM_OF_LOSS_T": "float",
    "COM_OBL_ACT": "int",
    # RC - mixed types
    "COM_RC_LOSS_T": "float",
    "NAV_RCL_ACT": "int",
    "COM_RCL_EXCEPT": "int",
    # Battery - mixed types
    "BAT_LOW_THR": "float",
    "BAT_CRIT_THR": "float",
    "BAT_EMERGEN_THR": "float",
    "COM_LOW_BAT_ACT": "int",
    "COM_ARM_BAT_MIN": "float",
    # Geofence - mostly integers
    "GF_MAX_HOR_DIST": "float",
    "GF_MAX_VER_DIST": "float",
    "GF_ACTION": "int",
    "GF_ALTMODE": "int",
    # Data Link - mixed
    "COM_DL_LOSS_T": "float",
    "NAV_DLL_ACT": "int",
}


@dataclass
class ParameterStatus:
    """Status of a single parameter check.

    Attributes:
        name: Parameter name (e.g., "COM_OF_LOSS_T")
        expected_value: The expected/safe value for this parameter
        actual_value: The current value on the drone (None if couldn't read)
        is_valid: Whether actual matches expected (within tolerance)
        description: Human-readable description of this parameter
        message: Optional status message (e.g., error details)
    """

    name: str
    expected_value: float
    actual_value: Optional[float]
    is_valid: bool
    description: str
    message: str = ""


class PX4ParameterError(Exception):
    """Raised when parameter operations fail critically."""

    pass


class SafetyError(PX4ParameterError):
    """Raised when safety parameters are not configured correctly."""

    pass


class PX4ParameterManager:
    """PX4 safety parameter configuration and validation.

    Ensures Layer 1 (PX4 hard reflexes) are properly configured before
    flight operations. Provides parameter read/write and safety verification.

    Usage:
        pm = PX4ParameterManager(drone)

        # Verify all safety parameters
        results = await pm.verify_safety_parameters()
        if not all(r.is_valid for r in results):
            raise SafetyError("PX4 parameters not configured correctly")

        # Configure parameters
        await pm.configure_safety_parameters()

        # Check specific areas
        offboard_status = await pm.verify_offboard_failsafe()
        battery_status = await pm.verify_battery_failsafe()
    """

    # Tolerance for float comparisons (0.1% relative or absolute 0.001)
    FLOAT_TOLERANCE: float = 0.001
    FLOAT_RELATIVE_TOLERANCE: float = 0.001

    def __init__(self, drone: System) -> None:
        """Initialize the parameter manager.

        Args:
            drone: MAVSDK System instance (connected)
        """
        self.drone = drone
        self._param_cache: Dict[str, Optional[float]] = {}
        self._cache_valid = False

    # =========================================================================
    # Core Parameter Operations
    # =========================================================================

    async def get_parameter(self, name: str, use_cache: bool = True) -> Optional[float]:
        """Read a single parameter value from PX4.

        Uses MAVSDK param module with automatic type selection based on
        parameter metadata. Results are cached for subsequent reads.

        Args:
            name: Parameter name (e.g., "COM_OF_LOSS_T")
            use_cache: If True, return cached value if available

        Returns:
            Parameter value as float, or None if read failed

        Raises:
            PX4ParameterError: If parameter type is unknown
        """
        # Check cache first if enabled
        if use_cache and name in self._param_cache:
            return self._param_cache[name]

        try:
            param_type = PARAMETER_TYPES.get(name, "float")

            if param_type == "int":
                value = await self.drone.param.get_param_int(name)
            elif param_type == "float":
                value = await self.drone.param.get_param_float(name)
            else:
                raise PX4ParameterError(f"Unknown parameter type for {name}: {param_type}")

            self._param_cache[name] = float(value)
            return float(value)

        except Exception as e:
            logger.warning(f"Failed to read parameter {name}: {e}")
            return None

    async def set_parameter(self, name: str, value: Union[int, float]) -> bool:
        """Write a parameter value to PX4.

        Uses MAVSDK param module with automatic type selection. Invalidates
        the parameter cache on successful write.

        Args:
            name: Parameter name
            value: New value (int or float)

        Returns:
            True if write succeeded, False otherwise
        """
        try:
            param_type = PARAMETER_TYPES.get(name, "float")

            if param_type == "int":
                await self.drone.param.set_param_int(name, int(value))
            elif param_type == "float":
                await self.drone.param.set_param_float(name, float(value))
            else:
                raise PX4ParameterError(f"Unknown parameter type for {name}: {param_type}")

            # Invalidate cache since we changed a parameter
            self._cache_valid = False

            logger.info(f"Set parameter {name} = {value}")
            return True

        except Exception as e:
            logger.error(f"Failed to set parameter {name}: {e}")
            return False

    async def get_all_parameters(self) -> Dict[str, Optional[float]]:
        """Read all critical safety parameters from PX4.

        Returns:
            Dictionary mapping parameter names to their values
            (None for parameters that couldn't be read)
        """
        results: Dict[str, Optional[float]] = {}

        for name in CRITICAL_PARAMETERS.keys():
            results[name] = await self.get_parameter(name)

        self._param_cache = results
        self._cache_valid = True

        return results

    # =========================================================================
    # Safety Verification Methods
    # =========================================================================

    def check_parameter(
        self,
        name: str,
        expected: Union[int, float],
        actual: Optional[Union[int, float]],
    ) -> ParameterStatus:
        """Validate a single parameter against expected value.

        Performs type-aware comparison with tolerance for float values.

        Args:
            name: Parameter name
            expected: Expected/safe value
            actual: Current value (None if unavailable)

        Returns:
            ParameterStatus with validation results
        """
        description = PARAMETER_DESCRIPTIONS.get(name, f"PX4 parameter {name}")

        if actual is None:
            return ParameterStatus(
                name=name,
                expected_value=float(expected),
                actual_value=None,
                is_valid=False,
                description=description,
                message="Could not read parameter from drone",
            )

        # Determine if this is an int or float parameter
        param_type = PARAMETER_TYPES.get(name, "float")

        if param_type == "int":
            # Integer comparison - must be exact
            is_valid = int(actual) == int(expected)
        else:
            # Float comparison with tolerance
            expected_f = float(expected)
            actual_f = float(actual)

            # Use relative tolerance for larger values, absolute for small ones
            tolerance = max(
                self.FLOAT_TOLERANCE,
                abs(expected_f) * self.FLOAT_RELATIVE_TOLERANCE,
            )
            is_valid = abs(actual_f - expected_f) <= tolerance

        message = ""
        if not is_valid:
            message = f"Expected {expected}, got {actual}"
            logger.warning(f"Parameter {name} mismatch: {message}")

        return ParameterStatus(
            name=name,
            expected_value=float(expected),
            actual_value=float(actual),
            is_valid=is_valid,
            description=description,
            message=message,
        )

    async def verify_safety_parameters(self) -> List[ParameterStatus]:
        """Verify all critical safety parameters are configured correctly.

        Reads all parameters from the drone and validates against expected
        values. This is the primary pre-flight safety check.

        Returns:
            List of ParameterStatus for all critical parameters

        Raises:
            PX4ParameterError: If parameter reads fail completely
        """
        logger.info("Verifying all critical safety parameters...")

        results: List[ParameterStatus] = []
        actual_values = await self.get_all_parameters()

        for name, expected in CRITICAL_PARAMETERS.items():
            actual = actual_values.get(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        # Summary logging
        valid_count = sum(1 for r in results if r.is_valid)
        total_count = len(results)
        logger.info(f"Parameter verification: {valid_count}/{total_count} parameters valid")

        if valid_count < total_count:
            invalid = [r.name for r in results if not r.is_valid]
            logger.warning(f"Invalid parameters: {invalid}")

        return results

    async def configure_safety_parameters(self) -> List[ParameterStatus]:
        """Configure all critical safety parameters to expected values.

        Writes safety-critical parameters to PX4 and verifies they were
        set correctly. Use this during initial setup or after parameter reset.

        Returns:
            List of ParameterStatus showing write/verify results

        Note:
            Some parameters may require reboot to take effect. Always
            verify after reboot before flight.
        """
        logger.info("Configuring critical safety parameters...")

        results: List[ParameterStatus] = []

        for name, expected in CRITICAL_PARAMETERS.items():
            # Write the parameter
            success = await self.set_parameter(name, expected)

            if success:
                # Read back to verify
                actual = await self.get_parameter(name)
                status = self.check_parameter(name, expected, actual)
            else:
                # Write failed
                description = PARAMETER_DESCRIPTIONS.get(name, f"PX4 parameter {name}")
                status = ParameterStatus(
                    name=name,
                    expected_value=float(expected),
                    actual_value=None,
                    is_valid=False,
                    description=description,
                    message="Failed to write parameter",
                )

            results.append(status)

        # Summary logging
        valid_count = sum(1 for r in results if r.is_valid)
        total_count = len(results)
        logger.info(f"Configuration complete: {valid_count}/{total_count} parameters set correctly")

        return results

    async def get_parameter_diff(self) -> List[ParameterStatus]:
        """Get list of parameters that differ from expected values.

        Convenience method to see only the parameters that need attention.

        Returns:
            List of ParameterStatus where actual != expected
        """
        all_status = await self.verify_safety_parameters()
        return [s for s in all_status if not s.is_valid]

    # =========================================================================
    # Category-Specific Verification (Convenience Methods)
    # =========================================================================

    async def verify_offboard_failsafe(self) -> List[ParameterStatus]:
        """Verify offboard loss failsafe configuration.

        Critical for LLM-driven flight - ensures drone returns home if
        offboard control signals are lost.

        Returns:
            List of ParameterStatus for offboard parameters
        """
        results: List[ParameterStatus] = []

        for name, expected in OFFBOARD_FAILSAFE_PARAMS.items():
            actual = await self.get_parameter(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        return results

    async def verify_rc_failsafe(self) -> List[ParameterStatus]:
        """Verify RC loss failsafe configuration.

        Ensures proper behavior when RC link is lost during offboard flight.

        Returns:
            List of ParameterStatus for RC failsafe parameters
        """
        results: List[ParameterStatus] = []

        for name, expected in RC_FAILSAFE_PARAMS.items():
            actual = await self.get_parameter(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        return results

    async def verify_battery_failsafe(self) -> List[ParameterStatus]:
        """Verify battery failsafe configuration.

        Ensures multi-level battery protection is properly configured.

        Returns:
            List of ParameterStatus for battery parameters
        """
        results: List[ParameterStatus] = []

        for name, expected in BATTERY_FAILSAFE_PARAMS.items():
            actual = await self.get_parameter(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        return results

    async def verify_geofence(self) -> List[ParameterStatus]:
        """Verify geofence configuration.

        Ensures spatial boundaries are set to prevent flyaway.

        Returns:
            List of ParameterStatus for geofence parameters
        """
        results: List[ParameterStatus] = []

        for name, expected in GEOFENCE_PARAMS.items():
            actual = await self.get_parameter(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        return results

    async def verify_data_link_failsafe(self) -> List[ParameterStatus]:
        """Verify data link loss failsafe configuration.

        Ensures proper RTL behavior when telemetry link to ground station is lost.

        Returns:
            List of ParameterStatus for data link parameters
        """
        results: List[ParameterStatus] = []

        for name, expected in DATA_LINK_PARAMS.items():
            actual = await self.get_parameter(name)
            status = self.check_parameter(name, expected, actual)
            results.append(status)

        return results

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def is_safety_configured(self, results: List[ParameterStatus]) -> bool:
        """Check if all safety parameters are valid.

        Args:
            results: Results from verify_safety_parameters()

        Returns:
            True if all parameters are valid, False otherwise
        """
        return all(r.is_valid for r in results)

    def get_safety_summary(self, results: List[ParameterStatus]) -> Dict[str, Any]:
        """Generate a human-readable summary of safety configuration.

        Args:
            results: Results from verify_safety_parameters()

        Returns:
            Dictionary with summary statistics and invalid parameter list
        """
        invalid = [r for r in results if not r.is_valid]

        return {
            "total_parameters": len(results),
            "valid_count": len(results) - len(invalid),
            "invalid_count": len(invalid),
            "is_safe": len(invalid) == 0,
            "invalid_parameters": [
                {
                    "name": r.name,
                    "expected": r.expected_value,
                    "actual": r.actual_value,
                    "message": r.message,
                }
                for r in invalid
            ],
        }

    def clear_cache(self) -> None:
        """Clear the parameter cache.

        Call this if you suspect parameters have been changed externally.
        """
        self._param_cache.clear()
        self._cache_valid = False
        logger.debug("Parameter cache cleared")


# =============================================================================
# Standalone Functions for Quick Checks
# =============================================================================


async def quick_safety_check(drone: System) -> Tuple[bool, List[ParameterStatus]]:
    """Perform a quick safety parameter verification.

    Convenience function for one-off safety checks without managing
    the ParameterManager instance.

    Args:
        drone: Connected MAVSDK System instance

    Returns:
        Tuple of (all_safe, list_of_statuses)

    Example:
        is_safe, results = await quick_safety_check(drone)
        if not is_safe:
            print("Safety check failed!")
    """
    manager = PX4ParameterManager(drone)
    results = await manager.verify_safety_parameters()
    return manager.is_safety_configured(results), results


def format_parameter_status(status: ParameterStatus) -> str:
    """Format a ParameterStatus for display.

    Args:
        status: ParameterStatus to format

    Returns:
        Formatted string representation
    """
    indicator = "OK" if status.is_valid else "FAIL"
    actual_str = f"{status.actual_value:.4f}" if status.actual_value is not None else "N/A"
    return f"[{indicator}] {status.name}: {actual_str} (expected {status.expected_value:.4f}) - {status.description}"
