"""Vision provider seam for mock, Gazebo, and hardware camera backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from avatar.vision.gazebo_camera_client import GazeboCameraClient
from avatar.vision.mock_detector import Detection, MockDetector


@dataclass(frozen=True)
class VisionBackendConfig:
    """Selected camera and detector backends for the current runtime."""

    camera_backend: str = "mock_camera"
    detector_backend: str = "mock_detector"
    width: int = 640
    height: int = 480
    confidence_threshold: float = 0.5


class MockCameraProvider:
    """Mock camera provider backed by deterministic generated frames."""

    backend_name = "mock_camera"

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.client = GazeboCameraClient(width=width, height=height)

    def capture_frame(self) -> np.ndarray:
        return self.client.capture_frame_as_numpy()


class MockDetectorProvider:
    """Mock detector provider backed by deterministic generated detections."""

    backend_name = "mock_detector"

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.detector = MockDetector(
            confidence_threshold=confidence_threshold,
            deterministic=True,
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        return self.detector.detect(frame)


class GazeboCameraProvider:
    """Boundary for future Gazebo camera transport integration."""

    backend_name = "gazebo_camera"

    def __init__(self, topic: str = "/drone/camera/image_raw") -> None:
        self.topic = topic

    def capture_frame(self) -> np.ndarray:
        raise RuntimeError(
            "gazebo_camera backend requires a Gazebo camera transport adapter. "
            "Use mock_camera until the Gazebo bridge is configured."
        )
