# Project Boat — Bill of Materials (purchased only)

Everything you need to **buy**. Printed parts live in `hardware/cad/print/` and are
not listed here (friend’s printer / your filament).

CAD contract: `hardware/cad/docs/DESIGN.md`  
Engineering brief: `hardware/cad/docs/ENGINEERING_BRIEF.md`  
Print handoff: `hardware/cad/docs/PRINT_RELEASE.md`

**Budget target:** ~$130–175 CAD all-new (~$100–130 if battery + charger already owned)

---

## Cost summary

| Category | Est. CAD | Notes |
|----------|----------|-------|
| Motor + ESC | $38 | Surpass KK 2838 + 35A + cooling jacket |
| Battery + charger | $30–41 | 3S 2200 + USB balance (skip if owned) |
| Electronics | $23–35 | ESP32-S3, IMU, compass, servo(s), sensors |
| Jet drivetrain hardware | $15–25 | Shaft, coupler, bearings, seals, bushing |
| Water cannon plumbing | $11–14 | Pump, MOSFET, tubing, check valve |
| Waterproofing & fasteners | $25–30 | Epoxy, silicone, M3, tape, foam |
| Steering linkage | $5–8 | Pushrod + bellows |
| **Total** | **~$147–191** | Prototype build, AliExpress / hobby shops |

---

## Propulsion (purchased)

| Part | Qty | Est. CAD | Notes |
|------|-----|----------|-------|
| Surpass Hobby KK **2838** + **35A** waterproof ESC + water-cooling jacket | 1 | $38 | qwinout / AliExpress combo |
| 3S **2200 mAh** 30–45C LiPo, XT60 | 1 | $18–25 | Design pack; upgrade 5200 later |
| 2S/3S USB balance charger | 1 | $12–16 | |
| **4 mm** stainless shaft, buy ~120 mm cut to fit | 1 | $3–5 | Impeller stub through cartridge |
| **3.175 → 4 mm** rigid coupler | 1 | $3–5 | Motor shaft → jet shaft |
| Front sealed bearing **4×8×3** (or 4×9×4) | 1–2 | $3–5 | Shaft cartridge / front support |
| Aft bearing **MR74ZZ** (4×7×2.5) | 1 | $2–3 | Stator hub seat |
| Rotary lip seals **4×8×3** | 2 | $3–5 | Grease cavity between seals |
| Flanged brass/PTFE bushing Ø7 OD / Ø4.2 ID (optional spare) | 1 | $2 | Front wall pocket if not using cartridge bearing |
| M3 set screws | pack | $2 | Coupler + impeller |

---

## Steering & cannon

| Part | Qty | Est. CAD | Notes |
|------|-----|----------|-------|
| **SG90** micro servo | 1 | $4 | Nozzle steering (+1 if using turret) |
| RC pushrod (~1.5–2 mm) + clevis | 1 | $3 | Servo → nozzle horn |
| RC pushrod **bellows** / boot | 1 | $2–3 | Fits over printed `pushrod_gland` barb |
| 5V mini submersible pump 80–120 L/h | 1 | $4 | Stern wet-well → cannon |
| Logic-level MOSFET module | 1 | $2 | Pump switch (GPIO 14) |
| Silicone tube **6 mm ID** ~0.5–1 m | 1 | $3 | Matches cannon barb |
| Inline check valve (6 mm) | 1 | $2 | Reduces siphon drip |

---

## Electronics (onboard)

| Part | Qty | Est. CAD | Notes |
|------|-----|----------|-------|
| **ESP32-S3** DevKit USB-C (N8R8 PSRAM preferred) | 1 | $7 | Do **not** use GPIO 22 / 34 / 35 |
| **MPU-6050** | 1 | $4 | Rate / attitude |
| **QMC5883L** compass | 1 | $2 | Absolute heading hold |
| Water / rain ingress sensor | 1 | $2 | Bilge wet detect |
| NEO-6M GPS (optional) | 1 | $10 | RTH / COG backup |
| XT60 pigtails + 16–18 AWG silicone wire | kit | $4 | ESC + battery |
| Heat-shrink, Dupont, zip-ties | kit | $3 | |

### ESP32-S3 pin map

| GPIO | Function |
|------|----------|
| 13 | ESC PWM |
| 12 | Nozzle servo |
| 14 | Pump MOSFET |
| 4 | Battery ADC (divider) |
| 5 | Water ADC |
| 8 / 9 | I2C SDA / SCL |
| 17 / 18 | GPS UART2 (optional) |

---

## Sealing, fasteners, foam

| Part | Qty | Est. CAD | Notes |
|------|-----|----------|-------|
| **XTC-3D** (or equivalent) epoxy coating | 1 | $15 | Wet interiors / tunnel |
| Marine silicone sealant | 1 | $5 | Joints + gasket faces |
| 2 mm neoprene / foam tape | 1 | $3 | Deck lid seals |
| M3 self-tapping assortment | 1 | $4 | Hull joints, lids, house |
| M3×8 / M3×10 / M3×12 / M3×16 machine screws | assortment | $4 | Transom stack, fins, plates |
| M3 nuts / washers (small pack) | 1 | $2 | Where through-bolting |
| Pool noodle / EPS scrap | 1 | $3 | Bow foam fill |
| Rubber drain stopper ~Ø8 | 1 | $1 | Stern drain |

---

## Optional / later

| Part | Qty | Est. CAD | Notes |
|------|-----|----------|-------|
| 3S **5200 mAh** LiPo | 1 | $42 | Longer patrol |
| Second SG90 | 1 | $4 | Turret pan |
| PTFE / acetal Ø washer ~Ø8–10 | 2 | $2 | Prefer over printed nozzle thrust washers |
| PETG / ASA filament | ~0.5–1 kg | $20–35 | Friend prints — not in “buy hardware” total above |

---

## Assembly order (buy kit → dry fit)

1. Dry-fit bow ↔ mid ↔ stern; silicone + M3.  
2. Install shaft cartridge / bearings / seals; motor + coupler + impeller.  
3. Bolt pump housing to intake pad; clamp nozzle plate through transom.  
4. Nozzle + servo + pushrod + bellows on gland.  
5. Foam-fill bow; install drain plug / foam-port plug.  
6. Trays, electronics, lids (neoprene), cannon hose from wet-well.  
7. Epoxy wet surfaces → paper-towel leak test → bathtub flip → pond.

Printed STL checklist: see `hardware/cad/docs/PRINT_RELEASE.md` and `hardware/cad/print/`.
