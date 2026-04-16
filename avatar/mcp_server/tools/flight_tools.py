"""Flight control MCP tools for Project Avatar.

This module provides drone flight control capabilities for MCP-compatible AI agents.
It wraps MAVSDK operations with safety validation through the GuardianProcess and
state machine tracking for reliable autonomous flight operations.

Available Tools (MCP Functions):
    - arm_and_takeoff: Arm the drone and takeoff to a specified altitude
    - goto_gps: Navigate to absolute GPS coordinates
    - fly_body_offset: Move relative to current position (forward/right/up)
    - set_velocity: Direct velocity control in NED frame (offboard mode)
    - land: Land at current position
    - rtl: Return to launch position and land
    - abort_mission: Emergency abort - stop and hover in place
    - hold: Hold position with drift monitoring

Architecture:
    The module uses a two-layer design:
    1. FlightTools class: Core implementation with state machine integration
    2. Module-level async functions: MCP-compatible wrappers that return JSON strings

Safety Integration:
    All flight commands validate against:
    - GuardianProcess hard limits (geofence, altitude, speed)
    - FlightStateMachine state preconditions
    - MAVSDK health checks (GPS lock, home position)

Coordinate Frames:
    - NED: North-East-Down (inertial frame, absolute)
    - Body: Forward-Right-Down (drone-relative, changes with yaw)

Example Usage (as MCP tool):
    >>> result = await arm_and_takeoff(altitude_m=15)
    >>> print(json.loads(result))
    {"success": True, "message": "Takeoff initiated...", "altitude_m": 15}

Example Usage (direct FlightTools):
    >>> tools = FlightTools()
    >>> result = await tools.goto_gps(lat=37.7749, lon=-122.4194, alt_m=20)
    >>> print(result)
    {"success": True, "message": "Navigation command sent", "target": {...}}

Dependencies:
    - MAVSDK: For PX4/MAVLink communication
    - GuardianProcess: Safety validation
    - FlightStateMachine: State tracking
    - ConnectionManager: Persistent drone connection singleton

Note:
    All functions are async and must be awaited. Connection to the drone
    (real or SITL) must be established before calling any flight command.
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Optional, Tuple, Dict, List

# Internal imports - these provide the safety and connection layers
from avatar.mav.connection import DroneConnection, ConnectionConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.offboard_streamer import OffboardVelocityStreamer

# MAVSDK imports with fallback for testing environments
# This allows the module to be imported even when MAVSDK is not installed
try:
    from mavsdk.offboard import VelocityNedYaw, OffboardError
except ImportError:
    # Fallback for testing without mavsdk installed
    # These mock classes allow type checking and basic testing
    class VelocityNedYaw:  # type: ignore
        """Mock VelocityNedYaw for testing without MAVSDK.

        In real operation, this comes from mavsdk.offboard and represents
        a velocity setpoint in NED (North-East-Down) frame with yaw.

        Attributes:
            north_m_s: Velocity north in meters/second
            east_m_s: Velocity east in meters/second
            down_m_s: Velocity down in meters/second (positive = descending)
            yaw_deg: Yaw angle in degrees (0 = north, 90 = east)
        """

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
        """Mock OffboardError for testing.

        In real operation, raised by MAVSDK when offboard mode fails to start.
        Common causes:
            - No position estimate (no GPS lock)
            - Already in offboard mode
            - Vehicle not armed
        """
        pass

# Module-level logger for debugging flight operations
logger = logging.getLogger(__name__)

# Global state references - set by the MCP server at startup
# These allow the flight tools to integrate with the server's state management
_state_machine: Optional[FlightStateMachine] = None
_telemetry_cache: Optional[Any] = None


def set_state_machine(sm: FlightStateMachine) -> None:
    """Set the global state machine reference.

    This is called by the MCP server during initialization to enable
    flight tools to track and validate flight state transitions.

    Args:
        sm: The state machine instance to use for all flight operations.

    Example:
        >>> from avatar.mav.state_machine import FlightStateMachine
        >>> sm = FlightStateMachine()
        >>> set_state_machine(sm)
    """
    global _state_machine
    _state_machine = sm


def set_telemetry_cache(cache: Any) -> None:
    """Set the global telemetry cache reference.

    The telemetry cache provides fast access to current drone state
    (position, altitude, battery, etc.) without blocking on MAVSDK calls.
    Called by the MCP server during initialization.

    Args:
        cache: The telemetry cache instance (typically TelemetryCache class).

    Example:
        >>> from avatar.mav.telemetry_cache import TelemetryCache
        >>> cache = TelemetryCache()
        >>> set_telemetry_cache(cache)
    """
    global _telemetry_cache
    _telemetry_cache = cache


def get_state_machine() -> Optional[FlightStateMachine]:
    """Get the global state machine instance.

    Returns:
        The state machine instance if set, None otherwise.
        When None, FlightTools will create its own state machine.
    """
    return _state_machine


def get_telemetry_cache() -> Optional[Any]:
    """Get the global telemetry cache instance.

    Returns:
        TelemetryCache instance if set, None otherwise.
        When None, flight tools will query MAVSDK directly (slower).
    """
    return _telemetry_cache


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in meters.

    Uses the haversine formula which accounts for Earth's curvature.
    Accurate for typical drone flight distances (up to several km).

    Args:
        lat1: Latitude of first point in degrees (-90 to 90).
        lon1: Longitude of first point in degrees (-180 to 180).
        lat2: Latitude of second point in degrees (-90 to 90).
        lon2: Longitude of second point in degrees (-180 to 180).

    Returns:
        Distance between the two points in meters.

    Example:
        >>> # Distance between San Francisco and Los Angeles (approx)
        >>> d = haversine_distance(37.7749, -122.4194, 34.0522, -118.2437)
        >>> print(f"Distance: {d/1000:.1f} km")
        Distance: 559.0 km

    Note:
        Earth radius is approximated as 6,371 km (mean radius).
        For drone-scale distances, this is sufficiently accurate.
    """
    R = 6371000  # Earth's mean radius in meters

    # Convert to radians for trigonometric functions
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    # Haversine formula
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def body_to_ned(
    forward_m: float,
    right_m: float,
    yaw_deg: float
) -> Tuple[float, float]:
    """Transform body-frame offset to NED (North-East-Down) frame.

    This is essential for body-relative movement commands. The drone's body
    frame changes with its heading, while NED is an inertial (fixed) frame.

    Body Frame (drone-relative):
        - forward = +X_body (positive = forward)
        - right = +Y_body (positive = right)
        - down = +Z_body (positive = down)

    NED Frame (inertial/absolute):
        - north = +X_ned (positive = north)
        - east = +Y_ned (positive = east)
        - down = +Z_ned (positive = down)

    Transformation (rotation from body to NED by yaw angle):
        north = forward * cos(yaw) - right * sin(yaw)
        east = forward * sin(yaw) + right * cos(yaw)

    Args:
        forward_m: Distance forward (positive) or backward (negative) in meters.
        right_m: Distance right (positive) or left (negative) in meters.
        yaw_deg: Current yaw angle in degrees (0 = north, 90 = east, 180 = south).

    Returns:
        Tuple of (north_offset_m, east_offset_m) - the equivalent movement
        in the NED (inertial) frame.

    Example:
        >>> # Drone facing east (90 degrees), move 10m forward
        >>> north, east = body_to_ned(forward_m=10, right_m=0, yaw_deg=90)
        >>> print(f"NED offset: north={north:.1f}m, east={east:.1f}m")
        NED offset: north=0.0m, east=10.0m
        >>> # Drone facing north (0 degrees), move 5m right
        >>> north, east = body_to_ned(forward_m=0, right_m=5, yaw_deg=0)
        >>> print(f"NED offset: north={north:.1f}m, east={east:.1f}m")
        NED offset: north=0.0m, east=5.0m
    """
    yaw_rad = math.radians(yaw_deg)

    # 2D rotation matrix application
    north = forward_m * math.cos(yaw_rad) - right_m * math.sin(yaw_rad)
    east = forward_m * math.sin(yaw_rad) + right_m * math.cos(yaw_rad)

    return north, east


