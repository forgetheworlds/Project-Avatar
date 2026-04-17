"""Vision providers package with registry and exports.

This package provides async vision provider protocols and implementations
for camera capture and object detection from various hardware backends.

Available Camera Providers:
-------------------------
- mock_camera: Deterministic mock for testing
- gazebo: Gazebo SITL simulation camera
- rtsp: RTSP IP camera streams
- realsense: Intel RealSense depth cameras (requires SDK)
- oak: Luxonis OAK depth cameras (requires SDK)

Available Detector Providers:
---------------------------
- mock_detector: Deterministic mock for testing
- yolo: YOLO object detection (ultralytics/ncnn/openvino backends)

Registry Usage:
--------------
    >>> from avatar.vision.providers import (
    ...     CAMERA_PROVIDERS, DETECTOR_PROVIDERS,
    ...     get_camera_provider, get_detector_provider,
    ... )
    >>>
    >>> # List available backends
    >>> print(CAMERA_PROVIDERS.keys())  # ['mock', 'gazebo', 'rtsp', ...]
    >>>
    >>> # Get provider class
    >>> RtspProvider = get_camera_provider("rtsp")
    >>> provider = RtspProvider(url="rtsp://camera.local/stream")

Direct Import Usage:
-------------------
    >>> from avatar.vision.providers import (
    ...     RtspCameraProvider,
    ...     YoloDetectorProvider,
    ...     GazeboCameraProvider,
    ... )
    >>>
    >>> provider = RtspCameraProvider(url="rtsp://192.168.1.100/stream")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from dataclasses import dataclass

from avatar.vision.errors import ProviderRegistryError, VisionErrorCode
from avatar.vision.providers.base import (
    CameraConfig,
    CameraProvider,
    DetectorConfig,
    DetectorProvider,
    Detection,
    Frame,
    VisionProvider,
)


@dataclass(frozen=True)
class VisionBackendConfig:
    """Selected camera and detector backends for the current runtime.

    Legacy configuration class for backward compatibility.

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

logger = logging.getLogger(__name__)


# =============================================================================
# Provider Implementations
# =============================================================================

# Import implementations with graceful handling of missing dependencies

# Mock providers (always available)
from avatar.vision.mock_detector import MockDetector  # Legacy import


class MockCameraProvider:
    """Mock camera provider backed by deterministic generated frames.

    This is a thin wrapper around GazeboCameraProvider in mock mode.
    """

    backend_name = "mock_camera"

    def __init__(self, width: int = 640, height: int = 480) -> None:
        """Initialize mock camera provider.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
        """
        from avatar.vision.providers.gazebo import GazeboCameraProvider

        self._impl = GazeboCameraProvider(
            use_mock=True,
            config=CameraConfig(width=width, height=height),
        )

    async def connect(self) -> bool:
        """Connect to mock camera (always succeeds)."""
        return await self._impl.connect()

    async def disconnect(self) -> None:
        """Disconnect from mock camera."""
        await self._impl.disconnect()

    async def capture_frame(self) -> Frame:
        """Capture a mock frame."""
        return await self._impl.capture_frame()

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._impl.is_connected

    def get_info(self) -> Dict[str, Any]:
        """Get mock camera info."""
        info = self._impl.get_info()
        info["backend"] = self.backend_name
        return info


class MockDetectorProvider:
    """Mock detector provider backed by deterministic generated detections.

    Wraps the legacy MockDetector with async protocol support.
    """

    backend_name = "mock_detector"

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        num_detections: int = 3,
        deterministic: bool = True,
    ) -> None:
        """Initialize mock detector provider.

        Args:
            confidence_threshold: Minimum confidence for detections.
            num_detections: Number of detections to generate.
            deterministic: Generate same detections for same input.
        """
        self._detector = MockDetector(
            confidence_threshold=confidence_threshold,
            num_detections=num_detections,
            deterministic=deterministic,
        )
        self._initialized = True

    async def initialize(self) -> bool:
        """Initialize mock detector (always succeeds)."""
        return True

    async def detect(self, frame: Frame) -> List[Detection]:
        """Detect objects in frame.

        Args:
            frame: Frame to detect objects in.

        Returns:
            List of Detection objects.
        """
        # Run in executor to maintain async contract
        import asyncio

        loop = asyncio.get_event_loop()
        legacy_detections = await loop.run_in_executor(
            None, self._detector.detect, frame.data
        )

        # Convert legacy Detection to new Detection type
        detections = []
        for det in legacy_detections:
            # Legacy Detection has same structure, just copy
            detections.append(
                Detection(
                    label=det.label,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    class_id=det.class_id,
                )
            )

        return detections

    @property
    def is_initialized(self) -> bool:
        """Check if initialized."""
        return self._initialized

    @property
    def class_names(self) -> List[str]:
        """Return class names."""
        return self._detector.class_names

    def get_info(self) -> Dict[str, Any]:
        """Get mock detector info."""
        return {
            "backend": self.backend_name,
            "initialized": self._initialized,
            "confidence_threshold": self._detector.confidence_threshold,
            "num_detections": self._detector.num_detections,
            "deterministic": self._detector.deterministic,
            "class_names": self.class_names,
        }


