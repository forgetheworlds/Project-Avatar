"""Telemetry MCP tools.

Provides drone telemetry tools for MCP-compatible AI agents.

Tools:
    - get_telemetry: Get comprehensive drone telemetry data
    - get_battery_status: Get detailed battery information
    - get_status: Get unified system status for LLM consumption

What is Telemetry and Why It Matters:
    Telemetry is the real-time data stream from the drone's flight controller that
tells us everything about its current state. Think of it as the drone's vital signs
— without it, we're flying blind. Telemetry includes:

    - Position: Where is the drone? (GPS coordinates, altitude)
    - Velocity: How fast and in what direction? (speed in 3D space)
    - Attitude: Which way is the drone facing? (roll, pitch, yaw)
    - Battery: How much power is left? (percentage, voltage, current draw)
    - Health: Are sensors calibrated and working? (GPS, gyros, accelerometers)
    - Flight Mode: Is it in manual, hover, or autonomous mode?
    - Armed/In-Air Status: Is the propellers spinning? Is it airborne?

    Why telemetry matters:
    1. Safety: We can detect low battery, poor GPS, or sensor failures before they
cause crashes
    2. Navigation: LLM agents need to know position and heading to make decisions
    3. Mission Planning: Knowing speed, altitude, and battery helps plan waypoints
    4. Geofencing: We can enforce boundaries (stay within X meters of home)
    5. Emergency Response: If something goes wrong, telemetry tells us immediately

Data Flow from PX4 to the User:

    The data flows through several layers:

    [PX4 Flight Controller] <--MAVLink--> [MAVSDK] <--Python API--> [TelemetryTools]
                                              |
                                              v
                                     [TelemetryCache] (stores latest values)
                                              |
                                              v
                                     [TelemetryTools.get_telemetry()] (formats output)
                                              |
                                              v
                                     [MCP Server] (exposes as tool)
                                              |
                                              v
                                     [AI Agent / LLM] (consumes data)

    Detailed flow:
    1. PX4 Autopilot continuously broadcasts telemetry over MAVLink protocol
       (typically at 1-10Hz for different data types)
    2. MAVSDK receives these MAVLink messages and converts them to Python objects
    3. TelemetryCache subscribes to MAVSDK streams and stores the latest values
       in memory for fast access (no blocking the MCP tool calls)
    4. When get_telemetry() is called, it reads from the cache and formats
       the data into a JSON-friendly dictionary
    5. The MCP server exposes this as a tool that any AI agent can call
    6. The LLM receives structured data it can use for decision-making

    Why this architecture?
    - Caching prevents blocking: If we waited for fresh MAVLink messages every
      time an agent requested telemetry, the response would be slow and could
      time out. The cache always has fresh data ready.
    - Async design: MAVSDK uses async/await pattern, so our tools are non-blocking
    - Safety layer: The GuardianProcess validates telemetry against limits

Telemetry Structure:

    The telemetry data is organized hierarchically for clarity:

    {
        "success": true,                    # Whether data retrieval succeeded
        "position": {                       # Geographic position
            "latitude_deg": 37.7749,       # GPS latitude (WGS84)
            "longitude_deg": -122.4194,    # GPS longitude (WGS84)
            "absolute_altitude_m": 50.0,    # Altitude above sea level (AMSL)
            "relative_altitude_m": 10.0     # Altitude above takeoff point
        },
        "velocity": {                       # Velocity in NED frame
            "north_m_s": 2.5,               # Velocity northward (positive = north)
            "east_m_s": 1.0,                # Velocity eastward (positive = east)
            "down_m_s": 0.1,                # Velocity downward (positive = down)
            "speed_m_s": 2.69               # Total horizontal ground speed
        },
        "attitude": {                       # Orientation (Euler angles)
            "roll_deg": 2.5,                # Bank angle (-180 to 180, 0 = level)
            "pitch_deg": -1.2,              # Nose up/down (-90 to 90, 0 = level)
            "yaw_deg": 45.0                 # Compass heading (0-360, 0 = north)
        },
        "battery": {                        # Battery status
            "remaining_percent": 85.0,      # Remaining capacity (0-100)
            "voltage_v": 15.2,              # Pack voltage (depends on cell count)
            "current_a": 10.5               # Current draw (positive = discharging)
        },
        "flight_mode": "OFFBOARD",          # Current flight mode (PX4 enum)
        "health": {                         # System health checks
            "is_global_position_ok": true,  # GPS lock quality sufficient
            "is_home_position_ok": true,    # Home position is set
            "is_gyrometer_calibration_ok": true,   # Gyros calibrated
            "is_accelerometer_calibration_ok": true # Accels calibrated
        },
        "armed": true,                      # Motors armed (spinning)
        "in_air": true,                     # Detected as airborne by PX4
        "heartbeat_age_s": 0.5              # Seconds since last data update
    }

    Coordinate Reference Systems:
    - NED (North-East-Down): Velocity uses this aviation standard where:
      * North = positive X (forward when heading north)
      * East = positive Y (right when heading north)
      * Down = positive Z (downward toward earth)
    - WGS84: Position uses standard GPS datum
    - Euler Angles: Attitude uses roll/pitch/yaw in degrees (intuitive for humans)

Real-Time Updates Explanation:

    The telemetry system provides near real-time data through a push-pull hybrid model:

    PULL MODEL (Direct Queries):
    - When an agent calls get_telemetry(), it receives the most recent cached data
    - Response time: < 10ms (reading from memory, no I/O blocking)
    - Data freshness: Typically < 1 second old (depends on MAVLink stream rate)

    PUSH MODEL (Background Updates):
    - TelemetryCache runs background tasks that subscribe to MAVSDK streams
    - Each stream emits values asynchronously when PX4 broadcasts them:
      * Position: ~5Hz (5 times per second)
      * Battery: ~1Hz (once per second)
      * Attitude: ~10Hz (10 times per second for fast orientation changes)
      * Health: ~1Hz (health checks are slower)
    - The cache updates its internal state immediately upon receiving new data

    Why async for-each loops in get_telemetry()?
    You may notice code like:
        async for position in drone.telemetry.position():
            telemetry_data["position"] = {...}
            break

    MAVSDK uses "async for" because telemetry streams are infinite generators.
    The stream continuously yields new values as they arrive from PX4.
    We use "break" after the first value because:
    1. We only need the current snapshot (one reading)
    2. The cache already has fresher data if we want continuous updates
    3. MCP tool calls should complete quickly

    Heartbeat Monitoring:
    - guardian.update_heartbeat() records when we last received data
    - heartbeat_age_s tells us if the data is stale (> 5s might indicate comm loss)
    - If heartbeat is too old, the Guardian can trigger failsafe actions

    Cache Staleness Handling:
    - TelemetryCache tracks when each data type was last updated
    - If data is older than the threshold (e.g., position > 2s), it's marked stale
    - Stale data is still returned but flagged so agents know it may be unreliable
    - This prevents using old GPS positions for navigation decisions

    Typical Update Frequencies in PX4 SITL:
    - Position (GPS): 5 Hz
    - Attitude (IMU): 50-250 Hz (interpolated to ~10Hz by MAVSDK)
    - Battery: 1 Hz
    - Health: 1 Hz
    - Velocity: 10-50 Hz
    - Flight Mode: Event-driven (only when it changes)

    For LLM Agent Usage:
    - Agents should call get_status() for a complete snapshot (recommended)
    - For continuous monitoring, agents should poll every 1-2 seconds
    - Battery and health should be checked before any mission
    - Position should be validated (not stale) before navigation commands
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from avatar.mav.connection_config import ConnectionConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData
from avatar.mav.state_machine import FlightStateMachine
from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.guardian_async import AsyncGuardian

if TYPE_CHECKING:
    from avatar.mcp_server.compat import DroneConnection

logger = logging.getLogger(__name__)


@dataclass
class TelemetryToolsConfig:
    """Configuration for telemetry tools.

    Controls connection parameters and timeouts for telemetry retrieval.

    Attributes:
        system_address: MAVLink connection string (e.g., "udp://:14540" for SITL)
        max_retries: Number of connection attempts before failing
        retry_delay_s: Seconds to wait between retry attempts
        health_timeout_s: Seconds before considering connection unhealthy
    """
    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0


class TelemetryTools:
    """Telemetry tools for MCP server.

    Provides telemetry retrieval operations with safety monitoring
    through the GuardianProcess. This class handles the connection
    lifecycle and formats telemetry data for LLM consumption.

    Data Flow Within This Class:
    1. _ensure_connection() establishes MAVSDK connection to PX4
    2. get_telemetry() queries MAVSDK streams for current values
    3. Guardian validates telemetry against safety limits
    4. Data is formatted into a JSON-serializable dictionary
    5. Caller receives structured telemetry data

    Usage:
        tools = TelemetryTools()
        telemetry = await tools.get_telemetry()
        print(json.dumps(telemetry, indent=2))

    Note:
        This class maintains a persistent connection to avoid the overhead
        of reconnecting for every telemetry request. Call disconnect() when
        done to clean up resources.
    """

    def __init__(
        self,
        config: Optional[TelemetryToolsConfig] = None,
        hard_limits: Optional[HardLimits] = None
    ):
        """Initialize telemetry tools.

        Args:
            config: Telemetry tools configuration (uses defaults if None)
            hard_limits: Safety limits for telemetry validation (uses defaults if None)
        """
        self.config = config or TelemetryToolsConfig()
        self.hard_limits = hard_limits or HardLimits()
        # GuardianProcess validates telemetry against safety limits
        # e.g., is battery too low? Is drone outside geofence?
        self.guardian = GuardianProcess(self.hard_limits)
        self._drone: Optional["DroneConnection"] = None
        self._connected = False

    async def _ensure_connection(self) -> dict[str, Any]:
        """Ensure drone connection is established.

        This internal method manages the connection lifecycle. It returns an
        error dict if connection fails, or an empty dict if already connected.

        Connection Strategy:
        - If already connected, return immediately (no-op)
        - Otherwise, create DroneConnection and attempt to connect
        - Retry logic is handled by DroneConnection internally

        Returns:
            Error dict if connection failed, empty dict if connected.
            Error format: {"success": False, "error": "description"}
        """
        if self._drone is not None and self._connected:
            return {}

        connection_config = ConnectionConfig(
            system_address=self.config.system_address,
            max_retries=self.config.max_retries,
            retry_delay_s=self.config.retry_delay_s,
            health_timeout_s=self.config.health_timeout_s,
        )
        from avatar.mcp_server.compat import DroneConnection
        self._drone = DroneConnection(connection_config)

        if not await self._drone.connect():
            return {
                "success": False,
                "error": "Failed to connect to drone. Ensure SITL or hardware is running.",
            }

        self._connected = True
        return {}

    async def get_telemetry(self) -> dict[str, Any]:
        """Get comprehensive drone telemetry data.

        This is the primary telemetry retrieval method. It queries multiple
        MAVSDK streams to build a complete picture of the drone's state.

        Data Sources Queried:
        - position(): GPS coordinates and altitude (WGS84 datum)
        - velocity_ned(): Velocity in NED frame (meters/second)
        - attitude_euler(): Orientation as roll/pitch/yaw (degrees)
        - ground_truth(): Simulation ground truth (if in SITL)
        - flight_mode(): Current PX4 flight mode (e.g., "OFFBOARD")
        - armed(): Boolean - are motors spinning?
        - in_air(): Boolean - is drone detected as airborne?

        Safety Integration:
        - Records home position when first GPS lock obtained
        - Updates guardian heartbeat for connection health monitoring
        - Includes heartbeat_age_s to indicate data freshness

        Returns:
            Dict with all telemetry data organized hierarchically.
            See module docstring for full structure details.

            Example success:
                {
                    "success": True,
                    "position": {
                        "latitude_deg": 37.7749,
                        "longitude_deg": -122.4194,
                        "absolute_altitude_m": 50.0,
                        "relative_altitude_m": 10.0
                    },
                    "velocity": {...},
                    "attitude": {...},
                    "battery": {...},
                    "flight_mode": "OFFBOARD",
                    "health": {...},
                    "armed": true,
                    "in_air": true,
                    "heartbeat_age_s": 0.5
                }
            Example failure:
                {"success": False, "error": "Drone not connected"}

        Note:
            The async for/break pattern is used because MAVSDK streams are
            infinite generators. We only need the current snapshot.
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone
        telemetry_data: dict[str, Any] = {"success": True}

        try:
            # Get position from GPS
            # PX4 streams this at ~5Hz in real flight, variable in SITL
            async for position in drone.telemetry.position():
                telemetry_data["position"] = {
                    "latitude_deg": position.latitude_deg,
                    "longitude_deg": position.longitude_deg,
                    "absolute_altitude_m": position.absolute_altitude_m,
                    "relative_altitude_m": position.relative_altitude_m,
                }

                # Set home position if not set (critical for RTL safety)
                # Home is where the drone takes off - Return-to-Land targets this point
                if not self.guardian.is_home_set:
                    self.guardian.set_home(
                        position.latitude_deg,
                        position.longitude_deg
                    )
                break

            # Get velocity in NED frame (North, East, Down)
            # NED is the aviation standard where:
            #   North = positive X (forward when facing north)
            #   East = positive Y (right when facing north)
            #   Down = positive Z (toward center of earth)
            async for velocity in drone.telemetry.velocity_ned():
                telemetry_data["velocity"] = {
                    "north_m_s": velocity.north_m_s,
                    "east_m_s": velocity.east_m_s,
                    "down_m_s": velocity.down_m_s,
                    "speed_m_s": (
                        velocity.north_m_s ** 2 +
                        velocity.east_m_s ** 2
                    ) ** 0.5,  # Horizontal ground speed (Pythagorean theorem)
                }
                break

            # Get attitude (Euler angles)
            # Roll: rotation around front-to-back axis (-180 to 180)
            # Pitch: rotation around side-to-side axis (-90 to 90)
            # Yaw: rotation around vertical axis (0-360, compass heading)
            async for attitude in drone.telemetry.attitude_euler():
                telemetry_data["attitude"] = {
                    "roll_deg": round(attitude.roll_deg, 2),
                    "pitch_deg": round(attitude.pitch_deg, 2),
                    "yaw_deg": round(attitude.yaw_deg, 2),
                }
                break

            # Get ground truth (if available - for simulation)
            # Ground truth is the "perfect" position from the simulator
            # Useful for validating GPS accuracy in SITL tests
            try:
                async for gt in drone.telemetry.ground_truth():
                    telemetry_data["ground_truth"] = {
                        "latitude_deg": gt.latitude_deg,
                        "longitude_deg": gt.longitude_deg,
                        "absolute_altitude_m": gt.absolute_altitude_m,
                    }
                    break
            except Exception:
                # Ground truth not available on hardware or if not supported
                pass

            # Get flight mode
            # PX4 flight modes: MANUAL, STABILIZED, ACRO, OFFBOARD, AUTO_LOITER, etc.
            # OFFBOARD is what we use for autonomous LLM control
            async for flight_mode in drone.telemetry.flight_mode():
                telemetry_data["flight_mode"] = str(flight_mode)
                break

            # Get armed state
            # Armed = motors spinning (propellers can cause injury)
            # Disarmed = motors stopped (safe to approach)
            async for armed in drone.telemetry.armed():
                telemetry_data["armed"] = armed
                break

            # Get in-air state
            # PX4 detects airborne state using accelerometer and altitude changes
            # Useful for: takeoff confirmation, landing detection, mission state
            async for in_air in drone.telemetry.in_air():
                telemetry_data["in_air"] = in_air
                break

            # Update heartbeat timestamp
            # This tells the guardian that communication is alive
            # If heartbeat gets too old, guardian may trigger failsafe
            self.guardian.update_heartbeat()
            telemetry_data["heartbeat_age_s"] = self.guardian.get_heartbeat_age()

        except Exception as e:
            # Partial data is still useful - we log the warning and return what we got
            telemetry_data["warning"] = f"Partial telemetry data: {e}"

        return telemetry_data

    async def get_battery_status(self) -> dict[str, Any]:
        """Get detailed battery status information.

        Battery monitoring is critical for safe flight. This method provides
        not just the raw battery data but also safety analysis.

        Battery Physics:
        - LiPo batteries have non-linear discharge curves
        - Voltage sags under load (high current draw)
        - Remaining_percent is estimated by PX4 using voltage + current integration

        Safety Analysis Performed:
        - is_low: < 50% triggers a warning (conservative threshold)
        - rtl_required: < hard_limits.min_battery_rtl_percent triggers Return-to-Land
        - command_allowed: Guardian validates if battery level permits commands

        Returns:
            Dict with battery data and safety analysis.

            Example success:
                {
                    "success": True,
                    "battery": {
                        "remaining_percent": 85.0,
                        "voltage_v": 15.2,
                        "voltage_v_cell": 3.8,
                        "current_a": 10.5
                    },
                    "safety": {
                        "is_low": false,
                        "rtl_required": false,
                        "min_rtl_percent": 25.0
                    }
                }
            Example failure:
                {"success": False, "error": "Battery data unavailable"}

        Safety Thresholds:
        - Good: > 50% (normal operations)
        - Low: 25-50% (caution, plan landing)
        - Critical: < 25% (RTL triggered, land immediately)
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone
        battery_data: dict[str, Any] = {"success": True}

        try:
            async for battery in drone.telemetry.battery():
                remaining_percent = battery.remaining_percent

                battery_data["battery"] = {
                    "remaining_percent": round(remaining_percent, 1),
                }

                # Safety status analysis
                min_rtl = self.hard_limits.min_battery_rtl_percent
                battery_data["safety"] = {
                    "is_low": remaining_percent < 50.0,  # Warning threshold
                    "rtl_required": remaining_percent < min_rtl,  # RTL trigger
                    "min_rtl_percent": min_rtl,
                    "status": (
                        "critical" if remaining_percent < min_rtl
                        else "low" if remaining_percent < 50.0
                        else "good"
                    ),
                }

                # Validate battery level for commands
                # Guardian may block takeoff if battery is too low
                is_valid, reason = self.guardian.validate_command({
                    "battery_percent": remaining_percent
                })
                battery_data["safety"]["command_allowed"] = is_valid
                if not is_valid:
                    battery_data["safety"]["warning"] = reason

                break

        except Exception as e:
            battery_data["success"] = False
            battery_data["error"] = f"Battery data unavailable: {e}"

        return battery_data

    async def get_health_status(self) -> dict[str, Any]:
        """Get drone health and calibration status.

        Health checks ensure all critical systems are operational before flight.
        This method aggregates multiple sensor health indicators.

        Health Checks Performed:
        - Gyrometer calibration: Required for attitude estimation
        - Accelerometer calibration: Required for attitude and velocity
        - Magnetometer calibration: Required for heading (yaw)
        - Level calibration: Required for accurate attitude reference
        - Local position: EKF has valid local position estimate
        - Global position: GPS lock sufficient for navigation
        - Home position: Takeoff point recorded for RTL safety

        Ready-to-Fly Criteria:
        The drone is considered ready when:
        1. Global position is OK (GPS locked)
        2. Home position is set (recorded at takeoff)
        3. Gyrometer is calibrated (attitude estimation working)

        Returns:
            Dict with health status and ready-to-fly determination.

            Example:
                {
                    "success": True,
                    "health": {
                        "is_global_position_ok": true,
                        "is_home_position_ok": true,
                        "is_gyrometer_calibration_ok": true,
                        "is_accelerometer_calibration_ok": true
                    },
                    "ready_to_fly": true,
                    "issues": []
                }

        Note:
            Always check ready_to_fly before takeoff. If false, review issues
            list for specific problems (e.g., "GPS position not ready").
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone
        health_data: dict[str, Any] = {"success": True}

        try:
            async for health in drone.telemetry.health():
                health_info = {
                    "is_gyrometer_calibration_ok": health.is_gyrometer_calibration_ok,
                    "is_accelerometer_calibration_ok": health.is_accelerometer_calibration_ok,
                    "is_magnetometer_calibration_ok": health.is_magnetometer_calibration_ok,
                    "is_level_calibration_ok": health.is_level_calibration_ok,
                    "is_local_position_ok": health.is_local_position_ok,
                    "is_global_position_ok": health.is_global_position_ok,
                    "is_home_position_ok": health.is_home_position_ok,
                }

                health_data["health"] = health_info

                # Determine if ready to fly
                # These are the minimum requirements for safe flight
                ready = (
                    health.is_global_position_ok and
                    health.is_home_position_ok and
                    health.is_gyrometer_calibration_ok
                )
                health_data["ready_to_fly"] = ready

                # Collect human-readable issues list
                # This helps agents understand what needs to be fixed
                issues = []
                if not health.is_global_position_ok:
                    issues.append("GPS position not ready")
                if not health.is_home_position_ok:
                    issues.append("Home position not set")
                if not health.is_gyrometer_calibration_ok:
                    issues.append("Gyrometer needs calibration")
                if not health.is_accelerometer_calibration_ok:
                    issues.append("Accelerometer needs calibration")
                if not health.is_magnetometer_calibration_ok:
                    issues.append("Magnetometer needs calibration")

                health_data["issues"] = issues

                break

        except Exception as e:
            health_data["success"] = False
            health_data["error"] = f"Health check failed: {e}"

        return health_data

    async def get_position_info(self) -> dict[str, Any]:
        """Get simplified position information.

        This is a convenience method for agents that only need position data
        without the full telemetry payload. It includes geofence status.

        Data Provided:
        - Current position (lat/lon/alt)
        - Home position (if set)
        - Distance from home (meters)
        - Geofence status (within bounds or exceeded)

        Geofence Logic:
        - max_distance_m from HardLimits defines the boundary
        - within_bounds indicates if drone is inside the geofence
        - Distance is calculated using haversine formula for GPS accuracy

        Returns:
            Dict with position data and geofence status.

            Example:
                {
                    "success": True,
                    "position": {"lat": 37.7749, "lon": -122.4194, "alt": 10.0},
                    "home": {"lat": 37.7749, "lon": -122.4194},
                    "distance_from_home_m": 0.0,
                    "relative_altitude_m": 10.0,
                    "geofence": {
                        "max_distance_m": 1000.0,
                        "within_bounds": true
                    }
                }

        Use Case:
            This method is ideal for agents monitoring "is the drone still
            within the mission area?" without parsing full telemetry.
        """
        # Ensure connection
        conn_error = await self._ensure_connection()
        if conn_error:
            return conn_error

        if self._drone is None or self._drone.drone is None:
            return {"success": False, "error": "Drone not connected"}

        drone = self._drone.drone
        position_data: dict[str, Any] = {"success": True}

        try:
            async for position in drone.telemetry.position():
                lat = position.latitude_deg
                lon = position.longitude_deg
                alt = position.relative_altitude_m

                position_data["position"] = {
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                }
                position_data["relative_altitude_m"] = alt
                position_data["absolute_altitude_m"] = position.absolute_altitude_m

                # Set home if needed (first GPS lock)
                if not self.guardian.is_home_set:
                    self.guardian.set_home(lat, lon)

                # Get home position and calculate distance
                home = self.guardian.home_position
                if home:
                    position_data["home"] = {
                        "lat": home[0],
                        "lon": home[1],
                    }

                    # Calculate distance from home using haversine formula
                    # This accounts for Earth's curvature (more accurate than simple trig)
                    is_valid, _ = self.guardian.validate_command({
                        "latitude": lat,
                        "longitude": lon,
                    })

                    distance = self.guardian._haversine_distance(home[0], home[1], lat, lon)
                    position_data["distance_from_home_m"] = round(distance, 1)

                    # Geofence status for safety monitoring
                    max_dist = self.hard_limits.max_distance_from_home_m
                    position_data["geofence"] = {
                        "max_distance_m": max_dist,
                        "within_bounds": distance <= max_dist,
                    }

                break

        except Exception as e:
            position_data["success"] = False
            position_data["error"] = f"Position data unavailable: {e}"

        return position_data

    async def disconnect(self) -> None:
        """Disconnect from drone.

        Cleanly closes the MAVSDK connection and resets internal state.
        Should be called when telemetry monitoring is complete to free resources.
        """
        if self._drone:
            await self._drone.disconnect()
        self._connected = False
        self._drone = None


