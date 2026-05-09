#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: build-image.sh [--dry-run]" >&2
}

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
elif [[ -n "${1:-}" ]]; then
  usage
  exit 2
fi

IMG_NAME="raspios-avatar-$(date +%Y%m%d).img.xz"
echo "IMG_NAME=$IMG_NAME"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo '{"dry_run":true,"would_invoke":"pi-gen or rpi-image-gen","eta_min":8}'
  exit 0
fi

# Real build: clone pi-gen, copy cloud-init, run build.sh
# Implementor fills per org mirror policy and pi-gen configuration
echo "ERROR: Real build not implemented. Use --dry-run for validation." >&2
exit 1
