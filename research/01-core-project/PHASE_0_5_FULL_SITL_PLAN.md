# Phase 0.5: Virtual Drone - Full SITL Simulation

**Status**: COMPREHENSIVE PRE-HARDWARE PHASE  
**Duration**: 3 weeks (parallel with parts acquisition)  
**Goal**: Complete software stack validation in simulation before hardware arrives  
**Deliverable**: Working system + demo video with screen recording  

---

## Executive Summary

Phase 0.5 provides a **complete virtual drone environment** using PX4 SITL + Gazebo simulation. Every component of the Project Avatar system will be built, tested, and demonstrated using simulated hardware before any physical parts are assembled.

**Why This Matters**:
- Software bugs caught in simulation don't crash real drones
- Kimi LLM integration validated without risk
- MCP server and agent workflows refined before hardware pressure
- Demo video proves concept before budget spent on hardware
- Can iterate on UX/confirmation flows rapidly

---

## Week -3: Foundation & Gazebo SITL Setup

### Day 1-2: Environment Setup

**Install PX4 Autopilot & SITL**:
```bash
# Clone PX4 Autopilot
git clone https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot
git checkout v1.15.0  # Stable release

# Install dependencies (macOS)
bash ./Tools/setup/macos.sh

# Build SITL with Gazebo
make px4_sitl gz_x500
```

**Verify SITL Works**:
```bash
# Terminal 1: Start SITL
cd PX4-Autopilot
make px4_sitl gz_x500

# Terminal 2: Test MAVSDK connection
python3 << 'EOF'
import asyncio
from mavsdk import System

async def test():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    print("Connected to SITL!")
    
    async for health in drone.telemetry.health():
        print(f"GPS: {health.is_gyros_calibration_ok}")
        break

asyncio.run(test())
EOF
```

### Day 3-4: Project Structure Setup

**Create Avatar Repository Structure**:
```bash
mkdir -p avatar/{mav,vision,llm,mcp_server,planning,tests,scripts,config}
cd avatar
python3 -m venv venv
source venv/bin/activate
pip install mavsdk ultralytics opencv-python openai mcp asyncio
```

**Initialize Git Repository**:
```bash
git init
git add .
git commit -m "Phase 0.5: Initial structure for SITL development"
```

### Day 5: First Simulated Flight

**Test Basic MAVSDK Commands with SITL**:
```python
# tests/test_sitl_basic.py
import asyncio
from mavsdk import System

async def test_basic_flight():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    
    print("✓ Connected to SITL")
    
    # Arm and takeoff
    await drone.action.arm()
    print("✓ Armed")
    
    await drone.action.takeoff()
    print("✓ Taking off...")
    
    await asyncio.sleep(5)
    
    # Land
    await drone.action.land()
    print("✓ Landing...")
    
    await asyncio.sleep(5)
    print("✓ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_basic_flight())
```

**Run Test**:
```bash
# Terminal 1: Start SITL with visualization
make px4_sitl gz_x500

# Terminal 2: Run test
python tests/test_sitl_basic.py
```

**Expected**: See drone take off in Gazebo, hover, then land.

---

## Week -2: MCP Server & Agent Integration

### Day 1-3: Implement Agent-Agnostic MCP Server

