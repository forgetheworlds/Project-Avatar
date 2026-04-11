# Project Avatar: $500 Hardware Budget Optimization Guide

## Executive Summary

This document provides a comprehensive procurement strategy to keep Project Avatar's Stage 1-2 hardware under $500 while maximizing capability and leaving room for Stage 3 depth camera expansion.

**Key Strategy**: Aggressive used purchasing (50-60% of retail), strategic component alternatives, and staged buying to spread costs.

---

## 1. Current Budget Analysis

### 1.1 Airframe: Holybro X500 V2

| Source | Price Range | Notes |
|--------|-------------|-------|
| **New (Holybro Official)** | $300-350 | Complete ARF kit with motors, ESCs, PDB, props, mounts |
| **New (GetFPV/Banggood)** | $280-320 | Occasional sales, check holiday promotions |
| **Used (Facebook/MP)** | $150-220 | Frame + motors + ESCs, often crash-damaged but repairable |
| **Used (FPV Groups)** | $120-180 | FPV community often selling 500mm class frames |

**Budget Target**: $150 via used deal (50% of new price)

**Alternative Airframes** (if X500 deal falls through):
| Frame | Used Price | Notes |
|-------|------------|-------|
| S500/S550 clone | $80-120 | Generic 500mm frames, compatible mounting |
| DJI F450/F550 | $100-150 | Older but robust, widely available used |
| Tarot 650 | $120-180 | Slightly larger, good for payload |

### 1.2 Flight Controller: Pixhawk Options

| Controller | New Price | Used Price | Notes |
|------------|-----------|------------|-------|
| **Pixhawk 6C** | $160-180 | $100-130 | Current gen, excellent PX4 support |
| **Pixhawk 6X** | $240-280 | $150-190 | Dual IMU, more robust, overkill for budget |
| **Pixhawk 4** | $120-150 (discontinued) | $80-100 | Older gen, still excellent, watch for clones |
| **Pixhawk 2.4.8** | $50-80 (clones) | $30-50 | Cheap clones, mixed reliability |
| **Pixhawk 5X** | $200-250 | $130-160 | Mid-range option |

**Budget Target**: $120 for used Pixhawk 6C

**Clone Warning**: Many "Pixhawk" boards on AliExpress for $30-50 are clones with:
- Inconsistent barometer quality
- Questionable IMU calibration
- Poor power regulation
- **Verdict**: Avoid for primary FC. Acceptable only as backup.

### 1.3 Companion Computer: Raspberry Pi Options

| Model | Used Price | New Price | Power | PX4 Suitability |
|-------|------------|-----------|-------|-----------------|
| **RPi 4 (4GB)** | $40-60 | $55-75 | 7.5W | Excellent, proven |
| **RPi 4 (2GB)** | $35-50 | $45-55 | 6W | Good for headless |
| **RPi Zero 2 W** | $15-25 | $15-20 | 2.5W | Marginal, very slow MAVSDK |
| **RPi 3B+** | $25-35 | $40 | 5W | Usable but dated |
| **CM4 + carrier** | $50-80 | $70-100 | 7W | Compact, good for custom mounts |
| **Orange Pi 5** | $50-70 | $80-100 | 8W | Faster CPU, PX4 community growing |

**Budget Target**: $50 for used RPi 4 4GB

**Recommendation**: The RPi 4 4GB is the proven standard. Zero 2 W will struggle with MAVSDK + camera streaming simultaneously. CM4 is compelling if building a custom carrier board, but adds complexity.

### 1.4 Camera Options

| Camera | Price | Resolution | Best For |
|--------|-------|------------|----------|
| **Raspberry Pi Camera v2** | $20-25 | 8MP | Budget option, proven compatibility |
| **Raspberry Pi Camera v3 (Wide)** | $35 | 12MP, AF | Better low light, wider FOV |
| **Raspberry Pi Camera v3 (NoIR)** | $35 | 12MP, AF | Night vision potential |
| **Generic USB 1080p webcam** | $15-25 | 2MP | Quick setup, no CSI cable needed |
| **Arducam 16MP IMX519** | $45-55 | 16MP | Higher resolution for VLM |
| **Logitech C920/C270** | $25-40 | 2MP | Robust, good drivers |

**Budget Target**: $30 (Pi Camera v2 or USB webcam)

**Upgrade Path**: Start with v2 ($25), upgrade to v3 Wide ($35) or Arducam ($50) in Stage 2 if vision quality is limiting.

