# Project Avatar: Change Log

**Purpose**: Maintain a chronological record of all changes to the project for auditability and debugging.

**Format**: Reverse chronological order (newest first). Each entry includes date, change type, description, and impact.

---

## Change Types

- `[ARCH]` - Architecture/structural changes
- `[CODE]` - Code implementation
- `[DOC]` - Documentation updates
- `[CONFIG]` - Configuration changes
- `[HARDWARE]` - Hardware changes
- `[SAFETY]` - Safety-related changes
- `[RESEARCH]` - Research findings captured

---

## 2026-04-10

### [ARCH] Created organized research directory structure

**Files**: `research/{01-core-project,02-safety-failsafe,03-software-architecture,04-vision-perception,05-testing-validation,06-hardware,07-references,08-decisions,09-changes}/`

**Description**: Organized 26 research documents into 9 categorized subdirectories with numbered prefixes for consistent ordering.

**Impact**: All research now has permanent location. Directory structure follows logical flow: core → safety → software → vision → testing → hardware → references → decisions → changes.

**Research Documents Moved**:
- `01-core-project/`: MASTER_BRIEFING.md, implementation_roadmap.md, project_requirements.md, risk_register.md, ros2_vs_mavsdk.md
- `02-safety-failsafe/`: failsafe_hierarchy.md, geofencing_hard_limits.md, px4_parameter_checklist.md, safety_requirements.md
- `03-software-architecture/`: python_asyncio_patterns.md, tool_schema_design.md, mvp_drone_system.md
- `04-vision-perception/`: yolo_tracking_integration.md, depth_estimation_realsense.md, v11_mode_switching.md
- `05-testing-validation/`: test_flight_procedures.md, validation_checklist.md
- `06-hardware/`: complete_hardware_manifest.md, companion_computer_setup.md
- `07-references/`: raspberry_pi_5_vs_4.md, daa_sensor_research.md, mavlink_message_references.md, px4_rtl_behavior.md

---

### [DOC] Created DECISIONS.md audit trail

**Files**: `research/08-decisions/DECISIONS.md`

**Description**: Created comprehensive decision log documenting 12 architectural and design decisions (DEC-001 through DEC-012). Includes MAVSDK over ROS2 choice, 4-layer safety architecture, YOLOv8-nano selection, asyncio priority scheduling, and research organization structure.

**Impact**: All major project decisions now have documented rationale, trade-offs, and consequences. Enables future team members to understand why choices were made.

---

### [DOC] Created CHANGES_MADE.md audit trail

**Files**: `research/09-changes/CHANGES_MADE.md` (this file)

**Description**: Established change logging system to track all project modifications.

**Impact**: Provides chronological history of all changes for debugging, accountability, and project archaeology.

---

### [RESEARCH] Captured 7 memory files for persistent knowledge

**Files**: `~/.claude/projects/-Users-muadhsambul/memory/{project_avatar_overview.md,patterns_drone_safety_architecture.md,patterns_asyncio_priority_scheduling.md,patterns_json_tool_schema.md,patterns_yolo_tracking.md,decisions_mavsdk_over_ros2.md,MEMORY.md}`

**Description**: Synthesized all research into persistent memory system for future conversation context.

**Memory Files Created**:
1. `project_avatar_overview.md` - System architecture and roadmap
2. `patterns_drone_safety_architecture.md` - 4-layer safety pattern
3. `patterns_asyncio_priority_scheduling.md` - Priority scheduling pattern
4. `patterns_json_tool_schema.md` - Tool validation pattern
5. `patterns_yolo_tracking.md` - Vision pipeline pattern
6. `decisions_mavsdk_over_ros2.md` - MAVSDK vs ROS2 decision
7. `MEMORY.md` - Index of all memory entries

**Impact**: Future conversations will have full context of Project Avatar research without re-reading all documents.

---

### [RESEARCH] Consolidated 22 research documents into MASTER_BRIEFING.md

**Files**: `research/MASTER_BRIEFING.md`

**Description**: Created single source of truth document (106KB, 1500+ lines) consolidating all research. Includes 10 major sections: Executive Summary, Safety Constraints, Architecture, Implementation Roadmap, Component Deep Dives, Performance Budgets, Risk Register, Research Index, Quick Reference, and Next Steps.

**Impact**: Single document provides complete project overview. All team members can reference one authoritative source.

---

### [ARCH] Validated three-stage development approach

**Research**: `implementation_roadmap.md`, `mvp_drone_system.md`

**Description**: Confirmed Stage 1 → Stage 2 → Stage 3 progression:
- Stage 1: Control Spine (GPS-only navigation) - 4-6 weeks
- Stage 2: Vision System (Person detection + tracking) - 6-8 weeks
- Stage 3: Depth & Payload (Obstacle avoidance, gimbal) - 8-10 weeks

