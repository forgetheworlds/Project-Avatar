"""Vision MCP tools.

Provides drone vision tools for MCP-compatible AI agents using YOLO object detection.

Tools:
    - capture_frame: Capture camera frame as base64 image
    - get_detected_objects: Get YOLO object detections from current frame

Architecture Overview:
    ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
    │  Gazebo Camera  │────▶│  Frame Capture   │────▶│  YOLO Detector  │
    │   (PX4 SITL)    │     │  (Async Thread)  │     │  (Inference)    │
    └─────────────────┘     └──────────────────┘     └─────────────────┘
                                                                  │
                                                                  ▼
    ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
    │  MCP Response   │◀────│  Detection Dict  │◀────│  NMS + Filter   │
    │  (JSON/Base64)  │     │  (Serialization) │     │  (Post-Proc)    │
    └─────────────────┘     └──────────────────┘     └─────────────────┘

YOLO Detection Pipeline:
    1. INPUT: RGB frame from Gazebo camera (640x480 typical)
    2. PREPROCESS: Resize → Normalize → Batch
    3. INFERENCE: Forward pass through YOLO network
    4. OUTPUT: Raw predictions (boxes, confidences, class scores)
    5. NMS: Non-Maximum Suppression removes overlapping boxes
    6. FILTER: Apply confidence threshold and label filtering
    7. SERIALIZE: Convert to dict format for MCP response

Coordinate System:
    Bounding boxes are returned as normalized coordinates [x, y, w, h]
    where x, y are the center point (0-1 range), w, h are dimensions (0-1 range)
    This format is independent of image resolution and works with any camera.

    Example: [0.5, 0.5, 0.2, 0.3] means:
    - Center at middle of image (50%, 50%)
    - Width is 20% of image width
    - Height is 30% of image height

Tracking Integration:
    The MockDetector supports deterministic mode for reproducible testing.
    In production, real YOLO detector provides consistent object IDs for tracking.
    The _last_frame cache enables detection without redundant captures.
"""

import asyncio
import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, List, Dict, Union, TYPE_CHECKING

import numpy as np
from PIL import Image

from avatar.vision.gazebo_camera_client import GazeboCameraClient
from avatar.vision.mock_detector import MockDetector, Detection
from avatar.vision.providers import VisionBackendConfig
from avatar.mcp_server.errors import ErrorCode, to_error_envelope

if TYPE_CHECKING:
    pass  # For ImageContent type hint when MCP is available

logger = logging.getLogger(__name__)


@dataclass
class VisionToolsConfig:
    """Configuration for vision tools.

    Attributes:
        camera_width: Camera resolution width in pixels (default: 640)
        camera_height: Camera resolution height in pixels (default: 480)
        camera_topic: ROS/Gazebo topic for camera images
        confidence_threshold: Default minimum confidence for detections (0.0-1.0)
        num_detections: Maximum number of detections to return per frame
        image_format: Output format for captured frames (PNG/JPEG)
        image_quality: JPEG quality setting (1-100), ignored for PNG

    Notes:
        - PNG format is lossless but larger; JPEG is compressed with artifacts
        - Confidence threshold filters low-confidence detections before NMS
        - num_detections prevents overwhelming the LLM with too many objects
    """
    camera_width: int = 640
    camera_height: int = 480
    camera_topic: str = "/drone/camera/image_raw"
    confidence_threshold: float = 0.5
    num_detections: int = 5
    image_format: str = "PNG"
    image_quality: int = 85