---

## 2. Shopping Strategies

### 2.1 Best Sources by Category

| Source | Best For | Risk Level | Tips |
|--------|----------|------------|------|
| **Facebook Marketplace** | Airframes, used radios | Low-Medium | Meet local, inspect before buying |
| **FPV Facebook Groups** | Flight controllers, frames | Low | "Drone Flea Market", "Multirotor Classifieds" |
| **RCGroups Classifieds** | Premium used gear | Low | Vetted community, PayPal protection |
| **AliExpress** | New components, clones | Medium-High | Use stores with 95%+ rating, 30-day delivery |
| **Banggood** | New kits, batteries | Medium | Check reviews, slower shipping |
| **GetFPV/ReadyMadeRC** | New FCs, verified parts | Low | US-based, warranty support |
| **Amazon** | Pi accessories, cables | Low | Prime shipping, easy returns |
| **eBay** | Everything | Medium | Check seller ratings, use buyer protection |
| **Local hobby shops** | Emergency parts, advice | Low | Higher prices but immediate availability |

### 2.2 FPV/Drone Facebook Groups to Join

- **Drone Flea Market** (buy/sell/trade)
- **Multirotor Classifieds**
- **FPV Drone Enthusiasts** (your local city)
- **Pixhawk/PX4 Users Group**
- **Raspberry Pi Drones**

### 2.3 AliExpress Strategy

**Safe vendors for FCs**:
- Holybro Official Store (verified)
- CUAV Official Store
- MATEK Official Store

**What to buy on AliExpress**:
- Power distribution boards ($8-15)
- GPS modules ($12-25)
- Telemetry radios ($15-25)
- Propellers in bulk ($10 for 10 sets)
- BECs and voltage regulators ($5-12)
- Camera mounts and hardware ($10-20)

**What NOT to buy on AliExpress**:
- Primary flight controller (risk of clone/defective)
- Batteries (shipping restrictions, questionable cells)
- High-current ESCs (quality control issues)

### 2.4 Bundle Hunting

Look for these high-value bundles:

| Bundle Type | Expected Price | Savings |
|-------------|----------------|---------|
| "Complete 500mm build minus FC" | $200-250 | $100+ vs piecemeal |
| "Pixhawk + GPS + Telemetry" | $150-180 | $40-60 |
| "Frame + Motors + ESCs" | $120-180 | $50-80 |
| "Pi 4 kit + Camera + Case" | $70-90 | $20-30 |

---

## 3. Staged Purchase Strategy

### Stage 1: Minimum Viable (Weeks 1-4) - $350 Target

| Component | Strategy | Budget |
|-----------|----------|--------|
| Airframe + Motors + ESCs | Used from FPV group | $150 |
| Flight Controller | Used Pixhawk 6C | $120 |
| Raspberry Pi 4 4GB | Used/local | $50 |
| Cables, BEC, basic hardware | AliExpress bundle | $30 |
| **Stage 1 Total** | | **$350** |

**Priority**: Get flying with manual control first. RC radio assumed owned.

### Stage 2: Vision Addition (Weeks 5-8) - $100 Target

| Component | Strategy | Budget |
|-----------|----------|--------|
| Pi Camera v2 or USB cam | New/Amazon | $25-35 |
| Vibration dampening mount | AliExpress | $10-15 |
| Additional cables/connectors | Local/Amazon | $15-20 |
| Battery expansion (2x 4S) | Local used/FPV | $40-60 |
| **Stage 2 Total** | | **$90-130** |

**Running Total**: $440-480

### Stage 3: Depth & Payload (Months 4-6) - $150-250 Additional

| Component | Strategy | Budget |
|-----------|----------|--------|
| Intel RealSense D435i | Used eBay/FPV | $120-180 |
| Mounting hardware | 3D print/AliExpress | $20-30 |
| ESP32 + servos | Amazon/AliExpress | $15-25 |
| **Stage 3 Total** | | **$155-235** |

**Cumulative Total**: $595-715 (Stage 3 pushes over initial $500, planned separately)

### When to Buy What

