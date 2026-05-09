#!/usr/bin/env python3
"""Detect locally available simulator commands for Project Avatar."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def detect_capabilities(project_root: Path) -> dict[str, object]:
    """Return local simulator availability and recommended launch commands."""
    px4_dir = project_root / "PX4-Autopilot"
    return {
        "px4_autopilot_dir": str(px4_dir),
        "px4_autopilot_present": px4_dir.exists(),
        "make_present": shutil.which("make") is not None,
        "gz_present": shutil.which("gz") is not None,
        "gazebo_present": shutil.which("gazebo") is not None,
        "java_present": shutil.which("java") is not None,
        "recommended_order": ["gazebo_gz_x500", "px4_sih", "jmavsim"],
        "commands": {
            "gazebo_gz_x500": "cd PX4-Autopilot && make px4_sitl gz_x500",
            "gazebo_depth": "cd PX4-Autopilot && make px4_sitl gz_x500_depth",
            "gazebo_vision": "cd PX4-Autopilot && make px4_sitl gz_x500_vision",
            "px4_sih": "cd PX4-Autopilot && make px4_sitl_default sihsim_quadx",
            "jmavsim": "cd PX4-Autopilot && make px4_sitl jmavsim",
        },
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    print(json.dumps(detect_capabilities(project_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
