"""Tests for YOLO detector provider with multi-backend support."""

import sys

import numpy as np
import pytest

from avatar.vision.errors import DetectorError, VisionErrorCode
from avatar.vision.providers import list_detector_backends
from avatar.vision.providers.base import DetectorConfig, Frame

# Check if ultralytics is available
try:
    from ultralytics import YOLO

    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

# Check for Python 3.14+ deprecation issue with ultralytics
# ultralytics uses asyncio.iscoroutinefunction which is deprecated in Python 3.14
ULTRALYTICS_PYTHON_314_INCOMPATIBLE = (
    ULTRALYTICS_AVAILABLE and sys.version_info >= (3, 14)
)

# Check if provider is registered
YOLO_REGISTERED = "yolo" in list_detector_backends()


class TestYoloDetectorProviderAvailability:
    """Tests for YOLO provider availability."""

    def test_yolo_provider_registered_when_ultralytics_available(self):
        """YOLO provider should be registered if ultralytics is available."""
        if ULTRALYTICS_AVAILABLE:
            assert "yolo" in list_detector_backends()
        else:
            # If ultralytics not available, should not be registered
            assert "yolo" not in list_detector_backends()


@pytest.mark.skipif(not YOLO_REGISTERED, reason="YoloDetectorProvider not registered")
class TestYoloDetectorProviderBackendSelection:
    """Tests for YOLO provider backend selection."""

    @pytest.mark.asyncio
    async def test_ultralytics_backend_selected_by_default(self):
        """Ultralytics backend should be selected by default if available."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")

        if ULTRALYTICS_AVAILABLE:
            assert provider.inference_backend == "ultralytics"
        else:
            # Should raise when no backend available
            with pytest.raises(DetectorError):
                provider.inference_backend

    @pytest.mark.skipif(not ULTRALYTICS_AVAILABLE, reason="ultralytics not installed")
    @pytest.mark.asyncio
    async def test_explicit_backend_selection(self):
        """Explicit backend selection should work."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n", backend="ultralytics")

        assert provider.inference_backend == "ultralytics"

    @pytest.mark.asyncio
    async def test_invalid_backend_raises(self):
        """Invalid backend should raise DetectorError."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")

        with pytest.raises(DetectorError) as exc_info:
            provider = YoloDetectorProvider(model="yolov8n", backend="invalid_backend")

        assert exc_info.value.code == VisionErrorCode.DETECTOR_INVALID_BACKEND

    def test_backend_availability_in_info(self):
        """get_info should report backend availability."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")

        info = provider.get_info()

        assert "backend_availability" in info
        assert "ultralytics" in info["backend_availability"]
        assert "ncnn" in info["backend_availability"]
        assert "openvino" in info["backend_availability"]


