"""Flight control MCP tools.

Provides drone flight control tools for MCP-compatible AI agents.

Tools:
    - arm_and_takeoff: Arm drone and takeoff to altitude
    - goto_gps: Navigate to GPS coordinates
    - fly_body_offset: Body-relative offset movement
    - set_velocity: Set velocity setpoint in NED frame (offboard mode)
    - land: Land at current position
    - rtl: Return to launch
    - abort_mission: Abort and hover
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Optional, Tuple, Dict, List

from avatar.mav.connection import DroneConnection, ConnectionConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mav.connection_manager import ConnectionManager

try:
    from mavsdk.offboard import VelocityNedYaw, OffboardError
except ImportError:
    # Fallback for testing without mavsdk installed
    class VelocityNedYaw:  # type: ignore
        """Mock VelocityNedYaw for testing."""

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

# Global state machine and telemetry cache references (to be set by server)
_state_machine: Optional[FlightStateMachine] = None
_telemetry_cache: Optional[Any] = None


def set_state_machine(sm: FlightStateMachine) -> None:
    """Set the global state machine reference.

    Args:
        sm: The state machine instance to use.
    """
    global _state_machine
    _state_machine = sm


def set_telemetry_cache(cache: Any) -> None:
    """Set the global telemetry cache reference.

    Args:
        cache: The telemetry cache instance to use.
    """
    global _telemetry_cache
    _telemetry_cache = cache


def get_state_machine() -> Optional[FlightStateMachine]:
    """Get the global state machine instance.

    Returns:
        The state machine instance or None if not set.
    """
    return _state_machine


def get_telemetry_cache() -> Optional[Any]:
    """Get the global telemetry cache instance.

    Returns:
        TelemetryCache instance or None if not set.
    """
    return _telemetry_cache


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in meters.

    Uses the haversine formula for great-circle distance calculation.

    Args:
        lat1: Latitude of first point in degrees.
        lon1: Longitude of first point in degrees.
        lat2: Latitude of second point in degrees.
        lon2: Longitude of second point in degrees.

    Returns:
        Distance between points in meters.
    """
    R = 6371000  # Earth radius in meters

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def body_to_ned(
    forward_m: float,
    right_m: float,
    yaw_deg: float
) -> Tuple[float, float]:
    """Transform body-frame offset to NED frame.

    Body frame:
        forward = +X_body
        right = +Y_body

    NED frame:
        north = +X_ned
        east = +Y_ned

    Transform (standard rotation from body to NED):
        north = forward * cos(yaw) - right * sin(yaw)
        east = forward * sin(yaw) + right * cos(yaw)

    Args:
        forward_m: Distance forward (positive) or back (negative) in meters
        right_m: Distance right (positive) or left (negative) in meters
        yaw_deg: Current yaw angle in degrees (0 = north, 90 = east)

    Returns:
        Tuple of (north_offset_m, east_offset_m)
    """
    yaw_rad = math.radians(yaw_deg)

    north = forward_m * math.cos(yaw_rad) - right_m * math.sin(yaw_rad)
    east = forward_m * math.sin(yaw_rad) + right_m * math.cos(yaw_rad)

    return north, east


def validate_gps(lat: float, lon: float) -> None:
    """Validate GPS coordinates are within valid ranges.

    Args:
        lat: Latitude in degrees (-90 to 90).
        lon: Longitude in degrees (-180 to 180).

    Raises:
        ValueError: If coordinates are outside valid ranges.
    """
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")


@dataclass
class FlightToolsConfig:
    """Configuration for flight tools."""
    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0
    default_takeoff_altitude_m: float = 10.0
    default_goto_speed_m_s: float = 5.0
    default_body_offset_speed_m_s: float = 5.0