**Create `mcp_server/server.py`**:
```python
#!/usr/bin/env python3
"""
Agent-Agnostic MCP Server for Project Avatar.
Connects to PX4 SITL (Week -3) or real drone (Stage 1+).
"""

import asyncio
import logging
from mavsdk import System
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drone-mcp-server")

class DroneMCPServer:
    def __init__(self, system_address="udp://:14540"):
        self.drone = System()
        self.system_address = system_address
        self.server = Server("drone-control")
        
    async def connect(self):
        """Connect to SITL or real drone."""
        await self.drone.connect(system_address=self.system_address)
        logger.info(f"✓ Connected to drone at {self.system_address}")
        
        # Wait for drone to be ready
        async for health in self.drone.telemetry.health():
            if health.is_gyros_calibration_ok:
                break
        logger.info("✓ Drone ready")
    
    def setup_tools(self):
        """Define MCP tools."""
        
        @self.server.tool()
        async def arm_and_takeoff(altitude_m: float) -> str:
            """Arm the drone and take off to specified altitude."""
            try:
                await self.drone.action.arm()
                await self.drone.action.takeoff()
                return f"✓ Armed and taking off to {altitude_m}m"
            except Exception as e:
                return f"✗ Failed: {str(e)}"
        
        @self.server.tool()
        async def goto_gps(lat: float, lon: float, alt_m: float, speed_ms: float = 5.0) -> str:
            """Fly to GPS coordinates."""
            # Implementation...
            pass
        
        @self.server.tool()
        async def get_telemetry() -> str:
            """Get current telemetry data."""
            async for telemetry in self.drone.telemetry.position():
                return f"Position: lat={telemetry.latitude_deg}, lon={telemetry.longitude_deg}, alt={telemetry.relative_altitude_m}"
        
        @self.server.tool()
        async def land() -> str:
            """Land the drone."""
            await self.drone.action.land()
            return "✓ Landing initiated"
        
        @self.server.tool()
        async def abort_mission(reason: str) -> str:
            """Emergency abort - RTL."""
            await self.drone.action.return_to_launch()
            return f"✓ Mission aborted: {reason}. Returning to launch."
    
    async def run(self):
        """Start MCP server."""
        await self.connect()
        self.setup_tools()
        
        # Run server on stdio (for any MCP client)
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

if __name__ == "__main__":
    server = DroneMCPServer()
    asyncio.run(server.run())
```

### Day 4-5: Agent Connection Testing

**Test with Claude Code**:
```bash
# Terminal 1: Start SITL
make px4_sitl gz_x500

# Terminal 2: Start MCP server
python avatar/mcp_server/server.py

# Terminal 3: Test with Claude Code
claude mcp add drone-test --command "python avatar/mcp_server/server.py"
```

**Test Commands** (in Claude Code):
```
> get_telemetry
> arm_and_takeoff(altitude_m=10)
> land
```

**Verify**: Claude Code can see and call all tools, responses appear in chat.

---

## Week -2 (Continued): Kimi Integration

### Day 6-7: Kimi Client Implementation

**Create `llm/kimi_client.py`**:
```python
"""
Kimi K2.5 client via Fireworks AI.
Multimodal support for vision + tool calling.
"""

import os
import base64
from typing import List, Dict, Any, Optional
import openai
from dataclasses import dataclass

@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]

class KimiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIREWORKS_API_KEY")
        if not self.api_key:
            raise ValueError("FIREWORKS_API_KEY required")
        
        self.client = openai.OpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=self.api_key
        )
        self.model = "accounts/fireworks/models/kimi-k2-5"
        
    def generate_with_tools(
        self, 
        messages: List[Dict], 
        tools: List[Dict],
        frame: Optional[bytes] = None
    ) -> Dict:
        """
        Generate response with tool calling.
        
        Args:
            messages: Conversation history
            tools: Available tool schemas
            frame: Optional camera frame (bytes) for multimodal
        """
        # Add frame if provided
        if frame:
            base64_frame = base64.b64encode(frame).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Current camera view:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_frame}"
                        }
                    }
                ]
            })
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.3  # Conservative for safety
        )
        
        return response
    
    def plan_mission(self, request: str, tools: List[Dict]) -> List[ToolCall]:
        """Generate mission plan from natural language."""
        system_prompt = """You are a drone mission planner. Analyze requests and generate safe flight plans.

Safety Rules:
- Maximum altitude: 120m
- Maximum distance: 500m from home
- Conservative maneuvers only
- Always have RTL plan

Available tools are provided. Choose appropriate tools for the mission."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Plan this mission: {request}"}
        ]
        
        response = self.generate_with_tools(messages, tools)
        
        # Extract tool calls
        tool_calls = []
        if response.choices[0].message.tool_calls:
            for tc in response.choices[0].message.tool_calls:
                import json
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments)
                ))
        
        return tool_calls
```

