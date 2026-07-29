# Fable Critique — Bad Assumptions in the Research & Plan

**Date:** 2026-07-29
**Scope:** Assumptions carried into the adopted plan (Kimi report + CLAUDE.md + MASTER_BRIEFING).
The Comparison Report already killed the Claude-report errors (catamaran self-righting, free PLA,
$5 batteries, twin-prop-for-v1); this report covers what *survived* into the current plan and is
still wrong or untested. Ordered by how much it hurts if ignored.

---

## 1. The ESP32-S3 pin table is wrong (would not boot / not read)

CLAUDE.md's pin assignments were copied from a **classic ESP32**, not an S3:

| Function | Planned GPIO | Problem on ESP32-S3 |
|---|---|---|
| I2C SCL | 22 | **GPIO 22 does not exist on the S3** (S3 has 0–21, 26–48) |
| Battery ADC | 34 | Not ADC-capable on S3 (ADC1 = GPIO 1–10, ADC2 = 11–20); on the recommended **N8R8** module GPIO 33–37 are eaten by octal PSRAM |
| Water sensor | 35 | Same double problem as GPIO 34 |
| Camera | "2/14" | **Conflicts with pump on 14**; also a USB webcam dongle is not realistic — the S3 cannot act as a UVC host at useful framerates. Use a DVP camera module (OV2640 on an S3-CAM board) or skip camera onboard |

**Corrected map (S3-safe):** ESC = 13, servo = 12, pump MOSFET = 14, battery ADC = **4** (ADC1),
water sensor = **5** (ADC1), I2C SDA/SCL = **8/9** (DevKitC-1 defaults), all avoiding strapping
pins 0/3/45/46. Firmware must use these.

## 2. MPU-6050 cannot do absolute heading hold

The plan's L1 loop is "IMU heading-hold" on an MPU-6050. The MPU-6050 is a 6-axis part — **no
magnetometer** — so yaw comes from integrating the gyro and drifts by degrees per minute. That is
fine for *damping* (rate hold, smoothing turns) but not for "hold 215° for a patrol leg," and the
drift compounds exactly when the LLM issues sparse setpoints.

Fixes, cheapest first: add a **QMC5883L compass (~$2)** and fuse with the gyro; or derive heading
from **GPS course-over-ground** when moving >0.5 m/s (NEO-6M is already in the BOM); or demote L1
to yaw-rate hold and let L3 vision correct heading. Recommend the compass — it is the only $2 part
that fixes a core loop.

## 3. Speed and runtime numbers ignore the jet drive's own report

Kimi's 5–7 m/s top speed and the runtime table assume prop-like efficiency, but the same report
says the printed jet loses 15–25% (community consensus says up to 30–40%). Realistic expectations
for a ~1.15 kg hull on a printed 28 mm jet: **top speed 3–5 m/s, patrol draw 35–60 W (not 25 W),
so ~25–40 min patrol on 3S 2200**, not 47. The 5200 mAh upgrade doubles that. Nothing breaks —
just don't tune the failsafe/geofence around 47 minutes of endurance.

## 4. The water cannon will be a squirt, not a cannon

An 80–120 L/h 5 V pump is ~25 mL/s at near-zero head. Through the Ø2 mm nozzle that is a ~7–9 m/s
stream → **1.5–3 m of range**, and the backpressure will push a cheap centrifugal pump down its
curve, so the real number is the low end. That's fine for the mission (it's theater), but if you
want a visible arc: a **12 V diaphragm pump (~$12)** on the 3S rail through a second MOSFET gets
5–8 m. The turret makes this worth doing later. Keep Kimi's interlock (fire only when water sensor
dry AND throttle < 30%) — it survives critique.

## 5. Flood chamber: two physical details the research skipped

- **Air lock.** A sealed chamber with one hole floods slowly because air must escape through the
  same hole. The chamber needs a small vent near its top (a 2 mm drilled hole after printing is
  enough) or righting takes tens of seconds instead of ~5.
- **It only works if the rest of the boat stays buoyant.** The mechanism assumes the electronics
  bay stays sealed and the bow is foam-filled so the capsized boat floats high. Skipping the foam
  or leaving a lid screw loose defeats self-righting. The bathtub flip test is load-bearing, not
  optional — Kimi said this and it deserves emphasis.

## 6. "Waterproof ESC" and the cooling jacket

Vendor "waterproof" on $15 ESCs means splash-proof potting, not submersion-rated. And the
water-cooling jacket in the combo needs a **pressurized water source** — on jet boats that is a tap
off the pump housing, which no document in this repo had planned for. At patrol loads (<10 A on a
35 A ESC) it survives uncooled; before sustained full-throttle running, add a cooling loop off the
pump (the printed housing can gain a barb in v2). Until then, firmware should slew-limit and cap
continuous full throttle.

## 7. "Zero hull penetrations" is marketing, not geometry

The real design has: intake aperture, transom nozzle hole, servo pushrod exit, flood hole, wet-well
opening, drain. The honest claim is: **no rotating-shaft seal below the waterline** (the #1 leak
mechanism), and every opening is either above the static waterline, a gasketed bolted flange, or an
intentionally flooded compartment. The sealed boundary is the deck lids + bow compartment — treat
the rest of the bilge as "gets damp."

## 8. Phone hotspot: test AP client isolation on day one

Several Android vendors (and some iOS configurations) enable **client isolation** on hotspots —
the laptop and boat both connect but cannot see each other. The whole architecture dies on this
silently. Test laptop→ESP32 ping on the actual phone before building anything else on top. The
fallback (old spare phone / travel router) is cheap; discovering isolation at the lake is not.

## 9. PLA in a hot car

Tg of PLA is 60–65 °C; a black hull on a parked-car dashboard in July will warp before it ever
sees water. Print in a light color, and since the friend's printer allows it, **PETG for the stern
segment** (motor heat + sun) is a worthwhile upgrade even if the rest stays PLA.

## 10. Smaller residual errors

- **Impeller press-fit on a "4mm shaft"** (old CAD spec): the 2838 shaft is 3.175 mm. Fixed in the
  fable-cad design with a 3.175→4 coupler + 4 mm stub shaft + set-screw impeller.
- **Self-tapping M3 into PLA** is good for ~10 insertion cycles per boss; the lids will be opened
  constantly, so plan on brass heat-set inserts for the deck lids in v2.
- **0.15 mm layers / 80% infill everywhere** (old spec) roughly triples print time and adds ~$10 of
  PLA for no watertightness gain — perimeters + epoxy do the sealing (Kimi got this right; the CAD
  spec ignored it).
- **Print orientation**: "flat, keel down" in the old spec puts the V-bottom at a ~70° overhang and
  layer lines across the hull (the weak axis). Segments must print upright on their joint faces —
  which also matches Kimi's structural advice.
- **Library 8-hour cap** analysis is moot with friend printing, but bed-size checks still apply:
  upright hull segments need only a 130×165 mm footprint and 160 mm Z — fits any common printer.

## What survives critique intact

Monohull deep-V; flood-chamber self-righting (with §5 caveats); single 2838 + steerable-nozzle jet;
ESP32-S3 absorbing PID + Guardian; phone-as-hotspot topology (with §8 test); local-LLM setpoint
architecture and the six-layer latency budget; battery-as-ballast; XTC-3D epoxy sealing; the
bench → bathtub → pond → tethered → autonomous test ladder. These are all well-sourced and correct.
