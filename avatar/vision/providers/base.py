"""Base protocols and data classes for vision providers.

This module defines the core protocols that all vision providers must implement,
including CameraProvider (frame capture) and DetectorProvider (object detection).

Design Philosophy:
-----------------
1. Async-first: All capture/detect operations are async for non-blocking I/O.
2. Protocol-based: Structural typing allows flexible implementations.
3. Immutable data: Frame and Detection are frozen dataclasses for safety.
4. Backend-agnostic: Protocols hide implementation details (RTSP, RealSense, etc.)

Example:
    >>> from avatar.vision.providers.base import CameraProvider, DetectorProvider
    >>> from typing import runtime_checkable
    >>> import numpy as np
    >>>
    >>> class MyCamera:
    ...     backend_name = "my_camera"
    ...     async def capture_frame(self) -> Frame:
    ...         return Frame(np.zeros((480, 640, 3), dtype=np.uint8))
    >>>
    >>> isinstance(MyCamera(), CameraProvider)  # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

import numpy as np


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class Frame:
    """Immutable frame container with capture metadata.

    Wraps a numpy array with timestamp and optional metadata. The frozen
    dataclass ensures frames cannot be accidentally modified after capture.

    Attributes:
        data: Raw pixel data as numpy array (H, W, C) with dtype uint8.
              Format is RGB (not BGR like OpenCV default).
        timestamp: Unix timestamp of frame capture (seconds).
        metadata: Optional dictionary with additional frame info
                  (e.g., exposure, gain, camera serial).

    Example:
        >>> frame = Frame(np.zeros((480, 640, 3), dtype=np.uint8))
        >>> frame.timestamp  # Auto-populated
        1716000000.123
        >>> frame.data.shape
        (480, 640, 3)
    """

    data: np.ndarray
    timestamp: float = field(default_factory=time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        """Return frame height in pixels."""
        return self.data.shape[0]

    @property
    def width(self) -> int:
        """Return frame width in pixels."""
        return self.data.shape[1]

    @property
    def channels(self) -> int:
        """Return number of color channels (typically 3 for RGB)."""
        return self.data.shape[2] if len(self.data.shape) > 2 else 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize frame info (not raw data) to dictionary."""
        return {
            "shape": self.data.shape,
            "dtype": str(self.data.dtype),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class Detection:
    """Immutable detection result with bounding box and metadata.

    Represents a single object detection with normalized bounding box
    coordinates (0-1 range relative to image dimensions), confidence
    score, and optional class information.

    Bounding Box Format:
    -------------------
    [x, y, width, height] where:
    - x, y: Top-left corner coordinates (0.0 = left/top, 1.0 = right/bottom)
    - width, height: Box dimensions (0.0 to 1.0)

    This normalization is resolution-independent and matches YOLO output.

    Attributes:
        label: Class label string (e.g., "person", "vehicle", "drone").
        confidence: Detection confidence score (0.0 to 1.0).
        bbox: Normalized bounding box [x, y, w, h] in 0-1 range.
        class_id: Optional numeric class ID for the label.
        metadata: Optional dict with extra info (e.g., tracking ID, depth).

    Example:
        >>> det = Detection("person", 0.95, [0.25, 0.3, 0.1, 0.15], class_id=0)
        >>> det.center_point()
        (0.3, 0.375)
        >>> det.to_pixel_coords(640, 480)
        (160, 144, 64, 72)
    """

    label: str
    confidence: float
    bbox: List[float]  # [x, y, width, height] normalized 0-1
    class_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_pixel_coords(
        self, image_width: int, image_height: int
    ) -> Tuple[int, int, int, int]:
        """Convert normalized bbox to pixel coordinates.

        Args:
            image_width: Source image width in pixels.
            image_height: Source image height in pixels.

        Returns:
            Tuple of (x, y, width, height) in pixel coordinates.
        """
        x = int(self.bbox[0] * image_width)
        y = int(self.bbox[1] * image_height)
        w = int(self.bbox[2] * image_width)
        h = int(self.bbox[3] * image_height)
        return (x, y, w, h)

    def center_point(self) -> Tuple[float, float]:
        """Get center point of bounding box in normalized coordinates.

        Returns:
            Tuple of (center_x, center_y) in 0-1 range.
        """
        center_x = self.bbox[0] + self.bbox[2] / 2
        center_y = self.bbox[1] + self.bbox[3] / 2
        return (center_x, center_y)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize detection to dictionary."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "class_id": self.class_id,
            "metadata": self.metadata,
        }


# =============================================================================
# Protocol Classes
# =============================================================================


