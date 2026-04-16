"""
MAVSDK Drone Communication Layer - Package Exports

This __init__.py exports the public API for MAVSDK-based drone communication,
safety monitoring, and PX4 parameter management.

================================================================================
WHAT IS __init__.py? (For Beginners)
================================================================================

This file is the "front door" to the 'avatar.mav' package. When you write:

    from avatar.mav import AsyncGuardian

Python executes this file and uses the imports below to find AsyncGuardian.

Think of __init__.py like a store's display window - it shows the most
important items you can "buy" (import) from this package without making
you walk through the warehouse (individual module files).

================================================================================
WHY WE EXPORT THESE CLASSES
================================================================================

The 'mav' package handles low-level drone communication. We export:

1. SAFETY COMPONENTS (from escalation_matrix, guardian_async)
   - AsyncGuardian: Real-time safety monitoring (20Hz watchdog)
   - EscalationMatrix: Fail-safe escalation rules
   - SeverityLevel: Safety event severity classification
   -> These MUST be easily accessible because safety is critical

2. HEARTBEAT MONITORING (from heartbeat_service)
   - HeartbeatService: PX4 offboard mode heartbeat (20Hz required)
   - HeartbeatConfig: Configuration for heartbeat behavior
   -> Required to maintain connection with PX4 autopilot

3. PROTOCOLS & INTERFACES (from protocols)
   - DroneConnectionProtocol: Interface for drone connections
   - TelemetryProviderProtocol: Interface for telemetry data
   - SafetyValidatorProtocol: Interface for safety checks
   -> Protocols enable dependency injection and testing

4. RESOURCE MANAGEMENT (from resource_monitor)
   - ResourceMonitor: Track CPU/memory/battery
   - GracefulDegradationManager: Reduce features under pressure
   -> Essential for long-running autonomous missions

5. PX4 PARAMETERS (from px4_parameters)
   - PX4ParameterManager: Read/write PX4 flight controller settings
   - CRITICAL_PARAMETERS: Safety-critical parameter names
   - quick_safety_check: Validate pre-flight settings
   -> Required for configuring the flight controller safely

================================================================================
HOW IMPORTS WORK HERE
================================================================================

There are TWO ways things become available:

1. Direct imports at the top of this file:
       from avatar.mav.guardian_async import AsyncGuardian

   This makes 'AsyncGuardian' available as:
       from avatar.mav import AsyncGuardian

2. The __all__ list at the bottom:
   - Documents what's public API (vs internal)
   - Controls what 'from avatar.mav import *' imports
   - Prevents accidentally exporting internal helpers

IMPORT CHAIN EXAMPLE:
--------------------------
Your code:          from avatar.mav import AsyncGuardian
                          ↓
This __init__.py:    from avatar.mav.guardian_async import AsyncGuardian
                          ↓
guardian_async.py:   class AsyncGuardian: ... (actual implementation)

================================================================================
LAZY IMPORTS (WHY WE USE try/except)
================================================================================

You may notice some submodules use try/except around imports. This is because:

1. MAVSDK requires specific system dependencies
2. Not all environments have PX4 SITL installed
3. We want 'import avatar.mav' to work even if some components can't load

If a component fails to import, it's set to None and won't be in __all__.

================================================================================
PACKAGE STRUCTURE
================================================================================

avatar/mav/
├── __init__.py              <- This file - public API exports
├── escalation_matrix.py     <- Safety escalation rules & timers
├── heartbeat_service.py     <- PX4 heartbeat for offboard mode
├── protocols.py             <- Abstract interfaces (Protocols)
├── resource_monitor.py      <- Resource pressure monitoring
├── guardian_async.py         <- Real-time safety watchdog
└── px4_parameters.py        <- PX4 flight controller configuration

================================================================================
USAGE EXAMPLES
================================================================================

# Basic safety import
from avatar.mav import AsyncGuardian, GuardianConfig

# Protocols for type hints
from avatar.mav import DroneConnectionProtocol, TelemetryProviderProtocol

# Resource monitoring
from avatar.mav import ResourceMonitor, create_rtl_monitor

# PX4 parameters
from avatar.mav import PX4ParameterManager, quick_safety_check

# Everything at once (not recommended for production)
from avatar.mav import *
"""

# =============================================================================
# ACTUAL IMPORTS
# =============================================================================

# --- Safety Escalation System ---
# These handle failsafe responses when something goes wrong
from avatar.mav.escalation_matrix import (
    check_battery_level,      # Validate battery against thresholds
    check_geofence_breach,    # Detect if drone left safe zone
    check_heartbeat,          # Verify communication link health
    EscalationEvent,          # Data class for safety events
    EscalationMatrix,         # Rule engine for fail-safe responses
    EscalationRule,           # Single escalation rule definition
    EscalationTimer,          # Time-based escalation triggers
    SeverityLevel,            # Enum: INFO, WARNING, CRITICAL, EMERGENCY
)

