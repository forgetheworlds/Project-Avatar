# Wave 5 Tasks: Recording & Testing

**Wave**: 5
**Dependencies**: Wave 4 complete
**Estimated Duration**: 90 minutes with parallelization

---

## J-001: Create Utils Directory

```yaml
id: J-001
title: Create utils/ directory structure
track: Recording
wave: 5
blockedBy: [B-001]
status: NOT_STARTED
estimated_minutes: 5
assignee: null

description: |
  Create the utils module directory structure.

acceptance_criteria:
  - utils/ directory exists
  - Initial files created

structure:
  utils/
  ├── __init__.py
  └── flight_recorder.py
```

---

## J-002: Create Flight Recorder

```yaml
id: J-002
title: Create flight_recorder.py
track: Recording
wave: 5
blockedBy: [J-001]
status: NOT_STARTED
estimated_minutes: 25
assignee: null

description: |
  Create the flight recorder for mission logging and replay.

acceptance_criteria:
  - FlightRecorder class implemented
  - Event logging works
  - Mission save/load works
  - Video frame buffer included

implementation: |
  class FlightRecorder:
      def __init__(self, mission_name: str)
      def log_event(self, event_type: str, data: dict)
      def save_mission(self) -> str
      def load_mission(self, filename: str) -> Dict
```

---

## J-003: Create Demo Recording Script

```yaml
id: J-003
title: Create scripts/start_demo_recording.sh
track: Recording
wave: 5
blockedBy: [J-002]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create the demo recording script that launches all necessary components.

acceptance_criteria:
  - Script launches SITL
  - Script launches MCP server
  - Script starts screen recording
  - Script provides demo instructions

script_functions:
  - start_gazebo_terminal
  - start_mcp_server_terminal
  - start_claude_code_terminal
  - start_screen_recording
  - display_demo_script
```

---

## J-004: Test Mission Logging

```yaml
id: J-004
title: Test mission logging and replay
track: Recording
wave: 5
blockedBy: [J-002]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Test the mission logging and replay functionality.

acceptance_criteria:
  - Events logged correctly
  - Mission file saves
  - Mission file loads
  - Replay timeline accurate

test_scenarios:
  - log_arm_event
  - log_takeoff_event
  - log_waypoint_reached
  - log_land_event
  - save_and_load_mission
```

---

## L-001: Create Kimi Integration Test

```yaml
id: L-001
title: Create tests/test_kimi_integration.py
track: Testing
wave: 5
blockedBy: [E-002]
status: NOT_STARTED
estimated_minutes: 25
assignee: null

description: |
  Create the full Kimi + MCP + SITL integration test.

acceptance_criteria:
  - Test connects to SITL
  - Test initializes Kimi client
  - Test verifies tool calling
  - Test verifies mission execution

test_functions:
  - test_mission_planning
  - test_natural_language_to_tools
  - test_full_pipeline_integration
```

---

## L-002: Create Vision Pipeline Test

```yaml
id: L-002
title: Create tests/test_vision_pipeline.py
track: Testing
wave: 5
blockedBy: [G-004]
status: NOT_STARTED
estimated_minutes: 20
assignee: null

description: |
  Create the vision pipeline test for detection -> exception flow.

acceptance_criteria:
  - Test frame capture
  - Test mock detection
  - Test detection -> confirmation flow

test_functions:
  - test_frame_capture
  - test_mock_detection
  - test_detection_triggers_confirmation
```

---

## L-003: Create Confirmation Test

```yaml
id: L-003
title: Create tests/test_confirmation.py
track: Testing
wave: 5
blockedBy: [I-002]
status: NOT_STARTED
estimated_minutes: 20
assignee: null

description: |
  Create the confirmation workflow test.

acceptance_criteria:
  - Test pre-flight confirmation
  - Test pre-arm confirmation
  - Test mid-flight exception confirmation
  - Test timeout behavior

test_functions:
  - test_pre_flight_confirmation
  - test_pre_arm_confirmation
  - test_exception_confirmation
  - test_confirmation_timeout
```

---

## L-004: Create Benchmarks

```yaml
id: L-004
title: Create tests/benchmarks.py for latency validation
track: Testing
wave: 5
blockedBy: [L-001]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Create performance benchmarks for latency validation.

acceptance_criteria:
  - End-to-end latency benchmark
  - Target: < 2 seconds
  - Multiple test runs averaged

benchmark_targets:
  - end_to_end_latency: 2.0s
  - tool_call_latency: 0.5s
  - telemetry_update_rate: 20Hz
```

