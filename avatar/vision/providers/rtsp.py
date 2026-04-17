"""RTSP camera provider using PyAV for video streaming.

This module provides RtspCameraProvider for capturing frames from RTSP
video streams, supporting real IP cameras, NVRs, and video files via
file:// URLs.

Architecture:
------------
RTSP Stream -> PyAV Decoder -> Frame Queue -> capture_frame()

PyAV provides direct access to FFmpeg for efficient video decoding
without the overhead of higher-level libraries.

Example:
    >>> provider = RtspCameraProvider(url="rtsp://camera.local/stream")
    >>> await provider.connect()
    >>> frame = await provider.capture_frame()
    >>> print(f"Captured {frame.width}x{frame.height}")
"""

from __future__ import annotations

import asyncio
import logging
from queue import Empty, Queue
from threading import Event, Thread
from time import time
from typing import Any, Dict, Optional

import numpy as np

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers.base import CameraConfig, Frame

logger = logging.getLogger(__name__)

# PyAV availability check
_PYAV_AVAILABLE = False
_av = None

try:
    import av

    _PYAV_AVAILABLE = True
    _av = av
except ImportError:
    logger.debug("PyAV not available. RtspCameraProvider will raise on use.")


class RtspCameraProvider:
    """RTSP camera provider using PyAV for frame capture.

    Captures frames from RTSP streams, video files, or any FFmpeg-compatible
    source. Uses a background thread for continuous decoding with a frame
    queue for smooth async access.

    Thread Architecture:
    -------------------
    Main Thread: Python async loop for capture_frame() calls
    Decode Thread: Continuous PyAV decoding, fills frame queue
    Frame Queue: Thread-safe buffer between threads

    This architecture ensures:
    - Non-blocking capture_frame() for async callers
    - Continuous decoding even when frames aren't requested
    - Graceful handling of network issues

    Attributes:
        backend_name: Provider identifier ("rtsp").
        url: RTSP stream URL or file path.
        config: Camera configuration.
        is_connected: Whether connected to stream.

    Example:
        >>> # RTSP camera
        >>> provider = RtspCameraProvider(url="rtsp://192.168.1.100:554/stream")
        >>> await provider.connect()
        >>> frame = await provider.capture_frame()

        >>> # Video file (for testing)
        >>> provider = RtspCameraProvider(url="file:///path/to/video.mp4")
        >>> await provider.connect()
        >>> frame = await provider.capture_frame()
    """

    backend_name = "rtsp"

    def __init__(
        self,
        url: str,
        config: Optional[CameraConfig] = None,
        reconnect_timeout: float = 5.0,
        buffer_size: int = 2,
    ) -> None:
        """Initialize RTSP camera provider.

        Args:
            url: RTSP URL (rtsp://...) or file path (file://...).
            config: Optional camera configuration.
            reconnect_timeout: Seconds to wait for reconnection.
            buffer_size: Maximum frames in decode queue.
        """
        self._url = url
        self._config = config or CameraConfig(width=640, height=480, source=url)
        self._reconnect_timeout = reconnect_timeout
        self._buffer_size = buffer_size

        self._connected = False
        self._container: Optional[Any] = None
        self._stream: Optional[Any] = None

        # Thread-safe frame queue
        self._frame_queue: Queue = Queue(maxsize=buffer_size)
        self._decode_thread: Optional[Thread] = None
        self._stop_event = Event()

        # Track if PyAV is available
        self._pyav_available = _PYAV_AVAILABLE

    @property
    def url(self) -> str:
        """Return the RTSP URL."""
        return self._url

    @property
    def is_connected(self) -> bool:
        """Check if connected to the RTSP stream."""
        return self._connected and self._container is not None

    async def connect(self) -> bool:
        """Connect to the RTSP stream.

        Opens the stream and starts the decode thread.

        Returns:
            True if connection successful.

        Raises:
            CameraError: If PyAV not available or connection fails.
        """
        if not self._pyav_available:
            raise CameraError(
                VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE,
                "PyAV library not installed. Install with: pip install av",
                backend=self.backend_name,
            )

        try:
            # Open container in decode thread to avoid blocking
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._connect_sync)

            if success:
                # Start decode thread
                self._stop_event.clear()
                self._decode_thread = Thread(target=self._decode_loop, daemon=True)
                self._decode_thread.start()
                self._connected = True
                logger.info(f"Connected to RTSP stream: {self._url}")

            return success

        except Exception as e:
            raise CameraError(
                VisionErrorCode.CAMERA_CONNECTION_FAILED,
                f"Failed to connect to RTSP stream: {self._url}",
                backend=self.backend_name,
                cause=e if not isinstance(e, CameraError) else None,
            )

    def _connect_sync(self) -> bool:
        """Synchronous connection logic (runs in thread)."""
        try:
            # Open container
            options = {}
            if self._url.startswith("rtsp://"):
                # RTSP-specific options for better streaming
                options = {
                    "rtsp_transport": "tcp",
                    "stimeout": "5000000",  # 5 second timeout in microseconds
                }

            self._container = _av.open(self._url, options=options)

            # Find video stream
            self._stream = self._container.streams.video[0]
            self._stream.thread_type = "AUTO"  # Enable multi-threaded decoding

            # Set frame rate from config
            if self._config.fps > 0:
                self._stream.codec_context.framerate = (
                    self._config.fps
                )  # type: ignore[attr-defined]

            logger.debug(
                f"Opened stream: {self._stream.codec_context.format.name}, "
                f"{self._stream.width}x{self._stream.height}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to open RTSP stream: {e}")
            return False

    def _decode_loop(self) -> None:
        """Background decode loop running in separate thread.

        Continuously decodes frames from the stream and puts them
        in the frame queue. Handles stream reconnection.
        """
        consecutive_errors = 0
        max_errors = 10

        while not self._stop_event.is_set():
            try:
                if self._container is None or self._stream is None:
                    # Attempt reconnection
                    if not self._connect_sync():
                        self._stop_event.wait(self._reconnect_timeout)
                        continue

                for packet in self._container.demux(self._stream):
                    if self._stop_event.is_set():
                        break

                    for frame in packet.decode():
                        if self._stop_event.is_set():
                            break

                        # Convert to numpy array (RGB format)
                        img = frame.to_ndarray(format="rgb24")

                        # Resize if needed
                        if (
                            img.shape[1] != self._config.width
                            or img.shape[0] != self._config.height
                        ):
                            # Simple resize using PIL if available
                            try:
                                from PIL import Image

                                pil_img = Image.fromarray(img)
                                pil_img = pil_img.resize(
                                    (self._config.width, self._config.height),
                                    Image.Resampling.BILINEAR,
                                )
                                img = np.array(pil_img)
                            except ImportError:
                                pass  # Keep original size

                        # Put in queue (non-blocking, drop old frames if full)
                        frame_obj = Frame(
                            data=img,
                            timestamp=time(),
                            metadata={"source": self._url},
                        )

                        # Clear queue if full to keep latest frame
                        if self._frame_queue.full():
                            try:
                                self._frame_queue.get_nowait()
                            except Empty:
                                pass

                        self._frame_queue.put(frame_obj)
                        consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"Decode error ({consecutive_errors}): {e}")

                if consecutive_errors >= max_errors:
                    logger.error("Too many decode errors, stopping decode thread")
                    self._connected = False
                    break

                # Try to reconnect
                self._container = None
                self._stop_event.wait(self._reconnect_timeout)

    async def disconnect(self) -> None:
        """Disconnect from RTSP stream and cleanup resources."""
        logger.info(f"Disconnecting from RTSP stream: {self._url}")

        # Stop decode thread
        self._stop_event.set()

        if self._decode_thread and self._decode_thread.is_alive():
            self._decode_thread.join(timeout=2.0)

        # Close container
        if self._container:
            try:
                self._container.close()
            except Exception as e:
                logger.warning(f"Error closing container: {e}")

        self._container = None
        self._stream = None
        self._connected = False

        # Clear frame queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break

    async def capture_frame(self) -> Frame:
        """Capture a frame from the RTSP stream.

        Returns:
            Frame object with latest image data.

        Raises:
            CameraError: If not connected or timeout waiting for frame.
        """
        if not self.is_connected:
            raise CameraError(
                VisionErrorCode.CAMERA_NOT_CONNECTED,
                "Not connected to RTSP stream. Call connect() first.",
                backend=self.backend_name,
            )

        try:
            # Get frame from queue with timeout
            frame = await asyncio.get_event_loop().run_in_executor(
                None, self._frame_queue.get, True, 2.0  # 2 second timeout
            )
            return frame

        except Empty:
            raise CameraError(
                VisionErrorCode.CAMERA_TIMEOUT,
                "Timeout waiting for frame from RTSP stream",
                backend=self.backend_name,
            )

    def get_info(self) -> Dict[str, Any]:
        """Get camera information and configuration.

        Returns:
            Dictionary with backend info and stream details.
        """
        info = {
            "backend": self.backend_name,
            "url": self._url,
            "connected": self._connected,
            "config": {
                "width": self._config.width,
                "height": self._config.height,
                "fps": self._config.fps,
            },
            "pyav_available": self._pyav_available,
        }

        if self._stream:
            info["stream_info"] = {
                "width": self._stream.width,
                "height": self._stream.height,
                "fps": float(self._stream.average_rate)
                if self._stream.average_rate
                else 0,
                "codec": self._stream.codec_context.name,
            }

        return info

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"RtspCameraProvider(url={self._url!r}, "
            f"connected={self._connected})"
        )
