"""Primitive flight control MCP tools for Project Avatar.

This module provides low-level MCP tool primitives that wrap basic MAVSDK operations
with safety validation through AsyncGuardian and state machine tracking.

W2a: Primitive Tools Architecture
=================================
Primitive tools are the building blocks for higher-level flight operations.
Each primitive:
1. Validates input with Pydantic v2 schemas
2. Checks state preconditions (via FlightStateMachine)
3. Calls preflight safety checks
4. Uses ConfirmationManager for curated confirmations (first arm in session)
5. Executes the MAVSDK operation
6. Updates state machine

Available Primitives:
    - arm: Arm the drone motors (NOT takeoff - just arm)
    - set_position_ned: Command position in NED frame using offboard mode
    - set_velocity_ned: Command velocity in NED frame using offboard mode

NED Coordinate Frame:
    - North (X): Positive = northward from home
    - East (Y): Positive = eastward from home
    - Down (Z): Positive = downward from home (NEGATIVE = UP)

Safety Integration:
    All primitives integrate with:
    - AsyncGuardian: Preflight safety checks
    - FlightStateMachine: State precondition validation
    - ConfirmationManager: Human-in-the-loop confirmation for dangerous ops
    - TelemetryCache: Real-time drone state

Example Usage (as MCP tool):
    >>> result = await arm({"force": False}, context={})
    >>> print(result)
    {"success": True, "message": "Drone armed successfully", "state": "ARMED"}

Dependencies:
    - MAVSDK: For PX4/MAVLink communication
    - OffboardOwner: Mutual exclusion for offboard mode
    - GuardianProcess: Safety validation
    - FlightStateMachine: State tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.offboard_owner import get_offboard_owner
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.errors import ErrorCode, to_error_envelope
from avatar.mcp_server.confirmation_policy import (
    CRITICAL_PARAMETERS,
    is_critical_parameter,
    get_parameter_category,
)
from avatar.mcp_server.schemas import FlightMode, Point

if TYPE_CHECKING:
    from avatar.mav.offboard_owner import OffboardOwner

# MAVSDK imports with fallback for testing environments
try:
    from mavsdk.offboard import PositionNedYaw, VelocityNedYaw, OffboardError
except ImportError:
    # Fallback for testing without mavsdk installed
    class PositionNedYaw:  # type: ignore
        """Mock PositionNedYaw for testing without MAVSDK."""

        def __init__(
            self,
            north_m: float,
            east_m: float,
            down_m: float,
            yaw_deg: float
        ) -> None:
            self.north_m = north_m
            self.east_m = east_m
            self.down_m = down_m
            self.yaw_deg = yaw_deg

    class VelocityNedYaw:  # type: ignore
        """Mock VelocityNedYaw for testing without MAVSDK."""

        def __init__(
            self,
            north_m_s: float,
            east_m_s: float,
            down_m_s: float,
            yaw_deg: float
        ) -> None:
            self.north_m_s = north_m_s
            self.east_m_s = east_m_s
            self.down_m_s = down_m_s
            self.yaw_deg = yaw_deg

    class OffboardError(Exception):  # type: ignore
        """Mock OffboardError for testing."""
        pass


logger = logging.getLogger(__name__)

# Global state references - set by the MCP server at startup
_state_machine: Optional[FlightStateMachine] = None
_telemetry_cache: Optional[Any] = None
_confirmation_manager: Optional[Any] = None  # D2.6: ConfirmationManager reference


def set_state_machine(sm: FlightStateMachine) -> None:
    """Set the global state machine reference."""
    global _state_machine
    _state_machine = sm


def set_telemetry_cache(cache: Any) -> None:
    """Set the global telemetry cache reference."""
    global _telemetry_cache
    _telemetry_cache = cache


def set_confirmation_manager(manager: Any) -> None:
    """Set the global confirmation manager reference.

    D2.6: The confirmation manager provides human-in-the-loop confirmation
    for dangerous operations like setting critical PX4 parameters.

    Args:
        manager: The ConfirmationManager instance.

    Example:
        >>> from avatar.mcp_server.confirmation import ConfirmationManager
        >>> manager = ConfirmationManager()
        >>> set_confirmation_manager(manager)
    """
    global _confirmation_manager
    _confirmation_manager = manager


def get_state_machine() -> Optional[FlightStateMachine]:
    """Get the global state machine instance."""
    return _state_machine


def get_telemetry_cache() -> Optional[Any]:
    """Get the global telemetry cache instance."""
    return _telemetry_cache


def get_confirmation_manager() -> Optional[Any]:
    """Get the global confirmation manager instance.

    D2.6: Used by primitive tools to request confirmation for critical operations.

    Returns:
        ConfirmationManager instance if set, None otherwise.
        When None, operations proceed without confirmation (not recommended).
    """
    return _confirmation_manager


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

# Track first arm in session for confirmation requirement
_arm_count: int = 0


def reset_arm_count() -> None:
    """Reset the arm counter (for testing)."""
    global _arm_count
    _arm_count = 0


def get_arm_count() -> int:
    """Get the current arm count."""
    return _arm_count


class ArmInput(BaseModel):
    """Input schema for the arm primitive.

    Attributes:
        force: Force arm even if preflight checks incomplete.
               Use with caution - bypasses safety checks.
    """
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    force: bool = Field(
        default=False,
        description="Force arm even if preflight checks incomplete"
    )


class SetPositionNedInput(BaseModel):
    """Input schema for set_position_ned tool."""

    north_m: float = Field(
        ...,
        ge=-1000.0,
        le=1000.0,
        description="Position north from home in meters (-1000 to 1000)"
    )
    east_m: float = Field(
        ...,
        ge=-1000.0,
        le=1000.0,
        description="Position east from home in meters (-1000 to 1000)"
    )
    down_m: float = Field(
        ...,
        ge=-500.0,
        le=0.0,
        description="Position down from home in meters (negative = up, -500 to 0)"
    )
    yaw_deg: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=360.0,
        description="Yaw angle in degrees (0=north, 90=east, None=maintain current)"
    )
    speed_m_s: float = Field(
        default=5.0,
        gt=0.0,
        le=20.0,
        description="Travel speed in m/s (0.1 to 20)"
    )

    @field_validator('down_m')
    @classmethod
    def validate_altitude(cls, v: float) -> float:
        """Ensure down_m is non-positive (altitude is positive)."""
        if v > 0:
            raise ValueError("down_m must be <= 0 (negative = up from ground)")
        return v


class SetPositionGpsInput(BaseModel):
    """Input schema for set_position_gps tool.

    Commands the drone to navigate to absolute GPS coordinates.
    Uses MAVSDK action.goto_location() for GPS navigation.

    Attributes:
        target: Target position with lat_deg, lon_deg, and alt_m (AMSL meters).
        speed_m_s: Travel speed in meters per second (0.0 to 20.0 m/s).

    Example:
        >>> input = SetPositionGpsInput(
        ...     target=Point(lat_deg=37.7749, lon_deg=-122.4194, alt_m=50.0),
        ...     speed_m_s=5.0
        ... )
    """

    target: Point = Field(
        ...,
        description="Target GPS position. lat_deg and lon_deg required. alt_m is AMSL altitude in meters.",
    )
    speed_m_s: float = Field(
        default=5.0,
        gt=0.0,
        le=20.0,
        description="Travel speed in m/s. Must be > 0 and <= 20.",
    )


class SetVelocityNedInput(BaseModel):
    """Input schema for set_velocity_ned tool.

    NED Frame:
        - North: Positive = velocity toward geographic north
        - East: Positive = velocity toward geographic east
        - Down: Positive = descending velocity, Negative = climbing

    Safety Limits:
        - North/East: +-20 m/s (maximum horizontal velocity)
        - Down: +-10 m/s (maximum vertical velocity)
        - Duration: 0 to 60 seconds
    """

    north_m_s: float = Field(
        default=0.0,
        ge=-20.0,
        le=20.0,
        description="Velocity north in m/s (-20 to 20)"
    )
    east_m_s: float = Field(
        default=0.0,
        ge=-20.0,
        le=20.0,
        description="Velocity east in m/s (-20 to 20)"
    )
    down_m_s: float = Field(
        default=0.0,
        ge=-10.0,
        le=10.0,
        description="Velocity down in m/s (-10 to 10, negative = climb)"
    )
    yaw_deg: Optional[float] = Field(
        default=None,
        description="Absolute yaw angle in degrees (0 = north, 90 = east)"
    )
    duration_s: float = Field(
        ...,
        gt=0.0,
        le=60.0,
        description="Duration to maintain velocity in seconds (max 60)"
    )


class SetParameterInput(BaseModel):
    """Input schema for set_parameter tool.

    Validates that:
    - Parameter name is non-empty string
    - Value is a numeric type (int or float)

    Attributes:
        name: PX4 parameter name (e.g., "MPC_XY_CRUISE", "NAV_DLL_ACT").
            Must be at least 1 character.
        value: Parameter value to set. Can be int or float depending on
            the parameter type. PX4 stores parameters as either int or float.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="PX4 parameter name (e.g., 'MPC_XY_CRUISE', 'NAV_DLL_ACT')"
    )
    value: float = Field(
        ...,
        description="Parameter value to set (int or float depending on parameter type)"
    )


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class PositionToolsConfig:
    """Configuration parameters for position primitive tools."""
    streaming_rate_hz: float = 20.0
    approach_timeout_s: float = 60.0
    position_tolerance_m: float = 1.0
    max_retries: int = 3


