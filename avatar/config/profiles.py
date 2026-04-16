"""Runtime profiles for SITL and hardware connection boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# COM_OBL_RC_ACT parameter values for offboard loss failsafe action
# 0: Disable, 1: Land, 2: Return to Launch, 3: Hold position
ComOblRcAct = Literal[0, 1, 2, 3]


@dataclass(frozen=True)
class RuntimeProfile:
    """Configuration seam between simulated and physical drone runtimes."""

    name: str
    system_address: str
    camera_backend: str
    detector_backend: str
    requires_px4_parameter_check: bool
    com_obl_rc_act: ComOblRcAct = 2  # default: RTL on offboard loss


SITL_PROFILE = RuntimeProfile(
    name="sitl",
    system_address="udp://:14540",
    camera_backend="mock_camera",
    detector_backend="mock_detector",
    requires_px4_parameter_check=False,
    com_obl_rc_act=2,  # RTL on offboard loss (default for SITL x500)
)

HARDWARE_PROFILE = RuntimeProfile(
    name="hardware",
    system_address="serial:///dev/ttyACM0:921600",
    camera_backend="rtsp_camera",
    detector_backend="yolo_detector",
    requires_px4_parameter_check=True,
    com_obl_rc_act=2,  # RTL on offboard loss (safest default for hardware)
)