def validate_gps(lat: float, lon: float) -> None:
    """Validate GPS coordinates are within valid ranges.

    This is a basic sanity check before sending navigation commands.
    Invalid coordinates can cause navigation failures or safety issues.

    Args:
        lat: Latitude in degrees. Valid range: -90 to 90.
        lon: Longitude in degrees. Valid range: -180 to 180.

    Raises:
        ValueError: If latitude or longitude are outside valid ranges.

    Example:
        >>> validate_gps(37.7749, -122.4194)  # San Francisco - OK
        >>> validate_gps(95.0, 0.0)  # Invalid latitude - raises ValueError
        Traceback (most recent call last):
            ...
        ValueError: Latitude must be between -90 and 90, got 95.0
    """
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")


@dataclass
class FlightToolsConfig:
    """Configuration parameters for flight tools.

    This dataclass holds default values for flight operations.
    Create a custom instance to override defaults.

    Attributes:
        system_address: MAVSDK connection string (e.g., "udp://:14540" for SITL).
        max_retries: Number of connection retry attempts.
        retry_delay_s: Seconds to wait between connection retries.
        health_timeout_s: Maximum seconds to wait for health checks.
        default_takeoff_altitude_m: Default altitude for takeoff if not specified.
        default_goto_speed_m_s: Default speed for GPS navigation.
        default_body_offset_speed_m_s: Default speed for body-relative movement.

    Example:
        >>> config = FlightToolsConfig(
        ...     system_address="serial:///dev/ttyUSB0:921600",
        ...     default_takeoff_altitude_m=20.0,
        ...     default_goto_speed_m_s=8.0
        ... )
        >>> tools = FlightTools(config=config)
    """
    system_address: str = "udp://:14540"  # Default SITL connection
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0
    default_takeoff_altitude_m: float = 10.0
    default_goto_speed_m_s: float = 5.0
    default_body_offset_speed_m_s: float = 5.0


