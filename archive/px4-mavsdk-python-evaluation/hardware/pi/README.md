# Avatar Raspberry Pi Provisioning

One-page operator guide for deploying Project Avatar on Raspberry Pi hardware.

## Quick Start

```bash
# 1. Build image (dry-run first)
./build-image.sh --dry-run

# 2. Flash to SD card (requires root)
./flash.sh --wifi-config wifi.json --api-keys keys.env

# 3. Boot Pi and run bring-up
./bring-up.sh
```

## Directory Structure

```
hardware/pi/
├── build-image.sh          # Build custom Raspberry Pi OS image
├── flash.sh                # Flash image to SD card
├── bring-up.sh             # Hardware diagnostics and status
├── README.md               # This file
├── cloud-init/
│   ├── user-data           # Cloud-init user configuration
│   └── network-config      # WiFi/Ethernet configuration
├── bootstrap/
│   ├── install-avatar.sh   # Install Avatar software stack
│   ├── install-mavsdk.sh   # Install MAVSDK server
│   └── install-yolo-runtime.sh  # Install YOLO inference engine
├── systemd/
│   ├── avatar-mavlink-bridge.service  # MAVLink communication
│   ├── avatar-heartbeat.service       # Telemetry broadcast
│   ├── avatar-mcp.service             # MCP API server (disabled)
│   └── watchdog.service               # Hardware watchdog
└── udev/
    └── 99-pixhawk.rules    # USB/serial device rules for Pixhawk
```

## Services

| Service | Purpose | Default |
|---------|---------|---------|
| avatar-mavlink-bridge | MAVLink communication with Pixhawk | Enabled |
| avatar-heartbeat | Telemetry broadcast and health monitoring | Enabled |
| avatar-mcp | MCP API server for agent control | **Disabled** |
| watchdog | Hardware reset on system hang | Enabled |

### Enable MCP Server (when ready)

```bash
sudo systemctl enable avatar-mcp.service
sudo systemctl start avatar-mcp.service
```

## Hardware Requirements

- Raspberry Pi 4 or 5 (4GB+ RAM recommended)
- microSD card (32GB+ Class 10)
- Pixhawk flight controller with USB or serial connection
- WiFi dongle (if using Pi 4 without built-in WiFi)

## Serial Connection

The udev rules create `/dev/pixhawk` symlink when a Pixhawk is connected:

```bash
# Verify Pixhawk connection
ls -la /dev/pixhawk

# Check device info
udevadm info -a -n /dev/pixhawk
```

## Troubleshooting

### No /dev/pixhawk device

1. Check USB cable connection
2. Verify Pixhawk is powered on
3. Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### MAVSDK connection fails

1. Verify MAVSDK server is running:
   ```bash
   systemctl status avatar-mavlink-bridge
   ```
2. Check serial port permissions:
   ```bash
   groups avatar  # Should include 'dialout'
   ```

### Boot status shows red

Run bring-up with verbose output:
```bash
./bring-up.sh
cat /boot/firmware/avatar-status.txt
```

## Configuration Files

| File | Purpose |
|------|---------|
| `/boot/firmware/avatar-status.txt` | System health status |
| `/opt/avatar/config/profiles/*.yaml` | Mission profiles |
| `/opt/avatar/.env` | API keys and secrets |

## Updating

```bash
cd /opt/avatar
git pull
source .venv/bin/activate
pip install -e ".[dev]"
sudo systemctl restart avatar-mavlink-bridge avatar-heartbeat
```

## Safety Notes

1. Always run `bring-up.sh` before flight
2. Verify status is **green** before arming
3. MCP server should only be enabled on trusted networks
4. Keep watchdog service enabled for autonomous reliability

## Support

- Documentation: https://github.com/your-org/project-avatar
- Issues: https://github.com/your-org/project-avatar/issues
