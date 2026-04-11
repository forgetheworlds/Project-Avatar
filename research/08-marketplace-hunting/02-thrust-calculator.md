# Thrust-to-Weight Calculator for Marketplace Hunting

**Purpose**: Quick reference to evaluate if a drone can lift Project Avatar payload.

**Formula**: TWR = (Total Thrust in grams) / (Total Weight in grams)

**Minimum Required**: 2:1 (can hover and maneuver with payload)  
**Ideal**: 3:1 (responsive, safe margin)

---

## Quick Thrust Lookup Table

### 5" Props (Typical FPV freestyle)

| Motor Size | KV (4S) | KV (6S) | Max Thrust/ Motor | 4x Total Thrust |
|------------|---------|---------|-------------------|-----------------|
| 2207 | 2450 | 1700 | ~1200g | ~4800g |
| 2207 | 2750 | 1900 | ~1350g | ~5400g |
| 2306 | 2450 | 1700 | ~1250g | ~5000g |
| 2306 | 2750 | 1900 | ~1400g | ~5600g |

### 7" Props (Long range / heavy lifter)

**Thrust Test Data (2026) - 6S Battery / 7" Props [1]**:

| Motor Model | KV | Peak Thrust/Motor | 4x Total Thrust | Weight |
|-------------|-----|-------------------|-----------------|--------|
| **AOS Supernova 2807** | 1400KV | **2,500g+** | **10,000g+** | 49g |
| **EMAX ECO II 2807** | 1300KV | **~2,250g** | **~9,000g** | 54g |
| **Mad Bsc 2807** | 1300KV | **2,100g** | **~8,400g** | 48g |
| **BrotherHobby SE 2807** | 1300KV | **~2,150g** | **~8,600g** | 48g |

**Key Performance Insights**:
- Max current draw: 55A-66A at full throttle
- Efficiency sweet spot: 20-30% throttle for long flight times
- Standard prop: HQ 7x3.5x3 V1S

**Source**: [1] Thrust stand testing 2026 - multiple YouTube sources (see end of doc)

### 10" Props (Cinelifter / cinema)

| Motor Size | KV (6S) | Max Thrust/ Motor | 4x Total Thrust |
|------------|---------|-------------------|-----------------|
| 3115 | 900 | ~3000g | ~12000g |
| 4214 | 400 | ~5000g | ~20000g |

---

## Project Avatar Weight Budget

### Current Plan (X500 V2 - Too Heavy)

| Component | Weight |
|-----------|--------|
| Frame (X500 V2) | ~400g |
| Motors 4x (2216) | ~180g |
| ESCs 4-in-1 | ~40g |
| Pixhawk 6C Mini | ~25g |
| GPS + Compass | ~25g |
| Raspberry Pi 4 | 46g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio | ~15g |
| Cables, mounts, fasteners | ~50g |
| Battery 5000mAh 4S | ~500g |
| **TOTAL AUW** | **~1284g** |

**Thrust Required for 2:1 TWR**: 2568g  
**Thrust Required for 3:1 TWR**: 3852g

X500 V2 with 2216 motors: ~3000g total thrust → **2.3:1 TWR** (marginal)

---

## Revised Plan (Sub-250g Target)

### Option A: Light 5" Build

