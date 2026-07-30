# Project Boat — Fable CAD Design (v1)

> Authoritative design contract for all parts in `fable-cad/`. Implements **Kimi's plan**
> (deep-V monohull, printed jet drive, flood-chamber self-righting, bolted segment joints,
> pump-in-lake water cannon).
> All units mm. Every part is a build123d `gen_step() -> bd.Part`.

## Design notes (vs earlier drafts)

1. Complete bolt-in jet pump: bottom intake ramp, Ø28 tunnel, integral motor mount + grate, stator in the transom plate, steerable nozzle.
2. Lofted wave-piercing bow (plan-view taper; deadrise sharpens toward stem).
3. Flood chamber ~120 cc with side flood hole that can actually fill the chamber.
4. Bolted bulkhead flanges + alignment pins + silicone (not dovetail-only).
5. Impeller: 3.175→4 coupler + 4 mm stub shaft, Ø4.05 slip bore + M3 set screw (2838 shaft is 3.175 mm).
6. Hull segments print upright on a joint face (lengthwise layers, zero supports).
7. Beam 120 / depth 72; static draft ≈ 38 mm at ~1.15 kg all-up.
8. 10–15% gyroid + 5–6 perimeters + XTC-3D epoxy (watertightness from perimeters + sealing).

## Coordinate system (all hull-frame parts)

- X = beam (+X starboard), Y = length (bow tip Y=0 → transom), Z = height (keel Z=0).
- Each segment uses **local Y** starting at 0 at its forward face.
- Small parts use their own natural local origin (mounting face on XY, +Z up).

## Global hull constants (copy verbatim into every hull-frame part)

```python
import math
BEAM = 120.0          # max beam at chine plane
HALF_BEAM = 60.0
DEPTH = 72.0          # keel to deck
DEADRISE_DEG = 20.0
CHINE_H = HALF_BEAM * math.tan(math.radians(DEADRISE_DEG))   # 21.84
DECK_HALF = 64.0      # topside flare: chine (60, 21.84) -> deck edge (64, 72)
WALL = 2.4
SEG_L = 160.0         # each of bow / mid / stern
BULK_T = 3.0          # joint bulkhead thickness
FLANGE_W = 8.0        # inward deck flange lip width (mid + stern)
FLANGE_T = 2.4        # deck flange thickness (Z 69.6..72)
WL = 38.0             # est. static waterline at 1.15 kg all-up (reference only)
```

**Outer cross-section** (closed loop on XZ): `(0,0) → (60, 21.84) → (64, 72) → (-64, 72) → (-60, 21.84) → close`.
**Inner cross-section** = outer offset inward by WALL. Use analytic offsets:
keel inner apex `(0, WALL/cos(radians(DEADRISE_DEG)))` = (0, 2.554); inner chine ≈ `(57.16, 22.88)`; inner deck ≈ `(61.29, 72.0)` (open at top; deck flange added separately). Any consistent analytic offset is fine but **all three hull segments must use the identical formulas**.

## Segment joint interface (bow↔mid and mid↔stern, identical)

- Both segment ends carry a BULK_T bulkhead plate flush with the end face (inner profile).
- **+Y (aft) face of the forward segment**: 2 alignment pins Ø3.0 × 4.0 tall at (±30, 45); 4 bosses Ø8 × 8 deep with Ø2.6 pilot holes (axis Y) at **(±38, 58)** and **(±24, 30)**.
- **−Y (forward) face of the aft segment**: Ø3.4 × 4.5 deep pin sockets at (±30, 45); Ø3.4 through clearance holes at the same 4 bolt positions.
- Fastening: M3×12 self-tapping screws + silicone on the face.
- Wire pass hole Ø22 at (0, 48) through: mid both bulkheads, stern forward bulkhead. **Bow aft bulkhead is solid** (sealed foam-filled buoyancy compartment) except pilot bosses and one Ø10 foam-fill hole in the bow deck (sealed after filling).

## Parts

