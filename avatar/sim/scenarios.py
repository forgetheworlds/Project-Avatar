"""Simulation scenarios that represent real Project Avatar use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioKind = Literal[
    "runner_follow",
    "sailboat_follow",
    "nature_cinematic",
    "indoor_obstacle_room",
    "snowboard_halfpipe",
    "skate_bowl",
]


@dataclass(frozen=True)
class SimulationScenario:
    """A realistic scenario that must be validated before hardware purchase."""

    name: str
    kind: ScenarioKind
    simulator: str
    px4_command: str
    required_backends: tuple[str, ...]
    acceptance_test: str
    description: str


SCENARIOS: dict[str, SimulationScenario] = {
    "runner_follow_basic": SimulationScenario(
        name="runner_follow_basic",
        kind="runner_follow",
        simulator="gazebo_or_mock_target",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "vision_state"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_runner_follow.py -q --run-sitl",
        description=(
            "Drone takes off, tracks a moving runner target state, keeps safe follow "
            "distance, then lands."
        ),
    ),
    "sailboat_follow_wide": SimulationScenario(
        name="sailboat_follow_wide",
        kind="sailboat_follow",
        simulator="gazebo_marine_world_or_mock_target",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "vision_state", "wind_safe_offsets"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_sailboat_follow.py -q --run-sitl",
        description=(
            "Drone follows a slow moving boat from a wide lateral offset without "
            "descending below safe altitude."
        ),
    ),
    "nature_orbit_reveal": SimulationScenario(
        name="nature_orbit_reveal",
        kind="nature_cinematic",
        simulator="gazebo_gz_x500",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500",
        required_backends=("mcp_stdio", "mavsdk", "cinematic_templates"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_nature_cinematic.py -q --run-sitl",
        description="Drone runs a slow reveal and orbit shot around a static landmark target.",
    ),
    "indoor_obstacle_room_depth": SimulationScenario(
        name="indoor_obstacle_room_depth",
        kind="indoor_obstacle_room",
        simulator="gazebo_depth",
        px4_command="cd PX4-Autopilot && make px4_sitl gz_x500_depth",
        required_backends=("mcp_stdio", "mavsdk", "depth_camera", "guardian_geofence"),
        acceptance_test="python3 -m pytest tests/e2e/test_scenario_indoor_obstacles.py -q --run-sitl",
        description=(
            "Drone navigates a room-like obstacle layout using conservative speed and "
            "aborts on obstacle or vision loss."
        ),
    ),
}


def get_scenario(name: str) -> SimulationScenario:
    return SCENARIOS[name]


def list_scenarios() -> list[SimulationScenario]:
    return list(SCENARIOS.values())
