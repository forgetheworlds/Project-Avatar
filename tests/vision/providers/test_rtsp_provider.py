"""Tests for RTSP camera provider.

Tests use file:// URLs to avoid requiring live RTSP streams.
"""

import asyncio
import os
import tempfile

import numpy as np
import pytest

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers import list_camera_backends
from avatar.vision.providers.base import CameraConfig, Frame

# Check if PyAV is available for these tests
try:
    import av

    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False

# Check if provider is registered
RTSP_REGISTERED = "rtsp" in list_camera_backends()


@pytest.mark.skipif(not RTSP_REGISTERED, reason="RtspCameraProvider not registered")
class TestRtspCameraProviderAvailability:
    """Tests for RTSP provider availability and registration."""

    def test_rtsp_provider_registered_when_pyav_available(self):
        """RTSP provider should be registered if PyAV is available."""
        if PYAV_AVAILABLE:
            assert "rtsp" in list_camera_backends()
        else:
            # If PyAV not available, should not be registered
            assert "rtsp" not in list_camera_backends()


@pytest.mark.skipif(not PYAV_AVAILABLE, reason="PyAV not installed")
class TestRtspCameraProviderWithFile:
    """Tests for RTSP provider using file:// URLs."""

    @pytest.fixture
    def sample_video_path(self):
        """Create a sample video file for testing."""
        # Create a minimal valid MP4 file
        # In production, you'd use a real test video
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name

        # Write minimal MP4 header (not valid video, but tests error handling)
        # For real testing, use a proper test video file
        with open(path, "wb") as f:
            # Minimal ftyp box for MP4
            f.write(b"\x00\x00\x00\x18ftypmp42")
            f.write(b"\x00\x00\x00\x00mp42mp41")
            f.write(b"\x00\x00\x00\x08free")

        yield path

        # Cleanup
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.mark.asyncio
    async def test_rtsp_provider_can_be_instantiated(self):
        """RTSP provider should be instantiable."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(url="file:///nonexistent.mp4")

        assert provider.backend_name == "rtsp"
        assert provider.url == "file:///nonexistent.mp4"
        assert not provider.is_connected

    @pytest.mark.asyncio
    async def test_rtsp_provider_connect_to_invalid_file_raises(self):
        """Connecting to nonexistent file should raise CameraError."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(url="file:///nonexistent_video.mp4")

        with pytest.raises(CameraError) as exc_info:
            await provider.connect()

        assert exc_info.value.code == VisionErrorCode.CAMERA_CONNECTION_FAILED
        assert "rtsp" in exc_info.value.backend

    @pytest.mark.asyncio
    async def test_rtsp_provider_capture_without_connect_raises(self):
        """Capturing without connect should raise CameraError."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(url="file:///test.mp4")

        with pytest.raises(CameraError) as exc_info:
            await provider.capture_frame()

        assert exc_info.value.code == VisionErrorCode.CAMERA_NOT_CONNECTED

    @pytest.mark.asyncio
    async def test_rtsp_provider_get_info(self):
        """get_info should return provider information."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(
            url="rtsp://camera.local/stream",
            config=CameraConfig(width=1280, height=720, fps=30.0),
        )

        info = provider.get_info()

        assert info["backend"] == "rtsp"
        assert info["url"] == "rtsp://camera.local/stream"
        assert info["pyav_available"] is True
        assert info["config"]["width"] == 1280
        assert info["config"]["height"] == 720


class TestRtspCameraProviderWithoutPyAV:
    """Tests for RTSP provider behavior when PyAV not installed."""

    @pytest.mark.skipif(PYAV_AVAILABLE, reason="Test requires PyAV to NOT be installed")
    @pytest.mark.asyncio
    async def test_connect_raises_sdk_not_available(self):
        """Connect should raise CameraError when PyAV not installed."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(url="rtsp://camera.local/stream")

        with pytest.raises(CameraError) as exc_info:
            await provider.connect()

        assert exc_info.value.code == VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE
        assert "PyAV" in exc_info.value.message or "av" in exc_info.value.message


class TestRtspCameraProviderConfig:
    """Tests for RTSP provider configuration."""

    @pytest.mark.skipif(not PYAV_AVAILABLE, reason="PyAV not installed")
    def test_config_applied_on_creation(self):
        """Configuration should be applied on provider creation."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        config = CameraConfig(width=1920, height=1080, fps=60.0, source="rtsp://test")
        provider = RtspCameraProvider(url="rtsp://test", config=config)

        assert provider._config.width == 1920
        assert provider._config.height == 1080
        assert provider._config.fps == 60.0

    @pytest.mark.skipif(not PYAV_AVAILABLE, reason="PyAV not installed")
    def test_default_config_used_if_not_provided(self):
        """Default configuration should be used if not provided."""
        from avatar.vision.providers import get_camera_provider

        RtspCameraProvider = get_camera_provider("rtsp")
        provider = RtspCameraProvider(url="rtsp://test")

        assert provider._config.width == 640
        assert provider._config.height == 480
        assert provider._config.fps == 30.0
