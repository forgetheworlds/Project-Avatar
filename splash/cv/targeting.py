"""
Splash CV Pipeline — Person detection, tracking, targeting.
Runs on MacBook M3, feeds aim commands to drone via MCP.
"""
import cv2
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(Enum):
    IDLE = "idle"
    DETECT = "detect"
    TRACK = "track"
    AIM = "aim"
    FIRE = "fire"


@dataclass
class Target:
    id: int
    bbox: tuple  # (x1, y1, x2, y2)
    center_offset: tuple  # (dx, dy) pixels from frame center
    pan_angle: float  # degrees
    tilt_angle: float  # degrees
    distance_estimate: float  # meters
    confidence: float
    frames_lost: int = 0


class TargetingSystem:
    """Calculates servo angles and fire commands from tracking data."""

    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 480,
        hfov_deg: float = 70.0,
        vfov_deg: float = 55.0,
        pan_range: tuple = (-90, 90),
        tilt_range: tuple = (-45, 45),
        fire_distance_m: float = 3.0,
        aim_deadzone_px: int = 30,
    ):
        self.fw = frame_width
        self.fh = frame_height
        self.hfov = np.radians(hfov_deg)
        self.vfov = np.radians(vfov_deg)
        self.pan_range = pan_range
        self.tilt_range = tilt_range
        self.fire_distance = fire_distance_m
        self.deadzone = aim_deadzone_px

        # Pixels per degree
        self.px_per_deg_h = frame_width / hfov_deg
        self.px_per_deg_v = frame_height / vfov_deg

    def calculate(
        self, bbox: tuple, frame_center: tuple = None
    ) -> dict:
        """Calculate aim angles and fire command from bounding box."""
        if frame_center is None:
            frame_center = (self.fw // 2, self.fh // 2)

        x1, y1, x2, y2 = bbox
        cx, cy = frame_center
        bx = (x1 + x2) / 2
        by = (y1 + y2) / 2

        # Offset from center
        dx = bx - cx
        dy = by - cy

        # Convert to angles
        pan = dx / self.px_per_deg_h
        tilt = dy / self.px_per_deg_v

        # Clamp
        pan = max(self.pan_range[0], min(self.pan_range[1], pan))
        tilt = max(self.tilt_range[0], min(self.tilt_range[1], tilt))

        # Distance estimate from bbox height (rough)
        bbox_h = y2 - y1
        # Assuming avg person height ~1.7m, focal length heuristic
        focal_estimate = self.fh / (2 * np.tan(self.vfov / 2))
        distance = (1.7 * focal_estimate) / bbox_h if bbox_h > 0 else 999

        # Fire if close enough and centered
        centered = abs(dx) < self.deadzone and abs(dy) < self.deadzone
        in_range = distance < self.fire_distance
        fire = centered and in_range

        return {
            "center_offset": (round(dx, 1), round(dy, 1)),
            "pan_angle": round(pan, 1),
            "tilt_angle": round(tilt, 1),
            "distance_estimate": round(distance, 1),
            "fire_command": fire,
            "is_centered": centered,
            "in_range": in_range,
        }


class KalmanTracker:
    """Simple Kalman filter for smoothing target position."""

    def __init__(self, process_noise: float = 0.01, measurement_noise: float = 0.1):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        self.kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
        )
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * measurement_noise
        self.initialized = False

    def update(self, x: float, y: float) -> tuple:
        if not self.initialized:
            self.kf.statePre = np.array([[x], [y], [0], [0]], np.float32)
            self.kf.statePost = np.array([[x], [y], [0], [0]], np.float32)
            self.initialized = True
            return x, y
        prediction = self.kf.predict()
        measurement = np.array([[np.float32(x)], [np.float32(y)]])
        self.kf.correct(measurement)
        return float(prediction[0]), float(prediction[1])

    def reset(self):
        self.initialized = False
