"""
MCP Server Tools Package for Project Avatar.
================================================================================

WHAT IS __init__.py?
--------------------
This file marks the 'tools/' directory as a Python package, allowing its contents
to be imported as a module (e.g., 'from avatar.mcp_server.tools import FlightTools').

In Python, __init__.py serves three critical purposes:
1. Package marker: Tells Python "this directory is a module you can import"
2. Initialization: Runs when the package is first imported (setup, logging, etc.)
3. API control: Defines what the package exports via __all__

Think of __init__.py as the "front desk" of a package - it's the first thing
Python runs when someone says "import this package."


WHY DOES THIS FILE EXIST?
-------------------------
Even though Python 3.3+ supports "implicit namespace packages" (directories without
__init__.py), this file actively:

1. RE-EXPORTS: Brings tools from submodules up to the package level
   Instead of: from avatar.mcp_server.tools.flight_tools import FlightTools
   Users write: from avatar.mcp_server.tools import FlightTools

2. ORGANIZES: Groups 30+ tools into 6 logical categories:
   - Flight: Core flight operations
   - Vision: Camera and object detection
   - Telemetry: Real-time status monitoring
   - Acrobatics: Advanced maneuvers
   - Tracking: Gimbal and target following
   - Cinematic: Pre-programmed videography

3. DOCUMENTS: __all[] explicitly lists public API, following PEP 8 best practices


PACKAGE STRUCTURE
-----------------
avatar/mcp_server/tools/
├── __init__.py          <- You are here (exports public API)
├── flight_tools.py      <- Core flight operations (arm, takeoff, land, goto)
├── vision_tools.py      <- YOLO detection and camera control
├── telemetry_tools.py   <- Real-time drone data (battery, position, status)
├── tracking_tools.py    <- Object tracking and gimbal control
├── cinematic_shots.py  <- Pre-programmed drone cinematography
└── acrobatics.py        <- Acrobatic maneuvers (flips, rolls, spins)


HOW THE IMPORTS WORK
--------------------
This file uses "re-export" pattern to flatten the API:

  Submodule                     Package level (this file)
  ──────────────────────────────────────────────────────────
  flight_tools.py               →  re-exported here
    ↓ ↓ ↓                              ↓ ↓ ↓
  arm_and_takeoff()        →  from .flight_tools import arm_and_takeoff
                              ↓
  User imports: from avatar.mcp_server.tools import arm_and_takeoff

Why do this?
- Cleaner imports: Users don't need to know internal file structure
- Flexibility: Can reorganize files without breaking user code
- Discovery: All tools are visible in one place


USAGE EXAMPLES
--------------

1. Basic flight control (most common):
   ```python
   from avatar.mcp_server.tools import arm_and_takeoff, land, get_telemetry

   # Takeoff to 10 meters
   await arm_and_takeoff(altitude=10.0)

   # Check battery
   telemetry = await get_telemetry()
   print(f"Battery: {telemetry.battery.percentage}%")

   # Land
   await land()
   ```

2. Vision-based mission:
   ```python
   from avatar.mcp_server.tools import (
       arm_and_takeoff,
       capture_frame,
       get_detected_objects,
       goto_gps
   )

   await arm_and_takeoff(altitude=20.0)
   frame = await capture_frame()
   detections = await get_detected_objects()

   if detections:
       target = detections[0]
       await goto_gps(lat=target.lat, lon=target.lon, altitude=15.0)
   ```

3. Cinematic shot:
   ```python
   from avatar.mcp_server.tools import (
       list_cinematic_templates,
       execute_cinematic_shot
   )

   # See available shots
   templates = await list_cinematic_templates()
   # ['dolly_zoom', 'orbit_reveal', 'spiral_ascent', ...]

   # Execute a pre-programmed shot
   await execute_cinematic_shot('orbit_reveal', target_lat=37.7749, target_lon=-122.4194)
   ```

4. Class-based configuration (advanced):
   ```python
   from avatar.mcp_server.tools import FlightTools, FlightToolsConfig

   config = FlightToolsConfig(
       default_altitude=15.0,
       rtl_on_disconnect=True
   )
   flight = FlightTools(config)
   await flight.takeoff()
   ```


ARCHITECTURE NOTES
------------------
Safety Architecture:
- All flight commands go through GuardianProcess for validation
- Guardian checks: geofence, altitude limits, battery levels, flight mode
- Telemetry broadcasts at 1Hz minimum for real-time monitoring

Import Patterns:
- Explicit imports (not wildcard) for clarity
- Functions = direct tool calls (MCP server uses these)
- Classes = stateful management (advanced users)
- Config classes = tool configuration

For beginners: Think of __init__.py as the "front desk" of a package. When someone
says "import this package," Python runs this file first to set things up.
================================================================================
"""

