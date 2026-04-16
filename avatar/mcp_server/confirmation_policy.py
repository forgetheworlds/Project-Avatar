"""Confirmation policy for critical drone operations.

This module defines which PX4 parameters require explicit confirmation before
modification, based on their safety-critical nature. These parameters control
failsafe behaviors, navigation limits, and critical flight characteristics.

SAFETY RATIONALE:
=================
PX4 parameters can significantly alter drone behavior. Some parameters are
"dangerous" because changing them can:

1. DISABLE FAILSAFES: Preventing automatic safety responses
2. EXPAND FLIGHT ENVELOPE: Allowing flight beyond safe limits
3. CHANGE RECOVERY BEHAVIOR: Altering how the drone responds to emergencies

These parameters require explicit human confirmation before modification
to ensure the operator understands the implications of the change.

PARAMETER CATEGORIES:
====================

1. DISARM PARAMETERS:
   - COM_DISARM_PRFLT: Disarm on landing detection
   - COM_DISARM_LAND: Automatically disarm after landing
   These control whether the drone automatically disarms. Disabling
   auto-disarm can be useful for specific scenarios but increases
   risk of spinning props while on ground.

2. NAVIGATION FAILSAFES:
   - NAV_DLL_ACT: Action on datalink loss (RTL, Land, etc.)
   - NAV_RCL_ACT: Action on RC signal loss
   These define what happens when communication is lost. Setting to
   "disabled" removes this safety net.

3. GEOFENCE PARAMETERS:
   - GF_ACTION: Action when geofence is breached
   Controls whether the drone responds to geofence violations.
   Disabling this allows flight outside the safe operating area.

4. BATTERY FAILSAFES:
   - BAT_LOW_THR: Low battery threshold percentage
   - BAT_CRIT_THR: Critical battery threshold percentage
   These define when battery warnings trigger. Setting thresholds
   too low risks in-flight power loss.

5. SAFETY BEHAVIORS:
   - COM_OBL_RC_ACT: Action when operating without RC link
   Controls behavior when RC control is not available. Important
   for autonomous-only operations.

6. FLIGHT ENVELOPE:
   - MPC_XY_CRUISE: Default cruise speed in mission
   - MPC_Z_VEL_MAX_UP: Maximum upward velocity
   - MPC_Z_VEL_MAX_DN: Maximum downward velocity
   - MIS_TAKEOFF_ALT: Default takeoff altitude
   These define flight envelope limits. Increasing these can
   violate airspace regulations or exceed hardware capabilities.

USAGE:
======
Before modifying any parameter, check if it's in CRITICAL_PARAMETERS:

    from avatar.mcp_server.confirmation_policy import CRITICAL_PARAMETERS

    if parameter_name in CRITICAL_PARAMETERS:
        # Require confirmation via ConfirmationManager
        token = await confirmation_manager.require(
            action=f"set_parameter_{parameter_name}",
            destructive=True,
            summary=f"Set {parameter_name} to {value}",
            payload={"parameter": parameter_name, "value": value}
        )
        response = confirmation_manager.get_pending(token.token)
        if not response or not response["approved"]:
            # Parameter change rejected
            return

    # Proceed with parameter change

CONFIGURATION:
==============
The set of critical parameters can be extended by combining frozensets:

    CUSTOM_CRITICAL = CRITICAL_PARAMETERS | frozenset({
        "MY_CUSTOM_PARAM",
    })

This allows project-specific safety policies while maintaining the base set.
"""