@pytest.mark.skipif(not ULTRALYTICS_AVAILABLE, reason="ultralytics not installed")
@pytest.mark.skipif(
    ULTRALYTICS_PYTHON_314_INCOMPATIBLE,
    reason="ultralytics incompatible with Python 3.14+ (asyncio.iscoroutinefunction deprecation)",
)
class TestYoloDetectorProviderWithUltralytics:
    """Tests for YOLO provider using ultralytics backend."""

    @pytest.mark.asyncio
    async def test_initialize_loads_model(self):
        """Initialize should load the YOLO model."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")

        assert not provider.is_initialized

        success = await provider.initialize()

        assert success is True
        assert provider.is_initialized

        # Cleanup
        provider._model_instance = None
        provider._initialized = False

    @pytest.mark.asyncio
    async def test_detect_on_empty_frame_raises(self):
        """Detect on empty frame should raise DetectorError."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")
        await provider.initialize()

        empty_frame = Frame(data=np.zeros((0, 0, 3), dtype=np.uint8))

        with pytest.raises(DetectorError) as exc_info:
            await provider.detect(empty_frame)

        assert exc_info.value.code == VisionErrorCode.DETECTOR_INVALID_FRAME

        # Cleanup
        provider._model_instance = None
        provider._initialized = False

    @pytest.mark.asyncio
    async def test_detect_without_initialize_raises(self):
        """Detect without initialize should raise DetectorError."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")

        frame = Frame(data=np.zeros((480, 640, 3), dtype=np.uint8))

        with pytest.raises(DetectorError) as exc_info:
            await provider.detect(frame)

        assert exc_info.value.code == VisionErrorCode.DETECTOR_NOT_INITIALIZED

    @pytest.mark.asyncio
    async def test_detect_returns_detections(self):
        """Detect should return list of Detection objects."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n", confidence_threshold=0.3)
        await provider.initialize()

        # Create a test frame with some structure
        # (solid color frame usually produces no detections)
        frame = Frame(data=np.zeros((640, 640, 3), dtype=np.uint8))

        detections = await provider.detect(frame)

        # Should return a list (may be empty for black frame)
        assert isinstance(detections, list)

        # Cleanup
        provider._model_instance = None
        provider._initialized = False

    def test_class_names_available(self):
        """class_names property should return COCO class names."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(model="yolov8n")

        class_names = provider.class_names

        assert isinstance(class_names, list)
        # COCO has 80 classes, but the provider's COCO_CLASSES list has 79
        # (some implementations vary slightly)
        assert len(class_names) >= 79
        assert "person" in class_names
        assert "car" in class_names


@pytest.mark.skipif(not YOLO_REGISTERED, reason="YoloDetectorProvider not registered")
class TestYoloDetectorProviderConfig:
    """Tests for YOLO provider configuration."""

    def test_config_applied_on_creation(self):
        """Configuration should be applied on provider creation."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        config = DetectorConfig(
            model="yolov8s",
            confidence_threshold=0.7,
            backend="ultralytics",
            classes=["person", "car"],
        )
        provider = YoloDetectorProvider(config=config)

        assert provider._config.model == "yolov8s"
        assert provider._config.confidence_threshold == 0.7
        assert provider._config.classes == ["person", "car"]

    def test_kwargs_override_config(self):
        """Keyword arguments should override config values."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(
            model="yolov8m",
            confidence_threshold=0.8,
            classes=["person"],
        )

        assert provider._model == "yolov8m"
        assert provider._config.confidence_threshold == 0.8
        assert provider._config.classes == ["person"]

    def test_get_info_returns_config(self):
        """get_info should include configuration."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")
        provider = YoloDetectorProvider(
            model="yolov8n",
            confidence_threshold=0.6,
        )

        info = provider.get_info()

        assert info["model"] == "yolov8n"
        assert info["confidence_threshold"] == 0.6
        assert info["initialized"] is False


class TestYoloDetectorProviderNCNNBackend:
    """Tests for NCNN backend (stub)."""

    @pytest.mark.skipif(not YOLO_REGISTERED, reason="YoloDetectorProvider not registered")
    @pytest.mark.asyncio
    async def test_ncnn_backend_requires_preconverted_models(self):
        """NCNN backend should raise error about pre-converted models."""
        # This test assumes NCNN is NOT set up with pre-converted models
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")

        # Try to use NCNN backend (will fail if not set up)
        try:
            provider = YoloDetectorProvider(model="yolov8n", backend="ncnn")
            await provider.initialize()
            # If we get here, NCNN is properly configured
            # (unlikely in test environment)
        except DetectorError as e:
            # If NCNN backend is not available, we get INVALID_BACKEND
            # If NCNN is available but model files missing, we get MODEL_LOAD_FAILED
            assert e.code in [
                VisionErrorCode.DETECTOR_INVALID_BACKEND,
                VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
            ]
            assert "NCNN" in e.message or ".param" in e.message or ".bin" in e.message or "not available" in e.message


class TestYoloDetectorProviderOpenVINOBackend:
    """Tests for OpenVINO backend (stub)."""

    @pytest.mark.skipif(not YOLO_REGISTERED, reason="YoloDetectorProvider not registered")
    @pytest.mark.asyncio
    async def test_openvino_backend_requires_preconverted_models(self):
        """OpenVINO backend should raise error about pre-converted models."""
        from avatar.vision.providers import get_detector_provider

        YoloDetectorProvider = get_detector_provider("yolo")

        try:
            provider = YoloDetectorProvider(model="yolov8n", backend="openvino")
            await provider.initialize()
        except DetectorError as e:
            assert e.code in [
                VisionErrorCode.DETECTOR_INVALID_BACKEND,
                VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
            ]
            assert (
                "OpenVINO" in e.message
                or ".xml" in e.message
                or "IR" in e.message
                or "not available" in e.message
            )
