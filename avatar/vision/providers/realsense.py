"""RealSense camera provider for Intel RealSense depth cameras.

This module provides RealSenseCameraProvider for capturing RGB and depth
frames from Intel RealSense cameras (D400 series, L500 series, etc.).

Hardware Support:
----------------
- Intel RealSense D415, D435, D435i, D455
- Intel RealSense L515
- Intel RealSense D405

Features:
---------
- RGB frame capture
- Depth frame capture (optional)
- Infrared frame capture (optional)
- Camera intrinsics access
- Real-time point cloud generation

Example:
    >>> provider = RealSenseCameraProvider(serial="123456")
    >>> await provider.connect()
    >>> frame = await provider.capture_frame()

Note:
    This is a stub implementation that gracefully fails when the RealSense
    SDK (pyrealsense2) is not installed. Full implementation requires:
    - Intel RealSense SDK 2.0
    - pyrealsense2 Python package
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers.base import CameraConfig, Frame

logger = logging.getLogger(__name__)

# RealSense SDK availability check
_REALSENSE_AVAILABLE = False
_rs = None

try:
    import pyrealsense2 as rs

    _REALSENSE_AVAILABLE = True
    _rs = rs
    logger.debug("RealSense SDK (pyrealsense2) is available")
except ImportError:
    logger.debug(
        "RealSense SDK not available. "
        "Install with: pip install pyrealsense2"
    )


class RealSenseCameraProvider:
    """RealSense camera provider for Intel RealSense depth cameras.

    Captures RGB frames from RealSense cameras with optional depth data.
    Gracefully handles missing SDK by raising clear errors at runtime.

    When SDK Not Available:
    ----------------------
    The provider can be instantiated but connect() will raise a clear
    CameraError explaining that the RealSense SDK is not installed.
    This allows code to import and check availability without crashing.

    Attributes:
        backend_name: Provider identifier ("realsense").
        serial: Camera serial number (optional, auto-detects if None).
        config: Camera configuration.
        is_connected: Whether connected to camera.

    Example:
        >>> # With RealSense SDK installed
        >>> provider = RealSenseCameraProvider()
        >>> await provider.connect()
        >>> frame = await provider.capture_frame()
        >>> print(f"Depth available: {frame.metadata.get('has_depth', False)}")

        >>> # Without RealSense SDK (graceful failure)
        >>> provider = RealSenseCameraProvider()
        >>> try:
        ...     await provider.connect()
        ... except CameraError as e:
        ...     print(f"RealSense not available: {e.message}")
    """

    backend_name = "realsense"

    def __init__(
        self,
        serial: Optional[str] = None,
        config: Optional[CameraConfig] = None,
        enable_depth: bool = True,
        enable_infrared: bool = False,
    ) -> None:
        """Initialize RealSense camera provider.

        Args:
            serial: Camera serial number. If None, auto-detects first camera.
            config: Optional camera configuration.
            enable_depth: Enable depth stream alongside RGB.
            enable_infrared: Enable infrared stream.
        """
        self._serial = serial
        self._config = config or CameraConfig(width=640, height=480, fps=30.0)
        self._enable_depth = enable_depth
        self._enable_infrared = enable_infrared

        self._connected = False
        self._pipeline: Optional[Any] = None
        self._profile: Optional[Any] = None
        self._align: Optional[Any] = None

        # Track SDK availability
        self._sdk_available = _REALSENSE_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Check if connected to RealSense camera."""
        return self._connected and self._pipeline is not None

    async def connect(self) -> bool:
        """Connect to RealSense camera.

        Returns:
            True if connection successful.

        Raises:
            CameraError: If SDK not available or connection fails.
        """
        if not self._sdk_available:
            raise CameraError(
                VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE,
                "RealSense SDK (pyrealsense2) not installed. "
                "Install with: pip install pyrealsense2. "
                "Also requires Intel RealSense SDK 2.0 from "
                "https://github.com/IntelRealSense/librealsense",
                backend=self.backend_name,
            )

        try:
            # Create pipeline
            self._pipeline = _rs.pipeline()
            config = _rs.config()

            # Configure streams
            config.enable_stream(
                _rs.stream.color,
                self._config.width,
                self._config.height,
                _rs.format.rgb8,
                int(self._config.fps),
            )

            if self._enable_depth:
                config.enable_stream(
                    _rs.stream.depth,
                    self._config.width,
                    self._config.height,
                    _rs.format.z16,
                    int(self._config.fps),
                )

            if self._enable_infrared:
                config.enable_stream(
                    _rs.stream.infrared,
                    self._config.width,
                    self._config.height,
                    _rs.format.y8,
                    int(self._config.fps),
                )

            # Select specific camera by serial
            if self._serial:
                config.enable_device(self._serial)

            # Start pipeline
            self._profile = self._pipeline.start(config)

            # Create align object for depth-to-color alignment
            if self._enable_depth:
                depth_stream = _rs.stream.depth
                color_stream = _rs.stream.color
                self._align = _rs.align(color_stream)

            self._connected = True
            logger.info(f"Connected to RealSense camera")
            return True

        except Exception as e:
            self._pipeline = None
            self._profile = None
            raise CameraError(
                VisionErrorCode.CAMERA_CONNECTION_FAILED,
                f"Failed to connect to RealSense camera: {e}",
                backend=self.backend_name,
                cause=e if not isinstance(e, CameraError) else None,
            )

    async def disconnect(self) -> None:
        """Disconnect from RealSense camera."""
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception as e:
                logger.warning(f"Error stopping RealSense pipeline: {e}")

        self._pipeline = None
        self._profile = None
        self._align = None
        self._connected = False
        logger.info("Disconnected from RealSense camera")

    async def capture_frame(self) -> Frame:
        """Capture a frame from the RealSense camera.

        Returns:
            Frame object with RGB data and optional depth metadata.

        Raises:
            CameraError: If not connected or capture fails.
        """
        if not self.is_connected:
            raise CameraError(
                VisionErrorCode.CAMERA_NOT_CONNECTED,
                "Not connected to RealSense camera. Call connect() first.",
                backend=self.backend_name,
            )

        try:
            # Wait for frames
            frames = self._pipeline.wait_for_frames()

            # Align depth to color if depth enabled
            if self._align:
                frames = self._align.process(frames)

            # Get color frame
            color_frame = frames.get_color_frame()
            if not color_frame:
                raise CameraError(
                    VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
                    "No color frame received",
                    backend=self.backend_name,
                )

            # Convert to numpy
            color_data = np.asanyarray(color_frame.get_data())

            # Build metadata
            metadata: Dict[str, Any] = {
                "backend": self.backend_name,
                "has_depth": False,
                "has_infrared": False,
            }

            # Get depth if available
            if self._enable_depth:
                depth_frame = frames.get_depth_frame()
                if depth_frame:
                    metadata["has_depth"] = True
                    metadata["depth_data"] = np.asanyarray(
                        depth_frame.get_data()
                    )
                    # Get depth scale for meter conversion
                    depth_sensor = self._profile.get_device().first_depth_sensor()
                    metadata["depth_scale"] = depth_sensor.get_depth_scale()

            # Get infrared if available
            if self._enable_infrared:
                ir_frame = frames.get_infrared_frame()
                if ir_frame:
                    metadata["has_infrared"] = True
                    metadata["infrared_data"] = np.asanyarray(
                        ir_frame.get_data()
                    )

            # Get intrinsics
            intrinsics = color_frame.get_profile().as_video_stream_profile().get_intrinsics()
            metadata["intrinsics"] = {
                "width": intrinsics.width,
                "height": intrinsics.height,
                "fx": intrinsics.fx,
                "fy": intrinsics.fy,
                "ppx": intrinsics.ppx,
                "ppy": intrinsics.ppy,
                "model": str(intrinsics.model),
            }

            return Frame(data=color_data, metadata=metadata)

        except CameraError:
            raise
        except Exception as e:
            raise CameraError(
                VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
                f"Failed to capture frame: {e}",
                backend=self.backend_name,
                cause=e,
            )

    def get_info(self) -> Dict[str, Any]:
        """Get camera information and configuration.

        Returns:
            Dictionary with backend info and RealSense details.
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
                "enable_infrared": self._enable_infrared,
            },
            "serial": self._serial,
        }

        # Add device info if connected
        if self._profile and self._sdk_available:
            try:
                device = self._profile.get_device()
                info["device_info"] = {
                    "name": device.get_info(_rs.camera_info.name),
                    "serial": device.get_info(_rs.camera_info.serial_number),
                    "firmware": device.get_info(_rs.camera_info.firmware_version),
                }
            except Exception:
                pass

        return info

    @classmethod
    def list_devices(cls) -> Dict[str, Any]:
        """List available RealSense devices.

        Returns:
            Dictionary with device list or error info.
        """
        if not _REALSENSE_AVAILABLE:
            return {
                "available": False,
                "error": "RealSense SDK not installed",
                "devices": [],
            }

        try:
            ctx = _rs.context()
            devices = ctx.query_devices()

            device_list = []
            for dev in devices:
                device_list.append({
                    "name": dev.get_info(_rs.camera_info.name),
                    "serial": dev.get_info(_rs.camera_info.serial_number),
                    "firmware": dev.get_info(_rs.camera_info.firmware_version),
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
            f"RealSenseCameraProvider(serial={self._serial!r}, "
            f"connected={self._connected}, "
            f"sdk_available={self._sdk_available})"
        )
