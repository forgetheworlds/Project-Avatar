#!/usr/bin/env bash
# Project Avatar SIH Smoke Test
# Wave 1 D4.8: Verify SIH heartbeat within 15 seconds
#
# This script validates:
# 1. SIH simulation starts correctly
# 2. PX4 SITL is ready within 15 seconds
# 3. MAVSDK can connect and receive health telemetry
#
# Usage:
#   ./scripts/test-sih-smoke.sh
#
# Exit codes:
#   0 - All checks passed
#   1 - SIH startup failed
#   2 - PX4 not ready within timeout
#   3 - Cleanup error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

echo "=========================================="
echo "SIH Smoke Test - Heartbeat Verification"
echo "=========================================="
echo "Wave 1 D4.8: PX4 ready within 15 seconds"
echo "=========================================="

# Cleanup function
cleanup() {
    local exit_code=$?
    echo ""
    echo "Cleaning up SIH containers..."
    docker compose down --remove-orphans 2>/dev/null || true
    exit $exit_code
}
trap cleanup EXIT

# Start SIH simulation
echo ""
echo "Step 1: Starting SIH simulation..."
docker compose --profile sih up -d

# Wait for PX4 with 15 second timeout (D4.8 requirement)
echo ""
echo "Step 2: Waiting for PX4 heartbeat (15s timeout)..."
echo "        This tests D4.8 requirement: SIH smoke heartbeat under 15s"

START_TIME=$(date +%s)

if python3 "${PROJECT_ROOT}/docker/shared/wait-for-px4.py" --timeout-s 15; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    echo ""
    echo "=========================================="
    echo "SUCCESS: PX4 ready in ${ELAPSED}s"
    echo "=========================================="

    # Verify it was under 15 seconds
    if [[ $ELAPSED -lt 15 ]]; then
        echo "VERIFIED: Heartbeat under 15s requirement met"
        echo ""
        echo "Test Results:"
        echo "  - SIH container:     STARTED"
        echo "  - PX4 SITL:          READY"
        echo "  - Time to ready:     ${ELAPSED}s (< 15s threshold)"
        echo "  - Status:            PASSED"
        exit 0
    else
        echo "WARNING: PX4 ready but exceeded 15s threshold (${ELAPSED}s)"
        exit 2
    fi
else
    echo ""
    echo "=========================================="
    echo "FAILED: PX4 not ready within 15 seconds"
    echo "=========================================="
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check container logs: docker compose logs px4-sih"
    echo "  2. Verify port 14540 is available"
    echo "  3. Check Docker resources are sufficient"
    exit 2
fi
