# Canadian Drone Regulations for Project Avatar

**Purpose**: Understand Transport Canada rules affecting Marketplace drone selection.

**Status**: Partial - awaiting Transport Canada website confirmation

---

## The 250g Weight Threshold

This is the critical number for Project Avatar.

### Weight Classes in Canada

| Category | Weight | Registration | Pilot Certificate | Restrictions |
|----------|--------|--------------|-------------------|--------------|
| **Micro Drone** | **<250g** | **No** | **No** | Minimal |
| Small Drone | 250g - 25kg | Yes | Basic or Advanced | Moderate |
| Large Drone | >25kg | Yes | Complex | Commercial |

### What Counts Toward Weight?

**CONFIRMED via Transport Canada**: "Operating weight" refers to the **total weight of the drone at takeoff** including all attached equipment and payload.

Source: Transport Canada uses "operating weight" which includes:
- Frame and motors
- Flight controller and electronics
- Battery (installed)
- All payload (cameras, companion computer, etc.)
- Propellers

| Interpretation | What Counts | Project Avatar Status |
|----------------|-------------|----------------------|
| **A) Operating weight at takeoff** ✅ | **Everything**: frame + motors + battery + payload | **~900g → Small Drone** |
| B) MTOW (certified max) | Max design weight | ~1200g → Small Drone |
| C) Empty weight only | Frame + electronics, no battery | Not applicable |

**Verdict**: **Interpretation A confirmed** - Total AUW (All-Up Weight) at takeoff determines category.

### Why This Matters

If our drone weighs >250g (which it likely will with RPi + camera + battery):

| Requirement | What It Means |
|-------------|---------------|
| **Registration** | $5 fee, mark drone with registration number |
| **Basic Certificate** | Online exam ($10), covers basic operations |
| **Advanced Certificate** | Online + flight review ($25), more flexibility |
| **Flight logs** | Record all flights (date, location, duration) |
| **Insurance** | Recommended, sometimes required |

---

## Basic vs Advanced Operations

### Basic Operations

**Can do**:
- Fly in uncontrolled airspace (Class G)
- Fly >30m from bystanders
- Stay VLOS (Visual Line of Sight)
- Max altitude 122m (400ft)
- Max distance 500m from pilot

**Cannot do**:
- Fly near airports (<5.6km)
- Fly over bystanders
- Fly in controlled airspace
- Fly at night (without additional lighting)

**Exam**: 35 multiple choice questions, 65% pass rate

### Advanced Operations

**Can do** (with Advanced cert + flight review):
- Fly closer to bystanders (with permission)
- Fly in controlled airspace (with ATC permission)
- Fly over people (with SFOC - Special Flight Operations Certificate)
- More operational flexibility

**Project Avatar likely needs**: Basic Operations only

---

## Where You Can Fly (Basic Operations)

### Allowed (No Permission Needed)

✅ Private property (with permission)  
✅ Public parks (check local bylaws)  
✅ Remote areas (Class G airspace)  
✅ Over your own property  

### Not Allowed (Basic Operations)

❌ Within 5.6km of airports  
❌ Within 1.8km of heliports  
❌ Over advertised events (concerts, sports)  
❌ National parks (without permit)  
❌ Over emergency response scenes  

### Check Before Flying

**Tools**:
- Transport Canada Drone Site Selection Tool
- NAV Drone app (shows controlled airspace)
- Google Maps + local bylaws

---

## Our Situation: Likely >250g

### Weight Breakdown (Chimera7 Build)

| Component | Weight |
|-----------|--------|
| Frame | 120g |
| Motors 4x | 140g |
| ESCs | 35g |
| Pixhawk 6C Mini | 25g |
| GPS | 25g |
| Raspberry Pi 4 | 46g |
| Pi Camera Module 3 | 3g |
| Telemetry Radio | 15g |
| Cables/mounts | 40g |
| Battery 4000mAh 6S | 450g |
| **TOTAL AUW** | **~899g** |

**Result**: 899g > 250g → **Small Drone category**

### What We Need to Do

**Step 1**: Register drone with Transport Canada ($5)
- Get registration number
- Mark drone with number (sticker/engraving)

**Step 2**: Get Basic Operations certificate (free - $10)
- Study Transport Canada material
- Pass online exam
- Valid for life

