# Project Avatar Phase 0.5 - Demo Video Script

**Duration**: 4-5 minutes
**Format**: Screen recording (Gazebo + Terminal split view)
**Recording Tool**: QuickTime Player (macOS)

---

## Pre-Recording Setup

### Terminal Layout (3 terminals side-by-side or tiled)

1. **Terminal 1 - Gazebo SITL**: PX4 SITL with Gazebo visualization
2. **Terminal 2 - MCP Server**: Drone MCP server running
3. **Terminal 3 - Claude Code**: Agent interface for natural language commands

### Pre-Flight Checklist

```bash
# Terminal 1: Start PX4 SITL + Gazebo
cd ~/PX4-Autopilot
make px4_sitl gz_x500
# Wait for: "[px4] INFO: Ready for takeoff" and Gazebo window to appear

# Terminal 2: Start MCP Server
cd ~/Project-Avatar
source venv/bin/activate
python -m avatar.mcp_server.server
# Wait for: "Connected to drone successfully"

# Terminal 3: Start Claude Code with MCP
claude
# Verify MCP tools are available (auto-loaded from settings)
```

---

## Scene 1: SITL Startup (0:00 - 0:30)

### Visual
- Full screen or split showing Gazebo window
- X500 quadrotor drone model in simulation environment

### Narration/Audio
"This is Project Avatar Phase 0.5 - a complete autonomous drone system running entirely in PX4 SITL simulation. The drone you see is a virtual X500 quadrotor in Gazebo, using the same MAVLink protocol as real hardware."

### Actions (No interaction needed - just show startup)

```
# Already running from setup
# Highlight the Gazebo window showing:
# - X500 drone on ground
# - Simulation environment (Zurich test field)
# - "Ready for takeoff" in terminal
```

### Key Points to Show
- Gazebo window with drone
- Terminal showing "[px4] INFO: Ready for takeoff"
- GPS lock confirmation

---

## Scene 2: MCP Server Connection (0:30 - 1:00)

### Visual
- Switch to Terminal 2 showing MCP server logs
- Then Terminal 3 showing Claude Code with MCP tools

### Narration/Audio
"The drone MCP server exposes flight control tools through the Model Context Protocol. Any MCP-compatible AI agent - Claude Code, OpenCode, or others - can connect and control the drone using natural language."

### Actions

**Step 1: Show MCP Server Status**
```
# Terminal 2 should already show:
# INFO:__main__:Starting Drone MCP Server (address: udp://:14540)
# INFO:avatar.mav.connection:Connected to drone successfully
```

**Step 2: Verify MCP Tools in Claude Code**
```
# In Terminal 3 (Claude Code), type:
> What drone tools are available?

# Claude should list:
# - arm_and_takeoff(altitude_m)
# - get_telemetry()
# - land()
# - rtl()
# - abort_mission()
```

### Key Points to Show
- MCP server running and connected
- Claude Code recognizing drone tools
- Tool descriptions and parameters

---

## Scene 3: Natural Language Flight (1:00 - 3:00)

### Visual
- Split screen: Gazebo (left) + Claude Code terminal (right)
- Drone visible in Gazebo throughout

### Narration/Audio
"Now let's demonstrate natural language drone control. The user simply asks in plain English, and the agent translates this into precise flight commands."

### Actions

**Step 1: Check Drone Status**
```
# In Claude Code:
> Check the drone status

# Claude calls get_telemetry() and shows:
{
  "success": true,
  "position": {
    "latitude_deg": 47.397742,
    "longitude_deg": 8.545594,
    "relative_altitude_m": 0.0
  },
  "battery": {
    "remaining_percent": 100.0
  },
  "flight_mode": "OFFBOARD",
  "armed": false,
  "in_air": false
}
```

**Step 2: Pre-Flight Confirmation (Show Guardian validation)**
```
# In Claude Code:
> Take off to 10 meters

# Claude shows pre-flight check:
"Before takeoff, let me verify:
 - Battery: 100% (OK)
 - GPS: Locked (OK)
 - Home position: Set (OK)
 
 Proceed with arm_and_takeoff(altitude_m=10)?"
```

**Step 3: Confirm and Take Off**
```
# User confirms:
> yes

# Claude executes:
"Arming drone... Armed.
Initiating takeoff to 10m..."

# SHOW: Drone lifting off in Gazebo
# Wait 10-15 seconds for drone to reach altitude

# Claude confirms:
"Takeoff initiated to 10m. Drone is now hovering."
```

