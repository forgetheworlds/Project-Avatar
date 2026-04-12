#!/bin/bash
#
# Safety Gate Hook: Geofence and Altitude Validation
#
# A bash-level safety gate that runs before drone commands.
# This provides a fast, shell-based validation layer.
#
# Exit codes:
#   0 - Command is safe to execute
#   1 - Command blocked (safety violation)
#
# Environment variables:
#   DRONE_MAX_ALTITUDE_M       - Maximum allowed altitude (default: 120)
#   DRONE_GEOFENCE_RADIUS_M    - Geofence radius in meters (default: 500)
#   DRONE_MIN_BATTERY_PCT      - Minimum battery percentage (default: 20)
#   SAFETY_CONFIG_FILE         - Path to safety config JSON
#   DRONE_STATE_FILE           - Path to current drone state JSON
#

set -euo pipefail

# Configuration defaults
MAX_ALTITUDE_M="${DRONE_MAX_ALTITUDE_M:-120}"
GEOFENCE_RADIUS_M="${DRONE_GEOFENCE_RADIUS_M:-500}"
MIN_BATTERY_PCT="${DRONE_MIN_BATTERY_PCT:-20}"
SAFETY_CONFIG_FILE="${SAFETY_CONFIG_FILE:-/tmp/drone_safety_config.json}"
DRONE_STATE_FILE="${DRONE_STATE_FILE:-/tmp/drone_state.json}"
LOG_FILE="${SAFETY_GATE_LOG:-/tmp/safety_gate.log}"

# Colors for output (if terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Load configuration from JSON file if it exists
load_config() {
    if [ -f "$SAFETY_CONFIG_FILE" ]; then
        # Parse JSON using python if available, else use grep/sed
        if command -v python3 &>/dev/null; then
            eval "$(python3 -c "
import json
import sys
try:
    with open('$SAFETY_CONFIG_FILE', 'r') as f:
        config = json.load(f)
        for key, value in config.items():
            key_upper = key.upper()
            if isinstance(value, bool):
                print(f'export {key_upper}={str(value).lower()}')
            elif isinstance(value, (int, float)):
                print(f'export {key_upper}={value}')
            elif isinstance(value, str):
                print(f'export {key_upper}=\"{value}\"')
except Exception as e:
    sys.exit(1)
" 2>/dev/null)" || true
        fi
    fi
}

# Load current drone state
load_state() {
    if [ -f "$DRONE_STATE_FILE" ]; then
        if command -v python3 &>/dev/null; then
            eval "$(python3 -c "
import json
import sys
try:
    with open('$DRONE_STATE_FILE', 'r') as f:
        state = json.load(f)
        print(f'CURRENT_ALTITUDE={state.get(\"altitude_m\", 0)}')
        print(f'CURRENT_LAT={state.get(\"latitude\", 0)}')
        print(f'CURRENT_LON={state.get(\"longitude\", 0)}')
        print(f'CURRENT_BATTERY={state.get(\"battery_percent\", 100)}')
        print(f'IS_ARMED={str(state.get(\"armed\", False)).lower()}')
        print(f'IN_FLIGHT={str(state.get(\"in_flight\", False)).lower()}')
except Exception:
    pass
" 2>/dev/null)" || true
        fi
    fi

    # Set defaults if not loaded
    CURRENT_ALTITUDE="${CURRENT_ALTITUDE:-0}"
    CURRENT_BATTERY="${CURRENT_BATTERY:-100}"
    IS_ARMED="${IS_ARMED:-false}"
    IN_FLIGHT="${IN_FLIGHT:-false}"
}

# Check if command contains altitude specification
check_altitude() {
    local command="$1"

    # Extract altitude from command (patterns like "altitude 50m", "at 100 meters")
    local altitude=$(echo "$command" | grep -ioE '(altitude|height|at|climb to)[^0-9]*[0-9]+\.?[0-9]*\s*m?' | grep -oE '[0-9]+\.?[0-9]*' | head -1)

    if [ -n "$altitude" ]; then
        # Compare with max altitude (using bc for floating point)
        if command -v bc &>/dev/null; then
            if [ "$(echo "$altitude > $MAX_ALTITUDE_M" | bc -l)" -eq 1 ]; then
                echo -e "${RED}[SAFETY GATE] BLOCKED${NC}"
                echo "Altitude ${altitude}m exceeds maximum allowed ${MAX_ALTITUDE_M}m"
                log "BLOCK" "Altitude ${altitude}m exceeds max ${MAX_ALTITUDE_M}m"
                return 1
            fi
        elif [ "${altitude%.*}" -gt "${MAX_ALTITUDE_M%.*}" ] 2>/dev/null; then
            echo -e "${RED}[SAFETY GATE] BLOCKED${NC}"
            echo "Altitude ${altitude}m exceeds maximum allowed ${MAX_ALTITUDE_M}m"
            log "BLOCK" "Altitude ${altitude}m exceeds max ${MAX_ALTITUDE_M}m"
            return 1
        fi
        log "PASS" "Altitude ${altitude}m within limits"
    fi

    # Check current altitude if in flight
    if [ "$IN_FLIGHT" = "true" ]; then
        if command -v bc &>/dev/null; then
            if [ "$(echo "$CURRENT_ALTITUDE > $MAX_ALTITUDE_M" | bc -l)" -eq 1 ]; then
                echo -e "${RED}[SAFETY GATE] BLOCKED${NC}"
                echo "Current altitude ${CURRENT_ALTITUDE}m exceeds maximum ${MAX_ALTITUDE_M}m"
                log "BLOCK" "Current altitude ${CURRENT_ALTITUDE}m exceeds max"
                return 1
            fi
        fi
    fi

    return 0
}

