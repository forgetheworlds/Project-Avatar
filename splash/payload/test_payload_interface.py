"""
test_payload_interface.py — Validate the payload interface contract.

Tests:
    1. Payload lifecycle: discover → init → activate → deactivate → teardown
    2. State transitions (valid + invalid)
    3. Command dispatch (fire, aim, center, status)
    4. Emergency stop (<50ms requirement)
    5. Registry scan + power budget enforcement
    6. Health monitoring (mock)
    7. SIM_MODE vs real mode behavior

Run:
    python -m pytest splash/payload/test_payload_interface.py -v
    python splash/payload/test_payload_interface.py           # no pytest

Project Avatar — Modular payload interface system.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Project-Avatar/
sys.path.insert(0, str(PROJECT_ROOT))

from splash.payload.base_payload import (
    BasePayload,
    PayloadState,
    PayloadInfo,
    PayloadHealth,
    PayloadCommandResult,
)
from splash.payload.payload_registry import (
    PayloadRegistry,
    PayloadNotReadyError,
    PayloadFaultError,
    PayloadPowerLimitError,
)
from splash.payload.splash_payload import SplashPayload


# =========================================================================
# Test helpers
# =========================================================================

def test_splash_metadata():
    """Payload metadata matches spec."""
    payload = SplashPayload("test_0", sim_mode=True)

    assert payload.payload_type == "splash"
    assert payload.display_name == "Splash Water Gun"
    assert payload.version == "1.0.0"
    assert payload.mass_g == 50
    assert payload.power_max_ma == 1500
    assert payload.power_nominal_ma == 200
    assert "fire" in payload.commands
    assert "aim" in payload.commands
    assert "center" in payload.commands
    assert "get_status" in payload.commands
    assert payload.critical is True
    assert payload.bus_addresses == {"pca9685": 0x40}

    info = payload.get_info()
    assert isinstance(info, PayloadInfo)
    assert info.payload_id == "test_0"
    assert info.payload_type == "splash"
    assert info.mass_g == 50

    print("  ✓ test_splash_metadata passed")


def test_lifecycle_sim():
    """Full lifecycle in SIM_MODE: discover → init → activate → deactivate → teardown."""
    payload = SplashPayload("life_0", sim_mode=True)

    # 1. Discover (SIM always True)
    assert SplashPayload.discover(sim_mode=True) is True
    assert payload.state == PayloadState.UNKNOWN
    print("  ✓ discover: True")

    # 2. Initialize
    assert payload.initialize() is True
    assert payload.state == PayloadState.READY
    print("  ✓ initialize: READY")

    # 3. Activate
    assert payload.activate() is True
    assert payload.state == PayloadState.ACTIVE
    print("  ✓ activate: ACTIVE")

    # 4. Command while active
    result = payload.execute_command("aim", {"pan_deg": 45, "tilt_deg": 120})
    assert result.success is True
    assert "pan=45" in result.message or "45.0" in result.data.get("pan_deg", "")
    print("  ✓ aim command: success")

    result = payload.execute_command("fire", {"duration_ms": 200})
    assert result.success is True
    assert result.data["fire_count"] == 1
    print("  ✓ fire command: success")

    # 5. Deactivate
    assert payload.deactivate() is True
    assert payload.state == PayloadState.READY
    print("  ✓ deactivate: READY")

    # 6. Teardown
    payload.teardown()
    assert payload.state == PayloadState.TEARDOWN
    print("  ✓ teardown: TEARDOWN")

    print("  ✓✓ test_lifecycle_sim passed")


def test_command_requires_active():
    """Aim/fire must fail when not ACTIVE."""
    payload = SplashPayload("cmd_0", sim_mode=True)
    payload.initialize()  # READY, not ACTIVE

    # fire should fail (not active)
    result = payload.execute_command("fire", {"duration_ms": 200})
    assert result.success is False
    assert "ACTIVE" in result.message.upper() or "active" in result.message.lower()
    print("  ✓ fire rejected when READY")

    # get_status should succeed (queries don't need ACTIVE)
    result = payload.execute_command("get_status", {})
    assert result.success is True
    print("  ✓ get_status allowed when READY")

    print("  ✓ test_command_requires_active passed")


def test_invalid_state_transitions():
    """Invalid transitions are handled."""
    payload = SplashPayload("trans_0", sim_mode=True)

    # Can't activate from UNKNOWN — returns False, state unchanged
    result = payload.activate()
    assert result is False
    assert payload.state == PayloadState.UNKNOWN
    print("  ✓ activate from UNKNOWN rejected (state unchanged)")

    # Can't deactivate from UNKNOWN (handled, logs warning)
    payload2 = SplashPayload("trans_1", sim_mode=True)
    result = payload2.deactivate()
    assert result is True  # returns True but warns
    print("  ✓ deactivate from UNKNOWN: handled gracefully")

    print("  ✓ test_invalid_state_transitions passed")


def test_emergency_stop_timing():
    """Emergency stop must complete within 50ms."""
    payload = SplashPayload("estop_0", sim_mode=True)
    payload.initialize()
    payload.activate()

    assert payload.state == PayloadState.ACTIVE

    t0 = time.perf_counter()
    result = payload.emergency_stop()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result is True
    assert payload.state == PayloadState.FAULTED
    assert elapsed_ms < 50.0, f"Emergency stop took {elapsed_ms:.1f}ms > 50ms limit"

    print(f"  ✓ emergency_stop: {elapsed_ms:.1f}ms (limit 50ms)")
    print("  ✓ test_emergency_stop_timing passed")


def test_health_check():
    """Health check returns valid PayloadHealth."""
    payload = SplashPayload("health_0", sim_mode=True)
    payload.initialize()
    payload.activate()

    health = payload.health_check()
    assert isinstance(health, PayloadHealth)
    assert health.status == "OK"
    assert health.simulated is True
    assert health.uptime_s >= 0
    assert "pan_angle_deg" in health.payload_specific
    assert "pump_active" in health.payload_specific

    print("  ✓ health_check: valid PayloadHealth")
    print("  ✓ test_health_check passed")


def test_reservoir_tracking():
    """Reservoir decreases with each fire."""
    payload = SplashPayload("res_0", sim_mode=True)
    payload.initialize()
    payload.activate()

    result = payload.execute_command("get_status", {})
    assert result.data["reservoir_ml"] == 15.0
    assert result.data["fire_count"] == 0

    # Fire 10 × 500ms bursts = 5ml total
    for i in range(10):
        payload.execute_command("fire", {"duration_ms": 500})

    result = payload.execute_command("get_status", {})
    assert result.data["fire_count"] == 10
    assert result.data["reservoir_ml"] == 10.0  # 15 - 5 = 10
    assert round(result.data["total_fired_ml"], 1) == 5.0

    print("  ✓ reservoir tracked correctly: 15 → 10ml after 10 shots")
    print("  ✓ test_reservoir_tracking passed")


def test_deadzone_config():
    """Deadzone can be configured via command."""
    payload = SplashPayload("dz_0", sim_mode=True)
    payload.initialize()

    # Default deadzone (queries allowed when READY)
    result = payload.execute_command("get_status", {})
    assert result.data["deadzone_px"] == 30

    # Set new deadzone (non-query, needs ACTIVE)
    payload.activate()
    result = payload.execute_command("set_deadzone", {"deadzone_px": 15})
    assert result.success is True
    assert result.data["deadzone_px"] == 15

    result = payload.execute_command("get_status", {})
    assert result.data["deadzone_px"] == 15

    print("  ✓ deadzone configured: 30 → 15px")
    print("  ✓ test_deadzone_config passed")


# =========================================================================
# Registry tests
# =========================================================================

def test_registry_scan_sim():
    """Registry scans and discovers payloads in SIM_MODE."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )

    discovered = registry.scan_bus()
    assert len(discovered) == 1
    assert discovered[0].payload_type == "splash"
    assert discovered[0].payload_id == "splash_0"

    # Verify payload is registered and READY
    payload = registry.get("splash_0")
    assert payload is not None
    assert payload.state == PayloadState.READY

    print("  ✓ registry.scan_bus: 1 payload discovered")
    print("  ✓ test_registry_scan_sim passed")


