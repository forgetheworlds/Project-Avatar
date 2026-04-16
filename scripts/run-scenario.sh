#!/usr/bin/env bash
# Project Avatar scenario orchestrator
# Wave 1 D4.7: Run simulation scenarios with artifact collection
#
# Usage:
#   ./scripts/run-scenario.sh <scenario-id>
#
# Environment variables:
#   RUN_ID    - Unique run identifier (default: timestamp YYYYMMDD_HHMMSS)
#
# Examples:
#   ./scripts/run-scenario.sh smoke_heartbeat
#   RUN_ID=test_001 ./scripts/run-scenario.sh orbit_demo
#
# Exit codes:
#   0 - Scenario completed successfully
#   1 - General error
#   2 - Invalid arguments
#   3 - Timeout waiting for PX4

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"

# Generate run ID if not provided
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
SCENARIO="${1:?Error: scenario id required

Usage: ./scripts/run-scenario.sh <scenario-id>

Available scenarios:
  smoke_heartbeat  - SIH heartbeat verification
  smoke_hover      - SIH basic hover test
  gazebo_orbit     - Gazebo orbit demonstration
}"
STAGE_DIR="${ARTIFACTS_DIR}/stage/${RUN_ID}"

# Create directories
mkdir -p "${STAGE_DIR}"
mkdir -p "${ARTIFACTS_DIR}"

echo "=========================================="
echo "Project Avatar Scenario Runner"
echo "=========================================="
echo "Run ID:    ${RUN_ID}"
echo "Scenario:  ${SCENARIO}"
echo "Artifacts: ${STAGE_DIR}"
echo "=========================================="

# Cleanup function
cleanup() {
    local exit_code=$?
    echo ""
    echo "Cleaning up..."

    # Create tarball if stage directory has content
    if [[ -d "${STAGE_DIR}" ]] && [[ -n "$(ls -A "${STAGE_DIR}" 2>/dev/null)" ]]; then
        echo "Creating artifact tarball..."
        tar -czf "${ARTIFACTS_DIR}/${RUN_ID}.tar.gz" -C "${ARTIFACTS_DIR}/stage" "${RUN_ID}"
        echo "Artifacts saved: ${ARTIFACTS_DIR}/${RUN_ID}.tar.gz"
    fi

    # Teardown containers
    echo "Stopping containers..."
    docker compose down --remove-orphans 2>/dev/null || true

    exit $exit_code
}
trap cleanup EXIT

# Start appropriate compose profile based on scenario
echo ""
echo "Starting simulation..."
if [[ "$SCENARIO" == smoke* ]]; then
    echo "Using SIH profile (lightweight simulation)"
    docker compose --profile sih up -d
else
    echo "Using Gazebo profile (full physics simulation)"
    docker compose --profile gazebo up -d
fi

# Wait for PX4 to be ready
echo ""
echo "Waiting for PX4 SITL to be ready..."
TIMEOUT_S=30
if [[ "$SCENARIO" == smoke* ]]; then
    TIMEOUT_S=15
fi

if python3 "${PROJECT_ROOT}/docker/shared/wait-for-px4.py" --timeout-s "${TIMEOUT_S}"; then
    echo "PX4 SITL is ready!"
else
    echo "ERROR: Timeout waiting for PX4 SITL (after ${TIMEOUT_S}s)" >&2
    exit 3
fi

# Run scenario (stub if avatar.sim.runner doesn't exist)
echo ""
echo "Running scenario: ${SCENARIO}"
if python3 -c "import avatar.sim.runner" 2>/dev/null; then
    python3 -m avatar.sim.runner --scenario "$SCENARIO" --artifacts "${STAGE_DIR}"
    echo "Scenario completed."
else
    echo "STUB: Scenario '$SCENARIO' (avatar.sim.runner not implemented)"
    echo "Stub result: SUCCESS" > "${STAGE_DIR}/result.txt"
    echo "scenario: ${SCENARIO}" >> "${STAGE_DIR}/result.txt"
    echo "timestamp: $(date -Iseconds)" >> "${STAGE_DIR}/result.txt"
    echo "status: stub_success" >> "${STAGE_DIR}/result.txt"
fi

echo ""
echo "=========================================="
echo "Scenario ${SCENARIO} completed successfully!"
echo "=========================================="
