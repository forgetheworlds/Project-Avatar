#!/bin/bash
# Entrypoint for PX4 SITL with Gazebo Harmonic simulation
# Wave 1 D4.2: Launch Gazebo X500 simulation on UDP 14540

set -euo pipefail

# Gazebo vehicle model (default: X500 quadrotor)
GZ_MODEL="${GZ_MODEL:-x500}"
GZ_WORLD="${GZ_WORLD:-empty}"

echo "Starting PX4 SITL Gazebo Harmonic simulation..."
echo "Gazebo model: ${GZ_MODEL}"
echo "Gazebo world: ${GZ_WORLD}"
echo "MAVLink UDP port: 14540"
echo "LIBGL_ALWAYS_SOFTWARE: ${LIBGL_ALWAYS_SOFTWARE}"

# Source the xvfb wrapper for virtual display
source /app/docker/sim-gazebo/xvfb-wrapper.sh

# Change to PX4 build directory
cd /px4/build/px4_sitl_default

# Set environment for Gazebo simulation
export PX4_SYS_AUTOSTART=4001  # X500 quadrotor
export PX4_SIMULATOR=gz
export PX4_GZ_MODEL=${GZ_MODEL}
export PX4_GZ_WORLD=${GZ_WORLD}

# Launch PX4 SITL with Gazebo X500
exec ./bin/px4 -d -p /px4/ROMFS/px4fmu_common
