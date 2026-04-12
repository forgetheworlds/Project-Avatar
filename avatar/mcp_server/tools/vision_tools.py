"""Vision MCP tools.

Provides drone vision tools for MCP-compatible AI agents.

Tools:
    - capture_frame: Capture camera frame as base64 image
    - get_detected_objects: Get YOLO object detections from current frame
"""

import asyncio
import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, List, Dict, Union

import numpy as np
from PIL import Image

from avatar.vision.gazebo_camera_client import GazeboCameraClient
from avatar.vision.mock_detector import MockDetector, Detection

logger = logging.getLogger(__name__)


@dataclass
class VisionToolsConfig:
    """Configuration for vision tools."""
    camera_width: int = 640
    camera_height: int = 480
    camera_topic: str = "/drone/camera/image_raw"
    confidence_threshold: float = 0.5
    num_detections: int = 5
    image_format: str = "PNG"
    image_quality: int = 85


class VisionTools:
    """Vision tools for MCP server.

    Provides camera capture and object detection capabilities.

    Usage:
        tools = VisionTools()
        frame_b64 = await tools.capture_frame()
        detections = await tools.get_detected_objects()
    """

    def __init__(self, config: Optional[VisionToolsConfig] = None):
        """Initialize vision tools.

        Args:
            config: Vision tools configuration.
        """
        self.config = config or VisionToolsConfig()
        self._camera: Optional[GazeboCameraClient] = None
        self._detector: Optional[MockDetector] = None
        self._last_frame: Optional[np.ndarray] = None

    def _ensure_camera(self) -> GazeboCameraClient:
        """Ensure camera client is initialized.

        Returns:
            GazeboCameraClient instance.
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

        Returns:
            MockDetector instance.
        """
        if self._detector is None:
            self._detector = MockDetector(
                confidence_threshold=self.config.confidence_threshold,
                num_detections=self.config.num_detections,
                deterministic=True,
            )
        return self._detector

    async def capture_frame(self) -> dict[str, Any]:
        """Capture a single frame from the drone camera.

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
        """
        try:
            camera = self._ensure_camera()

            # Capture frame using asyncio.to_thread to avoid blocking
            frame = await asyncio.to_thread(camera.capture_frame)

            # Convert to numpy array for processing
            if isinstance(frame, Image.Image):
                frame_array = np.array(frame)
            else:
                frame_array = frame

            # Store last frame for detection
            self._last_frame = frame_array.copy()

            # Convert to base64
            pil_image = Image.fromarray(frame_array)

            # Determine format and encode
            img_format = self.config.image_format.upper()
            buffer = io.BytesIO()
            if img_format == "JPEG":
                pil_image.save(buffer, format=img_format, quality=int(self.config.image_quality))
            else:
                pil_image.save(buffer, format=img_format)
            img_bytes = buffer.getvalue()

            # Encode to base64
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            # Get frame dimensions
            height, width = frame_array.shape[:2]
            channels = frame_array.shape[2] if len(frame_array.shape) > 2 else 1

            return {
                "success": True,
                "image_base64": img_base64,
                "format": img_format,
                "width": width,
                "height": height,
                "channels": channels,
            }

        except Exception as e:
            logger.exception("Failed to capture frame")
            return {"success": False, "error": f"Frame capture failed: {e}"}

    async def get_detected_objects(
        self,
        target_labels: Optional[List[str]] = None,
        min_confidence: Optional[float] = None
    ) -> dict[str, Any]:
        """Get object detections from current camera frame.

        Captures a frame and runs object detection. Returns detected
        objects with labels, confidence scores, and bounding boxes.

        Args:
            target_labels: Optional list of labels to filter (e.g., ["person", "vehicle"]).
            min_confidence: Minimum confidence threshold (0.0 to 1.0).

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

            # Capture new frame if needed
            if self._last_frame is None:
                camera = self._ensure_camera()
                frame = await asyncio.to_thread(camera.capture_frame)
                if isinstance(frame, Image.Image):
                    self._last_frame = np.array(frame)
                else:
                    self._last_frame = frame

            # Override confidence threshold if provided
            original_threshold = detector.confidence_threshold
            if min_confidence is not None:
                detector.confidence_threshold = min_confidence

            # Run detection using asyncio.to_thread to avoid blocking
            detections = await asyncio.to_thread(
                detector.detect_with_labels,
                self._last_frame,
                target_labels
            )

            # Restore original threshold
            detector.confidence_threshold = original_threshold

            # Convert detections to dict format
            detection_list = [d.to_dict() for d in detections]

            return {
                "success": True,
                "detections": detection_list,
                "frame_captured": True,
                "total_detections": len(detection_list),
                "filter_labels": target_labels,
            }

        except Exception as e:
            logger.exception("Detection failed")
            return {"success": False, "error": f"Detection failed: {e}"}

    async def capture_and_detect(
        self,
        target_labels: Optional[List[str]] = None,
        min_confidence: Optional[float] = None
    ) -> dict[str, Any]:
        """Capture frame and detect objects in one call.

        Combines capture_frame and get_detected_objects for efficiency.

        Args:
            target_labels: Optional list of labels to filter.
            min_confidence: Minimum confidence threshold.

        Returns:
            Dict with both frame data and detections.
        """
        # Capture frame
        frame_result = await self.capture_frame()
        if not frame_result.get("success"):
            return frame_result

        # Detect objects
        detection_result = await self.get_detected_objects(
            target_labels=target_labels,
            min_confidence=min_confidence
        )

        # Combine results
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
        """Reset detector state for new sequence."""
        if self._detector:
            self._detector.reset()


# Tool function wrappers for MCP registration
async def capture_frame() -> str:
    """MCP tool: Capture camera frame as base64 image.

    Captures a single frame from the drone camera and returns
    it as a base64-encoded image.

    Returns:
        JSON string with base64 image data.
    """
    tools = VisionTools()
    result = await tools.capture_frame()
    return json.dumps(result)


async def get_detected_objects(
    target_labels: Optional[List[str]] = None,
    min_confidence: float = 0.5
) -> str:
    """MCP tool: Get object detections from current frame.

    Runs object detection on current camera frame and returns
    detected objects with labels, confidence, and bounding boxes.

    Args:
        target_labels: Optional filter for specific object types.
        min_confidence: Minimum confidence threshold (default: 0.5).

    Returns:
        JSON string with detection results.
    """
    tools = VisionTools()
    result = await tools.get_detected_objects(
        target_labels=target_labels,
        min_confidence=min_confidence
    )
    return json.dumps(result)


async def detect_objects(confidence_threshold: float = 0.5) -> str:
    """MCP tool: Detect objects in current frame with confidence threshold.

    This is an alias for get_detected_objects with a simpler interface
    for basic object detection needs.

    Args:
        confidence_threshold: Minimum confidence threshold (default: 0.5).

    Returns:
        JSON string with detection results.
    """
    return await get_detected_objects(min_confidence=confidence_threshold)
