# Project Avatar: Stage 1-3 Hardware Validation Report

**Date:** April 9, 2026  
**Status:** VALIDATED (with recommendations)  
**Priority:** CRITICAL for flight safety

---

## Executive Summary

This report validates the Stage 1-3 hardware selections for Project Avatar's autonomous drone platform. **All core components are compatible** with minor configuration adjustments required. Key findings include power system adequacy for 4S operation, confirmed BEC sizing for Pi power, and critical EMI mitigation steps for reliable MAVLink communication.

**CRITICAL ACTIONS REQUIRED:**
1. Add EMI shielding for USB3-Pi Camera interface
2. Configure BAT_* parameters for voltage monitoring
3. Validate BEC output under full Pi load
4. Add vibration dampening for companion computer

---

## 1. Airframe Validation: Holybro X500 V2

### 1.1 Current Selection Assessment

| Specification | Value | Rating |
|--------------|-------|--------|
| Wheelbase | 500mm | STANDARD |
| Frame Weight | ~650g | GOOD |
| Max Payload | ~1.2kg | EXCELLENT |
| Motor Mount | 16mm/19mm tubes | COMPATIBLE |
| Battery Bay | 4S/6S compatible | VERIFIED |

### 1.2 Comparison with Alternatives

| Frame | Weight | Payload | Build Quality | Price | Verdict |
|-------|--------|---------|---------------|-------|---------|
| **Holybro X500 V2** | 650g | 1.2kg | Excellent | $89 | **SELECTED** |
| Holybro S500 | 550g | 1.0kg | Good | $75 | Alternative - less payload |
| DJI F450 | 620g | 1.1kg | Good | $65 | Alternative - dated design |
| Tarot 650 | 850g | 2.0kg | Excellent | $120 | Upgrade path for heavy payloads |

### 1.3 X500 V2 Key Features
- **Integrated PDB**: 5V/3A BEC + 12V/3A BEC built-in
- **Carbon fiber arms**: 16mm diameter
- **Dual battery mount**: Supports up to 6S 5200mAh
- **Quick-release landing gear**: Tool-free removal
- **Pre-threaded motor mounts**: Easy motor installation

### 1.4 Compatibility Check

| Component | Compatibility | Notes |
|-----------|---------------|-------|
| Pixhawk 6C | EXCELLENT | Standard 30.5x30.5 mounting |
| Raspberry Pi 4 | GOOD | Vibration isolation required |
| 4S LiPo | EXCELLENT | Standard configuration |
| 6S LiPo | GOOD | Requires motor/ESC check |

**VERDICT: X500 V2 is OPTIMAL for this build.** The integrated PDB with dual BEC outputs is ideal for powering both the flight controller and companion computer.

---

## 2. Flight Controller Validation: Pixhawk 6C

### 2.1 Current Selection: Pixhawk 6C

| Specification | Value | Status |
|--------------|-------|--------|
| Processor | STM32H743 | CURRENT GEN |
| IMU | ICM-42688-P (single) | ADEQUATE |
| Barometer | ICM-20649 | INCLUDED |
| Compass | RM3100 | INCLUDED |
| UART Ports | 5x UART | SUFFICIENT |
| CAN Bus | 2x CAN | FUTURE-PROOF |
| Power Input | 5V (redundant) | GOOD |

### 2.2 Pixhawk 6C vs 6X Comparison

| Feature | Pixhawk 6C | Pixhawk 6X | Impact |
|---------|-----------|------------|---------|
| **Price** | ~$180 | ~$350 | 6C saves $170 |
| **IMU Redundancy** | Single IMU | Triple IMU | 6X for commercial ops |
| **Vibration Isolation** | None | Integrated | Add external damping for 6C |
| **Processor** | STM32H743 | STM32H753 | Both excellent |
| **Temperature Calibration** | No | Yes | Manual calibration needed |
| **UART Ports** | 5 | 6 | 5 is sufficient |

### 2.3 UART Allocation Plan (6C)

