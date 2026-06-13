#!/usr/bin/env python3
"""
setup_sitl_sim.py — ArduPilot SITL simulation setup for Splash testing.

Sets up a SITL simulation environment for testing Splash MCP server,
protection mode, and CV pipeline without real hardware.

Usage:
  python setup_sitl_sim.py              # Setup only
  python setup_sitl_sim.py --run        # Setup + run SITL
  python setup_sitl_sim.py --kill       # Stop SITL

Requirements:
  - ardupilot_gazebo or sitl binaries
  - pymavlink
  - mavproxy (optional, for telemetry routing)

Architecture:
  SITL (UDP:14550)  →  MCP Server (UDP:14551 for SIM mode)
  MCP Server        →  CV Pipeline (shared memory / ZMQ)
  MCP Server        →  QGroundControl (UDP:14550)

Project Avatar — Splash water gun drone.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("sitl_setup")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME_DIR = Path.home()
AVATAR_DIR = HOME_DIR / "Downloads" / "Project-Avatar"
SPLASH_DIR = AVATAR_DIR / "splash"
SITL_DIR = HOME_DIR / "ardupilot" / "Tools" / "autotest"

# SITL binary paths
SITL_BIN = shutil.which("sim_vehicle.py") or str(SITL_DIR / "sim_vehicle.py")
ARDUPILOT_DIR = HOME_DIR / "ardupilot"

# Default SITL parameters for Splash testing
SITL_PARAMS = {
    "FRAME_CLASS": "1",        # Quad frame
    "FRAME_TYPE": "1",         # X frame
    "SERIAL4_PROTOCOL": "2",   # MAVLink2 on UART4 (for MCP server)
    "SERIAL4_BAUD": "115",     # 115200
    "SERIAL5_PROTOCOL": "-1",  # Disable (no RC in sim)
    "FENCE_ENABLE": "0",       # Disable fence for testing
    "CIRCLE_RADIUS": "1000",   # cm (10m)
    "CIRCLE_RATE": "20",       # deg/s (20s per orbit)
    "WPNAV_ACCEL": "500",      # cm/s²
    "BATT_LOW_VOLT": "13.6",   # 3.4V/cell for 4S
    "BATT_CRT_VOLT": "12.8",   # 3.2V/cell
    "FS_GCS_ENABLE": "1",      # RTL on GCS loss
    "FS_GCS_TIMEOUT": "10",    # 10s timeout
    "ARMING_CHECK": "1",       # All checks
    "SCR_ENABLE": "1",         # Lua scripting
}

# ---------------------------------------------------------------------------
# SITL Management
# ---------------------------------------------------------------------------

class SITLManager:
    """Manages ArduPilot SITL simulation process."""

    def __init__(self, workdir: Path = SPLASH_DIR):
        self.workdir = workdir
        self.process: subprocess.Popen | None = None
        self._started = False

    def is_installed(self) -> bool:
        """Check if ArduPilot SITL is available."""
        if os.path.exists(SITL_BIN):
            return True
        # Check for ardupilot directory
        if ARDUPILOT_DIR.exists():
            return True
        return False

    def setup_mavlink_params(self, param_file: str = "splash_sitl.params") -> Path:
        """Write Splash-specific ArduPilot parameters to file."""
        filepath = self.workdir / param_file
        lines = [f"{k}={v}\n" for k, v in SITL_PARAMS.items()]
        filepath.write_text("".join(lines))
        logger.info(f"SITL params written: {filepath} ({len(lines)} params)")
        return filepath

    def run(self, instance: int = 0, timeout: float = 30.0) -> None:
        """Start SITL simulation.

        Uses sim_vehicle.py with:
          - Quad copter
          - No RC (SERIAL5 disabled)
          - Splash parameters loaded
          - Mavproxy disabled (we manage MAVLink via MCP server)
        """
        if self._started:
            logger.warning("SITL already running")
            return

        if not self.is_installed():
            logger.error(
                "ArduPilot SITL not found. Install with:\n"
                "  git clone https://github.com/ArduPilot/ardupilot.git\n"
                "  cd ardupilot && ./Tools/environment_install/install-prereqs-ubuntu.sh\n"
                "  ./waf configure --board sitl\n"
                "  ./waf copter"
            )
            # Instead, offer a Python-only simulation fallback
            logger.info("Starting Python-only SIM mode (no SITL binary required)")
            self._start_python_sim(instance)
            return

        param_file = self.setup_mavlink_params()

        cmd = [
            sys.executable, SITL_BIN,
            "-v", "ArduCopter",
            "--model", "quad",
            "--no-mavproxy",
            "--out", f"127.0.0.1:{14550 + instance}",
            "--instance", str(instance),
            "--custom-location", "47.397742,8.545594,0,0",  # Switzerland testing
        ]

        logger.info(f"Starting SITL: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            cwd=str(ARDUPILOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._started = True

        # Wait for heartbeat
        start = time.time()
        timeout_s = 30
        while time.time() - start < timeout_s:
            line = self.process.stdout.readline() if self.process.stdout else ""
            if "Ready to fly" in line or "Arming motors" in line:
                logger.info(f"SITL ready ({time.time() - start:.1f}s)")
                break
            time.sleep(0.1)
        else:
            logger.warning(f"SITL may not be ready after {timeout_s}s")

        logger.info(f"SITL running on UDP:1455{instance}")

        # Apply params after startup
        time.sleep(2)
        self._apply_params(param_file, instance)

    def _start_python_sim(self, instance: int) -> None:
        """Fallback: Python-only SIM mode using pymavlink."""
        logger.info("Python SIM mode: MCP server can run with SIM_MODE=true")
        logger.info("No actual SITL binary needed. MCP will simulate responses.")

    def _apply_params(self, param_file: Path, instance: int) -> None:
        """Apply parameters via MAVProxy param set commands."""
        try:
            from pymavlink import mavutil
            conn = mavutil.mavlink_connection(
                f"udp:127.0.0.1:{14550 + instance}",
                source_system=2,
            )
            conn.wait_heartbeat(timeout=10)

            for key, value in SITL_PARAMS.items():
                conn.mav.param_set_send(
                    conn.target_system,
                    conn.target_component,
                    key.encode(),
                    float(value),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
                )
                time.sleep(0.05)
            logger.info(f"SITL params applied ({len(SITL_PARAMS)} params)")
        except Exception as e:
            logger.warning(f"Could not apply params via MAVLink: {e}")

    def stop(self) -> None:
        """Stop SITL gracefully."""
        if self.process:
            logger.info("Stopping SITL...")
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
                logger.info("SITL stopped")
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("SITL killed (timeout)")
            self.process = None
        self._started = False

    def health_check(self) -> bool:
        """Quick check if SITL is running and responding."""
        if not self.process or self.process.poll() is not None:
            return False
        try:
            from pymavlink import mavutil
            conn = mavutil.mavlink_connection(
                "udp:127.0.0.1:14550", source_system=2
            )
            msg = conn.wait_heartbeat(timeout=3)
            return msg is not None
        except Exception:
            return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Splash SITL Simulation Setup")
    parser.add_argument("--run", action="store_true", help="Start SITL")
    parser.add_argument("--kill", action="store_true", help="Stop SITL")
    parser.add_argument("--check", action="store_true", help="Check SITL health")
    parser.add_argument("--params-only", action="store_true",
                        help="Only write param file, don't run")
    args = parser.parse_args()

    manager = SITLManager()

    if args.params_only:
        manager.setup_mavlink_params()
        print(f"Params written to {SPLASH_DIR}/splash_sitl.params")
        print("Start SITL manually with:")
        print(f"  {SITL_BIN} -v ArduCopter --model quad --no-mavproxy \\")
        print(f"    --out 127.0.0.1:14550 --instance 0")

    elif args.kill:
        manager.stop()

    elif args.check:
        ok = manager.health_check()
        print(f"SITL health: {'OK' if ok else 'NOT RUNNING'}")
        sys.exit(0 if ok else 1)

    elif args.run:
        print("Starting SITL simulation for Splash...")
        print(f"  MCP Server: python splash/control/mcp_server.py")
        print(f"  CV Pipeline: python splash/cv/main.py --motion-comp")
        print(f"  Protection: python splash/control/protection_mode.py")
        manager.run()

    else:
        parser.print_help()
        print("\nQuick start:")
        print("  # 1. Start SITL")
        print("  python setup_sitl_sim.py --run")
        print("  # 2. Start MCP server")
        print("  python splash/control/mcp_server.py")
        print("  # 3. In another terminal, start CV pipeline")
        print("  python splash/cv/main.py --no-preview")
        print("  # 4. Connect QGroundControl to UDP:14550")


if __name__ == "__main__":
    main()