**Impact**: Current focus locked to Stage 1. Vision integration deferred until control spine is bulletproof.

---

### [SAFETY] Validated 4-layer safety architecture

**Research**: `failsafe_hierarchy.md`, `geofencing_hard_limits.md`

**Description**: Documented safety layers: PX4 Hard Reflexes (<100ms) → Guardian Process (~10ms) → LLM Reactions (1-3s) → Operator Override (RC).

**Key Finding**: Heartbeat MUST run on RPi, not Mac. If WiFi drops with heartbeat on Mac, drone falls.

**Impact**: GuardianProcess implementation must run on RPi. Safety architecture prevents AI errors from causing physical harm.

---

### [ARCH] Confirmed MAVSDK-Python over ROS2

**Research**: `ros2_vs_mavsdk.md`

**Description**: Validated decision to use MAVSDK-Python (2.8ms latency) over ROS2 (7.1ms latency).

**Rationale**: Lower latency, simpler architecture, direct asyncio, less overhead.

**Trade-offs**: Smaller ecosystem, less industry standard.

**Impact**: All drone control uses MAVSDK-Python. No ROS2 dependencies.

---

### [CODE] Validated asyncio priority scheduling pattern

**Research**: `python_asyncio_patterns.md`

**Description**: Confirmed 5-level priority system: CRITICAL (20Hz heartbeat), HIGH (<10ms), MEDIUM (<50ms YOLO), LOW (1-3s LLM), BACKGROUND (logging).

**Key Pattern**: ComputeIsolator with ProcessPoolExecutor for CPU-bound work isolation.

**Impact**: Heartbeat task must use asyncio.sleep(0.05) exactly, never blocked by vision inference.

---

### [CODE] Validated YOLOv8-nano + ByteTrack configuration

**Research**: `yolo_tracking_integration.md`

**Description**: Confirmed YOLOv8-nano (3.2M params, ~80ms inference) with ByteTrack at 640x480, 10-15 FPS.

**Configuration**: track_thresh=0.4, match_thresh=0.8, track_buffer=60 (6 sec occlusion tolerance).

**Impact**: Memory budget ~50-60MB per stream. Detection optimized for people only (class=[0]).

---

### [ARCH] Validated JSON tool schema pattern

**Research**: `tool_schema_design.md`

**Description**: Confirmed structured JSON schemas for LLM tool calls including parameter validation, preconditions, postconditions, and safety checks.

**Validation Flow**: LLM generates → JSON Schema validation → Precondition checking → GuardianProcess validation → Execution → Post-condition verification.

**Impact**: All LLM tools must have defined schemas with hard limits enforced.

---

### [SAFETY] Documented PX4 parameter configuration

**Research**: `px4_parameter_checklist.md`

**Description**: Validated critical PX4 safety parameters:
- COM_OBL_RC_ACT: 3 (RTL on offboard loss)
- COM_OF_LOSS_T: 0.5 (500ms timeout)
- GF_MAX_HOR_DIST: 500m geofence
- GF_MAX_VER_DIST: 120m altitude ceiling
- BAT_CRIT_THR: 20% (RTL), BAT_EMERGEN_THR: 15% (land)

**Impact**: These parameters provide hard limits that cannot be overridden by software.

---

### [HARDWARE] Validated hardware manifest

**Research**: `complete_hardware_manifest.md`, `companion_computer_setup.md`

**Description**: Confirmed hardware selection:
- Flight Controller: Pixhawk 6C Mini with PX4
- Companion Computer: Raspberry Pi 4 (4GB)
- Telemetry: mRo 915MHz SiK
- Camera: Raspberry Pi Camera Module 3 Wide
- Depth: OAK-D-Lite (Stage 3)

**Impact**: Hardware purchases staged to match three-stage development roadmap.

---

### [SAFETY] Reviewed risk register

**Research**: `risk_register.md`

**Description**: Validated risk categorization: Catastrophic (injury/property), Critical (flyaway/crash), Major (damage/loss of control), Minor (performance), Negligible (inconvenience).

**High Priority Risks**: GPS denial, battery failure, wind shear, RC link loss, software crash.

**Impact**: Risk mitigation strategies inform safety architecture decisions.

---

## How to Log Changes

When making changes to the project:

1. Add entry to TOP of this file (reverse chronological)
2. Use format: `### [TYPE] Brief description`
3. Include: Files affected, Description, Impact
4. Use appropriate change type tag

**Example**:
```markdown
### [CODE] Implemented GuardianProcess.validate_command()

**Files**: `src/safety/guardian.py`, `tests/test_guardian.py`

**Description**: Implemented command validation with hard limits checking. Validates altitude ceiling (120m), distance from home (500m), battery RTL reserve (25%).

**Impact**: All LLM commands now validated before execution. Returns ValidationResult with approval status and reason.
```

---

### [RESEARCH] Created Marketplace Hunting Guide

