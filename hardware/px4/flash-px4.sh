#!/usr/bin/env bash
# =============================================================================
# PX4 Firmware Flash Script
# =============================================================================
# Downloads and flashes PX4 firmware to supported flight controllers.
# Uses PX4-Autopilot/Tools/upload.py for USB flashing without QGroundControl.
#
# Supported airframes:
#   - mark4_7in: Mark4 7" 6S 1500kV quad (Pixhawk 6X or compatible)
#   - x500_v2: PX4 X500 v2 kit (Pixhawk 4 or compatible, used in SITL/Gazebo)
#
# Usage:
#   ./flash-px4.sh --airframe mark4_7in [--port /dev/ttyACM0]
#   ./flash-px4.sh --airframe x500_v2
#   ./flash-px4.sh --help
#
# Prerequisites:
#   - Python 3.10+ with pyserial
#   - PX4-Autopilot repo cloned at $PX4_ROOT or sibling directory
#   - USB cable connected to flight controller
#   - Flight controller in bootloader mode (hold button during power-on)
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# PX4 firmware version (pinned for reproducibility)
PX4_VERSION="v1.15.0"

# PX4-Autopilot location (prefer environment variable, then sibling directory)
PX4_ROOT="${PX4_ROOT:-$(dirname "$0")/../../PX4-Autopilot}"
PX4_UPLOAD_SCRIPT="$PX4_ROOT/Tools/upload.py"

# Firmware download base URL
FIRMWARE_BASE_URL="https://github.com/PX4/PX4-Autopilot/releases/download/$PX4_VERSION"

# Default USB port (auto-detected if not specified)
DEFAULT_PORT=""

# Airframe to board mapping
declare -A AIRFRAME_TO_BOARD=(
    ["mark4_7in"]="pixhawk6x"
    ["x500_v2"]="pixhawk4"
)

# Airframe descriptions for help text
declare -A AIRFRAME_DESC=(
    ["mark4_7in"]="Mark4 7in 6S 1500kV quad (Pixhawk 6X)"
    ["x500_v2"]="PX4 X500 v2 kit (Pixhawk 4)"
)

# =============================================================================
# Functions
# =============================================================================

usage() {
    cat << 'EOF'
usage: flash-px4.sh --airframe <mark4_7in|x500_v2> [--port /dev/ttyACM0] [--dry-run]

Flash PX4 firmware to a flight controller without QGroundControl.

Options:
  --airframe <name>   Airframe configuration to flash
                      mark4_7in: Mark4 7in 6S quad (Pixhawk 6X)
                      x500_v2:   PX4 X500 v2 kit (Pixhawk 4)
  --port <device>     USB serial port (auto-detected if not specified)
  --dry-run           Show what would be done without flashing
  --help              Show this help message

Examples:
  # Flash Mark4 7in firmware
  ./flash-px4.sh --airframe mark4_7in

  # Flash X500 v2 firmware with explicit port
  ./flash-px4.sh --airframe x500_v2 --port /dev/ttyACM0

  # Dry-run to verify configuration
  ./flash-px4.sh --airframe mark4_7in --dry-run

Prerequisites:
  1. PX4-Autopilot repo cloned at $PX4_ROOT or ../../PX4-Autopilot
  2. Python 3.10+ with pyserial installed
  3. Flight controller connected via USB
  4. Flight controller in bootloader mode for some boards
EOF
}

log_info() {
    echo "[INFO] $*"
}

log_warn() {
    echo "[WARN] $*" >&2
}

log_error() {
    echo "[ERROR] $*" >&2
}