# ==============================================================================
# CATEGORY 1: FLIGHT TOOLS - Core flight operations
# ==============================================================================
# These functions handle essential flight control: arming, takeoff, landing,
# navigation, and velocity control. All commands pass through GuardianProcess
# for safety validation before execution.
#
# Safety-first design:
# - arm_and_takeoff: Validates GPS lock and battery before arming
# - goto_gps: Checks geofence bounds before navigation
# - set_velocity: Rate-limited to prevent abrupt movements
# - abort_mission: Immediate emergency stop (highest priority)
# ==============================================================================

from avatar.mcp_server.tools.flight_tools import (
    # Main classes for stateful flight management
    FlightTools,           # High-level flight control interface
    FlightToolsConfig,     # Configuration object for FlightTools
    # Core flight commands (primary MCP tools)
    arm_and_takeoff,       # Arm motors + takeoff to specified altitude (meters)
    goto_gps,              # Navigate to GPS coordinates (lat, lon, alt)
    land,                  # Initiate landing at current position
    rtl,                   # Return to Launch (takeoff point)
    abort_mission,         # Emergency abort - stops all actions immediately
    hold,                  # Enter LOITER mode (hold position)
    set_velocity,          # Direct velocity control (vx, vy, vz in m/s)
    # Utility functions
    haversine_distance,    # Calculate GPS distance between two points (km)
    # State management (for testing/advanced use)
    set_state_machine,     # Inject state machine (testing only)
    get_state_machine,     # Access current state machine
    set_telemetry_cache,   # Configure telemetry caching
    get_telemetry_cache,   # Access telemetry cache
)

# ==============================================================================
# CATEGORY 2: VISION TOOLS - Computer vision and detection
# ==============================================================================
# Vision tools interface with the camera and YOLO object detection pipeline.
# These enable visual navigation, object identification, and AI-powered
# decision making based on the drone's camera feed.
#
# Pipeline: Camera → YOLOv8-nano inference → Object list with confidence scores
# Supported objects: person, car, drone, animal, building, etc. (80+ COCO classes)
# ==============================================================================

from avatar.mcp_server.tools.vision_tools import (
    VisionTools,           # Vision pipeline manager (camera + YOLO)
    VisionToolsConfig,     # Camera resolution, model weights, thresholds
    capture_frame,         # Grab current camera frame (returns image bytes)
    get_detected_objects,  # Run YOLO inference (returns list of detections)
)

# ==============================================================================
# CATEGORY 3: TELEMETRY TOOLS - Real-time status monitoring
# ==============================================================================
# Telemetry provides continuous data stream about drone state. Essential for:
# - Mission monitoring and logging
# - Battery safety (RTL when low)
# - Position tracking and geofencing
# - Connection health checks
#
# Data includes: GPS position, altitude, attitude (roll/pitch/yaw), battery,
# flight mode, velocity, and system health indicators.
# ==============================================================================

from avatar.mcp_server.tools.telemetry_tools import (
    TelemetryTools,        # Telemetry aggregator and broadcaster
    TelemetryToolsConfig,  # Update rates, caching policies
    # Main telemetry functions
    get_telemetry,         # Full telemetry snapshot (position, battery, attitude)
    get_battery_status,    # Battery voltage, current, percentage, remaining time
    get_status,            # Human-readable status summary string
    get_status_tool,       # Formatted dict for MCP tool responses
    # Infrastructure accessors (setup/testing)
    get_connection_manager,  # MAVSDK connection manager
    get_guardian,          # Get GuardianProcess instance (safety validator)
    set_guardian,          # Set custom GuardianProcess (advanced/testing)
)

# ==============================================================================
# CATEGORY 4: ACROBATIC TOOLS - Advanced flight maneuvers
# ==============================================================================
# Pre-programmed acrobatic sequences for demonstration and fun.
# SAFETY WARNING: Only use with sufficient altitude (>20m recommended) and
# in appropriate airspace away from obstacles.
#
# Each maneuver includes:
# - Pre-check: Minimum altitude validation
# - Execution: Timed sequence of attitude/velocity commands
# - Recovery: Automatic stabilization after completion
# ==============================================================================

from avatar.mcp_server.tools.acrobatics import (
    front_flip,            # Forward 360° flip (pitch)
    back_flip,             # Backward 360° flip (pitch)
    barrel_roll,           # 360° roll around longitudinal axis
    yaw_spin,              # 360° rotation around vertical axis
    loop_maneuver,         # Vertical loop (pitch up then over)
    corkscrew,             # Combined roll + yaw spiral pattern
    acrobatic_sequence,    # Chain multiple maneuvers: e.g., [flip, roll, spin]
)