**Step 4: Show Telemetry During Flight**
```
# In Claude Code:
> What's the current altitude?

# Claude calls get_telemetry() and shows:
{
  "position": {
    "relative_altitude_m": 10.2
  },
  "velocity": {
    "north_m_s": 0.01,
    "east_m_s": -0.02,
    "down_m_s": 0.0
  },
  "in_air": true
}
```

### Key Points to Show
- Natural language understanding
- Pre-flight safety checks
- Drone movement in Gazebo
- Real-time telemetry updates

---

## Scene 4: Safety & Abort (3:00 - 4:00)

### Visual
- Continue split screen
- Show terminal logs for safety validation

### Narration/Audio
"Safety is paramount. The Guardian Process validates every command against hard limits. Let's demonstrate the abort functionality - useful for emergencies or when unexpected situations arise."

### Actions

**Step 1: Demonstrate Abort Command**
```
# In Claude Code:
> Abort the mission

# Claude executes abort_mission():
{
  "success": true,
  "message": "Mission aborted - drone hovering in place"
}

# SHOW: Drone holds position in Gazebo
```

**Step 2: Show Return to Launch**
```
# In Claude Code:
> Return home and land

# Claude executes rtl():
{
  "success": true,
  "message": "Return to Launch initiated - drone returning home",
  "home_position": {
    "latitude": 47.397742,
    "longitude": 8.545594
  }
}

# SHOW: Drone flying back to launch point in Gazebo
# Wait for drone to reach home and start descending
```

**Step 3: Landing Confirmation**
```
# Claude confirms:
"Drone has landed safely at home position."

# get_telemetry() shows:
{
  "armed": false,
  "in_air": false,
  "relative_altitude_m": 0.0
}
```

### Key Points to Show
- Abort/hover functionality
- Return to Launch behavior
- Safe landing sequence
- GuardianProcess validation logs

---

## Scene 5: Wrap-up (4:00 - 4:30)

### Visual
- Drone on ground in Gazebo
- Summary overlay or text

### Narration/Audio
"Phase 0.5 is complete. We've demonstrated:
- PX4 SITL + Gazebo simulation
- Agent-agnostic MCP interface
- Natural language drone control
- GuardianProcess safety validation
- Safe abort and landing procedures

All software has been validated in simulation. The same code will control real hardware with just a connection string change - from UDP to serial.

Ready for Stage 1: Hardware integration."

### End Screen
```
Project Avatar Phase 0.5: COMPLETE

Components Validated:
[✓] PX4 SITL + Gazebo simulation
[✓] Agent-agnostic MCP server
[✓] Natural language control via Claude Code
[✓] GuardianProcess safety validation
[✓] Abort and RTL functionality

Next: Stage 1 - Hardware Integration
```

---

## Recording Instructions

### QuickTime Setup
1. Open QuickTime Player
2. File > New Screen Recording
3. Select "Record Entire Screen" or drag to select region
4. Ensure all 3 terminals are visible

### Audio
- Use built-in microphone or external mic
- Record narration live or add in post-production

### Post-Production
- Trim beginning/end
- Add title cards between scenes (optional)
- Export as H.264 MP4 (1080p recommended)
- Upload to YouTube/Vimeo

### Backup Recording
```bash
# Alternative: Use ffmpeg for recording
ffmpeg -f avfoundation -i "1" -r 30 -pix_fmt uyvy422 demo_phase_0.5.mp4
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Address already in use" | `pkill -f px4; pkill -f gz` then restart SITL |
| "Connection refused" | Wait longer for SITL to fully initialize |
| "No GPS fix" | Wait 10-30 seconds for GPS convergence |
| Drone flips on takeoff | Restart SITL with `make px4_sitl gz_x500` |
| MCP tools not showing | Check Claude Code MCP configuration |

---

## File Locations

| Component | Path |
|-----------|------|
| MCP Server | `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mcp_server/server.py` |
| Flight Tools | `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mcp_server/tools/flight_tools.py` |
| Guardian Process | `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mav/guardian.py` |
| Confirmation Workflow | `/Users/muadhsambul/Downloads/Project-Avatar/avatar/mcp_server/confirmation.py` |
| PX4 SITL | `~/PX4-Autopilot` |

---

## Demo Timeline Summary

| Scene | Time | Duration | Content |
|-------|------|----------|---------|
| 1 | 0:00-0:30 | 30s | SITL startup, Gazebo visualization |
| 2 | 0:30-1:00 | 30s | MCP server, tool discovery |
| 3 | 1:00-3:00 | 2m | Natural language flight |
| 4 | 3:00-4:00 | 1m | Safety & abort demo |
| 5 | 4:00-4:30 | 30s | Wrap-up summary |

**Total**: ~4.5 minutes

---

*Script prepared for Project Avatar Phase 0.5 demo video recording.*
