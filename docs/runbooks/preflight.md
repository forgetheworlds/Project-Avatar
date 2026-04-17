# Preflight checklist (bench FC)

Operator goal: confirm PX4 safety parameters, sensors, and MAVLink path before arming outdoors.

Out of scope: airspace, NOTAM, weather forecasts — see project spec section 13.

## 0. Environment

```bash
cd /path/to/Project-Avatar
source .venv/bin/activate
export AVATAR_HITL_TARGET=fc_bench
```

## 1. Dry-run (no USB required)

Command:

```bash
python3 hardware/px4/preflight.py --dry-run --airframe mark4_7in
```

Expected stdout (representative):

```
dry_run: true
airframe: mark4_7in
overlay: hardware/px4/airframes/mark4_7in.params
result: PASS
notes: no serial open in dry-run mode
```

## 2. Live USB check (Pixhawk on bench)

Connect USB. Confirm symlink:

```bash
ls -l /dev/pixhawk
```

Expected:

```
lrwxrwxrwx 1 root dialout ... /dev/pixhawk -> ttyACM0
```

## 3. Full preflight

Command:

```bash
python3 hardware/px4/preflight.py --airframe mark4_7in
```

Expected (representative tail):

```
serial: /dev/pixhawk @ 921600
param_verify: PASS
estimator: PASS
rc: WARN or PASS per configuration
battery: PASS (bench PSU)
overall: PASS
```

Abort if `overall: FAIL` or any `FAIL` line appears—do not arm.

## 4. MCP cross-check (optional)

```bash
python3 -m avatar.mcp_server
```

In agent session, call read-only `preflight_checklist` tool if exposed; expect JSON echoing same PASS/FAIL summary.

## 5. HITL pytest gate

```bash
python3 -m pytest tests/hitl -m preflight --run-hitl -rs
```

Expected: `test_preflight_cli_passes` **passed** on hardware; skipped tests show explicit hardware reasons only for non-preflight markers.