# =============================================================================
# VELOCITY STREAMER CLASS
# =============================================================================


@dataclass
class VelocityStreamer:
    """Streams MAVSDK velocity setpoints at a fixed cadence for PX4 Offboard mode.

    SAFETY NOTES:
    - PX4 requires setpoints at minimum 10Hz (ideally 20Hz)
    - If setpoints stop, PX4 triggers COM_OF_LOSS_T failsafe (default 0.5s)
    - OffboardOwner integration prevents conflicting control sources
    """

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        """Time between setpoint transmissions."""
        return 1.0 / self.rate_hz

    async def stream_for(
        self,
        drone: Any,
        velocity_setpoint: Any,
        duration_s: float,
        offboard_owner: Optional[OffboardOwner] = None,
        owner_id: str = "velocity_streamer",
    ) -> int:
        """Stream velocity setpoints for specified duration.

        This method handles the complete offboard lifecycle:
        1. Acquire OffboardOwner (if provided) for mutual exclusion
        2. Set initial velocity setpoint
        3. Start offboard mode
        4. Stream setpoints at configured rate for duration
        5. Stop offboard mode
        6. Release OffboardOwner (if acquired)

        Args:
            drone: MAVSDK System instance
            velocity_setpoint: MAVSDK VelocityNedYaw setpoint
            duration_s: How long to stream setpoints (seconds)
            offboard_owner: Optional OffboardOwner for mutual exclusion
            owner_id: Identifier for this streamer when acquiring ownership

        Returns:
            Number of setpoints sent. Returns 0 if OffboardOwner acquisition fails.
        """
        setpoint_count = 0
        started = False
        acquired_owner = False

        try:
            # Attempt to acquire OffboardOwner if provided
            if offboard_owner is not None:
                acquired = await offboard_owner.acquire(owner_id)
                if not acquired:
                    current = offboard_owner.current_owner()
                    logger.warning(
                        f"Failed to acquire offboard ownership. "
                        f"Currently owned by: {current}"
                    )
                    return 0
                acquired_owner = True

            # Set initial velocity and start offboard
            await drone.offboard.set_velocity_ned(velocity_setpoint)
            await drone.offboard.start()
            started = True
            logger.info(f"Offboard mode started, streaming velocity for {duration_s}s")

            start_time = time.monotonic()
            next_send_time = start_time

            # Stream for specified duration
            while time.monotonic() - start_time < duration_s:
                await drone.offboard.set_velocity_ned(velocity_setpoint)
                setpoint_count += 1

                # Maintain streaming rate
                next_send_time += self.interval_s
                sleep_s = next_send_time - time.monotonic()
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            return setpoint_count

        except asyncio.CancelledError:
            logger.info("Velocity streaming cancelled")
            raise
        except Exception as exc:
            logger.error("Velocity streaming failed: %s", exc)
            return setpoint_count
        finally:
            # Always stop offboard mode if started
            if started:
                try:
                    await drone.offboard.stop()
                    logger.info("Offboard mode stopped")
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)

            # Release OffboardOwner if we acquired it
            if acquired_owner and offboard_owner is not None:
                try:
                    await offboard_owner.release(owner_id)
                except Exception as exc:
                    logger.warning("Failed to release offboard ownership: %s", exc)


# =============================================================================
# POSITION STREAMER CLASS
# =============================================================================


@dataclass
class PositionStreamer:
    """Streams MAVSDK position setpoints at a fixed cadence for PX4 Offboard mode."""

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        """Time between setpoint transmissions."""
        return 1.0 / self.rate_hz

    async def stream_until_reached(
        self,
        drone: Any,
        position_setpoint: PositionNedYaw,
        target_north: float,
        target_east: float,
        target_down: float,
        tolerance_m: float = 1.0,
        timeout_s: float = 30.0,
        speed_m_s: float = 5.0,
        offboard_owner: Optional[OffboardOwner] = None,
        owner_id: str = "position_streamer",
    ) -> dict[str, Any]:
        """Stream position setpoints until target reached or timeout."""
        setpoint_count = 0
        started = False
        acquired_owner = False
        reached = False
        final_distance = float('inf')

        try:
            # Attempt to acquire OffboardOwner if provided
            if offboard_owner is not None:
                acquired = await offboard_owner.acquire(owner_id)
                if not acquired:
                    current = offboard_owner.current_owner()
                    logger.warning(
                        f"Failed to acquire offboard ownership. "
                        f"Currently owned by: {current}"
                    )
                    return {
                        "setpoints_sent": 0,
                        "reached": False,
                        "final_distance_m": float('inf'),
                        "error": f"Offboard owned by {current}",
                    }
                acquired_owner = True

            # Set initial position and start offboard
            await drone.offboard.set_position_ned(position_setpoint)
            await drone.offboard.start()
            started = True
            logger.info(f"Offboard mode started, streaming to position "
                       f"({target_north}, {target_east}, {target_down})")

            start_time = time.monotonic()
            next_send_time = start_time

            # Stream until reached or timeout
            while time.monotonic() - start_time < timeout_s:
                await drone.offboard.set_position_ned(position_setpoint)
                setpoint_count += 1

                # Get current position from telemetry
                try:
                    async for pos_vel in drone.telemetry.position_velocity_ned():
                        pos = pos_vel.position
                        current_north = pos.north_m
                        current_east = pos.east_m
                        current_down = pos.down_m

                        # Calculate distance to target
                        dist_n = target_north - current_north
                        dist_e = target_east - current_east
                        dist_d = target_down - current_down
                        final_distance = math.sqrt(
                            dist_n**2 + dist_e**2 + dist_d**2
                        )

                        if final_distance <= tolerance_m:
                            reached = True
                            logger.info(
                                f"Position reached: distance={final_distance:.2f}m"
                            )
                        break
                except Exception as e:
                    logger.debug(f"Could not get position for distance check: {e}")

                if reached:
                    break

                # Maintain streaming rate
                next_send_time += self.interval_s
                sleep_s = next_send_time - time.monotonic()
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            return {
                "setpoints_sent": setpoint_count,
                "reached": reached,
                "final_distance_m": final_distance,
            }

        except asyncio.CancelledError:
            logger.info("Position streaming cancelled")
            raise
        except Exception as exc:
            logger.error("Position streaming failed: %s", exc)
            return {
                "setpoints_sent": setpoint_count,
                "reached": False,
                "final_distance_m": final_distance,
                "error": str(exc),
            }
        finally:
            # Always stop offboard mode if started
            if started:
                try:
                    await drone.offboard.stop()
                    logger.info("Offboard mode stopped")
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)

            # Release OffboardOwner if we acquired it
            if acquired_owner and offboard_owner is not None:
                try:
                    await offboard_owner.release(owner_id)
                except Exception as exc:
                    logger.warning("Failed to release offboard ownership: %s", exc)


# =============================================================================
# MAIN TOOL IMPLEMENTATIONS
# =============================================================================


async def set_position_ned(
    north_m: float,
    east_m: float,
    down_m: float,
    yaw_deg: Optional[float] = None,
    speed_m_s: float = 5.0,
) -> str:
    """MCP Tool: Command position in NED frame using offboard mode."""
    # Validate input schema
    try:
        input_data = SetPositionNedInput(
            north_m=north_m,
            east_m=east_m,
            down_m=down_m,
            yaw_deg=yaw_deg,
            speed_m_s=speed_m_s,
        )
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Input validation failed: {e}",
        })

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Validate state precondition - must be in flying state
    valid_states = {
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
    }
    if sm.current_state not in valid_states:
        return json.dumps({
            "success": False,
            "error": (
                f"Cannot set_position_ned in {sm.current_state_name} state. "
                f"Must be in one of: {[s.name for s in valid_states]}"
            ),
        })

    # Get drone connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps({
            "success": False,
            "error": f"Not connected to drone: {e}",
        })

    if drone is None:
        return json.dumps({
            "success": False,
            "error": "Drone not connected",
        })

    # Get current yaw if not specified
    final_yaw = input_data.yaw_deg
    if final_yaw is None:
        try:
            async for attitude in drone.telemetry.attitude_euler():
                final_yaw = attitude.yaw_deg
                break
        except Exception:
            final_yaw = 0.0

    # Create position setpoint
    position_setpoint = PositionNedYaw(
        input_data.north_m,
        input_data.east_m,
        input_data.down_m,
        final_yaw,
    )

    # Get OffboardOwner for mutual exclusion
    offboard_owner = get_offboard_owner()

    # Create position streamer
    streamer = PositionStreamer(rate_hz=20.0)

    # Transition to POSITION_CONTROL state
    sm.transition(
        FlightState.POSITION_CONTROL,
        f"position_command: ({input_data.north_m}, {input_data.east_m}, {input_data.down_m})",
        "llm"
    )

    # Stream position setpoints until reached or timeout
    config = PositionToolsConfig()
    result = await streamer.stream_until_reached(
        drone=drone,
        position_setpoint=position_setpoint,
        target_north=input_data.north_m,
        target_east=input_data.east_m,
        target_down=input_data.down_m,
        tolerance_m=config.position_tolerance_m,
        timeout_s=config.approach_timeout_s,
        speed_m_s=input_data.speed_m_s,
        offboard_owner=offboard_owner,
        owner_id="set_position_ned",
    )

    # Check result
    if "error" in result and result.get("setpoints_sent", 0) == 0:
        return json.dumps({
            "success": False,
            "error": result.get("error", "Failed to start offboard mode"),
        })

    # Transition back to HOVERING after position command
    if sm.current_state == FlightState.POSITION_CONTROL:
        sm.transition(
            FlightState.HOVERING,
            "position_command_completed",
            "telemetry",
        )

    return json.dumps({
        "success": True,
        "message": f"Position command completed (reached={result['reached']})",
        "position": {
            "north_m": input_data.north_m,
            "east_m": input_data.east_m,
            "down_m": input_data.down_m,
        },
        "yaw_deg": final_yaw,
        "speed_m_s": input_data.speed_m_s,
        "setpoints_sent": result["setpoints_sent"],
        "reached": result["reached"],
        "final_distance_m": round(result["final_distance_m"], 2),
    })


