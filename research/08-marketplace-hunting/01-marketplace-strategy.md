# Facebook Marketplace Drone Hunting Strategy

**Purpose**: Guide for finding suitable drone hardware on Facebook Marketplace with Canadian law compliance and Project Avatar requirements.

**Status**: In Progress - Awaiting Canadian regulation confirmation

---

## Table of Contents

1. [Weight & Legal Requirements](#weight--legal-requirements)
2. [Thrust-to-Weight Requirements](#thrust-to-weight-requirements)
3. [Compatible Frame Types](#compatible-frame-types)
4. [Red Flags to Avoid](#red-flags-to-avoid)
5. [Inspection Checklist](#inspection-checklist)
6. [Negotiation Strategy](#negotiation-strategy)

---

## Weight & Legal Requirements

### Critical Weight Threshold

**Target**: Stay under **250g total takeoff weight** (including payload)

This is the magic number for Canadian drone regulations:

| Weight Class | Registration | License | Operational Rules | Project Avatar Status |
|--------------|------------|---------|-------------------|----------------------|
| **<250g** | No | No (Basic Ops) | Simplified rules | ✅ **TARGET** |
| 250g-25kg | Yes | Basic/Advanced | More restrictions | ❌ Avoid |
| >25kg | Yes | Complex | Commercial license | ❌ Not applicable |

### What Counts Toward Weight

**Clarification needed from Transport Canada**:
- Does "drone weight" include payload (RPi, camera, battery)?
- Or is it just the base frame + motors + flight controller?

**Assumption for safety**: Count everything that flies:
- Frame + motors + props
- Flight controller + ESCs
- Battery
- Companion computer (RPi 4)
- Camera module
- Cabling, mounts, fasteners
- **TOTAL must be <250g**

### Canadian Drone Rules (Micro Drone <250g)

**To be confirmed via Google AI search**:
- No registration required
- No pilot certificate required
- Must operate in uncontrolled airspace
- Keep 30m+ from bystanders
- VLOS (Visual Line of Sight) only
- No flight over advertised events

---

## Thrust-to-Weight Requirements

### Minimum TWR for Project Avatar

**Requirement**: **2:1 minimum**, ideally 3:1

| TWR | Performance | Safety Margin | Use Case |
|-----|-------------|---------------|----------|
| 1.5:1 | Can hover | None | ❌ Unacceptable |
| **2:1** | Good control | Basic | ✅ **Minimum** |
| **3:1** | Responsive | Comfortable | ✅ **Ideal** |
| 4:1+ | Sport/acro | High | Nice but not required |

### Why 2:1 Minimum

Project Avatar needs to lift:

| Component | Weight | Notes |
|-----------|--------|-------|
| Holybro X500 V2 frame kit | ~800g | Too heavy! |
| Raspberry Pi 4 | 46g | Companion computer |
| Pi Camera Module 3 | 3g | Vision system |
| 5000mAh 4S battery | ~500g | Power |
| Motors + ESCs + FC | ~200g | Base hardware |
| Cabling, mounts, fasteners | ~50g | Misc |
| **TOTAL** | **~1600g** | Far exceeds 250g limit |

### The 250g Challenge

**Problem**: X500 V2 (~800g empty, ~1600g loaded) cannot meet Canadian micro drone requirements.

**Options**:

1. **Accept >250g** → Register drone, get basic/advanced certificate, more restrictions
2. **Find lighter frame** → 5-inch or 7-inch FPV frame designed for <250g AUW
3. **Split hardware** → Smaller companion computer (Pi Zero 2W = 16g)

**Recommendation**: Option 2 + 3 combined

---

## Compatible Frame Types

### What to Look For on Marketplace

**Search Terms**:
- "5 inch FPV frame"
- "7 inch long range frame"
- "Cinelifter frame"
- "Deadcat frame"
- "Pixhawk compatible"

**Frame Requirements**:

| Spec | Minimum | Ideal | Notes |
|------|---------|-------|-------|
| Wheelbase | 7 inch | 7-10 inch | Stability for payload |
| Motor size | 2207 | 2807 | Torque for lift |
| Props | 5" | 7" | Efficiency vs thrust |
| Weight (frame only) | <150g | <100g | Leave room for payload |
| Mount pattern | 30.5x30.5mm | Both 30.5 + 20x20 | Pixhawk 6C Mini fits |

### Specific Frames to Hunt For

**Target 1: iFlight Chimera7**
- Weight: ~120g frame
- Can carry ~1kg payload with 2807 motors
- 7" props = efficient + stable
- Deadcat layout = props out of camera view

**Target 2: HGLRC Rekon 7**
- Weight: ~130g frame
- Budget-friendly
- Good Pixhawk compatibility

**Target 3: Shendrones Squirt V2**
- Weight: ~180g frame
- Purpose-built for cinelifter (carrying cameras)
- 3" ducted props
- Excellent for stability

**Target 4: Any 7" Deadcat Frame**
- Look for: Apex LR7, Rekon7, Chimera7 clones
- Must have 30.5x30.5mm mount for Pixhawk

### Motors to Look For

**Minimum viable**:
- 2207 size (22mm diameter, 7mm height)
- 1500-1900 KV for 6S
- 2450-2800 KV for 4S

**Preferred**:
- 2807 size (more torque for payload)
- 1300-1500 KV 6S
- Brands: EMAX, T-Motor, iFlight, HGLRC

### What to Avoid

❌ **Tiny whoops** (2-3 inch) - Can't lift payload  
❌ **Racing frames** - Optimized for speed, not lift  
❌ **DJI FPV / Avata** - Closed ecosystem, hard to modify  
❌ **Pre-built DJI drones** - Cannot install Pixhawk companion computer  

---

## Red Flags to Avoid

### Seller Red Flags

| Red Flag | Risk | Action |
|----------|------|--------|
| "No test, sold as-is" | Dead electronics | ❌ Skip |
| "Was working when crashed" | Structural damage | ⚠️ Inspect carefully |
| No photos of electronics | Hidden damage | Ask for photos |
| "Just needs calibration" | Likely bigger problem | ⚠️ Be cautious |
| Too cheap (<$50 for full quad) | Stolen or broken | ❌ Skip |
| Listed as "drone" but is toy | Waste of time | Verify specs |

### Hardware Red Flags

| Red Flag | Why It Matters |
|----------|----------------|
| 3S battery only | Insufficient voltage for payload lift |
| <2306 motors | Insufficient torque for Project Avatar |
| 20x20mm FC mount only | Pixhawk 6C Mini requires 30.5x30.5mm |
| Plastic frame only | Too flexible for precision control |
| No GPS mount | Cannot implement waypoint navigation |
| Tiny camera (Runcam Nano) | Not compatible with Pi Camera Module 3 |

### Missing Components Check

**Full functional quad needs**:
- Frame ✓
- 4x motors ✓
- 4x ESCs (or 4-in-1) ✓
- Flight controller (we'll replace with Pixhawk) ⚠️
- Propellers ✓
- Battery ✓
- Receiver (we'll use telemetry radio) ⚠️
- GPS (we'll add) ⚠️

---

## Inspection Checklist

### Physical Inspection

**Frame**:
- [ ] No cracks in carbon fiber (check arms, plates)
- [ ] Mounting holes not stripped
- [ ] Standoffs present and threaded
- [ ] Arms don't wiggle (check screws)

**Motors**:
- [ ] Spin smoothly by hand (no grinding)
- [ ] No bent shafts
- [ ] Bell doesn't rub against stator
- [ ] Magnets feel strong (resistance when turning)

**Electronics**:
- [ ] No burn marks on ESCs/FC
- [ ] No corrosion from crashes
- [ ] Solder joints look clean
- [ ] Wires not frayed

### Test Before Buying (if possible)

- [ ] Motors spin up without smoke
- [ ] ESCs beep normally on power
- [ ] No magic smoke on power-up
- [ ] USB connects to FC (if present)

### Questions to Ask Seller

1. "What's the total AUW (all-up weight) with battery?"
2. "What motors and what KV?"
3. "Has it been crashed? Where?"
4. "Is the flight controller 30.5x30.5mm mount?"
5. "What's included - just frame or full quad?"
6. "Why are you selling?"

---

## Negotiation Strategy

### Fair Pricing Guide

| Item | New Price | Good Used | Target Price |
|------|-----------|-----------|--------------|
| 7" frame (Chimera7) | $60-80 | $40-60 | $35-50 |
| 2807 motors (set of 4) | $80-120 | $50-80 | $40-60 |
| 4-in-1 ESC 50A | $60-80 | $40-60 | $30-50 |
| Full bind-n-fly quad | $400-600 | $250-350 | $200-300 |

### Bundle Deals to Look For

**Best value**: Someone selling FPV gear to quit the hobby
- Often includes: quad + goggles + radio + batteries
- Keep quad, sell goggles/radio separately

### Negotiation Scripts

**For frames only**:
> "I'm looking for just the frame and motors to build a photography drone. Would you sell just those parts? I don't need the FPV gear."

**For testing**:
> "Would you mind if I power it up with my battery to check the motors spin before buying?"

**For price**:
> "I see a similar setup sold for $X last week. Would you take $Y?"

---

## Search Strategy

### Comprehensive Search Terms

Use these exact search terms on Facebook Marketplace:

#### Primary Targets (Best Results)
1. "7 inch FPV drone"
2. "Chimera7"
3. "iFlight long range"
4. "2807 motors"
5. "6S drone"
6. "Rekon7"
7. "cinelifter"
8. "FPV long range"

#### Secondary Terms (Wider Net)
9. "FPV drone 7 inch"
10. "heavy lift drone"
11. "camera drone FPV"
12. "dji air unit drone"
13. "analog FPV drone"
14. "GPS drone FPV"
15. "crossfire drone"

#### Brand-Specific (High Quality)
16. "iFlight drone"
17. "HGLRC drone"
18. "Flywoo drone"
19. "TBS drone"
20. "GEPRC drone"

#### Full Kit Terms
21. "bind and fly drone"
22. "BNF drone 7 inch"
23. "FPV quad complete"
24. "drone with goggles"
25. "drone with radio"

#### Hobby Exit Terms (Best Deals)
26. "getting out of FPV"
27. "selling drone gear"
28. "FPV lot for sale"
29. "drone equipment sale"
30. "hobby clearout"

### Facebook Marketplace Filters

**Location**: Your city + 100km radius (worth driving for right deal)

**Price Filters**:
- Minimum: $50 (filters out toys)
- Maximum: $600 (full kits with FPV gear)

**Categories**:
- Electronics → "Other"
- Hobbies & Collectibles → "Radio Control"
- Sporting Goods → "Other"

**Condition**:
- Used - Good
- Used - Fair (if confident in repairs)

### Setting Up Alerts

1. Save searches with notification bell
2. Check 3x daily (good deals go fast)
3. Enable "Show results within 100km"
4. Sort by "Newly listed" (not price)

### Alternative Marketplaces

| Marketplace | Best For | URL/Access |
|-------------|----------|------------|
| **Kijiji** | More FPV gear in Canada | kijiji.ca |
| **r/fpvclassifieds** | Quality gear, US/CA shipping | reddit.com/r/fpvclassifieds |
| **Rotorbuilds** | Builder community | rotorbuilds.com/classifieds |
| **FPV Exchange (FB)** | Active Canadian community | Facebook search "FPV Exchange Canada" |
| **Canadian Drone Hub** | Local Canadian deals | Facebook groups |
| **RCGroups** | Forum marketplace | rcgroups.com |

### Timing Strategy

| When | Why |
|------|-----|
| **Thursday-Sunday** | Most people post on weekends |
| **First thing morning** | Beat other buyers |
| **End of month** | People need money, negotiable |
| **After Christmas** | Gift returns, upgrades |
| **Spring (April-May)** | Winter project clearouts |

---

## Evaluating Full Kits on Marketplace

### Step-by-Step Evaluation Process

When you find a complete quad listing:

#### Step 1: Extract Specs from Photos/Description

Look for these visual cues:
- **Motor size stamped on bell**: "2807" or "2207"
- **Motor KV on sticker**: "1300KV" or "1500KV"
- **Prop size**: Count holes (3-blade vs 5-blade)
- **Battery connector**: XT60 (4-6S) vs XT30 (2-3S)
- **Stack height**: How many boards visible?

#### Step 2: Request These Photos from Seller

```
"Hi! Interested in your drone. Could you send:
1. Close-up photo of one motor (to see size/KV)
2. Photo of the flight controller stack
3. Photo of battery connector
4. What battery size/cells do you run?
5. Total weight with battery?
Thanks!"
```

#### Step 3: Decode the Specs

| What You See | What It Means |
|--------------|---------------|
| "2807" on motor | 28mm diameter, 7mm height - GOOD |
| "1300KV" | Low KV, likely 6S - GOOD |
| "2400KV" | High KV, likely 4S - OK |
| "4S 4000mAh" on battery | 4-cell, medium capacity - OK |
| "6S 3000mAh" | 6-cell, good for payload - GOOD |
| "50A" on ESC | 50 amp ESCs - GOOD |
| "20A" on ESC | Too small for heavy lift - AVOID |
| "Chimera7" frame | Perfect 7" deadcat - GOOD |
| "Apex 5" frame | 5" freestyle - AVOID |
| "DJI Air Unit" | FPV system - SELL SEPARATELY |

#### Step 4: Calculate TWR

Example conversation with seller:

```
Seller: "iFlight Chimera7, 2807 1300KV, 6S 4000mAh, about 700g"

Your calculation:
- Motors: 2807 1300KV on 6S = ~2,100g per motor (from table)
- Total thrust: 2,100g × 4 = 8,400g
- Their AUW: 700g
- + Our payload: 130g
- Total AUW: 830g
- TWR: 8,400 / 830 = 10.1:1 ✅ EXCELLENT

Action: Contact immediately, this is perfect!
```

---

## Kit Pricing Guide

### What's a Good Deal?

| Configuration | New Price | Good Used | Great Deal | Steal |
|---------------|-----------|-----------|------------|-------|
| **Frame only (7")** | $60-80 | $40-60 | $30-40 | <$30 |
| **Motors 4x (2807)** | $100-140 | $60-90 | $40-60 | <$40 |
| **ESC 4-in-1 (50A)** | $70-90 | $40-60 | $30-40 | <$25 |
| **Full quad (no FPV)** | $400-500 | $250-350 | $180-250 | <$150 |
| **Full quad + FPV gear** | $600-900 | $400-600 | $300-400 | <$250 |
| **Frame + motors only** | $160-220 | $100-140 | $70-100 | <$60 |

### Value Assessment Formula

```
Quick Value Calculation:
Frame:        $___
Motors 4x:    $___
ESC:          $___
Other parts:  $___
--------------------
Total Value:  $___

Asking Price: $___

If Asking < 70% of Total Value → Good deal
If Asking < 50% of Total Value → Excellent deal
```

### Bundle Deal Opportunities

**Best Value**: Someone "getting out of FPV"
- Often selling: quad + goggles + radio + batteries + charger
- You want: quad only
- Sell the rest separately
- Net cost can be 50-70% less

**Example**:
```
Seller asking: $600 for full kit
  - Quad worth: $350
  - Goggles worth: $200
  - Radio worth: $100
  - Batteries worth: $150
  - Total value: $800

You pay: $600
Sell goggles: -$200
Sell radio: -$100
Sell batteries: -$150
--------------------
Net cost for quad: $150 ✅
```

---

## Action Items

### Immediate

1. **Confirm Canadian regulations** (Google AI search in progress)
   - What exactly counts toward 250g?
   - Registration requirements if over
   - Operating restrictions

2. **Set Marketplace alerts**
   - "7 inch drone"
   - "Chimera7"
   - "FPV cinelifter"

3. **Research Pi Zero 2W as alternative**
   - Weight: 16g vs 46g (Pi 4)
   - MAVSDK-Python compatibility
   - Processing power for YOLO-nano

### Weight Budget Calculation

Once we confirm the exact regulation interpretation, calculate:

```
Frame (target <100g)     = ___g
Motors 4x (target <80g)  = ___g
ESCs 4-in-1 (<30g)       = ___g
Pixhawk 6C Mini (25g)     = ___g
Pi Zero 2W (16g)          = ___g
Pi Camera 3 (3g)        = ___g
Battery (target <200g)    = ___g
Misc (cables, mounts)     = ___g
-------------------------------
TOTAL TAKEOFF WEIGHT      = ___g

Target: <250g
Margin: ___g
```

---

## Next Steps

1. Wait for Canadian regulation confirmation
2. Adjust weight budget accordingly
3. Start Marketplace searches with defined criteria
4. Prioritize 7" frames with 30.5mm FC mount

---

*Last Updated: 2026-04-10*  
*Status: Pending Canadian regulation confirmation*