# ==============================================================================
# CATEGORY 5: TRACKING TOOLS - Gimbal control and target tracking
# ==============================================================================
# Tracking tools combine gimbal control with flight path planning to enable
# filming moving subjects or surveying points of interest.
#
# Use cases:
# - set_gimbal: Manual camera angle control
# - point_camera_at: Focus on GPS coordinates while flying
# - orbit_target: Circle around subject (popular for videography)
# - track_target: Follow moving subject (requires vision detection)
# - spiral_search: Expanding spiral for search and rescue
# ==============================================================================

from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal,            # Set gimbal pitch/yaw angles (degrees)
    point_camera_at,       # Aim camera at specific GPS coordinates
    orbit_target,          # Circular orbit around target (radius, speed)
    track_target,          # Follow detected object using vision + flight
    spiral_search,         # Expanding spiral search pattern (search & rescue)
)

# ==============================================================================
# CATEGORY 6: CINEMATIC SHOT TOOLS - Pre-programmed aerial videography
# ==============================================================================
# Professional-grade cinematic shots commonly used in film production.
# Each template combines smooth flight paths with coordinated camera movement.
#
# Templates include:
# - dolly_zoom: Classic "vertigo effect" (move back while zooming in)
# - orbit_reveal: Circle subject while ascending
# - flyover_reveal: Forward flight with camera tilt down
# - spiral_ascent: Spiral up around subject
# - tracking_follow: Smooth follow of moving subject
# ==============================================================================

from avatar.mcp_server.tools.cinematic_shots import (
    execute_cinematic_shot,     # Execute named shot template with parameters
    list_cinematic_templates,   # Get available shot names and descriptions
    preview_cinematic_shot,     # Simulate path without flying (dry run)
)

# ==============================================================================
# CATEGORY 7: META TOOLS - Server health and operation management
# ==============================================================================
# Meta tools manage the MCP server itself rather than controlling the drone.
# They provide health monitoring and operation control capabilities.
#
# These tools work independently of drone connection, making them reliable
# for health checks and debugging even when the drone is offline.
# ==============================================================================

from avatar.mcp_server.tools.meta_tools import (
    ping,                      # Check server liveness (health check)
    async_ping,                # Async wrapper for MCP transport
    cancel_operation,          # Cancel a running long-running operation
    async_cancel_operation,    # Async wrapper for MCP transport
    register_operation,        # Register operation for cancellation tracking
    unregister_operation,      # Remove operation from tracking
    generate_operation_id,     # Generate unique operation ID
    create_cancellable_context, # Create cancellation context for long ops
)

# ==============================================================================
# CATEGORY 8: ORCHESTRATOR TOOLS - Complex multi-step operations
# ==============================================================================
# Orchestrators coordinate multiple primitive operations into sophisticated
# mission patterns. They combine vision, flight, and tracking subsystems.
#
# Available orchestrators:
# - orbit_subject_vision: Orbit around visually-detected subject
# - track_bbox: Track object identified by bounding box with Kalman prediction
# ==============================================================================

from avatar.mcp_server.tools.orchestrators import (
    orbit_subject_vision,    # Orbit around vision-detected subject
    OrbitSubjectVisionInput, # Input schema for orbit orchestrator
    ORBIT_SUBJECT_VISION_TOOL, # Tool registration metadata
    track_bbox,              # Track object via bounding box with Kalman filter
    TrackBboxInput,          # Input schema for track_bbox orchestrator
    TRACK_BBOX_TOOL,         # Tool registration metadata
)

# ==============================================================================
# CATEGORY 9: PRIMITIVE TOOLS - Low-level position control
# ==============================================================================
# Primitive tools provide direct control over drone position using NED frame.
# These are building blocks for higher-level navigation and mission planning.
#
# NED Frame:
# - North: Positive = northward from home
# - East: Positive = eastward from home
# - Down: Positive = descending (NEGATIVE = UP)
#
# Uses offboard mode for precise position control with OffboardOwner for
# mutual exclusion and 20Hz setpoint streaming.
# ==============================================================================

from avatar.mcp_server.tools.primitives import (
    set_position_ned,       # Command position in NED frame (offboard mode)
    SetPositionNedInput,    # Input schema for position validation
    PositionStreamer,       # 20Hz setpoint streaming for position control
    PositionToolsConfig,    # Configuration for position tools
    set_yaw,                # Command yaw angle (heading)
    SetYawInput,            # Input schema for yaw validation
)

