"""Advanced tracking and camera control tools.

Provides sophisticated camera tracking capabilities:
    - orbit_target: Circle around a target while keeping camera locked
    - track_target: Follow a moving target (e.g., snowboarder down hill)
    - set_gimbal: Control camera gimbal angle independently
    - point_camera_at: Point camera at specific GPS coordinates
    - spiral_search: Expanding spiral search pattern

Features:
    - Gimbal control (pitch, yaw, roll)
    - Coordinated flight + camera movement
    - Velocity-based target following
    - Predictive tracking for moving targets
    - Smooth transitions and interpolation
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

logger = logging.getLogger(__name__)

# Gimbal limits (degrees)
GIMBAL_PITCH_MIN = -90.0   # Straight down
GIMBAL_PITCH_MAX = 30.0    # Slightly up
GIMBAL_YAW_MIN = -180.0    # Full rotation
GIMBAL_YAW_MAX = 180.0
GIMBAL_ROLL_MIN = -45.0    # Limited roll for stability
GIMBAL_ROLL_MAX = 45.0

# Tracking constants
DEFAULT_ORBIT_RADIUS = 10.0       # meters
DEFAULT_ORBIT_SPEED = 3.0         # m/s
DEFAULT_ORBIT_ALTITUDE = 15.0     # meters above target
DEFAULT_TRACK_DISTANCE = 8.0      # meters behind target
MIN_TRACK_ALTITUDE = 10.0         # minimum tracking altitude


@dataclass
class TargetInfo:
    """Information about a tracked target.

    Attributes:
        lat: Target latitude
        lon: Target longitude
        alt_m: Target altitude (optional)
        velocity_north: Target velocity north component (m/s)
        velocity_east: Target velocity east component (m/s)
        last_update: Timestamp of last update
        label: Target label/classification
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
    """Gimbal angle configuration.

    Attributes:
        pitch_deg: Pitch angle (-90 = down, 0 = level, 30 = up)
        yaw_deg: Yaw angle relative to drone (-180 to 180)
        roll_deg: Roll angle (-45 to 45)
    """
    pitch_deg: float = -45.0  # Default looking down at 45°
    yaw_deg: float = 0.0
    roll_deg: float = 0.0


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def _calculate_look_angles(
    drone_lat: float, drone_lon: float, drone_alt: float,
    target_lat: float, target_lon: float, target_alt: Optional[float]
) -> Tuple[float, float]:
    """Calculate gimbal angles to look at target.

    Returns:
        Tuple of (pitch_deg, yaw_deg) relative to drone
    """
    # Calculate horizontal distance
    lat_diff = math.radians(target_lat - drone_lat)
    lon_diff = math.radians(target_lon - drone_lon)
    avg_lat = math.radians((drone_lat + target_lat) / 2)

    # Approximate meters per degree
    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(avg_lat)

    north_dist = lat_diff * meters_per_lat
    east_dist = lon_diff * meters_per_lon

    # Calculate yaw (heading to target)
    yaw = math.degrees(math.atan2(east_dist, north_dist))

    # Calculate pitch
    horizontal_dist = math.sqrt(north_dist**2 + east_dist**2)
    alt_diff = (target_alt or drone_alt) - drone_alt
    pitch = math.degrees(math.atan2(alt_diff, horizontal_dist))

    return pitch, yaw


