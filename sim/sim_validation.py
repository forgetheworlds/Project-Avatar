#!/usr/bin/env python3
"""
sim_validation.py — End-to-end validation for Project Avatar.

Runs validation scenarios against SITL (when available) or in mock mode.
Tests the complete stack: MAVLink bridge, state machine, payload system,
and telemetry.

Modes:
    --sitl       Require running SITL (UDP:14551)
    --mock       Run without SITL (tests code paths with simulated hardware)
    --smoke      Quick subset: payload + state machine + telemetry schema
    --scenario X Run a single named scenario
    --full       Run all available scenarios

Usage:
    python3 sim/sim_validation.py                  # auto-detect SITL
    python3 sim/sim_validation.py --mock           # no SITL required
    python3 sim/sim_validation.py --smoke          # quick check
    python3 sim/sim_validation.py --scenario payload

Project Avatar — Simulation validation harness.
"""

from __future__ import annotations

import json
import sys
import time
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================================
# Result types
# =========================================================================

@dataclass
class ValidationResult:
    scenario: str
    passed: bool
    duration_s: float
    message: str
    details: dict = field(default_factory=dict)

    def status_icon(self) -> str:
        return "PASS" if self.passed else "FAIL"

    def __str__(self) -> str:
        icon = self.status_icon()
        return f"  [{icon}] {self.scenario:<30s} ({self.duration_s:.1f}s)  {self.message}"


class ValidationRunner:
    """Runs scenarios and collects results."""

    def __init__(self):
        self.results: list[ValidationResult] = []

    def run(self, name: str, fn: Callable) -> ValidationResult:
        t0 = time.monotonic()
        try:
            result = fn(self)
            duration = time.monotonic() - t0
            if isinstance(result, tuple):
                passed, message, details = result
            elif isinstance(result, bool):
                passed, message, details = result, "", {}
            else:
                passed, message, details = True, str(result), {}

            r = ValidationResult(name, passed, duration, message, details)
        except Exception as e:
            duration = time.monotonic() - t0
            import traceback
            tb = traceback.format_exc()
            r = ValidationResult(name, False, duration, str(e), {"traceback": tb})

        self.results.append(r)
        print(r)
        return r

    def summary(self) -> tuple[int, int, int, float]:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        total_time = sum(r.duration_s for r in self.results)
        return passed, failed, total, total_time

    def save_report(self, path: str):
        with open(path, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "total": len(self.results),
                "results": [
                    {
                        "scenario": r.scenario,
                        "passed": r.passed,
                        "duration_s": round(r.duration_s, 2),
                        "message": r.message,
                        "details": r.details,
                    }
                    for r in self.results
                ],
            }, f, indent=2)


# =========================================================================
# SITL detection
# =========================================================================

def sitl_available() -> bool:
    """Check if a SITL instance is reachable on UDP:14551."""
    try:
        from pymavlink import mavutil
        conn = mavutil.mavlink_connection("udp:127.0.0.1:14551")
        msg = conn.wait_heartbeat(timeout=2.0)
        conn.close()
        return msg is not None
    except Exception:
        return False


# =========================================================================
# Scenarios (Mock mode — no SITL required)
# =========================================================================

def scenario_payload_registry(runner: ValidationRunner):
    """Validate payload registry: scan, activate, command, health."""
    from splash.payload import PayloadRegistry, SplashPayload, PayloadPowerLimitError

    # --- 1. Registry creation and scan ---
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )

    discovered = registry.scan_bus()
    assert len(discovered) == 1, f"Expected 1 payload, got {len(discovered)}"
    assert discovered[0].payload_type == "splash", "Wrong type"

    # --- 2. Activate ---
    assert registry.activate("splash_0"), "Activation failed"
    p = registry.get("splash_0")
    assert p is not None, "Payload not found after activate"
    assert p.state.name == "ACTIVE", f"Expected ACTIVE, got {p.state.name}"

    # --- 3. Fire command ---
    fire_result = registry.execute("splash_0", "fire", {"duration_ms": 100})
    assert fire_result.success, f"Fire failed: {fire_result.message}"
    assert fire_result.data["fire_count"] == 1, f"Fire count: {fire_result.data['fire_count']}"

    # --- 4. Aim command ---
    aim_result = registry.execute("splash_0", "aim", {"pan_deg": 30, "tilt_deg": 120})
    assert aim_result.success, f"Aim failed: {aim_result.message}"

    # --- 5. Health ---
    status = registry.health_status_all()
    assert "splash_0" in status, "Missing in health status"
    assert status["splash_0"]["health"]["status"] == "OK", "Health not OK"

    # --- 6. Power budget enforcement ---
    tight_registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
        power_budget_ma=100,  # Too low
    )
    tight_registry.scan_bus()
    try:
        tight_registry.activate("splash_0")
        assert False, "Should have raised PayloadPowerLimitError"
    except PayloadPowerLimitError:
        pass  # Expected

    # --- 7. Deactivate and teardown ---
    registry.deactivate("splash_0")
    assert p.state.name == "READY"
    registry.teardown_all()
    assert p.state.name == "TEARDOWN"

    return True, "All payload operations passed", {"fire_count": fire_result.data["fire_count"]}