class FlightTools:
    """Core flight control implementation for the MCP server.

    This class provides all flight operations with integrated safety validation,
    state machine tracking, and MAVSDK communication. Each method handles:
    1. Connection management (via ConnectionManager singleton)
    2. Safety validation (via GuardianProcess)
    3. State machine transitions
    4. MAVSDK command execution
    5. Result reporting

    Usage:
        Typically used through the module-level MCP wrapper functions,
        but can be instantiated directly for custom implementations.

        >>> tools = FlightTools()
        >>> result = await tools.arm_and_takeoff(altitude_m=15)
        >>> if result["success"]:
        ...     print("Takeoff initiated!")
        >>> else:
        ...     print(f"Failed: {result['error']}")

    Safety:
        All commands validate against GuardianProcess limits:
        - Geofence boundaries
        - Maximum altitude
        - Speed limits
        - Distance from home

    State Management:
        Commands check and update the FlightStateMachine:
        - Precondition checks (e.g., can't takeoff if already flying)
        - State transitions (e.g., ARMING -> TAKEOFF -> FLYING)
        - Failsafe triggers on errors

    Attributes:
        config: FlightToolsConfig instance with operation parameters.
        hard_limits: GuardianProcess safety limits.
        guardian: GuardianProcess instance for command validation.
        state_machine: FlightStateMachine for state tracking.
        _drone: DroneConnection wrapper (lazily initialized).
        _connected: Whether MAVSDK connection is active.
        _heartbeat_task: Background heartbeat update task.
    """

    def __init__(
        self,
        config: Optional[FlightToolsConfig] = None,
        hard_limits: Optional[HardLimits] = None,
        state_machine: Optional[FlightStateMachine] = None
    ):
        """Initialize flight tools with configuration and safety components.

        Args:
            config: Flight tools configuration. Uses defaults if not provided.
            hard_limits: Safety limits for GuardianProcess. Uses defaults if not provided.
            state_machine: Flight state machine for state tracking.
                          Creates new instance if not provided (not recommended for MCP use).

        Example:
            >>> # Default initialization (for MCP server)
            >>> tools = FlightTools()
            >>>
            >>> # Custom configuration for outdoor flight
            >>> from avatar.mav.guardian import HardLimits
            >>> limits = HardLimits(
            ...     max_distance_from_home_m=500,
            ...     max_altitude_msl_m=120
            ... )
            >>> config = FlightToolsConfig(default_goto_speed_m_s=10.0)
            >>> tools = FlightTools(config=config, hard_limits=limits)
        """
        self.config = config or FlightToolsConfig()
        self.hard_limits = hard_limits or HardLimits()
        self.guardian = GuardianProcess(self.hard_limits)
        self.state_machine = state_machine or FlightStateMachine()
        self._drone: Optional[DroneConnection] = None
        self._connected = False
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self.offboard_streamer = OffboardVelocityStreamer(rate_hz=20.0)

    async def _ensure_connection(self) -> Dict[str, Any]:
        """Ensure MAVSDK drone connection is established.

        Uses ConnectionManager singleton pattern for efficient connection reuse.
        The ConnectionManager maintains a persistent connection across tool calls,
        avoiding repeated connect/disconnect overhead.

        This method is called internally by all flight commands before
        attempting MAVSDK operations.

        Returns:
            Empty dict {} if connection successful.
            Error dict {"success": False, "error": "..."} if connection failed.

        Side Effects:
            - Sets self._drone to DroneConnection wrapper
            - Sets self._connected to True
            - Starts background heartbeat task if not running

        Example:
            >>> # Internal usage in flight commands
            >>> conn_error = await self._ensure_connection()
            >>> if conn_error:
            ...     return conn_error  # Return error to caller
            >>> # Connection established, proceed with command
        """
        # Use ConnectionManager singleton for persistent connection across calls
        cm = ConnectionManager()

        try:
            # Attempt to get or establish connection
            drone = await cm.ensure_connected()
            if drone is None:
                return {
                    "success": False,
                    "error": "Failed to connect to drone. Ensure SITL or hardware is running.",
                }

            # Wrap MAVSDK System in DroneConnection for compatibility
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

            # Start heartbeat background task for GuardianProcess
            # This updates the "last command timestamp" at 20Hz
            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return {}

        except ConnectionError as e:
            return {
                "success": False,
                "error": f"Failed to connect to drone: {e}",
            }

    async def _heartbeat_loop(self) -> None:
        """Background task to update GuardianProcess heartbeat at 20Hz.

        The heartbeat informs the GuardianProcess that the control system is alive.
        If the heartbeat stops, the Guardian may trigger failsafe actions.

        This runs continuously while _connected is True.

        Note:
            This is an internal background task. Do not call directly.
        """
        while self._connected:
            self.guardian.update_heartbeat()
            await asyncio.sleep(0.05)  # 20Hz update rate

    async def arm_and_takeoff(
        self,
        altitude_m: Optional[float] = None
    ) -> dict[str, Any]:
        """Arm the drone motors and takeoff to specified altitude.

        This is the standard initialization sequence for flight:
        1. Validate altitude against limits
        2. Connect to drone
        3. Wait for health checks (GPS lock, home position set)
        4. Set home position from current location
        5. Arm motors
        6. Set takeoff altitude
        7. Initiate takeoff
        8. Start background monitoring

        When to Use:
            - At the start of any flight mission
            - After landing if you want to fly again
            - When transitioning from ground to air operations

        MAVSDK Operations:
            - action.arm(): Engages motor controllers
            - action.set_takeoff_altitude(): Sets target altitude
            - action.takeoff(): Initiates vertical climb
            - telemetry.position(): Gets GPS for home position

        Args:
            altitude_m: Target takeoff altitude in meters above takeoff point.
                       Defaults to config.default_takeoff_altitude_m (10m).
                       Typical values: 5-30m for safety and obstacle clearance.

        Returns:
            Dict with operation result:
            {
                "success": bool,       # True if takeoff initiated successfully
                "message": str,        # Human-readable status
                "altitude_m": float,   # Target altitude
                "error": str           # Present only if success is False
            }

            Example success:
                {"success": True, "message": "Takeoff initiated to 15m", "altitude_m": 15}

            Example failure:
                {"success": False, "error": "Failed to arm: GPS not locked"}

        State Transitions:
            - Current -> ARMING -> TAKEOFF -> FLYING (monitored in background)

        Safety Checks:
            - Altitude within max_altitude_msl_m limit
            - GPS lock available (wait_for_health)
            - Home position can be determined

        Example:
            >>> tools = FlightTools()
            >>> result = await tools.arm_and_takeoff(altitude_m=15)
            >>> if result["success"]:
            ...     print(f"Climbing to {result['altitude_m']}m...")
            ... else:
            ...     print(f"Takeoff failed: {result.get('error')}")
        """
        altitude = altitude_m or self.config.default_takeoff_altitude_m

        # Validate altitude against Guardian hard limits
        is_valid, reason = self.guardian.validate_command({
            "altitude_amsl_m": altitude
        })
        if not is_valid:
            return {"success": False, "error": reason}

        # Establish MAVSDK connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Wait for health checks - GPS lock and home position required
        logger.info("Waiting for drone health checks...")
        health_ok = await self._drone.wait_for_health()
        if not health_ok:
            return {
                "success": False,
                "error": "Health check failed - no GPS lock or home position",
            }

        # Set home position from current GPS reading
        # This is critical for RTL (return to launch) safety feature
        try:
            async for position in drone.telemetry.position():
                self.guardian.set_home(
                    position.latitude_deg,
                    position.longitude_deg
                )
                logger.info(f"Home set: {position.latitude_deg}, {position.longitude_deg}")
                break  # Get first position reading only
        except Exception as e:
            logger.warning(f"Could not set home position: {e}")
            # Continue anyway - non-fatal for takeoff

        # Arm the drone - engage motor controllers
        logger.info("Arming drone...")
        try:
            await drone.action.arm()
            if self.state_machine.current_state == FlightState.DISARMED:
                self.state_machine.transition(
                    FlightState.ARMED,
                    "arm_command_completed",
                    "mavsdk",
                )
            logger.info("Drone armed - motors ready")
        except Exception as e:
            return {"success": False, "error": f"Failed to arm: {e}"}

        # Set takeoff altitude in MAVSDK
        await drone.action.set_takeoff_altitude(altitude)

        # Initiate takeoff
        logger.info(f"Taking off to {altitude}m...")
        try:
            await drone.action.takeoff()
            if self.state_machine.current_state == FlightState.ARMED:
                self.state_machine.transition(
                    FlightState.TAKING_OFF,
                    "takeoff_command_issued",
                    "mavsdk",
                )
            logger.info("Takeoff initiated - climb started")

            # Start background task to monitor takeoff completion
            # We return immediately to avoid blocking the MCP server
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

        Monitors the takeoff progress and updates state machine when complete.
        This runs asynchronously so the main command returns immediately.

        Args:
            altitude: Target altitude in meters (used for timing estimate).

        Note:
            This is an internal background task. Do not call directly.
            Uses simple time-based estimation (~1m/s climb rate).
        """
        # Estimate: ~1m/s climb rate + 2 second buffer for acceleration
        await asyncio.sleep(altitude + 2)
        if self.state_machine.current_state == FlightState.TAKING_OFF:
            self.state_machine.transition(
                FlightState.HOVERING,
                "takeoff_monitor_completed",
                "telemetry",
            )
        logger.info(f"Takeoff to {altitude}m completed (background monitor)")

    async def goto_gps(
        self,
        lat: float,
        lon: float,
        alt_m: Optional[float] = None,
        speed_ms: Optional[float] = None
    ) -> dict[str, Any]:
        """Navigate drone to absolute GPS coordinates.

        Commands the drone to fly to a specific latitude/longitude position.
        The drone will maintain its current altitude or use the specified one.

        When to Use:
            - Flying to specific waypoints in a mission
            - Moving to a target location identified by vision/object detection
            - Relocating to a new area for search/patrol
            - Return to a specific coordinate

        MAVSDK Operations:
            - action.set_maximum_speed(): Set travel speed
            - action.goto_location(): Command navigation to target
            - telemetry.position(): Get current altitude if not specified

        Args:
            lat: Target latitude in decimal degrees (-90 to 90).
            lon: Target longitude in decimal degrees (-180 to 180).
            alt_m: Target altitude in meters above sea level.
                   If None, uses current relative altitude.
                   Typical: 20-120m for safe flight.
            speed_ms: Travel speed in meters/second.
                      Defaults to config.default_goto_speed_m_s (5 m/s).
                      Max: 15 m/s (enforced by Guardian).

        Returns:
            Dict with navigation result:
            {
                "success": bool,
                "message": str,
                "target": {
                    "latitude": float,
                    "longitude": float,
                    "altitude_m": float,
                    "speed_m_s": float
                }
            }

            Example success:
                {
                    "success": True,
                    "message": "Navigation command sent",
                    "target": {"latitude": 37.7749, "longitude": -122.4194,
                              "altitude_m": 20, "speed_m_s": 5}
                }

            Example failure:
                {"success": False, "error": "Distance exceeds geofence limit"}

        Safety Checks:
            - GPS coordinates are valid ranges
            - Target within geofence boundaries
            - Altitude within max_altitude_msl_m
            - Speed within speed limits

        State Transitions:
            - FLYING -> POSITION_CONTROL -> FLYING (on arrival)

        Example:
            >>> # Navigate to San Francisco coordinates
            >>> result = await tools.goto_gps(
            ...     lat=37.7749,
            ...     lon=-122.4194,
            ...     alt_m=50,
            ...     speed_ms=8
            ... )
            >>> print(result["message"])
            Navigation command sent
        """
        # Validate GPS coordinates are in valid ranges
        try:
            validate_gps(lat, lon)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        speed = speed_ms or self.config.default_goto_speed_m_s

        # Establish connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Get current position and altitude from telemetry
        current_abs_alt = None
        current_rel_alt = None
        try:
            async for position in drone.telemetry.position():
                current_abs_alt = position.absolute_altitude_m
                current_rel_alt = position.relative_altitude_m
                if self.guardian.home_position is None:
                    self.guardian.set_home(
                        position.latitude_deg,
                        position.longitude_deg,
                    )
                # If no altitude specified, use current relative altitude
                if alt_m is None:
                    alt_m = current_rel_alt
                break  # Single reading sufficient
        except Exception as e:
            logger.warning(f"Could not get current position: {e}")

        # Validate target against Guardian safety limits
        is_valid, reason = self.guardian.validate_command({
            "latitude": lat,
            "longitude": lon,
            "altitude_amsl_m": alt_m,
            "speed_m_s": speed,
        })
        if not is_valid:
            return {"success": False, "error": reason}

        try:
            set_maximum_speed = getattr(drone.action, "set_maximum_speed", None)
            if callable(set_maximum_speed):
                await set_maximum_speed(speed)

            # Navigate to target position using MAVSDK goto_location
            # Parameters: lat, lon, altitude_amsl, yaw_deg (0 = maintain current)
            if current_abs_alt is not None and current_rel_alt is not None and alt_m is not None:
                target_alt_amsl = current_abs_alt - current_rel_alt + alt_m
            else:
                target_alt_amsl = alt_m or current_abs_alt or 50.0

            await drone.action.goto_location(lat, lon, target_alt_amsl, 0.0)

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

        Initiates a controlled descent to land at the current horizontal position.
        The drone will descend vertically until ground contact is detected.

        When to Use:
            - End of mission - land at current location
            - Emergency landing at current position
            - Before disarming after completing operations
            - Battery low - land immediately

        MAVSDK Operations:
            - action.land(): Initiates landing mode

        Returns:
            Dict with landing result:
            {
                "success": bool,
                "message": str,
                "error": str  # Present only if failed
            }

            Example success:
                {"success": True, "message": "Landing initiated - drone descending"}

            Example failure:
                {"success": False, "error": "Landing failed: not in air"}

        State Transitions:
            - FLYING/HOVERING -> LANDING -> DISARMED (on ground contact)

        Safety Notes:
            - Ensure landing area is clear of obstacles
            - Landing may be rejected if not in appropriate flight state
            - Ground effect may cause instability near surface

        Example:
            >>> result = await tools.land()
            >>> if result["success"]:
            ...     print("Landing sequence started...")
        """
        # Establish connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        try:
            logger.info("Initiating landing...")
            await drone.action.land()
            logger.info("Landing command sent - descending")

            return {
                "success": True,
                "message": "Landing initiated - drone descending",
            }

        except Exception as e:
            return {"success": False, "error": f"Landing failed: {e}"}

    async def rtl(self) -> dict[str, Any]:
        """Command drone to Return to Launch (RTL) position and land.

        RTL is the primary safety recovery mode. The drone will:
        1. Ascend to RTL altitude (if below)
        2. Fly directly to home position (takeoff point)
        3. Land at home position

        When to Use:
            - Mission complete - return to takeoff point
            - Low battery - emergency return
            - Communication loss expected
            - Failsafe trigger (automatic or manual)
            - User requests return to base

        MAVSDK Operations:
            - action.return_to_launch(): Initiates RTL mode
            - guardian.home_position: Reference for home location

        Returns:
            Dict with RTL result:
            {
                "success": bool,
                "message": str,
                "home_position": {"lat": float, "lon": float} or None,
                "error": str  # Present only if failed
            }

            Example success:
                {
                    "success": True,
                    "message": "Return to Launch initiated",
                    "home_position": {"lat": 37.7749, "lon": -122.4194}
                }

            Example failure:
                {"success": False, "error": "RTL failed: no home position"}

        State Transitions:
            - Any flying state -> RTL -> LANDING -> DISARMED

        Requirements:
            - Home position must have been set during arming
            - GPS lock required for navigation

        Safety:
            - RTL altitude should be above all obstacles between current and home
            - Clears geofence checks (RTL is always allowed as failsafe)

        Example:
            >>> result = await tools.rtl()
            >>> if result["success"]:
            ...     print(f"Returning to {result['home_position']}")
        """
        # Establish connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone

        # Update heartbeat to show activity
        self.guardian.update_heartbeat()

        try:
            logger.info("Initiating Return to Launch...")
            await drone.action.return_to_launch()
            logger.info("RTL command sent - returning home")

            return {
                "success": True,
                "message": "Return to Launch initiated - drone returning home",
                "home_position": self.guardian.home_position,
            }

        except Exception as e:
            return {"success": False, "error": f"RTL failed: {e}"}

    async def abort_mission(self, reason: Optional[str] = None) -> dict[str, Any]:
        """Abort current mission and hover in place.

        Immediately stops any ongoing mission or navigation and commands
        the drone to hold position. This is the emergency "pause" button.

        When to Use:
            - Emergency stop - hold position immediately
            - Abort current mission due to unexpected conditions
            - Pause for manual intervention
            - Stop before executing a different command
            - Obstacle detected in path

        MAVSDK Operations:
            - action.hold(): Switches to hold mode (position hold)

        Args:
            reason: Optional reason for abort (logged for debugging).
                    Example: "Obstacle detected", "User request", "Low battery"

        Returns:
            Dict with abort result:
            {
                "success": bool,
                "message": str,
                "reason": str,
                "error": str  # Present only if failed
            }

            Example success:
                {
                    "success": True,
                    "message": "Mission aborted - drone hovering",
                    "reason": "Obstacle detected ahead"
                }

            Example failure:
                {"success": False, "error": "Abort failed: not flying"}

        State Transitions:
            - Any flying state -> HOVERING

        Note:
            Does NOT land the drone - only stops movement and hovers.
            Use land() or rtl() if you need to descend.

        Example:
            >>> result = await tools.abort_mission("Vision system detected obstacle")
            >>> print(result["message"])
            Mission aborted - drone hovering
        """
        # Establish connection
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

    async def hold(
        self,
        duration_s: float = 5.0,
        position_tolerance_m: float = 1.0,
        auto_rtl_on_drift: bool = False,
    ) -> dict[str, Any]:
        """Hold position with drift monitoring.

        Commands the drone to hold its current position and actively monitors
        for position drift. Can automatically trigger RTL if drift exceeds tolerance.

        This is more sophisticated than abort_mission() as it provides:
        - Duration-based holding (not indefinite)
        - Drift detection and measurement
        - Optional automatic RTL on excessive drift

        When to Use:
            - Waiting at a waypoint for a condition
            - Hovering while processing vision data
            - Stability testing
            - Holding for other aircraft to pass
            - Taking photos/video at a fixed position

        MAVSDK Operations:
            - action.hold(): Enter hold mode
            - telemetry.position(): Monitor current position

        Args:
            duration_s: Duration to hold position in seconds (default: 5.0).
                       Typical: 5-30s for waypoint holds.
            position_tolerance_m: Allowed position drift in meters (default: 1.0).
                               If exceeded, drift_detected becomes True.
            auto_rtl_on_drift: If True, trigger RTL when drift exceeds tolerance.
                              Safety feature for GPS/estimation failures.
                              Default: False (just report drift).

        Returns:
            Dict with hold result:
            {
                "success": bool,
                "duration_s": float,       # Requested duration
                "max_drift_m": float,      # Maximum drift detected
                "was_drift_detected": bool,# True if drift exceeded tolerance
                "state": str,              # Current flight state name
                "error": str               # Present only if failed
            }

            Example success:
                {
                    "success": True,
                    "duration_s": 10.0,
                    "max_drift_m": 0.5,
                    "was_drift_detected": False,
                    "state": "HOVERING"
                }

            Example with drift detection:
                {
                    "success": True,
                    "duration_s": 30.0,
                    "max_drift_m": 2.3,
                    "was_drift_detected": True,
                    "state": "HOVERING"
                }

        State Transitions:
            - FLYING -> HOVERING (hold starts)
            - HOVERING -> FLYING (after duration, if continuing)

        Monitoring:
            - Position sampled from telemetry cache or MAVSDK at 10Hz
            - Drift calculated using haversine_distance()
            - Initial position captured at hold start

        Example:
            >>> # Hold for 10 seconds, RTL if drift > 2m
            >>> result = await tools.hold(
            ...     duration_s=10,
            ...     position_tolerance_m=2.0,
            ...     auto_rtl_on_drift=True
            ... )
            >>> print(f"Max drift: {result['max_drift_m']:.2f}m")
        """
        # Check state precondition - must be in appropriate state for holding
        sm = self.state_machine
        if not sm.check_command_precondition("hold"):
            return {"success": False, "error": f"Cannot hold in state {sm.current_state_name}"}

        # Get initial position from telemetry cache (fast) or drone directly
        initial_lat: Optional[float] = None
        initial_lon: Optional[float] = None

        # Try telemetry cache first (non-blocking, preferred)
        cache = get_telemetry_cache()
        if cache:
            cache_data = cache.get_data()
            if cache_data:
                initial_lat = cache_data.latitude
                initial_lon = cache_data.longitude

        # Fall back to direct MAVSDK telemetry (blocking)
        if initial_lat is None or initial_lon is None:
            conn_error = await self._ensure_connection()
            if conn_error:
                return conn_error

            if self._drone is None or self._drone.drone is None:
                return {"success": False, "error": "Drone not connected"}

            try:
                # Get single position reading from MAVSDK
                async for position in self._drone.drone.telemetry.position():
                    initial_lat = position.latitude_deg
                    initial_lon = position.longitude_deg
                    break  # Single reading sufficient
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
                # Non-fatal: continue monitoring anyway

        # Update state machine to HOVERING
        sm.transition(FlightState.HOVERING, reason="hold_command", source="llm")

        # Monitor position for requested duration
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

            await asyncio.sleep(0.1)  # 10Hz monitoring rate

        return {
            "success": True,
            "duration_s": duration_s,
            "max_drift_m": max_drift,
            "was_drift_detected": drift_detected,
            "state": sm.current_state_name,
        }

    async def fly_body_offset(
        self,
        forward_m: float = 0.0,
        right_m: float = 0.0,
        up_m: float = 0.0,
        yaw_align: bool = False,
        speed_m_s: Optional[float] = None,
    ) -> dict[str, Any]:
        """Fly to a body-relative offset position.

        Moves the drone forward/back, left/right, and up/down relative to
        its current orientation. This is intuitive for "pilot perspective"
        movement where forward is always where the drone is facing.

        Body Frame (relative to drone's current heading):
            - forward_m > 0: Move forward (where drone is facing)
            - forward_m < 0: Move backward
            - right_m > 0: Move right (from drone's perspective)
            - right_m < 0: Move left
            - up_m > 0: Ascend
            - up_m < 0: Descend

        When to Use:
            - Adjusting position relative to current heading
            - Orbiting an object (combine with yaw_align)
            - Fine position adjustments during inspection
            - Following a moving target
            - Maneuvering around obstacles

        MAVSDK Operations:
            - telemetry.position(): Get current GPS position
            - telemetry.attitude_euler(): Get current yaw angle
            - action.set_maximum_speed(): Set movement speed
            - action.goto_location(): Navigate to calculated target

        Args:
            forward_m: Distance forward (positive) or back (negative) in meters.
                     Default: 0.0 (no forward movement).
            right_m: Distance right (positive) or left (negative) in meters.
                     Default: 0.0 (no lateral movement).
            up_m: Distance up (positive) or down (negative) in meters.
                  Default: 0.0 (maintain altitude).
            yaw_align: If True, yaw to face movement direction.
                      Useful for forward-facing cameras.
                      Default: False (maintain current yaw).
            speed_m_s: Approach speed in m/s.
                      Defaults to config.default_body_offset_speed_m_s (5 m/s).

        Returns:
            Dict with movement result:
            {
                "success": bool,
                "message": str,
                "offset": {"forward_m": float, "right_m": float, "up_m": float},
                "transform": {"north_m": float, "east_m": float},
                "target": {"latitude": float, "longitude": float,
                          "altitude_amsl_m": float, "yaw_deg": float},
                "current": {"latitude": float, "longitude": float, "yaw_deg": float},
                "yaw_align": bool,
                "speed_m_s": float,
                "error": str  # Present only if failed
            }

            Example success:
                {
                    "success": True,
                    "message": "Offset movement initiated",
                    "offset": {"forward_m": 10.0, "right_m": 5.0, "up_m": 2.0},
                    "transform": {"north_m": 8.5, "east_m": 6.2},
                    "target": {"latitude": 37.7750, "longitude": -122.4193,
                              "altitude_amsl_m": 52.0, "yaw_deg": 30.0},
                    ...
                }

            Example failure:
                {"success": False, "error": "State precondition failed: Must be in flying state"}

        State Transitions:
            - FLYING/HOVERING -> POSITION_CONTROL

        Coordinate Transformation:
            1. Get current position and yaw from telemetry
            2. Transform body offset to NED using body_to_ned()
            3. Calculate target GPS using haversine approximation
            4. Validate target against geofence
            5. Send goto_location command

        Safety Checks:
            - Must be in flying state (state precondition)
            - Speed within limits
            - Target position within geofence
            - Target altitude within limits

        Example:
            >>> # Move 10m forward, 5m right, ascend 2m, align yaw
            >>> result = await tools.fly_body_offset(
            ...     forward_m=10,
            ...     right_m=5,
            ...     up_m=2,
            ...     yaw_align=True,
            ...     speed_m_s=3
            ... )
        """
        # Check state precondition - must be in a flying state to move
        if not self.state_machine.check_command_precondition("set_position"):
            return {
                "success": False,
                "error": f"State precondition failed: Cannot move in {self.state_machine.current_state_name} state. Must be in a flying state (HOVERING, FLYING, POSITION_CONTROL, etc.)"
            }

        # Validate speed against Guardian limits
        speed = speed_m_s or self.config.default_body_offset_speed_m_s
        is_valid, reason = self.guardian.validate_command({"speed_m_s": speed})
        if not is_valid:
            return {"success": False, "error": reason}

        # Establish connection
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

            # Get GPS position
            async for position in drone.telemetry.position():
                current_lat = position.latitude_deg
                current_lon = position.longitude_deg
                current_alt_amsl = position.absolute_altitude_m
                if self.guardian.home_position is None:
                    self.guardian.set_home(current_lat, current_lon)
                break

            # Get current heading (yaw)
            async for attitude in drone.telemetry.attitude_euler():
                current_yaw = attitude.yaw_deg
                break

            if current_lat is None or current_lon is None:
                return {"success": False, "error": "Failed to get current position"}

            # Transform body offset to NED frame using current yaw
            north_offset, east_offset = body_to_ned(forward_m, right_m, current_yaw)

            # Calculate target GPS coordinates
            # Using haversine approximation: 1 deg lat ~ 111km
            # Longitude varies with latitude (cos factor)
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * math.cos(math.radians(current_lat))

            target_lat = current_lat + (north_offset / meters_per_deg_lat)
            target_lon = current_lon + (east_offset / meters_per_deg_lon)
            target_alt = current_alt_amsl + up_m if current_alt_amsl else 50.0 + up_m

            # Validate target position against geofence
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
                # Calculate heading to face movement direction
                movement_angle = math.degrees(math.atan2(right_m, forward_m))
                target_yaw_deg = current_yaw + movement_angle
                # Normalize to 0-360 range
                target_yaw_deg = target_yaw_deg % 360.0

            # Set movement speed
            await drone.action.set_maximum_speed(speed)

            # Navigate to target position using MAVSDK goto_location
            # Parameters: lat, lon, altitude_amsl, yaw_deg
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

            # Update state machine to POSITION_CONTROL
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
        """Set velocity setpoint in NED frame using offboard mode.

        Offboard mode allows direct velocity control rather than position targets.
        This is useful for:
        - Smooth, continuous movement
        - Dynamic trajectory following
        - Vision-guided navigation
        - Fine-grained motion control

        CRITICAL SAFETY REQUIREMENT:
            Must maintain 20Hz setpoint stream or PX4 triggers failsafe!
            This function handles the streaming automatically.

        NED Frame (inertial/absolute):
            - north_m_s > 0: Move north
            - north_m_s < 0: Move south
            - east_m_s > 0: Move east
            - east_m_s < 0: Move west
            - down_m_s > 0: Descend
            - down_m_s < 0: Climb (negative down = up)

        When to Use:
            - Dynamic trajectory following
            - Vision-based closed-loop control
            - Smooth velocity ramping
            - Joystick-like control from LLM
            - Precise maneuvering

        MAVSDK Operations:
            - offboard.set_velocity_ned(): Send velocity setpoint (20Hz)
            - offboard.start(): Activate offboard mode
            - offboard.stop(): Deactivate offboard mode

        Args:
            north_m_s: Velocity north component in m/s (default: 0.0).
            east_m_s: Velocity east component in m/s (default: 0.0).
            down_m_s: Velocity down component in m/s (default: 0.0).
                      Positive = descending, negative = climbing.
            yaw_deg: Absolute yaw angle in degrees (default: maintain current).
                    0 = north, 90 = east, 180 = south, 270 = west.
            duration_s: Duration to maintain setpoint in seconds (default: 1.0).
                       Longer durations = longer streaming time.

        Returns:
            Dict with velocity control result:
            {
                "success": bool,
                "velocity_ned": [north_m_s, east_m_s, down_m_s],
                "yaw_deg": float,
                "duration_s": float,
                "setpoints_sent": int,        # Actual count sent
                "approximate_rate_hz": float, # Calculated streaming rate
                "error": str  # Present only if failed
            }

            Example success:
                {
                    "success": True,
                    "velocity_ned": [5.0, 0.0, 0.0],  # 5 m/s north
                    "yaw_deg": 0.0,
                    "duration_s": 3.0,
                    "setpoints_sent": 60,
                    "approximate_rate_hz": 20.0
                }

        Safety Limits (enforced):
            - Max horizontal speed: 15 m/s
            - Max vertical speed: 3 m/s
            - Must be in flying state

        State Transitions:
            - FLYING/HOVERING -> VELOCITY_CONTROL -> FLYING (after duration)

        Implementation:
            Uses _maintain_offboard_streaming() to handle 20Hz setpoint stream.
            This is a blocking call for the duration - no other commands
            can be processed simultaneously.

        Example:
            >>> # Fly north at 5 m/s for 3 seconds
            >>> result = await tools.set_velocity(
            ...     north_m_s=5.0,
            ...     east_m_s=0.0,
            ...     down_m_s=0.0,
            ...     yaw_deg=0.0,
            ...     duration_s=3.0
            ... )
            >>> print(f"Sent {result['setpoints_sent']} setpoints")

        Note:
            This function blocks for the entire duration. Do not call other
            flight commands until it completes. For non-blocking velocity
            control, use a different architecture (not implemented here).
        """
        # Validate velocity limits
        horizontal_speed = sqrt(north_m_s**2 + east_m_s**2)
        if horizontal_speed > 15.0:
            return {"success": False, "error": "Horizontal speed exceeds 15 m/s limit"}
        if abs(down_m_s) > 3.0:
            return {"success": False, "error": "Vertical speed exceeds 3 m/s limit"}

        # State check - only allow in flying states (not on ground)
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

        # Get drone via ConnectionManager singleton
        cm = ConnectionManager()
        try:
            drone = await cm.ensure_connected()
        except ConnectionError as e:
            return {"success": False, "error": f"Not connected to drone: {e}"}

        # Prepare velocity setpoint for MAVSDK
        yaw = yaw_deg if yaw_deg is not None else 0.0
        velocity_setpoint = VelocityNedYaw(north_m_s, east_m_s, down_m_s, yaw)

        # Maintain 20Hz offboard streaming for specified duration
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
        """Maintain 20Hz velocity setpoint stream for offboard mode.

        CRITICAL SAFETY FUNCTION: PX4 requires continuous setpoint stream
        at minimum 2Hz (preferably 10-20Hz) or it triggers failsafe.

        This function blocks for the entire duration and handles:
        - Starting offboard mode
        - Maintaining precise 50ms (20Hz) setpoint transmission
        - Stopping offboard mode on completion or error
        - State machine transitions

        Args:
            drone: MAVSDK System instance (from ConnectionManager).
            velocity_setpoint: VelocityNedYaw setpoint to stream repeatedly.
            duration_s: Duration to maintain streaming in seconds.

        Returns:
            Number of setpoints sent (0 if failed to start offboard).

        Raises:
            asyncio.CancelledError: If the task is cancelled (re-raised after cleanup).

        Implementation Details:
            - Target rate: 20Hz (50ms interval)
            - Sends setpoint BEFORE starting offboard (required by PX4)
            - Uses asyncio.sleep for timing (not precise real-time)
            - Calculates actual rate at completion for diagnostics

        Safety:
            - Stops offboard mode in finally block (guaranteed cleanup)
            - Logs all errors but continues streaming
            - Transitions state machine on completion

        Note:
            This is an internal helper. Use set_velocity() for normal operations.
        """
        setpoint_count = await self.offboard_streamer.stream_for(
            drone=drone,
            velocity_setpoint=velocity_setpoint,
            duration_s=duration_s,
        )

        if self.state_machine.current_state == FlightState.VELOCITY_CONTROL:
            self.state_machine.transition(
                FlightState.FLYING,
                "velocity_command_completed",
                "llm"
            )

        return setpoint_count

    async def disconnect(self) -> None:
        """Disconnect from drone and cleanup resources.

        Closes the MAVSDK connection and stops background tasks.
        Called automatically on server shutdown or when switching connections.

        Side Effects:
            - Disconnects DroneConnection
            - Sets _connected to False
            - Clears _drone reference
            - Stops heartbeat task
        """
        if self._drone:
            await self._drone.disconnect()
        self._connected = False
        self._drone = None


