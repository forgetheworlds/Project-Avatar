"""
main.py — Full CV pipeline for Splash water gun drone.

Ties together:
  • Webcam capture or ESP32-CAM WiFi stream
  • YOLO person detection + LAB/HSV colour filtering
  • ByteTrack multi-object tracking
  • Motion compensation via IMU gyro homography (for drone ego-motion)
  • Targeting (servo angles, distance, fire command)
  • State machine: IDLE → DETECT → TRACK → AIM → FIRE
  • Annotated video output (saved to disk)
  • Protection mode integration

Motion Compensation:
  Uses MAVLink ATTITUDE messages (roll/pitch/yaw) from the drone's IMU
  to compute a camera homography, stabilizing pixel coordinates before
  target tracking. This prevents the turret from oscillating due to
  drone ego-motion during flight.

Usage:
  python main.py                          # webcam, show preview
  python main.py --no-preview             # webcam, headless
  python main.py --video input.mp4        # process video file
  python main.py --target-team team_a    # only fire on team_a
  python main.py --coreml                 # use CoreML on MacBook M3
  python main.py --motion-comp            # enable motion compensation (drone mode)

Project Avatar — Splash water gun drone CV pipeline.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from detector import PersonDetector, LABColorClassifier, HSVColorClassifier
from tracker import ByteTracker, KalmanBoxTracker
from targeting import TargetingEngine, AimConfig, TargetInfo


# ---------------------------------------------------------------------------
# Motion Compensator — IMU gyro homography
# ---------------------------------------------------------------------------

class MotionCompensator:
    """Compensates for drone ego-motion using IMU gyro data.

    When the drone flies, its roll/pitch/yaw changes cause the camera
    view to shift. Without compensation, the CV pipeline sees targets
    moving even when they're stationary, causing the turret to oscillate.

    This class computes a homography matrix H that warps the current
    frame into a stabilized coordinate system.

    H = K @ R @ K_inv

    Where:
      K = camera intrinsic matrix (from calibration)
      R = rotation matrix from IMU attitude (delta from reference)

    Usage:
        compensator = MotionCompensator(
            camera_matrix=camera_K,
            image_size=(640, 480)
        )
        stabilised_frame = compensator.stabilize(frame, roll_deg, pitch_deg, yaw_deg)
    """

    def __init__(
        self,
        camera_matrix: Optional[np.ndarray] = None,
        image_size: Tuple[int, int] = (640, 480),
        enable: bool = False,
    ) -> None:
        self.enable = enable
        self.image_size = image_size

        # Default camera matrix (assume 70° HFOV, 50° VFOV, 640x480)
        if camera_matrix is not None:
            self.K = camera_matrix
        else:
            # Reasonable default for 640x480, 70° HFOV camera
            fx = image_size[0] / (2 * np.tan(np.radians(70 / 2)))
            fy = image_size[1] / (2 * np.tan(np.radians(50 / 2)))
            cx = image_size[0] / 2
            cy = image_size[1] / 2
            self.K = np.array([
                [fx, 0, cx],
                [0, fy, cy],
                [0,  0,  1],
            ], dtype=np.float32)

        self.K_inv = np.linalg.inv(self.K)

        # Reference attitude (set on first frame)
        self.ref_roll: float = 0.0
        self.ref_pitch: float = 0.0
        self.ref_yaw: float = 0.0
        self._initialized = False

    def set_reference(self, roll_deg: float, pitch_deg: float, yaw_deg: float) -> None:
        """Set the reference attitude (usually from first frame or hover)."""
        self.ref_roll = roll_deg
        self.ref_pitch = pitch_deg
        self.ref_yaw = yaw_deg
        self._initialized = True

    def reset(self) -> None:
        """Reset reference to current frame."""
        self._initialized = False

    def stabilize_frame(
        self,
        frame: np.ndarray,
        roll_deg: float,
        pitch_deg: float,
        yaw_deg: float,
    ) -> np.ndarray:
        """Warp frame to compensate for IMU attitude change.

        Returns the stabilized frame (same size).
        If not enabled or not initialized, returns original frame.
        """
        if not self.enable:
            return frame

        if not self._initialized:
            self.set_reference(roll_deg, pitch_deg, yaw_deg)
            return frame

        # Compute delta rotation
        d_roll = np.radians(roll_deg - self.ref_roll)
        d_pitch = np.radians(pitch_deg - self.ref_pitch)
        d_yaw = np.radians(yaw_deg - self.ref_yaw)

        # Rotation matrices (Z-Y-X Euler)
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(d_roll), -np.sin(d_roll)],
            [0, np.sin(d_roll), np.cos(d_roll)],
        ])
        Ry = np.array([
            [np.cos(d_pitch), 0, np.sin(d_pitch)],
            [0, 1, 0],
            [-np.sin(d_pitch), 0, np.cos(d_pitch)],
        ])
        Rz = np.array([
            [np.cos(d_yaw), -np.sin(d_yaw), 0],
            [np.sin(d_yaw), np.cos(d_yaw), 0],
            [0, 0, 1],
        ])

        R = Rz @ Ry @ Rx

        # Homography: H = K @ R @ K_inv
        H = self.K @ R @ self.K_inv

        h, w = frame.shape[:2]
        stabilized = cv2.warpPerspective(frame, H, (w, h),
                                         borderMode=cv2.BORDER_REPLICATE)
        return stabilized

    def stabilize_points(
        self,
        points: np.ndarray,
        roll_deg: float,
        pitch_deg: float,
        yaw_deg: float,
    ) -> np.ndarray:
        """Apply motion compensation to pixel coordinates.

        Args:
            points: N×2 array of (x, y) pixel coordinates
            roll_deg, pitch_deg, yaw_deg: current IMU attitude

        Returns:
            N×2 array of compensated pixel coordinates
        """
        if not self.enable or not self._initialized:
            return points

        d_roll = np.radians(roll_deg - self.ref_roll)
        d_pitch = np.radians(pitch_deg - self.ref_pitch)
        d_yaw = np.radians(yaw_deg - self.ref_yaw)

        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(d_roll), -np.sin(d_roll)],
            [0, np.sin(d_roll), np.cos(d_roll)],
        ])
        Ry = np.array([
            [np.cos(d_pitch), 0, np.sin(d_pitch)],
            [0, 1, 0],
            [-np.sin(d_pitch), 0, np.cos(d_pitch)],
        ])
        Rz = np.array([
            [np.cos(d_yaw), -np.sin(d_yaw), 0],
            [np.sin(d_yaw), np.cos(d_yaw), 0],
            [0, 0, 1],
        ])
        R = Rz @ Ry @ Rx
        H = self.K @ R @ self.K_inv

        # Transform points
        pts_h = cv2.perspectiveTransform(
            points.reshape(-1, 1, 2).astype(np.float32), H
        )
        return pts_h.reshape(-1, 2)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class State(Enum):
    IDLE   = auto()
    DETECT = auto()
    TRACK  = auto()
    AIM    = auto()
    FIRE   = auto()


@dataclass
class PipelineState:
    """Mutable state carried across frames."""

    current: State = State.IDLE
    frame_count: int = 0
    fps: float = 0.0
    last_time: float = field(default_factory=time.time)

    # Primary target
    active_target_id: Optional[int] = None
    target_locked_frames: int = 0

    # FIRE cooldown
    fire_cooldown_frames: int = 0
    fire_cooldown_max: int = 15          # frames between shots
    aim_stable_frames: int = 0
    aim_stable_required: int = 10        # frames on-target before firing

    # Statistics
    shots_fired: int = 0


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

class Visualizer:
    """Draw annotations directly onto the frame."""

    # Colour palette
    COLOR_TEAM_A = (0, 0, 255)      # red
    COLOR_TEAM_B = (255, 0, 0)      # blue
    COLOR_UNKNOWN = (128, 128, 128) # grey
    COLOR_TARGET = (0, 255, 255)    # yellow
    COLOR_CROSSHAIR = (255, 255, 255)
    COLOR_FIRE = (0, 0, 255)

    @classmethod
    def draw(cls, frame, tracks, targets, state: PipelineState,
             target_team: Optional[str] = None):
        h, w = frame.shape[:2]

        # Crosshair at centre
        cx, cy = w // 2, h // 2
        cv2.drawMarker(frame, (cx, cy), cls.COLOR_CROSSHAIR,
                       cv2.MARKER_CROSS, 20, 2)

        # Each track
        for t in tracks:
            color = cls._track_color(t.color_label)
            if state.active_target_id is not None and t.id == state.active_target_id:
                color = cls.COLOR_TARGET
                thickness = 3
            else:
                thickness = 2

            x1, y1, x2, y2 = t.bbox
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Label
            label = f"ID:{t.id} {t.color_label} {t.confidence:.2f}"
            cv2.putText(frame, label, (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        # Target info overlay
        if targets:
            for ti in targets:
                if ti.target_id == state.active_target_id:
                    cls._draw_target_overlay(frame, ti)

        # State badge
        state_colors = {
            State.IDLE: (200, 200, 200),
            State.DETECT: (255, 200, 0),
            State.TRACK: (0, 255, 0),
            State.AIM: (0, 200, 255),
            State.FIRE: (0, 0, 255),
        }
        badge_color = state_colors.get(state.current, (255, 255, 255))
        cv2.putText(frame, f"STATE: {state.current.name}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, badge_color, 2)
        cv2.putText(frame, f"FPS: {state.fps:.1f}  Shots: {state.shots_fired}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    @staticmethod
    def _track_color(label: str):
        if label == "team_a":
            return Visualizer.COLOR_TEAM_A
        elif label == "team_b":
            return Visualizer.COLOR_TEAM_B
        return Visualizer.COLOR_UNKNOWN

    @classmethod
    def _draw_target_overlay(cls, frame, ti: TargetInfo):
        h, w = frame.shape[:2]
        y0 = h - 130 if h > 200 else 10

        lines = [
            f"Target #{ti.target_id}  {ti.color_label}",
            f"Offset: ({ti.center_offset[0]:+.0f}, {ti.center_offset[1]:+.0f}) px",
            f"Pan: {ti.pan_angle:.1f}  Tilt: {ti.tilt_angle:.1f}",
            f"Dist: ~{ti.distance_estimate:.1f}m  Fire: {'YES' if ti.fire_command else 'no'}",
        ]
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (10, y0 + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, cls.COLOR_TARGET, 1)

        if ti.fire_command:
            cv2.putText(frame, "FIRE!", (w // 2 - 40, h // 2 + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, cls.COLOR_FIRE, 4)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SplashCVPipeline:
    """End-to-end CV pipeline with state machine."""

    def __init__(
        self,
        target_team: Optional[str] = None,
        aim_config: Optional[AimConfig] = None,
        detector_conf: float = 0.4,
        tracker_high: float = 0.5,
        tracker_low: float = 0.2,
        output_video: Optional[str] = None,
        show_preview: bool = True,
        model_path: str = "yolov8n.pt",
        use_coreml: bool = False,
        motion_comp: bool = False,
    ) -> None:
        self.target_team = target_team
        self.show_preview = show_preview

        # Model backend selection
        if use_coreml:
            model_path = model_path.replace(".pt", ".mlpackage")
            if model_path == model_path.replace(".pt", ".mlpackage"):
                model_path = "yolo11n.mlpackage"

        # Modules
        self.detector = PersonDetector(
            model_path=model_path,
            backend="coreml" if use_coreml else "auto",
            confidence_threshold=detector_conf,
            use_lab=True,  # LAB color space for outdoor
        )
        self.tracker = ByteTracker(
            track_high_thresh=tracker_high,
            track_low_thresh=tracker_low,
        )
        self.aim_cfg = aim_config or AimConfig()
        self.targeting = TargetingEngine(self.aim_cfg)

        # Motion compensation
        self.motion_comp = MotionCompensator(
            enable=motion_comp,
            image_size=(self.aim_cfg.frame_width, self.aim_cfg.frame_height)
        )

        # State
        self.state = PipelineState()

        # Output
        self.output_video = output_video
        self._writer: Optional[cv2.VideoWriter] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame, roll_deg: float = 0.0,
                     pitch_deg: float = 0.0, yaw_deg: float = 0.0) -> Optional[List[TargetInfo]]:
        """Run one frame through the full pipeline. Returns target info list.

        Args:
            frame: BGR image frame
            roll_deg, pitch_deg, yaw_deg: Current drone IMU attitude (for motion comp)
        """
        frame = self._ensure_bgr(frame)
        h, w = frame.shape[:2]
        self.aim_cfg.frame_width = w
        self.aim_cfg.frame_height = h

        # Update motion compensator image size
        self.motion_comp.image_size = (w, h)

        # --- Step 0: Motion compensation (drone mode) ---
        if self.motion_comp.enable:
            self.motion_comp.set_reference(roll_deg, pitch_deg, yaw_deg)

        # --- Step 1: Detect ---
        detections = self.detector.detect(frame)
        self.state.current = State.DETECT

        # Apply motion compensation to detection centers
        if self.motion_comp.enable and self.motion_comp._initialized and detections:
            for det in detections:
                cx, cy = det.center
                compensated = self.motion_comp.stabilize_points(
                    np.array([[cx, cy]]),
                    roll_deg, pitch_deg, yaw_deg
                )
                # Shift bbox by compensated offset
                new_cx, new_cy = compensated[0]
                dx = new_cx - cx
                dy = new_cy - cy
                det.bbox = (
                    int(det.bbox[0] + dx),
                    int(det.bbox[1] + dy),
                    int(det.bbox[2] + dx),
                    int(det.bbox[3] + dy),
                )

        # --- Step 2: Track ---
        tracks = self.tracker.update(detections)

        if tracks:
            self.state.current = State.TRACK

        # --- Step 3: Select primary target ---
        primary = self._select_target(tracks)

        targets: List[TargetInfo] = []
        if primary is not None:
            self.state.current = State.AIM
            ti = self.targeting.calculate(
                bbox=primary.bbox,
                track_id=primary.id,
                confidence=primary.confidence,
                color_label=primary.color_label,
                target_team=self.target_team,
            )
            targets.append(ti)

            # --- Step 4: State machine transitions ---
            self._update_state_machine(ti)

        else:
            self._reset_target()

        # --- Annotate ---
        vis_frame = frame.copy() if self._writer else frame
        Visualizer.draw(vis_frame, list(self.tracker.tracks.values()),
                        targets, self.state, self.target_team)

        if self.show_preview:
            cv2.imshow("Splash CV Pipeline", vis_frame)

        if self._writer:
            self._writer.write(vis_frame)

        # --- FPS ---
        now = time.time()
        elapsed = now - self.state.last_time
        self.state.last_time = now
        self.state.fps = 0.9 * self.state.fps + 0.1 * (1.0 / max(elapsed, 0.001))
        self.state.frame_count += 1

        return targets if targets else None

    def start_capture(self, source=0):
        """Run pipeline on a video source (camera index or file path)."""
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        if self.output_video:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(
                self.output_video, fourcc, fps, (w, h)
            )
            print(f"Recording → {self.output_video}")

        print(f"Pipeline running on {'camera' if isinstance(source, int) else source}")
        print(f"Target team: {self.target_team or 'any'}")
        print("Press 'q' to quit, 't' to toggle team targeting, 'space' to force fire\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                targets = self.process_frame(frame)

                # Print targeting info to console when aiming
                if targets and self.state.current in (State.AIM, State.FIRE):
                    for ti in targets:
                        arrow = ">>> FIRE <<<" if ti.fire_command else "  aim  "
                        print(
                            f"\r[{arrow}] ID:{ti.target_id} "
                            f"pan={ti.pan_angle:.1f} tilt={ti.tilt_angle:.1f} "
                            f"dist={ti.distance_estimate:.1f}m  "
                            f"offset=({ti.center_offset[0]:+.0f},{ti.center_offset[1]:+.0f})px  ",
                            end="", flush=True,
                        )

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("t"):
                    self.target_team = None if self.target_team else "team_a"
                    print(f"\nTarget team: {self.target_team or 'any'}")
                elif key == ord(" "):
                    self.state.shots_fired += 1
                    print(f"\n[MANUAL FIRE] Shot #{self.state.shots_fired}")

        except KeyboardInterrupt:
            pass
        finally:
            cap.release()
            if self._writer:
                self._writer.release()
            if self.show_preview:
                cv2.destroyAllWindows()
            print(f"\nDone. {self.state.shots_fired} shots fired.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_bgr(frame):
        """Convert RGBA / greyscale to BGR if needed."""
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        return frame

    def _select_target(self, tracks: List[KalmanBoxTracker]) -> Optional[KalmanBoxTracker]:
        """Pick the best track as the primary target."""
        if not tracks:
            return None

        # If we already have a locked target, try to keep it
        if self.state.active_target_id is not None:
            for t in tracks:
                if t.id == self.state.active_target_id:
                    self.state.target_locked_frames += 1
                    return t

        # Score candidates: prefer target_team matches, then highest confidence
        candidates = []
        for t in tracks:
            score = t.confidence
            if self.target_team and t.color_label == self.target_team:
                score += 1.0
            elif self.target_team and t.color_label == "unknown":
                score += 0.3
            candidates.append((score, t))

        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates:
            best = candidates[0][1]
            self.state.active_target_id = best.id
            self.state.target_locked_frames = 1
            return best

        return None

    def _update_state_machine(self, ti: TargetInfo) -> None:
        """Evaluate fire logic and manage state transitions."""
        if ti.fire_command:
            self.state.aim_stable_frames += 1
            if self.state.aim_stable_frames >= self.state.aim_stable_required:
                if self.state.fire_cooldown_frames <= 0:
                    self.state.current = State.FIRE
                    self.state.shots_fired += 1
                    self.state.fire_cooldown_frames = self.state.fire_cooldown_max
                    self.state.aim_stable_frames = 0
                else:
                    self.state.fire_cooldown_frames -= 1
                    self.state.current = State.AIM
        else:
            self.state.aim_stable_frames = max(0, self.state.aim_stable_frames - 1)
            if self.state.fire_cooldown_frames > 0:
                self.state.fire_cooldown_frames -= 1

    def _reset_target(self) -> None:
        """Called when no target is visible."""
        self.state.active_target_id = None
        self.state.target_locked_frames = 0
        self.state.aim_stable_frames = 0
        self.state.current = State.IDLE


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Splash CV Pipeline")
    parser.add_argument("--video", type=str, default=None,
                        help="Path to video file (default: webcam)")
    parser.add_argument("--camera", type=int, default=0,
                        help="Camera device index (default: 0)")
    parser.add_argument("--target-team", type=str, default=None,
                        choices=["team_a", "team_b"],
                        help="Only track/fire on this team colour")
    parser.add_argument("--no-preview", action="store_true",
                        help="Disable preview window")
    parser.add_argument("--output", type=str, default=None,
                        help="Save annotated output to video file")
    parser.add_argument("--detector-conf", type=float, default=0.4,
                        help="Detection confidence threshold")
    parser.add_argument("--coreml", action="store_true",
                        help="Use CoreML backend (MacBook M3 ANE)")
    parser.add_argument("--motion-comp", action="store_true",
                        help="Enable motion compensation (drone mode)")
    parser.add_argument("--hfov", type=float, default=70.0,
                        help="Camera horizontal FOV (degrees)")
    parser.add_argument("--vfov", type=float, default=50.0,
                        help="Camera vertical FOV (degrees)")
    parser.add_argument("--fire-dist", type=float, default=3.0,
                        help="Maximum fire distance (metres)")
    args = parser.parse_args()

    source = args.video if args.video else args.camera

    aim_cfg = AimConfig(
        hfov_deg=args.hfov,
        vfov_deg=args.vfov,
        fire_max_distance_m=args.fire_dist,
    )

    pipeline = SplashCVPipeline(
        target_team=args.target_team,
        aim_config=aim_cfg,
        detector_conf=args.detector_conf,
        output_video=args.output,
        show_preview=not args.no_preview,
        use_coreml=args.coreml,
        motion_comp=args.motion_comp,
    )

    pipeline.start_capture(source)


if __name__ == "__main__":
    main()
