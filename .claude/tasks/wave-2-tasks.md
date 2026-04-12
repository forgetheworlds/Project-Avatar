# Wave 2 Tasks: Basic Validation

**Wave**: 2
**Dependencies**: Wave 1 complete
**Estimated Duration**: 30 minutes with parallelization

---

## A-005: Start SITL and Verify Gazebo

```yaml
id: A-005
title: Start SITL and verify Gazebo visualization
track: Environment
wave: 2
blockedBy: [A-004]
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Start the SITL simulation and verify that Gazebo launches correctly.

acceptance_criteria:
  - SITL starts without errors
  - Gazebo window appears
  - X500 drone model visible in simulation

implementation_steps:
  - Open Terminal 1
  - cd PX4-Autopilot
  - make px4_sitl gz_x500
  - Verify Gazebo launches and shows drone

commands:
  - cd PX4-Autopilot && make px4_sitl gz_x500
```

---

## A-006: Test MAVSDK Connection to SITL

```yaml
id: A-006
title: Test MAVSDK connection to SITL (udp://:14540)
track: Environment
wave: 2
blockedBy: [A-005]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Test the MAVSDK Python connection to the running SITL instance.

acceptance_criteria:
  - Connection established successfully
  - Telemetry received from SITL
  - GPS health check passes

implementation_steps:
  - With SITL running in Terminal 1
  - Open Terminal 2
  - Run Python test script
  - Verify connection and telemetry

test_script: |
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
```

---

## C-001: Create Basic SITL Test Script

```yaml
id: C-001
title: Create tests/test_sitl_basic.py
track: FlightTest
wave: 2
blockedBy: [B-003]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the basic SITL flight test script that tests arm, takeoff, and land.

acceptance_criteria:
  - Test file created
  - Contains arm/takeoff/land sequence
  - Proper error handling

implementation_steps:
  - Create tests/test_sitl_basic.py
  - Implement test_basic_flight() function
  - Add proper async handling

test_functions:
  - test_connection()
  - test_arm()
  - test_takeoff()
  - test_land()
  - test_basic_flight()
```

---

## C-002: Run Basic Flight Test in SITL

```yaml
id: C-002
title: Run basic arm/takeoff/land test in SITL
track: FlightTest
wave: 2
blockedBy: [A-006, C-001]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Execute the basic flight test and verify drone behavior in Gazebo.

acceptance_criteria:
  - Drone arms successfully
  - Drone takes off to target altitude
  - Drone lands successfully
  - All steps visible in Gazebo

implementation_steps:
  - Ensure SITL running in Terminal 1
  - Run test in Terminal 2
  - Observe drone in Gazebo
  - Verify log output

commands:
  - python tests/test_sitl_basic.py
```

---

## D-001: Create MCP Server Directory

```yaml
id: D-001
title: Create mcp_server/ directory and files
track: MCPServer
wave: 2
blockedBy: [B-001]
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Create the MCP server directory structure and initial files.

acceptance_criteria:
  - mcp_server/ directory exists
  - Server file created
  - __init__.py created

implementation_steps:
  - Create mcp_server/server.py
  - Create mcp_server/__init__.py
  - Create mcp_server/tools/

structure:
  mcp_server/
  ├── __init__.py
  ├── server.py
  └── tools/
      └── __init__.py
```

---

## D-002: Implement DroneMCPServer Class Skeleton

```yaml
id: D-002
title: Implement DroneMCPServer class skeleton (completed as T18)
track: MCPServer
wave: 2
blockedBy: [D-001]
status: COMPLETED
completed_date: 2026-04-12
estimated_minutes: 20
assignee: Claude

description: |
  Created the AvatarMCPServer class with full server wiring and component integration.
  This was completed as task T18 with comprehensive integration tests.

acceptance_criteria:
  - [X] AvatarMCPServer class created with all components wired
  - [X] ConnectionManager singleton integration
  - [X] TelemetryCache with 100ms refresh
  - [X] HeartbeatService with 20Hz emission
  - [X] FlightStateMachine for state tracking
  - [X] AsyncGuardian for safety monitoring
  - [X] 34 integration tests passing

implementation:
  - avatar/mcp_server/server.py: Main server implementation
  - tests/mcp_server/test_server_integration.py: 34 integration tests
  - avatar/mcp_server/__init__.py: Export server components
  - avatar/mcp_server/compat.py: Legacy compatibility
  - avatar/mcp_server/tools/flight_tools.py: Tool updates

notes: |
  Enhanced from basic skeleton to full Architecture 2.0 implementation.
  Includes lifecycle management, graceful shutdown, singleton pattern enforcement.
```