# Critical parameters that require explicit confirmation before modification.
# These parameters control failsafe behaviors, navigation limits, and
# safety-critical flight characteristics. Modifying them can significantly
# alter the drone's safety profile.
CRITICAL_PARAMETERS: frozenset[str] = frozenset({
    # -------------------------------------------------------------------------
    # DISARM BEHAVIOR
    # -------------------------------------------------------------------------
    # These control automatic disarming, which affects ground safety.
    # Disabling auto-disarm leaves props spinning after landing.
    "COM_DISARM_PRFLT",   # Automatically disarm after landing detection
    "COM_DISARM_LAND",    # Automatically disarm on landing

    # -------------------------------------------------------------------------
    # NAVIGATION FAILSAFES
    # -------------------------------------------------------------------------
    # These define automatic responses to communication loss.
    # Disabling these removes the safety net for link failures.
    "NAV_DLL_ACT",        # Datalink loss action (0=disabled, 1=RTL, 2=Land)
    "NAV_RCL_ACT",        # RC signal loss action

    # -------------------------------------------------------------------------
    # GEOFENCE BEHAVIOR
    # -------------------------------------------------------------------------
    # Controls response to geofence violations.
    # Disabling allows flight outside the designated safe area.
    "GF_ACTION",          # Geofence violation action

    # -------------------------------------------------------------------------
    # BATTERY FAILSAFES
    # -------------------------------------------------------------------------
    # Define battery level thresholds for warnings and failsafes.
    # Setting these too low risks in-flight power loss.
    "BAT_LOW_THR",        # Low battery warning threshold (%)
    "BAT_CRIT_THR",       # Critical battery threshold (%)

    # -------------------------------------------------------------------------
    # OPERATIONAL SAFETY
    # -------------------------------------------------------------------------
    # Behavior when operating without RC control link.
    "COM_OBL_RC_ACT",     # Action on RC loss in mission

    # -------------------------------------------------------------------------
    # FLIGHT ENVELOPE
    # -------------------------------------------------------------------------
    # Define speed and altitude limits. Increasing these can violate
    # regulations or exceed hardware capabilities.
    "MPC_XY_CRUISE",      # Default cruise speed in mission (m/s)
    "MPC_Z_VEL_MAX_UP",   # Maximum upward velocity (m/s)
    "MPC_Z_VEL_MAX_DN",   # Maximum downward velocity (m/s)
    "MIS_TAKEOFF_ALT",    # Default takeoff altitude (m)
})


# Additional parameter categories for specific use cases

# Parameters that can DISABLE a failsafe entirely
FAILSAFE_DISABLE_PARAMETERS: frozenset[str] = frozenset({
    "NAV_DLL_ACT",        # Setting to 0 disables datalink loss action
    "NAV_RCL_ACT",        # Setting to 0 disables RC loss action
    "GF_ACTION",          # Setting to 0 disables geofence action
})

# Parameters that affect FLIGHT ENVELOPE limits
FLIGHT_ENVELOPE_PARAMETERS: frozenset[str] = frozenset({
    "MPC_XY_CRUISE",
    "MPC_Z_VEL_MAX_UP",
    "MPC_Z_VEL_MAX_DN",
    "MIS_TAKEOFF_ALT",
})

# Parameters that affect BATTERY SAFETY
BATTERY_SAFETY_PARAMETERS: frozenset[str] = frozenset({
    "BAT_LOW_THR",
    "BAT_CRIT_THR",
})


def is_critical_parameter(parameter_name: str) -> bool:
    """Check if a parameter requires confirmation before modification.

    Args:
        parameter_name: PX4 parameter name (case-sensitive).

    Returns:
        True if the parameter is in CRITICAL_PARAMETERS, False otherwise.

    Example:
        >>> is_critical_parameter("NAV_DLL_ACT")
        True
        >>> is_critical_parameter("MPC_THR_CURVE1")
        False
    """
    return parameter_name in CRITICAL_PARAMETERS


def get_parameter_category(parameter_name: str) -> str:
    """Get the safety category for a parameter.

    Args:
        parameter_name: PX4 parameter name.

    Returns:
        Category string: "failsafe_disable", "flight_envelope",
        "battery_safety", or "other".

    Example:
        >>> get_parameter_category("NAV_DLL_ACT")
        'failsafe_disable'
        >>> get_parameter_category("MPC_XY_CRUISE")
        'flight_envelope'
    """
    if parameter_name in FAILSAFE_DISABLE_PARAMETERS:
        return "failsafe_disable"
    if parameter_name in FLIGHT_ENVELOPE_PARAMETERS:
        return "flight_envelope"
    if parameter_name in BATTERY_SAFETY_PARAMETERS:
        return "battery_safety"
    return "other"
