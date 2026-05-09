"""
test_integration.py — End-to-end integration: CV pipeline → MCP → payload.

Validates the full chain without hardware:
    1. CV targeting produces pan/tilt angles from bbox
    2. Angles routed through MCP-style payload registry
    3. Payload (Splash) aims and fires
    4. Reservoir tracking works across engagement cycle
    5. State transitions: FLYING → ORBITING → ENGAGING → fire

Run:
    python3 splash/test_integration.py

Project Avatar — Integration validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_targeting_to_payload():
    """Simulate CV bbox → targeting → payload aim → fire."""
    from splash.cv.targeting import TargetingSystem

    ts = TargetingSystem(frame_width=1280, frame_height=720, fire_distance_m=10.0, aim_deadzone_px=80)
    bbox = (540, 150, 740, 550)  # Centered, 400px tall (close person)
    result = ts.calculate(bbox)

    pan = result["pan_angle"]
    tilt = result["tilt_angle"]
    fire_cmd = result["fire_command"]
    dist = result["distance_estimate"]

    print(f"  CV → pan={pan:.1f}° tilt={tilt:.1f}° dist={dist:.1f}m fire={fire_cmd}")

    assert -90 <= pan <= 90, f"Pan {pan} out of range"
    assert -90 <= tilt <= 90, f"Tilt {tilt} out of range"
    assert fire_cmd, f"Should fire, got fire_command={fire_cmd}"

    # Route through payload
    from splash.payload import SplashPayload

    payload = SplashPayload("int_test", sim_mode=True)
    payload.initialize()
    payload.activate()

    aim_r = payload.execute_command("aim", {"pan_deg": pan, "tilt_deg": tilt})
    assert aim_r.success, f"Aim failed: {aim_r.message}"

    fire_r = payload.execute_command("fire", {"duration_ms": 300})
    assert fire_r.success, f"Fire failed: {fire_r.message}"
    assert fire_r.data["fire_count"] == 1

    status_r = payload.execute_command("get_status", {})
    assert status_r.data["reservoir_ml"] < 15.0

    print(f"  ✓ CV→Payload: aim({pan:.0f}°,{tilt:.0f}°) → fire → {status_r.data['reservoir_ml']:.1f}ml")
    return True


def test_full_engagement_cycle():
    """Simulate complete engagement: detect → track → aim → fire × N."""
    from splash.cv.targeting import TargetingSystem
    from splash.payload import SplashPayload

    payload = SplashPayload("engage_test", sim_mode=True)
    payload.initialize()
    payload.activate()

    ts = TargetingSystem(frame_width=1280, frame_height=720, aim_deadzone_px=50, fire_distance_m=15.0)
    shots = 0

    for i in range(10):
        progress = i / 9.0
        cx = int(640 + 200 * (1 - progress))
        cy = int(360 + 50 * (1 - progress))
        bbox = (cx - 100, cy - 200, cx + 100, cy + 200)  # Bigger bbox = closer

        result = ts.calculate(bbox)
        if result["fire_command"]:
            payload.execute_command("aim", {
                "pan_deg": result["pan_angle"],
                "tilt_deg": result["tilt_angle"],
            })
            fr = payload.execute_command("fire", {"duration_ms": 200})
            if fr.success:
                shots += 1

    status = payload.execute_command("get_status", {})
    assert shots > 0, f"No shots fired in 10 frames"
    assert status.data["reservoir_ml"] < 15.0

    ml_per_shot = status.data["total_fired_ml"] / shots if shots > 0 else 0
    print(f"  ✓ Engagement: {shots} shots in 10 frames, {ml_per_shot:.1f}ml/shot, "
          f"remaining={status.data['reservoir_ml']:.1f}ml")
    return True


def test_state_machine_with_payload():
    """Verify state transitions integrate with payload lifecycle."""
    from splash.control.state_machine import StateMachine, DroneState
    from splash.payload import PayloadRegistry, SplashPayload

    sm = StateMachine()
    registry = PayloadRegistry(known_payloads=[SplashPayload], sim_mode=True)
    registry.scan_bus()
    registry.activate("splash_0")

    sm.set_arming()
    assert sm.state == DroneState.ARMED
    sm.set_taking_off()
    sm.set_flying()
    assert sm.state == DroneState.FLYING

    sm.set_orbiting()
    assert sm.state == DroneState.ORBITING
    assert registry.get("splash_0").state.name == "ACTIVE"

    sm.set_engaging()
    assert sm.state == DroneState.ENGAGING
    result = registry.execute("splash_0", "fire", {"duration_ms": 200})
    assert result.success

    sm.set_returning()
    registry.deactivate("splash_0")
    assert registry.get("splash_0").state.name == "READY"

    sm.set_idle()
    assert sm.state == DroneState.IDLE

    print(f"  ✓ State machine: IDLE→ARMED→FLYING→ORBITING→ENGAGING→RETURNING→IDLE")
    return True


def test_cv_targeting_edge_cases():
    """Test targeting edge cases: off-center, far, empty."""
    from splash.cv.targeting import TargetingSystem
    import numpy as np

    ts = TargetingSystem(frame_width=1280, frame_height=720)

    # Far target — should NOT fire
    far_bbox = (635, 355, 645, 365)  # tiny bbox = far away
    r = ts.calculate(far_bbox)
    assert not r["fire_command"], f"Far target should not fire, got: {r}"
    print(f"  ✓ Far target: dist={r['distance_estimate']:.1f}m fire={r['fire_command']}")

    # Off-center target — should NOT fire
    off_bbox = (100, 100, 300, 500)  # left edge
    r = ts.calculate(off_bbox)
    assert not r["fire_command"], f"Off-center should not fire, got: {r}"
    print(f"  ✓ Off-center: offset={r['center_offset']} fire={r['fire_command']}")

    # Clamped angles
    extreme_bbox = (0, 0, 10, 10)
    r = ts.calculate(extreme_bbox)
    assert -90 <= r["pan_angle"] <= 90, f"Pan not clamped: {r['pan_angle']}"
    assert -45 <= r["tilt_angle"] <= 45, f"Tilt not clamped: {r['tilt_angle']}"
    print(f"  ✓ Clamped: pan={r['pan_angle']}° tilt={r['tilt_angle']}°")

    return True


# =========================================================================
# Runner
# =========================================================================

def main():
    tests = [
        ("CV targeting → payload fire", test_targeting_to_payload),
        ("Full engagement cycle", test_full_engagement_cycle),
        ("State machine + payload", test_state_machine_with_payload),
        ("CV targeting edge cases", test_cv_targeting_edge_cases),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  Project Avatar — Integration Tests")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  ✓ {name}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {name}: {e}")
            import traceback
            traceback.print_exc()
        print()

    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
