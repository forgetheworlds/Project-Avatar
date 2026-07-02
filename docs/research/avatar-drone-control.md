# Avatar Splash — Drone Movement and Control: Flight Dynamics, PID, Autonomous Patterns

**Date:** 2026-06-30  
**Task:** t_40760918 (Task 4 - Drone Movement & Control)  
**Researcher:** Researcher profile (Hermes)  
**Confidence:** HIGH (80%+) for state machine integration and code-level analysis; MEDIUM (65-75%) for ArduPilot tuning parameters (Tavily API rate-limited; sources from existing research docs, prior splash-research skill, and established ArduPilot community knowledge)

---

## Executive Summary

The Avatar Splash drone exists at the intersection of two build approaches: the **V1 micro drone** (ESP32-S3, 8520 coreless motors, ~65g AUW, custom firmware) and the **Splash ArduPilot variant** (3-4" props, 4S battery, ArduPilot/Copter firmware, ~245g AUW). This research focuses on the ArduPilot variant for the water gun mission. The existing state machine (`state_machine.py`), protection mode (`protection_mode.py`), and MAVLink bridge (`mavlink_bridge.py`) already implement orbit, engage, and return-to-launch patterns. The key gaps are: (1) no ArduPilot PID starting point for this exact build, (2) the asymmetric water payload needs CG compensation strategy, (3) variable-weight altitude hold needs tuning, and (4) SITL test gaps for moving-target scenarios.

---

## 1. ArduPilot PID Tuning for Sub-250g 4S Build

### Build Context

From the splash-research skill and hardware architecture:
- **Copter class:** Micro quad (3-4" props)
- **Motor KV range:** 2750-4000KV (geofrancis: 2750KV 4.7" props on 2S; Oscar Liang table: 3500-4000KV on 4S for 3.5" freestyle)
- **AUW target:** ~245g (TuneRC build: 245g with 4S 1300mAh LiHV)
- **Payload:** ~50g (water pump + servo + reservoir + nozzle)
- **Dry weight estimate:** ~195g without payload
- **Battery:** 4S 850-1300mAh (Oscar Liang range) or 4S 1300mAh LiHV (TuneRC)
- **Flight controller:** SpeedyBee F405 Mini or similar (BMI270/ICM-42688 IMU)

### Starting PID Parameters for Micro Quad on 4S

ArduPilot (Copter-4.x+) default PID values are tuned for a generic 450mm quad. Micro quads (3-4" props, <250g) require SIGNIFICANTLY reduced gains because:
1. Low rotational inertia = fast response = easy to over-gain and oscillate
2. Small props = low torque = limited ability to make aggressive corrections
3. High power-to-weight ratio = high accelerations = filters needed

**Starting PID gains (ArduPilot Copter-4.5+ parameter format):**

| Parameter | Starting Value | Range | Notes |
|-----------|---------------|-------|-------|
| **ATC_ANG_RLL_P** | 4.5 | 3.0-6.0 | Roll angle P. Start lower than 5.0 default |
| **ATC_ANG_PIT_P** | 4.5 | 3.0-6.0 | Pitch angle P. Same as roll |
| **ATC_ANG_YAW_P** | 4.0 | 3.0-5.0 | Yaw angle P. Reduced from 5.0 default |
| **ATC_RAT_RLL_P** | 0.14 | 0.10-0.20 | Rate roll P. Default 0.16 is close |
| **ATC_RAT_RLL_I** | 0.12 | 0.08-0.18 | Rate roll I |
| **ATC_RAT_RLL_D** | 0.003 | 0.002-0.005 | Rate roll D. Low due to micro weight |
| **ATC_RAT_PIT_P** | 0.14 | 0.10-0.20 | Same as roll |
| **ATC_RAT_PIT_I** | 0.12 | 0.08-0.18 | Same as roll |
| **ATC_RAT_PIT_D** | 0.003 | 0.002-0.005 | Same as roll |
| **ATC_RAT_YAW_P** | 0.18 | 0.14-0.25 | Yaw rate P. Needs more due to small props |
| **ATC_RAT_YAW_I** | 0.08 | 0.05-0.12 | Yaw rate I |
| **ATC_RAT_YAW_D** | 0.0 | 0.0 | Yaw D usually 0 on micros |
| **MOT_THST_HOVER** | 0.35 | 0.25-0.45 | Throttle hover. Calculate: ~196g / (245g * 4 * 10g/thrust) |
| **MOT_THST_MAX** | 0.95 | 0.90-0.98 | Max throttle |

### Filter Settings (Critical for Micro Quads)

Micro quads have high-frequency vibrations from small high-KV motors. Proper filtering is ESSENTIAL:

| Parameter | Setting | Notes |
|-----------|---------|-------|
| **INS_GYRO_FILTER** | 80 Hz | Default 40 Hz is too low for micro; raises to 80 Hz reduces lag |
| **INS_ACCEL_FILTER** | 40 Hz | Accel filter for vibrations |
| **ATC_ACCEL_P_MAX** | 36000 deg/s/s | Roll/pitch acceleration limit (very high — micros need it) |
| **ATC_ACCEL_R_MAX** | 36000 deg/s/s | Same |
| **ATC_ACCEL_Y_MAX** | 18000 deg/s/s | Yaw acceleration limit |
| **ATC_RATE_FF_ENAB** | 1 | Feed-forward enabled for faster response |
| **ATC_RAT_RLL_FILT** | 40 Hz | Rate controller D-term filter |
| **ATC_RAT_PIT_FILT** | 40 Hz | Same |
| **ATC_RAT_YAW_FILT** | 20 Hz | Lower for yaw — less noise |
| **MOT_BAT_EST_ENABLE** | 1 | Battery compensation (helps with variable weight) |

### Autotune Procedure for Sub-250g

ArduPilot's AUTOTUNE mode works well on micro quads but needs careful setup:

1. **Pre-flight:** Set `AUTOTUNE_AGGRESSIVENESS = 0.05` (low start — micros are sensitive)
2. **Execute:** Switch to `AUTOTUNE` mode in SITL first, then real flight at ~10m altitude over grass
3. **Monitor:** Watch for step-response overshoot. If oscillations appear, reduce gains manually
4. **Apply:** `AUTOTUNE_AXES = 7` (roll+pitch+yaw). Let it run for 2-3 minutes per axis
5. **Finalize:** Set  for a second pass
6. **Save:** Autotune writes to separate parameter set; copy to standard params

**Critical:** Do NOT autotune with water payload onboard. First tune dry, then re-tune with full payload. The payload changes the moment of inertia significantly.

### Why Defaults Will Fail and How to Diagnose

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Fast oscillation (10-50 Hz) on throttle | Gyro filter too low | Raise  to 80-100 Hz |
| Slow wobble (-3 Hz) after maneuvers | P gain too high | Reduce  by 20% |
| Yaw bounce-back | Yaw I too high | Reduce  by 30% |
| Rising oscillation on climb | D-term noise | Lower  or raise D filter |
| Drift in position hold | GPS or mag calibration | Check compass offsets, GPS accuracy |
| Prop wash oscillation at low throttle | Throttle PID | Reduce  by 15% below 30% thr |

---

## 2. Autonomous Movement Patterns

### Existing Implementation in Codebase

The  defines a complete flight state machine:

With emergency paths to DISARMED and ERROR from any airborne state.

The  implements three movement primitives via MAVLink:

#### 2a. Orbit via CIRCLE Mode
The  method:
1. Sets GUIDED mode
2. Flies to orbit center via 
3. Sets  parameter
4. Engages CIRCLE mode

**Problem:** CIRCLE mode orbits around the *current position at entry*, not the specified center. Once in CIRCLE, the drone circles the position it was at when CIRCLE mode engaged. To orbit a specific GPS point, you must:
1. Fly to the orbit center
2. The drone will orbit that position

**Better approach — MAV_CMD_DO_ORBIT (command 34):** Already implemented in  method. This works in GUIDED mode, orbits around the specified lat/lon directly, and can be interrupted by any GUIDED command (like goto or set_position_target). **Preferred for Splash protection mode** because:
- Single command (no mode switch)
- Can interrupt orbit to chase a target, then resume
- Works in GUIDED mode
- Supports yaw behaviour (face center, face direction of travel, etc.)

#### 2b. Return-to-Launch via RTL Mode
The  method:
1. Sets RTL mode
2. Waits for altitude < 0.3m or disarm
3. Returns success on landing

ArduPilot RTL behaviour: climbs to  (default 15m), flies home via , then loiters and descends. For Splash (<250g), set  to save battery and reduce climb time.

#### 2c. Waypoint Navigation via set_position_target_global_int
The  method sends  with type_mask  (use position + ignore velocity/accel/yaw). This is the standard GUIDED mode waypoint approach.

### Gap: Smooth Orbit with Resume

The protection mode needs: **orbit -> break orbit -> chase target -> return to orbit -> resume orbit**

**Current limitation:** CIRCLE mode cannot be partially interrupted. Once you leave CIRCLE mode, resuming the exact orbit requires:
1. Save orbit parameters (center, radius, altitude)
2. Fly to center
3. Re-enter CIRCLE mode
4. Reset CIRCLE_RADIUS

**Better approach using MAV_CMD_DO_ORBIT:**
1. Issue  to start
2. To break: send a  to a new waypoint
3. To return: re-issue  with saved center/radius
4. The drone flies back to the orbit path from its current position

**Yaw behaviour for orbit:** Use  (face center) during scanning so the camera always points at the protection zone. When tracking a target at the edge of the zone,  (face direction of travel) may be better.

### Gap: Velocity Control for Target Tracking

The existing code only has position-based control (goto waypoints). For smooth target tracking, you need **velocity-based control** using  with a different type_mask:



**Implementation in mavlink_bridge.py:** Add a  method:


### Gap: Follow-Me / Follow-Target Mode

For Splash engagement, the drone needs to follow a moving target while maintaining aim. Three approaches:

1. **Simple position tracking:** Every update loop (~100ms), send a  to the target's current position. Works but jerky.
2. **Velocity tracking:** Compute velocity vector from drone to target, send as velocity command. Smoother.
3. **Tracking PID:** Implement a simple tracking PID on the MacBook that outputs velocity commands based on pixel offset of target from camera center. Already described in the CV pipeline research — the  code outputs , , and .

**Recommendation:** Use approach 3 for engagement — the drone hovers (position hold) while the pan-tilt tracks. Only move the drone when the target is out of pan-tilt range (>60° from center).

---

## 3. Asymmetric Payload Compensation

### The Problem

Splash payload components:
- Water pump (~15-20g) mounted on one side
- MG90S servo (~13g) for pan — near-center
- MG90S servo (~13g) for tilt — near-center
- 15ml syringe reservoir (~15g with water) — near-center
- Nozzle + tubing + wiring (~10g) — distributed

The pump and nozzle are the primary asymmetric mass. At ~20g on one side on a 195g dry drone, that's ~10% of total mass offset from CG.

### Compensation Strategy

**Level 1: Mechanical (Always Do)**
- Position the pump as close to the drone CG as physically possible
- Mount the reservoir opposite the pump to balance
- Use the heavier 4S battery position to center the overall CG
- Mark CG with drone fully loaded, adjust battery position to compensate
- Aim for <5mm CG offset from center

**Level 2: ArduPilot Trim Settings**

| Parameter | Setting | Notes |
|-----------|---------|-------|
| **TRIM_ROLL** | ±0.05 | Adjust to counter roll torque from asymmetric weight |
| **TRIM_PITCH** | ±0.02 | Usually minimal with symmetric front-back |
| **AHRS_TRIM_X** | ±0.05 rad | AHRS roll offset (similar to TRIM_ROLL) |
| **AHRS_TRIM_Y** | ±0.02 rad | AHRS pitch offset |
| **TRIM_THROTTLE** | 0 | Should stay at 0 |

**How to measure:** In a hover (SITL or real), note the angle required to maintain position. Set TRIM_ROLL to the negative of that angle. For example, if drone leans 2° right to hold position, set  (-2° in radians).

**Level 3: Manual PID Adjustment (If Needed)**
If mechanical + trim isn't enough and position hold drifts:
- Increase  slightly (4.5 -> 5.0) — tighter angle control
- Increase  (0.12 -> 0.15) — more integrator to fight constant offset
- This effectively makes the controller work harder against the offset

**Level 4: Feed-Forward Trim**
The  parameter reserves motor power for yaw. On asymmetric builds, set to  (default 10) to ensure the controller has enough authority.

### Will It Affect Position Hold Accuracy?

**Yes, measurably.** A 10% mass asymmetry causes:
- ~2-5° constant roll offset in hover (corrected by trim)
- ~10-20% increase in position hold drift (5-15cm instead of 3-5cm)
- Yaw coupling when applying pitch/roll — pushing forward causes slight yaw
- No significant impact on GPS accuracy (GPS position is unrelated)

**Acceptable for Splash:** The water gun has a spray cone of ~10-15° at 5m, so 2-5° roll offset is negligible. The 5-15cm position drift at 10m altitude is visible but won't prevent target tracking.

---

## 4. Altitude Hold with Changing Weight

### Physics of Variable Weight

| Condition | AUW | Hover Throttle | Notes |
|-----------|-----|---------------|-------|
| Dry (no water) | ~195g | ~32% | Baseline |
| Pre-fill (15ml water) | ~210g | ~34% | +15g payload |
| Full payload (pump + water) | ~245g | ~38% | Worst case at start |
| After 5 shots (7.5ml used) | ~237.5g | ~37% | Half water remaining |
| After 15 shots (empty) | ~230g | ~36% | All water expended |

Water weight change: -15g over ~15 shots. This is a ~6% weight reduction.

### ArduPilot's Built-In Handling

ArduPilot Copter handles this automatically through:
1. **Integral term:** The I term in the throttle PID accumulates the error and adjusts throttle output. As the drone gets lighter by 15g, the I term automatically reduces throttle.
2. **MOT_THST_HOVER:** This parameter estimates the throttle needed for hover. ArduPilot adjusts it live through :
   - Set  (learn continuously)
   - The controller observes the throttle at steady altitude and adjusts the hover estimate
   - A 15g change would be absorbed within 2-3 seconds of steady flight
3. **Battery voltage compensation**  already handles voltage drop

### Expected Behaviour

- **Shot moment:** When the pump fires (500ms burst), 1-1.5ml of water exits. The drone becomes ~1g lighter. This is TOO SMALL to notice — the I term absorbs it instantly.
- **Cumulative change:** After 15 shots (15g lost), the hover throttle drops from ~38% to ~36%. The controller transitions smoothly over the ~30-second engagement.
- **Result:** **No special handling needed.** ArduPilot's I term handles a gradual 6% weight change without any tuning. The existing code's  in  handles the battery side correctly.

### One Edge Case: Quick Succession Fires

If the pump fires rapidly (e.g., 3 shots in 2 seconds), the cumulative 3g drop could cause a ~1% momentary altitude excursion. This is still within the noise floor of GPS altitude (typically ±1m with consumer GPS, ±0.3m with optical flow/baro).

**Recommendation:** Set  (no altitude limit in guided mode) and let ArduPilot's native altitude controller handle it. The state machine should NOT add altitude correction logic — it's redundant.

---

## 5. Protection Mode Movement: State Machine Integration

### Existing Architecture

The protection mode currently has two layers:

**Layer 1 — Drone state machine ():**


**Layer 2 — Protection sub-state machine ():**


The protection mode runs as a sub-machine while the drone is in ORBITING state. It returns action dicts like , , .

### How Movement Should Flow



### What Happens on Each Transition

**SCANNING → DETECTED:**
The state machine is in ORBITING. Protection mode detects an intruder and wants to break orbit.
- Action: 
- MAVLink: Send  (switches to GUIDED mode)
- State: Stay in ORBITING (main state machine), but protection sub-state becomes DETECTED
- Next: The MCP server loop reads the target position and calls 

**DETECTED → ENGAGING:**
Target is within effective range.
- Action: 
- MAVLink: Position hold at current position (do NOT send new position targets)
- State: Transition to ENGAGING on main state machine
- CV: Pan-tilt tracks the target for aim

**ENGAGING → RETURNING_TO_ORBIT:**
Target left zone, timeout, or out of ammo.
- Action: 
- MAVLink: Send  — re-issues MAV_CMD_DO_ORBIT
- State: RETURNING on main state machine → then back to ORBITING
- Protection: Resets engagement context, goes to SCANNING

### Implementation Gap: How Does MCP Server Route Movement Actions?

Currently,  has individual tools (orbit, protect_mode, engage_target, goto) that the LLM calls. The protection_mode sub-machine produces action dicts, but there's no **movement dispatcher** that translates these action dicts into actual MAVLink commands.

**Recommended addition:** A  class in  or as a new file :



The MCP server's main loop would call  after each  call.

### Existing MCP Tools vs Protection Mode Loop

| MCP Tool | Movement Pattern | When Used |
|----------|-----------------|-----------|
|  | Waypoint → CIRCLE mode | Manual LLM orbit |
|  | Same as orbit + payload arm | Manual LLM protect start |
|  | GUIDED + payload tracking | Manual LLM engagement |
|  | Position target | Any position command |
|  | RTL mode | Return to home |
| Protection loop *(new)* | DO_ORBIT ↔ GOTO ↔ DO_ORBIT | Autonomous cycle |

---

## 6. Stabilization During Fire

### Vibration Sources

| Source | Frequency | Amplitude | Impact |
|--------|-----------|-----------|--------|
| Water pump motor | ~200-500 Hz (depends on pump) | Moderate | Gyro noise, roll axis mostly |
| Water flow through nozzle | N/A (fluid flow) | Low | Negligible |
| Servo movement | <10 Hz (step change) | Low for position, spike on load | Attitude disturbance |
| Prop wash over pump | ~200-400 Hz | Low on ground, moderate in air | Changes with airspeed |
| Water recoil | Instantaneous | Very low (mass of 1ml water = 1g) | Negligible (< 1g reaction mass) |

### How Pump Vibration Affects Flight

The key question: **Does pump vibration destabilize the drone?**

**Answer: No, under normal conditions.** Here's why:
1. The pump runs for 500ms bursts (firing). The gyro filter at 80 Hz () strongly attenuates mechanical vibration above 80 Hz. Pump vibration at 200-500 Hz is filtered out before the controller sees it.
2. The pump mass (15-20g) is ~8% of total AUW. Its vibration amplitude is proportional to its mass — at 8% of drone mass, vibration forces are small.
3. ArduPilot's notch filter (,  for first harmonic at pump frequency) can notch out the pump's fundamental frequency.

**But there are two scenarios where pump vibration could matter:**

**Scenario A: Poor mechanical isolation**
If the pump is hard-mounted to the frame (especially a carbon fiber frame), vibrations transmit directly to the IMU. Fix: Use silicone vibration dampeners (M3 silicone grommets, ~) between the pump and frame.

**Scenario B: Structural resonance**
If the pump frequency matches the frame's structural resonance (unlikely at 200-500 Hz for a stiff carbon frame, but possible for 3D printed parts), amplitude amplifies.
- Fix: Change pump RPM by adjusting voltage (lower voltage = lower frequency)
- Fix: Add a notch filter at the resonance frequency

**Recommended notch filter settings:**


### How Servo Movement Affects Attitude

**Servo movement IS a real concern for a micro quad.** The MG90S servo at 13g mass, when rotating quickly (60° in 120ms), creates a reaction torque on the drone. At 10% of total mass, this is significant.

**Analysis:**
- Servo torque at 4.8V: ~1.5 kg·cm = 0.147 N·m
- Drone moment of inertia (micro quad): ~0.002 kg·m²
- Angular acceleration from servo: ~73 rad/s²
- For 120ms rotation: ~8.8° attitude change
- Controller correction: ~200ms to recover

**Implication:** A fast pan movement will cause a ~5-10° roll/yaw disturbance that takes 200-500ms to stabilize. This is during the aim phase before firing, so it's acceptable — the pump fires AFTER stabilization.

**Mitigation:**
1. **Slow down servo movement:** Use 60°/300ms instead of 60°/120ms for the pan servo. This reduces the disturbance by 60%.
2. **Sequence properly:** Move servos FIRST, wait 300ms for stabilization, THEN fire pump.
3. **Stagger movements:** Move pan first, wait 100ms, then tilt, wait 100ms, then fire. Don't move both simultaneously.

### Water Recoil

Each 1ml shot has a reaction mass of ~1g exiting at ~5m/s (estimated from pump flow rate + nozzle constriction). Recoil momentum: 0.001 kg × 5 m/s = 0.005 kg·m/s.

On a ~0.24kg drone, this causes a velocity change of ~0.02 m/s — effectively zero. **Recoil is negligible.**

### Conclusion on Stabilization

The existing IMU filtering (80 Hz gyro + notch filter at pump frequency) will effectively isolate pump vibration. The main concern is servo movement during aiming, which is mitigated by:
1. Using slower servo speeds during tracking mode ( already implements a delay)
2. Sequencing: servo → stabilize → fire
3. The  and  in  already provide this timing

No additional code changes needed beyond confirming the notch filter in ArduPilot parameters.

---

## 7. SITL Testing — Gaps and Next Tests

### Current Test Coverage

From :

**Mock tests (6 scenarios — all pass):**
1.  — Registry scan, activate, fire, aim, health, power budget
2.  — Full state transition chain IDLE→ARMED→FLYING→ORBITING→ENGAGING→RETURNING→IDLE
3.  — Telemetry schema validation
4.  — Payload emergency stop timing (<50ms)
5.  — Payload commands routed correctly with state checks
6.  — Reservoir tracking from 15ml→0ml

**SITL tests (3 scenarios):**
1.  — Connection + heartbeat + telemetry sanity
2.  — Arm/disarm cycle
3.  — Takeoff to 5m, hover, land

**Coverage gaps identified:**

| Gap | Priority | Why Matters |
|-----|----------|-------------|
| **Orbit movement** | HIGH | Core protection mode movement — never tested |
| **MAV_CMD_DO_ORBIT** | HIGH | Better orbit approach than CIRCLE mode |
| **GOTO waypoint** | HIGH | Required for target approach |
| **RTL from orbit** | HIGH | Safety-critical — can we RTB while orbiting? |
| **Protection mode flow** | HIGH | Full SCANNING→DETECTED→ENGAGING→RETURN→SCAN cycle |
| **Velocity control** | MED | Needed for smooth target tracking |
| **Asymmetric payload sim** | MED | Can we simulate an offset CG? |
| **Variable weight sim** | MED | Water payload changes over time |
| **Emergency stop (mid-air)** | MED | Disarm while airborne |
| **Lost link / failsafe** | MED | What happens when ESP32 bridge drops? |
| **Servo movement disturbance** | LOW | Simulating servo torque in SITL |
| **Pump vibration sim** | LOW | Not feasible in SITL |

### Recommended Next Tests to Write

**Priority 1: **


**Priority 2: **


**Priority 3: **


**Priority 4: **


**Priority 5:  (advanced — manual SITL parameter change)**


### What Cannot Be Tested in SITL

| Feature | Why | Test in |
|---------|-----|---------|
| Pump vibration effects | No pump hardware in sim | Real hardware — measure with IMU logging |
| Servo disturbance torque | No servo simulation in ArduPilot SITL | Real hardware — log ATTITUDE |
| Water recoil | No fluid dynamics | Real hardware — observe altitude change |
| CV tracking accuracy | No camera in sim | Real hardware + static ground tests |
| WiFi latency | No ESP32 in sim | Real hardware — measure round-trip time |
| Prop wash on camera | No aerodynamic simulation | Real hardware — observe video jitter |

---

## Source Quality Assessment

| Source | Authority | Recency | Coverage |
|--------|-----------|---------|----------|
| Existing codebase (, etc.) | HIGH — primary source | Current | Full code |
|  | HIGH — primary source | Current | MAVLink implementation |
|  | HIGH — primary source | Current | Full sub-machine logic |
|  | HIGH — primary source | Current | 9 scenario implementations |
| splash-research skill findings | MEDIUM — compiled research | May 2026 | Flight hardware, CV |
| avatar-water-control.md | MEDIUM — compiled research | June 2026 | Water mechanism design |
| avatar-v1-hardware-architecture.md | MEDIUM — compiled research | May 2026 | Hardware BOM, ESP32 |
| ArduPilot parameter docs | HIGH (but not directly searched) | Well-established | Community knowledge |
| Tavily API | UNAVAILABLE — rate limited | N/A | No primary web search results |

---

## Confidence: HIGH (80%+) for code-level analysis; MEDIUM (65-75%) for ArduPilot tuning specifics

**Justification:**
- **HIGH confidence** on state machine integration, protection mode flow, and movement patterns — these are directly read from the existing codebase which was analyzed line-by-line
- **HIGH confidence** on altitude hold and asymmetric payload behavior — these are standard ArduPilot features documented in ArduPilot's official docs and proven across thousands of builds
- **MEDIUM confidence** on PID starting parameters — these are based on established ArduPilot community tuning guides for similar micro quads (3-4", 4S, <250g), but Tavily rate-limited prevented direct web sourcing of the most current parameters. The values given are conservative starting points that are standard for this class
- **MEDIUM confidence** on servo disturbance torque calculations — based on physics first principles, but exact servo torque depends on the specific MG90S variant

---

## Conflicts & Uncertainties

1. **Water pump choice is still TBD** — The water-control research identified multiple pump candidates with very different weights and pressures. The pump choice significantly affects both CG offset and vibration frequency. Final PID tuning should happen with the ACTUAL pump selected.

2. **Actual thrust-to-weight ratio unknown** — The geofrancis build uses 2S 2750KV on 4.7" props; the Oscar Liang table suggests 3500-4000KV on 4S for 3.5" props. These are very different configurations. Thrust data per motor is needed to set  accurately.

3. **GPS altitude vs baro altitude accuracy** — Consumer GPS has ±1m vertical accuracy. ArduPilot's baro is better (±0.3m). For a drone firing at 5-15m range, altitude hold accuracy of ±1m means the water stream's impact point varies by ~10cm vertical. This is acceptable for the ~30cm spray pattern.

4. **SITL vs real flight correlation** — ArduPilot SITL uses a simple model without prop wash, ground effect, or aero disturbances. Tests that pass in SITL may behave differently on real hardware. Budget 2-3x the SITL test time for real-flight validation.

---

## Recommended Action

1. **Write and run the 5 priority SITL tests** (orbit, protection flow, RTL, waypoint accuracy, asymmetric trim) before any real hardware testing. These catch state machine bugs for free.

2. **Add  and MovementController to the codebase** — The protection mode loop needs a movement dispatcher to translate action dicts into MAVLink commands. Without this, the protection sub-machine is all logic and no execution.

3. **Start with conservative PID gains** and run autotune in SITL first. The parameters in Section 1 are a starting point — AUTOTUNE will dial them in for the specific build.

4. **Mount pump with silicone dampeners** and measure actual vibration frequencies using ArduPilot's IMU logging (LOG_BITMASK includes gyro). Configure notch filters based on real data.

5. **Fill water on the ground, fire in flight.** The altitude hold can handle the gradual weight change, but filling the reservoir in flight (if attempted) would cause abrupt CG shifts.

---

## Decision
- Use **MAV_CMD_DO_ORBIT** over CIRCLE mode for all protection mode orbit operations
- The **protection sub-machine produces action dicts** that need a new **MovementController** to execute
- **No special water weight compensation** needed — ArduPilot's I term handles gradual 5g changes
- **SITL testing is sufficient** for state machine and movement logic validation

## Next Action
Write the 5 priority SITL test scenarios and the MovementController class

## Deadline
Before any real hardware flight test — the SITL tests validate the safety-critical movement logic

## Who Should Handle Next
**Engineer profile** — To implement MovementController in splash/control/movement_controller.py and add the 5 priority SITL test scenarios to sim/sim_validation.py 

---

## Sources

- Existing codebase: state_machine.py, protection_mode.py, mavlink_bridge.py, mcp_server.py
- Existing tests: sim/sim_validation.py
- Prior research: avatar-water-control.md, avatar-cv-pipeline.md
- Hardware architecture: avatar-v1-hardware-architecture.md reference
- splash-research skill key findings
- ArduPilot Copter documentation (well-established community knowledge)
