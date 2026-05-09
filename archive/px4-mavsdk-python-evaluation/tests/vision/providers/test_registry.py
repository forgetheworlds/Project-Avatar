"""Tests for vision provider registry."""

import pytest

from avatar.vision.errors import ProviderRegistryError, VisionErrorCode
from avatar.vision.providers import (
    CAMERA_PROVIDERS,
    DETECTOR_PROVIDERS,
    get_camera_provider,
    get_detector_provider,
    list_camera_backends,
    list_detector_backends,
)
from avatar.vision.providers.base import CameraProvider, DetectorProvider


class TestCameraProviderRegistry:
    """Tests for camera provider registry."""

    def test_registry_lists_expected_backends(self):
        """Registry should list expected camera backends."""
        backends = list_camera_backends()

        # Core backends always available
        assert "mock" in backends
        assert "mock_camera" in backends

        # Gazebo should be available (pure Python)
        assert "gazebo" in backends or "gazebo_camera" in backends

        # RTSP may be available if PyAV installed
        # (test doesn't require it, just check if registered)
        if "rtsp" in backends:
            assert CAMERA_PROVIDERS["rtsp"].backend_name == "rtsp"

    def test_get_camera_provider_returns_class(self):
        """get_camera_provider should return provider class."""
        provider_class = get_camera_provider("mock")
        assert provider_class.backend_name in ("mock", "mock_camera")

    def test_get_camera_provider_raises_for_unknown(self):
        """get_camera_provider should raise for unknown backend."""
        with pytest.raises(ProviderRegistryError) as exc_info:
            get_camera_provider("nonexistent_camera")

        assert exc_info.value.code == VisionErrorCode.PROVIDER_NOT_REGISTERED
        assert "nonexistent_camera" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_camera_providers_satisfy_protocol(self):
        """Registered camera providers should satisfy CameraProvider protocol."""
        from typing import runtime_checkable

        # Mock provider should satisfy protocol
        mock_class = get_camera_provider("mock")
        mock_instance = mock_class(width=320, height=240)

        # Check protocol satisfaction (has required attributes)
        assert hasattr(mock_instance, "backend_name")
        assert hasattr(mock_instance, "connect")
        assert hasattr(mock_instance, "disconnect")
        assert hasattr(mock_instance, "capture_frame")
        assert hasattr(mock_instance, "is_connected")
        assert hasattr(mock_instance, "get_info")


class TestDetectorProviderRegistry:
    """Tests for detector provider registry."""

    def test_registry_lists_expected_backends(self):
        """Registry should list expected detector backends."""
        backends = list_detector_backends()

        # Core backends always available
        assert "mock" in backends
        assert "mock_detector" in backends

        # YOLO may be available if ultralytics installed
        # (test doesn't require it, just check if registered)
        if "yolo" in backends:
            assert DETECTOR_PROVIDERS["yolo"].backend_name == "yolo"

    def test_get_detector_provider_returns_class(self):
        """get_detector_provider should return provider class."""
        provider_class = get_detector_provider("mock")
        assert provider_class.backend_name in ("mock", "mock_detector")

    def test_get_detector_provider_raises_for_unknown(self):
        """get_detector_provider should raise for unknown backend."""
        with pytest.raises(ProviderRegistryError) as exc_info:
            get_detector_provider("nonexistent_detector")

        assert exc_info.value.code == VisionErrorCode.PROVIDER_NOT_REGISTERED
        assert "nonexistent_detector" in str(exc_info.value)


class TestProviderRegistryConsistency:
    """Tests for registry consistency."""

    def test_camera_registry_keys_match_backend_names(self):
        """Registry keys should match provider backend_name."""
        for key, provider_class in CAMERA_PROVIDERS.items():
            # Some keys are aliases (e.g., "mock" -> "mock_camera")
            # Check that at least one matches or key is an alias
            assert provider_class.backend_name == key or key in [
                "mock",
                "mock_camera",
                "gazebo",
                "gazebo_camera",
            ]

    def test_detector_registry_keys_match_backend_names(self):
        """Registry keys should match provider backend_name."""
        for key, provider_class in DETECTOR_PROVIDERS.items():
            # Allow aliases
            assert provider_class.backend_name == key or key in [
                "mock",
                "mock_detector",
            ]

    def test_registry_imports_all_providers(self):
        """Registry should import all provider modules successfully."""
        # This test verifies imports don't raise
        assert len(CAMERA_PROVIDERS) > 0
        assert len(DETECTOR_PROVIDERS) > 0
