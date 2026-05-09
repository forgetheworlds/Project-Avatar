# Marketplace Hunting Guide

**Purpose**: Systematic approach to finding suitable drone hardware on Facebook Marketplace for Project Avatar.

---

## Contents

1. **[Marketplace Strategy](01-marketplace-strategy.md)** - Search approach, compatible frames, red flags
2. **[Thrust Calculator](02-thrust-calculator.md)** - TWR calculations, motor database, evaluation formulas
3. **[Canadian Drone Laws](03-canadian-drone-laws.md)** - Transport Canada regulations, 250g threshold

---

## Quick Start

### You Are Here Because

You need to find a drone on Facebook Marketplace that can:
1. Lift Project Avatar payload (~130g: RPi + camera + radio + GPS)
2. Have sufficient thrust (2:1 TWR minimum, 3:1 ideal)
3. Accommodate Pixhawk 6C Mini (30.5x30.5mm mount)
4. Meet Canadian regulations (likely >250g, requiring registration)

### The 250g Reality

**You asked**: "Does weight only refer to the drone and not what we put on it?"

**Answer**: Unclear pending Transport Canada confirmation, but most likely interpretation is **total weight as flown** (AUW - All-Up Weight) including payload.

**Our situation**:
- RPi 4 (46g) + Camera (3g) + Radio (15g) + GPS (25g) + Battery (~400g) + Frame (~200g) + Motors (~140g)
- **Total: ~900g** (far exceeds 250g)

**Implication**: We accept >250g and get Basic Operations certificate (free online exam).

---

## Target Specs (Main Factor: Thrust)

**You said**: "Main factor is the thrust power I think"

**You're absolutely right.**

### What to Look For

| Spec | Minimum | Ideal |
|------|---------|-------|
| Frame size | 7" | 7-10" |
| Motors | 2807 1300KV | 2807 1500KV |
| Battery | 6S 3000mAh | 6S 4000mAh |
| TWR with payload | 2:1 | 3:1+ |

### Why 7" Frame with 2807 Motors

**Thrust calculation**:
- 2807 1300KV on 6S: ~1900g per motor
- 4 motors: ~7600g total thrust
- AUW with payload: ~900g
- **TWR: 8.4:1** → Responsive, safe, room for maneuvers

---

## Search Terms for Facebook Marketplace

### Use These

1. "7 inch FPV drone"
2. "Chimera7"
3. "iFlight long range"
4. "2807 motors"
5. "Cinelifter"
6. "6S drone"
7. "Pixhawk" (if lucky)

### Avoid These

1. "DJI Mini" (closed system, no Pixhawk)
2. "Toy drone" (insufficient thrust)
3. "Tiny whoop" (2-3 inch, can't lift payload)
4. "Racing drone" (wrong optimization)

---

## Evaluation Workflow

### Step 1: Identify Motor Specs

Ask seller: "What motors? Size and KV?"

### Step 2: Calculate Thrust

Use table in [02-thrust-calculator.md](02-thrust-calculator.md):
- 2807 1300KV on 6S = ~1900g per motor
- Total = 1900g × 4 = 7600g

### Step 3: Calculate Weight

Ask seller: "What's the AUW with battery?"

Add our payload (~130g) to their answer.

### Step 4: Calculate TWR

```
TWR = Total Thrust / Total Weight
TWR = 7600g / (Seller's AUW + 130g)
```

### Step 5: Decision

- TWR < 2:1 → Skip
- 2:1 ≤ TWR < 3:1 → Marginal, keep looking
- TWR ≥ 3:1 → Good candidate

---

## Questions to Ask Sellers

1. **"What motors? Size and KV rating?"** (for thrust calc)
2. **"What battery? 4S or 6S? Capacity?"** (for weight/thrust)
3. **"What's the total flying weight?"** (AUW)
4. **"What frame is it?"** (for mount pattern verification)
5. **"Has it been crashed? Motor damage?"** (bent shafts = less thrust)
6. **"Why are you selling?"** ("too heavy" = perfect for us!)
7. **"Can I power it on to check motors spin?"** (pre-purchase test)

---

## Red Flags (Skip These)

| Red Flag | Why Skip |
|----------|----------|
| "No test, as-is" | Could be dead electronics |
| Motors <2306 size | Insufficient torque |
| Only 3S battery | Insufficient voltage for payload |
| No FC photos | Hidden damage |
| Too cheap (<$50) | Stolen or broken |
| Toy-grade frame | Won't survive Project Avatar use |
| 20x20mm FC mount only | Pixhawk needs 30.5x30.5mm |

---

## Canadian Compliance (If >250g)

### What We Need

1. **Register drone** - $5, mark with number
2. **Basic certificate** - Free online exam, 35 questions, 65% pass
3. **Follow rules** - VLOS, >30m from people, altitude limits

### What We Can Do (Basic Ops)

- Fly in uncontrolled airspace
- Fly >30m from bystanders
- Stay VLOS
- Max 122m altitude
- Log flights

### What We Cannot Do (without Advanced)

- Fly over people
- Fly in controlled airspace
- Fly <5.6km from airports

---

## Alternative Marketplaces

If Facebook Marketplace is dry:

1. **Kijiji** (more FPV gear in Canada)
2. **r/fpvclassifieds** (Reddit)
3. **Rotorbuilds** (classifieds)
4. **Local FPV Facebook groups**

---

## Decision Matrix

| Seller Has | TWR Est. | Verdict | Action |
|------------|----------|---------|--------|
| 7" frame + 2807 motors + 6S | 8:1 | ✅ Perfect | Buy if price fair |
| 7" frame + 2806 motors + 6S | 7:1 | ✅ Good | Negotiate down |
| 5" frame + 2207 motors + 4S | 9:1 | ⚠️ Thrust OK, frame small | Skip (tight build) |
| 7" frame + 2207 motors + 4S | 7:1 | ⚠️ Motors undersized | Skip |
| Unknown motors | ? | ❌ Can't evaluate | Ask for specs |

---

## Next Steps

1. Set Marketplace alerts: "7 inch drone", "Chimera7", "2807 motors"
2. When listing found, use [Thrust Calculator](02-thrust-calculator.md)
3. Verify TWR ≥ 3:1 before contacting seller
4. Ask inspection questions before meeting
5. Power on test before buying (motors spin smoothly)
6. Register with Transport Canada after purchase
7. Get Basic certificate before first flight

---

*Created: 2026-04-10*  
*Main factor: Thrust power*
