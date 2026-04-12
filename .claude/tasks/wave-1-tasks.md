# Wave 1 Tasks: Foundation

**Wave**: 1
**Dependencies**: None (can start immediately)
**Estimated Duration**: 45 minutes with parallelization

---

## A-001: Clone PX4-Autopilot Repository

```yaml
id: A-001
title: Clone PX4-Autopilot repository
track: Environment
wave: 1
blockedBy: []
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Clone the PX4-Autopilot repository from GitHub to the local machine.
  This is the first step in setting up the SITL simulation environment.

acceptance_criteria:
  - Repository cloned successfully
  - Directory exists at expected location

implementation_steps:
  - Run: git clone https://github.com/PX4/PX4-Autopilot.git
  - Verify clone completed without errors
  - Note the clone location for subsequent tasks

commands:
  - git clone https://github.com/PX4/PX4-Autopilot.git
```

---

## A-002: Checkout PX4 v1.15.0 Stable Release

```yaml
id: A-002
title: Checkout PX4 v1.15.0 stable release
track: Environment
wave: 1
blockedBy: [A-001]
status: NOT_STARTED
estimated_minutes: 2
assignee: null

description: |
  Checkout the stable v1.15.0 release of PX4 for reliable SITL operation.

acceptance_criteria:
  - Correct version checked out
  - Git shows v1.15.0 tag

implementation_steps:
  - cd PX4-Autopilot
  - git checkout v1.15.0
  - git describe --tags

commands:
  - cd PX4-Autopilot && git checkout v1.15.0
```

---

## A-003: Run macOS Setup Script

```yaml
id: A-003
title: Run macOS setup script
track: Environment
wave: 1
blockedBy: [A-002]
status: NOT_STARTED
estimated_minutes: 30
assignee: null

description: |
  Run the macOS setup script to install all PX4 dependencies.
  This is a long-running task that should be monitored.

acceptance_criteria:
  - Setup script completes without errors
  - All dependencies installed

implementation_steps:
  - cd PX4-Autopilot
  - bash ./Tools/setup/macos.sh
  - Monitor output for any errors

commands:
  - cd PX4-Autopilot && bash ./Tools/setup/macos.sh
```

---

## A-004: Build PX4 SITL with Gazebo

```yaml
id: A-004
title: Build PX4 SITL with Gazebo (gz_x500)
track: Environment
wave: 1
blockedBy: [A-003]
status: NOT_STARTED
estimated_minutes: 20
assignee: null

description: |
  Build the PX4 SITL target with Gazebo simulation for the X500 quadrotor model.

acceptance_criteria:
  - Build completes without errors
  - SITL executable created

implementation_steps:
  - cd PX4-Autopilot
  - make px4_sitl gz_x500
  - Verify build succeeded

commands:
  - cd PX4-Autopilot && make px4_sitl gz_x500
```

---

## B-001: Create Avatar Directory Structure

```yaml
id: B-001
title: Create avatar/ directory structure
track: Structure
wave: 1
blockedBy: []
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Create the main project directory structure for Project Avatar.

acceptance_criteria:
  - All directories created
  - Structure matches specification

implementation_steps:
  - mkdir -p avatar/{mav,vision,llm,mcp_server,planning,tests,scripts,config}
  - Verify directory structure

structure:
  avatar/
  ├── mav/
  ├── vision/
  ├── llm/
  ├── mcp_server/
  ├── planning/
  ├── tests/
  ├── scripts/
  └── config/

commands:
  - mkdir -p avatar/{mav,vision,llm,mcp_server,planning,tests,scripts,config}
```

---

## B-002: Initialize Python Virtual Environment

```yaml
id: B-002
title: Initialize Python virtual environment
track: Structure
wave: 1
blockedBy: [B-001]
status: NOT_STARTED
estimated_minutes: 3
assignee: null

description: |
  Create a Python virtual environment for the project.

acceptance_criteria:
  - Virtual environment created
  - Activation script works

implementation_steps:
  - cd avatar
  - python3 -m venv venv
  - Test activation: source venv/bin/activate

commands:
  - cd avatar && python3 -m venv venv
```

---

## B-003: Install Core Dependencies