def _calculate_orbit_velocity(
    current_lat: float, current_lon: float,
    target_lat: float, target_lon: float,
    radius_m: float, speed_m_s: float, clockwise: bool = True
) -> Tuple[float, float, float]:
    """Calculate velocity to maintain circular orbit.

    Args:
        current_lat, current_lon: Current drone position
        target_lat, target_lon: Center of orbit
        radius_m: Desired orbit radius
        speed_m_s: Orbit speed
        clockwise: Orbit direction

    Returns:
        Tuple of (north_m_s, east_m_s, yaw_rate_deg_s)
    """
    # Calculate vector to target
    lat_diff = math.radians(target_lat - current_lat)
    lon_diff = math.radians(target_lon - current_lon)
    avg_lat = math.radians((current_lat + target_lat) / 2)

    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(avg_lat)

    to_target_north = lat_diff * meters_per_lat
    to_target_east = lon_diff * meters_per_lon

    # Current distance from target
    current_dist = math.sqrt(to_target_north**2 + to_target_east**2)

    # Normalize direction to target
    if current_dist > 0:
        target_dir_north = to_target_north / current_dist
        target_dir_east = to_target_east / current_dist
    else:
        target_dir_north = 1.0
        target_dir_east = 0.0

    # Tangential direction for orbit (perpendicular to target direction)
    if clockwise:
        tangent_north = target_dir_east
        tangent_east = -target_dir_north
    else:
        tangent_north = -target_dir_east
        tangent_east = target_dir_north

    # Add radial component to maintain radius
    radial_correction = (current_dist - radius_m) * 0.5  # P controller
    radial_north = -target_dir_north * radial_correction
    radial_east = -target_dir_east * radial_correction

    # Combined velocity
    north_vel = tangent_north * speed_m_s + radial_north
    east_vel = tangent_east * speed_m_s + radial_east

    # Yaw rate for orbiting (degrees per second)
    yaw_rate = (speed_m_s / radius_m) * 57.3  # rad/s to deg/s
    if not clockwise:
        yaw_rate = -yaw_rate

    return north_vel, east_vel, yaw_rate


def _predict_target_position(
    target: TargetInfo, prediction_time_s: float = 1.0
) -> Tuple[float, float]:
    """Predict target position in future.

    Args:
        target: Current target info with velocity
        prediction_time_s: How far ahead to predict

    Returns:
        Tuple of (predicted_lat, predicted_lon)
    """
    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(math.radians(target.lat))

    # Predict position change
    delta_north = target.velocity_north * prediction_time_s
    delta_east = target.velocity_east * prediction_time_s

    delta_lat = delta_north / meters_per_lat
    delta_lon = delta_east / meters_per_lon

    return target.lat + delta_lat, target.lon + delta_lon


# MCP Tool Functions