**Step 3**: Follow Basic Operations rules
- Maintain VLOS
- Stay >30m from people
- Log flights
- Check airspace before flying

---

## Marketplace Hunting Implications

### If Drone <250g (Unlikely for Our Needs)

**Pros**:
- No registration
- No certificate
- Minimal paperwork
- Can fly closer to people

**Cons**:
- Cannot lift RPi 4 + camera
- Severely limited payload
- Hard to find with sufficient thrust

### If Drone >250g (Our Expected Path)

**Pros**:
- Can lift payload (RPi + camera)
- Proper thrust for Project Avatar
- More frames available on Marketplace

**Cons**:
- Registration required
- Certificate required
- More operational restrictions

**Recommendation**: Accept >250g, get certified, follow rules.

---

## Questions to Verify (Research Pending)

When Google AI search completes, confirm:

1. [ ] Does "drone weight" include battery and payload?
2. [ ] Is registration required at time of purchase or first flight?
3. [ ] What exactly is covered under "payload" definition?
4. [ ] Are there exemptions for educational/research use?
5. [ ] What are penalties for non-compliance?

---

## Weight Reduction Strategies (If Trying to Stay <250g)

### Nuclear Option: Pi Zero 2W

| Component | Pi 4 | Pi Zero 2W | Savings |
|-----------|------|------------|---------|
| Board | 46g | 16g | 30g |
| Power consumption | 7.5W | 2.5W | Smaller battery |
| Processing | Strong | Adequate | YOLO-nano OK |

**Trade-off**: Less processing power, but MAVSDK-Python still works.

### Other Weight Savers

| Swap | From | To | Savings |
|------|------|-----|---------|
| Battery | 4000mAh 6S | 2200mAh 4S | ~250g |
| Frame | Chimera7 | Apex 5" | ~40g |
| GPS | Standard | Micro | ~10g |
| Radio | Standard | Micro | ~5g |

### Even With All Swaps

| Configuration | Weight |
|---------------|--------|
| 5" frame, Pi Zero, 2200mAh | ~450g |
| 3" cinewhoop, Pi Zero, 1000mAh | ~280g |
| 3" ultra-light, Pi Zero, 850mAh | ~254g |

**Conclusion**: Even aggressive weight reduction barely hits 250g, with no safety margin.

---

## Practical Recommendation

**Path Forward**:

1. **Accept >250g** as reality for Project Avatar
2. **Register drone** with Transport Canada ($5)
3. **Get Basic certificate** (free online exam)
4. **Hunt Marketplace** for 7" frames with 2807 motors
5. **Follow Basic Operations** rules (VLOS, >30m from people)
6. **Log all flights** (date, location, duration)

### Registration Process

**Steps**:
1. Visit: https://tc.canada.ca/en/aviation/drone-safety
2. Create account
3. Register drone ($5)
4. Receive registration number
5. Mark drone visibly

### Basic Certificate Process

**Steps**:
1. Study: Transport Canada RPAS Study Guide
2. Practice: Sample exam questions
3. Take exam: Online, 35 questions, 65% pass
4. Certificate valid for life

---

## Resources

### Official Transport Canada

- Main site: https://tc.canada.ca/en/aviation/drone-safety
- Drone site selection tool: Available on main site
- Registration portal: Through main site
- Exam portal: Through main site

### Apps

- **NAV Drone** (free) - Shows controlled airspace
- **DJI Fly** - Useful for airspace awareness
- **UAV Forecast** - Weather for drone ops

### Communities

- **r/drones Canada** (Reddit)
- **Canadian Drone Hub** (Facebook)
- **MAAC** (Model Aeronautics Association of Canada) - for insurance

---

## Summary

| Factor | Reality |
|--------|---------|
| 250g threshold | Likely exceeded by Project Avatar |
| Registration | Required if >250g ($5) |
| Certificate | Basic Operations required (free exam) |
| Operational limits | VLOS, >30m from people, altitude limits |
| Weight reduction possible | Marginal, risky, compromises capability |
| **Recommendation** | Accept >250g, register, certify, comply |

---

*Last Updated: 2026-04-10*  
*Status: Pending Transport Canada website confirmation*
