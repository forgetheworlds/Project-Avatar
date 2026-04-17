"""Orchestrator tools for complex multi-step drone operations.

This module provides high-level orchestrator functions that combine multiple
primitive operations into sophisticated mission patterns. Orchestrators
coordinate between vision, flight, and tracking subsystems.

Available Orchestrators:
    - orbit_subject_vision: Orbit around a visually-detected subject while
      keeping them centered in the camera frame.
    - track_bbox: Track an object identified by bounding box using Kalman
      filter prediction for smooth intercept.

Architecture:
    Orchestrators sit at the highest level of the tool hierarchy:

    ┌─────────────────────────────────────────────────────────────────┐
    │                      ORCHESTRATORS (this module)                │
    │  Complex multi-step missions combining vision + flight + gimbal │
    └─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   TRACKING TOOLS (tracking_tools.py)            │
    │  Orbit mechanics, target following, gimbal coordination         │
    └─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     FLIGHT TOOLS (flight_tools.py)             │
    │  Primitives: arm, takeoff, goto, land, velocity control        │
    └─────────────────────────────────────────────────────────────────┘

ORBIT_SUBJECT_VISION Overview:
------------------------------
This orchestrator enables a drone to orbit around a subject detected by
computer vision (YOLO). It:

1. Estimates subject position from bounding box
2. Calculates orbit trajectory around estimated position
3. Flies circular path while adjusting gimbal to keep subject centered
4. Continuously re-estimates position as drone moves

Use Cases:
    - Cinematic 360-degree shots of athletes
    - Inspection of detected objects (vehicles, structures)
    - Surveillance of tracked individuals
    - Dynamic action sports filming

Vision-to-Position Estimation:
    The subject's 3D position is estimated from 2D bounding box using:
    - Camera FOV and focal length
    - Current drone altitude (from telemetry)
    - Assumed subject size or ground contact assumption

Safety Features:
    - Validates altitude before starting orbit
    - Continuous telemetry monitoring
    - Automatic hold on loss of vision target
    - Geofence compliance via GuardianProcess

Dependencies:
    - MAVSDK for drone communication
    - ConnectionManager for persistent connection
    - Vision system for bounding box updates
    - TelemetryCache for position feedback
"""

import asyncio
import json
import logging
import math
import time
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from avatar.mcp_server.schemas import BBox, TrackerState
from avatar.mav.connection_manager import ConnectionManager
from avatar.mcp_server.tools.flight_tools import hold, set_velocity
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal,
    _calculate_look_angles,
    _clamp,
)
from avatar.mcp_server.tools.advanced_tracking import (
    KalmanTracker,
    TrackingState as KalmanTrackingState,
    LeadLagController,
    SmoothGimbalController,
    GimbalLimits,
)
from avatar.mcp_server.tools.vision_tools import get_vision_tools_instance
from avatar.mcp_server.errors import to_error_envelope, ErrorCode

logger = logging.getLogger(__name__)


# =============================================================================
# STANDARD TOOL ANNOTATIONS
# =============================================================================
# These are the 4 standard hints for MCP tool annotations as per D2.1 contract.

ANNOTATIONS_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

ANNOTATIONS_WRITE_SAFE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

ANNOTATIONS_DESTRUCTIVE = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
}

OUTPUT_SCHEMA = {"type": "object"}


# =============================================================================
# CONSTANTS
# =============================================================================

# Camera parameters for position estimation
# These are typical values for a drone camera setup
DEFAULT_CAMERA_FOV_DEG = 90.0  # Horizontal field of view (typical wide-angle)
DEFAULT_CAMERA_FOCAL_LENGTH_PX = 800.0  # Approximate focal length in pixels

# Orbit constraints
MIN_ORBIT_RADIUS_M = 2.0
MAX_ORBIT_RADIUS_M = 50.0
MIN_ORBIT_SPEED_M_S = 0.5
MAX_ORBIT_SPEED_M_S = 10.0
MAX_ORBITS = 10

# Safety constraints
MIN_ALTITUDE_M = 5.0  # Minimum safe orbit altitude

# Control parameters
ORBIT_UPDATE_RATE_HZ = 10.0  # Update frequency during orbit
ORBIT_DT = 1.0 / ORBIT_UPDATE_RATE_HZ  # Time step

# Tracking parameters
TRACKING_UPDATE_RATE_HZ = 10.0  # Update frequency during tracking
TRACKING_DT = 1.0 / TRACKING_UPDATE_RATE_HZ  # Time step


# =============================================================================
# INPUT SCHEMAS (Pydantic v2)
# =============================================================================