---

## L-005: Run Full Test Suite

```yaml
id: L-005
title: Run full test suite (pytest)
track: Testing
wave: 5
blockedBy: [L-001, L-002, L-003, L-004]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Execute the complete test suite and verify all tests pass.

acceptance_criteria:
  - All tests pass
  - No regressions
  - Test output logged

commands:
  - python -m pytest tests/phase05/ -v
```

---

## L-006: Verify Latency Target

```yaml
id: L-006
title: Verify end-to-end latency < 2 seconds
track: Testing
wave: 5
blockedBy: [L-004]
status: NOT_STARTED
estimated_minutes: 10
assignee: null

description: |
  Verify that end-to-end latency meets the <2 second target.

acceptance_criteria:
  - Average latency < 2 seconds
  - Max latency < 3 seconds
  - Latency distribution documented

verification_steps:
  - Run benchmark multiple times
  - Calculate average and max
  - Document results
```

---

## K-001: Write Demo Scenario Script

```yaml
id: K-001
title: Write demo scenario script
track: Demo
wave: 5
blockedBy: [E-002, I-004]
status: NOT_STARTED
estimated_minutes: 20
assignee: null

description: |
  Write the detailed demo scenario script for the video.

acceptance_criteria:
  - Scene-by-scene script written
  - Timing for each scene defined
  - Narration text prepared

demo_script:
  scene_1:
    title: Introduction
    duration: 30s
    content: Overview of Phase 0.5
    
  scene_2:
    title: Agent Connection
    duration: 30s
    content: Claude Code connecting to MCP
    
  scene_3:
    title: Natural Language Mission
    duration: 90s
    content: Mission planning and execution
    
  scene_4:
    title: Vision + Exception
    duration: 60s
    content: Person detection and confirmation
    
  scene_5:
    title: RTL + Landing
    duration: 30s
    content: Safe return and landing
    
  scene_6:
    title: Conclusion
    duration: 30s
    content: Summary and next steps
```

---

## K-002: Create Screen Recording Setup

```yaml
id: K-002
title: Create screen recording setup
track: Demo
wave: 5
blockedBy: [J-003]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Set up screen recording for the demo video.

acceptance_criteria:
  - QuickTime or equivalent configured
  - Window layout prepared
  - Audio settings checked

setup_steps:
  - Configure recording window
  - Set up split view (Gazebo + Claude Code)
  - Test audio capture
```

---

## K-003: Record Demo Video

```yaml
id: K-003
title: Record demo video (4-5 minutes)
track: Demo
wave: 5
blockedBy: [K-001, K-002]
status: NOT_STARTED
estimated_minutes: 30
assignee: null

description: |
  Record the complete demo video following the scenario script.

acceptance_criteria:
  - All scenes recorded
  - Video is 4-5 minutes
  - Audio clear
  - No interruptions

recording_steps:
  - Start recording
  - Execute demo script
  - Stop recording
  - Review recording
```

---

## K-004: Upload Demo Video

```yaml
id: K-004
title: Export and upload demo to video platform
track: Demo
wave: 5
blockedBy: [K-003]
status: NOT_STARTED
estimated_minutes: 15
assignee: null

description: |
  Export and upload the demo video to a video platform.

acceptance_criteria:
  - Video exported in high quality
  - Uploaded to YouTube/Vimeo
  - URL accessible
  - Added to documentation

upload_steps:
  - Export from QuickTime
  - Upload to video platform
  - Set appropriate privacy settings
  - Copy URL for documentation
```

---

## Wave 5 Summary

**Tasks**: 14
**Parallel Groups**: 7

**Execution Order**:
1. Start J-001, L-001, L-002, L-003 simultaneously
2. After J-001: Start J-002
3. After L-001: Start L-004
4. After J-002: Start J-003, J-004 simultaneously
5. After J-003, K-001: Start K-002
6. After L-001, L-002, L-003, L-004: Start L-005
7. After L-004: Start L-006
8. After K-001, K-002: Start K-003
9. After K-003: Start K-004

**Next Wave**: Wave 6 starts when all Wave 5 tasks complete
