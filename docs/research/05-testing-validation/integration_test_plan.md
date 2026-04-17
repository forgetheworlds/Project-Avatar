# Project Avatar - Integration Test Plan

**Document Version:** 1.0  
**Date:** 2026-04-09  
**Status:** Draft for Review  
**Author:** QA Engineering  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Test Architecture](#2-test-architecture)
3. [Component Integration Tests](#3-component-integration-tests)
4. [End-to-End Scenario Tests](#4-end-to-end-scenario-tests)
5. [Stress Tests](#5-stress-tests)
6. [Safety Tests](#6-safety-tests)
7. [Test Automation Framework](#7-test-automation-framework)
8. [Test Matrices](#8-test-matrices)
9. [Pass/Fail Criteria](#9-passfail-criteria)
10. [Risk Assessment & Mitigations](#10-risk-assessment--mitigations)

---

## 1. Executive Summary

This integration test plan defines comprehensive testing strategies for Project Avatar, an LLM-driven drone system using MAVSDK-Python, PX4 Offboard mode, YOLOv8 vision, and local LLM orchestration. The plan addresses:

- **Component integration** across the distributed architecture (Mac Ground Station → RPi Companion → PX4 FC)
- **End-to-end mission scenarios** from natural language to flight execution
- **Stress testing** under degraded conditions
- **Safety validation** for failsafes and emergency procedures
- **Test automation** for CI/CD with SITL and HIL

### Test Coverage Summary

| Category | Test Count | Priority | Execution Environment |
|----------|------------|----------|----------------------|
| Component Integration | 32 | P0 | SITL + Hardware |
| End-to-End Scenarios | 18 | P0 | SITL + Hardware |
| Stress Tests | 24 | P1 | SITL + Hardware |
| Safety Tests | 28 | P0 | SITL + Hardware |
| **Total** | **102** | | |

---

## 2. Test Architecture

### 2.1 Test Pyramid for Drone Systems

```
                    ┌─────────────────┐
                    │   E2E Mission   │  Hardware-in-Loop
                    │     Tests       │  Field Tests
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │    Integration   │     Tests       │
           │  (Component +    │  (Safety +      │
           │   System)        │   Stress)       │
           └─────────────────┼─────────────────┘
                             │
                    ┌────────┴────────┐
                    │   Unit Tests    │  SITL-based
                    │  (Tools, Utils) │  CI/CD
                    └─────────────────┘
```

### 2.2 Test Environments

| Environment | Purpose | Fidelity | Speed | Cost |
|-------------|---------|----------|-------|------|
| **SITL** | CI/CD, regression, safety scenarios | Medium (software physics) | Fast | Low |
| **HITL** | Hardware validation, timing tests | High (real FC) | Real-time | Medium |
| **Bench** | Component isolation, payload tests | N/A | Fast | Low |
| **Field** | Final validation, end-to-end | Full | Real-time | High |

### 2.3 Test Infrastructure Components

```python
# Test Architecture Overview
class TestInfrastructure:
    """
    ┌──────────────────────────────────────────────────────────────┐
    │                     TEST ORCHESTRATOR                        │
    │  - Test sequencing, state management, reporting              │
    │  - Mock LLM for reproducible testing                        │
    └──────────────────────┬─────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───┴───┐        ┌────┴────┐       ┌─────┴──────┐
    │ SITL  │        │  HITL   │       │  Hardware  │
    │ Runner│        │ Runner  │       │   Runner   │
    └───────┘        └─────────┘       └────────────┘
        │                  │                  │
    ┌───┴───┐        ┌────┴────┐       ┌─────┴──────┐
    │ PX4   │        │  PX4    │       │   PX4      │
    │ Sim   │        │  FC     │       │   FC + RPi │
    │(jmavsim│       │(Pixhawk)│       │  + Mac     │
    │/gazebo)│       └─────────┘       └────────────┘
    └───────┘
    """
```

---

## 3. Component Integration Tests

### 3.1 MAVSDK Connection Tests

#### TEST-MAV-001: Basic Connection Establishment
```yaml
Objective: Verify MAVSDK-Python connects to PX4 via all supported transports
Prerequisites:
  - PX4 SITL or hardware running
  - MAVSDK-Python installed
  - Network connectivity (UDP/TCP/Serial)

Test Steps:
  1. Initialize MAVSDK System
  2. Attempt connection with valid address
  3. Subscribe to connection_state()
  4. Verify is_connected becomes True within 5s

Test Variants:
  - UDP inbound: udpin://0.0.0.0:14540
  - UDP outbound: udp://192.168.1.10:14540
  - TCP: tcp://192.168.1.10:5760
  - Serial: serial:///dev/ttyACM0:57600

Pass Criteria:
  - Connection established within 5 seconds
  - No exceptions thrown
  - Connection state properly reported

Priority: P0
Automation: Fully automated
```

#### TEST-MAV-002: Connection Recovery After Drop
```yaml
Objective: Verify system handles connection drops and recovers gracefully
Prerequisites:
  - Active MAVSDK connection
  - Ability to interrupt network

Test Steps:
  1. Establish connection
  2. Start telemetry subscription
  3. Simulate network interruption (5s, 30s, 120s)
  4. Restore network
  5. Verify automatic reconnection
  6. Verify telemetry resumes

Pass Criteria:
  - Reconnection within 10s of network restoration
  - Telemetry subscriptions automatically resume
  - No zombie tasks or memory leaks

Priority: P0
Automation: Fully automated
```

#### TEST-MAV-003: Multiple System Connection
```yaml
Objective: Test connection to multiple MAVLink systems
Prerequisites:
  - Multiple PX4 instances or broadcast capability

Test Steps:
  1. Connect to primary system
  2. Discover secondary systems on network
  3. Verify UUID-based system identification
  4. Test switching between systems

Pass Criteria:
  - Correct system identification via UUID
  - No cross-contamination between systems
  - Clean disconnection from one, connection to another

Priority: P1
Automation: Semi-automated (requires multi-vehicle setup)
```

#### TEST-MAV-004: Connection Timeout Handling
```yaml
Objective: Verify proper timeout handling for unreachable systems
Prerequisites:
  - MAVSDK client ready
  - Invalid/non-existent target address

Test Steps:
  1. Attempt connection to non-existent endpoint
  2. Verify timeout occurs at expected duration
  3. Verify appropriate exception raised
  4. Verify clean resource cleanup

Pass Criteria:
  - Timeout within configured limit (default 30s)
  - ConnectionError or similar raised
  - No resource leaks (check with psutil)

Priority: P1
Automation: Fully automated
```

#### TEST-MAV-005: High-Latency Connection Resilience
```yaml
Objective: Verify operation under high network latency
Prerequisites:
  - Network latency injection capability (tc/netem)

Test Steps:
  1. Establish baseline connection
  2. Inject 100ms latency
  3. Inject 500ms latency
  4. Inject 1000ms latency
  5. Verify telemetry still received
  6. Verify setpoint streaming tolerated

Pass Criteria:
  - Connection maintained up to 500ms latency
  - Telemetry received (possibly delayed)
  - No offboard timeout at 100ms latency
  - Graceful degradation above 500ms

Priority: P0
Automation: Fully automated (Linux netem)
```

### 3.2 Camera Streaming Tests

#### TEST-CAM-001: Video Stream Initialization
```yaml
Objective: Verify camera stream starts and delivers frames
Prerequisites:
  - Camera hardware connected to RPi
  - Streaming server configured

Test Steps:
  1. Initialize camera on RPi
  2. Start streaming server (MJPEG/RTSP)
  3. Connect client on Mac
  4. Capture 100 frames
  5. Measure frame rate and latency

Pass Criteria:
  - Stream starts within 3 seconds
  - Frame rate >= 15 FPS at 640x480
  - No corrupted frames
  - Latency < 200ms

Priority: P0
Automation: Semi-automated (requires hardware)
```

#### TEST-CAM-002: Stream Resilience Under Network Stress
```yaml
Objective: Test camera stream under packet loss and jitter
Prerequisites:
  - Active camera stream
  - Network impairment tools

Test Steps:
  1. Establish baseline stream quality
  2. Inject 1% packet loss
  3. Inject 5% packet loss
  4. Inject 20% packet loss
  5. Inject 100ms jitter
  6. Measure frame drops and recovery

Pass Criteria:
  - Graceful degradation at 5% loss
  - Automatic recovery after packet loss stops
  - No stream corruption propagating to YOLO

Priority: P1
Automation: Semi-automated
```

#### TEST-CAM-003: YOLO Integration Pipeline
```yaml
Objective: Verify YOLOv8 processes camera frames correctly
Prerequisites:
  - Camera stream active
  - YOLOv8-nano model available

Test Steps:
  1. Start camera stream
  2. Initialize YOLOv8 detector
  3. Run detection loop for 60 seconds
  4. Place known objects in view
  5. Verify detections match expected classes
  6. Measure inference latency

Pass Criteria:
  - Inference >= 10 FPS on Mac M3 (MPS or CPU)
  - Correct class detection (person, etc.)
  - Bounding box coordinates valid
  - Memory usage stable over 60s

Priority: P0
Automation: Semi-automated (requires hardware or test video)
```

#### TEST-CAM-004: ByteTrack Integration
```yaml
Objective: Verify object tracking maintains IDs across frames
Prerequisites:
  - YOLO pipeline running
  - ByteTrack tracker configured

Test Steps:
  1. Initialize YOLO + ByteTrack pipeline
  2. Present moving target in frame
  3. Track target for 100 frames
  4. Verify ID persistence
  5. Test occlusion recovery

Pass Criteria:
  - ID maintained for continuous tracking
  - ID preserved through brief occlusions (< 1s)
  - No ID switches without re-detection

Priority: P1
Automation: Semi-automated (test video with ground truth)
```

#### TEST-CAM-005: State String Synthesis
```yaml
Objective: Verify telemetry + vision fusion produces correct state
Prerequisites:
  - MAVSDK telemetry active
  - YOLO detections active
  - State String generator implemented

Test Steps:
  1. Start telemetry subscription
  2. Start vision pipeline
  3. Generate state strings at 1Hz
  4. Verify format correctness
  5. Verify data freshness (< 2s old)

Pass Criteria:
  - State string generated every 1-2 seconds
  - Telemetry fields present and valid
  - Detection counts accurate
  - ID positions correctly described

Priority: P0
Automation: Semi-automated
```

### 3.3 LLM Orchestration Tests

#### TEST-LLM-001: Local LLM Initialization
```yaml
Objective: Verify Ollama/Llama 3 starts and responds
Prerequisites:
  - Ollama installed on Mac
  - Llama 3 model pulled

Test Steps:
  1. Start Ollama server
  2. Verify model loaded
  3. Send test prompt
  4. Measure response latency
  5. Verify response quality

Pass Criteria:
  - Server starts within 10s
  - Response received within 3s (warm)
  - Response coherent and relevant
  - Memory usage acceptable (< 8GB for 8B model)

Priority: P0
Automation: Fully automated
```

#### TEST-LLM-002: Tool Schema Validation
```yaml
Objective: Verify LLM emits valid tool call JSON
Prerequisites:
  - LLM initialized
  - Tool schema defined

Test Steps:
  1. Send system prompt with tool definitions
  2. Request tool call with natural language
  3. Parse LLM response
  4. Validate against JSON schema
  5. Test each tool: arm_and_takeoff, goto_gps, etc.

Test Cases:
  - "Take off to 10 meters"
  - "Fly 20 meters north"
  - "Land immediately"
  - "Find and orbit the person"

Pass Criteria:
  - Valid JSON emitted for all test cases
  - Required parameters present
  - Parameter types correct
  - Tool name matches schema

Priority: P0
Automation: Fully automated
```

#### TEST-LLM-003: Malformed Response Handling
```yaml
Objective: Verify graceful handling of invalid LLM outputs
Prerequisites:
  - LLM orchestrator running
  - JSON validator implemented

Test Steps:
  1. Send prompts designed to trigger hallucinations
  2. Verify invalid JSON rejection
  3. Verify retry logic engages
  4. Verify safety fallback activated
  5. Test maximum retry limits

Test Cases:
  - Hallucinated tool names
  - Missing required parameters
  - Invalid parameter types
  - JSON syntax errors
  - Non-JSON plain text responses

Pass Criteria:
  - All malformed outputs rejected
  - Retry up to 3 times
  - Safe fallback after max retries
  - Events logged

Priority: P0
Automation: Fully automated
```

#### TEST-LLM-004: Latency Under Load
```yaml
Objective: Measure LLM response time under various conditions
Prerequisites:
  - LLM server running
  - Load generation capability

Test Steps:
  1. Measure cold-start latency
  2. Measure warm latency (single request)
  3. Measure latency under 5 concurrent requests
  4. Measure latency with 4K context
  5. Measure latency with 8K context

Pass Criteria:
  - Cold start < 10s
  - Warm latency < 2s (p95)
  - Concurrent requests handled (queued)
  - Context scaling linear or better

Priority: P1
Automation: Fully automated
```

#### TEST-LLM-005: Mock LLM for Reproducible Testing
```yaml
Objective: Verify mock LLM produces deterministic outputs
Prerequisites:
  - Mock LLM implementation
  - Test scenario definitions

Test Steps:
  1. Configure mock with fixed responses
  2. Run identical inputs 10 times
  3. Verify identical outputs
  4. Test conditional responses
  5. Verify state machine transitions

Pass Criteria:
  - Deterministic responses for same input
  - State transitions follow defined rules
  - Suitable for regression testing

Priority: P0
Automation: Fully automated
```

### 3.4 Telemetry Flow Tests

#### TEST-TEL-001: Basic Telemetry Subscription
```yaml
Objective: Verify all telemetry streams deliver data
Prerequisites:
  - MAVSDK connection active
  - Drone powered and armed

Test Steps:
  1. Subscribe to battery telemetry
  2. Subscribe to position telemetry
  3. Subscribe to flight mode telemetry
  4. Subscribe to health telemetry
  5. Subscribe to velocity telemetry
  6. Verify data received for 30 seconds

Pass Criteria:
  - All subscriptions return data within 2s
  - Data values reasonable (not NaN/None)
  - Update rates match configured rates

Priority: P0
Automation: Fully automated
```

#### TEST-TEL-002: Concurrent Telemetry Handling
```yaml
Objective: Verify system handles multiple simultaneous telemetry streams
Prerequisites:
  - MAVSDK connection active

Test Steps:
  1. Create 5+ concurrent telemetry tasks
  2. Run for 60 seconds
  3. Monitor for dropped messages
  4. Monitor CPU usage
  5. Monitor memory usage

Pass Criteria:
  - No dropped messages
  - CPU usage < 50% on M3
  - Memory stable (no leaks)
  - No asyncio warnings

Priority: P1
Automation: Fully automated
```

#### TEST-TEL-003: EKF Status Monitoring
```yaml
Objective: Verify EKF health telemetry correctly interpreted
Prerequisites:
  - Drone with GPS fix
  - EKF converged

Test Steps:
  1. Subscribe to EKF status
  2. Verify solution_status_flags
  3. Verify innovation_test_ratios
  4. Verify pre_flt_fail flags
  5. Test behavior during GPS denial

Pass Criteria:
  - Health.is_global_position_ok accurate
  - EKF flags correctly parsed
  - Innovation ratios below threshold (< 1.0)

Priority: P0
Automation: Fully automated
```

#### TEST-TEL-004: Telemetry Rate Configuration
```yaml
Objective: Verify custom telemetry rates are respected
Prerequisites:
  - MAVSDK connection active

Test Steps:
  1. Set position rate to 10Hz
  2. Set velocity rate to 5Hz
  3. Measure actual received rates
  4. Test rate 0 (stop)
  5. Test rate 50Hz (maximum)

Pass Criteria:
  - Rates within 10% of requested
  - 0Hz stops stream
  - Maximum rate respected

Priority: P2
Automation: Fully automated
```

#### TEST-TEL-005: Flight Mode Transition Detection
```yaml
Objective: Verify accurate detection of PX4 mode changes
Prerequisites:
  - Drone armed and in Position mode
  - Offboard capability configured

Test Steps:
  1. Start mode monitoring task
  2. Manually switch modes via RC
  3. Verify mode changes detected within 500ms
  4. Test offboard entry/exit
  5. Test failsafe mode transitions

Pass Criteria:
  - Mode changes detected within 500ms
  - Offboard entry/exit properly logged
  - Failsafe transitions captured

Priority: P0
Automation: Semi-automated (requires manual RC input)
```

---

## 4. End-to-End Scenario Tests

### 4.1 Full Takeoff-Orbit-Land with Vision

#### TEST-E2E-001: Basic Takeoff and Land
```yaml
Objective: Complete end-to-end mission: takeoff → hover → land
Prerequisites:
  - Drone assembled and calibrated
  - GPS fix obtained
  - Safety pilot present
  - Pre-flight checks passed

Test Steps:
  1. LLM receives: "Take off to 5 meters and land"
  2. LLM generates tool sequence
  3. Orchestrator validates tools
  4. Pre-arm checks executed
  5. Arming command sent
  6. Takeoff executed
  7. Hover for 5 seconds
  8. Landing executed
  9. Mission completion verified

Pass Criteria:
  - Takeoff reaches target altitude ± 0.5m
  - Hover stable (position variance < 1m)
  - Landing smooth (no bounce, no tip-over)
  - Total mission time < 60s
  - All telemetry logged

Priority: P0
Environment: Field (after SITL validation)
Safety: Spotter required, RC override tested
```

#### TEST-E2E-002: GPS Waypoint Mission
```yaml
Objective: Execute multi-waypoint mission via natural language
Prerequisites:
  - GPS area surveyed
  - Waypoints programmed
  - Geofence configured

Test Steps:
  1. LLM receives: "Take off, fly to point A, then point B, then land"
  2. Execute full mission
  3. Verify waypoint arrival (within 2m radius)
  4. Verify altitude compliance
  5. Verify smooth transitions

Pass Criteria:
  - All waypoints reached
  - Position error < 2m at each waypoint
  - Altitude maintained ± 1m
  - No geofence breaches

Priority: P0
Environment: Field
Safety: Geofence active, RC override ready
```

#### TEST-E2E-003: Vision-Guided Person Orbit
```yaml
Objective: Find person and orbit using vision guidance
Prerequisites:
  - Stage 2 vision active
  - Person in test area
  - Safety area cleared

Test Steps:
  1. LLM receives: "Take off, find the person, orbit them at 10m distance"
  2. Drone executes takeoff
  3. YOLO detects person
  4. ByteTrack maintains ID
  5. LLM switches to orbit mode
  6. Drone orbits while maintaining visual contact
  7. Mission complete command
  8. RTL or land

Pass Criteria:
  - Person detected within 30s
  - ID maintained during orbit
  - Orbit radius maintained ± 2m
  - Yaw keeps person in frame (>70% of time)

Priority: P0
Environment: Field
Safety: Minimum 20m safety radius, spotter
```

#### TEST-E2E-004: Person Following Mission
```yaml
Objective: Track and follow a moving person
Prerequisites:
  - Vision system active
  - Cooperative test subject
  - Large clear area

Test Steps:
  1. Initiate follow mode
  2. Person walks predictable path
  3. Drone maintains offset
  4. Test speed variations
  5. Test direction changes
  6. Terminate mission safely

Pass Criteria:
  - Target maintained in frame >80% of time
  - Following distance maintained ± 3m
  - Smooth velocity transitions
  - No aggressive maneuvers

Priority: P1
Environment: Field
Safety: Emergency stop tested, max speed limited
```

### 4.2 Network Loss During Flight

#### TEST-E2E-005: Brief Wi-Fi Loss (< 3s)
```yaml
Objective: Verify resilience to brief network interruption
Prerequisites:
  - Wi-Fi controllable (can be disabled)
  - COM_OBL_RC_ACT configured

Test Steps:
  1. Drone in offboard mode at 10m
  2. Disable Wi-Fi for 2 seconds
  3. Monitor PX4 flight mode
  4. Re-enable Wi-Fi
  5. Verify automatic recovery

Pass Criteria:
  - Failsafe triggered within 1s (COM_OF_LOSS_T)
  - Failsafe action executed (Land or Hold)
  - Recovery after reconnection
  - No erratic behavior

Priority: P0
Environment: SITL + Field
Safety: SITL first, then supervised field test
```

#### TEST-E2E-006: Extended Wi-Fi Loss (> 10s)
```yaml
Objective: Verify proper handling of extended disconnection
Prerequisites:
  - Active flight in progress
  - RC link available as backup

Test Steps:
  1. Drone in mission
  2. Disable Wi-Fi for 15 seconds
  3. Verify failsafe progression
  4. Either auto-land or RC takeover
  5. Document behavior

Pass Criteria:
  - Failsafe action consistent with NAV_DLL_ACT
  - If configured RTL: drone returns home
  - If configured Land: drone lands safely
  - RC can override at any time

Priority: P0
Environment: SITL mandatory first
Safety: Field test only after SITL validation
```

#### TEST-E2E-007: Intermittent Packet Loss
```yaml
Objective: Test behavior under degraded link quality
Prerequisites:
  - Network impairment capability

Test Steps:
  1. Start mission
  2. Inject 20% packet loss
  3. Monitor setpoint continuity
  4. Monitor flight stability
  5. Remove impairment
  6. Verify recovery

Pass Criteria:
  - MAVSDK handles packet loss gracefully
  - Offboard timeout not triggered
  - Mission continues
  - Smooth recovery

Priority: P1
Environment: SITL
Automation: Fully automated with netem
```

### 4.3 RC Override at Each Phase

#### TEST-E2E-008: Takeoff Phase Override
```yaml
Objective: Verify immediate RC takeover during takeoff
Prerequisites:
  - COM_RC_OVERRIDE enabled
  - RC configured for Position mode

Test Steps:
  1. Initiate takeoff command
  2. During climb, move RC sticks > 10%
  3. Verify mode switch to Position
  4. Verify manual control

Pass Criteria:
  - Mode switch within 500ms
  - Manual control responsive
  - Smooth transition
  - No altitude loss

Priority: P0
Environment: Field
Safety: Experienced pilot required
```

#### TEST-E2E-009: Offboard Mission Override
```yaml
Objective: Verify RC override during active offboard control
Prerequisites:
  - Drone in offboard mode
  - Active setpoint streaming

Test Steps:
  1. Drone executing offboard waypoint
  2. Pilot initiates mode switch
  3. Verify immediate switch
  4. Verify setpoint stream stops
  5. Verify manual control

Pass Criteria:
  - Mode change immediate
  - No offboard setpoints processed after switch
  - Manual control authoritative

Priority: P0
Environment: Field
Safety: Pilot ready to assume control
```

#### TEST-E2E-010: RTL Override
```yaml
Objective: Verify RC can interrupt RTL
Prerequisites:
  - RTL triggered (loss of offboard or command)

Test Steps:
  1. Trigger RTL (via command or failsafe)
  2. During RTL, switch to Position mode
  3. Verify RTL aborted
  4. Verify manual control resumed

Pass Criteria:
  - RTL aborts immediately
  - Position mode engaged
  - Pilot has full control

Priority: P0
Environment: Field
Safety: RTL tested at low altitude first
```

#### TEST-E2E-011: Kill Switch Test
```yaml
Objective: Verify kill switch stops motors immediately
Prerequisites:
  - Kill switch configured on RC
  - Props installed (bench test first)

Test Steps:
  1. Bench test: props off, verify kill disarms
  2. Field test at low altitude (< 2m)
  3. Activate kill switch
  4. Verify immediate motor stop
  5. Verify auto-disarm after 5s

Pass Criteria:
  - Motors stop within 100ms
  - Auto-disarm after 5s
  - Manual re-arm required

Priority: P0
Environment: Bench first, then field
Safety: Minimal altitude, clear area
```

### 4.4 Battery Failsafe Trigger

#### TEST-E2E-012: Low Battery Warning
```yaml
Objective: Verify low battery warning propagated to LLM
Prerequisites:
  - Simulated or real low battery condition
  - BAT_LOW_THR configured

Test Steps:
  1. Set battery threshold artificially high for test
  2. Monitor telemetry
  3. Verify warning in state string
  4. Verify LLM informed
  5. Verify appropriate response

Pass Criteria:
  - Warning appears in state string
  - LLM notified
  - Conservative behavior triggered

Priority: P1
Environment: SITL (can simulate battery)
Automation: Fully automated in SITL
```

#### TEST-E2E-013: Critical Battery RTL
```yaml
Objective: Verify RTL triggered at critical battery
Prerequisites:
  - BAT_CRIT_THR configured
  - COM_LOW_BAT_ACT = 2 (RTL at critical)

Test Steps:
  1. Simulate critical battery level
  2. Verify automatic RTL triggered
  3. Monitor RTL progress
  4. Verify landing at home

Pass Criteria:
  - RTL triggers automatically
  - Drone returns to home
  - Lands safely
  - State logged

Priority: P0
Environment: SITL mandatory, field with caution
Safety: Field test only with fresh battery, software threshold
```

#### TEST-E2E-014: Emergency Battery Land
```yaml
Objective: Verify immediate landing at emergency battery
Prerequisites:
  - BAT_EMERGEN_THR configured

Test Steps:
  1. Simulate emergency battery level
  2. Verify immediate Land mode
  3. Verify descent at landing speed
  4. Verify disarm on touchdown

Pass Criteria:
  - Land mode immediate
  - Descent controlled
  - Disarm on landing detected

Priority: P0
Environment: SITL
Automation: Fully automated
```

---

## 5. Stress Tests

### 5.1 High-Frequency LLM Commands

#### TEST-STR-001: Rapid Command Sequencing
```yaml
Objective: Test system stability under rapid LLM tool calls
Prerequisites:
  - Mock LLM configured for high frequency
  - SITL environment

Test Steps:
  1. Generate 1 command per second for 60 seconds
  2. Mix of: position changes, velocity changes, holds
  3. Monitor setpoint consistency
  4. Monitor offboard stability
  5. Check for race conditions

Pass Criteria:
  - No offboard timeouts
  - Smooth trajectory
  - No command queue overflow
  - Memory usage stable

Priority: P1
Environment: SITL
Automation: Fully automated
```

#### TEST-STR-002: Concurrent LLM Requests
```yaml
Objective: Verify handling of overlapping LLM decisions
Prerequisites:
  - Multiple prompt sources simulated

Test Steps:
  1. Send overlapping natural language requests
  2. Verify command serialization
  3. Verify no conflicting setpoints
  4. Test command queuing policy

Pass Criteria:
  - Commands serialized properly
  - Current command completes before next
  - No conflicting setpoints sent

Priority: P1
Environment: SITL
Automation: Fully automated
```

#### TEST-STR-003: LLM Response Delay Stress
```yaml
Objective: Test behavior when LLM exceeds latency budget
Prerequisites:
  - Ability to inject LLM delays
  - Offboard heartbeat independent

Test Steps:
  1. Inject 5s LLM response delay
  2. Verify heartbeat continues
  3. Verify no offboard timeout
  4. Inject 10s delay
  5. Document behavior

Pass Criteria:
  - Heartbeat maintained during LLM delay
  - Drone holds position
  - No failsafe triggered

Priority: P0
Environment: SITL
Automation: Fully automated
```

### 5.2 Rapid Mode Switches

#### TEST-STR-004: Mode Switch Flood
```yaml
Objective: Verify stability under rapid mode transitions
Prerequisites:
  - SITL or safe test environment

Test Steps:
  1. Rapidly switch between: Position, Offboard, Hold
  2. 10 switches per minute
  3. Monitor for lockups
  4. Check telemetry consistency

Pass Criteria:
  - No mode transition failures
  - Telemetry accurate after each switch
  - No memory leaks

Priority: P1
Environment: SITL
Automation: Fully automated
```

#### TEST-STR-005: Offboard Entry/Exit Storm
```yaml
Objective: Test rapid offboard start/stop cycles
Prerequisites:
  - Drone in safe hover state

Test Steps:
  1. Start offboard
  2. Send setpoint
  3. Stop offboard
  4. Repeat 20 times
  5. Monitor for errors

Pass Criteria:
  - No OffboardError exceptions
  - Clean entry/exit each time
  - Setpoints properly initialized

Priority: P1
Environment: SITL
Automation: Fully automated
```

### 5.3 Concurrent Operations

#### TEST-STR-006: Telemetry + Vision + LLM Concurrency
```yaml
Objective: Verify stability with all subsystems active
Prerequisites:
  - All components running
  - Resource monitoring enabled

Test Steps:
  1. Start telemetry (5+ streams)
  2. Start vision pipeline (YOLO + tracking)
  3. Start LLM inference loop
  4. Run for 10 minutes
  5. Monitor resource usage

Pass Criteria:
  - CPU usage < 80%
  - Memory usage stable
  - No dropped frames
  - No telemetry gaps

Priority: P0
Environment: Mac + SITL
Automation: Fully automated
```

#### TEST-STR-007: Multi-Target Tracking Load
```yaml
Objective: Test vision system with many simultaneous targets
Prerequisites:
  - Video feed with 10+ detectable objects
  - YOLO + ByteTrack active

Test Steps:
  1. Present 5, 10, 15 simultaneous targets
  2. Measure inference time
  3. Measure tracking quality
  4. Monitor frame drops

Pass Criteria:
  - Inference time < 200ms per frame
  - ID tracking accuracy > 90%
  - Frame rate maintained

Priority: P2
Environment: SITL with test video
Automation: Fully automated
```

### 5.4 Memory Pressure

#### TEST-STR-008: Long-Duration Memory Test
```yaml
Objective: Detect memory leaks over extended operation
Prerequisites:
  - Memory profiling enabled
  - 1+ hour test duration

Test Steps:
  1. Start all subsystems
  2. Run mission simulation for 1 hour
  3. Capture memory snapshot every 5 minutes
  4. Analyze for leaks

Pass Criteria:
  - Memory growth < 10% over hour
  - No unbounded growth trend
  - Clean garbage collection

Priority: P1
Environment: SITL
Automation: Fully automated
```

#### TEST-STR-009: High-Resolution Vision Stress
```yaml
Objective: Test memory limits with large video frames
Prerequisites:
  - Camera capable of 1080p+
  - Memory monitoring

Test Steps:
  1. Run at 480p baseline
  2. Increase to 720p
  3. Increase to 1080p
  4. Monitor memory and performance

Pass Criteria:
  - No OOM crashes
  - Graceful degradation
  - Performance metrics logged

Priority: P2
Environment: Hardware (Mac M3)
Automation: Semi-automated
```

---

## 6. Safety Tests

### 6.1 Geofence Breach Attempts

#### TEST-SAF-001: Geofence Horizontal Breach
```yaml
Objective: Verify geofence prevents horizontal boundary violation
Prerequisites:
  - GF_MAX_HOR_DIST configured (e.g., 100m)
  - GF_ACTION configured (Hold or Return)
  - Test area mapped

Test Steps:
  1. Drone positioned 80m from home
  2. Command goto_gps outside geofence
  3. Verify geofence triggers
  4. Verify configured action
  5. Verify logging

Pass Criteria:
  - Geofence triggers before breach
  - Action executed (Hold/Return)
  - No boundary violation
  - Event logged

Priority: P0
Environment: SITL mandatory, field with extreme caution
Safety: SITL first, field only with RTL configured
```

#### TEST-SAF-002: Geofence Altitude Breach
```yaml
Objective: Verify altitude geofence enforcement
Prerequisites:
  - GF_MAX_VER_DIST configured
  - Altitude mode tested

Test Steps:
  1. Configure max altitude (e.g., 50m)
  2. Attempt climb to 60m
  3. Verify geofence action

Pass Criteria:
  - Climb stopped at limit
  - No altitude breach
  - Smooth enforcement

Priority: P0
Environment: SITL
Automation: Fully automated
```

#### TEST-SAF-003: Geofence Recovery
```yaml
Objective: Verify recovery after geofence breach
Prerequisites:
  - Geofence triggered previously

Test Steps:
  1. Trigger geofence (Hold mode)
  2. Command return to safe area
  3. Verify drone returns
  4. Verify mission can resume

Pass Criteria:
  - Safe return to geofence interior
  - Manual control restored
  - Mission resumption possible

Priority: P1
Environment: SITL
Automation: Fully automated
```

### 6.2 Invalid Command Injection

#### TEST-SAF-004: Out-of-Bounds Coordinates
```yaml
Objective: Verify rejection of impossible coordinates
Prerequisites:
  - Input validation implemented

Test Cases:
  - Latitude: 95.0 (invalid range)
  - Longitude: -200.0 (invalid range)
  - Coordinates in ocean (null island)
  - Distance > 10km from home

Pass Criteria:
  - All invalid coordinates rejected
  - Error returned to LLM
  - No command execution
  - Event logged

Priority: P0
Environment: Unit + SITL
Automation: Fully automated
```

#### TEST-SAF-005: Dangerous Altitude Commands
```yaml
Objective: Verify altitude safety limits enforced
Prerequisites:
  - Altitude bounds configured

Test Cases:
  - Altitude: -10m (below ground)
  - Altitude: 200m (exceeds safe limit)
  - Altitude: 500m (regulatory violation)

Pass Criteria:
  - Negative altitude rejected
  - Excessive altitude rejected
  - Hard limits not bypassable

Priority: P0
Environment: Unit + SITL
Automation: Fully automated
```

#### TEST-SAF-006: Invalid Velocity Commands
```yaml
Objective: Verify velocity command validation
Prerequisites:
  - Velocity safety limits

Test Cases:
  - Velocity > 20 m/s (unsafe)
  - Negative vertical velocity (excessive descent)
  - NaN or Infinity values

Pass Criteria:
  - Unsafe velocities rejected
  - Valid commands accepted
  - NaN/Infinity handled gracefully

Priority: P1
Environment: Unit test
Automation: Fully automated
```

#### TEST-SAF-007: JSON Injection Attack
```yaml
Objective: Verify protection against malicious JSON
Prerequisites:
  - JSON parser hardened

Test Cases:
  - Nested objects (depth attack)
  - Extremely long strings
  - Unicode escape sequences
  - Control characters

Pass Criteria:
  - All malformed JSON rejected
  - Parser doesn't crash
  - No code execution

Priority: P1
Environment: Unit test
Automation: Fully automated
```

### 6.3 Emergency Stop Verification

#### TEST-SAF-008: Software Emergency Stop
```yaml
Objective: Verify software emergency_stop() tool
Prerequisites:
  - Emergency stop tool implemented

Test Steps:
  1. Drone in motion
  2. Trigger emergency_stop
  3. Verify immediate hover
  4. Verify all motion ceases

Pass Criteria:
  - Stop within 500ms
  - Hover maintained
  - No continued motion

Priority: P0
Environment: SITL, then field
Automation: Fully automated in SITL
```

#### TEST-SAF-009: Kill Switch Hardware Test
```yaml
Objective: Verify hardware kill switch function
Prerequisites:
  - Kill switch configured
  - Bench test completed

Test Steps:
  1. Armed on ground
  2. Activate kill switch
  3. Verify immediate disarm
  4. Verify motors stop

Pass Criteria:
  - Motors stop within 100ms
  - Disarm confirmed
  - Safe state achieved

Priority: P0
Environment: Bench, then field at low altitude
Safety: Prop guards recommended
```

#### TEST-SAF-010: Emergency RTL Trigger
```yaml
Objective: Verify RTL command execution
Prerequisites:
  - RTL configured
  - Home position set

Test Steps:
  1. Drone at 100m distance
  2. Trigger RTL
  3. Verify RTL mode engaged
  4. Verify return path
  5. Verify landing

Pass Criteria:
  - RTL mode immediate
  - Return path safe
  - Landing at home position

Priority: P0
Environment: SITL mandatory
Automation: Fully automated
```

### 6.4 Recovery Procedures

#### TEST-SAF-011: EKF Recovery After GPS Glitch
```yaml
Objective: Verify EKF recovers from simulated GPS failure
Prerequisites:
  - SITL capable of GPS failure injection

Test Steps:
  1. Establish GPS lock
  2. Inject GPS failure for 10s
  3. Monitor EKF status
  4. Restore GPS
  5. Verify EKF recovery

Pass Criteria:
  - EKF detects GPS loss
  - Position estimate degrades gracefully
  - Recovery when GPS restored
  - No flyaway behavior

Priority: P0
Environment: SITL
Automation: Fully automated
```

#### TEST-SAF-012: Communication Bridge Recovery
```yaml
Objective: Verify RPi bridge recovers from failure
Prerequisites:
  - RPi bridge active
  - Failure injection capability

Test Steps:
  1. Kill mavsdk_server process
  2. Monitor connection state
  3. Verify auto-restart
  4. Verify reconnection

Pass Criteria:
  - Connection loss detected
  - Reconnection attempted
  - Full recovery within 15s

Priority: P1
Environment: SITL + Hardware
Automation: Semi-automated
```

#### TEST-SAF-013: Vision Pipeline Recovery
```yaml
Objective: Verify vision system recovers from crashes
Prerequisites:
  - YOLO pipeline active
  - Process monitoring

Test Steps:
  1. Kill YOLO process
  2. Verify detection stops
  3. Monitor recovery
  4. Verify restart success

Pass Criteria:
  - Detection loss detected
  - Auto-restart within 10s
  - Detections resume

Priority: P1
Environment: Hardware
Automation: Semi-automated
```

#### TEST-SAF-014: LLM Service Recovery
```yaml
Objective: Verify LLM orchestration handles Ollama restart
Prerequisites:
  - Ollama running
  - Process monitoring

Test Steps:
  1. Kill Ollama process
  2. Send LLM request
  3. Verify error handling
  4. Restart Ollama
  5. Verify reconnection

Pass Criteria:
  - Connection failure detected
  - User/operator notified
  - Reconnection on restart
  - Resume normal operation

Priority: P1
Environment: Mac hardware
Automation: Semi-automated
```

#### TEST-SAF-015: State Corruption Recovery
```yaml
Objective: Verify system handles corrupted state gracefully
Prerequisites:
  - State management implemented

Test Steps:
  1. Corrupt internal state variables
  2. Verify detection
  3. Verify safe fallback
  4. Verify recovery

Pass Criteria:
  - Corruption detected
  - Safe mode engaged
  - Recovery possible

Priority: P2
Environment: Unit + SITL
Automation: Semi-automated
```

---

## 7. Test Automation Framework

### 7.1 SITL-Based CI Tests

#### Framework Architecture

```python
# tests/conftest.py - Test Configuration
import pytest
import asyncio
from mavsdk import System
from unittest.mock import Mock

@pytest.fixture(scope="session")
def sitl_drone():
    """
    Start PX4 SITL and return connected MAVSDK System
    Requires: PX4_AUTOPILOT_REPO, jmavsim or gazebo
    """
    # Start SITL subprocess
    sitl_process = start_sitl()
    
    # Connect MAVSDK
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    
    # Wait for connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    
    yield drone
    
    # Cleanup
    await drone.action.disarm()
    sitl_process.terminate()

@pytest.fixture
def mock_llm():
    """Mock LLM with deterministic responses"""
    return MockLLM(responses=LOADED_TEST_SCENARIOS)

@pytest.fixture
def telemetry_collector():
    """Capture and store telemetry for analysis"""
    return TelemetryCollector()
```

#### GitHub Actions CI Configuration

```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  sitl-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup PX4 SITL
      run: |
        git clone https://github.com/PX4/PX4-Autopilot.git
        cd PX4-Autopilot
        make px4_sitl_default
        
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
        
    - name: Install dependencies
      run: |
        pip install mavsdk pytest pytest-asyncio
        pip install -r requirements-test.txt
        
    - name: Run Component Tests
      run: |
        pytest tests/integration/test_mavsdk_connection.py -v
        pytest tests/integration/test_telemetry.py -v
        
    - name: Run Safety Tests
      run: |
        pytest tests/integration/test_safety_geofence.py -v
        pytest tests/integration/test_safety_failsafe.py -v
        
    - name: Run Stress Tests
      run: |
        pytest tests/integration/test_stress_rapid_commands.py -v
        
    - name: Generate Report
      run: |
        pytest --html=report.html --self-contained-html
        
    - name: Upload Report
      uses: actions/upload-artifact@v3
      with:
        name: test-report
        path: report.html
```

### 7.2 Hardware-in-Loop Tests

#### HITL Test Bench Setup

```python
# tests/hitl/conftest.py
import pytest
import serial

@pytest.fixture(scope="session")
def hitl_drone():
    """
    Connect to physical Pixhawk via USB/serial
    Requires: Hardware connected, props removed
    """
    drone = System()
    
    # Connect to physical FC
    await drone.connect(system_address="serial:///dev/ttyACM0:57600")
    
    # Safety: Ensure disarmed, props removed
    await drone.action.disarm()
    
    # Verify health (no props = can't arm, but can test communication)
    async for health in drone.telemetry.health():
        if health.is_gyrometer_calibration_ok:
            break
    
    yield drone
    
    # Safety cleanup
    await drone.action.disarm()
    await drone.action.kill()  # Emergency stop
```

#### HITL Test Categories

| Category | HITL Required? | Why? |
|----------|----------------|------|
| Connection tests | Yes | Serial timing differs from UDP |
| Telemetry tests | Yes | Real sensor data validation |
| Offboard tests | Yes | Timing validation with real FC |
| Geofence tests | Yes | Real parameter storage |
| RC override tests | **Required** | Only real hardware has RC |
| Kill switch tests | **Required** | Safety-critical hardware only |
| Vision tests | Yes | Real camera integration |

### 7.3 Mock LLM for Reproducibility

```python
# tests/mocks/llm_mock.py
class MockLLM:
    """
    Deterministic LLM for reproducible integration tests.
    Eliminates non-determinism of real LLM inference.
    """
    
    def __init__(self, scenario_file: str):
        self.scenarios = self._load_scenarios(scenario_file)
        self.call_count = 0
        
    def _load_scenarios(self, path: str) -> dict:
        """Load test scenarios from YAML"""
        with open(path) as f:
            return yaml.safe_load(f)
    
    async def generate(self, prompt: str, context: dict) -> dict:
        """
        Return deterministic response based on prompt matching.
        """
        self.call_count += 1
        
        # Match prompt to scenario
        for scenario in self.scenarios:
            if scenario['match'] in prompt:
                return {
                    'tool': scenario['tool'],
                    'parameters': scenario['parameters'],
                    'reasoning': scenario.get('reasoning', ''),
                    'latency_ms': scenario.get('latency_ms', 500)
                }
        
        # Default fallback
        return {
            'tool': 'hold',
            'parameters': {'seconds': 5},
            'reasoning': 'No matching scenario, defaulting to hold',
            'latency_ms': 100
        }
    
    def inject_delay(self, delay_ms: int):
        """Configure artificial latency for stress testing"""
        self.injected_delay = delay_ms
```

#### Scenario Definition Format

```yaml
# tests/scenarios/basic_mission.yaml
scenarios:
  - id: "takeoff_5m"
    match: "take off to 5 meters"
    tool: "arm_and_takeoff"
    parameters:
      altitude_m: 5.0
    reasoning: "User requested takeoff to 5 meters"
    latency_ms: 800
    
  - id: "goto_north_20m"
    match: "fly.*north.*20 meters"
    tool: "fly_body_offset"
    parameters:
      forward_m: 20.0
      right_m: 0.0
      up_m: 0.0
    reasoning: "Flying north 20 meters"
    latency_ms: 600
    
  - id: "land_now"
    match: "land"
    tool: "land"
    parameters: {}
    reasoning: "User requested landing"
    latency_ms: 400
```

### 7.4 Telemetry Replay Tests

```python
# tests/replay/telemetry_replay.py
class TelemetryReplay:
    """
    Replay recorded telemetry for regression testing.
    Useful for testing new code against historical flight data.
    """
    
    def __init__(self, recording_path: str):
        self.recording = self._load_recording(recording_path)
        self.index = 0
        
    def _load_recording(self, path: str) -> list:
        """Load telemetry recording from JSONL"""
        records = []
        with open(path) as f:
            for line in f:
                records.append(json.loads(line))
        return records
    
    async def replay(self, drone: System, speed_multiplier: float = 1.0):
        """
        Replay telemetry as if it were live.
        """
        for record in self.recording:
            # Simulate timestamp
            await asyncio.sleep(
                (record['timestamp'] - self._prev_timestamp) / speed_multiplier
            )
            
            # Inject into system
            await self._inject_telemetry(drone, record)
            
    async def _inject_telemetry(self, drone: System, record: dict):
        """Inject a telemetry record into mock system"""
        # Implementation depends on mock architecture
        pass
```

---

## 8. Test Matrices

### 8.1 Component Integration Test Matrix

| Test ID | Component | SITL | HITL | Field | Priority | Automated |
|---------|-----------|------|------|-------|----------|-----------|
| TEST-MAV-001 | Connection | X | X | | P0 | Yes |
| TEST-MAV-002 | Connection Recovery | X | X | | P0 | Yes |
| TEST-MAV-003 | Multi-System | X | | | P1 | Partial |
| TEST-MAV-004 | Connection Timeout | X | X | | P1 | Yes |
| TEST-MAV-005 | High Latency | X | | | P0 | Yes |
| TEST-CAM-001 | Stream Init | X | X | X | P0 | Partial |
| TEST-CAM-002 | Stream Resilience | X | X | | P1 | Partial |
| TEST-CAM-003 | YOLO Pipeline | X | X | X | P0 | Partial |
| TEST-CAM-004 | ByteTrack | X | X | | P1 | Partial |
| TEST-CAM-005 | State String | X | X | X | P0 | Partial |
| TEST-LLM-001 | LLM Init | X | | | P0 | Yes |
| TEST-LLM-002 | Tool Schema | X | | | P0 | Yes |
| TEST-LLM-003 | Malformed Handling | X | | | P0 | Yes |
| TEST-LLM-004 | Latency Load | X | | | P1 | Yes |
| TEST-LLM-005 | Mock LLM | X | | | P0 | Yes |
| TEST-TEL-001 | Basic Telemetry | X | X | | P0 | Yes |
| TEST-TEL-002 | Concurrent | X | X | | P1 | Yes |
| TEST-TEL-003 | EKF Status | X | X | | P0 | Yes |
| TEST-TEL-004 | Rate Config | X | X | | P2 | Yes |
| TEST-TEL-005 | Mode Detection | X | X | X | P0 | Partial |

### 8.2 End-to-End Scenario Test Matrix

| Test ID | Scenario | SITL | HITL | Field | Priority | Automated |
|---------|----------|------|------|-------|----------|-----------|
| TEST-E2E-001 | Basic T/L | X | X | X | P0 | Partial |
| TEST-E2E-002 | Waypoint Mission | X | X | X | P0 | Partial |
| TEST-E2E-003 | Person Orbit | X | | X | P0 | Partial |
| TEST-E2E-004 | Person Follow | X | | X | P1 | Partial |
| TEST-E2E-005 | Brief Wi-Fi Loss | X | | X | P0 | Partial |
| TEST-E2E-006 | Extended Wi-Fi Loss | X | | X | P0 | Partial |
| TEST-E2E-007 | Packet Loss | X | | | P1 | Yes |
| TEST-E2E-008 | Takeoff Override | X | | X | P0 | Partial |
| TEST-E2E-009 | Offboard Override | X | | X | P0 | Partial |
| TEST-E2E-010 | RTL Override | X | | X | P0 | Partial |
| TEST-E2E-011 | Kill Switch | | X | X | P0 | Partial |
| TEST-E2E-012 | Low Battery Warn | X | X | | P1 | Yes |
| TEST-E2E-013 | Critical Battery RTL | X | | X | P0 | Yes |
| TEST-E2E-014 | Emergency Land | X | | X | P0 | Yes |

### 8.3 Stress Test Matrix

| Test ID | Stress Type | Duration | SITL | HITL | Priority | Automated |
|---------|-------------|----------|------|------|----------|-----------|
| TEST-STR-001 | Rapid Commands | 60s | X | | P1 | Yes |
| TEST-STR-002 | Concurrent LLM | 60s | X | | P1 | Yes |
| TEST-STR-003 | LLM Delay | 30s | X | | P0 | Yes |
| TEST-STR-004 | Mode Flood | 60s | X | | P1 | Yes |
| TEST-STR-005 | Offboard Storm | 60s | X | | P1 | Yes |
| TEST-STR-006 | Full Concurrency | 600s | X | X | P0 | Yes |
| TEST-STR-007 | Multi-Target | 120s | X | | P2 | Yes |
| TEST-STR-008 | Memory Long | 3600s | X | | P1 | Yes |
| TEST-STR-009 | High-Res Vision | 300s | | X | P2 | Partial |

### 8.4 Safety Test Matrix

| Test ID | Safety Feature | SITL | HITL | Field | Priority | Automated |
|---------|---------------|------|------|-------|----------|-----------|
| TEST-SAF-001 | Geofence H | X | | X | P0 | Partial |
| TEST-SAF-002 | Geofence V | X | | | P0 | Yes |
| TEST-SAF-003 | Geofence Recovery | X | | | P1 | Yes |
| TEST-SAF-004 | Invalid Coords | X | X | | P0 | Yes |
| TEST-SAF-005 | Dangerous Alt | X | X | | P0 | Yes |
| TEST-SAF-006 | Invalid Velocity | X | X | | P1 | Yes |
| TEST-SAF-007 | JSON Injection | X | | | P1 | Yes |
| TEST-SAF-008 | Software Stop | X | | X | P0 | Yes |
| TEST-SAF-009 | Kill Switch | | X | X | P0 | Partial |
| TEST-SAF-010 | RTL Trigger | X | | X | P0 | Yes |
| TEST-SAF-011 | EKF Recovery | X | | | P0 | Yes |
| TEST-SAF-012 | Bridge Recovery | X | X | | P1 | Partial |
| TEST-SAF-013 | Vision Recovery | | X | | P1 | Partial |
| TEST-SAF-014 | LLM Recovery | | X | | P1 | Partial |
| TEST-SAF-015 | State Corruption | X | | | P2 | Partial |

---

## 9. Pass/Fail Criteria

### 9.1 Component Integration Pass Criteria

| Component | Metric | Target | Warning | Failure |
|-----------|--------|--------|---------|---------|
| **Connection** | Establish time | < 5s | 5-10s | > 10s |
| | Recovery time | < 10s | 10-30s | > 30s |
| | Latency (p99) | < 100ms | 100-500ms | > 500ms |
| **Camera** | Frame rate | >= 15 FPS | 10-15 FPS | < 10 FPS |
| | Latency | < 200ms | 200-500ms | > 500ms |
| | Drop rate | < 1% | 1-5% | > 5% |
| **YOLO** | Inference | < 100ms | 100-200ms | > 200ms |
| | Detection rate | > 95% | 90-95% | < 90% |
| | Memory | Stable | < 10% growth | > 10% growth |
| **LLM** | Cold start | < 10s | 10-20s | > 20s |
| | Warm latency | < 2s | 2-5s | > 5s |
| | Valid JSON | > 99% | 95-99% | < 95% |
| **Telemetry** | Update rate | Configured ±10% | ±25% | > ±25% |
| | Freshness | < 2s | 2-5s | > 5s |

### 9.2 End-to-End Pass Criteria

| Scenario | Metric | Target | Warning | Failure |
|----------|--------|--------|---------|---------|
| **Takeoff/Land** | Altitude error | ± 0.5m | ± 1m | > ± 1m |
| | Time to target | < 30s | 30-60s | > 60s |
| | Hover stability | σ < 0.3m | σ < 0.5m | σ > 0.5m |
| **Waypoint** | Position error | < 2m | 2-5m | > 5m |
| | Arrival detection | < 3s | 3-10s | > 10s |
| **Vision Orbit** | ID persistence | > 95% | 90-95% | < 90% |
| | Orbit radius | ± 2m | ± 3m | > ± 3m |
| | Frame center rate | > 70% | 50-70% | < 50% |
| **Network Loss** | Failsafe trigger | < 1s | 1-3s | > 3s |
| | Recovery | < 10s | 10-30s | > 30s |
| **RC Override** | Mode switch | < 500ms | 500ms-1s | > 1s |
| | Control authority | Immediate | < 1s | > 1s |

### 9.3 Stress Test Pass Criteria

| Test Type | Metric | Target | Warning | Failure |
|-----------|--------|--------|---------|---------|
| **Rapid Commands** | Offboard timeout | 0 | 1 | > 1 |
| | Setpoint consistency | 100% | 95-100% | < 95% |
| **Concurrency** | CPU usage | < 70% | 70-85% | > 85% |
| | Memory growth | < 5%/hr | 5-10%/hr | > 10%/hr |
| | Frame drops | < 2% | 2-10% | > 10% |
| **LLM Delay** | Heartbeat maintained | Yes | Degraded | Fails |
| | Safe fallback | Immediate | < 5s | > 5s |
| **Memory** | Growth rate | < 10%/hr | 10-20%/hr | > 20%/hr |
| | OOM events | 0 | 0 | > 0 |

### 9.4 Safety Test Pass Criteria

| Safety Feature | Metric | Target | Warning | Failure |
|---------------|--------|--------|---------|---------|
| **Geofence** | Breach prevention | 100% | 95-100% | < 95% |
| | Action time | < 1s | 1-3s | > 3s |
| | Recovery | Yes | Partial | No |
| **Invalid Commands** | Rejection rate | 100% | 95-100% | < 95% |
| | No execution | Yes | - | No |
| **Emergency Stop** | Response time | < 500ms | 500ms-1s | > 1s |
| | Motion cessation | < 1s | 1-3s | > 3s |
| **Recovery** | Detection time | < 5s | 5-15s | > 15s |
| | Full recovery | < 15s | 15-30s | > 30s |

### 9.5 Test Completion Criteria

A test run is considered **PASSED** when:

1. **All P0 tests** pass without warnings
2. **> 95% of P1 tests** pass
3. No critical failures in safety tests
4. Performance metrics within target bounds
5. No resource leaks detected
6. Logs complete and reviewable

A test run is **FAILED** when:

1. Any P0 test fails
2. Safety test produces dangerous behavior
3. > 20% of P1 tests fail
4. Resource leak detected
5. Performance degradation > 50% from baseline
6. Unhandled exceptions in flight-critical paths

---

## 10. Risk Assessment & Mitigations

### 10.1 Testing Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **SITL/Real Behavior Divergence** | Medium | High | HITL validation mandatory; parameter matching |
| **Test Induced Flyaway** | Low | Critical | Geofence always active; kill switch ready; tethered tests |
| **Hardware Damage During Test** | Medium | Medium | Props-off for bench; low altitude; insurance |
| **Network Instability Affecting Results** | High | Medium | Multiple runs; statistical analysis; controlled network |
| **LLM Non-Determinism** | High | Medium | Mock LLM for regression; statistical testing |
| **Resource Exhaustion** | Medium | Medium | Resource monitoring; test timeouts; cleanup |
| **Incomplete Test Coverage** | Medium | High | Coverage analysis; risk-based prioritization; reviews |

### 10.2 Safety Protocol for Field Tests

```
FIELD TEST SAFETY CHECKLIST

Before Each Field Test:
□ Pre-flight inspection completed
□ Geofence configured and tested
□ Kill switch functional
□ RC transmitter charged, range checked
□ Battery >= 80% charge
□ Weather conditions acceptable
□ Safety area cleared (> 30m radius)
□ Spotter assigned and briefed
□ Emergency procedures reviewed
□ Insurance documentation current

During Test:
□ RC pilot maintains visual contact
□ Test director monitors telemetry
□ Emergency stop capability confirmed
□ No spectators within safety zone
□ Communication established (radio/hand signals)

After Test:
□ Disarm and secure vehicle
□ Download and preserve logs
□ Inspect for damage
□ Document any anomalies
```

### 10.3 Test Escalation Path

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST ESCALATION                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Level 1: SITL Only                                        │
│  - All new tests start here                                │
│  - Safe to run in CI/CD                                    │
│  - Validates logic and timing                              │
│                                                             │
│         ↓ After 10 successful SITL runs                  │
│                                                             │
│  Level 2: HITL (Props Off)                                 │
│  - Pixhawk on bench                                        │
│  - Serial communication timing                             │
│  - Parameter validation                                    │
│                                                             │
│         ↓ After 5 successful HITL runs                     │
│                                                             │
│  Level 3: HITL (Props On, Tethered)                        │
│  - Real motors, constrained                                │
│  - Vibration profile validation                            │
│  - Current draw measurement                                │
│                                                             │
│         ↓ After 3 successful tethered runs                 │
│                                                             │
│  Level 4: Field Test (Low Altitude)                        │
│  - < 5m altitude                                           │
│  - Limited radius                                          │
│  - Direct RC supervision                                   │
│                                                             │
│         ↓ After 3 successful low-altitude runs             │
│                                                             │
│  Level 5: Full Mission Test                                │
│  - Full altitude                                           │
│  - Full mission profile                                    │
│  - All safety systems active                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 10.4 Incident Response

| Severity | Definition | Response | Documentation |
|----------|------------|----------|---------------|
| **Critical** | Crash, flyaway, injury | Immediate stand-down; incident report within 24h; investigation | Full report to safety officer |
| **High** | Close approach to boundary, unexpected mode change | Pause testing; root cause analysis; resume after fix | Incident log + fix verification |
| **Medium** | Test failure, performance degradation | Log and schedule fix; continue other tests | Test failure report |
| **Low** | Warnings, minor anomalies | Log for review; aggregate in weekly report | Weekly summary |

---

## Appendices

### Appendix A: PX4 Parameter Checklist for Testing

```yaml
# Safety-critical parameters to verify before field tests
com_of_loss_t: 0.5          # Offboard timeout
com_obl_rc_act: 4           # Offboard loss action (Land=4)
com_rc_override: 3          # RC override enable
nav_rcl_act: 2              # RC loss action (RTL=2)
nav_dll_act: 3              # Data link loss action
bat_low_thr: 25             # Low battery threshold
bat_crit_thr: 15            # Critical battery threshold
bat_emergen_thr: 10          # Emergency battery threshold
gf_max_hor_dist: 500        # Geofence horizontal (m)
gf_max_ver_dist: 120        # Geofence vertical (m)
gf_action: 2                # Geofence breach action (Hold=2)
```

### Appendix B: Test Data Format

```json
{
  "test_id": "TEST-E2E-001",
  "timestamp": "2026-04-09T14:30:00Z",
  "environment": "SITL",
  "result": "PASS",
  "metrics": {
    "takeoff_time_ms": 8500,
    "altitude_error_m": 0.2,
    "hover_stability_m": 0.15,
    "landing_time_ms": 12000
  },
  "logs": [
    {
      "time": "14:30:01.234Z",
      "level": "INFO",
      "message": "Pre-arm checks passed"
    }
  ],
  "anomalies": [],
  "artifacts": [
    "flight_log.ulg",
    "telemetry.jsonl",
    "video_capture.mp4"
  ]
}
```

### Appendix C: Testing Tools Reference

| Tool | Purpose | Usage |
|------|---------|-------|
| `px4-sitl` | Software-in-loop simulation | `make px4_sitl_default jmavsim` |
| `mavsdk_server` | MAVLink backend | `mavsdk_server -p 50051` |
| `QGroundControl` | Mission planning, log analysis | GUI tool |
| `mavlogdump.py` | Log parsing | `python -m pymavlink.mavlogdump` |
| `tc/netem` | Network impairment | `tc qdisc add dev eth0 netem delay 100ms` |
| `pytest` | Test execution | `pytest tests/integration/` |
| `pytest-asyncio` | Async test support | Decorator: `@pytest.mark.asyncio` |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-04-09 | QA Engineering | Initial draft |
| 1.0 | 2026-04-09 | QA Engineering | Complete test plan |

---

**Next Steps:**
1. Review and approve test plan with engineering team
2. Set up SITL CI/CD pipeline
3. Implement mock LLM and test infrastructure
4. Begin with TEST-MAV-001 through TEST-MAV-005
5. Schedule first HITL session after 10 successful SITL runs

**Related Documents:**
- `/Users/muadhsambul/Downloads/Project-Avatar/project_avatar_prd.md`
- `/Users/muadhsambul/Downloads/Project-Avatar/project_avatar_technical.md`
- `/Users/muadhsambul/Downloads/Project-Avatar/research/mavsdk_px4_deep_dive.md`
- `/Users/muadhsambul/Downloads/Project-Avatar/research/rc_failsafe_emergency.md`
