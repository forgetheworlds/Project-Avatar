"""Vision provider seam for mock, Gazebo, and hardware camera backends.

This module re-exports from the providers package for backward compatibility.
New code should import directly from avatar.vision.providers package.

Backward Compatibility:
----------------------
The following legacy classes are maintained for existing code:
- VisionBackendConfig: Configuration dataclass
- MockCameraProvider: Mock camera (now wraps GazeboCameraProvider)
- MockDetectorProvider: Mock detector
- GazeboCameraProvider: Gazebo simulation camera (raises without bridge)

Migration Guide:
--------------
Old import:
    from avatar.vision.providers import MockCameraProvider, MockDetectorProvider

New import (recommended):
    from avatar.vision.providers import (
        MockCameraProvider,
        MockDetectorProvider,
        RtspCameraProvider,
        YoloDetectorProvider,
    )

Or use registry:
    from avatar.vision.providers import get_camera_provider, get_detector_provider

    CameraProvider = get_camera_provider("rtsp")
    DetectorProvider = get_detector_provider("yolo")
"""

from __future__ import annotations

# Re-export everything from the providers package
from avatar.vision.providers import (
    CAMERA_PROVIDERS,
    DETECTOR_PROVIDERS,
    CameraConfig,
    CameraProvider,
    DetectorConfig,
    DetectorProvider,
    Detection,
    Frame,
    GazeboCameraProvider,
    MockCameraProvider,
    MockDetectorProvider,
    OakCameraProvider,
    RealSenseCameraProvider,
    RtspCameraProvider,
    VisionProvider,
    YoloDetectorProvider,
    get_camera_provider,
    get_detector_provider,
    list_camera_backends,
    list_detector_backends,
)

# Legacy configuration dataclass (maintained for backward compatibility)
from dataclasses import dataclass


@dataclass(frozen=True)
class VisionBackendConfig:
    """Selected camera and detector backends for the current runtime.

    Legacy configuration class maintained for backward compatibility.
    New code should use CameraConfig and DetectorConfig directly.

    Attributes:
        camera_backend: Camera backend name (default: "mock_camera").
        detector_backend: Detector backend name (default: "mock_detector").
        width: Frame width in pixels.
        height: Frame height in pixels.
        confidence_threshold: Detection confidence threshold.
    """

    camera_backend: str = "mock_camera"
    detector_backend: str = "mock_detector"
    width: int = 640
    height: int = 480
    confidence_threshold: float = 0.5


__all__ = [
    # Legacy
    "VisionBackendConfig",
    # Re-exports from providers package
    "Frame",
    "Detection",
    "CameraConfig",
    "DetectorConfig",
    "CameraProvider",
    "DetectorProvider",
    "VisionProvider",
    # Camera providers
    "MockCameraProvider",
    "GazeboCameraProvider",
    "RtspCameraProvider",
    "RealSenseCameraProvider",
    "OakCameraProvider",
    # Detector providers
    "MockDetectorProvider",
    "YoloDetectorProvider",
    # Registry
    "CAMERA_PROVIDERS",
    "DETECTOR_PROVIDERS",
    "get_camera_provider",
    "get_detector_provider",
    "list_camera_backends",
    "list_detector_backends",
]