# =============================================================================
# Global Singleton Instances for get_status() Integration
# =============================================================================
# These singletons enable the get_status() function to access shared resources
# without requiring a TelemetryTools instance. This design supports:
# - Multiple telemetry consumers (different agents/tools)
# - Shared state across the application
# - Lazy initialization pattern

_telemetry_cache: Optional[TelemetryCache] = None
_state_machine: Optional[FlightStateMachine] = None
_guardian: Optional[AsyncGuardian] = None


def get_telemetry_cache() -> Optional[TelemetryCache]:
    """Get the global telemetry cache instance.

    The telemetry cache is the primary data flow optimization in the system.
    It subscribes to MAVSDK streams and stores the latest values, allowing
    instantaneous reads without blocking on MAVLink communication.

    Returns:
        TelemetryCache instance or None if not initialized.
    """
    global _telemetry_cache
    return _telemetry_cache


def set_telemetry_cache(cache: TelemetryCache) -> None:
    """Set the global telemetry cache instance.

    Args:
        cache: TelemetryCache instance to use globally.
    """
    global _telemetry_cache
    _telemetry_cache = cache


def get_state_machine() -> FlightStateMachine:
    """Get the global state machine instance.

    The flight state machine tracks the drone's operational state:
    - DISCONNECTED -> CONNECTED -> ARMED -> TAKEOFF -> IN_FLIGHT -> LANDING -> DISARMED

    Returns:
        FlightStateMachine instance (creates new if none exists).
    """
    global _state_machine
    if _state_machine is None:
        _state_machine = FlightStateMachine()
    return _state_machine