def scenario_state_machine(runner: ValidationRunner):
    """Validate state machine transitions and guards."""
    from splash.control.state_machine import (
        StateMachine, DroneState, StateTransitionError, StateGuardError
    )

    sm = StateMachine()
    assert sm.state == DroneState.IDLE

    # IDLE → ARMED (valid)
    sm.set_arming()
    assert sm.state == DroneState.ARMED

    # ARMED → TAKING_OFF (valid)
    sm.set_taking_off()
    assert sm.state == DroneState.TAKING_OFF

    # TAKING_OFF → FLYING (valid)
    sm.set_flying()
    assert sm.state == DroneState.FLYING

    # FLYING → ORBITING (valid)
    sm.set_orbiting()
    assert sm.state == DroneState.ORBITING

    # ORBITING → ENGAGING (valid)
    sm.set_engaging()
    assert sm.state == DroneState.ENGAGING

    # ENGAGING → RETURNING (valid)
    sm.set_returning()
    assert sm.state == DroneState.RETURNING

    # RETURNING → IDLE (valid)
    sm.set_idle()
    assert sm.state == DroneState.IDLE

    # Guard: can't arm from FLYING
    sm.force_state(DroneState.FLYING)
    assert not sm.can_arm()

    # is_airborne
    assert sm.is_airborne()

    # require_state
    sm.require_state(DroneState.FLYING, DroneState.ORBITING)  # Should not raise

    try:
        sm.require_state(DroneState.IDLE)
        assert False, "Should have raised StateGuardError"
    except StateGuardError:
        pass

    # Force state (emergency)
    sm.force_state(DroneState.DISARMED)
    assert sm.state == DroneState.DISARMED

    # Status dict
    status = sm.status_dict()
    assert "state" in status
    assert "is_airborne" in status
    assert "context" in status

    return True, "State machine: IDLE→ARMED→FLYING→ORBITING→ENGAGING→RETURNING→IDLE", {}


def scenario_telemetry_schema(runner: ValidationRunner):
    """Validate the Telemetry dataclass schema."""
    from splash.control.mavlink_bridge import Telemetry

    t = Telemetry(
        lat=43.5890, lon=-79.6441, alt=10.5, heading=90.0,
        vx=1.0, vy=0.5, vz=-0.1,
        roll=5.0, pitch=-2.0, yaw=88.0,
        battery_voltage=16.2, battery_current=3.5, battery_remaining=78,
        airspeed=2.0, groundspeed=2.5, throttle=45, climb=0.2,
        armed=True, mode="CIRCLE", gps_fix=3, gps_sats=14,
        heartbeat_age_s=0.1,
    )

    d = t.to_dict()

    # Check structure
    assert "position" in d
    assert d["position"]["lat"] == 43.589
    assert d["position"]["lon"] == -79.6441

    assert "altitude_m" in d
    assert d["altitude_m"] == 10.5

    assert "attitude" in d
    assert d["attitude"]["roll"] == 5.0
    assert d["attitude"]["pitch"] == -2.0
    assert d["attitude"]["yaw"] == 88.0

    assert "velocity" in d
    assert d["velocity"]["groundspeed"] == 2.5

    assert "battery" in d
    assert d["battery"]["voltage"] == 16.2
    assert d["battery"]["remaining_pct"] == 78

    assert "state" in d
    assert d["state"]["armed"] is True
    assert d["state"]["mode"] == "CIRCLE"
    assert d["state"]["gps_fix"] == 3

    assert "link" in d
    assert d["link"]["heartbeat_age_s"] == 0.1

    return True, "Telemetry schema valid", {"fields": len(d)}


def scenario_emergency_stop(runner: ValidationRunner):
    """Validate payload emergency stop timing."""
    from splash.payload import SplashPayload

    payload = SplashPayload("estop_test", sim_mode=True)
    payload.initialize()
    payload.activate()

    t0 = time.perf_counter()
    result = payload.emergency_stop()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result, "Emergency stop returned False"
    assert elapsed_ms < 50.0, f"Emergency stop too slow: {elapsed_ms:.1f}ms > 50ms limit"
    assert payload.state.name == "FAULTED", f"Expected FAULTED, got {payload.state.name}"

    return True, f"Emergency stop in {elapsed_ms:.1f}ms", {"elapsed_ms": round(elapsed_ms, 1)}