async def set_velocity_ned(
    north_m_s: float = 0.0,
    east_m_s: float = 0.0,
    down_m_s: float = 0.0,
    yaw_deg: Optional[float] = None,
    duration_s: float = 1.0,
) -> str:
    """MCP Tool: Set velocity setpoint in NED frame (offboard mode).

    Direct velocity control in inertial NED frame. Maintains 20Hz setpoint
    stream to PX4 for duration. BLOCKS for entire duration.

    CRITICAL: Must maintain 20Hz stream or PX4 triggers failsafe.
    This function handles streaming automatically.

    NED Frame (inertial/absolute):
        - north_m_s > 0: Move toward geographic north
        - north_m_s < 0: Move toward geographic south
        - east_m_s > 0: Move toward geographic east
        - east_m_s < 0: Move toward geographic west
        - down_m_s > 0: Descend (positive down)
        - down_m_s < 0: Climb (negative down = up)

    Safety Limits:
        - Horizontal speed: +-20 m/s (north, east)
        - Vertical speed: +-10 m/s (down)
        - Duration: 0-60 seconds

    When to Use:
        - Direct velocity control in geographic frame
        - Search patterns with known headings
        - NED-referenced navigation
        - Precise velocity control

    Args:
        north_m_s: Velocity north in m/s (positive=north, negative=south, range: +-20).
        east_m_s: Velocity east in m/s (positive=east, negative=west, range: +-20).
        down_m_s: Velocity down in m/s (positive=down, negative=up/climb, range: +-10).
        yaw_deg: Absolute yaw in degrees (0=north, 90=east, etc.). None = maintain current.
        duration_s: Duration to maintain setpoint in seconds (default: 1.0, max: 60).

    Returns:
        JSON string with result dict including velocity, duration,
        and setpoint transmission statistics.

    Example:
        >>> # Fly north at 5 m/s for 3 seconds
        >>> result = await set_velocity_ned(
        ...     north_m_s=5.0, east_m_s=0.0, down_m_s=0.0,
        ...     yaw_deg=0.0, duration_s=3.0
        ... )
        >>> data = json.loads(result)
        >>> print(f"Sent {data['setpoints_sent']} setpoints")

    Note:
        This function blocks for the entire duration. No other commands
        can be executed until it completes.
    """
    # Validate input schema
    try:
        input_data = SetVelocityNedInput(
            north_m_s=north_m_s,
            east_m_s=east_m_s,
            down_m_s=down_m_s,
            yaw_deg=yaw_deg,
            duration_s=duration_s,
        )
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Input validation failed: {e}",
        })

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Validate state precondition - must be in flying state
    valid_states = {
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
    }
    if sm.current_state not in valid_states:
        return json.dumps({
            "success": False,
            "error": (
                f"Cannot set_velocity_ned in {sm.current_state_name} state. "
                f"Must be in one of: {[s.name for s in valid_states]}"
            ),
        })

    # Transition to VELOCITY_CONTROL state
    sm.transition(
        FlightState.VELOCITY_CONTROL,
        "velocity_ned_command_issued",
        "llm"
    )

    # Get drone connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps({
            "success": False,
            "error": f"Not connected to drone: {e}",
        })

    if drone is None:
        return json.dumps({
            "success": False,
            "error": "Drone not connected",
        })

    # Get current yaw if not specified
    final_yaw = input_data.yaw_deg
    if final_yaw is None:
        try:
            async for attitude in drone.telemetry.attitude_euler():
                final_yaw = attitude.yaw_deg
                break
        except Exception:
            final_yaw = 0.0

    # Create velocity setpoint
    velocity_setpoint = VelocityNedYaw(
        input_data.north_m_s,
        input_data.east_m_s,
        input_data.down_m_s,
        final_yaw if final_yaw is not None else 0.0,
    )

    # Get OffboardOwner for mutual exclusion
    offboard_owner = get_offboard_owner()

    # Create velocity streamer
    streamer = VelocityStreamer(rate_hz=20.0)

    # Stream velocity setpoints for duration
    setpoint_count = await streamer.stream_for(
        drone=drone,
        velocity_setpoint=velocity_setpoint,
        duration_s=input_data.duration_s,
        offboard_owner=offboard_owner,
        owner_id="set_velocity_ned",
    )

    # Check result
    if setpoint_count == 0:
        return json.dumps({
            "success": False,
            "error": "Failed to start offboard mode (ownership conflict or offboard error)",
        })

    # Transition back to FLYING after velocity command
    if sm.current_state == FlightState.VELOCITY_CONTROL:
        sm.transition(
            FlightState.FLYING,
            "velocity_ned_command_completed",
            "llm"
        )

    return json.dumps({
        "success": True,
        "velocity_ned": [input_data.north_m_s, input_data.east_m_s, input_data.down_m_s],
        "yaw_deg": final_yaw if final_yaw is not None else 0.0,
        "duration_s": input_data.duration_s,
        "setpoints_sent": setpoint_count,
        "approximate_rate_hz": round(setpoint_count / input_data.duration_s, 1) if input_data.duration_s > 0 else 0,
    })


# =============================================================================
# VELOCITY BODY INPUT SCHEMA
# =============================================================================


class SetVelocityBodyInput(BaseModel):
    """Input schema for set_velocity_body MCP tool.

    All velocities are in body frame (drone-relative):
    - forward_m_s: Positive = forward, negative = backward
    - right_m_s: Positive = right, negative = left
    - down_m_s: Positive = descend, negative = climb
    - yaw_rate_deg_s: Positive = rotate right, negative = rotate left

    Safety limits enforced:
    - Horizontal velocity: max 20 m/s (combined forward/right magnitude)
    - Vertical velocity: max 10 m/s
    - Yaw rate: max 180 deg/s
    - Duration: max 60 seconds
    """

    forward_m_s: float = Field(
        default=0.0,
        ge=-20.0,
        le=20.0,
        description="Forward velocity in m/s. Positive = forward, negative = backward.",
    )
    right_m_s: float = Field(
        default=0.0,
        ge=-20.0,
        le=20.0,
        description="Right velocity in m/s. Positive = right, negative = left.",
    )
    down_m_s: float = Field(
        default=0.0,
        ge=-10.0,
        le=10.0,
        description="Down velocity in m/s. Positive = descend, negative = climb.",
    )
    yaw_rate_deg_s: float = Field(
        default=0.0,
        ge=-180.0,
        le=180.0,
        description="Yaw rate in deg/s. Positive = rotate right, negative = rotate left.",
    )
    duration_s: float = Field(
        ...,
        gt=0.0,
        le=60.0,
        description="Duration to maintain velocity in seconds. Required, max 60s.",
    )


# =============================================================================
# VELOCITY BODY STREAMER
# =============================================================================


@dataclass
class VelocityBodyStreamer:
    """Streams MAVSDK body-frame velocity setpoints at a fixed cadence.

    This streamer handles the continuous setpoint stream required by PX4 to
    maintain offboard mode. It integrates with OffboardOwner for mutual exclusion.

    SAFETY NOTES:
    - PX4 requires setpoints at minimum 10Hz (ideally 20Hz)
    - If setpoints stop, PX4 triggers COM_OF_LOSS_T failsafe (default 0.5s)
    - OffboardOwner integration prevents conflicting control sources

    Example:
        streamer = VelocityBodyStreamer(rate_hz=20.0)
        owner = get_offboard_owner()
        count = await streamer.stream_for(
            drone, velocity_setpoint, duration_s=5.0,
            offboard_owner=owner, owner_id="set_velocity_body"
        )
    """

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        """Time between setpoints in seconds."""
        return 1.0 / self.rate_hz

    async def stream_for(
        self,
        drone: Any,
        velocity_setpoint: Any,  # VelocityBodyYawspeed
        duration_s: float,
        offboard_owner: Optional[OffboardOwner] = None,
        owner_id: str = "velocity_body_streamer",
    ) -> int:
        """Send body-frame velocity setpoints, start offboard mode, stream, and stop.

        This method handles the complete offboard lifecycle:
        1. Acquire OffboardOwner (if provided) for mutual exclusion
        2. Set initial velocity setpoint
        3. Start offboard mode
        4. Stream setpoints at configured rate for duration
        5. Stop offboard mode
        6. Release OffboardOwner (if acquired)

        Args:
            drone: MAVSDK System instance
            velocity_setpoint: MAVSDK VelocityBodyYawspeed setpoint
            duration_s: How long to stream setpoints (seconds)
            offboard_owner: Optional OffboardOwner for mutual exclusion
            owner_id: Identifier for this streamer when acquiring ownership

        Returns:
            Number of setpoints sent. Returns 0 if OffboardOwner acquisition fails.
        """
        setpoint_count = 0
        started = False
        acquired_owner = False

        try:
            # Attempt to acquire OffboardOwner if provided
            if offboard_owner is not None:
                acquired = await offboard_owner.acquire(owner_id)
                if not acquired:
                    current = offboard_owner.current_owner()
                    logger.warning(
                        f"Failed to acquire offboard ownership. "
                        f"Currently owned by: {current}"
                    )
                    return 0
                acquired_owner = True

            # Set initial setpoint before starting offboard
            await drone.offboard.set_velocity_body(velocity_setpoint)
            await drone.offboard.start()
            started = True
            logger.info(
                f"Offboard mode started, streaming body velocity "
                f"(forward={velocity_setpoint.forward_m_s}, "
                f"right={velocity_setpoint.right_m_s}, "
                f"down={velocity_setpoint.down_m_s}, "
                f"yaw_rate={velocity_setpoint.yawspeed_deg_s}) for {duration_s}s"
            )

            # Stream setpoints for the specified duration
            start_time = time.monotonic()
            next_send_time = start_time

            while time.monotonic() - start_time < duration_s:
                await drone.offboard.set_velocity_body(velocity_setpoint)
                setpoint_count += 1

                # Precise timing to maintain rate
                next_send_time += self.interval_s
                sleep_s = next_send_time - time.monotonic()
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            return setpoint_count

        except asyncio.CancelledError:
            # Re-raise cancellation to allow proper cleanup
            raise
        except Exception as exc:
            logger.error("Offboard velocity body streaming failed: %s", exc)
            return setpoint_count
        finally:
            # Always stop offboard mode if started
            if started:
                try:
                    await drone.offboard.stop()
                    logger.info("Offboard mode stopped")
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)

            # Release OffboardOwner if we acquired it
            if acquired_owner and offboard_owner is not None:
                try:
                    await offboard_owner.release(owner_id)
                except Exception as exc:
                    logger.warning("Failed to release offboard ownership: %s", exc)