```yaml
id: B-003
title: Install core dependencies (mavsdk, opencv, etc.)
track: Structure
wave: 1
blockedBy: [B-002]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Install all required Python packages for the project.

acceptance_criteria:
  - All packages installed successfully
  - Import tests pass

implementation_steps:
  - source venv/bin/activate
  - pip install mavsdk ultralytics opencv-python openai mcp asyncio
  - Test imports

dependencies:
  - mavsdk
  - ultralytics
  - opencv-python
  - openai
  - mcp
  - asyncio

commands:
  - pip install mavsdk ultralytics opencv-python openai mcp asyncio
```

---

## B-004: Initialize Git Repository

```yaml
id: B-004
title: Initialize Git repository
track: Structure
wave: 1
blockedBy: [B-003]
status: NOT_STARTED
estimated_minutes: 3
assignee: null

description: |
  Initialize a Git repository in the avatar directory.

acceptance_criteria:
  - Git repository initialized
  - Initial commit created

implementation_steps:
  - cd avatar
  - git init
  - git add .
  - git commit -m "Phase 0.5: Initial structure for SITL development"

commands:
  - git init && git add . && git commit -m "Phase 0.5: Initial structure for SITL development"
```

---

## P-001: Create .claude Directory Structure

```yaml
id: P-001
title: Create .claude/ directory structure
track: ClaudeConfig
wave: 1
blockedBy: []
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Create the .claude/ directory for Claude Code configuration.

acceptance_criteria:
  - .claude/ directory exists
  - Subdirectories created

implementation_steps:
  - mkdir -p .claude/{commands,agents,skills,hooks}

structure:
  .claude/
  ├── commands/
  ├── agents/
  ├── skills/
  └── hooks/

commands:
  - mkdir -p .claude/{commands,agents,skills,hooks}
```

---

## P-002: Create Project CLAUDE.md

```yaml
id: P-002
title: Create project CLAUDE.md with drone-specific instructions
track: ClaudeConfig
wave: 1
blockedBy: [P-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the project-level CLAUDE.md file with drone-specific instructions
  for Claude Code to understand the project context.

acceptance_criteria:
  - CLAUDE.md file created
  - Contains drone operation guidelines
  - Contains safety protocols
  - Contains project structure reference

implementation_steps:
  - Create .claude/CLAUDE.md
  - Include drone operation guidelines
  - Include safety protocols
  - Include MCP server reference

content_sections:
  - Project Overview
  - Drone Operation Guidelines
  - Safety Protocols
  - MCP Server Tools Reference
  - Project Structure
```

---

## P-003: Create settings.json with Drone Permissions

```yaml
id: P-003
title: Create settings.json with drone permissions
track: ClaudeConfig
wave: 1
blockedBy: [P-001]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Create the settings.json file with appropriate permissions for drone operations.

acceptance_criteria:
  - settings.json created
  - Contains drone-specific permissions
  - Follows safety guidelines

implementation_steps:
  - Create .claude/settings.json
  - Define allowed commands for drone operations
  - Define restricted dangerous operations

permissions:
  allow:
    - Read drone telemetry
    - Execute flight commands
    - Capture camera frames
  require_confirmation:
    - Arm drone
    - Takeoff
    - Land
    - Abort mission
```

---

## P-004: Create .mcp.json for Drone MCP Server

```yaml
id: P-004
title: Create .mcp.json for drone MCP server registration
track: ClaudeConfig
wave: 1
blockedBy: [P-001]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Create the .mcp.json configuration file to register the drone MCP server.

acceptance_criteria:
  - .mcp.json created
  - MCP server properly configured
  - Server accessible from Claude Code

implementation_steps:
  - Create .mcp.json in project root
  - Configure drone MCP server connection
  - Test connection

configuration:
  mcpServers:
    drone-control:
      command: python
      args: ["avatar/mcp_server/server.py"]
      transport: stdio
```

---

## Wave 1 Summary

**Tasks**: 12
**Parallel Groups**: 4
**Critical Path**: A-001 → A-002 → A-003 → A-004

**Execution Order**:
1. Start A-001, B-001, P-001 simultaneously
2. After A-001: Start A-002
3. After A-002: Start A-003 (long-running)
4. After B-001: Start B-002
5. After B-002: Start B-003
6. After A-003: Start A-004
7. After B-003: Start B-004
8. After P-001: Start P-002, P-003, P-004 simultaneously

**Next Wave**: Wave 2 starts when all Wave 1 tasks complete