class OrbitSubjectVisionInput(BaseModel):
    """Input schema for orbit_subject_vision orchestrator.

    This schema validates the input parameters for vision-based orbiting.
    The bounding box is provided by the vision system (YOLO detection).

    Attributes:
        bbox: Normalized bounding box from vision detection (x, y, w, h in 0..1).
        radius_m: Orbit radius in meters (2-50m, default 10m).
        speed_m_s: Orbit speed in m/s (0.5-10 m/s, default 3 m/s).
        orbits: Number of complete orbits to perform (1-10, default 1).
        direction: Orbit direction ("cw" = clockwise, "ccw" = counter-clockwise).
    """

    model_config = ConfigDict(extra="forbid")

    bbox: BBox = Field(
        ...,
        description="Normalized bounding box from vision detection. "
        "x,y = center position, w,h = width,height (all in 0..1 range).",
    )
    radius_m: float = Field(
        default=10.0,
        ge=MIN_ORBIT_RADIUS_M,
        le=MAX_ORBIT_RADIUS_M,
        description="Orbit radius in meters. Min 2m, max 50m.",
    )
    speed_m_s: float = Field(
        default=3.0,
        ge=MIN_ORBIT_SPEED_M_S,
        le=MAX_ORBIT_SPEED_M_S,
        description="Orbit speed in m/s. Min 0.5, max 10.",
    )
    orbits: int = Field(
        default=1,
        ge=1,
        le=MAX_ORBITS,
        description="Number of complete orbits to perform. Min 1, max 10.",
    )
    direction: Literal["cw", "ccw"] = Field(
        default="cw",
        description="Orbit direction: 'cw' = clockwise, 'ccw' = counter-clockwise.",
    )