| Week | Purchase | Rationale |
|------|----------|-----------|
| **Week -2** | Scout used listings, join groups | Build relationships, know prices |
| **Week 0** | Buy airframe + motors used | Longest lead time for inspection/repairs |
| **Week 1** | Buy FC + Pi simultaneously | Parallel work on bench setup |
| **Week 2** | AliExpress order (cables, hardware) | 2-3 week shipping, arrives for assembly |
| **Week 4** | Manual flight achieved | Validate airframe before camera investment |
| **Week 6** | Buy camera + streaming hardware | Only after telemetry bridge confirmed working |
| **Month 4+** | RealSense + payload | Only after vision system proven |

---

## 4. Hidden Costs & Budget Padding

### 4.1 Often Forgotten Items

| Item | Est. Cost | Notes |
|------|-----------|-------|
| **LiPo batteries (2-3x 4S 5000mAh)** | $30-50 each | Budget $100 for 3 quality used |
| **LiPo charger** | $40-80 | ISDT, HOTA D6 Pro recommended |
| **Battery bags/cases** | $15-25 | Safety requirement |
| **XT60 connectors** | $8-12 | Spares for repairs |
| **Power distribution cables** | $10-15 | 12AWG silicone wire |
| **Pixhawk cable set** | $15-20 | I2C, CAN, safety switch |
| **GPS module (if not with FC)** | $25-40 | M8N or better |
| **Telemetry radios** | $20-40 | SiK 915MHz or similar |
| **MicroSD cards (2-3x)** | $10-15 each | High endurance for Pi + FC logging |
| **Vibration dampening** | $10-25 | Flight controller isolation |
| **Propellers (10+ sets)** | $20-30 | Stock up, you'll crash |
| **Threadlock (blue)** | $5 | Essential for motor screws |
| **Zip ties, heat shrink, tape** | $15-20 | Organization and strain relief |
| **Multimeter** | $15-25 | Debugging essential |
| **USB-to-TTL adapter** | $8-12 | Pi console access |
| **HDMI cable + adapter** | $10-15 | Pi troubleshooting |

### 4.2 Shipping & Import Considerations

| Source | Shipping Time | Duties (US) |
|--------|---------------|-------------|
| US vendors (GetFPV, Amazon) | 2-5 days | None |
| AliExpress standard | 15-30 days | None under $800 |
| AliExpress premium | 7-15 days | None under $800 |
| Banggood | 20-40 days | Possible 2-5% |
| EU to US | 7-14 days | Possible duties >$800 |

**Strategy**: Keep individual AliExpress orders under $800 to avoid customs paperwork. Split large orders.

### 4.3 Revised Total Budget with Hidden Costs

| Category | Initial Budget | With Hidden Costs |
|----------|---------------|-------------------|
| Stage 1 (Airframe, FC, Pi) | $350 | $420 |
| Stage 2 (Camera + extras) | $100 | $180 |
| Stage 3 (Depth + payload) | $200 | $250 |
| **Total** | **$650** | **$850** |

**Recommendation**: Set $650 as realistic Stage 1-2 target, $850 for full Stage 3 completion.

---

## 5. Concrete Shopping Lists

### Option A: Aggressive Used (Target: $400 Stage 1-2)

| Component | Source | Price | Notes |
|-----------|--------|-------|-------|
| Used 500mm frame + motors + ESCs | FPV Marketplace/Facebook | $120 | Negotiate bundle |
| Used Pixhawk 6C | RCGroups/FPV group | $100 | Verify firmware support |
| Used RPi 4 4GB | Facebook/eBay | $45 | Check for SD card slot damage |
| Pi Camera v2 | Amazon (new) | $25 | Reliable, easy return |
| BEC 5V 3A + wiring | AliExpress | $15 | Order with other items |
| GPS M8N | AliExpress | $20 | BN-880 or similar |
| Telemetry radio pair | AliExpress | $25 | 500mW 915MHz |
| Propellers (8 sets) | AliExpress | $20 | 10x4.5 or similar |
| Cables, connectors, hardware | AliExpress | $30 | XT60, JST, DuPont |
| Battery (2x 4S 5000mAh used) | Local FPV | $60 | Check cell voltage balance |
| Basic charger | Amazon | $50 | ISDT Q6 Nano or similar |
| **Total Stage 1-2** | | **$510** | |

### Option B: Mixed New/Used (Target: $500 Stage 1-2)