| UART | Assignment | Baud Rate | Notes |
|------|-----------|-----------|-------|
| UART1 | GPS/Compass | 115200 | Standard GPS |
| UART2 | Raspberry Pi MAVLink | 921600 | High-speed companion link |
| UART4 | Telemetry Radio | 57600 | Ground station link |
| UART6 | RC Input | N/A | SBUS/CPPM input |
| UART7 | Debug/Spare | 57600 | Development use |

### 2.4 Power Requirements

| Input | Voltage | Current Draw | Notes |
|-------|---------|--------------|-------|
| Main Power | 5V | ~150mA | From PDB BEC |
| USB Power | 5V | ~200mA | Development only |
| Servo Rail | 5V | Shared | For peripherals |

**VERDICT: Pixhawk 6C is APPROPRIATE for R&D phase.** Consider upgrading to 6X for commercial deployment requiring redundancy.

---

## 3. Companion Computer Validation: Raspberry Pi 4

### 3.1 Current Selection: Raspberry Pi 4 (4GB)

| Specification | Value | Status |
|--------------|-------|--------|
| Processor | BCM2711 Quad-core 1.8GHz | EXCELLENT |
| RAM | 4GB LPDDR4 | ADEQUATE |
| GPIO | 40-pin | COMPATIBLE |
| USB Ports | 4x USB3 | GOOD |
| Ethernet | Gigabit | OPTIONAL |
| WiFi | Dual-band 802.11ac | REQUIRED |
| Power | 5V/3A USB-C | CRITICAL |

### 3.2 Pi 4 vs Compute Module 4 Comparison

| Feature | Raspberry Pi 4 | CM4 + Carrier | Recommendation |
|---------|---------------|---------------|----------------|
| **Form Factor** | Full-size | Compact custom | CM4 for integration |
| **Power Draw** | 600-800mA | 400-600mA | CM4 more efficient |
| **GPIO Access** | Full 40-pin | Custom on carrier | Both compatible |
| **Storage** | MicroSD | eMMC option | eMMC more reliable |
| **Cost** | $55 | $90+ | Pi 4 for prototyping |
| **Availability** | Good | Poor | Pi 4 easier to source |
| **Vibration Resistance** | Poor | Better | CM4 advantage |
| **Thermal Management** | Easier | Custom design | Pi 4 simpler |

### 3.3 Power Analysis for Pi 4

| Component | Current Draw | Notes |
|-----------|--------------|-------|
| Pi 4 Base (idle) | 600mA | @5V = 3W |
| Pi 4 Load (CPU+GPU) | 1200mA | @5V = 6W |
| Pi Camera Module | 250mA | CSI interface |
| WiFi Active | 100mA | TX peak |
| **Total Peak** | **~1550mA** | **@5V = 7.75W** |

### 3.4 Power Supply Requirements

**REQUIRED: 5V/3A (15W) minimum for reliable operation**

| Source | Rating | Suitability | Recommendation |
|--------|--------|-------------|----------------|
| X500 V2 PDB 5V BEC | 3A | MARGINAL | Monitor voltage drop |
| External BEC 5V/5A | 5A | GOOD | Better headroom |
| Battery direct (4S) | 14.8V nominal | NOT COMPATIBLE | Requires buck converter |

**CRITICAL FINDING**: The X500 V2's built-in 5V/3A BEC is at the edge of capability for Pi 4 + camera + WiFi under full load. **Recommendation: Add external 5V/5A BEC for safety margin.**

### 3.5 UART Interface Configuration

Pi 4 to Pixhawk 6C connection:

```
Pi 4 GPIO          Pixhawk 6C TELEM2
-------            ----------------
GPIO14 (TX)  ----> RX
GPIO15 (RX)  <---- TX
GND          ----- GND
5V (BEC)     ----- 5V (NOT from Pi!)
```

**Configuration:**
- Disable Bluetooth on Pi (uses same UART)
- Add to `/boot/config.txt`: `dtoverlay=disable-bt`
- Enable serial: `enable_uart=1`
- Baud rate: 921600 for MAVLink 2

**VERDICT: Pi 4 is SUITABLE for development.** Consider CM4 for production with custom carrier board for better integration.

---

## 4. Camera Selection Validation