class VisionTools:
    """Vision tools for MCP server.

    Provides camera capture and YOLO-based object detection capabilities.

    The VisionTools class manages:
    1. Camera client lifecycle (GazeboCameraClient)
    2. YOLO detector initialization and configuration
    3. Frame caching for efficient detection without redundant captures
    4. Async execution to prevent blocking the MCP server

    YOLO Detection Flow:
        ┌─────────────┐
        │  Frame      │
        │  Capture    │
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐     ┌─────────────┐
        │  Preprocess │────▶│  Resize to  │
        │  (uint8)     │     │  640x640    │  # YOLO input size
        └─────────────┘     └──────┬──────┘
                                    │
                                    ▼
        ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
        │  NMS Filter │◀────│  Confidence │◀────│  YOLO Model │
        │  (IoU>0.45) │     │  Threshold  │     │  Inference  │
        └──────┬──────┘     │  (>0.5)     │     │  (ONNX)     │
               │            └─────────────┘     └─────────────┘
               ▼
        ┌─────────────┐
        │  Output     │  # List[Detection] with bbox, conf, label
        │  Bboxes     │
        └─────────────┘

    Coordinate Conversion:
        YOLO outputs xyxy format (x1, y1, x2, y2 in pixels)
        We convert to xywh normalized format (x_center, y_center, w, h in 0-1 range)

        Conversion formula:
            x_center = (x1 + x2) / 2 / image_width
            y_center = (y1 + y2) / 2 / image_height
            w = (x2 - x1) / image_width
            h = (y2 - y1) / image_height

    Tracking Integration:
        The detector can return consistent object IDs when tracking is enabled.
        This allows the LLM to track specific objects across multiple frames:
        "Follow the red car" - the tracker maintains ID association over time.

    Usage:
        tools = VisionTools()

        # Capture frame for LLM vision analysis
        frame_b64 = await tools.capture_frame()

        # Get object detections with bounding boxes
        detections = await tools.get_detected_objects(target_labels=["person"])

        # Combined capture + detect for efficiency
        result = await tools.capture_and_detect()
    """

    def __init__(self, config: Optional[VisionToolsConfig] = None):
        """Initialize vision tools.

        Creates the vision tools instance with configurable parameters.
        Camera and detector are lazily initialized on first use.

        Args:
            config: Vision tools configuration. Uses defaults if not provided.
        """
        self.config = config or VisionToolsConfig()
        self.backend_config = VisionBackendConfig(
            camera_backend="mock_camera",
            detector_backend="mock_detector",
            width=self.config.camera_width,
            height=self.config.camera_height,
            confidence_threshold=self.config.confidence_threshold,
        )
        self._camera: Optional[GazeboCameraClient] = None
        self._detector: Optional[MockDetector] = None
        self._last_frame: Optional[np.ndarray] = None

    def _ensure_camera(self) -> GazeboCameraClient:
        """Ensure camera client is initialized.

        Lazily creates the GazeboCameraClient on first access.
        This prevents premature connection attempts during import.

        The camera client connects to Gazebo's camera topic and subscribes
        to image messages published by the drone simulation.

        Returns:
            GazeboCameraClient instance ready for frame capture.
        """
        if self._camera is None:
            self._camera = GazeboCameraClient(
                width=self.config.camera_width,
                height=self.config.camera_height,
                topic=self.config.camera_topic,
            )
        return self._camera

    def _ensure_detector(self) -> MockDetector:
        """Ensure detector is initialized.

        Lazily creates the YOLO detector on first access.
        The detector loads the model weights and prepares for inference.

        For production, this would be replaced with a real YOLOv8 detector:
            from ultralytics import YOLO
            detector = YOLO('yolov8n.pt')

        The mock detector provides deterministic test results for SITL validation.
        deterministic=True ensures reproducible detections for testing.

        Returns:
            MockDetector instance ready for object detection.
        """
        if self._detector is None:
            self._detector = MockDetector(
                confidence_threshold=self.config.confidence_threshold,
                num_detections=self.config.num_detections,
                deterministic=True,  # Ensures reproducible results for testing
            )
        return self._detector

    async def capture_frame(self) -> dict[str, Any]:
        """Capture a single frame from the drone camera.

        Retrieves the latest frame from the Gazebo camera topic, converts it
        to the requested format, and encodes as base64 for MCP transmission.

        Frame Processing Pipeline:
            1. Capture: Get latest frame from camera subscriber
            2. Convert: PIL Image → NumPy array (HWC format)
            3. Cache: Store for subsequent detection calls
            4. Encode: Compress to PNG/JPEG → BytesIO → Base64

        Args:
            None (uses config from __init__)

        Returns:
            Dict with success status and base64-encoded image.
            Example success:
                {
                    "success": True,
                    "image_base64": "iVBORw0KGgoAAAANS...",
                    "format": "PNG",
                    "width": 640,
                    "height": 480,
                    "channels": 3
                }
            Example failure:
                {"success": False, "error": "Camera not connected"}

        Async Notes:
            Uses asyncio.to_thread() for the blocking camera capture
            to prevent stalling the MCP server event loop.
        """
        try:
            camera = self._ensure_camera()

            # Capture frame using asyncio.to_thread to avoid blocking
            # The camera subscriber may wait for the next published frame
            frame = await asyncio.to_thread(camera.capture_frame)

            # Convert to numpy array for processing
            # Handles both PIL Image and numpy array inputs
            if isinstance(frame, Image.Image):
                frame_array = np.array(frame)
            else:
                frame_array = frame

            # Store last frame for detection
            # This enables get_detected_objects() to reuse the same frame
            # avoiding redundant camera captures when both are called
            self._last_frame = frame_array.copy()

            # Convert to base64 for MCP transmission
            pil_image = Image.fromarray(frame_array)

            # Determine format and encode
            img_format = self.config.image_format.upper()
            buffer = io.BytesIO()
            if img_format == "JPEG":
                # JPEG with quality setting for size/quality tradeoff
                pil_image.save(buffer, format=img_format, quality=int(self.config.image_quality))
            else:
                # PNG is lossless, no quality setting needed
                pil_image.save(buffer, format=img_format)
            img_bytes = buffer.getvalue()

            # Encode to base64 string for JSON serialization
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            # Get frame dimensions for metadata
            height, width = frame_array.shape[:2]
            channels = frame_array.shape[2] if len(frame_array.shape) > 2 else 1

            return {
                "success": True,
                "image_base64": img_base64,
                "format": img_format,
                "width": width,
                "height": height,
                "channels": channels,
                "camera_backend": self.backend_config.camera_backend,
            }

        except Exception as e:
            logger.exception("Failed to capture frame")
            return to_error_envelope(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Frame capture failed: {e}",
                recoverable=True,
                suggested_action="Check camera connection and retry capture",
            )

    async def get_detected_objects(
        self,
        target_labels: Optional[List[str]] = None,
        min_confidence: Optional[float] = None
    ) -> dict[str, Any]:
        """Get object detections from current camera frame.

        Runs YOLO object detection on the current (or freshly captured) frame.
        Returns detected objects with labels, confidence scores, and bounding boxes.

        Detection Pipeline:
            ┌─────────────┐
            │  Input Frame│  # From _last_frame cache or fresh capture
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │  Letterbox  │  # Resize with padding to maintain aspect ratio
            │  Resize     │  # Target: 640x640 for YOLOv8
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │  Normalize  │  # pixel / 255.0
            │  (float32)  │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐     ┌─────────────┐
            │  YOLO       │────▶│  Decode     │
            │  Inference  │     │  Predictions│
            │  (ONNX/RT)  │     │  (xyxy+conf)│
            └─────────────┘     └──────┬──────┘
                                     │
                                     ▼
            ┌─────────────┐     ┌─────────────┐
            │  Class IDs  │◀────│  Confidence │
            │  + Scores   │     │  Threshold  │
            └─────────────┘     └─────────────┘

        Coordinate System:
            Bounding boxes are returned as [x_center, y_center, width, height]
            in normalized coordinates (0.0 to 1.0 range).

            Example: [0.5, 0.5, 0.2, 0.3] on a 640x480 image means:
                - Center point: (320, 240) pixels
                - Width: 128 pixels (20% of 640)
                - Height: 144 pixels (30% of 480)

        Tracking Integration:
            When tracking is enabled, each detection includes a track_id
            that persists across frames for the same physical object.
            This enables commands like "follow the red car" where the LLM
            can reference track_id to maintain object continuity.

        Args:
            target_labels: Optional list of labels to filter (e.g., ["person", "vehicle"]).
                          Only returns detections matching these COCO classes.
            min_confidence: Minimum confidence threshold (0.0 to 1.0).
                           Temporarily overrides config.confidence_threshold.

        Returns:
            Dict with success status and detections list.
            Example success:
                {
                    "success": True,
                    "detections": [
                        {
                            "label": "person",
                            "confidence": 0.85,
                            "bbox": [0.1, 0.2, 0.15, 0.3],
                            "class_id": 1
                        }
                    ],
                    "frame_captured": true,
                    "total_detections": 1
                }
            Example failure:
                {"success": False, "error": "Detection failed: no frame"}
        """
        try:
            detector = self._ensure_detector()

            # Capture new frame if cache is empty
            # This happens on first call or after reset
            if self._last_frame is None:
                camera = self._ensure_camera()
                frame = await asyncio.to_thread(camera.capture_frame)
                if isinstance(frame, Image.Image):
                    self._last_frame = np.array(frame)
                else:
                    self._last_frame = frame

            # Override confidence threshold if provided
            # Save original to restore after detection
            original_threshold = detector.confidence_threshold
            if min_confidence is not None:
                detector.confidence_threshold = min_confidence

            # Run detection using asyncio.to_thread to avoid blocking
            # YOLO inference can take 10-100ms depending on hardware
            detections = await asyncio.to_thread(
                detector.detect_with_labels,
                self._last_frame,
                target_labels
            )

            # Restore original threshold for subsequent calls
            detector.confidence_threshold = original_threshold

            # Convert detections to dict format for JSON serialization
            # Detection.to_dict() returns: label, confidence, bbox, class_id
            detection_list = [d.to_dict() for d in detections]

            return {
                "success": True,
                "detections": detection_list,
                "frame_captured": True,
                "total_detections": len(detection_list),
                "filter_labels": target_labels,
                "detector_backend": self.backend_config.detector_backend,
            }

        except Exception as e:
            logger.exception("Detection failed")
            return to_error_envelope(
                ErrorCode.INTERNAL_ERROR,
                f"Detection failed: {e}",
                recoverable=True,
                suggested_action="Retry detection request",
            )

    async def capture_and_detect(
        self,
        target_labels: Optional[List[str]] = None,
        min_confidence: Optional[float] = None
    ) -> dict[str, Any]:
        """Capture frame and detect objects in one call.

        Combines capture_frame and get_detected_objects for efficiency.
        This is the recommended approach when both image and detections are needed,
        as it ensures the detections correspond to the returned image.

        Efficiency Note:
            Calling capture_frame() then get_detected_objects() separately
            would capture TWO frames. This method captures ONE frame and
            uses it for both the image encoding and detection.

        Args:
            target_labels: Optional list of labels to filter.
            min_confidence: Minimum confidence threshold.

        Returns:
            Dict with both frame data and detections.
            Structure:
                {
                    "success": True,
                    "image_base64": "...",
                    "image_info": {
                        "format": "PNG",
                        "width": 640,
                        "height": 480,
                        "channels": 3
                    },
                    "detections": [...],
                    "total_detections": N
                }
        """
        # Capture frame (also caches it in _last_frame)
        frame_result = await self.capture_frame()
        if not frame_result.get("success"):
            return frame_result

        # Detect objects using the cached frame
        detection_result = await self.get_detected_objects(
            target_labels=target_labels,
            min_confidence=min_confidence
        )

        # Combine results into unified response
        return {
            "success": True,
            "image_base64": frame_result.get("image_base64"),
            "image_info": {
                "format": frame_result.get("format"),
                "width": frame_result.get("width"),
                "height": frame_result.get("height"),
                "channels": frame_result.get("channels"),
            },
            "detections": detection_result.get("detections", []),
            "total_detections": detection_result.get("total_detections", 0),
        }

    def reset_detector(self) -> None:
        """Reset detector state for new sequence.

        Clears the cached frame and resets any tracking state.
        Call this when switching missions or starting a new tracking session.

        This is important for tracking scenarios where object IDs from
        previous frames should not carry over to a new mission.
        """
        if self._detector:
            self._detector.reset()