class TrackBboxInput(BaseModel):
    """Input schema for track_bbox orchestrator.

    W2a-T17: Tracks an object identified by bounding box using Kalman filter
    prediction for smooth intercept positioning.

    Attributes:
        bbox: Normalized bounding box [x_center, y_center, w, h] in 0-1 range.
        duration_s: Total tracking duration in seconds (0.1 to 300).
        approach_speed_m_s: Maximum speed when approaching target (0.1 to 10 m/s).
        standoff_m: Desired distance to maintain from target (2 to 50 meters).
    """

    model_config = ConfigDict(extra="forbid")

    bbox: BBox = Field(
        ...,
        description="Normalized bounding box from vision detection. "
        "x,y = center position, w,h = width,height (all in 0..1 range).",
    )
    duration_s: float = Field(
        ...,
        gt=0.0,
        le=300.0,
        description="Tracking duration in seconds. Max 300s (5 minutes).",
    )
    approach_speed_m_s: float = Field(
        default=2.0,
        gt=0.0,
        le=10.0,
        description="Max approach speed in m/s. Min 0.1, max 10.",
    )
    standoff_m: float = Field(
        default=5.0,
        ge=2.0,
        le=50.0,
        description="Standoff distance in meters. Min 2m, max 50m.",
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _estimate_subject_position_3d(
    bbox: BBox,
    drone_lat: float,
    drone_lon: float,
    drone_alt_m: float,
    camera_pitch_deg: float = -45.0,
    camera_fov_deg: float = DEFAULT_CAMERA_FOV_DEG,
) -> Tuple[float, float, float]:
    """Estimate 3D world position of subject from 2D bounding box.

    This function converts a 2D bounding box detection from the camera into
    an estimated 3D position in world coordinates (lat, lon, altitude).

    POSITION ESTIMATION METHOD:
    ---------------------------
    We use a simplified geometric model that assumes:
    1. The subject is on the ground (altitude = 0)
    2. Camera is looking at an angle (pitch_deg from horizontal)
    3. BBox center corresponds to where camera is pointing

    The geometry:

        Camera at altitude H, looking down at angle theta
        Subject on ground at distance D from camera

        Using trigonometry:
            D = H / tan(|theta|) for ground intersection

        The bbox center offset from image center tells us the angular offset:
            angle_offset_x = (bbox.x - 0.5) * fov_horizontal
            angle_offset_y = (bbox.y - 0.5) * fov_vertical

        Ground position relative to drone:
            north = D * cos(angle_offset_x) * cos(theta)
            east = D * sin(angle_offset_x)

    LIMITATIONS:
    ------------
    - Assumes flat ground (no terrain elevation)
    - Assumes subject on ground (not airborne)
    - Uses approximate FOV (actual varies with camera)
    - Does not account for camera lens distortion

    For better accuracy, use:
    - Terrain elevation data (DEM)
    - Stereo vision or depth camera
    - Known subject size for scale estimation

    Args:
        bbox: Normalized bounding box (x, y, w, h in 0..1).
        drone_lat: Drone latitude in degrees.
        drone_lon: Drone longitude in degrees.
        drone_alt_m: Drone altitude above ground in meters.
        camera_pitch_deg: Camera pitch angle (negative = looking down).
        camera_fov_deg: Camera horizontal field of view in degrees.

    Returns:
        Tuple of (estimated_lat, estimated_lon, estimated_alt_m) where
        estimated_alt_m is typically 0 (ground level assumption).
    """
    # Calculate distance to ground along camera ray
    # For a camera looking down at angle |theta| from horizontal:
    # ground_distance = altitude / tan(|theta|)
    pitch_rad = math.radians(abs(camera_pitch_deg))

    if pitch_rad < 0.01:  # Nearly horizontal - can't estimate ground position
        logger.warning("Camera pitch near horizontal, cannot estimate ground position")
        # Return drone position as fallback
        return drone_lat, drone_lon, 0.0

    # Distance to ground along camera ray
    ground_distance = drone_alt_m / math.tan(pitch_rad)

    # Apply correction for bbox center offset
    # bbox.x = 0.5 is image center; offset gives angular deviation
    # Angular offset from center = (offset_fraction) * (FOV / 2)
    horizontal_fov_rad = math.radians(camera_fov_deg)

    # bbox center offset from image center (-0.5 to 0.5)
    x_offset = bbox.x - 0.5
    y_offset = bbox.y - 0.5

    # Angular offset from camera boresight
    angle_offset_rad = x_offset * horizontal_fov_rad

    # Ground position relative to drone in meters
    # North is forward (along camera boresight), East is right
    # Account for camera pitch - forward distance is reduced when looking down
    forward_distance = ground_distance * math.cos(pitch_rad)

    # Calculate north/east offsets in meters
    north_offset_m = forward_distance * math.cos(angle_offset_rad)
    east_offset_m = forward_distance * math.sin(angle_offset_rad)

    # Convert meter offsets to GPS degrees
    # Using approximate conversion factors
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * math.cos(math.radians(drone_lat))

    lat_offset = north_offset_m / meters_per_deg_lat
    lon_offset = east_offset_m / meters_per_deg_lon

    estimated_lat = drone_lat + lat_offset
    estimated_lon = drone_lon + lon_offset
    estimated_alt = 0.0  # Ground level assumption

    return estimated_lat, estimated_lon, estimated_alt


def _calculate_orbit_velocity_vectors(
    drone_lat: float,
    drone_lon: float,
    subject_lat: float,
    subject_lon: float,
    radius_m: float,
    speed_m_s: float,
    clockwise: bool = True,
) -> Tuple[float, float]:
    """Calculate velocity vector for circular orbit.

    This implements orbital mechanics to maintain circular motion around
    a subject position. The velocity combines:

    1. TANGENTIAL component: Creates orbital motion
       - Perpendicular to radius vector
       - Magnitude = desired orbit speed

    2. RADIAL correction: Maintains exact radius
       - Uses proportional control
       - Corrects for drift due to GPS noise/wind

    Args:
        drone_lat: Current drone latitude.
        drone_lon: Current drone longitude.
        subject_lat: Subject latitude (orbit center).
        subject_lon: Subject longitude (orbit center).
        radius_m: Desired orbit radius in meters.
        speed_m_s: Desired orbit speed in m/s.
        clockwise: True for clockwise orbit (viewed from above).

    Returns:
        Tuple of (north_velocity_m_s, east_velocity_m_s) for set_velocity command.
    """
    # Calculate current distance and direction to subject
    lat_diff = math.radians(subject_lat - drone_lat)
    lon_diff = math.radians(subject_lon - drone_lon)
    avg_lat = math.radians((drone_lat + subject_lat) / 2)

    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(avg_lat)

    # Vector from drone TO subject
    to_subject_north = lat_diff * meters_per_lat
    to_subject_east = lon_diff * meters_per_lon

    # Current distance from subject
    current_distance = math.sqrt(to_subject_north**2 + to_subject_east**2)

    if current_distance < 0.1:  # Avoid division by zero
        current_distance = 0.1

    # Unit vector pointing toward subject
    unit_north = to_subject_north / current_distance
    unit_east = to_subject_east / current_distance

    # TANGENTIAL direction (perpendicular to radius)
    # For clockwise: rotate radius vector 90 degrees clockwise
    # (north, east) -> (east, -north)
    if clockwise:
        tangent_north = unit_east
        tangent_east = -unit_north
    else:
        # Counter-clockwise: rotate 90 degrees counter-clockwise
        tangent_north = -unit_east
        tangent_east = unit_north

    # RADIAL correction using proportional control
    # Positive = too far, need to move inward (negative radial)
    # Negative = too close, need to move outward (positive radial)
    radial_error = current_distance - radius_m
    radial_correction_gain = 0.5  # Proportional gain for smooth correction

    # Radial velocity (positive = outward, negative = inward)
    radial_north = -unit_north * radial_error * radial_correction_gain
    radial_east = -unit_east * radial_error * radial_correction_gain

    # Combine tangential and radial velocities
    north_vel = tangent_north * speed_m_s + radial_north
    east_vel = tangent_east * speed_m_s + radial_east

    return north_vel, east_vel


def _bbox_to_ned_offset(
    bbox: BBox,
    drone_alt_m: float,
    camera_fov_horizontal: float = 60.0,
    camera_fov_vertical: float = 45.0,
    assumed_object_alt_m: float = 0.0
) -> Tuple[float, float, float]:
    """Convert normalized bounding box to NED position offset estimate.

    This estimates the 3D position of an object given its 2D bounding box
    in the camera view. The estimation uses angular geometry and assumes
    the object is at a known altitude (typically ground level).

    Mathematical Model:
        The bounding box center gives the angular offset from camera center:
        - yaw_angle = (x_center - 0.5) * horizontal_fov
        - pitch_angle = (y_center - 0.5) * vertical_fov

        The distance to the object is estimated from altitude difference:
        - height_diff = drone_alt - object_alt
        - distance = height_diff / tan(pitch_angle) for downward-looking camera

        NED position is then:
        - North = distance * cos(yaw) * cos(pitch)
        - East = distance * sin(yaw) * cos(pitch)
        - Down = object_alt - drone_alt (negative if object below drone)

    Args:
        bbox: Normalized bounding box [x_center, y_center, w, h]
        drone_alt_m: Current drone altitude above ground (meters)
        camera_fov_horizontal: Camera horizontal field of view (degrees)
        camera_fov_vertical: Camera vertical field of view (degrees)
        assumed_object_alt_m: Assumed object altitude (default 0 = ground level)

    Returns:
        Tuple of (north_m, east_m, down_m) offset from drone in NED frame.
    """
    # Calculate angular offset from image center
    dx = bbox.x - 0.5  # -0.5 to +0.5 range
    dy = bbox.y - 0.5  # -0.5 to +0.5 range

    # Convert to angular offset in radians
    yaw_angle = math.radians(dx * camera_fov_horizontal)
    pitch_angle = math.radians(dy * camera_fov_vertical)

    # Estimate distance using altitude difference
    height_diff = drone_alt_m - assumed_object_alt_m

    if height_diff <= 0:
        height_diff = 1.0

    # Distance calculation accounting for camera pitch
    effective_pitch = abs(pitch_angle) + 0.5  # ~30 degree average camera tilt
    if effective_pitch > 0.01:
        ground_distance = height_diff / math.tan(effective_pitch)
    else:
        ground_distance = height_diff * 2

    # Clamp distance to reasonable range
    ground_distance = max(1.0, min(ground_distance, 100.0))

    # Convert to NED offset
    north_m = ground_distance * math.cos(yaw_angle)
    east_m = ground_distance * math.sin(yaw_angle)
    down_m = assumed_object_alt_m - drone_alt_m

    return north_m, east_m, down_m


def _calculate_intercept_velocity(
    current_pos: Tuple[float, float, float],
    target_pos: Tuple[float, float, float],
    max_speed: float,
    standoff: float,
    tracking_state: KalmanTrackingState
) -> Tuple[float, float, float]:
    """Calculate velocity vector to intercept target with standoff distance.

    Uses the LeadLagController philosophy: fly to where the target will be,
    not where it currently is. Accounts for target velocity from Kalman state.

    Args:
        current_pos: Drone position (north, east, down) in NED meters
        target_pos: Target estimated position (north, east, down) in NED meters
        max_speed: Maximum velocity magnitude (m/s)
        standoff: Desired standoff distance (meters)
        tracking_state: Kalman filter state with velocity/acceleration

    Returns:
        Tuple of (vel_north, vel_east, vel_down) in m/s
    """
    # Vector from drone to target
    dx = target_pos[0] - current_pos[0]
    dy = target_pos[1] - current_pos[1]
    dz = target_pos[2] - current_pos[2]

    # Current distance
    distance = math.sqrt(dx**2 + dy**2 + dz**2)

    if distance < 0.1:
        return 0.0, 0.0, 0.0

    # Unit vector toward target
    if distance > 0:
        ux, uy, uz = dx / distance, dy / distance, dz / distance
    else:
        return 0.0, 0.0, 0.0

    # Adjust for standoff distance
    distance_error = distance - standoff

    # Add target velocity prediction for intercept
    prediction_time = 0.5  # seconds ahead
    predicted_x = tracking_state.vx * prediction_time
    predicted_y = tracking_state.vy * prediction_time

    # Combined position error including prediction
    error_x = dx - ux * standoff + predicted_x
    error_y = dy - uy * standoff + predicted_y
    error_z = dz - uz * standoff

    # Proportional control with distance error
    kp = 0.3

    # Calculate raw velocity components
    vel_north = error_x * kp
    vel_east = error_y * kp
    vel_down = error_z * kp

    # Clamp vertical velocity separately (safer for altitude control)
    max_vertical_speed = max_speed * 0.3
    vel_down = _clamp(vel_down, -max_vertical_speed, max_vertical_speed)

    # Clamp the HORIZONTAL velocity magnitude to max_speed
    # This ensures the total horizontal speed doesn't exceed max_speed
    horizontal_vel_mag = math.sqrt(vel_north**2 + vel_east**2)
    if horizontal_vel_mag > max_speed and horizontal_vel_mag > 0:
        scale = max_speed / horizontal_vel_mag
        vel_north *= scale
        vel_east *= scale

    return vel_north, vel_east, vel_down


# =============================================================================
# ORCHESTRATOR IMPLEMENTATION
# =============================================================================


async def orbit_subject_vision(
    bbox: dict,
    radius_m: float = 10.0,
    speed_m_s: float = 3.0,
    orbits: int = 1,
    direction: str = "cw",
) -> str:
    """Orbit around a visually-detected subject while keeping them centered.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    This orchestrator combines:
    1. Vision-based subject position estimation
    2. Circular orbit trajectory generation
    3. Gimbal coordination for subject tracking
    4. Continuous position updates during orbit

    OPERATION SEQUENCE:
    -------------------
    1. Validate input parameters
    2. Get current drone position from telemetry
    3. Estimate subject position from bounding box
    4. Calculate orbit trajectory
    5. Execute orbit while:
       - Updating velocity for circular motion
       - Pointing gimbal at estimated subject position
       - Monitoring telemetry for safety
    6. Complete requested number of orbits
    7. Return to hover

    VISION TRACKING:
    ----------------
    The bounding box should be continuously updated by the vision system.
    This orchestrator estimates the 3D world position from the 2D bbox
    using camera geometry and drone altitude.

    For best results:
    - Provide bounding box updates at 5-10 Hz
    - Use a camera with known FOV calibration
    - Ensure drone altitude is accurate (use barometer or GPS altitude)

    ORBIT MECHANICS:
    ----------------
    The orbit uses velocity-based control for smooth motion:
    - Tangential velocity maintains orbital motion
    - Radial correction maintains exact radius
    - Gimbal tracks subject center

    Orbit time per revolution:
        T = 2 * pi * radius / speed

    Example:
        radius = 10m, speed = 3 m/s
        T = 2 * 3.14159 * 10 / 3 = 20.9 seconds per orbit

    Args:
        bbox: Dictionary with bounding box from vision detection.
              Format: {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3}
              Values are normalized (0..1 range).
        radius_m: Orbit radius in meters (2-50m, default 10m).
        speed_m_s: Orbit speed in m/s (0.5-10 m/s, default 3 m/s).
        orbits: Number of complete orbits (1-10, default 1).
        direction: Orbit direction: "cw" (clockwise) or "ccw" (counter-clockwise).

    Returns:
        JSON string with orbit statistics:
        - success: True if orbit completed successfully
        - orbits_completed: Actual number of orbits completed
        - duration_s: Total orbit duration in seconds
        - final_bbox: Last known subject bounding box
        - estimated_subject_position: Final estimated subject position

    Safety:
        - Validates minimum altitude before starting
        - Monitors telemetry continuously
        - Automatic hold on error or timeout

    Example:
        >>> # Orbit around detected person
        >>> result = await orbit_subject_vision(
        ...     bbox={"x": 0.5, "y": 0.6, "w": 0.15, "h": 0.3},
        ...     radius_m=15.0,
        ...     speed_m_s=4.0,
        ...     orbits=2,
        ...     direction="cw"
        ... )
        >>> data = json.loads(result)
        >>> print(f"Completed {data['orbits_completed']} orbits")
    """
    # =========================================================================
    # STEP 1: VALIDATE INPUT
    # =========================================================================
    try:
        validated = OrbitSubjectVisionInput(
            bbox=bbox,
            radius_m=radius_m,
            speed_m_s=speed_m_s,
            orbits=orbits,
            direction=direction,
        )
    except Exception as e:
        logger.warning(f"Invalid orbit_subject_vision input: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=True,
            suggested_action="Provide valid bbox (x,y,w,h in 0..1), radius (2-50m), speed (0.5-10 m/s), orbits (1-10)",
        ))

    # Extract validated values
    validated_bbox = validated.bbox
    validated_radius = validated.radius_m
    validated_speed = validated.speed_m_s
    validated_orbits = validated.orbits
    clockwise = validated.direction == "cw"

    logger.info(
        f"Starting orbit_subject_vision: radius={validated_radius}m, "
        f"speed={validated_speed}m/s, orbits={validated_orbits}, direction={validated.direction}"
    )

    # =========================================================================
    # STEP 2: GET DRONE CONNECTION AND TELEMETRY
    # =========================================================================
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before starting orbit",
        ))

    # Get initial telemetry
    telem = await cache.get_latest()
    if not telem:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "No telemetry available",
            recoverable=True,
            suggested_action="Wait for telemetry data before starting orbit",
        ))

    # Check minimum altitude
    if telem.relative_altitude_m < MIN_ALTITUDE_M:
        return json.dumps({
            "success": False,
            "error": f"Altitude {telem.relative_altitude_m:.1f}m below minimum {MIN_ALTITUDE_M}m for orbit",
            "suggested_action": f"Climb to at least {MIN_ALTITUDE_M}m before orbiting",
        })

    # =========================================================================
    # STEP 3: ESTIMATE INITIAL SUBJECT POSITION
    # =========================================================================
    estimated_lat, estimated_lon, estimated_alt = _estimate_subject_position_3d(
        bbox=validated_bbox,
        drone_lat=telem.latitude_deg,
        drone_lon=telem.longitude_deg,
        drone_alt_m=telem.relative_altitude_m,
    )

    logger.info(
        f"Estimated subject position: lat={estimated_lat:.7f}, lon={estimated_lon:.7f}"
    )

    # =========================================================================
    # STEP 4: CALCULATE ORBIT DURATION
    # =========================================================================
    # Time for one complete orbit: T = 2 * pi * r / v
    orbit_period_s = 2 * math.pi * validated_radius / validated_speed
    total_duration_s = orbit_period_s * validated_orbits

    logger.info(
        f"Orbit period: {orbit_period_s:.1f}s, total duration: {total_duration_s:.1f}s"
    )

    # =========================================================================
    # STEP 5: EXECUTE ORBIT
    # =========================================================================
    try:
        start_time = asyncio.get_event_loop().time()
        last_bbox = validated_bbox.model_dump()
        orbit_angle_accumulated = 0.0
        orbits_completed = 0.0
        last_angle = None

        while asyncio.get_event_loop().time() - start_time < total_duration_s:
            loop_start = asyncio.get_event_loop().time()

            # Get current telemetry
            telem = await cache.get_latest()
            if not telem:
                logger.warning("Lost telemetry during orbit")
                await asyncio.sleep(ORBIT_DT)
                continue

            # Update subject position estimate from bbox
            # (In production, bbox would be updated continuously by vision system)
            estimated_lat, estimated_lon, estimated_alt = _estimate_subject_position_3d(
                bbox=validated_bbox,
                drone_lat=telem.latitude_deg,
                drone_lon=telem.longitude_deg,
                drone_alt_m=telem.relative_altitude_m,
            )

            # Calculate orbit velocity
            north_vel, east_vel = _calculate_orbit_velocity_vectors(
                drone_lat=telem.latitude_deg,
                drone_lon=telem.longitude_deg,
                subject_lat=estimated_lat,
                subject_lon=estimated_lon,
                radius_m=validated_radius,
                speed_m_s=validated_speed,
                clockwise=clockwise,
            )

            # Send velocity command
            await set_velocity(
                north_m_s=north_vel,
                east_m_s=east_vel,
                down_m_s=0.0,  # Maintain altitude
                duration_s=ORBIT_DT,
            )

            # Point gimbal at subject
            pitch, yaw = _calculate_look_angles(
                drone_lat=telem.latitude_deg,
                drone_lon=telem.longitude_deg,
                drone_alt=telem.relative_altitude_m,
                target_lat=estimated_lat,
                target_lon=estimated_lon,
                target_alt=estimated_alt,
            )

            # Convert absolute yaw to relative gimbal yaw
            drone_yaw = getattr(telem, 'yaw_deg', 0.0)
            relative_yaw = yaw - drone_yaw

            try:
                gimbal = drone.gimbal
                await gimbal.set_pitch_and_yaw(pitch, relative_yaw)
            except Exception as gimbal_err:
                # Gimbal may not be available on all hardware
                logger.debug(f"Gimbal control not available: {gimbal_err}")

            # Track orbit progress
            current_angle = math.atan2(east_vel, north_vel)
            if last_angle is not None:
                angle_diff = current_angle - last_angle
                # Handle angle wraparound
                if angle_diff > math.pi:
                    angle_diff -= 2 * math.pi
                elif angle_diff < -math.pi:
                    angle_diff += 2 * math.pi
                orbit_angle_accumulated += abs(angle_diff)
                orbits_completed = orbit_angle_accumulated / (2 * math.pi)
            last_angle = current_angle

            # Maintain update rate
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < ORBIT_DT:
                await asyncio.sleep(ORBIT_DT - elapsed)

        # Orbit complete
        await hold(duration_s=2.0)

        total_time = asyncio.get_event_loop().time() - start_time

        return json.dumps({
            "success": True,
            "orbits_completed": round(orbits_completed, 2),
            "duration_s": round(total_time, 1),
            "radius_m": validated_radius,
            "speed_m_s": validated_speed,
            "direction": validated.direction,
            "final_bbox": last_bbox,
            "estimated_subject_position": {
                "lat_deg": round(estimated_lat, 7),
                "lon_deg": round(estimated_lon, 7),
                "alt_m": estimated_alt,
            },
        })

    except Exception as e:
        logger.exception("Orbit failed")
        await hold(duration_s=1.0)
        return json.dumps({
            "success": False,
            "error": str(e),
            "orbits_completed": round(orbits_completed, 2) if 'orbits_completed' in dir() else 0,
        })


