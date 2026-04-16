"""Runtime profiles for SITL and hardware connection boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProfile:
    """Configuration seam between simulated and physical drone runtimes."""

    name: str
    system_address: str
    camera_backend: str
    detector_backend: str
    requires_px4_parameter_check: bool


SITL_PROFILE = RuntimeProfile(
    name="sitl",
    system_address="udp://:14540",
    camera_backend="mock_camera",
    detector_backend="mock_detector",
    requires_px4_parameter_check=False,
)

HARDWARE_PROFILE = RuntimeProfile(
    name="hardware",
    system_address="serial:///dev/ttyACM0:921600",
    camera_backend="rtsp_camera",
    detector_backend="yolo_detector",
    requires_px4_parameter_check=True,
)