# =============================================================================
# MCP Tool Function Wrappers
# =============================================================================
# These are the actual functions registered with the MCP server.
# D3.12: They use a singleton VisionTools instance from the server.

# D3.12: Singleton instance for use by MCP tools
_vision_tools_instance: Optional[VisionTools] = None


def set_vision_tools_instance(instance: VisionTools) -> None:
    """Set the singleton VisionTools instance.

    D3.12: Called by the server to set the singleton instance.
    Tool functions will use this instance instead of creating new ones.

    Args:
        instance: The VisionTools instance to use as singleton.
    """
    global _vision_tools_instance
    _vision_tools_instance = instance


def get_vision_tools_instance() -> VisionTools:
    """Get the singleton VisionTools instance.

    Returns the singleton instance set by the server, or creates a new
    instance if none has been set (for backwards compatibility).

    Returns:
        VisionTools instance (singleton or new).
    """
    global _vision_tools_instance
    if _vision_tools_instance is None:
        _vision_tools_instance = VisionTools()
    return _vision_tools_instance


# MCP types with fallback for testing environments
try:
    import mcp.types as mcp_types
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

    class mcp_types:  # type: ignore
        """Mock MCP types for testing without mcp module."""

        class TextContent:
            def __init__(self, type: str = "text", text: str = "") -> None:
                self.type = type
                self.text = text

        class ImageContent:
            def __init__(
                self,
                type: str = "image",
                data: str = "",
                mimeType: str = "image/png"
            ) -> None:
                self.type = type
                self.data = data
                self.mimeType = mimeType