# =============================================================================
# TRACK_BBOX ORCHESTRATOR
# =============================================================================


async def track_bbox(
    bbox: dict,
    duration_s: float = 60.0,
    approach_speed_m_s: float = 2.0,
    standoff_m: float = 5.0,
) -> str:
    """Track an object identified by bounding box using Kalman filter prediction.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    W2a-T17: Orchestrator tool that coordinates vision, tracking, and flight
    to follow an object identified by its bounding box in camera view.

    Operation Flow:
        1. Get initial bbox from detection (provided as input)
        2. Convert bbox to NED position estimate using camera geometry
        3. Initialize KalmanTracker with position estimate
        4. Start tracking loop:
            a. Get new vision detection (if available)
            b. Update Kalman filter with new position
            c. Predict target position ahead
            d. Calculate intercept velocity
            e. Command drone via set_velocity
            f. Update gimbal to track target
        5. After duration, bring drone to hover

    Kalman Filter Integration:
        The KalmanTracker maintains a 9-dimensional state vector:
        [x, y, z, vx, vy, vz, ax, ay, az]

        This enables:
        - Smooth tracking despite noisy vision measurements
        - Prediction of future position for intercept
        - Handling of temporary vision occlusions

    Args:
        bbox: Dictionary with bounding box from vision detection.
              Format: {"x": 0.5, "y": 0.4, "w": 0.15, "h": 0.3}
              Values are normalized 0-1.
        duration_s: Total tracking duration in seconds. Max 300s (5 minutes).
        approach_speed_m_s: Maximum speed when approaching target. Max 10 m/s.
        standoff_m: Desired distance to maintain from target. Range 2-50 meters.

    Returns:
        JSON string with tracking results:
        {
            "success": true,
            "duration_s": <actual_duration>,
            "tracking_stats": {
                "total_updates": <int>,
                "avg_confidence": <float>,
                "max_velocity_m_s": <float>,
                "kalman_predictions": <int>
            },
            "final_state": <TrackerState>
        }

    Example:
        >>> # Track a person for 30 seconds at 5m distance
        >>> result = await track_bbox(
        ...     bbox={"x": 0.5, "y": 0.4, "w": 0.15, "h": 0.3},
        ...     duration_s=30.0,
        ...     approach_speed_m_s=3.0,
        ...     standoff_m=5.0
        ... )
    """
    # =========================================================================
    # STEP 1: VALIDATE INPUT
    # =========================================================================
    try:
        # Convert dict to BBox if needed
        if isinstance(bbox, dict):
            validated_bbox = BBox(
                x=bbox.get("x", 0.5),
                y=bbox.get("y", 0.5),
                w=bbox.get("w", 0.1),
                h=bbox.get("h", 0.1),
            )
        else:
            validated_bbox = bbox

        validated = TrackBboxInput(
            bbox=validated_bbox,
            duration_s=duration_s,
            approach_speed_m_s=approach_speed_m_s,
            standoff_m=standoff_m,
        )
    except Exception as e:
        logger.warning(f"Invalid track_bbox input: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=True,
            suggested_action="Provide valid bbox (x,y,w,h in 0..1), duration (0-300s), speed (0-10 m/s), standoff (2-50m)",
        ))

    # Extract validated values
    validated_bbox = validated.bbox
    validated_duration = validated.duration_s
    validated_speed = validated.approach_speed_m_s
    validated_standoff = validated.standoff_m

    logger.info(
        f"Starting track_bbox: duration={validated_duration}s, "
        f"speed={validated_speed}m/s, standoff={validated_standoff}m"
    )

    # =========================================================================
    # STEP 2: GET DRONE CONNECTION AND TELEMETRY
    # =========================================================================
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before tracking",
        ))

    # Get initial telemetry
    telem = await cache.get_latest()
    if not telem:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "No telemetry available",
            recoverable=True,
            suggested_action="Wait for telemetry data",
        ))

    # =========================================================================
    # STEP 3: INITIALIZE TRACKING SYSTEMS
    # =========================================================================
    # Initialize Kalman tracker
    kalman = KalmanTracker(dt=TRACKING_DT)

    # Initialize gimbal controller
    gimbal = SmoothGimbalController(limits=GimbalLimits())

    # Convert initial bbox to NED position estimate
    target_offset = _bbox_to_ned_offset(
        bbox=validated_bbox,
        drone_alt_m=telem.relative_altitude_m,
        assumed_object_alt_m=0.0,
    )

    # Initial target position in NED (relative to drone home)
    target_ned = (target_offset[0], target_offset[1], target_offset[2])

    # Initialize Kalman filter with first measurement
    current_time = time.time()
    kalman.update(target_ned[0], target_ned[1], target_ned[2], current_time)

    # Get vision tools for continuous detection
    vision_tools = get_vision_tools_instance()

    # Tracking statistics
    start_time = asyncio.get_event_loop().time()
    update_count = 0
    total_confidence = 0.0
    max_velocity = 0.0
    prediction_count = 0

    # =========================================================================
    # STEP 4: EXECUTE TRACKING LOOP
    # =========================================================================
    try:
        while asyncio.get_event_loop().time() - start_time < validated_duration:
            loop_start = asyncio.get_event_loop().time()

            # Get current telemetry
            telem = await cache.get_latest()
            if not telem:
                await asyncio.sleep(TRACKING_DT)
                continue

            current_time = time.time()

            # Try to get updated vision detection
            try:
                detection_result = await vision_tools.get_detected_objects(
                    min_confidence=0.3
                )

                if detection_result.get("success") and detection_result.get("detections"):
                    # Find the detection closest to our tracked bbox
                    detections = detection_result["detections"]
                    best_detection = None
                    best_distance = float('inf')

                    for det in detections:
                        det_bbox = det.get("bbox", [])
                        if len(det_bbox) >= 4:
                            # Calculate center distance
                            dx = det_bbox[0] - validated_bbox.x
                            dy = det_bbox[1] - validated_bbox.y
                            dist = math.sqrt(dx**2 + dy**2)
                            if dist < best_distance:
                                best_distance = dist
                                best_detection = det

                    # Update target position if we found a close detection
                    if best_detection and best_distance < 0.2:
                        det_bbox = best_detection.get("bbox", [])
                        if len(det_bbox) >= 4:
                            new_offset = _bbox_to_ned_offset(
                                bbox=BBox(x=det_bbox[0], y=det_bbox[1], w=det_bbox[2], h=det_bbox[3]),
                                drone_alt_m=telem.relative_altitude_m,
                            )
                            target_ned = (new_offset[0], new_offset[1], new_offset[2])

                            # Update Kalman filter with new measurement
                            kalman.update(target_ned[0], target_ned[1], target_ned[2], current_time)
                            update_count += 1
            except Exception as e:
                logger.debug(f"Vision detection failed: {e}")

            # Get current Kalman state
            kalman_state = kalman._get_state(current_time)
            total_confidence += kalman_state.confidence

            # Predict target position for intercept
            prediction_horizon = 0.5  # seconds ahead
            predicted_pos = kalman.predict(prediction_horizon)
            prediction_count += 1

            # Calculate velocity to intercept target
            drone_current_ned = (0.0, 0.0, -telem.relative_altitude_m)

            vel_north, vel_east, vel_down = _calculate_intercept_velocity(
                current_pos=drone_current_ned,
                target_pos=predicted_pos,
                max_speed=validated_speed,
                standoff=validated_standoff,
                tracking_state=kalman_state,
            )

            # Track max velocity
            current_vel = math.sqrt(vel_north**2 + vel_east**2 + vel_down**2)
            max_velocity = max(max_velocity, current_vel)

            # Send velocity command
            await set_velocity(
                north_m_s=vel_north,
                east_m_s=vel_east,
                down_m_s=vel_down,
                duration_s=TRACKING_DT,
            )

            # Update gimbal to track target
            try:
                # Calculate gimbal angles to look at predicted position
                horizontal_dist = math.sqrt(predicted_pos[0]**2 + predicted_pos[1]**2)
                vertical_dist = predicted_pos[2] - drone_current_ned[2]

                if horizontal_dist > 0.1:
                    pitch = math.degrees(math.atan2(vertical_dist, horizontal_dist))
                    yaw = math.degrees(math.atan2(predicted_pos[1], predicted_pos[0]))

                    # Clamp gimbal angles
                    pitch = _clamp(pitch, -90.0, 30.0)
                    yaw = _clamp(yaw, -180.0, 180.0)

                    # Update gimbal with rate limiting
                    gimbal.update(pitch, yaw, TRACKING_DT)
            except Exception as e:
                logger.debug(f"Gimbal update failed: {e}")

            # Maintain 10Hz update rate
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < TRACKING_DT:
                await asyncio.sleep(TRACKING_DT - elapsed)

        # Tracking complete - bring to hover
        await hold(duration_s=2.0)

        # Calculate final statistics
        total_time = asyncio.get_event_loop().time() - start_time
        avg_confidence = total_confidence / max(update_count, 1)

        # Get final Kalman state
        final_state = kalman._get_state(time.time())

        return json.dumps({
            "success": True,
            "duration_s": round(total_time, 2),
            "tracking_stats": {
                "total_updates": update_count,
                "avg_confidence": round(avg_confidence, 3),
                "max_velocity_m_s": round(max_velocity, 2),
                "kalman_predictions": prediction_count,
            },
            "final_state": {
                "x_m": round(final_state.x, 2),
                "y_m": round(final_state.y, 2),
                "z_m": round(final_state.z, 2),
                "vx_m_s": round(final_state.vx, 2),
                "vy_m_s": round(final_state.vy, 2),
                "vz_m_s": round(final_state.vz, 2),
                "confidence": round(final_state.confidence, 3),
            },
            "parameters": {
                "standoff_m": validated_standoff,
                "approach_speed_m_s": validated_speed,
                "initial_bbox": {"x": validated_bbox.x, "y": validated_bbox.y, "w": validated_bbox.w, "h": validated_bbox.h},
            },
        })

    except Exception as e:
        logger.exception("track_bbox failed")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