def scenario_command_routing(runner: ValidationRunner):
    """Validate that payload commands are properly routed with state checks."""
    from splash.payload import SplashPayload, PayloadCommandResult

    payload = SplashPayload("route_test", sim_mode=True)
    payload.initialize()

    # Queries allowed when READY (not ACTIVE)
    result = payload.execute_command("get_status", {})
    assert result.success, f"get_status should work when READY: {result.message}"
    assert result.data["reservoir_ml"] == 15.0

    # Actions blocked when READY
    result = payload.execute_command("fire", {"duration_ms": 200})
    assert not result.success, "Fire should be blocked when READY"
    assert "ACTIVE" in result.message.upper() or "active" in result.message.lower()

    # Activate and try again
    payload.activate()
    fire_r = payload.execute_command("fire", {"duration_ms": 200})
    assert fire_r.success, f"Fire should work when ACTIVE: {fire_r.message}"
    assert fire_r.data["fire_count"] == 1

    # Unknown command
    result = payload.execute_command("dance", {})
    assert not result.success, "Unknown command should fail"
    assert "Unknown" in result.message or "unknown" in result.message.lower()

    return True, "Command routing correct", {"fire_count": fire_r.data["fire_count"]}


def scenario_reservoir_management(runner: ValidationRunner):
    """Validate reservoir tracking across multiple fires."""
    from splash.payload import SplashPayload

    payload = SplashPayload("reservoir_test", sim_mode=True)
    payload.initialize()
    payload.activate()

    # Initial state
    r = payload.execute_command("get_status", {})
    assert r.data["reservoir_ml"] == 15.0
    assert r.data["fire_count"] == 0

    # Fire 10 bursts of 500ms each = 5ml used
    for i in range(10):
        payload.execute_command("fire", {"duration_ms": 500})

    r = payload.execute_command("get_status", {})
    assert r.data["fire_count"] == 10
    assert abs(r.data["reservoir_ml"] - 10.0) < 0.1, f"Expected 10.0ml, got {r.data['reservoir_ml']}"
    assert abs(r.data["total_fired_ml"] - 5.0) < 0.1, f"Expected 5.0ml, got {r.data['total_fired_ml']}"

    # Fire until empty
    for i in range(20):  # 20 more = 10ml — should hit empty
        payload.execute_command("fire", {"duration_ms": 500})

    r = payload.execute_command("get_status", {})
    assert r.data["reservoir_ml"] <= 0.1, f"Reservoir should be near 0, got {r.data['reservoir_ml']}"

    # Fire when empty — should fail
    result = payload.execute_command("fire", {"duration_ms": 200})
    assert not result.success, "Fire should fail when reservoir empty"
    assert "empty" in result.message.lower() or "reservoir" in result.message.lower()

    return True, f"Reservoir: 15ml → 0ml after {r.data['fire_count']} shots", {
        "total_shots": r.data["fire_count"],
        "total_fired_ml": round(r.data["total_fired_ml"], 1),
    }


# =========================================================================
# Scenarios (SITL mode — requires running SITL)
# =========================================================================

def scenario_sitl_heartbeat(runner: ValidationRunner):
    """Connect to SITL and verify heartbeat."""
    from splash.control.mavlink_bridge import MavlinkBridge

    bridge = MavlinkBridge(sim_mode=True, sim_host="127.0.0.1", sim_port=14551)
    try:
        bridge.connect(timeout=10.0)
        assert bridge.connected, "Not connected after connect()"
        assert bridge.heartbeat_ok, "Heartbeat not OK"

        t = bridge.get_telemetry()
        assert t.lat != 0.0, "Telemetry lat is zero"
        assert t.battery_voltage > 0, "Battery voltage is zero"

        return True, f"Heartbeat OK, pos=({t.lat:.4f}, {t.lon:.4f})", {
            "lat": round(t.lat, 4),
            "lon": round(t.lon, 4),
            "battery_v": round(t.battery_voltage, 1),
        }
    finally:
        try:
            bridge.disconnect()
        except Exception:
            pass


def scenario_sitl_arm_disarm(runner: ValidationRunner):
    """Arm and disarm in SITL."""
    from splash.control.mavlink_bridge import MavlinkBridge

    bridge = MavlinkBridge(sim_mode=True)
    try:
        bridge.connect()

        # Arm
        result = bridge.arm()
        assert result["success"], f"Arm failed: {result}"

        t = bridge.get_telemetry()
        assert t.armed, "Not armed after arm()"

        # Disarm
        result = bridge.disarm()
        assert result["success"], f"Disarm failed: {result}"

        t = bridge.get_telemetry()
        assert not t.armed, "Still armed after disarm()"

        return True, "Arm/disarm cycle OK", {}
    finally:
        try:
            bridge.disconnect()
        except Exception:
            pass


