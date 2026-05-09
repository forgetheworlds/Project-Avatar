"""
detector.py — YOLOv8 person detection with HSV team-jersey color filtering.

Project Avatar — Splash water gun drone CV pipeline.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ultralytics import YOLO


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """Single person detection from YOLO + colour classifier."""

    bbox: Tuple[int, int, int, int]   # (x1, y1, x2, y2) – pixel coords
    confidence: float
    class_id: int                     # 0 = person (COCO)
    class_name: str                   # "person"
    color_label: str = "unknown"      # "team_a", "team_b", "unknown"

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])


# ---------------------------------------------------------------------------
# HSV colour classifier
# ---------------------------------------------------------------------------

class HSVColorClassifier:
    """
    Classify a person region into a team label based on HSV colour ranges.

    Defaults are tuned for common jersey colours:
      team_a: red  (H ≈ 0-10, 170-180)
      team_b: blue (H ≈ 100-130)
    """

    def __init__(
        self,
        team_a_ranges: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
        team_b_ranges: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
    ) -> None:
        # Red wraps around 0 — use two ranges
        self.team_a_ranges = team_a_ranges or [
            (np.array([0, 50, 50]),   np.array([10, 255, 255])),
            (np.array([170, 50, 50]), np.array([180, 255, 255])),
        ]
        self.team_b_ranges = team_b_ranges or [
            (np.array([100, 50, 50]), np.array([130, 255, 255])),
        ]

    def classify(self, roi: np.ndarray) -> str:
        """Return 'team_a', 'team_b', or 'unknown' for a BGR ROI."""
        if roi.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Build combined masks
        mask_a = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in self.team_a_ranges:
            mask_a = cv2.bitwise_or(mask_a, cv2.inRange(hsv, lo, hi))

        mask_b = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in self.team_b_ranges:
            mask_b = cv2.bitwise_or(mask_b, cv2.inRange(hsv, lo, hi))

        pixels_a = int(cv2.countNonZero(mask_a))
        pixels_b = int(cv2.countNonZero(mask_b))
        total = pixels_a + pixels_b

        if total < 20:                     # too few coloured pixels
            return "unknown"
        if pixels_a / total > 0.5:
            return "team_a"
        if pixels_b / total > 0.5:
            return "team_b"
        return "unknown"


# ---------------------------------------------------------------------------
# Person detector
# ---------------------------------------------------------------------------

class PersonDetector:
    """
    YOLOv8 person detector with optional HSV team-colour classification.

    Parameters
    ----------
    model_path : str
        Path or name of the Ultralytics YOLO model.  Defaults to ``yolov8n.pt``
        (nano), which is fast enough for real-time on CPU.
    confidence_threshold : float
        Minimum confidence for a detection to be kept.
    color_classifier : HSVColorClassifier | None
        If provided, each detection is classified into a team label.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        color_classifier: Optional[HSVColorClassifier] = None,
    ) -> None:
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.color_classifier = color_classifier or HSVColorClassifier()

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run detection on a BGR frame and return a list of ``Detection``
        objects (persons only).
        """
        results = self.model(frame, verbose=False)
        detections: List[Detection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0].item())
                if cls_id != 0:               # COCO person class only
                    continue

                conf = float(box.conf[0].item())
                if conf < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bbox = (int(x1), int(y1), int(x2), int(y2))

                # Colour classification on torso region
                color_label = self._classify_person_color(frame, bbox)

                detections.append(Detection(
                    bbox=bbox,
                    confidence=conf,
                    class_id=0,
                    class_name="person",
                    color_label=color_label,
                ))

        return detections

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_person_color(
        self, frame: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> str:
        """Extract torso region and run HSV classifier."""
        x1, y1, x2, y2 = bbox
        # Torso is roughly the upper-middle of the bounding box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        h = y2 - y1
        w = x2 - x1

        clip_h, clip_w = frame.shape[:2]

        # Sample a window: ±¼ width, upper half of bbox (torso)
        sx1 = max(0, int(cx - w * 0.25))
        sx2 = min(clip_w, int(cx + w * 0.25))
        sy1 = max(0, int(y1 + h * 0.15))
        sy2 = min(clip_h, int(cy))

        if sx2 <= sx1 or sy2 <= sy1:
            return "unknown"

        roi = frame[sy1:sy2, sx1:sx2]
        return self.color_classifier.classify(roi)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    detector = PersonDetector(confidence_threshold=0.3)

    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is None:
            print(f"Cannot read {sys.argv[1]}")
            sys.exit(1)
    else:
        # Capture from default webcam for a single frame
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("No camera available")
            sys.exit(1)
        ret, img = cap.read()
        cap.release()
        if not ret:
            print("Failed to grab frame")
            sys.exit(1)

    dets = detector.detect(img)
    print(f"Found {len(dets)} person(s):")
    for d in dets:
        print(
            f"  bbox={d.bbox}  conf={d.confidence:.2f}  "
            f"centre={d.center}  colour={d.color_label}"
        )