| Component | Source | Price | Notes |
|-----------|--------|-------|-------|
| Holybro X500 ARF (new, sale) | Banggood/GetFPV | $280 | Holiday/flash sales |
| Pixhawk 6C (new) | GetFPV | $170 | Warranty, latest firmware |
| RPi 4 4GB (used) | Local/eBay | $50 | |
| Pi Camera v3 Wide | Amazon | $35 | Better low light |
| BEC + GPS + Telemetry bundle | AliExpress | $50 | Combined shipping |
| Props, cables, hardware | AliExpress | $40 | Bulk order |
| Battery 2x + basic charger | Amazon | $100 | Turnigy or similar |
| **Total Stage 1-2** | | **$725** | |

**Note**: Option B exceeds $500 - only viable with excellent sale prices or deferring some items.

### Option C: Budget Alternative (Target: $300 Stage 1)

| Component | Source | Price | Notes |
|-----------|--------|-------|-------|
| S550 frame + motors used | Facebook | $80 | Generic clone |
| Pixhawk 2.4.8 (clone) | AliExpress | $45 | Higher risk, have backup plan |
| RPi 3B+ | Used local | $30 | Slower but functional |
| USB webcam | Amazon | $20 | No CSI needed |
| Essential wiring + BEC | AliExpress | $25 | |
| Props + hardware | AliExpress | $15 | |
| 1x battery + borrow charger | Local | $30 | Upgrade later |
| **Total Stage 1** | | **$245** | Leaves room for repairs |

---

## 6. Risk Mitigation

### High-Risk Purchases to Avoid

| Risk | Item | Mitigation |
|------|------|------------|
| Counterfeit | Pixhawk from unknown AliExpress store | Buy from verified stores or used from community |
| DOA | Used FC without return policy | Ask for boot video, buy with PayPal protection |
| Swollen | Used LiPo batteries | Always inspect in person, check voltage |
| Obsolete | Old Pixhawk versions | Confirm PX4 1.14+ support |
| Underpowered | RPi Zero 2 W | Test MAVSDK latency first, have RPi 4 backup plan |

### Backup Plans

| If This Fails | Then Do This | Extra Cost |
|---------------|--------------|------------|
| Used X500 falls through | Buy S550/S500 frame new | +$50 |
| Used Pixhawk is DOA | Order Pixhawk 6C new (delay 1 week) | +$60 |
| RPi 4 unobtainable | Use RPi 3B+ temporarily | -$20, -performance |
| Camera doesn't work | Fallback to USB webcam | No change |
| RealSense too expensive | Defer to Stage 4 | $0 now, $150+ later |

---

## 7. Price Monitoring & Deal Alerts

### Tools to Use

| Tool | Use For |
|------|---------|
| **CamelCamelCamel** | Amazon price history on Pi, cameras |
| **Keepa** | Amazon deal alerts |
| **Distill.io** | Web page change monitoring (Banggood sales) |
| **Reddit r/Multicopter** | Deal announcements |
| **FPV Facebook groups** | Flash sales, member deals |

### Best Times to Buy

| Event | Typical Discount |
|-------|------------------|
| Black Friday/Cyber Monday | 20-30% on new gear |
| Banggood Anniversary (Sept) | 15-25% site-wide |
| GetFPV holiday sales | 10-20% |
| Local FPV meetups | Barter, package deals |

---

## 8. Summary Checklist

### Pre-Purchase
- [ ] Join 3+ FPV/drone Facebook groups
- [ ] Set up price alerts on CamelCamelCamel
- [ ] Check local Facebook Marketplace twice weekly
- [ ] Verify existing RC radio compatibility
- [ ] Confirm budget ceiling ($500 strict vs $650 realistic)

### Stage 1 Shopping
- [ ] Secure airframe deal first (longest lead time)
- [ ] Order AliExpress items simultaneously (2-3 week shipping)
- [ ] Buy FC + Pi in same week (parallel setup)
- [ ] Budget $50 buffer for unexpected hardware needs

### Stage 2 Shopping
- [ ] Confirm Stage 1 flight before buying camera
- [ ] Verify streaming pipeline works before mounting
- [ ] Buy props in bulk (you will crash)

### Stage 3 Shopping
- [ ] Only proceed if Stage 2 vision is valuable
- [ ] Hunt for used RealSense for 30+ days before buying new
- [ ] Consider Luxonis OAK-D as alternative (~$150 used)

---

## Document History

- **Created**: 2025-04-09
- **Based on**: project_avatar_prd.md, project_avatar_roadmap.md, project_avatar_technical.md
- **Budget Target**: $500 Stage 1-2, $650-850 total with hidden costs
- **Next Review**: Update prices quarterly