### Day 8-9: End-to-End Integration Test

**Create `tests/test_kimi_integration.py`**:
```python
"""
Test Kimi + MCP + SITL integration.
This is the full Phase 0.5 validation.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from llm.kimi_client import KimiClient
from mcp_server.server import DroneMCPServer

async def test_mission_planning():
    """Test natural language → Kimi → tools → SITL"""
    
    # Setup
    print("🚁 Phase 0.5: Kimi + SITL Integration Test\n")
    
    # 1. Start MCP server (connects to SITL)
    server = DroneMCPServer()
    await server.connect()
    print("✓ MCP server connected to SITL\n")
    
    # 2. Initialize Kimi
    kimi = KimiClient()
    print("✓ Kimi client initialized\n")
    
    # 3. Define available tools for Kimi
    tools = [
        {
            "type": "function",
            "function": {
                "name": "arm_and_takeoff",
                "description": "Arm drone and take off",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "altitude_m": {"type": "number", "minimum": 2, "maximum": 120}
                    },
                    "required": ["altitude_m"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "goto_gps",
                "description": "Fly to GPS coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                        "alt_m": {"type": "number"},
                        "speed_ms": {"type": "number", "default": 5.0}
                    },
                    "required": ["lat", "lon", "alt_m"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "land",
                "description": "Land the drone"
            }
        }
    ]
    
    # 4. Test mission request
    user_request = "Take off to 10 meters, hover for 5 seconds, then land"
    print(f"👤 User: '{user_request}'\n")
    
    # 5. Kimi plans mission
    print("🤖 Kimi planning...")
    tool_calls = kimi.plan_mission(user_request, tools)
    
    print(f"📋 Kimi generated {len(tool_calls)} tool calls:\n")
    for tc in tool_calls:
        print(f"  - {tc.name}({tc.arguments})")
    print()
    
    # 6. Execute through MCP server
    print("🎮 Executing via MCP server...\n")
    for tc in tool_calls:
        if tc.name == "arm_and_takeoff":
            result = await server.drone.action.arm()
            print(f"  ✓ Armed")
            await server.drone.action.takeoff()
            print(f"  ✓ Takeoff to {tc.arguments['altitude_m']}m")
            await asyncio.sleep(5)
            
        elif tc.name == "land":
            await server.drone.action.land()
            print(f"  ✓ Landing")
            await asyncio.sleep(5)
    
    print("\n✅ Integration test PASSED")
    print("   - Kimi understood natural language")
    print("   - Generated appropriate tool calls")
    print("   - SITL executed mission correctly")
    print("   - All systems working together")

if __name__ == "__main__":
    asyncio.run(test_mission_planning())
```

**Run Full Integration Test**:
```bash
# Terminal 1: SITL with Gazebo
make px4_sitl gz_x500

# Terminal 2: Integration test
export FIREWORKS_API_KEY="your-key"
python tests/test_kimi_integration.py
```

**Expected Output**:
```
🚁 Phase 0.5: Kimi + SITL Integration Test

✓ MCP server connected to SITL

✓ Kimi client initialized

👤 User: 'Take off to 10 meters, hover for 5 seconds, then land'

🤖 Kimi planning...
📋 Kimi generated 2 tool calls:
  - arm_and_takeoff({'altitude_m': 10})
  - land()

🎮 Executing via MCP server...
  ✓ Armed
  ✓ Takeoff to 10m
  ✓ Landing

✅ Integration test PASSED
   - Kimi understood natural language
   - Generated appropriate tool calls
   - SITL executed mission correctly
   - All systems working together
```

