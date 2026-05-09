#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: install-avatar.sh [--branch name] [--repo url]

Clones and installs the Avatar drone software stack.

Options:
  --branch name   Git branch to checkout (default: main)
  --repo url      Git repository URL (default: origin)
  -h, --help      Show this help message
EOF
}

BRANCH="main"
REPO_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_URL="${2:-}"
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

# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
  python3.12-venv \
  python3-pip \
  git \
  build-essential \
  libffi-dev \
  libssl-dev \
  libjpeg-dev \
  zlib1g-dev

# Create avatar user if not exists (cloud-init should have created it)
if ! id avatar &>/dev/null; then
  echo "WARNING: avatar user not found, creating..." >&2
  sudo useradd -m -s /bin/bash -G adm,dialout,sudo,video,plugdev avatar
fi

# Clone repository to /opt/avatar
sudo mkdir -p /opt/avatar
sudo chown avatar:avatar /opt/avatar

if [[ -n "$REPO_URL" ]]; then
  sudo -u avatar git clone --branch "$BRANCH" "$REPO_URL" /opt/avatar
elif [[ ! -d /opt/avatar/.git ]]; then
  echo "ERROR: No repository at /opt/avatar and no --repo specified" >&2
  exit 1
else
  sudo -u avatar git -C /opt/avatar fetch origin
  sudo -u avatar git -C /opt/avatar checkout "$BRANCH"
fi

# Create virtual environment
sudo -u avatar python3.12 -m venv /opt/avatar/.venv

# Install avatar package in editable mode
sudo -u avatar /opt/avatar/.venv/bin/pip install --upgrade pip wheel
sudo -u avatar /opt/avatar/.venv/bin/pip install -e "/opt/avatar[dev]"

# Create convenience symlinks
sudo ln -sf /opt/avatar/.venv/bin/avatar /usr/local/bin/avatar || true

echo ""
echo "Avatar installation complete."
echo "Virtual environment: /opt/avatar/.venv"
echo "Activate with: source /opt/avatar/.venv/bin/activate"