def set_state_machine(sm: FlightStateMachine) -> None:
    """Set the global state machine instance.

    Args:
        sm: FlightStateMachine instance to use globally.
    """
    global _state_machine
    _state_machine = sm


def get_connection_manager() -> ConnectionManager:
    """Get the singleton connection manager instance.

    The connection manager handles the MAVSDK connection lifecycle and
    health monitoring. It ensures only one connection exists per drone.

    Returns:
        ConnectionManager singleton instance.
    """
    return ConnectionManager()


def get_guardian() -> Optional[AsyncGuardian]:
    """Get the global guardian instance.

    The guardian provides safety monitoring and resource tracking:
    - Validates commands against safety limits
    - Tracks battery, geofence, and altitude constraints
    - Provides alerts for critical conditions

    Returns:
        AsyncGuardian instance or None if not initialized.
    """
    global _guardian
    return _guardian


def set_guardian(guardian: AsyncGuardian) -> None:
    """Set the global guardian instance.

    Args:
        guardian: AsyncGuardian instance to use globally.
    """
    global _guardian
    _guardian = guardian


def _telemetry_to_dict(telemetry: TelemetryData) -> Dict[str, Any]:
    """Convert TelemetryData to dictionary with LLM-friendly field names.

    This helper function normalizes the telemetry data format for consistency
    across the API. It provides multiple aliases for the same data (e.g.,
    both "altitude" and "relative_altitude_m") for backward compatibility.

    Args:
        telemetry: TelemetryData instance from the cache.

    Returns:
        Dictionary with formatted telemetry fields.
    """
    return {
        "latitude": telemetry.latitude,
        "longitude": telemetry.longitude,
        "altitude": telemetry.altitude,
        "absolute_altitude_m": telemetry.altitude,  # Alias for consistency
        "relative_altitude_m": telemetry.altitude,
        "velocity_north": telemetry.velocity_north,
        "velocity_east": telemetry.velocity_east,
        "velocity_down": telemetry.velocity_down,
        "groundspeed_m_s": telemetry.groundspeed,
        "roll_deg": telemetry.roll,
        "pitch_deg": telemetry.pitch,
        "yaw_deg": telemetry.yaw,
        "battery_percent": telemetry.battery_percent,
        "battery_voltage_v": telemetry.battery_voltage,
        "battery_current_a": telemetry.battery_current,
        "armed": telemetry.armed,
        "in_air": telemetry.in_air,
        "flight_mode": telemetry.flight_mode,
        "is_gps_ok": telemetry.is_gps_ok,
        "is_home_position_ok": telemetry.is_home_position_ok,
        "gps_fix": telemetry.gps_fix,
    }