# --- Heartbeat Service ---
# Required for PX4 offboard mode - must send heartbeats at 20Hz
from avatar.mav.heartbeat_service import (
    HeartbeatConfig,          # Configuration for heartbeat timing
    HeartbeatService,         # Main service that sends heartbeats
    HeartbeatSource,          # Identifies heartbeat origin
)

# --- Protocol Definitions ---
# Abstract interfaces - use these for type hints and mocking in tests
from avatar.mav.protocols import (
    DroneConnectionProtocol,      # Interface: connect(), disconnect()
    GeoPoint,                     # Data class: lat, lon, alt
    HeartbeatMonitorProtocol,     # Interface: monitor_heartbeat()
    SafetyLimits,                 # Data class: speed, altitude limits
    SafetyValidatorProtocol,      # Interface: validate_action()
    TelemetryProviderProtocol,    # Interface: get_telemetry()
    VelocityNED,                  # Data class: north, east, down velocities
)

# --- Resource Monitoring ---
# Monitor system resources and gracefully degrade under pressure
from avatar.mav.resource_monitor import (
    GracefulDegradationManager,  # Reduces features when resources low
    ResourceCallback,            # Callback type for resource events
    ResourceMonitor,             # Main monitoring service
    ResourcePressureLevel,       # Enum: NONE, LIGHT, MODERATE, SEVERE
    ResourceStatus,              # Data class: current resource state
    ResourceThresholds,          # Configuration for pressure levels
    create_rtl_monitor,          # Factory: RTL when battery low
)

# --- Async Guardian ---
# The main safety watchdog - monitors everything, triggers failsafes
from avatar.mav.guardian_async import (
    Alert,                   # Data class: safety alert information
    AsyncGuardian,           # Main safety monitoring class (20Hz)
    GuardianConfig,          # Configuration for guardian behavior
    GuardianStatus,          # Enum: ACTIVE, PAUSED, STANDBY, ERROR
    MonitorType,             # Enum: HEARTBEAT, GEOFENCE, BATTERY, etc.
    ResourceMetrics,         # Data class: CPU, memory, VIO status
    SafetyAction,            # Enum: LOG, WARN, RTL, LAND, KILL
    VIOMetrics,              # Data class: Visual Inertial Odometry status
)

# --- PX4 Parameters ---
# Flight controller configuration and safety checks
from avatar.mav.px4_parameters import (
    # Parameter groups - tuples of parameter names
    CRITICAL_PARAMETERS,       # Must-verify params for safety
    OFFBOARD_FAILSAFE_PARAMS,  # Offboard mode fail-safe settings
    RC_FAILSAFE_PARAMS,        # Remote control fail-safe settings
    BATTERY_FAILSAFE_PARAMS,   # Battery warning/RTL levels
    GEOFENCE_PARAMS,           # Geofence configuration params
    DATA_LINK_PARAMS,          # Data loss fail-safe settings
    # Classes and functions
    ParameterStatus,           # Data class: param validation result
    PX4ParameterManager,       # Read/write PX4 parameters
    PX4ParameterError,         # Exception for param operations
    SafetyError,               # Exception for safety violations
    quick_safety_check,        # Fast pre-flight param validation
    format_parameter_status,   # Pretty-print param status
)

# =============================================================================
# PUBLIC API DEFINITION
# =============================================================================

# __all__ controls what gets imported with 'from avatar.mav import *'
# It also documents our official public API
__all__ = [
    # ========================== Escalation Matrix ==============================
    "check_battery_level",
    "check_geofence_breach",
    "check_heartbeat",
    "EscalationEvent",
    "EscalationMatrix",
    "EscalationRule",
    "EscalationTimer",
    "SeverityLevel",

    # ============================ Guardian ===================================
    "Alert",
    "AsyncGuardian",
    "GuardianConfig",
    "GuardianStatus",
    "MonitorType",
    "ResourceMetrics",
    "SafetyAction",
    "VIOMetrics",

    # ========================= Heartbeat Service =============================
    "HeartbeatConfig",
    "HeartbeatService",
    "HeartbeatSource",

    # ============================= Protocols =================================
    "DroneConnectionProtocol",
    "GeoPoint",
    "HeartbeatMonitorProtocol",
    "SafetyLimits",
    "SafetyValidatorProtocol",
    "TelemetryProviderProtocol",
    "VelocityNED",

    # ========================= Resource Monitor ==============================
    "GracefulDegradationManager",
    "ResourceCallback",
    "ResourceMonitor",
    "ResourcePressureLevel",
    "ResourceStatus",
    "ResourceThresholds",
    "create_rtl_monitor",

    # ========================== PX4 Parameters ===============================
    "BATTERY_FAILSAFE_PARAMS",
    "CRITICAL_PARAMETERS",
    "DATA_LINK_PARAMS",
    "GEOFENCE_PARAMS",
    "OFFBOARD_FAILSAFE_PARAMS",
    "RC_FAILSAFE_PARAMS",
    "format_parameter_status",
    "ParameterStatus",
    "PX4ParameterError",
    "PX4ParameterManager",
    "quick_safety_check",
    "SafetyError",
]