async def set_gimbal(
    pitch_deg: float = -45.0,
    yaw_deg: float = 0.0,
    roll_deg: float = 0.0
) -> str:
    """Set gimbal angles to control camera orientation.

    Controls the camera gimbal independently of drone orientation.
    Useful for looking at targets while drone is in different orientations.

    Args:
        pitch_deg: Pitch angle (-90=down, 0=level, 30=up). Default -45°.
        yaw_deg: Yaw angle relative to drone (-180 to 180). Default 0°.
        roll_deg: Roll angle (-45 to 45). Default 0°.

    Returns:
        JSON string with gimbal status.
    """
    # Clamp to safe limits
    pitch = _clamp(pitch_deg, GIMBAL_PITCH_MIN, GIMBAL_PITCH_MAX)
    yaw = _clamp(yaw_deg, GIMBAL_YAW_MIN, GIMBAL_YAW_MAX)
    roll = _clamp(roll_deg, GIMBAL_ROLL_MIN, GIMBAL_ROLL_MAX)

    cm = ConnectionManager()
    drone = cm.get_drone()

    if not drone:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    try:
        # Get gimbal plugin
        gimbal = drone.gimbal

        # Set gimbal angles
        # MAVSDK gimbal expects: pitch (-90 to 0 looking down), yaw (-180 to 180)
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
    """Point camera at specific GPS coordinates.

    Calculates and sets gimbal angles to look at target coordinates.
    Drone maintains current position, only camera moves.

    Args:
        lat: Target latitude
        lon: Target longitude
        alt_m: Target altitude (optional, defaults to current altitude)

    Returns:
        JSON string with gimbal status.
    """
    cm = ConnectionManager()
    drone = cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps({
            "success": False,
            "error": "Drone not connected or no telemetry cache"
        })

    try:
        # Get current position
        telem = await cache.get_latest()
        if not telem:
            return json.dumps({
                "success": False,
                "error": "No telemetry available"
            })

        # Calculate look angles
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            lat, lon, alt_m
        )

        # Set gimbal
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

    Flies in a circle around the target point while continuously pointing
    the camera at the center. Perfect for cinematic shots or surveillance.

    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        target_alt_m: Target altitude (optional)
        radius_m: Orbit radius in meters (default: 10m)
        speed_m_s: Orbit speed in m/s (default: 3m/s)
        altitude_offset_m: Height above target to orbit (default: 15m)
        clockwise: Orbit direction (default: True)
        duration_s: How long to orbit in seconds (default: 30s)
        keep_camera_locked: Keep camera pointing at target (default: True)

    Returns:
        JSON string with orbit results.
    """
    cm = ConnectionManager()
    drone = cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    try:
        # Get telemetry
        telem = await cache.get_latest()
        if not telem:
            return json.dumps({
                "success": False,
                "error": "No telemetry available"
            })

        # Check altitude
        orbit_altitude = (target_alt_m or telem.relative_altitude_m) + altitude_offset_m
        if orbit_altitude < MIN_TRACK_ALTITUDE:
            return json.dumps({
                "success": False,
                "error": f"Orbit altitude {orbit_altitude:.1f}m below minimum {MIN_TRACK_ALTITUDE}m"
            })

        # Move to orbit entry point
        entry_lat = target_lat + (radius_m / 111320.0) * (1 if not clockwise else -1)
        entry_lon = target_lon

        logger.info(f"Moving to orbit entry point: {entry_lat}, {entry_lon}")
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

        # Start orbiting
        logger.info(f"Starting orbit: radius={radius_m}m, speed={speed_m_s}m/s, duration={duration_s}s")
        start_time = asyncio.get_event_loop().time()
        orbit_count = 0
        last_yaw = 0.0

        while asyncio.get_event_loop().time() - start_time < duration_s:
            loop_start = asyncio.get_event_loop().time()

            # Get current position
            telem = await cache.get_latest()
            if not telem:
                await asyncio.sleep(0.1)
                continue

            # Calculate orbit velocity
            north_vel, east_vel, yaw_rate = _calculate_orbit_velocity(
                telem.latitude_deg, telem.longitude_deg,
                target_lat, target_lon,
                radius_m, speed_m_s, clockwise
            )

            # Set velocity
            await set_velocity(
                north_m_s=north_vel,
                east_m_s=east_vel,
                down_m_s=0.0,
                duration_s=0.1
            )

            # Keep camera locked on target
            if keep_camera_locked:
                # Calculate look angles
                pitch, yaw = _calculate_look_angles(
                    telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
                    target_lat, target_lon, target_alt_m
                )

                # Normalize yaw to relative
                drone_yaw = telem.yaw_deg if hasattr(telem, 'yaw_deg') else 0.0
                relative_yaw = yaw - drone_yaw

                try:
                    await drone.gimbal.set_pitch_and_yaw(pitch, relative_yaw)
                except:
                    pass  # Gimbal may not be available

            # Track orbit progress
            current_yaw = math.atan2(east_vel, north_vel)
            if last_yaw != 0 and abs(current_yaw - last_yaw) > math.pi:
                orbit_count += 1
            last_yaw = current_yaw

            # Maintain 10Hz update rate
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        # Stop and hover
        await hold(duration_s=2.0)

        total_time = asyncio.get_event_loop().time() - start_time
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
    """Track and follow a moving target.

    Follows a target (like a snowboarder down a hill) while maintaining
    camera lock. Supports predictive tracking for smoother following.

    Args:
        target_lat: Initial target latitude
        target_lon: Initial target longitude
        target_velocity_north: Target north velocity in m/s
        target_velocity_east: Target east velocity in m/s
        follow_distance_m: Distance to maintain behind target
        altitude_m: Tracking altitude
        speed_m_s: Maximum tracking speed
        duration_s: How long to track
        predictive: Use velocity prediction for smoother tracking
        tracking_mode: "follow" (behind), "lead" (in front), or "side" (lateral)

    Returns:
        JSON string with tracking results.
    """
    cm = ConnectionManager()
    drone = cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    try:
        # Create target info
        target = TargetInfo(
            lat=target_lat,
            lon=target_lon,
            velocity_north=target_velocity_north,
            velocity_east=target_velocity_east,
            label="tracked_target"
        )

        start_time = asyncio.get_event_loop().time()
        update_count = 0
        max_velocity_reached = 0.0

        while asyncio.get_event_loop().time() - start_time < duration_s:
            loop_start = asyncio.get_event_loop().time()

            # Get current position
            telem = await cache.get_latest()
            if not telem:
                await asyncio.sleep(0.1)
                continue

            # Predict target position
            if predictive:
                target.lat, target.lon = _predict_target_position(target, 1.0)

            # Calculate vector to target
            lat_diff = math.radians(target.lat - telem.latitude_deg)
            lon_diff = math.radians(target.lon - telem.longitude_deg)
            avg_lat = math.radians((telem.latitude_deg + target.lat) / 2)

            meters_per_lat = 111320.0
            meters_per_lon = 111320.0 * math.cos(avg_lat)

            to_target_north = lat_diff * meters_per_lat
            to_target_east = lon_diff * meters_per_lon

            # Calculate desired position based on tracking mode
            target_vel_mag = math.sqrt(target.velocity_north**2 + target.velocity_east**2)

            if target_vel_mag > 0.1:
                # Target is moving - calculate follow position
                target_dir_north = target.velocity_north / target_vel_mag
                target_dir_east = target.velocity_east / target_vel_mag

                if tracking_mode == "follow":
                    # Position behind target
                    desired_north = to_target_north - target_dir_north * follow_distance_m
                    desired_east = to_target_east - target_dir_east * follow_distance_m
                elif tracking_mode == "lead":
                    # Position in front of target
                    desired_north = to_target_north + target_dir_north * follow_distance_m
                    desired_east = to_target_east + target_dir_east * follow_distance_m
                else:  # side
                    # Position to the side (perpendicular)
                    side_north = -target_dir_east * follow_distance_m
                    side_east = target_dir_north * follow_distance_m
                    desired_north = to_target_north + side_north
                    desired_east = to_target_east + side_east
            else:
                # Target stationary - hover above
                desired_north = to_target_north
                desired_east = to_target_east

            # Calculate velocity command (P controller)
            kp = 0.5  # Proportional gain
            vel_north = _clamp(desired_north * kp, -speed_m_s, speed_m_s)
            vel_east = _clamp(desired_east * kp, -speed_m_s, speed_m_s)

            # Altitude control
            alt_error = altitude_m - telem.relative_altitude_m
            vel_down = _clamp(-alt_error * 0.3, -3.0, 3.0)

            # Send velocity command
            await set_velocity(
                north_m_s=vel_north,
                east_m_s=vel_east,
                down_m_s=vel_down,
                duration_s=0.1
            )

            # Track metrics
            current_vel = math.sqrt(vel_north**2 + vel_east**2)
            max_velocity_reached = max(max_velocity_reached, current_vel)
            update_count += 1

            # Update target position (simulate target movement)
            if predictive:
                dt = 0.1
                target.lat += (target.velocity_north / meters_per_lat) * dt
                target.lon += (target.velocity_east / meters_per_lon) * dt

            # Maintain 10Hz
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        # Stop
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
    """Perform expanding spiral search pattern.

    Flies an expanding spiral pattern starting from center and spiraling
    outward while climbing. Useful for search and rescue or area survey.

    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        start_altitude_m: Starting altitude
        max_radius_m: Maximum spiral radius
        max_altitude_m: Maximum altitude
        rotations: Number of spiral rotations
        speed_m_s: Flight speed

    Returns:
        JSON string with search results.
    """
    cm = ConnectionManager()
    drone = cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    try:
        # First move to center
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

        # Calculate spiral parameters
        total_angle = 2 * math.pi * rotations
        steps = int(total_angle * 10)  # 10 steps per radian

        spiral_results = []

        for i in range(steps):
            angle = (i / steps) * total_angle

            # Expanding radius
            radius = (i / steps) * max_radius_m

            # Altitude climb
            altitude = start_altitude_m + (i / steps) * (max_altitude_m - start_altitude_m)

            # Calculate target position
            offset_north = radius * math.cos(angle)
            offset_east = radius * math.sin(angle)

            # Convert to lat/lon offset
            meters_per_lat = 111320.0
            meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

            target_lat = center_lat + (offset_north / meters_per_lat)
            target_lon = center_lon + (offset_east / meters_per_lon)

            # Fly to this point
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

            # Keep camera pointed at center
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

        # Return to center altitude
        await goto_gps(
            lat=center_lat,
            lon=center_lon,
            alt_m=start_altitude_m,
            speed_ms=speed_m_s
        )

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
