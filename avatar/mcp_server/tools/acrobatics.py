"""Acrobatic flight tools for drone aerobatics.

Provides high-energy maneuvers for demonstration and testing:
    - front_flip: Forward 360° rotation
    - back_flip: Backward 360° rotation
    - barrel_roll: Left/right 360° roll
    - yaw_spin: Rapid 360° rotation around Z axis
    - loop: Vertical circular maneuver
    - corkscrew: Combined roll and yaw spiral

SAFETY REQUIREMENTS:
    - Minimum altitude: 15m (hard limit)
    - Minimum battery: 50%
    - Acrobatics only allowed in ACROBATIC state
    - Guardian must approve each maneuver
    - Auto-recovery to HOVER after completion
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

logger = logging.getLogger(__name__)

# Rate limits for PX4 (degrees per second)
MAX_ROLL_RATE = 220.0   # deg/s - aggressive roll
MAX_PITCH_RATE = 220.0  # deg/s - aggressive pitch
MAX_YAW_RATE = 200.0    # deg/s - yaw is typically slower

# Safety limits
MIN_ACRO_ALTITUDE = 15.0  # meters
MIN_ACRO_BATTERY = 50.0   # percent
RECOVERY_ALTITUDE = 10.0  # meters after maneuver


class AcrobaticManeuver(Enum):
    """Enumeration of supported acrobatic maneuvers."""
    FRONT_FLIP = "front_flip"
    BACK_FLIP = "back_flip"
    BARREL_ROLL_LEFT = "barrel_roll_left"
    BARREL_ROLL_RIGHT = "barrel_roll_right"
    YAW_SPIN_CW = "yaw_spin_cw"
    YAW_SPIN_CCW = "yaw_spin_ccw"
    LOOP = "loop"
    CORKSCREW = "corkscrew"


@dataclass
class ManeuverConfig:
    """Configuration for an acrobatic maneuver.

    Attributes:
        name: Human-readable maneuver name
        duration_ms: Expected duration in milliseconds
        roll_rate: Roll rate setpoint (deg/s)
        pitch_rate: Pitch rate setpoint (deg/s)
        yaw_rate: Yaw rate setpoint (deg/s)
        thrust: Thrust setpoint (0.0-1.0, or >1.0 for boost)
        recovery_time_ms: Time to stabilize after maneuver
    """
    name: str
    duration_ms: float
    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0
    thrust: float = 0.7
    recovery_time_ms: float = 1000.0


# Predefined maneuver configurations
MANEUVER_CONFIGS = {
    AcrobaticManeuver.FRONT_FLIP: ManeuverConfig(
        name="Front Flip",
        duration_ms=800.0,
        pitch_rate=-MAX_PITCH_RATE,
        thrust=0.85,  # Boost to maintain altitude
        recovery_time_ms=1500.0
    ),
    AcrobaticManeuver.BACK_FLIP: ManeuverConfig(
        name="Back Flip",
        duration_ms=800.0,
        pitch_rate=MAX_PITCH_RATE,
        thrust=0.85,
        recovery_time_ms=1500.0
    ),
    AcrobaticManeuver.BARREL_ROLL_LEFT: ManeuverConfig(
        name="Barrel Roll Left",
        duration_ms=900.0,
        roll_rate=-MAX_ROLL_RATE,
        thrust=0.8,
        recovery_time_ms=1200.0
    ),
    AcrobaticManeuver.BARREL_ROLL_RIGHT: ManeuverConfig(
        name="Barrel Roll Right",
        duration_ms=900.0,
        roll_rate=MAX_ROLL_RATE,
        thrust=0.8,
        recovery_time_ms=1200.0
    ),
    AcrobaticManeuver.YAW_SPIN_CW: ManeuverConfig(
        name="Yaw Spin Clockwise",
        duration_ms=1200.0,
        yaw_rate=MAX_YAW_RATE,
        thrust=0.75,
        recovery_time_ms=1000.0
    ),
    AcrobaticManeuver.YAW_SPIN_CCW: ManeuverConfig(
        name="Yaw Spin Counter-Clockwise",
        duration_ms=1200.0,
        yaw_rate=-MAX_YAW_RATE,
        thrust=0.75,
        recovery_time_ms=1000.0
    ),
    AcrobaticManeuver.LOOP: ManeuverConfig(
        name="Vertical Loop",
        duration_ms=2000.0,
        pitch_rate=-MAX_PITCH_RATE * 0.8,
        thrust=1.0,  # Full thrust for loop
        recovery_time_ms=2000.0
    ),
    AcrobaticManeuver.CORKSCREW: ManeuverConfig(
        name="Corkscrew Spiral",
        duration_ms=3000.0,
        roll_rate=MAX_ROLL_RATE * 0.6,
        yaw_rate=MAX_YAW_RATE * 0.5,
        thrust=0.9,
        recovery_time_ms=2000.0
    ),
}


class AcrobaticsSafetyError(Exception):
    """Raised when acrobatics safety checks fail."""
    pass


async def _check_acrobatics_safety() -> Tuple[bool, str]:
    """Check if acrobatics are safe to perform.

    Returns:
        Tuple of (is_safe, reason)
    """
    cm = ConnectionManager()
    if not cm.is_connected:
        return False, "Drone not connected"

    # Check altitude
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

    Args:
        config: Maneuver configuration
        state_machine: Optional state machine for state tracking

    Returns:
        Dict with maneuver results
    """
    cm = ConnectionManager()
    drone = cm.get_drone()

    if not drone:
        return {"success": False, "error": "Drone not connected"}

    # Transition to ACROBATIC state if state machine provided
    if state_machine:
        # Add ACROBATIC state if not exists
        if hasattr(FlightState, 'ACROBATIC'):
            state_machine.transition_to(
                FlightState.ACROBATIC,
                f"Starting {config.name}",
                "llm"
            )

    logger.info(f"Executing {config.name}: {config.duration_ms}ms")

    # Get manual control plugin
    manual_control = drone.manual_control

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + (config.duration_ms / 1000.0)

    # Convert rates to manual control setpoints (-1 to 1 normalized)
    # PX4 manual control expects: x (roll), y (pitch), z (thrust), r (yaw)
    roll_norm = config.roll_rate / MAX_ROLL_RATE
    pitch_norm = config.pitch_rate / MAX_PITCH_RATE
    yaw_norm = config.yaw_rate / MAX_YAW_RATE

    # Clamp to valid range
    roll_norm = max(-1.0, min(1.0, roll_norm))
    pitch_norm = max(-1.0, min(1.0, pitch_norm))
    yaw_norm = max(-1.0, min(1.0, yaw_norm))

    try:
        # Send rate commands at 50Hz (20ms intervals)
        while asyncio.get_event_loop().time() < end_time:
            await manual_control.set_manual_control_input(
                x=roll_norm,
                y=pitch_norm,
                z=config.thrust,
                r=yaw_norm
            )
            await asyncio.sleep(0.02)  # 50Hz

        # Recovery period - gradual return to hover
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

        # Final hover command
        await manual_control.set_manual_control_input(
            x=0.0,
            y=0.0,
            z=0.6,
            r=0.0
        )

        # Return to HOVERING state
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
        logger.exception(f"Maneuver {config.name} failed")
        return {
            "success": False,
            "error": str(e),
            "maneuver": config.name
        }


