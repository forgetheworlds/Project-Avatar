#!/usr/bin/env bash
# ==============================================================================
# Project Avatar — ArduPilot SITL Launch Script
# ==============================================================================
# Launches ArduCopter SITL with custom parameters for a 3.5" class quadcopter.
#
# Hardware profile:
#   Frame:   3.5" class, ~220g dry weight
#   Motors:  1505 3800KV equivalent
#   Battery: 4S (14.8V nominal)
#   Sensors: GPS + Compass enabled
#
# MAVLink outputs:
#   UDP 127.0.0.1:14550  — Standard GCS port (Mission Planner, QGC, etc.)
#   UDP 127.0.0.1:14551  — MCP server / scripting port
#
# Usage:
#   ./launch.sh              # Interactive (with console + map)
#   ./launch.sh --headless   # No GUI console/map
#   ./launch.sh --help       # Show all options
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARDUPILOT_HOME="${ARDUPILOT_HOME:-$HOME/ardupilot}"
VEHICLE="${VEHICLE:-ArduCopter}"
FRAME="${FRAME:-quad}"
INSTANCE="${INSTANCE:-0}"
PARAM_FILE="${PARAM_FILE:-$SCRIPT_DIR/params/sitl_quad.parm}"

# Default MAVLink outputs
MAV_OUT1="--out udp:127.0.0.1:14550"
MAV_OUT2="--out udp:127.0.0.1:14551"

HEADLESS=false
CUSTOM_LOCATION=""

usage() {
    cat <<EOF
Project Avatar SITL Launcher
Usage: ./launch.sh [options]

Options:
  --headless          Run without MAVProxy console/map windows
  --instance N        Set SITL instance number (default: 0)
  --location LAT,LON,ALT,HDG  Override sim location (e.g., 37.7749,-122.4194,10,0)
  --home LAT,LON,ALT,HDG      Same as --location
  --vehicle TYPE      Vehicle type (default: ArduCopter)
  --frame TYPE        Frame type (default: quad)
  --param-file PATH   Custom parameter file (default: params/sitl_quad.parm)
  --help              Show this help

Examples:
  ./launch.sh                              # Interactive sim
  ./launch.sh --headless                   # Headless for scripting
  ./launch.sh --location 47.398,8.546,500,0  # Custom Swiss location
  ./launch.sh --instance 1                 # Second instance
EOF
    exit 0
}

# Parse arguments
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --headless)
            HEADLESS=true
            ;;
        --instance)
            INSTANCE="$2"
            shift
            ;;
        --location|--home)
            CUSTOM_LOCATION="--location $2"
            shift
            ;;
        --vehicle)
            VEHICLE="$2"
            shift
            ;;
        --frame)
            FRAME="$2"
            shift
            ;;
        --param-file)
            PARAM_FILE="$2"
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            EXTRA_ARGS+=("$1")
            ;;
    esac
    shift
done

# Verify ArduPilot exists
if [[ ! -d "$ARDUPILOT_HOME" ]]; then
    echo "ERROR: ArduPilot directory not found at $ARDUPILOT_HOME"
    echo "       Set ARDUPILOT_HOME environment variable or clone to ~/ardupilot"
    exit 1
fi

SIM_VEHICLE="$ARDUPILOT_HOME/Tools/autotest/sim_vehicle.py"
if [[ ! -f "$SIM_VEHICLE" ]]; then
    echo "ERROR: sim_vehicle.py not found at $SIM_VEHICLE"
    exit 1
fi

# Build SITL args
SIM_ARGS=(
    -v "$VEHICLE"
    -f "$FRAME"
    -I "$INSTANCE"
    $MAV_OUT1
    $MAV_OUT2
)

# Add parameter file if present
if [[ -n "$PARAM_FILE" && -f "$PARAM_FILE" ]]; then
    SIM_ARGS+=(--add-param-file "$PARAM_FILE")
    echo "[launch] Loading params from: $PARAM_FILE"
fi

# Add custom location if set
if [[ -n "$CUSTOM_LOCATION" ]]; then
    SIM_ARGS+=($CUSTOM_LOCATION)
fi

# Add extra args
SIM_ARGS+=("${EXTRA_ARGS[@]}")

# Headless: no console/map
if $HEADLESS; then
    SIM_ARGS+=(--no-mavproxy)
fi

# Add speedup for headless
if $HEADLESS; then
    SIM_ARGS+=(--speedup 1)
fi

cd "$ARDUPILOT_HOME"

echo "=============================================="
echo "  Project Avatar — ArduPilot SITL Launcher"
echo "=============================================="
echo "  Vehicle:   $VEHICLE"
echo "  Frame:     $FRAME"
echo "  Instance:  $INSTANCE"
echo "  Headless:  $HEADLESS"
echo "  MAVLink:   udp:127.0.0.1:14550 (GCS)"
echo "  MAVLink:   udp:127.0.0.1:14551 (Scripts)"
echo "=============================================="
echo ""

exec python3 "$SIM_VEHICLE" "${SIM_ARGS[@]}"
