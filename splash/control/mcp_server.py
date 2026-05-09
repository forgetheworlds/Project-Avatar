#!/usr/bin/env python3
"""
mcp_server.py — FastMCP tool server for LLM drone control.

Provides 13 MCP tools that let an LLM (Hermes) control the Avatar drone:
  1. arm()                — Arm the drone
  2. takeoff(altitude_m)  — Take off to altitude
  3. land()               — Land at current position
  4. goto(lat, lon, alt)  — Fly to GPS coordinates
  5. orbit(center, radius, alt) — Orbit a point
  6. get_telemetry()      — Full position/attitude/battery telemetry
  7. get_camera_feed()    — Latest frame info + payload status
  8. identify_target(desc)— Set target description for CV
  9. engage_target()      — Activate track+aim+fire via payload
  10. protect_mode(center, radius) — Orbit + detect + fire via payload
  11. disarm()            — Emergency disarm
  12. rtb()               — Return to home
  13. payload_command(payload_id, action, params) — Direct payload control

Payload interface:
    All payload ops go through PayloadRegistry (splash/payload/).
    The registry auto-discovers payloads on boot and routes commands.
    No hardcoded Splash logic — any payload that implements BasePayload works.

Usage:
    python mcp_server.py                        # SIM mode (UDP:14551)
    SIM_MODE=false  python mcp_server.py         # REAL mode (ESP32 bridge)
    SIM_HOST=... SIM_PORT=... python mcp_server.py

Project Avatar — LLM-controlled modular drone platform.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Optional

# ---------------------------------------------------------------------------
# FastMCP import (supports both mcp and fastmcp packages)
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("ERROR: FastMCP not installed. Run: pip install fastmcp")
        sys.exit(1)

from state_machine import (
    StateMachine,
    DroneState,
    StateTransitionError,
    StateGuardError,
)
from mavlink_bridge import MavlinkBridge

# Payload registry
from splash.payload import (
    PayloadRegistry,
    SplashPayload,
    PayloadNotReadyError,
    PayloadFaultError,
    PayloadPowerLimitError,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("splash.mcp")

# ---------------------------------------------------------------------------
# Config (environment overrides)
# ---------------------------------------------------------------------------
SIM_MODE = os.environ.get("SIM_MODE", "true").lower() in ("1", "true", "yes")
SIM_HOST = os.environ.get("SIM_HOST", "127.0.0.1")
SIM_PORT = int(os.environ.get("SIM_PORT", "14551"))
REAL_HOST = os.environ.get("REAL_HOST", "192.168.4.1")
REAL_PORT = int(os.environ.get("REAL_PORT", "14550"))

# ---------------------------------------------------------------------------
# Global state (singletons for the MCP server process)
# ---------------------------------------------------------------------------
state_machine = StateMachine()
bridge = MavlinkBridge(
    sim_mode=SIM_MODE,
    sim_host=SIM_HOST,
    sim_port=SIM_PORT,
    real_host=REAL_HOST,
    real_port=REAL_PORT,
)

# Payload registry — auto-discovers payloads on first use
# on_fault callback set after _on_payload_fault is defined below
payload_registry = PayloadRegistry(
    known_payloads=[SplashPayload],
    sim_mode=SIM_MODE,
    power_budget_ma=4500,
)

_connected = False
_payloads_initialized = False

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("Splash Drone Control")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_connected() -> None:
    """Lazy-connect to MAVLink on first tool call."""
    global _connected
    if not _connected:
        bridge.connect()
        _connected = True
        logger.info("MAVLink bridge connected for MCP session.")


def _ensure_payloads() -> None:
    """Lazy-initialize payload registry on first use."""
    global _payloads_initialized
    if not _payloads_initialized:
        discovered = payload_registry.scan_bus()
        logger.info(f"Payloads initialized: {len(discovered)} discovered")
        for info in discovered:
            logger.info(f"  {info.payload_id}: {info.display_name} "
                       f"({info.mass_g}g, {info.power_max_ma}mA)")
            payload_registry.activate(info.payload_id)
        _payloads_initialized = True


def _on_payload_fault(payload_id: str, health) -> None:
    """Callback when a payload faults. Triggers mission abort if critical."""
    logger.error(f"PAYLOAD FAULT: {payload_id} — {health.status}")
    if payload_registry.critical_payload_failed():
        logger.critical("CRITICAL payload failed — aborting mission!")
        # Auto-RTB
        try:
            if state_machine.is_airborne():
                bridge.rtb()
                state_machine.set_returning()
        except Exception:
            pass


# Wire the fault callback now that it's defined
payload_registry._on_fault = _on_payload_fault


def _ok(**kwargs) -> str:
    """Wrap a dict into a JSON success response string."""
    return json.dumps({"status": "success", **kwargs})


def _err(message: str, **kwargs) -> str:
    """Wrap an error message into a JSON error response string."""
    return json.dumps({"status": "error", "error": message, **kwargs})


def _validate_lat(name: str, val: float) -> None:
    if not (-90 <= val <= 90):
        raise ValueError(f"{name} must be between -90 and 90, got {val}")


def _validate_lon(name: str, val: float) -> None:
    if not (-180 <= val <= 180):
        raise ValueError(f"{name} must be between -180 and 180, got {val}")


def _validate_positive(name: str, val: float) -> None:
    if val <= 0:
        raise ValueError(f"{name} must be positive, got {val}")


# ===================================================================
# MCP TOOLS  (12 tools)
# ===================================================================

# ------------------------------------------------------------------
# 1. arm()
# ------------------------------------------------------------------
@mcp.tool()
def arm() -> str:
    """Arm the drone motors.

    Preconditions: Drone must be IDLE or DISARMED.
    Postconditions: Drone is ARMED (motors spinning at idle).

    Returns JSON with status and current state.
    """
    try:
        _ensure_connected()

        if not state_machine.can_arm():
            return _err(
                f"Cannot arm from state {state_machine.state_name}. "
                f"Must be IDLE or DISARMED.",
                current_state=state_machine.state_name,
            )

        result = bridge.arm()
        state_machine.set_arming()
        return _ok(**result, state=state_machine.state_name)

    except StateTransitionError as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("arm() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 2. takeoff(altitude_meters)
# ------------------------------------------------------------------
@mcp.tool()
def takeoff(altitude_meters: float) -> str:
    """Take off and climb to the specified altitude in meters.

    Preconditions: Drone must be ARMED (call arm() first).
    Postconditions: Drone is FLYING at the target altitude.

    Args:
        altitude_meters: Target altitude above ground in meters (positive).

    Returns JSON with status, reached altitude, and current state.
    """
    try:
        _ensure_connected()
        _validate_positive("altitude_meters", altitude_meters)

        state_machine.require_state(DroneState.ARMED)
        state_machine.set_taking_off()
        state_machine.context.takeoff_alt = altitude_meters

        result = bridge.takeoff(altitude_meters)
        state_machine.set_flying()

        # Record home position
        t = bridge.get_telemetry()
        if state_machine.context.home_lat == 0:
            state_machine.context.home_lat = t.lat
            state_machine.context.home_lon = t.lon

        return _ok(**result, state=state_machine.state_name)

    except (StateTransitionError, StateGuardError) as e:
        return _err(str(e), current_state=state_machine.state_name)
    except ValueError as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("takeoff() failed")
        state_machine.set_error(str(e))
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 3. land()
# ------------------------------------------------------------------
@mcp.tool()
def land() -> str:
    """Land the drone at its current position.

    Preconditions: Drone must be airborne (FLYING, ORBITING, ENGAGING, etc.).
    Postconditions: Drone is IDLE on the ground.

    Returns JSON with status and final altitude.
    """
    try:
        _ensure_connected()

        if not state_machine.is_airborne():
            return _err(
                f"Cannot land from state {state_machine.state_name}. "
                "Drone is not airborne.",
                current_state=state_machine.state_name,
            )

        state_machine.set_landing()
        result = bridge.land()

        if result.get("success"):
            state_machine.set_idle()

        return _ok(**result, state=state_machine.state_name)

    except Exception as e:
        logger.exception("land() failed")
        state_machine.set_error(str(e))
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 4. goto(lat, lon, alt)
# ------------------------------------------------------------------
@mcp.tool()
def goto(lat: float, lon: float, alt: float) -> str:
    """Fly to specified GPS coordinates at the given altitude.

    Preconditions: Drone must be airborne (FLYING, ORBITING, ENGAGING).
    Postconditions: Drone is at the target position (still FLYING).

    Args:
        lat: Target latitude in decimal degrees (-90 to 90).
        lon: Target longitude in decimal degrees (-180 to 180).
        alt: Target altitude above ground in meters (positive).

    Returns JSON with status, target position, and remaining distance.
    """
    try:
        _ensure_connected()
        _validate_lat("lat", lat)
        _validate_lon("lon", lon)
        _validate_positive("alt", alt)

        state_machine.require_state(
            DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING
        )

        # Store target in context
        state_machine.context.target_lat = lat
        state_machine.context.target_lon = lon
        state_machine.context.target_alt = alt

        result = bridge.goto(lat, lon, alt)

        # Return to FLYING if we were in a sub-state
        if result.get("success"):
            state_machine.set_flying()

        return _ok(**result, state=state_machine.state_name)

    except (StateTransitionError, StateGuardError) as e:
        return _err(str(e), current_state=state_machine.state_name)
    except ValueError as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("goto() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 5. orbit(center_lat, center_lon, radius_m, altitude_m)
# ------------------------------------------------------------------
@mcp.tool()
def orbit(center_lat: float, center_lon: float, radius_m: float,
          altitude_m: float) -> str:
    """Orbit around a GPS point at the given radius and altitude.

    Preconditions: Drone must be airborne.
    Postconditions: Drone is ORBITING the center point.

    First flies to the orbit center, then engages CIRCLE mode.

    Args:
        center_lat: Orbit center latitude (-90 to 90).
        center_lon: Orbit center longitude (-180 to 180).
        radius_m: Orbit radius in meters (positive, 5-100 recommended).
        altitude_m: Orbit altitude in meters (positive).

    Returns JSON with orbit parameters and status.
    """
    try:
        _ensure_connected()
        _validate_lat("center_lat", center_lat)
        _validate_lon("center_lon", center_lon)
        _validate_positive("radius_m", radius_m)
        _validate_positive("altitude_m", altitude_m)

        state_machine.require_state(
            DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING
        )

        # Store orbit context
        state_machine.context.orbit_center_lat = center_lat
        state_machine.context.orbit_center_lon = center_lon
        state_machine.context.orbit_radius_m = radius_m
        state_machine.context.orbit_altitude_m = altitude_m

        result = bridge.orbit(center_lat, center_lon, radius_m, altitude_m)
        state_machine.set_orbiting()

        return _ok(**result, state=state_machine.state_name)

    except (StateTransitionError, StateGuardError) as e:
        return _err(str(e), current_state=state_machine.state_name)
    except ValueError as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("orbit() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 6. get_telemetry()
# ------------------------------------------------------------------
@mcp.tool()
def get_telemetry() -> str:
    """Return comprehensive real-time telemetry.

    Includes: GPS position, altitude, attitude (roll/pitch/yaw), heading,
    velocity, battery voltage/current/remaining, flight mode, arm state,
    GPS fix quality, and heartbeat link health.

    Returns JSON with full telemetry snapshot and current state.
    """
    try:
        _ensure_connected()
        t = bridge.get_telemetry()
        state_info = state_machine.status_dict()

        # If we detect armed via telemetry but state machine is IDLE, sync it
        if t.armed and state_machine.state == DroneState.IDLE:
            state_machine.force_state(DroneState.ARMED)
            state_info = state_machine.status_dict()

        return _ok(
            telemetry=t.to_dict(),
            state=state_info,
        )

    except Exception as e:
        logger.exception("get_telemetry() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 7. get_camera_feed()
# ------------------------------------------------------------------
@mcp.tool()
def get_camera_feed() -> str:
    """Get the latest camera frame information and payload status.

    Returns frame info from the camera bridge plus the current state of all
    active payloads (pan/tilt angles, pump status, reservoir level, etc.).

    Returns JSON with camera info, payload status, and drone state.
    """
    try:
        _ensure_connected()
        _ensure_payloads()

        info = bridge.get_camera_frame_info()
        payloads_status = payload_registry.health_status_all()

        return _ok(
            camera=info,
            payloads=payloads_status,
            state=state_machine.state_name,
            target=state_machine.context.target_description or "none",
            shots_fired=state_machine.context.shots_fired,
        )

    except Exception as e:
        logger.exception("get_camera_feed() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 8. identify_target(description)
# ------------------------------------------------------------------
@mcp.tool()
def identify_target(description: str) -> str:
    """Set a target description for the CV pipeline to search for.

    This tells the computer vision system what to look for.
    Examples: "person in red shirt", "blue team member", "moving vehicle".

    The description is stored and used by the CV pipeline's detector
    (e.g., YOLOv8 class filtering, HSV color matching) to prioritize
    detections matching this description.

    Args:
        description: Natural language description of the target.

    Returns JSON confirming the target description was set.
    """
    try:
        if not description or not description.strip():
            return _err("Target description cannot be empty.")

        state_machine.context.target_description = description.strip()
        state_machine.context.target_acquired = False

        logger.info(f"Target identified: '{description}'")

        return _ok(
            message=f"Target description set: '{description}'",
            target_description=description.strip(),
            state=state_machine.state_name,
        )

    except Exception as e:
        logger.exception("identify_target() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 9. engage_target()
# ------------------------------------------------------------------
@mcp.tool()
def engage_target() -> str:
    """Activate the track+aim+fire engagement sequence via payload.

    Preconditions: Drone must be airborne and a target must be identified
                   (call identify_target() first).

    The drone enters GUIDED mode for precision positioning. The payload
    (e.g., Splash water gun) is activated for aiming and firing when:
      - Target is within range (< fire_max_distance_m)
      - Target is near crosshair center
      - Cooldown timer has elapsed

    The engagement continues until land(), rtb(), or disarm() is called.

    Returns JSON with engagement status, payload info, and target.
    """
    try:
        _ensure_connected()
        _ensure_payloads()

        state_machine.require_state(
            DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING
        )

        if not state_machine.context.target_description:
            return _err(
                "No target identified. Call identify_target() first.",
                current_state=state_machine.state_name,
            )

        bridge.engage_target_mode()
        state_machine.set_engaging()
        state_machine.context.target_acquired = True

        # Get splash payload and aim center
        payloads = payload_registry.get_payloads_of_type("splash")
        payload_info = {}
        for p in payloads:
            p.execute_command("center", {})
            payload_info[p.payload_id] = "armed"

        logger.info("Engage target sequence activated via payload.")

        return _ok(
            message="Target engagement active. Track+aim+fire via payload.",
            target_description=state_machine.context.target_description,
            target_acquired=True,
            shots_fired=state_machine.context.shots_fired,
            payloads=payload_info,
            state=state_machine.state_name,
        )

    except (StateTransitionError, StateGuardError) as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("engage_target() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 10. protect_mode(center_lat, center_lon, radius_m)
# ------------------------------------------------------------------
@mcp.tool()
def protect_mode(center_lat: float, center_lon: float, radius_m: float) -> str:
    """Enter protection mode: orbit a point while detecting and engaging targets.

    Combines orbit, target detection, and auto-engagement in one command.
    The drone will:
      1. Fly to the protection center
      2. Orbit at a tactical altitude (default: 10m)
      3. Continuously scan for targets matching identify_target() description
      4. Auto-engage and fire via payload when a valid target is detected

    This is the primary mode for the Splash water gun mission:
    protect a zone and shoot targets that enter it. The payload is
    automatically armed and centered.

    Args:
        center_lat: Protection zone center latitude (-90 to 90).
        center_lon: Protection zone center longitude (-180 to 180).
        radius_m: Orbit radius in meters (positive).

    Returns JSON with protection zone parameters, payload status, and state.
    """
    try:
        _ensure_connected()
        _ensure_payloads()
        _validate_lat("center_lat", center_lat)
        _validate_lon("center_lon", center_lon)
        _validate_positive("radius_m", radius_m)

        state_machine.require_state(
            DroneState.FLYING, DroneState.ORBITING, DroneState.ENGAGING
        )

        # Tactical altitude for protection
        altitude_m = 10.0

        # Store protection zone
        state_machine.context.protect_center_lat = center_lat
        state_machine.context.protect_center_lon = center_lon
        state_machine.context.protect_radius_m = radius_m

        bridge.protect_orbit_mode(center_lat, center_lon, radius_m, altitude_m)
        state_machine.set_orbiting()

        # Arm payloads for auto-engagement
        payload_info = {}
        for p in payload_registry.get_payloads_of_type("splash"):
            p.execute_command("center", {})
            payload_info[p.payload_id] = "armed"

        extra = {}
        if state_machine.context.target_description:
            extra["target_description"] = state_machine.context.target_description
            extra["auto_engage"] = True

        return _ok(
            message=f"Protect mode active — orbiting at radius {radius_m}m, "
                    f"altitude {altitude_m}m. Scanning for targets. "
                    f"{len(payload_info)} payload(s) armed.",
            zone={
                "center": {"lat": center_lat, "lon": center_lon},
                "radius_m": radius_m,
                "altitude_m": altitude_m,
            },
            payloads=payload_info,
            state=state_machine.state_name,
            **extra,
        )

    except (StateTransitionError, StateGuardError) as e:
        return _err(str(e), current_state=state_machine.state_name)
    except ValueError as e:
        return _err(str(e), current_state=state_machine.state_name)
    except Exception as e:
        logger.exception("protect_mode() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 11. disarm()
# ------------------------------------------------------------------
@mcp.tool()
def disarm() -> str:
    """Emergency disarm — immediately stop all motors.

    This works from ANY state and will cut power to the motors instantly.
    USE WITH CAUTION: disarming in flight will cause the drone to fall.

    Postconditions: Drone is DISARMED.

    Returns JSON with disarmed confirmation.
    """
    try:
        _ensure_connected()

        logger.warning("EMERGENCY DISARM triggered from state: "
                       f"{state_machine.state_name}")

        result = bridge.disarm()
        state_machine.set_disarmed()

        return _ok(
            **result,
            state=state_machine.state_name,
            warning="Drone disarmed. If airborne, this causes immediate fall!",
        )

    except Exception as e:
        logger.exception("disarm() failed")
        # Even on error, assume disarmed
        state_machine.force_state(DroneState.DISARMED)
        return _err(
            str(e),
            current_state=state_machine.state_name,
            note="State forced to DISARMED despite error.",
        )


# ------------------------------------------------------------------
# 12. rtb()
# ------------------------------------------------------------------
@mcp.tool()
def rtb() -> str:
    """Return to home (RTL — Return to Launch).

    The drone will:
      1. Climb to RTL altitude (if below it)
      2. Navigate back to the takeoff/home position
      3. Auto-land

    Preconditions: Drone must be airborne.
    Postconditions: Drone is IDLE at home position.

    This is the safe, automated way to bring the drone back.

    Returns JSON with RTL status and remaining distance.
    """
    try:
        _ensure_connected()

        if not state_machine.is_airborne():
            return _err(
                f"Cannot RTL from state {state_machine.state_name}. "
                "Drone is not airborne.",
                current_state=state_machine.state_name,
            )

        state_machine.set_returning()

        t_before = bridge.get_telemetry()
        home_lat = state_machine.context.home_lat or t_before.lat
        home_lon = state_machine.context.home_lon or t_before.lon
        dist_home = bridge._haversine(t_before.lat, t_before.lon, home_lat, home_lon)

        logger.info(f"RTL — {dist_home:.1f}m from home")

        result = bridge.rtb()

        if result.get("success"):
            state_machine.set_idle()

        return _ok(
            **result,
            distance_home_m=round(dist_home, 1),
            home_position={"lat": home_lat, "lon": home_lon},
            state=state_machine.state_name,
        )

    except Exception as e:
        logger.exception("rtb() failed")
        return _err(str(e), current_state=state_machine.state_name)


# ------------------------------------------------------------------
# 13. payload_command(payload_id, action, params)
# ------------------------------------------------------------------
@mcp.tool()
def payload_command(payload_id: str, action: str,
                    params: Optional[dict] = None) -> str:
    """Execute a payload-specific command directly.

    Routes the command through the payload registry to the correct
    payload instance. Supported actions depend on the payload type:
      - splash: fire, aim, center, set_deadzone, get_status
      - camera: (future)
      - spotlight: (future)

    Args:
        payload_id: Target payload ID, e.g. "splash_0".
        action: Command name (must be supported by the payload).
        params: Optional dict of parameters (e.g., {"duration_ms": 500}).

    Returns JSON with the payload's command result and current state.

    Examples:
        payload_command("splash_0", "aim", {"pan_deg": 45, "tilt_deg": 120})
        payload_command("splash_0", "fire", {"duration_ms": 500})
        payload_command("splash_0", "get_status")
    """
    try:
        _ensure_connected()
        _ensure_payloads()

        params = params or {}
        result = payload_registry.execute(payload_id, action, params)

        if result.success:
            return _ok(
                message=result.message,
                payload_id=payload_id,
                action=action,
                result=result.data,
                state=state_machine.state_name,
            )
        else:
            return _err(
                result.message,
                payload_id=payload_id,
                action=action,
                current_state=state_machine.state_name,
            )

    except (PayloadNotReadyError, PayloadFaultError,
            PayloadPowerLimitError) as e:
        return _err(str(e), payload_id=payload_id, action=action)
    except Exception as e:
        logger.exception("payload_command() failed")
        return _err(
            str(e),
            payload_id=payload_id,
            action=action,
            current_state=state_machine.state_name,
        )


# ===================================================================
# MCP RESOURCES  (informational endpoints)
# ===================================================================

@mcp.resource("splash://state")
def state_resource() -> str:
    """Current drone state and context as an MCP resource."""
    return json.dumps(state_machine.status_dict(), indent=2)


@mcp.resource("splash://health")
def health_resource() -> str:
    """Connection health, telemetry, and payload status summary."""
    if not _connected:
        return json.dumps({"connected": False, "message": "MAVLink not connected yet."})

    health = bridge.health_check()
    state_info = state_machine.status_dict()

    # Include payload health if initialized
    payloads = {}
    if _payloads_initialized:
        try:
            payloads = payload_registry.health_status_all()
        except Exception:
            pass

    return json.dumps({
        **health,
        "state": state_info,
        "payloads": payloads,
    }, indent=2)


# ===================================================================
# MAIN
# ===================================================================

def main() -> None:
    """Entry point: start the MCP server.

    Connection to MAVLink is lazy — the bridge connects on the first
    tool call, not at server startup. This allows the SITL simulator
    to be started after the MCP server.

    Payloads are also lazy-discovered on first payload-related tool call.
    """
    mode = "SIM" if SIM_MODE else "REAL"
    host = f"{SIM_HOST}:{SIM_PORT}" if SIM_MODE else f"{REAL_HOST}:{REAL_PORT}"
    transport = "UDP" if SIM_MODE else "TCP"

    print("=" * 55)
    print("  Project Avatar — MCP Tool Server")
    print("=" * 55)
    print(f"  Mode:      {mode} ({transport})")
    print(f"  Target:    {host}")
    print(f"  State:     {state_machine.state_name}")
    print(f"  Payloads:  {[c.__name__ for c in payload_registry._known_classes]}")
    print(f"  Tools:     13 (arm, takeoff, land, goto, orbit, "
          "get_telemetry, get_camera_feed, identify_target, "
          "engage_target, protect_mode, disarm, rtb, payload_command)")
    print(f"  Resources: splash://state, splash://health")
    print("=" * 55)
    print()
    print("MAVLink connection is LAZY — connects on first tool call.")
    print("Payload discovery is LAZY — scans on first payload command.")
    print("Start SITL first:  ../sim/launch.sh --headless")
    print()
    print("Starting MCP server...")
    print()

    # Register cleanup on exit
    import atexit
    def cleanup():
        if _connected:
            logger.info("Shutting down MAVLink bridge...")
            bridge.disconnect()
        # Teardown payloads
        payload_registry.teardown_all()
    atexit.register(cleanup)

    mcp.run()


if __name__ == "__main__":
    main()