detect_usb_port() {
    # Try common USB serial device patterns
    local candidates=()

    # Linux: /dev/ttyACM* (CDC ACM devices like Pixhawk)
    if [[ -d /dev ]]; then
        for dev in /dev/ttyACM*; do
            [[ -e "$dev" ]] && candidates+=("$dev")
        done
        for dev in /dev/ttyUSB*; do
            [[ -e "$dev" ]] && candidates+=("$dev")
        done
    fi

    # macOS: /dev/cu.usb* and /dev/cu.usbserial*
    if [[ "$(uname)" == "Darwin" ]]; then
        for dev in /dev/cu.usbmodem*; do
            [[ -e "$dev" ]] && candidates+=("$dev")
        done
        for dev in /dev/cu.usbserial*; do
            [[ -e "$dev" ]] && candidates+=("$dev")
        done
    fi

    if [[ ${#candidates[@]} -eq 0 ]]; then
        return 1
    fi

    # Return first candidate
    echo "${candidates[0]}"
    return 0
}

check_px4_repo() {
    if [[ ! -d "$PX4_ROOT" ]]; then
        log_error "PX4-Autopilot repo not found at: $PX4_ROOT"
        log_error "Clone it first: git clone https://github.com/PX4/PX4-Autopilot.git"
        return 1
    fi

    if [[ ! -f "$PX4_UPLOAD_SCRIPT" ]]; then
        log_error "PX4 upload script not found: $PX4_UPLOAD_SCRIPT"
        log_error "Ensure PX4-Autopilot is properly cloned"
        return 1
    fi

    return 0
}

download_firmware() {
    local board="$1"
    local firmware_file="Firmware-${board}.px4"
    local download_url="${FIRMWARE_BASE_URL}/${firmware_file}"
    local cache_dir="$HOME/.cache/px4-firmware"
    local cached_file="$cache_dir/$PX4_VERSION/$firmware_file"

    # Check cache first
    if [[ -f "$cached_file" ]]; then
        log_info "Using cached firmware: $cached_file"
        echo "$cached_file"
        return 0
    fi

    # Create cache directory
    mkdir -p "$cache_dir/$PX4_VERSION"

    # Download firmware
    log_info "Downloading firmware: $download_url"
    log_info "Caching to: $cached_file"

    if command -v curl &>/dev/null; then
        if curl -fsSL -o "$cached_file" "$download_url"; then
            log_info "Download successful"
            echo "$cached_file"
            return 0
        fi
    elif command -v wget &>/dev/null; then
        if wget -q -O "$cached_file" "$download_url"; then
            log_info "Download successful"
            echo "$cached_file"
            return 0
        fi
    fi

    log_error "Failed to download firmware from: $download_url"
    log_error "Check that PX4 $PX4_VERSION release includes $firmware_file"
    return 1
}

flash_firmware() {
    local firmware_file="$1"
    local port="$2"

    log_info "Flashing firmware: $firmware_file"
    log_info "Using port: $port"
    log_info "Using upload script: $PX4_UPLOAD_SCRIPT"

    # Run PX4 upload script
    if python3 "$PX4_UPLOAD_SCRIPT" --port "$port" "$firmware_file"; then
        log_info "Flash successful!"
        return 0
    else
        log_error "Flash failed. Check:"
        log_error "  1. Flight controller is connected via USB"
        log_error "  2. Flight controller is in bootloader mode (if required)"
        log_error "  3. Correct port is specified: $port"
        log_error "  4. User has permission to access the serial port"
        return 1
    fi
}

# =============================================================================
# Main Script
# =============================================================================

# Parse arguments
AIRFRAME=""
PORT=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --airframe)
            AIRFRAME="${2:-}"
            shift 2
            ;;
        --port)
            PORT="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            exit 2
            ;;
    esac
done

# Validate airframe
if [[ -z "$AIRFRAME" ]]; then
    log_error "Missing required argument: --airframe"
    usage
    exit 2
fi

if [[ -z "${AIRFRAME_TO_BOARD[$AIRFRAME]:-}" ]]; then
    log_error "Unknown airframe: $AIRFRAME"
    log_error "Valid airframes: ${!AIRFRAME_TO_BOARD[*]}"
    exit 2
fi

BOARD="${AIRFRAME_TO_BOARD[$AIRFRAME]}"
log_info "Airframe: $AIRFRAME (${AIRFRAME_DESC[$AIRFRAME]})"
log_info "Target board: $BOARD"
log_info "PX4 version: $PX4_VERSION"

# Check dry-run mode
if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY-RUN] Would download firmware from:"
    log_info "[DRY-RUN]   ${FIRMWARE_BASE_URL}/Firmware-${BOARD}.px4"
    log_info "[DRY-RUN] Would flash using: $PX4_UPLOAD_SCRIPT"

    # Detect port for dry-run info
    if DETECTED_PORT=$(detect_usb_port 2>/dev/null); then
        log_info "[DRY-RUN] Detected USB port: $DETECTED_PORT"
    else
        log_info "[DRY-RUN] No USB flight controller detected (would need manual port)"
    fi

    echo '{"dry_run":true,"airframe":"'"$AIRFRAME"'","board":"'"$BOARD"'","px4_version":"'"$PX4_VERSION"'"}'
    exit 0
fi

# Real execution
# Check PX4 repo exists
if ! check_px4_repo; then
    exit 1
fi

# Detect or validate port
if [[ -z "$PORT" ]]; then
    if ! PORT=$(detect_usb_port); then
        log_error "No USB flight controller detected"
        log_error "Specify port manually with --port"
        exit 1
    fi
    log_info "Auto-detected USB port: $PORT"
fi

# Download firmware
if ! FIRMWARE_FILE=$(download_firmware "$BOARD"); then
    exit 1
fi

# Flash firmware
if ! flash_firmware "$FIRMWARE_FILE" "$PORT"; then
    exit 1
fi

# Success
log_info "Firmware flash complete!"
log_info "Next steps:"
log_info "  1. Power cycle the flight controller"
log_info "  2. Apply airframe parameters: hardware/px4/airframes/${AIRFRAME}.params"
log_info "  3. Run preflight check: python hardware/px4/preflight.py --airframe $AIRFRAME"
exit 0