### hull/hull_bow.py — frigate-style bow (Y local 0=deck tip, 160=joint)
- Smooth **forward-rake stem curve**: deck tip at Y=0 overhangs the keel entry by ~28 mm (stem Y(z) uses a smoothstep ease — not a straight rake, not a plumb wall).
- Sharper plan taper (tip scale 0.02) + denser loft stations + smooth loft.
- Sealed stem plug near the tip (foam buoyancy), integral deck, Ø10 foam-fill hole.
- **Foredeck cannon pad**: Ø46 × 3 at (0, Y=55) with 4× Ø2.6 on Ø32 PCD (water_cannon bolts here, aimed FORWARD / −Y).
- Aft bulkhead joint interface unchanged (mates mid).
- Print: upright on joint face. ~110–150g.

### hull/hull_mid.py — constant section (Y local 0=fwd joint, 160=aft joint)
- Extruded outer/inner section, hollow, open deck with FLANGE_W deck flange lips both sides full length.
- Fwd bulkhead: clearance holes + pin sockets + Ø22 wire hole. Aft bulkhead: pins + pilot bosses + Ø22 wire hole.
- Deck-lid screw bosses under flange: Ø2.6 vertical pilots at (±45, Y=30, 80, 130), boss Ø8 hanging 6 below flange.
- Print: upright. ~105g.

### hull/hull_stern.py — stern (Y local 0=fwd joint, 160=transom aft face)
- Same section, hollow, deck flange + same 6 lid bosses at (±45, Y=25, 75, 125).
- Fwd bulkhead: clearance holes + sockets + Ø22 wire hole.
- **Transom**: solid plate Y=157..160 (full inner section); Ø30 hole centered (0, Z=40); 4× Ø3.4 clearance holes on Ø42 PCD around it (45° positions); pushrod hole Ø6 at (+18, 58); drain Ø8 at (−20, **16**) with Ø14×3 proud boss on aft face (rubber stopper). *(as-built: drain raised from Z=10 so the boss clears the V-bottom; servo-bracket pilots are at (+4, 67) and (+32, 67) on Ø8 bosses — Z=45 collided with the nozzle bore and pump flange seat)*.
- **Intake pad**: internal raised floor pad, flat top at Z=8.0, spanning |X|≤18, Y=64..126, fused to shell. **Intake aperture**: cut 24 wide (|X|≤12) × Y=70..120 through pad + shell (through the V bottom). 6× Ø2.6 vertical pilot holes in pad at (±15.5, Y=76, 97, 118).
- **Flood chamber (port)**: wall at X=−34 (2.4 thick) from hull shell to Z=64, Y=20..120; sealed top plate Z=61.6..64 from wall to hull side; end walls at Y=20 and 120. Flood hole Ø15 through the port hull side at Y=70, centered Z=50. (~120cc chamber).
- **Pump wet-well (starboard)**: vertical tube ID 38 / wall 2.4, center (+32, Y=45), from Z=69.6 down through the hull bottom; fuse to shell and deck flange; cut Ø24 opening in the hull shell at the well footprint (open to lake). Cannon pump sits inside; cable exits through stern deck lid.
- **Motor cradle pad**: flat-top boss Z top = 24.0, spanning |X|≤14, Y=18..56, with 2× Ø2.6 vertical pilots at (0, Y=24) and (0, Y=50).
- Print: upright on forward face (transom up). ~135g.

### jetdrive/pump_housing.py — bolt-in jet pump (hull frame, stern-local Y)
- Tunnel: Ø28 ID / wall 2.4 (Ø32.8 OD), axis (X=0, Z=40), Y=64..157.
- Front wall Y=64..68 (4 thick): closes tunnel; **Ø4.2 shaft bore** + **Ø7×5 bushing pocket** (aft, for flanged brass/PTFE) + **Ø12×2 coupler recess** (forward); motor mount = 4 radial slots 3.2 wide from r=8 to r=10 at 90° spacing (fits 2838 16–19mm hole patterns), on a Ø38 front boss.
- Intake duct: **curved scoop ramp** (multi-station loft) from rectangular mouth 24 × (Y=70..120) at Z=8 up into the tunnel — not a brick pedestal; front ramp eases into bore; fair rear lip. Duct walls 2.4.
- **Intake flange**: perimeter flange 6 wide around the mouth, flat underside at Z=8.0 (seals on stern pad, silicone gasket); 6× Ø3.4 clearance holes matching stern pad pilots (±15.5, Y=76, 97, 118).
- **Integral grate**: 3 longitudinal bars 2.5 wide × 3 deep across the mouth (along Y), even spacing (gaps ≤5.5mm).
- **Exit flange**: Ø44 disc, Y=153..157 (presses on transom inner face); 4× Ø2.6 pilot holes on Ø42 PCD (45° positions, matching transom clearance holes); tunnel bore continues through it.
- Shaft: 4mm shaft + 3.175→4 coupler (purchased) runs through the intake region to the impeller — standard jet-drive layout.
- Print: standing on exit flange, tunnel vertical. ~55g.