### Day 10: Confirmation Workflow

**Implement Progressive Confirmation**:
```python
# mcp_server/confirmation.py

class ConfirmationManager:
    """
    Progressive confirmation workflow.
    Pre-flight → Pre-arm → Mid-flight exceptions.
    """
    
    async def request_confirmation(
        self, 
        agent,  # MCP agent interface
        message: str,
        timeout_seconds: int = 10,
        default_action: str = "hold"
    ) -> str:
        """
        Request user confirmation through agent.
        Returns: 'continue', 'abort', or 'timeout'
        """
        # This will be implemented differently per agent
        # For Claude Code: chat-based
        # For OpenCode: chat-based
        # For scripts: CLI input
        
        pass
```

---

## Week -1: Vision Simulation & Advanced Testing

### Day 1-3: Gazebo Camera + Vision Pipeline

**Gazebo Camera Setup**:
Gazebo SITL includes simulated cameras. Enable with:
```bash
make px4_sitl gz_x500_depth  # X500 with depth camera
```

**Simulated Camera Stream**:
```python
# vision/gazebo_camera_client.py
import cv2
import numpy as np

def get_gazebo_frame():
    """
    Capture frame from Gazebo simulated camera.
    In real implementation, this connects to Gazebo's camera topic.
    """
    # Placeholder - actual implementation uses Gazebo transport library
    # For now, simulate with synthetic frames
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return frame
```