**Files**: `research/10-marketplace-hunting/{README.md,01-marketplace-strategy.md,02-thrust-calculator.md,03-canadian-drone-laws.md}`

**Description**: Created comprehensive guide for finding drone hardware on Facebook Marketplace. Includes thrust calculation formulas, Canadian regulation compliance (250g threshold confirmed as operating weight including payload), motor database, and evaluation checklists. Three searches completed via Google AI mode confirming Transport Canada regulations.

**Key Findings**:
- Canadian "operating weight" includes everything at takeoff (frame + battery + payload)
- Project Avatar will be ~900g (far exceeds 250g threshold)
- Solution: Accept >250g, register drone ($5), get Basic certificate
- Main factor: Thrust power - need 7" frame with 2807 motors for 8:1 TWR

**Impact**: Can now evaluate Marketplace listings with confidence. TWR calculation formula enables quick go/no-go decisions.

### [RESEARCH] Expanded Marketplace Guide - Motor & Frame Database

**Files**: `research/10-marketplace-hunting/{02-thrust-calculator.md,01-marketplace-strategy.md}`

**Description**: Comprehensive expansion of marketplace hunting documentation:

**Motor Database Added** (02-thrust-calculator.md):
- 5" frame motors: 10 models (2205-2306) with thrust, efficiency, pricing
- 7" frame motors: 15 models (2806-2809) with verified 2026 test data
- 10" frame motors: 5 cinema motors (3110-4214)
- KV selection guide by battery type
- Budget tiers: <$100, $100-140, $140-200, $200+
- Motor red flags section

**Frame Database Added** (02-thrust-calculator.md):
- 5" frames: 5 common options (marked as avoid for Project Avatar)
- 7" frames: 11 target frames (Chimera7, Rekon7, AOS 7, Explorer LR7, etc.)
- 10" frames: 5 cinelifter options
- Mount pattern explanation (30.5mm vs 20mm critical)
- Frame features checklist
- Frame red flags section

**Full Kits Section Added** (02-thrust-calculator.md):
- Kit configuration comparison table (6 configurations with TWR analysis)
- Ideal kit specification checklist
- FPV gear you can ignore or sell

**Search Strategy Expanded** (01-marketplace-strategy.md):
- 30 comprehensive search terms organized by category:
  - Primary targets (8 terms)
  - Secondary terms (7 terms)
  - Brand-specific (5 terms)
  - Full kit terms (5 terms)
  - Hobby exit terms (5 terms)
- Marketplace alert setup instructions
- Alternative marketplaces table with URLs
- Timing strategy (best days/times to search)
- Step-by-step kit evaluation process
- Example seller conversation templates
- Kit pricing guide with value assessment formula
- Bundle deal opportunity breakdown

**Impact**: User now has complete reference for evaluating any Marketplace listing. Can identify motor specs from photos, calculate TWR, negotiate effectively, and identify high-value bundle deals.

---

### [RESEARCH] Added Strict Budget Build Guide - Hard $500 Ceiling

**Files**: `research/10-marketplace-hunting/02-thrust-calculator.md`

**Description**: Revised budget guide with strict $500 hard ceiling for ENTIRE Project Avatar build:

**Revised Budget Breakdown**:
- Target total: $340-445 (with $55-160 buffer)
- Hard ceiling: $500 maximum
- Drone (Marketplace): $120-180 (aggressive negotiation)
- Pixhawk 6C Mini: $85-95 (must buy new)
- Raspberry Pi 4 2GB: $35-45 (used)
- Camera/GPS/Telemetry/Battery/Misc: $103-135

**Three Strategies to Stay Under $500**:
1. Aggressive Hobby Exit: $250-300 kit, sell FPV gear, net $130-180
2. Component Bundle Hunt: Frame + motors $100-140 + ESC $25-35
3. Extreme Scavenge: Frame $35-45 + motors $50-70 + ESC $25-35

**Verified Sub-$500 Build: $341-442**:
- Rekon 7 + EMAX 2807 used: $130-170
- Pixhawk 6C Mini new: $90-95
- Pi 4 2GB used: $35-45
- Pi Camera 3 new: $28-32
- GPS/telemetry: $33-42
- Battery 6S used: $30-40
- Misc: $15-18
- **Total: $341-442 with $58-159 buffer**

**Emergency Under-$400 Build**:
- 2207 motors instead of 2807: saves $30-50
- Accepts lower TWR (~6:1 vs 9:1)
- Total: $303-388

**Hard Ceiling Rules**:
- If drone >$200: walk away
- If total >$500 before tax: find alternative
- Skip all FPV gear entirely (not just sell later)

**Impact**: User now has strict budget discipline with verified component costs that sum to $341-442, leaving headroom for spares or upgrades while staying well under $500 total.

---

*Last Updated: 2026-04-10*<parameter name="replace_all">False</parameter>
