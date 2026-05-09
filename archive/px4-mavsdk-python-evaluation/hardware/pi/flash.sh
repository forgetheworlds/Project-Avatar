#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: flash.sh --wifi-config path --api-keys path [--img path]

Options:
  --wifi-config path   JSON file with WiFi SSID and password
  --api-keys path      File containing API keys to inject
  --img path           Path to image file (default: raspios-avatar-*.img.xz)

macOS: Uses diskutil to find and prepare SD card
Linux: Uses lsblk to find and prepare SD card

WARNING: This script will ERASE the target device. Verify carefully.
EOF
}

WIFI_CONFIG=""
API_KEYS_PATH=""
IMG_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wifi-config)
      WIFI_CONFIG="${2:-}"
      shift 2
      ;;
    --api-keys)
      API_KEYS_PATH="${2:-}"
      shift 2
      ;;
    --img)
      IMG_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

# Validate required arguments
if [[ -z "$WIFI_CONFIG" ]]; then
  echo "ERROR: --wifi-config is required" >&2
  usage
  exit 2
fi

if [[ -z "$API_KEYS_PATH" ]]; then
  echo "ERROR: --api-keys is required" >&2
  usage
  exit 2
fi

if [[ ! -f "$WIFI_CONFIG" ]]; then
  echo "ERROR: WiFi config file not found: $WIFI_CONFIG" >&2
  exit 2
fi

if [[ ! -f "$API_KEYS_PATH" ]]; then
  echo "ERROR: API keys file not found: $API_KEYS_PATH" >&2
  exit 2
fi

# Detect OS and list storage devices
detect_os() {
  case "$(uname -s)" in
    Darwin)
      echo "macOS detected. Listing disks:"
      diskutil list
      echo ""
      echo "Use 'diskutil list' to identify your SD card (usually /dev/disk2 or /dev/disk3)"
      echo "WARNING: Do NOT target your internal disk (usually /dev/disk0)"
      ;;
    Linux)
      echo "Linux detected. Listing block devices:"
      lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
      echo ""
      echo "Use 'lsblk' to identify your SD card (usually /dev/sdX or /dev/mmcblk0)"
      echo "WARNING: Do NOT target your internal disk"
      ;;
    *)
      echo "ERROR: Unsupported OS: $(uname -s)" >&2
      exit 2
      ;;
  esac
}

detect_os

# Determine image to flash
if [[ -z "$IMG_PATH" ]]; then
  IMG_PATH="raspios-avatar-$(date +%Y%m%d).img.xz"
  echo "No image specified, will use: $IMG_PATH"
fi

# Placeholder implementation - to be filled by engineer
echo ""
echo "ERROR: Flash implementation not complete." >&2
echo "This script requires:" >&2
echo "  1. User to confirm target device" >&2
echo "  2. Decompress image: xz -d -c $IMG_PATH | sudo dd of=<device>" >&2
echo "  3. Mount boot partition" >&2
echo "  4. Write wpa_supplicant.conf / firstrun.sh from --wifi-config JSON" >&2
echo "  5. Copy API keys to appropriate location" >&2
echo "  6. Unmount and sync" >&2
exit 1
