"""Mock detector for testing vision pipeline.

Provides deterministic mock detections for testing the vision pipeline
without requiring actual object detection models or real camera input.
"""

from typing import List, Dict, Any, Optional, Union, Tuple, ClassVar
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass
class Detection:
    """Represents a single object detection.

    Attributes:
        label: Class label of detected object.
        confidence: Detection confidence score (0.0 to 1.0).
        bbox: Bounding box as [x, y, width, height] normalized to 0-1.
        class_id: Numeric class ID.
    """
    label: str
    confidence: float
    bbox: List[float]  # [x, y, width, height] normalized 0-1
    class_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert detection to dictionary representation."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "class_id": self.class_id
        }


class MockDetector:
    """Mock object detector for testing purposes.

    Provides deterministic, reproducible detection results for testing
    the vision pipeline. Detections are generated based on frame content
    or can be configured for specific test scenarios.

    Example:
        >>> detector = MockDetector()
        >>> frame = np.zeros((480, 640, 3), dtype=np.uint8)
        >>> detections = detector.detect(frame)
        >>> len(detections) > 0
        True
    """

    # Predefined detection classes for testing
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
            confidence_threshold: Minimum confidence for detections.
            num_detections: Number of detections to generate per frame.
            deterministic: If True, generate same detections for same input.
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

        Generates mock detections for testing. The detections are
        deterministic based on frame content when deterministic=True.

        Args:
            frame: Input image as numpy array or PIL Image.

        Returns:
            List of Detection objects.
        """
        # Convert PIL Image to numpy if needed
        if isinstance(frame, Image.Image):
            frame_array = np.array(frame)
        else:
            frame_array = frame

        self._detection_count += 1

        # Generate deterministic detections based on frame hash
        if self.deterministic:
            seed = self._compute_frame_hash(frame_array)
        else:
            seed = self._detection_count

        return self._generate_detections(seed, frame_array.shape)

    def _compute_frame_hash(self, frame: np.ndarray) -> int:
        """Compute a hash value from frame content.

        Creates a deterministic seed from frame pixel values
        for reproducible detection generation.

        Args:
            frame: Numpy array of frame pixels.

        Returns:
            Integer hash value.
        """
        # Simple hash based on frame statistics
        # Uses mean values for simplicity and speed
        if frame.size == 0:
            return 0

        # Sum of means across channels, scaled to integer
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

        Creates deterministic detection results for testing.

        Args:
            seed: Seed value for deterministic generation.
            frame_shape: Shape of the input frame (H, W, C) or (H, W).

        Returns:
            List of Detection objects.
        """
        detections = []
        height = frame_shape[0]
        width = frame_shape[1] if len(frame_shape) > 1 else frame_shape[0]

        # Generate detections using seed for determinism
        np.random.seed(seed)

        for i in range(self.num_detections):
            # Select class based on seed
            class_info = self.DETECTION_CLASSES[i % len(self.DETECTION_CLASSES)]

            # Generate confidence above threshold
            confidence = 0.6 + (seed % 10) / 100 + i * 0.05
            confidence = min(confidence, 0.99)

            # Generate bounding box (normalized 0-1)
            # Deterministic but varied based on seed and index
            x = (seed % 100) / 200 + i * 0.1
            y = ((seed + i * 17) % 100) / 200
            w = 0.1 + (seed % 5) / 50
            h = 0.15 + ((seed + i) % 5) / 50

            # Clamp to valid range
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
            if detection.confidence >= self.confidence_threshold:
                detections.append(detection)

        # Reset random seed
        np.random.seed()

        return detections

    def detect_with_labels(
        self,
        frame: Union[np.ndarray, Image.Image],
        target_labels: Optional[List[str]] = None
    ) -> List[Detection]:
        """Detect objects, optionally filtering by label.

        Args:
            frame: Input image as numpy array or PIL Image.
            target_labels: If provided, only return detections with these labels.

        Returns:
            Filtered list of Detection objects.
        """
        all_detections = self.detect(frame)

        if target_labels is None:
            return all_detections

        return [d for d in all_detections if d.label in target_labels]

    @property
    def class_names(self) -> List[str]:
        """Return list of class names this detector can detect."""
        return [c["label"] for c in self.DETECTION_CLASSES]

    def reset(self) -> None:
        """Reset detection count for new sequence."""
        self._detection_count = 0

    def __repr__(self) -> str:
        """Return string representation of the detector."""
        return (
            f"MockDetector(confidence_threshold={self.confidence_threshold}, "
            f"num_detections={self.num_detections}, deterministic={self.deterministic})"
        )
