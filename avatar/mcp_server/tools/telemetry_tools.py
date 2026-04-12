"""Telemetry MCP tools.

Provides drone telemetry tools for MCP-compatible AI agents.

Tools:
    - get_telemetry: Get comprehensive drone telemetry data
    - get_battery_status: Get detailed battery information
    - get_status: Get unified system status for LLM consumption
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from avatar.mav.connection import DroneConnection, ConnectionConfig
from avatar.mav.guardian import GuardianProcess, HardLimits
from avatar.mav.telemetry_cache import TelemetryCache, TelemetryData
from avatar.mav.state_machine import FlightStateMachine
from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.guardian_async import AsyncGuardian

logger = logging.getLogger(__name__)


@dataclass
class TelemetryToolsConfig:
    """Configuration for telemetry tools."""
    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0


class TelemetryTools:
    """Telemetry tools for MCP server.

    Provides telemetry retrieval operations with safety monitoring
    through the GuardianProcess.

    Usage:
        tools = TelemetryTools()
        telemetry = await tools.get_telemetry()
        print(json.dumps(telemetry, indent=2))
    """

    def __init__(
        self,
        config: Optional[TelemetryToolsConfig] = None,
        hard_limits: Optional[HardLimits] = None
    ):
        """Initialize telemetry tools.

        Args:
            config: Telemetry tools configuration.
            hard_limits: Safety limits for telemetry validation.
        """
        self.config = config or TelemetryToolsConfig()
        self.hard_limits = hard_limits or HardLimits()
        self.guardian = GuardianProcess(self.hard_limits)
        self._drone: Optional[DroneConnection] = None
        self._connected = False

    async def _ensure_connection(self) -> dict[str, Any]:
        """Ensure drone connection is established.

        Returns:
            Error dict if connection failed, empty dict if connected.
        """
        if self._drone is not None and self._connected:
            return {}

        connection_config = ConnectionConfig(
            system_address=self.config.system_address,
            max_retries=self.config.max_retries,
            retry_delay_s=self.config.retry_delay_s,
            health_timeout_s=self.config.health_timeout_s,
        )
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

        Retrieves position, velocity, attitude, battery, flight mode,
        health status, and armed/in-air states.

        Returns:
            Dict with all telemetry data.
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
            # Get position
            async for position in drone.telemetry.position():
                telemetry_data["position"] = {
                    "latitude_deg": position.latitude_deg,
                    "longitude_deg": position.longitude_deg,
                    "absolute_altitude_m": position.absolute_altitude_m,
                    "relative_altitude_m": position.relative_altitude_m,
                }

                # Set home position if not set
                if not self.guardian.is_home_set:
                    self.guardian.set_home(
                        position.latitude_deg,
                        position.longitude_deg
                    )
                break

            # Get velocity (NED frame: North, East, Down)
            async for velocity in drone.telemetry.velocity_ned():
                telemetry_data["velocity"] = {
                    "north_m_s": velocity.north_m_s,
                    "east_m_s": velocity.east_m_s,
                    "down_m_s": velocity.down_m_s,
                    "speed_m_s": (
                        velocity.north_m_s ** 2 +
                        velocity.east_m_s ** 2
                    ) ** 0.5,  # Horizontal speed
                }
                break

            # Get attitude (Euler angles)
            async for attitude in drone.telemetry.attitude_euler():
                telemetry_data["attitude"] = {
                    "roll_deg": round(attitude.roll_deg, 2),
                    "pitch_deg": round(attitude.pitch_deg, 2),
                    "yaw_deg": round(attitude.yaw_deg, 2),
                }
                break

            # Get ground truth (if available - for simulation)
            try:
                async for gt in drone.telemetry.ground_truth():
                    telemetry_data["ground_truth"] = {
                        "latitude_deg": gt.latitude_deg,
                        "longitude_deg": gt.longitude_deg,
                        "absolute_altitude_m": gt.absolute_altitude_m,
                    }
                    break
            except Exception:
                # Ground truth not available (hardware or not supported)
                pass

            # Get flight mode
            async for flight_mode in drone.telemetry.flight_mode():
                telemetry_data["flight_mode"] = str(flight_mode)
                break

            # Get armed state
            async for armed in drone.telemetry.armed():
                telemetry_data["armed"] = armed
                break

            # Get in-air state
            async for in_air in drone.telemetry.in_air():
                telemetry_data["in_air"] = in_air
                break

            # Update heartbeat
            self.guardian.update_heartbeat()
            telemetry_data["heartbeat_age_s"] = self.guardian.get_heartbeat_age()

        except Exception as e:
            telemetry_data["warning"] = f"Partial telemetry data: {e}"

        return telemetry_data

    async def get_battery_status(self) -> dict[str, Any]:
        """Get detailed battery status information.

        Returns battery percentage, voltage, and safety warnings.

        Returns:
            Dict with battery data.
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

                # Safety status
                min_rtl = self.hard_limits.min_battery_rtl_percent
                battery_data["safety"] = {
                    "is_low": remaining_percent < 50.0,
                    "rtl_required": remaining_percent < min_rtl,
                    "min_rtl_percent": min_rtl,
                    "status": (
                        "critical" if remaining_percent < min_rtl
                        else "low" if remaining_percent < 50.0
                        else "good"
                    ),
                }

                # Validate battery level for commands
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

        Returns health check results for GPS, sensors, and home position.

        Returns:
            Dict with health status.
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
                ready = (
                    health.is_global_position_ok and
                    health.is_home_position_ok and
                    health.is_gyrometer_calibration_ok
                )
                health_data["ready_to_fly"] = ready

                # Collect issues
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

        Returns current position, altitude, and distance from home.

        Returns:
            Dict with position data.
            Example:
                {
                    "success": True,
                    "position": {"lat": 37.7749, "lon": -122.4194, "alt": 10.0},
                    "home": {"lat": 37.7749, "lon": -122.4194},
                    "distance_from_home_m": 0.0,
                    "relative_altitude_m": 10.0
                }
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

                # Set home if needed
                if not self.guardian.is_home_set:
                    self.guardian.set_home(lat, lon)

                # Get home position
                home = self.guardian.home_position
                if home:
                    position_data["home"] = {
                        "lat": home[0],
                        "lon": home[1],
                    }

                    # Calculate distance from home
                    is_valid, _ = self.guardian.validate_command({
                        "latitude": lat,
                        "longitude": lon,
                    })

                    # Calculate distance using guardian's haversine method
                    distance = self.guardian._haversine_distance(home[0], home[1], lat, lon)
                    position_data["distance_from_home_m"] = round(distance, 1)

                    # Geofence status
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
        """Disconnect from drone."""
        if self._drone:
            await self._drone.disconnect()
        self._connected = False
        self._drone = None


