# Project Avatar: Agent-Agnostic MCP Architecture

**Version**: 2.1 (April 2026)  
**Purpose**: Explain how the drone MCP server works with ANY AI agent supporting the Model Context Protocol

---

## Philosophy: Agent Independence

Project Avatar is designed to work with **any MCP-compatible AI agent**, not just one specific platform. This provides:

- **Portability**: Switch agents without changing drone software
- **Future-proofing**: New agents can connect without code changes
- **User choice**: Use your preferred agent (Claude, OpenCode, Hermes, etc.)
- **Interoperability**: Part of the growing MCP ecosystem

---

## What is MCP?

**Model Context Protocol (MCP)** is an open standard for connecting AI assistants to external tools and data sources. Think of it as "USB-C for AI agents" - a universal interface that works across different platforms.

**Key Features**:
- Standardized tool calling interface
- JSON schema for type safety
- Bi-directional communication
- Growing ecosystem support

**Official Resources**:
- Website: https://modelcontextprotocol.io
- Specification: https://spec.modelcontextprotocol.io
- SDKs: Python, TypeScript, and more

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER (Any MCP Client)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Claude     │  │   OpenCode   │  │   Hermes     │              │
│  │    Code      │  │   (Sisyphus) │  │   (Future)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼────────────────┼────────────────┼──────────────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                    ┌──────▼──────┐
                    │   MCP Wire   │
                    │  Protocol    │
                    └──────┬──────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────┐
│                   DRONE MCP SERVER (Agent-Agnostic)                │
│  ┌───────────────────────┼─────────────────────────────────────┐   │
│  │  MCP Server Core     │  Receives tool calls from ANY agent   │   │
│  │  - JSON validation   │  - Returns telemetry to ANY agent     │   │
│  │  - Session tracking  │  - Streams video to ANY agent           │   │
│  └───────────────────────┼─────────────────────────────────────┘   │
│                          │                                          │
│  ┌───────────────────────▼─────────────────────────────────────┐   │
│  │                   ORCHESTRATION LAYER                        │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐     │   │
│  │  │  Guardian   │  │  Kimi Client │  │  Mission Planner │     │   │
│  │  │  Process    │  │  (Optional)  │  │  (Optional LLM)  │     │   │
│  │  │  (Safety)   │  │  (Vision)    │  │  (Planning)      │     │   │
│  │  └─────────────┘  └──────────────┘  └──────────────────┘     │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                          │                                          │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   MAVLink   │
                    └──────┬──────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────┐
│                   DRONE HARDWARE (Hardware Layer)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐          │
│  │  Raspberry   │  │   Pixhawk    │  │    Camera +      │          │
│  │     Pi 4     │  │     6C       │  │    Sensors       │          │
│  └──────────────┘  └──────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Connection Guide

### 1. Claude Code (Anthropic)

**Setup**:
```bash
# Add MCP server to Claude Code
claude mcp add drone-server \
  --command "python /path/to/avatar/scripts/run_mcp_server.py" \
  --transport stdio
```

**Usage**:
```
User: "Drone, take off to 10 meters"
Claude: "I'll help you take off. Calling arm_and_takeoff(altitude_m=10)..."
[Calls MCP tool]
[Returns telemetry]
Claude: "Successfully armed and took off. Current altitude: 10.2m"
```

---

### 2. OpenCode

**Setup**:
```bash
# Add to .opencode/skills/ or via UI
# Configure connection to drone MCP server
```

**Configuration** (`drone_skill.json`):
```json
{
  "name": "drone-control",
  "mcp_server": {
    "command": "python /path/to/avatar/scripts/run_mcp_server.py",
    "transport": "stdio"
  },
  "tools": ["arm_and_takeoff", "goto_gps", "land", "capture_frame"]
}
```

**Usage**:
```
User: "Orbit this park at 20m"
Sisyphus: [Uses plan_mission tool with Kimi]
Sisyphus: "Mission plan generated. Preview: [shows map]. Confirm?"
User: "yes"
Sisyphus: "Executing orbit mission..."
```

---

### 3. Hermes (Future)

**Setup**:
```bash
# Configure in hermes.toml
[mcp.servers.drone]
command = "python /path/to/avatar/scripts/run_mcp_server.py"
transport = "stdio"
```

**Usage**:
```bash
$ hermes ask "Take off and hover at 15m"
Hermes: Planning mission...
Hermes: Executing arm_and_takeoff(altitude_m=15)
Hermes: ✓ Hovering at 15.1m
```

---

### 4. OpenClaw (Future)

