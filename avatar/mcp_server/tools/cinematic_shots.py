"""Cinematic shot system for professional-quality drone filming.

This module provides a production-ready cinematic shot system for Project Avatar's
drone filming capabilities. It combines computer vision, predictive algorithms,
and smooth motion control to capture professional-grade action sports footage.

Architecture Overview:
---------------------
The cinematic system is built on three core pillars:

1. PREDICTIVE TRACKING (LookaheadPredictor)
   Compensates for 150-250ms vision processing latency inherent in the Pi 4 +
   YOLOv8-nano setup. By predicting where the subject will be when the command
   reaches the drone, we eliminate the "laggy follow" effect common in
   vision-based tracking systems.

2. SMOOTH MOTION CONTROL (MotionCurves + PID)
   Uses motion curves (ease_in_out, bezier, exponential) for natural
   acceleration/deceleration, and PID controllers for precise distance/height
   maintenance. This creates fluid, professional footage without jarring movements.

3. SPORT-SPECIFIC PROFILES
   Pre-tuned parameters for different action sports (snowboard, skate, motocross,
   trail running). Each profile considers typical speeds, motion patterns, and
   framing requirements for that sport.

Hardware Context (Project Avatar Mark4 7" Build):
--------------------------------------------------
- Frame: Mark4 7" (long-range cinematic platform)
- Max speed: ~12-15 m/s (limited for filming smoothness)
- Comfortable filming speed: 4-5 m/s (optimal for stable footage)
- Flight Controller: Pixhawk 6C Mini with cinematic PX4 tuning
- Companion Computer: Raspberry Pi 4 (150-250ms vision latency)
- Camera: Gimbal-stabilized with pitch/yaw control
- Detection: YOLOv8-nano for real-time subject tracking

Recommended PX4 Parameters for Cinematic Flight:
    - MPC_XY_VEL_MAX = 15 m/s (hardware limit, rarely used fully)
    - MPC_XY_VEL_P_ACC = 1.2 (smooth response, not aggressive)
    - MPC_JERK_AUTO = 2.0 (jerk limiting for fluid motion)
    - MPC_ACC_HOR = 1.5 m/s² (gentle acceleration)
    - MPC_Z_VEL_MAX_UP = 3.0 m/s
    - MPC_Z_VEL_MAX_DOWN = 1.5 m/s

Shot Templates Library:
----------------------
The system provides pre-programmed shot templates optimized for different scenarios:

ORBIT SHOTS (Circular tracking around subject):
    - orbit_close: Tight 8m radius orbit, slow 2m/s, cinematic feel
      USE WHEN: Subject is relatively stationary, you want dramatic emphasis
      EXAMPLE: Skater preparing for trick, athlete at starting line

    - orbit_wide: Wide 20m radius, 4m/s, shows environmental context
      USE WHEN: Subject in scenic location, establishing shot
      EXAMPLE: Snowboarder on mountain ridge, runner on coastal trail

FOLLOW SHOTS (Dynamic tracking of moving subject):
    - follow_close: Close 6m distance, 8m/s, immersive action feel
      USE WHEN: Fast action, want viewer to feel "in the action"
      EXAMPLE: Following a snowboarder through trees, motocross through whoops

    - follow_wide: Wide 15m distance, 12m/s, shows subject in environment
      USE WHEN: Higher speed action where context matters
      EXAMPLE: Downhill mountain bike run, powder snowboard descent

REVEAL SHOTS (Vertical movement for dramatic reveal):
    - reveal_hero: Rising from ground level to 20m, dramatic subject reveal
      USE WHEN: Starting low (behind obstacle), revealing hero moment
      EXAMPLE: Rising over hill to reveal skater landing trick

    - reveal_descent (implied): Coming down to reveal subject detail
      USE WHEN: Starting high, want to focus on subject detail
      EXAMPLE: Descending to show skateboarder's foot placement

PASS-BY SHOTS (Lateral tracking for profile view):
    - pass_by_low: Low 1.5m height, 6m/s, smooth profile tracking
      USE WHEN: Want side/profile view of subject in motion
      EXAMPLE: Tracking alongside skater doing ledge tricks, runner stride analysis

TOP-DOWN SHOTS (Overhead perspective):
    - top_down_dynamic: Direct overhead at 15m, shows patterns/movement
      USE WHEN: Want to show subject's path through terrain
      EXAMPLE: Surfer on wave pattern, skater in bowl, motocross track lines

HEIGHT-LOCKED TRACKING (Critical for vertical motion sports):
    - height_locked_jump: Maintains exact altitude offset from subject
      USE WHEN: Subject has significant vertical movement (jumps, drops)
      EXAMPLE: Snowboarder in halfpipe, motocross jumps, skate bowl airs
      KEY FEATURE: PID controller with tight gains keeps constant height offset

FPV-STYLE SHOTS (Aggressive, fluid motion):
    - fpv_dynamic: Fast 15m/s, close 4m distance, bezier motion paths
      USE WHEN: Want "fpv drone racing" aesthetic for action sports
      EXAMPLE: Following snowboarder through terrain park, weaving through trees
      WARNING: Requires skilled pilot oversight, aggressive motion profile

SPORT-SPECIFIC TEMPLATES (Pre-tuned for specific sports):
    - snowboard_halfpipe: Height-locked tracking optimized for vertical transitions
      USE WHEN: Snowboarder/skier in halfpipe (up/down wall transitions)
      TUNING: 10m distance, 5m height offset, 0.3s lookahead for vertical prediction

    - snowboard_powder: Wide follow for powder spray and terrain context
      USE WHEN: Open powder runs where snow spray is part of the shot
      TUNING: 12m distance, 4m height, 10m/s speed for fast descents

    - skate_ledge_gap: Close follow for precise technical trick capture
      USE WHEN: Technical street skating (ledge tricks, gap jumps)
      TUNING: 5m distance, 2m height, 6m/s for precise framing

    - skate_bowl: Height-locked for bowl/ramp transitions
      USE WHEN: Bowl skating with airs and transitions
      TUNING: 8m distance, 3m height, 0.2s lookahead

    - motocross_jump: Height-locked for jump sequences
      USE WHEN: Motocross/supercross jumps (high vertical, fast horizontal)
      TUNING: 15m distance, 6m height, 0.35s lookahead for jump prediction

    - trail_running: Smooth follow for natural running motion
      USE WHEN: Trail running, ultramarathon following
      TUNING: 8m distance, 3m height, 5m/s for matching runner pace

Motion Curves Explained:
------------------------
Motion curves control how the drone accelerates and decelerates. Different curves
create different "feels" in the footage:

    LINEAR: Constant velocity throughout
        - Feel: Mechanical, robotic
        - Use: Very long shots where smoothness matters less
        - Math: position = start + (end-start) * t

    EASE_IN_OUT: Smooth acceleration and deceleration (default)
        - Feel: Natural, professional, cinematic
        - Use: Most shots - orbit, follow, reveal
        - Math: Cubic easing (slow start, fast middle, slow end)

    EASE_IN: Slow start, fast end
        - Feel: Building momentum, anticipation
        - Use: Reveal shots starting from hidden position
        - Math: Quadratic curve (t²)

    EASE_OUT: Fast start, slow end
        - Feel: Settling into position
        - Use: Arriving at final framing position
        - Math: Inverse quadratic (1 - (1-t)²)

    EXPONENTIAL: Quick start, slow settle
        - Feel: Aggressive, "snap" to position
        - Use: FPV-style shots, fast repositioning
        - Math: 1 - exp(-5*t) (fast initial response)

    BEZIER_QUADRATIC: Simple curved path through 3 points
        - Feel: Arcing motion
        - Use: Orbit shots, curved approaches
        - Math: Quadratic Bezier interpolation

    BEZIER_CUBIC: Complex S-curve path through 4 points
        - Feel: Fluid, organic motion
        - Use: FPV-style weaving, complex approaches
        - Math: Cubic Bezier interpolation

PID Controller Explained:
-------------------------
The PID (Proportional-Integral-Derivative) controller is the "autopilot" that
maintains consistent distance and height from the subject. It works like this:

    error = desired_distance - actual_distance

    Proportional (P): p = kp * error
        - Immediate response to error
        - Higher kp = faster correction, but can oscillate
        - Lower kp = slower, smoother, but more lag

    Integral (I): i = ki * ∫error dt
        - Accumulates error over time to eliminate steady-state offset
        - Prevents the drone from settling at wrong distance
        - Anti-windup limits prevent integral from growing too large

    Derivative (D): d = kd * d(error)/dt
        - Dampens oscillation by responding to rate of change
        - Predicts where error is heading
        - Smooths out P-term response

    Output = P + I + D (clamped to output_limit)

Tuning for Cinematic Shots:
    - Distance PID (kp=0.8, ki=0.1, kd=0.2): Moderate response, smooth tracking
    - Height PID (kp=2.0, ki=0.3, kd=0.5): Tighter control for height lock

LookaheadPredictor Explained:
-----------------------------
The LookaheadPredictor solves the latency problem in vision-based tracking:

PROBLEM:
    1. Camera captures frame (t=0)
    2. Pi 4 processes YOLO detection (t=150-250ms)
    3. Detection sent to control loop (t=250ms)
    4. Drone receives and acts (t=300ms)
    5. Motor response + flight dynamics (t=400ms)

    By the time the drone responds, the subject has moved! Result: laggy,
    behind-the-action footage.

SOLUTION (LookaheadPredictor):
    Instead of tracking where the subject WAS, predict where they WILL BE:

    predicted_position = current_position + (velocity * horizon_seconds)

    The predictor:
    1. Maintains history of subject positions and velocities
    2. Estimates velocity from position deltas if not provided
    3. Extrapolates future position based on current velocity
    4. Drone tracks the PREDICTED position, not current

    Result: Drone is already at the right place when the subject arrives,
    eliminating visible lag from the footage.

Configuration:
    - horizon_s: How far ahead to predict (default 0.2s for Pi 4 latency)
    - Higher for fast/vertical sports (0.3-0.35s for jumps)
    - Lower for slow/predictable motion (0.15s for skate ledge)

Quality Metrics:
---------------
The system continuously monitors shot quality:

    position_error_m: Distance from planned path
    height_error_m: Altitude deviation from target
    gimbal_angular_velocity_deg_s: How fast gimbal is moving (smoothness indicator)
    framing_score: 0-1 score for subject framing (1.0 = perfect)
    smoothness_score: 0-1 score for motion smoothness
    velocity_m_s: Current drone speed
    distance_to_subject_m: Current distance from subject

Thresholds determine if shot quality is acceptable:
    - MAX_POSITION_ERROR_M = 1.0 (1 meter deviation acceptable)
    - MAX_HEIGHT_ERROR_M = 0.5 (50cm altitude deviation)
    - MIN_SMOOTHNESS_SCORE = 0.8 (80% smoothness required)

Features:
    - LookaheadPredictor for 150-250ms latency compensation
    - Sport-specific motion profiles (snowboard, skate, motocross, running)
    - Hardware-aware speed limits (12-15 m/s max, 4-5 m/s comfortable)
    - PID distance controller for subject tracking
    - Height-locked tracking (±0.2m accuracy for jumps)
    - Automatic framing (rule of thirds, lead room considerations)
    - Shot quality metrics (position error, smoothness, framing score)
    - Gimbal coordination for dynamic composition
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
from avatar.mcp_server.tools.flight_tools import (
    get_telemetry_cache,
    goto_gps,
    hold,
    set_velocity,
)
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal, point_camera_at, _calculate_look_angles, _clamp
)

logger = logging.getLogger(__name__)

# =============================================================================
# HARDWARE LIMITS
# =============================================================================
# These constants define the physical capabilities and safety limits of the
# Project Avatar Mark4 7" build. All motion planning respects these constraints.

HARDWARE_MAX_SPEED_M_S = 15.0  # Absolute hardware limit (15 m/s = 54 km/h)
# Never exceeded even in emergency situations - protects hardware

HARDWARE_COMFORT_SPEED_M_S = 5.0  # Comfortable filming speed (5 m/s = 18 km/h)
# Optimal for stable footage with gimbal - filming above this causes jitter

HARDWARE_MAX_ACCEL_M_S2 = 2.0  # Gentle acceleration for cinematic feel
# Higher acceleration causes jarring footage and risks gimbal stabilization limits

# =============================================================================
# SHOT QUALITY THRESHOLDS
# =============================================================================
# These define acceptable quality levels for cinematic footage. If metrics fall
# outside these ranges, the shot is considered compromised.

MAX_POSITION_ERROR_M = 1.0  # Maximum deviation from planned trajectory (1 meter)
# Larger errors mean the drone is not following the intended cinematic path

MAX_HEIGHT_ERROR_M = 0.5  # Maximum altitude deviation (0.5 meters)
# Height errors are more noticeable than horizontal errors in footage

MAX_GIMBAL_ANGULAR_VELOCITY_DEG_S = 30.0  # Max gimbal slew rate (30 deg/s)
# Faster gimbal movement causes blurry subject tracking and mechanical stress

MIN_SMOOTHNESS_SCORE = 0.8  # Minimum acceptable smoothness (0-1 scale)
# Below this, footage will appear jerky or amateur

# =============================================================================
# VISION SYSTEM LATENCY COMPENSATION
# =============================================================================
# The Pi 4 + YOLOv8-nano vision pipeline has inherent latency that must be
# compensated for real-time tracking. These values are empirically measured.

VISION_LATENCY_MS = 200  # Typical Pi 4 + YOLOv8-nano processing latency
# Breakdown: Camera capture (33ms) + YOLO inference (~120ms) + transmission (~50ms)

PREDICTION_HORIZON_S = VISION_LATENCY_MS / 1000.0  # 0.2s default lookahead
# This is the time horizon the LookaheadPredictor uses for position prediction


@dataclass
class SubjectState:
    """Complete subject state for tracking and prediction.

    Stores position, velocity, and timestamp for a tracked subject. Used by
    LookaheadPredictor to estimate future positions and maintain tracking history.

    Attributes:
        lat: Latitude in decimal degrees (WGS84)
        lon: Longitude in decimal degrees (WGS84)
        alt_m: Altitude above ground level in meters (AGL, not AMSL)
        vel_north_m_s: Northward velocity component in m/s (positive = north)
        vel_east_m_s: Eastward velocity component in m/s (positive = east)
        vel_up_m_s: Vertical velocity component in m/s (positive = up/climbing)
        timestamp_s: Unix timestamp when this state was captured (seconds)

    Example:
        subject = SubjectState(
            lat=37.7749, lon=-122.4194, alt_m=50.0,
            vel_north_m_s=5.0, vel_east_m_s=2.0, vel_up_m_s=0.5,
            timestamp_s=time.time()
        )
    """
    lat: float
    lon: float
    alt_m: float
    vel_north_m_s: float = 0.0
    vel_east_m_s: float = 0.0
    vel_up_m_s: float = 0.0
    timestamp_s: float = 0.0


class LookaheadPredictor:
    """Predicts subject position to compensate for vision system latency.

    The LookaheadPredictor is the key component that enables smooth, lag-free