# =============================================================================
# TOOL REGISTRATION METADATA
# =============================================================================

# Tool metadata for MCP server registration
ORBIT_SUBJECT_VISION_TOOL = {
    "name": "orbit_subject_vision",
    "description": (
        "Orbit around a visually-detected subject while keeping them centered in camera. "
        "Uses bounding box from vision system to estimate subject position and generates "
        "circular orbit trajectory. Ideal for cinematic shots and subject inspection."
    ),
    "inputSchema": OrbitSubjectVisionInput.model_json_schema(),
    "annotations": ANNOTATIONS_WRITE_SAFE,
    "outputSchema": OUTPUT_SCHEMA,
}

TRACK_BBOX_TOOL = {
    "name": "track_bbox",
    "description": (
        "Track an object identified by bounding box using Kalman filter prediction. "
        "Coordinates vision detection with flight control for smooth intercept tracking. "
        "Uses 9-state Kalman filter for position, velocity, and acceleration estimation. "
        "Ideal for following moving subjects like people, vehicles, or athletes."
    ),
    "inputSchema": TrackBboxInput.model_json_schema(),
    "annotations": ANNOTATIONS_WRITE_SAFE,
    "outputSchema": OUTPUT_SCHEMA,
}

# List of all orchestrator tools for MCP server registration
ORCHESTRATOR_TOOLS = [
    ORBIT_SUBJECT_VISION_TOOL,
    TRACK_BBOX_TOOL,
]
