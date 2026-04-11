# Drone Safety Standards and Certification Requirements

**Document Type:** Research & Compliance Reference  
**Target:** UAV/Drone Software Systems with LLM Integration  
**Date:** April 2026  
**Classification:** Safety-Critical Systems Guidance

---

## Table of Contents

1. [Applicable Standards Overview](#1-applicable-standards-overview)
2. [ASTM F38: UAS Autonomy and Control Standards](#2-astm-f38-uas-autonomy-and-control-standards)
3. [ISO 21384: UAS Operational Procedures](#3-iso-21384-uas-operational-procedures)
4. [FAA Part 107: Operational Requirements](#4-faa-part-107-operational-requirements)
5. [Code Quality Gates for Drone Software](#5-code-quality-gates-for-drone-software)
6. [Safety Validation Checklist](#6-safety-validation-checklist)
7. [Implementation Guidance](#7-implementation-guidance)

---

## 1. Applicable Standards Overview

### Standards Hierarchy for UAV Software

```
Safety-Critical Level
├── DO-178C (Aviation Software Safety) - DAL C/D
├── ARP 4761 (Safety Assessment)
└── ARP 4754A (Development Process)

Operational Standards
├── ISO 21384-1/2/3 (UAS Operations)
├── ASTM F38 Series (Autonomy & Classification)
└── JARUS SORA (Risk Assessment)

Regulatory Requirements
├── FAA Part 107 (Small UAS Rules - US)
├── EASA Easy Access Rules (EU)
└── Local Aviation Authority Requirements
```

### Compliance Priority Matrix

| System Component | Primary Standard | DAL Level | Priority |
|------------------|------------------|-----------|----------|
| Flight Control | DO-178C | DAL C | Critical |
| Autonomy/AI Decision Layer | ASTM F38 | N/A | High |
| Emergency Response | DO-178C | DAL B | Critical |
| Geofencing | DO-178C | DAL C | High |
| RC Override | DO-178C | DAL B | Critical |
| Battery Monitor | DO-178C | DAL C | High |
| Telemetry | ISO 21384-1 | N/A | Medium |

---

## 2. ASTM F38: UAS Autonomy and Control Standards

### 2.1 Standard Family Structure

**ASTM F38 Committee** covers UAS standards including:
- **F2908-17**: Standard Practice for Maintenance of Unmanned Aircraft Systems
- **F2909-13**: Standard Practice for Maintenance of Light Sport Aircraft
- **F3002-14**: Standard Specification for Design of Unmanned Aircraft Systems
- **F3003-14**: Standard Practice for Unmanned Aircraft Systems (UAS) Visual Range
- **F3005-16**: Standard Practice for Unmanned Aircraft Systems (UAS) Sense and Avoid

### 2.2 Autonomy Classification Framework

ASTM defines UAS autonomy levels through capability assessment:

| Level | Designation | Human Oversight | LLM Integration Risk |
|-------|-------------|-----------------|---------------------|
| 0 | Manual Control | Continuous | Low |
| 1 | Assisted Control | Continuous | Low |
| 2 | Partial Autonomy | Periodic | Medium |
| 3 | Conditional Autonomy | On-Demand | **HIGH** |
| 4 | High Autonomy | Supervisory | **CRITICAL** |
| 5 | Full Autonomy | None | **PROHIBITED** |

### 2.3 Safety Requirements for Autonomous Systems

#### F3061 - Flight Control System Requirements

**Core Requirements:**
1. **Fail-Safe Design**: All autonomy systems must have deterministic failsafe modes
2. **Hierarchical Control**: Hard-wired safety reflexes must outrank software decisions
3. **State Verification**: Continuous validation of system state against expected parameters
4. **Degradation Path**: Graceful degradation through defined states

#### Key Safety Principles

```
┌─────────────────────────────────────────────────────────────┐
│  ASTM F38 Safety Architecture Principles                      │
├─────────────────────────────────────────────────────────────┤
│  1. Independence: Safety-critical functions independent of   │
│     primary autonomy logic                                   │
│                                                              │
│  2. Determinism: Response to safety events must be            │
│     predictable and bounded                                   │
│                                                              │
│  3. Isolation: Safety-critical systems run on isolated      │
│     hardware/software paths                                   │
│                                                              │
│  4. Monitoring: Continuous monitoring of autonomy decisions   │
│     against safety envelopes                                  │
│                                                              │
│  5. Override: Human/RC override must always be possible       │
│     and take precedence                                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 Testing Protocols

**ASTM F38 Testing Requirements:**

1. **Validation Testing**: Verify system meets specification
2. **Verification Testing**: Verify implementation meets design
3. **HIL Testing**: Hardware-in-the-loop for control systems
4. **SIL Testing**: Software-in-the-loop for algorithm validation
5. **Field Testing**: Controlled operational environment testing

---

## 3. ISO 21384: UAS Operational Procedures

### 3.1 Standard Structure

ISO 21384 consists of three parts:

- **ISO 21384-1**: General Requirements and Procedures
- **ISO 21384-2**: Specific Requirements and Procedures for UAS Operating in the Specific Category
- **ISO 21384-3**: Specific Requirements and Procedures for UAS Operating in the Certified Category

### 3.2 Operational Risk Management (SORA Alignment)

The ISO standard incorporates the JARUS SORA (Specific Operations Risk Assessment) methodology:

```
SORA Risk Assessment Flow:

Step 1: Concept of Operations (ConOps)
        └── Define flight envelope, mission, environment

Step 2: Ground Risk Class (GRC)
        └── Population density + system reliability

Step 3: Air Risk Class (ARC)
        └── Airspace classification + traffic

Step 4: Strategic Mitigation
        └── Reduce GRC/ARC through operational controls

Step 5: Tactical Mitigation
        └── SAA, geofencing, real-time monitoring

Step 6: Specific Assurance and Integrity Level (SAIL)
        └── Aggregate risk determines SAIL I-VI

Step 7: Operational Safety Objectives
        └── Required evidence based on SAIL level
```

### 3.3 Critical Operational Requirements

#### ISO 21384-1: General Requirements

**Required Documentation:**
1. Operations Manual
2. Flight Procedures
3. Emergency Procedures
4. Maintenance Procedures
5. Training Requirements

**Required Safety Systems:**
1. **Geofencing**: Virtual boundaries with automatic response
2. **Lost Link Procedure**: Defined behavior on communication loss
3. **Emergency Recovery**: Return-to-home and landing protocols
4. **Flight Termination**: Ability to end flight if required

#### ISO 21384 Safety Objectives Table

| SAIL Level | Software Assurance | Hardware Reliability | Human Factors | Airworthiness |
|------------|-------------------|---------------------|---------------|---------------|
| I (Low) | Basic | Standard | Standard | Self-declared |
| II | Enhanced | Enhanced | Standard | Self-declared |
| III | Full | Full | Enhanced | Review |
| IV | Full + Independent | Full + Redundant | Full | Audit |
| V | DO-178C DAL D | Full + Redundant | Full | Certification |
| VI (High) | DO-178C DAL C/B | Full + Dissimilar | Full | Full Certification |

### 3.4 Personnel Requirements

**Remote Pilot Requirements:**
- Competency-based training
- Medical fitness (Class 2 minimum for SAIL III+)
- Knowledge of:
  - Airspace regulations
  - Emergency procedures
  - System limitations
  - Weather assessment

---

## 4. FAA Part 107: Operational Requirements

### 4.1 Regulatory Framework

FAA Part 107 (14 CFR Part 107) governs small UAS operations in the United States National Airspace System (NAS).

### 4.2 Operational Limits

| Parameter | Standard Limit | Waiver Available |
|-----------|---------------|------------------|
| Altitude | 400 ft AGL | Yes |
| Speed | 100 mph (87 knots) | No |
| Visual Line of Sight | Required | Yes (BVLOS) |
| Time of Day | Daylight only | Yes (twilight) |
| Operations Over People | Prohibited | Yes (Category 1-4) |
| Moving Vehicle Operations | Prohibited | Yes |
| Airspace Authorization | Required (B/C/D/E surface) | Automatic via LAANC |

### 4.3 Remote Pilot Certificate Requirements

**Eligibility:**
- 16 years of age or older
- English language proficiency
- Pass Aeronautical Knowledge Test
- TSA vetting

**Recurrent Requirements:**
- Online training every 24 months
- Updates on regulations and procedures

### 4.4 Aircraft Requirements

**Registration:**
- All UAS > 250g must be registered
- Registration displayed on aircraft
- 3-year renewal cycle

**Remote ID (Effective March 2024):**
- Standard Remote ID broadcast required for most operations
- Broadcast: Identification, location, altitude, velocity
- Exceptions: FAA-recognized identification areas (FRIAs), operations < 400 ft from controlling station

### 4.5 Operational Categories (49 USC 44834)

| Category | Over People | Night | Moving Vehicle | Requirements |
|------------|-------------|-------|----------------|--------------|
| 0 | No | No | No | Basic Part 107 |
| 1 | Yes (no injury) | No | No | < 0.55 lb, no rotating parts exposed |
| 2 | Yes (no serious injury) | No | No | Conform to injury threshold, decalared compliance |
| 3 | Yes (no catastrophic injury) | No | No | Conform to higher threshold, TC/PC |
| 4 | Yes | Yes | Yes | Airworthiness certificate, approved maintenance |

### 4.6 Beyond Visual Line of Sight (BVLOS)

**Current Waiver Requirements:**
- Proposed mitigation for loss of visual contact
- Detect and Avoid (DAA) capability
- Communication link reliability
- Operational procedures and training

**AC 89-1A Guidance:**
- Acceptable means of compliance for BVLOS
- Risk-based approach to approvals
- Industry consensus standards accepted

---

## 5. Code Quality Gates for Drone Software

### 5.1 DO-178C Software Development Assurance

DO-178C "Software Considerations in Airborne Systems and Equipment Certification" is the primary standard for aviation software.

#### Development Assurance Levels (DAL)

| DAL | Failure Effect | Coverage Required | MC/DC Required |
|-----|---------------|-------------------|----------------|
| A | Catastrophic | 100% | Yes |
| B | Hazardous | 100% | Yes |
| C | Major | 100% | No |
| D | Minor | Coverage analysis | No |
| E | No Effect | N/A | No |

#### Recommended DAL for Drone Systems

| System | Recommended DAL | Rationale |
|--------|----------------|-----------|
| Flight Control Loop | DAL C/B | Loss of control = major/hazardous |
| Emergency Response | DAL B | Must work when needed |
| RC Override Path | DAL B | Critical safety function |
| Geofencing | DAL C | Loss = major consequence |
| Autonomy Planning | DAL C | Indirect safety impact |
| LLM Interface Layer | DAL D | Non-safety, monitored |
| Telemetry | DAL E | No safety effect |

### 5.2 Testing Coverage Requirements

#### Minimum Coverage by DAL

```
DAL C Requirements:
├── Statement Coverage: 100%
├── Decision Coverage: 100%
├── Function Coverage: 100%
└── MC/DC: Not required

DAL B Requirements:
├── Statement Coverage: 100%
├── Decision Coverage: 100%
├── MC/DC: 100%
├── Function Coverage: 100%
└── Data Coupling: Analyzed
```

#### Coverage Measurement Tools

Recommended stack:
- **C/C++**: gcov/lcov + bullseye (for MC/DC)
- **Python**: coverage.py + branch coverage
- **Rust**: cargo-tarpaulin + grcov
- **Embedded**: Custom instrumentation + hardware trace

### 5.3 Static Analysis Recommendations

#### Required Static Analysis

| Tool Category | Examples | Purpose |
|--------------|----------|---------|
| Linters | pylint, clippy, cppcheck | Basic defect detection |
| Semantic Analysis | SonarQube, Coverity, CodeSonar | Deep defect detection |
| Formal Methods | SPARK, Astree, Polyspace | Mathematical verification |
| Coding Standards | MISRA C:2012, JSF AV C++, CERT C | Enforce safe subset |

#### MISRA C:2012 Compliance (for embedded C)

**Critical Rules for Safety:**
- Rule 1.1: All code shall conform to ISO/IEC 9899:1999
- Rule 4.2: Trigraphs shall not be used
- Rule 17.2: Functions shall not call themselves, directly or indirectly
- Rule 21.3: Memory allocation/deallocation shall not occur after initialization

### 5.4 Runtime Assertion Patterns

#### Safety-Critical Assertion Strategy

```python
# Pattern 1: Defensive Precondition Checks
def set_motor_speed(motor_id: int, speed: float) -> None:
    """Set motor speed with safety checks."""
    # Hard assertions - always active in production
    assert 0 <= motor_id < MOTOR_COUNT, f"Invalid motor: {motor_id}"
    assert -MAX_SPEED <= speed <= MAX_SPEED, f"Speed out of range: {speed}"
    
    # System state assertions
    assert system_state == SystemState.ARMED, "Motors only when armed"
    assert not emergency_stop_active, "Cannot set speed during ESTOP"
    
    _apply_motor_speed(motor_id, speed)

# Pattern 2: Watchdog Pattern
class SafetyWatchdog:
    def __init__(self, timeout_ms: int):
        self.timeout = timeout_ms
        self.last_ok = time.monotonic()
    
    def check_in(self, status: SystemStatus) -> None:
        """Safety-critical systems must check in periodically."""
        if status != SystemStatus.HEALTHY:
            self.trigger_failsafe()
        self.last_ok = time.monotonic()
    
    def verify(self) -> None:
        """Called by independent monitor."""
        if time.monotonic() - self.last_ok > self.timeout / 1000:
            self.trigger_failsafe()
```

#### Runtime Monitoring Requirements

1. **Stack Overflow Detection**: Hardware or software stack monitoring
2. **Memory Corruption Detection**: Heap guards, stack canaries
3. **Timing Monitoring**: Deadline monitoring for real-time tasks
4. **Hardware Health**: Temperature, voltage, sensor validity
5. **Watchdog Timer**: External reset if software hangs

### 5.5 Documentation Requirements

#### Required Documentation per DO-178C

| Document | DAL C | DAL B | Description |
|----------|-------|-------|-------------|
| Plan for Software Aspects of Certification (PSAC) | Required | Required | Overall certification plan |
| Software Development Plan (SDP) | Required | Required | Development process |
| Software Verification Plan (SVP) | Required | Required | Verification strategy |
| Software Configuration Management Plan (SCMP) | Required | Required | CM procedures |
| Software Quality Assurance Plan (SQAP) | Required | Required | QA activities |
| Software Requirements Data (SRD) | Required | Required | Software requirements |
| Software Design Description (SDD) | Required | Required | Architecture/design |
| Source Code | Required | Required | Implementation |
| Object Code | Required | Required | Executable |
| Software Verification Cases and Procedures (SVCP) | Required | Required | Test cases |
| Software Verification Results (SVR) | Required | Required | Test results |
| Software Accomplishment Summary (SAS) | Required | Required | Compliance summary |

#### Code Documentation Standards

**Docstring Requirements:**
```python
def compute_failsafe_landing_site(
    current_position: GPSPosition,
    battery_remaining: float,
    wind_speed: float
) -> LandingSite:
    """
    Compute optimal landing site for emergency landing.
    
    Safety Level: DAL C
    Requirements: SRD-4.2.1, SRD-4.2.2, SRD-4.2.3
    Test Cases: SVCP-0421 through SVCP-0456
    
    Args:
        current_position: Current GPS position (WGS84)
        battery_remaining: Remaining battery percentage (0-100)
        wind_speed: Current wind speed in m/s
    
    Returns:
        LandingSite: Selected landing coordinates and approach path
    
    Raises:
        FailsafeError: If no valid landing site within range
    
    Note:
        This function runs on the safety-critical path and must
        complete within 100ms worst-case execution time.
    """
```

---

## 6. Safety Validation Checklist

### 6.1 Hard Reflex Independence from LLM

**Critical Requirement**: Safety-critical reflexes must be independent of LLM processing.

#### Validation Checklist

| Check | Method | Evidence |
|-------|--------|----------|
| Hardware isolation | Schematic review | Separate MCU/FPGA |
| Software isolation | Code review | No shared memory |
| Timing isolation | WCET analysis | < 10ms response |
| Power isolation | Power analysis | Independent rail |
| Communication isolation | Protocol review | One-way safety bus |

#### Implementation Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                    SAFETY REFLEX PATH                        │
│                     (Independent Hardware)                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Sensor ──► Safety MCU ──► Actuator Driver ──► Motors       │
│     │           │                                              │
│     │           └──► Failsafe Logic (Deterministic)          │
│     │                - Watchdog timeout                       │
│     │                - Geofence breach                       │
│     │                - RC loss                               │
│     │                - Low battery                           │
│     │                                                        │
│     └── Health Check ──► One-way to Main CPU                │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    MAIN CONTROL PATH                         │
│                     (LLM Integration Allowed)                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Main CPU ──► LLM Processing ──► Command Queue              │
│     │                              │                        │
│     └──► Safety Monitor ◄──────────┘                        │
│              │                                               │
│              └── Can veto any command                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Test Requirements

1. **LLM Failure Injection**: Verify safety reflexes function during LLM failure
2. **Command Flooding**: Verify safety system handles high-rate LLM output
3. **Malicious Commands**: Verify safety system rejects dangerous LLM suggestions
4. **Latency Tests**: Verify safety reflex < 50ms regardless of LLM load

### 6.2 RC Override Verification

**Critical Requirement**: RC override must always be available and take precedence.

#### Validation Checklist

| Test | Procedure | Pass Criteria |
|------|-----------|---------------|
| Override availability | Power cycle with RC off, then on | RC recognized within 2s |
| Override priority | Send conflicting commands | RC wins 100% of time |
| Override latency | Scope RC input to motor output | < 20ms end-to-end |
| Override during failsafe | Trigger failsafe, apply RC | RC takes control |
| Override during LLM op | Active LLM control, use RC | Immediate override |
| Loss of RC | Remove RC signal | Enter lost-link mode |
| Recovery of RC | Restore RC after loss | Resume RC control |

#### Code Review Checklist

```python
# Anti-pattern: Never do this
def process_commands():
    if llm_command:
        execute(llm_command)  # Dangerous: no RC check
    elif rc_command:
        execute(rc_command)

# Correct pattern: RC always checked first
def process_commands():
    # RC override has highest priority
    if rc_active and rc_fresh:
        return rc_command
    
    # Safety monitor second priority
    if safety_active:
        return safety_command
    
    # Autonomy only if both above clear
    if autonomy_enabled:
        return autonomy_command
    
    return hover_command
```

### 6.3 Geofencing Enforcement

**Critical Requirement**: Geofencing must be enforced by safety-critical systems.

#### Geofence Types

| Type | Enforcement | Response |
|------|-------------|----------|
| Altitude ceiling | Hard limit | Descend + notify |
| Horizontal boundary | Hard limit | Return + notify |
| No-fly zone | Hard limit | Stop + hover/land |
| Dynamic geofence | Hard limit | Adapt in real-time |

#### Validation Checklist

| Test | Scenario | Expected Response |
|------|----------|-------------------|
| Altitude breach | Climb toward ceiling | Stop at ceiling - 10m margin |
| Boundary breach | Fly toward boundary | Turn back at boundary - 20m margin |
| NFZ entry | Approach no-fly zone | Stop + hover at NFZ boundary |
| GPS degradation | GPS accuracy degrades | Expand margins + alert pilot |
| Geofence update | New geofence in flight | Accept if no immediate violation |
| Emergency NFZ | Pop-up restricted zone | Immediate compliance or land |

#### Enforcement Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   GEOFENCE ENFORCEMENT                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    │
│   │ Position    │───►│ Geofence     │───►│ Violation?  │    │
│   │ Source      │    │ Engine       │    │ Assessment  │    │
│   │ (GPS + INS) │    │              │    │             │    │
│   └─────────────┘    └──────────────┘    └──────┬──────┘    │
│                                                  │           │
│                           ┌─────────────────────┘           │
│                           ▼                                   │
│                    ┌──────────────┐                          │
│                    │  Boundary    │                          │
│                    │  Proximity   │                          │
│                    │  Check       │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│              ┌────────────┼────────────┐                      │
│              ▼            ▼            ▼                   │
│        ┌─────────┐   ┌──────────┐  ┌──────────┐             │
│        │ > Margin│   │ At Margin│  │ Violation│             │
│        │ Normal  │   │ Warning  │  │ Action   │             │
│        │ Ops     │   │ Alert    │  │ Required │             │
│        └─────────┘   └──────────┘  └──────────┘             │
│                                                              │
│  Violation Actions (Hard-wired):                             │
│  - Altitude: Descend to safe altitude                          │
│  - Boundary: Turn toward home                                │
│  - NFZ: Immediate hover or land                              │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 6.4 Failsafe Testing Requirements

#### Required Failsafe Scenarios

| Failsafe Type | Trigger Condition | Response | Test Method |
|--------------|-------------------|----------|-------------|
| Low Battery | < 25% capacity | Return-to-home | Battery simulator |
| Critical Battery | < 10% capacity | Immediate landing | Battery simulator |
| RC Loss | No signal > 3s | Lost-link procedure | RF shielding |
| GPS Loss | < 4 satellites | Altitude hold, manual mode | GPS simulator |
| Telemetry Loss | No GCS link > 10s | Continue if RC ok | Network disconnect |
| Geofence Violation | Breach of boundary | Return-to-home | Position spoof |
| Wind Limit | > max wind speed | Land immediately | Wind tunnel/sim |
| Motor Failure | Current anomaly | Emergency landing | Inject fault |
| Sensor Failure | Invalid sensor data | Redundant sensor switch | Sensor fault inject |
| LLM Failure | Timeout or error | Revert to RC/autopilot | Process kill |

#### Failsafe Test Protocol

```python
# Example failsafe test suite structure
class FailsafeTests:
    """
    Safety-critical failsafe test suite.
    Run before every flight firmware release.
    """
    
    def test_rc_loss_failsafe(self):
        """Verify RTH triggers on RC loss."""
        # Arrange
        self.arm_and_takeoff()
        initial_position = self.get_position()
        
        # Act
        self.simulate_rc_loss(duration=5)  # > 3s threshold
        
        # Assert
        assert self.get_mode() == FlightMode.RTH
        assert self.is_returning_to_home()
        assert self.rc_loss_timer == 0  # Reset when RC restored
    
    def test_battery_failsafe_sequence(self):
        """Verify staged battery response."""
        # Low battery - RTH
        self.set_battery_level(25)
        assert self.get_mode() == FlightMode.RTH
        
        # Critical battery - Land now
        self.set_battery_level(10)
        assert self.get_mode() == FlightMode.LAND
        assert self.get_landing_velocity() < MAX_LANDING_RATE
    
    def test_geofence_breach(self):
        """Verify geofence enforcement."""
        self.arm_and_takeoff()
        
        # Attempt to breach
        self.set_simulated_position(GEOFENCE_BOUNDARY + 10)
        
        # Must not actually breach
        actual = self.get_position()
        assert actual.distance_from(GEOFENCE_BOUNDARY) > -5  # 5m margin
        assert self.get_mode() == FlightMode.RTH
    
    def test_llm_timeout_failsafe(self):
        """Verify safe state on LLM failure."""
        self.enable_llm_mode()
        self.arm_and_takeoff()
        
        # Kill LLM process
        self.kill_llm_process()
        
        # Should revert to autopilot hover
        assert self.get_mode() == FlightMode.HOVER
        assert self.get_control_source() == ControlSource.AUTOPILOT
        assert not self.llm_active()
```

---

## 7. Implementation Guidance

### 7.1 Safety Architecture for LLM-Integrated Drones

#### Recommended Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        SYSTEM ARCHITECTURE                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────┐         ┌──────────────────┐                   │
│  │   RC Receiver    │         │   Telemetry      │                   │
│  │   (SBUS/CRSF)    │         │   (MAVLink)      │                   │
│  └────────┬─────────┘         └────────┬─────────┘                   │
│           │                            │                            │
│           ▼                            ▼                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │               SAFETY MCU / FLIGHT CONTROLLER              │       │
│  │  ┌────────────────────────────────────────────────────┐  │       │
│  │  │         HARD SAFETY REFLEXES (DAL B/C)              │  │       │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │       │
│  │  │  │ Watchdog    │  │ Geofence    │  │ Emergency  │  │  │       │
│  │  │  │ Monitor     │  │ Enforcer    │  │ Landing    │  │  │       │
│  │  │  │             │  │             │  │ Logic      │  │  │       │
│  │  │  └─────────────┘  └─────────────┘  └────────────┘  │  │       │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │       │
│  │  │  │ RC Override │  │ Failsafe    │  │ Kill       │  │  │       │
│  │  │  │ Handler     │  │ Scheduler   │  │ Switch     │  │  │       │
│  │  │  └─────────────┘  └─────────────┘  └────────────┘  │  │       │
│  │  └────────────────────────────────────────────────────┘  │       │
│  │                           │                              │       │
│  │                           ▼                              │       │
│  │  ┌────────────────────────────────────────────────────┐  │       │
│  │  │         FLIGHT CONTROL LOOP (DAL C)                 │  │       │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │  │       │
│  │  │  │ Attitude    │  │ Position    │  │ Mixer      │   │  │       │
│  │  │  │ Control     │  │ Control     │  │            │   │  │       │
│  │  │  └─────────────┘  └─────────────┘  └────────────┘   │  │       │
│  │  └────────────────────────────────────────────────────┘  │       │
│  └───────────────────────────┬──────────────────────────────┘       │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    MAIN COMPUTER (Linux/ROS2)                   │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │   │
│  │  │ Autopilot        │  │ Safety Monitor   │                 │   │
│  │  │ (PX4/ArduPilot)  │  │ (DAL D)          │                 │   │
│  │  │                  │  │ - Validates LLM  │                 │   │
│  │  │                  │  │ - Enforces limits  │                 │   │
│  │  └──────────────────┘  └──────────────────┘                 │   │
│  │            ▲                    ▲                              │   │
│  │            │                    │                              │   │
│  │  ┌────────┴────────────────────┴──────────┐                 │   │
│  │  │     LLM INTEGRATION LAYER (DAL D/E)     │                 │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌────────┐  │                 │   │
│  │  │  │ Natural  │  │ Command  │  │ Safety │  │                 │   │
│  │  │  │ Language │─►│ Parser   │─►│ Filter │  │                 │   │
│  │  │  │ Model    │  │          │  │        │  │                 │   │
│  │  │  └──────────┘  └──────────┘  └────────┘  │                 │   │
│  │  └─────────────────────────────────────────┘                 │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │                      ACTUATORS / MOTORS                        │     │
│  │  - Controlled only by Safety MCU                               │     │
│  │  - No direct connection to LLM system                          │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘

Key Principles:
1. Safety MCU is the single point of control for actuators
2. LLM outputs are advisory and must pass through safety validation
3. RC always has highest priority
4. Safety reflexes run on isolated hardware with no LLM dependency
```

### 7.2 Code Review Checklist

#### Pre-Flight Release Checklist

| Category | Item | Status |
|----------|------|--------|
| **Architecture** |||
| | Safety reflexes isolated from LLM | [ ] |
| | RC override hard-wired and highest priority | [ ] |
| | Geofence enforcement in safety-critical path | [ ] |
| | Kill switch independent of main processor | [ ] |
| **Code Quality** |||
| | 100% statement coverage for DAL C code | [ ] |
| | 100% decision coverage for DAL C code | [ ] |
| | MISRA C:2012 compliance for embedded C | [ ] |
| | No dynamic memory allocation in safety paths | [ ] |
| | All assertions active in production | [ ] |
| **Testing** |||
| | All failsafe scenarios tested | [ ] |
| | RC override verified under load | [ ] |
| | Geofence breach tested | [ ] |
| | LLM failure injection tested | [ ] |
| | Hardware-in-the-loop tests passed | [ ] |
| **Documentation** |||
| | Requirements traced to code | [ ] |
| | Test cases traced to requirements | [ ] |
| | Safety analysis completed | [ ] |
| | Operating limitations documented | [ ] |

### 7.3 Regulatory Compliance Roadmap

#### Phase 1: Basic Compliance (Months 1-3)

- [ ] FAA Part 107 remote pilot certification
- [ ] Aircraft registration
- [ ] Remote ID compliance
- [ ] Operations manual
- [ ] Basic safety systems (geofencing, RTH)

#### Phase 2: Enhanced Operations (Months 4-9)

- [ ] Category 2/3 over-people certification
- [ ] BVLOS waiver application
- [ ] SORA risk assessment
- [ ] ISO 21384-1 compliance documentation
- [ ] Third-party safety audit

#### Phase 3: Full Certification (Months 10-18)

- [ ] DO-178C DAL C certification for flight control
- [ ] ASTM F38 compliance verification
- [ ] Type certificate (if applicable)
- [ ] Production certificate (if applicable)
- [ ] Category 4 operations (if required)

---

## Appendix A: Reference Standards

### Primary Standards

| Standard | Title | Application |
|----------|-------|-------------|
| DO-178C | Software Considerations in Airborne Systems | Aviation software development |
| DO-330 | Software Tool Qualification | Tool qualification |
| ISO 21384-1 | UAS - General Requirements | UAS operations |
| ISO 21384-2 | UAS - Specific Category | Medium risk operations |
| ISO 21384-3 | UAS - Certified Category | High risk/certified |
| ASTM F38 | UAS Standards | Autonomy and operations |
| 14 CFR Part 107 | Small UAS Rules | FAA regulations |
| JARUS SORA | Specific Operations Risk Assessment | Risk methodology |

### Supporting Standards

| Standard | Title | Purpose |
|----------|-------|---------|
| ARP 4754A | Development of Civil Aircraft Systems | System development |
| ARP 4761 | Safety Assessment | Safety analysis |
| MIL-STD-882E | Standard Practice for System Safety | Safety engineering |
| STANAG 4586 | NATO UAS Interface | Interoperability |
| STANAG 4671 | NATO UAS Airworthiness | Military airworthiness |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| AGL | Above Ground Level |
| ARC | Air Risk Class |
| BVLOS | Beyond Visual Line of Sight |
| ConOps | Concept of Operations |
| DAA | Detect and Avoid |
| DAL | Development Assurance Level |
| GCS | Ground Control Station |
| GRC | Ground Risk Class |
| HIL | Hardware-In-the-Loop |
| MC/DC | Modified Condition/Decision Coverage |
| NFZ | No-Fly Zone |
| RTH | Return-to-Home |
| SAIL | Specific Assurance and Integrity Level |
| SIL | Software-In-the-Loop |
| SORA | Specific Operations Risk Assessment |
| SRD | Software Requirements Data |
| UAS | Unmanned Aircraft System |
| VLOS | Visual Line of Sight |
| WCET | Worst-Case Execution Time |

---

*Document Version: 1.1*  
*Classification: Safety Reference*  
*Last Updated: April 2025 - Added PX4-specific failsafe configuration*

---

# Supplement: Project Avatar Practical Safety Implementation

**Date:** April 2025  
**Project:** Project Avatar - LLM-Controlled Autonomous UAV  
**Target:** University/R&D environment with ≤USD 500 hardware budget

---

## S1. Applicable Standards for Project Avatar

### S1.1 Standards Applicability Matrix

| Standard | Mandatory | Recommended | Not Applicable | Notes |
|----------|-----------|-------------|----------------|-------|
| FAA Part 107 | For outdoor ops | - | Indoor ops only | Educational waiver possible |
| ASTM F3362 (Remote ID) | If in controlled airspace | - | Indoor/uncontrolled | Budget ~USD 50-150 for module |
| ASTM F3445 (Operations) | - | Yes | - | Best practice framework |
| ISO 21384-3 | - | Yes | - | International framework |
| DO-178C | - | Principles only | Full compliance | R&D below 55 lbs exempt |
| PX4 Safety | - | Yes | - | Implemented in autopilot |

### S1.2 Project Avatar Context

Based on the technical documentation, Project Avatar has the following safety considerations:

- **Flight Stack:** PX4 autopilot on Pixhawk-class FC
- **Companion Computer:** Raspberry Pi 4 (4GB)
- **Ground Station:** MacBook Pro M3
- **Control Interface:** MAVSDK-Python with offboard mode
- **Vision:** YOLOv8-nano for object detection
- **Budget:** ≤USD 500 hardware constraint
- **Stages:** Stage 1 (basic), Stage 2 (vision), Stage 3 (depth + payload)

---

## S2. PX4 Fail-safe Configuration for Project Avatar

### S2.1 Critical Safety Parameters

Based on PX4 documentation research, the following parameters must be configured:

#### Offboard Mode Safety (Critical for LLM Integration)

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| COM_OBL_RC_ACT | 0 | 3 | Offboard loss action: Return to Land (RTL) |
| COM_OBL_ACT | 0 | 3 | Offboard loss action (alternative parameter) |
| COM_DL_LOSS_T | 10 | 10 | Datalink loss timeout: 10 seconds |
| COM_RC_LOSS_T | 0.5 | 5 | RC loss timeout: 5 seconds |

**Critical for LLM Operations:**
- PX4 requires a continuous "proof of life" signal at ≥ 2 Hz (COM_OBL_RC_ACT)
- If setpoint stream stops, PX4 will exit Offboard and execute failsafe
- COM_OBL_RC_ACT = 3 (Return to Land) is recommended for Project Avatar

#### RC and Datalink Loss

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| NAV_RCL_ACT | 2 | 3 | RC loss action: Return to Land |
| NAV_DLL_ACT | 0 | 3 | Datalink loss action: Return to Land |
| COM_POS_LOW_ACT | 0 | 2 | Low position accuracy: Hold mode |
| COM_POS_LOW_EPH | 10 | 10 | Horizontal position error threshold (m) |

#### Geofence Configuration

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| GF_ACTION | 2 | 3 | Geofence breach: Return mode |
| GF_MAX_HOR_DIST | 0 | 500 | Max horizontal distance: 500m (0 = disabled) |
| GF_MAX_VER_DIST | 0 | 100 | Max vertical distance: 100m (0 = disabled) |
| GF_SOURCE | 0 | 0 | Position source: Global Position |
| GF_PREDICT | 0 | 0 | Pre-emptive geofence: Disabled (experimental) |

**Note:** Setting GF_ACTION = 4 (Terminate) will kill the vehicle on geofence breach. This requires CBRK_FLIGHTTERM circuit breaker to be explicitly disabled.

#### Battery Failsafe (3-Level System)

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| COM_LOW_BAT_ACT | 0 | 3 | Low battery action: Return at critical, land at emergency |
| BAT_CRIT_THR | 0.07 | 0.20 | Critical battery threshold: 20% |
| BAT_EMERGEN_THR | 0.05 | 0.15 | Emergency battery threshold: 15% |
| BAT_WARN_THR | 0.10 | 0.25 | Warning battery threshold: 25% |

**Behavior with COM_LOW_BAT_ACT = 3:**
- Warning level (25%): GCS warning only
- Critical level (20%): Return to Land (RTL) triggered
- Emergency level (15%): Immediate landing

#### Return to Land Parameters

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| RTL_APPR_FORCE | 0 | 0 | Force RTL approach: No |
| RTL_TIME_FACTOR | 1.0 | 1.5 | RTL time estimate safety factor |
| RTL_TIME_MARGIN | 100 | 300 | RTL time margin: 300 seconds |
| RTL_ALT | 60 | 60 | RTL altitude: 60m |
| RTL_MIN_DIST | 5 | 5 | Minimum RTL trigger distance: 5m |

### S2.2 Recommended Parameter Set for QGroundControl

```bash
# Save as safety_params.params or apply via QGroundControl

# Offboard Safety
COM_OBL_RC_ACT,3
COM_OBL_ACT,3
COM_DL_LOSS_T,10
COM_RC_LOSS_T,5

# Link Loss
NAV_RCL_ACT,3
NAV_DLL_ACT,3
COM_POS_LOW_ACT,2
COM_POS_LOW_EPH,10

# Geofence (500m cylinder, 100m vertical)
GF_ACTION,3
GF_MAX_HOR_DIST,500
GF_MAX_VER_DIST,100
GF_SOURCE,0

# Battery Failsafe (3-level)
COM_LOW_BAT_ACT,3
BAT_CRIT_THR,0.20
BAT_EMERGEN_THR,0.15
BAT_WARN_THR,0.25

# RTL Settings
RTL_TIME_FACTOR,1.5
RTL_TIME_MARGIN,300
RTL_ALT,60

# Save parameters
param save
```

### S2.3 Preflight EKF and Sensor Health Checks

Based on PX4 EKF2 documentation, the following telemetry items must be checked before arming:

```python
# EKF Pre-flight Health Flags (from EstimatorStatus message)
pre_flight_checks = {
    'heading_ok': not estimator_status.pre_flt_fail_innov_heading,
    'height_ok': not estimator_status.pre_flt_fail_innov_height,
    'position_horiz_ok': not estimator_status.pre_flt_fail_innov_pos_horiz,
    'velocity_horiz_ok': not estimator_status.pre_flt_fail_innov_vel_horiz,
    'velocity_vert_ok': not estimator_status.pre_flt_fail_innov_vel_vert,
    'mag_field_ok': not estimator_status.pre_flt_fail_mag_field_disturbed,
}

# GPS Health Checks (from EstimatorGpsStatus message)
gps_checks = {
    'checks_passed': estimator_gps_status.checks_passed,
    'gps_fix_ok': not estimator_gps_status.check_fail_gps_fix,
    'sat_count_ok': not estimator_gps_status.check_fail_min_sat_count,
    'pdop_ok': not estimator_gps_status.check_fail_max_pdop,
    'horizontal_error_ok': not estimator_gps_status.check_fail_max_horz_err,
    'vertical_error_ok': not estimator_gps_status.check_fail_max_vert_err,
    'not_spoofed': not estimator_gps_status.check_fail_spoofed_gps,
    'drift_acceptable': estimator_gps_status.position_drift_rate_horizontal_m_s < 0.1,
}

# All checks must pass before arming
all_checks_passed = all(pre_flight_checks.values()) and all(gps_checks.values())
```

---

## S3. Operational Envelopes for Project Avatar

### S3.1 Weather Limits

| Parameter | Limit | Rationale |
|-----------|-------|-----------|
| Wind speed | < 10 m/s (22 mph) | PX4 position control limit for typical quadcopter |
| Wind gusts | < 15 m/s (33 mph) | Margin for sudden gusts |
| Visibility | ≥ 3 statute miles | Part 107 requirement, VLOS operations |
| Ceiling | ≥ 500 ft AGL | Margin above 400 ft operational limit |
| Temperature | -10°C to 40°C | Battery and electronics operating range |
| Precipitation | None | No water ingress protection on budget build |
| Solar condition | Daylight only | No lighting for nighttime ops |

### S3.2 Flight Envelope

| Parameter | Limit | Notes |
|-----------|-------|-------|
| Maximum altitude | 400 ft AGL | Part 107 limit; set GF_MAX_VER_DIST accordingly |
| Maximum speed | 15 m/s (33 mph) | Conservative for LLM operations |
| Maximum range | 500 m from home | Geofence limit for early development |
| Maximum flight time | 15 minutes | Conservative for initial missions |
| Minimum battery for RTL | 25% | Configured in BAT_CRIT_THR |
| Maximum bank angle | 30° | Conservative for stability |
| Maximum climb rate | 3 m/s | Conservative for battery conservation |
| Maximum descent rate | 2 m/s | Avoids ground effect and vortex ring state |

### S3.3 LLM Operational Constraints

| Parameter | Limit | Rationale |
|-----------|-------|-----------|
| LLM decision latency | < 2 seconds | Keep setpoint updates responsive |
| Command validation | Mandatory | All LLM commands validated against bounds |
| Human confirmation | Required (Stage 1-2) | Manual approval for novel commands |
| Geofence override | Disabled | LLM cannot disable safety boundaries |
| Offboard exit | RTL on loss | Automatic failsafe behavior |
| Setpoint streaming rate | ≥ 10 Hz | Ensure > 2 Hz minimum required by PX4 |

---

## S4. Pre-flight Checklists for Project Avatar

### S4.1 Hardware Pre-flight Checklist

| Item | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| Airframe integrity | Visual inspection | Check for cracks, damage | No visible damage |
| Propeller condition | Visual + spin test | Check for nicks, balance | No damage, spins freely |
| Motor functionality | Manual spin + power test | Spin by hand, check grinding | Smooth rotation, no binding |
| Battery condition | Visual + voltage check | Inspect swelling, measure voltage | No swelling, voltage > min |
| GPS module | Connection + signal check | Verify connection, check sat count | > 8 satellites, HDOP < 2.0 |
| RPi companion computer | Boot test | Power on, verify SSH access | Successful boot, accessible |
| Camera module | Image test | Capture test image | Clear image, correct orientation |
| Telemetry radio | Range test | Verify link at planned distance | Stable at max range |
| RC transmitter | Function check | Verify switches and sticks | All controls responsive |

### S4.2 Software Pre-flight Checklist

| Item | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| PX4 firmware version | Version check | QGroundControl or MAVSDK | Matches planned version |
| Parameter configuration | Parameter verification | Review critical parameters | All safety params set |
| EKF health | Status check | Monitor EKF status via QGC | All pre_flt_fail flags false |
| Sensor calibration | Calibration status | Review calibration data | All sensors calibrated |
| Geofence configuration | Boundary verification | Review GF_MAX_HOR/VER_DIST | 500m H, 100m V configured |
| Failsafe parameters | Parameter check | Review NAV_RCL_ACT, NAV_DLL_ACT | RTL configured |
| Battery failsafe | Threshold verification | Check BAT_CRIT_THR, BAT_EMERGEN_THR | 20%, 15% configured |
| Offboard readiness | Heartbeat test | Verify setpoint streaming | ≥ 10 Hz confirmed |
| LLM service status | Health check | Verify Ollama/local LLM | Model loaded, responsive |
| Vision pipeline | Detection test | Run YOLO on test images | > 5 FPS achieved |

### S4.3 PX4-Specific Preflight Checks

**EKF Health Verification:**
```
estimator_status.pre_flt_fail_innov_heading: false
estimator_status.pre_flt_fail_innov_height: false
estimator_status.pre_flt_fail_innov_pos_horiz: false
estimator_status.pre_flt_fail_innov_vel_horiz: false
estimator_status.pre_flt_fail_innov_vel_vert: false
estimator_status.pre_flt_fail_mag_field_disturbed: false
```

**GPS Quality Verification:**
```
estimator_gps_status.checks_passed: true
estimator_gps_status.check_fail_gps_fix: false
estimator_gps_status.position_drift_rate_horizontal_m_s: < 0.1
satellite_count: > 8
hdop: < 2.0
```

**Battery Verification:**
```
battery.remaining > 0.25 (25%)
battery.voltage > minimum for cell count
battery.current < maximum continuous
```

---

## S5. Emergency Procedures

### S5.1 Loss of Offboard Setpoints (Critical for LLM)

**Detection:**
- Timeout: 0.5 seconds (stream must be ≥ 2 Hz)
- Action: Configured by COM_OBL_RC_ACT

**Automated Response:**
1. COM_OBL_RC_ACT = 3: Return to Land (RTL)
2. Vehicle climbs to RTL_ALT (60m)
3. Returns to home position
4. Lands at home

**Implementation Requirements:**
```python
# Required in offboard implementation
# Continuous setpoint streaming at ≥ 10 Hz recommended
# COM_OBL_RC_ACT = 3 (Return) configured

async def offboard_heartbeat():
    """Maintain minimum 2 Hz setpoint stream to PX4."""
    while True:
        await offboard.set_position_ned(current_target)
        await asyncio.sleep(0.1)  # 10 Hz
```

### S5.2 Geofence Breach

**Automated Response:**
1. Detection: GF_ACTION triggered when position exceeds GF_MAX_HOR_DIST or GF_MAX_VER_DIST
2. Action: RTL (GF_ACTION = 3)
3. Behavior: Climb to RTL_ALT, return to home, land

**Configuration:**
```
GF_MAX_HOR_DIST: 500 m (horizontal cylinder radius)
GF_MAX_VER_DIST: 100 m (vertical limit from home)
GF_ACTION: 3 (Return to Land)
GF_SOURCE: 0 (Global Position)
```

### S5.3 Battery Failsafe Sequence

| Level | Threshold | Action |
|-------|-----------|--------|
| Warning | 25% (BAT_WARN_THR) | GCS warning only |
| Failsafe | 20% (BAT_CRIT_THR) | Return to Land triggered |
| Emergency | 15% (BAT_EMERGEN_THR) | Immediate landing |

### S5.4 Loss of Control Link

**Automated Response:**
1. Timeout: 10 seconds (COM_DL_LOSS_T)
2. Action: Return to Land (NAV_DLL_ACT = 3)

**Operator Response:**
1. Attempt to re-establish telemetry link
2. If using RC, switch to manual control
3. Monitor vehicle status via RC telemetry if available
4. Prepare for manual recovery when in range

### S5.5 GPS/GNSS Failure

**Detection:**
- estimator_gps_status.checks_passed: false
- check_fail_gps_fix: true
- position_drift_rate_horizontal_m_s > threshold

**Automated Response:**
1. COM_POS_LOW_ACT triggered (set to 2: Hold mode)
2. Vehicle maintains current position if estimator still valid
3. Land immediately if position estimate degrades

### S5.6 LLM Failure Response

**Scenario: LLM process crashes or hangs**

**Automated Response:**
1. Offboard setpoint stream stops
2. COM_OBL_RC_ACT triggers after 0.5s timeout
3. Vehicle enters RTL mode

**Software Layer Protection:**
```python
# Safety wrapper implementation
class SafetyMonitor:
    def __init__(self):
        self.llm_last_response = time.time()
        self.llm_timeout = 2.0  # seconds
        
    def validate_llm_health(self):
        if time.time() - self.llm_last_response > self.llm_timeout:
            # Trigger failsafe
            self.initiate_rtl()
            return False
        return True
```

---

## S6. Software Safety Layer Implementation

### S6.1 Safety Wrapper for LLM Commands

```python
# mav/safety.py implementation for Project Avatar

from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import asyncio
import time

@dataclass
class SafetyLimits:
    """Hard safety limits for Project Avatar."""
    max_altitude_m: float = 120.0  # 400 ft AGL
    max_horizontal_distance_m: float = 500.0
    max_speed_m_s: float = 15.0
    min_battery_percent: float = 25.0
    max_wind_m_s: float = 10.0
    geofence_horizontal_m: float = 500.0
    geofence_vertical_m: float = 100.0

class ProjectAvatarSafetyMonitor:
    """Safety monitoring for LLM-controlled drone."""
    
    def __init__(self, limits: SafetyLimits):
        self.limits = limits
        self.home_position: Optional[Tuple[float, float, float]] = None
        self.ekf_healthy = False
        self.gps_healthy = False
        
    async def preflight_check(self, telemetry: Dict) -> Tuple[bool, list]:
        """
        Run preflight checks before arming.
        Returns (all_passed, list_of_failures)
        """
        failures = []
        
        # EKF health check
        ekf_flags = telemetry.get('estimator_status', {})
        if (ekf_flags.get('pre_flt_fail_innov_heading') or
            ekf_flags.get('pre_flt_fail_innov_height') or
            ekf_flags.get('pre_flt_fail_innov_pos_horiz')):
            failures.append("EKF preflight checks failed")
            
        # GPS quality check
        gps_status = telemetry.get('estimator_gps_status', {})
        if not gps_status.get('checks_passed', False):
            failures.append("GPS checks not passed")
        if gps_status.get('check_fail_gps_fix', False):
            failures.append("GPS fix insufficient")
            
        # Battery check
        battery = telemetry.get('battery', {})
        if battery.get('remaining', 0) < self.limits.min_battery_percent:
            failures.append(f"Battery {battery.get('remaining')}% < {self.limits.min_battery_percent}%")
            
        return len(failures) == 0, failures
    
    def validate_llm_command(self, command: Dict, 
                           current_position: Tuple[float, float, float],
                           battery_percent: float) -> Tuple[bool, Optional[str]]:
        """
        Validate LLM-generated command against safety limits.
        Returns (is_valid, error_message)
        """
        # Check battery level
        if battery_percent < self.limits.min_battery_percent:
            return False, f"Battery {battery_percent}% below minimum {self.limits.min_battery_percent}%"
        
        # Check altitude limit
        target_alt = command.get('altitude_m', current_position[2])
        if target_alt > self.limits.max_altitude_m:
            return False, f"Target altitude {target_alt}m exceeds limit {self.limits.max_altitude_m}m"
        
        # Check horizontal distance from home
        if self.home_position:
            distance = self._calculate_distance(
                self.home_position[0], self.home_position[1],
                command.get('latitude', current_position[0]),
                command.get('longitude', current_position[1])
            )
            if distance > self.limits.geofence_horizontal_m:
                return False, f"Distance from home {distance}m exceeds geofence"
        
        # Check speed limit
        target_speed = command.get('speed_m_s', 0)
        if target_speed > self.limits.max_speed_m_s:
            return False, f"Target speed {target_speed}m/s exceeds limit {self.limits.max_speed_m_s}m/s"
        
        return True, None
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two GPS coordinates."""
        # Haversine formula implementation
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth radius in meters
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
```

### S6.2 Failsafe State Machine

```python
class FailsafeStateMachine:
    """Manage failsafe states for Project Avatar."""
    
    STATE_NORMAL = "normal"
    STATE_RTL = "return_to_land"
    STATE_LAND = "land"
    STATE_HOLD = "hold"
    STATE_EMERGENCY = "emergency"
    
    def __init__(self, px4_interface):
        self.state = self.STATE_NORMAL
        self.px4 = px4_interface
        
    async def process_failsafe_flags(self, flags: Dict):
        """Process failsafe flags from PX4."""
        
        # Critical battery - emergency land
        if flags.get('battery_unhealthy') or flags.get('battery_low_remaining_time'):
            await self.transition_to(self.STATE_EMERGENCY)
            return
            
        # Geofence breach - RTL
        if flags.get('geofence_breached'):
            await self.transition_to(self.STATE_RTL)
            return
            
        # Datalink loss - RTL
        if flags.get('gcs_connection_lost'):
            await self.transition_to(self.STATE_RTL)
            return
            
        # RC loss - RTL
        if flags.get('manual_control_signal_lost'):
            await self.transition_to(self.STATE_RTL)
            return
            
        # Low position accuracy - Hold
        if flags.get('position_accuracy_low'):
            await self.transition_to(self.STATE_HOLD)
            return
            
    async def transition_to(self, new_state):
        """Transition to new failsafe state."""
        if self.state == new_state:
            return
            
        print(f"FAILSAFE: {self.state} -> {new_state}")
        self.state = new_state
        
        if new_state == self.STATE_RTL:
            await self.px4.execute_rtl()
        elif new_state == self.STATE_LAND:
            await self.px4.execute_land()
        elif new_state == self.STATE_HOLD:
            await self.px4.execute_hold()
        elif new_state == self.STATE_EMERGENCY:
            await self.px4.execute_emergency_land()
```

---

## S7. Risk Assessment for Project Avatar

### S7.1 Hazard Identification

| ID | Hazard | Cause | Effect | Likelihood | Severity | Risk |
|----|--------|-------|--------|------------|----------|------|
| H1 | Collision with persons | Loss of control, geofence breach | Injury | Low | High | Medium |
| H2 | Collision with property | Navigation error, wind gust | Damage | Low | Medium | Low |
| H3 | Loss of control | Software bug, hardware failure | Flyaway | Low | High | Medium |
| H4 | Battery failure | Low charge, cell failure | Forced landing | Medium | Medium | Medium |
| H5 | GPS failure | Signal loss, interference | Navigation error | Low | Medium | Low |
| H6 | LLM error | Hallucination, misinterpretation | Unsafe command | Medium | High | High |
| H7 | Weather exceedance | Unexpected gusts | Loss of control | Low | High | Medium |
| H8 | Communication loss | Radio failure | Loss of link | Low | Medium | Low |

### S7.2 Mitigation Strategies

| Hazard | Mitigation | Residual Risk |
|--------|------------|---------------|
| H1 | Geofence (500m), spectator distance > 30m, RTL on breach | Low |
| H2 | Altitude limits (120m), preflight planning, operational area clear | Low |
| H3 | PX4 failsafes, RC backup, software validation layer | Low |
| H4 | Battery monitoring (25/20/15%), conservative thresholds, RTL | Low |
| H5 | GPS health checks, EKF monitoring, manual backup | Low |
| H6 | Command validation, human confirmation (Stages 1-2), hard limits | Low |
| H7 | Weather limits (10 m/s), preflight assessment | Low |
| H8 | Dual links (telemetry + RC), RTL on loss | Low |

---

## S8. Documentation Templates

### S8.1 Flight Log Template

```markdown
# Project Avatar Flight Log

**Date:** YYYY-MM-DD  
**Location:** [GPS coordinates or site name]  
**Pilot in Command:** [Name]  
**Aircraft:** [Frame/FC ID]  
**Software Version:** [git hash]  
**Mission:** [Brief description]

## Pre-flight

- [ ] Hardware checklist complete
- [ ] Software checklist complete
- [ ] PX4 parameters verified (GF_ACTION=3, COM_OBL_RC_ACT=3, etc.)
- [ ] EKF health: All pre_flt_fail flags false
- [ ] GPS: > 8 satellites, HDOP < 2.0
- [ ] Battery: > 25% at start
- [ ] Weather: Wind < 10 m/s, visibility > 3 SM
- [ ] Airspace clear

**Parameters:**
- PX4 version: [x.x.x]
- Avatar software: [git hash]
- Geofence: H=500m, V=100m
- Battery thresholds: Warn=25%, Crit=20%, Emerg=15%

## Flight

**Start time:** HH:MM  
**Duration:** ___ minutes  
**Max altitude:** ___ m  
**Max distance:** ___ m  
**Battery at start:** ___%  
**Battery at end:** ___%
**Offboard mode duration:** ___ minutes

**LLM Interactions:**
- Number of commands: ___
- Commands validated: ___/___
- Human confirmations required: ___

**Anomalies:**
- [None / describe]

## Post-flight

- [ ] Aircraft condition: [Good / Issues noted]
- [ ] Data downloaded and archived
- [ ] Logs analyzed

**Notes:**
[Additional observations]

**Signed:** _________________
```

### S8.2 Incident Report Template

```markdown
# Project Avatar Incident Report

**Date:** YYYY-MM-DD  
**Time:** HH:MM  
**Location:** [GPS coordinates]  
**Reporter:** [Name]

## Incident Summary

[Brief description]

## Severity

- [ ] Near miss
- [ ] Minor (no damage/injury)
- [ ] Moderate (damage)
- [ ] Serious (injury potential)
- [ ] Critical (actual injury/major damage)

## Contributing Factors

- [ ] PX4 failsafe triggered
- [ ] Software error
- [ ] LLM error
- [ ] Human error
- [ ] Weather
- [ ] Equipment malfunction
- [ ] Other: _______

## Failsafe Response

[Which failsafe triggered and how did it respond?]

## Corrective Actions

| Action | Owner | Due Date |
|--------|-------|----------|
| | | |

**Approved by:** _________________
```

---

## S9. Quick Reference

### S9.1 Essential PX4 Parameters

```
COM_OBL_RC_ACT = 3 (RTL on offboard loss)
COM_DL_LOSS_T = 10 (10 sec datalink timeout)
NAV_DLL_ACT = 3 (RTL on datalink loss)
NAV_RCL_ACT = 3 (RTL on RC loss)
GF_ACTION = 3 (RTL on geofence breach)
GF_MAX_HOR_DIST = 500 (500m radius)
GF_MAX_VER_DIST = 100 (100m height)
COM_LOW_BAT_ACT = 3 (RTL at critical)
BAT_CRIT_THR = 0.20 (20% critical)
BAT_EMERGEN_THR = 0.15 (15% emergency)
```

### S9.2 Abort Criteria

- Wind exceeds 10 m/s
- Battery below 25%
- GPS satellites < 8
- Any failsafe triggered
- Unexpected vehicle behavior
- Loss of telemetry > 5 seconds
- LLM command rejected by safety layer

### S9.3 Emergency Contacts

- Local emergency services: 911
- University safety office: [insert]
- PIC direct contact: [insert]
- Project lead: [insert]

---

*Document Version: 1.1*  
*Classification: Safety Reference*  
*Next Review: Quarterly or upon regulatory change*  
*Last Updated: April 2025 - Added PX4-specific failsafe configuration for Project Avatar*

---

## References

1. PX4 Autopilot User Guide - Safety Configuration
2. PX4 Parameter Reference - Failsafe Settings
3. FAA Part 107 - Small UAS Operations
4. ASTM F3362 - UAS Remote ID
5. ASTM F3445 - Drone Operations
6. ISO 21384-3 - UAV Operational Procedures
7. DO-178C - Software Considerations in Airborne Systems
8. Project Avatar Technical Documentation (project_avatar_technical.md)
9. Project Avatar PRD (project_avatar_prd.md)
10. MAVSDK-Python Documentation

---

*End of Document*  
*File: /Users/muadhsambul/Downloads/Project-Avatar/research/safety_standards.md*
*Project Avatar Research Documentation*  
*Autonomous UAV Safety Standards & Requirements*  
*For Academic and R&D Use*  
*2025 Project Avatar Research Team*
</append>
