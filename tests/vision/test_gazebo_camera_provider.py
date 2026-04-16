import pytest

from avatar.vision.providers import GazeboCameraProvider


def test_gazebo_camera_provider_fails_clearly_without_bridge():
    provider = GazeboCameraProvider()

    with pytest.raises(RuntimeError, match="requires a Gazebo camera transport adapter"):
        provider.capture_frame()
