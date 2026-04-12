"""Gazebo camera client for capturing frames from simulated drone camera.

This module provides a client interface for capturing frames from a Gazebo
simulated camera. Currently uses mock images as placeholders until real
Gazebo integration is implemented.
"""

from typing import Union
import numpy as np
from PIL import Image


class GazeboCameraClient:
    """Client for capturing frames from Gazebo simulated camera.

    Provides an interface to capture frames from a drone's camera in Gazebo
    simulation. The captured frames can be used for vision processing,
    object detection, and navigation.

    Attributes:
        width: Width of captured frames in pixels.
        height: Height of captured frames in pixels.
        connected: Whether connected to Gazebo simulation.

    Example:
        >>> client = GazeboCameraClient()
        >>> frame = client.capture_frame()
        >>> isinstance(frame, Image.Image)
        True
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        topic: str = "/drone/camera/image_raw"
    ):
        """Initialize the Gazebo camera client.

        Args:
            width: Width of captured frames in pixels. Default 640.
            height: Height of captured frames in pixels. Default 480.
            topic: ROS topic for camera images. Default "/drone/camera/image_raw".
        """
        self.width = width
        self.height = height
        self.topic = topic
        self._connected = False
        self._frame_count = 0

        # Initialize connection (placeholder for real Gazebo integration)
        self._connect()

    def _connect(self) -> bool:
        """Establish connection to Gazebo simulation.

        Returns:
            True if connection successful, False otherwise.

        Note:
            Currently returns True as placeholder. Real implementation
            would use ROS/Gazebo bridges to establish connection.
        """
        # Placeholder: In real implementation, this would:
        # 1. Check if Gazebo is running
        # 2. Subscribe to camera ROS topic
        # 3. Set up ROS bridge connection if needed
        self._connected = True
        return self._connected

    def capture_frame(self) -> Union[Image.Image, np.ndarray]:
        """Capture a single frame from the simulated camera.

        Returns:
            PIL Image or numpy array containing the captured frame.
            Currently returns a mock image for testing purposes.

        Raises:
            RuntimeError: If camera is not connected.

        Note:
            Real implementation would subscribe to ROS Image messages
            and convert them to PIL/numpy format.
        """
        if not self._connected:
            raise RuntimeError("Camera not connected. Call _connect() first.")

        self._frame_count += 1

        # Generate a mock image for testing
        # Creates a simple gradient pattern that varies by frame count
        return self._generate_mock_frame()

    def _generate_mock_frame(self) -> Image.Image:
        """Generate a mock frame for testing purposes.

        Creates a deterministic test image with a gradient pattern
        and frame counter overlay. Useful for testing the vision
        pipeline without a running Gazebo simulation.

        Returns:
            PIL Image with test pattern.
        """
        # Create a gradient background
        x = np.linspace(0, 255, self.width, dtype=np.uint8)
        y = np.linspace(0, 255, self.height, dtype=np.uint8)
        xx, yy = np.meshgrid(x, y)

        # Combine for a diagonal gradient
        gradient = ((xx.astype(np.uint16) + yy.astype(np.uint16)) // 2).astype(np.uint8)

        # Create RGB image with varying colors based on frame count
        frame_mod = self._frame_count % 256
        r_channel = gradient
        g_channel = ((gradient.astype(np.uint16) + frame_mod) % 256).astype(np.uint8)
        b_channel = ((gradient.astype(np.uint16) + (256 - frame_mod)) % 256).astype(np.uint8)

        # Stack into RGB array
        rgb_array = np.stack([r_channel, g_channel, b_channel], axis=2)

        # Convert to PIL Image
        return Image.fromarray(rgb_array, mode='RGB')

    def capture_frame_as_numpy(self) -> np.ndarray:
        """Capture frame and return as numpy array.

        Convenience method that captures a frame and returns it
        as a numpy array with shape (height, width, 3).

        Returns:
            Numpy array with shape (height, width, 3) and dtype uint8.
        """
        frame = self.capture_frame()
        if isinstance(frame, Image.Image):
            return np.array(frame)
        return frame

    @property
    def connected(self) -> bool:
        """Check if client is connected to Gazebo simulation."""
        return self._connected

    def disconnect(self) -> None:
        """Disconnect from Gazebo simulation.

        Cleans up resources and connection state.
        """
        self._connected = False
        self._frame_count = 0

    def __repr__(self) -> str:
        """Return string representation of the client."""
        return (
            f"GazeboCameraClient(width={self.width}, height={self.height}, "
            f"topic='{self.topic}', connected={self._connected})"
        )