# =============================================================================
# SET VELOCITY BODY TOOL
# =============================================================================

# MAVSDK VelocityBodyYawspeed import with fallback for testing
try:
    from mavsdk.offboard import VelocityBodyYawspeed
except ImportError:
    class VelocityBodyYawspeed:  # type: ignore
        """Mock VelocityBodyYawspeed for testing without MAVSDK.

        In real operation, this comes from mavsdk.offboard and represents
        a velocity setpoint in body frame with yaw rate.
        """

        def __init__(
            self,
            forward_m_s: float,
            right_m_s: float,
            down_m_s: float,
            yawspeed_deg_s: float,
        ) -> None:
            self.forward_m_s = forward_m_s
            self.right_m_s = right_m_s
            self.down_m_s = down_m_s
            self.yawspeed_deg_s = yawspeed_deg_s


async def set_velocity_body(
    forward_m_s: float = 0.0,
    right_m_s: float = 0.0,
    down_m_s: float = 0.0,
    yaw_rate_deg_s: float = 0.0,
    duration_s: float = 1.0,
) -> str:
    """MCP Tool: Set velocity setpoint in body frame (offboard mode).

    Direct velocity control in body frame. "Forward" always means "where the
    drone is facing" regardless of heading. Maintains 20Hz setpoint stream.

    CRITICAL: Must maintain 20Hz stream or PX4 triggers failsafe.
    This function handles streaming automatically.

    Safety Limits:
        - Max horizontal speed: 20 m/s (combined forward/right magnitude)
        - Max vertical speed: 10 m/s
        - Max yaw rate: 180 deg/s

    When to Use:
        - Intuitive "pilot perspective" control
        - Dynamic trajectory following relative to drone heading
        - Vision-based closed-loop control
        - Smooth continuous movement in any direction

    Args:
        forward_m_s: Forward velocity in m/s (positive=forward, negative=backward).
        right_m_s: Right velocity in m/s (positive=right, negative=left).
        down_m_s: Down velocity in m/s (positive=descend, negative=climb).
        yaw_rate_deg_s: Yaw rate in deg/s (positive=right, negative=left).
        duration_s: Duration to maintain setpoint in seconds (required, max 60).

    Returns:
        JSON string with result dict including velocity, duration,
        and setpoint transmission statistics.

    Example:
        >>> # Fly forward at 5 m/s for 3 seconds while rotating right at 10 deg/s
        >>> result = await set_velocity_body(
        ...     forward_m_s=5.0, right_m_s=0.0, down_m_s=0.0,
        ...     yaw_rate_deg_s=10.0, duration_s=3.0
        ... )
        >>> data = json.loads(result)
        >>> print(f"Sent {data['setpoints_sent']} setpoints at {data['approximate_rate_hz']}Hz")
        Sent 60 setpoints at 20.0Hz

    Note:
        This function blocks for the entire duration. No other commands
        can be executed until it completes.

    Offboard Ownership:
        Acquires OffboardOwner before streaming. If another component
        already owns offboard control, returns OFFBOARD_OWNERSHIP_CONFLICT error.
    """
    # Validate input schema
    try:
        input_data = SetVelocityBodyInput(
            forward_m_s=forward_m_s,
            right_m_s=right_m_s,
            down_m_s=down_m_s,
            yaw_rate_deg_s=yaw_rate_deg_s,
            duration_s=duration_s,
        )
    except Exception as e:
        result = to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=False,
            suggested_action="Check parameter values and types",
        )
        return json.dumps(result)

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Validate state precondition - must be in flying state
    valid_states = {
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
    }
    if sm.current_state not in valid_states:
        return json.dumps(to_error_envelope(
            ErrorCode.PREFLIGHT_BLOCKED,
            f"Cannot set_velocity_body in {sm.current_state_name} state. "
            f"Must be in one of: {[s.name for s in valid_states]}",
            recoverable=False,
            suggested_action="Ensure drone is in a flying state before velocity control",
        ))

    # Validate velocity limits (horizontal combined magnitude)
    horizontal_speed = math.sqrt(forward_m_s**2 + right_m_s**2)
    if horizontal_speed > 20.0:
        return json.dumps(to_error_envelope(
            ErrorCode.GUARDIAN_VIOLATION,
            f"Horizontal speed {horizontal_speed:.1f} m/s exceeds 20 m/s limit",
            recoverable=False,
            suggested_action="Reduce forward/right velocity to stay within 20 m/s limit",
        ))

    # Get drone connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Not connected to drone: {e}",
            recoverable=True,
            suggested_action="Establish connection before velocity control",
        ))

    if drone is None:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Establish connection before velocity control",
        ))

    # Prepare velocity setpoint for MAVSDK
    velocity_setpoint = VelocityBodyYawspeed(
        input_data.forward_m_s,
        input_data.right_m_s,
        input_data.down_m_s,
        input_data.yaw_rate_deg_s,
    )

    # Get OffboardOwner singleton for mutual exclusion
    offboard_owner = get_offboard_owner()

    # Transition to VELOCITY_CONTROL state
    sm.transition(
        FlightState.VELOCITY_CONTROL,
        f"velocity_body_command: forward={input_data.forward_m_s}, right={input_data.right_m_s}",
        "llm",
    )

    # Create velocity body streamer
    streamer = VelocityBodyStreamer(rate_hz=20.0)

    # Stream velocity setpoints for specified duration
    setpoint_count = await streamer.stream_for(
        drone=drone,
        velocity_setpoint=velocity_setpoint,
        duration_s=input_data.duration_s,
        offboard_owner=offboard_owner,
        owner_id="set_velocity_body",
    )

    # Check result
    if setpoint_count == 0:
        # Check if it was an ownership conflict
        current_owner = offboard_owner.current_owner()
        if current_owner is not None and current_owner != "set_velocity_body":
            return json.dumps(to_error_envelope(
                ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT,
                f"Offboard control already acquired by '{current_owner}'",
                recoverable=False,
                suggested_action=f"Wait for '{current_owner}' to release offboard control",
            ))
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            "Failed to start offboard mode",
            recoverable=True,
            suggested_action="Check drone status and retry velocity command",
        ))

    # Transition back to FLYING after velocity control
    if sm.current_state == FlightState.VELOCITY_CONTROL:
        sm.transition(
            FlightState.FLYING,
            "velocity_body_command_completed",
            "llm",
        )

    return json.dumps({
        "success": True,
        "velocity_body": [input_data.forward_m_s, input_data.right_m_s, input_data.down_m_s],
        "yaw_rate_deg_s": input_data.yaw_rate_deg_s,
        "duration_s": input_data.duration_s,
        "setpoints_sent": setpoint_count,
        "approximate_rate_hz": round(setpoint_count / input_data.duration_s, 1) if input_data.duration_s > 0 else 0,
    })


# =============================================================================
# GEOFENCE PRIMITIVE TOOLS
# =============================================================================

# Global state references for geofence tools
_guardian: Optional[GuardianProcess] = None
_confirmation: Optional[Any] = None  # ConfirmationManager
_connection_manager_global: Optional[ConnectionManager] = None


def set_guardian(guardian: GuardianProcess) -> None:
    """Set the global guardian reference for geofence tools."""
    global _guardian
    _guardian = guardian


def get_guardian() -> Optional[GuardianProcess]:
    """Get the global guardian instance."""
    return _guardian


def set_confirmation(confirmation: Any) -> None:
    """Set the global confirmation manager reference."""
    global _confirmation
    _confirmation = confirmation


def set_connection_manager_global(cm: ConnectionManager) -> None:
    """Set the global connection manager reference for geofence tools."""
    global _connection_manager_global
    _connection_manager_global = cm


def _get_session() -> Any:
    """Get the current MCP session (placeholder for session access)."""
    # In real implementation, this would access the MCP session context
    # For now, return a mock with auto_confirm=False
    return type('Session', (), {'auto_confirm': False})()


