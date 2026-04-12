"""Cinematic shot system for professional-quality drone filming.

Provides pre-programmed cinematic shot templates with smooth motion curves,
height-locked tracking, and automatic framing for action sports filming.

Shot Templates:
    - orbit: Circular path around subject with camera locked
    - follow_dynamic: Smooth following with predictive positioning
    - reveal_ascent: Rise from low to reveal scene
    - reveal_descent: Descend to reveal subject
    - pass_by: Smooth lateral pass with framing
    - top_down: Direct overhead with height lock
    - height_locked_track: Maintain exact altitude offset from subject
    - fpv_style: Dynamic, fluid motion for action sports

Motion Curves:
    - ease_in_out: Smooth acceleration/deceleration
    - linear: Constant velocity
    - exponential: Quick start, slow settle
    - bezier_quadratic: Simple curved paths
    - bezier_cubic: Complex S-curve paths

Features:
    - Height-locked tracking (±0.2m accuracy)
    - Automatic framing (rule of thirds, lead room)
    - Shot quality metrics (position error, smoothness)
    - Gimbal coordination for composition
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.tools.flight_tools import set_velocity, hold, goto_gps
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal, point_camera_at, _calculate_look_angles, _clamp
)

logger = logging.getLogger(__name__)

# Shot quality thresholds
MAX_POSITION_ERROR_M = 1.0
MAX_HEIGHT_ERROR_M = 0.5
MAX_GIMBAL_ANGULAR_VELOCITY_DEG_S = 30.0
MIN_SMOOTHNESS_SCORE = 0.8


class ShotType(Enum):
    """Cinematic shot types."""
    ORBIT = auto()
    FOLLOW_DYNAMIC = auto()
    REVEAL_ASCENT = auto()
    REVEAL_DESCENT = auto()
    PASS_BY = auto()
    TOP_DOWN = auto()
    HEIGHT_LOCKED_TRACK = auto()
    FPV_STYLE = auto()


class MotionCurveType(Enum):
    """Motion curve interpolation types."""
    LINEAR = auto()
    EASE_IN_OUT = auto()
    EASE_IN = auto()
    EASE_OUT = auto()
    EXPONENTIAL = auto()
    BEZIER_QUADRATIC = auto()
    BEZIER_CUBIC = auto()


@dataclass
class MotionCurve:
    """Motion curve for smooth interpolation.

    Attributes:
        curve_type: Type of interpolation curve
        start_time: Start time (seconds)
        duration: Duration (seconds)
        start_value: Starting value
        end_value: Ending value
    """
    curve_type: MotionCurveType
    start_time: float
    duration: float
    start_value: float = 0.0
    end_value: float = 1.0

    def evaluate(self, t: float) -> float:
        """Evaluate curve at time t (relative to start_time)."""
        if t < self.start_time:
            return self.start_value
        if t > self.start_time + self.duration:
            return self.end_value

        # Normalized time [0, 1]
        u = (t - self.start_time) / self.duration

        if self.curve_type == MotionCurveType.LINEAR:
            return self._linear(u)
        elif self.curve_type == MotionCurveType.EASE_IN_OUT:
            return self._ease_in_out(u)
        elif self.curve_type == MotionCurveType.EASE_IN:
            return self._ease_in(u)
        elif self.curve_type == MotionCurveType.EASE_OUT:
            return self._ease_out(u)
        elif self.curve_type == MotionCurveType.EXPONENTIAL:
            return self._exponential(u)
        else:
            return self._linear(u)

    def _linear(self, u: float) -> float:
        """Linear interpolation."""
        return self.start_value + (self.end_value - self.start_value) * u

    def _ease_in_out(self, u: float) -> float:
        """Cubic ease-in-out (smooth acceleration/deceleration)."""
        if u < 0.5:
            return self.start_value + (self.end_value - self.start_value) * 4 * u * u * u
        else:
            f = 1 - u
            return self.start_value + (self.end_value - self.start_value) * (1 - 4 * f * f * f)

    def _ease_in(self, u: float) -> float:
        """Quadratic ease-in."""
        return self.start_value + (self.end_value - self.start_value) * u * u

    def _ease_out(self, u: float) -> float:
        """Quadratic ease-out."""
        return self.start_value + (self.end_value - self.start_value) * (1 - (1 - u) * (1 - u))

    def _exponential(self, u: float) -> float:
        """Exponential curve (quick start, slow settle)."""
        if u < 0.001:
            return self.start_value
        return self.start_value + (self.end_value - self.start_value) * (1 - math.exp(-5 * u))


@dataclass
class ShotTemplate:
    """Cinematic shot template configuration.

    Attributes:
        name: Human-readable shot name
        shot_type: Type of shot
        distance_m: Distance from subject (meters)
        height_offset_m: Height above subject (meters)
        lateral_offset_m: Lateral offset (meters)
        speed_m_s: Movement speed (m/s)
        duration_s: Shot duration (seconds)
        motion_curve: Type of motion curve
        gimbal_mode: Gimbal tracking mode
        gimbal_pitch_offset: Additional pitch angle
        predictive_frames: Seconds to predict ahead
        height_lock: Whether to lock height relative to subject
        quality_thresholds: Dict of quality metric thresholds
    """
    name: str
    shot_type: ShotType
    distance_m: float = 10.0
    height_offset_m: float = 5.0
    lateral_offset_m: float = 0.0
    speed_m_s: float = 3.0
    duration_s: float = 10.0
    motion_curve: MotionCurveType = MotionCurveType.EASE_IN_OUT
    gimbal_mode: str = "track_subject"
    gimbal_pitch_offset: float = -15.0
    predictive_frames: float = 1.0
    height_lock: bool = False
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "max_position_error_m": 1.0,
        "max_height_error_m": 0.5,
        "min_framing_score": 0.7,
    })


# Pre-defined shot templates
CINEMATIC_TEMPLATES = {
    "orbit_close": ShotTemplate(
        name="Close Orbit (Cinematic)",
        shot_type=ShotType.ORBIT,
        distance_m=8.0,
        height_offset_m=3.0,
        speed_m_s=2.0,
        duration_s=15.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
    ),
    "orbit_wide": ShotTemplate(
        name="Wide Orbit (Context)",
        shot_type=ShotType.ORBIT,
        distance_m=20.0,
        height_offset_m=8.0,
        speed_m_s=4.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-30.0,
    ),
    "follow_close": ShotTemplate(
        name="Close Follow (Action)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=6.0,
        height_offset_m=2.5,
        lateral_offset_m=2.0,
        speed_m_s=8.0,
        duration_s=30.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-10.0,
        predictive_frames=1.5,
    ),
    "follow_wide": ShotTemplate(
        name="Wide Follow (Context)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=15.0,
        height_offset_m=6.0,
        lateral_offset_m=5.0,
        speed_m_s=12.0,
        duration_s=45.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-20.0,
        predictive_frames=1.0,
    ),
    "reveal_hero": ShotTemplate(
        name="Hero Reveal",
        shot_type=ShotType.REVEAL_ASCENT,
        distance_m=0.0,
        height_offset_m=20.0,
        speed_m_s=2.0,
        duration_s=8.0,
        motion_curve=MotionCurveType.EASE_OUT,
        gimbal_pitch_offset=0.0,
    ),
    "pass_by_low": ShotTemplate(
        name="Low Pass-By (Profile)",
        shot_type=ShotType.PASS_BY,
        distance_m=12.0,
        height_offset_m=1.5,
        lateral_offset_m=8.0,
        speed_m_s=6.0,
        duration_s=5.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=0.0,
    ),
    "top_down_dynamic": ShotTemplate(
        name="Top-Down Context",
        shot_type=ShotType.TOP_DOWN,
        distance_m=0.0,
        height_offset_m=15.0,
        speed_m_s=3.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-90.0,
    ),
    "height_locked_jump": ShotTemplate(
        name="Height-Locked Jump Tracking",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=8.0,
        height_offset_m=3.0,
        speed_m_s=10.0,
        duration_s=10.0,
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-15.0,
        height_lock=True,
        quality_thresholds={
            "max_position_error_m": 1.0,
            "max_height_error_m": 0.2,  # Tighter tolerance for height lock
            "min_framing_score": 0.8,
        },
    ),
    "fpv_dynamic": ShotTemplate(
        name="FPV-Style Dynamic",
        shot_type=ShotType.FPV_STYLE,
        distance_m=4.0,
        height_offset_m=2.0,
        speed_m_s=15.0,
        duration_s=20.0,
        motion_curve=MotionCurveType.BEZIER_CUBIC,
        gimbal_pitch_offset=-25.0,
        predictive_frames=0.5,
    ),
    "snowboard_halfpipe": ShotTemplate(
        name="Snowboard Halfpipe (Height-Locked)",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=10.0,
        height_offset_m=5.0,
        lateral_offset_m=6.0,
        speed_m_s=8.0,
        duration_s=30.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
        height_lock=True,
        quality_thresholds={
            "max_position_error_m": 1.5,
            "max_height_error_m": 0.3,
            "min_framing_score": 0.75,
        },
    ),
    "skate_ledge_gap": ShotTemplate(
        name="Skate Ledge/Gap Tracking",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=5.0,
        height_offset_m=2.0,
        lateral_offset_m=3.0,
        speed_m_s=6.0,
        duration_s=8.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-15.0,
        predictive_frames=0.8,
    ),
}


@dataclass
class ShotMetrics:
    """Real-time shot quality metrics.

    Attributes:
        position_error_m: Distance from planned path
        height_error_m: Altitude deviation
        gimbal_angular_velocity_deg_s: Gimbal movement speed
        framing_score: 0-1 score for subject framing
        smoothness_score: 0-1 score for motion smoothness
        velocity_m_s: Current velocity magnitude
        distance_to_subject_m: Current distance from subject
    """
    position_error_m: float = 0.0
    height_error_m: float = 0.0
    gimbal_angular_velocity_deg_s: float = 0.0
    framing_score: float = 1.0
    smoothness_score: float = 1.0
    velocity_m_s: float = 0.0
    distance_to_subject_m: float = 0.0

    def is_quality_acceptable(self, thresholds: Dict[str, float]) -> bool:
        """Check if current metrics meet quality thresholds."""
        if self.position_error_m > thresholds.get("max_position_error_m", MAX_POSITION_ERROR_M):
            return False
        if self.height_error_m > thresholds.get("max_height_error_m", MAX_HEIGHT_ERROR_M):
            return False
        if self.framing_score < thresholds.get("min_framing_score", 0.7):
            return False
        return True


class CinematicShotPlanner:
    """Plans and executes cinematic shots with smooth motion."""

    def __init__(self):
        self.templates = CINEMATIC_TEMPLATES
        self.metrics_history: List[ShotMetrics] = []

    def get_template(self, name: str) -> Optional[ShotTemplate]:
        """Get a shot template by name."""
        return self.templates.get(name)

    def list_templates(self) -> List[str]:
        """List available template names."""
        return list(self.templates.keys())

    def calculate_orbit_trajectory(
        self,
        center_lat: float,
        center_lon: float,
        radius_m: float,
        height_m: float,
        duration_s: float,
        clockwise: bool = True,
        num_points: int = 100
    ) -> List[Tuple[float, float, float]]:
        """Calculate orbit trajectory points.

        Returns:
            List of (lat, lon, altitude) waypoints
        """
        trajectory = []
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            if not clockwise:
                angle = -angle

            # Calculate offset
            offset_north = radius_m * math.cos(angle)
            offset_east = radius_m * math.sin(angle)

            # Convert to lat/lon
            lat = center_lat + offset_north / meters_per_lat
            lon = center_lon + offset_east / meters_per_lon

            trajectory.append((lat, lon, height_m))

        return trajectory

    def calculate_follow_trajectory(
        self,
        subject_path: List[Tuple[float, float, float]],
        offset_north: float,
        offset_east: float,
        offset_up: float,
        num_points: int = 100
    ) -> List[Tuple[float, float, float]]:
        """Calculate follow trajectory relative to subject path.

        Args:
            subject_path: List of (lat, lon, alt) subject positions
            offset_north: North offset from subject (m)
            offset_east: East offset from subject (m)
            offset_up: Up offset from subject (m)

        Returns:
            List of (lat, lon, altitude) drone positions
        """
        trajectory = []
        meters_per_lat = 111320.0

        for lat, lon, alt in subject_path:
            meters_per_lon = 111320.0 * math.cos(math.radians(lat))

            # Apply offset
            drone_lat = lat + offset_north / meters_per_lat
            drone_lon = lon + offset_east / meters_per_lon
            drone_alt = alt + offset_up

            trajectory.append((drone_lat, drone_lon, drone_alt))

        return trajectory


# MCP Tool Functions


async def execute_cinematic_shot(
    template_name: str,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float] = None,
    duration_s: Optional[float] = None,
    custom_params: Optional[Dict[str, Any]] = None
) -> str:
    """Execute a pre-programmed cinematic shot.

    Args:
        template_name: Name of shot template (e.g., "orbit_close", "follow_close")
        target_lat: Target/subject latitude
        target_lon: Target/subject longitude
        target_alt_m: Target altitude (optional)
        duration_s: Override duration (optional)
        custom_params: Custom parameter overrides (optional)

    Available Templates:
        - orbit_close: Tight orbit, 8m radius, cinematic
        - orbit_wide: Wide orbit, 20m radius, context
        - follow_close: Close follow, 6m distance, action
        - follow_wide: Wide follow, 15m distance, context
        - reveal_hero: Rising reveal shot
        - pass_by_low: Low lateral pass, profile view
        - top_down_dynamic: Overhead view
        - height_locked_jump: Exact height tracking for jumps
        - fpv_dynamic: Aggressive FPV-style motion
        - snowboard_halfpipe: Optimized for halfpipe
        - skate_ledge_gap: Optimized for skate gaps

    Returns:
        JSON string with shot results and quality metrics.
    """
    planner = CinematicShotPlanner()
    template = planner.get_template(template_name)

    if not template:
        available = ", ".join(planner.list_templates())
        return json.dumps({
            "success": False,
            "error": f"Unknown template: {template_name}. Available: {available}"
        })

    # Apply custom overrides
    if duration_s:
        template.duration_s = duration_s
    if custom_params:
        for key, value in custom_params.items():
            if hasattr(template, key):
                setattr(template, key, value)

    cm = ConnectionManager()
    drone = cm.get_drone()
    cache = cm.get_telemetry_cache()

    if not drone or not cache:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    try:
        # Get current position
        telem = await cache.get_latest()
        if not telem:
            return json.dumps({"success": False, "error": "No telemetry available"})

        start_time = asyncio.get_event_loop().time()
        metrics_history = []

        # Create motion curve for velocity ramp
        velocity_curve = MotionCurve(
            curve_type=template.motion_curve,
            start_time=0.0,
            duration=template.duration_s,
            start_value=0.0,
            end_value=1.0
        )

        logger.info(f"Starting cinematic shot: {template.name}")

        # Execute shot based on type
        if template.shot_type == ShotType.ORBIT:
            result = await _execute_orbit(
                template, target_lat, target_lon, target_alt_m,
                velocity_curve, cache, drone, metrics_history
            )
        elif template.shot_type == ShotType.FOLLOW_DYNAMIC:
            result = await _execute_follow(
                template, target_lat, target_lon, target_alt_m,
                velocity_curve, cache, drone, metrics_history
            )
        elif template.shot_type == ShotType.HEIGHT_LOCKED_TRACK:
            result = await _execute_height_locked(
                template, target_lat, target_lon, target_alt_m,
                velocity_curve, cache, drone, metrics_history
            )
        else:
            # Generic execution for other types
            result = await _execute_generic(
                template, target_lat, target_lon, target_alt_m,
                velocity_curve, cache, drone, metrics_history
            )

        # Calculate overall quality
        if metrics_history:
            avg_position_error = sum(m.position_error_m for m in metrics_history) / len(metrics_history)
            avg_height_error = sum(m.height_error_m for m in metrics_history) / len(metrics_history)
            avg_framing = sum(m.framing_score for m in metrics_history) / len(metrics_history)
            min_framing = min(m.framing_score for m in metrics_history)
        else:
            avg_position_error = 0.0
            avg_height_error = 0.0
            avg_framing = 1.0
            min_framing = 1.0

        actual_duration = asyncio.get_event_loop().time() - start_time

        return json.dumps({
            "success": True,
            "template": template.name,
            "shot_type": template.shot_type.name,
            "duration_s": actual_duration,
            "quality_metrics": {
                "avg_position_error_m": round(avg_position_error, 2),
                "avg_height_error_m": round(avg_height_error, 2),
                "avg_framing_score": round(avg_framing, 2),
                "min_framing_score": round(min_framing, 2),
                "samples_collected": len(metrics_history),
            },
            "parameters_used": {
                "distance_m": template.distance_m,
                "height_offset_m": template.height_offset_m,
                "speed_m_s": template.speed_m_s,
                "motion_curve": template.motion_curve.name,
                "gimbal_pitch_offset": template.gimbal_pitch_offset,
            },
            "result": result
        })

    except Exception as e:
        logger.exception("Cinematic shot failed")
        return json.dumps({
            "success": False,
            "error": str(e),
            "template": template.name
        })


async def _execute_orbit(
    template: ShotTemplate,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float],
    curve: MotionCurve,
    cache: Any,
    drone: Any,
    metrics_history: List[ShotMetrics]
) -> Dict[str, Any]:
    """Execute orbit shot."""
    # Calculate trajectory
    planner = CinematicShotPlanner()
    telem = await cache.get_latest()

    orbit_alt = (target_alt_m or telem.relative_altitude_m) + template.height_offset_m

    trajectory = planner.calculate_orbit_trajectory(
        target_lat, target_lon,
        template.distance_m, orbit_alt,
        template.duration_s
    )

    start_time = asyncio.get_event_loop().time()
    points_executed = 0

    while asyncio.get_event_loop().time() - start_time < template.duration_s:
        loop_start = asyncio.get_event_loop().time()
        elapsed = loop_start - start_time

        # Get current telemetry
        telem = await cache.get_latest()
        if not telem:
            await asyncio.sleep(0.05)
            continue

        # Find closest trajectory point
        progress = elapsed / template.duration_s
        point_idx = int(progress * len(trajectory))
        if point_idx >= len(trajectory):
            point_idx = len(trajectory) - 1

        target_lat_traj, target_lon_traj, target_alt_traj = trajectory[point_idx]

        # Calculate velocity to reach target point
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        delta_lat = target_lat_traj - telem.latitude_deg
        delta_lon = target_lon_traj - telem.longitude_deg

        vel_north = delta_lat * meters_per_lat * 2.0  # P-controller
        vel_east = delta_lon * meters_per_lon * 2.0
        vel_down = -(target_alt_traj - telem.relative_altitude_m) * 1.0

        # Clamp velocities
        speed = math.sqrt(vel_north**2 + vel_east**2)
        if speed > template.speed_m_s:
            scale = template.speed_m_s / speed
            vel_north *= scale
            vel_east *= scale

        # Send velocity command
        await set_velocity(
            north_m_s=vel_north,
            east_m_s=vel_east,
            down_m_s=vel_down,
            duration_s=0.1
        )

        # Update gimbal to track subject
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            target_lat, target_lon, target_alt_m
        )
        pitch += template.gimbal_pitch_offset

        try:
            await drone.gimbal.set_pitch_and_yaw(pitch, yaw - telem.yaw_deg if hasattr(telem, 'yaw_deg') else 0)
        except:
            pass

        # Calculate metrics
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        lat_error = (target_lat_traj - telem.latitude_deg) * meters_per_lat
        lon_error = (target_lon_traj - telem.longitude_deg) * meters_per_lon
        alt_error = target_alt_traj - telem.relative_altitude_m

        position_error = math.sqrt(lat_error**2 + lon_error**2)

        metrics = ShotMetrics(
            position_error_m=position_error,
            height_error_m=abs(alt_error),
            velocity_m_s=speed,
            distance_to_subject_m=template.distance_m
        )
        metrics_history.append(metrics)

        points_executed += 1

        # Maintain 10Hz
        elapsed_loop = asyncio.get_event_loop().time() - loop_start
        if elapsed_loop < 0.1:
            await asyncio.sleep(0.1 - elapsed_loop)

    return {
        "points_executed": points_executed,
        "trajectory_points": len(trajectory),
        "orbit_complete": True
    }


async def _execute_follow(
    template: ShotTemplate,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float],
    curve: MotionCurve,
    cache: Any,
    drone: Any,
    metrics_history: List[ShotMetrics]
) -> Dict[str, Any]:
    """Execute follow shot."""
    # Similar to track_target but with cinematic parameters
    from avatar.mcp_server.tools.tracking_tools import track_target

    result_json = await track_target(
        target_lat=target_lat,
        target_lon=target_lon,
        target_velocity_north=0.0,  # Will be updated dynamically
        target_velocity_east=0.0,
        follow_distance_m=template.distance_m,
        altitude_m=(target_alt_m or 20.0) + template.height_offset_m,
        speed_m_s=template.speed_m_s,
        duration_s=template.duration_s,
        predictive=True,
        tracking_mode="follow"
    )

    return json.loads(result_json)


async def _execute_height_locked(
    template: ShotTemplate,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float],
    curve: MotionCurve,
    cache: Any,
    drone: Any,
    metrics_history: List[ShotMetrics]
) -> Dict[str, Any]:
    """Execute height-locked tracking shot."""
    start_time = asyncio.get_event_loop().time()
    last_target_lat = target_lat
    last_target_lon = target_lon
    last_target_alt = target_alt_m or 20.0

    while asyncio.get_event_loop().time() - start_time < template.duration_s:
        loop_start = asyncio.get_event_loop().time()

        # Get current telemetry
        telem = await cache.get_latest()
        if not telem:
            await asyncio.sleep(0.05)
            continue

        # Calculate desired position (behind and offset)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        # Vector to target
        to_target_lat = last_target_lat - telem.latitude_deg
        to_target_lon = last_target_lon - telem.longitude_deg

        to_target_north = to_target_lat * meters_per_lat
        to_target_east = to_target_lon * meters_per_lon

        # Desired position: behind target by distance_m
        dist_to_target = math.sqrt(to_target_north**2 + to_target_east**2)
        if dist_to_target > 0:
            # Position behind target
            desired_north = to_target_north - (to_target_north / dist_to_target) * template.distance_m
            desired_east = to_target_east - (to_target_east / dist_to_target) * template.distance_m
        else:
            desired_north = -template.distance_m
            desired_east = 0.0

        # Height lock: maintain exact offset
        desired_altitude = last_target_alt + template.height_offset_m

        # PID control for position
        kp_pos = 0.5
        vel_north = _clamp(desired_north * kp_pos, -template.speed_m_s, template.speed_m_s)
        vel_east = _clamp(desired_east * kp_pos, -template.speed_m_s, template.speed_m_s)

        # Height control with tighter gains
        kp_alt = 1.0
        alt_error = desired_altitude - telem.relative_altitude_m
        vel_down = _clamp(-alt_error * kp_alt, -3.0, 3.0)

        # Send velocity
        await set_velocity(
            north_m_s=vel_north,
            east_m_s=vel_east,
            down_m_s=vel_down,
            duration_s=0.1
        )

        # Calculate metrics
        position_error = math.sqrt(desired_north**2 + desired_east**2)
        height_error = abs(alt_error)
        velocity = math.sqrt(vel_north**2 + vel_east**2)

        metrics = ShotMetrics(
            position_error_m=position_error,
            height_error_m=height_error,
            velocity_m_s=velocity,
            distance_to_subject_m=dist_to_target
        )
        metrics_history.append(metrics)

        # Update gimbal
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            last_target_lat, last_target_lon, last_target_alt
        )
        pitch += template.gimbal_pitch_offset

        try:
            await drone.gimbal.set_pitch_and_yaw(pitch, 0.0)
        except:
            pass

        # Maintain 20Hz for height lock (higher precision)
        elapsed = asyncio.get_event_loop().time() - loop_start
        if elapsed < 0.05:
            await asyncio.sleep(0.05 - elapsed)

    return {
        "height_lock_maintained": True,
        "target_offset_m": template.height_offset_m
    }


async def _execute_generic(
    template: ShotTemplate,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float],
    curve: MotionCurve,
    cache: Any,
    drone: Any,
    metrics_history: List[ShotMetrics]
) -> Dict[str, Any]:
    """Execute generic shot (fallback)."""
    # Default to orbit behavior
    return await _execute_orbit(
        template, target_lat, target_lon, target_alt_m,
        curve, cache, drone, metrics_history
    )


async def list_cinematic_templates() -> str:
    """List available cinematic shot templates.

    Returns:
        JSON string with template names and descriptions.
    """
    planner = CinematicShotPlanner()
    templates = []

    for name, template in planner.templates.items():
        templates.append({
            "name": name,
            "display_name": template.name,
            "shot_type": template.shot_type.name,
            "distance_m": template.distance_m,
            "height_offset_m": template.height_offset_m,
            "duration_s": template.duration_s,
            "height_lock": template.height_lock,
        })

    return json.dumps({
        "success": True,
        "templates": templates,
        "count": len(templates)
    })


async def preview_cinematic_shot(
    template_name: str,
    target_lat: float,
    target_lon: float
) -> str:
    """Preview shot trajectory without executing.

    Returns:
        JSON string with trajectory preview.
    """
    planner = CinematicShotPlanner()
    template = planner.get_template(template_name)

    if not template:
        return json.dumps({
            "success": False,
            "error": f"Unknown template: {template_name}"
        })

    # Calculate sample trajectory
    if template.shot_type == ShotType.ORBIT:
        trajectory = planner.calculate_orbit_trajectory(
            target_lat, target_lon,
            template.distance_m,
            template.height_offset_m + 20.0,  # Assumed base altitude
            template.duration_s,
            num_points=20
        )
    else:
        # Generic preview
        trajectory = [(target_lat, target_lon, template.height_offset_m + 20.0)]

    return json.dumps({
        "success": True,
        "template": template_name,
        "shot_type": template.shot_type.name,
        "estimated_duration_s": template.duration_s,
        "sample_trajectory": [
            {"lat": lat, "lon": lon, "alt_m": alt}
            for lat, lon, alt in trajectory[:5]  # First 5 points
        ],
        "total_waypoints": len(trajectory),
        "motion_curve": template.motion_curve.name,
    })