# ==============================================================================
# CATEGORY 10: PREFLIGHT TOOLS - Safety validation before flight
# ==============================================================================
# Preflight tools run safety checks before arming the drone.
# They validate GPS lock, battery level, home position, sensor calibration,
# and MAVLink connection status.
#
# Use before any arm command to ensure safe flight conditions.
# ==============================================================================

from avatar.mcp_server.tools.primitives_preflight import (
    run_preflight,               # Run preflight checks and return results
    handle_run_preflight,        # MCP handler for preflight tool
    RunPreflightInput,           # Input schema for preflight checks
    PreflightResult,             # Output schema for preflight results
    run_preflight_tool_schema,   # JSON schema for MCP registration
    run_preflight_output_schema, # JSON schema for MCP registration
    run_preflight_annotations,   # MCP tool annotations
)

# ==============================================================================
# CATEGORY 11: MISSION INTELLIGENCE TOOLS - D8 Wave 2b
# ==============================================================================
# Mission intelligence provides area analysis, planning, and safety checks.
# Works offline-first using OSM/SRTM data when cached.
# ==============================================================================

from avatar.mcp_server.tools.mission_intel_tools import (
    analyze_area,              # Analyze area for drone flight planning
    lookup_place,              # Look up a place by name or address
    get_elevation,             # Get ground elevation for coordinates
    get_agl,                   # Calculate Above Ground Level altitude
    plan_scenic_sweep,         # Plan a scenic sweep mission
    plan_mission_from_intent,  # Plan mission from natural language intent
    propose_orbit_for_subject, # Propose an orbit plan for a subject
    # Tool definitions
    ANALYZE_AREA_TOOL,
    LOOKUP_PLACE_TOOL,
    GET_ELEVATION_TOOL,
    GET_AGL_TOOL,
    PLAN_SCENIC_SWEEP_TOOL,
    PLAN_MISSION_FROM_INTENT_TOOL,
    PROPOSE_ORBIT_FOR_SUBJECT_TOOL,
)

# ==============================================================================
# PUBLIC API DEFINITION (__all__)
# ==============================================================================
# __all__ controls what gets imported with 'from module import *'
# Following PEP 8: explicit is better than implicit
#
# We export 30+ symbols organized by category. Each export is commented with:
# - What it does (brief description)
# - Type: Class (C), Function (F), Config (Cfg)
# ==============================================================================

