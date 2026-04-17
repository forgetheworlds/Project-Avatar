"""Tests for RealSense camera provider.

Tests verify graceful handling when RealSense SDK is not installed.
"""

import numpy as np
import pytest

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers import list_camera_backends
from avatar.vision.providers.base import CameraConfig, Frame

# Check if RealSense SDK is available
try:
    import pyrealsense2 as rs

    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

# Check if provider is registered
REALSENSE_REGISTERED = "realsense" in list_camera_backends()


class TestRealSenseProviderAvailability:
    """Tests for RealSense provider availability."""

    def test_realsense_provider_registered_when_sdk_available(self):
        """RealSense provider should be registered if SDK is available."""
        if REALSENSE_AVAILABLE:
            assert "realsense" in list_camera_backends()
        else:
            assert "realsense" not in list_camera_backends()


@pytest.mark.skipif(
    not REALSENSE_REGISTERED, reason="RealSenseCameraProvider not registered"
)
class TestRealSenseProviderInstantiation:
    """Tests for RealSense provider instantiation."""

    def test_can_be_instantiated(self):
        """RealSense provider should be instantiable even without camera."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider()

        assert provider.backend_name == "realsense"
        assert not provider.is_connected

    def test_can_be_instantiated_with_serial(self):
        """RealSense provider can be created with serial number."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider(serial="123456")

        assert provider._serial == "123456"

    def test_can_be_instantiated_with_config(self):
        """RealSense provider can be created with configuration."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        config = CameraConfig(width=1280, height=720, fps=30.0)
        provider = RealSenseCameraProvider(config=config)

        assert provider._config.width == 1280
        assert provider._config.height == 720

    def test_get_info_without_connection(self):
        """get_info should work without connection."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider()

        info = provider.get_info()

        assert info["backend"] == "realsense"
        assert info["connected"] is False
        assert info["sdk_available"] == REALSENSE_AVAILABLE
        assert "config" in info


class TestRealSenseProviderWithoutSDK:
    """Tests for RealSense provider when SDK not installed."""

    @pytest.mark.skipif(REALSENSE_AVAILABLE, reason="Test requires SDK to NOT be installed")
    @pytest.mark.asyncio
    async def test_connect_raises_sdk_not_available(self):
        """Connect should raise clear error when SDK not installed."""
        # Create provider directly to test behavior
        from avatar.vision.providers.realsense import RealSenseCameraProvider

        provider = RealSenseCameraProvider()

        with pytest.raises(CameraError) as exc_info:
            await provider.connect()

        assert exc_info.value.code == VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE
        assert "pyrealsense2" in exc_info.value.message.lower()
        assert "install" in exc_info.value.message.lower()

    @pytest.mark.skipif(REALSENSE_AVAILABLE, reason="Test requires SDK to NOT be installed")
    def test_list_devices_reports_unavailable(self):
        """list_devices should report SDK not available."""
        from avatar.vision.providers.realsense import RealSenseCameraProvider

        result = RealSenseCameraProvider.list_devices()

        assert result["available"] is False
        assert "error" in result
        assert result["devices"] == []


@pytest.mark.skipif(
    not REALSENSE_AVAILABLE, reason="RealSense SDK not installed"
)
class TestRealSenseProviderWithSDK:
    """Tests for RealSense provider when SDK is available.

    Note: These tests require actual RealSense hardware to pass fully.
    They verify the SDK integration works, but may fail without camera.
    """

    @pytest.mark.asyncio
    async def test_connect_attempts_device_connection(self):
        """Connect should attempt to connect to device."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider()

        # Will fail if no camera connected, but tests the flow
        try:
            success = await provider.connect()
            assert success is True
            assert provider.is_connected

            # Cleanup
            await provider.disconnect()

        except CameraError as e:
            # Expected if no camera connected
            assert e.code in [
                VisionErrorCode.CAMERA_CONNECTION_FAILED,
            ]

    @pytest.mark.asyncio
    async def test_capture_without_connect_raises(self):
        """Capture should raise if not connected."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider()

        with pytest.raises(CameraError) as exc_info:
            await provider.capture_frame()

        assert exc_info.value.code == VisionErrorCode.CAMERA_NOT_CONNECTED

    def test_list_devices_returns_list(self):
        """list_devices should return list of connected devices."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")

        result = RealSenseCameraProvider.list_devices()

        assert result["available"] is True
        assert "count" in result
        assert "devices" in result
        # count may be 0 if no camera connected

    def test_depth_configuration(self):
        """Provider should support depth configuration."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider(enable_depth=True, enable_infrared=True)

        info = provider.get_info()

        assert info["config"]["enable_depth"] is True
        assert info["config"]["enable_infrared"] is True


class TestRealSenseProviderConfig:
    """Tests for RealSense provider configuration."""

    @pytest.mark.skipif(
        not REALSENSE_REGISTERED, reason="RealSenseCameraProvider not registered"
    )
    def test_default_config(self):
        """Default configuration should be sensible."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider()

        assert provider._config.width == 640
        assert provider._config.height == 480
        assert provider._config.fps == 30.0
        assert provider._enable_depth is True  # Default enabled

    @pytest.mark.skipif(
        not REALSENSE_REGISTERED, reason="RealSenseCameraProvider not registered"
    )
    def test_custom_resolution(self):
        """Custom resolution should be stored."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider(
            config=CameraConfig(width=1920, height=1080, fps=15.0)
        )

        assert provider._config.width == 1920
        assert provider._config.height == 1080
        assert provider._config.fps == 15.0

    @pytest.mark.skipif(
        not REALSENSE_REGISTERED, reason="RealSenseCameraProvider not registered"
    )
    def test_disable_depth(self):
        """Depth stream can be disabled."""
        from avatar.vision.providers import get_camera_provider

        RealSenseCameraProvider = get_camera_provider("realsense")
        provider = RealSenseCameraProvider(enable_depth=False)

        assert provider._enable_depth is False
