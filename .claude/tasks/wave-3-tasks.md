# Wave 3 Tasks: Integration

**Wave**: 3
**Dependencies**: Wave 2 complete
**Estimated Duration**: 60 minutes with parallelization

---

## D-003: Implement arm_and_takeoff Tool

```yaml
id: D-003
title: Implement arm_and_takeoff tool
track: MCPServer
wave: 3
blockedBy: [D-002]
status: COMPLETED
estimated_minutes: 15
assignee: null

description: |
  Implement the arm_and_takeoff MCP tool for drone arming and takeoff.

acceptance_criteria:
  - Tool function implemented
  - JSON schema defined
  - Safety preconditions checked
  - Error handling included

tool_schema:
  name: arm_and_takeoff
  parameters:
    altitude_m:
      type: number
      minimum: 2
      maximum: 120
  preconditions:
    - drone_disarmed
    - gps_lock
    - battery_gt_20_percent

implementation: |
  @server.tool()
  async def arm_and_takeoff(altitude_m: float) -> str:
      await drone.action.arm()
      await drone.action.takeoff()
      return f"Armed and taking off to {altitude_m}m"
```

---

## D-004: Implement goto_gps Tool

```yaml
id: D-004
title: Implement goto_gps tool
track: MCPServer
wave: 3
blockedBy: [D-002]
status: COMPLETED
estimated_minutes: 20
assignee: null

description: |
  Implement the goto_gps MCP tool for waypoint navigation.

acceptance_criteria:
  - Tool function implemented
  - JSON schema defined
  - Geofence validation included
  - Speed parameter supported

tool_schema:
  name: goto_gps
  parameters:
    lat:
      type: number
    lon:
      type: number
    alt_m:
      type: number
    speed_ms:
      type: number
      default: 5.0
  preconditions:
    - drone_armed
    - within_geofence
```

---

## D-005: Implement get_telemetry Tool

```yaml
id: D-005
title: Implement get_telemetry tool
track: MCPServer
wave: 3
blockedBy: [D-002]
status: COMPLETED
estimated_minutes: 10
assignee: null

description: |
  Implement the get_telemetry MCP tool for reading drone status.

acceptance_criteria:
  - Tool function implemented
  - Returns position, altitude, battery
  - Read-only operation

tool_schema:
  name: get_telemetry
  parameters: {}
  returns:
    latitude_deg: float
    longitude_deg: float
    relative_altitude_m: float
    battery_percent: float
```

---

## D-006: Implement land Tool

```yaml
id: D-006
title: Implement land tool
track: MCPServer
wave: 3
blockedBy: [D-002]
status: COMPLETED
estimated_minutes: 10
assignee: null

description: |
  Implement the land MCP tool for landing the drone.

acceptance_criteria:
  - Tool function implemented
  - Landing command sent to PX4
  - Status feedback returned

tool_schema:
  name: land
  parameters: {}
  preconditions:
    - drone_in_air
```

---

## D-007: Implement abort_mission/RTL Tool

```yaml
id: D-007
title: Implement abort_mission/RTL tool
track: MCPServer
wave: 3
blockedBy: [D-002]
status: COMPLETED
estimated_minutes: 15
assignee: null

description: |
  Implement the abort_mission and RTL (Return to Launch) tools for emergency situations.

acceptance_criteria:
  - abort_mission tool implemented
  - RTL command triggers return to home
  - Reason parameter logged

tool_schema:
  name: abort_mission
  parameters:
    reason:
      type: string
  action: rtl
```

---

## E-001: Test MCP Server with Claude Code

```yaml
id: E-001
title: Test MCP server with Claude Code connection
track: AgentTest
wave: 3
blockedBy: [D-003, D-004, D-005, D-006, D-007, P-004]
status: COMPLETED
estimated_minutes: 20
assignee: null

description: |
  Test the MCP server connection with Claude Code.

acceptance_criteria:
  - Claude Code connects to MCP server
  - Tools appear in Claude Code interface
  - Basic tool calls succeed

implementation_steps:
  - Start SITL in Terminal 1
  - Start MCP server in Terminal 2
  - Test with Claude Code: claude mcp list
  - Verify drone-control server appears

commands:
  - claude mcp list
  - claude mcp test drone-control
```

---

## E-002: Verify All Tools in Claude Code

```yaml
id: E-002
title: Verify all tools appear in Claude Code
track: AgentTest
wave: 3
blockedBy: [E-001]
status: COMPLETED
estimated_minutes: 10
assignee: null

description: |
  Verify that all implemented tools are visible and callable in Claude Code.

acceptance_criteria:
  - All 7+ tools listed
  - Each tool callable
  - Tool descriptions visible

tools_to_verify:
  - arm_and_takeoff
  - goto_gps
  - get_telemetry
  - land
  - abort_mission
  - capture_frame (if implemented)
  - get_mission_status (if implemented)
```

---

## G-001: Create Vision Directory

```yaml
id: G-001
title: Create vision/ directory structure
track: Vision
wave: 3
blockedBy: [B-001]
status: COMPLETED
estimated_minutes: 5
assignee: null

description: |
  Create the vision module directory structure.

acceptance_criteria:
  - vision/ directory exists
  - Initial files created

structure:
  vision/
  ├── __init__.py
  ├── gazebo_camera_client.py
  └── mock_detector.py
```

---

## G-002: Create Gazebo Camera Client

