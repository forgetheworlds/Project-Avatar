# Claude vs Kimi — Research Comparison

**Date:** 2026-07-28
**Purpose:** Identify agreements, disagreements, and which report is more trustworthy on each point.

---

## Executive Summary

The Kimi report is **more thorough, more cautious, and more correct** on most points. The Claude report made several assumptions that Kimi's deeper research invalidated:

| Topic | Claude Said | Kimi Said | Who's Right |
|-------|-------------|-----------|-------------|
| Hull shape | Catamaran | **Monohull (Deep V)** | **Kimi** — better wave handling, self-righting via flood chamber, fewer parts |
| Propulsion | Twin prop (differential thrust) | **Jet drive** | **Kimi** — eliminates hull penetrations (main leak source), cheaper, simpler |
| Budget | $69-100 USD | **$117-167 CAD** | **Kimi** — more honest accounting with library fees and HST |
| Motor | 3660 2600KV or 2x 2845 | **2838 brushless (Surpass KK combo)** | **Kimi** — right-sized for monohull, includes water cooling |
| Self-righting | Catamaran geometry = stable | **Flood chamber** | **Kimi** — actually solves the flipping problem |
| Library constraints | Assumed free printing | **$2/job + $0.12/g + HST + 8hr cap** | **Kimi** — discovered the actual library pricing |

---

## Detailed Point-by-Point Comparison

### 1. HULL SHAPE — Major Disagreement

**Claude:** Catamaran recommended. Self-righting by geometry (wide beam + sealed deck). Two narrow hulls fit S3 bed easily.

**Kimi:** Monohull (Deep V) recommended. Self-righting via flood chamber. Single shell = fewer joints = fewer leaks. Better wave handling.

**Analysis — Kimi is right.** The key evidence:

- **Catamaran CANNOT self-right** when flipped upside down — it floats stable inverted. The Claude report assumed catamarans are inherently self-righting, which is wrong. Catamarans are stable upright AND inverted (both are stable equilibrium points). A monohull with a flood chamber actually rights itself.
- **Wave handling:** Deep V slices chop; catamaran tunnel slams. For a small lake with wind chop, the monohull wins.
- **Printability:** 2-3 segments vs 4-6. Fewer joints = fewer leak points.
- **Library cost:** ~$29-38 for monohull vs $45-68 for catamaran (at $0.12/g + $2/job + HST).
- **Buoyancy:** 400mm monohull displaces 1.57L (safe all-up ~0.94kg). Two slim catamaran sponsons only displace 1.39L (~0.83kg safe). Monohull has MORE payload margin.

**Where Claude was right:** Catamaran IS faster on flat water (aerodynamic tunnel lift). But for a lake with chop and an autonomous boat, speed is less important than survivability.

### 2. PROPULSION — Major Disagreement

**Claude:** Twin 2845 props with differential thrust. Free steering, redundancy, chop performance.

**Kimi:** Single 2838 brushless with 3D-printed jet drive and steerable nozzle. Zero hull penetrations, cheaper, simpler.

**Analysis — Kimi is right for v1.** The key evidence:

- **Hull penetrations are the #1 leak source** in home-built RC boats. A conventional shaft drive needs 2 holes through the hull (shaft tube + rudder post). Jet drive needs 0-1. For a budget boat where waterproofing is the critical concern, this matters enormously.
- **Jet drive is free** — printed with the hull (open-source FJD designs on RCGroups). Shaft+strut+rudder+prop costs ~$35 USD.
- **The efficiency loss (15-25%) is acceptable** for an AI patrol boat that cruises at 20-60W. You're not racing.
- **Differential thrust sounds elegant** but introduces motor mismatch as a constant yaw disturbance. Single motor + steerable nozzle gives a cleaner PID plant.

**Where Claude was right:** Twin props DO give redundancy and better chop performance. But for v1, simplicity and waterproofing win. A prop conversion later is ~$25-50 hardware swap.

### 3. MOTOR SELECTION

**Claude:** 3660 2600KV (single) or 2x 2845 3000KV (twin). $12-22 USD.

**Kimi:** 2838 brushless (Surpass Hobby KK) + 35A waterproof ESC + water-cooling jacket combo. ~$38 CAD (~$27 USD).

**Analysis — Kimi is more specific and better matched.** The 2838/2845 combo at $27 USD with water cooling is specifically designed for boat use. The 3660 is overkill for a 1.4kg monohull. Kimi also correctly notes that the water-cooling jacket is essential for sustained operation.

### 4. BUDGET — Major Disagreement

**Claude:** $69-100 USD (single motor) or $74-119 USD (twin). PLA free from library.

**Kimi:** $117 CAD (lean/brushed) / $150 CAD (recommended/brushless). Printing costs $29-38 for monohull, $45-68 for catamaran.

**Analysis — Kimi is right.** Kimi discovered critical constraints Claude missed:

1. **Library charges $2/job setup fee + $0.12/g + 13% HST.** PLA is NOT free.
2. **8-hour print job cap** — no single part can exceed ~200-300g.
3. **PVA support material costs $0.23/g** (double PLA rate). Design for zero supports.
4. **Charger costs $12-16 CAD** — Claude omitted this entirely.
5. **Battery costs $18-25 CAD** — Claude estimated $5-7 (too low for quality packs).

**The $50 target is not achievable** for a complete new build. The structural floor (compute + propulsion + power + print) is ~$75-90 CAD even with a scrounged battery.

