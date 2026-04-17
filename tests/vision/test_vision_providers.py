import warnings

import numpy as np
import pytest

from avatar.vision.providers import (
    MockCameraProvider,
    MockDetectorProvider,
    VisionBackendConfig,
)
from avatar.vision.providers.base import Frame


async def test_mock_camera_provider_reports_backend_name():
    provider = MockCameraProvider(width=320, height=240)

    await provider.connect()
    frame = await provider.capture_frame()

    assert provider.backend_name == "mock_camera"
    assert frame.data.shape == (240, 320, 3)

    await provider.disconnect()


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_mock_detector_provider_reports_backend_name():
    provider = MockDetectorProvider(confidence_threshold=0.5)
    await provider.initialize()

    frame = Frame(data=np.zeros((240, 320, 3), dtype=np.uint8))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        detections = await provider.detect(frame)

    assert provider.backend_name == "mock_detector"
    assert isinstance(detections, list)


def test_vision_backend_config_defaults_are_explicitly_mock():
    config = VisionBackendConfig()

    assert config.camera_backend == "mock_camera"
    assert config.detector_backend == "mock_detector"
