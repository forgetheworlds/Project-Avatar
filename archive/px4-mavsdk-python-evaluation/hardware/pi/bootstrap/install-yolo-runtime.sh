#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: install-yolo-runtime.sh [--backend name]

Installs YOLO inference runtime optimized for the current architecture.

Options:
  --backend name   Force specific backend: ncnn, openvino, onnx (default: auto-detect)
  -h, --help       Show this help message

Auto-detection:
  aarch64/arm64  -> ncnn (optimized for ARM, used with YOLOv8-nano)
  x86_64/amd64   -> openvino (optimized for Intel CPUs)
EOF
}

BACKEND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend)
      BACKEND="${2:-}"
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

# Auto-detect backend if not specified
if [[ -z "$BACKEND" ]]; then
  case "$ARCH" in
    aarch64|arm64)
      BACKEND="ncnn"
      ;;
    x86_64|amd64)
      BACKEND="openvino"
      ;;
    *)
      echo "ERROR: Unknown architecture $ARCH, specify --backend manually" >&2
      exit 1
      ;;
  esac
fi

echo "Installing YOLO runtime: $BACKEND for $ARCH"

# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
  libopencv-dev \
  python3-opencv \
  libopenblas-dev \
  libprotobuf-dev \
  protobuf-compiler

case "$BACKEND" in
  ncnn)
    # NCNN is optimized for ARM/mobile inference
    echo "Installing ncnn..."

    # Install ncnn via pip (recommended for Python integration)
    if [[ -d /opt/avatar/.venv ]]; then
      /opt/avatar/.venv/bin/pip install ncnn
    else
      pip3 install --user ncnn
    fi

    # Install additional ARM optimizations
    sudo apt-get install -y \
      libarmnn23 \
      libarmnn-dev || echo "ARM NN not available, continuing without..."

    echo "NCNN installed for ARM inference"
    ;;

  openvino)
    # OpenVINO is optimized for Intel CPUs
    echo "Installing OpenVINO..."

    # Install OpenVINO via pip
    if [[ -d /opt/avatar/.venv ]]; then
      /opt/avatar/.venv/bin/pip install openvino
    else
      pip3 install --user openvino
    fi

    # Install Intel MKL for optimized BLAS
    sudo apt-get install -y libmkl-dev || echo "MKL not available, using OpenBLAS"

    echo "OpenVINO installed for Intel CPU inference"
    ;;

  onnx)
    # ONNX Runtime as fallback
    echo "Installing ONNX Runtime..."

    if [[ -d /opt/avatar/.venv ]]; then
      /opt/avatar/.venv/bin/pip install onnxruntime
    else
      pip3 install --user onnxruntime
    fi

    echo "ONNX Runtime installed"
    ;;

  *)
    echo "ERROR: Unknown backend: $BACKEND" >&2
    usage
    exit 2
    ;;
esac

# Install Ultralytics (YOLOv8) with minimal dependencies
if [[ -d /opt/avatar/.venv ]]; then
  /opt/avatar/.venv/bin/pip install ultralytics
else
  pip3 install --user ultralytics
fi

echo ""
echo "YOLO runtime installation complete."
echo "Backend: $BACKEND"
echo "Architecture: $ARCH"
