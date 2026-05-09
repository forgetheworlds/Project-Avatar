# Project Avatar — ArduPilot SITL Simulation

Software-in-the-Loop simulation environment for the Project Avatar 3.5" class
quadcopter drone. Uses ArduPilot's SITL with ArduCopter vehicle type.

## Hardware Profile

| Parameter       | Value              |
|-----------------|--------------------|
| Frame class     | 3.5" (~220g dry)   |
| Motors          | 1505 3800KV        |
| Battery         | 4S (14.8V nominal) |
| GPS             | Enabled            |
| Compass         | Enabled            |
| Flight modes    | STABILIZE, ALT_HOLD, LOITER, GUIDED, AUTO, CIRCLE, RTL, LAND |

## Prerequisites

- macOS (tested) or Linux
- Python 3.8+ with `pymavlink` (`pip install pymavlink`)
- ArduPilot repository (cloned automatically if not present)

### Installing ArduPilot

```bash
# Clone
cd ~
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git

# Install macOS dependencies
cd ardupilot
bash Tools/environment_install/install-prereqs-mac.sh -y

# Build SITL (first launch will also build)
./waf configure --board sitl
./waf copter
```

## Quick Start

### 1. Launch the Simulator

**Terminal 1** — Start SITL:

```bash
cd ~/Downloads/Project-Avatar/sim
chmod +x launch.sh

# Interactive (with map + console GUI)
./launch.sh

# Headless (for scripting / MCP server)
./launch.sh --headless
```

The simulator outputs MAVLink on two UDP ports:
- **UDP 127.0.0.1:14550** — Standard GCS port (QGroundControl, Mission Planner, etc.)
- **UDP 127.0.0.1:14551** — Scripting / MCP server port

Wait for the prompt: `Got MAVLink msg: COMMAND_ACK` — SITL is ready.

### 2. Control via Script

**Terminal 2** — Run MAVLink commands:

```bash
cd ~/Downloads/Project-Avatar/sim
python3 mavlink_control.py status       # Check telemetry
python3 mavlink_control.py arm           # Arm motors
python3 mavlink_control.py takeoff 5.0   # Takeoff to 5 meters
python3 mavlink_control.py goto 47.398 8.546 20.0  # Fly to waypoint
python3 mavlink_control.py orbit 15.0    # Orbit at 15m radius
python3 mavlink_control.py land          # Land
python3 mavlink_control.py rtl           # Return to launch
```

### 3. Run a Waypoint Mission

```bash
# Use the example mission
python3 mavlink_control.py mission example_mission.json
```

Custom missions are JSON arrays of waypoints:
```json
[
    {"cmd": 22, "lat": 47.3980, "lon": 8.5460, "alt": 10.0},
    {"cmd": 16, "lat": 47.3990, "lon": 8.5470, "alt": 15.0},
    {"cmd": 21, "lat": 47.3980, "lon": 8.5460, "alt": 0.0}
]
```

MAV_CMD values:
- `16` = WAYPOINT
- `21` = LAND
- `22` = TAKEOFF
- `20` = RTL

## Files

```
sim/
├── README.md                 # This file
├── launch.sh                 # SITL launch script
├── mavlink_control.py        # MAVLink control/telemetry script
├── example_mission.json      # Sample waypoint mission
└── params/
    └── sitl_quad.parm        # Custom vehicle parameters
```

## Customizing

### Change Default Location

```bash
# San Francisco
./launch.sh --location 37.7749,-122.4194,10,0

# Zurich
./launch.sh --location 47.3980,8.5460,500,0
```

### Custom Parameters

Edit `params/sitl_quad.parm` to adjust:
- Battery capacity and voltage thresholds
- PID tuning values
- Motor hover throttle
- Waypoint speed and acceleration
- Failsafe behaviors

### Multiple Instances

```bash
# Instance 0 on 14550/14551
./launch.sh --headless &

# Instance 1 on 14560/14561
./launch.sh --headless --instance 1 &
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No heartbeat received` | SITL not running. Start `launch.sh` first. |
| `sim_vehicle.py not found` | Set `ARDUPILOT_HOME` or clone to `~/ardupilot` |
| `waf: command not found` | Run install-prereqs-mac.sh, then `./waf configure --board sitl` |
| Connection refused | Check MAVLink output is configured on the expected port |
| `pymavlink` not installed | `pip install pymavlink` |

## MAVLink Interface Reference

| Port | Purpose |
|------|---------|
| UDP 127.0.0.1:14550 | Primary GCS connection |
| UDP 127.0.0.1:14551 | Secondary / scripting / MCP |

The MCP server can connect to `udp:127.0.0.1:14551` and issue MAVLink commands
directly or call `mavlink_control.py` as a subprocess.

## Integration with MCP Server

The MCP server connects to UDP 14551 and can:
- Read telemetry (position, attitude, battery, GPS)
- Arm/disarm
- Switch flight modes
- Command waypoints
- Upload missions
- Monitor flight progress

The `mavlink_control.py` script serves as both a standalone CLI tool and a
reference implementation for the MAVLink protocol integration.