**Setup**:
```bash
# Via web UI or config file
# Add MCP connector pointing to drone server
```

**Usage**:
- Web interface shows live telemetry
- Natural language input field
- Confirmation dialogs for safety

---

### 5. Custom Scripts (Python)

**Setup**:
```python
from mcp import ClientSession, StdioServerParameters

# Connect to drone MCP server
server_params = StdioServerParameters(
    command="python",
    args=["/path/to/avatar/scripts/run_mcp_server.py"]
)

async with ClientSession(server_params) as session:
    # Call any tool
    result = await session.call_tool("arm_and_takeoff", {"altitude_m": 10})
    print(result)
```

---

## Tool Interface (Agent-Agnostic)

All agents use the **same tool interface**:

### Flight Control Tools
```python
arm_and_takeoff(altitude_m: float) -> FlightResult
goto_gps(lat: float, lon: float, alt_m: float, speed_ms: float) -> FlightResult
set_velocity(vx: float, vy: float, vz: float, yaw_rate: float) -> FlightResult
fly_body_offset(forward_m: float, right_m: float, up_m: float) -> FlightResult
hold_position(seconds: float = 0) -> FlightResult
land() -> FlightResult
rtl() -> FlightResult  # Return to Launch
abort_mission(reason: str) -> FlightResult
```

### Telemetry & Status Tools
```python
get_telemetry() -> TelemetryData
get_mission_status() -> MissionState
get_battery_status() -> BatteryInfo
```

### Vision Tools
```python
capture_frame() -> Image  # Returns current camera frame
get_detected_objects() -> List[DetectedObject]
```

### Planning Tools (Optional LLM)
```python
plan_mission(natural_language_request: str) -> MissionPlan
# If Kimi configured: Uses LLM for intelligent planning
# If no LLM: Uses template-based planning
```

---

## Confirmation Workflow (Agent-Driven)

The **agent** handles user interaction; the **server** provides data:

```
1. MISSION REQUEST
   User (via agent): "Orbit the park at 20m"
   
2. PLANNING (Server provides, Agent displays)
   Server: plan_mission() → returns MissionPlan
   Agent: Shows plan preview to user
   
3. CONFIRMATION (Agent handles)
   Agent: "Confirm orbit at 20m with 30m radius?"
   User: "yes"
   
4. EXECUTION (Server performs)
   Server: arm_and_takeoff() → goto_gps() → [orbit logic]
   
5. MONITORING (Server streams, Agent displays)
   Server: Telemetry updates
   Agent: Shows live position, altitude, etc.
   
6. EXCEPTIONS (Server detects, Agent confirms)
   Server: "People detected 10m away"
   Agent: "People nearby. Stop or continue?"
   User: "stop"
   Server: hold_position()
```

**Key Point**: The agent can be ANY MCP client - the workflow is identical.

---

## Configuration: With vs Without Kimi

### Configuration A: Full Intelligence (Kimi Enabled)
```yaml
# config.yaml
llm:
  enabled: true
  provider: fireworks
  model: accounts/fireworks/models/kimi-k2-5
  api_key: ${FIREWORKS_API_KEY}
  
mcp_server:
  use_llm_for_planning: true
  
vision:
  send_frames_to_llm: true
  frame_interval_seconds: 3.0
```

**Capabilities**:
- `plan_mission()` uses Kimi for intelligent planning
- `capture_frame()` sent to Kimi for analysis
- Natural language understanding
- Vision-based recommendations

---

### Configuration B: Direct Control (No LLM)
```yaml
# config.yaml
llm:
  enabled: false
  
mcp_server:
  use_llm_for_planning: false
  
vision:
  send_frames_to_llm: false
```

**Capabilities**:
- Direct tool calling only
- Template-based mission planning
- YOLO detections in State String only
- No cloud dependency

**Use Case**: Works with simple agents or offline operation

---

## Agent-Specific Features (Optional)

While the core is agent-agnostic, agents can add platform-specific features:

| Feature | Claude Code | OpenCode | Hermes |
|---------|----------------|----------|--------|
| Chat history | ✅ Native | ✅ Native | ✅ Native |
| File uploads | ✅ | ✅ | ❌ |
| Web search | ✅ | ✅ | ❌ |
| Vision analysis | ✅ | ✅ | ⚠️ Limited |
| Notifications | ❌ | ⚠️ Limited | ✅ |
| CLI integration | ❌ | ❌ | ✅ |

**Implementation**: Server doesn't care - these are agent-side features.

---

## Safety: Independent of Agent

**Critical**: Safety-critical systems work regardless of agent connectivity:

```
Agent Connected:
  User → Agent → MCP Server → GuardianProcess → MAVLink → Drone
  
Agent Disconnected:
  Drone continues with last valid mission
  GuardianProcess still enforces limits
  20Hz heartbeat continues
  RC override works
  Failsafes trigger automatically
```

**Agent is NOT in the safety chain** - it's in the decision chain only.

---

## Testing Agent Compatibility

### Universal Test Script
```python
# test_agent_connection.py
# Works with ANY MCP client

async def test_drone_mcp():
    """Test basic connectivity and tool availability."""
    
    # 1. Connect to server
    session = await connect_to_drone_server()
    
    # 2. List available tools
    tools = await session.list_tools()
    assert "arm_and_takeoff" in tools
    assert "get_telemetry" in tools
    
    # 3. Test telemetry (read-only)
    telemetry = await session.call_tool("get_telemetry")
    assert telemetry.battery_percent > 0
    
    # 4. Test mission planning
    plan = await session.call_tool("plan_mission", {
        "natural_language_request": "Take off to 10m"
    })
    assert plan.steps[0].tool == "arm_and_takeoff"
    
    # 5. Test frame capture (if vision enabled)
    frame = await session.call_tool("capture_frame")
    assert frame.width > 0
    
    print("✓ All tests passed - MCP server compatible")
```

**Run with any agent**: `claude`, `opencode`, `hermes`, or custom script

---

## Best Practices for Agent Developers

If you're building a new agent that connects to Project Avatar:

### 1. Handle Confirmations Gracefully
```python
# Good: Respect server recommendations
result = await session.call_tool("plan_mission", request)
if result.requires_confirmation:
    user_response = await ask_user(result.summary)
    if user_response == "yes":
        await session.call_tool("execute_mission", result.plan)
```

### 2. Display Telemetry Richly
```python
# Good: Format telemetry for your UI
telemetry = await session.call_tool("get_telemetry")
if is_web_ui:
    show_map(telemetry.position)
    show_battery_gauge(telemetry.battery)
else:
    print(f"Battery: {telemetry.battery}%")
```

### 3. Handle Exceptions
```python
# Good: Clear error messages
try:
    await session.call_tool("goto_gps", coordinates)
except SafetyViolation as e:
    await notify_user(f"🚫 Safety check failed: {e.reason}")
except LLMUnavailable as e:
    await notify_user(f"⚠️ Planning unavailable. Direct commands only.")
```

---

## Troubleshooting Agent Connections

### Issue: Agent can't connect to MCP server
```bash
# Check server is running
python scripts/run_mcp_server.py --verbose

# Test connection manually
python -m mcp.client.cli connect stdio python scripts/run_mcp_server.py
```

### Issue: Tools not appearing in agent
- Verify `list_tools()` returns expected tools
- Check agent supports MCP tool listing
- Some agents require manual tool configuration

### Issue: Confirmation not working
- Confirm server returns `requires_confirmation: true`
- Check agent handles confirmation responses
- Verify timeout handling in agent

### Issue: Vision not working
- Check `capture_frame()` returns valid image
- Verify YOLO is running (check logs)
- Ensure agent supports image display

---

## Future: Expanding the Ecosystem

As MCP adoption grows, Project Avatar will work with:

- **IDEs**: Cursor, Windsurf, VS Code extensions
- **Mobile apps**: iOS/Android MCP clients
- **Voice assistants**: Siri, Alexa (via MCP bridges)
- **Enterprise platforms**: Slack, Teams, Discord bots
- **Custom hardware**: Dedicated ground control stations

**The drone doesn't care** - it just speaks MCP.

---

## Summary

| Aspect | Agent-Agnostic Design |
|--------|----------------------|
| **Protocol** | Model Context Protocol (MCP) |
| **Tools** | Same interface for all agents |
| **Safety** | Independent of agent (RPi/PX4) |
| **Planning** | Optional LLM (Kimi) - agent doesn't care |
| **Vision** | YOLO local + optional Kimi frames |
| **Confirmation** | Agent handles UI, server provides data |
| **Portability** | Works with any MCP client |

**The architecture is**: One MCP server, any number of agents, consistent experience.

---

## Related Documents

- `DECISIONS.md` DEC-016: Agent-Agnostic MCP Server Architecture
- `project_avatar_prd.md`: Full PRD with updated architecture
- `project_avatar_technical.md`: Implementation details
- MCP Specification: https://modelcontextprotocol.io

---

*Last Updated: 2026-04-11*  
*Architecture Version: 2.1 - Agent-Agnostic MCP*