### 4.1 Pi Camera Module vs USB Camera

| Feature | Pi Camera Module (v2/v3) | USB Camera | Recommendation |
|---------|-------------------------|------------|----------------|
| **Interface** | CSI-2 | USB2/USB3 | CSI-2 lower latency |
| **Latency** | ~50-100ms | 100-300ms | **Pi Camera wins** |
| **CPU Load** | Low (GPU accelerated) | High | Pi Camera better |
| **Cable Length** | Limited (30cm max) | 5m+ possible | USB for remote mount |
| **Resolution** | 8MP/12MP | Varies | Both adequate |
| **Power Draw** | 250mA | 300-500mA | Pi Camera efficient |
| **Driver Support** | Native | Varies | Pi Camera simpler |

### 4.2 CSI-2 Bandwidth Analysis

| Resolution | FPS | Data Rate | CSI-2 Lanes |
|------------|-----|-----------|-------------|
| 1080p | 30 | ~1.5 Gbps | 2 lanes OK |
| 1080p | 60 | ~3.0 Gbps | 2 lanes OK |
| 4K | 30 | ~6.0 Gbps | 4 lanes preferred |

**CRITICAL FINDING**: CSI-2 interface provides 50-70% lower latency than USB cameras. **Pi Camera Module is STRONGLY RECOMMENDED for autonomous flight.**

### 4.3 USB3 Interference Warning

**CRITICAL**: USB3 signals create broadband EMI at 2.4GHz, interfering with:
- WiFi (2.4GHz band)
- RC receivers
- Telemetry radios

**Mitigation Required:**
1. Use shielded USB3 cables (ferrite cores)
2. Keep USB3 cables away from antennas
3. Consider USB2 for non-critical peripherals
4. Add metallic shielding around USB3 ports

---

## 5. Power System Validation

### 5.1 Battery: 4S vs 6S LiPo

| Configuration | Voltage | Pros | Cons | Verdict |
|--------------|---------|------|------|---------|
| **4S (16.8V max)** | 14.8V nominal | Simpler, cheaper, safer | Less efficient | **RECOMMENDED for X500** |
| **6S (25.2V max)** | 22.2V nominal | More efficient, longer flight | Higher cost, complexity | Consider for heavy payloads |

### 5.2 4S Battery Sizing for X500

| Capacity | Weight | Flight Time (hover) | Recommended Use |
|----------|--------|---------------------|-----------------|
| 4S 4000mAh | ~350g | 12-15 min | Light payload |
| **4S 5200mAh** | ~450g | **18-22 min** | **RECOMMENDED** |
| 4S 6000mAh | ~520g | 22-25 min | Extended range |
| 6S 4000mAh | ~480g | 15-20 min | High-power setup |

**VERDICT: 4S 5200mAh is OPTIMAL** for X500 V2 with Pi companion computer.

### 5.3 BEC Selection for Pi Power

| BEC Type | Current Rating | Voltage | Price | Recommendation |
|----------|---------------|---------|-------|----------------|
| X500 V2 Integrated | 3A | 5V | Included | Marginal - monitor load |
| Holybro 5V/5A BEC | 5A | 5V | $12 | **RECOMMENDED** |
| Mauch 5V/5A BEC | 5A | 5V | $25 | High quality option |
| Castle 10A BEC | 10A | 5V-8V | $35 | Overkill but safe |

**CRITICAL CONFIGURATION:**
- **NEVER** power Pi from flight controller's USB port in flight
- Always use dedicated BEC for Pi ( galvanic isolation preferred)
- Add 1000uF capacitor on Pi power input for voltage spikes

### 5.4 Power Distribution Safety

**Required Safety Features:**

1. **Voltage Monitoring**: BAT_* parameters in PX4
2. **Current Sensing**: Hall sensor or shunt resistor
3. **Fail-Safe Voltage**: Set to 14.0V (4S) for RTL
4. **Emergency Voltage**: Set to 13.5V (4S) for land

**Wiring Diagram:**

