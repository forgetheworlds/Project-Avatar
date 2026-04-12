# PX4 SITL + Gazebo Setup Guide

**Platform**: macOS (Apple Silicon M3)  
**Purpose**: Phase 0.5 virtual drone validation

---

## Overview

This guide walks through setting up PX4 Software-In-The-Loop (SITL) simulation with Gazebo for Project Avatar. This enables complete software validation without any hardware.

**What You Get**:
- Simulated X500 quadrotor in Gazebo
- MAVLink connectivity (same as real drone)
- Simulated camera for vision testing
- Realistic flight physics

---

## Prerequisites

### System Requirements

- macOS 14+ (Sonoma or later)
- Apple Silicon M1/M2/M3 (Intel Macs also supported but slower)
- 16GB RAM minimum (32GB recommended)
- 50GB free disk space (PX4 build is large)

### Install Dependencies

```bash
# 1. Xcode Command Line Tools (if not already installed)
xcode-select --install

# 2. Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 3. Required packages
brew install cmake git ninja genromfs geographiclib-tools

# 4. Python environment
python3 -m venv ~/avatar-venv
source ~/avatar-venv/bin/activate
pip install mavsdk ultralytics opencv-python openai mcp
```

---

## Step-by-Step Installation

### Step 1: Clone PX4 Autopilot

```bash
# Clone the repository
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot

# Checkout stable release
git checkout v1.15.0
git submodule update --init --recursive
```

### Step 2: Run macOS Setup Script

```bash
cd ~/PX4-Autopilot

# This installs all PX4 dependencies (takes 10-15 minutes)
bash ./Tools/setup/macos.sh
```

**Note**: This script installs:
- GCC ARM toolchain
- Ninja build system
- Python dependencies
- Gazebo simulation environment

### Step 3: Build SITL with Gazebo

```bash
cd ~/PX4-Autopilot

# Build SITL with Gazebo and X500 model
make px4_sitl gz_x500
```

**Expected Output**:
```
[0/1] Re-running CMake...
-- PX4 version: v1.15.0
-- Building for macOS
...
[100%] Built target px4
```

**First build takes 10-20 minutes** - subsequent builds are much faster.

### Step 4: Verify SITL Works

```bash
# Terminal 1: Start SITL with Gazebo visualization
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

You should see:
- Gazebo window opens with X500 drone on the ground
- Terminal shows PX4 boot messages
- `[px4] INFO: Ready for takeoff` message

Keep this terminal running.

### Step 5: Test MAVSDK Connection

Open a **new terminal**:

```bash
# Activate your Python environment
source ~/avatar-venv/bin/activate

# Test script
python3 << 'EOF'
import asyncio
from mavsdk import System

async def test_sitl():
    print("Connecting to SITL...")
    
    drone = System()
    await drone.connect(system_address="udp://:14540")
    
    print("Waiting for drone...")
    async for health in drone.telemetry.health():
        print(f"GPS valid: {health.is_global_position_valid}")
        print(f"Gyro calibrated: {health.is_gyros_calibration_ok}")
        break
    
    print("\nTesting basic commands...")
    
    # Arm
    await drone.action.arm()
    print("Armed!")
    
    # Takeoff
    await drone.action.takeoff()
    print("Taking off...")
    
    # Wait
    await asyncio.sleep(5)
    
    # Land
    await drone.action.land()
    print("Landing...")
    
    await asyncio.sleep(5)
    print("Test complete!")

asyncio.run(test_sitl())
EOF
```

**Expected**: You should see the drone in Gazebo take off, hover, and land.

---

## Configuration

### MAVLink Ports

| Connection | Address |
|------------|---------|
| MAVSDK Python | `udp://:14540` |
| QGroundControl | `udp://:14550` |
| MAVLink Inspector | `udp://:14540` |

### PX4 Parameters for Phase 0.5

```bash
# In PX4 shell (terminal running SITL)
param set COM_OBL_RC_ACT 3      # RTL on offboard loss
param set COM_OF_LOSS_T 0.5     # 500ms timeout
param set GF_MAX_HOR_DIST 500   # Geofence: 500m
param set GF_MAX_VER_DIST 120   # Geofence: 120m altitude
param save
```

### Environment Variables

```bash
# Add to ~/.zshrc or run before testing
export MAVSDK_PORT=14540
export FIREWORKS_API_KEY="your-key-here"
export GOOGLE_MAPS_API_KEY="your-key-here"  # Optional
```

---

## Running SITL

