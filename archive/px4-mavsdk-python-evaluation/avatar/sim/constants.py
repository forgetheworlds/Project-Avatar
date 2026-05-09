"""Simulation constants shared across Avatar SIH/Gazebo tooling.

`SIH_VEHICLE_TARGET` is the PX4 CMake / make target name for Software-In-Hardware
quad simulation, taken from upstream PX4-Autopilot (see
`docs/en/sim_sih/index.md` on the probed commit).

Usage:
    make px4_sitl_sih $SIH_VEHICLE_TARGET

Reference: https://docs.px4.io/en/simulation/sih/
"""

SIH_VEHICLE_TARGET: str = "sihsim_quadx"
