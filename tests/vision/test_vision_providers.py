import numpy as np
from avatar.vision.providers import (
    MockCameraProvider,
    MockDetectorProvider,
    VisionBackendConfig,
)


def test_mock_camera_provider_reports_backend_name():
    provider = MockCameraProvider(width=320, height=240)

    frame = provider.capture_frame()

    assert provider.backend_name == "mock_camera"
    assert frame.shape == (240, 320, 3)


def test_mock_detector_provider_reports_backend_name():
    provider = MockDetectorProvider(confidence_threshold=0.5)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    detections = provider.detect(frame)

    assert provider.backend_name == "mock_detector"
    assert isinstance(detections, list)


def test_vision_backend_config_defaults_are_explicitly_mock():
    config = VisionBackendConfig()

    assert config.camera_backend == "mock_camera"
    assert config.detector_backend == "mock_detector"
