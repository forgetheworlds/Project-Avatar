# Calibration cadence

Out of scope: factory QC for new aircraft classes beyond quad — spec section 13.

## When to calibrate

| Event | Sensors |
|-------|---------|
| New FC flash | Accel, gyro, mag, level |
| First hardware boot | Accel, gyro, mag, RC, motor dirs |
| After hard landing / crash inspection | Accel, mag, level |
| Monthly idle storage | Gyro quick check (optional accel level) |
| Major firmware bump | Re-run `verify.py` then full accel/mag |

## Commands (headless)

Accel + gyro + mag + level (interactive prompts suppressed if script supports `--batch`):

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors accel,gyro,mag,level
```

Expected tail:

```
calibration: accel DONE
calibration: gyro DONE
calibration: mag DONE
calibration: level DONE
result: PASS
```

RC calibration:

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors rc
```

Motor direction test (props off):

```bash
python3 hardware/px4/calibrate.py --airframe mark4_7in --sensors motor_dirs
```

## Post-calibration verify

```bash
python3 hardware/px4/verify.py --airframe mark4_7in
```

Expected: `verify: PASS`.