```yaml
id: G-002
title: Create gazebo_camera_client.py
track: Vision
wave: 3
blockedBy: [G-001]
status: COMPLETED
estimated_minutes: 20
assignee: null

description: |
  Create the Gazebo camera client for capturing frames from the simulated camera.

acceptance_criteria:
  - Camera client implemented
  - Frame capture function works
  - Integration with Gazebo simulated camera

implementation: |
  def get_gazebo_frame():
      """Capture frame from Gazebo simulated camera."""
      # Connect to Gazebo camera topic
      # Capture frame
      # Return as numpy array
      pass
```

---

## G-003: Create Mock Detector

```yaml
id: G-003
title: Create mock_detector.py for synthetic detections
track: Vision
wave: 3
blockedBy: [G-001]
status: COMPLETED
estimated_minutes: 25
assignee: null

description: |
  Create a mock YOLO detector for testing mission logic with synthetic detections.

acceptance_criteria:
  - MockDetector class implemented
  - Generates synthetic person detections
  - Configurable detection timing

implementation: |
  class MockDetector:
      def __init__(self):
          self.frame_count = 0
          
      def detect(self, frame) -> List[Dict]:
          """Return synthetic detections."""
          # Simulate people at known frame intervals
          # Return detection dicts with bbox, class, confidence
          pass
```

---

## G-004: Test Vision Pipeline

```yaml
id: G-004
title: Test vision pipeline with mock data
track: Vision
wave: 3
blockedBy: [G-002, G-003]
status: COMPLETED
estimated_minutes: 15
assignee: null

description: |
  Test the complete vision pipeline with mock data.

acceptance_criteria:
  - Frame capture works
  - Mock detections generated
  - Detection events logged

test_scenario:
  - Capture 300 frames
  - Verify mock detections appear at expected frames
  - Log detection events
```

---

## Q-001: Create /fly Skill Definition

```yaml
id: Q-001
title: Create /fly skill definition
track: Skills
wave: 3
blockedBy: [D-003, D-004, D-005, D-006, D-007]
status: COMPLETED
estimated_minutes: 20
assignee: null

description: |
  Create the /fly skill for executing drone flight commands.

acceptance_criteria:
  - Skill file created
  - Proper frontmatter included
  - Flight command templates included

skill_config:
  name: fly
  description: Execute drone flight commands with natural language
  triggers:
    - "fly to"
    - "take off"
    - "land the drone"
  tools:
    - arm_and_takeoff
    - goto_gps
    - land
```

---

## Q-002: Create /preflight Skill Definition

```yaml
id: Q-002
title: Create /preflight skill definition
track: Skills
wave: 3
blockedBy: [S-006]
status: COMPLETED
estimated_minutes: 15
assignee: null

description: |
  Create the /preflight skill for running pre-flight checks.

acceptance_criteria:
  - Skill file created
  - Pre-flight checklist included
  - Safety validation steps

skill_config:
  name: preflight
  description: Run pre-flight checks before mission execution
  checklist:
    - GPS lock verification
    - Battery level check
    - Sensor calibration status
    - Geofence validation
```

---

## Q-003: Create /mission Skill Definition

```yaml
id: Q-003
title: Create /mission skill definition
track: Skills
wave: 3
blockedBy: [D-004]
status: COMPLETED
estimated_minutes: 20
assignee: null

description: |
  Create the /mission skill for planning and executing complex missions.

acceptance_criteria:
  - Skill file created
  - Mission planning templates included
  - Confirmation workflow integrated

skill_config:
  name: mission
  description: Plan and execute complex drone missions
  templates:
    - orbit
    - waypoint_survey
    - follow_me
  confirmation_required: true
```

---

## Q-004: Create /abort Skill Definition

```yaml
id: Q-004
title: Create /abort skill definition
track: Skills
wave: 3
blockedBy: [D-007]
status: COMPLETED
estimated_minutes: 15
assignee: null

description: |
  Create the /abort skill for emergency mission termination.

acceptance_criteria:
  - Skill file created
  - Abort procedures defined
  - RTL trigger included

skill_config:
  name: abort
  description: Emergency abort - return to launch immediately
  action: rtl
  priority: critical
```

---

## Q-005: Create /drone-status Skill Definition

```yaml
id: Q-005
title: Create /drone-status skill definition
track: Skills
wave: 3
blockedBy: [D-005]
status: COMPLETED
estimated_minutes: 10
assignee: null

description: |
  Create the /drone-status skill for checking drone status.

acceptance_criteria:
  - Skill file created
  - Status display templates included
  - Telemetry formatting defined

skill_config:
  name: drone-status
  description: Get current drone status and telemetry
  display:
    - position
    - altitude
    - battery
    - mission_state
```

---

## Wave 3 Summary

**Tasks**: 17
**Parallel Groups**: 6

**Execution Order**:
1. Start D-003, D-004, D-005, D-006, D-007 simultaneously (all MCP tools)
2. Start G-001 (vision directory)
3. After D-002: All D-003 through D-007 can run in parallel
4. After G-001: Start G-002, G-003 simultaneously
5. After D-tools complete and P-004: Start E-001
6. After E-001: Start E-002
7. After G-002, G-003: Start G-004
8. After D-tools complete: Start Q-001 through Q-005 simultaneously

**Next Wave**: Wave 4 starts when all Wave 3 tasks complete