__all__ = [
    # -----------------------------------------------------------------------------
    # FLIGHT TOOLS (11 exports)
    # Core flight operations - essential for any mission
    # -----------------------------------------------------------------------------
    "FlightTools",           # (C) Flight control interface
    "FlightToolsConfig",     # (Cfg) Flight configuration
    "arm_and_takeoff",       # (F) Arm motors and takeoff to altitude
    "goto_gps",              # (F) Navigate to GPS coordinates
    "land",                  # (F) Initiate landing sequence
    "rtl",                   # (F) Return to Launch point
    "abort_mission",         # (F) Emergency mission abort
    "hold",                  # (F) Hold current position
    "haversine_distance",    # (F) GPS distance calculation (utility)
    "set_state_machine",     # (F) Configure state machine (testing)
    "set_telemetry_cache",   # (F) Set telemetry cache (testing)
    "get_state_machine",     # (F) Get state machine (testing)
    "get_telemetry_cache",   # (F) Get telemetry cache (testing)
    "set_velocity",          # (F) Direct velocity control (vx, vy, vz)

    # -----------------------------------------------------------------------------
    # VISION TOOLS (4 exports)
    # Computer vision and YOLO object detection
    # -----------------------------------------------------------------------------
    "VisionTools",           # (C) Vision pipeline manager
    "VisionToolsConfig",     # (Cfg) Vision configuration
    "capture_frame",         # (F) Capture camera frame
    "get_detected_objects",  # (F) Get YOLO detection results

    # -----------------------------------------------------------------------------
    # TELEMETRY TOOLS (9 exports)
    # Real-time status monitoring and infrastructure
    # -----------------------------------------------------------------------------
    "TelemetryTools",        # (C) Telemetry manager
    "TelemetryToolsConfig",  # (Cfg) Telemetry configuration
    "get_telemetry",         # (F) Get full telemetry data
    "get_battery_status",    # (F) Battery voltage and percentage
    "get_status",            # (F) Status summary string
    "get_status_tool",       # (F) Formatted status for MCP
    "get_connection_manager",  # (F) MAVSDK connection accessor
    "get_guardian",          # (F) Get GuardianProcess instance
    "set_guardian",          # (F) Set GuardianProcess (testing)

    # -----------------------------------------------------------------------------
    # ACROBATIC TOOLS (7 exports)
    # Advanced maneuvers - for demonstration and fun
    # -----------------------------------------------------------------------------
    "front_flip",            # (F) Forward flip maneuver
    "back_flip",             # (F) Backward flip maneuver
    "barrel_roll",           # (F) Roll around longitudinal axis
    "yaw_spin",              # (F) 360-degree yaw rotation
    "loop_maneuver",         # (F) Vertical loop
    "corkscrew",             # (F) Spiral roll+yaw maneuver
    "acrobatic_sequence",    # (F) Multi-maneuver chain

    # -----------------------------------------------------------------------------
    # TRACKING TOOLS (5 exports)
    # Gimbal control and target tracking for videography
    # -----------------------------------------------------------------------------
    "set_gimbal",            # (F) Control gimbal angles
    "point_camera_at",       # (F) Point camera at GPS coords
    "orbit_target",          # (F) Orbit around target
    "track_target",          # (F) Follow detected target
    "spiral_search",         # (F) Spiral search pattern

    # -----------------------------------------------------------------------------
    # CINEMATIC TOOLS (3 exports)
    # Pre-programmed aerial videography shots
    # -----------------------------------------------------------------------------
    "execute_cinematic_shot",    # (F) Execute shot template
    "list_cinematic_templates",  # (F) List available shots
    "preview_cinematic_shot",    # (F) Preview shot path

    # -----------------------------------------------------------------------------
    # META TOOLS (9 exports)
    # Server health and operation management
    # -----------------------------------------------------------------------------
    "ping",                      # (F) Check server liveness
    "async_ping",                # (F) Async ping for MCP
    "cancel_operation",          # (F) Cancel running operation
    "async_cancel_operation",    # (F) Async cancel for MCP
    "register_operation",        # (F) Register operation for cancellation
    "unregister_operation",      # (F) Remove operation from tracking
    "generate_operation_id",     # (F) Generate unique operation ID
    "create_cancellable_context", # (F) Create cancellation context

    # -----------------------------------------------------------------------------
    # ORCHESTRATOR TOOLS (6 exports)
    # Complex multi-step operations combining vision + flight + tracking
    # -----------------------------------------------------------------------------
    "orbit_subject_vision",      # (F) Orbit around vision-detected subject
    "OrbitSubjectVisionInput",   # (Schema) Input validation for orbit
    "ORBIT_SUBJECT_VISION_TOOL", # (Meta) Tool registration metadata
    "track_bbox",                # (F) Track object via bbox with Kalman filter
    "TrackBboxInput",            # (Schema) Input validation for track_bbox
    "TRACK_BBOX_TOOL",           # (Meta) Tool registration metadata

    # -----------------------------------------------------------------------------
    # PRIMITIVE TOOLS (6 exports)
    # Low-level position control in NED frame
    # -----------------------------------------------------------------------------
    "set_position_ned",          # (F) Command position in NED frame
    "SetPositionNedInput",       # (Schema) Input validation for position
    "PositionStreamer",          # (C) 20Hz setpoint streaming
    "PositionToolsConfig",       # (Cfg) Position tools configuration
    "set_yaw",                   # (F) Command yaw angle (heading)
    "SetYawInput",               # (Schema) Input validation for yaw

    # -----------------------------------------------------------------------------
    # PREFLIGHT TOOLS (7 exports)
    # Safety validation checks before flight
    # -----------------------------------------------------------------------------
    "run_preflight",             # (F) Run preflight checks and return results
    "handle_run_preflight",      # (F) MCP handler for preflight tool
    "RunPreflightInput",         # (Schema) Input validation for preflight
    "PreflightResult",           # (Schema) Output schema for preflight results
    "run_preflight_tool_schema", # (F) JSON schema for MCP registration
    "run_preflight_output_schema", # (F) JSON schema for MCP registration
    "run_preflight_annotations", # (F) MCP tool annotations

    # -----------------------------------------------------------------------------
    # MISSION INTELLIGENCE TOOLS (D8)
    # Area analysis, planning, and safety checks
    # Offline-first using OSM/SRTM data
    # -----------------------------------------------------------------------------
    "analyze_area",              # (F) Analyze area for drone flight planning
    "lookup_place",              # (F) Look up a place by name or address
    "get_elevation",             # (F) Get ground elevation for coordinates
    "get_agl",                   # (F) Calculate Above Ground Level altitude
    "plan_scenic_sweep",         # (F) Plan a scenic sweep mission
    "plan_mission_from_intent",  # (F) Plan mission from natural language intent
    "propose_orbit_for_subject", # (F) Propose an orbit plan for a subject
]
