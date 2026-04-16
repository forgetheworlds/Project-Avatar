"""Mock detector for testing vision pipeline.

Provides deterministic mock detections for testing the vision pipeline
without requiring actual object detection models or real camera input.

YOLO Detection Overview:
------------------------
YOLO (You Only Look Once) is a real-time object detection algorithm that:
1. Divides the image into a grid (e.g., 13x13, 26x26, or 52x52 cells)
2. Each grid cell predicts multiple bounding boxes with confidence scores
3. Each bounding box includes: (x, y, width, height, confidence, class probabilities)
4. Non-Maximum Suppression (NMS) removes overlapping detections
5. Final output: List of detections with label, confidence, and bbox coordinates

Mock vs Real Detection:
----------------------
This mock detector simulates YOLO output format for testing purposes:
- Real YOLO: Runs neural network inference on GPU/CPU
- Mock: Generates deterministic fake detections based on frame content
- Use mock for: Unit tests, CI/CD, development without GPU
- Use real for: Production, accuracy validation, real-world missions

Coordinate System:
-----------------
Bounding boxes are normalized to 0-1 range (relative to image dimensions):
- x, y: Top-left corner of bounding box (0.0 = left/top edge, 1.0 = right/bottom edge)
- width, height: Size of bounding box (0.0 to 1.0)
- This normalization makes detections resolution-independent
- To convert to pixel coordinates: pixel_x = x * image_width

Example:
    bbox = [0.25, 0.3, 0.1, 0.15] means:
    - Top-left at 25% from left, 30% from top
    - Width = 10% of image width, Height = 15% of image height
"""