# =============================================================================
# MCP Tool Wrapper Functions
# =============================================================================
# These module-level functions provide the MCP-compatible interface.
# They wrap FlightTools methods and return JSON strings for MCP transport.
# =============================================================================

async def arm_and_takeoff(altitude_m: float = 10.0) -> str:
    """MCP Tool: Arm the drone and takeoff to specified altitude.

    Initiates the standard takeoff sequence: arm motors, set altitude, takeoff.
    Returns immediately with initiation status - actual takeoff is monitored
    in the background.

    When to Use:
        - At the start of any flight mission
        - To get airborne before other flight commands

    Args:
        altitude_m: Target altitude in meters above takeoff point (default: 10).
                   Recommended: 10-30m for obstacle clearance.

    Returns:
        JSON string with result dict:
        {
            "success": bool,
            "message": str,
            "altitude_m": float,
            "error": str  # Present only if success is False
        }

    Example:
        >>> result = await arm_and_takeoff(altitude_m=15)
        >>> data = json.loads(result)
        >>> print(data["message"])
        Takeoff initiated to 15m (monitoring in background)

    See Also:
        FlightTools.arm_and_takeoff() for detailed implementation.
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
    """MCP Tool: Navigate to absolute GPS coordinates.

    Commands the drone to fly to specific latitude/longitude/altitude.
    Uses MAVSDK goto_location action.

    When to Use:
        - Flying to waypoints
        - Moving to target locations
        - Area coverage missions

    Args:
        lat: Target latitude in decimal degrees (e.g., 37.7749 for SF).
        lon: Target longitude in decimal degrees (e.g., -122.4194 for SF).
        alt_m: Target altitude in meters (0 = use current altitude).
        speed_ms: Travel speed in m/s (default: 5, max: 15).

    Returns:
        JSON string with result dict containing success, message, and target details.

    Example:
        >>> result = await goto_gps(lat=37.7749, lon=-122.4194, alt_m=50, speed_ms=8)
        >>> data = json.loads(result)
        >>> print(data["target"])
        {"latitude": 37.7749, "longitude": -122.4194, "altitude_m": 50, "speed_m_s": 8}

    See Also:
        FlightTools.goto_gps() for detailed implementation.
    """
    # Use global state machine if available for state tracking
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.goto_gps(lat, lon, alt_m if alt_m > 0 else None, speed_ms)
    return json.dumps(result)


async def land() -> str:
    """MCP Tool: Land at current position.

    Initiates landing mode. Drone will descend vertically at current
    horizontal position until ground contact.

    When to Use:
        - End mission at current location
        - Emergency landing
        - Before disarming

    Returns:
        JSON string with result dict:
        {"success": True, "message": "Landing initiated - drone descending"}

    Example:
        >>> result = await land()
        >>> data = json.loads(result)
        >>> print("Landing..." if data["success"] else f"Failed: {data.get('error')}")

    See Also:
        FlightTools.land() for detailed implementation.
    """
    tools = FlightTools()
    result = await tools.land()
    return json.dumps(result)


async def rtl() -> str:
    """MCP Tool: Return to Launch position and land.

    Primary safety recovery command. Drone returns to takeoff point and lands.

    When to Use:
        - Mission complete
        - Low battery
        - Communication loss expected
        - User wants drone to come back

    Returns:
        JSON string with result dict including home_position coordinates.

    Example:
        >>> result = await rtl()
        >>> data = json.loads(result)
        >>> if data["success"]:
        ...     print(f"Returning to {data['home_position']}")

    See Also:
        FlightTools.rtl() for detailed implementation.
    """
    tools = FlightTools()
    result = await tools.rtl()
    return json.dumps(result)


async def abort_mission(reason: str = "") -> str:
    """MCP Tool: Abort mission and hover in place.

    Emergency "stop and hover" command. Does NOT land - only stops movement.

    When to Use:
        - Emergency stop
        - Pause for manual intervention
        - Obstacle detected
        - Need to reassess situation

    Args:
        reason: Optional reason for abort (logged for debugging).

    Returns:
        JSON string with result dict.

    Example:
        >>> result = await abort_mission("Obstacle detected in path")
        >>> data = json.loads(result)
        >>> print(data["message"])
        Mission aborted - drone hovering in place

    See Also:
        FlightTools.abort_mission() for detailed implementation.
    """
    tools = FlightTools()
    result = await tools.abort_mission(reason if reason else None)
    return json.dumps(result)


async def hold(
    duration_s: float = 5.0,
    position_tolerance_m: float = 1.0,
    auto_rtl_on_drift: bool = False,
) -> str:
    """MCP Tool: Hold position with drift monitoring.

    Commands drone to hold position and monitors for drift. Optionally
    triggers RTL if drift exceeds tolerance.

    When to Use:
        - Wait at waypoint
        - Hover while processing data
        - Hold for other aircraft
        - Position validation

    Args:
        duration_s: Duration to hold in seconds (default: 5).
        position_tolerance_m: Allowed drift in meters (default: 1).
        auto_rtl_on_drift: If True, RTL when drift exceeds tolerance (default: False).

    Returns:
        JSON string with result dict:
        {
            "success": bool,
            "duration_s": float,
            "max_drift_m": float,
            "was_drift_detected": bool,
            "state": str
        }

    Example:
        >>> result = await hold(duration_s=10, position_tolerance_m=2.0)
        >>> data = json.loads(result)
        >>> print(f"Max drift: {data['max_drift_m']:.2f}m")

    See Also:
        FlightTools.hold() for detailed implementation.
    """
    # Use global state machine and telemetry cache for integration
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
    """MCP Tool: Fly to body-relative offset position.

    Move forward/back, left/right, up/down relative to current heading.
    Body frame is intuitive: "forward" is where the drone is facing.

    When to Use:
        - Adjust position relative to current heading
        - Fine positioning during inspection
        - Orbiting a target
        - Following a moving subject

    Args:
        forward_m: Distance forward (positive) or back (negative) in meters.
        right_m: Distance right (positive) or left (negative) in meters.
        up_m: Distance up (positive) or down (negative) in meters.
        yaw_align: If True, yaw to face movement direction (default: False).
        speed_m_s: Movement speed in m/s (default: 5).

    Returns:
        JSON string with detailed result including offset, transform,
        target position, and current position.

    Example:
        >>> # Move 10m forward, 5m right, ascend 2m
        >>> result = await fly_body_offset(
        ...     forward_m=10, right_m=5, up_m=2, yaw_align=True
        ... )
        >>> data = json.loads(result)
        >>> print(data["transform"])  # NED transformation
        {"north_m": 8.5, "east_m": 6.2}

    See Also:
        FlightTools.fly_body_offset() for detailed implementation.
    """
    # Use global state machine for state tracking
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
    """MCP Tool: Set velocity setpoint in NED frame (offboard mode).

    Direct velocity control in inertial NED frame. Maintains 20Hz setpoint
    stream to PX4 for duration. BLOCKS for entire duration.

    CRITICAL: Must maintain 20Hz stream or PX4 triggers failsafe.
    This function handles streaming automatically.

    Safety Limits:
        - Max horizontal speed: 15 m/s
        - Max vertical speed: 3 m/s

    When to Use:
        - Dynamic trajectory following
        - Vision-guided navigation
        - Precise velocity control
        - Smooth continuous movement

    Args:
        north_m_s: Velocity north in m/s (positive=north, negative=south).
        east_m_s: Velocity east in m/s (positive=east, negative=west).
        down_m_s: Velocity down in m/s (positive=down, negative=up/climb).
        yaw_deg: Absolute yaw in degrees (0=north, 90=east, etc.).
        duration_s: Duration to maintain setpoint in seconds (default: 1.0).

    Returns:
        JSON string with result dict including velocity, duration,
        and setpoint transmission statistics.

    Example:
        >>> # Fly north at 5 m/s for 3 seconds
        >>> result = await set_velocity(
        ...     north_m_s=5.0, east_m_s=0.0, down_m_s=0.0,
        ...     yaw_deg=0.0, duration_s=3.0
        ... )
        >>> data = json.loads(result)
        >>> print(f"Sent {data['setpoints_sent']} setpoints at {data['approximate_rate_hz']}Hz")
        Sent 60 setpoints at 20.0Hz

    Note:
        This function blocks for the entire duration. No other commands
        can be executed until it completes.

    See Also:
        FlightTools.set_velocity() for detailed implementation.
    """
    # Use global state machine for state tracking
    sm = get_state_machine()
    tools = FlightTools(state_machine=sm)
    result = await tools.set_velocity(north_m_s, east_m_s, down_m_s, yaw_deg, duration_s)
    return json.dumps(result)
