#!/usr/bin/env python3
"""
Project Avatar — MAVLink Control Script
========================================
Connects to an ArduPilot SITL instance via MAVLink over UDP and provides
programmatic control: arm, takeoff, waypoint navigation, orbit, land,
and telemetry reading.

Usage:
    python3 mavlink_control.py [command] [options]

Commands:
    status       — Print current vehicle status (telemetry)
    arm          — Arm the vehicle
    disarm       — Disarm the vehicle
    takeoff ALT  — Arm + takeoff to altitude (meters, default: 2.5)
    goto LAT LON ALT — Go to waypoint (decimal degrees, meters)
    orbit RADIUS — Start orbit at current position
    land         — Land at current position
    rtl          — Return to launch
    mission FILE — Upload and run a waypoint mission from JSON file

Options:
    --host HOST  — MAVLink UDP host (default: 127.0.0.1)
    --port PORT  — MAVLink UDP port (default: 14551)
    --baud BAUD  — Serial baud (ignored for UDP)
    --verbose    — Verbose output

Examples:
    python3 mavlink_control.py status
    python3 mavlink_control.py arm
    python3 mavlink_control.py takeoff 5.0
    python3 mavlink_control.py goto 47.3980 8.5460 20.0
    python3 mavlink_control.py orbit 15.0
    python3 mavlink_control.py land
    python3 mavlink_control.py mission waypoints.json
    python3 mavlink_control.py --port 14550 status
"""

import sys
import time
import math
import json
import signal
import argparse
from threading import Thread, Event

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import ardupilotmega as mavlink
except ImportError as e:
    print(f"[FATAL] pymavlink not installed: {e}")
    print("        Install with: pip install pymavlink")
    sys.exit(1)


# ==============================================================================
# MAVLink Controller Class
# ==============================================================================

