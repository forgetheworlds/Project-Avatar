#!/bin/bash
# Switch from SITL to hardware configuration
# Update connection string in MCP server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")/config"

SITL_CONFIG="$CONFIG_DIR/sitl.yaml"
HARDWARE_CONFIG="$CONFIG_DIR/hardware.yaml"
ACTIVE_CONFIG="$CONFIG_DIR/active.yaml"

echo "=== Avatar Hardware Transition Script ==="
echo ""

# Check if hardware config exists
if [ ! -f "$HARDWARE_CONFIG" ]; then
    echo "ERROR: Hardware config not found at $HARDWARE_CONFIG"
    exit 1
fi

# Check for connected hardware
echo "Checking for connected flight controller..."
if ls /dev/tty.usbmodem* 2>/dev/null; then
    USB_DEVICE=$(ls /dev/tty.usbmodem* | head -1)
    echo "Found device: $USB_DEVICE"

    # Update hardware.yaml with actual device path
    if command -v yq &> /dev/null; then
        yq -i ".connection.address = \"$USB_DEVICE\"" "$HARDWARE_CONFIG"
        echo "Updated hardware.yaml with device path"
    else
        echo "WARNING: yq not installed, using default device path"
        echo "Install yq for automatic device path updates: brew install yq"
    fi
else
    echo "WARNING: No USB device found at /dev/tty.usbmodem*"
    echo "Connect flight controller and run again, or manually update hardware.yaml"
fi

# Copy hardware config to active config
cp "$HARDWARE_CONFIG" "$ACTIVE_CONFIG"
echo "Activated hardware configuration"

# Update MCP server connection if running
if pgrep -f "avatar_mcp_server" > /dev/null; then
    echo "MCP server is running - sending config reload signal..."
    # Send SIGHUP to reload config (server must handle this)
    pkill -HUP -f "avatar_mcp_server" || true
else
    echo "MCP server not running - config will be loaded on next start"
fi

echo ""
echo "=== Hardware Transition Complete ==="
echo "Active config: $ACTIVE_CONFIG"
echo "Connection type: serial"
echo ""
echo "Safety reminders:"
echo "  - Ensure propellers are removed for first-time testing"
echo "  - Verify RC link before arming"
echo "  - Check battery voltage before flight"