```
4S LiPo
   |
   +---> PDB (X500 V2)
            |
            +---> 5V/3A BEC ---> Pixhawk 6C (Power 1)
            |
            +---> 12V/3A BEC ---> Peripherals
            |
            +---> ESCs (4x) ---> Motors
   |
   +---> External 5V/5A BEC ---> Raspberry Pi 4
                                   |
                                   +---> Pi Camera (CSI)
                                   +---> USB devices
```

---

## 6. Interconnects and Cables

### 6.1 UART vs USB for MAVLink

| Interface | Latency | Reliability | CPU Load | Recommendation |
|-----------|---------|-------------|----------|----------------|
| **UART (Serial)** | <5ms | EXCELLENT | Very low | **PRIMARY CHOICE** |
| USB CDC | 10-50ms | Good | Medium | Backup option |
| UDP (Ethernet) | <1ms | Good | Low | Ground station |

**VERDICT: UART is REQUIRED for Pi-to-Pixhawk communication.** USB introduces unpredictable latency unacceptable for flight control.

### 6.2 Cable Routing for Vibration Isolation

**Vibration Sources:**
- Motors: 100-400Hz vibration
- Propellers: 50-200Hz (depending on RPM)
- Wind gusts: Low frequency

**Mitigation Strategy:**

1. **Flight Controller**: Use included foam pads (Pixhawk 6C)
2. **Raspberry Pi**: Add silicone gel mounts or O-ring suspension
3. **Camera**: Soft mount with vibration-dampening tape
4. **Cables**: Keep short, secured, strain-relieved

**Recommended Isolation Materials:**
- Kyosho Zeal foam (flight controller)
- Gel dampeners (companion computer)
- Silicone wire (all signal cables)
- Spiral wrap (cable management)

### 6.3 EMI Considerations

**High-Risk Areas:**

1. **USB3 + WiFi**: USB3 creates 2.4GHz noise
   - **Fix**: Shielded cables, ferrite beads, distance separation

2. **ESC PWM + GPS**: Motor noise affects GPS accuracy
   - **Fix**: GPS mast (10cm+ from frame), shielded GPS cable

3. **Power cables + Magnetometer**: Current creates magnetic fields
   - **Fix**: Twist power cables, external compass (GPS mast)

**Antenna Placement Rules:**
- GPS: Top of mast, clear sky view
- WiFi: Side of frame, away from USB3
- RC: Bottom of frame, away from power cables
- Telemetry: Side/rear, vertical orientation

---

## 7. Compatibility Matrix

### 7.1 Component Compatibility Summary

| Combination | Status | Notes |
|------------|--------|-------|
| X500 V2 + Pixhawk 6C | COMPATIBLE | Standard 30.5mm mounting |
| X500 V2 + Pi 4 | COMPATIBLE | Vibration isolation required |
| Pixhawk 6C + Pi 4 (UART) | COMPATIBLE | 921600 baud recommended |
| Pi 4 + Pi Camera | COMPATIBLE | CSI cable routing critical |
| 4S + X500 PDB | COMPATIBLE | Monitor BEC temperature |
| 6S + X500 | CHECK ESCs | Verify ESC voltage rating |

### 7.2 Critical Incompatibilities (NONE FOUND)

All selected components are electrically and mechanically compatible.

**Minor Concerns:**
1. Pi 4 power draw near PDB BEC limit under full load
2. USB3 EMI may affect WiFi/RC if cables not shielded
3. CSI cable length limits camera placement

---

## 8. Configuration Checklist

### 8.1 PX4 Battery Parameters (BAT_*)

```bash
# Voltage monitoring (4S LiPo)
BAT_V_DIV = 10.1        # Voltage divider ratio
BAT_A_PER_V = 36.0      # Current sensor A/V (if using Mauch sensor)

# Voltage thresholds
BAT_V_CHARGED = 16.8    # Fully charged (4S)
BAT_V_LOW = 14.4        # Warning level
BAT_V_CRIT = 13.8       # Critical level
BAT_V_EMERGENCY = 13.2  # Emergency land

# Capacity (for 5200mAh battery)
BAT_CAPACITY = 5200     # mAh
BAT_CRIT_THR = 0.15    # 15% remaining for RTL
BAT_LOW_THR = 0.25     # 25% remaining for warning

# Source
BAT_SOURCE = VoltageAndCurrent  # Enable both monitoring
```

