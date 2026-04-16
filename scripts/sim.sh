#!/usr/bin/env bash
# Project Avatar simulation dispatcher
# Wave 1 D4.6: Unified entry point for SIH, Gazebo, and scenario management
#
# Usage:
#   ./scripts/sim.sh sih              Start SIH simulation
#   ./scripts/sim.sh gazebo           Start Gazebo simulation
#   ./scripts/sim.sh scenario <id>    Run a specific scenario
#   ./scripts/sim.sh down             Stop all simulations
#   ./scripts/sim.sh logs [service]   View logs (optional service filter)
#   ./scripts/sim.sh -h               Show this help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

usage() {
  cat <<'EOF'
Usage: ./scripts/sim.sh {sih|gazebo|scenario <id>|down|logs [service]}|-h

Commands:
  sih              Start SIH (Software-In-Hardware) simulation
  gazebo           Start Gazebo physics simulation
  scenario <id>    Run a specific test scenario
  down             Stop all simulations and remove containers
  logs [service]   Follow logs (optionally filter by service)
  -h, --help       Show this help message

Examples:
  ./scripts/sim.sh sih
  ./scripts/sim.sh logs px4-sih
  ./scripts/sim.sh scenario orbit_demo
  ./scripts/sim.sh down
EOF
}

case "${1:-}" in
  sih)
    echo "Starting SIH simulation..."
    docker compose --profile sih up -d
    echo "SIH simulation started. Use './scripts/sim.sh logs' to view logs."
    ;;
  gazebo)
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