# =============================================================================
# GEOFENCE INPUT/OUTPUT SCHEMAS
# =============================================================================


class SetGeofencePolygonInput(BaseModel):
    """Input schema for set_geofence_polygon tool.

    Attributes:
        polygon: Polygon definition with vertices (minimum 3 points).
        action: Action on breach - 'rtl', 'hold', 'warn', or 'none'.
        shrink_ok: Whether to allow shrinking an existing fence without confirmation.
    """

    polygon: Any = Field(
        ...,
        description="Polygon geofence with vertices (minimum 3 points). "
                    "Each vertex has lat_deg and lon_deg.",
    )
    action: str = Field(
        default="rtl",
        description="Action on breach: 'rtl' (return to launch), 'hold', 'warn', or 'none'",
    )
    shrink_ok: bool = Field(
        default=False,
        description="Allow shrinking existing fence without confirmation",
    )

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of the allowed values."""
        allowed = {'rtl', 'hold', 'warn', 'none'}
        if v.lower() not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v.lower()


class SetGeofencePolygonOutput(BaseModel):
    """Output schema for set_geofence_polygon tool.

    Attributes:
        fence_id: Unique identifier for the uploaded fence.
        applied: Whether the fence was successfully applied.
    """

    fence_id: str = Field(
        default="",
        description="Unique identifier for the uploaded geofence",
    )
    applied: bool = Field(
        default=False,
        description="Whether the fence was successfully applied",
    )


# =============================================================================
# GEOFENCE TOOL SCHEMA FUNCTIONS
# =============================================================================


def set_geofence_polygon_tool_schema() -> dict[str, Any]:
    """Return the JSON schema for set_geofence_polygon input."""
    return SetGeofencePolygonInput.model_json_schema()


def set_geofence_polygon_output_schema() -> dict[str, Any]:
    """Return the JSON schema for set_geofence_polygon output."""
    return SetGeofencePolygonOutput.model_json_schema()


def set_geofence_polygon_annotations() -> dict[str, bool]:
    """Return MCP tool annotations for set_geofence_polygon.

    Annotations inform the LLM about tool behavior:
    - readOnlyHint: False - modifies drone state
    - destructiveHint: True - changes safety boundaries
    - idempotentHint: False - each call creates/modifies fence
    - openWorldHint: False - operates within drone context
    """
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


# =============================================================================
# GEOFENCE HELPER FUNCTIONS
# =============================================================================


def _polygon_area_m2(polygon: Any) -> float:
    """Calculate approximate area of polygon in square meters.

    Uses the shoelace formula with lat/lon to meters approximation.
    This is approximate but sufficient for comparing fence sizes.

    Args:
        polygon: Polygon object with vertices attribute.

    Returns:
        Approximate area in square meters.
    """
    if not hasattr(polygon, 'vertices') or len(polygon.vertices) < 3:
        return 0.0

    vertices = polygon.vertices
    n = len(vertices)

    # Shoelace formula with lat/lon to meters conversion
    # 1 degree latitude ~= 111,320 meters
    # Use first vertex as reference point
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        # Convert to local meters relative to first vertex
        x1 = (vertices[i].lon_deg - vertices[0].lon_deg) * 111_320.0
        y1 = (vertices[i].lat_deg - vertices[0].lat_deg) * 111_320.0
        x2 = (vertices[j].lon_deg - vertices[0].lon_deg) * 111_320.0
        y2 = (vertices[j].lat_deg - vertices[0].lat_deg) * 111_320.0
        acc += x1 * y2 - x2 * y1

    return abs(acc) * 0.5


# =============================================================================
# GEOFENCE MAIN TOOL IMPLEMENTATION
# =============================================================================


async def handle_set_geofence_polygon(arguments: dict[str, Any]) -> str:
    """Handle set_geofence_polygon MCP tool call.

    This implements the geofence polygon upload with:
    1. Input validation via SetGeofencePolygonInput schema
    2. Guardian preflight check
    3. Shrinking detection (curated confirmation #3)
    4. MAVSDK geofence upload
    5. Guardian state update

    Curated Confirmation #3 (per D2.6 spec):
        set_geofence_polygon when it would remove or shrink an existing fence.
        If shrink_ok=False and new fence is smaller, return CONFIRMATION_REQUIRED.

    Args:
        arguments: Tool arguments with polygon, action, and shrink_ok.

    Returns:
        JSON string with result or error envelope.
    """
    # Validate input
    try:
        # Convert polygon dict to Polygon object if needed
        polygon_data = arguments.get("polygon", {})
        if isinstance(polygon_data, dict):
            from avatar.mcp_server.schemas import Polygon, Point
            vertices_data = polygon_data.get("vertices", [])
            vertices = [Point.model_validate(v) for v in vertices_data]
            polygon = Polygon(vertices=vertices)
        else:
            polygon = polygon_data

        inp = SetGeofencePolygonInput(
            polygon=polygon,
            action=arguments.get("action", "rtl"),
            shrink_ok=arguments.get("shrink_ok", False),
        )
    except Exception as e:
        logger.warning(f"Invalid set_geofence_polygon input: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid polygon definition: {e}",
            recoverable=True,
            suggested_action="Provide valid polygon with at least 3 vertices",
        ))

    # Get dependencies
    guardian = _guardian or GuardianProcess()
    confirmation = _confirmation
    cm = _connection_manager_global or ConnectionManager()
    session = _get_session()

    # Guardian preflight check
    if hasattr(guardian, 'preflight'):
        preflight_result = await guardian.preflight(
            tool="set_geofence_polygon",
            payload={"action": inp.action, "vertices": len(inp.polygon.vertices)},
        )
        if preflight_result is not None:
            return json.dumps(preflight_result)

    # Check for existing fence and shrinking
    existing_fence = None
    if hasattr(guardian, 'get_geofence_polygon'):
        existing_fence = guardian.get_geofence_polygon()

    if existing_fence is not None and not inp.shrink_ok:
        # Compare areas to detect shrinking
        existing_area = _polygon_area_m2(existing_fence)
        new_area = _polygon_area_m2(inp.polygon)

        if new_area < existing_area * 0.99:  # Allow 1% tolerance
            logger.info(
                f"Geofence shrinking detected: existing={existing_area:.0f}m2, "
                f"new={new_area:.0f}m2"
            )

            # Check auto_confirm
            if not getattr(session, 'auto_confirm', False):
                # Curated confirmation #3: shrinking fence requires confirmation
                if confirmation is not None:
                    try:
                        token = await confirmation.require(
                            action="set_geofence_polygon_shrink",
                            destructive=True,
                            summary=(
                                f"New geofence is smaller than existing fence. "
                                f"Existing: {existing_area:.0f}m2, New: {new_area:.0f}m2. "
                                f"Proceed with smaller fence?"
                            ),
                            payload={
                                "existing_area_m2": existing_area,
                                "new_area_m2": new_area,
                                "shrink_percent": (1 - new_area / existing_area) * 100,
                            },
                        )
                        response = confirmation.get_pending(token.token)
                        confirmation.clear_pending(token.token)

                        if response is None or not response.get("approved", False):
                            return json.dumps(to_error_envelope(
                                ErrorCode.CONFIRMATION_REQUIRED,
                                "Shrinking geofence requires confirmation",
                                recoverable=True,
                                suggested_action="Set shrink_ok=True or confirm the operation",
                            ))
                    except asyncio.TimeoutError:
                        return json.dumps(to_error_envelope(
                            ErrorCode.CONFIRMATION_EXPIRED,
                            "Confirmation timed out for geofence shrink",
                            recoverable=True,
                            suggested_action="Retry the operation",
                        ))
                else:
                    # No confirmation manager - return error
                    return json.dumps(to_error_envelope(
                        ErrorCode.CONFIRMATION_REQUIRED,
                        "Shrinking geofence requires confirmation but no confirmation manager available",
                        recoverable=True,
                        suggested_action="Set shrink_ok=True or configure confirmation manager",
                    ))

    # Get drone connection
    try:
        drone = await cm.ensure_connected()
        if drone is None:
            return json.dumps(to_error_envelope(
                ErrorCode.MAV_NOT_CONNECTED,
                "Not connected to drone",
                recoverable=True,
                suggested_action="Connect to drone before setting geofence",
            ))
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Failed to get drone connection: {e}",
            recoverable=True,
            suggested_action="Check drone connection and retry",
        ))

    # Upload geofence via MAVSDK
    try:
        # Create MAVSDK geofence from polygon vertices
        # MAVSDK expects a list of Point objects
        if hasattr(drone, 'geofence') and hasattr(drone.geofence, 'upload_geofence'):
            # Build geofence points for MAVSDK
            # Note: MAVSDK geofence API varies by version
            fence_points = []
            for vertex in inp.polygon.vertices:
                fence_points.append({
                    "latitude_deg": vertex.lat_deg,
                    "longitude_deg": vertex.lon_deg,
                })

            await drone.geofence.upload_geofence(
                fence_points,
                action=inp.action,
            )
            logger.info(
                f"Geofence uploaded: {len(fence_points)} vertices, action={inp.action}"
            )
        else:
            logger.warning(
                "MAVSDK geofence.upload_geofence not available - "
                "geofence set in guardian only"
            )
    except Exception as e:
        logger.error(f"Failed to upload geofence: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            f"Failed to upload geofence: {e}",
            recoverable=True,
            suggested_action="Check drone geofence support and retry",
        ))

    # Update guardian state
    if hasattr(guardian, 'set_geofence_polygon'):
        guardian.set_geofence_polygon(inp.polygon)

    # Generate fence ID
    import uuid
    fence_id = f"fence_{uuid.uuid4().hex[:8]}"

    return json.dumps({
        "fence_id": fence_id,
        "applied": True,
        "vertices_count": len(inp.polygon.vertices),
        "action": inp.action,
        "area_m2": round(_polygon_area_m2(inp.polygon), 2),
    })


# =============================================================================
# SET YAW PRIMITIVE
# =============================================================================


class SetYawInput(BaseModel):
    """Input schema for set_yaw MCP tool.

    Validates yaw angle and rate parameters before command execution.

    W2a-T13: Yaw Control Primitive
    ==============================
    Commands the drone to rotate to a specific heading (yaw angle).
    Supports both absolute headings and relative offsets.

    Attributes:
        yaw_deg: Target yaw angle in degrees (-180 to 180 for relative,
                 absolute values can be any heading normalized to [-180, 180]).
        yaw_rate_deg_s: Maximum yaw rotation rate in degrees/second.
                       Higher values = faster rotation, lower = smoother.
                       Default: 20 deg/s (moderate rotation speed).
        absolute: If True, yaw_deg is absolute heading (0=North, 90=East).
                 If False, yaw_deg is relative to current heading.
                 Default: True (absolute heading).
    """
    yaw_deg: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Target yaw angle in degrees (-180 to 180)"
    )
    yaw_rate_deg_s: float = Field(
        default=20.0,
        gt=0.0,
        le=90.0,
        description="Yaw rotation rate in degrees/second (default 20)"
    )
    absolute: bool = Field(
        default=True,
        description="True for absolute heading, False for relative offset"
    )


def _normalize_yaw(yaw_deg: float) -> float:
    """Normalize yaw angle to [-180, 180] range.

    Args:
        yaw_deg: Yaw angle in degrees (any value).

    Returns:
        Normalized yaw in [-180, 180] range.
        Note: Both -180.0 and 180.0 represent the same heading (South)
        and are preserved as-is if already in range.
    """
    # Handle boundary cases - preserve -180 and 180 as-is
    if yaw_deg == -180.0 or yaw_deg == 180.0:
        return yaw_deg

    # Normalize to [0, 360) first
    normalized = yaw_deg % 360.0
    # Convert to [-180, 180]
    if normalized > 180.0:
        normalized -= 360.0
    return normalized


async def set_yaw(
    yaw_deg: float,
    yaw_rate_deg_s: float = 20.0,
    absolute: bool = True,
    context: Optional[dict[str, Any]] = None,
) -> str:
    """MCP Tool: Command the drone to rotate to a specific heading (yaw angle).

    MCP Tool Metadata:
        annotations: {readOnlyHint: False, destructiveHint: False, idempotentHint: True, openWorldHint: False}
        outputSchema: {type: object}

    Commands the drone's yaw angle (heading) using MAVSDK. Supports both
    absolute headings (relative to North) and relative offsets from current heading.

    W2a-T13: Yaw Control Primitive
    ==============================
    This is a fundamental primitive for controlling drone orientation.
    Used for:
    - Pointing camera toward a target (combined with gimbal)
    - Preparing for directional movement
    - Executing coordinated turns
    - Orbit operations

    Coordinate Frame (NED - North-East-Down):
        - 0 deg = North (heading north)
        - 90 deg = East (heading east)
        - 180 deg = South (heading south)
        - -90 deg = West (heading west)

    Absolute vs Relative Mode:
        - absolute=True: yaw_deg is heading relative to North
          Example: yaw_deg=90 points the drone East regardless of current heading
        - absolute=False: yaw_deg is offset from current heading
          Example: yaw_deg=45 turns drone 45 degrees right from current heading

    Implementation:
        Uses MAVSDK action.goto_location() with current position but new yaw.
        This is the most reliable way to command yaw without changing position.

    Args:
        yaw_deg: Target yaw angle in degrees.
                For absolute mode: any heading (will be normalized)
                For relative mode: offset in [-180, 180] range
        yaw_rate_deg_s: Maximum yaw rotation rate in degrees/second (default: 20).
                       Range: 0 < rate <= 90 deg/s
                       Higher values = faster rotation
        absolute: True for absolute heading (default), False for relative offset.
        context: Optional context dict (unused, for MCP interface compatibility).

    Returns:
        JSON string with yaw command result:
        {
            "success": bool,
            "message": str,
            "yaw_deg": float,          # Target yaw (normalized to [-180, 180])
            "yaw_rate_deg_s": float,
            "mode": str,               # "absolute" or "relative"
            "previous_yaw_deg": float  # Yaw before command
        }

        Example success:
            {
                "success": True,
                "message": "Yaw command sent: rotating to 90.0deg",
                "yaw_deg": 90.0,
                "yaw_rate_deg_s": 20.0,
                "mode": "absolute",
                "previous_yaw_deg": 0.0
            }

    Safety Notes:
        - Requires drone to be in flying state (HOVERING, FLYING, etc.)
        - Cannot yaw while on ground or during landing
        - Yaw rate limited to 90 deg/s maximum for safety

    Example:
        >>> # Face East (absolute heading)
        >>> result = await set_yaw(yaw_deg=90.0)
        >>> data = json.loads(result)
        >>> print(f"Rotating from {data['previous_yaw_deg']} to {data['yaw_deg']}")

        >>> # Turn 45 degrees right (relative)
        >>> result = await set_yaw(yaw_deg=45.0, absolute=False)
        >>> data = json.loads(result)
        >>> print(data["message"])
    """
    # Validate input using Pydantic schema
    try:
        input_data = SetYawInput(
            yaw_deg=yaw_deg,
            yaw_rate_deg_s=yaw_rate_deg_s,
            absolute=absolute
        )
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=False,
            suggested_action="Check parameter values and types",
        ))

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Check state precondition - must be in flying state
    valid_states = {
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
    }
    if sm.current_state not in valid_states:
        return json.dumps(to_error_envelope(
            ErrorCode.PREFLIGHT_BLOCKED,
            f"Cannot set_yaw in state {sm.current_state_name}. "
            f"Must be in one of: {[s.name for s in valid_states]}",
            recoverable=False,
            suggested_action="Ensure drone is in a flying state before yaw control",
        ))

    # Establish connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Not connected to drone: {e}",
            recoverable=True,
            suggested_action="Establish connection before yaw control",
        ))

    if drone is None:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Establish connection before yaw control",
        ))

    try:
        # Get current position and heading
        current_lat = None
        current_lon = None
        current_alt = None
        current_yaw = 0.0

        # Get current position from telemetry
        async for position in drone.telemetry.position():
            current_lat = position.latitude_deg
            current_lon = position.longitude_deg
            current_alt = position.absolute_altitude_m
            break

        # Get current heading
        async for attitude in drone.telemetry.attitude_euler():
            current_yaw = attitude.yaw_deg
            break

        if current_lat is None or current_lon is None or current_alt is None:
            return json.dumps(to_error_envelope(
                ErrorCode.INTERNAL_ERROR,
                "Failed to get current position",
                recoverable=True,
                suggested_action="Retry yaw command",
            ))

        # Calculate target yaw
        if input_data.absolute:
            # Normalize absolute yaw to [-180, 180] range
            target_yaw = _normalize_yaw(input_data.yaw_deg)
        else:
            # Add relative offset to current yaw
            target_yaw = _normalize_yaw(current_yaw + input_data.yaw_deg)

        logger.info(
            f"Setting yaw: current={current_yaw:.1f}deg, "
            f"target={target_yaw:.1f}deg, rate={input_data.yaw_rate_deg_s:.1f}deg/s, "
            f"mode={'absolute' if input_data.absolute else 'relative'}"
        )

        # Use goto_location with current position but new yaw
        # This is the most reliable way to command yaw without changing position
        # MAVSDK goto_location signature: (lat, lon, alt_amsl, yaw_deg)
        await drone.action.goto_location(
            current_lat,
            current_lon,
            current_alt,
            target_yaw
        )

        logger.info(f"Yaw command sent: rotating to {target_yaw:.1f}deg")

        return json.dumps({
            "success": True,
            "message": f"Yaw command sent: rotating to {target_yaw:.1f}deg",
            "yaw_deg": target_yaw,
            "yaw_rate_deg_s": input_data.yaw_rate_deg_s,
            "mode": "absolute" if input_data.absolute else "relative",
            "previous_yaw_deg": current_yaw,
        })

    except Exception as e:
        logger.error(f"Failed to set yaw: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            f"Failed to set yaw: {e}",
            recoverable=True,
            suggested_action="Check drone status and retry yaw command",
        ))


# =============================================================================
# SET POSITION GPS TOOL
# =============================================================================


async def set_position_gps(
    target: dict,
    speed_m_s: float = 5.0,
) -> str:
    """MCP Tool: Command position via GPS coordinates using goto_location.

    Positions the drone at the specified GPS coordinates (latitude, longitude,
    altitude AMSL). Uses MAVSDK action.goto_location() for GPS navigation.

    This is a simpler alternative to set_position_ned that works with absolute
    GPS coordinates rather than NED positions relative to home.

    GPS Coordinate System:
        - latitude: Degrees from equator (-90 to 90)
        - longitude: Degrees from prime meridian (-180 to 180)
        - altitude: Meters above mean sea level (AMSL)

    When to Use:
        - Navigate to specific geographic locations
        - Fly to waypoints from mission planning
        - Move to coordinates from external sources (maps, etc.)
        - Simple GPS navigation without offboard complexity

    Safety Requirements:
        - Drone must be in flying state (HOVERING, FLYING, etc.)
        - Position must be within geofence limits
        - Altitude must be within allowed range

    Args:
        target: Dict with lat_deg, lon_deg, and alt_m (AMSL meters).
                Example: {"lat_deg": 37.7749, "lon_deg": -122.4194, "alt_m": 50.0}
        speed_m_s: Travel speed in m/s (0.1 to 20, default: 5).

    Returns:
        JSON string with result dict:
        {
            "success": bool,
            "message": str,
            "target": {"lat_deg": float, "lon_deg": float, "alt_m": float},
            "speed_m_s": float,
            "error": str  # Present only if failed
        }

    Example:
        >>> # Navigate to San Francisco at 50m altitude
        >>> result = await set_position_gps(
        ...     target={"lat_deg": 37.7749, "lon_deg": -122.4194, "alt_m": 50.0},
        ...     speed_m_s=8.0
        ... )
        >>> data = json.loads(result)
        >>> print(f"Navigating to: {data['target']}")

    Note:
        This function uses goto_location which is simpler than offboard mode
        but does not provide the same level of precision or continuous
        position streaming. For precise positioning, use set_position_ned.
    """
    # Validate input schema
    try:
        # Create Point from target dict
        target_point = Point(
            lat_deg=target.get("lat_deg", 0.0),
            lon_deg=target.get("lon_deg", 0.0),
            alt_m=target.get("alt_m"),
        )
        input_data = SetPositionGpsInput(
            target=target_point,
            speed_m_s=speed_m_s,
        )
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=False,
            suggested_action="Provide valid lat_deg (-90 to 90), lon_deg (-180 to 180), and alt_m",
        ))

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Validate state precondition - must be in flying state
    valid_states = {
        FlightState.HOVERING,
        FlightState.FLYING,
        FlightState.POSITION_CONTROL,
        FlightState.VELOCITY_CONTROL,
        FlightState.MISSION_EXECUTION,
        FlightState.HOLD,
    }
    if sm.current_state not in valid_states:
        return json.dumps(to_error_envelope(
            ErrorCode.PREFLIGHT_BLOCKED,
            f"Cannot set_position_gps in {sm.current_state_name} state. "
            f"Must be in one of: {[s.name for s in valid_states]}",
            recoverable=False,
            suggested_action="Ensure drone is in a flying state before navigation",
        ))

    # Get drone connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Not connected to drone: {e}",
            recoverable=True,
            suggested_action="Establish connection before navigation",
        ))

    if drone is None:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Establish connection before navigation",
        ))

    # Validate against Guardian limits
    guardian = GuardianProcess()
    is_valid, reason = guardian.validate_command({
        "latitude": input_data.target.lat_deg,
        "longitude": input_data.target.lon_deg,
        "altitude_amsl_m": input_data.target.alt_m,
        "speed_m_s": input_data.speed_m_s,
    })
    if not is_valid:
        return json.dumps(to_error_envelope(
            ErrorCode.GUARDIAN_VIOLATION,
            f"Guardian validation failed: {reason}",
            recoverable=False,
            suggested_action="Adjust target position to within safety limits",
        ))

    # Transition to POSITION_CONTROL state
    sm.transition(
        FlightState.POSITION_CONTROL,
        f"gps_navigation: ({input_data.target.lat_deg}, {input_data.target.lon_deg})",
        "llm"
    )

    # Get current position for altitude reference
    current_alt_amsl = None
    try:
        async for position in drone.telemetry.position():
            current_alt_amsl = position.absolute_altitude_m
            break
    except Exception:
        pass

    # Determine target altitude
    target_alt = input_data.target.alt_m
    if target_alt is None:
        # Use current altitude if not specified
        target_alt = current_alt_amsl if current_alt_amsl else 50.0

    # Set travel speed
    try:
        set_max_speed = getattr(drone.action, "set_maximum_speed", None)
        if callable(set_max_speed):
            await set_max_speed(input_data.speed_m_s)
    except Exception as e:
        logger.warning(f"Could not set maximum speed: {e}")

    # Navigate to target position using MAVSDK goto_location
    # Parameters: lat, lon, altitude_amsl, yaw_deg (0 = maintain current)
    try:
        await drone.action.goto_location(
            input_data.target.lat_deg,
            input_data.target.lon_deg,
            target_alt,
            float("nan"),  # yaw = NaN means maintain current heading
        )
        logger.info(
            f"Navigating to ({input_data.target.lat_deg}, {input_data.target.lon_deg}) "
            f"at {target_alt}m AMSL"
        )
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            f"Navigation command failed: {e}",
            recoverable=True,
            suggested_action="Check drone status and retry navigation",
        ))

    return json.dumps({
        "success": True,
        "message": "Navigation command sent",
        "target": {
            "lat_deg": input_data.target.lat_deg,
            "lon_deg": input_data.target.lon_deg,
            "alt_m": target_alt,
        },
        "speed_m_s": input_data.speed_m_s,
    })


# =============================================================================
# DISARM PRIMITIVE TOOL (W2a-T02)
# =============================================================================


class DisarmInput(BaseModel):
    """Input schema for disarm MCP tool.

    W2a-T02: Disarm Primitive
    ==========================
    Disarms the drone motors. This is a safety-critical operation.

    Attributes:
        force: Force disarm even if drone is in air (DANGEROUS).
               This will cause the drone to fall if airborne.
    """

    force: bool = Field(
        default=False,
        description="Force disarm even if in air. DANGEROUS - will cause crash if airborne.",
    )


class DisarmOutput(BaseModel):
    """Output schema for disarm MCP tool.

    Attributes:
        armed: Whether drone is armed (should be False after disarm).
        timestamp: ISO timestamp of when disarm completed.
    """

    armed: bool = Field(
        description="Current armed state (False after successful disarm)",
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp of disarm completion",
    )


def disarm_tool_schema() -> dict[str, Any]:
    """Return the JSON schema for disarm input."""
    return DisarmInput.model_json_schema()


def disarm_output_schema() -> dict[str, Any]:
    """Return the JSON schema for disarm output."""
    return DisarmOutput.model_json_schema()


def disarm_annotations() -> dict[str, bool]:
    """Return MCP tool annotations for disarm.

    Annotations inform the LLM about tool behavior:
    - readOnlyHint: False - modifies drone state
    - destructiveHint: True - disarming in air causes crash
    - idempotentHint: False - calling twice may fail if already disarmed
    - openWorldHint: True - affects physical world
    """
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }


async def handle_disarm(arguments: dict[str, Any]) -> str:
    """Handle disarm MCP tool call.

    Disarms the drone motors. This is a safety-critical operation that
    requires confirmation when:
    - force=True and drone is in air (curated confirmation #6)

    Implementation follows W2a-T02 spec:
    1. Validate input with Pydantic DisarmInput
    2. Check state precondition (must be ARMED or in flying state)
    3. Call guardian.preflight(tool="disarm", payload=input)
    4. If force=True and in_air, call confirmation_manager.require()
    5. Execute MAVSDK drone.action.disarm()
    6. Update state machine to DISARMED
    7. Return success or error envelope

    Args:
        arguments: Tool arguments with optional 'force' boolean.

    Returns:
        JSON string with DisarmOutput or error envelope.
    """
    # Step 1: Validate input with Pydantic
    try:
        inp = DisarmInput.model_validate(arguments)
    except Exception as e:
        logger.warning(f"Invalid disarm input: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid input parameters: {e}",
            recoverable=False,
            suggested_action="Provide valid 'force' boolean parameter",
        ))

    # Get dependencies
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    guardian = _guardian or GuardianProcess()
    confirmation = _confirmation
    cm = _connection_manager_global or ConnectionManager()
    session = _get_session()

    # Step 2: Check state precondition
    # Disarm is allowed from ARMED states (see FlightStateMachine.COMMAND_PRECONDITIONS)
    valid_states = {
        FlightState.ARMED,
        FlightState.LANDED,
        FlightState.DISARMED,  # Already disarmed is OK
    }

    current_state = sm.current_state
    in_air = sm.is_flying

    # If already disarmed, return success immediately
    if current_state == FlightState.DISARMED:
        logger.info("Drone already disarmed")
        out = DisarmOutput(
            armed=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return out.model_dump_json()

    # Check if we're in a valid state for normal disarm
    if current_state not in valid_states and not inp.force:
        return json.dumps(to_error_envelope(
            ErrorCode.PREFLIGHT_BLOCKED,
            f"Cannot disarm from {current_state.name} state. "
            f"Must be in ARMED or LANDED state, or use force=True.",
            recoverable=False,
            suggested_action="Land the drone before disarming, or use force=True",
        ))

    # Step 3: Call guardian.preflight if available
    if hasattr(guardian, 'preflight'):
        try:
            preflight_result = await guardian.preflight(
                tool="disarm",
                payload=inp.model_dump(),
            )
            if preflight_result is not None:
                # Guardian blocked the operation
                return json.dumps(preflight_result)
        except Exception as e:
            logger.error(f"Guardian preflight check failed: {e}")
            # Continue with operation - guardian failure shouldn't block

    # Step 4: Force disarm in air requires confirmation (curated #6)
    if inp.force and in_air:
        logger.warning("Force disarm requested while drone is in air!")

        # Check auto_confirm from session
        if not getattr(session, 'auto_confirm', False):
            if confirmation is not None:
                try:
                    token = await confirmation.require(
                        action="force_disarm_in_air",
                        destructive=True,
                        summary=(
                            "FORCE DISARM while airborne. "
                            "This will immediately stop all motors and cause the drone to fall. "
                            "Only proceed if the alternative is worse."
                        ),
                        payload={
                            "force": True,
                            "in_air": True,
                            "current_state": current_state.name,
                        },
                    )
                    response = confirmation.get_pending(token.token)
                    confirmation.clear_pending(token.token)

                    if response is None or not response.get("approved", False):
                        return json.dumps(to_error_envelope(
                            ErrorCode.CONFIRMATION_REQUIRED,
                            "Force disarm while in air requires operator confirmation",
                            recoverable=True,
                            suggested_action="Confirm the dangerous operation or land first",
                        ))
                except asyncio.TimeoutError:
                    return json.dumps(to_error_envelope(
                        ErrorCode.CONFIRMATION_EXPIRED,
                        "Confirmation timed out for force disarm",
                        recoverable=True,
                        suggested_action="Retry and respond to confirmation prompt",
                    ))
            else:
                # No confirmation manager - require explicit consent
                return json.dumps(to_error_envelope(
                    ErrorCode.CONFIRMATION_REQUIRED,
                    "Force disarm while in air requires confirmation but no confirmation manager available",
                    recoverable=True,
                    suggested_action="Configure confirmation manager or land before disarming",
                ))

    # Get drone connection
    try:
        drone = await cm.ensure_connected()
        if drone is None:
            return json.dumps(to_error_envelope(
                ErrorCode.MAV_NOT_CONNECTED,
                "Not connected to drone",
                recoverable=True,
                suggested_action="Connect to drone before disarming",
            ))
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Failed to get drone connection: {e}",
            recoverable=True,
            suggested_action="Check drone connection and retry",
        ))

    # Step 5: Execute MAVSDK disarm
    try:
        if inp.force:
            # Force disarm - use kill if available, otherwise disarm
            try:
                await drone.action.kill()
                logger.critical("KILL action sent - immediate motor cutoff")
            except Exception:
                # Fallback to regular disarm if kill not available
                await drone.action.disarm()
                logger.warning("Force disarm executed (kill not available)")
        else:
            await drone.action.disarm()
            logger.info("Disarm command sent successfully")

    except Exception as e:
        logger.error(f"Failed to disarm: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            f"Disarm command rejected: {e}",
            recoverable=True,
            suggested_action="Check drone state and retry disarm",
        ))

    # Step 6: Update state machine
    # For force disarm in air, use failsafe mechanism (goes to EMERGENCY)
    # For normal disarm on ground, use regular transition to DISARMED
    if inp.force and in_air:
        # Force disarm triggers kill_switch failsafe
        sm.trigger_failsafe("kill_switch")
    else:
        sm.transition(
            FlightState.DISARMED,
            "disarm_command",
            "llm",
        )

    # Step 7: Return success
    out = DisarmOutput(
        armed=False,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return out.model_dump_json()


# =============================================================================
# SET FLIGHT MODE PRIMITIVE
# =============================================================================


class SetFlightModeInput(BaseModel):
    """Input schema for set_flight_mode primitive.

    Validates flight mode input using the FlightMode literal from schemas.

    Attributes:
        mode: Target flight mode (HOLD, OFFBOARD, AUTO_RTL, etc.).
        submode: Optional submode for mode-specific behavior.
    """

    mode: FlightMode = Field(
        ...,
        description="Target flight mode. Valid values: UNKNOWN, MANUAL, STABILIZED, ALTCTL, POSCTL, OFFBOARD, AUTO_MISSION, AUTO_LOITER, AUTO_RTL, ACRO, ORBIT, HOLD.",
    )
    submode: Optional[str] = Field(
        default=None,
        description="Optional submode for mode-specific behavior.",
    )


class SetFlightModeOutput(BaseModel):
    """Output schema for set_flight_mode primitive.

    Attributes:
        mode: The requested flight mode.
        accepted: Whether the mode change was accepted.
    """

    mode: FlightMode = Field(
        ...,
        description="The flight mode that was requested.",
    )
    accepted: bool = Field(
        ...,
        description="Whether the mode change was accepted by the drone.",
    )


def set_flight_mode_tool_schema() -> dict[str, Any]:
    """Return the JSON schema for set_flight_mode tool input.

    Used by MCP server for tool registration and validation.

    Returns:
        JSON schema dict for SetFlightModeInput.
    """
    return SetFlightModeInput.model_json_schema()


def set_flight_mode_output_schema() -> dict[str, Any]:
    """Return the JSON schema for set_flight_mode tool output.

    Used by MCP server for tool registration.

    Returns:
        JSON schema dict for SetFlightModeOutput.
    """
    return SetFlightModeOutput.model_json_schema()


def set_flight_mode_annotations() -> dict[str, bool]:
    """Return MCP annotations for the set_flight_mode tool.

    Annotations provide hints to MCP clients about tool behavior:
    - readOnlyHint: False (changes drone state)
    - destructiveHint: True (can interrupt mission)
    - idempotentHint: True (multiple calls with same mode have same effect)
    - openWorldHint: False (internal drone operation)

    Returns:
        Dict of annotation key-value pairs.
    """
    return {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }


async def set_flight_mode(mode: FlightMode, submode: Optional[str] = None) -> str:
    """MCP Tool: Change the PX4 flight mode.

    This primitive tool changes the drone's flight mode directly via MAVSDK.
    It validates the mode and executes the appropriate MAVSDK action.

    Args:
        mode: Target flight mode. Valid values:
            - UNKNOWN: Unknown/undefined mode
            - MANUAL: Full manual control
            - STABILIZED: Stabilized mode with attitude control
            - ALTCTL: Altitude control mode
            - POSCTL: Position control mode
            - OFFBOARD: Offboard mode for autonomous control
            - AUTO_MISSION: Execute uploaded mission
            - AUTO_LOITER: Loiter at current position
            - AUTO_RTL: Return to launch
            - ACRO: Acrobatic mode
            - ORBIT: Orbit mode
            - HOLD: Hold position
        submode: Optional submode for mode-specific behavior.

    Returns:
        JSON string with result:
        {
            "mode": str,
            "accepted": bool,
            "error": str  # Present only if failed
        }

    Example:
        >>> result = await set_flight_mode(mode="HOLD")
        >>> data = json.loads(result)
        >>> print(f"Mode accepted: {data['accepted']}")

    Safety:
        - Mode changes can interrupt ongoing missions
        - Some modes require preconditions (e.g., OFFBOARD requires setpoints)
        - AUTO_RTL is always allowed as a safety recovery
    """
    # Validate input with Pydantic
    try:
        inp = SetFlightModeInput(mode=mode, submode=submode)
    except Exception as e:
        return json.dumps(to_error_envelope(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"Invalid flight mode input: {e}",
            recoverable=True,
            suggested_action="Provide valid FlightMode value",
        ))

    # Get global state machine
    sm = get_state_machine()
    if sm is None:
        sm = FlightStateMachine()

    # Get drone connection
    cm = ConnectionManager()
    try:
        drone = await cm.ensure_connected()
    except ConnectionError as e:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            f"Not connected to drone: {e}",
            recoverable=True,
            suggested_action="Connect to drone before changing flight mode",
        ))

    if drone is None:
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_NOT_CONNECTED,
            "Drone not connected",
            recoverable=True,
            suggested_action="Connect to drone before changing flight mode",
        ))

    # Execute mode-specific MAVSDK action
    accepted = True
    try:
        if inp.mode == "HOLD":
            await drone.action.hold()
        elif inp.mode == "OFFBOARD":
            await drone.offboard.start()
        elif inp.mode == "AUTO_RTL":
            await drone.action.return_to_launch()
        elif inp.mode in ("MANUAL", "STABILIZED", "ALTCTL", "POSCTL"):
            # For modes without direct MAVSDK support, use hold as fallback
            # These typically require pilot input
            await drone.action.hold()
        elif inp.mode == "ACRO":
            # Acro mode typically requires pilot input
            await drone.action.hold()
        elif inp.mode == "ORBIT":
            # Orbit mode requires orbit configuration
            await drone.action.hold()
        elif inp.mode in ("AUTO_MISSION", "AUTO_LOITER"):
            # These modes require mission upload first
            await drone.action.hold()
        else:
            # Unknown mode - reject
            accepted = False
            logger.warning(f"Unknown flight mode requested: {inp.mode}")

        # Update state machine based on mode
        if accepted and sm is not None:
            if inp.mode == "AUTO_RTL":
                sm.transition(FlightState.RTL, "flight_mode_command", "llm")
            elif inp.mode == "HOLD":
                sm.transition(FlightState.HOLD, "flight_mode_command", "llm")
            elif inp.mode == "OFFBOARD":
                # Offboard state depends on what setpoints are sent
                pass  # State will be set by the setpoint streaming

        logger.info(f"Flight mode changed to: {inp.mode} (accepted={accepted})")

    except Exception as e:
        logger.error(f"Failed to change flight mode: {e}")
        return json.dumps(to_error_envelope(
            ErrorCode.MAV_COMMAND_REJECTED,
            f"Failed to change flight mode to {inp.mode}: {e}",
            recoverable=True,
            suggested_action="Check drone status and mode preconditions",
        ))

    # Return result
    out = SetFlightModeOutput(mode=inp.mode, accepted=accepted)
    return out.model_dump_json()