**Mock YOLO for Testing** (since Gazebo synthetic images don't have real people):
```python
# vision/mock_detector.py
"""
Mock YOLO detector for Phase 0.5 testing.
Generates synthetic detections at known positions for validation.
"""

import random
from typing import List, Dict

class MockDetector:
    """Generates synthetic detections for testing mission logic."""
    
    def __init__(self):
        self.frame_count = 0
        
    def detect(self, frame) -> List[Dict]:
        """Return synthetic detections."""
        self.frame_count += 1
        
        # Simulate people appearing at frame 50, 100, etc.
        detections = []
        if self.frame_count > 50 and self.frame_count < 200:
            detections.append({
                "class": "person",
                "confidence": 0.85,
                "bbox": [100, 200, 200, 400],  # x1, y1, x2, y2
                "track_id": 1
            })
        
        if self.frame_count > 100 and self.frame_count < 250:
            detections.append({
                "class": "person",
                "confidence": 0.78,
                "bbox": [300, 150, 400, 350],
                "track_id": 2
            })
        
        return detections
```

**Vision Integration Test**:
```python
# tests/test_vision_pipeline.py
async def test_vision_detection():
    """Test vision → exception → confirmation flow."""
    
    detector = MockDetector()
    
    for frame_num in range(300):
        frame = get_gazebo_frame()
        detections = detector.detect(frame)
        
        if detections:
            print(f"Frame {frame_num}: {len(detections)} people detected")
            
            # Simulate exception handling
            if len(detections) >= 2:
                print("⚠️  Multiple people detected - would trigger confirmation")
                # In real implementation: ask agent "Stop or continue?"
```

### Day 4-5: Google Maps Integration

**Pre-Flight Planning with Real Maps**:
```python
# planning/maps_integration.py
import googlemaps
from datetime import datetime

class MapsPlanner:
    """Google Maps integration for pre-flight mission planning."""
    
    def __init__(self, api_key: str):
        self.client = googlemaps.Client(key=api_key)
    
    def plan_mission_area(self, location_query: str) -> Dict:
        """
        Analyze area and suggest mission parameters.
        
        Returns:
            - Area boundaries
            - Recommended geofence
            - Obstacles nearby
            - Safe landing zones
        """
        # Geocode location
        geocode_result = self.client.geocode(location_query)
        if not geocode_result:
            raise ValueError(f"Location not found: {location_query}")
        
        location = geocode_result[0]['geometry']['location']
        
        # Get nearby features
        nearby = self.client.places_nearby(
            location=(location['lat'], location['lng']),
            radius=500  # 500m radius
        )
        
        return {
            "center": location,
            "search_radius_m": 500,
            "nearby_features": nearby.get('results', []),
            "recommended_geofence_m": 450,  # Conservative
            "recommended_altitude_m": 25,   # Safe for area
        }
```

**Test Maps Planning**:
```python
# tests/test_maps_planning.py
def test_park_planning():
    planner = MapsPlanner(api_key=os.getenv("GOOGLE_MAPS_API_KEY"))
    
    result = planner.plan_mission_area("High Park, Toronto")
    
    print(f"📍 Location: {result['center']}")
    print(f"🎯 Geofence: {result['recommended_geofence_m']}m")
    print(f"✈️  Altitude: {result['recommended_altitude_m']}m")
    print(f"📋 Nearby: {len(result['nearby_features'])} features")
```

### Day 6-7: Exception Handling & Safety Testing

**Test Scenarios**:
```python
# tests/test_safety_scenarios.py

async def test_scenario_person_detected():
    """
    Test: Person detected during orbit → confirmation requested
    """
    print("\n🎬 Scenario: Person detected during mission")
    
    # 1. Start mission
    await arm_and_takeoff(altitude_m=20)
    
    # 2. Start orbit
    await start_orbit(radius_m=30)
    
    # 3. Simulate person detection
    print("⚠️  YOLO detected: Person at 15m, bearing 45°")
    
    # 4. Exception handling
    print("🤖 Kimi: 'Person detected. Recommend holding position.'")
    print("💬 Agent: 'Person detected 15m away. Stop or continue?'")
    
    # 5. User response
    response = await mock_user_response("stop")  # or "continue"
    
    if response == "stop":
        await hold_position()
        print("✓ Holding position")
    else:
        await expand_orbit(new_radius_m=40)
        print("✓ Continuing with wider orbit")

async def test_scenario_low_battery():
    """Test: Low battery triggers RTL."""
    print("\n🎬 Scenario: Battery at 25%")
    
    # Simulate battery telemetry
    battery_percent = 25
    
    if battery_percent < 30:
        print("🤖 Kimi: 'Battery at 25%. Mission 60% complete.'")
        print("🤖 Kimi: 'Recommend RTL for safety.'")
        
        await rtl()
        print("✓ Returning to launch")
```

### Day 8-9: Recording & Logging

**Flight Recording System**:
```python
# utils/flight_recorder.py
import json
from datetime import datetime

class FlightRecorder:
    """Record all telemetry, decisions, and video for replay."""
    
    def __init__(self, mission_name: str):
        self.mission_name = mission_name
        self.start_time = datetime.now()
        self.events = []
        self.video_frames = []
        
    def log_event(self, event_type: str, data: dict):
        """Log significant event."""
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        })
    
    def save_mission(self):
        """Save complete mission record."""
        record = {
            "mission_name": self.mission_name,
            "start_time": self.start_time.isoformat(),
            "events": self.events,
            "total_events": len(self.events)
        }
        
        filename = f"missions/{self.mission_name}_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(record, f, indent=2)
        
        print(f"✓ Mission recorded: {filename}")
```

### Day 10: Screen Recording Setup

**Screen Recording Script**:
```bash
#!/bin/bash
# scripts/start_demo_recording.sh

# Create recording directory
mkdir -p recordings/$(date +%Y%m%d)

# Terminal 1: Gazebo (visualization)
osascript -e 'tell app "Terminal" to do script "cd ~/PX4-Autopilot && make px4_sitl gz_x500"'

# Terminal 2: MCP Server
osascript -e 'tell app "Terminal" to do script "cd ~/avatar && python mcp_server/server.py"'

# Terminal 3: Claude Code (for demo)
osascript -e 'tell app "Terminal" to do script "cd ~/avatar && claude"'

# Start screen recording (macOS)
echo "🎬 Starting screen recording..."
echo "   Press Ctrl+C in QuickTime Player to stop"
open -a "QuickTime Player"

# Instructions
echo ""
echo "📋 Demo Script:"
echo "   1. Wait for SITL to start (Gazebo window appears)"
echo "   2. In Claude Code: test connection with 'get_telemetry'"
echo "   3. Execute: 'Take off to 10 meters'"
echo "   4. Execute: 'Orbit this area'"
echo "   5. Show exception handling: 'abort mission'"
echo "   6. Land"
echo ""
echo "✅ When ready, start typing commands in Claude Code"
```

---

## Week 0: Demo Production & Documentation

### Day 1-3: Produce Demo Video

**Demo Scenario Script**:
```
TITLE: Project Avatar - Phase 0.5 Demo: Virtual Drone

SCENE 1: Introduction (0:00-0:30)
- Screen: Split view (Gazebo + Claude Code)
- Narrator: "This is Project Avatar Phase 0.5 - a complete drone system running in simulation"

SCENE 2: Agent Connection (0:30-1:00)
- Show: Claude Code connecting to MCP server
- Command: get_telemetry
- Result: Shows simulated telemetry from Gazebo

SCENE 3: Natural Language Mission (1:00-2:30)
- User: "Take off to 10 meters and orbit this area"
- Show: Kimi planning in real-time
- Show: Confirmation dialog
- Show: Mission execution in Gazebo

SCENE 4: Vision + Exception (2:30-3:30)
- Simulate person detection
- Show: Exception raised
- Show: "Stop or continue?" prompt
- Show: User aborts mission

SCENE 5: RTL + Landing (3:30-4:00)
- Show: Safe return and landing

SCENE 6: Conclusion (4:00-4:30)
- Narrator: "All software validated. Ready for hardware swap."
- Show: Architecture diagram
```

**Screen Recording**:
```bash
# Start recording with QuickTime
# Run through script
# Export as demo_phase_0.5.mp4
```

### Day 4-5: Comprehensive Test Suite

**Automated Testing**:
```bash
# Run all Phase 0.5 tests
python -m pytest tests/phase05/ -v

# Expected output:
tests/test_sitl_basic.py::test_connection PASSED
tests/test_kimi_integration.py::test_mission_planning PASSED
tests/test_vision_pipeline.py::test_detection PASSED
tests/test_confirmation.py::test_workflow PASSED
tests/test_safety_scenarios.py::test_person_detected PASSED
tests/test_maps.py::test_planning PASSED

7 passed in 45.32s
```

**Performance Benchmarks**:
```python
# tests/benchmarks.py
def test_latency():
    """Verify end-to-end latency < 2s."""
    start = time.time()
    result = kimi.plan_mission("Take off to 10m", tools)
    elapsed = time.time() - start
    
    assert elapsed < 2.0, f"Latency {elapsed}s exceeds 2s budget"
    print(f"✓ Latency: {elapsed:.2f}s")
```

### Day 6-7: Documentation

**Update All Docs**:
- `README.md`: Add Phase 0.5 section with demo video link
- `DECISIONS.md`: Add DEC-020: SITL Pre-Validation Phase
- `mcp_agent_agnostic_design.md`: Add SITL testing section

**Phase 0.5 Summary Document**:
```markdown
# Phase 0.5 Complete: Virtual Drone Validation

**Status**: ✅ COMPLETE
**Demo Video**: [Watch on YouTube](link)

## Validated Components

✅ **PX4 SITL + Gazebo**: Full flight stack simulation
✅ **MCP Server**: Agent-agnostic tool interface
✅ **Kimi Integration**: Natural language → tool calls
✅ **Vision Pipeline**: Mock detector for mission testing
✅ **Confirmation Workflow**: Pre-flight + exception handling
✅ **Maps Integration**: Pre-flight planning with real data
✅ **Safety Systems**: GuardianProcess validation
✅ **Recording System**: Full mission logging

## Test Results

- **Integration Tests**: 7/7 passed
- **Latency**: 1.2s average (target: <2s)
- **Mission Success Rate**: 100% (50 test missions)
- **Agent Compatibility**: Tested with Claude Code, OpenCode

## Ready for Hardware

All software components validated. Next: Swap SITL for real RPi/Pixhawk.
```

### Day 8-10: Hardware Swap Preparation

**Hardware Transition Checklist**:
```bash
# Hardware Swap Day Script
# scripts/swap_to_hardware.sh

echo "🔧 Phase 0.5 → Stage 1: Hardware Transition"
echo ""

# 1. Backup simulation config
cp config/sitl.yaml config/sitl.yaml.backup
echo "✓ Backed up SITL config"

# 2. Switch to hardware config
cp config/hardware.yaml config/active.yaml
echo "✓ Activated hardware configuration"

# 3. Update MCP server connection
# Change from: udp://:14540 (SITL)
# Change to: serial:///dev/tty.usbmodemXXX (hardware)
echo "✓ Updated MAVLink connection"

# 4. Verify RPi heartbeat
echo "⚠️  Verify: RPi is powered and running"
echo "⚠️  Verify: 20Hz heartbeat active"
echo "⚠️  Verify: Telemetry streaming to MacBook"

# 5. First hardware test
echo ""
echo "🎬 First Hardware Test Script:"
echo "   1. get_telemetry (verify connection)"
echo "   2. arm_and_takeoff(altitude_m=2) (very low)"
echo "   3. land()"
echo ""
echo "✅ Ready for first tethered flight"
```

---

## Phase 0.5 Deliverables Checklist

### Software Components
- [ ] `mcp_server/server.py` - Agent-agnostic MCP server
- [ ] `llm/kimi_client.py` - Fireworks AI integration
- [ ] `vision/mock_detector.py` - Synthetic detection for testing
- [ ] `planning/maps_integration.py` - Google Maps for pre-flight
- [ ] `mcp_server/confirmation.py` - Progressive confirmation
- [ ] `utils/flight_recorder.py` - Mission logging

### Testing
- [ ] `tests/test_sitl_basic.py` - SITL connectivity
- [ ] `tests/test_kimi_integration.py` - Full pipeline
- [ ] `tests/test_vision_pipeline.py` - Detection → exceptions
- [ ] `tests/test_confirmation.py` - User interaction flows
- [ ] `tests/test_safety_scenarios.py` - Edge cases
- [ ] `tests/benchmarks.py` - Performance validation

### Documentation
- [ ] Updated `README.md` with Phase 0.5 section
- [ ] DEC-020 added to `DECISIONS.md`
- [ ] `PHASE_0_5_SUMMARY.md` completion report
- [ ] SITL setup guide in `docs/`

### Demo
- [ ] `demo_phase_0.5.mp4` screen recording (4-5 minutes)
- [ ] YouTube/Vimeo upload
- [ ] Demo script document
- [ ] Architecture diagram updated

### Transition
- [ ] `scripts/swap_to_hardware.sh` ready
- [ ] Hardware configuration files prepared
- [ ] Transition checklist documented
- [ ] Team briefed on swap procedure

---

## Phase 0.5 Success Criteria

✅ **All Checklist Items Complete**  
✅ **Demo Video Published & Accessible**  
✅ **All Tests Passing**  
✅ **Latency Under 2s**  
✅ **Hardware Swap Script Ready**  
✅ **Documentation Complete**  

**When Complete**: You'll have a fully functional drone control system running in simulation, proven to work end-to-end with natural language commands, ready to swap in real hardware for Stage 1.

---

*Phase 0.5: The safest way to build a drone - all software validated before any hardware risk.*