| Component | Weight |
|-----------|--------|
| Frame (iFlight Apex 5") | ~80g |
| Motors 4x (2207) | ~120g |
| ESCs 4-in-1 (30A) | ~25g |
| Pixhawk 6C Mini | 25g |
| GPS (micro) | 15g |
| Raspberry Pi Zero 2W | 16g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio (915MHz micro) | 10g |
| Cables, mounts | 30g |
| Battery 2200mAh 4S | ~200g |
| **TOTAL AUW** | **~544g** |

**Result**: 544g > 250g limit → ❌ Does not meet Canadian micro drone rules

### Option B: Featherweight 3" Cinewhoop

| Component | Weight |
|-----------|--------|
| Frame (BetaFPV Pavo20) | ~35g |
| Motors 4x (1404) | ~40g |
| ESCs AIO (20A) | ~15g |
| Pixhawk 6C Mini | 25g |
| GPS (omit for now) | 0g |
| Raspberry Pi Zero 2W | 16g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio (tiny) | 5g |
| Cables, mounts | 20g |
| Battery 1000mAh 4S | ~120g |
| **TOTAL AUW** | **~279g** |

**Result**: 279g > 250g limit → ❌ Close but still over

### Option C: Ultra-Light 3" with Custom FC

| Component | Weight |
|-----------|--------|
| Frame (BetaFPV Pavo20) | ~35g |
| Motors 4x (1404) | ~40g |
| ESCs AIO (20A) | ~15g |
| Pixhawk 6C Mini | 25g |
| Raspberry Pi Zero 2W | 16g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio (tiny) | 5g |
| Cables, mounts | 15g |
| Battery 850mAh 4S | ~100g |
| **TOTAL AUW** | **~254g** |

**Result**: 254g → ⚠️ Within measurement error, risky

### Option D: Registered Drone (Accept >250g)

| Component | Weight |
|-----------|--------|
| Frame (iFlight Chimera7) | ~120g |
| Motors 4x (2807) | ~140g |
| ESCs 4-in-1 (50A) | ~35g |
| Pixhawk 6C Mini | 25g |
| GPS + Compass | 25g |
| Raspberry Pi 4 | 46g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio | 15g |
| Cables, mounts | 40g |
| Battery 4000mAh 6S | ~450g |
| **TOTAL AUW** | **~899g** |

**Thrust**: 2807 1500KV on 6S = ~2000g per motor = 8000g total  
**TWR**: 8000g / 899g = **8.9:1** → ✅ Excellent!

---

## Marketplace Evaluation Formula

When you find a listing, calculate:

```
Step 1: Identify motor size and KV from listing
        Example: "2807 1300KV motors"

Step 2: Look up thrust per motor (from tables above)
        Example: 2807 1300KV on 6S = ~2000g per motor

Step 3: Calculate total thrust
        2000g x 4 motors = 8000g total thrust

Step 4: Estimate total weight (ask seller or estimate)
        Frame:     ~120g
        Motors:    ~140g  
        ESCs:      ~40g
        FC:        ~40g (we'll replace with Pixhawk 25g)
        Battery:   ~400g (estimate based on size)
        -----------------------------------
        Estimated: ~740g bare
        + Our payload: RPi (46g) + Camera (3g) + Radio (15g) + GPS (25g) + misc (40g) = 129g
        -----------------------------------
        Total AUW: ~869g

Step 5: Calculate TWR
        TWR = 8000g / 869g = 9.2:1

Step 6: Decision
        9.2:1 > 3:1 → ✅ Strong candidate!
```

---

## Marketplace Evaluation Checklist

### When You Find a Listing

**Step 1: Get specs from seller**
- [ ] Motor size (e.g., 2207, 2807)
- [ ] Motor KV (e.g., 2450KV, 1300KV)
- [ ] Battery size (e.g., 4S 1500mAh, 6S 4000mAh)
- [ ] Frame size (5", 7", 10")
- [ ] Frame weight (or total AUW)

**Step 2: Calculate thrust**
```
Motor: _____ size, _____ KV, _____ S battery
Thrust per motor (from table): _____ g
Total thrust (x4): _____ g
```

**Step 3: Calculate weight**
```
Frame: _____ g
Motors 4x: _____ g
ESCs: _____ g
FC (we replace): _____ g → Use 25g for Pixhawk
Battery: _____ g
Props: _____ g
------------------------------------------------
Base weight: _____ g
+ Our payload (RPi + Cam + Radio + GPS + misc): ~130g
------------------------------------------------
Total AUW: _____ g
```

**Step 4: Calculate TWR**
```
TWR = Total Thrust / Total AUW
TWR = _____ g / _____ g = _____ : 1
```

**Step 5: Decision**
- TWR < 2:1 → ❌ Skip - Won't lift payload
- 2:1 ≤ TWR < 3:1 → ⚠️ Marginal - Might work but limited maneuverability
- TWR ≥ 3:1 → ✅ Good candidate

---

## Comprehensive Motor Database

### Understanding Motor Naming

**Format**: `[diameter]mm[height]mm` + `[KV]` + `[battery cells]`
- **2207**: 22mm diameter, 7mm height
- **1300KV**: 1300 RPM per volt
- **6S**: 6-cell LiPo (~22.2V nominal)

**Rule of thumb**: Larger diameter = more torque. Taller = more power/magnet mass.

---

### 5" Frame Motors (2205-2306)

Best for: Freestyle, light payload

| Motor | KV (4S) | KV (6S) | Peak Thrust | Efficiency | Price Range |
|-------|---------|---------|-------------|------------|---------------|
| **EMAX ECO 2207** | 2400 | 1700 | ~1200g | Good | $15-20/motor |
| **EMAX ECO II 2306** | 2400 | 1700 | ~1300g | Good | $18-22/motor |
| **iFlight XING 2207** | 2750 | 1850 | ~1350g | Good | $20-25/motor |
| **iFlight XING2 2207** | 2750 | 1850 | ~1400g | Excellent | $25-30/motor |
| **T-Motor F40 Pro** | 2400 | 1600 | ~1250g | Excellent | $25-30/motor |
| **T-Motor F60 Pro** | 2207 | 1750 | ~1350g | Excellent | $30-35/motor |
| **HGLRC Aeolus 2207** | 2550 | 1900 | ~1300g | Good | $15-20/motor |
| **BrotherHobby Avenger 2207** | 2500 | 1750 | ~1400g | Excellent | $25-30/motor |
| **RCinPower Smoox 2306** | 2580 | 1880 | ~1350g | Good | $20-25/motor |
| **Xnova 2207** | 2600 | 1800 | ~1380g | Excellent | $30-35/motor |

**4x Total Thrust Range**: 4800g - 5600g

**Verdict for Project Avatar**: ⚠️ **Marginal** - Thrust OK but frame size limits battery/payload space

---

### 7" Frame Motors (2806-2809) ⭐ TARGET

Best for: Long range, heavy payload, Project Avatar

| Motor | KV | Peak Thrust | Weight | Best Prop | Price Range |
|-------|-----|-------------|--------|-----------|---------------|
| **AOS Supernova 2807** | 1400KV | **2,500g+** | 49g | HQ 7x4x3 | $35-45/motor |
| **EMAX ECO II 2807** | 1300KV | ~2,250g | 54g | HQ 7x3.5x3 | $20-25/motor |
| **EMAX ECO II 2807** | 1500KV | ~2,400g | 54g | HQ 7x4x3 | $20-25/motor |
| **iFlight XING 2806** | 1300KV | ~1,900g | 48g | HQ 7x3.5x3 | $22-28/motor |
| **iFlight XING 2806** | 1800KV | ~2,200g | 48g | HQ 7x4x3 | $22-28/motor |
| **iFlight XING2 2809** | 1250KV | ~2,600g | 52g | HQ 7x4x3 | $35-40/motor |
| **iFlight XING2 2809** | 1500KV | ~2,800g | 52g | HQ 7x4.5x3 | $35-40/motor |
| **HGLRC Aeolus 2807** | 1300KV | ~2,100g | 50g | HQ 7x3.5x3 | $18-22/motor |
| **BrotherHobby SE 2807** | 1300KV | ~2,150g | 48g | HQ 7x3.5x3 | $25-30/motor |
| **BrotherHobby Avenger 2808** | 1200KV | ~2,300g | 56g | HQ 7x4x3 | $30-35/motor |
| **Mad Bsc 2807** | 1300KV | ~2,100g | 48g | HQ 7x3.5x3 | $22-26/motor |
| **T-Motor F90 3110** | 1050KV | ~2,800g | 68g | HQ 7x4x3 | $40-50/motor |
| **T-Motor F90 3110** | 1500KV | ~3,200g | 68g | HQ 7x5x3 | $40-50/motor |
| **Hobbywing XRotor 2807** | 1500KV | ~2,400g | 59g | HQ 7x4x3 | $30-35/motor |

**4x Total Thrust Range**: 7,600g - 12,800g

**Verdict for Project Avatar**: ✅ **EXCELLENT** - Sweet spot for payload capacity

**Recommended Motors (in order)**:
1. **iFlight XING2 2809 1500KV** - Best performance (~11,200g total)
2. **AOS Supernova 2807 1400KV** - Premium option (~10,000g total)
3. **EMAX ECO II 2807 1300/1500KV** - Budget champion (~9,000g total)
4. **BrotherHobby SE 2807 1300KV** - Reliable mid-range (~8,600g total)

---

### 10" Frame Motors (3110-4214)

Best for: Cinema, extreme payload

| Motor | KV | Peak Thrust | Weight | Best Prop | Price Range |
|-------|-----|-------------|--------|-----------|---------------|
| **T-Motor F90 3110** | 900KV | ~3,000g | 68g | 10x4.5 | $40-50/motor |
| **T-Motor P60 3115** | 900KV | ~3,200g | 72g | 10x5 | $45-55/motor |
| **T-Motor U8II 4214** | 400KV | ~5,000g | 95g | 14x4.8 | $80-100/motor |
| **iFlight XING2 3110** | 900KV | ~2,800g | 65g | 10x4.5 | $40-45/motor |
| **EMAX LS 2812** | 950KV | ~2,600g | 62g | 10x4 | $30-35/motor |

**4x Total Thrust Range**: 10,000g - 20,000g

**Verdict for Project Avatar**: ⚠️ **Overkill** - Great thrust but heavy, expensive, rare on Marketplace

---

### Motor Selection Guide by Budget

**Budget (<$100 for 4 motors)**:
- EMAX ECO II 2807 1300KV
- HGLRC Aeolus 2807 1300KV
- ~8,400-9,000g total thrust

**Mid-Range ($100-140 for 4 motors)**:
- iFlight XING 2806 1300KV
- BrotherHobby SE 2807 1300KV
- ~8,600-7,600g total thrust

**Premium ($140-200 for 4 motors)**:
- AOS Supernova 2807 1400KV
- iFlight XING2 2809 1500KV
- ~10,000-11,200g total thrust

**Cinema/Heavy Lift ($160+ for 4 motors)**:
- T-Motor F90 3110 1050KV
- T-Motor P60 3115 900KV
- ~11,200-12,800g total thrust

---

### KV Selection by Battery

| Battery | KV Range | Why |
|---------|----------|-----|
| **4S** (14.8V) | 2200-2800KV | Higher RPM compensates for lower voltage |
| **6S** (22.2V) | 1200-1600KV | Lower KV = more torque, efficiency at higher voltage |
| **8S** (29.6V) | 800-1100KV | Very low KV for cinema motors |

**Project Avatar Recommendation**: 6S 1300-1500KV
- Sweet spot for efficiency and thrust
- Common on 7" long-range quads
- More efficient than 4S for heavy loads

---

### Red Flag Motors (Avoid)

| Motor Type | Why Avoid |
|------------|-----------|
| <2205 size | Insufficient torque for payload |
| >2000KV on 6S | Too fast, inefficient, overheats |
| <900KV on 4S | Won't spin fast enough |
| Unknown brand, no specs | Can't verify thrust data |
| Bent shafts (visible wobble) | Reduced thrust, vibrations |
| Overheated/discolored | Weakened magnets |

---

## Frame Database

### Understanding Frame Types

**Deadcat**: Arms angle forward, props out of camera view
- Pros: No props in footage, stable
- Cons: Less agile, slightly less efficient

**True-X**: Equal arm length, symmetrical
- Pros: Balanced, agile, efficient
- Cons: Props in camera view

**Stretch-X**: Longer front-to-back
- Pros: Fast forward flight, aerodynamic
- Cons: Less stable hover

**Squashed-X**: Wider than long
- Pros: Stable hover, good for filming
- Cons: Less efficient forward flight

---

### 5" Frames (Avoid for Project Avatar)

| Frame | Weight | Mount | Type | Price Used |
|-------|--------|-------|------|------------|
| iFlight Apex 5" | ~85g | 30.5mm | True-X | $30-40 |
| GEPRC Mark5 | ~90g | 30.5mm | True-X | $35-45 |
| TBS Source One V5 | ~95g | 30.5mm | True-X | $25-35 |
| ImpulseRC Apex | ~80g | 30.5mm | True-X | $40-50 |
| iFlight SL5 | ~75g | 20x20mm | True-X | $30-40 |

**Verdict**: ⚠️ **Too small** - Can't fit battery + RPi + Pixhawk comfortably

---

### 7" Frames ⭐ TARGET

Best for: Long range, heavy payload, Project Avatar

| Frame | Weight | Mount | Type | Stack Height | Price Used |
|-------|--------|-------|------|--------------|------------|
| **iFlight Chimera7** | ~120g | 30.5mm | Deadcat | 20-25mm | $40-60 |
| **iFlight Chimera7 Pro** | ~130g | 30.5/20mm | Deadcat | 20-25mm | $50-70 |
| **HGLRC Rekon 7** | ~130g | 30.5mm | Deadcat | 20mm | $40-55 |
| **HGLRC Rekon 7 Pro** | ~140g | 30.5/20mm | Deadcat | 25mm | $50-65 |
| **GepRC MARK4 7"** | ~125g | 30.5mm | Deadcat | 20mm | $40-55 |
| **TBS Source 2 7"** | ~110g | 30.5mm | True-X | 20mm | $35-50 |
| **Flywoo Explorer LR7** | ~135g | 30.5/20mm | Deadcat | 25mm | $45-60 |
| **Caddx Vista 7"** | ~140g | 30.5mm | Deadcat | 25mm | $50-65 |
| **iFlight AOS 7** | ~150g | 30.5mm | Deadcat | 30mm | $55-75 |
| **Shendrones Thicc 7"** | ~160g | 30.5mm | Deadcat | 25mm | $50-70 |
| **Killer Bee 7"** | ~125g | 30.5mm | True-X | 20mm | $40-55 |

**Recommended Priority**:
1. **iFlight Chimera7 / Chimera7 Pro** - Most common, proven payload capacity
2. **HGLRC Rekon 7 / Rekon 7 Pro** - Budget-friendly, good build quality
3. **Flywoo Explorer LR7** - Long-range optimized, efficient
4. **iFlight AOS 7** - Premium option, heavy lifter

---

### 10" Frames (Cinelifter)

| Frame | Weight | Mount | Type | Price Used |
|-------|--------|-------|------|------------|
| iFlight XL10 V6 | ~180g | 30.5mm | True-X | $60-80 |
| HGLRC Rekon 10 | ~190g | 30.5mm | Deadcat | $60-80 |
| GEPRC CineLog 10 | ~200g | 30.5mm | Deadcat | $70-90 |
| TBS Source X 10" | ~170g | 30.5mm | True-X | $50-70 |
| Shendrones Squirt V2 | ~180g | 30.5mm | Cinewhoop | $80-100 |

**Verdict**: ⚠️ **Overkill** - Heavy, expensive, rare on Marketplace

---

### Frame Mount Patterns

**CRITICAL**: Must match your flight controller

| Pattern | Size | Compatible With |
|---------|------|-----------------|
| **30.5x30.5mm** (M3) | Standard | Pixhawk 6C Mini, most full-size FCs |
| **20x20mm** (M2) | Mini | Mini FCs, AIO boards |
| **25.5x25.5mm** (M2) | Whoop | Tiny whoop FCs |

**Project Avatar**: Must have **30.5x30.5mm** for Pixhawk 6C Mini

**Check Before Buying**: Ask seller "What mount pattern? 30.5mm or 20mm?"

---

### Frame Features to Look For

| Feature | Why It Matters |
|---------|----------------|
| **Deadcat layout** | Props out of camera view (clean footage) |
| **30.5mm mount** | Fits Pixhawk 6C Mini |
| **20-25mm stack** | Room for FC + ESC + possible 4G module |
| **Thick arms (5mm+)** | Rigid, reduces vibrations |
| **3D printed mounts** | GPS mount, antenna mounts included |
| **FPV camera mount** | Can repurpose for Pi Camera |
| **Battery strap slots** | Secure battery mounting |
| **Vibration dampening** | Rubber grommets for FC |

---

### Frame Red Flags

| Red Flag | Why Avoid |
|----------|-----------|
| 20x20mm mount only | Can't fit Pixhawk |
| <3mm arm thickness | Too flexible, wobbly |
| 3" or smaller | Can't lift payload |
| No stack space (AIO only) | Can't add companion computer |
| Cracked carbon fiber | Structural weakness |
| Stripped standoff threads | Hard to assemble |
| Missing hardware | Hard to complete build |

---

## Full Kits & Bind-n-Fly Options

### What to Look For on Marketplace

**Full Quad**: Frame + motors + ESCs + FC + props
- You'll replace FC with Pixhawk
- Keep motors/ESCs/frame if specs match
- Sell FPV gear if included

**Bind-n-Fly (BNF)**: Full quad + receiver, needs transmitter
- Good if you want FPV goggles too
- Check receiver protocol (ELRS, Crossfire)

**Ready-to-Fly (RTF)**: Everything included
- Usually overpriced on Marketplace
- May include low-quality parts

---

### Desirable Full Kit Configurations

| Kit Configuration | Est. Thrust | Est. Weight | TWR | Verdict |
|-------------------|-------------|-------------|-----|---------|
| **7" + 2807 1300KV + 6S 4000** | 8,400g | ~850g | 9.9:1 | ✅ **PERFECT** |
| **7" + 2806 1300KV + 6S 3000** | 7,200g | ~800g | 9.0:1 | ✅ **Good** |
| **7" + XING2 2809 1500KV + 6S** | 11,200g | ~900g | 12.4:1 | ✅ **Excellent** |
| **5" + 2207 2450KV + 4S 1500** | 4,800g | ~500g | 9.6:1 | ⚠️ **Thrust OK, frame small** |
| **10" + 3110 900KV + 6S 5000** | 11,200g | ~1200g | 9.3:1 | ✅ **Overkill but good** |
| **7" + 2207 2450KV + 4S** | 4,800g | ~650g | 7.4:1 | ❌ **Motors undersized** |
| **5" + 2306 + cinewhoop** | 5,000g | ~600g | 8.3:1 | ❌ **Too small for components** |

---

### Ideal Kit Specification Checklist

When you find a complete quad, check for:

```
Frame: 7" (Chimera7, Rekon7, etc.)
Motors: 2806-2809 size
KV: 1300-1500KV (for 6S) or 1700-1900KV (for 4S)
ESCs: 45A-60A 4-in-1 (or 50A+ individual)
Battery: 6S 3000mAh+ (or 4S 4000mAh+)
FC Mount: 30.5x30.5mm
Total weight: <800g without battery
```

---

### Kit Red Flags

| Red Flag | Why Skip |
|----------|----------|
| AIO FC/ESC board | Hard to separate, may not fit Pixhawk |
| 20x20mm FC only | Can't fit 30.5mm Pixhawk |
| Unknown motor brand | Can't verify thrust |
| 20A ESCs | Will overheat with payload |
| 3S battery only | Insufficient voltage |
| Tiny props (3-4") | Can't generate lift |
| All-in-one camera/FC | DJI system, hard to modify |
| No receiver | Extra cost to add |

---

### FPV Gear You Can Ignore (or Sell)

Most Marketplace quads come with FPV gear you don't need:

| Component | Purpose | Project Avatar Need |
|-----------|---------|---------------------|
| **FPV Camera** (Runcam, Caddx) | Pilot view | ❌ Use Pi Camera Module 3 |
| **FPV Transmitter** | Video to goggles | ❌ Not needed |
| **Receiver** (Crossfire, ELRS) | RC control | ⚠️ Maybe for backup |
| **FPV Goggles** | Pilot viewing | ❌ Not needed |
| **Radio Transmitter** | Manual control | ⚠️ Keep for safety |
| **GoPro mount** | Camera mount | ✅ Repurpose for Pi |
| **GPS** | Position hold | ✅ May keep if good module |

**Strategy**: Buy quad with FPV gear, sell FPV stuff separately to reduce net cost.

---

## Budget Build Guide: STRICTLY Under $500 Total

### Absolute Budget Breakdown (Hard Ceiling: $500)

| Category | Target Cost | Max Cost | What You Need |
|----------|-------------|----------|---------------|
| **Drone (Marketplace)** | $120-180 | $200 | 7" frame + 2807 motors + 50A ESC |
| **Flight Controller** | $85-95 | $100 | Pixhawk 6C Mini (new) |
| **Companion Computer** | $35-45 | $55 | Raspberry Pi 4 2GB (used) |
| **Camera** | $25-30 | $35 | Pi Camera Module 3 |
| **GPS/Compass** | $15-20 | $25 | M8N GPS + compass (AliExpress) |
| **Telemetry** | $15-20 | $25 | 915MHz module (used/Marketplace) |
| **Battery** | $30-40 | $50 | 6S 3000mAh LiPo (used) |
| **Misc** | $15-20 | $25 | Cables, mounts, XT60, straps |
| **TOTAL** | **$340-445** | **$500** | **Hard ceiling enforced** |

### Three Strategies to Stay Under $500

**Strategy 1: Aggressive "Hobby Exit" Deal** ⭐ BEST
```
Full kit with FPV gear: $250-300
  - Quad components: frame + motors + ESC
  - FPV gear resale: -$120-180 (goggles + radio + FPV cam)
Net drone cost: $130-180

Remaining for new parts: $320-370 ✅
```

**Strategy 2: Component Bundle Hunt**
```
Frame + motors bundle: $100-140
Used 50A ESC: $25-35
Net drone cost: $125-175

Remaining: $325-375 ✅
```

**Strategy 3: Extreme Scavenge**
```
Frame only (Chimera7): $35-45
Motors 4x (2807): $50-70
ESC 50A: $25-35
Props/hardware: $15-20
Net drone cost: $125-170

Remaining: $330-375 ✅
```

### Recommended Sub-$500 Build

**The $420-480 Build** (Verified Under Budget)

| Component | Source | Target Cost | Strategy |
|-----------|--------|-------------|----------|
| **HGLRC Rekon 7 + EMAX 2807 1300KV** | Marketplace hobby exit | $130-170 | Negotiate hard, no FPV needed |
| **Pixhawk 6C Mini** | GetFPV/Holybro new | $90-95 | Safety-critical, must be new |
| **Raspberry Pi 4 2GB** | Marketplace/Kijiji used | $35-45 | 2GB sufficient for MAVSDK |
| **Pi Camera Module 3** | Amazon/AliExpress | $28-32 | Buy new, cheapest source |
| **M8N GPS + Compass** | AliExpress new | $18-22 | Cheapest viable option |
| **915MHz Telemetry** | Marketplace bundle | $15-20 | Often bundled with GPS |
| **6S 3000mAh LiPo** | Marketplace used | $30-40 | Check cell voltage first |
| **Cables, XT60, straps** | AliExpress | $15-18 | Order with GPS |
| **TOTAL** | | **$341-442** | **$58-159 buffer remaining** |

**What to Do With Remaining Budget**:
- Spare props ($15-20)
- Better battery 4000mAh (+$15)
- SD cards ($10-15)
- Save for repairs/upgrades

### Aggressive Cost-Cutting Tactics

**Buy These Used (Safe)**:
| Component | Target Price | Where | What to Check |
|-----------|--------------|-------|---------------|
| 7" Frame | $35-50 | Marketplace | Cracks, mount holes |
| 2807 Motors | $50-70 | Marketplace | Spin test, bent shafts |
| 50A ESC | $25-35 | Marketplace | Power on test |
| Pi 4 2GB | $35-45 | Kijiji | SD slot, USB ports |
| Battery 6S | $30-40 | Marketplace | Cell voltage 3.7V+ each |
| Telemetry | $15-20 | Marketplace/Bundled | Range test |

**Buy These New (Cheap Sources)**:
| Component | Target Price | Source |
|-----------|--------------|--------|
| Pixhawk 6C Mini | $90-95 | GetFPV, Holybro direct |
| Pi Camera 3 | $28-32 | AliExpress, Amazon sale |
| GPS M8N | $18-22 | AliExpress |
| Cables/wire | $10-15 | AliExpress |

**Skip Entirely (Not Needed)**:
- ❌ FPV goggles ($0 instead of $150)
- ❌ FPV camera ($0 instead of $30)
- ❌ FPV transmitter ($0 instead of $40)
- ❌ Radio transmitter (use what you have or skip)
- ❌ Original FC (replace with Pixhawk)
- ❌ Prop guards (deadcat frame doesn't need)

### The $500 Hard Ceiling Rules

**If Marketplace drone costs >$200**: Walk away
**If Pixhawk >$100**: Wait for sale, check Holybro direct
**If any component exceeds "Max Cost"**: Find alternative
**Total must be ≤$500 before tax**: Tax is separate

### Emergency Under-$400 Build

If funds are extremely tight:

| Component | Cost | Compromise |
|-----------|------|------------|
| 7" frame + 2207 motors | $80-120 | Less thrust, but 2207 1700KV on 6S still works (~6:1 TWR) |
| Used 40A ESC | $20-25 | Riskier, but 40A minimum for 2207 |
| Pixhawk 6C Mini | $90 | No compromise |
| Pi 4 2GB used | $35 | No compromise |
| Pi Camera 3 | $28 | No compromise |
| GPS/telemetry combo | $30-35 | AliExpress bundle |
| Battery 4S 4000mAh used | $25-30 | Lower voltage, acceptable for 2207 |
| Misc | $15 | |
| **TOTAL** | **$303-388** | TWR ~6:1 (acceptable, not ideal) | 

**Warning**: 2207 motors on 4S will give ~5,000g thrust. With ~850g AUW, TWR = 5.9:1. This is the absolute minimum. Upgrade to 2807 when budget allows.

### What to Buy New vs Used

| Component | Recommendation | Why |
|-----------|----------------|-----|
| **Pixhawk 6C Mini** | Buy NEW | Safety-critical, warranty matters |
| **ESC 50A** | Can buy used | Test before buying, no moving parts |
| **Motors 2807** | Buy used OK | Spin test, check for bent shafts |
| **7" Frame** | Buy used OK | Visual inspection for cracks |
| **Raspberry Pi 4** | Used/refurb OK | Solid state, check SD card slot |
| **Pi Camera 3** | Buy NEW | Delicate ribbon cable |
| **GPS Module** | Buy new cheap | M8N clones work fine |
| **Battery 6S** | Careful with used | Must check cell voltage/health |
| **Cables/Mounts** | Buy new cheap | Not worth used hassle |

### Marketplace Negotiation for Budget Build

**Opening Message Template**:
```
"Hi! I'm interested in your [frame/motor/quad]. I'm building a photography 
drone project on a student budget. Would you take $[target] for [specific items]?
I don't need the FPV gear if you want to keep/sell separately. Cash, can pickup [time]."
```

**Target Discounts**:
- Listed >$400: Offer 70-75%
- Listed $200-400: Offer 80-85%
- Listed <$200: Offer 85-90%
- Bundle deals: Negotiate "without FPV gear" price

### Red Lines (Don't Skimp)

Even on $500 budget, DO NOT compromise on:
1. **Pixhawk 6C Mini** - Must be genuine (safety)
2. **50A+ ESCs** - 45A minimum for payload lift
3. **2807 motors** - 2806 minimum acceptable
4. **7" frame with 30.5mm mount** - Must fit Pixhawk

**Where to Save Money**:
- ✅ Buy used frame (carbon fiber is durable)
- ✅ Buy used motors (easy to test)
- ✅ Buy used ESC (if tested)
- ✅ Buy 2GB Pi 4 instead of 4GB (manageable)
- ✅ Skip FPV gear entirely (you don't need it)
- ✅ Buy battery used from trusted source
- ✅ Source GPS/telemetry from AliExpress

### Free Money Recapture

After building, sell what you don't need:
| Item | Resale Value | Where |
|------|--------------|-------|
| FPV goggles (from kit) | $80-150 | Marketplace, Kijiji |
| FPV camera | $20-40 | r/fpvclassifieds |
| FPV transmitter | $15-30 | Local FPV groups |
| Radio transmitter (if included) | $40-80 | Marketplace |
| Original flight controller | $20-40 | FPV community |

**Potential Recovery**: $175-340

If you recover $200 from FPV gear, your net build cost drops to $300-350.

---

## Real-World Examples</insert>

### Example 1: Good Candidate

**Listing**: "iFlight Chimera7, XING 2807 1300KV, 6S 4000mAh"

**Calculation**:
- Motors: 2807 1300KV on 6S = ~1900g per motor
- Total thrust: 1900g x 4 = 7600g
- Estimated base weight: 750g
- + Our payload: 130g
- Total AUW: 880g
- **TWR: 7600/880 = 8.6:1** → ✅ Excellent!

### Example 2: Too Small

**Listing**: "5 inch freestyle, 2207 2450KV, 4S 1500mAh"

**Calculation**:
- Motors: 2207 2450KV on 4S = ~1200g per motor
- Total thrust: 1200g x 4 = 4800g
- Estimated base weight: 400g
- + Our payload: 130g
- Total AUW: 530g
- **TWR: 4800/530 = 9:1** → ✅ Good TWR BUT...

**Problem**: Adding 130g payload to a 400g quad is a 32% increase. Frame not designed for that weight. Battery too small (1500mAh). Props may not have pitch for payload.

**Verdict**: ⚠️ Thrust is there but frame/battery not suitable

### Example 3: Marginal

**Listing**: "7 inch long range, 2806 1300KV, 6S 3000mAh"

**Calculation**:
- Motors: 2806 1300KV on 6S = ~1700g per motor
- Total thrust: 1700g x 4 = 6800g
- Estimated base weight: 700g
- + Our payload: 130g
- Total AUW: 830g
- **TWR: 6800/830 = 8.2:1** → ✅ Good TWR

**Verdict**: ✅ Acceptable, but 2807 would be better than 2806

---

## Questions to Ask Sellers (Thrust Focus)

1. **"What motors are these exactly? Size and KV?"**
   - Need: Motor size (e.g., 2807) and KV rating

2. **"What battery do you run? Voltage and capacity?"**
   - Need: 4S/6S and mAh (for weight estimate)

3. **"Do you know the AUW (all-up weight)?"**
   - Ideal: Actual measured weight
   - Acceptable: "With 4S 1500mAh it weighs about 450g"

4. **"Has it been crashed? Any motor damage?"**
   - Bent shafts = reduced thrust
   - Damaged magnets = reduced thrust

5. **"Why are you selling?"**
   - "Too heavy for my style" = might be perfect for us!
   - "Not enough power" = red flag

---

## Quick Decision Matrix

| Frame Size | Motor Size | Battery | Est. Thrust | Est. Weight | TWR | Verdict |
|------------|------------|---------|-------------|-------------|-----|---------|
| 5" | 2207 2450KV | 4S 1500 | 4800g | 530g | 9:1 | ⚠️ Thrust OK, frame small |
| 5" | 2306 2750KV | 4S 1500 | 5600g | 530g | 10.5:1 | ⚠️ Thrust OK, frame small |
| 7" | 2807 1300KV | 6S 4000 | 8000g | 900g | 8.9:1 | ✅ Good candidate |
| 7" | 2806 1300KV | 6S 3000 | 6800g | 830g | 8.2:1 | ✅ Acceptable |
| 10" | 3110 900KV | 6S 5000 | 10000g | 1200g | 8.3:1 | ✅ Excellent but heavy |
| 7" | 2207 2450KV | 4S 1800 | 4800g | 650g | 7.4:1 | ❌ Motors undersized |
| 5" | 2306 2450KV | 4S 1300 | 5000g | 480g | 10.4:1 | ⚠️ Thrust OK, battery small |

---

## Key Insight: Thrust vs Frame Size

**Main factor IS thrust power**, but frame size matters too:

| Frame | Pros | Cons |
|-------|------|------|
| 5" | Abundant, cheap | Small battery bay, tight build |
| 7" | Sweet spot for payload | More expensive |
| 10" | Massive payload capacity | Expensive, less common |

**Recommendation**: Focus on 7" frames with 2807 motors on 6S.

This gives:
- ~8000g thrust
- ~900g AUW with our payload
- **8.9:1 TWR** → Responsive, safe, room to grow

---

*Last Updated: 2026-04-10*