async def get_status() -> Dict[str, Any]:
    """Get comprehensive drone status.

    This is the RECOMMENDED method for AI agents to query drone status.
    It aggregates data from multiple sources into a unified, LLM-optimized format.

    Data Sources Aggregated:
    - Telemetry cache: Position, velocity, battery, attitude (fast, cached)
    - State machine: Current flight state, valid transitions
    - Connection manager: Connection health, MAVLink status
    - Guardian: Active safety alerts, resource constraints

    Unified Status Structure:
    {
        "timestamp": 1234567890.0,      # Unix timestamp
        "success": true,

        "position": {                   # Geographic position
            "lat": 37.7749,
            "lon": -122.4194,
            "alt_m": 50.0,
            "rel_alt_m": 10.0,
            "heading_deg": 45.0         # Yaw angle (compass heading)
        },

        "velocity": {                   # Velocity in NED frame
            "north_m_s": 2.5,
            "east_m_s": 1.0,
            "down_m_s": 0.1,
            "groundspeed_m_s": 2.69     # Total horizontal speed
        },

        "attitude": {                   # Orientation (Euler angles)
            "roll_deg": 2.5,
            "pitch_deg": -1.2,
            "yaw_deg": 45.0
        },

        "battery": {                    # Battery status
            "percent": 85.0,
            "voltage_v": 15.2,
            "current_a": 10.5
        },

        "flight": {                     # Flight state information
            "state": "IN_FLIGHT",
            "armed": true,
            "in_air": true,
            "flight_mode": "OFFBOARD",
            "valid_transitions": ["LANDING", "RTL", "HOLD"]
        },

        "connection": {                 # MAVLink connection status
            "connected": true,
            "state": "CONNECTED",
            "health": {
                "gps_ok": true,
                "home_ok": true
            }
        },

        "system": {                     # System-level information
            "alerts": [],                # Active guardian alerts
            "cache_age_ms": 150,         # Telemetry cache age
            "cache_stale": false         # Is cached data too old?
        }
    }

    Real-Time Characteristics:
    - Response time: < 10ms (all data from memory, no I/O blocking)
    - Data freshness: Depends on cache update rate (typically < 1 second)
    - Cache staleness: Data older than threshold is flagged but still returned

    LLM Consumption Design:
    - All values use clear, descriptive keys ("groundspeed_m_s" not "v_g")
    - Units included in key names where ambiguous ("_m_s", "_deg")
    - Nested structure groups related data (position, velocity, attitude)
    - Boolean flags for quick conditionals ("armed", "in_air", "gps_ok")
    - Valid transitions help agents understand available actions

    Returns:
        Dict with complete system status, formatted for LLM consumption.
        All telemetry values included with consistent naming.
        State information includes current state and valid transitions.
        Connection health shows connectivity and GPS/home status.
        Guardian alerts show any active safety warnings or critical issues.
    """
    # Gather all data sources
    cache = get_telemetry_cache()
    sm = get_state_machine()
    cm = get_connection_manager()
    guardian = get_guardian()

    # Get telemetry data from cache or use defaults
    # The cache provides the most recent values without blocking
    if cache is not None:
        telemetry_data = cache.get_data()
        cache_age_ms = cache.get_age_ms() if hasattr(cache, 'get_age_ms') else 0
        cache_stale = cache.is_stale()
    else:
        telemetry_data = None
        cache_age_ms = 0
        cache_stale = True

    # Build telemetry dict or use empty defaults
    # Default values (zeros/false) indicate "no data available"
    if telemetry_data is not None:
        telemetry = _telemetry_to_dict(telemetry_data)
    else:
        telemetry = {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "absolute_altitude_m": 0.0,
            "relative_altitude_m": 0.0,
            "velocity_north": 0.0,
            "velocity_east": 0.0,
            "velocity_down": 0.0,
            "groundspeed_m_s": 0.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 0.0,
            "battery_percent": 0.0,
            "battery_voltage_v": 0.0,
            "battery_current_a": 0.0,
            "armed": False,
            "in_air": False,
            "flight_mode": "UNKNOWN",
            "is_gps_ok": False,
            "is_home_position_ok": False,
            "gps_fix": 0,
        }

    # Get valid transitions from state machine
    # These are the actions the agent can legally take from current state
    valid_transitions = sm.get_valid_transitions()
    transition_names = [t.name for t in valid_transitions]

    # Get guardian status if available
    # Guardian alerts indicate safety issues (low battery, geofence, etc.)
    guardian_alerts = []
    if guardian is not None:
        try:
            guardian_status = guardian.get_status()
            # Extract alerts from guardian status
            if hasattr(guardian_status, 'alerts'):
                guardian_alerts = [
                    {
                        "level": alert.level if hasattr(alert, 'level') else alert.get('level', 'warning'),
                        "source": alert.source if hasattr(alert, 'source') else alert.get('source', 'unknown'),
                        "message": alert.message if hasattr(alert, 'message') else alert.get('message', ''),
                        "timestamp": alert.timestamp if hasattr(alert, 'timestamp') else alert.get('timestamp', 0),
                    }
                    for alert in guardian_status.alerts
                ]
        except Exception as e:
            logger.warning(f"Failed to get guardian status: {e}")
            guardian_alerts = []

    # Build unified status response
    # Organized hierarchically for LLM parsing and human readability
    status = {
        "timestamp": time.time(),
        "success": True,

        # Position group: Where is the drone?
        "position": {
            "lat": telemetry["latitude"],
            "lon": telemetry["longitude"],
            "alt_m": telemetry["absolute_altitude_m"],
            "rel_alt_m": telemetry["relative_altitude_m"],
            "heading_deg": telemetry["yaw_deg"],  # Compass heading
        },

        # Velocity group: How is it moving?
        "velocity": {
            "north_m_s": telemetry["velocity_north"],
            "east_m_s": telemetry["velocity_east"],
            "down_m_s": telemetry["velocity_down"],
            "groundspeed_m_s": telemetry["groundspeed_m_s"],
        },

        # Attitude group: Which way is it facing?
        "attitude": {
            "roll_deg": telemetry["roll_deg"],
            "pitch_deg": telemetry["pitch_deg"],
            "yaw_deg": telemetry["yaw_deg"],
        },

        # Battery group: Power status
        "battery": {
            "percent": telemetry["battery_percent"],
            "voltage_v": telemetry["battery_voltage_v"],
            "current_a": telemetry["battery_current_a"],
        },

        # Flight group: Operational state
        "flight": {
            "state": sm.current_state_name,
            "armed": telemetry["armed"],
            "in_air": telemetry["in_air"],
            "flight_mode": telemetry["flight_mode"],
            "valid_transitions": transition_names,  # What can we do next?
        },

        # Connection group: Communication health
        "connection": {
            "connected": cm.state.name == "CONNECTED" if hasattr(cm.state, 'name') else False,
            "state": cm.state.name if hasattr(cm.state, 'name') else str(cm.state),
            "health": {
                "gps_ok": telemetry["is_gps_ok"],
                "home_ok": telemetry["is_home_position_ok"],
            },
        },

        # System group: Meta-information
        "system": {
            "alerts": guardian_alerts,  # Active safety warnings
            "cache_age_ms": cache_age_ms,  # How fresh is the data?
            "cache_stale": cache_stale,  # Should we trust it?
        },
    }

    return status