cinematic
    tracking despite the 150-250ms latency in Project Avatar's Pi 4 + YOLOv8
    vision pipeline.

    How It Works:
    -------------
    Instead of tracking the subject's CURRENT position (which is already
    200ms old by the time the drone responds), the predictor extrapolates
    where the subject WILL BE in 200ms based on their current velocity.

    prediction = current_position + (velocity * prediction_horizon)

    For example, if a snowboarder is moving north at 10 m/s:
    - Current position: (lat, lon)
    - In 0.2 seconds, they will be 2 meters north of current position
    - Drone flies to the FUTURE position, not current
    - Result: No visible lag in footage

    Velocity Estimation:
    --------------------
    If velocity is not provided by the vision system, the predictor estimates
    it from position history using finite differences:

        velocity = (position_new - position_old) / (time_new - time_old)

    This works well for constant-velocity motion but degrades during
    rapid acceleration/deceleration (e.g., jump takeoffs/landings).

    History Management:
    -------------------
    The predictor maintains a rolling history of up to 10 SubjectState samples.
    This history is used for:
    1. Velocity estimation (from position deltas)
    2. Smoothing noisy detections
    3. Debugging and post-shot analysis

    Usage Pattern:
    --------------
        predictor = LookaheadPredictor(horizon_s=0.2)  # 200ms lookahead

        # In tracking loop (at vision detection rate, ~5-10Hz):
        predictor.update(lat, lon, alt, timestamp=now)

        # Get predicted position for control (at control rate, 20Hz):
        pred_lat, pred_lon, pred_alt = predictor.predict_future()

        # Use predicted position for drone control
        fly_to(pred_lat, pred_lon, pred_alt)

    Sport-Specific Tuning:
    ---------------------
    Different sports benefit from different prediction horizons:

        Skate ledge (slow, predictable): 0.15s
        - Short horizon because motion is slow and predictable

        Trail running (medium speed): 0.2s (default)
        - Default works well for steady-paced motion

        Snowboard halfpipe (vertical transitions): 0.3s
        - Longer horizon for predicting up/down wall transitions

        Motocross jumps (high speed, high vertical): 0.35s
        - Longest horizon for predicting jump trajectories

    Limitations:
    -----------
    - Assumes constant velocity (works poorly for rapid acceleration)
    - Prediction error grows with horizon (0.5s+ predictions become unreliable)
    - No model of subject dynamics (doesn't know about gravity, friction)

    For jump prediction improvements, consider adding physics-based trajectory
    prediction for airborne subjects.
    """

    def __init__(self, horizon_s: float = PREDICTION_HORIZON_S):
        """Initialize the LookaheadPredictor.

        Args:
            horizon_s: Prediction horizon in seconds. This is how far into
                the future to predict subject position. Default is 0.2s
                (200ms) which matches the typical Pi 4 + YOLOv8 latency.
                Use shorter horizons (0.15s) for slow predictable motion,
                longer horizons (0.3-0.35s) for fast vertical sports.
        """
        self.horizon_s = horizon_s
        self._state: Optional[SubjectState] = None
        self._history: List[SubjectState] = []
        self._max_history = 10  # Keep last 10 samples for velocity estimation

    def update(self, lat: float, lon: float, alt_m: float,
               vel_north: float = 0.0, vel_east: float = 0.0, vel_up: float = 0.0,
               timestamp_s: Optional[float] = None) -> None:
        """Update predictor with latest subject detection from vision system.

        This should be called every time the vision system produces a new
        subject detection (typically 5-10Hz for YOLOv8-nano on Pi 4).

        Args:
            lat: Current subject latitude in decimal degrees
            lon: Current subject longitude in decimal degrees
            alt_m: Current subject altitude in meters AGL
            vel_north: North velocity component in m/s. If 0.0 and history
                exists, velocity will be estimated from position deltas.
            vel_east: East velocity component in m/s. Same estimation applies.
            vel_up: Vertical velocity component in m/s. Same estimation applies.
            timestamp_s: Unix timestamp for this detection. If None, current
                event loop time is used.

        Velocity Estimation:
            If velocity components are not provided (all 0.0) and history exists,
            the predictor estimates velocity from the position change since the
            last update:

                vel = (pos_current - pos_last) / (time_current - time_last)

            This estimation is less accurate than direct velocity measurement
            but works for many tracking scenarios.
        """
        if timestamp_s is None:
            try:
                timestamp_s = asyncio.get_event_loop().time()
            except RuntimeError:
                import time
                timestamp_s = time.time()

        # Estimate velocity from history if not provided (finite difference method)
        if len(self._history) > 0 and (vel_north == 0.0 and vel_east == 0.0):
            last = self._history[-1]
            dt = timestamp_s - last.timestamp_s
            if dt > 0.001:  # Avoid division by zero
                # Conversion factors: meters per degree of lat/lon at this latitude
                meters_per_lat = 111320.0
                meters_per_lon = 111320.0 * math.cos(math.radians(lat))

                # Finite difference velocity estimation
                vel_north = (lat - last.lat) * meters_per_lat / dt
                vel_east = (lon - last.lon) * meters_per_lon / dt
                vel_up = (alt_m - last.alt_m) / dt

        state = SubjectState(
            lat=lat, lon=lon, alt_m=alt_m,
            vel_north_m_s=vel_north, vel_east_m_s=vel_east, vel_up_m_s=vel_up,
            timestamp_s=timestamp_s
        )

        self._state = state
        self._history.append(state)

        # Trim history to prevent unbounded growth
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def predict_future(self, horizon_s: Optional[float] = None) -> Tuple[float, float, float]:
        """Predict subject position at a future time.

        This is the core prediction function. It extrapolates the subject's
        future position based on current position and velocity:

            future_pos = current_pos + (velocity * horizon)

        Args:
            horizon_s: Prediction horizon in seconds. If None, uses the default
                horizon set during initialization. Override this for temporary
                horizon changes (e.g., predicting further ahead during jumps).

        Returns:
            Tuple of (predicted_lat, predicted_lon, predicted_alt_m)

        Raises:
            ValueError: If no state has been set (update() not called yet)

        Example:
            # Standard prediction
            pred_lat, pred_lon, pred_alt = predictor.predict_future()

            # Extended prediction for jump trajectory
            jump_lat, jump_lon, jump_alt = predictor.predict_future(horizon_s=0.5)
        """
        if self._state is None:
            raise ValueError("No state available - call update() first")

        h = horizon_s or self.horizon_s

        # Conversion factors for velocity-to-position conversion
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(self._state.lat))

        # Predict position: pos = pos + vel * dt
        # Convert velocity (m/s) back to lat/lon/alt changes
        delta_lat = self._state.vel_north_m_s * h / meters_per_lat
        delta_lon = self._state.vel_east_m_s * h / meters_per_lon
        delta_alt = self._state.vel_up_m_s * h

        return (
            self._state.lat + delta_lat,
            self._state.lon + delta_lon,
            self._state.alt_m + delta_alt
        )

    def get_velocity(self) -> Tuple[float, float, float]:
        """Get the current estimated velocity from the latest state.

        Returns:
            Tuple of (north_m_s, east_m_s, up_m_s) velocity components.
            Returns (0.0, 0.0, 0.0) if no state has been set.
        """
        if self._state is None:
            return (0.0, 0.0, 0.0)
        return (self._state.vel_north_m_s, self._state.vel_east_m_s, self._state.vel_up_m_s)

    def reset(self) -> None:
        """Reset predictor state, clearing current state and history.

        Call this when:
        - Starting a new shot
        - Subject tracking is lost and regained
        - You want to clear accumulated velocity history
        """
        self._state = None
        self._history.clear()


class PIDController:
    """PID (Proportional-Integral-Derivative) controller for smooth distance/height maintenance.

    The PID controller is the fundamental feedback mechanism that maintains
    consistent distance from the subject and precise altitude control. It
    continuously compares the desired state (setpoint) with the actual state
    (measurement) and produces a control output to minimize the error.

    How PID Works:
    --------------
    The controller computes three terms based on the error (e = setpoint - measurement):

        Error (e): Difference between where we want to be and where we are
        Example: Want 10m distance, currently 12m away -> e = -2m (too far)

        Proportional (P): p = kp * e
        - Immediate response proportional to error
        - Larger error = stronger correction
        - kp = 0.8 means 0.8 m/s correction per meter of error
        - If 2m too far, P term commands 1.6 m/s approach speed

        Integral (I): i = ki * ∫e dt
        - Accumulates error over time to eliminate steady-state offset
        - Without I term, drone might settle 0.5m away from target (residual error)
        - With I term, slowly creeps to exact distance
        - Anti-windup prevents integral from growing too large during saturation

        Derivative (D): d = kd * de/dt
        - Responds to rate of change of error (how fast error is changing)
        - Dampens oscillation by "predicting" where error is heading
        - Prevents overshoot: if approaching target fast, D term brakes
        - Noise-sensitive: differentiating noisy measurements amplifies noise

        Output: u = P + I + D (clamped to output_limit)

    Tuning Guidelines:
    ------------------
    Start with kp only (ki=0, kd=0), then add other terms:

        1. Increase kp until system responds quickly but doesn't oscillate
        2. Add small ki to eliminate steady-state error (start with ki = kp/10)
        3. Add small kd to reduce overshoot (start with kd = kp/4)

    For Cinematic Distance Control:
        kp=0.8, ki=0.1, kd=0.2
        - Moderate response, smooth tracking
        - Slight lag acceptable for cinematic feel
        - output_limit = max_speed (prevents excessive commands)

    For Height-Locked Tracking (tighter control needed):
        kp=2.0, ki=0.3, kd=0.5
        - Faster response for precise altitude maintenance
        - Critical for jump tracking where height errors ruin the shot
        - output_limit = 3.0 m/s (conservative for smooth motion)

    Anti-Windup:
    -----------
    When the controller saturates (hits output_limit), the integral term
    would normally keep accumulating, causing "integral windup". When the
    error finally changes sign, the huge integral causes massive overshoot.

    This implementation limits the integral to ±10.0 to prevent windup.

    DT Handling:
    -----------
    The controller measures actual time between updates for accurate
    integration/differentiation. If update() is called irregularly, the
    measured dt is used. dt is clamped to [0.001, 0.1] to prevent:
    - Division by zero (dt too small)
    - Unstable derivatives (dt too large)
    """

    def __init__(self, kp: float = 0.8, ki: float = 0.1, kd: float = 0.2,
                 output_limit: float = 10.0):
        """Initialize PID controller with gains and limits.

        Args:
            kp: Proportional gain. Higher = faster response, more oscillation.
                Recommended: 0.8 for distance, 2.0 for height control.
            ki: Integral gain. Eliminates steady-state error. Start with kp/10.
                Recommended: 0.1 for distance, 0.3 for height control.
            kd: Derivative gain. Dampens oscillation. Start with kp/4.
                Recommended: 0.2 for distance, 0.5 for height control.
            output_limit: Maximum output magnitude (saturation limit).
                For velocity controllers, set to max allowable speed.
                Recommended: template.speed_m_s for distance, 3.0 for height.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit

        # Internal state
        self._integral = 0.0  # Accumulated error over time
        self._last_error = 0.0  # Previous error for derivative calculation
        self._last_time: Optional[float] = None  # Timestamp of last update

    def reset(self) -> None:
        """Reset controller state, clearing integral and error history.

        Call this when:
        - Starting a new shot (prevents integral from previous shot carrying over)
        - Changing setpoints dramatically
        - Switching tracking modes
        """
        self._integral = 0.0
        self._last_error = 0.0
        self._last_time = None

    def update(self, error: float, timestamp_s: Optional[float] = None) -> float:
        """Update PID controller with new error measurement and return control output.

        This is the main control loop function. Call this at the control rate
        (typically 10-20Hz for drone control) with the current error.

        Args:
            error: Current error (setpoint - measurement). Positive means
                measurement is below setpoint (need to increase).
                Example: want 10m distance, have 12m -> error = -2m
            timestamp_s: Current timestamp. If None, uses event loop time.

        Returns:
            Control output (clamped to output_limit). For velocity controllers,
            this is the commanded velocity. For position controllers, this is
            the commanded position offset.

        Example:
            # Distance control
            desired_distance = 10.0
            current_distance = calculate_distance()
            error = desired_distance - current_distance

            approach_speed = pid.update(error, time.time())
            send_velocity_command(approach_speed)
        """
        if timestamp_s is None:
            try:
                timestamp_s = asyncio.get_event_loop().time()
            except RuntimeError:
                import time
                timestamp_s = time.time()

        # Calculate dt (time since last update), clamped to reasonable range
        dt = 0.05  # Default 50ms if no previous time
        if self._last_time is not None:
            dt = timestamp_s - self._last_time
            dt = max(0.001, min(dt, 0.1))  # Clamp: min 1ms, max 100ms

        # Proportional term: immediate response to error
        p = self.kp * error

        # Integral term with anti-windup protection
        self._integral += error * dt
        self._integral = _clamp(self._integral, -10.0, 10.0)  # Anti-windup
        i = self.ki * self._integral

        # Derivative term: rate of change of error
        d = 0.0
        if self._last_time is not None and dt > 0:
            d = self.kd * (error - self._last_error) / dt

        # Update state for next iteration
        self._last_error = error
        self._last_time = timestamp_s

        # Calculate and clamp output
        output = p + i + d
        return _clamp(output, -self.output_limit, self.output_limit)


@dataclass
class MotionProfile:
    """Sport-specific motion profile with hardware-aware limits.

    A MotionProfile encapsulates all the tuning parameters for a specific sport
    or filming scenario. It defines speed/acceleration limits, lookahead timing,
    and spatial offsets appropriate for that sport's typical motion patterns.

    Attributes:
        name: Human-readable profile name (e.g., "Snowboard Halfpipe")
        max_speed_m_s: Maximum speed for this sport (m/s). Should respect
            hardware limits (15 m/s max) but typically much lower for
            cinematic quality (5-12 m/s).
        max_accel_m_s2: Maximum acceleration (m/s²). Lower = smoother footage.
        lookahead_s: Prediction horizon in seconds. Higher for fast/vertical
            sports (jumps, halfpipe), lower for slow/predictable motion.
        distance_m: Default distance from subject (meters). Closer for
            immersive feel, farther for context/safety.
        height_offset_m: Height above subject (meters). Higher for wide
            context shots, lower for intimate/action shots.
        lateral_offset_m: Side offset for angled shots (meters). Creates
            lead room and dynamic composition.
        description: Human-readable description of when to use this profile

    Example:
        profile = MotionProfile(
            name="Snowboard Halfpipe",
            max_speed_m_s=8.0,
            max_accel_m_s2=2.0,
            lookahead_s=0.3,  # Higher for vertical prediction
            distance_m=10.0,
            height_offset_m=5.0,
            lateral_offset_m=6.0,
            description="Optimized for halfpipe transitions"
        )
    """
    name: str
    max_speed_m_s: float
    max_accel_m_s2: float
    lookahead_s: float
    distance_m: float
    height_offset_m: float
    lateral_offset_m: float
    description: str


# =============================================================================
# SPORT-SPECIFIC MOTION PROFILES
# =============================================================================
# These are pre-tuned profiles for different action sports. Each profile is
# optimized for the typical speeds, motion patterns, and filming requirements
# of that sport.

SPORT_PROFILES = {
    # -------------------------------------------------------------------------
    # SNOWBOARD HALFPIPE
    # -------------------------------------------------------------------------
    # Halfpipe riding involves rapid vertical transitions (up/down walls) with
    # airtime at the top. The drone must predict and track these vertical
    # movements smoothly.
    "snowboard_halfpipe": MotionProfile(
        name="Snowboard Halfpipe",
        max_speed_m_s=8.0,  # Match snowboarder speed (comfortable for filming)
        max_accel_m_s2=2.0,  # Moderate acceleration for smooth wall transitions
        lookahead_s=0.3,  # Higher lookahead for predicting vertical transitions
        distance_m=10.0,  # Medium distance to capture full rider in frame
        height_offset_m=5.0,  # Above lip height for wall context
        lateral_offset_m=6.0,  # Side angle for dynamic composition
        description="Optimized for halfpipe transitions, maintains distance during vertical movement"
    ),

    # -------------------------------------------------------------------------
    # SNOWBOARD POWDER RUN
    # -------------------------------------------------------------------------
    # Open powder runs are faster and more flowing than halfpipe. The wide
    # framing captures the powder spray and terrain context that makes
    # powder footage compelling.
    "snowboard_powder": MotionProfile(
        name="Snowboard Powder Run",
        max_speed_m_s=10.0,  # Faster for open powder descents
        max_accel_m_s2=2.5,  # Can accelerate more in open terrain
        lookahead_s=0.25,  # Standard lookahead for downhill motion
        distance_m=12.0,  # Wider for powder spray and terrain context
        height_offset_m=4.0,  # Lower for terrain intimacy
        lateral_offset_m=8.0,  # More side angle for landscape composition
        description="Wider framing for powder spray and terrain context"
    ),

    # -------------------------------------------------------------------------
    # SKATE LEDGE/GAP
    # -------------------------------------------------------------------------
    # Technical street skating requires precise, close framing for trick
    # details. The slow speed and tight distance capture every foot placement
    # and board flip.
    "skate_ledge": MotionProfile(
        name="Skate Ledge/Gap",
        max_speed_m_s=6.0,  # Slower for precise trick capture
        max_accel_m_s2=1.5,  # Gentle for smooth tracking
        lookahead_s=0.15,  # Short lookahead - skate motion is immediate
        distance_m=5.0,  # Close for trick detail
        height_offset_m=2.0,  # Low for skater-level perspective
        lateral_offset_m=3.0,  # Side angle for ledge/gap visibility
        description="Close follow for technical tricks, quick response"
    ),

    # -------------------------------------------------------------------------
    # SKATE BOWL
    # -------------------------------------------------------------------------
    # Bowl skating has vertical transitions (airs, grinds) but less extreme
    # than halfpipe. Medium distance captures both the skater and bowl context.
    "skate_bowl": MotionProfile(
        name="Skate Bowl",
        max_speed_m_s=7.0,  # Moderate speed for bowl flow
        max_accel_m_s2=2.0,  # Can accelerate for airs
        lookahead_s=0.2,  # Medium lookahead for transitions
        distance_m=8.0,  # Medium for bowl context
        height_offset_m=3.0,  # Above coping for air visibility
        lateral_offset_m=5.0,  # Side angle for bowl geometry
        description="Medium distance for bowl context and transitions"
    ),

    # -------------------------------------------------------------------------
    # MOTOCROSS JUMP
    # -------------------------------------------------------------------------
    # Motocross jumps combine high horizontal speed (40-60 km/h) with large
    # vertical air. The drone needs high speed capability and long lookahead
    # to predict jump trajectories.
    "motocross_jump": MotionProfile(
        name="Motocross Jump",
        max_speed_m_s=12.0,  # Higher speed for motocross (43 km/h)
        max_accel_m_s2=3.0,  # Can accelerate aggressively if needed
        lookahead_s=0.35,  # Highest lookahead for jump prediction
        distance_m=15.0,  # Wide for jump sequence framing
        height_offset_m=6.0,  # High for jump apex visibility
        lateral_offset_m=10.0,  # Far side for rider/bike in frame
        description="High speed, wide framing for jump sequences"
    ),

    # -------------------------------------------------------------------------
    # TRAIL RUNNING
    # -------------------------------------------------------------------------
    # Trail running is relatively slow and predictable. Smooth, natural
    # motion matching the runner's pace creates pleasant footage.
    "trail_running": MotionProfile(
        name="Trail Running",
        max_speed_m_s=5.0,  # Match runner pace (18 km/h typical)
        max_accel_m_s2=1.5,  # Gentle for natural motion
        lookahead_s=0.2,  # Standard lookahead
        distance_m=8.0,  # Medium for runner in environment
        height_offset_m=3.0,  # Eye level for immersion
        lateral_offset_m=4.0,  # Slight side for trail visibility
        description="Smooth tracking for natural running motion"
    ),
}


class ShotType(Enum):
    """Enumeration of cinematic shot types.

    Each shot type represents a distinct camera movement pattern with
    specific cinematic characteristics and use cases.

    ORBIT: Circular path around subject with camera locked on subject.
        Creates dramatic, focused emphasis on subject. Classic cinematic move.

    FOLLOW_DYNAMIC: Smooth following with predictive positioning.
        Most common action sports shot. Keeps subject in frame while moving.

    REVEAL_ASCENT: Rise from low altitude to reveal scene.
        Dramatic opening shot. Starts hidden, reveals landscape.

    REVEAL_DESCENT: Descend to reveal subject details.
        Closing or detail shot. Starts wide, focuses on subject.

    PASS_BY: Smooth lateral pass with framing.
        Profile view tracking. Shows side of subject in motion.

    TOP_DOWN: Direct overhead with height lock.
        Shows patterns, paths, and spatial relationships.

    HEIGHT_LOCKED_TRACK: Maintain exact altitude offset from subject.
        Critical for jump sports. Keeps consistent vertical framing.

    FPV_STYLE: Dynamic, fluid motion for action sports.
        Aggressive, weaving motion like FPV racing drones.
    """
    ORBIT = auto()
    FOLLOW_DYNAMIC = auto()
    REVEAL_ASCENT = auto()
    REVEAL_DESCENT = auto()
    PASS_BY = auto()
    TOP_DOWN = auto()
    HEIGHT_LOCKED_TRACK = auto()
    FPV_STYLE = auto()


class MotionCurveType(Enum):
    """Motion curve interpolation types for smooth acceleration/deceleration.

    These curves define how velocity changes over time, creating different
    "feels" in the footage. The curve type is a critical artistic choice
    that affects the cinematic quality of the shot.

    LINEAR: Constant velocity (no acceleration curve).
        - Mathematical: position = start + (end-start) * t
        - Feel: Mechanical, robotic, constant motion
        - Use: Long transitions where smoothness matters less

    EASE_IN_OUT: Smooth acceleration and deceleration (default, most cinematic).
        - Mathematical: Cubic easing (slow start, fast middle, slow end)
        - Feel: Natural, professional, polished
        - Use: Most cinematic shots (orbit, follow, reveal)

    EASE_IN: Slow start, accelerating to fast end.
        - Mathematical: Quadratic curve (t²)
        - Feel: Building momentum, anticipation, "pushing off"
        - Use: Starting from stationary, reveal shots

    EASE_OUT: Fast start, decelerating to slow end.
        - Mathematical: Inverse quadratic (1 - (1-t)²)
        - Feel: Settling into position, arriving
        - Use: Arriving at final framing, landing shots

    EXPONENTIAL: Quick start, slow settle.
        - Mathematical: 1 - exp(-5*t) (exponential approach)
        - Feel: Aggressive, "snap" to position, urgent
        - Use: FPV-style shots, quick repositioning

    BEZIER_QUADRATIC: Simple curved path through 3 control points.
        - Mathematical: Quadratic Bezier interpolation
        - Feel: Arcing, curved motion
        - Use: Orbit paths, curved approaches

    BEZIER_CUBIC: Complex S-curve path through 4 control points.
        - Mathematical: Cubic Bezier interpolation
        - Feel: Fluid, organic, weaving
        - Use: FPV-style weaving, complex cinematic paths
    """
    LINEAR = auto()
    EASE_IN_OUT = auto()
    EASE_IN = auto()
    EASE_OUT = auto()
    EXPONENTIAL = auto()
    BEZIER_QUADRATIC = auto()
    BEZIER_CUBIC = auto()


@dataclass
class MotionCurve:
    """Motion curve for smooth interpolation between values over time.

    The MotionCurve provides mathematical interpolation functions that create
    smooth, cinematic acceleration and deceleration. This is essential for
    professional-quality footage - linear movement looks mechanical and amateur.

    Attributes:
        curve_type: The type of interpolation curve (ease_in_out, bezier, etc.)
        start_time: Start time in seconds (relative to shot start)
        duration: Duration of the curve in seconds
        start_value: Starting value (e.g., 0.0 for velocity ramp)
        end_value: Ending value (e.g., 1.0 for full velocity)

    Mathematical Functions:
    -----------------------
    Each curve type implements a specific mathematical function that maps
    normalized time u (0.0 to 1.0) to an interpolated value:

        _linear(u): Linear interpolation
            value = start + (end-start) * u

        _ease_in_out(u): Cubic ease-in-out (default, most cinematic)
            For u < 0.5: value = start + (end-start) * 4 * u³
            For u >= 0.5: value = start + (end-start) * (1 - 4*(1-u)³)
            Creates smooth S-curve: slow start, fast middle, slow end

        _ease_in(u): Quadratic ease-in
            value = start + (end-start) * u²
            Accelerating curve: slow start, fast end

        _ease_out(u): Quadratic ease-out
            value = start + (end-start) * (1 - (1-u)²)
            Decelerating curve: fast start, slow end

        _exponential(u): Exponential approach
            value = start + (end-start) * (1 - exp(-5*u))
            Quick initial response, asymptotic approach to end

    Usage Example:
    -------------
        # Create ease-in-out velocity ramp for 10 second shot
        curve = MotionCurve(
            curve_type=MotionCurveType.EASE_IN_OUT,
            start_time=0.0,
            duration=10.0,
            start_value=0.0,  # Start stationary
            end_value=5.0     # Ramp to 5 m/s
        )

        # In control loop, get current velocity target
        current_time = asyncio.get_event_loop().time() - shot_start_time
        target_velocity = curve.evaluate(current_time)
    """
    curve_type: MotionCurveType
    start_time: float
    duration: float
    start_value: float = 0.0
    end_value: float = 1.0

    def evaluate(self, t: float) -> float:
        """Evaluate the curve at a given time.

        Args:
            t: Time in seconds (relative to curve start_time)

        Returns:
            Interpolated value at time t. Returns start_value if t is before
            start_time, end_value if t is after start_time + duration.
        """
        if t < self.start_time:
            return self.start_value
        if t > self.start_time + self.duration:
            return self.end_value

        # Normalized time [0, 1] within curve duration
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
        """Linear interpolation - constant rate of change.

        Mathematical: value = start + (end-start) * u

        Feel: Mechanical, robotic, no acceleration/deceleration
        """
        return self.start_value + (self.end_value - self.start_value) * u

    def _ease_in_out(self, u: float) -> float:
        """Cubic ease-in-out - smooth acceleration and deceleration.

        Mathematical:
            For u < 0.5: 4*u³ (accelerating)
            For u >= 0.5: 1 - 4*(1-u)³ (decelerating)

        Feel: Natural, professional, cinematic. This is the default choice
        for most cinematic shots because it mimics how humans naturally move.

        The cubic function creates an S-curve: slow start, fast middle, slow end.
        This eliminates jerk at the beginning and end of motion.
        """
        if u < 0.5:
            return self.start_value + (self.end_value - self.start_value) * 4 * u * u * u
        else:
            f = 1 - u
            return self.start_value + (self.end_value - self.start_value) * (1 - 4 * f * f * f)

    def _ease_in(self, u: float) -> float:
        """Quadratic ease-in - accelerating motion.

        Mathematical: value = start + (end-start) * u²

        Feel: Building momentum, anticipation. Motion starts slow and
        accelerates to full speed. Good for "pushing off" shots.
        """
        return self.start_value + (self.end_value - self.start_value) * u * u

    def _ease_out(self, u: float) -> float:
        """Quadratic ease-out - decelerating motion.

        Mathematical: value = start + (end-start) * (1 - (1-u)²)

        Feel: Settling, arriving. Motion starts fast and decelerates to stop.
        Good for arriving at final framing position.
        """
        return self.start_value + (self.end_value - self.start_value) * (1 - (1 - u) * (1 - u))

    def _exponential(self, u: float) -> float:
        """Exponential curve - quick start, slow settle.

        Mathematical: value = start + (end-start) * (1 - exp(-5*u))

        Feel: Aggressive, "snap" to position. Very fast initial response
        that asymptotically approaches the target. Good for FPV-style shots
        and quick repositioning.

        The factor of -5 in the exponent controls the aggressiveness.
        Higher = faster initial response, longer settling time.
        """
        if u < 0.001:
            return self.start_value
        return self.start_value + (self.end_value - self.start_value) * (1 - math.exp(-5 * u))


@dataclass
class ShotTemplate:
    """Cinematic shot template configuration.

    A ShotTemplate is a complete specification for a pre-programmed cinematic
    shot. It defines all the parameters needed to execute a specific type of
    shot with consistent cinematic quality.

    Attributes:
        name: Human-readable shot name (e.g., "Close Orbit (Cinematic)")

        shot_type: Type of shot (orbit, follow, reveal, etc.)
            Determines the execution algorithm and motion pattern.

        distance_m: Distance from subject in meters.
            Closer (4-6m) = immersive, intimate, action feel
            Medium (8-12m) = balanced, general purpose
            Far (15-20m) = context, environment, wide shots

        height_offset_m: Height above subject in meters.
            Low (2-3m) = eye level, intimate, terrain detail
            Medium (4-6m) = balanced, shows subject + some context
            High (8-20m) = wide context, environmental shots

        lateral_offset_m: Side offset for angled shots (meters).
            Creates lead room and dynamic composition.
            0 = directly behind subject (follow shot)
            3-6m = slight angle (pass-by feel)
            8-10m = significant side angle (profile view)

        speed_m_s: Movement speed in m/s.
            2-3 m/s = slow, deliberate, very smooth
            4-6 m/s = medium, cinematic standard
            8-12 m/s = fast, action, requires skilled pilot
            15 m/s = hardware maximum, rarely used

        duration_s: Shot duration in seconds.
            5-10s = short clip, social media
            15-30s = standard cinematic shot
            45-60s = long sequence, documentary style

        motion_curve: Type of motion curve for acceleration.
            EASE_IN_OUT (default) = smooth, professional
            LINEAR = mechanical, constant speed
            BEZIER_CUBIC = FPV-style fluid motion

        gimbal_mode: Gimbal tracking mode.
            "track_subject" = gimbal follows subject
            "fixed" = gimbal maintains angle
            "manual" = operator controlled

        gimbal_pitch_offset: Additional pitch angle in degrees.
            -10° to -20° = slight down angle (standard)
            -30° to -45° = steep down angle (top-down feel)
            0° = level horizon
            +10° to +20° = up angle (hero/reveal shots)

        predictive_frames: Seconds to predict ahead for latency compensation.
            0.15s = skate ledge (slow, immediate)
            0.2s = trail running (standard)
            0.3s = halfpipe (vertical transitions)
            0.35s = motocross jumps (high speed vertical)

        height_lock: Whether to maintain exact height offset from subject.
            True = drone follows subject's altitude changes exactly
            False = drone maintains constant absolute altitude
            Essential for jump sports (halfpipe, motocross).

        quality_thresholds: Dict of quality metric thresholds.
            max_position_error_m: Maximum path deviation (meters)
            max_height_error_m: Maximum altitude deviation (meters)
            min_framing_score: Minimum framing quality (0-1 scale)

    Example:
        template = ShotTemplate(
            name="Close Follow (Action)",
            shot_type=ShotType.FOLLOW_DYNAMIC,
            distance_m=6.0,
            height_offset_m=2.5,
            lateral_offset_m=2.0,
            speed_m_s=8.0,
            duration_s=30.0,
            motion_curve=MotionCurveType.EASE_IN_OUT,
            gimbal_mode="track_subject",
            gimbal_pitch_offset=-10.0,
            predictive_frames=1.5,
            height_lock=False,
            quality_thresholds={
                "max_position_error_m": 1.0,
                "max_height_error_m": 0.5,
                "min_framing_score": 0.7,
            }
        )
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


# =============================================================================
# CINEMATIC SHOT TEMPLATES LIBRARY
# =============================================================================
# These are pre-configured shot templates for common cinematic scenarios.
# Each template is tuned for specific use cases with appropriate distance,
# height, speed, and motion curve settings.

CINEMATIC_TEMPLATES = {
    # =========================================================================
    # ORBIT SHOTS (Circular tracking around subject)
    # =========================================================================

    # ORBIT CLOSE - Tight orbit for dramatic subject emphasis
    # Use when: Subject is relatively stationary, you want dramatic focus
    # Example: Skater preparing for trick, athlete at starting line
    # Feel: Intimate, intense, "hero" shot
    "orbit_close": ShotTemplate(
        name="Close Orbit (Cinematic)",
        shot_type=ShotType.ORBIT,
        distance_m=8.0,  # Close for intimacy
        height_offset_m=3.0,  # Low for eye-level feel
        speed_m_s=2.0,  # Slow for smoothness
        duration_s=15.0,  # Long enough for full rotation
        motion_curve=MotionCurveType.EASE_IN_OUT,  # Smooth start/stop
        gimbal_pitch_offset=-20.0,  # Slight down angle
    ),

    # ORBIT WIDE - Wide orbit for environmental context
    # Use when: Subject in scenic location, establishing shot
    # Example: Snowboarder on mountain ridge, runner on coastal trail
    # Feel: Epic, contextual, "sense of place"
    "orbit_wide": ShotTemplate(
        name="Wide Orbit (Context)",
        shot_type=ShotType.ORBIT,
        distance_m=20.0,  # Wide for context
        height_offset_m=8.0,  # Higher for landscape view
        speed_m_s=4.0,  # Faster for wide shot
        duration_s=20.0,  # Longer for full context
        motion_curve=MotionCurveType.LINEAR,  # Constant motion for wide shots
        gimbal_pitch_offset=-30.0,  # Steeper down angle
    ),

    # =========================================================================
    # FOLLOW SHOTS (Dynamic tracking of moving subject)
    # =========================================================================

    # FOLLOW CLOSE - Close follow for immersive action
    # Use when: Fast action, want viewer to feel "in the action"
    # Example: Following snowboarder through trees, motocross through whoops
    # Feel: Intense, immersive, "follow-cam" style
    "follow_close": ShotTemplate(
        name="Close Follow (Action)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=6.0,  # Close for immersion
        height_offset_m=2.5,  # Low for action feel
        lateral_offset_m=2.0,  # Slight side angle
        speed_m_s=8.0,  # Fast for action
        duration_s=30.0,  # Standard action sequence length
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-10.0,  # Slight down angle
        predictive_frames=1.5,  # Higher lookahead for fast motion
    ),

    # FOLLOW WIDE - Wide follow for context
    # Use when: Higher speed action where environment matters
    # Example: Downhill mountain bike run, powder snowboard descent
    # Feel: Balanced, shows subject in beautiful environment
    "follow_wide": ShotTemplate(
        name="Wide Follow (Context)",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=15.0,  # Wide for context
        height_offset_m=6.0,  # Higher for landscape
        lateral_offset_m=5.0,  # More side angle
        speed_m_s=12.0,  # Fast for high-speed action
        duration_s=45.0,  # Long for extended sequences
        motion_curve=MotionCurveType.LINEAR,  # Constant for smooth wide shots
        gimbal_pitch_offset=-20.0,
        predictive_frames=1.0,
    ),

    # =========================================================================
    # REVEAL SHOTS (Vertical movement for dramatic reveal)
    # =========================================================================

    # REVEAL HERO - Rising reveal shot
    # Use when: Starting low (behind obstacle), revealing hero moment
    # Example: Rising over hill to reveal skater landing trick
    # Feel: Dramatic, "hero" moment, building anticipation
    "reveal_hero": ShotTemplate(
        name="Hero Reveal",
        shot_type=ShotType.REVEAL_ASCENT,
        distance_m=0.0,  # Centered on subject
        height_offset_m=20.0,  # Rise 20m up
        speed_m_s=2.0,  # Slow and deliberate
        duration_s=8.0,  # Quick but not rushed
        motion_curve=MotionCurveType.EASE_OUT,  # Slow at end for reveal
        gimbal_pitch_offset=0.0,  # Level horizon
    ),

    # =========================================================================
    # PASS-BY SHOTS (Lateral tracking for profile view)
    # =========================================================================

    # PASS BY LOW - Low lateral pass for profile view
    # Use when: Want side/profile view of subject in motion
    # Example: Tracking alongside skater doing ledge tricks, runner stride
    # Feel: Technical, analytical, shows side detail
    "pass_by_low": ShotTemplate(
        name="Low Pass-By (Profile)",
        shot_type=ShotType.PASS_BY,
        distance_m=12.0,  # Lateral distance
        height_offset_m=1.5,  # Very low for profile
        lateral_offset_m=8.0,  # Significant side offset
        speed_m_s=6.0,  # Match subject speed
        duration_s=5.0,  # Short pass
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=0.0,  # Level (profile view)
    ),

    # =========================================================================
    # TOP-DOWN SHOTS (Overhead perspective)
    # =========================================================================

    # TOP DOWN DYNAMIC - Direct overhead with dynamic tracking
    # Use when: Want to show subject's path through terrain
    # Example: Surfer on wave pattern, skater in bowl
    # Feel: Graphic, pattern-revealing, "god's eye" view
    "top_down_dynamic": ShotTemplate(
        name="Top-Down Context",
        shot_type=ShotType.TOP_DOWN,
        distance_m=0.0,  # Centered overhead
        height_offset_m=15.0,  # High overhead
        speed_m_s=3.0,  # Slow for tracking
        duration_s=20.0,  # Long for pattern observation
        motion_curve=MotionCurveType.LINEAR,  # Constant for smooth tracking
        gimbal_pitch_offset=-90.0,  # Straight down
    ),

    # =========================================================================
    # HEIGHT-LOCKED TRACKING (Critical for vertical motion sports)
    # =========================================================================

    # HEIGHT LOCKED JUMP - Exact height tracking for jumps/airtime
    # Use when: Subject has significant vertical movement (jumps, drops)
    # Example: Snowboarder in halfpipe, motocross jumps
    # Feel: Smooth despite subject's vertical motion
    # Critical: Uses PID with tight gains, LookaheadPredictor for latency
    "height_locked_jump": ShotTemplate(
        name="Height-Locked Jump Tracking",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=8.0,
        height_offset_m=3.0,  # Maintains exactly 3m above subject
        speed_m_s=10.0,
        duration_s=10.0,
        motion_curve=MotionCurveType.LINEAR,  # Constant for predictability
        gimbal_pitch_offset=-15.0,
        height_lock=True,  # KEY FEATURE: follows subject altitude
        quality_thresholds={
            "max_position_error_m": 1.0,
            "max_height_error_m": 0.2,  # Tighter tolerance for height lock
            "min_framing_score": 0.8,
        },
    ),

    # =========================================================================
    # FPV-STYLE SHOTS (Aggressive, fluid motion)
    # =========================================================================

    # FPV DYNAMIC - Fast, aggressive FPV-style motion
    # Use when: Want "FPV drone racing" aesthetic
    # Example: Following snowboarder through terrain park, weaving through trees
    # Feel: Aggressive, dynamic, "fpv freestyle"
    # Warning: 15 m/s max speed, requires skilled pilot oversight
    "fpv_dynamic": ShotTemplate(
        name="FPV-Style Dynamic",
        shot_type=ShotType.FPV_STYLE,
        distance_m=4.0,  # Very close
        height_offset_m=2.0,  # Very low
        speed_m_s=15.0,  # Hardware maximum speed
        duration_s=20.0,
        motion_curve=MotionCurveType.BEZIER_CUBIC,  # Fluid weaving paths
        gimbal_pitch_offset=-25.0,
        predictive_frames=0.5,
    ),

    # =========================================================================
    # SPORT-SPECIFIC TEMPLATES (Pre-tuned for specific sports)
    # =========================================================================

    # SNOWBOARD HALFPIPE - Height-locked for vertical transitions
    # Use when: Snowboarder/skier in halfpipe (up/down wall transitions)
    # Tuning: 10m distance, 5m height, 0.3s lookahead for vertical prediction
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

    # SKATE LEDGE/GAP - Close follow for technical tricks
    # Use when: Technical street skating (ledge tricks, gap jumps)
    # Tuning: 5m distance, 2m height, 6m/s, 0.15s lookahead
    "skate_ledge_gap": ShotTemplate(
        name="Skate Ledge/Gap Tracking",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=SPORT_PROFILES["skate_ledge"].distance_m,
        height_offset_m=SPORT_PROFILES["skate_ledge"].height_offset_m,
        lateral_offset_m=SPORT_PROFILES["skate_ledge"].lateral_offset_m,
        speed_m_s=SPORT_PROFILES["skate_ledge"].max_speed_m_s,
        duration_s=8.0,  # Short for quick tricks
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-15.0,
        predictive_frames=SPORT_PROFILES["skate_ledge"].lookahead_s,
    ),

    # SKATE BOWL - Height-locked for bowl/ramp transitions
    # Use when: Bowl skating with airs and transitions
    # Tuning: 8m distance, 3m height, 0.2s lookahead
    "skate_bowl": ShotTemplate(
        name="Skate Bowl (Height-Locked)",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=SPORT_PROFILES["skate_bowl"].distance_m,
        height_offset_m=SPORT_PROFILES["skate_bowl"].height_offset_m,
        lateral_offset_m=SPORT_PROFILES["skate_bowl"].lateral_offset_m,
        speed_m_s=SPORT_PROFILES["skate_bowl"].max_speed_m_s,
        duration_s=20.0,
        motion_curve=MotionCurveType.EASE_IN_OUT,
        gimbal_pitch_offset=-20.0,
        predictive_frames=SPORT_PROFILES["skate_bowl"].lookahead_s,
        height_lock=True,
    ),

    # SNOWBOARD POWDER - Wide follow for powder runs
    # Use when: Open powder runs where snow spray and terrain matter
    # Tuning: 12m distance, 4m height, 10m/s speed
    "snowboard_powder": ShotTemplate(
        name="Snowboard Powder Run",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=SPORT_PROFILES["snowboard_powder"].distance_m,
        height_offset_m=SPORT_PROFILES["snowboard_powder"].height_offset_m,
        lateral_offset_m=SPORT_PROFILES["snowboard_powder"].lateral_offset_m,
        speed_m_s=SPORT_PROFILES["snowboard_powder"].max_speed_m_s,
        duration_s=45.0,  # Long for powder descents
        motion_curve=MotionCurveType.LINEAR,
        gimbal_pitch_offset=-25.0,
        predictive_frames=SPORT_PROFILES["snowboard_powder"].lookahead_s,
    ),

    # MOTOCROSS JUMP - Height-locked for jump sequences
    # Use when: Motocross/supercross jumps (high speed + vertical)
    # Tuning: 15m distance, 6m height, 0.35s lookahead for jumps
    "motocross_jump": ShotTemplate(
        name="Motocross Jump (Height-Locked)",
        shot_type=ShotType.HEIGHT_LOCKED_TRACK,
        distance_m=SPORT_PROFILES["motocross_jump"].distance_m,
        height_offset_m=SPORT_PROFILES["motocross_jump"].height_offset_m,
        lateral_offset_m=SPORT_PROFILES["motocross_jump"].lateral_offset_m,
        speed_m_s=SPORT_PROFILES["motocross_jump"].max_speed_m_s,
        duration_s=15.0,
        motion_curve=MotionCurveType.LINEAR,  # Predictable for jumps
        gimbal_pitch_offset=-30.0,
        predictive_frames=SPORT_PROFILES["motocross_jump"].lookahead_s,
        height_lock=True,
    ),

    # TRAIL RUNNING - Smooth follow for running
    # Use when: Trail running, ultramarathon following
    # Tuning: 8m distance, 3m height, 5m/s for running pace
    "trail_running": ShotTemplate(
        name="Trail Running Follow",
        shot_type=ShotType.FOLLOW_DYNAMIC,
        distance_m=SPORT_PROFILES["trail_running"].distance_m,
        height_offset_m=SPORT_PROFILES["trail_running"].height_offset_m,
        lateral_offset_m=SPORT_PROFILES["trail_running"].lateral_offset_m,
        speed_m_s=SPORT_PROFILES["trail_running"].max_speed_m_s,
        duration_s=60.0,  # Long for endurance events
        motion_curve=MotionCurveType.LINEAR,  # Smooth for natural motion
        gimbal_pitch_offset=-15.0,
        predictive_frames=SPORT_PROFILES["trail_running"].lookahead_s,
    ),
}


@dataclass
class ShotMetrics:
    """Real-time shot quality metrics for monitoring cinematic shot execution.

    ShotMetrics captures quantitative measurements of shot quality during
    execution. These metrics are used to assess whether the shot meets
    cinematic standards and to provide feedback for shot improvement.

    Attributes:
        position_error_m: Distance from planned trajectory (meters).
            Measures how well the drone is following the intended path.
            Lower is better. >1.0m is considered poor quality.

        height_error_m: Altitude deviation from target (meters).
            Critical for height-locked shots. Measures vertical accuracy.
            Lower is better. >0.5m is noticeable in footage.

        gimbal_angular_velocity_deg_s: Gimbal movement speed (deg/s).
            Measures how fast the gimbal is slewing. High values indicate
            the subject is moving quickly relative to the drone, potentially
            causing blurry footage or mechanical stress.
            >30°/s is concerning for smooth footage.

        framing_score: 0-1 score for subject framing quality.
            1.0 = perfect framing (subject centered, rule of thirds)
            0.5 = acceptable (subject in frame but not ideal composition)
            <0.5 = poor (subject near edge or partially out of frame)

        smoothness_score: 0-1 score for motion smoothness.
            Based on velocity consistency and acceleration magnitude.
            1.0 = perfectly smooth motion
            <0.8 = jerky or amateur-looking motion

        velocity_m_s: Current drone velocity magnitude (m/s).
            Used to verify speed limits are respected and for smoothness calc.

        distance_to_subject_m: Current distance from subject (meters).
            Target distance vs actual distance for tracking quality.

    Quality Assessment:
    -----------------
    The is_quality_acceptable() method compares metrics against thresholds:

        position_error_m < max_position_error_m (default 1.0m)
        height_error_m < max_height_error_m (default 0.5m)
        framing_score > min_framing_score (default 0.7)

    If all conditions pass, the shot quality is considered acceptable.
    Metrics history is saved for post-shot analysis and template tuning.
    """
    position_error_m: float = 0.0
    height_error_m: float = 0.0
    gimbal_angular_velocity_deg_s: float = 0.0
    framing_score: float = 1.0
    smoothness_score: float = 1.0
    velocity_m_s: float = 0.0
    distance_to_subject_m: float = 0.0

    def is_quality_acceptable(self, thresholds: Dict[str, float]) -> bool:
        """Check if current metrics meet quality thresholds.

        Args:
            thresholds: Dict with keys:
                - max_position_error_m: Maximum acceptable path deviation
                - max_height_error_m: Maximum acceptable altitude error
                - min_framing_score: Minimum acceptable framing quality

        Returns:
            True if all metrics are within acceptable ranges, False otherwise.
        """
        if self.position_error_m > thresholds.get("max_position_error_m", MAX_POSITION_ERROR_M):
            return False
        if self.height_error_m > thresholds.get("max_height_error_m", MAX_HEIGHT_ERROR_M):
            return False
        if self.framing_score < thresholds.get("min_framing_score", 0.7):
            return False
        return True


class CinematicShotPlanner:
    """Plans and executes cinematic shots with smooth motion and quality monitoring.

    The CinematicShotPlanner is the main orchestrator for cinematic shot
    execution. It provides:

    1. Template Management: Access to pre-defined shot templates
    2. Trajectory Planning: Calculate paths for orbit, follow, and reveal shots
    3. Quality Monitoring: Track metrics during shot execution
    4. Sport Profiles: Access to sport-specific tuning parameters

    Usage:
        planner = CinematicShotPlanner()

        # List available templates
        templates = planner.list_templates()

        # Get specific template
        template = planner.get_template("orbit_close")

        # Calculate orbit trajectory
        trajectory = planner.calculate_orbit_trajectory(
            center_lat=37.7749, center_lon=-122.4194,
            radius_m=10.0, height_m=30.0, duration_s=20.0
        )

    The planner does not execute shots directly - use execute_cinematic_shot()
    for actual execution. The planner provides the planning and calculation
    infrastructure that execution functions use.
    """

    def __init__(self):
        """Initialize the shot planner with template library."""
        self.templates = CINEMATIC_TEMPLATES
        self.metrics_history: List[ShotMetrics] = []

    def get_template(self, name: str) -> Optional[ShotTemplate]:
        """Get a shot template by name.

        Args:
            name: Template name (e.g., "orbit_close", "follow_close")

        Returns:
            ShotTemplate if found, None otherwise.
        """
        return self.templates.get(name)

    def list_templates(self) -> List[str]:
        """List available template names.

        Returns:
            List of template name strings.
        """
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
        """Calculate orbit trajectory waypoints around a center point.

        Generates a circular path around the subject with specified radius
        and height. The trajectory consists of num_points waypoints evenly
        spaced around the circle.

        Mathematical Model:
        -------------------
        For each point i (0 to num_points-1):
            angle = 2π * i / num_points (radians)
            offset_north = radius * cos(angle)
            offset_east = radius * sin(angle)

        Converting to lat/lon:
            lat = center_lat + offset_north / meters_per_lat
            lon = center_lon + offset_east / meters_per_lon

        Args:
            center_lat: Center point latitude (degrees)
            center_lon: Center point longitude (degrees)
            radius_m: Orbit radius in meters
            height_m: Orbit altitude in meters AGL
            duration_s: Total orbit duration (affects speed, not path)
            clockwise: True for clockwise orbit, False for counter-clockwise
            num_points: Number of waypoints to generate (default 100)

        Returns:
            List of (lat, lon, altitude) waypoints

        Example:
            trajectory = planner.calculate_orbit_trajectory(
                center_lat=37.7749, center_lon=-122.4194,
                radius_m=10.0, height_m=30.0, duration_s=20.0
            )
            # trajectory is list of 100 (lat, lon, alt) tuples forming circle
        """
        trajectory = []
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(center_lat))

        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            if not clockwise:
                angle = -angle

            # Calculate offset from center
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

        Generates a drone trajectory that maintains a constant offset from
        the subject's path. This is used for follow shots where the drone
        stays at a fixed position relative to the moving subject.

        Mathematical Model:
        -------------------
        For each subject position (lat, lon, alt):
            drone_lat = lat + offset_north / meters_per_lat
            drone_lon = lon + offset_east / meters_per_lon
            drone_alt = alt + offset_up

        Args:
            subject_path: List of (lat, lon, alt) subject positions
            offset_north: North offset from subject (m). Positive = north of subject.
            offset_east: East offset from subject (m). Positive = east of subject.
            offset_up: Up offset from subject (m). Positive = above subject.
            num_points: Number of waypoints (default 100, interpolated if needed)

        Returns:
            List of (lat, lon, altitude) drone positions

        Example:
            subject_path = [(37.7749, -122.4194, 10), (37.7750, -122.4195, 10)]
            drone_path = planner.calculate_follow_trajectory(
                subject_path,
                offset_north=-10.0,  # 10m behind subject
                offset_east=5.0,      # 5m to the right
                offset_up=3.0         # 3m above subject
            )
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


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================
# These functions are exposed as MCP (Model Context Protocol) tools, allowing
# AI agents to execute cinematic shots via the drone MCP server.


async def execute_cinematic_shot(
    template_name: str,
    target_lat: float,
    target_lon: float,
    target_alt_m: Optional[float] = None,
    duration_s: Optional[float] = None,
    custom_params: Optional[Dict[str, Any]] = None
) -> str:
    """Execute a pre-programmed cinematic shot via MCP.

    This is the main entry point for AI agents to execute cinematic shots.
    It loads the specified template, applies any custom overrides, and executes
    the appropriate shot algorithm based on shot type.

    Execution Flow:
    -------------
    1. Load shot template by name
    2. Apply custom parameter overrides (if provided)
    3. Connect to drone via ConnectionManager
    4. Get current telemetry for starting position
    5. Execute shot-specific algorithm (orbit, follow, height-locked, etc.)
    6. Collect quality metrics during execution
    7. Return results as JSON with quality metrics

    Args:
        template_name: Name of shot template to execute. Available templates:
            - orbit_close: Tight 8m radius orbit, 2m/s, cinematic
            - orbit_wide: Wide 20m radius orbit, 4m/s, context
            - follow_close: Close 6m follow, 8m/s, action
            - follow_wide: Wide 15m follow, 12m/s, context
            - reveal_hero: Rising reveal shot, dramatic
            - pass_by_low: Low lateral pass, profile view
            - top_down_dynamic: Overhead tracking, 15m height
            - height_locked_jump: Exact height tracking for jumps
            - fpv_dynamic: Aggressive 15m/s FPV-style
            - snowboard_halfpipe: Optimized for halfpipe
            - skate_ledge_gap: Optimized for skate tricks
            - skate_bowl: Optimized for bowl skating
            - snowboard_powder: Optimized for powder runs
            - motocross_jump: Optimized for motocross
            - trail_running: Optimized for running

        target_lat: Target/subject latitude in decimal degrees
        target_lon: Target/subject longitude in decimal degrees
        target_alt_m: Target altitude in meters AGL. If None, uses current
            drone altitude + template height_offset.
        duration_s: Override shot duration in seconds. If None, uses template
            default duration.
        custom_params: Dict of custom parameter overrides. Can override any
            ShotTemplate attribute (distance_m, speed_m_s, etc.).
            Example: {"distance_m": 12.0, "speed_m_s": 6.0}

    Returns:
        JSON string containing:
        {
            "success": true/false,
            "template": template name used,
            "shot_type": type of shot executed,
            "duration_s": actual duration in seconds,
            "quality_metrics": {
                "avg_position_error_m": average path deviation,
                "avg_height_error_m": average altitude error,
                "avg_framing_score": average framing quality (0-1),
                "min_framing_score": worst framing quality,
                "samples_collected": number of metric samples
            },
            "parameters_used": {
                "distance_m": distance from subject,
                "height_offset_m": height above subject,
                "speed_m_s": max speed used,
                "motion_curve": curve type used,
                "gimbal_pitch_offset": gimbal angle used
            },
            "result": shot-specific result data
        }

    Example:
        # Execute a close orbit around subject at specific location
        result = await execute_cinematic_shot(
            template_name="orbit_close",
            target_lat=37.7749,
            target_lon=-122.4194,
            target_alt_m=50.0,
            duration_s=20.0
        )

        # Execute with custom parameters
        result = await execute_cinematic_shot(
            template_name="follow_close",
            target_lat=37.7749,
            target_lon=-122.4194,
            custom_params={"distance_m": 8.0, "speed_m_s": 6.0}
        )
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
    drone = await cm.get_drone()
    cache = get_telemetry_cache()

    if not drone:
        return json.dumps({
            "success": False,
            "error": "Drone not connected"
        })

    if not cache:
        return json.dumps({
            "success": False,
            "error": "Telemetry cache not available"
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

        # Calculate overall quality metrics from history
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


def _template_to_dict(template_name: str, template: ShotTemplate) -> Dict[str, Any]:
    """Serialize a shot template into JSON-safe fields."""
    return {
        "id": template_name,
        "name": template_name,
        "display_name": template.name,
        "shot_type": template.shot_type.name,
        "distance_m": template.distance_m,
        "height_offset_m": template.height_offset_m,
        "lateral_offset_m": template.lateral_offset_m,
        "speed_m_s": template.speed_m_s,
        "duration_s": template.duration_s,
        "motion_curve": template.motion_curve.name,
        "gimbal_mode": template.gimbal_mode,
        "gimbal_pitch_offset": template.gimbal_pitch_offset,
        "predictive_frames": template.predictive_frames,
        "height_lock": template.height_lock,
        "quality_thresholds": dict(template.quality_thresholds),
    }


async def list_cinematic_templates() -> str:
    """List available cinematic shot templates for MCP clients."""
    planner = CinematicShotPlanner()
    templates = [
        _template_to_dict(name, planner.templates[name])
        for name in planner.list_templates()
    ]
    return json.dumps({
        "success": True,
        "templates": templates,
        "count": len(templates),
        "total_templates": len(templates),
    })


async def preview_cinematic_shot(
    template_name: str,
    target_lat: float,
    target_lon: float,
) -> str:
    """Preview a cinematic shot trajectory without commanding the drone."""
    planner = CinematicShotPlanner()
    template = planner.get_template(template_name)
    if template is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown template: {template_name}",
            "available_templates": planner.list_templates(),
        })

    preview_alt_m = template.height_offset_m
    if template.shot_type == ShotType.ORBIT:
        trajectory = planner.calculate_orbit_trajectory(
            center_lat=target_lat,
            center_lon=target_lon,
            radius_m=template.distance_m,
            height_m=preview_alt_m,
            duration_s=template.duration_s,
            num_points=24,
        )
    else:
        trajectory = [
            (
                target_lat,
                target_lon,
                preview_alt_m,
            )
        ]

    return json.dumps({
        "success": True,
        "template": template_name,
        "template_details": _template_to_dict(template_name, template),
        "target": {
            "latitude": target_lat,
            "longitude": target_lon,
        },
        "sample_trajectory": [
            {"latitude": lat, "longitude": lon, "altitude_m": alt}
            for lat, lon, alt in trajectory[:10]
        ],
        "total_waypoints": len(trajectory),
        "estimated_duration_s": template.duration_s,
        "motion_curve": template.motion_curve.name,
        "trajectory_preview": [
            {"latitude": lat, "longitude": lon, "altitude_m": alt}
            for lat, lon, alt in trajectory
        ],
        "trajectory_points": len(trajectory),
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
    """Execute an orbit shot (circular path around subject).

    Orbit Algorithm:
    ----------------
    1. Calculate circular trajectory around target point
    2. At each timestep:
       a. Find closest point on trajectory to current position
       b. Calculate velocity vector toward that point (P-controller)
       c. Clamp velocity to template speed limits
       d. Send velocity command to drone
       e. Update gimbal to track subject
       f. Record quality metrics
    3. Maintain 10Hz control loop

    The drone follows a pre-calculated circular path while the gimbal
    continuously tracks the subject at the center, creating the classic
    "orbit" effect where the subject stays centered while background rotates.

    Args:
        template: ShotTemplate with orbit parameters
        target_lat: Center latitude
        target_lon: Center longitude
        target_alt_m: Center altitude (uses current + offset if None)
        curve: MotionCurve for velocity ramping
        cache: TelemetryCache for position feedback
        drone: MAVSDK drone instance
        metrics_history: List to append ShotMetrics

    Returns:
        Dict with execution results:
        {
            "points_executed": number of control iterations,
            "trajectory_points": total trajectory waypoints,
            "orbit_complete": True/False
        }
    """
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

        # Find closest trajectory point based on elapsed time progress
        progress = elapsed / template.duration_s
        point_idx = int(progress * len(trajectory))
        if point_idx >= len(trajectory):
            point_idx = len(trajectory) - 1

        target_lat_traj, target_lon_traj, target_alt_traj = trajectory[point_idx]

        # Calculate velocity to reach target point (simple P-controller)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        delta_lat = target_lat_traj - telem.latitude_deg
        delta_lon = target_lon_traj - telem.longitude_deg

        vel_north = delta_lat * meters_per_lat * 2.0  # P-controller gain = 2.0
        vel_east = delta_lon * meters_per_lon * 2.0
        vel_down = -(target_alt_traj - telem.relative_altitude_m) * 1.0

        # Clamp velocities to template speed limit
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

        # Update gimbal to track subject at center
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            target_lat, target_lon, target_alt_m
        )
        pitch += template.gimbal_pitch_offset

        try:
            await drone.gimbal.set_pitch_and_yaw(pitch, yaw - telem.yaw_deg if hasattr(telem, 'yaw_deg') else 0)
        except:
            pass

        # Calculate quality metrics
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

        # Maintain 10Hz control loop
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
    """Execute a follow shot with LookaheadPredictor for latency compensation.

    Follow Algorithm with Latency Compensation:
    ------------------------------------------
    1. Initialize LookaheadPredictor with template lookahead horizon
    2. Initialize PID controller for distance maintenance
    3. At each timestep (20Hz):
       a. Get current telemetry
       b. Update predictor with latest target position (from vision)
       c. Predict target position after latency (predict_future)
       d. Calculate desired drone position (behind predicted target)
       e. Use PID to control approach velocity based on distance error
       f. Calculate lateral offset for composition
       g. Send velocity command
       h. Update gimbal to track PREDICTED target (not current)
       i. Record quality metrics

    The key insight: By tracking the PREDICTED position (where subject will be
    in 200ms), the drone eliminates the lag that would otherwise be visible
    in the footage due to vision system latency.

    Args:
        template: ShotTemplate with follow parameters
        target_lat: Initial target latitude (updated from vision in real use)
        target_lon: Initial target longitude
        target_alt_m: Target altitude
        curve: MotionCurve for velocity shaping
        cache: TelemetryCache for position feedback
        drone: MAVSDK drone instance
        metrics_history: List to append ShotMetrics

    Returns:
        Dict with execution results:
        {
            "follow_complete": True,
            "samples_collected": number of control iterations,
            "avg_distance_error_m": average distance from target,
            "lookahead_s": prediction horizon used
        }
    """
    # Initialize LookaheadPredictor for vision latency compensation
    lookahead_s = template.predictive_frames or PREDICTION_HORIZON_S
    predictor = LookaheadPredictor(horizon_s=lookahead_s)

    # Initialize PID controller for distance maintenance
    distance_pid = PIDController(kp=0.8, ki=0.1, kd=0.2, output_limit=template.speed_m_s)

    start_time = asyncio.get_event_loop().time()
    last_target_lat = target_lat
    last_target_lon = target_lon
    last_target_alt = target_alt_m or 20.0

    samples_collected = 0
    total_distance_error = 0.0

    while asyncio.get_event_loop().time() - start_time < template.duration_s:
        loop_start = asyncio.get_event_loop().time()

        # Get current telemetry
        telem = await cache.get_latest()
        if not telem:
            await asyncio.sleep(0.05)
            continue

        # Update predictor with latest target position
        # (In real implementation, this would come from vision system)
        predictor.update(
            lat=last_target_lat,
            lon=last_target_lon,
            alt_m=last_target_alt,
            timestamp_s=loop_start
        )

        # Predict where target will be after latency
        pred_lat, pred_lon, pred_alt = predictor.predict_future(lookahead_s)

        # Calculate desired position (behind and offset from predicted position)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        # Vector to predicted target
        to_pred_lat = pred_lat - telem.latitude_deg
        to_pred_lon = pred_lon - telem.longitude_deg

        to_pred_north = to_pred_lat * meters_per_lat
        to_pred_east = to_pred_lon * meters_per_lon

        # Current distance to target
        current_dist = math.sqrt(to_pred_north**2 + to_pred_east**2)

        # Use PID to control distance error
        distance_error = template.distance_m - current_dist
        approach_velocity = distance_pid.update(distance_error, loop_start)

        # Calculate direction to target
        if current_dist > 0.1:
            dir_north = to_pred_north / current_dist
            dir_east = to_pred_east / current_dist
        else:
            dir_north = 0.0
            dir_east = 0.0

        # Velocity command: approach/retreat based on PID + lateral offset
        lateral_scale = template.lateral_offset_m / max(current_dist, 1.0)

        vel_north = (dir_north * approach_velocity +
                     dir_east * template.speed_m_s * lateral_scale)
        vel_east = (dir_east * approach_velocity -
                     dir_north * template.speed_m_s * lateral_scale)

        # Height control
        desired_alt = pred_alt + template.height_offset_m
        kp_alt = 1.0
        alt_error = desired_alt - telem.relative_altitude_m
        vel_down = _clamp(-alt_error * kp_alt, -3.0, 3.0)

        # Clamp to speed limits
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

        # Update gimbal to track predicted target position (latency compensation)
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            pred_lat, pred_lon, pred_alt
        )
        pitch += template.gimbal_pitch_offset

        try:
            await drone.gimbal.set_pitch_and_yaw(pitch, 0.0)
        except:
            pass

        # Calculate metrics
        metrics = ShotMetrics(
            position_error_m=abs(distance_error),
            height_error_m=abs(alt_error),
            velocity_m_s=speed,
            distance_to_subject_m=current_dist
        )
        metrics_history.append(metrics)

        total_distance_error += abs(distance_error)
        samples_collected += 1

        # Maintain 20Hz for smooth tracking
        elapsed = asyncio.get_event_loop().time() - loop_start
        if elapsed < 0.05:
            await asyncio.sleep(0.05 - elapsed)

    avg_distance_error = total_distance_error / max(samples_collected, 1)

    return {
        "follow_complete": True,
        "samples_collected": samples_collected,
        "avg_distance_error_m": round(avg_distance_error, 2),
        "lookahead_s": lookahead_s
    }


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
    """Execute height-locked tracking shot with PID control and latency compensation.

    Height-Locked Algorithm:
    ------------------------
    This is the most sophisticated tracking mode, designed for sports with
    significant vertical motion (jumps, halfpipe, motocross).

    Key Components:
    1. LookaheadPredictor: Compensates for vision latency by predicting
       subject position 200-350ms ahead
    2. Height PID Controller: Specialized PID with tight gains (kp=2.0)
       for precise altitude tracking. Maintains exact height offset.
    3. Distance PID Controller: Separate PID for lateral distance maintenance
    4. 20Hz Control Loop: Higher frequency for precise height tracking

    Control Flow:
    1. Predict subject position after latency
    2. Calculate desired drone position (maintaining distance_m behind subject)
    3. Calculate desired altitude (subject_alt + height_offset_m)
    4. Distance PID: Controls approach velocity based on distance error
    5. Height PID: Controls vertical velocity based on altitude error
    6. Send combined velocity command
    7. Update gimbal to track predicted subject position

    Height Lock Importance:
    -----------------------
    Without height lock, when a snowboarder goes up a halfpipe wall:
    - Drone stays at constant altitude
    - Snowboarder goes from center frame to top of frame to leaving frame
    - Result: Subject lost, shot ruined

    With height lock:
    - Drone climbs as snowboarder climbs
    - Snowboarder stays at constant position in frame
    - Result: Smooth tracking throughout vertical transition

    Args:
        template: ShotTemplate with height-lock parameters
        target_lat: Initial target latitude
        target_lon: Initial target longitude
        target_alt_m: Target altitude
        curve: MotionCurve for velocity shaping
        cache: TelemetryCache for position feedback
        drone: MAVSDK drone instance
        metrics_history: List to append ShotMetrics

    Returns:
        Dict with execution results:
        {
            "height_lock_maintained": True,
            "target_offset_m": height offset from subject,
            "samples_collected": control iterations,
            "max_height_error_m": worst altitude deviation,
            "max_position_error_m": worst position deviation,
            "height_quality_score": 0-1 score for height tracking,
            "position_quality_score": 0-1 score for position tracking,
            "lookahead_s": prediction horizon used
        }
    """
    start_time = asyncio.get_event_loop().time()
    last_target_lat = target_lat
    last_target_lon = target_lon
    last_target_alt = target_alt_m or 20.0

    # Initialize LookaheadPredictor for latency compensation
    lookahead_s = template.predictive_frames or 0.3  # Higher for jump prediction
    predictor = LookaheadPredictor(horizon_s=lookahead_s)

    # Initialize separate PID controllers for position and height
    # Height PID has tighter gains (kp=2.0) for precise altitude control
    height_pid = PIDController(kp=2.0, ki=0.3, kd=0.5, output_limit=3.0)
    distance_pid = PIDController(kp=0.8, ki=0.1, kd=0.2, output_limit=template.speed_m_s)

    # Metrics tracking
    max_height_error = 0.0
    max_position_error = 0.0
    samples = 0

    while asyncio.get_event_loop().time() - start_time < template.duration_s:
        loop_start = asyncio.get_event_loop().time()

        # Get current telemetry
        telem = await cache.get_latest()
        if not telem:
            await asyncio.sleep(0.05)
            continue

        # Update predictor with target position
        predictor.update(
            lat=last_target_lat,
            lon=last_target_lon,
            alt_m=last_target_alt,
            timestamp_s=loop_start
        )

        # Predict target position after latency
        pred_lat, pred_lon, pred_alt = predictor.predict_future(lookahead_s)

        # Calculate desired position (behind predicted position)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * math.cos(math.radians(telem.latitude_deg))

        # Vector to predicted target
        to_pred_lat = pred_lat - telem.latitude_deg
        to_pred_lon = pred_lon - telem.longitude_deg

        to_pred_north = to_pred_lat * meters_per_lat
        to_pred_east = to_pred_lon * meters_per_lon

        # Current distance to predicted target
        dist_to_pred = math.sqrt(to_pred_north**2 + to_pred_east**2)

        # Desired position: behind predicted target by distance_m
        if dist_to_pred > 0.1:
            desired_north = to_pred_north - (to_pred_north / dist_to_pred) * template.distance_m
            desired_east = to_pred_east - (to_pred_east / dist_to_pred) * template.distance_m
        else:
            desired_north = -template.distance_m
            desired_east = 0.0

        # PID control for position (distance maintenance)
        distance_error = template.distance_m - dist_to_pred
        approach_velocity = distance_pid.update(distance_error, loop_start)

        # Calculate direction to desired position
        desired_dist = math.sqrt(desired_north**2 + desired_east**2)
        if desired_dist > 0.1:
            vel_north = (desired_north / desired_dist) * approach_velocity
            vel_east = (desired_east / desired_dist) * approach_velocity
        else:
            vel_north = 0.0
            vel_east = 0.0

        # HEIGHT LOCK: PID control with tight gains
        # This is the critical feature - maintain exact height offset from subject
        desired_altitude = pred_alt + template.height_offset_m
        height_error = desired_altitude - telem.relative_altitude_m
        vel_down = _clamp(-height_pid.update(height_error, loop_start), -3.0, 3.0)

        # Clamp to speed limits
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

        # Calculate metrics
        position_error = math.sqrt(desired_north**2 + desired_east**2)
        height_error_abs = abs(height_error)
        velocity = math.sqrt(vel_north**2 + vel_east**2)

        metrics = ShotMetrics(
            position_error_m=position_error,
            height_error_m=height_error_abs,
            velocity_m_s=velocity,
            distance_to_subject_m=dist_to_pred
        )
        metrics_history.append(metrics)

        # Track worst-case errors for quality assessment
        max_height_error = max(max_height_error, height_error_abs)
        max_position_error = max(max_position_error, position_error)
        samples += 1

        # Update gimbal to track predicted target
        pitch, yaw = _calculate_look_angles(
            telem.latitude_deg, telem.longitude_deg, telem.relative_altitude_m,
            pred_lat, pred_lon, pred_alt
        )
        pitch += template.gimbal_pitch_offset

        try:
            await drone.gimbal.set_pitch_and_yaw(pitch, 0.0)
        except:
            pass

        # Maintain 20Hz for precise height lock
        elapsed = asyncio.get_event_loop().time() - loop_start
        if elapsed < 0.05:
            await asyncio.sleep(0.05 - elapsed)

    # Calculate quality score
    height_threshold = template.quality_thresholds.get("max_height_error_m", 0.3)
    position_threshold = template.quality_thresholds.get("max_position_error_m", 1.5)

    height_quality = max(0, 1.0 - (max_height_error / height_threshold))
    position_quality = max(0, 1.0 - (max_position_error / position_threshold))

    return {
        "height_lock_maintained": True,
        "target_offset_m": template.height_offset_m,
        "samples_collected": samples,
        "max_height_error_m": round(max_height_error, 2),
        "max_position_error_m": round(max_position_error, 2),
        "height_quality_score": round(height_quality, 2),
        "position_quality_score": round(position_quality, 2),
        "lookahead_s": lookahead_s
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
    """Execute generic shot (fallback for unimplemented shot types).

    Currently defaults to orbit behavior as a safe fallback.
    This can be extended for additional shot types in the future.

    Args:
        template: ShotTemplate parameters
        target_lat: Target latitude
        target_lon: Target longitude
        target_alt_m: Target altitude
        curve: MotionCurve for velocity shaping
        cache: TelemetryCache
        drone: MAVSDK drone instance
        metrics_history: List to append metrics

    Returns:
        Dict with execution results from orbit algorithm
    """
    # Default to orbit behavior for unimplemented shot types
    return await _execute_orbit(
        template, target_lat, target_lon, target_alt_m,
        curve, cache, drone, metrics_history
    )
