#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: install-mavsdk.sh [--version tag]

Downloads and installs MAVSDK server for the current architecture.

Options:
  --version tag   Release tag to install (default: v1.4.0)
  -h, --help      Show this help message
EOF
}

VERSION="v1.4.0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
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

set -x

ARCH=$(uname -m)
case "$ARCH" in
  aarch64|arm64)
    BINARY_NAME="mavsdk_server-manylinux2014-aarch64"
    ;;
  x86_64|amd64)
    BINARY_NAME="mavsdk_server-manylinux2014-x86_64"
    ;;
  armv7l|armhf)
    BINARY_NAME="mavsdk_server-manylinux2014-armv7l"
    ;;
  *)
    echo "ERROR: Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

DOWNLOAD_URL="https://github.com/Auterion/MAVSDK/releases/download/${VERSION}/${BINARY_NAME}"
INSTALL_DIR="/opt/mavsdk"
BINARY_PATH="${INSTALL_DIR}/mavsdk_server"

echo "Installing MAVSDK server ${VERSION} for ${ARCH}..."

# Create installation directory
sudo mkdir -p "$INSTALL_DIR"

# Download binary
sudo curl -fsSL "$DOWNLOAD_URL" -o "$BINARY_PATH"
sudo chmod +x "$BINARY_PATH"

# Create convenience symlink
sudo ln -sf "$BINARY_PATH" /usr/local/bin/mavsdk_server || true

# Verify installation
if "$BINARY_PATH" --version 2>/dev/null; then
  echo ""
  echo "MAVSDK server installed successfully: $BINARY_PATH"
else
  echo "WARNING: Could not verify mavsdk_server installation" >&2
  echo "Binary exists at: $BINARY_PATH" >&2
fi

# Install Python bindings if virtual environment exists
if [[ -d /opt/avatar/.venv ]]; then
  echo "Installing MAVSDK Python bindings..."
  /opt/avatar/.venv/bin/pip install mavsdk
fi