# Hardware providers (may fail if SDK missing)
GazeboCameraProvider = None
RtspCameraProvider = None
YoloDetectorProvider = None
RealSenseCameraProvider = None
OakCameraProvider = None

try:
    from avatar.vision.providers.gazebo import (
        GazeboCameraProvider as _GazeboCameraProvider,
    )

    GazeboCameraProvider = _GazeboCameraProvider
except ImportError as e:
    logger.debug(f"GazeboCameraProvider not available: {e}")

try:
    from avatar.vision.providers.rtsp import (
        RtspCameraProvider as _RtspCameraProvider,
    )

    RtspCameraProvider = _RtspCameraProvider
except ImportError as e:
    logger.debug(f"RtspCameraProvider not available: {e}")

try:
    from avatar.vision.providers.yolo import (
        YoloDetectorProvider as _YoloDetectorProvider,
    )

    YoloDetectorProvider = _YoloDetectorProvider
except ImportError as e:
    logger.debug(f"YoloDetectorProvider not available: {e}")

try:
    from avatar.vision.providers.realsense import (
        RealSenseCameraProvider as _RealSenseCameraProvider,
    )

    RealSenseCameraProvider = _RealSenseCameraProvider
except ImportError as e:
    logger.debug(f"RealSenseCameraProvider not available: {e}")

try:
    from avatar.vision.providers.oak import (
        OakCameraProvider as _OakCameraProvider,
    )

    OakCameraProvider = _OakCameraProvider
except ImportError as e:
    logger.debug(f"OakCameraProvider not available: {e}")


# =============================================================================
# Provider Registry
# =============================================================================

# Camera provider registry
# Maps backend_name -> provider class
CAMERA_PROVIDERS: Dict[str, Type] = {}

# Register camera providers
CAMERA_PROVIDERS["mock"] = MockCameraProvider
CAMERA_PROVIDERS["mock_camera"] = MockCameraProvider  # Alias for backward compat

if GazeboCameraProvider:
    CAMERA_PROVIDERS["gazebo"] = GazeboCameraProvider
    CAMERA_PROVIDERS["gazebo_camera"] = GazeboCameraProvider  # Alias

# RTSP: Check if PyAV is actually available (not just importable)
if RtspCameraProvider:
    try:
        import av
        CAMERA_PROVIDERS["rtsp"] = RtspCameraProvider
    except ImportError:
        pass

# RealSense: Check if pyrealsense2 is actually available
if RealSenseCameraProvider:
    try:
        import pyrealsense2
        CAMERA_PROVIDERS["realsense"] = RealSenseCameraProvider
    except ImportError:
        pass

# OAK: Check if depthai is actually available
if OakCameraProvider:
    try:
        import depthai
        CAMERA_PROVIDERS["oak"] = OakCameraProvider
    except ImportError:
        pass


# Detector provider registry
DETECTOR_PROVIDERS: Dict[str, Type] = {}

# Register detector providers
DETECTOR_PROVIDERS["mock"] = MockDetectorProvider
DETECTOR_PROVIDERS["mock_detector"] = MockDetectorProvider  # Alias for backward compat

if YoloDetectorProvider:
    DETECTOR_PROVIDERS["yolo"] = YoloDetectorProvider


def get_camera_provider(name: str) -> Type:
    """Get camera provider class by name.

    Args:
        name: Backend name (e.g., "mock", "rtsp", "gazebo").

    Returns:
        Provider class (not instance).

    Raises:
        ProviderRegistryError: If provider not registered.
    """
    if name not in CAMERA_PROVIDERS:
        available = list(CAMERA_PROVIDERS.keys())
        raise ProviderRegistryError(
            VisionErrorCode.PROVIDER_NOT_REGISTERED,
            f"Camera provider '{name}' not registered. Available: {available}",
        )
    return CAMERA_PROVIDERS[name]


def get_detector_provider(name: str) -> Type:
    """Get detector provider class by name.

    Args:
        name: Backend name (e.g., "mock", "yolo").

    Returns:
        Provider class (not instance).

    Raises:
        ProviderRegistryError: If provider not registered.
    """
    if name not in DETECTOR_PROVIDERS:
        available = list(DETECTOR_PROVIDERS.keys())
        raise ProviderRegistryError(
            VisionErrorCode.PROVIDER_NOT_REGISTERED,
            f"Detector provider '{name}' not registered. Available: {available}",
        )
    return DETECTOR_PROVIDERS[name]


def list_camera_backends() -> List[str]:
    """List registered camera backend names.

    Returns:
        List of backend names.
    """
    return list(CAMERA_PROVIDERS.keys())


def list_detector_backends() -> List[str]:
    """List registered detector backend names.

    Returns:
        List of backend names.
    """
    return list(DETECTOR_PROVIDERS.keys())


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base protocols and types
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
