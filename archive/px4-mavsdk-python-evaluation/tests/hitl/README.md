# HITL (Hardware-In-The-Loop) Tests

This directory contains pytest tests for validating drone behavior on real hardware.

## Running HITL Tests

HITL tests are gated by the `--run-hitl` flag. They are skipped by default:

```bash
# Collect tests (shows skips)
python3 -m pytest tests/hitl --collect-only -q

# Run HITL tests with fc_bench topology
export AVATAR_HITL_TARGET=fc_bench
python3 -m pytest tests/hitl --run-hitl -rs

# Run only preflight tests
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
```

## Topologies

### fc_bench (SIH-on-FC)

USB connection to Flight Controller with SYS_HITL=2 enabled.

Requirements:
- FC connected via USB (/dev/pixhawk or /dev/ttyUSB*)
- SYS_HITL=2 parameter set on FC
- PX4 firmware with SIH support

### pi_plus_fc (Pi Bridge)

Laptop -> Raspberry Pi -> FC UART connection.

Requirements:
- Raspberry Pi on network (AVATAR_PI_HOST defaults to avatar.local)
- mavsdk_server running on Pi
- SSH access to Pi for verification

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| AVATAR_HITL_TARGET | (required) | Topology: fc_bench or pi_plus_fc |
| AVATAR_FC_SERIAL_BAUD | 921600 | Serial baud rate for fc_bench |
| AVATAR_PI_HOST | avatar.local | Pi hostname for pi_plus_fc |
| AVATAR_PI_MAVSDK_UDP | udp://:14540 | UDP URI for Pi bridge |

## Test Categories

- `hitl`: All HITL tests
- `preflight`: Preflight CLI validation subset

## Markers

Tests use pytest markers for categorization:

```python
@pytest.mark.hitl        # Standard HITL test
@pytest.mark.preflight   # Preflight gate test (W4)
```
