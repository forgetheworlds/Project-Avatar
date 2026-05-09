"""Gazebo camera provider for simulated drone cameras.

This module provides GazeboCameraProvider for capturing frames from
Gazebo SITL simulation cameras via ROS topics or mock generation.

Architecture:
------------
Two modes of operation:
1. Mock Mode (default): Generates deterministic test frames without Gazebo
2. ROS Mode (future): Connects to Gazebo camera topic via roslibpy

Mock mode is useful for:
- Unit testing vision pipeline without simulation
- CI/CD pipelines without Gazebo dependency
- Development iteration on vision algorithms

ROS mode (future) will enable:
- Real Gazebo camera simulation
- Photorealistic rendering from Gazebo
- Multi-camera setups in simulation

Example:
    >>> # Mock mode (works without Gazebo)
    >>> provider = GazeboCameraProvider()
    >>> await provider.connect()
    >>> frame = await provider.capture_frame()
    >>> print(f"Frame: {frame.width}x{frame.height}")
"""

from __future__ import annotations

import logging
from time import time
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers.base import CameraConfig, Frame

logger = logging.getLogger(__name__)


class GazeboCameraProvider:
    """Gazebo camera provider for simulated drone cameras.

    Provides frames from Gazebo simulation or mock test generation.
    Designed to work with PX4 SITL + Gazebo Classic or Gazebo Garden.

    Mock Frame Generation:
    ---------------------
    When Gazebo is not available (or use_mock=True), generates
    deterministic test frames with:
    - Gradient background for brightness testing
    - Frame counter for temporal verification
    - Consistent size and format

    ROS Integration (Future):
    ------------------------
    For real Gazebo camera capture:
    1. Connect to rosbridge (roslibpy or rclpy)
    2. Subscribe to camera topic (sensor_msgs/Image)
    3. Convert ROS message to numpy array
    4. Handle encoding (rgb8, bgr8, mono8)

    Attributes:
        backend_name: Provider identifier ("gazebo").
        topic: ROS topic for camera (e.g., "/drone/camera/image_raw").
        config: Camera configuration.
        is_connected: Whether connected.

    Example:
        >>> # Mock mode (works everywhere)
        >>> provider = GazeboCameraProvider(use_mock=True)
        >>> await provider.connect()
        >>> frame = await provider.capture_frame()
    """

    backend_name = "gazebo"

    def __init__(
        self,
        topic: str = "/drone/camera/image_raw",
        config: Optional[CameraConfig] = None,
        use_mock: bool = True,
        rosbridge_url: Optional[str] = None,
    ) -> None:
        """Initialize Gazebo camera provider.

        Args:
            topic: ROS topic for camera images.
            config: Optional camera configuration.
            use_mock: Use mock frames instead of ROS (default True for testing).
            rosbridge_url: WebSocket URL for roslibpy (e.g., "ws://localhost:9090").
        """
        self._topic = topic
        self._config = config or CameraConfig(
            width=640, height=480, fps=30.0, source=topic
        )
        self._use_mock = use_mock
        self._rosbridge_url = rosbridge_url

        self._connected = False
        self._frame_count = 0
        self._ros_client: Optional[Any] = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to camera source."""
        return self._connected

    async def connect(self) -> bool:
        """Connect to camera source.

        For mock mode: Always succeeds immediately.
        For ROS mode: Requires rosbridge connection.

        Returns:
            True if connection successful.

        Raises:
            CameraError: If ROS connection fails (in ROS mode).
        """
        if self._use_mock:
            self._connected = True
            logger.info("Gazebo camera provider connected (mock mode)")
            return True

        # ROS mode (future implementation)
        if self._rosbridge_url:
            try:
                import roslibpy

                self._ros_client = roslibpy.Ros(
                    url=self._rosbridge_url.replace("ws://", "").replace("/", "")
                )
                self._ros_client.run()

                # Wait for connection
                import asyncio

                await asyncio.sleep(0.5)

                if self._ros_client.is_connected:
                    self._connected = True
                    logger.info(
                        f"Connected to Gazebo via rosbridge: {self._rosbridge_url}"
                    )
                    return True
                else:
                    raise CameraError(
                        VisionErrorCode.CAMERA_CONNECTION_FAILED,
                        f"Failed to connect to rosbridge: {self._rosbridge_url}",
                        backend=self.backend_name,
                    )

            except ImportError:
                raise CameraError(
                    VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE,
                    "roslibpy not installed for ROS mode. "
                    "Install with: pip install roslibpy",
                    backend=self.backend_name,
                )
            except Exception as e:
                raise CameraError(
                    VisionErrorCode.CAMERA_CONNECTION_FAILED,
                    f"Failed to connect to ROS: {e}",
                    backend=self.backend_name,
                    cause=e if not isinstance(e, CameraError) else None,
                )

        # No ROS bridge configured
        raise CameraError(
            VisionErrorCode.CAMERA_CONNECTION_FAILED,
            "Gazebo ROS mode requires rosbridge_url. "
            "Use use_mock=True for testing without Gazebo.",
            backend=self.backend_name,
        )

    async def disconnect(self) -> None:
        """Disconnect from camera source."""
        if self._ros_client:
            try:
                self._ros_client.terminate()
            except Exception as e:
                logger.warning(f"Error closing ROS client: {e}")

        self._ros_client = None
        self._connected = False
        self._frame_count = 0
        logger.info("Disconnected from Gazebo camera")

    async def capture_frame(self) -> Frame:
        """Capture a frame from the Gazebo camera.

        Returns:
            Frame object with image data.

        Raises:
            CameraError: If not connected or capture fails.
        """
        if not self._connected:
            raise CameraError(
                VisionErrorCode.CAMERA_NOT_CONNECTED,
                "Not connected. Call connect() first.",
                backend=self.backend_name,
            )

        if self._use_mock:
            return self._generate_mock_frame()

        # ROS mode capture (future implementation)
        raise CameraError(
            VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
            "ROS capture not implemented. Use mock mode for testing.",
            backend=self.backend_name,
        )

    def _generate_mock_frame(self) -> Frame:
        """Generate a deterministic mock frame for testing.

        Creates a gradient test pattern that varies by frame count,
        useful for verifying frame capture and vision pipeline.

        Returns:
            Frame with gradient test pattern.
        """
        self._frame_count += 1

        width = self._config.width
        height = self._config.height

        # Create gradient background
        x = np.linspace(0, 255, width, dtype=np.uint8)
        y = np.linspace(0, 255, height, dtype=np.uint8)
        xx, yy = np.meshgrid(x, y)

        # Diagonal gradient
        gradient = ((xx.astype(np.uint16) + yy.astype(np.uint16)) // 2).astype(
            np.uint8
        )

        # Vary colors by frame count for temporal variation
        frame_mod = self._frame_count % 256
        r_channel = gradient
        g_channel = ((gradient.astype(np.uint16) + frame_mod) % 256).astype(np.uint8)
        b_channel = ((gradient.astype(np.uint16) + (256 - frame_mod)) % 256).astype(
            np.uint8
        )

        # Stack into RGB
        rgb_array = np.stack([r_channel, g_channel, b_channel], axis=2)

        return Frame(
            data=rgb_array,
            timestamp=time(),
            metadata={
                "backend": self.backend_name,
                "mode": "mock",
                "frame_count": self._frame_count,
                "topic": self._topic,
            },
        )

    def get_info(self) -> Dict[str, Any]:
        """Get camera information and configuration.

        Returns:
            Dictionary with backend info and settings.
        """
        return {
            "backend": self.backend_name,
            "connected": self._connected,
            "mode": "mock" if self._use_mock else "ros",
            "topic": self._topic,
            "config": {
                "width": self._config.width,
                "height": self._config.height,
                "fps": self._config.fps,
            },
            "frame_count": self._frame_count,
            "rosbridge_url": self._rosbridge_url,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"GazeboCameraProvider(topic={self._topic!r}, "
            f"mode={'mock' if self._use_mock else 'ros'}, "
            f"connected={self._connected})"
        )
