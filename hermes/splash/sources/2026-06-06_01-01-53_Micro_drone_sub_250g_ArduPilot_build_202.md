Building a **sub-250g autonomous micro drone** running ArduPilot is highly achievable using an **[H743 All-In-One (AIO) flight controller Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462865395388244,imageDocid:6652063207339861283,gpcid:2976809413005077848,headlineOfferDocid:5263659290882121758,catalogid:3844865969633096636,productDocid:17050519222662587814,rds:PC_2976809413005077848%7CPROD_PC_2976809413005077848&q=product&sa=X&ved=2ahUKEwjCitLk6vGUAxWXg4kEHR89HP8Qxa4PeggIAggACAkQAg)** powered by a **4S LiPo battery**. The high processing power of the H7 compiler allows you to run complete autonomous waypoint navigation, ArduPilot Lua scripts, and complex tuning on a frame small enough to bypass most restrictive airspace regulations. 

Core Component Selection 

*

* **Flight Controller & ESC**: The [MicoAir H743 V2 AIO 45A](https://micoair.com/flightcontroller_micoair743/) is the gold standard for this specific footprint. It packs an STM32H743 processor, dual gyros (BMI088 + BMI270), a built-in barometer, an SD card slot for ArduPilot logs, 7 UARTs, and an integrated 45A AM32 ESC into a 25.5x25.5mm mounting pattern. 

* **Frame**: A lightweight 3.5-inch or aggressive 3-inch open-prop carbon fiber frame (e.g., lightweight freestyle or long-range frames under 45g). 

* **Motors**: 1404 or 1504 brushless motors rated between 2800KV and 3800KV, optimized for 4S voltage efficiency. 

* **Battery**: A 4S 550mAh to 850mAh LiPo (for high agility/freestyle) or a custom 4S 18650/18350 Li-Ion pack (for maximum flight endurance while staying safely under 249 grams). 

* **GPS/Compass Module**: A miniature M10 GPS with an integrated magnetometer (like the
  [Foxeer M10Q-5883 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462768551438272,imageDocid:1215353289655242333,gpcid:10951996430052043838,headlineOfferDocid:10356872744197952501,catalogid:8381141043403693588,productDocid:7925205249058890144,rds:PC_10951996430052043838%7CPROD_PC_10951996430052043838&q=product&sa=X&ved=2ahUKEwjCitLk6vGUAxWXg4kEHR89HP8Qxa4PeggIAggACBIQGQ) or
  [Matek M10Q-5883 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462900632408643,imageDocid:2309665270382602428,gpcid:7972112619825772177,headlineOfferDocid:3022502616713948710,catalogid:14646175283674404545,productDocid:16540865815889119919,rds:PC_7972112619825772177%7CPROD_PC_7972112619825772177&q=product&sa=X&ved=2ahUKEwjCitLk6vGUAxWXg4kEHR89HP8Qxa4PeggIAggACBIQGw)
). *ArduPilot absolutely requires a compass for multirotor navigation.* 

* **Receiver/Telemetry**: An
  [ExpressLRS (ELRS) 2.4GHz receiver Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:11746844496737932102,headlineOfferDocid:16191106677930397597,productDocid:16191106677930397597,rds:PC_18293031635269104798%7CPROD_PC_18293031635269104798&q=product&sa=X&ved=2ahUKEwjCitLk6vGUAxWXg4kEHR89HP8Qxa4PeggIAggACBIQIA)
. You can utilize the **ELRS AirPort** feature to passthrough MAVLink telemetry over your RC link directly to Mission Planner. 

*

Weight Budget Breakdown 

| Component `[1][2][3][4][5][6]` | Estimated Weight |
| --- | --- |
| Carbon Fiber Frame (3" or 3.5") | 35g - 45g |
| MicoAir H743 V2 AIO | 10g |
| 4x Motors (e.g., 1404) | 36g - 42g |
| Propellers & Hardware | 10g |
| Micro M10 GPS + Compass | 8g |
| FPV Camera + VTX (Analog or Digital Walksnail/O3) | 15g - 35g |
| 4S 750mAh LiPo Battery | 75g - 85g |
| **Total Build Weight** | **~189g to 235g** (Safe sub-250g) |

ArduPilot Software Configuration 

1. **Firmware Flashing**: Flash the ArduPilot Copter firmware via the STM32 Cube Programmer or directly through Mission Planner using the `MicoAir743v2` target.
2. **ESC Configuration**: Because the AIO utilizes AM32 ESC firmware, configure the motor protocol in ArduPilot to **DShot600** or **DShot300**. Enable bidirectional DShot (`SERVO_BLH_BDMASK`) to feed motor RPM data directly into ArduPilot’s dynamic notch filters.
3. **Sensor Alignment**: Wire the external GPS/Compass module to an available I2C port. Calibrate the compass far away from indoor magnetic interference.
4. **Tuning Small Craft**: Micro drones have very low rotational inertia and fast motor response times. Out-of-the-box ArduPilot tunes are intended for larger craft. You **must drop your initial PID values** (specifically `ATC_RAT_RLL_P/I` and `ATC_RAT_PIT_P/I`) by roughly 30–40% before your maiden flight to avoid violent, high-frequency oscillations. 

If you want to move forward with planning, let me know: 

*

* What **FPV video system** you want to use (Analog, Walksnail Avatar, HDZero, or DJI O3/O4).

* Whether your primary goal is **long-range autonomous cruising** or **agile cinematic/freestyle flight**. 

*

I can give you the exact wiring layout or custom ArduPilot parameters for those choices! 

Copy

# Share public link

This public link is valid for 7 days and shares a thread, including any personal information you added. This link or copies made by others cannot be deleted. If you share with third parties, their policies apply.

Can’t copy the link right now. Try again later.

Facebook

Gmail

X

Reddit

WhatsApp

Good response

Bad response

---

## Sources:

[1] Building a sub 250g Autonomous Drone with Ardupilot and .... Opens in new tab.  
https://www.youtube.com/watch?v=u_ArriXbrR0&t=879

[2] MicoAir H743 AIO - Speedybee35 Arducopter Build. Opens in new tab.  
https://www.youtube.com/watch?v=MUv2rEdoiS4&t=415

[3] Getting Started Guide for Ardupilot - MicoAir Tech. Opens in new tab.  
https://micoair.com/docs/getting-started-guide-for-ardupilot/

[4] MicoAir743v2 — Plane documentation - ArduPilot. Opens in new tab.  
https://ardupilot.org/plane/docs/common-MicoAir743v2.html

[5] Installing ArduPilot/PX4/INAV/Betaflight on H743 Flight .... Opens in new tab.  
https://www.youtube.com/watch?v=53Lv2s-gBa8

[6] Sub250 Huma 20 is 2" cinewhoop designed for DJI O4 Air .... Opens in new tab.  
https://www.instagram.com/reel/DIHToiERD52/?hl=en