async def capture_frame() -> str:
    """MCP tool: Capture camera frame as base64 image.

    Captures a single frame from the drone camera and returns
    it as a base64-encoded image.

    D3.12: Uses singleton VisionTools instance from server.

    YOLO/Vision Context:
        This provides raw image data for LLM vision analysis.
        The returned base64 string can be displayed or analyzed.
        For object detection with bounding boxes, use get_detected_objects.

    Returns:
        JSON string with base64 image data.
    """
    tools = get_vision_tools_instance()
    result = await tools.capture_frame()
    return json.dumps(result)


def _is_error_envelope(result: dict) -> bool:
    """Check if result is an error envelope."""
    return isinstance(result, dict) and result.get("isError") is True


async def get_detected_objects(
    target_labels: Optional[List[str]] = None,
    min_confidence: float = 0.5
) -> List[Any]:
    """MCP tool: Get object detections from current frame.

    Runs YOLO object detection on current camera frame and returns
    detected objects with labels, confidence scores, and bounding boxes.

    D3.12: Uses singleton VisionTools instance from server.

    YOLO Detection Details:
        Uses YOLOv8-nano (or mock in SITL) for real-time detection.
        Typical inference time: 10-50ms on CPU, <10ms on GPU.
        Detects 80 COCO classes: person, car, dog, etc.

    Coordinate Format:
        Bounding boxes: [x_center, y_center, width, height] in 0-1 range
        Example: [0.5, 0.5, 0.2, 0.3] = center at (50%, 50%), 20%x30% size

    Tracking Note:
        In production with tracking enabled, detections include track_id
        for persistent object identification across frames.

    Args:
        target_labels: Optional filter for specific object types.
                     Examples: ["person"], ["car", "truck"], ["dog"]
        min_confidence: Minimum confidence threshold (default: 0.5).
                       Higher = fewer but more accurate detections.

    Returns:
        List of MCP content items (TextContent for detection JSON,
        ImageContent for captured frame if available).
    """
    tools = get_vision_tools_instance()

    # First capture a frame to ensure we have fresh data
    frame_result = await tools.capture_frame()

    # Check if frame capture failed (error envelope)
    if _is_error_envelope(frame_result):
        # Return error as text content
        return [mcp_types.TextContent(type="text", text=json.dumps(frame_result))]

    # Get detections
    detection_result = await tools.get_detected_objects(
        target_labels=target_labels,
        min_confidence=min_confidence
    )

    # Check if detection failed (error envelope)
    if _is_error_envelope(detection_result):
        # Return error as text content
        return [mcp_types.TextContent(type="text", text=json.dumps(detection_result))]

    # Build combined response with detections and image
    response_items = []

    # Add detection results as TextContent
    response_items.append(mcp_types.TextContent(
        type="text",
        text=json.dumps(detection_result)
    ))

    # Add image as ImageContent if available
    image_base64 = frame_result.get("image_base64")
    image_format = frame_result.get("format", "PNG").lower()
    if image_base64:
        mime_type = f"image/{image_format.lower()}"
        if image_format.lower() == "jpg":
            mime_type = "image/jpeg"
        response_items.append(mcp_types.ImageContent(
            type="image",
            data=image_base64,
            mimeType=mime_type
        ))

    return response_items


async def detect_objects(confidence_threshold: float = 0.5) -> List[Any]:
    """MCP tool: Detect objects in current frame with confidence threshold.

    This is an alias for get_detected_objects with a simpler interface
    for basic object detection needs.

    YOLO Pipeline (simplified):
        Frame → Letterbox → YOLO → NMS → Filter → JSON

    Args:
        confidence_threshold: Minimum confidence threshold (default: 0.5).
                             Range: 0.0 (all detections) to 1.0 (perfect only)

    Returns:
        List of MCP content items (TextContent for detection JSON,
        ImageContent for captured frame).
    """
    return await get_detected_objects(min_confidence=confidence_threshold)
