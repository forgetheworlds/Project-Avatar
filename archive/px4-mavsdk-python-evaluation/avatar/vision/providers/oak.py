"""OAK (OpenCV AI Kit) camera provider for Luxonis OAK cameras.

This module provides OakCameraProvider for capturing frames and running
on-device neural network inference on Luxonis OAK cameras (OAK-D, OAK-D-Lite,
OAK-1, etc.).

Hardware Support:
----------------
- Luxonis OAK-D (stereo depth + RGB)
- Luxonis OAK-D-Lite (compact stereo depth)
- Luxonis OAK-D-Pro (high resolution depth)
- Luxonis OAK-1 (RGB only)

Features:
---------
- On-device neural network inference (MYRIAD X VPU)
- Stereo depth perception
- Object detection with hardware acceleration
- Multi-model pipeline support

Example:
    >>> provider = OakCameraProvider(device_id="14442C10D13EABD300")
    >>> await provider.connect()
    >>> frame, detections = await provider.capture_and_detect()

Note:
    This is a stub implementation that gracefully fails when the DepthAI
    SDK is not installed. Full implementation requires:
    - Luxonis DepthAI SDK
    - depthai Python package
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers.base import CameraConfig, Detection, Frame

logger = logging.getLogger(__name__)

# DepthAI SDK availability check
_DEPTHAI_AVAILABLE = False
_dai = None

try:
    import depthai as dai

    _DEPTHAI_AVAILABLE = True
    _dai = dai
    logger.debug("DepthAI SDK is available")
except ImportError:
    logger.debug(
        "DepthAI SDK not available. "
        "Install with: pip install depthai"
    )


class OakCameraProvider:
    """OAK camera provider for Luxonis OAK depth cameras.

    The OAK (OpenCV AI Kit) combines camera sensors with a MYRIAD X VPU
    for on-device neural network inference. This provider supports both
    frame capture and on-device detection.

    When SDK Not Available:
    ----------------------
    The provider can be instantiated but connect() will raise a clear
    CameraError explaining that the DepthAI SDK is not installed.
    This allows code to import and check availability without crashing.

    On-Device Inference:
    -------------------
    Unlike other detectors, OAK runs inference on the device's VPU.
    This provides:
    - Lower latency (no host CPU involvement)
    - Lower power consumption
    - Consistent frame rate regardless of host load

    Attributes:
        backend_name: Provider identifier ("oak").
        device_id: Device ID (optional, auto-detects if None).
        config: Camera configuration.
        is_connected: Whether connected to camera.

    Example:
        >>> # With DepthAI SDK installed
        >>> provider = OakCameraProvider()
        >>> await provider.connect()
        >>> frame, detections = await provider.capture_and_detect()

        >>> # Without DepthAI SDK (graceful failure)
        >>> provider = OakCameraProvider()
        >>> try:
        ...     await provider.connect()
        ... except CameraError as e:
        ...     print(f"OAK not available: {e.message}")
    """

    backend_name = "oak"

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[CameraConfig] = None,
        enable_depth: bool = True,
        model: str = "yolov8n",
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize OAK camera provider.

        Args:
            device_id: Device ID (MX ID). If None, auto-detects first device.
            config: Optional camera configuration.
            enable_depth: Enable stereo depth stream.
            model: Neural network model for on-device inference.
            confidence_threshold: Minimum confidence for detections.
        """
        self._device_id = device_id
        self._config = config or CameraConfig(width=640, height=480, fps=30.0)
        self._enable_depth = enable_depth
        self._model = model
        self._confidence_threshold = confidence_threshold

        self._connected = False
        self._device: Optional[Any] = None
        self._pipeline: Optional[Any] = None
        self._queue: Optional[Any] = None

        # Track SDK availability
        self._sdk_available = _DEPTHAI_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Check if connected to OAK camera."""
        return self._connected and self._device is not None

    async def connect(self) -> bool:
        """Connect to OAK camera.

        Returns:
            True if connection successful.

        Raises:
            CameraError: If SDK not available or connection fails.
        """
        if not self._sdk_available:
            raise CameraError(
                VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE,
                "DepthAI SDK not installed. "
                "Install with: pip install depthai. "
                "See https://docs.luxonis.com for setup instructions.",
                backend=self.backend_name,
            )

        try:
            # Create pipeline
            self._pipeline = _dai.Pipeline()

            # Setup camera nodes (stub - would need full implementation)
            # In production:
            # 1. Create ColorCamera node for RGB
            # 2. Create StereoDepth node if depth enabled
            # 3. Create NeuralNetwork node for on-device inference
            # 4. Create XLinkOut nodes for output queues

            # For stub, we just note the structure
            logger.warning(
                "OAK camera provider is a stub implementation. "
                "Full implementation requires DepthAI pipeline setup."
            )

            # Attempt device connection
            device_info = None
            if self._device_id:
                device_info = _dai.DeviceInfo(self._device_id)

            self._device = _dai.Device(self._pipeline, device_info)

            self._connected = True
            logger.info(f"Connected to OAK device")
            return True

        except Exception as e:
            self._device = None
            self._pipeline = None
            raise CameraError(
                VisionErrorCode.CAMERA_CONNECTION_FAILED,
                f"Failed to connect to OAK camera: {e}",
                backend=self.backend_name,
                cause=e if not isinstance(e, CameraError) else None,
            )

    async def disconnect(self) -> None:
        """Disconnect from OAK camera."""
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.warning(f"Error closing OAK device: {e}")

        self._device = None
        self._pipeline = None
        self._queue = None
        self._connected = False
        logger.info("Disconnected from OAK camera")

    async def capture_frame(self) -> Frame:
        """Capture a frame from the OAK camera.

        Returns:
            Frame object with RGB data and optional depth metadata.

        Raises:
            CameraError: If not connected or capture fails.
        """
        if not self.is_connected:
            raise CameraError(
                VisionErrorCode.CAMERA_NOT_CONNECTED,
                "Not connected to OAK camera. Call connect() first.",
                backend=self.backend_name,
            )

        # Stub implementation
        raise CameraError(
            VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
            "OAK frame capture not implemented in stub. "
            "Requires full DepthAI pipeline setup with ColorCamera and XLinkOut nodes.",
            backend=self.backend_name,
        )

    async def capture_and_detect(self) -> Tuple[Frame, List[Detection]]:
        """Capture frame and run on-device detection.

        OAK's unique capability is running neural network inference
        on-device, returning both the frame and detections efficiently.

        Returns:
            Tuple of (Frame, List[Detection]).

        Raises:
            CameraError: If not connected or capture fails.
        """
        if not self.is_connected:
            raise CameraError(
                VisionErrorCode.CAMERA_NOT_CONNECTED,
                "Not connected to OAK camera. Call connect() first.",
                backend=self.backend_name,
            )

        # Stub implementation
        raise CameraError(
            VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
            "OAK capture_and_detect not implemented in stub. "
            "Requires full DepthAI pipeline setup with NeuralNetwork node.",
            backend=self.backend_name,
        )

    def get_info(self) -> Dict[str, Any]:
        """Get camera information and configuration.

        Returns:
            Dictionary with backend info and OAK details.
        """
        info = {
            "backend": self.backend_name,
            "connected": self._connected,
            "sdk_available": self._sdk_available,
            "config": {
                "width": self._config.width,
                "height": self._config.height,
                "fps": self._config.fps,
                "enable_depth": self._enable_depth,
                "model": self._model,
            },
            "device_id": self._device_id,
        }

        # Add device info if connected
        if self._device and self._sdk_available:
            try:
                info["device_info"] = {
                    "mx_id": self._device.getMxId(),
                    "name": self._device.getDeviceName(),
                    "camera_sensors": [
                        {
                            "type": str(sensor.type),
                            "width": sensor.width,
                            "height": sensor.height,
                        }
                        for sensor in self._device.getCameraSensorNames().items()
                    ],
                }
            except Exception:
                pass

        return info

    @classmethod
    def list_devices(cls) -> Dict[str, Any]:
        """List available OAK devices.

        Returns:
            Dictionary with device list or error info.
        """
        if not _DEPTHAI_AVAILABLE:
            return {
                "available": False,
                "error": "DepthAI SDK not installed",
                "devices": [],
            }

        try:
            devices = _dai.Device.getAllAvailableDevices()

            device_list = []
            for dev in devices:
                device_list.append({
                    "mx_id": dev.getMxId(),
                    "name": dev.getDeviceName(),
                    "state": str(dev.state),
                })

            return {
                "available": True,
                "count": len(device_list),
                "devices": device_list,
            }

        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "devices": [],
            }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"OakCameraProvider(device_id={self._device_id!r}, "
            f"connected={self._connected}, "
            f"sdk_available={self._sdk_available})"
        )
