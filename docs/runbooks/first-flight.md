# First flight (tethered to short translation)

This procedure assumes: Mark4 7" + Pixhawk 6C Mini + Pi stack, outdoor calm wind, spotter present, RC transmitter programmed with RTL on switch. **No** NOTAM/weather automation (spec section 13).

## A. Tether + ground idle

1. **Environment check:** props off for bench checks; on field, props on, tether attached to airframe frame (not ESC leads).
2. **Command:**

```bash
python3 hardware/px4/preflight.py --airframe mark4_7in
```

Expected: `overall: PASS`.

3. **MCP:** `get_drone_status` — `armed: false`, GPS `fix_type` >= 3, battery healthy.
4. **Abort if:** GPS no fix after 120 s, compass variance warnings, preflight FAIL, tether tangled.

## B. Hover 1 m x 10 s

1. **Environment:** clear 5 m radius, people outside cordon.
2. **MCP:** `arm` then `set_flight_mode` / `arm_and_takeoff` per tool policy — `altitude_m: 1.0`.
3. **Observe:** altitude hold within +/-0.3 m; no yaw windup; tether slack not pulling craft sideways.
4. **Abort:** oscillation >+/-0.5 m sustained 3 s, unusual vibration, RC override invoked.

## C. Hover 3 m x 30 s

1. **MCP:** climb to `3.0` m AGL (tool-specific: `goto_local_ned` with `z_m` or `arm_and_takeoff` if still on ground—choose the primitive your W2a tools expose; document the exact JSON you used in the flight log).
2. **Observe:** stable hover, Guardian no alerts.
3. **Abort:** battery sag below configured RTL threshold unexpectedly, tether tension near structural limit.

## D. First 5 m translation

1. **MCP:** `set_velocity_body` `{forward: 0.5, right: 0, down: 0, yawspeed: 0, duration_s: 10}` then stop with zero velocity (repeat until ~5 m horizontal displacement confirmed via telemetry).
2. **Observe:** no heading drift beyond acceptable; obstacle clearance manually verified.
3. **Abort:** tether angle >45 degrees, proximity to people, GPS dropout.

## E. RTL

1. **MCP:** `rtl()` or RC RTL switch.
2. **Observe:** climb-turn-home pattern per PX4 params; soft landing within 2 m of home.
3. **Abort:** if RTL path intersects obstacles—switch RC to manual Loiter and land visually (training mode).

## Post-flight

Export `flight_recorder` JSONL if enabled.