### jetdrive/impeller.py — helical 3-blade impeller (jdobry-faithful, local: axis Z)
- Hub Ø10 × 19; bore Ø4.05 + M3 set-screw pilot (4 mm shaft; 2838 via 3.175→4 coupler).
- **Helical blades** (not flat plates): axial loft with 120° twist + tip camber, topology from Jiri Dobry waterJet (`research/designs/jdobry-waterjet`), scaled to Ø28 tunnel; OD 27 (chamber−1).
- Consumable — print 2 in PETG. Print: hub down, 0.1–0.15 mm, 100% infill.

### jetdrive/nozzle_plate.py — fixed transom plate + stator (local: plate on XY, flow +Z)
- Plate 60 × 60 × 4; center bore Ø28; bore extends as a stub tube Ø28 ID / Ø32.8 OD × 14 proud on the aft side; **4 stator vanes** inside the stub with Ø11 hub.
- **MR74ZZ bearing seat** Ø7.2 × 3 in the stator hub (same bearing as jdobry waterJet) + Ø4.2 shaft clearance aft.
- 4× Ø3.4 clearance holes Ø42 PCD (45° positions; Y negated for rx=−90 assembly) — M3×16 from outside through plate + transom into pump exit-flange pilots.
- Pivot lugs: top + bottom, extending 18 aft, Ø3.4 vertical holes coaxial at 14 aft of plate face.
- Print: flat on plate. ~20g.

### jetdrive/nozzle.py — steerable nozzle (local: pivot axis = Z through origin)
- Inlet bell Ø34 ID × 8 long (rides over stub with ~0.6 clearance), converging cone to **Ø15 outlet** over 34 length, wall 2.4.
- Pivot bosses top + bottom (aligned with inlet mouth, 14 fwd of bell face): Ø7 bosses with Ø2.6 pilots (M3 self-tap pivot pins into plate lugs).
- Steering horn: 2.5 thick arm on starboard side, reaching 18 out, Ø2.1 pushrod hole at tip.
- Print: outlet up. ~10g.

### jetdrive/servo_bracket.py — SG90 mount (local: base plate on XY)
- Base 46 × 20 × 3, two Ø3.4 vertical slots (3.4×6) at **X=±14** (matches the as-built transom pilots 28mm apart at (+4,67)/(+32,67); mount on inner transom face, servo horn reaching down in line with the Ø6 pushrod hole at Z=58).
- SG90 pocket: 23.2 × 12.6 opening in a 3-wall cage 16 tall; two Ø2.1 pilots at ±14 X on the pocket rim (servo flange screws).
- Stern transom gets NO extra bosses — bracket screws into 2× Ø2.6 pilots at (+4, 45) and (+32, 45) on the transom inner face (add these to hull_stern.py transom).
- Print: flat. ~6g.

### deck/deck_mid.py — mid deck lid (local: plate on XY at Z=0 top of flange)
- Plate 124 × 158 × 3 (corners chamfered 6); downward inner lip **105** wide × 145 long × 5 deep (locates in the ~106.6-wide opening between flange inner edges at |X|≈53.3; the old 111 figure was wrong); seal = 2mm neoprene tape on flange (note, not printed).
- 6× Ø3.4 screw holes at (±45, Y=30, 80, 130) matching mid flange bosses.
- **Cannon/turret pad**: raised Ø56 × 3 disc at (0, Y=55) with 4× Ø2.6 pilots on **Ø32 PCD** (cannon direct) AND 4× Ø2.6 pilots on **Ø44 PCD** (turret base), offset 45° from each other.
- Wire grommet hole Ø10 at (0, Y=120). Print: flat. ~45g.

### deck/deck_stern.py — stern deck lid
- Same construction, holes at (±45, Y=25, 75, 125); Ø30 pump-well access hole at (+32, Y=45); Ø8 wire hole at (−20, Y=100). Print: flat. ~40g.

