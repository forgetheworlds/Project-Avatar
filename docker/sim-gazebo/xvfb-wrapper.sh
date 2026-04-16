#!/bin/bash
# xvfb-wrapper.sh - Set up virtual display for headless Gazebo simulation
# Wave 1 D4.2: Xvfb display configuration for software rendering

# Virtual display settings
DISPLAY_NUM="${DISPLAY_NUM:-99}"
SCREEN_WIDTH="${SCREEN_WIDTH:-1920}"
SCREEN_HEIGHT="${SCREEN_HEIGHT:-1080}"
SCREEN_DEPTH="${SCREEN_DEPTH:-24}"

# Ensure LIBGL_ALWAYS_SOFTWARE is set for headless rendering
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"

# Export display
export DISPLAY=":${DISPLAY_NUM}"

# Kill any existing Xvfb on this display
if pkill -9 -f "Xvfb ${DISPLAY}" 2>/dev/null; then
    echo "Killed existing Xvfb on display ${DISPLAY}"
    sleep 1
fi

# Start Xvfb virtual framebuffer
echo "Starting Xvfb on display ${DISPLAY} (${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH})..."
Xvfb "${DISPLAY}" \
    -screen "0" "${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}" \
    -ac \
    -nolisten tcp \
    -dpi 96 \
    &

XVFB_PID=$!

# Wait for Xvfb to be ready
sleep 2

# Verify Xvfb is running
if ! kill -0 ${XVFB_PID} 2>/dev/null; then
    echo "ERROR: Xvfb failed to start on display ${DISPLAY}"
    exit 1
fi

echo "Xvfb started successfully (PID: ${XVFB_PID})"
echo "Virtual display ready at ${DISPLAY}"

# Cleanup function to kill Xvfb on exit
cleanup_xvfb() {
    echo "Cleaning up Xvfb (PID: ${XVFB_PID})..."
    kill ${XVFB_PID} 2>/dev/null || true
}
trap cleanup_xvfb EXIT
