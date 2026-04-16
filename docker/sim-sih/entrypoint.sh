#!/bin/bash
# Entrypoint for PX4 SITL SIH simulation
# Wave 1 D4.1: Launch SIH quad simulation on UDP 14540

set -euo pipefail

# SIH vehicle target (pinned by avatar/sim/constants.py)
SIH_VEHICLE_TARGET="${SIH_VEHICLE_TARGET:-sihsim_quadx}"

# Map SIH vehicle target to SYS_AUTOSTART ID
case "${SIH_VEHICLE_TARGET}" in
    sihsim_quadx)   PX4_SYS_AUTOSTART=10040 ;;
    sihsim_airplane) PX4_SYS_AUTOSTART=10041 ;;
    sihsim_xvert)   PX4_SYS_AUTOSTART=10042 ;;
    *)              PX4_SYS_AUTOSTART=10040 ;;
esac

echo "Starting PX4 SITL SIH simulation..."
echo "Vehicle target: ${SIH_VEHICLE_TARGET}"
echo "SYS_AUTOSTART: ${PX4_SYS_AUTOSTART}"
echo "MAVLink UDP port: 14540"

# Change to PX4 build rootfs directory (required for PX4 runtime)
cd /px4/build/px4_sitl_default/rootfs

# Set environment for SIH simulation
export PX4_SYS_AUTOSTART
export PX4_SIMULATOR=sihsim

# Exec PX4 SITL binary
# MAVLink UDP 14540 is the default for SITL
exec ../bin/px4 /px4/ROMFS/px4fmu_common