@runtime_checkable
class CameraProvider(Protocol):
    """Protocol for camera frame capture providers.

    Implementations must provide async frame capture and connection management.
    All camera backends (RTSP, RealSense, Gazebo, mock) implement this protocol.

    WHY ASYNC CAPTURE:
    -----------------
    Camera I/O is inherently blocking (network for RTSP, USB for RealSense).
    Async capture allows the drone control loop to continue while waiting
    for frames, preventing control latency.

    BACKEND NAME:
    ------------
    Each implementation must define a unique backend_name for registry
    lookup and configuration selection.

    Example Implementation:
        >>> class RtspCameraProvider:
        ...     backend_name = "rtsp"
        ...
        ...     async def connect(self) -> bool:
        ...         # Connect to RTSP stream
        ...         return True
        ...
        ...     async def disconnect(self) -> None:
        ...         # Cleanup resources
        ...         pass
        ...
        ...     async def capture_frame(self) -> Frame:
        ...         # Capture and return frame
        ...         return Frame(np.zeros((480, 640, 3), dtype=np.uint8))
        ...
        ...     @property
        ...     def is_connected(self) -> bool:
        ...         return True
        ...
        ...     def get_info(self) -> dict:
        ...         return {"backend": self.backend_name}
    """

    backend_name: str

    async def connect(self) -> bool:
        """Establish connection to camera source.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            CameraError: If connection fails critically.
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from camera and cleanup resources."""
        ...

    async def capture_frame(self) -> Frame:
        """Capture a single frame from the camera.

        Returns:
            Frame object with image data and metadata.

        Raises:
            CameraError: If frame capture fails.
        """
        ...

    @property
    def is_connected(self) -> bool:
        """Check if camera is connected and ready."""
        ...

    def get_info(self) -> Dict[str, Any]:
        """Get camera information and configuration.

        Returns:
            Dictionary with backend name, resolution, and settings.
        """
        ...


@runtime_checkable
class DetectorProvider(Protocol):
    """Protocol for object detection providers.

    Implementations must provide async detection on frames with configurable
    confidence thresholds. All detector backends (YOLO, mock, custom) implement
    this protocol.

    WHY ASYNC DETECT:
    ----------------
    Neural network inference can take 10-100ms. Async detection allows
    frame capture to continue in parallel, improving pipeline throughput.

    BACKEND NAME:
    ------------
    Each implementation must define a unique backend_name for registry
    lookup and configuration selection.

    Example Implementation:
        >>> class YoloDetectorProvider:
        ...     backend_name = "yolo"
        ...
        ...     async def initialize(self) -> bool:
        ...         # Load model weights
        ...         return True
        ...
        ...     async def detect(self, frame: Frame) -> List[Detection]:
        ...         # Run inference and return detections
        ...         return [Detection("person", 0.9, [0.5, 0.5, 0.1, 0.1])]
        ...
        ...     @property
        ...     def is_initialized(self) -> bool:
        ...         return True
        ...
        ...     def get_info(self) -> dict:
        ...         return {"backend": self.backend_name, "model": "yolov8n"}
    """

    backend_name: str

    async def initialize(self) -> bool:
        """Initialize detector (load model weights, allocate resources).

        Returns:
            True if initialization successful, False otherwise.

        Raises:
            DetectorError: If initialization fails critically.
        """
        ...

    async def detect(self, frame: Frame) -> List[Detection]:
        """Detect objects in the given frame.

        Args:
            frame: Frame object containing image data.

        Returns:
            List of Detection objects, sorted by confidence (highest first).

        Raises:
            DetectorError: If detection fails.
        """
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if detector is initialized and ready."""
        ...

    def get_info(self) -> Dict[str, Any]:
        """Get detector information and configuration.

        Returns:
            Dictionary with backend name, model, and settings.
        """
        ...

    @property
    def class_names(self) -> List[str]:
        """Return list of class names this detector can detect."""
        ...


@runtime_checkable
class VisionProvider(Protocol):
    """Combined protocol for vision systems with camera and detector.

    Some vision systems (e.g., OAK-D) combine camera and detector in one
    device. This protocol represents such integrated systems.

    Example:
        >>> class OakVisionProvider:
        ...     backend_name = "oak"
        ...
        ...     async def initialize(self) -> bool:
        ...         return True
        ...
        ...     async def capture_and_detect(self) -> Tuple[Frame, List[Detection]]:
        ...         frame = Frame(np.zeros((480, 640, 3), dtype=np.uint8))
        ...         dets = [Detection("person", 0.9, [0.5, 0.5, 0.1, 0.1])]
        ...         return (frame, dets)
        ...
        ...     @property
        ...     def is_ready(self) -> bool:
        ...         return True
    """

    backend_name: str

    async def initialize(self) -> bool:
        """Initialize the combined vision system.

        Returns:
            True if initialization successful.
        """
        ...

    async def capture_and_detect(self) -> Tuple[Frame, List[Detection]]:
        """Capture frame and run detection in one operation.

        For integrated systems, this can be more efficient than
        separate capture + detect calls.

        Returns:
            Tuple of (Frame, List[Detection]).
        """
        ...

    @property
    def is_ready(self) -> bool:
        """Check if the vision system is ready."""
        ...


# =============================================================================
# Provider Config
# =============================================================================


@dataclass(frozen=True)
class CameraConfig:
    """Configuration for camera providers.

    Attributes:
        width: Target frame width in pixels.
        height: Target frame height in pixels.
        fps: Target frame rate (frames per second).
        source: Source identifier (URL, device ID, topic name).
        params: Backend-specific parameters.
    """

    width: int = 640
    height: int = 480
    fps: float = 30.0
    source: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DetectorConfig:
    """Configuration for detector providers.

    Attributes:
        model: Model name or path to weights.
        confidence_threshold: Minimum confidence for detections.
        backend: Detector backend ("ultralytics", "ncnn", "openvino").
        classes: Optional list of classes to detect (None = all).
        params: Backend-specific parameters.
    """

    model: str = "yolov8n"
    confidence_threshold: float = 0.5
    backend: str = "ultralytics"
    classes: Optional[List[str]] = None
    params: Dict[str, Any] = field(default_factory=dict)