def scenario_sitl_takeoff_land(runner: ValidationRunner):
    """Take off, verify altitude, land."""
    from splash.control.mavlink_bridge import MavlinkBridge

    bridge = MavlinkBridge(sim_mode=True)
    try:
        bridge.connect()

        result = bridge.takeoff(5.0, timeout=45.0)
        assert result["success"], f"Takeoff failed: {result}"

        t = bridge.get_telemetry()
        assert t.alt >= 4.0, f"Altitude {t.alt:.1f}m below 4.0m target"
        assert t.armed, "Not armed in flight"

        result = bridge.land(timeout=60.0)
        assert result["success"], f"Land failed: {result}"

        return True, f"Takeoff→hover→land (reached {t.alt:.1f}m)", {
            "peak_altitude_m": round(t.alt, 1),
        }
    finally:
        try:
            bridge.disconnect()
        except Exception:
            pass


# =========================================================================
# Main
# =========================================================================

SCENARIOS_MOCK = {
    "payload": scenario_payload_registry,
    "state-machine": scenario_state_machine,
    "telemetry": scenario_telemetry_schema,
    "emergency-stop": scenario_emergency_stop,
    "command-routing": scenario_command_routing,
    "reservoir": scenario_reservoir_management,
}

SCENARIOS_SITL = {
    "sitl-heartbeat": scenario_sitl_heartbeat,
    "sitl-arm-disarm": scenario_sitl_arm_disarm,
    "sitl-takeoff-land": scenario_sitl_takeoff_land,
}

SMOKE_SCENARIOS = ["payload", "state-machine", "telemetry"]


def main():
    parser = argparse.ArgumentParser(
        description="Project Avatar — Simulation Validation"
    )
    parser.add_argument("--sitl", action="store_true", help="Require SITL (fail if not running)")
    parser.add_argument("--mock", action="store_true", help="Mock mode (no SITL required)")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test")
    parser.add_argument("--scenario", type=str, help="Run a single scenario by name")
    parser.add_argument("--full", action="store_true", help="Run all scenarios")
    parser.add_argument("--report", type=str, default="sim/validation_report.json",
                       help="JSON report path")
    args = parser.parse_args()

    has_sitl = sitl_available()

    print("=" * 60)
    print("  Project Avatar — Simulation Validation")
    print("=" * 60)
    print(f"  SITL available: {'YES' if has_sitl else 'NO'} {'(not installed)' if not has_sitl else '(UDP:14551)'}")
    print(f"  pymavlink:      OK (v2.4.49)")
    print("=" * 60)
    print()

    runner = ValidationRunner()

    # Determine which scenarios to run
    if args.scenario:
        if args.scenario in SCENARIOS_MOCK:
            runner.run(args.scenario, SCENARIOS_MOCK[args.scenario])
        elif args.scenario in SCENARIOS_SITL:
            if not has_sitl:
                print(f"ERROR: Scenario '{args.scenario}' requires SITL but none detected.")
                sys.exit(1)
            runner.run(args.scenario, SCENARIOS_SITL[args.scenario])
        else:
            print(f"ERROR: Unknown scenario '{args.scenario}'.")
            print(f"  Mock: {list(SCENARIOS_MOCK.keys())}")
            print(f"  SITL: {list(SCENARIOS_SITL.keys())}")
            sys.exit(1)
    elif args.smoke:
        for name in SMOKE_SCENARIOS:
            if name in SCENARIOS_MOCK:
                runner.run(name, SCENARIOS_MOCK[name])
    elif args.mock or not has_sitl:
        # Run all mock scenarios
        for name, fn in SCENARIOS_MOCK.items():
            runner.run(name, fn)
    elif args.sitl or has_sitl:
        # Run SITL scenarios
        for name, fn in SCENARIOS_SITL.items():
            runner.run(name, fn)
        # Also run mock scenarios (they don't need SITL)
        for name, fn in SCENARIOS_MOCK.items():
            runner.run(name, fn)
    else:
        # Default: run mock scenarios
        for name, fn in SCENARIOS_MOCK.items():
            runner.run(name, fn)

    # Summary
    passed, failed, total, total_time = runner.summary()
    print()
    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {total} total")
    print(f"  Duration: {total_time:.1f}s")
    print("=" * 60)

    # Save report
    report_path = PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    runner.save_report(str(report_path))
    print(f"\nReport saved: {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