# Global singleton instances for get_status integration
_telemetry_cache: Optional[TelemetryCache] = None
_state_machine: Optional[FlightStateMachine] = None
_guardian: Optional[AsyncGuardian] = None


def get_telemetry_cache() -> Optional[TelemetryCache]:
    """Get the global telemetry cache instance.

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

    Returns:
        ConnectionManager singleton instance.
    """
    return ConnectionManager()


def get_guardian() -> Optional[AsyncGuardian]:
    """Get the global guardian instance.

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

    Args:
        telemetry: TelemetryData instance.

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

    Aggregates data from:
    - Telemetry cache (position, velocity, battery, attitude)
    - State machine (current state, valid transitions)
    - Connection manager (connection health)
    - Guardian (active alerts, resource status)

    Returns:
        Dict with complete system status, formatted for LLM consumption.
        All telemetry values are included with consistent naming.
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
    if cache is not None:
        telemetry_data = cache.get_data()
        cache_age_ms = cache.get_age_ms() if hasattr(cache, 'get_age_ms') else 0
        cache_stale = cache.is_stale()
    else:
        telemetry_data = None
        cache_age_ms = 0
        cache_stale = True

    # Build telemetry dict or use empty defaults
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
    valid_transitions = sm.get_valid_transitions()
    transition_names = [t.name for t in valid_transitions]

    # Get guardian status if available
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
    status = {
        "timestamp": time.time(),
        "success": True,

        # Position
        "position": {
            "lat": telemetry["latitude"],
            "lon": telemetry["longitude"],
            "alt_m": telemetry["absolute_altitude_m"],
            "rel_alt_m": telemetry["relative_altitude_m"],
            "heading_deg": telemetry["yaw_deg"],
        },

        # Velocity
        "velocity": {
            "north_m_s": telemetry["velocity_north"],
            "east_m_s": telemetry["velocity_east"],
            "down_m_s": telemetry["velocity_down"],
            "groundspeed_m_s": telemetry["groundspeed_m_s"],
        },

        # Attitude
        "attitude": {
            "roll_deg": telemetry["roll_deg"],
            "pitch_deg": telemetry["pitch_deg"],
            "yaw_deg": telemetry["yaw_deg"],
        },

        # Battery
        "battery": {
            "percent": telemetry["battery_percent"],
            "voltage_v": telemetry["battery_voltage_v"],
            "current_a": telemetry["battery_current_a"],
        },

        # Flight state
        "flight": {
            "state": sm.current_state_name,
            "armed": telemetry["armed"],
            "in_air": telemetry["in_air"],
            "flight_mode": telemetry["flight_mode"],
            "valid_transitions": transition_names,
        },

        # Connection
        "connection": {
            "connected": cm.state.name == "CONNECTED" if hasattr(cm.state, 'name') else False,
            "state": cm.state.name if hasattr(cm.state, 'name') else str(cm.state),
            "health": {
                "gps_ok": telemetry["is_gps_ok"],
                "home_ok": telemetry["is_home_position_ok"],
            },
        },

        # System
        "system": {
            "alerts": guardian_alerts,
            "cache_age_ms": cache_age_ms,
            "cache_stale": cache_stale,
        },
    }

    return status


# Tool function wrappers for MCP registration
async def get_telemetry() -> str:
    """MCP tool: Get comprehensive drone telemetry.

    Retrieves position, velocity, attitude, battery, flight mode,
    health status, and armed/in-air states.

    Returns:
        JSON string with telemetry data.
    """
    tools = TelemetryTools()
    result = await tools.get_telemetry()
    return json.dumps(result, indent=2)


async def get_battery_status() -> str:
    """MCP tool: Get detailed battery information.

    Returns battery percentage, voltage, and safety warnings.

    Returns:
        JSON string with battery status.
    """
    tools = TelemetryTools()
    result = await tools.get_battery_status()
    return json.dumps(result, indent=2)


async def get_status_tool() -> str:
    """MCP tool: Get unified drone status.

    Returns comprehensive system status aggregating telemetry, state machine,
    connection health, and guardian alerts. Formatted for LLM consumption.

    Returns:
        JSON string with complete system status.
    """
    result = await get_status()
    return json.dumps(result, indent=2, default=str)
