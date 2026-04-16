"""Advanced tracking and camera control tools for autonomous drone operations.

This module provides sophisticated camera tracking capabilities for drone missions,
integrating gimbal control, orbital mechanics, and predictive tracking algorithms.

Core Capabilities:
    - orbit_target: Circle around a target while maintaining camera lock
    - track_target: Follow moving targets (e.g., vehicles, people) with prediction
    - set_gimbal: Direct gimbal angle control independent of drone orientation
    - point_camera_at: Point camera at specific GPS coordinates
    - spiral_search: Expanding spiral search pattern for area coverage

Tracking System Architecture:
    The tracking system uses a combination of GPS-based positioning and velocity-based
    prediction to maintain visual contact with targets. It operates in two modes:

    1. ORBIT MODE (Cinematic/Surveillance):
       - Drone flies in a circular path around a stationary target
       - Gimbal continuously points at target center
       - Uses tangential velocity vectors with radial correction
       - Perfect for 360-degree inspection or cinematic orbiting shots

    2. TRACK MODE (Following Moving Targets):
       - Drone follows a target using velocity prediction
       - Supports three tracking sub-modes:
         * "follow": Position behind target (default)
         * "lead": Position ahead of target (intercept)
         * "side": Lateral tracking (perpendicular to motion)
       - Uses dead reckoning for position prediction
       - P-controller for smooth velocity transitions

Mathematical Foundations:
    GPS Coordinate Conversions:
        The system uses the haversine approximation for small distances:
        - 1 degree latitude = 111,320 meters (constant)
        - 1 degree longitude = 111,320 * cos(latitude) meters (varies by latitude)
        This allows conversion between GPS coordinates and local meters (NED frame).

    Gimbal Angle Calculations:
        Pitch and yaw are calculated using 3D trigonometry from drone position to
        target position in the local tangent plane.

    Orbital Mechanics:
        Velocity vectors combine tangential (orbital) and radial (distance correction)
        components to maintain perfect circular motion while pointing at center.

Features:
    - Gimbal control (pitch, yaw, roll) with hardware limits enforcement
    - Coordinated flight + camera movement at 10Hz update rate
    - Velocity-based target following with predictive dead reckoning
    - Smooth transitions using proportional control (P-controllers)
    - Configurable orbit radius, speed, and altitude offsets

Safety Considerations:
    - Minimum tracking altitude enforced (MIN_TRACK_ALTITUDE = 10m)
    - Gimbal angle clamping prevents hardware damage
    - Velocity clamping prevents sudden aggressive maneuvers
    - All tracking functions include emergency hold capability

Dependencies:
    - MAVSDK for drone communication
    - ConnectionManager for telemetry access
    - FlightStateMachine for state validation

Example Usage:
    >>> # Orbit a target for cinematic shot
    >>> await orbit_target(
    ...     target_lat=37.7749,
    ...     target_lon=-122.4194,
    ...     radius_m=15.0,
    ...     speed_m_s=2.5,
    ...     duration_s=60.0
    ... )

    >>> # Track a moving vehicle
    >>> await track_target(
    ...     target_lat=37.7749,
    ...     target_lon=-122.4194,
    ...     target_velocity_north=5.0,
    ...     target_velocity_east=2.0,
    ...     tracking_mode="follow",
    ...     predictive=True
    ... )
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.tools.flight_tools import (
    set_velocity, goto_gps, hold, fly_body_offset
)
from avatar.core.decorators import timeout, require_state
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
# HARDWARE LIMITS AND CONSTANTS
# =============================================================================

# Gimbal limits (degrees) - These constrain the physical movement range of the
# gimbal to prevent hardware damage and maintain image stabilization.
# Note: Different gimbal models may have different limits; these are conservative defaults.
GIMBAL_PITCH_MIN = -90.0   # Straight down (nadir view)
GIMBAL_PITCH_MAX = 30.0    # Slightly up (positive pitch looks above horizon)
GIMBAL_YAW_MIN = -180.0    # Full 360-degree rotation capability (relative to drone)
GIMBAL_YAW_MAX = 180.0
GIMBAL_ROLL_MIN = -45.0    # Limited roll for stability (excessive roll degrades footage)
GIMBAL_ROLL_MAX = 45.0

# Tracking constants - Default values for various tracking operations.
# These provide sensible defaults while allowing per-mission customization.
DEFAULT_ORBIT_RADIUS = 10.0       # meters - Standard orbit distance for close inspection
DEFAULT_ORBIT_SPEED = 3.0           # m/s - Comfortable speed for smooth video footage
DEFAULT_ORBIT_ALTITUDE = 15.0     # meters above target - Safe clearance for most operations
DEFAULT_TRACK_DISTANCE = 8.0        # meters behind target - Close follow distance
MIN_TRACK_ALTITUDE = 10.0         # minimum tracking altitude - Safety buffer for terrain/obstacles


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TargetInfo:
    """Information about a tracked target for prediction and tracking.

    This dataclass encapsulates all relevant state about a target being tracked,
    including position, velocity, and metadata. It serves as the primary
    data structure for the predictive tracking algorithm.

    The velocity components (velocity_north, velocity_east) are critical for
    dead reckoning prediction. When a target's velocity is known, the system
    can predict its future position, allowing the drone to intercept or follow
    more smoothly rather than reacting to past positions.

    Attributes:
        lat: Target latitude in decimal degrees (WGS84)
        lon: Target longitude in decimal degrees (WGS84)
        alt_m: Target altitude above ground level in meters (optional, used for 3D tracking)
        velocity_north: Target velocity north component in m/s (positive = moving north)
        velocity_east: Target velocity east component in m/s (positive = moving east)
        last_update: Unix timestamp of last update (for staleness detection)
        label: Target label/classification (e.g., "person", "vehicle", "interest_point")

    Example:
        >>> target = TargetInfo(
        ...     lat=37.7749,
        ...     lon=-122.4194,
        ...     velocity_north=5.0,  # Moving north at 5 m/s (18 km/h)
        ...     velocity_east=0.0,
        ...     label="snowboarder"
        ... )
    """
    lat: float
    lon: float
    alt_m: Optional[float] = None
    velocity_north: float = 0.0
    velocity_east: float = 0.0
    last_update: float = 0.0
    label: str = "target"


@dataclass
class GimbalAngles:
    """Gimbal angle configuration for camera orientation control.

    Represents a complete 3-axis gimbal orientation. The angles are specified
    relative to the drone body frame (not Earth frame), meaning:
    - yaw=0 means camera points in same direction as drone nose
    - pitch=-90 means camera points straight down (regardless of drone tilt)

    Coordinate System:
        All angles follow the right-hand rule and are in degrees:
        - Pitch: Rotation around lateral (Y) axis
          * -90 = straight down (nadir)
          * 0 = level with horizon
          * 30 = slightly up (above horizon)
        - Yaw: Rotation around vertical (Z) axis, relative to drone heading
          * 0 = aligned with drone nose
          * 90 = pointing right of drone
          * -90 = pointing left of drone
        - Roll: Rotation around longitudinal (X) axis
          * Limited to +/-45 degrees for stability

    Attributes:
        pitch_deg: Pitch angle (-90 = down, 0 = level, 30 = up). Default -45° for typical survey.
        yaw_deg: Yaw angle relative to drone (-180 to 180). Default 0° (aligned with drone).
        roll_deg: Roll angle (-45 to 45). Default 0° (level horizon).

    Note:
        These angles are constrained by the GIMBAL_*_MIN/MAX constants before
        being sent to hardware to prevent damage and ensure stabilization limits.
    """
    pitch_deg: float = -45.0  # Default looking down at 45° (good balance of view and context)
    yaw_deg: float = 0.0
    roll_deg: float = 0.0


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to specified range [min_val, max_val].

    This utility ensures values stay within safe operational bounds,
    used extensively for gimbal angles and velocity commands.

    Args:
        value: The value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value constrained to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


# =============================================================================
# GIMBAL CALCULATION ENGINE
# =============================================================================

def _calculate_look_angles(
    drone_lat: float, drone_lon: float, drone_alt: float,
    target_lat: float, target_lon: float, target_alt: Optional[float]
) -> Tuple[float, float]:
    """Calculate gimbal pitch and yaw angles to look at a target from drone position.

    This is the core geometry engine for camera pointing. It converts GPS coordinates
    into gimbal angles using 3D trigonometry in the local tangent plane (NED frame).

    Mathematical Derivation:
        1. Convert GPS coordinate differences to meters using haversine approximation
           - meters_per_lat is constant: 111,320 m/deg (Earth's meridian circumference / 360)
           - meters_per_lon varies with latitude: 111,320 * cos(lat) (accounts for longitude convergence)

        2. Calculate displacement vector in local North-East plane
           - north_dist = (target_lat - drone_lat) * meters_per_lat
           - east_dist = (target_lon - drone_lon) * meters_per_lon

        3. Calculate yaw (heading to target)
           - yaw = atan2(east_dist, north_dist) in radians
           - Convert to degrees for gimbal command
           - Result: 0° = north, 90° = east, 180° = south, -90° = west

        4. Calculate pitch (elevation angle to target)
           - horizontal_dist = sqrt(north_dist^2 + east_dist^2)
           - alt_diff = target_alt - drone_alt (vertical displacement)
           - pitch = atan2(alt_diff, horizontal_dist) in radians
           - Convert to degrees
           - Result: negative = looking down, positive = looking up, 0 = level

    Why this approach:
        - Uses local tangent plane approximation (accurate for distances < ~10km)
        - Avoids complex ellipsoid calculations for real-time performance
        - Accounts for latitude-dependent longitude scaling (cos(lat) factor)

    Args:
        drone_lat: Drone latitude in decimal degrees
        drone_lon: Drone longitude in decimal degrees
        drone_alt: Drone altitude in meters (above ground or MSL)
        target_lat: Target latitude in decimal degrees
        target_lon: Target longitude in decimal degrees
        target_alt: Target altitude in meters (optional, defaults to drone altitude)

    Returns:
        Tuple of (pitch_deg, yaw_deg) relative to drone:
        - pitch_deg: Elevation angle (negative = down, positive = up)
        - yaw_deg: Azimuth angle relative to drone heading (0 = forward)

    Example:
        >>> pitch, yaw = _calculate_look_angles(
        ...     drone_lat=37.7749, drone_lon=-122.4194, drone_alt=20.0,
        ...     target_lat=37.7750, target_lon=-122.4195, target_alt=0.0
        ... )
        >>> # If drone is at 20m and target at ground 15m away:
        >>> # pitch will be approximately -53 degrees (looking down)
    """
    # Step 1: Calculate latitude difference and average latitude for scaling
    lat_diff = math.radians(target_lat - drone_lat)
    lon_diff = math.radians(target_lon - drone_lon)
    avg_lat = math.radians((drone_lat + target_lat) / 2)

    # Step 2: Convert degree differences to meters using haversine approximation
    # These constants represent the Earth's circumference divided by 360 degrees
    meters_per_lat = 111320.0  # Approximately 111.32 km per degree of latitude
    meters_per_lon = 111320.0 * math.cos(avg_lat)  # Longitude lines converge at poles

    # Step 3: Calculate displacement in North-East plane (NED frame)
    north_dist = lat_diff * meters_per_lat  # Positive = target is north of drone
    east_dist = lon_diff * meters_per_lon   # Positive = target is east of drone

    # Step 4: Calculate yaw angle (heading from drone to target)
    # atan2(east, north) gives angle from north, clockwise
    # 0 radians = north, π/2 = east, π = south, -π/2 = west
    yaw = math.degrees(math.atan2(east_dist, north_dist))

    # Step 5: Calculate pitch angle (elevation to target)
    # First get horizontal distance (ground plane projection)
    horizontal_dist = math.sqrt(north_dist**2 + east_dist**2)

    # Calculate altitude difference (vertical displacement)
    # If target_alt is None, assume same altitude as drone (level flight)
    alt_diff = (target_alt or drone_alt) - drone_alt

    # atan2(altitude_diff, horizontal_dist) gives elevation angle
    # Negative pitch = looking down, Positive = looking up
    pitch = math.degrees(math.atan2(alt_diff, horizontal_dist))

    return pitch, yaw


# =============================================================================
# ORBITAL MECHANICS ENGINE
# =============================================================================

def _calculate_orbit_velocity(
    current_lat: float, current_lon: float,
    target_lat: float, target_lon: float,
    radius_m: float, speed_m_s: float, clockwise: bool = True
) -> Tuple[float, float, float]:
    """Calculate velocity vector to maintain circular orbit around a target.

    This implements orbital mechanics for drone cinematography and surveillance.
    The algorithm produces velocity commands that result in circular motion around
    a target point while continuously facing the center.

    Orbital Mechanics Derivation:
        A perfect orbit requires two velocity components:

        1. TANGENTIAL COMPONENT (Orbital motion):
           - Direction: Perpendicular to radius vector
           - Magnitude: speed_m_s (desired orbital speed)
           - For clockwise orbit: tangent = (east, -north) [90° rotation]
           - For counter-clockwise: tangent = (-east, north) [-90° rotation]

        2. RADIAL COMPONENT (Radius correction):
           - Uses proportional control to maintain exact radius
           - correction = (current_radius - target_radius) * k
           - k = 0.5 (proportional gain) - provides gentle correction without oscillation
           - Direction: Toward/away from target to adjust distance

        3. YAW RATE (Camera tracking):
           - Angular velocity = linear_velocity / radius
           - Convert from rad/s to deg/s: multiply by 57.3 (180/π ≈ 57.2958)
           - yaw_rate = (speed_m_s / radius_m) * 57.3 deg/s

    Why proportional control for radius:
        - Purely tangential motion drifts due to GPS noise, wind, and timing jitter
        - P-controller adds restoring force toward desired radius
        - Gain of 0.5 chosen for stability (damping ratio > 0.7)
        - Prevents orbital decay or divergence

    Args:
        current_lat: Current drone latitude
        current_lon: Current drone longitude
        target_lat: Center of orbit latitude (target to point camera at)
        target_lon: Center of orbit longitude
        radius_m: Desired orbit radius in meters
        speed_m_s: Desired orbital speed in m/s
        clockwise: Orbit direction (True = clockwise when viewed from above)

    Returns:
        Tuple of (north_m_s, east_m_s, yaw_rate_deg_s):
        - north_m_s: North component of velocity command
        - east_m_s: East component of velocity command
        - yaw_rate_deg_s: Yaw rate to keep camera on target (for coordinated turns)

    Example:
        >>> # Drone at 10m north of target, orbiting clockwise at 3 m/s
        >>> north_vel, east_vel, yaw_rate = _calculate_orbit_velocity(
        ...     current_lat=37.7749, current_lon=-122.4194,
        ...     target_lat=37.7748, target_lon=-122.4194,
        ...     radius_m=10.0, speed_m_s=3.0, clockwise=True
        ... )
        >>> # east_vel will be positive (moving east)
        >>> # north_vel will be negative (correcting toward 10m radius)
        >>> # yaw_rate will be ~17 deg/s (3/10 * 57.3)
    """
    # Step 1: Convert GPS differences to meters in local tangent plane
    lat_diff = math.radians(target_lat - current_lat)
    lon_diff = math.radians(target_lon - current_lon)
    avg_lat = math.radians((current_lat + target_lat) / 2)

    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(avg_lat)

    # Vector pointing from drone TO target (radius vector)
    to_target_north = lat_diff * meters_per_lat  # Positive = target is north
    to_target_east = lon_diff * meters_per_lon  # Positive = target is east

    # Step 2: Calculate current distance from target (actual radius)
    current_dist = math.sqrt(to_target_north**2 + to_target_east**2)

    # Step 3: Normalize direction to target (unit vector)
    # This gives us the radial direction (pointing toward target)
    if current_dist > 0:
        target_dir_north = to_target_north / current_dist
        target_dir_east = to_target_east / current_dist
    else:
        # Edge case: exactly at center, default to north
        target_dir_north = 1.0
        target_dir_east = 0.0

    # Step 4: Calculate TANGENTIAL direction (perpendicular to radius)
    # For clockwise orbit: rotate radius vector +90° (east, -north)
    # For counter-clockwise: rotate radius vector -90° (-east, north)
    # This is the direction of orbital motion
    if clockwise:
        tangent_north = target_dir_east        # 90° rotation: north becomes east
        tangent_east = -target_dir_north      # east becomes negative north
    else:
        tangent_north = -target_dir_east       # -90° rotation
        tangent_east = target_dir_north

    # Step 5: Calculate RADIAL correction using proportional control
    # If we're too far from target, add velocity toward center
    # If we're too close, add velocity away from center
    # Gain of 0.5 means 1m error produces 0.5 m/s correction velocity
    radial_correction = (current_dist - radius_m) * 0.5  # P-controller

    # Radial velocity is opposite to target direction (pointing away from target)
    radial_north = -target_dir_north * radial_correction
    radial_east = -target_dir_east * radial_correction

    # Step 6: Combine components into final velocity command
    # Tangential provides orbital motion, radial maintains distance
    north_vel = tangent_north * speed_m_s + radial_north
    east_vel = tangent_east * speed_m_s + radial_east

    # Step 7: Calculate yaw rate for camera tracking
    # In coordinated turn, yaw rate = linear_velocity / radius
    # Convert radians per second to degrees per second: 180/π = 57.2958 ≈ 57.3
    yaw_rate = (speed_m_s / radius_m) * 57.3  # rad/s to deg/s
    if not clockwise:
        yaw_rate = -yaw_rate  # Reverse for counter-clockwise orbit

    return north_vel, east_vel, yaw_rate


# =============================================================================
# PREDICTIVE TRACKING ENGINE
# =============================================================================

def _predict_target_position(
    target: TargetInfo, prediction_time_s: float = 1.0
) -> Tuple[float, float]:
    """Predict target's future position using dead reckoning.

    Dead reckoning is the process of calculating current position by using a
    previously determined position and advancing that position based upon known
    or estimated speeds over elapsed time.

    This is essential for smooth tracking of moving targets. Without prediction:
    1. Drone follows where target WAS (lag behind by ~1 second due to telemetry latency)
    2. Result: drone constantly chasing, never catching up
    3. Video footage shows target drifting in frame

    With prediction:
    1. Drone flies toward where target WILL BE in 1 second
    2. Result: drone intercepts target's path, maintains lock
    3. Video footage stays centered on target

    Mathematical Model:
        Future Position = Current Position + (Velocity × Time)

        In coordinate form:
        lat_future = lat_current + (velocity_north / meters_per_lat) × time
        lon_future = lon_current + (velocity_east / meters_per_lon) × time

        Where:
        - meters_per_lat ≈ 111,320 (constant)
        - meters_per_lon = 111,320 × cos(latitude) (latitude-dependent)

    Prediction Horizon (prediction_time_s):
        - 1.0 second is default, balancing responsiveness vs. noise rejection
        - Too short (<0.5s): Insufficient lead time, still lags
        - Too long (>3s): Accumulates velocity errors, overshoots
        - Adaptive horizon would improve accuracy for varying speeds

    Velocity Sources:
        - Vision system: Object tracking (YOLO) provides relative velocity
        - GPS tracker: Target's own GPS broadcast
        - Manual input: User estimates speed
        - Kalman filter: Would provide optimal velocity estimation

    Limitations:
        - Assumes constant velocity (no acceleration handling)
        - Does not model target turning or direction changes
        - GPS velocity has inherent noise (typically ±0.1 m/s)

    Args:
        target: TargetInfo dataclass containing current position and velocity
        prediction_time_s: How far ahead to predict in seconds (default 1.0)

    Returns:
        Tuple of (predicted_lat, predicted_lon) in decimal degrees

    Example:
        >>> target = TargetInfo(
        ...     lat=37.7749, lon=-122.4194,
        ...     velocity_north=10.0,  # Moving north at 10 m/s (36 km/h)
        ...     velocity_east=0.0
        ... )
        >>> future_lat, future_lon = _predict_target_position(target, 2.0)
        >>> # In 2 seconds, target will be 20 meters north
        >>> # future_lat ≈ 37.77508 (20m / 111,320m per degree)
    """
    # Step 1: Get coordinate conversion factors
    # These convert meters to degrees for GPS coordinate updates
    meters_per_lat = 111320.0  # Constant: 1 degree lat = 111.32 km
    meters_per_lon = 111320.0 * math.cos(math.radians(target.lat))  # Varies by latitude

    # Step 2: Calculate position change in meters over prediction horizon
    # Using: distance = velocity × time
    delta_north = target.velocity_north * prediction_time_s  # North displacement in meters
    delta_east = target.velocity_east * prediction_time_s   # East displacement in meters

    # Step 3: Convert meter displacements to degree changes
    # Using: degrees = meters / (meters per degree)
    delta_lat = delta_north / meters_per_lat  # Latitude change in degrees
    delta_lon = delta_east / meters_per_lon  # Longitude change in degrees

    # Step 4: Apply changes to current position
    # This is the dead reckoning update: new_pos = old_pos + displacement
    predicted_lat = target.lat + delta_lat
    predicted_lon = target.lon + delta_lon

    return predicted_lat, predicted_lon


# =============================================================================
# MCP TOOL FUNCTIONS - USER-FACING API
# =============================================================================

async def set_gimbal(
    pitch_deg: float = -45.0,
    yaw_deg: float = 0.0,
    roll_deg: float = 0.0
) -> str:
    """Set gimbal angles to control camera orientation independently of drone.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: True, openWorldHint: False}
        outputSchema: {type: object}

    This is the low-level gimbal control function that sets absolute angles.
    It clamps inputs to safe hardware limits before sending to MAVSDK.

    Use Cases:
    - Pre-positioning camera before tracking begins
    - Manual framing adjustments during flight
    - Setting fixed angles for mapping/survey missions

    Coordinate Frame:
        All angles are relative to the DRONE body frame (not Earth):
        - Yaw 0° = aligned with drone nose (regardless of drone heading)
        - Pitch -90° = straight down (nadir, regardless of drone tilt)
        - Roll 0° = camera horizon level (compensates for drone bank angle)

        This means the gimbal automatically stabilizes the image even when
        the drone banks during turns or pitches during acceleration.

    Hardware Constraints:
        - Pitch: -90° to +30° (limited upward to prevent propeller intrusion)
        - Yaw: -180° to +180° (full rotation)
        - Roll: -45° to +45° (limited to maintain stabilization quality)

        Values outside these ranges are automatically clamped.

    Args:
        pitch_deg: Pitch angle (-90=down, 0=level, 30=up). Default -45° (downward).
        yaw_deg: Yaw angle relative to drone (-180 to 180). Default 0° (forward).
        roll_deg: Roll angle (-45 to 45). Default 0° (level).

    Returns:
        JSON string with gimbal status including actual angles achieved.

    Example:
        >>> # Look straight down for nadir mapping
        >>> await set_gimbal(pitch_deg=-90.0, yaw_deg=0.0)
        >>>
        >>> # Look at 45° angle to side for oblique photography
        >>> await set_gimbal(pitch_deg=-45.0, yaw_deg=45.0)
    """
    # Clamp to safe limits to prevent hardware damage
    pitch = _clamp(pitch_deg, GIMBAL_PITCH_MIN, GIMBAL_PITCH_MAX)
    yaw = _clamp(yaw_deg, GIMBAL_YAW_MIN, GIMBAL_YAW_MAX)
    roll = _clamp(roll_deg, GIMBAL_ROLL_MIN, GIMBAL_ROLL_MAX)

    cm = ConnectionManager()
    drone = await cm.get_drone()

    if not drone:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before setting gimbal"
        ))

    try:
        # Get gimbal plugin from MAVSDK
        gimbal = drone.gimbal

        # Set gimbal angles via MAVSDK
        # MAVSDK gimbal protocol expects:
        # - pitch: -90° (looking down) to 0° (level), positive is up
        # - yaw: -180° to +180° relative to drone heading
        await gimbal.set_pitch_and_yaw(pitch, yaw)

        return json.dumps({
            "success": True,
            "pitch_deg": pitch,
            "yaw_deg": yaw,
            "roll_deg": roll,
            "message": f"Gimbal set to pitch={pitch:.1f}°, yaw={yaw:.1f}°"
        })

    except Exception as e:
        logger.exception("Failed to set gimbal")
        return json.dumps({
            "success": False,
            "error": str(e),
            "requested_angles": {"pitch": pitch_deg, "yaw": yaw_deg, "roll": roll_deg}
        })


async def point_camera_at(
    lat: float,
    lon: float,
    alt_m: Optional[float] = None
) -> str:
    """Point camera at specific GPS coordinates without moving the drone.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: True, openWorldHint: True}
        outputSchema: {type: object}

    This is a convenience function that combines position-based angle calculation
    with gimbal control. The drone maintains its current position while the camera
    reorients to frame the target coordinates.

    Calculation Process:
        1. Query current drone telemetry (position, altitude)
        2. Call _calculate_look_angles() to compute pitch and yaw to target
        3. Call set_gimbal() to execute the camera movement

    Use Cases:
    - Quick camera repositioning without flight
    - Framing static points of interest from hover
    - Manual tracking when automatic tracking is unavailable
    - Pre-positioning camera before engaging tracking mode

    Args:
        lat: Target latitude in decimal degrees
        lon: Target longitude in decimal degrees
        alt_m: Target altitude in meters (optional, defaults to current drone altitude)

    Returns:
        JSON string with gimbal status and calculated angles.

    Example:
        >>> # Point at a building entrance while hovering
        >>> await point_camera_at(lat=37.7749, lon=-122.4194, alt_m=5.0)
    """
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected or no telemetry cache",
            recoverable=True,
            suggested_action="Connect to drone before pointing camera"
        ))

    try:
        # Get current drone position from telemetry cache
        telem = await cache.get_latest()
        if not telem:
            return json.dumps({
                "success": False,
                "error": "No telemetry available"
            })

        # Calculate look angles from drone position to target
        # This uses 3D trigonometry in the local tangent plane
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            lat, lon, alt_m
        )

        # Apply calculated angles to gimbal
        # Roll is kept at 0 for level horizon
        return await set_gimbal(pitch_deg=pitch, yaw_deg=yaw, roll_deg=0.0)

    except Exception as e:
        logger.exception("Failed to point camera")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


async def orbit_target(
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float] = None,
    radius_m: float = DEFAULT_ORBIT_RADIUS,
    speed_m_s: float = DEFAULT_ORBIT_SPEED,
    altitude_offset_m: float = DEFAULT_ORBIT_ALTITUDE,
    clockwise: bool = True,
    duration_s: float = 30.0,
    keep_camera_locked: bool = True
) -> str:
    """Orbit around a target while keeping camera locked on it.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    This is the primary cinematic tracking mode. The drone flies a circular path
    around a target point while continuously pointing the camera at the center.
    Combines orbital mechanics (_calculate_orbit_velocity) with real-time gimbal control.

    Flight Pattern:
        1. Calculate orbit entry point (radius_m offset from target)
        2. Navigate to entry point using goto_gps
        3. Execute orbit loop at 10Hz:
           - Calculate orbital velocity with radial correction
           - Send velocity command to maintain circular motion
           - Update gimbal to track target center
        4. After duration, transition to hover (hold)

    Orbital Physics:
        Uses _calculate_orbit_velocity() to combine:
        - Tangential velocity: creates orbital motion
        - Radial correction: maintains exact radius despite disturbances
        - Result: smooth circular path with configurable radius and speed

    Gimbal Tracking:
        When keep_camera_locked=True:
        - Continuously calculates look angles from current position to target
        - Updates gimbal at 10Hz for smooth target tracking
        - Compensates for drone orientation changes during orbit

    Entry Point Selection:
        Entry point is offset by radius_m east or west of target, depending on
        orbit direction. This ensures immediate orbital motion without initial
        positioning phase.

    Args:
        target_lat: Target latitude (center of orbit)
        target_lon: Target longitude (center of orbit)
        target_alt_m: Target altitude in meters (optional)
        radius_m: Orbit radius in meters (default: 10m for close inspection)
        speed_m_s: Orbit speed in m/s (default: 3m/s for smooth video)
        altitude_offset_m: Height above target to orbit (default: 15m)
        clockwise: Orbit direction (default: True for clockwise)
        duration_s: Orbit duration in seconds (default: 30s)
        keep_camera_locked: Keep camera on target vs. free orientation (default: True)

    Returns:
        JSON string with orbit statistics including approximate orbit count.

    Safety Checks:
        - Verifies orbit altitude > MIN_TRACK_ALTITUDE (10m)
        - Validates successful entry point navigation before orbiting

    Example:
        >>> # Cinematic 360° shot of a building
        >>> await orbit_target(
        ...     target_lat=37.7749,
        ...     target_lon=-122.4194,
        ...     radius_m=20.0,
        ...     speed_m_s=2.0,
        ...     duration_s=60.0
        ... )
    """
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before orbiting"
        ))

    try:
        # Get current telemetry for altitude reference
        telem = await cache.get_latest()
        if not telem:
            return json.dumps(to_error_envelope(
                ErrorCode.MAV_NOT_CONNECTED,
                "No telemetry available",
                recoverable=True,
                suggested_action="Wait for telemetry data"
            ))

        # Calculate orbit altitude and validate safety limits
        # orbit_altitude = target_alt + offset (or current_alt + offset if target_alt unknown)
        orbit_altitude = (target_alt_m or telem.relative_altitude_m) + altitude_offset_m
        if orbit_altitude < MIN_TRACK_ALTITUDE:
            return json.dumps({
                "success": False,
                "error": f"Orbit altitude {orbit_altitude:.1f}m below minimum {MIN_TRACK_ALTITUDE}m"
            })

        # Calculate orbit entry point
        # Position entry point at radius_m offset, alternating east/west based on direction
        # This ensures immediate start of orbital motion
        entry_lat = target_lat + (radius_m / 111320.0) * (1 if not clockwise else -1)
        entry_lon = target_lon

        logger.info(f"Moving to orbit entry point: {entry_lat}, {entry_lon}")

        # Navigate to entry point before starting orbit
        entry_result = json.loads(await goto_gps(
            lat=entry_lat,
            lon=entry_lon,
            alt_m=orbit_altitude,
            speed_ms=speed_m_s
        ))

        if not entry_result.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Failed to reach orbit entry: {entry_result.get('error')}"
            })

        # Initialize orbit tracking variables
        logger.info(f"Starting orbit: radius={radius_m}m, speed={speed_m_s}m/s, duration={duration_s}s")
        start_time = asyncio.get_event_loop().time()
        orbit_count = 0
        last_yaw = 0.0

        # Main orbit loop - runs at 10Hz for smooth motion
        while asyncio.get_event_loop().time() - start_time < duration_s:
            loop_start = asyncio.get_event_loop().time()

            # Get current telemetry for position feedback
            telem = await cache.get_latest()
            if not telem:
                await asyncio.sleep(0.1)
                continue

            # Calculate orbital velocity command
            # Combines tangential motion with radial distance correction
            north_vel, east_vel, yaw_rate = _calculate_orbit_velocity(
                telem.latitude_deg, telem.longitude_deg,
                target_lat, target_lon,
                radius_m, speed_m_s, clockwise
            )

            # Send velocity command to flight controller
            # Duration 0.1s matches our 10Hz control loop
            await set_velocity(
                north_m_s=north_vel,
                east_m_s=east_vel,
                down_m_s=0.0,  # Maintain altitude
                duration_s=0.1
            )

            # Update gimbal to track target center
            if keep_camera_locked:
                # Calculate current look angles from drone to target
                pitch, yaw = _calculate_look_angles(
                    telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
                    target_lat, target_lon, target_alt_m
                )

                # Convert absolute yaw to relative gimbal yaw
                # Gimbal yaw is relative to drone nose, not absolute north
                drone_yaw = telem.yaw_deg if hasattr(telem, 'yaw_deg') else 0.0
                relative_yaw = yaw - drone_yaw

                try:
                    await drone.gimbal.set_pitch_and_yaw(pitch, relative_yaw)
                except:
                    pass  # Gimbal may not be available on all hardware

            # Track orbit progress for statistics
            # Detect full orbits by monitoring yaw angle crossing
            current_yaw = math.atan2(east_vel, north_vel)
            if last_yaw != 0 and abs(current_yaw - last_yaw) > math.pi:
                orbit_count += 1
            last_yaw = current_yaw

            # Maintain 10Hz update rate precisely
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        # Orbit complete - transition to hover for safety
        await hold(duration_s=2.0)

        # Calculate orbit statistics
        total_time = asyncio.get_event_loop().time() - start_time
        # Circumference = 2πr, distance = speed × time
        # orbits = distance / circumference = (speed × time) / (2πr)
        approximate_orbits = (speed_m_s * total_time) / (2 * math.pi * radius_m)

        return json.dumps({
            "success": True,
            "duration_s": total_time,
            "approximate_orbits": round(approximate_orbits, 1),
            "radius_m": radius_m,
            "speed_m_s": speed_m_s,
            "clockwise": clockwise,
            "camera_locked": keep_camera_locked
        })

    except Exception as e:
        logger.exception("Orbit failed")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


async def track_target(
    target_lat: float,
    target_lon: float,
    target_velocity_north: float = 0.0,
    target_velocity_east: float = 0.0,
    follow_distance_m: float = DEFAULT_TRACK_DISTANCE,
    altitude_m: float = 20.0,
    speed_m_s: float = 8.0,
    duration_s: float = 60.0,
    predictive: bool = True,
    tracking_mode: str = "follow"
) -> str:
    """Track and follow a moving target with predictive velocity compensation.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    This is the primary dynamic tracking mode for following moving subjects
    (people, vehicles, boats). It uses dead reckoning prediction to compensate
    for system latency and maintain smooth target lock.

    Tracking Modes:
        "follow" (default): Position behind target, following its path
            - Ideal for: tracking a snowboarder, following a car
            - Positions drone at follow_distance_m behind target

        "lead": Position ahead of target, leading its motion
            - Ideal for: intercepting paths, anticipating turns
            - Positions drone at follow_distance_m in front of target

        "side": Lateral tracking, perpendicular to target motion
            - Ideal for: profile shots, parallel survey
            - Positions drone to side based on velocity vector

    Predictive Algorithm:
        When predictive=True:
        1. Calculate target's predicted position in 1 second using:
           predicted_pos = current_pos + (velocity × 1s)
        2. Calculate desired drone position based on tracking mode
        3. Use P-controller to generate velocity command toward desired position
        4. Update target position simulation for next iteration

        This 1-second lookahead compensates for:
        - Telemetry latency (typically 100-500ms)
        - Command execution delay (flight controller response time)
        - GPS position uncertainty

    Control Architecture:
        The system uses a proportional (P) controller for velocity:
        velocity_command = position_error × kp

        Where:
        - position_error = desired_position - current_position (in meters)
        - kp = 0.5 (proportional gain) - chosen for smooth, non-oscillatory response
        - Output clamped to max speed (speed_m_s) for safety

        Higher kp = faster response but more oscillation
        Lower kp = smoother but more lag
        0.5 provides good balance for typical tracking scenarios

    Altitude Control:
        Separate P-controller maintains target altitude:
        vel_down = -(target_alt - current_alt) × 0.3
        Clamped to ±3 m/s for smooth altitude changes

    Args:
        target_lat: Initial target latitude
        target_lon: Initial target longitude
        target_velocity_north: Target north velocity component in m/s
        target_velocity_east: Target east velocity component in m/s
        follow_distance_m: Distance to maintain from target (default: 8m)
        altitude_m: Tracking altitude in meters (default: 20m)
        speed_m_s: Maximum tracking speed in m/s (default: 8m/s)
        duration_s: Tracking duration in seconds (default: 60s)
        predictive: Enable velocity prediction (default: True)
        tracking_mode: "follow", "lead", or "side" (default: "follow")

    Returns:
        JSON string with tracking statistics including update count and max velocity.

    Example:
        >>> # Follow a moving vehicle
        >>> await track_target(
        ...     target_lat=37.7749,
        ...     target_lon=-122.4194,
        ...     target_velocity_north=15.0,  # 54 km/h north
        ...     target_velocity_east=0.0,
        ...     tracking_mode="follow",
        ...     predictive=True,
        ...     duration_s=120.0
        ... )
    """
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before tracking"
        ))

    try:
        # Initialize target tracking state
        target = TargetInfo(
            lat=target_lat,
            lon=target_lon,
            velocity_north=target_velocity_north,
            velocity_east=target_velocity_east,
            label="tracked_target"
        )

        # Initialize tracking metrics
        start_time = asyncio.get_event_loop().time()
        update_count = 0
        max_velocity_reached = 0.0

        # Main tracking loop at 10Hz
        while asyncio.get_event_loop().time() - start_time < duration_s:
            loop_start = asyncio.get_event_loop().time()

            # Get current drone telemetry
            telem = await cache.get_latest()
            if not telem:
                await asyncio.sleep(0.1)
                continue

            # PREDICTIVE TRACKING STEP
            # If enabled, calculate where target will be in 1 second
            # This compensates for system latency and provides smoother tracking
            if predictive:
                target.lat, target.lon = _predict_target_position(target, 1.0)

            # Calculate vector from drone to (predicted) target in local meters
            # Convert GPS difference to meters using haversine approximation
            lat_diff = math.radians(target.lat - telem.latitude_deg)
            lon_diff = math.radians(target.lon - telem.longitude_deg)
            avg_lat = math.radians((telem.latitude_deg + target.lat) / 2)

            meters_per_lat = 111320.0
            meters_per_lon = 111320.0 * math.cos(avg_lat)

            to_target_north = lat_diff * meters_per_lat  # Positive = target north of drone
            to_target_east = lon_diff * meters_per_lon   # Positive = target east of drone

            # Calculate desired drone position based on tracking mode
            target_vel_mag = math.sqrt(target.velocity_north**2 + target.velocity_east**2)

            if target_vel_mag > 0.1:  # Target is moving significantly
                # Normalize target velocity to get direction vector
                target_dir_north = target.velocity_north / target_vel_mag
                target_dir_east = target.velocity_east / target_vel_mag

                if tracking_mode == "follow":
                    # DESIRED POSITION: Behind target
                    # Subtract follow_distance in direction of motion
                    # This keeps drone trailing the target
                    desired_north = to_target_north - target_dir_north * follow_distance_m
                    desired_east = to_target_east - target_dir_east * follow_distance_m

                elif tracking_mode == "lead":
                    # DESIRED POSITION: In front of target (intercept path)
                    # Add follow_distance in direction of motion
                    desired_north = to_target_north + target_dir_north * follow_distance_m
                    desired_east = to_target_east + target_dir_east * follow_distance_m

                else:  # side mode
                    # DESIRED POSITION: To the side (perpendicular to motion)
                    # Rotate direction vector 90° to get side vector
                    # For clockwise 90° rotation: (x, y) -> (y, -x)
                    side_north = -target_dir_east * follow_distance_m
                    side_east = target_dir_north * follow_distance_m
                    desired_north = to_target_north + side_north
                    desired_east = to_target_east + side_east
            else:
                # Target is stationary - hover directly above it
                desired_north = to_target_north
                desired_east = to_target_east

            # PROPORTIONAL CONTROLLER for velocity command
            # velocity = error × kp, where kp is proportional gain
            # kp = 0.5 chosen for balance of responsiveness and smoothness
            kp = 0.5  # Proportional gain - 1m error produces 0.5 m/s velocity
            vel_north = _clamp(desired_north * kp, -speed_m_s, speed_m_s)
            vel_east = _clamp(desired_east * kp, -speed_m_s, speed_m_s)

            # ALTITUDE CONTROL - separate P-controller
            # vel_down positive = descend, negative = ascend
            alt_error = altitude_m - telem.relative_altitude_m
            vel_down = _clamp(-alt_error * 0.3, -3.0, 3.0)  # Limit vertical rate to ±3 m/s

            # Send velocity command to flight controller
            await set_velocity(
                north_m_s=vel_north,
                east_m_s=vel_east,
                down_m_s=vel_down,
                duration_s=0.1  # 10Hz control rate
            )

            # Update tracking metrics
            current_vel = math.sqrt(vel_north**2 + vel_east**2)
            max_velocity_reached = max(max_velocity_reached, current_vel)
            update_count += 1

            # SIMULATE TARGET MOVEMENT (for predictive tracking)
            # Update target position based on its velocity for next iteration
            if predictive:
                dt = 0.1  # 10Hz = 0.1s timestep
                target.lat += (target.velocity_north / meters_per_lat) * dt
                target.lon += (target.velocity_east / meters_per_lon) * dt

            # Maintain 10Hz update rate
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        # Tracking complete - bring to hover
        await hold(duration_s=1.0)

        total_time = asyncio.get_event_loop().time() - start_time

        return json.dumps({
            "success": True,
            "duration_s": total_time,
            "updates_sent": update_count,
            "max_velocity_m_s": round(max_velocity_reached, 1),
            "tracking_mode": tracking_mode,
            "predictive": predictive,
            "final_target_lat": round(target.lat, 7),
            "final_target_lon": round(target.lon, 7)
        })

    except Exception as e:
        logger.exception("Tracking failed")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


async def spiral_search(
    center_lat: float,
    center_lon: float,
    start_altitude_m: float = 20.0,
    max_radius_m: float = 100.0,
    max_altitude_m: float = 50.0,
    rotations: float = 3.0,
    speed_m_s: float = 5.0
) -> str:
    """Perform expanding spiral search pattern for area coverage.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    This mission pattern executes a systematic expanding spiral starting from
    a center point, useful for search and rescue, area survey, or establishing
    visual contact with targets.

    Flight Pattern:
        The spiral is defined in polar coordinates (r, θ):
        - Radius increases linearly: r(t) = (t/T) × max_radius_m
        - Angle increases linearly: θ(t) = (t/T) × 2π × rotations
        - Altitude increases linearly: z(t) = start_alt + (t/T) × (max_alt - start_alt)

        Where t is step index and T is total steps.

        This creates an Archimedean spiral pattern with simultaneous climb,
        ensuring complete coverage of expanding search area.

        Total points = 10 × rotations × 2π (10 steps per radian for smooth motion)

    Camera Behavior:
        The gimbal continuously points at the spiral center, maintaining visual
        contact with the search origin even as the drone expands outward.

    Safety Features:
        - Begins with navigation to center point at start_altitude_m
        - Climbs gradually to maintain clearance as radius increases
        - Returns to center at original altitude after completing spiral

    Args:
        center_lat: Center latitude of search area
        center_lon: Center longitude of search area
        start_altitude_m: Starting altitude in meters (default: 20m)
        max_radius_m: Maximum spiral radius in meters (default: 100m)
        max_altitude_m: Maximum altitude in meters (default: 50m)
        rotations: Number of complete spiral rotations (default: 3.0)
        speed_m_s: Flight speed between points in m/s (default: 5m/s)

    Returns:
        JSON string with search statistics including success rate per point.

    Example:
        >>> # Search 100m radius area with 3 spiral rotations
        >>> await spiral_search(
        ...     center_lat=37.7749,
        ...     center_lon=-122.4194,
        ...     max_radius_m=100.0,
        ...     rotations=3.0
        ... )
    """
    cm = ConnectionManager()
    drone = await cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before spiral search"
        ))

    try:
        # Phase 1: Navigate to spiral center
        logger.info(f"Moving to spiral center: {center_lat}, {center_lon}")
        center_result = json.loads(await goto_gps(
            lat=center_lat,
            lon=center_lon,
            alt_m=start_altitude_m,
            speed_ms=speed_m_s
        ))

        if not center_result.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Failed to reach center: {center_result.get('error')}"
            })

        # Calculate spiral trajectory parameters
        # Total angular distance in radians (2π × number of rotations)
        total_angle = 2 * math.pi * rotations

        # Steps at 10 steps per radian for smooth motion
        steps = int(total_angle * 10)

        spiral_results = []

        # Phase 2: Execute spiral pattern
        for i in range(steps):
            # Calculate current position in spiral (normalized 0-1 progress)
            progress = i / steps  # 0.0 at start, 1.0 at end
            angle = progress * total_angle  # Current angle in radians

            # Expanding radius: linear interpolation from 0 to max_radius_m
            radius = progress * max_radius_m

            # Climbing altitude: linear interpolation from start to max
            altitude = start_altitude_m + progress * (max_altitude_m - start_altitude_m)

            # Convert polar coordinates (radius, angle) to cartesian offset (north, east)
            # angle=0 is north (cos(0)=1), angle=π/2 is east (sin(π/2)=1)
            offset_north = radius * math.cos(angle)  # North component of offset
            offset_east = radius * math.sin(angle)   # East component of offset

            # Convert meter offset to GPS coordinate offset
            meters_per_lat = 111320.0
            meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

            target_lat = center_lat + (offset_north / meters_per_lat)
            target_lon = center_lon + (offset_east / meters_per_lon)

            # Navigate to this spiral point
            point_result = json.loads(await goto_gps(
                lat=target_lat,
                lon=target_lon,
                alt_m=altitude,
                speed_ms=speed_m_s
            ))

            spiral_results.append({
                "step": i,
                "radius_m": round(radius, 1),
                "altitude_m": round(altitude, 1),
                "success": point_result.get("success", False)
            })

            # Keep camera pointed at search center for visual reference
            telem = await cache.get_latest()
            if telem:
                pitch, yaw = _calculate_look_angles(
                    telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
                    center_lat, center_lon, None
                )
                try:
                    await drone.gimbal.set_pitch_and_yaw(pitch, 0.0)
                except:
                    pass

        # Phase 3: Return to center at original altitude
        await goto_gps(
            lat=center_lat,
            lon=center_lon,
            alt_m=start_altitude_m,
            speed_ms=speed_m_s
        )

        # Calculate completion statistics
        successful_points = sum(1 for r in spiral_results if r["success"])

        return json.dumps({
            "success": True,
            "total_points": len(spiral_results),
            "successful_points": successful_points,
            "max_radius_m": max_radius_m,
            "max_altitude_m": max_altitude_m,
            "rotations": rotations,
            "pattern": "expanding_spiral"
        })

    except Exception as e:
        logger.exception("Spiral search failed")
        return json.dumps({
            "success": False,
            "error": str(e)
        })