### Standard Start

```bash
# Terminal 1: SITL + Gazebo
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

### Headless Mode (No GUI)

```bash
# For automated testing without visualization
cd ~/PX4-Autopilot
HEADLESS=1 make px4_sitl gz_x500
```

### With Camera Model

```bash
# X500 with depth camera for vision testing
cd ~/PX4-Autopilot
make px4_sitl gz_x500_depth
```

### Stopping SITL

```bash
# In SITL terminal
# Press: Ctrl+C

# Or kill all processes
pkill -f px4
pkill -f gz
```

---

## macOS Specific Notes

### Apple Silicon (M1/M2/M3)

PX4 builds natively on Apple Silicon. No Rosetta required.

**Performance**:
- Build time: ~10 minutes
- SITL real-time factor: 1.0 (perfect)
- Memory usage: ~4GB

### Memory Management

If you encounter memory errors during build:

```bash
# Increase file descriptor limit
ulimit -n 10240

# Free memory before building
sudo purge
```

### Screen Recording for Demo

```bash
# Using QuickTime Player
open -a "QuickTime Player"
# File > New Screen Recording

# Using ffmpeg (install first: brew install ffmpeg)
ffmpeg -f avfoundation -i "1" -r 30 demo.mp4
```

---

## Troubleshooting

### Problem: "Address already in use"

**Cause**: Previous SITL instance still running.

**Solution**:
```bash
pkill -f px4
pkill -f gz
sleep 2
make px4_sitl gz_x500
```

### Problem: "No GPS fix"

**Cause**: SITL needs time to simulate GPS.

**Solution**: Wait 10-30 seconds. GPS should converge automatically.

### Problem: "Gazebo won't start"

**Cause**: Missing Gazebo dependencies.

**Solution**:
```bash
# Re-run setup
cd ~/PX4-Autopilot
bash ./Tools/setup/macos.sh --clean
make px4_sitl gz_x500
```

### Problem: "MAVSDK connection refused"

**Cause**: SITL not fully started.

**Solution**:
```bash
# Wait for this message before connecting:
# [px4] INFO: Ready for takeoff
```

### Problem: "Drone flips on takeoff"

**Cause**: Simulation instability.

**Solution**:
```bash
# Reset simulation
# In SITL terminal:
reset

# Or restart SITL
make px4_sitl gz_x500
```

### Problem: Build errors after macOS update

**Cause**: Xcode tools outdated.

**Solution**:
```bash
sudo xcode-select --switch /Library/Developer/CommandLineTools
xcode-select --install
cd ~/PX4-Autopilot
bash ./Tools/setup/macos.sh --clean
```

---

## Useful Commands

### PX4 Console Commands

```bash
# In SITL terminal:
status              # Show system status
top                 # CPU usage
listener <topic>    # Listen to MAVLink topic
param show <param>  # Show parameter value
param set <p> <v>   # Set parameter
reboot              # Restart simulation
reset               # Reset to initial state
shutdown            # Stop SITL
```

### Gazebo Controls

| Key | Action |
|-----|--------|
| Space | Pause/resume |
| T | View from top |
| W/A/S/D | Move camera |
| Mouse drag | Rotate camera |
| Scroll | Zoom |

---

## Integration with Project Avatar

### MCP Server Connection

```bash
# Terminal 1: SITL
cd ~/PX4-Autopilot
make px4_sitl gz_x500

# Terminal 2: MCP Server
source ~/avatar-venv/bin/activate
cd ~/Project-Avatar
python avatar/mcp_server/server.py

# Terminal 3: Agent (Claude Code)
claude
# Then use drone tools
```

### Test Mission Script

```bash
# Full end-to-end test
cd ~/Project-Avatar
python tests/test_sitl_basic.py
```

---

## Resources

- **PX4 Documentation**: https://docs.px4.io/main/en/simulation/
- **MAVSDK Python**: https://github.com/mavlink/MAVSDK-Python
- **Gazebo Simulation**: https://gazebosim.org/
- **Project Avatar Phase 0.5 Plan**: `research/01-core-project/PHASE_0_5_FULL_SITL_PLAN.md`

---

## Next Steps

After SITL is working:

1. Run `tests/test_sitl_basic.py` to verify MAVSDK connection
2. Test MCP server with `python mcp_server/server.py`
3. Connect your AI agent and test natural language commands
4. Run integration tests with Kimi LLM
5. Record demo video

---

*SITL Setup Guide - Phase 0.5 Documentation*
