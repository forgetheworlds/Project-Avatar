# Avatar FPV Drone — Canadian Hardware Sourcing Guide


**Author:** Researcher  
**Date:** June 30, 2026  
**Status:** Complete (medium-high confidence)  
**Context:** Sourcing for 15-item BOM from Project-Avatar (FPV water-gun drone build)

---

## Methodology

- **Tools used:** DuckDuckGo (DDGS), TinyFish, Tavily confirmatory searches
- **Canadian vendors identified:** Rotor Village (ON), EpicFPV (ON/QC), Rotorgeeks (QC), RoboFusion Canada, Great Hobbies (national chain), Amazon.ca
- **Exchange rate:** ~1.40 CAD/USD (June 2026)
- **Synthesis rounds:** 3 (subagent deep research -> DDGS vendor ID -> price verification)
- **Confidence:** MEDIUM (80%) — prices verified from vendor sites, stock may shift. Some +/-$5-10.

---

## Component Sourcing Table

| # | Component | Part | Best CAN Vendor | CAD Price | Stock | Ship ON | Alt |
|---|-----------|------|-----------------|-----------|-------|--------|-----|
| 1 | FC+ESC | MicoAir H743 AIO 35A | Rotor Village (rotorvillage.ca) | ~$89.99 | In stock | 2-5d | RoboFusion ~$89, Amazon H743 stack ~$95 |
| 2 | Frame | SpeedyBee Master3X 3-3.6 | Rotor Village or EpicFPV | ~$44.99 | In stock | 2-5d | AliEx $42 (2-4wk), SpeedyBee direct $42 (7-14d) |
| 3 | Motors x4 | 1505 3800KV | EpicFPV (epicfpv.ca) | ~$16.99ea = $67.96 | Check stock | 2-5d | AliEx $56/set (3-5wk), SpeedyBee 1507 $18.99ea |
| 4 | Props x8 | Gemfan 3.5 tri-blade | Rotorgeeks (rotorgeeks.com) | ~$6.99/4pk x2 = $13.98 | Stocked | 3-6d | Amazon.ca $8.99/4pk, AliEx $3.50/4pk (3-5wk) |
| 5 | GPS | GOKU GM10 Nano V3 | Rotor Village or EpicFPV | ~$39.99 | Sp order | 3-7d | AliEx $34 (2-4wk), NewBeeDrone M10Q $28 (US) |
| 6 | ESP32 x2 | XIAO ESP32-S3 | Amazon.ca | ~$26.99ea = $53.98 | Prime | 1-3d | DigiKey $26ea, uni-solder $25ea, AliEx $14ea (3-5wk) |
| 7 | RX | ELRS Nano RX 2.4GHz | Rotor Village (SpeedyBee Nano) | ~$24.99 | In stock | 2-5d | Amazon.ca $29.99, AliEx $14 (2-4wk) |
| 8 | Battery x2 | 4S 850mAh XT30 LiPo | Great Hobbies (CNHL MiniStar 70C) | ~$29.99ea = $59.98 | CNHL CA whse | 3-7d | Amazon $34.99ea, RV $32.99ea, AliEx $20ea |
| 9 | Camera | Hawkeye Thumb 4K | Amazon.ca (Lilianos variant) | ~$69.99 | Varies | 1-3d | Makerfire CA $79.99 (Thumb 2), AliEx $67 (2-4wk) |
| 10 | Pump | Micro diaphragm 12V | Amazon.ca | ~$9.99 | Prime | 1-3d | Princess Auto $7.99, AliEx $4.50 (3-5wk) |
| 11 | Servo x2 | MG90S metal gear | Amazon.ca | ~$5.99ea = $11.98 | Prime | 1-3d | Great Hobbies $7.99ea, 10pk $29.99, AliEx $3ea |
| 12 | Reservoir | 15ml syringe/IV bag | Amazon.ca (10pk luer-lock) | ~$5.99 (10pk) | Prime | 1-3d | Dollarama $2.50, AliEx $1.50 (3-5wk) |
| 13 | Nozzle | 3D printed or brass | Self-print / Mississauga Library | ~$0.00 | N/A | 0d | Amazon brass nozzle $6.99, AliEx $3 |
| 14 | MOSFET | IRFZ44N N-Channel | DigiKey.ca or Amazon.ca | ~$2.49 / $4.99 (5pk) | In stock | 3-5d/1-3d | Sayal Electronics Mississauga $1.50, AliEx $1 |
| 15 | Wiring | Silicone 16-22AWG + JST | Amazon.ca (wire kit + JST kit) | ~$14.99+$8.99 = $23.98 | Prime | 1-3d | AliEx $5.99 (3-5wk), DigiKey $18 |

---

## Total Cost Estimates

### Option A: Fastest (All Canadian + Amazon Prime) — ~$535 CAD

| Source | Items | Cost |
|--------|-------|------|
| Rotor Village | FC+ESC + Frame + RX | ~$159.97 |
| EpicFPV | Motors x4 | ~$67.96 |
| Rotorgeeks | Props x2 | ~$13.98 |
| Great Hobbies | Batteries x2 | ~$59.98 |
| Amazon.ca Prime | ESP32x2 + Camera + Pump + Servox2 + Reservoir + MOSFET 5pk + Wiring+JST | ~$180.90 |
| Self-print | Nozzle | $0.00 |
| **Total (+~$50 shipping)** | | **~$535 CAD** |

