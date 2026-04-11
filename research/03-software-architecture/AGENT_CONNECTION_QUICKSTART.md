# Quick Reference: Connecting Agents to Project Avatar

**One-liner**: Install the MCP server, configure your agent, start flying.

---

## Claude Code

```bash
# 1. Install MCP server
claude mcp add drone-server \
  --command "python /path/to/avatar/scripts/run_mcp_server.py" \
  --transport stdio

# 2. Start Claude Code
# 3. Type: "Take off to 10 meters"
```

**Verify**: `claude mcp list` should show `drone-server`

---

## OpenCode

```bash
# 1. Create skill directory
mkdir -p ~/.opencode/skills/drone-control

# 2. Create skill configuration
cat > ~/.opencode/skills/drone-control/skill.json << 'EOF'
{
  "name": "drone-control",
  "version": "2.0",
  "mcp_server": {
    "command": "python /path/to/avatar/scripts/run_mcp_server.py",
    "args": [],
    "transport": "stdio"
  }
}
EOF

# 3. Enable skill in OpenCode UI
# 4. Chat: "Orbit the park at 20m"
```

---

## Python Script (Custom)

```python
#!/usr/bin/env python3
"""Quick drone controller using MCP."""

import asyncio
from mcp import ClientSession, StdioServerParameters

async def main():
    # Connect to drone MCP server
    server = StdioServerParameters(
        command="python",
        args=["/path/to/avatar/scripts/run_mcp_server.py"]
    )
    
    async with ClientSession(server) as session:
        # List tools
        tools = await session.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        
        # Get telemetry
        telemetry = await session.call_tool("get_telemetry")
        print(f"Battery: {telemetry.battery_percent}%")
        
        # Take off
        result = await session.call_tool(
            "arm_and_takeoff", 
            {"altitude_m": 10}
        )
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Configuration: Environment Variables

All agents use the same configuration:

```bash
# Required
export FIREWORKS_API_KEY="your-key-here"  # For Kimi LLM
export DRONE_MAVLINK_URL="udp://:14540"    # MAVLink connection

# Optional
export DRONE_USE_KIMI="true"               # Enable cloud LLM
export DRONE_FRAME_INTERVAL="3.0"          # Seconds between frames to Kimi
export DRONE_CONFIRMATION_TIMEOUT="10"     # Seconds to wait for user confirm
```

---

## Testing Connection

```bash
# Universal test (works with any MCP client)
python scripts/test_agent_connection.py

# Expected output:
# ✓ MCP server reachable
# ✓ Tools available: 15
# ✓ Telemetry readable
# ✓ Vision working
# ✓ Planning functional
# All tests passed!
```

---

## Common Commands (All Agents)

| Command | Tool | Example |
|---------|------|---------|
| Take off | `arm_and_takeoff` | `"Take off to 10m"` |
| Fly to GPS | `goto_gps` | `"Fly to lat: 43.65, lon: -79.38"` |
| Orbit | `fly_body_offset` | `"Orbit clockwise"` |
| Land | `land` | `"Land now"` |
| Return home | `rtl` | `"Return to launch"` |
| Check status | `get_telemetry` | `"What's the battery?"` |
| Take photo | `capture_frame` | `"Show me the view"` |
| Abort | `abort_mission` | `"Emergency stop"` |

---

## Troubleshooting

**"Agent can't see drone tools"**
```bash
# Restart MCP server
pkill -f run_mcp_server.py
python scripts/run_mcp_server.py
```

**"Connection refused"**
```bash
# Check MAVLink
# Is RPi connected? Check network.
ping raspberrypi.local
```

**"Kimi not responding"**
```bash
# Check API key
echo $FIREWORKS_API_KEY
# Should show your key
```

**"No vision"**
```bash
# Check camera stream
python -c "from avatar.vision.video_client import test_stream; test_stream()"
```

---

## Architecture Recap

```
You → [Any MCP Agent] → Drone MCP Server → Drone
              ↓
         [Optional: Kimi LLM for planning]
```

**Key Point**: The drone doesn't care which agent you use.

---

## Next Steps

1. **Install**: `python scripts/install_mcp_server.py`
2. **Configure**: Set `FIREWORKS_API_KEY` (optional, for Kimi)
3. **Connect**: Use your preferred agent (Claude Code, OpenCode, etc.)
4. **Test**: `arm_and_takeoff(altitude_m=5)` in safe area
5. **Fly**: Natural language missions!

---

**Documentation**: See `mcp_agent_agnostic_design.md` for full details.