### electronics/electronics_tray.py — ESP32-S3 + ESC + IMU + BEC (local: base on XY)
- Plate 100 × 62 × 3 with 2 raised rails; ESP32 zone: 2 pairs of cable-tie slots 12×3 spanning a 55×28 zone (devkits lack holes); ESC pad 42×27 raised 3 with 2 tie slots; IMU (GY-521) 2× Ø2.6 pilots 15.5 apart on a 6-tall boss pair; BEC pocket 27×17×3; 4 corner Ø3.4 holes; velcro to mid-hull floor over battery. Print flat. ~15g.

### electronics/battery_tray.py — 3S 2200 cradle (local: saddle base on XY)
- For 106×35×26 pack. Saddle 120 long × 60 wide; underside V 20° (matches hull floor); flat bed; side walls 8 tall; end stops 12 tall; 2 strap slots 12×3 through both walls; sits in mid segment on keel (velcro strap). Print: bed down (V up, supports-free by 45° chamfer). ~25g.

### cannon/water_cannon.py — cannon (local: flange on XY, barrel +Y at +10° elevation)
- Flange Ø46 × 3 with 4× Ø3.4 on Ø32 PCD; riser wedge sets +10° elevation.
- Barrel 90 long, Ø12 OD; **bore SUBTRACTIVE**: Ø6 ID, converging to **Ø2 outlet** over last 15 (≈9 m/s jet on an 80–120 L/h pump).
- Rear hose barb: 14 long, Ø7.5/Ø6.0 barbed steps, Ø4 bore (6mm ID silicone tube from pump in the wet-well).
- 2 gussets 2.5 thick. Print: flange down. ~18g.

### cannon/turret_base.py — pan turret base (optional)
- Ø56 × 3 base plate, 4× Ø3.4 on Ø44 PCD; cylindrical body Ø50 OD / wall 2.4 / 27 tall; internal SG90 pocket 23.2 × 12.6 through the top face (servo drops in from top, output spline up, centered on part axis); 2× Ø2.1 servo-flange pilots at ±14; side wire slot 8 wide. Print: base down. ~20g.

### cannon/turret_platform.py — rotating platform
- Disc Ø54 × 4; underside: round-horn pocket Ø21.5 × 2 + Ø5.5 spline recess + Ø2.6 center screw hole; top: 4× Ø2.6 pilots on Ø32 PCD (cannon bolts here). Print: top down. ~8g.

## Assembly matrix

```
bow→mid, mid→stern : 4× M3×12 self-tap + 2 pins each joint, silicone faces
pump_housing→stern : 6× M3×10 self-tap down into intake pad, silicone gasket
nozzle_plate→transom→pump : 4× M3×16 through plate + transom into pump flange
nozzle→plate lugs  : 2× M3×10 self-tap pivot pins
impeller→shaft     : 4mm shaft + 3.175→4 coupler + M3 set screw
motor→pump front   : 2× or 4× M3×8 machine screws (16–19mm pattern slots)
servo_bracket→transom (inner) : 2× M3 self-tap
deck lids→flanges  : 6× M3 self-tap each + neoprene tape
cannon→mid lid pad (Ø32 PCD) or turret_platform (Ø32 PCD)
turret_base→mid lid pad (Ø44 PCD); platform→SG90 horn screw
battery/electronics trays : velcro + straps, mid segment
pump (cannon)      : drops into stern wet-well, tube to cannon barb
```

## Print settings

| Part group | Layer | Walls | Infill | Supports |
|---|---|---|---|---|
| Hull segments (upright) | 0.2 | 5–6 | 12% gyroid | none |
| Pump, nozzle, plate | 0.15 | 4 | 25% | none |
| Impeller | 0.1–0.15 | 3 | 100% | allowed |
| Lids, trays, cannon, turret | 0.2 | 4 | 15% | none |

Waterproofing: XTC-3D/epoxy inside wet hull surfaces, silicone all joints (per Kimi). Bathtub flip test tunes flood chamber before lake.

## Purchased-hardware deltas vs old BOM

- 4mm SS shaft ~80mm + 3.175→4mm rigid coupler (~$6)
- M3 self-tapping assortment, M3×16 machine screws, M3 set screws
- 2mm neoprene/foam tape, 6mm ID silicone tube
