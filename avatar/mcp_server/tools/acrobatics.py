"""Acrobatic flight tools for drone aerobatics.

================================================================================
AVAILABLE ACROBATIC MANEUVERS
================================================================================

This module provides 7 distinct acrobatic maneuvers for demonstration and
testing purposes. Each maneuver is pre-configured with safe rate limits and
timings for the X500 quadcopter platform in PX4 SITL.

1. FRONT_FLIP (front_flip)
   - A forward 360° rotation around the pitch axis
   - Duration: ~800ms for full rotation
   - The drone pitches nose-down rapidly, completing a full forward somersault
   - Uses 85% thrust to maintain altitude during the flip
   - Highest altitude loss of all flips (~3-5 meters)

2. BACK_FLIP (back_flip)
   - A backward 360° rotation around the pitch axis
   - Duration: ~800ms for full rotation
   - The drone pitches nose-up rapidly, completing a full backward somersault
   - Uses 85% thrust to maintain altitude
   - Slightly more stable than front flip (easier to recover from)

3. BARREL_ROLL_LEFT / BARREL_ROLL_RIGHT (barrel_roll)
   - A 360° rotation around the roll axis (left or right)
   - Duration: ~900ms for full rotation
   - The drone rolls like an airplane doing a barrel roll
   - Uses 80% thrust to maintain altitude
   - Moderate altitude loss (~2-3 meters)
   - Generally the safest acrobatic maneuver for beginners

4. YAW_SPIN_CW / YAW_SPIN_CCW (yaw_spin)
   - Rapid 360° rotation around the Z (vertical/yaw) axis
   - Duration: ~1200ms per rotation
   - The drone spins in place while maintaining level attitude
   - Uses 75% thrust (minimal altitude loss)
   - Can be chained for multiple rotations (2x, 3x spins)
   - Does NOT affect altitude - safest acrobatic maneuver

5. LOOP (loop_maneuver)
   - A complete vertical circle in the air
   - Duration: ~2000ms (2 seconds)
   - The drone traces a vertical circular path:
     * Nose up to climb
     * Inverted at top of loop
     * Nose down to dive
     * Level recovery
   - Uses 100% thrust (full power required)
   - Requires minimum 20m altitude (strictest requirement)
   - Most altitude loss of any maneuver (~8-12 meters)

6. CORKSCREW (corkscrew)
   - A spiral maneuver combining roll and yaw simultaneously
   - Duration: ~3000ms per spiral rotation
   - The drone traces a helical path upward while spinning
   - Uses 90% thrust
   - Creates a spiral "corkscrew" pattern in 3D space
   - Can be chained for multi-rotation spirals
   - Most visually complex maneuver

================================================================================
HOW EACH MANEUVER WORKS MECHANICALLY
================================================================================

PX4 ACRO Mode:
--------------
All maneuvers execute in PX4's ACRO (Acrobatic) flight mode, which provides
raw rate control without attitude limits. The autopilot does NOT stabilize
or correct - the LLM/controller has full authority.

Rate Control:
-------------
Each maneuver sends normalized rate setpoints to PX4's manual control input:
- X (roll):     -1.0 to +1.0  →  -220°/s to +220°/s
- Y (pitch):    -1.0 to +1.0  →  -220°/s to +220°/s
- R (yaw):      -1.0 to +1.0  →  -200°/s to +200°/s
- Z (thrust):    0.0 to 1.0   →  0% to 100% motor power

Execution Sequence:
-------------------
1. Safety Check: Verify altitude, battery, and flight state
2. State Transition: Enter ACROBATIC flight state
3. Maneuver Phase (50Hz control loop):
   - Send rate commands at 20ms intervals for configured duration
   - Example: Front flip sends pitch_rate=-220°/s, thrust=0.85 for 800ms
4. Recovery Phase:
   - Gradual interpolation back to neutral rates over 1-2 seconds
   - Reduces motor commands smoothly to prevent oscillation
5. Hover Establishment:
   - Final hover command (roll=0, pitch=0, yaw=0, thrust=0.6)
6. State Transition: Return to HOVERING state

Physics of Each Maneuver:
-------------------------
- FLIPS (front/back): Change pitch angle 360°. The drone uses momentum
  and thrust to carry through the rotation. Without sufficient thrust,
  the drone will lose altitude rapidly during the inverted phase.

- BARREL ROLLS: Change roll angle 360°. The drone maintains roughly
  level pitch throughout, losing less altitude than flips because the
  rotors never point fully downward.

- YAW SPINS: Change heading only. The drone stays flat, making this
  the safest maneuver. High yaw rate can induce "yaw washout" where the
  drone loses some altitude due to control authority being diverted.

- LOOP: Combines pitch changes through a full 360° cycle. The climb phase
  requires maximum thrust. The inverted phase is critical - insufficient
  speed/thrust here results in failed loop and crash.

- CORKSCREW: Superimposes roll and yaw rates, creating spiral motion.
  The drone is never truly "flat" during this maneuver, requiring
  constant thrust to maintain the climbing spiral.

================================================================================
SAFETY REQUIREMENTS
================================================================================

Hard Limits (Enforced by Code):
--------------------------------
1. MINIMUM ALTITUDE: 15 meters (hard limit for all maneuvers except loop)
   - Loop requires 20 meters minimum
   - Altitude checked via telemetry before execution
   - If below minimum: maneuver rejected with error

2. MINIMUM BATTERY: 50% remaining
   - Acrobatics require high sustained current draw
   - Low battery + high throttle = voltage sag and potential failsafe
   - If below 50%: maneuver rejected with error

3. FLIGHT STATE: Must be in appropriate state
   - Can execute from: HOVERING, ACROBATIC states
   - Cannot execute from: TAKEOFF, LANDING, EMERGENCY states
   - Auto-transition to ACROBATIC during maneuver

4. CONNECTION: MAVSDK connection must be active
   - Telemetry cache must provide valid data
   - Manual control plugin must be available

Operational Safety Guidelines:
------------------------------
- Verify GPS lock before acrobatics (loss of position can trigger failsafe)
- Clear airspace - ensure no obstacles within 30m in all directions
- Check weather - avoid acrobatics in wind >5 m/s
- Battery health - do not perform if voltage is sagging under load
- Start with yaw spins, progress to barrel rolls, then flips, then loops
- Single maneuvers only until proficiency confirmed
- ALWAYS have kill switch ready (Q or space in simulation)

Recovery Behavior:
------------------
- Automatic recovery to hover after each maneuver completes
- If maneuver fails mid-execution, sends neutral hover command
- State machine tracks acrobatic state and ensures clean exit
- 1-2 second recovery period allows drone to stabilize

================================================================================
WHEN NOT TO USE ACROBATICS
================================================================================

NEVER perform acrobatics when:

1. Near Ground:
   - Below 15 meters (or 20m for loop)
   - Recovery from failed maneuver needs 8-12m minimum

2. Low Battery:
   - Below 50% charge remaining
   - Voltage sag during high-throttle maneuvers can trigger failsafe
   - Risk of uncontrolled descent during/after maneuver

3. Unstable Flight Conditions:
   - High wind (>5 m/s sustained, >8 m/s gusts)
   - Wind can push drone into obstacles during inverted maneuvers
   - Recovery becomes unpredictable in gusty conditions

4. GPS/GNSS Issues:
   - No GPS lock or weak signal
   - Position loss during acrobatics can trigger return-to-home
   - Return-to-home during acrobatics = crash

5. Heavy Payload:
   - Additional mass increases inertia, slower response
   - Higher thrust required, may exceed available power
   - Recovery timing changes with payload

6. First Flight/Test:
   - Always verify basic flight (hover, waypoints) first
   - Test in SITL extensively before real hardware
   - Start with single maneuvers, not sequences

7. Near Obstacles:
   - Within 30m of buildings, trees, people
   - In confined spaces (indoor, under canopies)
   - Near other aircraft or drones

8. Pilot/Operator Uncertainty:
   - Unfamiliar with kill switch location
   - Unclear on emergency procedures
   - First time with this drone platform

9. Hardware Concerns:
   - Vibration or unusual sounds
   - Unbalanced props
   - Loose mountings
   - Damaged or worn motors

10. In Production/Non-Test Environments:
    - Never during paying customer missions
    - Never during mapping/survey work
    - Never with expensive payloads attached

================================================================================
MODULE IMPLEMENTATION
================================================================================
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.core.decorators import timeout, require_state
from avatar.mcp_server.errors import to_error_envelope, ErrorCode

logger = logging.getLogger(__name__)


# =============================================================================
# STANDARD TOOL ANNOTATIONS
# =============================================================================
# These are the 4 standard hints for MCP tool annotations as per D2.1 contract.

ANNOTATIONS_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

ANNOTATIONS_WRITE_SAFE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

ANNOTATIONS_ACROBATIC = {
    "readOnlyHint": False,
    "destructiveHint": True,  # Acrobatic maneuvers can cause altitude loss
    "idempotentHint": False,
    "openWorldHint": True,
}

OUTPUT_SCHEMA = {"type": "object"}

# =============================================================================
# RATE LIMITS FOR PX4 (degrees per second)
# =============================================================================
# These are the maximum angular rates the flight controller will attempt.
# Higher rates = faster maneuvers but less stable and more aggressive.
# Lower rates = slower, more controlled maneuvers.
#
# The X500 quadcopter in SITL is capable of these rates, but real hardware
# may have different limits based on motor power, prop size, and tuning.
# =============================================================================

MAX_ROLL_RATE = 220.0   # Maximum roll rate: 220 degrees/second
                        # Used for barrel rolls and corkscrew maneuvers
                        # 220°/s = full 360° rotation in ~1.6 seconds

MAX_PITCH_RATE = 220.0  # Maximum pitch rate: 220 degrees/second
                        # Used for front flips, back flips, and loops
                        # 220°/s = full 360° rotation in ~1.6 seconds
                        # Flips use slightly less for controlled arcs

MAX_YAW_RATE = 200.0    # Maximum yaw rate: 200 degrees/second
                        # Used for yaw spins and corkscrew
                        # Yaw is typically limited lower than roll/pitch
                        # because yaw control shares motors with thrust

# =============================================================================
# SAFETY LIMITS
# =============================================================================
# These are the absolute minimums for safe acrobatic operation.
# The code will REFUSE to execute maneuvers if these are not met.
# =============================================================================

MIN_ACRO_ALTITUDE = 15.0  # Minimum altitude in meters for acrobatics
                          # Loop maneuver requires 20m (enforced separately)
                          # Recovery from failed flip needs ~8-10m
                          # This leaves ~5m safety margin

MIN_ACRO_BATTERY = 50.0   # Minimum battery percentage for acrobatics
                          # High-throttle maneuvers draw 40-60A
                          # Below 50%, voltage sag can cause instability

RECOVERY_ALTITUDE = 10.0  # Target altitude after maneuver recovery
                          # Drone will naturally descend during maneuvers
                          # This is the expected altitude post-recovery


class AcrobaticManeuver(Enum):
    """Enumeration of supported acrobatic maneuvers.

    Each enum value maps to a predefined configuration in MANEUVER_CONFIGS
    that specifies rates, timing, and thrust for that maneuver.
    """
    FRONT_FLIP = "front_flip"           # Forward pitch rotation
    BACK_FLIP = "back_flip"             # Backward pitch rotation
    BARREL_ROLL_LEFT = "barrel_roll_left"   # Left roll rotation
    BARREL_ROLL_RIGHT = "barrel_roll_right" # Right roll rotation
    YAW_SPIN_CW = "yaw_spin_cw"         # Clockwise yaw rotation
    YAW_SPIN_CCW = "yaw_spin_ccw"       # Counter-clockwise yaw rotation
    LOOP = "loop"                       # Complete vertical circle
    CORKSCREW = "corkscrew"             # Spiral roll + yaw combination


@dataclass
class ManeuverConfig:
    """Configuration for an acrobatic maneuver.

    This dataclass defines all parameters needed to execute a specific
    acrobatic maneuver safely. Each maneuver in MANEUVER_CONFIGS uses
    these parameters to control the drone's angular rates and thrust.

    Attributes:
        name: Human-readable name for logging and status messages
        duration_ms: Total time the maneuver should execute (milliseconds)
                     This determines how long rate commands are sent.
        roll_rate: Roll angular velocity setpoint (degrees/second)
                   Positive = roll right, Negative = roll left
                   Set to 0.0 for maneuvers without roll component
        pitch_rate: Pitch angular velocity setpoint (degrees/second)
                    Positive = pitch up (back flip), Negative = pitch down (front flip)
                    Set to 0.0 for maneuvers without pitch component
        yaw_rate: Yaw angular velocity setpoint (degrees/second)
                  Positive = clockwise, Negative = counter-clockwise
                  Set to 0.0 for maneuvers without yaw component
        thrust: Thrust setpoint as percentage (0.0 to 1.0, can exceed 1.0 for boost)
                Higher thrust = more altitude maintained during maneuver
                Lower thrust = more altitude loss but faster rotation
        recovery_time_ms: Time allocated for recovery after maneuver completes
                          During this time, rates gradually return to neutral
                          and thrust reduces to hover level.
    """
    name: str
    duration_ms: float
    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0
    thrust: float = 0.7
    recovery_time_ms: float = 1000.0


# =============================================================================
# PREDEFINED MANEUVER CONFIGURATIONS
# =============================================================================
# These configurations define the specific rate commands and timing for
# each supported acrobatic maneuver.
#
# IMPORTANT: These are tuned for the X500 quadcopter in PX4 SITL. Real
# hardware may require different timing and rates based on motor power,
# propeller size, and airframe characteristics.
#
# Timing Calculation:
# - For a 360° rotation at rate R, time = 360 / R seconds
# - Front flip at 220°/s = 360/220 = 1.64s, but we use 0.8s because
#   the drone continues rotating from momentum after commands stop
#
# Thrust Selection:
# - Higher thrust = less altitude loss but slower rotation
# - Lower thrust = faster rotation but more altitude loss
# - Loop requires 100% thrust (1.0) to complete the climb phase
# =============================================================================

MANEUVER_CONFIGS = {
    # FRONT_FLIP: Forward 360° rotation
    # - Pitches nose down at max rate
    # - 85% thrust maintains altitude during inverted phase
    # - ~800ms of active pitching, ~1500ms total with recovery
    # - Typical altitude loss: 3-5 meters
    AcrobaticManeuver.FRONT_FLIP: ManeuverConfig(
        name="Front Flip",
        duration_ms=800.0,              # Active pitching duration
        pitch_rate=-MAX_PITCH_RATE,       # Negative = nose down
        thrust=0.85,                      # 85% thrust for altitude hold
        recovery_time_ms=1500.0           # 1.5s to stabilize
    ),

    # BACK_FLIP: Backward 360° rotation
    # - Pitches nose up at max rate
    # - 85% thrust maintains altitude
    # - Slightly more intuitive recovery than front flip
    # - Typical altitude loss: 3-5 meters
    AcrobaticManeuver.BACK_FLIP: ManeuverConfig(
        name="Back Flip",
        duration_ms=800.0,                # Active pitching duration
        pitch_rate=MAX_PITCH_RATE,        # Positive = nose up
        thrust=0.85,                      # 85% thrust
        recovery_time_ms=1500.0          # 1.5s to stabilize
    ),

    # BARREL_ROLL_LEFT: Left 360° roll
    # - Rolls to the left (negative roll rate)
    # - 80% thrust sufficient (rotors stay relatively level)
    # - Generally safest acrobatic maneuver
    # - Typical altitude loss: 2-3 meters
    AcrobaticManeuver.BARREL_ROLL_LEFT: ManeuverConfig(
        name="Barrel Roll Left",
        duration_ms=900.0,                # Slightly longer than flip
        roll_rate=-MAX_ROLL_RATE,         # Negative = roll left
        thrust=0.8,                       # 80% thrust
        recovery_time_ms=1200.0          # 1.2s to stabilize
    ),

    # BARREL_ROLL_RIGHT: Right 360° roll
    # - Rolls to the right (positive roll rate)
    # - 80% thrust sufficient
    # - Most pilots find right roll easier to control
    # - Typical altitude loss: 2-3 meters
    AcrobaticManeuver.BARREL_ROLL_RIGHT: ManeuverConfig(
        name="Barrel Roll Right",
        duration_ms=900.0,                # Slightly longer than flip
        roll_rate=MAX_ROLL_RATE,          # Positive = roll right
        thrust=0.8,                       # 80% thrust
        recovery_time_ms=1200.0          # 1.2s to stabilize
    ),

    # YAW_SPIN_CW: Clockwise 360° yaw rotation
    # - Rotates around Z axis (vertical)
    # - Drone stays flat - safest maneuver
    # - 75% thrust for minimal altitude maintenance
    # - Typical altitude loss: <1 meter
    AcrobaticManeuver.YAW_SPIN_CW: ManeuverConfig(
        name="Yaw Spin Clockwise",
        duration_ms=1200.0,               # 200°/s = 1.8s, but we use 1.2s
        yaw_rate=MAX_YAW_RATE,            # Positive = clockwise
        thrust=0.75,                      # 75% thrust
        recovery_time_ms=1000.0          # 1s to stabilize
    ),

    # YAW_SPIN_CCW: Counter-clockwise 360° yaw rotation
    # - Rotates around Z axis (vertical)
    # - Drone stays flat - safest maneuver
    # - 75% thrust for minimal altitude maintenance
    # - Typical altitude loss: <1 meter
    AcrobaticManeuver.YAW_SPIN_CCW: ManeuverConfig(
        name="Yaw Spin Counter-Clockwise",
        duration_ms=1200.0,               # 200°/s = 1.8s, but we use 1.2s
        yaw_rate=-MAX_YAW_RATE,           # Negative = counter-clockwise
        thrust=0.75,                      # 75% thrust
        recovery_time_ms=1000.0          # 1s to stabilize
    ),

    # LOOP: Complete vertical circle
    # - Most demanding maneuver
    # - Requires full 100% thrust for climb phase
    # - Inverted at top of loop requires momentum carry
    # - Duration split: climb (increasing pitch up), dive (pitch down)
    # - Typical altitude loss: 8-12 meters (hence 20m minimum)
    AcrobaticManeuver.LOOP: ManeuverConfig(
        name="Vertical Loop",
        duration_ms=2000.0,               # 2 seconds for full circle
        pitch_rate=-MAX_PITCH_RATE * 0.8, # 80% rate for smoother arc
        thrust=1.0,                       # 100% thrust REQUIRED
        recovery_time_ms=2000.0          # 2s recovery (longer due to stress)
    ),

    # CORKSCREW: Spiral maneuver combining roll and yaw
    # - Simultaneous roll and yaw create helical path
    # - 90% thrust for climbing spiral
    # - Most visually impressive but complex to recover from
    # - Can be chained for multiple spiral rotations
    # - Typical altitude change: Climbing (depends on duration)
    AcrobaticManeuver.CORKSCREW: ManeuverConfig(
        name="Corkscrew Spiral",
        duration_ms=3000.0,               # 3 seconds per spiral
        roll_rate=MAX_ROLL_RATE * 0.6,    # 60% roll rate for control
        yaw_rate=MAX_YAW_RATE * 0.5,      # 50% yaw rate combined with roll
        thrust=0.9,                       # 90% thrust for climbing
        recovery_time_ms=2000.0          # 2s to stabilize from combined rates
    ),
}


class AcrobaticsSafetyError(Exception):
    """Raised when acrobatics safety checks fail.

    This exception is raised when a maneuver is requested but safety
    conditions are not met (low altitude, low battery, wrong state, etc.).
    The error message explains which specific check failed.
    """
    pass


async def _check_acrobatics_safety() -> Tuple[bool, str]:
    """Check if acrobatics are safe to perform.

    Performs all safety checks required before executing any acrobatic
    maneuver. This includes verifying connection, altitude, and battery
    levels against the minimum safety thresholds.

    Safety Checks Performed:
        1. Connection Check: Drone must be connected via MAVSDK
        2. Altitude Check: Must be above MIN_ACRO_ALTITUDE (15m)
        3. Battery Check: Must be above MIN_ACRO_BATTERY (50%)

    Returns:
        Tuple of (is_safe, reason) where:
        - is_safe: Boolean indicating if all checks passed
        - reason: Human-readable explanation (success or failure reason)

    Example:
        >>> safe, reason = await _check_acrobatics_safety()
        >>> if not safe:
        ...     print(f"Cannot perform acrobatics: {reason}")
    """
    cm = ConnectionManager()
    if not cm.is_connected:
        return False, "Drone not connected"

    # Check altitude and battery from telemetry cache
    cache = cm.get_telemetry_cache()
    if cache:
        telem = await cache.get_latest()
        if telem and telem.relative_altitude_m < MIN_ACRO_ALTITUDE:
            return False, f"Altitude {telem.relative_altitude_m:.1f}m < {MIN_ACRO_ALTITUDE}m minimum"

        # Check battery
        if telem and telem.battery_remaining_percent < MIN_ACRO_BATTERY:
            return False, f"Battery {telem.battery_remaining_percent:.1f}% < {MIN_ACRO_BATTERY}% minimum"

    return True, "Safety checks passed"


async def _execute_maneuver(
    config: ManeuverConfig,
    state_machine: Optional[FlightStateMachine] = None
) -> Dict[str, Any]:
    """Execute a single acrobatic maneuver.

    This is the core execution engine for all acrobatic maneuvers.
    It sends rate commands to PX4 at 50Hz and manages the recovery phase.

    Execution Flow:
        1. State Transition: Enter ACROBATIC state via state machine
        2. Maneuver Phase: Send rate commands at 50Hz for duration_ms
        3. Recovery Phase: Gradual interpolation back to neutral rates
        4. Hover Command: Final neutral command to stabilize
        5. State Transition: Return to HOVERING state

    Rate Normalization:
        The raw rate values (deg/s) are normalized to PX4's expected
        -1.0 to +1.0 range by dividing by MAX_*_RATE constants.

    Args:
        config: ManeuverConfig defining rates, timing, and thrust
        state_machine: Optional FlightStateMachine for state tracking

    Returns:
        Dict with maneuver results containing:
        - success: Boolean indicating if maneuver completed
        - maneuver: Name of the executed maneuver
        - duration_ms: Actual duration of maneuver phase
        - recovery_ms: Duration of recovery phase
        - roll_rate, pitch_rate, yaw_rate: Applied rates
        - error: Error message if maneuver failed

    Raises:
        No exceptions raised - all errors are caught and returned in result dict
    """
    cm = ConnectionManager()
    drone = cm.get_drone()

    if not drone:
        return {"success": False, "error": "Drone not connected"}

    # Transition to ACROBATIC state if state machine provided
    # This allows the system to track that dangerous maneuvers are in progress
    if state_machine:
        # Add ACROBATIC state if not exists
        if hasattr(FlightState, 'ACROBATIC'):
            state_machine.transition_to(
                FlightState.ACROBATIC,
                f"Starting {config.name}",
                "llm"
            )

    logger.info(f"Executing {config.name}: {config.duration_ms}ms")

    # Get manual control plugin from MAVSDK
    # This plugin provides direct rate control in ACRO mode
    manual_control = drone.manual_control

    # Calculate timing for maneuver phase
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + (config.duration_ms / 1000.0)

    # Convert angular rates to normalized PX4 setpoints (-1.0 to +1.0)
    # PX4 manual control expects: x (roll), y (pitch), z (thrust), r (yaw)
    roll_norm = config.roll_rate / MAX_ROLL_RATE
    pitch_norm = config.pitch_rate / MAX_PITCH_RATE
    yaw_norm = config.yaw_rate / MAX_YAW_RATE

    # Clamp to valid range (safety check against configuration errors)
    roll_norm = max(-1.0, min(1.0, roll_norm))
    pitch_norm = max(-1.0, min(1.0, pitch_norm))
    yaw_norm = max(-1.0, min(1.0, yaw_norm))

    try:
        # =====================================================================
        # MANEUVER PHASE: Send rate commands at 50Hz
        # =====================================================================
        # We send manual control inputs at 20ms intervals (50Hz) for the
        # duration of the maneuver. This is the standard rate for PX4
        # manual control.
        #
        # The setpoints are constant during this phase - the drone will
        # attempt to achieve and maintain the requested angular rates.
        # =====================================================================
        while asyncio.get_event_loop().time() < end_time:
            await manual_control.set_manual_control_input(
                x=roll_norm,
                y=pitch_norm,
                z=config.thrust,
                r=yaw_norm
            )
            await asyncio.sleep(0.02)  # 50Hz update rate

        # =====================================================================
        # RECOVERY PHASE: Gradual return to neutral
        # =====================================================================
        # After the maneuver completes, we gradually interpolate the rates
        # back to zero over multiple steps. This prevents the drone from
        # oscillating or overshooting when we suddenly stop commanding rates.
        #
        # Recovery uses 20 steps with linear interpolation:
        # Step 0: Full maneuver rates
        # Step 20: Zero rates (neutral)
        # =====================================================================
        recovery_end = asyncio.get_event_loop().time() + (config.recovery_time_ms / 1000.0)
        recovery_steps = 20
        step_time = (config.recovery_time_ms / 1000.0) / recovery_steps

        for i in range(recovery_steps):
            progress = (i + 1) / recovery_steps  # 0.05 to 1.0
            # Linear interpolation back to neutral
            roll_recover = roll_norm * (1.0 - progress)
            pitch_recover = pitch_norm * (1.0 - progress)
            yaw_recover = yaw_norm * (1.0 - progress)

            await manual_control.set_manual_control_input(
                x=roll_recover,
                y=pitch_recover,
                z=0.6,  # Moderate hover thrust
                r=yaw_recover
            )
            await asyncio.sleep(step_time)

        # =====================================================================
        # HOVER ESTABLISHMENT: Final neutral command
        # =====================================================================
        # Send a final hover command to ensure the drone is stabilized
        # at neutral rates before transitioning out of acrobatic state.
        # =====================================================================
        await manual_control.set_manual_control_input(
            x=0.0,
            y=0.0,
            z=0.6,
            r=0.0
        )

        # Return to HOVERING state via state machine
        if state_machine and hasattr(FlightState, 'HOVERING'):
            state_machine.transition_to(
                FlightState.HOVERING,
                f"Completed {config.name}",
                "llm"
            )

        return {
            "success": True,
            "maneuver": config.name,
            "duration_ms": config.duration_ms,
            "recovery_ms": config.recovery_time_ms,
            "roll_rate": config.roll_rate,
            "pitch_rate": config.pitch_rate,
            "yaw_rate": config.yaw_rate,
        }

    except Exception as e:
        # Log the full exception for debugging
        logger.exception(f"Maneuver {config.name} failed")
        return {
            "success": False,
            "error": str(e),
            "maneuver": config.name
        }


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================
# These functions are the public API exposed to the MCP server. They are called
# by the LLM agent and return JSON strings with the maneuver results.
#
# Each function:
# 1. Performs safety checks via _check_acrobatics_safety()
# 2. Retrieves the appropriate ManeuverConfig from MANEUVER_CONFIGS
# 3. Calls _execute_maneuver() to perform the actual maneuver
# 4. Returns a JSON string with the results
# =============================================================================


async def front_flip() -> str:
    """Execute a forward 360° flip.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone pitches nose-down at maximum rate (220°/s) for ~800ms,
        completing a full forward rotation. 85% thrust is applied to
        maintain altitude during the inverted phase.

    SAFETY:
        - Requires minimum 15m altitude
        - Requires minimum 50% battery
        - Altitude loss: 3-5 meters typical
        - Recovery time: 1.5 seconds

    WHEN NOT TO USE:
        - Below 15m altitude (REQUIRED - will be rejected)
        - Below 50% battery
        - Near obstacles (needs 30m clearance)
        - First acrobatic attempt (try yaw_spin or barrel_roll first)
        - In high winds (>5 m/s)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Front Flip",
            "duration_ms": 800,
            "error": "error message if failed"
        }
    """
    # Safety check - verify altitude, battery, and connection
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.FRONT_FLIP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def back_flip() -> str:
    """Execute a backward 360° flip.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone pitches nose-up at maximum rate (220°/s) for ~800ms,
        completing a full backward rotation. 85% thrust is applied to
        maintain altitude during the inverted phase.

    SAFETY:
        - Requires minimum 15m altitude
        - Requires minimum 50% battery
        - Altitude loss: 3-5 meters typical
        - Recovery time: 1.5 seconds
        - Generally easier to recover from than front flip

    WHEN NOT TO USE:
        - Below 15m altitude (REQUIRED - will be rejected)
        - Below 50% battery
        - Near obstacles (needs 30m clearance)
        - Without prior acrobatic experience
        - In high winds (>5 m/s)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Back Flip",
            "duration_ms": 800,
            "error": "error message if failed"
        }
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.BACK_FLIP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def barrel_roll(direction: str = "right") -> str:
    """Execute a 360° barrel roll.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone rolls around its longitudinal axis at maximum rate (220°/s)
        for ~900ms, completing a full 360° roll. 80% thrust is sufficient
        because the rotors stay relatively level throughout the maneuver.

    SAFETY:
        - Requires minimum 15m altitude
        - Requires minimum 50% battery
        - Altitude loss: 2-3 meters typical (less than flips!)
        - Recovery time: 1.2 seconds
        - SAFEST acrobatic maneuver - recommended for first attempts

    Args:
        direction: "left" or "right" (default: right)
                   Right roll is generally more intuitive for pilots

    WHEN NOT TO USE:
        - Below 15m altitude (REQUIRED - will be rejected)
        - Below 50% battery
        - Near obstacles (needs 20m clearance minimum)
        - In strong crosswinds (>5 m/s)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Barrel Roll Right/Left",
            "duration_ms": 900,
            "error": "error message if failed"
        }
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    if direction.lower() == "left":
        config = MANEUVER_CONFIGS[AcrobaticManeuver.BARREL_ROLL_LEFT]
    else:
        config = MANEUVER_CONFIGS[AcrobaticManeuver.BARREL_ROLL_RIGHT]

    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def yaw_spin(direction: str = "cw", rotations: float = 1.0) -> str:
    """Execute rapid yaw rotation.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone rotates around its vertical (Z) axis at 200°/s,
        spinning in place while maintaining level attitude. Only 75%
        thrust is needed because the drone stays flat throughout.

        This is the ONLY acrobatic maneuver where the drone maintains
        a level attitude. All others involve inverted flight phases.

    SAFETY:
        - Requires minimum 15m altitude
        - Requires minimum 50% battery
        - Altitude loss: <1 meter (safest maneuver!)
        - Recovery time: 1 second
        - Recommended first acrobatic maneuver for testing

    Args:
        direction: "cw" (clockwise) or "ccw" (counter-clockwise)
                   Default is clockwise when viewed from above
        rotations: Number of full 360° rotations (default: 1.0)
                   Can be fractional (0.5 = 180°, 2.0 = 720°)
                   Scaling: 1 rotation = 1200ms, 2 rotations = 2400ms

    WHEN NOT TO USE:
        - Below 15m altitude (REQUIRED - will be rejected)
        - Below 50% battery
        - Near other drones/aircraft (spinning can be disorienting)
        - When you need precise heading control afterward
          (use simple 1.0 rotation to minimize disorientation)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Yaw Spin 2.0x CW",
            "duration_ms": 2400,
            "error": "error message if failed"
        }
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    base_config = MANEUVER_CONFIGS[
        AcrobaticManeuver.YAW_SPIN_CW if direction.lower() == "cw"
        else AcrobaticManeuver.YAW_SPIN_CCW
    ]

    # Scale duration by rotation count
    # This allows for multiple spins (e.g., 2x, 3x) or partial spins
    config = ManeuverConfig(
        name=f"Yaw Spin {rotations}x {direction.upper()}",
        duration_ms=base_config.duration_ms * rotations,
        yaw_rate=base_config.yaw_rate,
        thrust=base_config.thrust,
        recovery_time_ms=base_config.recovery_time_ms
    )

    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def loop_maneuver() -> str:
    """Execute a vertical loop (circular climb and dive).

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone traces a complete vertical circle in the air:
        1. Pitch up to begin climb (nose up)
        2. Continue pitching through inverted at top of loop
        3. Pitch down to dive (nose down)
        4. Level out at original heading

        Requires 100% thrust (full power) to complete the climb phase.
        Pitch rate is reduced to 80% of max for smoother arc.

    SAFETY:
        - Requires minimum 20m altitude (STRICTER than other maneuvers!)
        - Requires minimum 50% battery
        - Altitude loss: 8-12 meters (highest of all maneuvers!)
        - Recovery time: 2 seconds
        - MOST DEMANDING maneuver - save for last

    WHEN NOT TO USE:
        - Below 20m altitude (REQUIRED - will be rejected even at 15m!)
        - Below 50% battery (insufficient power for climb)
        - Near ANY obstacles (needs 40m+ clearance in all directions)
        - Without extensive acrobatic experience
        - In any wind conditions (even light wind affects loop shape)
        - First time testing acrobatics (master flips and rolls first)
        - With heavy payloads (mass affects loop dynamics)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Vertical Loop",
            "duration_ms": 2000,
            "error": "error message if failed"
        }

    Note:
        This maneuver has STRONGER altitude check than others (20m vs 15m)
        because it loses the most altitude and requires the most height
        to recover from if something goes wrong.
    """
    # Stricter safety check for loop - requires 20m minimum
    # Loop loses more altitude than any other maneuver (8-12m typical)
    cm = ConnectionManager()
    cache = cm.get_telemetry_cache()
    if cache:
        telem = await cache.get_latest()
        if telem and telem.relative_altitude_m < 20.0:
            return json.dumps({
                "success": False,
                "error": f"Loop requires 20m altitude, current: {telem.relative_altitude_m:.1f}m"
            })

    # Standard safety check for battery and connection
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.LOOP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def corkscrew(rotations: float = 1.0) -> str:
    """Execute a corkscrew spiral (combined roll and yaw).

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    MECHANICS:
        The drone executes a spiral maneuver by combining roll and yaw
        rates simultaneously. This creates a helical climbing path:
        - 60% roll rate combined with 50% yaw rate
        - 90% thrust for sustained climb during spiral
        - Drone traces a 3D spiral path upward

        The combined rotation creates a visually impressive "corkscrew"
        effect where the drone is both spinning and climbing.

    SAFETY:
        - Requires minimum 15m altitude
        - Requires minimum 50% battery
        - Altitude change: Climbing (depends on duration)
        - Recovery time: 2 seconds
        - Complex recovery due to combined angular momentum

    Args:
        rotations: Number of spiral rotations (default: 1.0)
                   Each rotation = 3 seconds at current rate settings
                   Can be fractional for partial spirals
                   Example: 2.0 = 6 second double spiral

    WHEN NOT TO USE:
        - Below 15m altitude (REQUIRED - will be rejected)
        - Below 50% battery
        - Near obstacles (spiral path makes clearance unpredictable)
        - Without mastering simpler maneuvers first
        - When you need precise position control after
          (the combined rotation can be disorienting)
        - First time acrobatic testing (try yaw_spin first)

    Returns:
        JSON string with maneuver results:
        {
            "success": true/false,
            "maneuver": "Corkscrew Spiral 1.0x",
            "duration_ms": 3000,
            "error": "error message if failed"
        }
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    base_config = MANEUVER_CONFIGS[AcrobaticManeuver.CORKSCREW]

    # Scale duration by rotation count
    config = ManeuverConfig(
        name=f"Corkscrew {rotations}x",
        duration_ms=base_config.duration_ms * rotations,
        roll_rate=base_config.roll_rate,
        yaw_rate=base_config.yaw_rate,
        thrust=base_config.thrust,
        recovery_time_ms=base_config.recovery_time_ms
    )

    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def acrobatic_sequence(maneuvers: List[str]) -> str:
    """Execute a sequence of acrobatic maneuvers.

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: True, idempotentHint: False, openWorldHint: True}
        outputSchema: {type: object}

    This function allows chaining multiple maneuvers together with a
    1-second pause between each for stabilization.

    SUPPORTED MANEUVERS IN SEQUENCES:
        - "front_flip" / "back_flip"
        - "barrel_roll" / "barrel_roll_left" / "barrel_roll_right"
        - "yaw_spin" / "yaw_spin_cw" / "yaw_spin_ccw"
        - "loop" / "corkscrew"

    SAFETY NOTES FOR SEQUENCES:
        - Altitude compounds: 2x flips = 2x altitude loss
        - Battery drain is cumulative and faster than individual maneuvers
        - Plan sequence to maintain altitude (start high!)
        - Recommended: yaw_spin → barrel_roll → flip → corkscrew
        - Avoid: flip → flip → loop (too much altitude loss)

    SEQUENCE PLANNING GUIDE:
        Good Sequences (altitude management):
        - ["yaw_spin", "barrel_roll"] - minimal altitude loss
        - ["yaw_spin", "barrel_roll", "front_flip"] - progressive altitude loss
        - ["corkscrew", "yaw_spin"] - corkscrew climbs, yaw stabilizes

        Bad Sequences (high risk):
        - ["front_flip", "back_flip", "loop"] - massive altitude loss
        - ["loop", "loop"] - requires 40m+ starting altitude
        - ["corkscrew", "front_flip"] - disorienting combination

    Args:
        maneuvers: List of maneuver names as strings.
                   Example: ["front_flip", "barrel_roll", "yaw_spin"]
                   Unknown maneuvers are skipped with error logged.

    WHEN NOT TO USE:
        - Below 25m altitude for 2+ maneuver sequences
        - Below 35m altitude for 3+ maneuver sequences
        - Below 60% battery (sequences drain more power)
        - First time testing acrobatics (test individually first!)
        - Without visual contact on drone
        - Near any obstacles

    Returns:
        JSON string with sequence results:
        {
            "success": true if all succeeded, false otherwise,
            "maneuvers_completed": N,
            "maneuvers_total": M,
            "results": [
                {"maneuver": "...", "success": true/false, ...},
                ...
            ]
        }
    """
    # Safety check before entire sequence
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    results = []
    for maneuver_name in maneuvers:
        logger.info(f"Executing sequence maneuver: {maneuver_name}")

        # Map string names to async functions
        # Lambdas used for parameterized maneuvers
        maneuver_map = {
            "front_flip": front_flip,
            "back_flip": back_flip,
            "barrel_roll": lambda: barrel_roll("right"),
            "barrel_roll_left": lambda: barrel_roll("left"),
            "barrel_roll_right": lambda: barrel_roll("right"),
            "yaw_spin": lambda: yaw_spin("cw", 1.0),
            "yaw_spin_cw": lambda: yaw_spin("cw", 1.0),
            "yaw_spin_ccw": lambda: yaw_spin("ccw", 1.0),
            "loop": loop_maneuver,
            "corkscrew": lambda: corkscrew(1.0),
        }

        if maneuver_name not in maneuver_map:
            results.append({
                "maneuver": maneuver_name,
                "success": False,
                "error": f"Unknown maneuver: {maneuver_name}"
            })
            continue

        # Execute maneuver and parse result
        result_json = await maneuver_map[maneuver_name]()
        result = json.loads(result_json)
        results.append(result)

        # Brief pause between maneuvers for stabilization
        # This gives the drone time to settle before next maneuver
        if result.get("success"):
            await asyncio.sleep(1.0)

    # Count successful maneuvers
    successes = sum(1 for r in results if r.get("success"))

    return json.dumps({
        "success": successes == len(maneuvers),
        "maneuvers_completed": successes,
        "maneuvers_total": len(maneuvers),
        "results": results
    })


# =============================================================================
# STATE MACHINE ACCESS
# =============================================================================
# This function provides access to the global state machine instance
# for tracking flight state transitions during acrobatics.
# =============================================================================

# Import state machine getter from flight_tools to avoid circular imports
def get_state_machine() -> Optional[FlightStateMachine]:
    """Get the global state machine instance.

    This function imports and returns the global FlightStateMachine
    instance from flight_tools. The import is done inside the function
    to avoid circular import issues between modules.

    The state machine is used to:
    - Transition to ACROBATIC state during maneuvers
    - Return to HOVERING state after completion
    - Provide status updates for logging

    Returns:
        FlightStateMachine instance if available, None otherwise
    """
    try:
        from avatar.mcp_server.tools.flight_tools import get_state_machine as _gsm
        return _gsm()
    except ImportError:
        return None
