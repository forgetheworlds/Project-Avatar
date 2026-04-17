import pytest

from avatar.vision.errors import CameraError, VisionErrorCode
from avatar.vision.providers import GazeboCameraProvider, list_camera_backends


def test_gazebo_camera_provider_available_in_registry():
    """GazeboCameraProvider should be registered in providers."""
    backends = list_camera_backends()
    assert "gazebo" in backends or "gazebo_camera" in backends


async def test_gazebo_camera_provider_mock_mode():
    """GazeboCameraProvider should work in mock mode."""
    from avatar.vision.providers import get_camera_provider

    if "gazebo" not in list_camera_backends():
        pytest.skip("GazeboCameraProvider not registered")

    GazeboProvider = get_camera_provider("gazebo")
    provider = GazeboProvider(use_mock=True)

    await provider.connect()
    frame = await provider.capture_frame()

    assert frame.data.shape[0] > 0  # Has height
    assert frame.data.shape[1] > 0  # Has width
    assert frame.data.shape[2] == 3  # RGB

    await provider.disconnect()


async def test_gazebo_camera_provider_ros_mode_requires_bridge():
    """GazeboCameraProvider ROS mode should require rosbridge URL."""
    from avatar.vision.providers import get_camera_provider

    if "gazebo" not in list_camera_backends():
        pytest.skip("GazeboCameraProvider not registered")

    GazeboProvider = get_camera_provider("gazebo")
    provider = GazeboProvider(use_mock=False)  # ROS mode without URL

    with pytest.raises(CameraError) as exc_info:
        await provider.connect()

    assert exc_info.value.code == VisionErrorCode.CAMERA_CONNECTION_FAILED
