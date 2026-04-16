"""PX4 safety parameter configuration and validation.

Provides parameter definitions, read/write functionality, and safety verification
for Layer 1 (PX4 hard reflexes) of the 4-layer safety architecture.

Reference: https://docs.px4.io/main/en/advanced_config/parameter_reference.html

================================================================================
WHAT ARE PX4 PARAMETERS?
================================================================================

PX4 parameters are persistent configuration variables stored in the flight
controller's memory. They control virtually every aspect of the drone's
behavior - from flight modes and failsafe actions to PID tuning and sensor
calibration. Think of them as the "settings" that define how the drone operates.

Key characteristics:
- Stored in non-volatile memory (survive reboots)
- Can be read/written via MAVLink (MAVSDK in our case)
- Changes often require reboot to take full effect
- Organized hierarchically (e.g., "COM_" for commander, "BAT_" for battery)
- Some are integers (discrete modes), others are floats (continuous values)

================================================================================
WHY PARAMETERS MATTER FOR FILMING
================================================================================

Aerial filming imposes unique requirements on drone behavior:

1. SMOOTH MOVEMENT: Camera footage requires stable, predictable flight paths
   - Aggressive failsafe actions can ruin shots
   - Jerky movements from mode changes are unacceptable

2. RELIABILITY: Film shoots are expensive (crew, talent, location)
   - Must handle edge cases gracefully
   - Cannot afford flyaways or crashes

3. AUTONOMOUS OPERATION: Offboard/LLM control is primary control method
   - RC transmitter may not be actively monitored
   - Failsafes must be tuned for autonomous operation

4. LEGAL/SAFETY COMPLIANCE: Commercial filming has strict safety requirements
   - Geofencing prevents unauthorized airspace entry
   - Failsafes must favor safe outcomes over preserving footage

================================================================================
CONFIGURATION PROCESS
================================================================================

1. PRE-FLIGHT VERIFICATION (Every flight):
   - Use verify_safety_parameters() to check all critical params
   - Any mismatch is a no-go for flight
   - Log verification results for audit trail

2. INITIAL CONFIGURATION (First setup or after reset):
   - Use configure_safety_parameters() to write expected values
   - Reboot the flight controller
   - Run verification again to confirm persistence

3. MAINTENANCE:
   - Parameters can drift after firmware updates
   - Check periodically with quick_safety_check()
   - Document any intentional deviations

================================================================================
LAYER 1 SAFETY ARCHITECTURE
================================================================================

This module implements Layer 1 of our 4-layer safety system:

Layer 1 (PX4 Hard Reflexes): Immediate, automatic responses
  - No software decision-making - pure reflexes
  - Configured through these parameters
  - Always active, cannot be overridden by higher layers

Layer 2 (GuardianProcess): Runtime safety limits
Layer 3 (AvatarPilot): Intelligent execution monitoring
Layer 4 (Ground Control): Human oversight

Layer 1 is the last line of defense. When all else fails, these parameters
determine whether the drone lands safely or becomes a liability.
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
#
# Each parameter below is categorized by failsafe type. For each:
# - Parameter name follows PX4 naming convention
# - Value is our recommended safe setting
# - See PARAMETER_DESCRIPTIONS for human-readable explanation
#
# WHY THESE VALUES WERE CHOSEN:
# - Offboard timeout: 500ms balances responsiveness vs. spurious triggers
# - Geofence: 500m horizontal allows filming range while containing flyaways
# - Battery: 25/15/10% thresholds provide early warning → emergency action
# - RC exceptions: Bitmask 4 = ignore RC loss in offboard (we use LLM, not RC)

# -----------------------------------------------------------------------------
# OFFBOARD LOSS FAILSAFE
# -----------------------------------------------------------------------------
#
# CRITICAL FOR LLM-DRIVEN FLIGHT: When the LLM or MCP server stops sending
# setpoints (offboard control commands), PX4 must take immediate action.
#
# Why this matters for filming:
# - If the AI agent crashes or disconnects, the drone cannot just hover
   # - A hovering drone is a hazard to talent/crew and wastes battery
   # - Return-to-Launch (RTL) brings it home where ground crew can recover it
   #
   # Common failure modes this protects against:
   # - Network connectivity loss between agent and MCP server
   # - LLM taking too long to respond (>500ms timeout)
   # - MCP server crash or overload
   # - WiFi/telemetry link degradation during offboard flight
   #
   # Value 3 = RTL (Return to Launch):
   # - Climbs to RTL altitude
   # - Flies directly to takeoff point
   # - Lands automatically
   # - Preserves the drone for recovery and analysis
OFFBOARD_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # COM_OBL_RC_ACT: Primary offboard loss action
    # Options: 0=disabled (DANGEROUS), 1=hold, 2=land, 3=RTL (RECOMMENDED)
    # For filming: RTL preserves equipment, land could be unsafe near crew
    "COM_OBL_RC_ACT": 3,

    # COM_OF_LOSS_T: Timeout before offboard failsafe triggers
    # PX4 requires continuous setpoint updates; gap > timeout = connection lost
    # 0.5 seconds = 500ms allows minor latency while catching true failures
    # Too short: spurious triggers from network jitter
    # Too long: drone drifts uncontrolled during actual failures
    "COM_OF_LOSS_T": 0.5,

    # COM_OBL_ACT: Action when offboard lost while in Hold/Loiter mode
    # This is a secondary case - what to do if already hovering when offboard dies
    # 1 = land at current position (safe when already in hover)
    "COM_OBL_ACT": 1,
}

# -----------------------------------------------------------------------------
# RC LOSS PROTECTION
# -----------------------------------------------------------------------------
#
# IMPORTANT DISTINCTION: We fly via OFFBOARD (LLM commands), not RC (transmitter).
# However, PX4 still monitors RC link as a backup safety mechanism.
#
# For filming operations:
# - RC may be held by safety pilot as backup
# - But offboard flight should NOT fail if RC is lost (we're using LLM!)
# - COM_RCL_EXCEPT = 4 tells PX4: "ignore RC loss when in offboard mode"
#
# Why keep RC failsafe at all?
# - If pilot takes manual control (mode switch), RC loss should still trigger RTL
# - Provides backup if offboard stack fails and pilot attempts intervention
# - Regulatory compliance (many jurisdictions require RC link monitoring)
RC_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # COM_RC_LOSS_T: RC signal loss timeout
    # Same logic as offboard timeout - 500ms catches real loss quickly
    "COM_RC_LOSS_T": 0.5,

    # NAV_RCL_ACT: RC loss action
    # 2 = RTL (Return to Launch)
    # Only triggers if NOT in offboard mode (see COM_RCL_EXCEPT below)
    "NAV_RCL_ACT": 2,

    # COM_RCL_EXCEPT: RC loss exceptions (bitmask)
    # This is CRITICAL for our use case.
    # Bit 2 (value 4) = offboard mode
    # By setting this to 4, we tell PX4: "Don't RTL on RC loss if in offboard"
    # Without this, the drone would RTL every time RC signal degrades,
    # even though we're controlling via LLM, not RC!
    "COM_RCL_EXCEPT": 4,
}

# -----------------------------------------------------------------------------
# BATTERY FAILSAFE
# -----------------------------------------------------------------------------
#
# MULTI-LEVEL PROTECTION STRATEGY:
# Aerial filming is power-hungry (gimbal, camera, downlink). Batteries
# degrade with age and temperature. We implement a graduated response:
#
# Level 1 - LOW (25% remaining):
#   - Warning to ground station
#   - Continue mission but monitor closely
#   - Plan RTL before hitting critical threshold
#
# Level 2 - CRITICAL (15% remaining):
#   - Automatic action required
#   - COM_LOW_BAT_ACT = 2 means "land immediately"
#   - Better to land safely with footage than crash with footage
#
# Level 3 - EMERGENCY (10% remaining):
#   - Battery may suddenly cut out
#   - Drone will descend rapidly
#   - This is "save the hardware" territory, not "save the shot"
#
# ARM MINIMUM (40%):
#   - Prevent takeoff with depleted battery
#   - Ensures enough margin for the planned shot + RTL reserve
BATTERY_FAILSAFE_PARAMS: Dict[str, Union[int, float]] = {
    # BAT_LOW_THR: Low battery warning threshold
    # 0.25 = 25% remaining capacity
    # Triggers warnings but not automatic actions
    "BAT_LOW_THR": 0.25,

    # BAT_CRIT_THR: Critical battery threshold
    # 0.15 = 15% remaining
    # Below this, immediate action is required
    "BAT_CRIT_THR": 0.15,

    # BAT_EMERGEN_THR: Emergency threshold
    # 0.10 = 10% remaining
    # Near-certain power loss imminent
    "BAT_EMERGEN_THR": 0.10,

    # COM_LOW_BAT_ACT: Action on low battery
    # 0 = warning only (unsafe for filming)
    # 1 = RTL (may not complete before power loss)
    # 2 = LAND (safest - descend at current position)
    # 3 = terminate (kill switch - nuclear option)
    # For filming: LAND (2) is safest - we know where it will come down
    "COM_LOW_BAT_ACT": 2,

    # COM_ARM_BAT_MIN: Minimum battery to allow arming
    # 0.40 = 40% minimum
    # Prevents taking off with depleted battery
    "COM_ARM_BAT_MIN": 0.40,
}

# -----------------------------------------------------------------------------
# GEOFENCING (SPATIAL BOUNDARIES)
# -----------------------------------------------------------------------------
#
# GEOFENCING PREVENTS FLYAWAYS - one of the most dangerous failure modes.
# A flyaway drone can enter controlled airspace, crash into people/property,
# or be lost entirely (expensive equipment + irreplaceable footage).
#
# PX4 geofence creates an invisible boundary:
# - Horizontal cylinder: Max distance from home point
# - Vertical cylinder: Max altitude
# - Breach action: Automatic RTL or hold
#
# FILMING CONSIDERATIONS:
# - 500m radius allows large tracking shots while containing flyaways
# - 120m altitude complies with FAA Part 107 (US commercial ops)
#   and most other jurisdictions' altitude limits
# - RTL on breach is safest - returns to known safe position
#
# SETUP REQUIREMENT:
# - Geofence is centered on "home position" (GPS at arming)
# - Must have valid GPS lock before arming for geofence to work
# - Home position should be a safe, clear area suitable for RTL
GEOFENCE_PARAMS: Dict[str, Union[int, float]] = {
    # GF_MAX_HOR_DIST: Maximum horizontal distance from home
    # 500 meters = ~1640 feet
    # Large enough for cinematic tracking shots
    # Small enough to contain runaway drones
    "GF_MAX_HOR_DIST": 500,

    # GF_MAX_VER_DIST: Maximum altitude above home
    # 120 meters = ~394 feet
    # Aligns with FAA Part 107 altitude limit
    # Can be adjusted for local regulations
    "GF_MAX_VER_DIST": 120,

    # GF_ACTION: Geofence breach action
    # 0 = warning only (insufficient for filming)
    # 1 = hold mode (may drift outside fence in wind)
    # 2 = land (may land in unsafe area)
    # 3 = RTL (RECOMMENDED - returns to known safe point)
    "GF_ACTION": 3,

    # GF_ALTMODE: Altitude reference mode
    # 0 = absolute (AMSL - above mean sea level)
    #   - Fence altitude is fixed regardless of takeoff elevation
    #   - Safer if flying in varied terrain
    # 1 = relative (above home)
    #   - Fence moves with takeoff point
    #   - Use if takeoff at high elevation
    "GF_ALTMODE": 0,
}

# -----------------------------------------------------------------------------
# DATA LINK LOSS FAILSAFE
# -----------------------------------------------------------------------------
#
# DATA LINK = Telemetry connection to ground station
# This carries: mission status, battery, position, health monitoring
#
# DIFFERENT FROM OFFBOARD LOSS:
# - Offboard loss = no flight commands being received
# - Data link loss = no telemetry being sent (may still be receiving commands)
#
# WHY BOTH ARE NEEDED:
# 1. May lose telemetry (data link) while still receiving commands
    #    - Ground station may still be sending via different channel
    #    - Drone should continue if commands still coming
    #    - But need timeout in case BOTH are lost
    #
    # 2. Data link loss means ground crew is "flying blind"
    #    - No position/battery updates
    #    - Cannot verify mission success
    #    - RTL allows re-establishing link at home position
    #
    # TIMEOUT SETTING (5 seconds):
    # - Longer than offboard timeout because:
    #   - Telemetry is less critical than control
    #   - Don't want RTL if just a brief telemetry glitch
    #   - 5 seconds allows reconnection attempts
DATA_LINK_PARAMS: Dict[str, Union[int, float]] = {
    # COM_DL_LOSS_T: Data link timeout
    # 5.0 seconds before triggering failsafe
    # Longer than offboard timeout (0.5s) because telemetry is less critical
    "COM_DL_LOSS_T": 5.0,

    # NAV_DLL_ACT: Data link loss action
    # 0 = disabled (unsafe)
    # 1 = hold (may lose link permanently)
    # 2 = RTL (recommended)
    # 3 = land (acceptable alternative)
    "NAV_DLL_ACT": 2,
}

# -----------------------------------------------------------------------------
# COMBINED CRITICAL PARAMETERS
# -----------------------------------------------------------------------------
#
# Master dictionary combining all safety-critical parameters.
# Used by verification and configuration functions to ensure
# complete coverage of Layer 1 safety settings.
CRITICAL_PARAMETERS: Dict[str, Union[int, float]] = {
    **OFFBOARD_FAILSAFE_PARAMS,
    **RC_FAILSAFE_PARAMS,
    **BATTERY_FAILSAFE_PARAMS,
    **GEOFENCE_PARAMS,
    **DATA_LINK_PARAMS,
}

# =============================================================================
# PARAMETER METADATA
# =============================================================================
#
# Human-readable descriptions for each parameter.
# Used in logging, reports, and user interfaces.
# Format: "Name: Description (valid options)"
PARAMETER_DESCRIPTIONS: Dict[str, str] = {
    # Offboard failsafe parameters
    "COM_OBL_RC_ACT": "Offboard loss action (0=disabled, 1=hold, 2=land, 3=RTL)",
    "COM_OF_LOSS_T": "Offboard loss timeout (seconds)",
    "COM_OBL_ACT": "Offboard action in Hold/Loiter (0=hold, 1=land)",

    # RC failsafe parameters
    "COM_RC_LOSS_T": "RC loss timeout (seconds)",
    "NAV_RCL_ACT": "RC loss action (0=disabled, 1=hold, 2=RTL, 3=land, 4=terminate)",
    "COM_RCL_EXCEPT": "RC loss exceptions (bitmask, 4=offboard)",

    # Battery failsafe parameters
    "BAT_LOW_THR": "Low battery threshold (0-1 ratio, e.g., 0.25 = 25%)",
    "BAT_CRIT_THR": "Critical battery threshold (0-1 ratio)",
    "BAT_EMERGEN_THR": "Emergency battery threshold (0-1 ratio)",
    "COM_LOW_BAT_ACT": "Low battery action (0=warning, 1=RTL, 2=land, 3=terminate)",
    "COM_ARM_BAT_MIN": "Minimum battery to arm (0-1 ratio, e.g., 0.40 = 40%)",

    # Geofence parameters
    "GF_MAX_HOR_DIST": "Geofence max horizontal distance from home (meters)",
    "GF_MAX_VER_DIST": "Geofence max altitude from home (meters)",
    "GF_ACTION": "Geofence breach action (0=warning, 1=hold, 2=land, 3=RTL)",
    "GF_ALTMODE": "Geofence altitude mode (0=absolute/AMSL, 1=relative to home)",

    # Data link parameters
    "COM_DL_LOSS_T": "Data link loss timeout (seconds)",
    "NAV_DLL_ACT": "Data link loss action (0=disabled, 1=hold, 2=RTL, 3=land)",
}

# -----------------------------------------------------------------------------
# PARAMETER TYPE DEFINITIONS
# -----------------------------------------------------------------------------
#
# MAVSDK requires different methods for int vs float parameters:
#   - get_param_int() / set_param_int() for integer values
#   - get_param_float() / set_param_float() for float values
#
# This mapping tells the ParameterManager which method to use.
# Incorrect typing will cause MAVSDK errors.
PARAMETER_TYPES: Dict[str, str] = {
    # Offboard parameters
    "COM_OBL_RC_ACT": "int",
    "COM_OF_LOSS_T": "float",
    "COM_OBL_ACT": "int",

    # RC parameters
    "COM_RC_LOSS_T": "float",
    "NAV_RCL_ACT": "int",
    "COM_RCL_EXCEPT": "int",

    # Battery parameters
    "BAT_LOW_THR": "float",
    "BAT_CRIT_THR": "float",
    "BAT_EMERGEN_THR": "float",
    "COM_LOW_BAT_ACT": "int",
    "COM_ARM_BAT_MIN": "float",

    # Geofence parameters
    "GF_MAX_HOR_DIST": "float",
    "GF_MAX_VER_DIST": "float",
    "GF_ACTION": "int",
    "GF_ALTMODE": "int",

    # Data link parameters
    "COM_DL_LOSS_T": "float",
    "NAV_DLL_ACT": "int",
}


@dataclass
class ParameterStatus:
    """Status of a single parameter check.

    This dataclass holds the result of comparing an expected parameter value
    against the actual value read from the flight controller.

    Attributes:
        name: Parameter name (e.g., "COM_OF_LOSS_T")
        expected_value: The expected/safe value for this parameter
        actual_value: The current value on the drone (None if couldn't read)
        is_valid: Whether actual matches expected (within tolerance)
        description: Human-readable description of this parameter
        message: Optional status message (e.g., error details)

    Example:
        status = ParameterStatus(
            name="COM_OF_LOSS_T",
            expected_value=0.5,
            actual_value=0.5,
            is_valid=True,
            description="Offboard loss timeout (seconds)"
        )
    """

    name: str
    expected_value: float
    actual_value: Optional[float]
    is_valid: bool
    description: str
    message: str = ""


class PX4ParameterError(Exception):
    """Raised when parameter operations fail critically.

    This exception indicates a fundamental problem with parameter access,
    such as:
    - MAVSDK connection failure
    - Unknown parameter names
    - Communication timeouts

    This is different from SafetyError (configuration mismatch) - this
    indicates we couldn't even check the configuration.
    """

    pass


class SafetyError(PX4ParameterError):
    """Raised when safety parameters are not configured correctly.

    This exception indicates that safety-critical parameters have been
    verified and found to deviate from expected values.

    This is a MORE SERIOUS condition than a read error - it means the
    drone is configured unsafely and should NOT fly until corrected.

    Example scenarios:
    - Offboard timeout set to 5 seconds (too long - dangerous)
    - Geofence disabled (GF_ACTION = 0)
    - Battery failsafe disabled (COM_LOW_BAT_ACT = 0)
    """

    pass


class PX4ParameterManager:
    """PX4 safety parameter configuration and validation.

    This class provides a complete interface for managing the Layer 1 safety
    parameters that form the foundation of our 4-layer safety architecture.

    CORE RESPONSIBILITIES:
    1. Reading parameters from PX4 via MAVSDK
    2. Writing parameters to PX4
    3. Verifying parameters match expected safe values
    4. Configuring parameters for safe flight operations

    USAGE PATTERNS:

    Pattern 1: Pre-flight verification (most common)
        pm = PX4ParameterManager(drone)
        results = await pm.verify_safety_parameters()
        if not pm.is_safety_configured(results):
            raise SafetyError("Parameters not configured correctly")

    Pattern 2: Initial setup
        pm = PX4ParameterManager(drone)
        results = await pm.configure_safety_parameters()
        # Reboot flight controller here
        # Then verify again

    Pattern 3: Category-specific checks
        pm = PX4ParameterManager(drone)
        battery_ok = await pm.verify_battery_failsafe()
        geofence_ok = await pm.verify_geofence()

    CACHING:
    The manager caches parameter reads to minimize MAVLink traffic.
    Cache is invalidated on parameter writes or when clear_cache() is called.

    THREAD SAFETY:
    This class is NOT thread-safe. Use one instance per drone connection
    in async/await context.
    """

    # Tolerance values for float comparisons
    # PX4 stores floats with limited precision; exact equality is unrealistic
    FLOAT_TOLERANCE: float = 0.001  # Absolute tolerance
    FLOAT_RELATIVE_TOLERANCE: float = 0.001  # 0.1% relative tolerance

    def __init__(self, drone: System) -> None:
        """Initialize the parameter manager.

        Args:
            drone: MAVSDK System instance that is already connected to PX4

        Raises:
            No exceptions raised, but operations will fail if drone
            is not properly connected.
        """
        self.drone = drone
        self._param_cache: Dict[str, Optional[float]] = {}
        self._cache_valid = False

    # =========================================================================
    # Core Parameter Operations
    # =========================================================================
    #
    # These methods implement the low-level read/write interface to PX4.
    # They handle type selection (int vs float) and caching automatically.

    async def get_parameter(self, name: str, use_cache: bool = True) -> Optional[float]:
        """Read a single parameter value from PX4.

        This is the primary read method. It automatically selects the correct
        MAVSDK call based on PARAMETER_TYPES and caches results.

        Args:
            name: Parameter name (e.g., "COM_OF_LOSS_T")
            use_cache: If True, return cached value if available

        Returns:
            Parameter value as float, or None if read failed
            (None indicates communication error or invalid parameter name)

        Raises:
            PX4ParameterError: If parameter type is unknown

        Example:
            value = await pm.get_parameter("COM_OF_LOSS_T")
            if value is None:
                logger.error("Failed to read offboard timeout")
            else:
                logger.info(f"Offboard timeout: {value}s")

        Implementation Notes:
        - Uses PARAMETER_TYPES to determine int vs float
        - Converts int results to float for uniform interface
        - Caches successful reads (controlled by use_cache)
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

        This method writes a parameter and invalidates the cache.
        Note: Some parameters require a reboot to take effect.

        Args:
            name: Parameter name (must exist in PARAMETER_TYPES)
            value: New value (int or float, must match expected type)

        Returns:
            True if write succeeded, False otherwise

        Important Notes:
        - Cache is invalidated after any write (safety precaution)
        - Write may succeed but parameter may not take effect until reboot
        - Always verify after writing and rebooting

        Example:
            success = await pm.set_parameter("COM_OF_LOSS_T", 0.5)
            if not success:
                raise PX4ParameterError("Failed to set offboard timeout")
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

        This is a convenience method that reads all parameters defined
        in CRITICAL_PARAMETERS. Used for bulk verification.

        Returns:
            Dictionary mapping parameter names to their values
            (None for parameters that couldn't be read)

        Performance:
        - Reads parameters sequentially (MAVLink limitation)
        - Updates cache with all values
        - Takes ~1-2 seconds for 15+ parameters
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
    #
    # These methods implement the Layer 1 safety verification logic.
    # They compare expected vs actual values and report discrepancies.

    def check_parameter(
        self,
        name: str,
        expected: Union[int, float],
        actual: Optional[Union[int, float]],
    ) -> ParameterStatus:
        """Validate a single parameter against expected value.

        This is the core validation logic. It performs type-aware comparison
        with tolerance for float values.

        Args:
            name: Parameter name
            expected: Expected/safe value from CRITICAL_PARAMETERS
            actual: Current value from drone (None if unavailable)

        Returns:
            ParameterStatus with validation results

        Comparison Logic:
        - Integer parameters: Must match exactly
        - Float parameters: Within FLOAT_TOLERANCE or 0.1% relative
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

        This is the PRIMARY PRE-FLIGHT SAFETY CHECK for Layer 1.
        It reads all critical parameters and validates them against
        expected values.

        Returns:
            List of ParameterStatus for all critical parameters

        Raises:
            PX4ParameterError: If parameter reads fail completely

        Usage:
            results = await pm.verify_safety_parameters()
            if not pm.is_safety_configured(results):
                # DO NOT FLY - safety parameters incorrect
                raise SafetyError("Safety check failed")

        Output:
        - Logs summary: "X/Y parameters valid"
        - Lists invalid parameters
        - Each ParameterStatus has is_valid flag
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

        This method writes safety-critical parameters to PX4 and verifies
        they were set correctly. Use this during:
        - Initial drone setup
        - After parameter reset
        - When updating safety configuration

        Returns:
            List of ParameterStatus showing write/verify results

        Important Notes:
        - Some parameters require reboot to take effect
        - Always verify after reboot before flight
        - Failed writes are logged but don't raise exceptions

        Post-Configuration Steps:
        1. Run configure_safety_parameters()
        2. Reboot flight controller
        3. Run verify_safety_parameters() to confirm
        4. Only then proceed to flight
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

        Convenience method that returns only the parameters needing attention.
        Useful for generating reports or focused troubleshooting.

        Returns:
            List of ParameterStatus where actual != expected
        """
        all_status = await self.verify_safety_parameters()
        return [s for s in all_status if not s.is_valid]

    # =========================================================================
    # Category-Specific Verification (Convenience Methods)
    # =========================================================================
    #
    # These methods allow checking specific safety categories.
    # Useful when you want to verify one aspect without the full check.

    async def verify_offboard_failsafe(self) -> List[ParameterStatus]:
        """Verify offboard loss failsafe configuration.

        CRITICAL FOR LLM-DRIVEN FLIGHT - ensures drone returns home if
        offboard control signals are lost.

        This is arguably the most important check for Project Avatar because:
        - We rely exclusively on offboard (LLM) control
        - Offboard loss is the primary failure mode
        - Wrong settings here cause immediate flyaways

        Checks:
        - COM_OBL_RC_ACT: Action on offboard loss
        - COM_OF_LOSS_T: Timeout before triggering
        - COM_OBL_ACT: Secondary action in hover

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

        For our use case (LLM control), RC loss should NOT trigger failsafe
        during offboard flight. This method verifies that exception is set.

        Checks:
        - COM_RC_LOSS_T: RC loss timeout
        - NAV_RCL_ACT: RC loss action
        - COM_RCL_EXCEPT: RC loss exceptions (critical: should be 4)

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

        Battery failures are catastrophic - this protects against:
        - Sudden power loss mid-flight
        - Flying with depleted battery
        - Not knowing battery state

        Checks:
        - BAT_LOW_THR: Low warning threshold (25%)
        - BAT_CRIT_THR: Critical threshold (15%)
        - BAT_EMERGEN_THR: Emergency threshold (10%)
        - COM_LOW_BAT_ACT: Action on low battery (land=2)
        - COM_ARM_BAT_MIN: Minimum to arm (40%)

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

        Geofencing is the "safety net" that prevents:
        - Flyaways from GPS glitches
        - Entry into controlled airspace
        - Loss of control at distance

        For filming: Geofence defines the "operating envelope" for shots.
        Plan missions within these bounds.

        Checks:
        - GF_MAX_HOR_DIST: Horizontal limit (500m)
        - GF_MAX_VER_DIST: Altitude limit (120m)
        - GF_ACTION: Breach action (RTL=3)
        - GF_ALTMODE: Altitude reference (absolute=0)

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

        Data link carries mission-critical information:
        - Battery status
        - Position/altitude
        - System health
        - Video feedback

        Without data link, ground crew cannot make informed decisions.
        RTL allows reconnection at known location.

        Checks:
        - COM_DL_LOSS_T: Data link timeout (5s)
        - NAV_DLL_ACT: Data link loss action (RTL=2)

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

        Convenience method to quickly determine if verification passed.

        Args:
            results: Results from verify_safety_parameters()

        Returns:
            True if all parameters are valid, False otherwise

        Example:
            results = await pm.verify_safety_parameters()
            if not pm.is_safety_configured(results):
                print("SAFETY CHECK FAILED - DO NOT FLY")
        """
        return all(r.is_valid for r in results)

    def get_safety_summary(self, results: List[ParameterStatus]) -> Dict[str, Any]:
        """Generate a human-readable summary of safety configuration.

        Useful for logging, reporting, or UI display.

        Args:
            results: Results from verify_safety_parameters()

        Returns:
            Dictionary with summary statistics and invalid parameter list

        Output format:
            {
                "total_parameters": 14,
                "valid_count": 12,
                "invalid_count": 2,
                "is_safe": False,
                "invalid_parameters": [
                    {
                        "name": "COM_OF_LOSS_T",
                        "expected": 0.5,
                        "actual": 5.0,
                        "message": "Expected 0.5, got 5.0"
                    }
                ]
            }
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

        Call this if you suspect parameters have been changed externally
        (e.g., via QGroundControl while this manager was running).

        Cache is automatically invalidated on parameter writes.
        """
        self._param_cache.clear()
        self._cache_valid = False
        logger.debug("Parameter cache cleared")


# =============================================================================
# Standalone Functions for Quick Checks
# =============================================================================
#
# These functions provide one-off safety checks without managing
# a ParameterManager instance. Useful for scripts and quick diagnostics.


async def quick_safety_check(drone: System) -> Tuple[bool, List[ParameterStatus]]:
    """Perform a quick safety parameter verification.

    Convenience function for one-off safety checks without managing
    the ParameterManager instance. Returns a simple pass/fail result.

    Args:
        drone: Connected MAVSDK System instance

    Returns:
        Tuple of (all_safe, list_of_statuses)
        all_safe: True if all parameters valid, False otherwise
        list_of_statuses: Full details for reporting

    Example:
        is_safe, results = await quick_safety_check(drone)
        if not is_safe:
            print("Safety check failed!")
            for r in results:
                if not r.is_valid:
                    print(f"  - {r.name}: {r.message}")

    Performance:
    - Creates temporary ParameterManager
    - Reads all critical parameters (~1-2 seconds)
    - Returns immediately with results
    """
    manager = PX4ParameterManager(drone)
    results = await manager.verify_safety_parameters()
    return manager.is_safety_configured(results), results


def format_parameter_status(status: ParameterStatus) -> str:
    """Format a ParameterStatus for display.

    Creates a human-readable string suitable for logging or console output.

    Args:
        status: ParameterStatus to format

    Returns:
        Formatted string representation

    Example output:
        [OK] COM_OF_LOSS_T: 0.5000 (expected 0.5000) - Offboard loss timeout
        [FAIL] GF_MAX_HOR_DIST: 1000.0000 (expected 500.0000) - Max horizontal distance
    """
    indicator = "OK" if status.is_valid else "FAIL"
    actual_str = f"{status.actual_value:.4f}" if status.actual_value is not None else "N/A"
    return f"[{indicator}] {status.name}: {actual_str} (expected {status.expected_value:.4f}) - {status.description}"
