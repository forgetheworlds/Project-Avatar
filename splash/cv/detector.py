"""
detector.py — YOLO person detection with team-jersey color filtering.

Supports:
  • YOLOv8n / YOLOv11n PyTorch (CPU/MPS)
  • YOLOv11n CoreML FP16 (Apple ANE, 110-130 FPS on M3)
  • HSV color classifier (original, fast)
  • LAB (CIELAB) color classifier (superior outdoor performance)
  • LAB decouples lightness from color — more stable under variable outdoor lighting

Usage:
    detector = PersonDetector(model_path="yolo11n.pt")
    detections = detector.detect(frame)

    # CoreML on MacBook M3:
    detector = PersonDetector(model_path="yolo11n.mlpackage", backend="coreml")
    detections = detector.detect(frame)

Project Avatar — Splash water gun drone CV pipeline.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import logging
from ultralytics import YOLO

logger = logging.getLogger("splash.cv.detector")


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
# LAB (CIELAB) color classifier — RECOMMENDED for outdoor use
# ---------------------------------------------------------------------------

class LABColorClassifier:
    """Classify a person region into team label using LAB color space.

    LAB is superior to HSV for outdoor team jersey identification because:
      - L* (lightness) is decoupled from a*/b* (color)
      - HSV H channel becomes unstable under variable outdoor lighting
      - Less sensitive to shadows and sunlight angle changes

    Pipeline:
      1. CLAHE pre-processing on L* channel (normalize lighting)
      2. BGR → LAB conversion
      3. Threshold a*/b* channels for team colors
      4. Vote by pixel majority

    Team A (Red jersey):  a* > 140, b* < 140
    Team B (Blue jersey):  a* < 130, b* < 120
    """

    def __init__(
        self,
        team_a_lab_range: Optional[dict] = None,
        team_b_lab_range: Optional[dict] = None,
        use_clahe: bool = True,
        min_colored_pixels: int = 20,
        majority_threshold: float = 0.55,
    ) -> None:
        # Default LAB thresholds (tunable for specific jersey colors)
        self.team_a_range = team_a_lab_range or {
            "a_min": 140, "a_max": 255,
            "b_min": 0, "b_max": 140,
        }
        self.team_b_range = team_b_lab_range or {
            "a_min": 0, "a_max": 130,
            "b_min": 0, "b_max": 120,
        }
        self.use_clahe = use_clahe
        self.min_colored_pixels = min_colored_pixels
        self.majority_threshold = majority_threshold

        # CLAHE for lighting normalization
        if self.use_clahe:
            self._clahe = cv2.createCLAHE(clip_limit=2.0, tile_grid_size=(8, 8))

    def classify(self, roi: np.ndarray) -> str:
        """Return 'team_a', 'team_b', or 'unknown' for a BGR ROI."""
        if roi.size == 0:
            return "unknown"

        # CLAHE on L* channel for lighting normalization
        if self.use_clahe:
            lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l_eq = self._clahe.apply(l)
            lab_eq = cv2.merge([l_eq, a, b])
        else:
            lab_eq = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)

        l, a, b = cv2.split(lab_eq)

        # Team A mask (red): high a*, low b*
        mask_a = cv2.inRange(
            cv2.merge([a, b, l]),  # Combine channels for inRange
            np.array([self.team_a_range["a_min"], self.team_a_range["b_min"], 0]),
            np.array([self.team_a_range["a_max"], self.team_a_range["b_max"], 255])
        )

        # Team B mask (blue): low a*, low b*
        mask_b = cv2.inRange(
            cv2.merge([a, b, l]),
            np.array([self.team_b_range["a_min"], self.team_b_range["b_min"], 0]),
            np.array([self.team_b_range["a_max"], self.team_b_range["b_max"], 255])
        )

        pixels_a = int(cv2.countNonZero(mask_a))
        pixels_b = int(cv2.countNonZero(mask_b))
        total = pixels_a + pixels_b

        if total < self.min_colored_pixels:
            return "unknown"

        ratio_a = pixels_a / total
        if ratio_a > self.majority_threshold:
            return "team_a"
        ratio_b = pixels_b / total
        if ratio_b > self.majority_threshold:
            return "team_b"
        return "unknown"


# ---------------------------------------------------------------------------
# HSV color classifier (original, fallback for indoor/controlled lighting)
# ---------------------------------------------------------------------------

class HSVColorClassifier:
    """
    Classify a person region into a team label based on HSV colour ranges.

    Defaults are tuned for common jersey colours:
      team_a: red  (H ≈ 0-10, 170-180)
      team_b: blue (H ≈ 100-130)

    ⚠️ NOTE: HSV H channel is unstable under variable outdoor lighting.
    Use LABColorClassifier for outdoor deployment.
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
    YOLO person detector with team-colour classification.

    Supports:
      - YOLOv8n / YOLOv11n PyTorch (CPU / MPS)
      - YOLOv11n CoreML FP16 (Apple ANE, 110-130 FPS on M3)
      - HSV color classification (indoor/controlled)
      - LAB color classification (outdoor, recommended)

    Parameters
    ----------
    model_path : str
        Path to YOLO model. Supports:
          - "yolov8n.pt" (PyTorch, CPU/MPS)
          - "yolov11n.pt" (PyTorch, CPU/MPS)
          - "yolo11n.mlpackage" (CoreML FP16, Apple ANE — M3 MacBooks)
    backend : str
        Inference backend: "auto" (default), "coreml", "mps", "cpu".
        "auto" detects .mlpackage extension and routes to CoreML.
    confidence_threshold : float
        Minimum confidence for a detection to be kept.
    color_classifier : Any
        If provided, each detection is classified into a team label.
        Expected to have a classify(roi: np.ndarray) -> str method.
        Default: LABColorClassifier (outdoor-optimized).
    use_lab : bool
        If True (default), use LABColorClassifier. Falls back to HSVColorClassifier.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        backend: str = "auto",
        confidence_threshold: float = 0.5,
        color_classifier: Optional[object] = None,
        use_lab: bool = True,
    ) -> None:
        self.backend = backend
        self.confidence_threshold = confidence_threshold

        # Auto-detect backend
        if self.backend == "auto":
            if model_path.endswith(".mlpackage"):
                self.backend = "coreml"
            else:
                self.backend = "mps"  # Apple Silicon GPU as default for .pt

        # Color classifier
        if color_classifier is not None:
            self.color_classifier = color_classifier
        elif use_lab:
            self.color_classifier = LABColorClassifier()
        else:
            self.color_classifier = HSVColorClassifier()

        # Load model
        self.model = YOLO(model_path)

        # CoreML-specific config for Apple ANE
        if self.backend == "coreml":
            logger.info("Using CoreML backend — auto-routes to Apple Neural Engine")
            # CoreML model auto-routes to ANE via coremltools

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection on a BGR frame and return person detections only.

        The backend selection:
          - 'coreml': model() auto-uses ANE on M3
          - 'mps': model(device='mps') uses Metal GPU
          - 'cpu': model(device='cpu') uses CPU

        YOLOv11n on M3:
          - CoreML FP16 ANE: 110-130 FPS
          - MPS (GPU): 50-60 FPS
          - CPU: 21 FPS
        """
        if self.backend == "coreml":
            results = self.model(frame, verbose=False)
        elif self.backend == "mps":
            results = self.model(frame, device="mps", verbose=False)
        else:
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
        """Extract torso region and run color classifier.

        Torso extraction:
          - Upper-middle of bounding box (shoulders to chest)
          - Avoids legs (won't have jersey color) and head (skin tone)
        """
        x1, y1, x2, y2 = bbox
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
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example: Use CoreML .mlpackage on MacBook M3
    # detector = PersonDetector(model_path="yolo11n.mlpackage", backend="coreml")

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