from typing import List, Dict, Any, Optional, Union, Tuple, ClassVar
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass
class Detection:
    """Represents a single object detection result.

    This dataclass mirrors the output format of YOLO and other object detectors.
    In a real YOLO implementation, this would be populated from neural network
    inference results.

    Attributes:
        label: Class label of detected object (e.g., "person", "vehicle", "drone").
               In real YOLO, this comes from the COCO dataset classes (80 classes)
               or custom trained classes.
        confidence: Detection confidence score (0.0 to 1.0).
                      Real YOLO: Output from sigmoid activation on class probabilities.
                      Higher values = more confident prediction.
        bbox: Bounding box as [x, y, width, height] normalized to 0-1.
              Format is [top-left-x, top-left-y, width, height] in relative coords.
              Real YOLO predicts offsets from anchor boxes, then applies sigmoid.
        class_id: Numeric class ID matching the label.
                  In COCO: person=0, bicycle=1, car=2, etc.
                  For custom models: depends on training data.

    Coordinate Transformation Example:
        >>> detection = Detection("person", 0.95, [0.5, 0.5, 0.2, 0.3], 0)
        >>> # Convert normalized bbox to pixel coordinates for 640x480 image:
        >>> image_width, image_height = 640, 480
        >>> x_pixel = detection.bbox[0] * image_width      # 320
        >>> y_pixel = detection.bbox[1] * image_height     # 240
        >>> w_pixel = detection.bbox[2] * image_width      # 128
        >>> h_pixel = detection.bbox[3] * image_height     # 144
        >>> # Result: person detected at (320, 240) with size 128x144 pixels
    """
    label: str
    confidence: float
    bbox: List[float]  # [x, y, width, height] normalized 0-1
    class_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert detection to dictionary representation.

        Useful for serialization (JSON logging, API responses, telemetry).
        Real YOLO outputs are often converted to this format for downstream processing.
        """
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "class_id": self.class_id
        }

    def to_pixel_coords(self, image_width: int, image_height: int) -> Tuple[int, int, int, int]:
        """Convert normalized bbox to pixel coordinates.

        Args:
            image_width: Width of the source image in pixels.
            image_height: Height of the source image in pixels.

        Returns:
            Tuple of (x, y, width, height) in pixel coordinates.

        Example:
            >>> d = Detection("person", 0.9, [0.5, 0.5, 0.2, 0.2], 0)
            >>> d.to_pixel_coords(640, 480)
            (320, 240, 128, 96)
        """
        x = int(self.bbox[0] * image_width)
        y = int(self.bbox[1] * image_height)
        w = int(self.bbox[2] * image_width)
        h = int(self.bbox[3] * image_height)
        return (x, y, w, h)

    def center_point(self) -> Tuple[float, float]:
        """Get the center point of the bounding box.

        Returns:
            Tuple of (center_x, center_y) in normalized coordinates (0-1).
            Useful for tracking - drone can aim at object center.

        Example:
            >>> d = Detection("target", 0.9, [0.4, 0.3, 0.2, 0.2], 0)
            >>> d.center_point()
            (0.5, 0.4)  # Center of the bbox
        """
        center_x = self.bbox[0] + self.bbox[2] / 2
        center_y = self.bbox[1] + self.bbox[3] / 2
        return (center_x, center_y)


class MockDetector:
    """Mock object detector for testing purposes.

    This class simulates a YOLO-style object detector without requiring:
    - GPU/CPU neural network inference
    - Model weights (e.g., yolov8n.pt)
    - PyTorch/TensorFlow dependencies
    - Real camera input

    Mock vs Real YOLO Comparison:
    -----------------------------
    | Aspect        | MockDetector                    | Real YOLO (e.g., YOLOv8)      |
    |---------------|----------------------------------|-------------------------------|
    | Inference     | Deterministic generation         | Neural network forward pass   |
    | Speed         | Instant (~0.001s)                | ~10-50ms depending on model   |
    | Accuracy      | Perfect for testing              | Depends on training data      |
    | Dependencies  | numpy, PIL                       | torch, torchvision, ultralytics|
    | GPU Required  | No                               | Optional but recommended      |
    | Use Case      | Testing, CI/CD, development      | Production, real missions     |

    Deterministic Detection Generation:
    ----------------------------------
    The mock generates detections based on frame content hash:
    1. Compute hash from frame pixel statistics (mean values)
    2. Use hash as random seed for reproducibility
    3. Generate bounding boxes and confidences from seeded random
    4. Same input frame = same detections (deterministic)

    This is useful for:
    - Unit tests: Verify pipeline handles detections correctly
    - Integration tests: Test vision -> navigation integration
    - CI/CD: Run tests without GPU/model dependencies
    - Development: Work on downstream components without vision setup

    Example:
        >>> detector = MockDetector()
        >>> frame = np.zeros((480, 640, 3), dtype=np.uint8)
        >>> detections = detector.detect(frame)
        >>> len(detections) > 0
        True
        >>> # Access first detection
        >>> det = detections[0]
        >>> print(f"Detected: {det.label} at {det.bbox} with confidence {det.confidence}")
    """

    # Predefined detection classes for testing
    # In real YOLO, these would come from the model's training dataset
    # COCO dataset has 80 classes: person, car, airplane, etc.
    # Custom drone model might have: drone, person, vehicle, landing_pad
    DETECTION_CLASSES: ClassVar[List[Dict[str, Any]]] = [
        {"label": "person", "class_id": 1},
        {"label": "vehicle", "class_id": 2},
        {"label": "object", "class_id": 3},
    ]

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        num_detections: int = 3,
        deterministic: bool = True
    ):
        """Initialize the mock detector.

        Args:
            confidence_threshold: Minimum confidence for detections (0.0 to 1.0).
                                  Real YOLO typically uses 0.25-0.5.
                                  Lower = more detections but more false positives.
                                  Higher = fewer but more confident detections.
            num_detections: Number of detections to generate per frame.
                            Real YOLO varies: 0 to 100+ depending on scene complexity.
            deterministic: If True, generate same detections for same input.
                           If False, random detections each call (for stress testing).
        """
        self.confidence_threshold = confidence_threshold
        self.num_detections = num_detections
        self.deterministic = deterministic
        self._detection_count = 0

    def detect(
        self,
        frame: Union[np.ndarray, Image.Image]
    ) -> List[Detection]:
        """Detect objects in the given frame.

        In real YOLO, this would:
        1. Preprocess frame (resize to model input size, e.g., 640x640)
        2. Normalize pixel values (0-255 -> 0-1 or -1 to 1)
        3. Run neural network forward pass
        4. Decode output tensors (objectness, class probs, bbox coords)
        5. Apply NMS to remove duplicates
        6. Scale bboxes back to original image size
        7. Filter by confidence threshold

        This mock skips all that and generates fake detections.

        Args:
            frame: Input image as numpy array (H, W, C) or PIL Image.
                   Real YOLO expects RGB format, specific input size.

        Returns:
            List of Detection objects, sorted by confidence (highest first).
            Empty list if no objects detected (or all below threshold).
        """
        # Convert PIL Image to numpy if needed
        # Real YOLO implementations typically work with numpy arrays or tensors
        if isinstance(frame, Image.Image):
            frame_array = np.array(frame)
        else:
            frame_array = frame

        self._detection_count += 1

        # Generate deterministic detections based on frame hash
        # This simulates how real YOLO would return consistent results
        # for the same input image
        if self.deterministic:
            seed = self._compute_frame_hash(frame_array)
        else:
            seed = self._detection_count

        return self._generate_detections(seed, frame_array.shape)

    def _compute_frame_hash(self, frame: np.ndarray) -> int:
        """Compute a hash value from frame content.

        Creates a deterministic seed from frame pixel values for reproducible
        detection generation. This mimics how real YOLO would return the same
        detections for identical frames.

        In production, you wouldn't need this - the neural network output
        is inherently deterministic given the same weights and input.

        Args:
            frame: Numpy array of frame pixels (H, W, C) or (H, W).

        Returns:
            Integer hash value (0-9999) used as random seed.
        """
        # Simple hash based on frame statistics
        # Uses mean values for simplicity and speed
        if frame.size == 0:
            return 0

        # Sum of means across channels, scaled to integer
        # For RGB image: average red, green, blue values across entire image
        # Different images will have different "fingerprints"
        if len(frame.shape) == 3:
            channel_means = frame.mean(axis=(0, 1))
            hash_val = int(sum(channel_means) * 100) % 10000
        else:
            hash_val = int(frame.mean() * 100) % 10000

        return hash_val

    def _generate_detections(
        self,
        seed: int,
        frame_shape: Tuple[int, ...]
    ) -> List[Detection]:
        """Generate mock detections based on seed.

        Creates deterministic detection results for testing. The bounding boxes
        are positioned pseudo-randomly but consistently for the same seed.

        Bounding Box Generation Strategy:
        --------------------------------
        - x position: Based on seed mod 100, spread across image width
        - y position: Based on seed + offset, varies per detection
        - width/height: Small variations to simulate different object sizes
        - All values clamped to valid 0-1 range

        Real YOLO Bounding Box Prediction:
        ---------------------------------
        - Predicts tx, ty (center offsets), tw, th (log-space dimensions)
        - Applies sigmoid to tx, ty to get 0-1 range
        - Exponentiates tw, th and multiplies by anchor box dimensions
        - Converts from grid-relative to image-relative coordinates

        Args:
            seed: Seed value for deterministic generation.
            frame_shape: Shape of the input frame (H, W, C) or (H, W).
                         Used to ensure bboxes fit within image bounds.

        Returns:
            List of Detection objects above confidence threshold.
        """
        detections = []
        height = frame_shape[0]
        width = frame_shape[1] if len(frame_shape) > 1 else frame_shape[0]

        # Generate detections using seed for determinism
        np.random.seed(seed)

        for i in range(self.num_detections):
            # Select class based on seed
            # Cycles through available classes (person, vehicle, object)
            class_info = self.DETECTION_CLASSES[i % len(self.DETECTION_CLASSES)]

            # Generate confidence above threshold
            # Real YOLO confidences come from sigmoid of network output
            # Range: typically 0.3-0.99 for true detections
            confidence = 0.6 + (seed % 10) / 100 + i * 0.05
            confidence = min(confidence, 0.99)

            # Generate bounding box (normalized 0-1)
            # Deterministic but varied based on seed and index
            # Strategy: spread detections across image, vary by frame content
            x = (seed % 100) / 200 + i * 0.1  # Left position, 0-0.5 range + spread
            y = ((seed + i * 17) % 100) / 200  # Top position, varies per detection
            w = 0.1 + (seed % 5) / 50  # Width: 0.1-0.2 of image
            h = 0.15 + ((seed + i) % 5) / 50  # Height: 0.15-0.25 of image

            # Clamp to valid range (ensure bbox stays within image)
            # x must be < 1.0 - width, y must be < 1.0 - height
            bbox = [
                min(max(x, 0.0), 1.0 - w),
                min(max(y, 0.0), 1.0 - h),
                min(w, 1.0),
                min(h, 1.0)
            ]

            detection = Detection(
                label=class_info["label"],
                confidence=round(confidence, 2),
                bbox=[round(v, 3) for v in bbox],
                class_id=class_info["class_id"]
            )

            # Only include detections above confidence threshold
            # This mimics real YOLO post-processing where low-confidence
            # predictions are filtered out before NMS
            if detection.confidence >= self.confidence_threshold:
                detections.append(detection)

        # Reset random seed to avoid affecting other code
        np.random.seed()

        # Sort by confidence (highest first) - matches YOLO behavior
        return sorted(detections, key=lambda d: d.confidence, reverse=True)

    def detect_with_labels(
        self,
        frame: Union[np.ndarray, Image.Image],
        target_labels: Optional[List[str]] = None
    ) -> List[Detection]:
        """Detect objects, optionally filtering by label.

        This is a common pattern in drone vision pipelines where you only
        care about specific object types (e.g., only track "person" or "drone").

        Real-world use cases:
        - Search and rescue: Only detect "person" class
        - Surveillance: Detect "vehicle" and "person" only
        - Package delivery: Detect "landing_pad" only
        - Collision avoidance: Detect "obstacle" classes

        Args:
            frame: Input image as numpy array or PIL Image.
            target_labels: If provided, only return detections with these labels.
                          Example: ["person", "vehicle"] to find only people and cars.

        Returns:
            Filtered list of Detection objects matching target labels.
        """
        all_detections = self.detect(frame)

        if target_labels is None:
            return all_detections

        return [d for d in all_detections if d.label in target_labels]

    @property
    def class_names(self) -> List[str]:
        """Return list of class names this detector can detect.

        In real YOLO, this comes from the model's class names file (e.g., coco.names).
        For custom models, this is defined during training.

        Returns:
            List of class label strings.
        """
        return [c["label"] for c in self.DETECTION_CLASSES]

    def reset(self) -> None:
        """Reset detection count for new sequence.

        Call this when starting a new video stream or mission to ensure
        consistent behavior. Useful for testing reproducibility.
        """
        self._detection_count = 0

    def __repr__(self) -> str:
        """Return string representation of the detector."""
        return (
            f"MockDetector(confidence_threshold={self.confidence_threshold}, "
            f"num_detections={self.num_detections}, deterministic={self.deterministic})"
        )
