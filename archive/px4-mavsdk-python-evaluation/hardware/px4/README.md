# PX4 Provisioning

This directory contains tools for PX4 flight controller provisioning, including firmware flashing, sensor calibration, parameter verification, and pre-flight checks.

## Directory Structure

```
hardware/px4/
├── README.md              # This file
├── flash-px4.sh           # Firmware flash script
├── calibrate.py           # Sensor calibration script
├── verify.py              # Parameter verification module
├── preflight.py           # Pre-flight check CLI
└── airframes/
    ├── mark4_7in.params    # Mark4 7" quad parameters
    ├── x500_v2.params      # X500 v2 kit parameters
    └── custom_template.params  # Template for custom builds
```

## Quick Start

### 1. Flash Firmware

```bash
# Dry-run to verify configuration
./hardware/px4/flash-px4.sh --airframe mark4_7in --dry-run

# Flash to Pixhawk 6X (auto-detect USB port)
./hardware/px4/flash-px4.sh --airframe mark4_7in

# Flash with explicit port
./hardware/px4/flash-px4.sh --airframe mark4_7in --port /dev/ttyACM0
```

### 2. Apply Airframe Parameters

After flashing, load the airframe-specific parameters:

1. Connect to flight controller via QGroundControl
2. Open Vehicle Setup > Parameters
3. Load from file: `hardware/px4/airframes/mark4_7in.params`
4. Reboot flight controller

### 3. Calibrate Sensors

```bash
# Full calibration sequence
python hardware/px4/calibrate.py --system udp://:14540

# Individual calibrations
python hardware/px4/calibrate.py --system udp://:14540 --accel-only
python hardware/px4/calibrate.py --system udp://:14540 --gyro-only

# Dry-run (print instructions only)
python hardware/px4/calibrate.py --dry-run
```

Calibration order (automatically followed):
1. **Accelerometer** - 6-position orientation
2. **Gyroscope** - Stationary on level surface
3. **Magnetometer** - Outdoor rotation pattern
4. **Level Horizon** - Fine-tune on level surface
5. **RC** - Radio control stick calibration
6. **Motor** - Verify motor direction/order (REMOVE PROPS!)

### 4. Run Pre-flight Verification

```bash
# Dry-run (no drone required)
python hardware/px4/preflight.py --dry-run --airframe mark4_7in

# Live verification with SITL
python hardware/px4/preflight.py --airframe mark4_7in --system udp://:14540

# JSON output for scripting
python hardware/px4/preflight.py --dry-run --airframe mark4_7in --json
```

Expected output:
```json
{"status":"PASS","mode":"dry_run","airframe":"mark4_7in",...}
```

## Airframe Parameters

### mark4_7in.params

Mark4 7" 6S 1500kV racing/freestyle quad:
- **SYS_AUTOSTART**: 4001 (Generic quad)
- **Battery**: 6S LiPo, 1500mAh
- **Geofence**: 500m horizontal, 150m vertical
- **Failsafe**: RTL on offboard/RC/data link loss

### x500_v2.params

PX4 X500 v2 development kit:
- **SYS_AUTOSTART**: 4011 (X500)
- **Battery**: 4S LiPo, 5000mAh
- **Geofence**: 500m horizontal, 150m vertical
- **Failsafe**: RTL on offboard/RC/data link loss

### Custom Airframes

1. Copy `custom_template.params` to `<your_airframe>.params`
2. Fill in all required parameters
3. Run preflight verification
4. Test in SITL before real hardware

## Parameter Categories

### Offboard Failsafe (Critical for LLM Control)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `COM_OBL_RC_ACT` | 3 | RTL on offboard loss |
| `COM_OF_LOSS_T` | 0.5 | 500ms timeout |

### RC Failsafe

| Parameter | Value | Description |
|-----------|-------|-------------|
| `NAV_RCL_ACT` | 2 | RTL on RC loss |
| `COM_RCL_EXCEPT` | 4 | Ignore RC loss in OFFBOARD |

### Battery Failsafe

| Parameter | Value | Description |
|-----------|-------|-------------|
| `BAT_LOW_THR` | 0.25 | 25% warning |
| `BAT_CRIT_THR` | 0.15 | 15% critical |
| `BAT_EMERGEN_THR` | 0.10 | 10% emergency |

### Geofence

| Parameter | Value | Description |
|-----------|-------|-------------|
| `GF_MAX_HOR_DIST` | 500 | 500m radius |
| `GF_MAX_VER_DIST` | 150 | 150m altitude |
| `GF_ACTION` | 2 | Land on breach |

## SITL Testing

For simulation testing with PX4 SITL:

```bash
# Start SITL with Gazebo
cd PX4-Autopilot
make px4_sitl gz_x500

# Run preflight (SITL auto-loads params)
python hardware/px4/preflight.py --airframe x500_v2 --system udp://:14540

# Run calibration dry-run
python hardware/px4/calibrate.py --dry-run
```

## MCP Integration

The MCP server's `preflight_checklist` tool calls this script:

```python
# avatar/mcp_server/tools/primitives/preflight.py
result = subprocess.run(
    ["python", "hardware/px4/preflight.py", "--dry-run", "--airframe", airframe],
    capture_output=True,
    text=True,
)
```

## Troubleshooting

### Flash Failed

1. Check USB cable connection
2. Verify flight controller is in bootloader mode
3. Try explicit `--port` argument
4. Check user has permission for serial port (Linux: add to `dialout` group)

### Calibration Failed

1. Accelerometer: Ensure all 6 positions are held steady
2. Gyroscope: Ensure drone is on perfectly flat, still surface
3. Magnetometer: Move away from metal/rebar/electronics
4. Motor: REMOVE PROPS before running

### Pre-flight Failed

1. Check params file exists for airframe
2. Verify all CRITICAL_PARAMETERS are defined
3. For live mode, check MAVSDK connection
4. Review warnings in output

## References

- [PX4 Parameter Reference](https://docs.px4.io/main/en/advanced_config/parameter_reference.html)
- [PX4 Calibration](https://docs.px4.io/main/en/flying/flight_mode_2.html)
- [MAVSDK Python](https://github.com/mavlink/MAVSDK-Python)
- [QGroundControl](https://docs.qgroundcontrol.com/)