---

## S-001: Create Subagents Directory

```yaml
id: S-001
title: Create subagents/ directory structure
track: Subagents
wave: 2
blockedBy: [B-001]
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Create the subagents directory for drone-specific Claude Code subagents.

acceptance_criteria:
  - subagents/ directory exists
  - Subdirectories for each agent type

implementation_steps:
  - mkdir -p .claude/agents/drone/
  - Create placeholder files

structure:
  .claude/agents/drone/
  ├── mission-planner.md
  ├── safety-guardian.md
  ├── vision.md
  ├── logger.md
  └── preflight.md
```

---

## S-002: Create Mission Planner Subagent

```yaml
id: S-002
title: Create Mission Planner subagent config
track: Subagents
wave: 2
blockedBy: [S-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the Mission Planner subagent configuration for mission planning tasks.

acceptance_criteria:
  - mission-planner.md created
  - Contains proper agent frontmatter
  - Defines mission planning capabilities

agent_config:
  name: mission-planner
  description: Plans and optimizes drone missions based on natural language requests
  tools:
    - plan_mission
    - get_telemetry
    - goto_gps
  model: inherit
```

---

## S-003: Create Safety Guardian Subagent

```yaml
id: S-003
title: Create Safety Guardian subagent config
track: Subagents
wave: 2
blockedBy: [S-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the Safety Guardian subagent configuration for safety monitoring.

acceptance_criteria:
  - safety-guardian.md created
  - Contains proper agent frontmatter
  - Defines safety monitoring capabilities

agent_config:
  name: safety-guardian
  description: Monitors drone safety parameters and enforces hard limits
  tools:
    - get_telemetry
    - abort_mission
    - rtl
  model: inherit
  triggers:
    - altitude_exceeded
    - geofence_violation
    - low_battery
```

---

## S-004: Create Vision Subagent

```yaml
id: S-004
title: Create Vision subagent config
track: Subagents
wave: 2
blockedBy: [S-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the Vision subagent configuration for visual detection handling.

acceptance_criteria:
  - vision.md created
  - Contains proper agent frontmatter
  - Defines vision processing capabilities

agent_config:
  name: vision
  description: Processes camera frames and manages detection events
  tools:
    - capture_frame
    - get_detected_objects
  model: inherit
  triggers:
    - person_detected
    - object_detected
```

---

## S-005: Create Logger Subagent

```yaml
id: S-005
title: Create Logger subagent config
track: Subagents
wave: 2
blockedBy: [S-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the Logger subagent configuration for mission recording.

acceptance_criteria:
  - logger.md created
  - Contains proper agent frontmatter
  - Defines logging capabilities

agent_config:
  name: logger
  description: Records mission events and maintains flight logs
  tools:
    - get_telemetry
    - get_mission_status
  model: inherit
  behavior: always_on
```

---

## S-006: Create Preflight Subagent

```yaml
id: S-006
title: Create Preflight subagent config
track: Subagents
wave: 2
blockedBy: [S-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the Preflight subagent configuration for pre-flight checks.

acceptance_criteria:
  - preflight.md created
  - Contains proper agent frontmatter
  - Defines preflight check capabilities

agent_config:
  name: preflight
  description: Performs pre-flight checks and validates mission readiness
  tools:
    - get_telemetry
    - get_battery_status
  model: inherit
  checklist:
    - GPS lock
    - Battery level
    - Sensor calibration
    - Geofence clear
```

---

## Wave 2 Summary

**Tasks**: 12
**Parallel Groups**: 3

**Execution Order**:
1. Start A-005, D-001, S-001 simultaneously
2. After A-005: Start A-006
3. After D-001: Start D-002
4. After S-001: Start S-002, S-003, S-004, S-005, S-006 simultaneously
5. After B-003: Start C-001
6. After A-006 and C-001: Start C-002

**Next Wave**: Wave 3 starts when all Wave 2 tasks complete
