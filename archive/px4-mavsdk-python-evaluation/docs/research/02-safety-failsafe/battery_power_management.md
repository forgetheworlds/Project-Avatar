# Drone Battery & Power Management Guide

**Project Avatar - Power Systems Engineering Reference**  
**Date:** 2026-04-10  
**Version:** 1.0  
**Classification:** Safety-Critical Design Document

---

## Table of Contents

1. [LiPo Battery Safety Fundamentals](#1-lipo-battery-safety-fundamentals)
2. [PX4 Battery Parameters & Failsafes](#2-px4-battery-parameters--failsafes)
3. [Power System Design](#3-power-system-design)
4. [Current Sensing & Calibration](#4-current-sensing--calibration)
5. [Operational Procedures](#5-operational-procedures)
6. [Environmental Considerations](#6-environmental-considerations)
7. [Quick Reference Tables](#7-quick-reference-tables)

---

## 1. LiPo Battery Safety Fundamentals

### 1.1 C-Rating and Current Draw

The **C-rating** of a LiPo battery defines the maximum safe continuous current draw relative to the battery's capacity:

**Formula:**
```
Max Continuous Current (A) = Capacity (Ah) × C-Rating
Max Burst Current (A) = Capacity (Ah) × Burst C-Rating
```

**Example Calculations:**
| Battery | C-Rating | Capacity | Max Continuous | Max Burst (10s) |
|---------|----------|----------|----------------|-----------------|
| 4S 5000mAh | 25C | 5.0Ah | 125A | 200A (40C) |
| 6S 6000mAh | 35C | 6.0Ah | 210A | 300A (50C) |
| 3S 5200mAh | 50C | 5.2Ah | 260A | 390A (75C) |

**Power Systems Engineering Guidelines:**

1. **Motor Current Draw Budgeting**
   - Calculate total max current: Sum of all motor peak currents
   - Apply 20% safety margin: `Battery C-Rating ≥ 1.2 × (Total Motor Current / Capacity)`
   - Account for hover current (typically 30-50% of max)

2. **Voltage Sag Under Load**
   - LiPo cells experience voltage drop under high current draw
   - Internal resistance causes voltage sag: `V_sag = I_load × R_internal`
   - Typical LiPo internal resistance: 5-20mΩ per cell
   - Voltage sag can trigger false low-battery warnings

3. **Practical C-Rating Selection**
   - Racing drones: 50C-100C minimum (high current spikes)
   - Photography drones: 25C-35C sufficient
   - Long-endurance: Lower C-rating acceptable (continuous draw)

### 1.2 LiPo Cell Voltage Characteristics

**Nominal and Limit Voltages:**

| State | Per Cell (V) | 3S Battery | 4S Battery | 6S Battery |
|-------|--------------|------------|------------|------------|
| **Fully Charged** | 4.20V | 12.6V | 16.8V | 25.2V |
| **Storage Charge** | 3.85V | 11.55V | 15.4V | 23.1V |
| **Nominal** | 3.70V | 11.1V | 14.8V | 22.2V |
| **Low (land soon)** | 3.50V | 10.5V | 14.0V | 21.0V |
| **Critical (land now)** | 3.30V | 9.9V | 13.2V | 19.8V |
| **Damage Threshold** | 3.00V | 9.0V | 12.0V | 18.0V |

**Critical Rule:** Never discharge below 3.0V per cell (9.0V for 3S, 12.0V for 4S). Deep discharge causes permanent capacity loss and safety hazards.

### 1.3 Battery Capacity Estimation Methods

PX4 supports three progressively more accurate methods:

#### Method 1: Basic Voltage Estimation (Default)
- Compares measured voltage to empty/full range
- **Pros:** Simple, no current sensor needed
- **Cons:** Coarse estimates, fluctuates under load
- **Use when:** No power module with current sensing

#### Method 2: Load-Compensated Voltage
- Accounts for voltage sag due to internal resistance
- **Requires:** Current measurements from power module
- **Formula:** `V_compensated = V_measured + (I × R_internal)`
- **Configuration:** `BAT1_R_INTERNAL` (set to -1 for real-time estimation)

#### Method 3: Voltage + Current Integration (Recommended)
- Fuses voltage-based estimate with current integration
- Most accurate method comparable to smart batteries
- **Requires:** Calibrated current sensing
- **Configuration:** Set `BAT1_CAPACITY` to 90% of rated capacity

---

## 2. PX4 Battery Parameters & Failsafes

### 2.1 Essential Battery Parameters

**Core Battery Settings (BAT1_*, BAT2_* for dual battery):**

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `BAT1_N_CELLS` | Number of cells in series | 3 | Match battery |
| `BAT1_V_CHARGED` | Full cell voltage | 4.05V | 4.05V (LiPo) |
| `BAT1_V_EMPTY` | Empty cell voltage | 3.60V | 3.50V (conservative) |
| `BAT1_CAPACITY` | Battery capacity (mAh) | -1 | 90% of rated |
| `BAT1_R_INTERNAL` | Internal resistance (mΩ) | -1 | -1 (auto) or measured |
| `BAT1_SOURCE` | Data source | 0 | 0 (power module) |

### 2.2 Failsafe Threshold Parameters

**Battery Failsafe Levels:**

| Parameter | Description | Default | Recommended Range |
|-----------|-------------|---------|-------------------|
| `BAT_LOW_THR` | Warning level (ratio 0-1) | 0.25 | 0.25-0.30 (25-30%) |
| `BAT_CRIT_THR` | Critical/RTL level | 0.15 | 0.15-0.20 (15-20%) |
| `BAT_EMERGEN_THR` | Emergency/Land level | 0.10 | 0.05-0.10 (5-10%) |
| `COM_LOW_BAT_ACT` | Low battery action | 0 | 2 (Land) or 1 (Return) |

**Failsafe Action Options (`COM_LOW_BAT_ACT`):**
- `0`: None (disabled)
- `1`: Warning only
- `2`: Return mode (RTL)
- `3`: Land mode (immediate)
- `4`: Disarm (kill motors - DANGEROUS)

### 2.3 Battery Failsafe Behavior

**Three-Tier Failsafe System:**

```
Capacity Level → Action
============================
100% to BAT_LOW_THR    → Normal operation
BAT_LOW_THR (25%)      → Warning triggered (GCS alert)
BAT_CRIT_THR (15%)     → Return to Launch (RTL) initiated
BAT_EMERGEN_THR (10%)  → Immediate Land mode
0% or voltage critical → Disarm (emergency stop)
```

**Recommended Configuration for Project Avatar:**

```yaml
# Battery Type Configuration
BAT1_N_CELLS: 4              # 4S LiPo (adjust for your battery)
BAT1_V_CHARGED: 4.05         # Slightly below 4.20V to account for settling
BAT1_V_EMPTY: 3.50           # Conservative cutoff to protect battery
BAT1_CAPACITY: 4500          # 90% of 5000mAh rated capacity

# Failsafe Thresholds (Conservative for Raspberry Pi payload)
BAT_LOW_THR: 0.30            # 30% - Early warning with payload overhead
BAT_CRIT_THR: 0.20           # 20% - Begin RTL
BAT_EMERGEN_THR: 0.10        # 10% - Emergency land

# Action Configuration
COM_LOW_BAT_ACT: 2           # 2 = Land at current position (safest)
COM_FLTT_LOW_ACT: 3          # Return when flight time insufficient

# Pre-arm Check
COM_ARM_BAT_MIN: 0.40        # Require 40% to arm (prevents deep discharge)
```

### 2.4 Return to Launch (RTL) Voltage Planning

**Critical Concept:** RTL requires sufficient battery for:
1. Climb to RTL altitude
2. Transit to home position (worst-case distance)
3. Descent and landing

**Reserve Calculation:**
```
Required Reserve (mAh) = (Hover Current × RTL Time × 1.5 safety factor)

Example:
- Hover current: 30A
- RTL time: 3 minutes
- Safety factor: 1.5
- Required: 30A × 0.05h × 1.5 = 2.25Ah = 2250mAh

For 5000mAh battery: BAT_CRIT_THR should be 2250/5000 = 0.45 (45%)
```

**Practical Recommendation:** Set `BAT_CRIT_THR` based on actual RTL test flight data.

---

## 3. Power System Design

### 3.1 BEC Selection for Raspberry Pi 4

**Raspberry Pi 4 Power Requirements:**
- **Voltage:** 5.0V (USB-C PD or GPIO 5V pin)
- **Current:** 3.0A minimum (typical), 5.0A peak (under load)
- **Power:** 15-25W depending on workload

**BEC (Battery Eliminator Circuit) Options:**

| Type | Output | Pros | Cons |
|------|--------|------|------|
| **Linear BEC** | 5V/1-3A | Simple, clean output | Inefficient, heat, limited current |
| **Switching BEC** | 5V/3-10A | Efficient, high current | Can introduce noise |
| **Isolated DC-DC** | 5V/5A+ | Clean power, isolated | Expensive, larger |

**Recommended Setup for Pi 4:**

```
Main Battery (4S/6S) → Power Module → Flight Controller
                     ↓
              BEC/DC-DC (5V/5A) → Raspberry Pi 4
                     ↓
              BEC (5V/2A) → Servos/Peripherals
```

**Recommended BEC Specifications:**
- Input: 7.4V-26.4V (2S-6S compatible)
- Output: 5.0V-5.2V (adjustable)
- Current: Minimum 5A continuous, 8A burst
- Ripple: <100mVpp
- Efficiency: >90%

### 3.2 Power Distribution Redundancy

**Single Point of Failure Analysis:**

| Component | Failure Mode | Mitigation |
|-----------|--------------|------------|
| Main battery | Cell failure | Dual battery setup |
| BEC | Output loss | Dual BEC with OR-ing |
| Power module | Current sensor failure | Voltage-only backup estimation |
| Wiring | Short/open | Fusing, proper gauge |

**Redundant Power Architecture:**

```
Option 1: Dual BEC with Diode OR-ing
====================================
Battery → BEC 1 (5V/3A) → Diode → Pi 4
        → BEC 2 (5V/3A) → Diode → (backup)

Option 2: Battery + USB Power Bank
=================================
Flight Battery → BEC → Pi 4 (primary)
USB Power Bank → USB-C → Pi 4 (backup, diode isolated)

Option 3: Dual Battery with Auto-Switch
========================================
Battery 1 → Power Module 1 → Power Selector → FC
Battery 2 → Power Module 2 → (automatic failover)
```

### 3.3 Wiring and Fusing

**Wire Gauge Selection:**

| Current | Wire Gauge (AWG) | Max Length (m) |
|---------|------------------|----------------|
| <5A | 22 AWG | 1.5 |
| 5-10A | 20 AWG | 1.5 |
| 10-20A | 18 AWG | 1.0 |
| 20-40A | 16 AWG | 0.5 |
| >40A | 14 AWG or larger | 0.3 |

**Fusing Strategy:**
- Main battery: 150% of max expected current
- Pi 4 power: 5A fast-blow fuse (for 3A draw)
- Peripherals: Individual fuses per circuit

---

## 4. Current Sensing & Calibration

### 4.1 Power Module Overview

**Common Power Modules:**

| Module | Voltage | Current | Connector | Notes |
|--------|---------|---------|-----------|-------|
| Pixhawk 4 PM | 3S-6S | 120A | XT60 | Standard reference |
| Mauch Electronics | 3S-12S | 200A | Various | High precision |
| Holybro PM02 | 3S-6S | 60A | XT60 | Budget option |
| ATI NANO | 3S-6S | 100A | XT30 | Compact |

### 4.2 Voltage Calibration

**Purpose:** Ensure accurate voltage readings from ADC

**Procedure:**
1. Measure actual battery voltage with quality multimeter (V_actual)
2. Read voltage reported in QGroundControl (V_reported)
3. Calculate divider: `Voltage Divider = V_reported / V_actual`
4. Update `BAT1_V_DIV` parameter

**QGroundControl Auto-Calibration:**
- Navigate to Vehicle Setup > Power
- Enter measured battery voltage
- Click "Calculate" to auto-set divider

### 4.3 Current Calibration

**Purpose:** Enable accurate current integration for capacity estimation

**Procedure:**

**Method 1: Using Battery Capacity (Recommended)**
1. Fully charge battery
2. Set `BAT1_CAPACITY` to 90% of rated capacity (mAh)
3. Fly normal mission, land at safe voltage
4. Read `battery_consumed` from flight log (mAh used)
5. Calculate: `Amps/Volt = (mAh used / 1000) / (ADC current voltage - offset)`

**Method 2: DC Clamp Meter**
1. Connect clamp meter in series with battery
2. Arm vehicle (props off or at idle)
3. Read current from clamp meter (I_actual)
4. Read current from QGroundControl (I_reported)
5. Calculate: `Amps/Volt = I_reported / I_actual`
6. Update `BAT1_A_PER_V` parameter

### 4.4 Internal Resistance Estimation

**Real-Time Estimation (Recommended):**
- Set `BAT1_R_INTERNAL` to -1
- PX4 estimates during flight based on voltage sag under load
- Adapts to temperature and battery age

**Manual Measurement:**
1. Use LiPo charger with IR measurement feature
2. Or calculate: `R_internal = (V_no_load - V_load) / I_load`
3. Typical values: 5-10mΩ per cell (new), 15-25mΩ (aged)

---

## 5. Operational Procedures

### 5.1 Pre-Flight Voltage Checks

**Pre-Flight Battery Checklist:**

```
☐ Battery visually inspected (no swelling, damage)
☐ Voltage measured with multimeter:
   - Per cell: 3.7V - 4.2V (acceptable)
   - Per cell: <3.5V (DO NOT FLY - damaged/over-discharged)
☐ Balance plug checked (all cells within 0.1V)
☐ PX4 voltage reading matches multimeter (±0.1V)
☐ Capacity shows >40% (per COM_ARM_BAT_MIN)
☐ Current sensor reading near zero when disarmed
☐ BEC output voltage: 5.0V-5.2V at Pi 4
```

**Cell Balance Tolerance:**
- Acceptable: <0.05V difference between cells
- Caution: 0.05V-0.1V difference
- Do not fly: >0.1V difference (cell failure risk)

### 5.2 In-Flight Capacity Estimation

**Real-Time Monitoring:**

1. **Voltage-Based Estimate**
   - Watch for sudden voltage drops (high current draw)
   - Compare to no-load voltage at rest
   - Account for temperature (cold = lower voltage)

2. **Current Integration**
   - Most accurate when properly calibrated
   - Shows cumulative consumption
   - Estimate remaining: `Remaining = (Capacity - Consumed) / Capacity`

3. **Flight Time Estimation**
   - `COM_FLTT_LOW_ACT` triggers when insufficient battery for RTL
   - Requires calibrated current sensing and accurate capacity

**In-Flight Warnings:**
- **25% Warning:** Begin planning RTL, reduce aggressive maneuvers
- **15% Critical:** Initiate RTL immediately unless mission critical
- **10% Emergency:** Land at nearest safe location immediately

### 5.3 Emergency Landing on Low Battery

**Decision Tree:**

```
Battery < BAT_EMERGEN_THR (10%)?
├── YES → Immediate Land mode at current position
│         - Reduce throttle to descent rate
│         - Scan landing zone
│         - Land, disarm, inspect battery
│
└── NO → Battery < BAT_CRIT_THR (15%)?
          ├── YES → Can you reach home safely?
          │         ├── YES → Initiate RTL
          │         └── NO → Find nearest safe landing
          │
          └── NO → Continue with caution
```

**Emergency Landing Best Practices:**
1. Reduce groundspeed (higher efficiency in loiter/transit)
2. Avoid aggressive maneuvers (high current draw)
3. Choose flat, clear area over returning to rough terrain
4. After landing, allow battery to cool before charging

### 5.4 Battery Logging and Analysis

**Post-Flight Analysis:**

1. **Log Review (PX4 .ulog)**
   - Plot `battery_voltage` vs `battery_current`
   - Check for abnormal voltage sag patterns
   - Verify capacity estimation accuracy

2. **Battery Health Metrics**
   - Internal resistance trend (increasing = aging)
   - Capacity fade (compare to rated capacity)
   - Cell balance degradation

3. **Maintenance Schedule**
   - Every 50 cycles: Deep discharge test to measure capacity
   - Every 100 cycles: Replace if capacity < 80% rated
   - Visual inspection: Before every flight

---

## 6. Environmental Considerations

### 6.1 Cold Weather Effects

**Temperature Impact on LiPo Performance:**

| Temperature | Capacity | Internal Resistance | Voltage |
|-------------|----------|---------------------|---------|
| 25°C (77°F) | 100% | Baseline | Nominal |
| 10°C (50°F) | ~95% | +20% | -3% |
| 0°C (32°F) | ~85% | +50% | -6% |
| -10°C (14°F) | ~70% | +100% | -10% |

**Cold Weather Procedures:**

1. **Pre-Flight**
   - Store batteries in insulated container until use
   - Pre-warm to >15°C before flight if possible
   - Expect reduced flight time (plan for 70-80% of normal)

2. **Configuration Adjustments**
   - Increase `BAT_LOW_THR` to 35-40% (account for reduced capacity)
   - Monitor voltage more closely (higher sag under load)
   - Reduce RTL distance expectations

3. **In-Flight**
   - Allow battery to self-warm (current draw generates heat)
   - Avoid hovering (less self-warming than active flight)
   - Land earlier than normal

### 6.2 Hot Weather Considerations

**High Temperature Effects:**
- Increased discharge rate capability
- Higher risk of thermal runaway (>60°C dangerous)
- Accelerated battery aging

**Hot Weather Procedures:**
- Never leave batteries in direct sunlight
- Allow cooling period between flights
- Monitor battery temperature if sensor available
- Reduce C-rating demands (don't push to limits)

### 6.3 Storage Guidelines

**Long-Term Storage:**
- Store at 3.8-3.85V per cell (storage charge)
- Temperature: 15-25°C ideal
- Check voltage monthly
- Recharge to storage voltage every 3 months

**Transport:**
- Use fireproof LiPo bags
- Carry in cabin baggage (airline regulations)
- Insulate from extreme temperatures

---

## 7. Quick Reference Tables

### 7.1 PX4 Battery Parameter Quick Reference

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `BAT1_N_CELLS` | 3 | 1-16 | Number of cells in series |
| `BAT1_V_CHARGED` | 4.05 | 3.0-4.5 | Full cell voltage |
| `BAT1_V_EMPTY` | 3.60 | 2.0-3.5 | Empty cell voltage |
| `BAT1_CAPACITY` | -1 | 0-100000 | Capacity in mAh |
| `BAT1_R_INTERNAL` | -1 | -1.0-0.2 | Internal resistance (Ω) |
| `BAT1_V_DIV` | -1 | 0.0-30.0 | Voltage divider |
| `BAT1_A_PER_V` | -1 | -1.0-1000.0 | Amps per volt |
| `BAT_LOW_THR` | 0.25 | 0.0-1.0 | Low battery threshold |
| `BAT_CRIT_THR` | 0.15 | 0.0-1.0 | Critical battery threshold |
| `BAT_EMERGEN_THR` | 0.10 | 0.0-1.0 | Emergency threshold |
| `COM_LOW_BAT_ACT` | 0 | 0-4 | Low battery action |
| `COM_ARM_BAT_MIN` | 0.0 | 0.0-1.0 | Min battery to arm |

### 7.2 Battery Voltage by Cell Count

| Cells | Full (4.2V/cell) | Nominal (3.7V) | Empty (3.5V) | Critical (3.0V) |
|-------|------------------|----------------|---------------|-----------------|
| 2S | 8.4V | 7.4V | 7.0V | 6.0V |
| 3S | 12.6V | 11.1V | 10.5V | 9.0V |
| 4S | 16.8V | 14.8V | 14.0V | 12.0V |
| 5S | 21.0V | 18.5V | 17.5V | 15.0V |
| 6S | 25.2V | 22.2V | 21.0V | 18.0V |

### 7.3 Emergency Response Quick Guide

| Scenario | Immediate Action | Post-Landing Action |
|----------|------------------|---------------------|
| Battery < 10% | Land immediately at current position | Inspect, cool, recharge |
| Voltage sag > 20% | Reduce throttle, reduce load | Check battery health |
| Cell imbalance > 0.2V | Land, do not fly again | Dispose/recycle battery |
| Battery swelling | Land, stay clear after landing | Dispose in LiPo bag |
| Smoke/heat from battery | Land immediately, evacuate area | Fire extinguisher (class D) |

### 7.4 Project Avatar Recommended Settings

```yaml
# === BATTERY CONFIGURATION ===
# 4S LiPo 5000mAh typical for Pi 4 payload
BAT1_N_CELLS: 4
BAT1_V_CHARGED: 4.05
BAT1_V_EMPTY: 3.50
BAT1_CAPACITY: 4500          # 90% of 5000mAh for safety
BAT1_R_INTERNAL: -1         # Auto-estimate

# === FAILSAFE THRESHOLDS (Conservative) ===
BAT_LOW_THR: 0.30           # 30% - Early warning
BAT_CRIT_THR: 0.20          # 20% - Begin RTL
BAT_EMERGEN_THR: 0.10       # 10% - Emergency land

# === FAILSAFE ACTIONS ===
COM_LOW_BAT_ACT: 2          # 2 = Land immediately
COM_FLTT_LOW_ACT: 3         # Return if insufficient battery
COM_ARM_BAT_MIN: 0.40       # Require 40% to arm

# === CURRENT SENSING ===
BAT1_A_PER_V: [calibrate per procedure]
BAT1_V_DIV: [calibrate per procedure]

# === ESTIMATION ===
BAT1_SOURCE: 0              # Power module
BAT1_PARAMS: 0              # Load compensation enabled
```

---

## References

1. PX4 User Guide - Battery Estimation Tuning: https://docs.px4.io/main/en/config/battery.html
2. PX4 User Guide - Safety Configuration: https://docs.px4.io/main/en/config/safety.html
3. PX4 Parameter Reference: https://docs.px4.io/main/en/advanced_config/parameter_reference.html
4. Project Avatar Failsafe Hierarchy: `failsafe_hierarchy.md`

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-10 | Initial release - Comprehensive battery and power management guide |

---

**Document Author:** Power Systems Engineer  
**Review Status:** Technical Reference  
**Next Review Date:** As required for Project Avatar milestones