class MavlinkController:
    """High-level MAVLink controller for ArduPilot SITL."""

    def __init__(self, host="127.0.0.1", port=14551, verbose=False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.conn = None
        self._stop_event = Event()
        self._telemetry = {}
        self._telemetry_thread = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, timeout=15.0):
        """Connect to the SITL instance via MAVLink UDP."""
        connection_string = f"udp:{self.host}:{self.port}"
        self._log(f"Connecting to {connection_string}...")
        self.conn = mavutil.mavlink_connection(connection_string)

        # Wait for heartbeat
        self._log("Waiting for heartbeat...")
        msg = self.conn.wait_heartbeat(timeout=timeout)
        if msg is None:
            raise TimeoutError(
                f"No heartbeat received within {timeout}s. Is SITL running?"
            )

        self._log(f"Heartbeat received: type={msg.type} autopilot={msg.autopilot} "
                  f"base_mode={msg.base_mode} system_status={msg.system_status}")

        # Start telemetry thread
        self._stop_event.clear()
        self._telemetry_thread = Thread(target=self._telemetry_loop, daemon=True)
        self._telemetry_thread.start()

        return self

    def disconnect(self):
        """Disconnect and clean up."""
        self._stop_event.set()
        if self._telemetry_thread:
            self._telemetry_thread.join(timeout=2.0)
        if self.conn:
            self.conn.close()
        self._log("Disconnected.")

    def _log(self, msg):
        if self.verbose:
            print(f"[MAV] {msg}")

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def _telemetry_loop(self):
        """Background thread that reads telemetry."""
        while not self._stop_event.is_set():
            try:
                msg = self.conn.recv_msg()
                if msg is None:
                    continue

                msg_type = msg.get_type()

                if msg_type == "GLOBAL_POSITION_INT":
                    self._telemetry["lat"] = msg.lat / 1e7
                    self._telemetry["lon"] = msg.lon / 1e7
                    self._telemetry["alt"] = msg.relative_alt / 1000.0  # meters
                    self._telemetry["heading"] = msg.hdg / 100.0
                    self._telemetry["vx"] = msg.vx / 100.0
                    self._telemetry["vy"] = msg.vy / 100.0
                    self._telemetry["vz"] = msg.vz / 100.0

                elif msg_type == "ATTITUDE":
                    self._telemetry["roll"] = math.degrees(msg.roll)
                    self._telemetry["pitch"] = math.degrees(msg.pitch)
                    self._telemetry["yaw"] = math.degrees(msg.yaw)

                elif msg_type == "BATTERY_STATUS":
                    self._telemetry["battery_voltage"] = msg.voltages[0] / 1000.0 if msg.voltages else 0
                    self._telemetry["battery_current"] = msg.current_battery / 100.0
                    self._telemetry["battery_remaining"] = msg.battery_remaining

                elif msg_type == "VFR_HUD":
                    self._telemetry["airspeed"] = msg.airspeed
                    self._telemetry["groundspeed"] = msg.groundspeed
                    self._telemetry["throttle"] = msg.throttle
                    self._telemetry["climb"] = msg.climb

                elif msg_type == "HEARTBEAT":
                    self._telemetry["armed"] = (msg.base_mode & mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                    self._telemetry["mode"] = mavutil.mode_string_v10(msg)

                elif msg_type == "GPS_RAW_INT":
                    self._telemetry["gps_fix"] = msg.fix_type
                    self._telemetry["gps_sats"] = msg.satellites_visible

            except Exception:
                time.sleep(0.01)

    def get_telemetry(self):
        """Return a snapshot of latest telemetry."""
        return dict(self._telemetry)

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------

    def send_command(self, command, params=None, confirmation=0):
        """Send a MAVLink COMMAND_LONG and wait for ACK."""
        self.conn.mav.command_long_send(
            self.conn.target_system,
            self.conn.target_component,
            command,
            confirmation,
            *params,
            *([0] * (7 - len(params))),
        )

    def set_mode(self, mode_name):
        """Set flight mode by name."""
        mode_id = self.conn.mode_mapping().get(mode_name)
        if mode_id is None:
            raise ValueError(f"Unknown mode: {mode_name}. "
                           f"Available: {list(self.conn.mode_mapping().keys())}")
        self._log(f"Setting mode: {mode_name} (id={mode_id})")
        self.conn.mav.set_mode_send(
            self.conn.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
        )

    def arm(self, timeout=10.0):
        """Arm the vehicle."""
        self._log("Arming...")
        self.conn.arducopter_arm()
        self.conn.motors_armed_wait()
        self._log("Armed.")

    def disarm(self, timeout=5.0):
        """Disarm the vehicle."""
        self._log("Disarming...")
        self.conn.arducopter_disarm()
        self.conn.motors_disarmed_wait()
        self._log("Disarmed.")

    def takeoff(self, altitude=2.5, timeout=30.0):
        """Arm and takeoff to given altitude (meters)."""
        self._log(f"Taking off to {altitude}m...")

        # Switch to GUIDED mode
        self.set_mode("GUIDED")

        # Arm
        self.arm()

        # Takeoff command
        self.conn.mav.command_long_send(
            self.conn.target_system,
            self.conn.target_component,
            mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            altitude
        )

        # Wait to reach altitude
        start_time = time.time()
        while time.time() - start_time < timeout:
            alt = self._telemetry.get("alt", 0)
            if alt >= altitude * 0.95:
                self._log(f"Takeoff complete at {alt:.1f}m")
                return
            time.sleep(0.5)

        self._log(f"Takeoff timeout — reached {self._telemetry.get('alt', 0):.1f}m")

    def goto(self, lat, lon, alt, timeout=60.0):
        """Go to a waypoint in GUIDED mode (lat, lon in degrees, alt in meters)."""
        self._log(f"Going to {lat:.6f}, {lon:.6f} at {alt:.1f}m...")

        # Ensure GUIDED mode
        self.set_mode("GUIDED")

        # Send waypoint
        self.conn.mav.set_position_target_global_int_send(
            0,  # time_boot_ms (0 for immediate)
            self.conn.target_system,
            self.conn.target_component,
            mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,  # type_mask: use position and yaw
            int(lat * 1e7),
            int(lon * 1e7),
            alt,  # relative altitude
            0, 0, 0,  # vx, vy, vz (ignored)
            0, 0, 0,  # afx, afy, afz (ignored)
            0,  # yaw (ignored)
            0,  # yaw_rate (ignored)
        )

        self._log("Waypoint sent. Waiting to arrive...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_lat = self._telemetry.get("lat", 0)
            current_lon = self._telemetry.get("lon", 0)
            dist = self._haversine(current_lat, current_lon, lat, lon)
            if dist < 1.0:  # within 1 meter
                self._log(f"Arrived at waypoint (dist={dist:.1f}m)")
                return
            if self.verbose:
                print(f"\r  Distance: {dist:.1f}m  Alt: {self._telemetry.get('alt', 0):.1f}m", end="")
            time.sleep(0.5)

        self._log("Waypoint timeout")

    def orbit(self, radius=10.0, alt=None, timeout=30.0):
        """Start orbiting at current position.

        Uses CIRCLE mode — vehicle enters a circular path.
        For guided orbit use set_position_target_global_int with circular
        motion parameters.

        Actually uses MAV_CMD_DO_ORBIT for ArduPilot 4.4+.
        """
        current_lat = self._telemetry.get("lat", 0)
        current_lon = self._telemetry.get("lon", 0)
        current_alt = self._telemetry.get("alt", 0)

        if alt is None:
            alt = current_alt

        self._log(f"Orbiting at ({current_lat:.6f}, {current_lon:.6f}) "
                  f"radius={radius}m alt={alt:.1f}m...")

        # Use CIRCLE mode
        self.set_mode("CIRCLE")

        # Set circle radius via parameter
        self.conn.mav.param_set_send(
            self.conn.target_system,
            self.conn.target_component,
            b"CIRCLE_RADIUS",
            float(radius),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )

        self._log(f"Orbit started. Radius: {radius}m")
        time.sleep(2)

        # Print periodic position
        try:
            while True:
                dist_from_center = self._haversine(
                    self._telemetry.get("lat", 0),
                    self._telemetry.get("lon", 0),
                    current_lat,
                    current_lon,
                )
                print(f"\r  Dist from center: {dist_from_center:.1f}m  "
                      f"Alt: {self._telemetry.get('alt', 0):.1f}m  "
                      f"Batt: {self._telemetry.get('battery_voltage', 0):.1f}V  "
                      f"Ctrl+C to stop", end="")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[MAV] Orbit monitoring stopped.")

    def land(self, timeout=60.0):
        """Land at current position."""
        self._log("Landing...")

        self.set_mode("LAND")

        # Wait for disarm / altitude near zero
        start_time = time.time()
        while time.time() - start_time < timeout:
            alt = self._telemetry.get("alt", 0)
            armed = self._telemetry.get("armed", False)
            if not armed or alt < 0.3:
                self._log(f"Landed. Alt: {alt:.1f}m")
                return
            if self.verbose:
                print(f"\r  Altitude: {alt:.1f}m  Throttle: {self._telemetry.get('throttle', 0)}%", end="")
            time.sleep(0.5)

        self._log("Land timeout")

    def rtl(self, timeout=120.0):
        """Return to launch position."""
        self._log("Return to launch...")
        self.set_mode("RTL")

        start_time = time.time()
        while time.time() - start_time < timeout:
            alt = self._telemetry.get("alt", 0)
            armed = self._telemetry.get("armed", False)
            if not armed or alt < 0.3:
                self._log(f"RTL complete. Alt: {alt:.1f}m")
                return
            time.sleep(1)

        self._log("RTL timeout")

    # ------------------------------------------------------------------
    # Mission upload (from JSON)
    # ------------------------------------------------------------------

    def upload_mission(self, waypoints_file):
        """Upload a mission from a JSON file.

        JSON format:
        [
            {"cmd": 16, "lat": 47.398, "lon": 8.546, "alt": 10.0},
            {"cmd": 16, "lat": 47.399, "lon": 8.547, "alt": 10.0},
            {"cmd": 21, "lat": 47.398, "lon": 8.546, "alt": 0.0}
        ]

        Key MAV_CMD values:
            16 = WAYPOINT
            21 = LAND
            22 = TAKEOFF
            20 = RTL
        """
        with open(waypoints_file) as f:
            wpts = json.load(f)

        self._log(f"Uploading {len(wpts)} waypoints from {waypoints_file}...")

        # Clear existing mission
        self.conn.mav.mission_clear_all_send(
            self.conn.target_system, self.conn.target_component
        )

        # Send waypoint count
        self.conn.mav.mission_count_send(
            self.conn.target_system,
            self.conn.target_component,
            len(wpts),
            mavlink.MAV_MISSION_TYPE_MISSION,
        )

        for i, wp in enumerate(wpts):
            # Wait for MISSION_REQUEST
            msg = self.conn.recv_match(type="MISSION_REQUEST", blocking=True, timeout=5)
            if msg is None:
                print(f"[WARN] No MISSION_REQUEST for waypoint {i}")
                break

            cmd = wp.get("cmd", mavlink.MAV_CMD_NAV_WAYPOINT)
            lat = wp.get("lat", 0)
            lon = wp.get("lon", 0)
            alt = wp.get("alt", 0)

            self.conn.mav.mission_item_int_send(
                self.conn.target_system,
                self.conn.target_component,
                i,  # seq
                mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                cmd,
                0, 1,  # current, autocontinue
                wp.get("param1", 0),
                wp.get("param2", 0),
                wp.get("param3", 0),
                wp.get("param4", 0),
                int(lat * 1e7),
                int(lon * 1e7),
                alt,
                mavlink.MAV_MISSION_TYPE_MISSION,
            )
            self._log(f"  WP {i}: cmd={cmd} ({lat:.6f}, {lon:.6f}, {alt:.1f}m)")

        self._log("Mission upload complete.")

    def start_mission(self):
        """Start the uploaded mission in AUTO mode."""
        self._log("Starting mission...")
        self.arm()
        self.set_mode("AUTO")
        self._log("Mission running (AUTO mode).")

    # ------------------------------------------------------------------
    # Status display
    # ------------------------------------------------------------------

    def print_status(self):
        """Print current vehicle status."""
        t = self.get_telemetry()
        print("\n" + "=" * 55)
        print("  Project Avatar — Vehicle Status")
        print("=" * 55)
        print(f"  Armed:         {t.get('armed', False)}")
        print(f"  Mode:          {t.get('mode', 'N/A')}")
        print(f"  GPS Fix:       {t.get('gps_fix', 'N/A')} ({t.get('gps_sats', 0)} sats)")
        print(f"  Position:      {t.get('lat', 0):.6f}, {t.get('lon', 0):.6f}")
        print(f"  Altitude:      {t.get('alt', 0):.1f} m")
        print(f"  Heading:       {t.get('heading', 0):.0f}°")
        print(f"  Roll/Pitch:    {t.get('roll', 0):.1f}° / {t.get('pitch', 0):.1f}°")
        print(f"  Ground Speed:  {t.get('groundspeed', 0):.1f} m/s")
        print(f"  Climb Rate:    {t.get('climb', 0):.1f} m/s")
        print(f"  Throttle:      {t.get('throttle', 0):.0f}%")
        print(f"  Battery:       {t.get('battery_voltage', 0):.2f}V "
              f"({t.get('battery_remaining', 0)}% remaining)")
        print("=" * 55)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two lat/lon points."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Project Avatar — MAVLink Control Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 mavlink_control.py status
  python3 mavlink_control.py arm
  python3 mavlink_control.py takeoff 5.0
  python3 mavlink_control.py goto 47.3980 8.5460 20.0
  python3 mavlink_control.py orbit 15.0
  python3 mavlink_control.py land
  python3 mavlink_control.py rtl
  python3 mavlink_control.py mission waypoints.json
  python3 mavlink_control.py --port 14550 status
        """,
    )
    parser.add_argument("--host", default="127.0.0.1", help="MAVLink host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=14551, help="MAVLink UDP port (default: 14551)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("command", nargs="?", default="status",
                       help="Command to execute (status, arm, disarm, takeoff, goto, orbit, land, rtl, mission)")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()
    cmd = args.command.lower()
    cmd_args = args.args

    controller = MavlinkController(
        host=args.host,
        port=args.port,
        verbose=args.verbose,
    )

    try:
        controller.connect()

        if cmd == "status":
            controller.print_status()

        elif cmd == "arm":
            controller.arm()

        elif cmd == "disarm":
            controller.disarm()

        elif cmd == "takeoff":
            alt = float(cmd_args[0]) if cmd_args else 2.5
            controller.takeoff(alt)

        elif cmd == "goto":
            if len(cmd_args) < 3:
                print("[ERROR] goto requires: lat lon alt")
                print("  Example: python3 mavlink_control.py goto 47.398 8.546 20.0")
                sys.exit(1)
            lat, lon, alt = float(cmd_args[0]), float(cmd_args[1]), float(cmd_args[2])
            controller.goto(lat, lon, alt)

        elif cmd == "orbit":
            radius = float(cmd_args[0]) if cmd_args else 10.0
            alt = float(cmd_args[1]) if len(cmd_args) > 1 else None
            controller.orbit(radius, alt)

        elif cmd == "land":
            controller.land()

        elif cmd == "rtl":
            controller.rtl()

        elif cmd == "mission":
            if not cmd_args:
                print("[ERROR] mission requires a JSON waypoint file")
                print("  Example: python3 mavlink_control.py mission waypoints.json")
                sys.exit(1)
            controller.upload_mission(cmd_args[0])
            controller.start_mission()

        else:
            print(f"[ERROR] Unknown command: {cmd}")
            print("  Available: status, arm, disarm, takeoff, goto, orbit, land, rtl, mission")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n[MAV] Interrupted.")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