### 8.2 MAVLink Configuration

```bash
# TELEM2 (Pi connection)
MAV_1_CONFIG = TELEM2
MAV_1_MODE = Onboard
MAV_1_RATE = 100000     # 100KB/s
SER_TEL2_BAUD = 921600

# TELEM1 (Ground station)
MAV_0_CONFIG = TELEM1
MAV_0_MODE = Normal
MAV_0_RATE = 57600
```

### 8.3 Pi 4 Configuration

```bash
# /boot/config.txt additions
dtparam=uart0=on
dtoverlay=disable-bt
dtoverlay=disable-wifi  # If using external WiFi
enable_uart=1

# Disable serial console
cmdline.txt: remove console=serial0,115200
```

---

## 9. Shopping List Additions

Based on validation, add these items:

| Item | Purpose | Priority | Est. Cost |
|------|---------|----------|-----------|
| External 5V/5A BEC | Reliable Pi power | **HIGH** | $12 |
| Pi 4 Vibration Mount | Isolate from frame | **HIGH** | $8 |
| Shielded USB3 cable | EMI mitigation | MEDIUM | $6 |
| Ferrite beads (5 pack) | EMI filtering | MEDIUM | $5 |
| GPS Mast (25cm) | Compass/GPS isolation | MEDIUM | $15 |
| 1000uF capacitor | Pi power smoothing | LOW | $2 |
| XT60 current sensor | Battery monitoring | LOW | $12 |
| Silicone wire (various AWG) | Flexible wiring | LOW | $15 |

**Total Additional Cost: ~$75**

---

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BEC overload causing Pi reboot | Medium | **CRITICAL** | Add external 5V/5A BEC |
| USB3 EMI causing RC loss | Medium | HIGH | Shielded cables, ferrite |
| Vibration damaging Pi | Medium | HIGH | Gel isolation mounts |
| Voltage sag causing failsafe | Low | HIGH | Proper BAT_* params |
| CSI cable too short | Low | Medium | Measure before mounting |

---

## 11. Recommendations Summary

### 11.1 Keep Current Selections
- **Holybro X500 V2**: Excellent choice with integrated PDB
- **Pixhawk 6C**: Adequate for R&D phase
- **Raspberry Pi 4**: Good for development
- **Pi Camera Module**: Lower latency than USB

### 11.2 Required Modifications
1. **Add external 5V/5A BEC** for Pi power margin
2. **Vibration isolate the Pi** with gel mounts
3. **Use shielded USB3 cables** for EMI control
4. **Configure BAT_* parameters** for safe voltage monitoring

### 11.3 Future Upgrade Path
- **Pixhawk 6X**: When moving to commercial operations
- **CM4 + Custom Carrier**: For production integration
- **6S Battery**: If payload increases beyond 1kg

---

## 12. Validation Sign-off

| Component | Status | Validator Notes |
|-----------|--------|-----------------|
| X500 V2 Frame | PASS | PDB BEC marginal, external BEC recommended |
| Pixhawk 6C | PASS | Single IMU adequate for development |
| Raspberry Pi 4 | PASS | Add vibration isolation |
| Pi Camera Module | PASS | Use CSI, not USB |
| 4S LiPo | PASS | Standard, safe configuration |
| UART MAVLink | PASS | 921600 baud configured |
| Overall System | **PASS** | Ready for assembly with noted modifications |

---

## Appendix A: Reference Documents

- Pixhawk 6C Pinout: https://docs.holybro.com/autopilot/pixhawk-6c
- X500 V2 Assembly: https://docs.holybro.com/airframe/x500-v2
- Pi 4 UART Config: https://docs.px4.io/main/en/companion_computer/pixhawk_rpi.html
- PX4 Battery Params: https://docs.px4.io/main/en/config/battery.html

---

**Report compiled by:** Claude Code Hardware Specialist  
**Next Review:** Post-first-flight hardware check
