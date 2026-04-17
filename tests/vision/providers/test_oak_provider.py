"""Tests for OAK (Luxonis) camera provider.

Tests verify graceful handling when DepthAI SDK is not installed.
"""

import numpy as np
import pytest

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers import list_camera_backends
from avatar.vision.providers.base import CameraConfig, Frame

# Check if DepthAI SDK is available
try:
    import depthai as dai

    DEPTHAI_AVAILABLE = True
except ImportError:
    DEPTHAI_AVAILABLE = False

# Check if provider is registered
OAK_REGISTERED = "oak" in list_camera_backends()


class TestOakProviderAvailability:
    """Tests for OAK provider availability."""

    def test_oak_provider_registered_when_sdk_available(self):
        """OAK provider should be registered if SDK is available."""
        if DEPTHAI_AVAILABLE:
            assert "oak" in list_camera_backends()
        else:
            assert "oak" not in list_camera_backends()


@pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
class TestOakProviderInstantiation:
    """Tests for OAK provider instantiation."""

    def test_can_be_instantiated(self):
        """OAK provider should be instantiable even without camera."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()

        assert provider.backend_name == "oak"
        assert not provider.is_connected

    def test_can_be_instantiated_with_device_id(self):
        """OAK provider can be created with device ID."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider(device_id="14442C10D13EABD300")

        assert provider._device_id == "14442C10D13EABD300"

    def test_can_be_instantiated_with_config(self):
        """OAK provider can be created with configuration."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        config = CameraConfig(width=1280, height=720, fps=30.0)
        provider = OakCameraProvider(config=config)

        assert provider._config.width == 1280
        assert provider._config.height == 720

    def test_get_info_without_connection(self):
        """get_info should work without connection."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()

        info = provider.get_info()

        assert info["backend"] == "oak"
        assert info["connected"] is False
        assert info["sdk_available"] == DEPTHAI_AVAILABLE
        assert "config" in info


class TestOakProviderWithoutSDK:
    """Tests for OAK provider when SDK not installed."""

    @pytest.mark.skipif(DEPTHAI_AVAILABLE, reason="Test requires SDK to NOT be installed")
    @pytest.mark.asyncio
    async def test_connect_raises_sdk_not_available(self):
        """Connect should raise clear error when SDK not installed."""
        # Create provider directly to test behavior
        from avatar.vision.providers.oak import OakCameraProvider

        provider = OakCameraProvider()

        with pytest.raises(CameraError) as exc_info:
            await provider.connect()

        assert exc_info.value.code == VisionErrorCode.CAMERA_SDK_NOT_AVAILABLE
        assert "depthai" in exc_info.value.message.lower()
        assert "install" in exc_info.value.message.lower()

    @pytest.mark.skipif(DEPTHAI_AVAILABLE, reason="Test requires SDK to NOT be installed")
    def test_list_devices_reports_unavailable(self):
        """list_devices should report SDK not available."""
        from avatar.vision.providers.oak import OakCameraProvider

        result = OakCameraProvider.list_devices()

        assert result["available"] is False
        assert "error" in result
        assert result["devices"] == []


@pytest.mark.skipif(not DEPTHAI_AVAILABLE, reason="DepthAI SDK not installed")
class TestOakProviderWithSDK:
    """Tests for OAK provider when SDK is available.

    Note: These tests require actual OAK hardware to pass fully.
    They verify the SDK integration works, but may fail without camera.
    """

    @pytest.mark.asyncio
    async def test_connect_attempts_device_connection(self):
        """Connect should attempt to connect to device."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()

        # Note: This is a stub implementation
        # Full implementation requires DepthAI pipeline setup
        try:
            success = await provider.connect()
            # Currently stub returns True but logs warning
            assert success is True

            # Cleanup
            await provider.disconnect()

        except CameraError as e:
            # Expected if no camera or stub limitations
            assert e.code in [
                VisionErrorCode.CAMERA_CONNECTION_FAILED,
                VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED,
            ]

    @pytest.mark.asyncio
    async def test_capture_frame_is_stub(self):
        """capture_frame should indicate stub implementation."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()
        await provider.connect()

        with pytest.raises(CameraError) as exc_info:
            await provider.capture_frame()

        # Stub should raise with helpful message
        assert exc_info.value.code == VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED
        assert "stub" in exc_info.value.message.lower() or "not implemented" in exc_info.value.message.lower()

        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_capture_and_detect_is_stub(self):
        """capture_and_detect should indicate stub implementation."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()
        await provider.connect()

        with pytest.raises(CameraError) as exc_info:
            await provider.capture_and_detect()

        assert exc_info.value.code == VisionErrorCode.CAMERA_FRAME_CAPTURE_FAILED

        await provider.disconnect()

    def test_list_devices_returns_list(self):
        """list_devices should return list of connected devices."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")

        result = OakCameraProvider.list_devices()

        assert result["available"] is True
        assert "count" in result
        assert "devices" in result


class TestOakProviderConfig:
    """Tests for OAK provider configuration."""

    @pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
    def test_default_config(self):
        """Default configuration should be sensible."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()

        assert provider._config.width == 640
        assert provider._config.height == 480
        assert provider._config.fps == 30.0
        assert provider._enable_depth is True  # Default enabled

    @pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
    def test_custom_resolution(self):
        """Custom resolution should be stored."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider(
            config=CameraConfig(width=1920, height=1080, fps=15.0)
        )

        assert provider._config.width == 1920
        assert provider._config.height == 1080
        assert provider._config.fps == 15.0

    @pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
    def test_model_configuration(self):
        """YOLO model can be configured for on-device inference."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider(model="yolov8n", confidence_threshold=0.6)

        assert provider._model == "yolov8n"
        assert provider._confidence_threshold == 0.6

    @pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
    def test_depth_configuration(self):
        """Provider should support depth configuration."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider(enable_depth=False)

        info = provider.get_info()

        assert info["config"]["enable_depth"] is False


class TestOakProviderOnDeviceInference:
    """Tests for OAK's on-device inference capability."""

    @pytest.mark.skipif(not OAK_REGISTERED, reason="OakCameraProvider not registered")
    def test_on_device_inference_concept(self):
        """Verify on-device inference is part of the interface."""
        from avatar.vision.providers import get_camera_provider

        OakCameraProvider = get_camera_provider("oak")
        provider = OakCameraProvider()

        # Check that capture_and_detect method exists
        assert hasattr(provider, "capture_and_detect")

        # This is OAK's unique feature - combined capture and inference
        # Full implementation requires DepthAI pipeline setup
        info = provider.get_info()
        assert "model" in info["config"]
        # Confidence threshold is stored as private attribute
        assert hasattr(provider, "_confidence_threshold")