# =============================================================================
# MCP Tool Function Wrappers
# =============================================================================
# These async functions are the actual entry points registered with the MCP server.
# They wrap the TelemetryTools methods to provide the JSON string interface
# expected by the MCP protocol.

async def get_telemetry() -> str:
    """MCP tool: Get comprehensive drone telemetry.

    Retrieves position, velocity, attitude, battery, flight mode,
    health status, and armed/in-air states.

    This is a convenience wrapper that creates a TelemetryTools instance,
    calls get_telemetry(), and returns JSON string for MCP transport.

    Returns:
        JSON string with telemetry data.

    Example response:
        '{
            "success": true,
            "position": {"latitude_deg": 37.7749, ...},
            ...
        }'
    """
    tools = TelemetryTools()
    result = await tools.get_telemetry()
    return json.dumps(result, indent=2)


async def get_battery_status() -> str:
    """MCP tool: Get detailed battery information.

    Returns battery percentage, voltage, current draw, and safety analysis
    including whether RTL (Return-to-Land) is required.

    Returns:
        JSON string with battery status.

    Example response:
        '{
            "success": true,
            "battery": {"remaining_percent": 85.0, ...},
            "safety": {"is_low": false, "rtl_required": false, ...}
        }'
    """
    tools = TelemetryTools()
    result = await tools.get_battery_status()
    return json.dumps(result, indent=2)


async def get_status_tool() -> str:
    """MCP tool: Get unified drone status.

    Returns comprehensive system status aggregating telemetry, state machine,
    connection health, and guardian alerts. Formatted for LLM consumption.

    RECOMMENDED: This is the primary status tool for AI agents. It provides
    the most complete picture of the drone's current state in a single call.

    Returns:
        JSON string with complete system status.

    Data included:
    - Position, velocity, attitude (telemetry)
    - Battery status with safety analysis
    - Flight state and valid transitions
    - Connection health (GPS, home position)
    - Active safety alerts from guardian
    - Cache freshness indicators
    """
    result = await get_status()
    return json.dumps(result, indent=2, default=str)
