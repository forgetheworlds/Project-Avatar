#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: collect-artifacts.sh <run_suffix>" >&2
}

RUN_SUFFIX="${1:-}"
if [[ -z "$RUN_SUFFIX" ]]; then
  usage
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
mkdir -p "$ROOT/collected-artifacts/$RUN_SUFFIX"
shopt -s nullglob
for f in "$ROOT/artifacts"/*.tar.gz; do
  cp -a "$f" "$ROOT/collected-artifacts/$RUN_SUFFIX/"
done
printf "OK\t%s\t%d files\n" "$RUN_SUFFIX" "$(ls -1 "$ROOT/collected-artifacts/$RUN_SUFFIX" | wc -l)"