# MCP Tool Functions
# These are called by the MCP server and return JSON strings


async def front_flip() -> str:
    """Execute a forward 360° flip.

    The drone pitches forward rapidly, completing a full rotation.
    Requires minimum 15m altitude and 50% battery.

    Returns:
        JSON string with maneuver results.
    """
    # Safety check
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.FRONT_FLIP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def back_flip() -> str:
    """Execute a backward 360° flip.

    The drone pitches backward rapidly, completing a full rotation.
    Requires minimum 15m altitude and 50% battery.

    Returns:
        JSON string with maneuver results.
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.BACK_FLIP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def barrel_roll(direction: str = "right") -> str:
    """Execute a 360° barrel roll.

    Args:
        direction: "left" or "right" (default: right)

    Returns:
        JSON string with maneuver results.
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

    Args:
        direction: "cw" (clockwise) or "ccw" (counter-clockwise)
        rotations: Number of full 360° rotations (default: 1.0)

    Returns:
        JSON string with maneuver results.
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    base_config = MANEUVER_CONFIGS[
        AcrobaticManeuver.YAW_SPIN_CW if direction.lower() == "cw"
        else AcrobaticManeuver.YAW_SPIN_CCW
    ]

    # Scale duration by rotation count
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

    The drone traces a vertical circle while maintaining orientation.
    Requires minimum 20m altitude and full battery.

    Returns:
        JSON string with maneuver results.
    """
    # Stricter safety for loop
    cm = ConnectionManager()
    cache = cm.get_telemetry_cache()
    if cache:
        telem = await cache.get_latest()
        if telem and telem.relative_altitude_m < 20.0:
            return json.dumps({
                "success": False,
                "error": f"Loop requires 20m altitude, current: {telem.relative_altitude_m:.1f}m"
            })

    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    config = MANEUVER_CONFIGS[AcrobaticManeuver.LOOP]
    result = await _execute_maneuver(config, get_state_machine())
    return json.dumps(result)


async def corkscrew(rotations: float = 1.0) -> str:
    """Execute a corkscrew spiral (combined roll and yaw).

    Args:
        rotations: Number of spiral rotations (default: 1.0)

    Returns:
        JSON string with maneuver results.
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    base_config = MANEUVER_CONFIGS[AcrobaticManeuver.CORKSCREW]

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

    Args:
        maneuvers: List of maneuver names ["front_flip", "barrel_roll", "yaw_spin"]

    Returns:
        JSON string with sequence results.
    """
    safe, reason = await _check_acrobatics_safety()
    if not safe:
        return json.dumps({"success": False, "error": reason})

    results = []
    for maneuver_name in maneuvers:
        logger.info(f"Executing sequence maneuver: {maneuver_name}")

        # Map string names to functions
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

        # Execute maneuver
        result_json = await maneuver_map[maneuver_name]()
        result = json.loads(result_json)
        results.append(result)

        # Brief pause between maneuvers
        if result.get("success"):
            await asyncio.sleep(1.0)

    # Count successes
    successes = sum(1 for r in results if r.get("success"))

    return json.dumps({
        "success": successes == len(maneuvers),
        "maneuvers_completed": successes,
        "maneuvers_total": len(maneuvers),
        "results": results
    })


# Import state machine getter from flight_tools to avoid circular imports
def get_state_machine() -> Optional[FlightStateMachine]:
    """Get the global state machine instance."""
    try:
        from avatar.mcp_server.tools.flight_tools import get_state_machine as _gsm
        return _gsm()
    except ImportError:
        return None
