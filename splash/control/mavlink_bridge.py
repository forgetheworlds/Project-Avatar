"""
mavlink_bridge.py — MAVLink connection manager for Splash MCP server.

Handles:
  • Connection to SITL (sim mode) via UDP or real hardware via ESP32 WiFi bridge
  • Heartbeat monitoring
  • Telemetry collection (background thread)
  • Command sending with ACK
  • Mode switching, arming, navigation, orbit, land, RTL

Mode selection:
  SIM_MODE=true   → UDP to localhost SITL
  SIM_MODE=false  → TCP/UDP to ESP32 bridge

Project Avatar — Splash water gun drone MCP tool server.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import ardupilotmega as mavlink
    HAS_MAVLINK = True
except ImportError:
    HAS_MAVLINK = False
    mavutil = None  # type: ignore
    mavlink = None  # type: ignore

logger = logging.getLogger("splash.mavlink")


# ==============================================================================
# Telemetry snapshot
# ==============================================================================

@dataclass
class Telemetry:
    """Immutable telemetry snapshot."""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0                 # relative altitude, meters
    heading: float = 0.0             # degrees
    vx: float = 0.0                  # m/s
    vy: float = 0.0
    vz: float = 0.0
    roll: float = 0.0                # degrees
    pitch: float = 0.0
    yaw: float = 0.0
    battery_voltage: float = 0.0     # V
    battery_current: float = 0.0     # A
    battery_remaining: int = 0       # %
    airspeed: float = 0.0            # m/s
    groundspeed: float = 0.0
    throttle: float = 0.0            # %
    climb: float = 0.0               # m/s
    armed: bool = False
    mode: str = "UNKNOWN"
    gps_fix: int = 0
    gps_sats: int = 0
    heartbeat_age_s: float = 999.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": {"lat": round(self.lat, 7), "lon": round(self.lon, 7)},
            "altitude_m": round(self.alt, 2),
            "attitude": {
                "roll": round(self.roll, 1),
                "pitch": round(self.pitch, 1),
                "yaw": round(self.yaw, 1),
                "heading": round(self.heading, 1),
            },
            "velocity": {
                "vx": round(self.vx, 2),
                "vy": round(self.vy, 2),
                "vz": round(self.vz, 2),
                "groundspeed": round(self.groundspeed, 2),
                "airspeed": round(self.airspeed, 2),
                "climb": round(self.climb, 2),
            },
            "battery": {
                "voltage": round(self.battery_voltage, 2),
                "current": round(self.battery_current, 2),
                "remaining_pct": self.battery_remaining,
            },
            "state": {
                "armed": self.armed,
                "mode": self.mode,
                "gps_fix": self.gps_fix,
                "gps_sats": self.gps_sats,
            },
            "link": {
                "heartbeat_age_s": round(self.heartbeat_age_s, 1),
            },
        }


# ==============================================================================
# MAVLink Bridge
# ==============================================================================

class MavlinkBridge:
    """Manages MAVLink connection, telemetry, and command execution.

    Usage:
        bridge = MavlinkBridge(sim_mode=True)
        bridge.connect()
        telemetry = bridge.get_telemetry()
        bridge.arm()
        bridge.takeoff(5.0)
        bridge.goto(47.398, 8.546, 20.0)
        bridge.orbit(47.398, 8.546, 15.0, 20.0)
        bridge.land()
        bridge.disconnect()
    """

    # MAVLink command constants
    MAV_CMD_NAV_TAKEOFF = 22
    MAV_CMD_DO_ORBIT = 34
    MAV_CMD_DO_SET_MODE = 176

    # MAV_FRAME
    MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

    def __init__(
        self,
        sim_mode: bool = True,
        sim_host: str = "127.0.0.1",
        sim_port: int = 14551,
        real_host: str = "192.168.4.1",
        real_port: int = 14550,
        heartbeat_timeout: float = 5.0,
    ) -> None:
        if not HAS_MAVLINK:
            raise ImportError(
                "pymavlink is required. Install with: pip install pymavlink"
            )

        self.sim_mode = sim_mode
        self.sim_host = sim_host
        self.sim_port = sim_port
        self.real_host = real_host
        self.real_port = real_port
        self.heartbeat_timeout = heartbeat_timeout

        self.conn: Optional[Any] = None  # mavutil.mavlink_connection
        self._stop_event = threading.Event()
        self._telemetry_thread: Optional[threading.Thread] = None
        self._telemetry_lock = threading.Lock()
        self._latest_telemetry = Telemetry()
        self._last_heartbeat_time = 0.0

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 15.0) -> MavlinkBridge:
        """Connect to MAVLink (UDP for SITL, TCP for ESP32 bridge)."""
        if self.sim_mode:
            addr = f"udp:{self.sim_host}:{self.sim_port}"
        else:
            addr = f"tcp:{self.real_host}:{self.real_port}"

        logger.info(f"Connecting MAVLink → {addr} ({'SIM' if self.sim_mode else 'REAL'})")
        self.conn = mavutil.mavlink_connection(addr)

        # Wait for heartbeat
        logger.info("Waiting for heartbeat...")
        msg = self.conn.wait_heartbeat(timeout=timeout)
        if msg is None:
            raise TimeoutError(
                f"No heartbeat within {timeout}s. "
                f"Is {'SITL running' if self.sim_mode else 'ESP32 bridge connected'}?"
            )

        self._last_heartbeat_time = time.time()
        logger.info(
            f"Heartbeat OK: type={msg.type} autopilot={msg.autopilot} "
            f"base_mode={msg.base_mode}"
        )

        # Start telemetry thread
        self._stop_event.clear()
        self._telemetry_thread = threading.Thread(
            target=self._telemetry_loop, daemon=True, name="mav-telem"
        )
        self._telemetry_thread.start()

        return self

    def disconnect(self) -> None:
        """Close connection and stop telemetry thread."""
        self._stop_event.set()
        if self._telemetry_thread:
            self._telemetry_thread.join(timeout=3.0)
        if self.conn:
            self.conn.close()
        logger.info("MAVLink disconnected.")

    @property
    def connected(self) -> bool:
        return self.conn is not None and not self._stop_event.is_set()

    @property
    def heartbeat_ok(self) -> bool:
        age = time.time() - self._last_heartbeat_time
        return age < self.heartbeat_timeout

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def _telemetry_loop(self) -> None:
        """Background thread: read MAVLink messages, update telemetry."""
        while not self._stop_event.is_set():
            try:
                msg = self.conn.recv_msg()
                if msg is None:
                    continue

                msg_type = msg.get_type()
                now = time.time()

                with self._telemetry_lock:
                    t = self._latest_telemetry

                    if msg_type == "GLOBAL_POSITION_INT":
                        t.lat = msg.lat / 1e7
                        t.lon = msg.lon / 1e7
                        t.alt = msg.relative_alt / 1000.0
                        t.heading = msg.hdg / 100.0
                        t.vx = msg.vx / 100.0
                        t.vy = msg.vy / 100.0
                        t.vz = msg.vz / 100.0
                        t.timestamp = now

                    elif msg_type == "ATTITUDE":
                        t.roll = math.degrees(msg.roll)
                        t.pitch = math.degrees(msg.pitch)
                        t.yaw = math.degrees(msg.yaw)

                    elif msg_type == "BATTERY_STATUS":
                        if msg.voltages:
                            t.battery_voltage = msg.voltages[0] / 1000.0
                        t.battery_current = msg.current_battery / 100.0
                        t.battery_remaining = msg.battery_remaining

                    elif msg_type == "VFR_HUD":
                        t.airspeed = msg.airspeed
                        t.groundspeed = msg.groundspeed
                        t.throttle = msg.throttle
                        t.climb = msg.climb

                    elif msg_type == "HEARTBEAT":
                        self._last_heartbeat_time = now
                        t.heartbeat_age_s = 0
                        t.armed = (msg.base_mode & mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                        t.mode = mavutil.mode_string_v10(msg)

                    elif msg_type == "GPS_RAW_INT":
                        t.gps_fix = msg.fix_type
                        t.gps_sats = msg.satellites_visible

            except Exception as e:
                logger.debug(f"Telemetry read error: {e}")
                time.sleep(0.01)

    def get_telemetry(self) -> Telemetry:
        """Return a copy of the latest telemetry snapshot."""
        with self._telemetry_lock:
            t = self._latest_telemetry
            # Compute heartbeat age
            age = time.time() - self._last_heartbeat_time
            return Telemetry(
                lat=t.lat, lon=t.lon, alt=t.alt, heading=t.heading,
                vx=t.vx, vy=t.vy, vz=t.vz,
                roll=t.roll, pitch=t.pitch, yaw=t.yaw,
                battery_voltage=t.battery_voltage,
                battery_current=t.battery_current,
                battery_remaining=t.battery_remaining,
                airspeed=t.airspeed, groundspeed=t.groundspeed,
                throttle=t.throttle, climb=t.climb,
                armed=t.armed, mode=t.mode,
                gps_fix=t.gps_fix, gps_sats=t.gps_sats,
                heartbeat_age_s=age,
                timestamp=t.timestamp,
            )

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------

    def send_command(self, command: int, params: list[float] = None,
                     confirmation: int = 0) -> None:
        """Send a MAVLink COMMAND_LONG."""
        if params is None:
            params = []
        # Pad to 7 params
        padded = list(params) + [0.0] * (7 - len(params))
        self.conn.mav.command_long_send(
            self.conn.target_system,
            self.conn.target_component,
            command,
            confirmation,
            *padded,
        )

    def set_mode(self, mode_name: str) -> None:
        """Set flight mode by name (e.g., GUIDED, CIRCLE, LAND, RTL, STABILIZE)."""
        mode_id = self.conn.mode_mapping().get(mode_name)
        if mode_id is None:
            available = list(self.conn.mode_mapping().keys())
            raise ValueError(
                f"Unknown mode: '{mode_name}'. Available: {available}"
            )
        logger.info(f"Setting mode: {mode_name} (id={mode_id})")
        self.conn.mav.set_mode_send(
            self.conn.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
        )
        # Wait for mode to take effect
        time.sleep(0.5)

    # ------------------------------------------------------------------
    # Drone control commands
    # ------------------------------------------------------------------

    def arm(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Arm the motors. Returns status dict."""
        logger.info("Arming motors...")
        self.conn.arducopter_arm()
        self.conn.motors_armed_wait()
        logger.info("Armed OK.")
        return {"success": True, "message": "Drone armed", "state": "ARMED"}

    def disarm(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Immediate disarm. Returns status dict."""
        logger.info("Disarming motors...")
        self.conn.arducopter_disarm()
        self.conn.motors_disarmed_wait()
        logger.info("Disarmed OK.")
        return {"success": True, "message": "Drone disarmed", "state": "DISARMED"}

    def takeoff(self, altitude_m: float, timeout: float = 30.0) -> Dict[str, Any]:
        """Arm and take off to altitude (meters). Returns status dict."""
        logger.info(f"Takeoff → {altitude_m}m")
        self.set_mode("GUIDED")
        self.arm()

        # Send takeoff command
        self.conn.mav.command_long_send(
            self.conn.target_system,
            self.conn.target_component,
            mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            altitude_m,
        )

        # Wait for altitude
        start = time.time()
        while time.time() - start < timeout:
            t = self.get_telemetry()
            if t.alt >= altitude_m * 0.95:
                logger.info(f"Takeoff complete at {t.alt:.1f}m")
                return {
                    "success": True,
                    "message": f"Takeoff complete at {t.alt:.1f}m",
                    "altitude_m": round(t.alt, 2),
                    "target_altitude_m": altitude_m,
                }
            time.sleep(0.5)

        t = self.get_telemetry()
        logger.warning(f"Takeoff timeout at {t.alt:.1f}m")
        return {
            "success": True,
            "message": f"Takeoff timeout — reached {t.alt:.1f}m (target: {altitude_m}m)",
            "altitude_m": round(t.alt, 2),
            "target_altitude_m": altitude_m,
        }

    def goto(self, lat: float, lon: float, alt: float,
             timeout: float = 60.0) -> Dict[str, Any]:
        """Fly to GPS coordinates in GUIDED mode. Returns status dict."""
        logger.info(f"GOTO → ({lat:.6f}, {lon:.6f}, {alt:.1f}m)")
        self.set_mode("GUIDED")

        # Send position target
        self.conn.mav.set_position_target_global_int_send(
            0,  # time_boot_ms (0 = immediate)
            self.conn.target_system,
            self.conn.target_component,
            mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,  # use position + yaw
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,  # vx, vy, vz (ignored)
            0, 0, 0,  # afx, afy, afz (ignored)
            0,  # yaw (ignored)
            0,  # yaw_rate (ignored)
        )

        # Wait to arrive
        start = time.time()
        while time.time() - start < timeout:
            t = self.get_telemetry()
            dist = self._haversine(t.lat, t.lon, lat, lon)
            if dist < 1.0:  # within 1 meter
                logger.info(f"GOTO arrived (dist={dist:.1f}m)")
                return {
                    "success": True,
                    "message": f"Arrived at destination ({dist:.1f}m away)",
                    "position": {"lat": lat, "lon": lon, "alt": alt},
                    "remaining_distance_m": round(dist, 2),
                }
            time.sleep(0.5)

        t = self.get_telemetry()
        dist = self._haversine(t.lat, t.lon, lat, lon)
        return {
            "success": False,
            "message": f"GOTO timeout — {dist:.1f}m remaining",
            "remaining_distance_m": round(dist, 2),
        }

    def orbit(self, center_lat: float, center_lon: float, radius_m: float,
              altitude_m: float) -> Dict[str, Any]:
        """Start orbiting a GPS point.

        Uses ArduPilot CIRCLE mode with CIRCLE_RADIUS parameter.
        First flies to the orbit center, then engages circle mode.
        """
        logger.info(f"ORBIT → center=({center_lat:.6f}, {center_lon:.6f}) "
                     f"radius={radius_m}m alt={altitude_m}m")

        # Fly to the center point first
        self.set_mode("GUIDED")
        self.goto(center_lat, center_lon, altitude_m)

        # Set circle radius via parameter
        self.conn.mav.param_set_send(
            self.conn.target_system,
            self.conn.target_component,
            b"CIRCLE_RADIUS",
            float(radius_m),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )

        # Engage CIRCLE mode
        time.sleep(0.5)
        self.set_mode("CIRCLE")

        logger.info(f"Orbit engaged — radius={radius_m}m")
        return {
            "success": True,
            "message": f"Orbiting at radius {radius_m}m, altitude {altitude_m}m",
            "center": {"lat": center_lat, "lon": center_lon},
            "radius_m": radius_m,
            "altitude_m": altitude_m,
        }

    def land(self, timeout: float = 60.0) -> Dict[str, Any]:
        """Land at current position using LAND mode."""
        logger.info("Landing...")
        self.set_mode("LAND")

        start = time.time()
        while time.time() - start < timeout:
            t = self.get_telemetry()
            if not t.armed or t.alt < 0.3:
                logger.info(f"Landed — alt={t.alt:.1f}m")
                return {
                    "success": True,
                    "message": f"Landed (altitude {t.alt:.2f}m)",
                    "altitude_m": round(t.alt, 2),
                }
            time.sleep(0.5)

        t = self.get_telemetry()
        return {
            "success": False,
            "message": f"Land timeout — altitude {t.alt:.2f}m",
            "altitude_m": round(t.alt, 2),
        }

    def rtb(self, timeout: float = 120.0) -> Dict[str, Any]:
        """Return to home using RTL mode. Returns status dict."""
        logger.info("Return to home (RTL)...")
        self.set_mode("RTL")

        start = time.time()
        while time.time() - start < timeout:
            t = self.get_telemetry()
            if not t.armed or t.alt < 0.3:
                logger.info(f"RTL complete — alt={t.alt:.1f}m")
                return {
                    "success": True,
                    "message": f"Returned home (altitude {t.alt:.2f}m)",
                    "altitude_m": round(t.alt, 2),
                }
            time.sleep(1.0)

        t = self.get_telemetry()
        return {
            "success": False,
            "message": f"RTL timeout — altitude {t.alt:.2f}m",
            "altitude_m": round(t.alt, 2),
        }

    # ------------------------------------------------------------------
    # Sensor helpers
    # ------------------------------------------------------------------

    def get_camera_frame_info(self) -> Dict[str, Any]:
        """Return placeholder camera frame info.

        In production, this reads from the CV pipeline's shared memory
        or a ZeroMQ/Redis pub-sub channel. Currently returns telemetry-
        based contextual info for the LLM.
        """
        t = self.get_telemetry()
        return {
            "available": False,
            "message": "Camera feed not yet connected. Use real hardware or "
                       "configure CV pipeline for frame streaming.",
            "drone_heading": round(t.heading, 1),
            "drone_altitude_m": round(t.alt, 2),
            "mode": t.mode,
        }

    # ------------------------------------------------------------------
    # Engage / protect mode helpers
    # ------------------------------------------------------------------

    def engage_target_mode(self) -> None:
        """Set up GUIDED mode for precision targeting.

        In production, this would also activate the CV pipeline
        and enable the pan-tilt servo turret.
        """
        self.set_mode("GUIDED")
        logger.info("Target engagement mode active.")

    def protect_orbit_mode(self, center_lat: float, center_lon: float,
                           radius_m: float, altitude_m: float) -> None:
        """Enter protect mode: orbit + detect + fire.

        Combines orbit with target engagement readiness.
        """
        self.orbit(center_lat, center_lon, radius_m, altitude_m)
        logger.info("Protect mode active — orbiting + scanning for targets.")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distance in meters between two GPS coordinates."""
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ------------------------------------------------------------------
    # Connection health
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Quick health check for the LLM to verify connection."""
        t = self.get_telemetry()
        return {
            "connected": self.connected,
            "heartbeat_ok": self.heartbeat_ok,
            "heartbeat_age_s": round(t.heartbeat_age_s, 1),
            "mode": t.mode,
            "armed": t.armed,
            "gps_fix": t.gps_fix,
            "gps_sats": t.gps_sats,
            "battery_pct": t.battery_remaining,
            "sim_mode": self.sim_mode,
        }
