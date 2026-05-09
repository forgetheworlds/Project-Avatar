#!/usr/bin/env bash
# Project Avatar simulation dispatcher
# Wave 1 D4.6: Unified entry point for SIH, Gazebo, and scenario management
# Wave 3 D11: Added all-scenarios orchestration for W3 gate
#
# Usage:
#   ./scripts/sim.sh sih              Start SIH simulation
#   ./scripts/sim.sh gazebo           Start Gazebo simulation
#   ./scripts/sim.sh scenario <id>    Run a specific scenario
#   ./scripts/sim.sh all-scenarios    Run all 12 Wave 3 scenarios
#   ./scripts/sim.sh down             Stop all simulations
#   ./scripts/sim.sh logs [service]   View logs (optional service filter)
#   ./scripts/sim.sh -h               Show this help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"
export COMPOSE_FILE="${PROJECT_ROOT}/docker/compose.yaml"

docker_available() {
  docker info >/dev/null 2>&1
}

# Wave 3 scenario IDs in fixed order
W3_SCENARIO_IDS=(
  "search_acquire_follow_vision_dropout"
  "gps_jam_expect_rtl"
  "runner_follow_wind_gust"
  "orbit_offboard_freeze"
  "cinematic_reveal_battery_critical"
  "depth_room_obstacle_abort"
  "sailboat_follow_altitude_floor"
  "mcp_tool_storm"
  "acrobatic_corkscrew_battery_drop"
  "geofence_adjacent_goto_reject"
  "companion_fc_partition_recover"
  "flight_recorder_replay_diff"
)

usage() {
  cat <<'EOF'
Usage: ./scripts/sim.sh {sih|gazebo|scenario <id>|all-scenarios|down|logs [service]}|-h

Commands:
  sih              Start SIH (Software-In-Hardware) simulation
  gazebo           Start Gazebo physics simulation
  scenario <id>    Run a specific test scenario
  all-scenarios    Run all 12 Wave 3 scenarios and write summary
  down             Stop all simulations and remove containers
  logs [service]   Follow logs (optionally filter by service)
  -h, --help       Show this help message

Examples:
  ./scripts/sim.sh sih
  ./scripts/sim.sh logs px4-sih
  ./scripts/sim.sh scenario orbit_demo
  ./scripts/sim.sh all-scenarios
  ./scripts/sim.sh down
EOF
}

case "${1:-}" in
  sih)
    if ! docker_available; then
      echo "ERROR: Docker daemon is not available. Start Docker Desktop and retry." >&2
      exit 3
    fi
    echo "Starting SIH simulation..."
    docker compose --profile sih up -d
    echo "SIH simulation started. Use './scripts/sim.sh logs' to view logs."
    ;;
  gazebo)
    if ! docker_available; then
      echo "ERROR: Docker daemon is not available. Start Docker Desktop and retry." >&2
      exit 3
    fi
    echo "Starting Gazebo simulation..."
    docker compose --profile gazebo up -d
    echo "Gazebo simulation started. Use './scripts/sim.sh logs' to view logs."
    ;;
  scenario)
    shift
    if [[ -z "${1:-}" ]]; then
      echo "Error: scenario id required" >&2
      usage
      exit 2
    fi
    exec "${SCRIPT_DIR}/run-scenario.sh" "${1}"
    ;;
  all-scenarios)
    if ! docker_available; then
      echo "ERROR: Docker daemon is not available. all-scenarios requires Docker simulation profiles." >&2
      echo "Run offline scenarios directly with: ./scripts/run-scenario.sh flight_recorder_replay_diff" >&2
      exit 3
    fi

    echo "=========================================="
    echo "Running all 12 Wave 3 scenarios"
    echo "=========================================="

    mkdir -p "${ARTIFACTS_DIR}"

    # Initialize summary JSON
    summary_file="${ARTIFACTS_DIR}/all-scenarios-summary.json"
    echo '{"scenarios": [' > "${summary_file}"

    passed=0
    failed=0
    first_entry=true

    for id in "${W3_SCENARIO_IDS[@]}"; do
      echo ""
      echo ">>> Scenario: ${id}"

      start_time=$(date +%s)

      exit_code=0
      if "${SCRIPT_DIR}/run-scenario.sh" "${id}"; then
        ((passed++)) || true
      else
        exit_code=$?
        ((failed++)) || true
      fi

      end_time=$(date +%s)
      duration=$((end_time - start_time))

      # Find artifact tarball if exists
      artifact_path=""
      shopt -s nullglob
      for f in "${ARTIFACTS_DIR}"/*"${id}"*.tar.gz; do
        artifact_path="${f}"
        break
      done
      shopt -u nullglob

      # Append to summary JSON
      if [[ "${first_entry}" == "true" ]]; then
        first_entry=false
      else
        echo ',' >> "${summary_file}"
      fi

      printf '    {"id": "%s", "exit_code": %d, "duration_s": %d, "artifact": "%s"}' \
        "${id}" "${exit_code}" "${duration}" "${artifact_path##*/}" >> "${summary_file}"
    done

    echo '' >> "${summary_file}"
    echo '  ],' >> "${summary_file}"
    printf '  "passed": %d,\n' "${passed}" >> "${summary_file}"
    printf '  "failed": %d,\n' "${failed}" >> "${summary_file}"
    printf '  "total": %d,\n' "${#W3_SCENARIO_IDS[@]}" >> "${summary_file}"
    echo '  "status": "complete"' >> "${summary_file}"
    echo '}' >> "${summary_file}"

    echo ""
    if [[ "${failed}" -gt 0 ]]; then
      echo "=========================================="
      echo "ALL_SCENARIOS_FAILED ${passed}/${#W3_SCENARIO_IDS[@]}"
      echo "Summary: ${summary_file}"
      echo "=========================================="
      exit 1
    fi

    echo "=========================================="
    echo "ALL_SCENARIOS_OK ${passed}/${#W3_SCENARIO_IDS[@]}"
    echo "Summary: ${summary_file}"
    echo "=========================================="
    ;;
  down)
    echo "Stopping all simulations..."
    docker compose down --remove-orphans
    echo "All simulations stopped."
    ;;
  logs)
    shift
    docker compose logs -f "${@:-}"
    ;;
  -h|--help)
    usage
    ;;
  *)
    echo "Error: Unknown command '${1:-}'" >&2
    usage
    exit 2
    ;;
esac