# Check battery level
check_battery() {
    local command="$1"

    # Skip battery check for emergency/landing commands
    if echo "$command" | grep -iqE '(emergency|land|disarm|stop|kill|halt)'; then
        log "PASS" "Emergency/safety operation - battery check bypassed"
        return 0
    fi

    # Check if this is a flight command
    if echo "$command" | grep -iqE '(takeoff|fly|arm|mission|goto|navigate)'; then
        if command -v bc &>/dev/null; then
            if [ "$(echo "$CURRENT_BATTERY < $MIN_BATTERY_PCT" | bc -l)" -eq 1 ]; then
                echo -e "${RED}[SAFETY GATE] BLOCKED${NC}"
                echo "Battery ${CURRENT_BATTERY}% below minimum ${MIN_BATTERY_PCT}% for flight operations"
                log "BLOCK" "Battery ${CURRENT_BATTERY}% below min ${MIN_BATTERY_PCT}%"
                return 1
            fi
        elif [ "${CURRENT_BATTERY%.*}" -lt "${MIN_BATTERY_PCT%.*}" ] 2>/dev/null; then
            echo -e "${RED}[SAFETY GATE] BLOCKED${NC}"
            echo "Battery ${CURRENT_BATTERY}% below minimum ${MIN_BATTERY_PCT}% for flight operations"
            log "BLOCK" "Battery ${CURRENT_BATTERY}% below min ${MIN_BATTERY_PCT}%"
            return 1
        fi
    fi

    return 0
}

# Check geofence (simplified - checks radius from center)
check_geofence() {
    local command="$1"

    # Skip for landing/RTL commands
    if echo "$command" | grep -iqE '(land|rtl|return)'; then
        log "PASS" "Landing operation - geofence check bypassed"
        return 0
    fi

    # If geofence center and position are set, check distance
    # This is a simplified check - full implementation would use haversine
    if [ -n "${GEOFENCE_CENTER_LAT:-}" ] && [ -n "${GEOFENCE_CENTER_LON:-}" ] && \
       [ -n "${CURRENT_LAT:-}" ] && [ -n "${CURRENT_LON:-}" ]; then
        # Simple bounding box check (not accurate for large distances)
        local lat_diff=$(echo "${CURRENT_LAT:-0} - ${GEOFENCE_CENTER_LAT:-0}" | bc -l 2>/dev/null || echo "0")
        local lon_diff=$(echo "${CURRENT_LON:-0} - ${GEOFENCE_CENTER_LON:-0}" | bc -l 2>/dev/null || echo "0")

        # Rough approximation: 1 degree ~ 111km
        # Check if outside radius
        if command -v python3 &>/dev/null; then
            local distance=$(python3 -c "
import math
try:
    lat1, lon1 = float('${GEOFENCE_CENTER_LAT:-0}'), float('${GEOFENCE_CENTER_LON:-0}')
    lat2, lon2 = float('${CURRENT_LAT:-0}'), float('${CURRENT_LON:-0}')
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    print(int(R * c))
except:
    print(0)
" 2>/dev/null)

            if [ "$distance" -gt "$GEOFENCE_RADIUS_M" ] 2>/dev/null; then
                echo -e "${YELLOW}[SAFETY GATE] WARNING${NC}"
                echo "Current position ${distance}m from center, outside geofence radius ${GEOFENCE_RADIUS_M}m"
                log "WARN" "Position ${distance}m outside geofence ${GEOFENCE_RADIUS_M}m"
                # Warning only, not blocking
            fi
        fi
    fi

    return 0
}

# Main validation function
validate_command() {
    local command="$1"

    # Load configuration and state
    load_config
    load_state

    # Check if this is a drone command
    if ! echo "$command" | grep -iqE '(drone|uav|fly|arm|takeoff|land|mission|altitude|geofence|copter|quad)'; then
        # Not a drone command, allow
        exit 0
    fi

    log "INFO" "Validating command: ${command:0:100}"

    # Run all safety checks
    if ! check_altitude "$command"; then
        exit 1
    fi

    if ! check_battery "$command"; then
        exit 1
    fi

    if ! check_geofence "$command"; then
        exit 1
    fi

    # All checks passed
    echo -e "${GREEN}[SAFETY GATE] PASSED${NC}"
    log "PASS" "Command validated successfully"
    exit 0
}

# Main entry point
main() {
    # Read input from stdin (JSON format expected)
    local input=""
    if [ -p /dev/stdin ]; then
        input=$(cat)
    else
        # If no stdin, check for command line argument
        input="${1:-}"
    fi

    # Parse JSON if python is available
    local command=""
    if command -v python3 &>/dev/null && [ -n "$input" ]; then
        command=$(python3 -c "
import json
import sys
try:
    data = json.loads('''$input''')
    # Extract command from various possible fields
    cmd = data.get('command', '')
    cmd = data.get('tool_input', {}).get('command', cmd)
    cmd = data.get('tool_input', {}).get('prompt', cmd)
    cmd = data.get('tool_input', {}).get('text', cmd)
    print(cmd)
except:
    print('')
" 2>/dev/null)
    else
        # Fallback: use input directly
        command="$input"
    fi

    if [ -z "$command" ]; then
        # No command to validate
        exit 0
    fi

    validate_command "$command"
}

# Run main
main "$@"
