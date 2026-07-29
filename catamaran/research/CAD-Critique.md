# CAD Critique — `hardware/cad` vs `hardware/fable-cad`

**Date:** 2026-07-29  
**Verdict:** Print from **`fable-cad/`**. Treat **`cad/`** as a superseded prototype tree that should not be sent to a printer.

---

## 1. What exists

| Tree | Role | Parts | Status |
|------|------|-------|--------|
| `hardware/cad/` | Earlier agent pass against `CAD_SPEC.md` | bow/mid/stern, single deck_lid, electronics_tray, grate/nozzle/impeller/motor_mount/servo_bracket, water_cannon | Incomplete jet system; several geometry bugs |
| `hardware/fable-cad/` | Redesign against Kimi plan + `DESIGN.md` | 3 hull segs, 2 deck lids, 2 trays, full jet pump stack, cannon + optional turret | Preferred print set; mating fixes applied 2026-07-29 |

Also in the folder (not CAD files, but related):

- `CAD_SPEC.md` — self-contained agent brief that **encoded several of the bugs below**
- `DESIGN.md` — fable contract (authoritative for print)
- `research/Fable-Critique-Report.md` — research/assumption critique (pins, IMU, runtime)
- Firmware / BOM / CLAUDE.md still partly mirrored the **old** pin map and incomplete part list (updated alongside this doc)

---

## 2. Critical failures in `hardware/cad/` (do not print)

### 2.1 Jet drive is not a jet drive
`cad/hull/hull_stern.py` cuts a **top-side pocket** (~45×50×25 mm down from the deck). There is **no bottom intake, no tunnel, no stator plate**. An impeller in that pocket sits above the waterline and pumps air.

`fable-cad` replaces this with a bolt-in `pump_housing` (bottom mouth → Ø28 tunnel → exit flange), `nozzle_plate` with stator, steerable `nozzle`, and matching stern intake pad/aperture.

### 2.2 Flood chamber cannot flood
Old stern: chamber top at **Z≈27**, flood hole at **Z=40**. The hole is *above* the chamber. Self-righting fails by construction.

`fable-cad` places a ~120 cc port chamber with the flood hole through the port side at **Y=70, Z=50**, chamber sealed under Z≈64. (Still needs a small air vent in practice — see research critique.)

### 2.3 Bow is not wave-piercing
Old bow uses a **constant full beam** extrusion plus a single rake wedge. In plan view the waterline stays wide to the stem → barge entry.

`fable-cad` lofts stations with beam scales 0.05→1.00 so the entry actually narrows.

### 2.4 Wrong print orientation + weak layer axis
`CAD_SPEC` / old sources say print **keel-down**. That puts the 20° V at a severe overhang and puts layer lines **across** the hull (weak under bending).

`fable-cad` prints segments **upright on the joint face** (lengthwise layers, zero supports) per Kimi.

### 2.5 Impeller / shaft mismatch
Old impeller used a **4 mm press-fit** narrative against a 2838 motor whose shaft is **3.175 mm** — either won’t fit or spins free.

`fable-cad` uses 3.175→4 coupler + 4 mm stub + Ø4.05 slip bore + set screw.

### 2.6 Joint strategy too weak for waves
Old: dovetail-only. RC consensus (and Kimi): snap/interlock-only PLA fails under shear.

`fable-cad`: pins + **4× M3 self-tap** through bulkheads + silicone face seal.

### 2.7 Missing systems
`cad/` has no:

- pump housing / intake duct / stator plate  
- separate mid + stern deck lids with wet-well access  
- battery tray (keel saddle)  
- cannon wet-well in stern  
- optional pan turret (Kimi: fixed-forward v1, turret later)

`fable-cad` has all of the above; turret mounts on the mid-deck pad via Ø44 PCD without redesigning the cannon (Ø32 PCD shared).

### 2.8 Hydrostatics / print settings in the spec
Old beam 100 / depth 60 with deep chine burial at realistic weight; **80% infill / 0.15 mm everywhere** wastes time and plastic. Watertightness is **perimeters + epoxy**, not dense infill.

`fable-cad`: 120×72 deep-V, ~38 mm draft @ ~1.15 kg, 12% gyroid + 5–6 walls.

---

## 3. Remaining issues in `fable-cad/` (print with eyes open)

These are **known, manageable** — not reasons to go back to `cad/`.

| Issue | Severity | Mitigation |
|-------|----------|------------|
| Deck lip was 111 mm (would not fit ~106.6 opening) | Fixed 2026-07-29 → **105 mm** | Regenerated STEPs/STLs |
| Servo bracket slots ±19 vs stern pilots at +4/+32 (28 mm span) | Fixed → **±14** | Regenerated |
| Flood chamber airlock (single hole) | Medium | Drill ~2 mm vent near chamber top after print |
| Self-tap M3 into PLA lid bosses | Medium (wear) | Brass heat-set inserts in v2 if lids open often |
| No cooling-water barb on pump housing | Low at patrol loads | Add barb in v2 before sustained full throttle |
| “Zero penetrations” marketing | Doc only | Honest claim: no below-waterline rotating shaft seal |
| Full assembly STEP not generated | Low | Parts mate by documented PCDs; assemble in slicer/viewer |
| Jetdrive/deck snapshot coverage thinner than hull | Low | Viewer + STLs are the print path |
| Cannon range on 5 V pump ~1.5–3 m | Expectation | Keep; upgrade pump later if wanted |

---

## 4. Folder-level critique (non-CAD, but blocks “ready”)

| Area | Finding |
|------|---------|
| **Two CAD trees** | Confusing for a friend printing. Prefer marking `cad/` DEPRECATED or deleting after backup. |
| **CLAUDE.md / BOM / firmware pins** | Classic ESP32 map (GPIO 22 missing on S3; 34/35 bad on N8R8). Corrected to S3-safe map in the same pass as this critique. |
| **BOM printed-parts list** | Still described 2 hull segs + grate as separate part; fable has 3 segs, integral grate, mid+stern lids, trays, turret. Updated to match fable-cad. |
| **Firmware** | Architecture sound (50 Hz PID / 2 s failsafe / phone hotspot). Heading-hold on MPU-6050 alone will drift — add compass or GPS COG (research critique). |
| **Phone app / GCS** | Present as stubs; fine for Phase 0 CAD. Not required to print. |
| **Docs** | MASTER_BRIEFING + ARCHITECTURE align with Kimi; CAD_SPEC does not — supersede with DESIGN.md. |

---

## 5. Recommendation

1. **Print only** `catamaran/hardware/fable-cad/stl/*.stl` (or the matching `.step` for CAM tools).  
2. **Do not print** anything under `hardware/cad/` for the lake boat.  
3. Keep `DESIGN.md` as the contract; keep this critique + `Fable-Critique-Report.md` as the “why.”  
4. First print batch: small parts (impeller×2, nozzle, bracket, trays) → then hull segments → lids last after dry-fit.

### Print readiness checklist

- [x] Complete fable part set (STEP)  
- [x] Mating lip / servo slot fixes  
- [x] STL export folder  
- [ ] Visual sign-off in CAD Viewer (open `fable-cad/`)  
- [ ] Friend printer dry-fit of mid↔stern joint + pump flange on intake pad  
- [ ] Epoxy + foam bow + bathtub flip test before lake  