class FlightTools:
    """Flight control tools for MCP server.

    Provides flight control operations with safety validation
    through the GuardianProcess.

    Usage:
        tools = FlightTools()
        result = await tools.arm_and_takeoff(altitude_m=15)
        print(json.dumps(result, indent=2))
    """

    async def hold(
        self,
        duration_s: float = 5.0,
        position_tolerance_m: float = 1.0,
        auto_rtl_on_drift: bool = False,
    ) -> dict[str, Any]:
        """Hold position with monitoring.

        Enters position hold mode and monitors for drift.
        Automatically transitions state machine to HOVERING.

        Args:
            duration_s: Duration to hold position in seconds.
            position_tolerance_m: Allowed position drift in meters.
            auto_rtl_on_drift: If True, RTL when drift exceeds tolerance.

        Returns:
            Dict with hold result and metrics:
            {
                "success": bool,
                "duration_s": float,
                "max_drift_m": float,
                "was_drift_detected": bool,
                "state": str,
            }
        """
        # State check
        sm = self.state_machine
        if not sm.check_command_precondition("hold"):
            return {"success": False, "error": f"Cannot hold in state {sm.current_state_name}"}

        # Get initial position from telemetry cache or drone
        initial_lat: Optional[float] = None
        initial_lon: Optional[float] = None

        # Try telemetry cache first
        cache = get_telemetry_cache()
        if cache:
            cache_data = cache.get_data()
            if cache_data:
                initial_lat = cache_data.latitude
                initial_lon = cache_data.longitude

        # Fall back to direct drone telemetry
        if initial_lat is None or initial_lon is None:
            conn_error = await self._ensure_connection()
            if conn_error:
                return conn_error

            if self._drone is None or self._drone.drone is None:
                return {"success": False, "error": "Drone not connected"}

            try:
                async for position in self._drone.drone.telemetry.position():
                    initial_lat = position.latitude_deg
                    initial_lon = position.longitude_deg
                    break
            except Exception as e:
                logger.warning(f"Could not get initial position: {e}")
                return {"success": False, "error": f"Could not get initial position: {e}"}

        if initial_lat is None or initial_lon is None:
            return {"success": False, "error": "Could not determine initial position"}

        # Send hold command to drone if connected
        if self._connected and self._drone and self._drone.drone:
            try:
                await self._drone.drone.action.hold()
                logger.info("Hold command sent to drone")
            except Exception as e:
                logger.warning(f"Could not send hold command: {e}")
                # Continue anyway - we'll monitor position

        # Transition to HOVERING state
        sm.transition(FlightState.HOVERING, reason="hold_command", source="llm")

        # Monitor position for duration
        start_time = time.time()
        max_drift = 0.0
        drift_detected = False

        while time.time() - start_time < duration_s:
            current_lat: Optional[float] = None
            current_lon: Optional[float] = None

            # Get current position from cache or telemetry
            if cache:
                cache_data = cache.get_data()
                if cache_data:
                    current_lat = cache_data.latitude
                    current_lon = cache_data.longitude

            # Calculate drift if we have position data
            if current_lat is not None and current_lon is not None:
                drift = haversine_distance(
                    initial_lat, initial_lon,
                    current_lat, current_lon
                )
                max_drift = max(max_drift, drift)

                if drift > position_tolerance_m:
                    drift_detected = True

                    if auto_rtl_on_drift:
                        logger.warning(f"Drift {drift:.1f}m exceeds tolerance, triggering RTL")
                        sm.trigger_failsafe("position_drift")
                        return {
                            "success": False,
                            "reason": "rtl_triggered_due_to_drift",
                            "drift_m": drift,
                            "max_drift_m": max_drift,
                            "state": sm.current_state_name,
                        }

            await asyncio.sleep(0.1)  # 10Hz monitoring

        return {
            "success": True,
            "duration_s": duration_s,
            "max_drift_m": max_drift,
            "was_drift_detected": drift_detected,
            "state": sm.current_state_name,
        }

    def __init__(
        self,
        config: Optional[FlightToolsConfig] = None,
        hard_limits: Optional[HardLimits] = None,
        state_machine: Optional[FlightStateMachine] = None
    ):
        """Initialize flight tools.

        Args:
            config: Flight tools configuration.
            hard_limits: Safety limits for flight operations.
            state_machine: Flight state machine for state tracking.
        """
        self.config = config or FlightToolsConfig()
        self.hard_limits = hard_limits or HardLimits()
        self.guardian = GuardianProcess(self.hard_limits)
        self.state_machine = state_machine or FlightStateMachine()
        self._drone: Optional[DroneConnection] = None
        self._connected = False
        self._heartbeat_task: Optional[asyncio.Task[None]] = None

    async def _ensure_connection(self) -> Dict[str, Any]:
        """Ensure drone connection is established.

        Uses ConnectionManager singleton for persistent connection.

        Returns:
            Error dict if connection failed, empty dict if connected.
        """
        # Use ConnectionManager singleton for persistent connection
        cm = ConnectionManager()

        try:
            drone = await cm.ensure_connected()
            if drone is None:
                return {
                    "success": False,
                    "error": "Failed to connect to drone. Ensure SITL or hardware is running.",
                }

            # Wrap in DroneConnection for compatibility
            if self._drone is None:
                connection_config = ConnectionConfig(
                    system_address=self.config.system_address,
                    max_retries=self.config.max_retries,
                    retry_delay_s=self.config.retry_delay_s,
                    health_timeout_s=self.config.health_timeout_s,
                )
                self._drone = DroneConnection(connection_config)
                self._drone.drone = drone
                self._drone._connected = True

            self._connected = True

            # Start heartbeat background task if not already running
            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return {}

        except ConnectionError as e:
            return {
                "success": False,
                "error": f"Failed to connect to drone: {e}",
            }

    async def _heartbeat_loop(self) -> None:
        """Background task to update heartbeat at 20Hz."""
        while self._connected:
            self.guardian.update_heartbeat()
            await asyncio.sleep(0.05)  # 20Hz

    async def arm_and_takeoff(
        self,
        altitude_m: Optional[float] = None
    ) -> dict[str, Any]:
        """Arm the drone and takeoff to specified altitude.

        Args:
            altitude_m: Target takeoff altitude in meters.
                       Defaults to config.default_takeoff_altitude_m.

        Returns:
            Dict with success status, message, and altitude reached.
            Example success:
                {"success": True, "message": "Takeoff complete", "altitude_m": 10.0}
            Example failure:
                {"success": False, "error": "Failed to arm: GPS not locked"}
        """
        altitude = altitude_m or self.config.default_takeoff_altitude_m

        # Validate altitude against limits
        is_valid, reason = self.guardian.validate_command({
            "altitude_amsl_m": altitude
        })
        if not is_valid:
            return {"success": False, "error": reason}

        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Wait for health checks
        logger.info("Waiting for drone health checks...")
        health_ok = await self._drone.wait_for_health()
        if not health_ok:
            return {
                "success": False,
                "error": "Health check failed - no GPS lock or home position",
            }

        # Set home position from telemetry
        try:
            async for position in drone.telemetry.position():
                self.guardian.set_home(
                    position.latitude_deg,
                    position.longitude_deg
                )
                break
        except Exception as e:
            logger.warning(f"Could not set home position: {e}")

        # Arm the drone
        logger.info("Arming drone...")
        try:
            await drone.action.arm()
            logger.info("Drone armed")
        except Exception as e:
            return {"success": False, "error": f"Failed to arm: {e}"}

        # Set takeoff altitude
        await drone.action.set_takeoff_altitude(altitude)

        # Takeoff
        logger.info(f"Taking off to {altitude}m...")
        try:
            await drone.action.takeoff()
            logger.info("Takeoff initiated")

            # Start background task to monitor takeoff, return immediately
            # to avoid blocking the MCP server
            asyncio.create_task(self._monitor_takeoff(altitude))

            return {
                "success": True,
                "message": f"Takeoff initiated to {altitude}m (monitoring in background)",
                "altitude_m": altitude,
            }

        except Exception as e:
            return {"success": False, "error": f"Takeoff failed: {e}"}

    async def _monitor_takeoff(self, altitude: float) -> None:
        """Background task to monitor takeoff completion.

        Args:
            altitude: Target altitude in meters.
        """
        # Rough estimate: ~1m/s climb rate + 2s buffer
        await asyncio.sleep(altitude + 2)
        logger.info(f"Takeoff to {altitude}m completed (background monitor)")

    async def goto_gps(
        self,
        lat: float,
        lon: float,
        alt_m: Optional[float] = None,
        speed_ms: Optional[float] = None
    ) -> dict[str, Any]:
        """Navigate drone to specified GPS coordinates.

        Args:
            lat: Target latitude in degrees.
            lon: Target longitude in degrees.
            alt_m: Target altitude in meters. Uses current altitude if not specified.
            speed_ms: Travel speed in m/s. Defaults to config.default_goto_speed_m_s.

        Returns:
            Dict with success status and navigation details.
            Example success:
                {"success": True, "message": "Navigating to target", "target": {...}}
            Example failure:
                {"success": False, "error": "Distance exceeds geofence limit"}
        """
        # Validate GPS coordinates
        try:
            validate_gps(lat, lon)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        speed = speed_ms or self.config.default_goto_speed_m_s

        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Get current position and altitude
        current_alt = None
        try:
            async for position in drone.telemetry.position():
                current_alt = position.absolute_altitude_m
                if alt_m is None:
                    alt_m = position.relative_altitude_m
                break
        except Exception as e:
            logger.warning(f"Could not get current position: {e}")

        # Validate command against safety limits
        is_valid, reason = self.guardian.validate_command({
            "latitude": lat,
            "longitude": lon,
            "altitude_amsl_m": alt_m,
            "speed_m_s": speed,
        })
        if not is_valid:
            return {"success": False, "error": reason}

        try:
            # Set speed
            await drone.action.set_maximum_speed(speed)

            # Navigate to position using goto_location
            await drone.action.goto_location(lat, lon, alt_m or current_alt or 50.0, 0.0)

            logger.info(f"Navigating to ({lat}, {lon}) at {alt_m}m")

            return {
                "success": True,
                "message": "Navigation command sent",
                "target": {
                    "latitude": lat,
                    "longitude": lon,
                    "altitude_m": alt_m,
                    "speed_m_s": speed,
                },
            }

        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {e}"}

    async def land(self) -> dict[str, Any]:
        """Command drone to land at current position.

        Returns:
            Dict with success status.
            Example success:
                {"success": True, "message": "Landing initiated"}
            Example failure:
                {"success": False, "error": "Landing failed: not in air"}
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        try:
            logger.info("Initiating landing...")
            await drone.action.land()
            logger.info("Landing command sent")

            return {
                "success": True,
                "message": "Landing initiated - drone descending",
            }

        except Exception as e:
            return {"success": False, "error": f"Landing failed: {e}"}

    async def rtl(self) -> dict[str, Any]:
        """Command drone to return to launch and land.

        Returns:
            Dict with success status.
            Example success:
                {"success": True, "message": "Return to launch initiated"}
            Example failure:
                {"success": False, "error": "RTL failed: no home position"}
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Update heartbeat
        self.guardian.update_heartbeat()

        try:
            logger.info("Initiating Return to Launch...")
            await drone.action.return_to_launch()
            logger.info("RTL command sent")

            return {
                "success": True,
                "message": "Return to Launch initiated - drone returning home",
                "home_position": self.guardian.home_position,
            }

        except Exception as e:
            return {"success": False, "error": f"RTL failed: {e}"}

    async def abort_mission(self, reason: Optional[str] = None) -> dict[str, Any]:
        """Abort current mission and hover in place.

        Args:
            reason: Optional reason for abort (for logging/reporting).

        Returns:
            Dict with success status.
            Example success:
                {"success": True, "message": "Mission aborted - hovering"}
            Example failure:
                {"success": False, "error": "Abort failed: not flying"}
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        abort_reason = reason or "User requested abort"

        try:
            logger.info(f"Aborting mission: {abort_reason}")
            # Hold position by switching to hold mode
            await drone.action.hold()
            logger.info("Hold command sent - drone hovering")

            return {
                "success": True,
                "message": "Mission aborted - drone hovering in place",
                "reason": abort_reason,
            }

        except Exception as e:
            return {"success": False, "error": f"Abort failed: {e}"}

    async def fly_body_offset(
        self,
        forward_m: float = 0.0,
        right_m: float = 0.0,
        up_m: float = 0.0,
        yaw_align: bool = False,
        speed_m_s: Optional[float] = None,
    ) -> dict[str, Any]:
        """Fly to a body-relative offset position.

        Moves forward/back, left/right, up/down relative to current heading.

        Args:
            forward_m: Distance forward (positive) or back (negative) in meters
            right_m: Distance right (positive) or left (negative) in meters
            up_m: Distance up (positive) or down (negative) in meters
            yaw_align: If True, align yaw to movement direction
            speed_m_s: Approach speed in m/s (default: config.default_body_offset_speed_m_s)

        Returns:
            Dict with success status and metrics.
            Example success:
                {
                    "success": True,
                    "message": "Offset movement initiated",
                    "offset": {"forward_m": 10.0, "right_m": 5.0, "up_m": 2.0},
                    "target_yaw": 45.0,
                    "speed_m_s": 5.0
                }
            Example failure:
                {"success": False, "error": "State precondition failed: Must be in a flying state"}
        """
        # Check state precondition - must be in a flying state
        if not self.state_machine.check_command_precondition("set_position"):
            return {
                "success": False,
                "error": f"State precondition failed: Cannot move in {self.state_machine.current_state_name} state. Must be in a flying state (HOVERING, FLYING, POSITION_CONTROL, etc.)"
            }

        # Validate speed against limits
        speed = speed_m_s or self.config.default_body_offset_speed_m_s
        is_valid, reason = self.guardian.validate_command({"speed_m_s": speed})
        if not is_valid:
            return {"success": False, "error": reason}

        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        try:
            # Get current position and yaw from telemetry
            current_lat = None
            current_lon = None
            current_alt_amsl = None
            current_yaw = 0.0

            async for position in drone.telemetry.position():
                current_lat = position.latitude_deg
                current_lon = position.longitude_deg
                current_alt_amsl = position.absolute_altitude_m
                break

            async for attitude in drone.telemetry.attitude_euler():
                current_yaw = attitude.yaw_deg
                break

            if current_lat is None or current_lon is None:
                return {"success": False, "error": "Failed to get current position"}

            # Transform body offset to NED frame
            north_offset, east_offset = body_to_ned(forward_m, right_m, current_yaw)

            # Calculate target position using haversine approximation
            # 1 degree latitude ~ 111km, varies for longitude
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * math.cos(math.radians(current_lat))

            target_lat = current_lat + (north_offset / meters_per_deg_lat)
            target_lon = current_lon + (east_offset / meters_per_deg_lon)
            target_alt = current_alt_amsl + up_m if current_alt_amsl else 50.0 + up_m

            # Validate target against geofence
            is_valid, reason = self.guardian.validate_command({
                "latitude": target_lat,
                "longitude": target_lon,
                "altitude_amsl_m": target_alt,
            })
            if not is_valid:
                return {"success": False, "error": f"Target position invalid: {reason}"}

            # Calculate target yaw if alignment requested
            target_yaw_deg = current_yaw
            if yaw_align and (forward_m != 0 or right_m != 0):
                # Calculate heading to target in body frame
                # Add the movement direction to current yaw
                movement_angle = math.degrees(math.atan2(right_m, forward_m))
                target_yaw_deg = current_yaw + movement_angle
                # Normalize to 0-360
                target_yaw_deg = target_yaw_deg % 360.0

            # Set speed
            await drone.action.set_maximum_speed(speed)

            # Navigate to target position
            # MAVSDK goto_location takes: latitude, longitude, altitude_amsl, yaw_deg
            await drone.action.goto_location(
                target_lat,
                target_lon,
                target_alt,
                target_yaw_deg if yaw_align else current_yaw
            )

            logger.info(
                f"Body offset: forward={forward_m}m, right={right_m}m, up={up_m}m, "
                f"yaw_align={yaw_align}, speed={speed}m/s"
            )
            logger.info(
                f"Transformed to NED: north={north_offset:.1f}m, east={east_offset:.1f}m, "
                f"target=({target_lat:.6f}, {target_lon:.6f}, {target_alt:.1f}m)"
            )

            # Transition state to POSITION_CONTROL
            self.state_machine.transition(
                FlightState.POSITION_CONTROL,
                f"Body offset: forward={forward_m}m, right={right_m}m",
                "llm"
            )

            return {
                "success": True,
                "message": "Offset movement initiated - navigating to body-relative target",
                "offset": {
                    "forward_m": forward_m,
                    "right_m": right_m,
                    "up_m": up_m,
                },
                "transform": {
                    "north_m": round(north_offset, 2),
                    "east_m": round(east_offset, 2),
                },
                "target": {
                    "latitude": target_lat,
                    "longitude": target_lon,
                    "altitude_amsl_m": target_alt,
                    "yaw_deg": round(target_yaw_deg, 2),
                },
                "current": {
                    "latitude": current_lat,
                    "longitude": current_lon,
                    "yaw_deg": round(current_yaw, 2),
                },
                "yaw_align": yaw_align,
                "speed_m_s": speed,
            }

        except Exception as e:
            logger.error(f"Body offset movement failed: {e}")
            return {"success": False, "error": f"Body offset movement failed: {e}"}


    async def set_velocity(
        self,
        north_m_s: float = 0.0,
        east_m_s: float = 0.0,
        down_m_s: float = 0.0,
        yaw_deg: Optional[float] = None,
        duration_s: float = 1.0,
    ) -> dict[str, Any]:
        """Set velocity setpoint in NED frame (offboard mode).

        Critical: Must maintain 20Hz stream or PX4 triggers failsafe.

        Args:
            north_m_s: Velocity north (positive) / south (negative) in m/s
            east_m_s: Velocity east (positive) / west (negative) in m/s
            down_m_s: Velocity down (positive) / up (negative) in m/s
            yaw_deg: Absolute yaw angle (optional, maintains current if None)
            duration_s: Duration to maintain setpoint in seconds

        Returns:
            Dict with result and metrics

        Safety:
            - Max horizontal speed: 15 m/s (enforced by Guardian)
            - Max vertical speed: 3 m/s (enforced by Guardian)
            - Requires VELOCITY_CONTROL or compatible state
            - Auto-activates offboard mode
        """
        # Velocity validation
        horizontal_speed = sqrt(north_m_s**2 + east_m_s**2)
        if horizontal_speed > 15.0:
            return {"success": False, "error": "Horizontal speed exceeds 15 m/s limit"}
        if abs(down_m_s) > 3.0:
            return {"success": False, "error": "Vertical speed exceeds 3 m/s limit"}

        # State check - only allow in flying states
        valid_states = {
            FlightState.HOVERING,
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
            FlightState.HOLD,
        }
        if self.state_machine.current_state not in valid_states:
            return {
                "success": False,
                "error": f"Cannot set_velocity in state {self.state_machine.current_state_name}. "
                        f"Must be in one of: {[s.name for s in valid_states]}"
            }

        # Transition to VELOCITY_CONTROL state
        self.state_machine.transition(
            FlightState.VELOCITY_CONTROL,
            "velocity_command_issued",
            "llm"
        )

        # Get drone via ConnectionManager (singleton for fast access)
        cm = ConnectionManager()
        try:
            drone = await cm.ensure_connected()
        except ConnectionError as e:
            return {"success": False, "error": f"Not connected to drone: {e}"}

        # Prepare velocity setpoint
        yaw = yaw_deg if yaw_deg is not None else 0.0
        velocity_setpoint = VelocityNedYaw(north_m_s, east_m_s, down_m_s, yaw)

        # Start offboard streaming
        setpoint_count = await self._maintain_offboard_streaming(
            drone, velocity_setpoint, duration_s
        )

        if setpoint_count == 0:
            return {"success": False, "error": "Failed to start offboard mode"}

        return {
            "success": True,
            "velocity_ned": [north_m_s, east_m_s, down_m_s],
            "yaw_deg": yaw,
            "duration_s": duration_s,
            "setpoints_sent": setpoint_count,
            "approximate_rate_hz": round(setpoint_count / duration_s, 1) if duration_s > 0 else 0,
        }

    async def _maintain_offboard_streaming(
        self,
        drone: Any,
        velocity_setpoint: VelocityNedYaw,
        duration_s: float
    ) -> int:
        """Maintain 20Hz setpoint stream for duration.

        Critical safety function - stops offboard on any error.

        Args:
            drone: MAVSDK System instance
            velocity_setpoint: VelocityNedYaw setpoint to stream
            duration_s: Duration to maintain streaming

        Returns:
            Number of setpoints sent (0 if failed to start)
        """
        setpoint_count = 0
        start_time = time.time()
        interval = 0.05  # 20Hz = 50ms

        try:
            # Send initial setpoint before starting offboard
            await drone.offboard.set_velocity_ned(velocity_setpoint)

            # Start offboard mode
            try:
                await drone.offboard.start()
                logger.info("Offboard mode started")
            except OffboardError as e:
                logger.error(f"Failed to start offboard: {e}")
                return 0

            # Maintain 20Hz streaming
            while time.time() - start_time < duration_s:
                loop_start = time.time()

                # Re-send setpoint (required for offboard)
                await drone.offboard.set_velocity_ned(velocity_setpoint)
                setpoint_count += 1

                # Precise timing
                elapsed = time.time() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            return setpoint_count

        except asyncio.CancelledError:
            logger.warning("Offboard streaming cancelled")
            raise
        except Exception as e:
            logger.error(f"Offboard streaming failed: {e}")
            return setpoint_count
        finally:
            try:
                await drone.offboard.stop()
                logger.info("Offboard mode stopped")
                # Transition back to FLYING state
                if self.state_machine.current_state == FlightState.VELOCITY_CONTROL:
                    self.state_machine.transition(
                        FlightState.FLYING,
                        "velocity_command_completed",
                        "llm"
                    )
            except Exception as e:
                logger.warning(f"Error stopping offboard: {e}")

    async def disconnect(self) -> None:
        """Disconnect from drone."""
        if self._drone:
            await self._drone.disconnect()
        self._connected = False
        self._drone = None


# Tool function wrappers for MCP registration
async def arm_and_takeoff(altitude_m: float = 10.0) -> str:
    """MCP tool: Arm and takeoff to altitude.

    Args:
        altitude_m: Target altitude in meters (default: 10).

    Returns:
        JSON string with result.
    """
    tools = FlightTools()
    result = await tools.arm_and_takeoff(altitude_m)
    return json.dumps(result)


async def goto_gps(
    lat: float,
    lon: float,
    alt_m: float = 0.0,
    speed_ms: float = 5.0
) -> str:
    """MCP tool: Navigate to GPS coordinates.

    Args:
        lat: Target latitude in degrees.
        lon: Target longitude in degrees.
        alt_m: Target altitude in meters (0 = current altitude).
        speed_ms: Travel speed in m/s (default: 5).

    Returns:
        JSON string with result.
    """
    # Use global state machine if available
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.goto_gps(lat, lon, alt_m if alt_m > 0 else None, speed_ms)
    return json.dumps(result)


async def land() -> str:
    """MCP tool: Land at current position.

    Returns:
        JSON string with result.
    """
    tools = FlightTools()
    result = await tools.land()
    return json.dumps(result)


async def rtl() -> str:
    """MCP tool: Return to launch position and land.

    Returns:
        JSON string with result.
    """
    tools = FlightTools()
    result = await tools.rtl()
    return json.dumps(result)


async def abort_mission(reason: str = "") -> str:
    """MCP tool: Abort mission and hover.

    Args:
        reason: Optional reason for abort.

    Returns:
        JSON string with result.
    """
    tools = FlightTools()
    result = await tools.abort_mission(reason if reason else None)
    return json.dumps(result)


async def hold(
    duration_s: float = 5.0,
    position_tolerance_m: float = 1.0,
    auto_rtl_on_drift: bool = False,
) -> str:
    """MCP tool: Hold position with monitoring.

    Enters position hold mode and monitors for drift.
    Automatically transitions state machine to HOVERING.

    Args:
        duration_s: Duration to hold position in seconds (default: 5).
        position_tolerance_m: Allowed position drift in meters (default: 1).
        auto_rtl_on_drift: If True, RTL when drift exceeds tolerance (default: False).

    Returns:
        JSON string with result containing:
        - success: Whether hold completed successfully
        - duration_s: Duration held
        - max_drift_m: Maximum drift detected
        - was_drift_detected: Whether drift exceeded tolerance
        - state: Current flight state name
        - error/reason: Error message if failed
    """
    # Use global state machine and telemetry cache if available
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.hold(duration_s, position_tolerance_m, auto_rtl_on_drift)
    return json.dumps(result)


async def fly_body_offset(
    forward_m: float = 0.0,
    right_m: float = 0.0,
    up_m: float = 0.0,
    yaw_align: bool = False,
    speed_m_s: float = 5.0,
) -> str:
    """MCP tool: Fly to body-relative offset position.

    Moves forward/back, left/right, up/down relative to current heading.
    Body frame is oriented with the drone's current yaw direction.

    Args:
        forward_m: Distance forward (positive) or back (negative) in meters.
        right_m: Distance right (positive) or left (negative) in meters.
        up_m: Distance up (positive) or down (negative) in meters.
        yaw_align: If True, align yaw to movement direction (default: False).
        speed_m_s: Approach speed in m/s (default: 5).

    Returns:
        JSON string with result containing:
        - success: Whether movement was initiated
        - offset: Body frame offset applied
        - transform: NED frame transformation
        - target: Target position (lat, lon, alt, yaw)
        - current: Current position (lat, lon, yaw)
        - error: Error message if failed
    """
    # Use global state machine if available
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.fly_body_offset(forward_m, right_m, up_m, yaw_align, speed_m_s)
    return json.dumps(result)


async def set_velocity(
    north_m_s: float = 0.0,
    east_m_s: float = 0.0,
    down_m_s: float = 0.0,
    yaw_deg: float = 0.0,
    duration_s: float = 1.0,
) -> str:
    """MCP tool: Set velocity setpoint in NED frame (offboard mode).

    Critical: Must maintain 20Hz stream or PX4 triggers failsafe.
    Max horizontal speed: 15 m/s. Max vertical speed: 3 m/s.

    Args:
        north_m_s: Velocity north (positive) / south (negative) in m/s
        east_m_s: Velocity east (positive) / west (negative) in m/s
        down_m_s: Velocity down (positive) / up (negative) in m/s
        yaw_deg: Absolute yaw angle in degrees (0 = north, 90 = east)
        duration_s: Duration to maintain setpoint in seconds (default: 1.0)

    Returns:
        JSON string with result.
    """
    # Use global state machine if available
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.set_velocity(north_m_s, east_m_s, down_m_s, yaw_deg, duration_s)
    return json.dumps(result)
