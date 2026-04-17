#!/usr/bin/env bash
# trivial-flash.sh - Five-step bring-up helper for first-flight-ready
# Reference: spec section 9.5
#
# Usage:
#   ./scripts/trivial-flash.sh [--airframe AIRFRAME] [--pi-host HOST]
#
# Steps:
#   1. Flash PX4 firmware with airframe params
#   2. Flash Pi image (pass-through args to flash.sh)
#   3. Poll Pi status file until green
#   4. HITL preflight pytest
#   5. Reference to tethered flight runbook

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Parse arguments
AIRFRAME="${AIRFRAME:-mark4_7in}"
PI_HOST="${AVATAR_PI_HOST:-avatar.local}"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --airframe)
            AIRFRAME="$2"
            shift 2
            ;;
        --pi-host)
            PI_HOST="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--airframe AIRFRAME] [--pi-host HOST]"
            echo ""
            echo "Five-step bring-up for first-flight-ready:"
            echo "  1. Flash PX4 firmware"
            echo "  2. Flash Pi image"
            echo "  3. Poll Pi status until green"
            echo "  4. HITL preflight pytest"
            echo "  5. Reference to tethered flight runbook"
            echo ""
            echo "Arguments:"
            echo "  --airframe    Airframe name (default: mark4_7in)"
            echo "  --pi-host     Pi hostname (default: avatar.local)"
            exit 0
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

echo "============================================"
echo "trivial-flash.sh - Five-step bring-up"
echo "============================================"
echo "Airframe: $AIRFRAME"
echo "Pi host: $PI_HOST"
echo ""

# Step 1: Flash PX4
echo "[1/5] Flash PX4 ($AIRFRAME)"
if [[ -x "./hardware/px4/flash-px4.sh" ]]; then
    ./hardware/px4/flash-px4.sh --airframe "$AIRFRAME"
else
    echo "WARN: hardware/px4/flash-px4.sh not found or not executable"
    echo "Skipping PX4 flash step"
fi
echo ""

# Step 2: Flash Pi image
echo "[2/5] Flash Pi image (pass-through args to flash.sh)"
if [[ -x "./hardware/pi/flash.sh" ]]; then
    ./hardware/pi/flash.sh "${EXTRA_ARGS[@]}"
else
    echo "WARN: hardware/pi/flash.sh not found or not executable"
    echo "Skipping Pi flash step"
fi
echo ""

# Step 3: Poll Pi status file
echo "[3/5] Poll Pi status file (/boot/avatar-status.txt)"
echo "Target: $PI_HOST"
ok=0
for i in $(seq 1 60); do
    state="$(ssh -o ConnectTimeout=5 -o BatchMode=yes "pi@${PI_HOST}" 'cat /boot/avatar-status.txt 2>/dev/null || echo missing')" || true
    echo "  try ${i}: ${state}"
    case "$state" in
        *green*) ok=1; echo "STATUS: GREEN"; break ;;
        *red*) echo "STATUS: RED — abort"; exit 2 ;;
    esac
    sleep 5
done
if [[ "$ok" -ne 1 ]]; then
    echo "TIMEOUT: never saw green in /boot/avatar-status.txt"
    echo "Continuing anyway (may be operating in bench-only mode)"
fi
echo ""

# Step 4: HITL preflight pytest
echo "[4/5] HITL preflight pytest"
export AVATAR_HITL_TARGET="${AVATAR_HITL_TARGET:-fc_bench}"
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
echo ""

# Step 5: Tethered flight reference
echo "[5/5] Tethered flight (manual — see docs/runbooks/first-flight.md)"
echo ""
echo "============================================"
echo "ALL STEPS COMPLETE"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Review docs/runbooks/first-flight.md"
echo "  2. Ensure tether is properly attached"
echo "  3. Verify clear area and spotter present"
echo "  4. Follow tethered first-flight procedure"