### 5. SELF-RIGHTING — Claude Was Wrong

**Claude:** Catamaran is "inherently self-righting" due to wide beam.

**Kimi:** Catamaran CANNOT self-right when flipped. Monohull with flood chamber can.

**Analysis — Kimi is correct.** This is the most critical error in the Claude report. Catamarans have two stable equilibrium points (upright and inverted). The "self-righting catamaran" claim was wrong. The flood chamber mechanism (sealed side chamber that floods when capsized, offset weight rolls boat back) is the proven solution used on production RC boats like VectorSR80.

### 6. CONTROL LOOPS — Both Agree, Kimi Goes Deeper

**Claude:** 3-layer architecture (LLM 0.2-0.5Hz → Guardian 10-50Hz → PWM 50Hz). 10-35ms latency.

**Kimi:** 6-layer architecture (L0-L5). Same core insight but more granular. Adds L0 (hardware reflexes), L3 (ground guardian), L5 (human override).

**Key additional findings from Kimi:**
- HLA paper (AAMAS 2024): hierarchical agent cut atomic action latency from 0.71s to 0.08s
- Local LLM on MacBook: ~1-1.5s vs 3.5s cloud API
- JSON setpoints (20-40 tokens) vs code-as-policy (150 tokens) = 5s vs 1s
- Phone as hotspot (not ESP32 softAP) — ESP32 softAP causes 200ms packet clusters

**Both agree:** ESP32 handles all safety-critical loops. LLM steers mission, never hull. 50Hz PID is sufficient.

### 7. WATER CANNON — Both Agree

Both recommend: 5V submersible pump ($4), no onboard tank (lake water = infinite ammo), MOSFET switching, aim with the boat. Kimi adds the pump interlock safety rule (only fire when water sensor dry + throttle < 30%).

### 8. PRINTABILITY

**Claude:** 13 parts, 130-520 hours total, 2-4 weeks.

**Kimi:** 2-3 segments for monohull, each under 200-300g (8-hour cap). Much less print time.

**Kimi's 8-hour cap discovery changes everything.** Every part must be designed to print in under 8 hours at the library. This means:
- Hull segments must be small (under 200-300g each)
- Batch small parts onto single plates
- Zero supports (PVA costs double)

---

## What Claude Got Right

1. **ESP32 architecture** — correct that ESP32 replaces Pi+FC. Both agree.
2. **WiFi latency** — 10-35ms is accurate. Both agree on disabling power save.
3. **50Hz control loop** — sufficient for boats. Both agree.
4. **Epoxy coating for PLA** — both agree this is mandatory.
5. **Code-as-Policies reference** — both independently identified it as the relevant paper (Waddle Labs is defunct).
6. **Twin prop advantages** — the arguments are valid, just not the right priority for v1.

## What Claude Got Wrong

1. **Catamaran self-righting** — fundamentally wrong. Catamarans are stable inverted.
2. **Snap-fit assembly** — wave stress deforms PLA clips. Need bolts + epoxy.
3. **Budget estimates** — too low. Didn't account for library fees, HST, charger.
4. **Propulsion choice** — twin prop is over-engineered for v1. Jet drive is simpler and waterproof.
5. **Motor sizing** — 3660 is overkill for a 1.4kg monohull.
6. **PLA free from library** — it's $0.12/g + $2/job + HST.

## What Kimi Got Right That Claude Missed

1. **Library 8-hour print cap** — critical constraint on part size
2. **Library pricing model** — $2/job + $0.12/g + HST
3. **Flood chamber for self-righting** — proven mechanism for monohulls
4. **Jet drive eliminates hull penetrations** — #1 leak source
5. **Phone hotspot (not ESP32 softAP)** — prevents packet clustering
6. **Local LLM on MacBook** — eliminates cloud latency
7. **Battery as ballast** — densest component, put it low in hull
8. **PLA brittleness** — bow is sacrificial, keep g-code handy for reprint
9. **Test plan** — bench → bathtub flip test → pond → tethered autonomy → full LLM

---

## Recommendation

**Follow the Kimi report's design decisions:**
- **Monohull (Deep V)** with flood chamber for self-righting
- **Jet drive** (3D printed, FJD design) — zero hull penetrations
- **Single 2838 brushless** with water-cooled ESC combo
- **3S 2200mAh LiPo** (upgrade to 5200mAh later)
- **ESP32-S3** (not plain ESP32) with external antenna

**Keep the Claude report's control loop architecture** — the 3-layer design (LLM → Guardian → PWM) is solid and both reports agree on it.

**The realistic budget is $117-167 CAD** for a complete new build, or **$86-106 CAD** if you already own a battery + charger.

---

## Sources

Both reports drew from:
- RCGroups forums (waterproofing, 3D printed boats, jet drives)
- BoatDesign.net (engineering thread)
- RCBoatHQ (jet vs prop comparison)
- Arctic Challenge build log
- Code as Policies (arXiv:2209.07753)
- ESP-IDF documentation
- Mississauga Library makerspace pricing

Kimi additionally used:
- EXHOBBY hull guide (catamaran vs monohull vs hydroplane)
- Model Boat Mayhem (power rules of thumb)
- HLA paper (AAMAS 2024) for latency analysis
- Snapmaker blog (waterproofing testing)
- Amazon.ca for Canadian pricing
- Prusa forum (pressure testing PLA vs PETG)
