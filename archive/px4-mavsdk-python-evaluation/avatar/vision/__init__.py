"""Vision pipeline for camera capture and object detection.

This package provides async vision providers for camera capture and
object detection from various hardware backends.

Key Components:
--------------
- Camera Providers: RTSP, Gazebo, RealSense, OAK, Mock
- Detector Providers: YOLO, Mock
- Error Types: VisionProviderError, CameraError, DetectorError

Example:
    >>> from avatar.vision import (
    ...     MockCameraProvider,
    ...     MockDetectorProvider,
    ...     list_camera_backends,
    ... )
    >>> backends = list_camera_backends()
    >>> print(backends)  # ['mock', 'gazebo', 'rtsp', ...]
"""

# Re-export from providers package
from avatar.vision.providers import (
    # Registry
    CAMERA_PROVIDERS,
    DETECTOR_PROVIDERS,
    get_camera_provider,
    get_detector_provider,
    list_camera_backends,
    list_detector_backends,
    # Base types
    Frame,
    Detection,
    CameraConfig,
    DetectorConfig,
    VisionBackendConfig,
    # Camera providers
    MockCameraProvider,
    GazeboCameraProvider,
    RtspCameraProvider,
    RealSenseCameraProvider,
    OakCameraProvider,
    # Detector providers
    MockDetectorProvider,
    YoloDetectorProvider,
)

# Re-export errors
from avatar.vision.errors import (
    VisionErrorCode,
    VisionProviderError,
    CameraError,
    DetectorError,
    ProviderRegistryError,
)

# Legacy exports (for backward compatibility)
from avatar.vision.gazebo_camera_client import GazeboCameraClient
from avatar.vision.mock_detector import MockDetector

__all__ = [
    # Registry
    "CAMERA_PROVIDERS",
    "DETECTOR_PROVIDERS",
    "get_camera_provider",
    "get_detector_provider",
    "list_camera_backends",
    "list_detector_backends",
    # Base types
    "Frame",
    "Detection",
    "CameraConfig",
    "DetectorConfig",
    "VisionBackendConfig",
    # Camera providers
    "MockCameraProvider",
    "GazeboCameraProvider",
    "RtspCameraProvider",
    "RealSenseCameraProvider",
    "OakCameraProvider",
    # Detector providers
    "MockDetectorProvider",
    "YoloDetectorProvider",
    # Errors
    "VisionErrorCode",
    "VisionProviderError",
    "CameraError",
    "DetectorError",
    "ProviderRegistryError",
    # Legacy
    "GazeboCameraClient",
    "MockDetector",
]