**Delivery: 3-7 business days.**

### Option B: Balanced (Canadian now + AliExpress economy) — ~$490 CAD

Order core Canadian items (FC, Frame, RX, Batteries, ESP32) now + slow AliExpress (Motors, Props, Camera, GPS, extras) simultaneously.
Build starts 1 week. Full build: 3-5 weeks.

### Option C: Max Economy (AliExpress everything) — ~$392 CAD

All components from AliExpress + Amazon.ca essentials + self-print nozzle.
Delivery: 3-5 weeks. Not recommended for time-sensitive build.

---

## Bundle Deals

| Bundle | Price | Savings |
|--------|-------|---------|
| MG90S 10-pack (Amazon.ca) | ~$29.99 | ~$30 vs singles |
| Silicone Wire Kit + JST Kit (Amazon.ca) | ~$23.98 | Best wiring value |
| CNHL MiniStar 2-pack (Great Hobbies) | ~$59.98 | ~$10 vs single |

---

## Critical Component Alternatives

| Component | Primary | Alt 1 | Alt 2 | Key Note |
|-----------|---------|-------|-------|----------|
| FC+ESC (1) | MicoAir H743 AIO 35A | SpeedyBee F405 V4 (~$65, fewer UARTs) | Matek H743 (~$89, wider avail) | MicoAir niche. F405 lacks UARTs for ESP32+GPS+ELRS+camera |
| Frame (2) | SpeedyBee Master3X | iFlight XL3 V5 (~$49) | Flywoo GOKU (~$39) | Master3X best for modular payload mounting |
| Motors (3) | 1505 3800KV x4 | SpeedyBee 1507-3600KV (~$18.99ea) | iFlight 1505 (~$15.99ea) | 1507 heavier but more torque for water payload |
| Camera (9) | Hawkeye Thumb 4K | Hawkeye Thumb 2 (~$79.99 Makerfire) | RunCam Thumb 2 (~$99 Great Hobbies) | Thumb 4K best value. Thumb 2 reliable fallback |

---

## Canadian Vendor Quick Reference

| Vendor | Type | Ship ON | FPV? | Notes |
|--------|------|---------|------|-------|
| Rotor Village (rotorvillage.ca) | FPV spec ON | 2-5d | YES | Best: FC, Frame, RX. CAD pricing |
| EpicFPV (epicfpv.ca) | FPV spec | 2-5d | YES | Motors, frames. CAD pricing |
| Rotorgeeks (rotorgeeks.com) | FPV spec QC | 3-6d | YES | Props, batteries. Ships from Canada |
| RoboFusion Canada | Drone comp | 3-7d | YES | MicoAir H743 at good price |
| Great Hobbies | RC chain PEI/ON | 3-7d | PART | Batteries, servos. National stores |
| Amazon.ca | General | 1-3d | NO | ESP32, pump, servo, wiring. Prime |
| DigiKey Canada | Components | 3-5d | NO | MOSFETs. Flat $8 shipping |
| AliExpress | China import | 14-35d | YES | Lowest prices. Duties risk >$40 CAD per order |
| Sayal Electronics | Mississauga walk-in | Same day | NO | MOSFETs, wire. 1315 Derry Rd E |
| Princess Auto | Mississauga | Same day | NO | Cheap pumps on Mavis Rd |

---

## Key Decisions

1. **Split order strategy:** Canadian items NOW (Rotor Village + Amazon.ca) + AliExpress spares in parallel.
2. **Camera is hardest to source in Canada:** Hawkeye Thumb 4K limited domestic stock. Thumb 2 at Makerfire CA $79.99 is reliable fallback.
3. **MicoAir H743 confirmed at Rotor Village.** If unavailable: Matek H743 is more available at Canadian stores.
4. **AliExpress tactic:** Keep orders under $40 CAD each to avoid CBSA duties. Split into 2-3 small orders.
5. **Local Mississauga options:** Sayal Electronics (1315 Derry Rd E) for components. Central Library has free 3D printing for nozzle.

---

## Decision

**Option A (~$535 CAD all-in) — fastest build, 3-7 business days.** The $143 premium vs max AliExpress saves 3-4 weeks. Worth it for time-sensitive school game build.

## Next Action

**Order Canadian items today:**
1. Rotor Village: FC+ESC ($89.99), Frame ($44.99), ELRS RX ($24.99)
2. EpicFPV: Motors x4 ($67.96)
3. Great Hobbies: Batteries x2 ($59.98)
4. Amazon.ca: ESP32 x2 ($53.98), Camera ($69.99), Pump ($9.99), Servo x2 ($11.98), Syringes ($5.99), Wiring+JST ($23.98), MOSFET 5pk ($4.99)
5. AliExpress (optional): Backup motors + props + servos for spares (~$70)

## Deadline

**Order within 48 hours (by July 2)** for delivery by July 7-10. Build start: July 7 weekend.

## Who Handles Next

**Muadh** — authorizes purchase orders and checks cart totals against budget. Researcher can compile direct cart links on request.

---

*Sourced June 30, 2026. Prices verified via DDGS/TinyFish searches of Canadian vendor sites. Stock may shift — verify before purchasing.*
