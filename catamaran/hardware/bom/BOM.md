# Project Boat — Bill of Materials (fable-cad aligned)

## Design Summary

- **Type:** Monohull deep-V with 3D-printed jet drive
- **Length:** 480 mm (3 × 160 mm segments)
- **CAD:** `hardware/fable-cad/` (`DESIGN.md`)
- **Control:** ESP32-S3 WiFi → phone PWA (Phase 1), LLM agent (Phase 2)
- **Power:** 3S 2200mAh LiPo (upgrade to 5200mAh)
- **Self-righting:** Flood chamber + foam-filled bow
- **Budget Target:** ~$130–160 CAD (friend prints)

## Cost Summary

| Category | Friend Print | Notes |
|----------|-------------|-------|
| Printed parts (PLA) | ~$8–12 | ~400–500 g incl. spare impeller |
| Motor + ESC combo | $38 | Surpass KK 2838 + 35A + jacket |
| Battery + charger | $30–41 | 3S 2200 + USB balance |
| Electronics | $21–25 | ESP32-S3 + IMU + compass + servo + sensors |
| Jet hardware | $6–10 | 4 mm shaft + 3.175→4 coupler |
| Water cannon | $11 | 5V pump + MOSFET + tubing |
| Waterproofing | $23 | XTC-3D + silicone |
| Hardware & misc | $12–15 | M3 self-taps, neoprene tape, foam |
| **Total** | **~$150–175** | ~$120 if battery+charger already owned |

---

## Printed Parts (`fable-cad/print/`)

All 15 STLs are also copied to **`hardware/fable-cad/print/`** for one-folder slicer import.

| Part | File | Est. Mass | Notes |
|------|------|-----------|-------|
| Hull bow | `hull_bow.stl` | ~110g | Foam-filled sealed compartment |
| Hull mid | `hull_mid.stl` | ~105g | Battery + electronics bay |
| Hull stern | `hull_stern.stl` | ~135g | Jet intake, flood chamber, wet-well |
| Deck mid | `deck_mid.stl` | ~45g | Cannon/turret pad |
| Deck stern | `deck_stern.stl` | ~40g | Wet-well access hole |
| Pump housing | `pump_housing.stl` | ~55g | Integral grate + intake flange |
| Impeller | `impeller.stl` | ~5g | Print **2** (consumable) |
| Nozzle plate | `nozzle_plate.stl` | ~20g | Stator + pivot lugs |
| Nozzle | `nozzle.stl` | ~10g | Steerable |
| Servo bracket | `servo_bracket.stl` | ~6g | SG90 |
| Electronics tray | `electronics_tray.stl` | ~15g | ESP32 + ESC + IMU |
| Battery tray | `battery_tray.stl` | ~25g | Keel saddle |
| Water cannon | `water_cannon.stl` | ~18g | Fixed or on turret |
| Turret base (opt) | `turret_base.stl` | ~20g | Pan SG90 |
| Turret platform (opt) | `turret_platform.stl` | ~8g | Cannon mounts here |

**Print settings:** hull upright on joint face — 0.2 mm, 5–6 walls, 12% gyroid, no supports. Impeller 0.12–0.15 mm, 100% infill. Seal wet surfaces with XTC-3D.

---

## Motor + ESC

| Part | Qty | Price (CAD) | Source |
|------|-----|-------------|--------|
| Surpass Hobby KK 2838 + 35A waterproof ESC + water-cooling jacket | 1 | $38 | qwinout.com |

At patrol loads the jacket is optional until a cooling tap is added to the pump housing (v2).

---

## Battery + Charger

| Part | Qty | Price (CAD) | Notes |
|------|-----|-------------|-------|
| 3S 2200mAh 45C LiPo XT60 | 1 | $18–25 | ~25–40 min realistic patrol on jet (not 47) |
| 3S 5200mAh (upgrade) | 1 | $42 | ~2× patrol |
| 2S/3S USB balance charger | 1 | $12–16 | |

---

## Electronics

| Part | Qty | Price (CAD) | Notes |
|------|-----|-------------|-------|
| ESP32-S3-WROOM N8R8 USB-C | 1 | $7 | |
| MPU-6050 | 1 | $4 | Rate / attitude |
| QMC5883L compass | 1 | $2 | **Needed** for absolute heading hold |
| SG90 (nozzle) | 1 | $4 | +1 if turret |
| Water ingress sensor | 1 | $2 | |
| NEO-6M GPS (optional) | 1 | $10 | RTH / COG heading backup |
| XT60 + silicone wire | 1 | $4 | |

### Pin map (ESP32-S3)

| GPIO | Function |
|------|----------|
| 13 | ESC PWM |
| 12 | Nozzle servo |
| 14 | Pump MOSFET |
| 4 | Battery ADC |
| 5 | Water ADC |
| 8 / 9 | I2C SDA / SCL |
| 17 / 18 | GPS UART2 (optional) |

Do **not** use GPIO 22, 34, or 35 on this board.

---

## Jet drivetrain hardware (purchased)

| Part | Qty | Price (CAD) | Notes |
|------|-----|-------------|-------|
| 4 mm SS shaft ~80 mm | 1 | $2–3 | Impeller stub |
| 3.175 → 4 mm rigid coupler | 1 | $3–5 | Motor → shaft |
| M3 set screws | pack | $2 | Impeller + coupler |

---

## Water Cannon

| Part | Qty | Price (CAD) | Notes |
|------|-----|-------------|-------|
| 5V mini submersible pump 80–120 L/h | 1 | $4 | Sits in stern wet-well |
| MOSFET module | 1 | $2 | |
| 6 mm ID silicone tube ~0.5 m | 1 | $3 | Matches cannon barb |
| Check valve | 1 | $2 | |

Expect ~1.5–3 m stream range. Aim with boat (or turret).

---

## Waterproofing & hardware

| Part | Qty | Price (CAD) |
|------|-----|-------------|
| XTC-3D epoxy | 1 | $15 |
| Silicone sealant | 1 | $5 |
| 2 mm neoprene/foam tape | 1 | $3 |
| M3 self-tapping assortment | 1 | $4 |
| M3×16 machine screws (transom stack) | 8 | $2 |
| Pool noodle / EPS scrap (bow foam) | 1 | $3 |
| Rubber drain stopper ~8 mm | 1 | $1 |

---

## Assembly order (short)

1. Dry-fit bow↔mid↔stern joints; silicone + M3 self-taps.  
2. Bolt pump housing to intake pad; clamp nozzle plate through transom.  
3. Install motor, coupler, shaft, impeller, nozzle, servo + pushrod.  
4. Foam-fill bow; seal fill hole. Drill ~2 mm flood-chamber air vent near top.  
5. Mount trays, lids (neoprene tape), cannon (deck pad or turret).  
6. Epoxy coat wet interiors; paper-towel leak test → bathtub flip test → pond.