def test_registry_activate_deactivate():
    """Registry activates and deactivates payloads."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )
    registry.scan_bus()

    # Activate
    assert registry.activate("splash_0") is True
    payload = registry.get("splash_0")
    assert payload.state == PayloadState.ACTIVE

    # Deactivate
    assert registry.deactivate("splash_0") is True
    assert payload.state == PayloadState.READY

    print("  ✓ registry activate/deactivate cycle")
    print("  ✓ test_registry_activate_deactivate passed")


def test_registry_command_dispatch():
    """Registry routes commands to correct payload."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )
    registry.scan_bus()
    registry.activate("splash_0")

    # Dispatch fire command through registry
    result = registry.execute("splash_0", "fire", {"duration_ms": 300})
    assert result.success is True
    assert result.data["fire_count"] == 1

    # Unknown payload ID
    result = registry.execute("nonexistent", "fire")
    assert result.success is False
    assert "not registered" in result.message

    print("  ✓ registry command dispatch works")
    print("  ✓ test_registry_command_dispatch passed")


def test_registry_power_budget():
    """Registry enforces power budget."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
        power_budget_ma=500,  # Too low for Splash (1500mA)
    )
    registry.scan_bus()

    try:
        registry.activate("splash_0")
        assert False, "Should have raised PayloadPowerLimitError"
    except PayloadPowerLimitError as e:
        assert "exceed budget" in str(e)
        print(f"  ✓ power budget enforced: {e}")

    print("  ✓ test_registry_power_budget passed")


def test_registry_health_status():
    """Registry can query all payload health."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )
    registry.scan_bus()
    registry.activate("splash_0")

    status = registry.health_status_all()
    assert "splash_0" in status
    assert status["splash_0"]["state"] == "ACTIVE"
    assert status["splash_0"]["health"]["status"] == "OK"

    print("  ✓ registry.health_status_all works")
    print("  ✓ test_registry_health_status passed")


def test_registry_list_methods():
    """Registry list_all, list_active, list_ready work correctly."""
    registry = PayloadRegistry(
        known_payloads=[SplashPayload],
        sim_mode=True,
    )
    registry.scan_bus()

    # Before activation: ready
    assert len(registry.list_all()) == 1
    assert len(registry.list_ready()) == 1
    assert len(registry.list_active()) == 0

    # After activation: active
    registry.activate("splash_0")
    assert len(registry.list_all()) == 1
    assert len(registry.list_ready()) == 0
    assert len(registry.list_active()) == 1

    print("  ✓ registry list methods correct")
    print("  ✓ test_registry_list_methods passed")


# =========================================================================
# Runner
# =========================================================================

def run_all():
    """Run all tests and report results."""
    tests = [
        test_splash_metadata,
        test_lifecycle_sim,
        test_command_requires_active,
        test_invalid_state_transitions,
        test_emergency_stop_timing,
        test_health_check,
        test_reservoir_tracking,
        test_deadzone_config,
        test_registry_scan_sim,
        test_registry_activate_deactivate,
        test_registry_command_dispatch,
        test_registry_power_budget,
        test_registry_health_status,
        test_registry_list_methods,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  Payload Interface Tests")
    print("=" * 60)
    print()

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} FAILED: {e}")

    print()
    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
